"""FastAPI backend for GCP Release Notes Navigator."""

from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.ai import generate_sql_query, summarize_release_notes, LLM_MODEL, LLM_ENDPOINT
from src.bq import init_bq_client
from src.config import get_table_name
from src.queries import (
    get_date_range,
    load_product_names,
    load_release_note_types,
    query_release_notes,
)

# --------------- Startup ---------------

bq_client = None
table_name = None
_filter_options: dict | None = None

TABLE_SCHEMA = [
    {"name": "description", "type": "STRING"},
    {"name": "release_note_type", "type": "STRING"},
    {"name": "published_at", "type": "DATE"},
    {"name": "product_name", "type": "STRING"},
    {"name": "product_version_name", "type": "STRING"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bq_client, table_name, _filter_options
    bq_client = init_bq_client()
    table_name = get_table_name()
    # Pre-load stable filter options once at startup
    types = load_release_note_types(bq_client, table_name)
    products = load_product_names(bq_client, table_name)
    min_date, max_date = get_date_range(bq_client, table_name)
    _filter_options = {
        "types": types,
        "products": products,
        "min_date": str(min_date),
        "max_date": str(max_date),
    }
    yield


app = FastAPI(title="GCP Release Notes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------- Health ---------------


@app.get("/health")
def health():
    return {"status": "ok"}


# --------------- Filter Options ---------------


@app.get("/api/filter-options")
def get_filter_options():
    return _filter_options


# --------------- Release Notes ---------------


@app.get("/api/release-notes")
def get_release_notes(
    types: list[str] = Query(default=[]),
    products: list[str] = Query(default=[]),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: str = "",
    page: int = 1,
    page_size: int = 10,
):
    offset = (page - 1) * page_size
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    df, total = query_release_notes(
        types, products, start, end, search, page_size, offset, bq_client, table_name
    )

    if not df.empty and "published_at" in df.columns:
        df["published_at"] = df["published_at"].astype(str)

    return {"data": df.to_dict(orient="records"), "total": int(total)}


# --------------- Insights ---------------


@app.get("/api/insights/time-series")
def get_time_series():
    query = f"""
    SELECT DATE_TRUNC(published_at, MONTH) as month, COUNT(*) as count
    FROM `{table_name}`
    WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR) AND CURRENT_DATE()
    GROUP BY month ORDER BY month
    """
    df = bq_client.query(query).to_dataframe()
    df["month"] = df["month"].astype(str)
    return df.to_dict(orient="records")


@app.get("/api/insights/type-distribution")
def get_type_distribution():
    query = f"""
    SELECT release_note_type, COUNT(*) as count
    FROM `{table_name}`
    WHERE release_note_type IS NOT NULL
    GROUP BY release_note_type ORDER BY count DESC LIMIT 10
    """
    df = bq_client.query(query).to_dataframe()
    return df.to_dict(orient="records")


@app.get("/api/insights/top-products")
def get_top_products():
    query = f"""
    SELECT product_name, COUNT(*) as count
    FROM `{table_name}`
    WHERE product_name IS NOT NULL
    GROUP BY product_name ORDER BY count DESC LIMIT 10
    """
    df = bq_client.query(query).to_dataframe()
    return df.to_dict(orient="records")


@app.get("/api/insights/heatmap")
def get_heatmap():
    query = f"""
    SELECT
        EXTRACT(DAYOFWEEK FROM published_at) as day_of_week,
        DATE_TRUNC(published_at, WEEK) as week,
        COUNT(*) as count
    FROM `{table_name}`
    WHERE published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH) AND CURRENT_DATE()
    GROUP BY day_of_week, week
    ORDER BY week, day_of_week
    """
    df = bq_client.query(query).to_dataframe()
    df["week"] = df["week"].astype(str)
    return df.to_dict(orient="records")


# --------------- AI ---------------


class AIQueryRequest(BaseModel):
    question: str


@app.get("/api/ai/health")
def ai_health():
    """Check that the model runner is reachable and the model is loaded."""
    import requests as _req
    from src.ai import LLM_MODEL, LLM_ENDPOINT
    print(f"Checking AI health at {LLM_ENDPOINT} for model {LLM_MODEL}...")
    MODEL_ENDPOINT = f"{LLM_ENDPOINT}/v1/models" if LLM_ENDPOINT.endswith("run.app") else f"{LLM_ENDPOINT}/models"
    print(f"Model endpoint: {MODEL_ENDPOINT}")
    try:
        resp = _req.get(MODEL_ENDPOINT, timeout=5)
        print(f"AI health response: {resp.status_code} {resp.text}")
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        print(f"Available models: {models}")
        ready = any(LLM_MODEL in m for m in models)
        print(f"Model {LLM_MODEL} ready: {ready}")
        return {"reachable": True, "model": LLM_MODEL, "ready": ready, "available_models": models}
    except Exception as e:
        print(f"Error checking AI health: {e}")
        return {"reachable": False, "model": LLM_MODEL, "url": LLM_ENDPOINT,"error": str(e)}


@app.post("/api/ai/generate-sql")
def generate_sql(request: AIQueryRequest):
    f"""Return the SQL generated for a natural-language question.
    {LLM_MODEL} at {LLM_ENDPOINT}
    """
#    try:
    sql = generate_sql_query(request.question, table_name, TABLE_SCHEMA)
    return {"sql": sql}
#    except Exception as e:
#        raise HTTPException(status_code=503, detail=f"AI service unavailable for {get_llm_model_name()}: {e}")


@app.post("/api/ai/query")
def ai_query(request: AIQueryRequest):
    """Generate SQL from a question, execute it, and return the results."""
    try:
        sql = generate_sql_query(request.question, table_name, TABLE_SCHEMA)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {e}")

    try:
        df = bq_client.query(sql).to_dataframe()
        if "published_at" in df.columns:
            df["published_at"] = df["published_at"].astype(str)
        records = df.head(50).to_dict(orient="records")
        return {"sql": sql, "rows": records, "total": len(df)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {e}\n\nGenerated SQL:\n{sql}")


# --------------- AI Chat (natural-language summarisation) ---------------


class AIChatRequest(BaseModel):
    question: str
    products: list[str] = []
    types: list[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@app.post("/api/ai/chat")
def ai_chat(request: AIChatRequest):
    """Fetch release notes matching the filters and answer the question in plain language."""
    # try:
    start = date.fromisoformat(request.start_date) if request.start_date else None
    end   = date.fromisoformat(request.end_date)   if request.end_date   else None

    df, total = query_release_notes(
        request.types, request.products, start, end, "", 100, 0, bq_client, table_name
    )

    if df.empty:
        return {
            "answer": (
                "No release notes found for the given filters. "
                "Try broadening the date range or removing product filters."
            ),
            "count": 0,
            "total": 0,
        }

    if "published_at" in df.columns:
        df["published_at"] = df["published_at"].astype(str)

    answer = summarize_release_notes(request.question, df, len(df), int(total))
    return {"answer": answer, "count": len(df), "total": int(total)}

    # except Exception as e:
    #     raise HTTPException(status_code=503, detail=f"AI chat unavailable: {e}, Exception type: {type(e)}")
