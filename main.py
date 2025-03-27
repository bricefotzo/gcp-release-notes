from typing import Dict, List
import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import datetime
import plotly.express as px
import os
import json
from google.api_core.exceptions import GoogleAPIError
from google.cloud import aiplatform
from vertexai.language_models import TextGenerationModel
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv
import vertexai
from PIL import Image
import streamlit as st
from queries import execute_query, query_release_notes
from utils import format_description
import streamlit_antd_components as sac


im = Image.open("google.png")

load_dotenv()
from google import genai
from google.genai import types

gen_client = genai.Client()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/bricefotzo/workspace/tutos/application-sa.json"
def init_vertex(project, credentials,location="us-central1" ):
    vertexai.init(
        project=project,
        location=location,
        # experiment=experiment,
        # staging_bucket=staging_bucket,
        credentials=credentials,
        # encryption_spec_key_name=encryption_spec_key_name,
        service_account="bq-access@gke-trial-453409.iam.gserviceaccount.com",
    )


# Page config
st.set_page_config(
    page_title="GCP Release Notes Navigator",
    page_icon=im,
    layout="wide"
)
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
.stAppHeader {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True) 

# Application title
sac.buttons([
             sac.ButtonsItem(label= "GCP Release Notes Navigator",icon=sac.BsIcon(name='google', size=30))], 
             align='left', size='xl', variant='link', index=None)
with st.expander("About this App"):
    st.markdown("The purpose of this app is to turn Google Cloud release notes into relevant insights.")
    st.markdown("""Visitors can search by keyword but also filter notes them by:
- Google Service or Product
- The type of change
- The release date
                """)
    st.markdown("More evolutions will come later.")
# st.title("GCP Release Notes Navigator")

# Function to initialize BigQuery client
@st.cache_resource
def get_bigquery_client():
    # For local development, you'll need to use service account credentials
    # In production on GCP, the application can use default credentials
    try:
        # Check for environment variable with credentials
        if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            return bigquery.Client()
        
        # Check for Streamlit secrets
        elif st.secrets.get("gcp_service_account"):
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return bigquery.Client(credentials=credentials)
        
        # Try application default credentials
        else:
            return bigquery.Client()
            
    except Exception as e:
        st.error(f"Credentials error: {str(e)}")
        # Show instructions for setting up credentials
        st.info("""
        To set up BigQuery credentials:
        1. Export credentials: `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
        2. Or add credentials to .streamlit/secrets.toml
        """)
        raise e


# BigQuery project ID
project_id = "bigquery-public-data"

# Dataset name
dataset_id = "google_cloud_release_notes"
 #.google_cloud_release_notes.release_notes
# Table name
table_id = "release_notes"

# Full table name
@st.cache_data
def get_full_table_name():
    if not project_id or not dataset_id or not table_id:
        return None
    return f"{project_id}.{dataset_id}.{table_id}"
credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
table_name = get_full_table_name()
init_vertex(project=project_id, credentials=credentials)
# Only try to connect if we have a table name
if not table_name:
    st.warning("Please fill in all project configuration fields")
    st.stop()

# Create BigQuery client
try:
    client = get_bigquery_client()
    
    # Verify connection with a simple query
    test_query = f"""
    SELECT COUNT(*) as count
    FROM `{table_name}`
    LIMIT 1
    """
    
    try:
        test_result = client.query(test_query).result()
        # st.success(f"✅ Connected to BigQuery table: {table_name}")
    except Exception as e:
        st.error(f"Connection test failed: {e}")
        st.error(f"""
        Failed to query table `{table_name}`. 
        
        Possible issues:
        - Table doesn't exist
        - Insufficient permissions
        - Invalid project/dataset/table name
        
        Error details: {str(e)}
        """)
        st.stop()
        
except Exception as e:
    st.sidebar.error(f"Failed to connect to BigQuery: {e}")
    st.stop()


# Cache data loading function
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_release_note_types():
    query = f"""
    SELECT DISTINCT release_note_type
    FROM `{table_name}`
    WHERE release_note_type IS NOT NULL
    ORDER BY release_note_type
    """
    df = execute_query(query, client)
    return df['release_note_type'].tolist() if not df.empty and 'release_note_type' in df.columns else []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_product_names():
    query = f"""
    SELECT DISTINCT product_name
    FROM `{table_name}`
    WHERE product_name IS NOT NULL
    ORDER BY product_name
    """
    df = execute_query(query, client)
    return df['product_name'].tolist() if not df.empty and 'product_name' in df.columns else []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_date_range():
    query = f"""
    SELECT MIN(published_at) as min_date, MAX(published_at) as max_date
    FROM `{table_name}`
    """
    df = execute_query(query, client)
    if df.empty or 'min_date' not in df.columns or 'max_date' not in df.columns:
        # Return default dates if query fails
        today = datetime.date.today()
        start = today - datetime.timedelta(days=365)
        return start, today
    
    # Handle None values
    min_date = df['min_date'][0] if pd.notna(df['min_date'][0]) else datetime.date.today() - datetime.timedelta(days=365)
    max_date = df['max_date'][0] if pd.notna(df['max_date'][0]) else datetime.date.today()
    
    return min_date, max_date

