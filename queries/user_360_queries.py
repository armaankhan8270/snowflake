# queries/user_360_queries.py
"""
SQL query definitions for the User 360 Dashboard.
These queries use placeholders for dynamic filtering:
- {start_date}, {end_date}: For date range filtering.
- {object_filter}: For filtering by the selected user (if apply_object_filter is True).
"""

USER_360_QUERIES = {
    "total_queries_by_user": {
        "query": """
            SELECT COUNT(*) AS TOTAL_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
        """,
        "label": "Total Queries by User",
        "description": "Total number of queries executed by the selected user.",
        "format": "number",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "total_execution_time_by_user": {
        "query": """
            SELECT SUM(EXECUTION_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
        """,
        "label": "Total Execution Time",
        "description": "Total query execution time for the selected user in milliseconds.",
        "format": "duration",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "avg_execution_time_by_user": {
        "query": """
            SELECT AVG(EXECUTION_TIME) AS AVG_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
        """,
        "label": "Avg Execution Time",
        "description": "Average query execution time for the selected user.",
        "format": "duration",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "data_scanned_by_user": {
        "query": """
            SELECT SUM(BYTES_SCANNED) / POW(1024, 3) AS DATA_SCANNED_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
        """,
        "label": "Data Scanned (GB)",
        "description": "Total data scanned by the selected user in gigabytes.",
        "format": "number",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "failed_queries_by_user_metric": { # Renamed for clarity vs chart
        "query": """
            SELECT COUNT(*) AS FAILED_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND ERROR_MESSAGE IS NOT NULL
              {object_filter}
        """,
        "label": "Failed Queries",
        "description": "Number of failed queries for the selected user.",
        "format": "number",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "long_running_queries_by_user_metric": { # Renamed for clarity vs chart
        "query": """
            SELECT COUNT(*) AS LONG_RUNNING_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND EXECUTION_TIME > 1000 -- Over 1 second
              {object_filter}
        """,
        "label": "Long-Running Queries",
        "description": "Number of queries exceeding 1 second execution time for the selected user.",
        "format": "number",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    "distinct_warehouses_used_by_user": {
        "query": """
            SELECT COUNT(DISTINCT WAREHOUSE_NAME) AS DISTINCT_WAREHOUSES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND WAREHOUSE_NAME IS NOT NULL
              {object_filter}
        """,
        "label": "Distinct Warehouses Used",
        "description": "Number of distinct warehouses used by the selected user.",
        "format": "number",
        "apply_object_filter": True # Will apply USER_NAME filter if selected
    },
    # --- Charts ---
    "top_users_by_data_scanned": {
        "query": """
            SELECT USER_NAME,
                   SUM(BYTES_SCANNED) / POW(1024, 3) AS DATA_SCANNED_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            GROUP BY USER_NAME
            ORDER BY DATA_SCANNED_GB DESC
            LIMIT 10
        """,
        "label": "Top 10 Users by Data Scanned (All Users)",
        "description": "Identifies the top 10 users consuming the most data (in GB) across all users.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "DATA_SCANNED_GB",
        "hover_data": ["DATA_SCANNED_GB"],
        "apply_object_filter": False # This chart should *always* show top users globally.
    },
    "top_users_by_execution_time": {
        "query": """
            SELECT USER_NAME,
                   SUM(EXECUTION_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            GROUP BY USER_NAME
            ORDER BY TOTAL_EXECUTION_TIME_MS DESC
            LIMIT 10
        """,
        "label": "Top 10 Users by Execution Time (All Users)",
        "description": "Identifies the top 10 users with the highest total query execution time (in milliseconds) across all users.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "TOTAL_EXECUTION_TIME_MS",
        "hover_data": ["TOTAL_EXECUTION_TIME_MS"],
        "apply_object_filter": False # This chart should *always* show top users globally.
    },
    "top_users_by_query_count": {
        "query": """
            SELECT USER_NAME,
                   COUNT(*) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            GROUP BY USER_NAME
            ORDER BY QUERY_COUNT DESC
            LIMIT 10
        """,
        "label": "Top 10 Users by Query Count (All Users)",
        "description": "Identifies the top 10 users with the highest number of queries executed across all users.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "QUERY_COUNT",
        "hover_data": ["QUERY_COUNT"],
        "apply_object_filter": False # This chart should *always* show top users globally.
    },
    "execution_time_vs_query_count_scatter": { # Renamed key for clarity
        "query": """
            SELECT USER_NAME,
                   COUNT(*) AS QUERY_COUNT,
                   SUM(EXECUTION_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
            GROUP BY USER_NAME
        """,
        "label": "Execution Time vs Query Count (Selected User)",
        "description": "A scatter plot showing the relationship between total query count and total execution time for the selected user. If 'All Users' is selected, this will plot for all users.",
        "chart_type": "scatter",
        "x_col": "QUERY_COUNT",
        "y_col": "TOTAL_EXECUTION_TIME_MS",
        "hover_data": ["USER_NAME", "QUERY_COUNT", "TOTAL_EXECUTION_TIME_MS"],
        "apply_object_filter": True # This chart should apply the user filter if present.
    },
    "daily_query_trend_by_user": { # Renamed key for clarity
        "query": """
            SELECT TO_DATE(START_TIME) AS QUERY_DATE,
                   USER_NAME,
                   COUNT(*) AS TOTAL_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              {object_filter}
            GROUP BY QUERY_DATE, USER_NAME
            ORDER BY QUERY_DATE ASC
        """,
        "label": "Daily Query Trend (Selected User)",
        "description": "Shows the daily trend of query execution for the selected user. If 'All Users' is selected, it will show trends for all users (potentially aggregated).",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_col": "TOTAL_QUERIES",
        "color_col": "USER_NAME", # Useful if object_filter is 'all'
        "hover_data": ["TOTAL_QUERIES", "USER_NAME"],
        "apply_object_filter": True # This chart should apply the user filter if present.
    },
    "query_failures_by_user_chart": { # Renamed for clarity vs metric
        "query": """
            SELECT USER_NAME,
                   COUNT(*) AS FAILED_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND ERROR_MESSAGE IS NOT NULL
              {object_filter}
            GROUP BY USER_NAME
            ORDER BY FAILED_QUERIES DESC
            LIMIT 10
        """,
        "label": "Top Users by Query Failures",
        "description": "Bar chart showing users with the highest number of failed queries.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "FAILED_QUERIES",
        "hover_data": ["FAILED_QUERIES"],
        "apply_object_filter": True # Should filter if a specific user is selected, otherwise show top global.
    },
    "long_running_queries_by_user_chart": { # Renamed for clarity vs metric
        "query": """
            SELECT USER_NAME,
                   COUNT(*) AS LONG_RUNNING_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND EXECUTION_TIME > 1000 -- Over 1 second
              {object_filter}
            GROUP BY USER_NAME
            ORDER BY LONG_RUNNING_QUERIES DESC
            LIMIT 10
        """,
        "label": "Top Users by Long-Running Queries",
        "description": "Bar chart showing users with the highest number of queries exceeding 1 second execution time.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "LONG_RUNNING_QUERIES",
        "hover_data": ["LONG_RUNNING_QUERIES"],
        "apply_object_filter": True # Should filter if a specific user is selected, otherwise show top global.
    },
    "user_warehouse_heatmap": {
        "query": """
            SELECT USER_NAME,
                   WAREHOUSE_NAME,
                   COUNT(*) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
              AND WAREHOUSE_NAME IS NOT NULL
              {object_filter}
            GROUP BY USER_NAME, WAREHOUSE_NAME
        """,
        "label": "User vs Warehouse Usage Heatmap (Selected User)",
        "description": "Heatmap showing query count distribution for the selected user across different warehouses. If 'All Users' is selected, this will show for all users.",
        "chart_type": "heatmap",
        "x_col": "WAREHOUSE_NAME",
        "y_col": "USER_NAME",
        "value_col": "QUERY_COUNT",
        "color_continuous_scale": "YlGnBu", # Changed to a common heatmap color scale
        "hover_data": ["QUERY_COUNT"],
        "apply_object_filter": True # Should filter if a specific user is selected, otherwise show global usage.
    },
}