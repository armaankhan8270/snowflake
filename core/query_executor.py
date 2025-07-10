# core/query_executor.py (Re-confirming current state, no major changes needed here based on previous)
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSessionException

logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Manages Snowflake connection and query execution.
    Utilizes Streamlit's caching for performance.
    """

    def __init__(self):
        self._session = None

    @st.cache_resource
    def _create_snowpark_session(_self):
        """
        Creates and caches a Snowpark session.
        This method is marked with st.cache_resource to ensure the session
        is created only once and reused across reruns.
        """
        try:
            secrets = st.secrets["snowflake"]
            connection_parameters = {
                "account": secrets["account"],
                "user": secrets["user"],
                "private_key": secrets["private_key"],
                "role": secrets["role"],
                "warehouse": secrets["warehouse"],
                "database": secrets["database"],
                "schema": secrets["schema"],
            }
            session = Session.builder.configs(connection_parameters).create()
            logger.info("Snowpark session created successfully.")
            return session
        except Exception as e:
            logger.error(f"Error creating Snowpark session: {e}")
            st.error(
                f"Failed to connect to Snowflake. Please check your "
                f".streamlit/secrets.toml file and network connection. Error: {e}"
            )
            st.stop()  # Stop the app if connection fails

    def get_session(self):
        """Returns the cached Snowpark session."""
        if self._session is None:
            self._session = self._create_snowpark_session()
        return self._session

    @st.cache_data(ttl=3600)  # Cache data for 1 hour
    def execute_query(
        _self, query_template: str, params: Optional[dict] = None
    ) -> pd.DataFrame:
        """
        Executes a parameterized SQL query using Snowpark and returns a Pandas DataFrame.
        Caching is applied here for query results.

        Args:
            query_template (str): The SQL query string, possibly with placeholders.
            params (dict): Dictionary of parameters to format the query.

        Returns:
            pd.DataFrame: The query result as a Pandas DataFrame.
        """
        session = _self.get_session()
        
        # Ensure query_template is a string, and params is a dictionary (even if empty)
        if not isinstance(query_template, str):
            logger.error(f"Invalid query_template type: {type(query_template)}. Must be string.")
            return pd.DataFrame()
        if not isinstance(params, dict) and params is not None:
             logger.error(f"Invalid params type: {type(params)}. Must be dictionary or None.")
             params = {} # Default to empty dict

        formatted_query = query_template.format(**(params or {}))

        logger.info(f"Executing query: {formatted_query}")

        try:
            df = session.sql(formatted_query).to_pandas()
            logger.info(f"Query executed successfully. Rows returned: {len(df)}")
            return df
        except SnowparkSessionException as se:
            logger.error(f"Snowpark session error during query execution: {se}")
            # Do not st.error here, let the renderer handle the display to the user
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error executing query '{formatted_query}': {e}")
            # Do not st.error here, let the renderer handle the display to the user
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_object_values(_self, object_type: str, search_term: str = "") -> list:
        """
        Fetches distinct values for a given object type from Snowflake usage views.

        Args:
            object_type (str): The type of object (e.g., 'user', 'warehouse', 'role', 'database').
            search_term (str): Optional search term to filter results.

        Returns:
            list: A list of distinct object values, including 'All'.
        """
        session = _self.get_session()

        object_queries = {
            "user": """
                SELECT DISTINCT USER_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE USER_NAME IS NOT NULL
            """,
            "warehouse": """
                SELECT DISTINCT WAREHOUSE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE WAREHOUSE_NAME IS NOT NULL
            """,
            "role": """
                SELECT DISTINCT NAME AS ROLE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES
                WHERE DELETED_ON IS NULL
            """,
            "database": """
                SELECT DISTINCT DATABASE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
                WHERE DELETED IS NULL
            """,
        }

        if object_type not in object_queries:
            logger.warning(
                f"Unsupported object type for fetching values: {object_type}"
            )
            return ["All"]

        # Base query to get all distinct values
        query = object_queries[object_type]

        # Apply search term filter if provided
        if search_term:
            # Determine the correct column name for filtering based on object_type
            column_name_map = {
                "user": "USER_NAME",
                "warehouse": "WAREHOUSE_NAME",
                "role": "ROLE_NAME",
                "database": "DATABASE_NAME",
            }
            filter_column = column_name_map.get(object_type)
            if filter_column:
                # Sanitize search_term to prevent SQL injection (basic, for user-provided string)
                # For production, consider using Snowpark's parameter binding fully or more robust sanitization.
                sanitized_search_term = search_term.replace("'", "''")
                query += f" AND UPPER({filter_column}) LIKE UPPER('%{sanitized_search_term}%')"
            else:
                logger.warning(f"No specific filter column defined for object type: {object_type}")

        query += " ORDER BY 1 LIMIT 100" # Limit to 100 results for performance

        try:
            df = session.sql(query).to_pandas()
            if df.empty:
                logger.info(f"No {object_type} values found for search term '{search_term}'.")
                return ["All"]

            column = df.columns[0] # Get the first column name for values
            values = df[column].dropna().astype(str).tolist()
            return ["All"] + values
        except Exception as e:
            logger.error(f"Error fetching {object_type} values: {e}")
            return ["All"]

    def get_date_range(
        self,
        date_filter: str,
        custom_start: Optional[datetime.date] = None, # Changed to datetime.date
        custom_end: Optional[datetime.date] = None,   # Changed to datetime.date
    ) -> Tuple[str, str]:
        """
        Calculates start and end dates based on the selected date filter.

        Args:
            date_filter (str): Predefined date range key (e.g., '7_days', '1_month', 'custom').
            custom_start (datetime.date): Custom start date (for 'custom' filter).
            custom_end (datetime.date): Custom end date (for 'custom' filter).

        Returns:
            Tuple[str, str]: A tuple containing (start_date_str, end_date_str) in 'YYYY-MM-DD' format.
        """
        end_date = datetime.now().date() # Use date() for consistency with st.date_input

        if date_filter == "1_day":
            start_date = end_date - timedelta(days=1)
        elif date_filter == "7_days":
            start_date = end_date - timedelta(days=7)
        elif date_filter == "14_days":
            start_date = end_date - timedelta(days=14)
        elif date_filter == "1_month":
            # For accurate "1 month ago", adjust by month, not fixed days
            # This logic attempts to get the same day of the previous month
            temp_date = end_date.replace(day=1) - timedelta(days=1) # Last day of previous month
            start_date = temp_date.replace(day=min(end_date.day, temp_date.day))
        elif date_filter == "3_months":
            start_date = end_date - timedelta(days=90) # Approximation
        elif date_filter == "6_months":
            start_date = end_date - timedelta(days=180) # Approximation
        elif date_filter == "1_year":
            start_date = end_date - timedelta(days=365) # Approximation
        elif date_filter == "custom":
            start_date = custom_start if custom_start else end_date - timedelta(days=7)
            end_date = custom_end if custom_end else end_date
            # Ensure start_date is not after end_date; if so, default to a sensible range
            if start_date > end_date:
                logger.warning(f"Custom start date {start_date} is after end date {end_date}. Adjusting to 7 days prior to end_date.")
                start_date = end_date - timedelta(days=7)
        else:  # Default to 7 days if unknown or initial load
            start_date = end_date - timedelta(days=7)

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


# Global instance for easy import
query_executor = QueryExecutor()