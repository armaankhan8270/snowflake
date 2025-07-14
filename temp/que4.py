{
    "1_wasted_compute_failed_cancelled_queries": {
        "label": "Wasted Compute (Failed/Cancelled Queries)",
        "description": "High-impact metric showing users burning credits on failed/cancelled queries, indicating issues with query development or environment stability.",
        "query": """
            SELECT
                USER_NAME,
                SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                COUNT(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN 1 ELSE NULL END) AS FAILED_OR_CANCELLED_QUERIES,
                ROUND(WASTED_COMPUTE_HOURS * {{cost_per_credit}}, 2) AS ESTIMATED_WASTED_CREDITS_USD
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP()) -- Last 30 days
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING FAILED_OR_CANCELLED_QUERIES > 0
            ORDER BY WASTED_COMPUTE_HOURS DESC;
        """,
        "bad_user_pattern": "Users with consistently high wasted compute hours, especially with a low success rate, are likely pushing untested code or encountering frequent data/logic errors.",
        "action": "Implement mandatory query testing in development environments. Review complex ETL/ELT pipelines for robustness. Encourage smaller, modular queries. Set appropriate statement timeouts."
    },
    "2_query_efficiency_index_data_scanned_to_output": {
        "label": "Query Efficiency Index (Data Scanned vs. Output)",
        "description": "Identifies users scanning massive amounts of data for disproportionately small results, signaling inefficient data access patterns.",
        "query": """
            SELECT
                USER_NAME,
                COUNT(CASE WHEN BYTES_SCANNED > 0 AND BYTES_WRITTEN > 0 THEN 1 ELSE NULL END) AS EFFICIENT_QUERIES,
                COUNT(CASE WHEN BYTES_SCANNED > 0 AND (BYTES_WRITTEN IS NULL OR BYTES_WRITTEN = 0) THEN 1 ELSE NULL END) AS SELECT_ONLY_QUERIES,
                COUNT(*) AS TOTAL_QUERIES,
                SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) AS TOTAL_BYTES_SCANNED,
                SUM(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0)) AS TOTAL_BYTES_WRITTEN,
                AVG(CASE WHEN BYTES_WRITTEN > 0 THEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0) ELSE NULL END) AS AVG_SCAN_TO_OUTPUT_RATIO,
                AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) AS AVG_DATA_SCANNED_TB_PER_QUERY
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                EXECUTION_STATUS = 'SUCCESS'
                AND START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING TOTAL_BYTES_SCANNED > 0
            ORDER BY AVG_SCAN_TO_OUTPUT_RATIO DESC NULLS LAST;
        """,
        "bad_user_pattern": "An 'AVG_SCAN_TO_OUTPUT_RATIO' consistently above 1000 (for write operations) or 'AVG_DATA_SCANNED_TB_PER_QUERY' above a threshold (e.g., 1 TB) for 'SELECT_ONLY_QUERIES' without corresponding large result sets, indicates poor filtering, missing WHERE clauses, or full table scans.",
        "action": "Promote judicious use of `WHERE` clauses. Advise on column pruning (`SELECT specific_columns` instead of `SELECT *`). Recommend proper clustering keys and materialized views for frequently queried large tables. Investigate if data model requires denormalization for specific analytical workloads."
    },
    "3_warehouse_sizing_mismatch_spill_rate": {
        "label": "Warehouse Sizing Mismatch (Spill Rate)",
        "description": "Highlights users whose queries frequently spill to local or remote storage, suggesting their chosen warehouse size is insufficient for their workload or queries are not optimized.",
        "query": """
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0) THEN 1 ELSE NULL END) AS SPILLING_QUERIES,
                ROUND(100.0 * SPILLING_QUERIES / NULLIF(TOTAL_QUERIES, 0), 2) AS SPILL_RATE_PCT,
                AVG(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0)) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                EXECUTION_STATUS = 'SUCCESS'
                AND START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING TOTAL_QUERIES > 20 AND SPILL_RATE_PCT > 5 -- Focus on users with consistent query volume and spill
            ORDER BY SPILL_RATE_PCT DESC;
        """,
        "bad_user_pattern": "A 'SPILL_RATE_PCT' consistently above 10% (especially for `BYTES_SPILLED_TO_REMOTE_STORAGE`) coupled with long query execution times, indicates that the current warehouse size is not adequately handling their query complexity or data volume. This leads to performance degradation and higher costs.",
        "action": "Analyze the specific queries causing spills; optimize JOIN order and complexity. Recommend using a larger virtual warehouse (e.g., Medium to Large) for heavy analytical queries or complex ETL. Advise on breaking down large queries into smaller steps using CTEs or temporary tables. Review data types for efficiency."
    },
    "4_compilation_overhead_index": {
        "label": "Compilation Overhead Index",
        "description": "Identifies users whose queries spend a disproportionate amount of time compiling rather than executing, often due to dynamic SQL, frequent DDL, or lack of query caching.",
        "query": """
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                SUM(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS TOTAL_COMPILE_TIME_SEC,
                SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS TOTAL_EXECUTION_TIME_SEC,
                AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / NULLIF(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) AS COMPILE_TO_EXEC_RATIO,
                AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS AVG_COMPILE_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                EXECUTION_STATUS = 'SUCCESS'
                AND COMPILATION_TIME > 0
                AND START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING TOTAL_QUERIES > 50 AND AVG_COMPILE_TIME_SEC > 1 -- Focus on users with frequent and noticeable compilation
            ORDER BY COMPILE_TO_EXEC_RATIO DESC NULLS LAST;
        """,
        "bad_user_pattern": "A 'COMPILE_TO_EXEC_RATIO' consistently above 0.3 (30%) or 'AVG_COMPILE_TIME_SEC' above 2 seconds, especially for recurring queries, indicates that queries are not leveraging Snowflake's result cache or are being dynamically generated too frequently, leading to unnecessary compilation cycles.",
        "action": "Encourage the use of prepared statements and parameterized queries where applicable. Advise against frequent DDL operations within production pipelines. Ensure queries are designed to leverage Snowflake's result caching by being deterministic and not including non-deterministic functions (e.g., `CURRENT_TIMESTAMP()`) without appropriate `WHERE` clauses."
    },
    "5_concurrency_contention_impact_queued_blocked_time": {
        "label": "Concurrency Contention Impact (Queued/Blocked Time)",
        "description": "Shows users whose queries are frequently queued or blocked, indicating they are contributing to or suffering from warehouse contention, impacting overall performance and user experience.",
        "query": """
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0) > 0 THEN 1 ELSE NULL END) AS QUEUED_OVERLOAD_QUERIES,
                COUNT(CASE WHEN TRY_TO_NUMBER(BLOCKED_TIME, 38, 0) > 0 THEN 1 ELSE NULL END) AS BLOCKED_QUERIES,
                ROUND(AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000, 2) AS AVG_QUEUE_TIME_SEC,
                ROUND(AVG(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0)) / 1000, 2) AS AVG_BLOCKED_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                EXECUTION_STATUS = 'SUCCESS'
                AND START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING TOTAL_QUERIES > 20
            ORDER BY (AVG_QUEUE_TIME_SEC + AVG_BLOCKED_TIME_SEC) DESC NULLS LAST;
        """,
        "bad_user_pattern": "Consistently high 'AVG_QUEUE_TIME_SEC' or 'AVG_BLOCKED_TIME_SEC' (e.g., > 10 seconds), especially during peak business hours, suggests that either the warehouse is undersized for the concurrent workload, or the user is submitting very long-running, resource-intensive queries without proper scheduling.",
        "action": "For heavy users, consider dedicated virtual warehouses or multi-cluster warehouses. Implement workload management and resource monitors. Advise on scheduling large batch queries during off-peak hours. Review query design to reduce resource intensity (e.g., less complex joins, pre-aggregation)."
    },
    "6_unoptimized_data_access_concentration": {
        "label": "Unoptimized Data Access Concentration",
        "description": "Identifies users repeatedly accessing a small set of objects inefficiently, without leveraging features like result caching or materialized views, leading to redundant compute.",
        "query": """
            SELECT
                QH.USER_NAME,
                COUNT(DISTINCT A.VALUE:objectName || '.' || A.VALUE:objectType) AS UNIQUE_ACCESSED_OBJECTS,
                COUNT(*) AS TOTAL_QUERIES_ACCESSING_OBJECTS,
                ROUND(TOTAL_QUERIES_ACCESSING_OBJECTS::FLOAT / NULLIF(UNIQUE_ACCESSED_OBJECTS, 0), 2) AS ACCESS_CONCENTRATION_RATIO
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY QH,
                 LATERAL FLATTEN(INPUT => PARSE_JSON(QUERY_TAG), PATH => 'accessedObjects', OUTER => TRUE) A -- Assuming object access info in QUERY_TAG for more detail if needed, else use ACCESS_HISTORY. For this example, let's stick to ACCESS_HISTORY as it's more direct.
            WHERE
                QH.START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND QH.EXECUTION_STATUS = 'SUCCESS'
                AND QH.USER_NAME IS NOT NULL
                AND A.VALUE IS NOT NULL -- Ensure objects were accessed
            GROUP BY QH.USER_NAME
            HAVING TOTAL_QUERIES_ACCESSING_OBJECTS > 50 AND UNIQUE_ACCESSED_OBJECTS > 1 -- Ensure meaningful activity
            ORDER BY ACCESS_CONCENTRATION_RATIO DESC;
            -- NOTE: The above query uses QUERY_HISTORY and flattens a (hypothetical) QUERY_TAG.
            -- A more direct approach for accessed objects is SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY.
            -- Let's use ACCESS_HISTORY for better accuracy as it's designed for this.
            -- Re-writing with ACCESS_HISTORY for more direct and reliable object access info:
            -- Query for Access History for objects accessed in Queries.
            -- This will show how many distinct objects a user accesses and how many times they access them.
            -- A higher concentration on a few objects might mean repetitive queries that could be cached or materialized.
            SELECT
                T1.USER_NAME,
                COUNT(DISTINCT T2.OBJECT_ID) AS UNIQUE_ACCESSED_OBJECTS,
                COUNT(*) AS TOTAL_ACCESSES_VIA_QUERY,
                ROUND(TOTAL_ACCESSES_VIA_QUERY::FLOAT / NULLIF(UNIQUE_ACCESSED_OBJECTS, 0), 2) AS ACCESS_CONCENTRATION_RATIO
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY T1
            JOIN SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY T2
                ON T1.QUERY_ID = T2.QUERY_ID
            WHERE
                T1.START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND T1.EXECUTION_STATUS = 'SUCCESS'
                AND T1.USER_NAME IS NOT NULL
                AND T2.OBJECT_TYPE IN ('TABLE', 'VIEW', 'MATERIALIZED_VIEW') -- Focus on data objects
            GROUP BY T1.USER_NAME
            HAVING TOTAL_ACCESSES_VIA_QUERY > 50 AND UNIQUE_ACCESSED_OBJECTS > 1
            ORDER BY ACCESS_CONCENTRATION_RATIO DESC;
        """,
        "bad_user_pattern": "A high 'ACCESS_CONCENTRATION_RATIO' (e.g., >50) where a user is repeatedly querying the same small set of objects without the expected result cache hits, suggests these queries are either non-deterministic or users are not aware of/leveraging caching mechanisms.",
        "action": "Educate users on Snowflake's result caching. Identify highly concentrated objects and consider creating materialized views for them if the underlying data changes infrequently. Promote standardizing query patterns to maximize cache hits. Review queries for non-deterministic functions that prevent caching."
    },
    "7_peak_hour_resource_hogging": {
        "label": "Peak Hour Resource Hogging",
        "description": "Identifies users running expensive queries during peak business hours, potentially impacting other users and driving up costs unnecessarily.",
        "query": """
            SELECT
                USER_NAME,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 ELSE NULL END) AS PEAK_HOUR_QUERIES,
                SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) AS PEAK_HOUR_COMPUTE_HOURS,
                SUM(TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
                ROUND((PEAK_HOUR_COMPUTE_HOURS / NULLIF(TOTAL_COMPUTE_HOURS, 0)) * 100, 2) AS PCT_PEAK_HOUR_COMPUTE_USAGE
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                EXECUTION_STATUS = 'SUCCESS'
                AND START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING PEAK_HOUR_QUERIES > 20 AND PEAK_HOUR_COMPUTE_HOURS > 1 -- Focus on users with meaningful peak hour activity
            ORDER BY PCT_PEAK_HOUR_COMPUTE_USAGE DESC;
        """,
        "bad_user_pattern": "Users with a high percentage of their total compute hours spent during peak business hours (e.g., > 50%) running long-running queries (e.g., > 30 minutes execution time on average) indicates poor workload scheduling or lack of awareness of peak vs. off-peak costs.",
        "action": "Implement query governance policies to prevent long-running queries during peak hours. Advise users to schedule heavy ETL/batch jobs during off-peak hours. Utilize separate warehouses for interactive vs. batch workloads. Implement resource monitors with suspend/notify actions."
    },
    "8_cost_to_value_ratio_user_cost_contribution": {
        "label": "Cost-to-Value Ratio (User Cost Contribution)",
        "description": "Analyzes a user's total compute cost against a proxy for their 'value' (e.g., successful query count, data written), helping to identify high-cost users whose contribution might not justify the expense.",
        "query": """
            SELECT
                USER_NAME,
                SUM(TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
                COUNT(CASE WHEN EXECUTION_STATUS = 'SUCCESS' THEN 1 ELSE NULL END) AS SUCCESSFUL_QUERIES,
                SUM(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0)) / POW(1024, 3) AS TOTAL_DATA_WRITTEN_GB,
                ROUND(TOTAL_COMPUTE_HOURS * {{cost_per_credit}}, 2) AS ESTIMATED_COST_USD,
                ROUND(ESTIMATED_COST_USD / NULLIF(SUCCESSFUL_QUERIES, 0), 2) AS COST_PER_SUCCESSFUL_QUERY_USD,
                ROUND(ESTIMATED_COST_USD / NULLIF(TOTAL_DATA_WRITTEN_GB, 0), 2) AS COST_PER_GB_WRITTEN_USD
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                AND USER_NAME IS NOT NULL
            GROUP BY USER_NAME
            HAVING TOTAL_COMPUTE_HOURS > 0.1 -- Focus on users with some activity
            ORDER BY ESTIMATED_COST_USD DESC;
        """,
        "bad_user_pattern": "Users with a high 'ESTIMATED_COST_USD' but low 'SUCCESSFUL_QUERIES' or 'TOTAL_DATA_WRITTEN_GB' (if their role is data ingestion/transformation). Or, a 'COST_PER_SUCCESSFUL_QUERY_USD' significantly higher than the team average without a clear justification (e.g., highly complex, infrequent analytical reports). This indicates they are costing more without proportionate output or value.",
        "action": "For high-cost, low-value users, deep dive into their specific queries to identify inefficiencies. Engage with the user to understand their workflow and objectives. Provide targeted training. If justified, consider optimizing their specific data models or providing pre-aggregated datasets. If no value is derived, assess the necessity of their access."
    }
}

