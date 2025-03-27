import pandas as pd
import streamlit as st

# Safe query execution function
def execute_query(query, client):
    """Safely execute a BigQuery query and return a dataframe"""
    try:
        job = client.query(query)
        # Use the classic API which is more stable
        results = [dict(row) for row in job.result()]
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Query failed: {str(e)}")
        st.code(query, language="sql")
        return pd.DataFrame()


# Function to query BigQuery with filters
def query_release_notes(release_types, product_names, start_date, end_date, search_text, limit, offset, client, table_name):
    # Build the WHERE clause dynamically
    where_clauses = []
    query_params = []
    
    # Release note type filter
    if release_types:
        placeholders = ", ".join(["?"] * len(release_types))
        where_clauses.append(f"release_note_type IN ({placeholders})")
        query_params.extend(release_types)
    
    # Product name filter
    if product_names:
        placeholders = ", ".join(["?"] * len(product_names))
        where_clauses.append(f"product_name IN ({placeholders})")
        query_params.extend(product_names)
    
    # Date range filter
    if start_date and end_date:
        where_clauses.append("published_at BETWEEN ? AND ?")
        query_params.extend([start_date.isoformat(), end_date.isoformat()])
    
    # Text search - using CONTAINS instead of LIKE for better performance
    if search_text:
        where_clauses.append("LOWER(description) LIKE ?")
        query_params.append(f"%{search_text.lower()}%")
    
    # Combine all WHERE clauses
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Replace ? with actual values for BigQuery (it doesn't support prepared statements this way)
    formatted_where = where_clause
    for param in query_params:
        if isinstance(param, str):
            # Escape single quotes in strings
            escaped_param = param.replace("'", "''")
            formatted_where = formatted_where.replace("?", f"'{escaped_param}'", 1)
        else:
            formatted_where = formatted_where.replace("?", str(param), 1)
    
    # Build the final query
    query = f"""
    SELECT 
        description,
        release_note_type,
        published_at,
        product_name,
        product_version_name
    FROM 
        `{table_name}`
    WHERE 
        {formatted_where}
    ORDER BY 
        published_at DESC
    LIMIT {limit}
    OFFSET {offset}
    """
    
    # Count query for pagination
    count_query = f"""
    SELECT 
        COUNT(*) as total
    FROM 
        `{table_name}`
    WHERE 
        {formatted_where}
    """
    
    # Execute queries
    results_df = client.query(query).to_dataframe()
    count_df = client.query(count_query).to_dataframe()
    
    return results_df, count_df['total'][0]

