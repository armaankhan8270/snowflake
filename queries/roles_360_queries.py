# queries/roles_360_queries.py
"""
SQL query definitions for the Roles 360 Dashboard.
These queries use placeholders for dynamic filtering:
- {start_date}, {end_date}: For date range filtering.
- {object_filter}: For filtering by the selected role (if apply_object_filter is True).
"""

ROLES_360_QUERIES = {
    "total_roles": {
        "query": """
            SELECT COUNT(DISTINCT NAME)
            FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES
            WHERE DELETED_ON IS NULL
            {object_filter}
        """,
        "label": "Total Active Roles",
        "description": "Total number of active roles in Snowflake. This counts roles, not grants.",
        "format": "number",
        "apply_object_filter": True # Will apply ROLE_NAME filter if selected
    },
    "users_with_role": {
        "query": """
            SELECT COUNT(DISTINCT GRANTEE_NAME)
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE GRANTED_ON = 'ROLE'
            AND GRANTEES_TO_ROLES.GRANTEE_TYPE = 'USER'
            AND GRANT_TIME >= '{start_date}' AND GRANT_TIME <= '{end_date}'
            {object_filter}
        """,
        "label": "Users Granted Selected Role",
        "description": "Number of distinct users who were granted the selected role within the date range. Note: This counts grants, not necessarily active users of the role.",
        "format": "number",
        "apply_object_filter": True # Will apply ROLE_NAME filter if selected
    },
    "queries_by_role": {
        "query": """
            SELECT COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            {object_filter}
        """,
        "label": "Queries Executed by Role",
        "description": "Total number of queries executed by users assigned to the selected role within the specified date range.",
        "format": "number",
        "apply_object_filter": True # Will apply ROLE_NAME filter if selected
    },
    "avg_query_time_by_role": {
        "query": """
            SELECT AVG(EXECUTION_TIME)
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            {object_filter}
        """,
        "label": "Avg Query Time by Role",
        "description": "Average execution time (in milliseconds) for queries run by users with the selected role.",
        "format": "duration",
        "apply_object_filter": True # Will apply ROLE_NAME filter if selected
    },
    "top_users_in_role_by_queries": {
        "query": """
            SELECT USER_NAME, COUNT(*) AS QUERY_COUNT, SUM(EXECUTION_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            {object_filter}
            GROUP BY USER_NAME
            ORDER BY QUERY_COUNT DESC
            LIMIT 10
        """,
        "label": "Top Users for Selected Role by Query Count/Time",
        "description": "Shows the top 10 most active users who utilized the selected role, by query count or total execution time.",
        "chart_type": "bar",
        "x_col": "USER_NAME",
        "y_col": "QUERY_COUNT",
        "toggle_options": {
            "query_count": {"label": "By Query Count", "y_col": "QUERY_COUNT"},
            "execution_time": {"label": "By Execution Time (ms)", "y_col": "TOTAL_EXECUTION_TIME_MS", "format": "duration"}
        },
        "hover_data": ["QUERY_COUNT", "TOTAL_EXECUTION_TIME_MS"],
        "apply_object_filter": True # This chart *should* be filtered by the selected role.
    },
    "top_roles_by_total_queries": {
        "query": """
            SELECT ROLE_NAME, COUNT(*) AS TOTAL_QUERIES, SUM(TOTAL_ELAPSED_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            AND ROLE_NAME IS NOT NULL
            GROUP BY ROLE_NAME
            ORDER BY TOTAL_QUERIES DESC
            LIMIT 10
        """,
        "label": "Top 10 Roles by Query Volume / Execution Time (All Roles)",
        "description": "Identifies the roles with the highest query volume or total execution time across the entire Snowflake account for the selected period, regardless of the role filter.",
        "chart_type": "bar",
        "x_col": "ROLE_NAME",
        "y_col": "TOTAL_QUERIES",
        "toggle_options": {
            "query_count": {"label": "By Query Count", "y_col": "TOTAL_QUERIES"},
            "execution_time": {"label": "By Execution Time (ms)", "y_col": "TOTAL_EXECUTION_TIME_MS", "format": "duration"}
        },
        "hover_data": ["TOTAL_QUERIES", "TOTAL_EXECUTION_TIME_MS"],
        "apply_object_filter": False # This chart should *always* show top roles globally.
    },
    "queries_by_warehouse_for_role": {
        "query": """
            SELECT WAREHOUSE_NAME, COUNT(*) AS QUERY_COUNT, SUM(TOTAL_ELAPSED_TIME) AS TOTAL_EXECUTION_TIME_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{start_date}' AND START_TIME <= '{end_date}'
            AND WAREHOUSE_NAME IS NOT NULL
            {object_filter}
            GROUP BY WAREHOUSE_NAME
            ORDER BY QUERY_COUNT DESC
            LIMIT 10
        """,
        "label": "Warehouse Usage for Selected Role",
        "description": "Breakdown of queries executed by users of the selected role, by warehouse, showing query count or execution time.",
        "chart_type": "bar",
        "x_col": "WAREHOUSE_NAME",
        "y_col": "QUERY_COUNT",
        "toggle_options": {
            "queries": {"label": "Total Queries", "y_col": "QUERY_COUNT"},
            "execution_time": {"label": "Total Execution Time (ms)", "y_col": "TOTAL_EXECUTION_TIME_MS", "format": "duration"}
        },
        "hover_data": ["QUERY_COUNT", "TOTAL_EXECUTION_TIME_MS"],
        "apply_object_filter": True # Should be filtered by the selected role.
    },
    "role_grants_history": {
        "query": """
            SELECT GRANT_TIME::DATE AS GRANT_DATE,
                   COUNT(*) AS GRANTS_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE GRANT_TIME >= '{start_date}' AND GRANT_TIME <= '{end_date}'
            AND GRANTED_ON = 'ROLE'
            {object_filter}
            GROUP BY GRANT_DATE
            ORDER BY GRANT_DATE ASC
        """,
        "label": "Role Grants History (Selected Role)",
        "description": "Historical trend of how many times the selected role was granted or revoked daily.",
        "chart_type": "line",
        "x_col": "GRANT_DATE",
        "y_col": "GRANTS_COUNT",
        "show_table_toggle": True,
        "apply_object_filter": True # Should be filtered by the selected role.
    },
    "role_privilege_summary": {
        "query": """
            SELECT PRIVILEGE, COUNT(*) AS PRIVILEGE_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE GRANTED_ON != 'ROLE' -- Exclude role grants to roles themselves
            AND GRANT_TIME >= '{start_date}' AND GRANT_TIME <= '{end_date}'
            {object_filter} -- This will be the role name filter
            GROUP BY PRIVILEGE
            ORDER BY PRIVILEGE_COUNT DESC
            LIMIT 10
        """,
        "label": "Top Privileges Granted to Role",
        "description": "Lists the most common privileges granted directly to the selected role. This does not account for inherited privileges.",
        "chart_type": "bar",
        "x_col": "PRIVILEGE",
        "y_col": "PRIVILEGE_COUNT",
        "hover_data": ["PRIVILEGE_COUNT"],
        "apply_object_filter": True
    },
    "role_cost_by_warehouse_heatmap": {
        "query": """
            SELECT QH.WAREHOUSE_NAME, QH.ROLE_NAME,
                   SUM(WH.CREDITS_USED) AS TOTAL_CREDITS_USED
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY AS QH
            JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY AS WH
                ON QH.WAREHOUSE_ID = WH.WAREHOUSE_ID
                AND QH.START_TIME BETWEEN WH.START_TIME AND WH.END_TIME
            WHERE QH.START_TIME >= '{start_date}' AND QH.START_TIME <= '{end_date}'
            AND QH.WAREHOUSE_NAME IS NOT NULL
            {object_filter} -- This will filter by role_name if selected
            GROUP BY QH.WAREHOUSE_NAME, QH.ROLE_NAME
            ORDER BY TOTAL_CREDITS_USED DESC
        """,
        "label": "Role Cost by Warehouse Heatmap",
        "description": "Visualizes the credit consumption for the selected role across different warehouses. Higher values indicate more cost.",
        "chart_type": "heatmap",
        "x_col": "WAREHOUSE_NAME",
        "y_col": "ROLE_NAME",
        "value_col": "TOTAL_CREDITS_USED",
        "color_continuous_scale": "Viridis",
        "hover_data": ["TOTAL_CREDITS_USED"],
        "apply_object_filter": True
    }
}