# Load filter options with error handling
with st.spinner("Loading filter options..."):
    release_note_types = load_release_note_types()
    if not release_note_types:
        st.warning("No release note types found. Check if the table contains data.")
        release_note_types = ["Feature", "Issue", "Announcement"]  # Fallback defaults
        
    product_names = load_product_names()
    if not product_names:
        st.warning("No product names found. Check if the table contains data.")
        product_names = ["Compute Engine", "BigQuery", "Cloud Storage"]  # Fallback defaults
        
    min_date, max_date = get_date_range()

# Sidebar filters
# st.header("Filters")

# Text search
search_text = st.text_input("Search", "")

pn, tn, dr = st.columns(3)

# Product name filter
with pn:
    selected_products = st.multiselect(
        "Product name",
        options=product_names,
        default=[]
    )

with tn:
# Release note type filter
    selected_types = st.multiselect(
        "Release note type",
        options=release_note_types,
        default=[]
    )

with dr:
# Date range filter
    date_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )




# Apply button
apply_filters = st.button("Reload")


# Pagination state
if 'page' not in st.session_state:
    st.session_state.page = 1

if 'items_per_page' not in st.session_state:
    st.session_state.items_per_page = 5


# Pagination functions
def next_page():
    st.session_state.page += 1

def prev_page():
    st.session_state.page = max(1, st.session_state.page - 1)

def reset_page():
    st.session_state.page = 1

# # Reset page when filters are applied
if apply_filters:
    reset_page()

# Current page
current_page = st.session_state.page
offset = (current_page - 1) * st.session_state.items_per_page

# Query data with filters
start_date = date_range[0] if len(date_range) >= 1 else min_date
end_date = date_range[1] if len(date_range) >= 2 else max_date

results, total_count = query_release_notes(
    selected_types,
    selected_products,
    start_date,
    end_date,
    search_text,
    st.session_state.items_per_page,
    offset,
    client,
    table_name
)

# Display results count
st.write(f"Found {total_count} release notes")

table = client.get_table(table_name)
# st.write(table)
# st.write(table.schema)
# query = st.text_input("Requête SQL")
# SQL_QUERY = generate_sql_query(query, table_name, table.schema)
# st.write(SQL_QUERY)
# Show visualizations when no specific filters are applied
tab1, tab2 = st.tabs(["Notes", "Insights"])
# Display search results
with tab1:
    st.header("Search Results")

    # Display results as cards
    if not results.empty:
        for _, row in results.iterrows():
            with st.container():
                st.markdown(f"### {row['product_name']}")
                st.markdown(f"**Type:** {row['release_note_type']} | **Published:** {row['published_at'].strftime('%Y-%m-%d')}")
                st.markdown(f"**Description:** ")
                st.markdown(f"{format_description(row['description'])}")
                st.divider()
    else:
        st.info("No results found matching your criteria.")

    # Results per page


    # Pagination controls
    total_pages = (total_count + st.session_state.items_per_page - 1) // st.session_state.items_per_page
    if total_pages > 1:
        col1, col2, col3,col4 = st.columns([1, 3, 1,1])
        
        with col1:
            if current_page > 1:
                st.button("← Previous", on_click=prev_page)
        
        with col2:
            st.write(f"Page {current_page} of {total_pages}")
        
        with col3:
            if current_page < total_pages:
                st.button("Next →", on_click=next_page)
        with col4:
            st.session_state.items_per_page = st.selectbox("", [5,10,15,20,50])

with tab2:
    # if not search_text and not selected_types and not selected_products:
    st.header("Release Notes Overview")
    
    # Split screen into columns
    col1, col2 = st.columns(2)
    
    with col1:
        # Time series chart of release notes
        time_series_query = f"""
        SELECT 
            DATE_TRUNC(published_at, MONTH) as month,
            COUNT(*) as count
        FROM 
            `{table_name}`
        WHERE 
            published_at BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR) AND CURRENT_DATE()
        GROUP BY 
            month
        ORDER BY 
            month
        """
        time_df = client.query(time_series_query).to_dataframe()
        fig1 = px.line(time_df, x='month', y='count', title='Release Notes by Month (Last 12 Months)')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Release note types distribution
        types_query = f"""
        SELECT 
            release_note_type,
            COUNT(*) as count
        FROM 
            `{table_name}`
        WHERE 
            release_note_type IS NOT NULL
        GROUP BY 
            release_note_type
        ORDER BY 
            count DESC
        LIMIT 10
        """
        types_df = client.query(types_query).to_dataframe()
        fig2 = px.pie(types_df, values='count', names='release_note_type', 
                      title='Distribution of Release Note Types')
        st.plotly_chart(fig2, use_container_width=True)

    # Footer
st.markdown("---")
st.markdown("GCP Release Notes Navigator | By Brice Fotzo")