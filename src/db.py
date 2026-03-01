"""MongoDB connection and initialization."""

import os

import streamlit as st
from pymongo import MongoClient
from pymongo.database import Database


@st.cache_resource
def get_mongo_client() -> MongoClient | None:
    """Initialize MongoDB client from MONGODB_URI env var."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except Exception:
        return None


@st.cache_resource
def _init_database() -> Database | None:
    """Initialize database with required indexes (runs once per session)."""
    client = get_mongo_client()
    if client is None:
        return None
    db = client["gcp_release_notes"]
    db.users.create_index("email", unique=True)
    db.ai_summaries.create_index("cache_key", unique=True)
    db.ai_summaries.create_index("created_at", expireAfterSeconds=86400)
    return db


def get_database() -> Database | None:
    """Return the application database, or None if MongoDB is not configured."""
    return _init_database()
