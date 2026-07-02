# Release Notes Ingestion Job

A standalone Cloud Run **Job** (not a service — it runs to completion, once
a day, then exits) that copies cloud-provider release notes into a
BigQuery table in **your own project**, so you own the data instead of
querying a public dataset live on every request.

Built as a **provider plugin architecture** so more clouds (AWS, Azure,
...) can be added later without touching the pipeline itself — see
[Adding a new platform](#adding-a-new-platform). Today only **GCP** is
implemented.

```
ingestion/
├── main.py                  # entrypoint — loops over PLATFORMS, calls loader
├── src/
│   ├── config.py             # env vars (PLATFORMS + per-provider config)
│   ├── loader.py             # create-if-needed table + idempotent MERGE load
│   ├── bq_client.py          # destination BigQuery client (ADC)
│   └── providers/
│       ├── base.py           # BaseProvider interface every platform implements
│       ├── __init__.py       # registry: platform name -> provider factory
│       └── gcp.py            # GCPBigQuerySource, GCPRssSource
```

## How it works

1. `main.py` reads `PLATFORMS` (default `GCP`) and, for each platform,
   asks the registry in `src/providers/__init__.py` for a provider
   instance.
2. For that platform, it looks up the current watermark
   (`MAX(published_at) WHERE platform = ...`) in the destination table —
   independently per platform, so adding AWS later doesn't touch GCP's
   incremental state, and vice versa.
3. The provider fetches rows published on/after `watermark - WATERMARK_OVERLAP_DAYS`
   (or a full backfill on that platform's first run).
4. `loader.py` loads the batch into a staging table, tags it with
   `platform` + `source`, and `MERGE`s only genuinely new rows into the
   shared destination table, deduped by a content hash. Every platform's
   rows land in the **same table**, discriminated by the `platform`
   column (see [Destination table schema](#destination-table-schema)).

Every provider returns the same row shape
(`description`, `release_note_type`, `published_at`, `product_name`,
`product_version_name` — `src/providers/base.py::ROW_COLUMNS`), so the
loader and the rest of the pipeline never need to know which platform or
source produced a row.

### GCP provider (the only one implemented today)

Selected by `GCP_SOURCE_MODE`:

| Mode | Source | Reliability |
|------|--------|-------------|
| `bigquery` (default) | `bigquery-public-data.google_cloud_release_notes.release_notes` | Structured columns, same shape this whole app already uses. **Recommended.** |
| `rss` | `https://cloud.google.com/feeds/gcp-release-notes.xml` | Best-effort field mapping — see the caveat in `src/providers/gcp.py`. |

> **Why BigQuery is the default:** the public dataset already has exactly
> the columns this app needs. The RSS feed does not carry a structured
> product/type field, so `GCPRssSource` infers them heuristically from
> the entry title/text. That parser was written without being able to
> fetch a live sample of the feed (the sandboxed environment used to
> build this couldn't reach `cloud.google.com` — outbound access was
> blocked by network policy), so treat `GCP_SOURCE_MODE=rss` as untested
> until you've run it once and checked the "[GCP/rss] sample parsed row"
> line in Cloud Logging against the real feed content.

The job is **idempotent**: every row is deduped by a content hash
(`platform` + `product_name` + `release_note_type` + `published_at` +
`description`) before being merged into the destination table, so
re-running it — even over an overlapping date range, or for a platform
that partially failed last time — never creates duplicates. Safe to run
more often than daily, or re-run manually after a failure, with no
cleanup step.

---

## Adding a new platform

Nothing in `main.py` or `loader.py` needs to change. To add, say, AWS:

1. Create `src/providers/aws.py` with a class implementing `BaseProvider`:

   ```python
   from src.providers.base import BaseProvider

   class AWSWhatsNewSource(BaseProvider):
       platform = "AWS"
       source_id = "rss"  # or "api", "bigquery", whatever it actually is

       def fetch_new_rows(self, since):
           # return a DataFrame with ROW_COLUMNS: description,
           # release_note_type, published_at, product_name,
           # product_version_name
           ...
   ```

2. Register it in `src/providers/__init__.py`:

   ```python
   from src.providers.aws import AWSWhatsNewSource

   @register("AWS")
   def _build_aws_provider(bq_client):
       return AWSWhatsNewSource()
   ```

3. Add it to the schedule: `PLATFORMS=GCP,AWS`.

Two things worth deciding deliberately when you write that provider:

- **`release_note_type` values** — GCP uses `FEATURE / FIX / ISSUE /
  ANNOUNCEMENT / BREAKING_CHANGE / DEPRECATION`. Map AWS/Azure's own
  categories onto this same vocabulary if you want the frontend's type
  filter to keep working uniformly across platforms; introduce new
  values only if there's no reasonable mapping.
- **Whatever feed/API you pull from, verify its actual field layout
  against a live response before trusting it** — don't assume RSS/Atom
  conventions carry over. The GCP RSS caveat above exists precisely
  because that step couldn't be done here.

---

## How the schedule works

There's no publicly documented exact time-of-day when providers refresh
their release-notes data — notes are published throughout the day. Two
things make this a non-issue in practice:

1. The job pulls everything **on/after `MAX(published_at) - WATERMARK_OVERLAP_DAYS`**
   per platform, not just "today" — so even if a run lands a few hours
   before or after a platform's actual update, the next run picks up
   anything that was missed.
2. Because loads are idempotent, running more frequently than daily costs
   nothing extra in correctness — only in the (small) BigQuery job cost.

**Recommended default: once a day at `06:00 UTC`.** This is late enough
in the UTC day to have absorbed a full US business day's worth of
publishing from the day before, and paired with the overlap window it's
self-healing if that assumption is ever wrong. If you want tighter
freshness, drop the Cloud Scheduler cron to every 6 hours (`0 */6 * * *`)
— it's safe to do so.

---

## Local test run

```bash
cd ingestion
uv pip install -r requirements.txt   # or: pip install -r requirements.txt
gcloud auth application-default login

cp .env.example .env   # edit DEST_PROJECT_ID at minimum
export $(grep -v '^#' .env | xargs)

python main.py
```

First run backfills up to `INITIAL_BACKFILL_DAYS` (default 730) for any
platform using `GCPBigQuerySource`, and creates
`DEST_DATASET_ID.DEST_TABLE_ID` in `DEST_PROJECT_ID` if it doesn't
already exist.

---

## Deploy to Cloud Run Jobs + Cloud Scheduler

Everything below is `gcloud` — nothing here has been applied for you, run
it yourself against your own project.

### 0. Variables

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export JOB_NAME=cloud-release-notes-ingest
export DEST_DATASET_ID=cloud_release_notes
export DEST_TABLE_ID=release_notes
```

### 1. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT_ID"
```

### 2. Create a service account for the job itself

This identity runs the ingestion code — it needs to create/write your
destination dataset and table, and run BigQuery jobs (billed to
`$PROJECT_ID`). GCP's public source dataset is already world-readable, so
no extra grant is needed to read it; a future non-BigQuery provider (e.g.
an AWS feed reached over plain HTTPS) wouldn't need any GCP-side grant
either.

```bash
gcloud iam service-accounts create cloud-rn-ingest \
  --display-name="Cloud Release Notes Ingestion Job" \
  --project "$PROJECT_ID"

INGEST_SA="cloud-rn-ingest@${PROJECT_ID}.iam.gserviceaccount.com"

# Lets the job create the destination dataset/table and write rows.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${INGEST_SA}" \
  --role="roles/bigquery.dataEditor"

# Lets the job run query/load/merge jobs, billed to $PROJECT_ID.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${INGEST_SA}" \
  --role="roles/bigquery.jobUser"
```

### 3. Build and deploy the Cloud Run Job

`gcloud run jobs deploy --source` builds the container with Cloud Build
and deploys it in one step — no manual Artifact Registry push needed.

```bash
gcloud run jobs deploy "$JOB_NAME" \
  --source=./ingestion \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --service-account="$INGEST_SA" \
  --set-env-vars="PLATFORMS=GCP,GCP_SOURCE_MODE=bigquery,DEST_PROJECT_ID=${PROJECT_ID},DEST_DATASET_ID=${DEST_DATASET_ID},DEST_TABLE_ID=${DEST_TABLE_ID}" \
  --max-retries=2 \
  --task-timeout=900 \
  --memory=512Mi
```

Run it once manually to confirm it works (and to do the initial
backfill) before wiring up the schedule:

```bash
gcloud run jobs execute "$JOB_NAME" --region="$REGION" --project="$PROJECT_ID" --wait
```

Check logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}" \
  --project="$PROJECT_ID" --limit=50 --format="value(textPayload)"
```

### 4. Create a service account for Cloud Scheduler to invoke the job

Separate, minimal identity — its only job is to trigger the job execution.

```bash
gcloud iam service-accounts create cloud-rn-scheduler \
  --display-name="Cloud Release Notes Scheduler Invoker" \
  --project "$PROJECT_ID"

SCHEDULER_SA="cloud-rn-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud run jobs add-iam-policy-binding "$JOB_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker"
```

If job creation in the next step fails with a permission error, Cloud
Scheduler's own service agent may need explicit rights to mint tokens as
`$SCHEDULER_SA`:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

gcloud iam service-accounts add-iam-policy-binding "$SCHEDULER_SA" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### 5. Create the Cloud Scheduler job

Triggers a run by POSTing to the Cloud Run Jobs REST API's `:run` endpoint.

```bash
gcloud scheduler jobs create http "${JOB_NAME}-schedule" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --schedule="0 6 * * *" \
  --time-zone="UTC" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --http-method=POST \
  --oauth-service-account-email="$SCHEDULER_SA"
```

Test it fires correctly on demand:

```bash
gcloud scheduler jobs run "${JOB_NAME}-schedule" --location="$REGION" --project="$PROJECT_ID"
```

### 6. Redeploy after code changes (e.g. after adding a new platform)

```bash
gcloud run jobs deploy "$JOB_NAME" --source=./ingestion --region="$REGION" --project="$PROJECT_ID"
```

Then widen the schedule to include it, e.g.:

```bash
gcloud run jobs update "$JOB_NAME" \
  --region="$REGION" --project="$PROJECT_ID" \
  --update-env-vars="PLATFORMS=GCP,AWS"
```

### 7. Tear down

```bash
gcloud scheduler jobs delete "${JOB_NAME}-schedule" --location="$REGION" --project="$PROJECT_ID"
gcloud run jobs delete "$JOB_NAME" --region="$REGION" --project="$PROJECT_ID"
```

---

## Switching the GCP provider to RSS

```bash
gcloud run jobs update "$JOB_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --update-env-vars="GCP_SOURCE_MODE=rss"
```

Run it once manually and check the logs (`[GCP/rss] sample parsed row`)
before trusting it on a schedule — see the caveat above.

---

## Environment variables

| Var | Default | Meaning |
|-----|---------|---------|
| `PLATFORMS` | `GCP` | Comma-separated platform list, e.g. `GCP,AWS,AZURE` — each needs a registered provider |
| `GCP_SOURCE_MODE` | `bigquery` | `bigquery` or `rss` — which GCP provider to use |
| `GCP_SOURCE_PROJECT_ID` | `bigquery-public-data` | Public source project |
| `GCP_SOURCE_DATASET_ID` | `google_cloud_release_notes` | Public source dataset |
| `GCP_SOURCE_TABLE_ID` | `release_notes` | Public source table |
| `GCP_RSS_FEED_URL` | `https://cloud.google.com/feeds/gcp-release-notes.xml` | Feed URL, used when `GCP_SOURCE_MODE=rss` |
| `DEST_PROJECT_ID` | *(required, or `PROJECT_ID`)* | Your project — where rows land and jobs are billed |
| `DEST_DATASET_ID` | `cloud_release_notes` | Destination dataset (created if missing), shared across all platforms |
| `DEST_TABLE_ID` | `release_notes` | Destination table (created if missing), shared across all platforms |
| `DEST_LOCATION` | `US` | BigQuery dataset location |
| `WATERMARK_OVERLAP_DAYS` | `3` | Days of overlap re-pulled each run per platform, to self-heal missed/late notes |
| `INITIAL_BACKFILL_DAYS` | `730` | How far back to backfill on a platform's first run (only meaningful for deep-history sources like GCP's BigQuery provider) |

## Destination table schema

```
row_hash               STRING    -- sha256 dedup key (platform+product+type+date+description), not from the source
platform               STRING    -- "GCP", "AWS", "AZURE", ... -- clustered
description            STRING
release_note_type      STRING    -- clustered
published_at           DATE      -- partitioned on this column
product_name           STRING    -- clustered
product_version_name   STRING
source                 STRING    -- provider.source_id, e.g. "bigquery" or "rss"
ingested_at            TIMESTAMP
```

To point `backend/.env` at your own ingested table instead of the public
dataset, set `DATA_PROJECT_ID=$PROJECT_ID`, `DATASET_ID=$DEST_DATASET_ID`,
`TABLE_ID=$DEST_TABLE_ID`. Note the backend's `query_release_notes()`
doesn't currently filter or expose the `platform` column — that's a
frontend/backend change, out of scope for this ingestion job.
