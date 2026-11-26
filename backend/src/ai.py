"""AI module — SQL generation + natural-language summarisation via Docker Model Runner."""

import html
import json
import os
import re
import threading
from urllib.parse import urlparse

import requests
from openai import OpenAI

_TAG_RE = re.compile(r"<[^>]+>")

# Prompt budget for /api/ai/chat: keeps the prompt well inside the model's
# context window so a small local GPU answers in seconds, not minutes.
AI_MAX_NOTES = int(os.environ.get("AI_MAX_NOTES", "25"))
AI_MAX_NOTE_CHARS = int(os.environ.get("AI_MAX_NOTE_CHARS", "600"))

# LLM Provider switch: "local" (default) or "gemini"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "local")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if LLM_PROVIDER == "gemini":
    LLM_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/"
    LLM_MODEL = os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL") or "gemini-1.5-flash"
    client = OpenAI(
        base_url=LLM_ENDPOINT,
        api_key=GEMINI_API_KEY or "mock-key",
        timeout=30.0
    )
else:
    # Injected automatically by Docker Compose when using the `models:` key.
    # Falls back to the standard Docker Model Runner host for local testing.
    LLM_URL = os.environ.get("LLM_URL")
    LLM_MODEL_ENV = os.environ.get("LLM_MODEL")
    LLM_ENDPOINT = f"{LLM_URL}/v1" if LLM_URL and LLM_URL.endswith("run.app") else f"{LLM_URL}"
    LLM_MODEL = "ai/gemma4:e4b" if LLM_URL and LLM_URL.endswith("run.app") else (LLM_MODEL_ENV or "ai/llama3.2")
    client = OpenAI(
        base_url=LLM_ENDPOINT,
        api_key="not-needed",  # DMR doesn't require an API key
        timeout=7200
    )

print(f"Using LLM Provider: {LLM_PROVIDER}, Endpoint: {LLM_ENDPOINT}, Model: {LLM_MODEL}")


# --------------- Model pre-hook (Docker Model Runner) ---------------
# On Cloud Run the model store lives in the instance's in-memory filesystem:
# every new instance (scale from zero, scale out, new revision) starts empty.
# Before each LLM call we make sure the model exists, and pull it if not.

MODEL_PULL_TIMEOUT = int(os.environ.get("MODEL_PULL_TIMEOUT", "900"))
_model_lock = threading.Lock()


def _normalize_ref(ref: str) -> str:
    """'docker.io/ai/llama3.2' and 'ai/llama3.2:latest' → 'ai/llama3.2:latest'."""
    for prefix in ("docker.io/", "index.docker.io/"):
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
    if ":" not in ref.rsplit("/", 1)[-1]:
        ref += ":latest"
    return ref


def _runner_base_url() -> str:
    """Native DMR API root (/models, /models/create) — the host of LLM_URL, without /v1."""
    parsed = urlparse(LLM_URL)
    return f"{parsed.scheme}://{parsed.netloc}"


def _model_present(base: str) -> bool:
    resp = requests.get(f"{base}/models", timeout=10)
    resp.raise_for_status()
    wanted = _normalize_ref(LLM_MODEL)
    return any(
        _normalize_ref(tag) == wanted
        for model in resp.json()
        for tag in model.get("tags") or []
    )


def ensure_model_available() -> None:
    """Pull LLM_MODEL into the model runner if it is missing. No-op for Gemini."""
    if LLM_PROVIDER != "local" or not LLM_URL:
        return
    base = _runner_base_url()
    if _model_present(base):
        return
    # One pull at a time: concurrent requests wait for the first pull instead of starting their own
    with _model_lock:
        if _model_present(base):
            return
        print(f"Model {LLM_MODEL} missing on {base}, pulling…")
        resp = requests.post(
            f"{base}/models/create",
            json={"from": LLM_MODEL},
            timeout=(10, MODEL_PULL_TIMEOUT),
        )
        resp.raise_for_status()
        # The runner streams JSON progress lines; the last one reports success or error
        lines = [l for l in html.unescape(resp.text).splitlines() if l.strip()]
        last = json.loads(lines[-1]) if lines else {}
        if last.get("type") == "error":
            raise RuntimeError(f"Model pull failed: {last.get('message')}")
        print(f"Model {LLM_MODEL} pulled: {last.get('message', 'ok')}")




_SYSTEM_PROMPT = """\
You are an expert cloud engineer assistant helping developers, data engineers, \
and cloud architects understand GCP release notes.

When answering:
- Be direct and actionable — these are busy engineers
- Use Markdown (headers, bullets, bold) for clarity
- For summaries: group by product/theme, highlight what matters most
- For impact questions: open with a clear yes/no, then explain
- For deprecations or breaking changes: always include specific action items and urgency
- If something requires immediate action, flag it with ⚠️
- Stick to what the release notes say; do not hallucinate details\
"""


def summarize_release_notes(
    question: str,
    notes_df,          # pd.DataFrame
    shown: int,
    total: int,
) -> str:
    """Answer a natural-language question grounded in release note rows."""
    lines = []
    for _, row in notes_df.iterrows():
        pub = str(row["published_at"])[:10]
        desc = _TAG_RE.sub("", str(row.get("description", "") or "")).strip()
        if len(desc) > AI_MAX_NOTE_CHARS:
            desc = desc[:AI_MAX_NOTE_CHARS].rstrip() + "…"
        lines.append(
            f"[{row['release_note_type']}] {row['product_name']} ({pub})\n{desc}"
        )
    notes_text = "\n\n---\n\n".join(lines)

    user_prompt = (
        f"Here are {shown} GCP release notes (out of {total:,} total matching "
        f"the active filters):\n\n{notes_text}\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def generate_sql_query(question: str, table_id: str, table_schema: list[dict]) -> str:
    """Generate a BigQuery SQL query from a natural language question."""
    schema_lines = "\n".join(f"  - {col['name']} ({col['type']})" for col in table_schema)
    prompt = f"""Generate a BigQuery SQL query to answer this question:
"{question}"

Table: `{table_id}`
Schema:
{schema_lines}

Rules:
- Output only the SQL query, no explanation or markdown fences
- Wrap the table name in backticks
- Use standard BigQuery SQL syntax
- Handle case sensitivity with LOWER() where appropriate"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    print(response.choices[0].message.content)
    return response.choices[0].message.content.strip()
