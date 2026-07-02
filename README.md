# GCP Release Notes Navigator

A web app for browsing, filtering, and analyzing Google Cloud release notes from the BigQuery public dataset. Built for developers, data engineers, and cloud architects who need to track breaking changes, deprecations, and new features across GCP products.

---

## Architecture

```
Browser
  │
  ▼
frontend/    Streamlit + nginx    port 8080 (container) → 8081 (host, dev)
  │
  ▼
backend/     FastAPI              port 8000
  │
  ├──▶ BigQuery          bigquery-public-data.google_cloud_release_notes.release_notes
  └──▶ LLM               Docker Model Runner — llama3.2 (local) / Cloud Run GPU (remote)
```

Both services run as Docker containers orchestrated by Docker Compose. For production,
they deploy as Cloud Run services via `gcloud run compose up`.

---

## Features

- **Search** – Full-text keyword search across release note descriptions
- **Filter** – By product, note type (FEATURE, FIX, BREAKING\_CHANGE, DEPRECATION, …), and date range
- **Notes tab** – Paginated cards with product, badge, date, and description
- **Insights tab** – Charts: release volume by month, type distribution, top products, activity heatmap
- **Breaking changes banner** – Surfaces BREAKING\_CHANGE notes that match the active filters
- **Watchlist** – Save favourite products; auto-applied on the next visit
- **Ask AI** – Natural-language Q&A grounded in the current result set (llama3.2)
- **Export** – Download visible notes as CSV or JSON; shareable filter URLs

---

## Local Development

### Prerequisites

- **Docker Desktop 4.40+** with Model Runner enabled:
  ```bash
  docker desktop enable model-runner --tcp 12434
  ```
- A GCP project with billing enabled (queries against the public dataset are billed to your project)
- `gcloud` CLI for generating credentials

### 1. Clone

```bash
git clone https://github.com/bricefotzo/gcp-release-notes.git
cd gcp-release-notes
```

### 2. Configure credentials

The backend uses [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) — no service account JSON key required locally.

```bash
gcloud auth application-default login
cp ~/.config/gcloud/application_default_credentials.json adc.json
```

The override file mounts `adc.json` (or `$ADC_PATH` if set) read-only into the backend
container and points `GOOGLE_APPLICATION_CREDENTIALS` at it automatically.

### 3. Configure the backend environment

