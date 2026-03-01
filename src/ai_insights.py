"""AI-powered insights using Google Generative AI (Gemini)."""

import hashlib
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pymongo.database import Database

load_dotenv()


def _get_genai_model():
    """Initialize and return a Gemini generative model, or None."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.0-flash")
    except Exception:
        return None


def _build_summary_prompt(notes_df: pd.DataFrame, preferences: dict) -> str:
    """Build a prompt for the AI weekly summary."""
    products = preferences.get("products", [])
    types = preferences.get("types", [])

    notes_lines = []
    for _, row in notes_df.head(50).iterrows():
        desc = str(row.get("description", ""))[:200]
        notes_lines.append(
            f"- [{row['release_note_type']}] {row['product_name']} "
            f"({row['published_at'].strftime('%Y-%m-%d')}): {desc}"
        )
    notes_text = "\n".join(notes_lines)

    return f"""You are an expert Google Cloud Platform analyst. Based on the following recent GCP release notes that match the user's interests, provide a concise and actionable summary.

User's tracked products: {', '.join(products) if products else 'All products'}
User's tracked release types: {', '.join(types) if types else 'All types'}

Recent release notes:
{notes_text}

Provide:
1. A brief overview (2-3 sentences) of the most important changes
2. Key highlights (bullet points, max 5) — focus on breaking changes, new features, and deprecations
3. Action items if any breaking changes affect the tracked products

Keep the summary concise, professional, and actionable. Use markdown formatting."""


def _cache_key(user_id: str, preferences: dict) -> str:
    """Generate a deterministic cache key from user ID and preferences."""
    prefs_str = (
        str(sorted(preferences.get("products", [])))
        + str(sorted(preferences.get("types", [])))
    )
    return hashlib.md5(f"{user_id}:{prefs_str}".encode()).hexdigest()


def _get_cached_summary(db: Database, user_id: str, preferences: dict) -> str | None:
    """Return a cached summary if one exists and is less than 24h old."""
    key = _cache_key(user_id, preferences)
    doc = db.ai_summaries.find_one(
        {
            "cache_key": key,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)},
        }
    )
    return doc["summary"] if doc else None


def _save_summary(
    db: Database, user_id: str, preferences: dict, summary: str
) -> None:
    """Upsert a cached AI summary."""
    key = _cache_key(user_id, preferences)
    db.ai_summaries.update_one(
        {"cache_key": key},
        {
            "$set": {
                "user_id": user_id,
                "cache_key": key,
                "summary": summary,
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def generate_ai_summary(
    db: Database,
    user_id: str,
    notes_df: pd.DataFrame,
    preferences: dict,
) -> str | None:
    """Generate (or retrieve cached) AI summary of personalized release notes.

    Returns None if AI is not configured, notes are empty, or generation fails.
    """
    if notes_df.empty:
        return None

    cached = _get_cached_summary(db, user_id, preferences)
    if cached:
        return cached

    model = _get_genai_model()
    if not model:
        return None

    try:
        prompt = _build_summary_prompt(notes_df, preferences)
        response = model.generate_content(prompt)
        summary = response.text

        _save_summary(db, user_id, preferences, summary)
        return summary
    except Exception:
        return None
