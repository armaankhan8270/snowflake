# queries/user_360_queries.py

"""
SQL query definitions for the User 360 Dashboard.
These queries use placeholders for dynamic filtering:
- {start_date}: For date range filtering (expects ISO 8601 format or similar string convertible by TRY_TO_TIMESTAMP_NTZ).
- {user_filter}: Dynamically inserted WHERE clause for user filtering (e.g., "AND USER_NAME = 'selected_user_name'").
  If no user is selected, this placeholder will be replaced by "AND 1=1" to keep the WHERE clause valid.
"""

USER_360_QUERIES = {
    # --- Core Metrics (KPIs) ---
    "total_queries_run": {
        "query": """
            SELECT
                COUNT(*) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND user_name IS NOT NULL
                {user_filter}
                AND query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                AND execution_status IN ('SUCCESS', 'FAIL');
        """,
        "label": "Total Queries Run",
        "description": "Total number of non-meta queries (successful or failed) in the period.",
        "format": "number",
        "apply_object_filter": True # Applies if a specific user is selected
    },
    "total_users_defined": {
        "query": """
            SELECT
                COUNT(*) AS METRIC_VALUE
            FROM
                snowflake.account_usage.users
            WHERE
                deleted_on IS NULL;
        """,
        "label": "Total Users Defined",
        "description": "Total number of active user accounts defined in Snowflake.",
        "format": "number",
        "apply_object_filter": False # This is a global metric, user filter doesn't apply
    },
    "total_active_users": {
        "query": """
            SELECT
                COUNT(DISTINCT user_name) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND user_name IS NOT NULL
                {user_filter};
        """,
        "label": "Total Active Users",
        "description": "Count of distinct users who executed queries in the selected period.",
        "format": "number",
        "apply_object_filter": True # If 'All' is selected, it shows all active. If user is selected, it's 1 or 0.
    },
    "avg_cost_per_user": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            user_costs AS (
                SELECT
                    qh.user_name,
                    ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0), 2) AS user_cost
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
            )
            SELECT COALESCE(ROUND(AVG(user_cost), 2), 0) AS METRIC_VALUE
            FROM user_costs;
        """,
        "label": "Avg Cost Per User (USD)",
        "description": "Average estimated USD cost per active user in the period ($3/credit assumed).",
        "format": "currency",
        "apply_object_filter": True # Applies if a specific user is selected (showing avg for that user), or overall avg.
    },
    "high_cost_users_count": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            user_costs AS (
                SELECT
                    qh.user_name,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) AS user_cost
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
                HAVING
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) > 100 -- Users with > $100 cost
            )
            SELECT COUNT(*) AS METRIC_VALUE FROM user_costs;
        """,
        "label": "High Cost Users (> $100)",
        "description": "Number of users whose estimated cost exceeds $100 in the period.",
        "format": "number",
        "apply_object_filter": True # If 'All' is selected, shows global count. If user is selected, 1 or 0.
    },
    "failed_queries_percentage": {
        "query": """
            WITH query_stats AS (
                SELECT
                    COUNT(*) AS total_queries,
                    COUNT(CASE WHEN execution_status = 'FAIL' THEN 1 END) AS failed_queries
                FROM
                    snowflake.account_usage.query_history
                WHERE
                    start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND user_name IS NOT NULL
                    {user_filter}
            )
            SELECT COALESCE(ROUND((failed_queries * 100.0 / NULLIF(total_queries, 0)), 2), 0) AS METRIC_VALUE
            FROM query_stats;
        """,
        "label": "Failed Queries %",
        "description": "Percentage of queries that failed in the selected period.",
        "format": "percentage",
        "apply_object_filter": True # Applies to selected user or overall
    },
    "avg_query_duration": {
        "query": """
            SELECT
                COALESCE(ROUND(AVG(total_elapsed_time) / 1000.0, 2), 0) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND total_elapsed_time > 0
                AND execution_status = 'SUCCESS'
                AND user_name IS NOT NULL
                {user_filter};
        """,
        "label": "Avg Query Duration (s)",
        "description": "Average duration of successful queries in seconds.",
        "format": "duration_seconds",
        "apply_object_filter": True # Applies to selected user or overall
    },
    "percentage_high_cost_users": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            user_total_costs AS (
                SELECT
                    qh.user_name,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) AS total_user_cost_usd
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.warehouse_name IS NOT NULL
                    AND qh.user_name IS NOT NULL
                    AND 1=1 -- Ensure a valid WHERE clause even if {user_filter} is empty
                GROUP BY
                    qh.user_name
            ),
            cost_statistics AS (
                SELECT
                    COALESCE(AVG(total_user_cost_usd), 0) AS overall_average_cost,
                    COUNT(*) AS total_active_user_count
                FROM user_total_costs
            ),
            high_cost_users AS (
                SELECT
                    urc.user_name,
                    urc.total_user_cost_usd,
                    cs.overall_average_cost
                FROM
                    user_total_costs urc
                CROSS JOIN
                    cost_statistics cs
                WHERE
                    cs.overall_average_cost > 0
                    AND urc.total_user_cost_usd >= 1.5 * cs.overall_average_cost -- 1.5x average cost
            )
            SELECT
                COALESCE(
                    ROUND(
                        (SELECT COUNT(*) FROM high_cost_users) * 100.0 /
                        NULLIF((SELECT total_active_user_count FROM cost_statistics), 0),
                        2
                    ),
                    0
                ) AS METRIC_VALUE;
        """,
        "label": "% High Cost Users",
        "description": "Percentage of users whose estimated cost is 1.5x or more than the average user cost.",
        "format": "percentage",
        "apply_object_filter": False # This is a global metric, user filter doesn't apply directly
    },

    # --- Charts & Detailed Tables ---
    "cost_by_user_and_role": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            user_costs AS (
                SELECT
                    qh.user_name AS NAME,
                    ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0), 2) AS COST_USD,
                    'User' AS TYPE
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.warehouse_name IS NOT NULL
                    AND qh.user_name IS NOT NULL
                    AND 1=1 -- Ensure a valid WHERE clause even if {user_filter} is empty
                GROUP BY
                    qh.user_name
            ),
            role_costs AS (
                SELECT
                    qh.role_name AS NAME,
                    ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0), 2) AS COST_USD,
                    'Role' AS TYPE
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.warehouse_name IS NOT NULL
                    AND qh.role_name IS NOT NULL
                    AND 1=1 -- Ensure a valid WHERE clause even if {user_filter} is empty
                GROUP BY
                    qh.role_name
            )
            SELECT NAME, COST_USD, TYPE FROM user_costs
            UNION ALL
            SELECT NAME, COST_USD, TYPE FROM role_costs
            ORDER BY COST_USD DESC
            LIMIT 10;
        """,
        "label": "Top 10 Users/Roles by Cost",
        "description": "Identifies the top users and roles by estimated USD cost.",
        "chart_type": "bar",
        "x_col": "NAME",
        "y_col": "COST_USD",
        "color_col": "TYPE",
        "hover_data": ["NAME", "COST_USD", "TYPE"],
        "apply_object_filter": False # This should always show global top 10 for users/roles
    },
    "cost_by_user_priority": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            user_raw_costs AS (
                SELECT
                    qh.user_name,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) AS raw_total_cost_usd,
                    COUNT(DISTINCT qh.query_id) AS query_count,
                    AVG(qh.total_elapsed_time / 1000.0) AS raw_avg_duration_sec,
                    COUNT(CASE WHEN qh.execution_status = 'FAIL' THEN 1 END) AS failed_queries
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
            ),
            user_avg_cost AS (
                SELECT
                    COALESCE(AVG(raw_total_cost_usd), 0) AS overall_avg_cost
                FROM user_raw_costs
            )
            SELECT
                urc.user_name AS USER_NAME,
                ROUND(urc.raw_total_cost_usd, 2) AS TOTAL_COST_USD,
                urc.query_count AS QUERY_COUNT,
                ROUND(urc.raw_avg_duration_sec, 2) AS AVG_DURATION_SEC,
                urc.failed_queries AS FAILED_QUERIES,
                CASE
                   WHEN urc.raw_total_cost_usd >= 2.0 * uac.overall_avg_cost THEN 'Critical Cost Risk 🔴'
                   WHEN urc.raw_total_cost_usd >= 1.5 * uac.overall_avg_cost THEN 'High Cost Exposure 🟠'
                   WHEN urc.raw_total_cost_usd > uac.overall_avg_cost THEN 'Above Average Spend 🟡'
                   ELSE 'Optimized Usage 🟢'
                END AS PRIORITY_LEVEL
            FROM user_raw_costs urc
            CROSS JOIN user_avg_cost uac
            ORDER BY urc.raw_total_cost_usd DESC
            LIMIT 15;
        """,
        "label": "User Cost & Priority Level",
        "description": "Users ranked by estimated cost, with a priority level indicating deviation from average.",
        "chart_type": "table",
        "apply_object_filter": True # If 'All' is selected, shows global top users by priority
    },
    "query_performance_bottlenecks": {
        "query": """
            WITH query_analysis AS (
                SELECT
                    query_id, -- Added for potential drill-down
                    user_name,
                    warehouse_name,
                    query_type,
                    total_elapsed_time / 1000.0 AS total_duration_sec,
                    execution_status,
                    partitions_scanned,
                    bytes_scanned
                FROM
                    snowflake.account_usage.query_history
                WHERE
                    start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND user_name IS NOT NULL
                    AND warehouse_name IS NOT NULL -- Ensure warehouse is known
                    AND query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                    {user_filter}
            )
            SELECT
                user_name AS USER_NAME,
                warehouse_name AS WAREHOUSE_NAME,
                query_type AS QUERY_TYPE,
                COUNT(*) AS QUERY_COUNT,
                ROUND(AVG(total_duration_sec), 2) AS AVG_DURATION_SEC,
                ROUND(MAX(total_duration_sec), 2) AS MAX_DURATION_SEC,
                COUNT(CASE WHEN total_duration_sec > 300 THEN 1 END) AS SLOW_QUERIES, -- Over 5 minutes (300 seconds)
                COUNT(CASE WHEN execution_status = 'FAIL' THEN 1 END) AS FAILED_QUERIES,
                ROUND((COUNT(CASE WHEN total_duration_sec > 300 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) AS SLOW_QUERY_PERCENTAGE,
                CASE
                    WHEN COUNT(CASE WHEN total_duration_sec > 300 THEN 1 END) > 0.1 * COUNT(*) THEN 'Critical'
                    WHEN COUNT(CASE WHEN total_duration_sec > 60 THEN 1 END) > 0.1 * COUNT(*) THEN 'Warning'
                    WHEN COUNT(CASE WHEN execution_status = 'FAIL' THEN 1 END) > 0.05 * COUNT(*) THEN 'Warning'
                    ELSE 'Good'
                END AS PERFORMANCE_STATUS,
                CASE
                    WHEN COUNT(CASE WHEN total_duration_sec > 300 THEN 1 END) > 0.1 * COUNT(*) THEN 'Optimize query logic, review data distribution, consider warehouse right-sizing or clustering.'
                    WHEN COUNT(CASE WHEN execution_status = 'FAIL' THEN 1 END) > 0.05 * COUNT(*) THEN 'Investigate error logs, check permissions, validate SQL syntax.'
                    WHEN AVG(total_duration_sec) > 60 AND AVG(total_duration_sec) <= 300 THEN 'Consider scaling warehouse, review query joins/filters, check caching.'
                    ELSE 'Monitor performance regularly.'
                END AS RECOMMENDED_ACTION
            FROM query_analysis
            GROUP BY user_name, warehouse_name, query_type
            HAVING COUNT(*) > 5 -- Only show groups with meaningful activity
            ORDER BY SLOW_QUERIES DESC, AVG_DURATION_SEC DESC
            LIMIT 20;
        """,
        "label": "Query Performance Bottlenecks & Actions",
        "description": "Identifies common query performance issues by user/warehouse/query type and suggests actions.",
        "chart_type": "table",
        "apply_object_filter": True # If 'All' is selected, shows global bottlenecks
    },
    "user_behavior_patterns": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            cost_ranked_users AS (
                SELECT
                    qh.user_name,
                    ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0), 2) AS total_cost_usd
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
                ORDER BY
                    total_cost_usd DESC
                LIMIT 10 -- Focus on top N users for heatmap if 'All' is selected, or the selected user
            ),
            hourly_usage AS (
                SELECT
                    qh.user_name,
                    EXTRACT(HOUR FROM qh.start_time) AS hour_of_day,
                    COUNT(*) AS query_count,
                    ROUND(AVG(qh.total_elapsed_time / 1000.0), 2) AS avg_duration
                FROM
                    snowflake.account_usage.query_history qh
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.user_name IN (SELECT user_name FROM cost_ranked_users) -- Filter by top users or specific user
                    {user_filter}
                GROUP BY
                    qh.user_name, EXTRACT(HOUR FROM qh.start_time)
            )
            SELECT
                user_name AS USER_NAME,
                hour_of_day AS HOUR_OF_DAY,
                SUM(query_count) AS TOTAL_QUERIES,
                ROUND(AVG(query_count), 2) AS AVG_QUERIES_PER_HOUR,
                ROUND(AVG(avg_duration), 2) AS AVG_DURATION_SEC,
                CASE
                    WHEN hour_of_day BETWEEN 0 AND 6 THEN 'Off-Hours'
                    WHEN hour_of_day BETWEEN 7 AND 18 THEN 'Business Hours'
                    ELSE 'Evening'
                END AS TIME_CATEGORY
            FROM hourly_usage
            GROUP BY user_name, hour_of_day
            ORDER BY user_name, hour_of_day;
        """,
        "label": "User Query Activity by Hour",
        "description": "Heatmap showing query activity volume by hour of day for top/selected users, highlighting peak usage times.",
        "chart_type": "heatmap",
        "x_col": "HOUR_OF_DAY",
        "y_col": "USER_NAME",
        "value_col": "TOTAL_QUERIES",
        "color_continuous_scale": "YlGnBu",
        "hover_data": ["TOTAL_QUERIES", "AVG_QUERIES_PER_HOUR", "AVG_DURATION_SEC", "TIME_CATEGORY"],
        "apply_object_filter": True # If 'All' is selected, shows top users' behavior. If user, shows specific user.
    },
    "optimization_opportunities": {
        "query": """
            WITH warehouse_rates AS (
                SELECT * FROM VALUES
                    ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                    ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
                AS warehouse_size(size, credits_per_hour)
            ),
            cost_ranked_users AS (
                SELECT
                    qh.user_name,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) AS total_cost_usd
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
                ORDER BY
                    total_cost_usd DESC
                LIMIT 10
            ),
            optimization_analysis AS (
                SELECT
                    qh.user_name,
                    qh.warehouse_name,
                    COUNT(qh.query_id) AS total_queries,
                    COUNT(CASE WHEN qh.total_elapsed_time > 300000 THEN 1 END) AS long_queries, -- Over 5 mins
                    COUNT(CASE WHEN qh.execution_status = 'FAIL' THEN 1 END) AS failed_queries,
                    COUNT(CASE WHEN COALESCE(qh.bytes_scanned, 0) > 1000000000 THEN 1 END) AS high_scan_queries, -- Over 1 GB
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * 3.0) AS total_cost_usd,
                    AVG(qh.total_elapsed_time / 1000.0) AS avg_duration
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    AND qh.user_name IN (SELECT user_name FROM cost_ranked_users) -- Ensure it's for relevant users
                    {user_filter}
                GROUP BY
                    qh.user_name, qh.warehouse_name
            )
            SELECT
                user_name AS USER_NAME,
                warehouse_name AS WAREHOUSE_NAME,
                total_queries AS TOTAL_QUERIES,
                long_queries AS LONG_QUERIES,
                failed_queries AS FAILED_QUERIES,
                high_scan_queries AS HIGH_SCAN_QUERIES,
                ROUND(total_cost_usd, 2) AS TOTAL_COST_USD,
                ROUND(avg_duration, 2) AS AVG_DURATION_SEC,
                ROUND((long_queries * 100.0 / NULLIF(total_queries, 0)), 2) AS LONG_QUERY_PERCENTAGE,
                ROUND((failed_queries * 100.0 / NULLIF(total_queries, 0)), 2) AS FAILURE_RATE,
                CASE
                    WHEN total_cost_usd > 1000 AND long_queries > 0.1 * total_queries THEN 'High Cost & Slow Queries'
                    WHEN total_cost_usd > 500 THEN 'High Cost User/Warehouse'
                    WHEN long_queries > 0.2 * total_queries THEN 'Frequent Long Queries'
                    WHEN failed_queries > 0.1 * total_queries THEN 'High Query Failure Rate'
                    WHEN high_scan_queries > 0.3 * total_queries THEN 'High Data Scan (Inefficient Queries)'
                    ELSE 'Good Performance'
                END AS OPTIMIZATION_PRIORITY,
                CASE
                    WHEN total_cost_usd > 1000 AND long_queries > 0.1 * total_queries THEN 'Review expensive queries, right-size warehouse, implement auto-suspend, consider clustering.'
                    WHEN total_cost_usd > 500 THEN 'Analyze user query patterns, optimize frequently run queries, right-size warehouse.'
                    WHEN long_queries > 0.2 * total_queries THEN 'Tune query filters, joins, use appropriate data types, consider materialized views.'
                    WHEN failed_queries > 0.1 * total_queries THEN 'Debug query errors, check user permissions, validate data integrity.'
                    WHEN high_scan_queries > 0.3 * total_queries THEN 'Implement table clustering, optimize micro-partitioning, review query WHERE clauses.'
                    ELSE 'Continue monitoring for efficiency gains.'
                END AS RECOMMENDED_ACTION
            FROM optimization_analysis
            WHERE total_queries > 10 -- Only show warehouses/users with significant activity
            ORDER BY TOTAL_COST_USD DESC, LONG_QUERY_PERCENTAGE DESC;
        """,
        "label": "Optimization Opportunities & Recommendations",
        "description": "Identifies key areas for cost and performance optimization based on user and warehouse usage patterns.",
        "chart_type": "table",
        "apply_object_filter": True # If 'All' is selected, shows global opportunities.
    }
}