Edit `backend/.env` (create it from the template below if it doesn't exist):

```dotenv
# GCP project that will be billed for BigQuery query jobs
PROJECT_ID=your-gcp-project-id

# Public dataset coordinates — leave these as-is
DATA_PROJECT_ID=bigquery-public-data
DATASET_ID=google_cloud_release_notes
TABLE_ID=release_notes

# LLM model served by Docker Model Runner
LLM_MODEL=ai/llama3.2
```

> `LLM_URL` is injected automatically by the Docker Compose `models:` key — do not set it manually.

### 4. Start in watch mode

```bash
docker compose watch
```

| Service      | URL                          |
|--------------|------------------------------|
| Frontend     | http://localhost:8081         |
| Backend API  | http://localhost:8000         |
| API docs     | http://localhost:8000/docs    |

`compose watch` syncs Python/CSS/asset changes into running containers without a rebuild.
Streamlit detects changed files and reloads the UI automatically; uvicorn reloads the API.
Editing `requirements.txt` or a `Dockerfile` triggers a full rebuild.

**Standard start (no file watching):**
```bash
docker compose up --build
```

---

## Cloud Run Deployment

`gcloud run compose` reads your `compose.yaml`, builds images, pushes them to Artifact Registry,
and deploys each service as a Cloud Run service — including the LLM as a GPU-backed Cloud Run
model service via the `x-google-cloudrun` extension fields.

> Reference: [gcloud run compose up — deploy a multi-service GPU stack to Cloud Run from Docker Compose](https://medium.com/@bricefotzo/gcloud-run-compose-up-deploy-a-multi-service-gpu-stack-to-cloud-run-from-docker-compose-77d650b39972)

### 1. Enable required APIs

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1   # pick any Cloud Run region

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT_ID"
```

### 2. Authenticate and configure gcloud

```bash
gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

# Allow Docker to push images to Artifact Registry
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

### 3. Create a service account for the backend

On Cloud Run, ADC is satisfied by the service account attached to the Cloud Run service —
no JSON key is needed.

```bash
# Create the service account
gcloud iam service-accounts create gcp-rn-backend \
  --display-name="GCP Release Notes Backend" \
  --project "$PROJECT_ID"

SA="gcp-rn-backend@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant BigQuery read access (the public dataset is free to read,
# but query jobs are billed to PROJECT_ID)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/bigquery.jobUser"
```

### 4. Deploy

```bash
gcloud run compose up
```

This single command:
1. Builds the `front` and `back` Docker images
2. Pushes them to Artifact Registry
3. Deploys `front`, `back`, and the `llm` model as Cloud Run services
4. Wires service-to-service networking automatically

When the command completes, gcloud prints the public URL of the `front` service.

To attach the service account created above to the backend service after the first deploy:

```bash
gcloud run services update back \
  --service-account="${SA}" \
  --region="$REGION" \
  --project="$PROJECT_ID"
```

### 5. Redeploy after changes

```bash
gcloud run compose up
```

Re-running the same command rebuilds changed images and rolls out new Cloud Run revisions in-place.

### 6. Tear down

```bash
# Delete Cloud Run services
gcloud run compose down

# Delete container images from Artifact Registry (optional)
gcloud artifacts repositories list --project "$PROJECT_ID"
gcloud artifacts repositories delete REPO_NAME \
  --location="$REGION" \
  --project="$PROJECT_ID"
```

---

## Project Structure

```
gcp-release-notes/
├── frontend/
│   ├── main.py              # Streamlit UI — single file, top-to-bottom execution
│   ├── src/utils.py         # HTML formatting helpers, badge/type CSS mappers
│   ├── assets/style.css     # All custom CSS (loaded once at startup)
│   ├── nginx.conf           # Reverse proxy: port 8080 → Streamlit on 8501
│   ├── start.sh             # Entrypoint: starts Streamlit, then nginx
│   ├── Dockerfile
│   └── requirements.txt
├── backend/
│   ├── app.py               # FastAPI endpoints
│   ├── src/ai.py            # LLM wrappers: summarize_release_notes(), generate_sql_query()
│   ├── src/queries.py       # BigQuery query builders
│   ├── src/bq.py            # BigQuery client — ADC-based, no JSON key needed
│   ├── src/config.py        # Env var wrappers for BQ table coordinates
│   ├── .env                 # Local environment variables (not committed)
│   ├── Dockerfile
│   └── requirements.txt
├── ingestion/
│   ├── main.py               # Entrypoint for the Cloud Run Job — loops over PLATFORMS
│   ├── src/providers/        # BaseProvider interface + one module per cloud (gcp.py today)
│   ├── src/loader.py         # Create-if-needed table + idempotent MERGE load
│   ├── README.md             # Full deployment guide (Cloud Run Jobs + Cloud Scheduler)
│   ├── Dockerfile
│   └── requirements.txt
├── compose.yaml             # Base Compose config (used for production and local)
├── compose.override.yaml    # Dev overrides: watch mode + ADC credential mount
└── .github/workflows/       # CI/CD pipeline
```

---

## Data Ingestion

A separate Cloud Run Job (`ingestion/`) syncs release notes into a
BigQuery table in your own project on a daily schedule, so the app can
optionally run against owned data instead of querying the public dataset
live. It's built as a provider plugin architecture (`ingestion/src/providers/`)
so more clouds — AWS, Azure, etc. — can be added as new provider modules
without touching the pipeline; only GCP is implemented today. Rows from
every platform land in one shared table, discriminated by a `platform`
column. See [`ingestion/README.md`](ingestion/README.md) for the full
`gcloud` deployment guide and the steps to add a new platform — it
deploys and schedules independently of the frontend/backend services
above.

---

## Data Source

| Field                  | Value                                                        |
|------------------------|--------------------------------------------------------------|
| Dataset                | `bigquery-public-data.google_cloud_release_notes.release_notes` |
| Key fields             | `description`, `release_note_type`, `published_at`, `product_name`, `product_version_name` |
| Release note types     | FEATURE · FIX · ISSUE · ANNOUNCEMENT · BREAKING\_CHANGE · DEPRECATION |
| Access                 | Public, read-only — queries are billed to your own project    |

---

## License

Use and modify as you like. Release note data is from Google Cloud's public BigQuery datasets.
