# query_store.py

USER_360_QUERIES = {
    # ----------------------------------------------------------------------
    # METRICS
    # ----------------------------------------------------------------------

    "total_queries_run_by_user": {
        "query": """
            SELECT
                COUNT(QUERY_ID) AS TOTAL_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
        """,
        "label": "Total Queries Run",
        "description": "Total number of queries executed by the selected object within the period.",
        "format": "number",
        "apply_object_filter": True # Apply object filter (e.g., USER_NAME)
    },
    "total_execution_time_min_by_user": {
        "query": """
            SELECT
                COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60) AS TOTAL_EXECUTION_TIME_MIN
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
        """,
        "label": "Total Execution Time",
        "description": "Total time spent executing queries (in minutes) by the selected object. Proxy for compute cost.",
        "format": "number", # Will be formatted as a general number
        "delta_query_key": "total_execution_time_min_by_user", # Delta for this metric
        "apply_object_filter": True
    },
    "avg_execution_time_sec_per_query_by_user": {
        "query": """
            SELECT
                COALESCE(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS' -- Only count successful queries for average
                {object_filter}
        """,
        "label": "Avg. Query Time",
        "description": "Average execution time per successful query (in seconds) by the selected object.",
        "format": "number",
        "apply_object_filter": True
    },
    "total_data_scanned_tb_by_user": {
        "query": """
            SELECT
                COALESCE(SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)), 0) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND BYTES_SCANNED > 0 -- Only count queries that actually scanned data
                {object_filter}
        """,
        "label": "Total Data Scanned",
        "description": "Total volume of data scanned by queries (in Terabytes) by the selected object. A major cost driver.",
        "format": "number", # Can be formatted as TB in UI if needed, for now just a number
        "delta_query_key": "total_data_scanned_tb_by_user",
        "apply_object_filter": True
    },
    "total_compilation_time_sec_by_user": {
        "query": """
            SELECT
                COALESCE(SUM(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)), 0) / 1000 AS TOTAL_COMPILATION_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
        """,
        "label": "Total Compile Time",
        "description": "Total time spent compiling queries (in seconds) by the selected object. High values might indicate complex or unoptimized queries.",
        "format": "number",
        "apply_object_filter": True
    },
    "failed_query_count_by_user": {
        "query": """
            SELECT
                COUNT(QUERY_ID) AS FAILED_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'FAIL'
                {object_filter}
        """,
        "label": "Failed Queries",
        "description": "Total number of failed queries executed by the selected object. Frequent failures indicate issues.",
        "format": "number",
        "apply_object_filter": True
    },
    "distinct_warehouses_used_by_user": {
        "query": """
            SELECT
                COUNT(DISTINCT WAREHOUSE_NAME) AS DISTINCT_WAREHOUSES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND WAREHOUSE_NAME IS NOT NULL
                {object_filter}
        """,
        "label": "Distinct Warehouses Used",
        "description": "Number of unique warehouses the selected object has run queries on. Helps understand resource spread.",
        "format": "number",
        "apply_object_filter": True
    },
    "longest_running_query_min_by_user": {
        "query": """
            SELECT
                COALESCE(MAX(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60) AS LONGEST_RUNNING_QUERY_MIN
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
        """,
        "label": "Longest Query (Min)",
        "description": "The duration (in minutes) of the single longest running successful query by the selected object. Identifies outliers.",
        "format": "number",
        "apply_object_filter": True
    },

    # ----------------------------------------------------------------------
    # CHARTS
    # ----------------------------------------------------------------------

    "daily_total_execution_time_by_user_chart": {
        "query": """
            SELECT
                TO_DATE(START_TIME) AS QUERY_DATE,
                COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60) AS TOTAL_EXECUTION_TIME_MIN
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY 1
            ORDER BY 1
        """,
        "label": "Daily Execution Time (Min)",
        "description": "Daily trend of total query execution time by the selected object.",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_col": "TOTAL_EXECUTION_TIME_MIN",
        "hover_data": ["TOTAL_EXECUTION_TIME_MIN"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "queries_by_execution_status_chart": {
        "query": """
            SELECT
                EXECUTION_STATUS,
                COUNT(QUERY_ID) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY 1
            ORDER BY 2 DESC
        """,
        "label": "Queries by Status",
        "description": "Distribution of queries by execution status (Success, Fail, etc.) for the selected object.",
        "chart_type": "pie",
        "x_col": "EXECUTION_STATUS", # Used as names for pie
        "y_col": "QUERY_COUNT", # Used as values for pie
        "hover_data": ["QUERY_COUNT"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "top_10_most_expensive_queries_by_user_chart": {
        "query": """
            SELECT
                QUERY_ID,
                SUBSTRING(QUERY_TEXT, 1, 100) AS QUERY_TEXT_SNIPPET, -- Take first 100 chars
                COALESCE(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0) / (1000 * 60) AS EXECUTION_TIME_MIN,
                WAREHOUSE_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            ORDER BY EXECUTION_TIME_MIN DESC
            LIMIT 10
        """,
        "label": "Top 10 Expensive Queries (Min)",
        "description": "Top 10 longest running successful queries by the selected object. Review these for optimization.",
        "chart_type": "bar",
        "x_col": "QUERY_TEXT_SNIPPET",
        "y_col": "EXECUTION_TIME_MIN",
        "hover_data": ["QUERY_ID", "WAREHOUSE_NAME"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "execution_time_by_warehouse_chart": {
        "query": """
            SELECT
                WAREHOUSE_NAME,
                COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60) AS TOTAL_EXECUTION_TIME_MIN
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND WAREHOUSE_NAME IS NOT NULL
                {object_filter}
            GROUP BY 1
            ORDER BY 2 DESC
        """,
        "label": "Execution Time by Warehouse",
        "description": "Total query execution time by the selected object, broken down by warehouse. Helps identify primary cost centers.",
        "chart_type": "bar",
        "x_col": "WAREHOUSE_NAME",
        "y_col": "TOTAL_EXECUTION_TIME_MIN",
        "hover_data": ["TOTAL_EXECUTION_TIME_MIN"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "daily_data_scanned_tb_by_user_chart": {
        "query": """
            SELECT
                TO_DATE(START_TIME) AS QUERY_DATE,
                COALESCE(SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)), 0) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND BYTES_SCANNED > 0
                {object_filter}
            GROUP BY 1
            ORDER BY 1
        """,
        "label": "Daily Data Scanned (TB)",
        "description": "Daily trend of data scanned by queries executed by the selected object.",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_col": "TOTAL_DATA_SCANNED_TB",
        "hover_data": ["TOTAL_DATA_SCANNED_TB"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "query_type_distribution_by_user_chart": {
        "query": """
            SELECT
                QUERY_TYPE,
                COUNT(QUERY_ID) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND QUERY_TYPE IS NOT NULL
                {object_filter}
            GROUP BY 1
            ORDER BY 2 DESC
        """,
        "label": "Query Type Distribution",
        "description": "Breakdown of query types (e.g., SELECT, INSERT) executed by the selected object. Provides insight into usage patterns.",
        "chart_type": "pie",
        "x_col": "QUERY_TYPE",
        "y_col": "QUERY_COUNT",
        "hover_data": ["QUERY_COUNT"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "daily_compile_time_by_user_chart": {
        "query": """
            SELECT
                TO_DATE(START_TIME) AS QUERY_DATE,
                COALESCE(SUM(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)), 0) / 1000 AS TOTAL_COMPILATION_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY 1
            ORDER BY 1
        """,
        "label": "Daily Compile Time (Sec)",
        "description": "Daily trend of total query compilation time by the selected object. High spikes might suggest unoptimized queries or schema issues.",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_col": "TOTAL_COMPILATION_TIME_SEC",
        "hover_data": ["TOTAL_COMPILATION_TIME_SEC"],
        "show_table_toggle": True,
        "apply_object_filter": True
    },
    "daily_queueing_blocked_time_by_user_chart": {
        "query": """
            SELECT
                TO_DATE(START_TIME) AS QUERY_DATE,
                COALESCE(AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)), 0) / 1000 AS AVG_QUEUED_OVERLOAD_TIME_SEC,
                COALESCE(AVG(TRY_TO_NUMBER(QUEUED_REPAIR_TIME, 38, 0)), 0) / 1000 AS AVG_QUEUED_REPAIR_TIME_SEC,
                COALESCE(AVG(TRY_TO_NUMBER(QUEUED_PROVISIONING_TIME, 38, 0)), 0) / 1000 AS AVG_QUEUED_PROVISIONING_TIME_SEC,
                COALESCE(AVG(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0)), 0) / 1000 AS AVG_BLOCKED_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY 1
            ORDER BY 1
        """,
        "label": "Daily Queueing/Blocked Time (Sec)",
        "description": "Daily average time queries spent queueing or blocked for the selected object. High values indicate warehouse contention or sizing issues.",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_col": ["AVG_QUEUED_OVERLOAD_TIME_SEC", "AVG_BLOCKED_TIME_SEC"], # Can plot multiple lines
        "hover_data": ["AVG_QUEUED_OVERLOAD_TIME_SEC", "AVG_QUEUED_REPAIR_TIME_SEC", "AVG_QUEUED_PROVISIONING_TIME_SEC", "AVG_BLOCKED_TIME_SEC"],
        "show_table_toggle": True,
        "apply_object_filter": True,
        "toggle_options": { # Example of how you might add toggle options
            "overload_only": {
                "label": "Overload Queue",
                "y_col": "AVG_QUEUED_OVERLOAD_TIME_SEC",
            },
            "blocked_only": {
                "label": "Blocked Time",
                "y_col": "AVG_BLOCKED_TIME_SEC",
            }
        }
    }
}