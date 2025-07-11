# core/query_executor.py (Final version based on your Snowpark Session setup)

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
import streamlit as st
from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSessionException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Manages Snowflake connection and query execution.
    Utilizes Streamlit's caching for performance with Snowpark.
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
        _self, query_config: dict, filters: Optional[dict] = None
    ) -> pd.DataFrame:
        """
        Executes a parameterized SQL query using Snowpark and returns a Pandas DataFrame.
        Caching is applied here for query results.

        Args:
            query_config (dict): Dictionary with 'query' template, 'label', and 'apply_object_filter'.
            filters (dict): Dictionary of parameters including 'start_date', 'end_date',
                            'object_type', 'object_value' to format the query.

        Returns:
            pd.DataFrame: The query result as a Pandas DataFrame.
        """
        session = _self.get_session()
        df = pd.DataFrame() # Default empty DataFrame
        query_label = query_config.get("label", "Unknown Query")
        query_template = query_config.get("query")

        if not query_template:
            logger.error(f"Query template is missing for: {query_label}")
            # Do not st.error here, let the renderer handle the display to the user
            return df

        # Ensure filters is a dictionary, even if empty
        filters = filters or {}

        try:
            # Extract date filters (ensure these are always provided by common_ui)
            start_date_str = filters.get("start_date")
            end_date_str = filters.get("end_date")

            # Fallback for start_date if not provided (should ideally come from filters)
            if not start_date_str:
                logger.warning(f"start_date missing in filters for query: {query_label}. Using a default.")
                start_date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d') # Format for date-only

            # --- CRITICAL ADJUSTMENT FOR USER FILTER ---
            user_filter_clause = "AND 1=1" # Default: no-op filter
            if query_config.get("apply_object_filter", False) and filters.get("object_type") == "user":
                selected_user = filters.get("object_value")
                if selected_user and selected_user != "All":
                    # Ensure USER_NAME is the correct column in your ACCOUNT_USAGE queries
                    # and that selected_user is safe to embed (e.g., no SQL injection concerns)
                    user_filter_clause = f"AND USER_NAME = '{selected_user}'"
                    logger.debug(f"Applying user filter: {user_filter_clause}")
                else:
                    logger.debug(f"Object filter is applied but 'All' selected or value is empty for {query_label}. Using AND 1=1.")
            else:
                logger.debug(f"Object filter NOT applied for {query_label} (apply_object_filter={query_config.get('apply_object_filter', False)}, object_type={filters.get('object_type')}).")
            # --- END CRITICAL ADJUSTMENT ---


            # Format the query with placeholders
            # Use TRY_TO_TIMESTAMP_NTZ for robust date parsing in Snowflake SQL
            formatted_query = query_template.format(
                start_date=start_date_str,
                end_date=end_date_str, # Pass end_date even if not all queries use it
                user_filter=user_filter_clause # This is the key dynamic part
            )

            logger.info(f"Executing query: {query_label}")
            logger.debug(f"Full SQL for {query_label}:\n{formatted_query}") # Log full SQL for debugging

            df = session.sql(formatted_query).to_pandas()
            logger.info(f"Query '{query_label}' executed successfully. Rows: {len(df)}")
            return df

        except SnowparkSessionException as se:
            logger.error(f"Snowpark session error during query execution for '{query_label}': {se}")
            # Do not st.error here, let the renderer handle the display to the user
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error executing query '{query_label}': {e}\nSQL: {formatted_query}")
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
        custom_start: Optional[datetime.date] = None,
        custom_end: Optional[datetime.date] = None,
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
        # Get current date as per server's timezone, which is usually UTC for cloud environments
        # For Navi Mumbai, IST is UTC+5:30. If your Snowflake account is set to UTC,
        # account_usage data will be in UTC. It's often best to keep dates in UTC
        # until display to avoid confusion with timezones.
        # For simplification, we will use datetime.now().date() which reflects local date.
        end_date = datetime.now().date()

        if date_filter == "1_day":
            start_date = end_date - timedelta(days=1)
        elif date_filter == "7_days":
            start_date = end_date - timedelta(days=7)
        elif date_filter == "14_days":
            start_date = end_date - timedelta(days=14)
        elif date_filter == "1_month":
            # Corrected logic for 1 month ago
            # Go back to the first day of the current month, then subtract a day to get last day of previous month
            # Then set day to min(current_day, last_day_of_previous_month)
            temp_date = end_date.replace(day=1) - timedelta(days=1) # Last day of previous month
            start_date = end_date.replace(year=temp_date.year, month=temp_date.month, 
                                          day=min(end_date.day, temp_date.day))
        elif date_filter == "3_months":
            start_date = end_date - timedelta(days=90)
        elif date_filter == "6_months":
            start_date = end_date - timedelta(days=180)
        elif date_filter == "1_year":
            start_date = end_date - timedelta(days=365)
        elif date_filter == "custom":
            # Ensure custom_start and custom_end are not None and are dates
            start_date = custom_start if isinstance(custom_start, datetime.date) else end_date - timedelta(days=7)
            end_date = custom_end if isinstance(custom_end, datetime.date) else end_date
            
            # Ensure start_date is not after end_date; if so, default to a sensible range
            if start_date > end_date:
                logger.warning(f"Custom start date {start_date} is after end date {end_date}. Adjusting to 7 days prior to end_date.")
                start_date = end_date - timedelta(days=7)
        else:  # Default to 7 days if unknown or initial load
            start_date = end_date - timedelta(days=7)

        # Format dates for SQL queries
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


# Global instance for easy import across the Streamlit application
query_executor = QueryExecutor()