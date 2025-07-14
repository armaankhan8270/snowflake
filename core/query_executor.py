# core/query_executor.py
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed # Added for parallelism

import pandas as pd
import streamlit as st

from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSessionException

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Manages Snowflake connection and query execution.
    Utilizes Streamlit's caching for performance with Snowpark.
    Supports parallel query execution.
    """

    # Using a class-level ThreadPoolExecutor to manage a pool of threads for concurrent queries.
    # The max_workers should be tuned based on expected concurrency and Snowflake warehouse capacity.
    _executor: Optional[ThreadPoolExecutor] = None
    _MAX_WORKERS = 5 # Tunable: Number of concurrent queries to run

    def __init__(self):
        self._session = None
        # Initialize executor lazily or ensure it's a singleton
        if QueryExecutor._executor is None:
            QueryExecutor._executor = ThreadPoolExecutor(max_workers=self._MAX_WORKERS)
            logger.info(f"ThreadPoolExecutor initialized with {self._MAX_WORKERS} workers.")

    @st.cache_resource
    def _create_snowpark_session(_self): # Using _self as per Streamlit's convention for cached methods
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

    def get_session(self) -> Session:
        """Returns the cached Snowpark session."""
        if self._session is None:
            self._session = self._create_snowpark_session()
        return self._session

    @st.cache_data(ttl=3600)  # Cache data for 1 hour
    def _execute_single_query(
        _self, query_template: str, formatted_params: Dict[str, str], query_label: str
    ) -> pd.DataFrame:
        """
        Internal method to execute a single SQL query using Snowpark and returns a Pandas DataFrame.
        This method expects `formatted_params` to contain all necessary string replacements for
        the `query_template` (e.g., 'start_date', 'end_date', 'object_filter').
        Caching is applied here for query results.

        Args:
            query_template (str): The SQL query string with placeholders like '{start_date}',
                                  '{end_date}', '{object_filter}'.
            formatted_params (dict): Dictionary where keys match query placeholders and values
                                     are the formatted strings (e.g., date strings, WHERE clauses).
            query_label (str): A label for logging/error reporting.

        Returns:
            pd.DataFrame: The query result as a Pandas DataFrame.
        """
        session = _self.get_session()
        df = pd.DataFrame()  # Default empty DataFrame
        formatted_query = ""

        if not query_template:
            logger.error(f"Query template is missing for: {query_label}")
            # Do not st.error here, let the renderer handle the display to the user
            return df

        try:
            # Format the query with ALL provided parameters
            # This makes the query robust to different filter types (user, role, warehouse)
            formatted_query = query_template.format(**formatted_params)

            logger.info(f"Executing query: {query_label}")
            logger.debug(
                f"Full SQL for {query_label}:\n{formatted_query}"
            )  # Log full SQL for debugging

            df = session.sql(formatted_query).to_pandas()
            logger.info(f"Query '{query_label}' executed successfully. Rows: {len(df)}")
            return df

        except SnowparkSessionException as se:
            error_msg = (
                f"Snowpark session error during query execution for '{query_label}': {se}"
            )
            logger.error(error_msg)
            # Store error in session state for Streamlit's global error display if needed
            st.session_state["last_error"] = error_msg
            return pd.DataFrame()
        except Exception as e:
            error_msg = f"Error executing query '{query_label}': {e}\nSQL: {formatted_query}"
            logger.error(error_msg, exc_info=True)
            # Store error in session state
            st.session_state["last_error"] = error_msg
            return pd.DataFrame()

    def execute_queries_parallel(
        self,
        query_jobs: List[Tuple[Dict[str, Any], Dict[str, str], str]]
    ) -> List[Dict[str, Union[pd.DataFrame, str]]]:
        """
        Executes multiple queries in parallel using a ThreadPoolExecutor.
        Each query job is a tuple containing the query configuration, its formatted parameters,
        and a label.

        Args:
            query_jobs (List[Tuple[Dict, Dict, str]]): A list where each item is a tuple containing:
                1. query_config (Dict): The query configuration (e.g., from USER_360_QUERIES).
                                        Only 'query' template is used from here by _execute_single_query.
                2. formatted_params (Dict[str, str]): A dictionary of already formatted parameters
                                                    (e.g., 'start_date', 'end_date', 'object_filter')
                                                    ready for string.format().
                3. query_label (str): A descriptive label for the query (for logging/error reporting).

        Returns:
            List[Dict[str, Union[pd.DataFrame, str]]]: A list of dictionaries, where each dict
                contains either {'data': pd.DataFrame} on success or {'error': str} on failure.
                The order of results corresponds to the order of input query_jobs.
        """
        futures = {}
        # Pre-allocate results list to maintain order of input jobs
        results = [None] * len(query_jobs)

        for i, (query_config, formatted_params, query_label) in enumerate(query_jobs):
            query_template = query_config.get("query")
            if not query_template:
                logger.error(f"Skipping query '{query_label}': template is missing.")
                results[i] = {"error": f"Query template missing for '{query_label}'."}
                continue
            
            # Submit the _execute_single_query to the thread pool
            future = QueryExecutor._executor.submit(
                self._execute_single_query, query_template, formatted_params, query_label
            )
            futures[future] = i # Map future back to its original index

        for future in as_completed(futures):
            index = futures[future]
            try:
                data = future.result() # Get the result (Pandas DataFrame)
                results[index] = {"data": data}
            except Exception as e:
                # This catches exceptions that were not handled within _execute_single_query
                error_msg = f"Error during parallel execution for query '{query_jobs[index][2]}': {e}"
                logger.error(error_msg, exc_info=True)
                results[index] = {"error": error_msg}
        
        # Clear any stored Streamlit errors after parallel execution completes,
        # as individual errors are now reported in the result list for granular handling by renderers.
        if "last_error" in st.session_state:
            del st.session_state["last_error"]

        return results

    @st.cache_data(ttl=3600)
    def get_object_values(
        _self,
        object_type: str,
        search_term: str = "",
        date_filters: Optional[dict] = None, # Contains 'start_date_str', 'end_date_str'
    ) -> list:
        """
        Fetches distinct values for a given object type from Snowflake usage views.

        Args:
            object_type (str): The type of object (e.g., 'user', 'warehouse', 'role', 'database').
            search_term (str): Optional search term to filter results.
            date_filters (dict): Dictionary containing 'start_date_str' and 'end_date_str'
                                 for filtering date-dependent object types (e.g., user, warehouse).

        Returns:
            list: A list of distinct object values, including 'All'.
        """
        session = _self.get_session()

        effective_start_date = None
        effective_end_date = None

        # Determine the effective date range for fetching object values
        # Prefer date filters from the common_ui if provided and relevant for the object type
        if (
            date_filters
            and date_filters.get("start_date_str")
            and (object_type == "user" or object_type == "warehouse") # Only apply date filter for these
        ):
            effective_start_date = date_filters.get("start_date_str")
            effective_end_date = date_filters.get("end_date_str")
            logger.debug(
                f"Using provided date filters for {object_type} values: {effective_start_date} to {effective_end_date}"
            )
        else:
            # Default to last 7 days if no date filters provided or not a date-dependent object type
            seven_days_ago = (datetime.now().date() - timedelta(days=7)).strftime("%Y-%m-%d")
            today_str = datetime.now().date().strftime("%Y-%m-%d")
            effective_start_date = seven_days_ago
            effective_end_date = today_str
            logger.debug(
                f"Using default 7-day filter for {object_type} values: {effective_start_date} to {effective_end_date}"
            )

        # Base queries for distinct object names
        # Note the use of TRY_TO_TIMESTAMP_NTZ for robustness in date parsing in SQL
        object_queries = {
            "user": f"""
                SELECT DISTINCT USER_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE USER_NAME IS NOT NULL
                AND START_TIME >= TRY_TO_TIMESTAMP_NTZ('{effective_start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{effective_end_date} 23:59:59')
            """,
            "warehouse": f"""
                SELECT DISTINCT WAREHOUSE_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE WAREHOUSE_NAME IS NOT NULL
                AND START_TIME >= TRY_TO_TIMESTAMP_NTZ('{effective_start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{effective_end_date} 23:59:59')
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
            filter_column = column_name_map.get(object_type.lower())
            if filter_column:
                # Sanitize search_term to prevent SQL injection.
                # WARNING: While replace("'", "''") is common, for robust production,
                # consider using parameter binding with Snowpark or stricter sanitization.
                sanitized_search_term = search_term.replace("'", "''")
                query += f" AND UPPER({filter_column}) LIKE UPPER('%{sanitized_search_term}%')"
            else:
                logger.warning(
                    f"No specific filter column defined for object type: {object_type}. Search filter will not be applied."
                )

        query += " ORDER BY 1 LIMIT 100"  # Limit results for performance

        try:
            df = session.sql(query).to_pandas()
            if df.empty:
                logger.info(
                    f"No {object_type} values found for search term '{search_term}'."
                )
                return ["All"]

            column = df.columns[0]  # Get the first column name for values
            values = df[column].dropna().astype(str).tolist()
            return ["All"] + values
        except Exception as e:
            logger.error(f"Error fetching {object_type} values: {e}", exc_info=True)
            return ["All"]

    def get_date_range(
        self,
        date_filter: str,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None,
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
        end_date = datetime.now().date()

        if date_filter == "1_day":
            start_date = end_date - timedelta(days=1)
        elif date_filter == "7_days":
            start_date = end_date - timedelta(days=7)
        elif date_filter == "14_days":
            start_date = end_date - timedelta(days=14)
        elif date_filter == "1_month":
            temp_date = end_date.replace(day=1) - timedelta(days=1)
            start_date = end_date.replace(
                year=temp_date.year,
                month=temp_date.month,
                day=min(end_date.day, temp_date.day),
            )
        elif date_filter == "3_months":
            start_date = end_date - timedelta(days=90)
        elif date_filter == "6_months":
            start_date = end_date - timedelta(days=180)
        elif date_filter == "1_year":
            start_date = end_date - timedelta(days=365)
        elif date_filter == "custom":
            start_date = (
                custom_start
                if isinstance(custom_start, date)
                else end_date - timedelta(days=7)
            )
            end_date = custom_end if isinstance(custom_end, date) else end_date

            if start_date and end_date and start_date > end_date:
                logger.warning(
                    f"Custom start date {start_date} is after end date {end_date}. Adjusting to 7 days prior to end_date."
                )
                start_date = end_date - timedelta(days=7)
        else:  # Default to 7 days if unknown or initial load
            start_date = end_date - timedelta(days=7)

        # Format dates for SQL queries
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


# Global instance for easy import across the Streamlit application
query_executor = QueryExecutor()