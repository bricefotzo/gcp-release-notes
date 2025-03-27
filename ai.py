

from typing import Dict, List


def generate_sql_query(query: str, table_id: str, table_schema: List[Dict[str, str]], client,
                      model_name: str = "gemini-1.5-flash-002") -> str:
    """
    Generate SQL query using Vertex AI text model.
    
    Args:
        query: Natural language query
        table_id: Full table identifier
        table_schema: List of column definitions
        model_name: Name of the text generation model to use
    
    Returns:
        Generated SQL query string
    """
    # Initialize model
    # model = TextGenerationModel.from_pretrained(model_name)
    # model = GenerativeModel("gemini-1.5-flash-002")


    # Create prompt
    prompt = f"""Generate an SQL query for the following question:
'{query}'

This is the table id: {table_id}
The target database has the following schema: {table_schema}

Write only the SQL query without any explanation or comments.
The query should be optimized and follow best practices.
Make sure to consider case sensitivity and proper column names."""
    response = client.models.generate_content(
    model=model_name,
    contents=[
        prompt,
    ]
)
    
    return response.text.strip()


