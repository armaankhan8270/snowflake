# queries/user_360_queries.py

"""
SQL query definitions for the User 360 FinOps Dashboard.
These queries use placeholders for dynamic filtering and configuration:
- {start_date}: For date range filtering (expects ISO 8601 format or similar string convertible by TRY_TO_TIMESTAMP_NTZ).
- {end_date}: For date range filtering (expects ISO 8601 format or similar string convertible by TRY_TO_TIMESTAMP_NTZ).
- {user_filter}: Dynamically inserted WHERE clause for user filtering (e.g., "AND USER_NAME = 'selected_user_name'").
  If no user is selected, this placeholder will be replaced by "AND 1=1" to keep the WHERE clause valid.
- {credit_cost_per_dollar}: Placeholder for the dynamic credit cost (e.g., 3.0 for $3 per credit).
  Your application should supply this value, defaulting to 3.0 if a dynamic lookup is not possible.
"""

USER_360_QUERIES = {
    # --- GLOBAL CTEs / Common Logic (Internal - Not a query exposed directly) ---
    # This CTE defines warehouse sizes and their credit rates. It will be reused across queries.
    "_WAREHOUSE_RATES_CTE": """
        WITH warehouse_rates AS (
            SELECT * FROM VALUES
                ('X-Small', 1), ('Small', 2), ('Medium', 4), ('Large', 8),
                ('X-Large', 16), ('2X-Large', 32), ('3X-Large', 64), ('4X-Large', 128)
            AS warehouse_size(size, credits_per_hour)
        )
    """,

    # --- FinOps KPIs: High-Impact Metrics for Top-Level Overview ---
    "total_estimated_cost_usd": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            SELECT
                COALESCE(
                    ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}), 2),
                    0
                ) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history qh
            JOIN
                warehouse_rates wr ON qh.warehouse_size = wr.size
            WHERE
                qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND qh.warehouse_name IS NOT NULL
                AND qh.user_name IS NOT NULL
                {user_filter};
        """,
        "label": "Total Estimated Cost (USD)",
        "description": "Total estimated compute cost for queries executed in the selected period for the selected user(s). This is your primary FinOps metric.",
        "format": "currency",
        "apply_object_filter": True
    },
    "total_queries_run": {
        "query": """
            SELECT
                COUNT(*) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND user_name IS NOT NULL
                {user_filter}
                AND query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                AND execution_status IN ('SUCCESS', 'FAIL');
        """,
        "label": "Total Queries Executed",
        "description": "Total count of analytical and DML queries (successful or failed) executed by the selected user(s).",
        "format": "number",
        "apply_object_filter": True
    },
    "query_success_rate_percentage": {
        "query": """
            SELECT
                COALESCE(
                    ROUND(
                        (COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) * 100.0) /
                        NULLIF(COUNT(*), 0),
                        2
                    ), 0
                ) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND user_name IS NOT NULL
                {user_filter}
                AND query_type NOT IN ('DESCRIBE', 'SHOW', 'USE');
        """,
        "label": "Query Success Rate %",
        "description": "Percentage of non-meta queries that completed successfully. A low rate indicates potential user errors, permission issues, or data problems.",
        "format": "percentage",
        "apply_object_filter": True
    },
    "avg_cost_per_query_usd": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            SELECT
                COALESCE(
                    ROUND(
                        SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}) /
                        NULLIF(COUNT(qh.query_id), 0),
                        4
                    ),
                    0
                ) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history qh
            JOIN
                warehouse_rates wr ON qh.warehouse_size = wr.size
            WHERE
                qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND qh.warehouse_name IS NOT NULL
                AND qh.user_name IS NOT NULL
                AND qh.query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                {user_filter};
        """,
        "label": "Avg Cost Per Query (USD)",
        "description": "Average estimated cost for a single query. High values might indicate inefficient individual queries or over-provisioned warehouses for common tasks.",
        "format": "currency",
        "apply_object_filter": True
    },
    "avg_query_queue_time_sec": {
        "query": """
            SELECT
                COALESCE(ROUND(AVG(queued_overload_time + queued_provisioning_time) / 1000.0, 2), 0) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND user_name IS NOT NULL
                {user_filter}
                AND query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                AND (queued_overload_time > 0 OR queued_provisioning_time > 0);
        """,
        "label": "Avg Query Queue Time (s)",
        "description": "Average time queries spent waiting due to warehouse overload or provisioning. High queue times suggest warehouse contention or undersizing.",
        "format": "duration_seconds",
        "apply_object_filter": True
    },
    "avg_query_spill_to_disk_mb": {
        "query": """
            SELECT
                COALESCE(ROUND(AVG(bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) / (1024*1024.0), 2), 0) AS METRIC_VALUE
            FROM
                snowflake.account_usage.query_history
            WHERE
                start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND user_name IS NOT NULL
                {user_filter}
                AND (bytes_spilled_to_local_storage > 0 OR bytes_spilled_to_remote_storage > 0);
        """,
        "label": "Avg Query Spill to Disk (MB)",
        "description": "Average data spilled to local or remote disk during query execution. Significant spilling indicates memory pressure, potentially requiring larger warehouses or query optimization.",
        "format": "data_mb",
        "apply_object_filter": True
    },

    # --- Detailed FinOps Insights: Tables & Charts for Deeper Analysis ---
    "user_cost_efficiency_table": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            WITH user_metrics AS (
                SELECT
                    qh.user_name,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}) AS total_cost_usd,
                    COUNT(qh.query_id) AS total_queries,
                    SUM(COALESCE(qh.bytes_scanned, 0)) AS total_bytes_scanned,
                    AVG(qh.total_elapsed_time / 1000.0) AS avg_duration_sec,
                    COUNT(CASE WHEN qh.execution_status = 'FAIL' THEN 1 END) AS failed_queries,
                    SUM(COALESCE(qh.bytes_spilled_to_local_storage, 0) + COALESCE(qh.bytes_spilled_to_remote_storage, 0)) AS total_spilled_bytes
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY
                    qh.user_name
                HAVING
                    COUNT(qh.query_id) > 0
            ),
            overall_stats AS (
                SELECT
                    AVG(total_cost_usd) AS overall_avg_cost,
                    STDDEV(total_cost_usd) AS overall_stddev_cost,
                    AVG(avg_duration_sec) AS overall_avg_duration,
                    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_cost_usd) AS p90_cost,
                    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avg_duration_sec) AS p90_duration,
                    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_spilled_bytes) AS p90_spill_bytes
                FROM user_metrics
            )
            SELECT
                um.user_name AS USER_NAME,
                ROUND(um.total_cost_usd, 2) AS TOTAL_COST_USD,
                um.total_queries AS TOTAL_QUERIES,
                ROUND(um.total_cost_usd / NULLIF(um.total_queries, 0), 4) AS COST_PER_QUERY_USD,
                ROUND(um.total_bytes_scanned / (1024*1024*1024.0), 2) AS TOTAL_BYTES_SCANNED_GB,
                ROUND(um.total_cost_usd / NULLIF(um.total_bytes_scanned / (1024*1024*1024.0), 0), 4) AS COST_PER_GB_SCANNED_USD,
                ROUND(um.avg_duration_sec, 2) AS AVG_QUERY_DURATION_SEC,
                ROUND(um.failed_queries * 100.0 / NULLIF(um.total_queries, 0), 2) AS FAILED_QUERY_PERCENTAGE,
                ROUND(um.total_spilled_bytes / (1024*1024.0), 2) AS TOTAL_SPILLED_MB,
                CASE
                    WHEN um.total_cost_usd > os.p90_cost AND um.avg_duration_sec > os.p90_duration THEN 'Critical: High Cost & Slow Performance 🔴'
                    WHEN um.total_cost_usd > os.p90_cost THEN 'High Cost User 🟠'
                    WHEN um.avg_duration_sec > os.p90_duration THEN 'Frequent Performance Bottleneck 🟡'
                    WHEN um.total_spilled_bytes > os.p90_spill_bytes THEN 'High Data Spilling 🟡'
                    WHEN um.failed_queries * 100.0 / NULLIF(um.total_queries, 0) > 10 THEN 'High Failure Rate 🟠' -- >10% failed queries
                    ELSE 'Good Efficiency 🟢'
                END AS FINOPS_PRIORITY_LEVEL,
                CASE
                    WHEN um.total_cost_usd > os.p90_cost AND um.avg_duration_sec > os.p90_duration THEN 'Action: Prioritize deep-dive into user''s most expensive and longest-running queries. Evaluate warehouse usage patterns (auto-suspend, multi-cluster), and explore query re-writes, clustering, or search optimization.'
                    WHEN um.total_cost_usd > os.p90_cost THEN 'Action: Analyze top cost drivers for this user. Are they using large warehouses for simple tasks? Identify queries with high compilation or execution time. Recommend right-sizing warehouses or query simplification.'
                    WHEN um.avg_duration_sec > os.p90_duration THEN 'Action: Investigate frequent long-running queries. Focus on query structure, join efficiency, and data pruning. Consider increasing warehouse size or implementing auto-scaling for peak loads.'
                    WHEN um.total_spilled_bytes > os.p90_spill_bytes THEN 'Action: Queries are exceeding memory limits. Recommend using a larger warehouse for specific workloads, or optimize queries to reduce intermediate data processing (e.g., complex joins, large aggregations).'
                    WHEN um.failed_queries * 100.0 / NULLIF(um.total_queries, 0) > 10 THEN 'Action: Review error messages for common failure patterns (e.g., invalid object names, permission denied, syntax errors). Provide user training or fix data/access issues.'
                    ELSE 'Action: User''s usage is efficient. Continue monitoring for changes and leverage their patterns as a best practice example.'
                END AS RECOMMENDED_ACTION
            FROM user_metrics um
            CROSS JOIN overall_stats os
            ORDER BY TOTAL_COST_USD DESC, AVG_QUERY_DURATION_SEC DESC
            LIMIT 20;
        """,
        "label": "User FinOps Efficiency & Actionable Insights",
        "description": "Comprehensive table showing user-level cost, performance, and efficiency metrics, coupled with calculated priority levels and specific FinOps recommendations.",
        "chart_type": "table",
        "apply_object_filter": True
    },
    "daily_cost_trend_by_user": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            WITH daily_user_costs AS (
                SELECT
                    DATE_TRUNC('DAY', CONVERT_TZ(qh.start_time, 'UTC', 'Asia/Kolkata')) AS ACTIVITY_DATE, -- Local time
                    qh.user_name AS USER_NAME,
                    SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}) AS DAILY_COST_USD
                FROM
                    snowflake.account_usage.query_history qh
                JOIN
                    warehouse_rates wr ON qh.warehouse_size = wr.size
                WHERE
                    qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                    AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                    AND qh.user_name IS NOT NULL
                    AND qh.warehouse_name IS NOT NULL
                    {user_filter}
                GROUP BY 1, 2
            )
            SELECT
                ACTIVITY_DATE,
                USER_NAME,
                ROUND(DAILY_COST_USD, 2) AS DAILY_COST_USD
            FROM daily_user_costs
            ORDER BY ACTIVITY_DATE, DAILY_COST_USD DESC;
        """,
        "label": "Daily Cost Trend by User",
        "description": "Time-series chart showing the daily estimated cost for selected user(s). Helps identify cost spikes and usage patterns over time.",
        "chart_type": "line",
        "x_col": "ACTIVITY_DATE",
        "y_col": "DAILY_COST_USD",
        "color_col": "USER_NAME", # If 'All' users are selected, this will show multiple lines
        "hover_data": ["ACTIVITY_DATE", "USER_NAME", "DAILY_COST_USD"],
        "apply_object_filter": True # If 'All' is selected, will show trends for top users implicitly or explicitly via other queries.
    },
    "cost_by_warehouse_size_distribution": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            SELECT
                qh.warehouse_size AS WAREHOUSE_SIZE,
                ROUND(SUM(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}), 2) AS TOTAL_COST_USD,
                (TOTAL_COST_USD * 100.0) / SUM(TOTAL_COST_USD) OVER () AS COST_PERCENTAGE
            FROM
                snowflake.account_usage.query_history qh
            JOIN
                warehouse_rates wr ON qh.warehouse_size = wr.size
            WHERE
                qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND qh.warehouse_name IS NOT NULL
                AND qh.user_name IS NOT NULL
                {user_filter}
            GROUP BY
                qh.warehouse_size
            ORDER BY
                TOTAL_COST_USD DESC;
        """,
        "label": "Cost Distribution by Warehouse Size",
        "description": "Pie chart showing the breakdown of estimated costs by warehouse size. Reveals if larger warehouses are disproportionately contributing to spend.",
        "chart_type": "pie",
        "names_col": "WAREHOUSE_SIZE",
        "values_col": "TOTAL_COST_USD",
        "hover_data": ["WAREHOUSE_SIZE", "TOTAL_COST_USD", "COST_PERCENTAGE"],
        "apply_object_filter": True # Can show for selected user or overall
    },
    "query_performance_scatter_analysis": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            SELECT
                qh.query_id AS QUERY_ID,
                qh.user_name AS USER_NAME,
                qh.warehouse_name AS WAREHOUSE_NAME,
                ROUND(qh.total_elapsed_time / 1000.0, 2) AS DURATION_SECONDS,
                ROUND(COALESCE(qh.bytes_scanned, 0) / (1024*1024.0), 2) AS BYTES_SCANNED_MB,
                ROUND(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}, 4) AS ESTIMATED_COST_USD,
                qh.execution_status AS STATUS,
                CASE
                    WHEN qh.total_elapsed_time > 300000 AND COALESCE(qh.bytes_scanned, 0) > 1000000000 THEN 'High Cost & Long Run' -- >5min and >1GB
                    WHEN qh.total_elapsed_time > 60000 THEN 'Long Running (>1min)'
                    WHEN COALESCE(qh.bytes_scanned, 0) > 500000000 THEN 'High Data Scan (>500MB)'
                    WHEN qh.execution_status = 'FAIL' THEN 'Failed Query'
                    ELSE 'Efficient Query'
                END AS OPTIMIZATION_CATEGORY
            FROM
                snowflake.account_usage.query_history qh
            JOIN
                warehouse_rates wr ON qh.warehouse_size = wr.size
            WHERE
                qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND qh.user_name IS NOT NULL
                AND qh.warehouse_name IS NOT NULL
                AND qh.query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                {user_filter}
            QUALIFY
                ROW_NUMBER() OVER (PARTITION BY USER_NAME ORDER BY ESTIMATED_COST_USD DESC) <= 50 OR -- Top 50 by cost per user
                ROW_NUMBER() OVER (PARTITION BY USER_NAME ORDER BY DURATION_SECONDS DESC) <= 50   -- Top 50 by duration per user
            ORDER BY ESTIMATED_COST_USD DESC
            LIMIT 500; -- Limit overall results for scatter plot performance
        """,
        "label": "Query Cost vs. Performance Scatter",
        "description": "Scatter plot visualizing query duration against bytes scanned, color-coded by optimization category and sized by cost. Helps identify queries that are expensive, slow, or scan too much data.",
        "chart_type": "scatter",
        "x_col": "BYTES_SCANNED_MB",
        "y_col": "DURATION_SECONDS",
        "color_col": "OPTIMIZATION_CATEGORY",
        "size_col": "ESTIMATED_COST_USD", # Bubble size reflects cost
        "hover_data": ["QUERY_ID", "USER_NAME", "WAREHOUSE_NAME", "DURATION_SECONDS", "BYTES_SCANNED_MB", "ESTIMATED_COST_USD", "STATUS"],
        "apply_object_filter": True
    },
    "top_n_expensive_queries_detailed": {
        "query": """
            {_WAREHOUSE_RATES_CTE}
            SELECT
                qh.query_id AS QUERY_ID,
                qh.user_name AS USER_NAME,
                qh.warehouse_name AS WAREHOUSE_NAME,
                qh.query_text AS QUERY_TEXT,
                ROUND(qh.total_elapsed_time / 1000.0, 2) AS DURATION_SECONDS,
                ROUND(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}, 2) AS ESTIMATED_COST_USD,
                qh.start_time AS START_TIME_UTC,
                qh.end_time AS END_TIME_UTC,
                qh.partitions_scanned AS PARTITIONS_SCANNED,
                ROUND(COALESCE(qh.bytes_scanned, 0) / (1024*1024.0), 2) AS BYTES_SCANNED_MB,
                ROUND(COALESCE(qh.bytes_spilled_to_local_storage, 0) / (1024*1024.0), 2) AS SPILL_LOCAL_MB,
                ROUND(COALESCE(qh.bytes_spilled_to_remote_storage, 0) / (1024*1024.0), 2) AS SPILL_REMOTE_MB,
                ROUND((qh.queued_overload_time + qh.queued_provisioning_time) / 1000.0, 2) AS QUEUE_TIME_SEC,
                qh.execution_status AS STATUS,
                CASE
                    WHEN qh.total_elapsed_time > 300000 AND COALESCE(qh.bytes_scanned, 0) > 1000000000 THEN 'Critical: High Cost + Long Run + Large Scan'
                    WHEN qh.total_elapsed_time > 300000 THEN 'Long Running (>5 min)'
                    WHEN COALESCE(qh.bytes_scanned, 0) > 1000000000 THEN 'Large Data Scan (>1 GB)'
                    WHEN qh.execution_status = 'FAIL' THEN 'Failed Query'
                    WHEN ROUND(qh.total_elapsed_time / 1000.0 / 3600.0 * wr.credits_per_hour * {credit_cost_per_dollar}, 2) > 10 THEN 'High Cost Query (> $10)' -- Example threshold for single query cost
                    ELSE 'Review Recommended'
                END AS OPTIMIZATION_CATEGORY,
                CASE
                    WHEN qh.total_elapsed_time > 300000 OR COALESCE(qh.bytes_scanned, 0) > 1000000000 THEN 'Action: This is a prime target for optimization. Analyze the query profile via Snowflake UI (Query ID: ' || qh.query_id || '). Look for large joins, full table scans, or complex aggregations. Consider: adding clustering keys, using materialized views, optimizing WHERE clauses, or breaking down into smaller queries.'
                    WHEN qh.execution_status = 'FAIL' THEN 'Action: Examine the error message in the query history. Common fixes: validate object names, check permissions, ensure data type compatibility, or correct SQL syntax errors.'
                    WHEN (COALESCE(qh.bytes_spilled_to_local_storage, 0) + COALESCE(qh.bytes_spilled_to_remote_storage, 0)) > 100000000 THEN 'Action: Excessive spilling indicates memory pressure. Consider using a larger warehouse size for this query, or optimize joins/aggregations to reduce intermediate data size.'
                    WHEN ROUND((qh.queued_overload_time + qh.queued_provisioning_time) / 1000.0, 2) > 10 THEN 'Action: High queue time suggests warehouse concurrency issues. Review warehouse scaling policies or consider using a dedicated warehouse for this workload.'
                    ELSE 'Action: This query could still be optimized. Review its purpose, how often it runs, and consider if its output can be pre-computed or if a smaller warehouse could be used.'
                END AS RECOMMENDATION_ACTION
            FROM
                snowflake.account_usage.query_history qh
            JOIN
                warehouse_rates wr ON qh.warehouse_size = wr.size
            WHERE
                qh.start_time >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND qh.start_time <= TRY_TO_TIMESTAMP_NTZ('{end_date}')
                AND qh.user_name IS NOT NULL
                AND qh.warehouse_name IS NOT NULL
                AND qh.query_type NOT IN ('DESCRIBE', 'SHOW', 'USE')
                {user_filter}
            ORDER BY
                ESTIMATED_COST_USD DESC
            LIMIT 50; -- Top 50 most expensive queries for detailed investigation and action
        """,
        "label": "Top 50 Most Impactful Queries for Optimization",
        "description": "Lists the top N queries by estimated cost, providing detailed performance metrics, optimization categories, and highly specific actions for FinOps engineers to take. This is your primary drill-down table.",
        "chart_type": "table",
        "apply_object_filter": True
    }
}