{
    "user_compute_cost_efficiency_matrix_chart": {
        "query": """
            SELECT
                USER_NAME,
                SUM(TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
                SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB,
                ROUND(TOTAL_COMPUTE_HOURS / NULLIF(TOTAL_DATA_SCANNED_TB, 0), 4) AS COMPUTE_EFFICIENCY_RATIO,
                COUNT(*) AS TOTAL_QUERIES,
                ROUND(TOTAL_COMPUTE_HOURS * {{cost_per_credit}}, 2) AS ESTIMATED_COST_DOLLARS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND BYTES_SCANNED > 0
                AND USER_NAME IS NOT NULL
                {{object_filter}} -- Apply object filter if provided
            GROUP BY USER_NAME
            HAVING TOTAL_COMPUTE_HOURS > 1 AND TOTAL_DATA_SCANNED_TB > 0.001 -- Meaningful activity
            ORDER BY COMPUTE_EFFICIENCY_RATIO DESC NULLS LAST;
        """,
        "label": "User Compute Cost Efficiency Matrix",
        "description": "Scatter plot showing users by cost efficiency (compute time vs. data processed). Users in the top-right quadrant (high compute, high data scan, potentially low efficiency ratio) need immediate optimization.",
        "chart_type": "scatter",
        "x_col": "TOTAL_DATA_SCANNED_TB",
        "y_col": "TOTAL_COMPUTE_HOURS",
        "size_col": "TOTAL_QUERIES",
        "color_col": "COMPUTE_EFFICIENCY_RATIO",
        "hover_data": ["USER_NAME", "ESTIMATED_COST_DOLLARS", "COMPUTE_EFFICIENCY_RATIO"],
        "show_table_toggle": true,
        "apply_object_filter": true
    },
    "daily_waste_pattern_heatmap_chart": {
        "query": """
            SELECT
                USER_NAME,
                DAYNAME(START_TIME) AS DAY_OF_WEEK,
                HOUR(START_TIME) AS HOUR_OF_DAY,
                SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                COUNT(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN 1 ELSE NULL END) AS FAILED_OR_CANCELLED_QUERIES,
                ROUND(WASTED_COMPUTE_HOURS * {{cost_per_credit}}, 2) AS WASTED_COST_DOLLARS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND USER_NAME IS NOT NULL
                {{object_filter}}
            GROUP BY USER_NAME, DAY_OF_WEEK, HOUR_OF_DAY
            HAVING WASTED_COMPUTE_HOURS > 0.01 -- Meaningful waste
            ORDER BY USER_NAME, 
                CASE DAY_OF_WEEK
                    WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2 WHEN 'Wed' THEN 3 WHEN 'Thu' THEN 4 WHEN 'Fri' THEN 5 WHEN 'Sat' THEN 6 WHEN 'Sun' THEN 7
                END, HOUR_OF_DAY;
        """,
        "label": "Daily & Hourly Waste Pattern Heatmap",
        "description": "Heatmap showing wasted compute by user, day of week, and hour of day. Consistent daily/hourly waste indicates systemic issues requiring intervention.",
        "chart_type": "heatmap",
        "x_col": "HOUR_OF_DAY",
        "y_col": "USER_NAME",
        "color_col": "WASTED_COMPUTE_HOURS",
        "hover_data": ["DAY_OF_WEEK", "FAILED_OR_CANCELLED_QUERIES", "WASTED_COST_DOLLARS"],
        "show_table_toggle": true,
        "apply_object_filter": true
    },
    "query_lifecycle_bottleneck_analysis_chart": {
        "query": """
            SELECT
                USER_NAME,
                TO_DATE(START_TIME) AS QUERY_DATE,
                AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS AVG_COMPILE_TIME_SEC,
                AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
                AVG(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0)) / 1000 AS AVG_BLOCKED_TIME_SEC,
                AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
                COUNT(*) AS DAILY_QUERIES_SUCCESS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND USER_NAME IS NOT NULL
                {{object_filter}}
            GROUP BY USER_NAME, QUERY_DATE
            HAVING DAILY_QUERIES_SUCCESS > 5
            ORDER BY USER_NAME, QUERY_DATE;
        """,
        "label": "Query Lifecycle Bottleneck Analysis",
        "description": "Multi-line chart showing where users spend time in the query lifecycle. High compile time suggests dynamic SQL abuse or lack of caching. High queue/blocked time indicates concurrency issues.",
        "chart_type": "line",
        "x_col": "QUERY_DATE",
        "y_cols": ["AVG_COMPILE_TIME_SEC", "AVG_QUEUE_TIME_SEC", "AVG_BLOCKED_TIME_SEC", "AVG_EXECUTION_TIME_SEC"],
        "color_col": "USER_NAME",
        "hover_data": ["DAILY_QUERIES_SUCCESS"],
        "show_table_toggle": true,
        "apply_object_filter": true
    },
    "spill_and_warehouse_size_impact_chart": {
        "query": """
            SELECT
                QH.USER_NAME,
                WH.WAREHOUSE_SIZE,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN (QH.BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR QH.BYTES_SPILLED_TO_REMOTE_STORAGE > 0) THEN 1 ELSE NULL END) AS SPILL_QUERIES,
                ROUND(100.0 * SPILL_QUERIES / NULLIF(TOTAL_QUERIES, 0), 2) AS SPILL_RATE_PCT,
                AVG(TRY_TO_NUMBER(QH.BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0)) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY QH
            JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY WM ON QH.WAREHOUSE_ID = WM.WAREHOUSE_ID
            JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES WH ON WM.WAREHOUSE_ID = WH.WAREHOUSE_ID
            WHERE
                QH.START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND QH.EXECUTION_STATUS = 'SUCCESS'
                AND QH.USER_NAME IS NOT NULL
                {{object_filter}}
            GROUP BY QH.USER_NAME, WH.WAREHOUSE_SIZE
            HAVING TOTAL_QUERIES > 10 AND SPILL_QUERIES > 0
            ORDER BY QH.USER_NAME, SPILL_RATE_PCT DESC;
        """,
        "label": "Spill & Warehouse Size Impact Chart",
        "description": "Grouped bar chart showing spill behavior by user and warehouse size. High spill rates on smaller warehouses might indicate under-sizing, while spills on larger warehouses suggest inefficient query design.",
        "chart_type": "grouped_bar",
        "x_col": "WAREHOUSE_SIZE",
        "y_col": "SPILL_RATE_PCT",
        "color_col": "USER_NAME",
        "hover_data": ["TOTAL_QUERIES", "SPILL_QUERIES", "AVG_REMOTE_SPILL_GB"],
        "show_table_toggle": true,
        "apply_object_filter": true
    },
    "error_categorization_and_frequency_chart": {
        "query": """
            SELECT
                USER_NAME,
                TO_DATE(START_TIME) AS ERROR_DATE,
                ERROR_CODE,
                COUNT(*) AS ERROR_COUNT,
                ROUND(AVG(TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0)) / 1000, 2) AS AVG_FAIL_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'FAILED'
                AND ERROR_CODE IS NOT NULL
                AND USER_NAME IS NOT NULL
                {{object_filter}}
            GROUP BY USER_NAME, ERROR_DATE, ERROR_CODE
            HAVING ERROR_COUNT > 1 -- Only show recurring errors
            ORDER BY USER_NAME, ERROR_DATE, ERROR_COUNT DESC;
        """,
        "label": "Error Categorization and Frequency Chart",
        "description": "Stacked bar or multi-line chart showing distinct error codes and their frequency per user over time. Helps pinpoint specific recurring issues (e.g., permissions, syntax, data type mismatches).",
        "chart_type": "stacked_bar",
        "x_col": "ERROR_DATE",
        "y_col": "ERROR_COUNT",
        "color_col": "ERROR_CODE",
        "group_by_col": "USER_NAME",
        "hover_data": ["AVG_FAIL_TIME_SEC"],
        "show_table_toggle": true,
        "apply_object_filter": true
    },
    "user_optimization_potential_score_breakdown": {
        "query": """
            SELECT
                USER_NAME,
                -- Waste Score (normalized 0-100)
                LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) / 10.0) * 100)) AS WASTE_SCORE, -- Assuming 10 hours of wasted compute is 100% bad
                -- Scan Inefficiency Score (normalized 0-100)
                LEAST(100, GREATEST(0, (AVG(CASE WHEN BYTES_WRITTEN > 0 THEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0) ELSE 0 END) / 1000.0) * 100)) AS SCAN_INEFFICIENCY_SCORE, -- Assuming a ratio of 1000 is 100% bad
                -- Memory Pressure Score (normalized 0-100)
                LEAST(100, GREATEST(0, (COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 20.0) * 100)) AS MEMORY_PRESSURE_SCORE, -- Assuming 20% spill rate is 100% bad
                -- Peak Hour Abuse Score (normalized 0-100)
                LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 50.0) * 100)) AS PEAK_HOUR_ABUSE_SCORE, -- Assuming 50% peak hour usage is 100% bad
                -- Total Opportunity Score
                ROUND((WASTE_SCORE + SCAN_INEFFICIENCY_SCORE + MEMORY_PRESSURE_SCORE + PEAK_HOUR_ABUSE_SCORE) / 4, 2) AS TOTAL_OPTIMIZATION_SCORE,
                COUNT(*) AS TOTAL_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE
                START_TIME BETWEEN TRY_TO_TIMESTAMP_NTZ('{start_date}') AND TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND USER_NAME IS NOT NULL
                {{object_filter}}
            GROUP BY USER_NAME
            HAVING TOTAL_QUERIES > 20
            ORDER BY TOTAL_OPTIMIZATION_SCORE DESC;
        """,
        "label": "User Optimization Potential Score Breakdown",
        "description": "Stacked bar chart showing the breakdown of optimization potential by user across different categories. A high 'TOTAL_OPTIMIZATION_SCORE' indicates significant room for improvement.",
        "chart_type": "stacked_bar",
        "x_col": "USER_NAME",
        "y_cols": ["WASTE_SCORE", "SCAN_INEFFICIENCY_SCORE", "MEMORY_PRESSURE_SCORE", "PEAK_HOUR_ABUSE_SCORE"],
        "hover_data": ["TOTAL_OPTIMIZATION_SCORE", "TOTAL_QUERIES"],
        "show_table_toggle": true,
        "apply_object_filter": true
    }
}


