"""BigQuery dataset and table configuration."""
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

PROJECT_ID = os.getenv("DATA_PROJECT_ID", )
DATASET_ID = os.getenv("DATASET_ID")
TABLE_ID = os.getenv("TABLE_ID")
MODEL = os.getenv("LLM_MODEL")  # Default model if not specified

def get_table_name() -> str | None:
    """Return full BigQuery table name."""
    if not (PROJECT_ID and DATASET_ID and TABLE_ID):
        return None
    return f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

def get_llm_model_name() -> str | None:
    """Return the name of the LLM model to use for SQL generation."""
    # This can be extended to read from environment variables or config files
    return MODEL
