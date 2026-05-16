# GCP Release Notes Navigator — CLAUDE.md

## What this project is

A web app for browsing, filtering, and analyzing GCP release notes stored in the BigQuery public dataset `bigquery-public-data.google_cloud_release_notes.release_notes`. Target audience: developers, data engineers, cloud architects who need to track breaking changes, deprecations, and new features across GCP products.

---

## Architecture

```
browser
  │
  ▼
frontend/          Streamlit app (port 8080)
  │  talks to ──▶ backend/           FastAPI app (port 8000)
                    │  talks to ──▶ BigQuery   (public dataset, read-only)
                    │  talks to ──▶ Docker Model Runner  (local LLM, port 12434)
```

Both services run as Docker containers orchestrated by `compose.yaml`. In dev mode, `compose watch` syncs file changes without rebuilding.

---

## Running the app

```bash
# Start everything (dev mode with live sync)
docker compose watch

# Or just start without watch
docker compose up --build

# Frontend only:  http://localhost:8080
# Backend API:    http://localhost:8000
# API docs:       http://localhost:8000/docs
```

### Prerequisites
- Docker Desktop 4.40+ with **Model Runner enabled**:
  ```bash
  docker desktop enable model-runner --tcp 12434
  ```
- `backend/.env` with BigQuery config (defaults to the public dataset):
  ```
  PROJECT_ID=bigquery-public-data
  DATASET_ID=google_cloud_release_notes
  TABLE_ID=release_notes
  LLM_MODEL=ai/smollm2
  ```
- `credentials.json` in repo root — GCP service account JSON key (mounted read-only into the backend container). Alternatively set `GCP_SERVICE_ACCOUNT_JSON` env var with the JSON inline.

---

## Key files

| Path | Role |
|------|------|
| `frontend/main.py` | Entire Streamlit UI — single file, top-to-bottom execution |
| `frontend/assets/style.css` | All custom CSS (loaded via `st.markdown` at startup) |
| `frontend/src/utils.py` | HTML formatting helpers and badge/type CSS mappers |
| `backend/app.py` | All FastAPI endpoints |
| `backend/src/ai.py` | LLM wrappers: `generate_sql_query()` and `summarize_release_notes()` |
| `backend/src/queries.py` | BigQuery query builders (`query_release_notes`, `load_product_names`, etc.) |
| `backend/src/bq.py` | BigQuery client initialization (env-based auth) |
| `backend/src/config.py` | Env var wrappers for BQ table coordinates |
| `compose.yaml` | Docker Compose config (services + Docker Model Runner `models:` key) |
| `.github/workflows/deploy.yaml` | CI/CD to Koyeb (deploys on every push, also on a daily cron) |

---

## Frontend conventions

### Streamlit execution model
`frontend/main.py` runs top-to-bottom on every user interaction. Session state is the only way to preserve values across reruns.

**Key session state keys:**
| Key | Purpose |
|-----|---------|
| `watchlist` | List of saved product names (persisted to `watchlist.json`) |
| `_products_select` | Backing state for the product multiselect widget |
| `_types_select` | Backing state for the type multiselect widget |
| `_watchlist_applied` | Flag — watchlist auto-applied on first load only |
| `_prev_last_visit` | ISO date string of the user's previous session |
| `_ai_q` | Current AI question text area value |

**Execution order within the script:**
1. CSS + JS component injection
2. Session state init (watchlist, last-visit, apply-stack trigger)
3. `load_filter_options()` (cached API call)
4. URL param loading (shareable links)
5. Sidebar renders (`with st.sidebar:`)
6. Hero header
7. Fetch release notes + breaking changes banner
8. Tabs (`st.tabs`) then tab content

### HTML in Streamlit — critical gotcha
`st.markdown(unsafe_allow_html=True)` passes HTML through React's `dangerouslySetInnerHTML` **which is sanitized by DOMPurify**. This means:
- **`onclick` handlers are stripped** — never put JS event handlers in `st.markdown` HTML
- **`data-*` attributes survive** — safe to use for data payloads
- **`<script>` tags are stripped**

**Pattern for JS that needs to interact with rendered HTML:**
Use a single `st.components.v1.html(script, height=0)` that accesses `window.parent.document` via same-origin iframe access, then adds delegated event listeners. See the copy-button setup near the top of `main.py`.

