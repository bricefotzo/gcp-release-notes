"""AI module — SQL generation + natural-language summarisation via Docker Model Runner."""

import os
import re

import requests
from openai import OpenAI

_TAG_RE = re.compile(r"<[^>]+>")

# Injected automatically by Docker Compose when using the `models:` key.
# Falls back to the standard Docker Model Runner host for local testing.
LLM_URL = os.environ.get("LLM_URL")
LLM_MODEL = os.environ.get("LLM_MODEL")  # Default model if not specified

LLM_ENDPOINT = f"{LLM_URL}/v1" if LLM_URL and LLM_URL.endswith("run.app") else f"{LLM_URL}"
LLM_MODEL = "ai/gemma4:E4B" if LLM_URL and LLM_URL.endswith("run.app") else (LLM_MODEL or "ai/llama3.2")
print(f"LLM_URL: {LLM_URL}, LLM_MODEL: {LLM_MODEL}")
client = OpenAI(
    base_url=LLM_ENDPOINT,
    api_key="not-needed",  # DMR doesn't resquire an API key
    timeout=7200
)




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
