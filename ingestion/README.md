# Release Notes Ingestion Job

A standalone Cloud Run **Job** (not a service — it runs to completion, once
a day, then exits) that copies Google Cloud release notes into a BigQuery
table in **your own project**, so you own the data instead of querying the
public dataset live on every request.

It supports two sources, selected by `SOURCE_MODE`:

| Mode | Source | Reliability |
|------|--------|-------------|
| `bigquery` (default) | `bigquery-public-data.google_cloud_release_notes.release_notes` | Structured columns, same shape this whole app already uses. **Recommended.** |
| `rss` | `https://cloud.google.com/feeds/gcp-release-notes.xml` | Best-effort field mapping — see the caveat below before relying on it. |

> **Why BigQuery is the default:** the public dataset already has exactly
> the columns this app needs (`description`, `release_note_type`,
> `published_at`, `product_name`, `product_version_name`). The RSS feed
> does not carry a structured product/type field, so `rss_source.py`
> infers them heuristically from the entry title/text. That parser was
> written without being able to fetch a live sample of the feed (the
> sandboxed environment used to build this couldn't reach
> `cloud.google.com` — outbound access was blocked by network policy), so
> treat `SOURCE_MODE=rss` as untested until you've run it once and checked
> the "RSS source: sample parsed row" line in Cloud Logging against the
> real feed content. Adjust `ingestion/src/sources/rss_source.py::_parse_entry`
> if the mapping is off.

The job is **idempotent**: every row is deduped by a content hash
(`product_name` + `release_note_type` + `published_at` + `description`)
before being merged into the destination table, so re-running it — even
over an overlapping date range — never creates duplicates. That means it's
safe to run more often than daily, or to re-run manually after a failure,
without any cleanup step.

---

## How the schedule works

There's no publicly documented exact time-of-day when Google refreshes the
`google_cloud_release_notes` public dataset or posts to the RSS feed —
notes are published throughout the day. Two things make this a non-issue
in practice:

1. The job pulls everything **on/after `MAX(published_at) - WATERMARK_OVERLAP_DAYS`**
   (default 3 days of overlap) from your own table, not just "today" — so
   even if a run lands a few hours before or after Google's actual update,
   the next day's run picks up anything that was missed.
2. Because loads are idempotent, running more frequently than daily costs
   nothing extra in correctness — only in the (small) BigQuery job cost.

**Recommended default: once a day at `06:00 UTC`.** This is late enough
in the UTC day to have absorbed a full US business day's worth of
publishing from the day before, and paired with the 3-day overlap window
it's self-healing if that assumption is ever wrong. If you want tighter
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

First run backfills up to `INITIAL_BACKFILL_DAYS` (default 730) when
`SOURCE_MODE=bigquery`, and creates `DEST_DATASET_ID.DEST_TABLE_ID` in
`DEST_PROJECT_ID` if it doesn't already exist.

---

## Deploy to Cloud Run Jobs + Cloud Scheduler

Everything below is `gcloud` — nothing here has been applied for you, run
it yourself against your own project.

### 0. Variables

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export JOB_NAME=gcp-release-notes-ingest
export DEST_DATASET_ID=gcp_release_notes
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
`$PROJECT_ID`). The public source dataset is already world-readable, so
no extra grant is needed to read it.

```bash
gcloud iam service-accounts create gcp-rn-ingest \
  --display-name="GCP Release Notes Ingestion Job" \
  --project "$PROJECT_ID"

INGEST_SA="gcp-rn-ingest@${PROJECT_ID}.iam.gserviceaccount.com"

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
  --set-env-vars="SOURCE_MODE=bigquery,DEST_PROJECT_ID=${PROJECT_ID},DEST_DATASET_ID=${DEST_DATASET_ID},DEST_TABLE_ID=${DEST_TABLE_ID}" \
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
gcloud iam service-accounts create gcp-rn-scheduler \
  --display-name="GCP Release Notes Scheduler Invoker" \
  --project "$PROJECT_ID"

SCHEDULER_SA="gcp-rn-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

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

### 6. Redeploy after code changes

```bash
gcloud run jobs deploy "$JOB_NAME" --source=./ingestion --region="$REGION" --project="$PROJECT_ID"
```

### 7. Tear down

```bash
gcloud scheduler jobs delete "${JOB_NAME}-schedule" --location="$REGION" --project="$PROJECT_ID"
gcloud run jobs delete "$JOB_NAME" --region="$REGION" --project="$PROJECT_ID"
```

---

## Switching to the RSS source

```bash
gcloud run jobs update "$JOB_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --update-env-vars="SOURCE_MODE=rss"
```

Run it once manually and check the logs (`RSS source: sample parsed row`)
before trusting it on a schedule — see the caveat at the top of this file.

---

## Environment variables

| Var | Default | Meaning |
|-----|---------|---------|
| `SOURCE_MODE` | `bigquery` | `bigquery` or `rss` |
| `SOURCE_PROJECT_ID` | `bigquery-public-data` | Public source project |
| `SOURCE_DATASET_ID` | `google_cloud_release_notes` | Public source dataset |
| `SOURCE_TABLE_ID` | `release_notes` | Public source table |
| `RSS_FEED_URL` | `https://cloud.google.com/feeds/gcp-release-notes.xml` | Feed URL, used when `SOURCE_MODE=rss` |
| `DEST_PROJECT_ID` | *(required, or `PROJECT_ID`)* | Your project — where rows land and jobs are billed |
| `DEST_DATASET_ID` | `gcp_release_notes` | Destination dataset (created if missing) |
| `DEST_TABLE_ID` | `release_notes` | Destination table (created if missing) |
| `DEST_LOCATION` | `US` | BigQuery dataset location |
| `WATERMARK_OVERLAP_DAYS` | `3` | Days of overlap re-pulled each run, to self-heal missed/late notes |
| `INITIAL_BACKFILL_DAYS` | `730` | How far back to backfill on first run (BigQuery mode only) |

## Destination table schema

```
row_hash               STRING    -- sha256 dedup key, not from the source
description            STRING
release_note_type      STRING    -- clustered
published_at           DATE      -- partitioned on this column
product_name           STRING    -- clustered
product_version_name   STRING
source                 STRING    -- "bigquery" or "rss"
ingested_at            TIMESTAMP
```

To point `backend/.env` at your own ingested table instead of the public
dataset, set `DATA_PROJECT_ID=$PROJECT_ID`, `DATASET_ID=$DEST_DATASET_ID`,
`TABLE_ID=$DEST_TABLE_ID`.
