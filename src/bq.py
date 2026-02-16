"""BigQuery client and connection handling."""

import os
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account


@st.cache_resource
def get_bigquery_client():
    """Initialize BigQuery client from env or Streamlit secrets."""
    try:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return bigquery.Client()
        if st.secrets.get("gcp_service_account"):
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return bigquery.Client(credentials=creds)
        return bigquery.Client()
    except Exception as e:
        st.error(f"Credentials error: {str(e)}")
        st.info(
            "Set GOOGLE_APPLICATION_CREDENTIALS or add gcp_service_account to .streamlit/secrets.toml"
        )
        raise