### Clipboard API gotcha
`navigator.clipboard.writeText()` requires the calling document to be focused. Since our JS runs in an `about:srcdoc` iframe, calls from there fail with `NotAllowedError: Document is not focused`.

**Fix:** create a temporary `textarea` in the **parent** document, focus + select it, then call `parentDoc.execCommand('copy')`. This sidesteps the focus requirement entirely. See `copyViaTextarea()` in `main.py`.

### CSS patterns
- All CSS lives in `frontend/assets/style.css`, loaded once at startup via `st.markdown`
- CSS variables are defined on `:root` — always use them instead of hardcoding colors
- Use `!important` on overrides for Streamlit's internal elements (unavoidable)
- Streamlit test IDs to know: `stSidebar`, `stHorizontalBlock`, `stTextInput`, `stMultiSelect`, `stDateInput`, `stDownloadButton`

### URL params (shareable links)
Filters are encoded as `?p=Product&t=Type&start=YYYY-MM-DD&end=YYYY-MM-DD` (multi-value: `?p=BigQuery&p=Cloud+Run`). Read with `st.query_params.get_all("p")` — use try/except for older Streamlit compatibility. Applied once on first load via the `_url_loaded` flag.

### Persistent files (within container lifetime)
| File | Contents |
|------|----------|
| `frontend/watchlist.json` | `["BigQuery", "Cloud Run", ...]` |
| `frontend/last_visit.json` | `{"date": "2026-04-17"}` |

These reset on container restart. For production persistence, replace with a database or external store.

---

## Backend conventions

### Endpoint layout (`backend/app.py`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness probe |
| GET | `/api/filter-options` | Products, types, date range (loaded at startup, cached in memory) |
| GET | `/api/release-notes` | Paginated, filtered release notes |
| GET | `/api/insights/*` | Time series, type distribution, top products, heatmap |
| GET | `/api/ai/health` | Check if model runner has the model loaded |
| POST | `/api/ai/chat` | Natural-language Q&A grounded in release notes |
| POST | `/api/ai/generate-sql` | SQL generation from NL (legacy) |
| POST | `/api/ai/query` | SQL generation + execution (legacy) |

### AI module (`backend/src/ai.py`)
The LLM is accessed via an OpenAI-compatible HTTP API served by Docker Desktop Model Runner. The `OpenAI` client is initialized at module load with `base_url=LLM_URL`. Two main functions:
- `summarize_release_notes(question, notes_df, shown, total)` — fetches up to 100 notes, strips HTML, sends to LLM with a system prompt instructing structured, actionable answers
- `generate_sql_query(question, table_id, schema)` — legacy SQL generation

`LLM_URL` is injected automatically by Docker Compose's `models:` key. `LLM_MODEL` comes from `backend/.env`.

### BigQuery
The dataset is public and read-only. Schema:
```
description           STRING
release_note_type     STRING   (FEATURE, FIX, ISSUE, ANNOUNCEMENT, BREAKING_CHANGE, DEPRECATION)
published_at          DATE
product_name          STRING
product_version_name  STRING
```

`query_release_notes()` in `backend/src/queries.py` builds parameterised WHERE clauses by string interpolation (no native BQ parameterised query API is used). Be careful with user input — always go through this function, never build raw SQL in endpoints.

### Startup
`bq_client` and `table_name` are module-level globals initialized to `None` and set in the FastAPI `lifespan()` context manager. The linter flags these as `None` type on every reference — this is a false positive, they are always set before any request is served.

---

## Deployment

Deployed to **Koyeb** via `koyeb/action-git-deploy`. Triggers on every push to any branch and on a daily cron at 09:25 UTC. Only the backend is deployed (Koyeb serves port 8000). The `GOOGLE_API_KEY` secret must be set in the GitHub repo secrets.

---

## What NOT to do

- **Do not add `onclick` or `<script>` to `st.markdown` HTML** — they are stripped silently
- **Do not call `navigator.clipboard.writeText()` from inside a `components.html` iframe** — use the `execCommand` + textarea trick
- **Do not set `st.session_state[widget_key]` after the widget has already rendered** in the current run — set it before the widget renders (or trigger a `st.rerun()`)
- **Do not add a new backend endpoint just to do filtering** — the existing `/api/release-notes` endpoint accepts all filter params as query strings; reuse it with different `page_size` values
- **Do not hardcode colors** — use CSS variables from `:root` in `style.css`
- **Do not commit `credentials.json`** — it is in `.gitignore` but double-check before any push