{
    "1_unoptimized_users_overview_table": {
        "label": "Unoptimized Users Overview",
        "description": "Lists users who exhibit multiple optimization opportunities, along with a summary of their impact.",
        "query": """
            WITH UserScores AS (
                SELECT
                    USER_NAME,
                    -- Waste Score
                    LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) / 5.0) * 100)) AS WASTE_SCORE,
                    -- Scan Inefficiency Score
                    LEAST(100, GREATEST(0, (AVG(CASE WHEN BYTES_WRITTEN > 0 THEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0) ELSE 0 END) / 500.0) * 100)) AS SCAN_INEFFICIENCY_SCORE,
                    -- Memory Pressure Score
                    LEAST(100, GREATEST(0, (COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 15.0) * 100)) AS MEMORY_PRESSURE_SCORE,
                    -- Peak Hour Abuse Score
                    LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 40.0) * 100)) AS PEAK_HOUR_ABUSE_SCORE,
                    COUNT(*) AS TOTAL_QUERIES,
                    SUM(TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
                    ROUND(TOTAL_COMPUTE_HOURS * {{cost_per_credit}}, 2) AS ESTIMATED_COST_USD
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE
                    START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                    AND USER_NAME IS NOT NULL
                GROUP BY USER_NAME
                HAVING TOTAL_QUERIES > 20
            )
            SELECT
                USER_NAME,
                WASTE_SCORE,
                SCAN_INEFFICIENCY_SCORE,
                MEMORY_PRESSURE_SCORE,
                PEAK_HOUR_ABUSE_SCORE,
                ROUND((WASTE_SCORE + SCAN_INEFFICIENCY_SCORE + MEMORY_PRESSURE_SCORE + PEAK_HOUR_ABUSE_SCORE) / 4, 2) AS OVERALL_OPTIMIZATION_SCORE,
                TOTAL_COMPUTE_HOURS,
                ESTIMATED_COST_USD,
                CASE
                    WHEN OVERALL_OPTIMIZATION_SCORE >= 80 THEN '🔴 High-Risk: Immediate Action Needed'
                    WHEN OVERALL_OPTIMIZATION_SCORE >= 40 THEN '🟡 Medium-Risk: Review & Optimize'
                    ELSE '🟢 Low-Risk: Monitor'
                END AS RISK_CATEGORY,
                CASE
                    WHEN OVERALL_OPTIMIZATION_SCORE >= 80 THEN 'Conduct deep dive query audit, mandatory optimization training, consider dedicated WH.'
                    WHEN OVERALL_OPTIMIZATION_SCORE >= 40 THEN 'Review top expensive queries, analyze query patterns, suggest best practices.'
                    ELSE 'Continue monitoring, promote best practices for new workflows.'
                END AS RECOMMENDED_ACTION
            FROM UserScores
            WHERE OVERALL_OPTIMIZATION_SCORE > 30 -- Only show users with some optimization potential
            ORDER BY OVERALL_OPTIMIZATION_SCORE DESC;
        """
    },
    "2_top_inefficient_queries_by_user_table": {
        "label": "Top Inefficient Queries by User",
        "description": "Details the most inefficient queries for selected 'bad' users, providing specific query IDs for investigation.",
        "query": """
            SELECT
                QH.USER_NAME,
                QH.QUERY_ID,
                QH.QUERY_TEXT,
                ROUND(QH.TOTAL_ELAPSED_TIME / 60000, 2) AS EXECUTION_TIME_MIN,
                ROUND(TRY_TO_NUMBER(QH.BYTES_SCANNED, 38, 0) / POW(1024, 3), 2) AS BYTES_SCANNED_GB,
                ROUND(TRY_TO_NUMBER(QH.BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) / POW(1024, 3), 2) AS REMOTE_SPILL_GB,
                ROUND(QH.COMPILATION_TIME / 1000, 2) AS COMPILATION_TIME_SEC,
                ROUND(QH.QUEUED_OVERLOAD_TIME / 1000, 2) AS QUEUE_TIME_SEC,
                QH.EXECUTION_STATUS,
                'Investigate query logic, consider partitioning/clustering, review JOINs.' AS RECOMMENDATION
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY QH
            WHERE
                QH.START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP()) -- Last 7 days for recent queries
                AND QH.USER_NAME IN (
                    -- Subquery to select top unoptimized users from the UserScores CTE above
                    SELECT USER_NAME
                    FROM (
                        SELECT
                            USER_NAME,
                            ROUND((LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60) / 5.0) * 100)) +
                                LEAST(100, GREATEST(0, (AVG(CASE WHEN BYTES_WRITTEN > 0 THEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0) ELSE 0 END) / 500.0) * 100)) +
                                LEAST(100, GREATEST(0, (COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 15.0) * 100)) +
                                LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0) / 40.0) * 100))) / 4, 2) AS OVERALL_OPTIMIZATION_SCORE
                        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                        WHERE START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP()) AND USER_NAME IS NOT NULL
                        GROUP BY USER_NAME
                        HAVING COUNT(*) > 20
                    ) AS UserScoresFiltered
                    WHERE OVERALL_OPTIMIZATION_SCORE >= 60 -- Focus on High-Risk and some Medium-Risk
                    ORDER BY OVERALL_OPTIMIZATION_SCORE DESC
                    LIMIT 5 -- Top 5 most unoptimized users
                )
                AND (
                    QH.EXECUTION_STATUS IN ('FAILED', 'CANCELED') OR -- Wasted compute
                    (TRY_TO_NUMBER(QH.BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(QH.BYTES_WRITTEN, 38, 0), 0) > 1000 AND QH.BYTES_WRITTEN > 0) OR -- High scan-to-output ratio
                    TRY_TO_NUMBER(QH.BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 OR -- Spilling
                    (QH.COMPILATION_TIME / NULLIF(QH.TOTAL_ELAPSED_TIME, 0) > 0.3 AND QH.TOTAL_ELAPSED_TIME > 1000) OR -- High compilation overhead
                    (QH.QUEUED_OVERLOAD_TIME > 30000 OR QH.BLOCKED_TIME > 30000) OR -- High queue/blocked time (>30 sec)
                    (HOUR(QH.START_TIME) BETWEEN 9 AND 17 AND QH.TOTAL_ELAPSED_TIME > 1800000) -- Long-running during peak hours (>30 min)
                )
            ORDER BY QH.USER_NAME, EXECUTION_TIME_MIN DESC
            LIMIT 50; -- Top 50 inefficient queries across these users
        """
    },
    "3_specific_optimization_recommendations_table": {
        "label": "Specific Optimization Recommendations",
        "description": "Tailored recommendations for specific users based on their dominant 'bad' patterns.",
        "query": """
            WITH UserOptimizationFlags AS (
                SELECT
                    USER_NAME,
                    -- Flag for Wasted Compute
                    MAX(CASE WHEN (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(TOTAL_ELAPSED_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60)) > 5 THEN TRUE ELSE FALSE END) AS HAS_HIGH_WASTE,
                    -- Flag for Scan Inefficiency
                    MAX(CASE WHEN (AVG(CASE WHEN BYTES_WRITTEN > 0 THEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0) ELSE 0 END)) > 1000 THEN TRUE ELSE FALSE END) AS HAS_SCAN_INEFFICIENCY,
                    -- Flag for Memory Pressure (Spilling)
                    MAX(CASE WHEN (COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0)) > 10 THEN TRUE ELSE FALSE END) AS HAS_MEMORY_PRESSURE,
                    -- Flag for Compilation Overhead
                    MAX(CASE WHEN (AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / NULLIF(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0)) > 0.3 THEN TRUE ELSE FALSE END) AS HAS_COMPILATION_OVERHEAD,
                    -- Flag for Concurrency Contention
                    MAX(CASE WHEN (AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000) > 10 THEN TRUE ELSE FALSE END) AS HAS_CONCURRENCY_CONTENTION,
                    -- Flag for Peak Hour Abuse
                    MAX(CASE WHEN (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 ELSE NULL END) * 100.0 / NULLIF(COUNT(*), 0)) > 50 THEN TRUE ELSE FALSE END) AS HAS_PEAK_HOUR_ABUSE
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                WHERE
                    START_TIME >= DATEADD(month, -1, CURRENT_TIMESTAMP())
                    AND USER_NAME IS NOT NULL
                GROUP BY USER_NAME
                HAVING COUNT(*) > 20
            )
            SELECT
                UOF.USER_NAME,
                CASE WHEN UOF.HAS_HIGH_WASTE THEN 'High Wasted Compute' ELSE NULL END AS OPTIMIZATION_AREA_1,
                CASE WHEN UOF.HAS_SCAN_INEFFICIENCY THEN 'Inefficient Data Scans' ELSE NULL END AS OPTIMIZATION_AREA_2,
                CASE WHEN UOF.HAS_MEMORY_PRESSURE THEN 'Frequent Memory Spilling' ELSE NULL END AS OPTIMIZATION_AREA_3,
                CASE WHEN UOF.HAS_COMPILATION_OVERHEAD THEN 'High Compilation Overhead' ELSE NULL END AS OPTIMIZATION_AREA_4,
                CASE WHEN UOF.HAS_CONCURRENCY_CONTENTION THEN 'Concurrency Contention' ELSE NULL END AS OPTIMIZATION_AREA_5,
                CASE WHEN UOF.HAS_PEAK_HOUR_ABUSE THEN 'Peak Hour Resource Abuse' ELSE NULL END AS OPTIMIZATION_AREA_6,
                CASE
                    WHEN UOF.HAS_HIGH_WASTE THEN 'Review failed/cancelled queries, implement robust error handling, use dev environment for testing.'
                    WHEN UOF.HAS_SCAN_INEFFICIENCY THEN 'Optimize WHERE clauses, use column pruning, consider clustering/materialized views.'
                    WHEN UOF.HAS_MEMORY_PRESSURE THEN 'Review query joins, consider larger warehouse for complex queries, break down large queries.'
                    WHEN UOF.HAS_COMPILATION_OVERHEAD THEN 'Use prepared statements, avoid dynamic SQL where possible, leverage result cache.'
                    WHEN UOF.HAS_CONCURRENCY_CONTENTION THEN 'Schedule heavy queries off-peak, consider multi-cluster warehouses or dedicated WH.'
                    WHEN UOF.HAS_PEAK_HOUR_ABUSE THEN 'Schedule batch jobs off-peak, enforce query governance during business hours.'
                    ELSE 'No specific recommendations based on current patterns. Continue monitoring for efficiency.'
                END AS DETAILED_RECOMMENDATION
            FROM UserOptimizationFlags UOF
            WHERE UOF.HAS_HIGH_WASTE OR UOF.HAS_SCAN_INEFFICIENCY OR UOF.HAS_MEMORY_PRESSURE OR UOF.HAS_COMPILATION_OVERHEAD OR UOF.HAS_CONCURRENCY_CONTENTION OR UOF.HAS_PEAK_HOUR_ABUSE
            ORDER BY UOF.USER_NAME;
        """
    },
    "4_untapped_optimization_potential_table": {
        "label": "Untapped Optimization Potential",
        "description": "Identifies queries or users where a simple optimization (like result caching or cloning) could yield significant cost savings.",
        "query": """
            SELECT
                QH.USER_NAME,
                QH.QUERY_ID,
                QH.QUERY_TEXT,
                ROUND(QH.TOTAL_ELAPSED_TIME / 60000, 2) AS EXECUTION_TIME_MIN,
                COUNT(*) OVER (PARTITION BY QH.QUERY_TEXT) AS SAME_QUERY_EXECUTIONS,
                ROUND(AVG(QH.TOTAL_ELAPSED_TIME) OVER (PARTITION BY QH.QUERY_TEXT) / 60000, 2) AS AVG_EXECUTION_TIME_SAME_QUERY_MIN,
                'Consider enabling or verifying result caching for this query pattern. If data is static, explore materialized views.' AS POTENTIAL_OPTIMIZATION
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY QH
            WHERE
                QH.START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP()) -- Recent queries
                AND QH.EXECUTION_STATUS = 'SUCCESS'
                AND QH.USER_NAME IS NOT NULL
                AND QH.QUERY_TEXT NOT ILIKE '%CURRENT_TIMESTAMP%' -- Exclude obvious non-cacheable queries
                AND QH.QUERY_TEXT NOT ILIKE '%RANDOM%'
                QUALIFY SAME_QUERY_EXECUTIONS > 5 AND AVG_EXECUTION_TIME_SAME_QUERY_MIN > 0.1 -- Repeated queries taking significant time
            ORDER BY SAME_QUERY_EXECUTIONS DESC, AVG_EXECUTION_TIME_SAME_QUERY_MIN DESC
            LIMIT 20;
        """
    }
}