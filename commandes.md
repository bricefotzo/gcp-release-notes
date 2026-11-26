# Talk — `gcloud run compose up`


**Sommaire :** 

- [1. Setup](#1-setup) 
- [2. Local](#2-local)
- [3. Déployer](#3-déployer)
- [4. SSH](#4-ssh)
- [5. LLM_URL](#5-llm_url)
- [6. URL personnalisée](#6-url-personnalisée)
- [7. GPU](#7-gpu)
- [8. Cycle de vie](#8-cycle-de-vie-du-modèle)
- [9. Bucket GCS](#9-préparer-le-bucket-gcs)
- [10. Monter GCS](#10-monter-les-modèles-depuis-gcs)
- [11. Scaling](#11-scaling-de-llm)
- [12. Vérifier GCS](#12-vérifier-les-modèles-sur-gcs)
- [13. Services compose](#13-services-créés-par-compose)
- [14. Nettoyage](#14-nettoyage)


---

## 1. Setup

Configurer le projet GCP :

```bash
gcloud config set project serial-techos
```

Configurer la région Cloud Run :

```bash
gcloud config set run/region europe-west1
```

---

## 2. Local

Lancer la stack en local (frontend + backend + DMR) :

```bash
docker compose up --build
```

Vérifier les modèles disponibles dans Docker Model Runner :

```bash
docker model ls
```

---

## 3. Déployer

Déployer tout le `compose.yaml` sur Cloud Run :

```bash
gcloud run compose up
```

Lister les services Cloud Run créés :

```bash
gcloud run services list --filter="metadata.labels.managed-by:runcompose"
```

Voir les dernières révisions du service `llm` :

```bash
gcloud run revisions list --service llm --limit 3
```

---

## 4. SSH

Activer SSH sur `gcp-release-notes` :

```bash
gcloud beta run services update gcp-release-notes --ssh
```

Activer SSH sur `llm` :

```bash
gcloud beta run services update llm --ssh
```

Ouvrir une session SSH dans le conteneur `back` :

```bash
gcloud beta run services ssh gcp-release-notes --container=back
```

**🔐 SSH (`back`)** — Tester le healthcheck interne :

```bash
curl localhost:8000/health
```

**🔐 SSH (`back`)** — Quitter la session :

```bash
exit
```

---

## 5. `LLM_URL`

Récupérer et afficher l'URL du service `llm` :

```bash
export LLM_URL=$(gcloud run services describe llm --format='value(status.url)') && echo "$LLM_URL"
```

Tester `/chat/completions` sans `/v1` *(→ attendu : `404`)* :

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$LLM_URL/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai/gemma4:e4b","messages":[{"role":"user","content":"Bonjour"}],"max_tokens":20}'
```

Tester `/v1/chat/completions` *(→ attendu : `200`)* :

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$LLM_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai/gemma4:e4b","messages":[{"role":"user","content":"Bonjour"}],"max_tokens":20}'
```

---

## 6. URL personnalisée

Mapper le domaine de l'app (`demo-news.cloud.run`) :

```bash
gcloud beta run domain-mappings create --service gcp-release-notes --domain demo-news.cloud.run
```

Mapper le domaine du LLM (`demo-llm-dmr.cloud.run`) :

```bash
gcloud beta run domain-mappings create --service llm --domain demo-llm-dmr.cloud.run
```

Vérifier les domain mappings actifs :

```bash
gcloud beta run domain-mappings list
```

---

## 7. GPU

Vérifier dans les logs que `:latest` tourne sur CPU *(→ `"no usable GPU found"`)* :

```bash
gcloud logging read 'resource.labels.service_name="llm" AND "no usable GPU found"' \
  --freshness=7d --limit 5 --format='value(timestamp,textPayload)'
```

Passer `llm` sur l'image CUDA :

```bash
gcloud run services update llm --image=docker/model-runner:v1.2.8-cuda
```

---

## 8. Cycle de vie du modèle

Montrer le cold start / re-téléchargement du modèle dans les logs :

```bash
gcloud logging read 'resource.labels.service_name="llm" AND ("Starting new instance" OR "model not found in local store" OR "Shutdown signal received")' \
  --freshness=7d --limit 20 --format='value(timestamp,textPayload)'
```

---

## 9. Préparer le bucket GCS

Définir le bucket et le tag du modèle :

```bash
export B=gs://serial-techos-dmr-models
export TAG=docker.io/ai/gemma4:e4b
```

Afficher `models.json` dans le bucket :

```bash
gcloud storage cat $B/models.json
```

Extraire l'identifiant SHA256 du modèle :

```bash
export ID=$(gcloud storage cat $B/models.json | python3 -c "import json,sys; print(next(m['id'] for m in json.load(sys.stdin)['models'] if '$TAG' in m['tags']).split(':')[1])") && echo "ID=$ID"
```

Afficher le manifest du modèle :

```bash
gcloud storage cat $B/manifests/sha256/$ID
```

Construire le bundle dans `bundles/sha256/$ID/` :

```bash
gcloud storage cat $B/manifests/sha256/$ID \
  | python3 -c "import json,sys; m=json.load(sys.stdin); print(m['config']['digest'][7:], 'config.json'); [print(l['digest'][7:], 'model/'+l['annotations']['org.cncf.model.filepath']) for l in m['layers']]" \
  | while read DIGEST FILE; do gcloud storage cp $B/blobs/sha256/$DIGEST $B/bundles/sha256/$ID/$FILE; done
```

Vérifier l'arborescence des bundles générés :

```bash
gcloud storage ls -r $B/bundles/
```

---

## 10. Monter les modèles depuis GCS

Monter le bucket GCS en lecture seule sur `/models` dans `llm` :

```bash
gcloud run services update llm \
  --add-volume='name=models,type=cloud-storage,bucket=serial-techos-dmr-models,readonly=true,mount-options=uid=994;gid=994' \
  --add-volume-mount='volume=models,mount-path=/models'
```

---

## 11. Scaling de `llm`

Garder 1 instance chaude et allonger le timeout :

```bash
gcloud run services update llm --min-instances=1 --max-instances=1 --timeout=300
```

---

## 12. Vérifier les modèles sur GCS

Lister la racine du bucket :

```bash
gcloud storage ls gs://serial-techos-dmr-models/
```

Lister les bundles SHA256 :

```bash
gcloud storage ls gs://serial-techos-dmr-models/bundles/sha256/
```

Ouvrir une session SSH sur `llm` :

```bash
gcloud beta run services ssh llm
```

**🔐 SSH (`llm`)** — Vérifier le montage GCS sur `/models` :

```bash
mount | grep /models
```

**🔐 SSH (`llm`)** — Lister les bundles montés :

```bash
ls /models/bundles
```

**🔐 SSH (`llm`)** — Quitter la session :

```bash
exit
```

Vérifier les modèles exposés par l'API `llm` :

```bash
curl -s https://demo-llm-dmr.cloud.run/models
```

---

## 13. Services créés par compose

Filtrer uniquement les services managés par `gcloud run compose` :

```bash
gcloud run services list --filter='metadata.labels.managed-by=runcompose'
```

---

## 14. Nettoyage

Couper le `min-instances` sur `llm` *(important pour la facture GPU)* :

```bash
gcloud run services update llm --min-instances=0
```

Supprimer le domain mapping `demo-news.cloud.run` :

```bash
gcloud beta run domain-mappings delete --domain demo-news.cloud.run --quiet
```

Supprimer le domain mapping `demo-llm-dmr.cloud.run` :

```bash
gcloud beta run domain-mappings delete --domain demo-llm-dmr.cloud.run --quiet
```

Supprimer le service `gcp-release-notes` :

```bash
gcloud run services delete gcp-release-notes --quiet
```

Supprimer le service `llm` :

```bash
gcloud run services delete llm --quiet
```
