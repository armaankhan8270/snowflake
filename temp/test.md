You've outlined an excellent and robust framework for a Snowflake native app designed for enterprise-level cost and performance optimization\! Your existing metrics are very strong. The request to integrate a **unified optimization scoring** is a brilliant addition, as it provides a clear, actionable signal for identifying and prioritizing users.

Let's refine your "Optimization Opportunity Scoring" and then apply this comprehensive approach to other key aspects for production readiness and a seamless user experience. The goal is to move beyond basic metrics to provide **context, actionable recommendations, and clear prioritization**.

Here’s an enhanced version of your "Optimization Opportunity Scoring" metric, followed by other charts and tables, all designed with robust logic for enterprise-grade applications. I've also incorporated dynamic placeholders (`{start_date}`, `{end_date}`, `{object_filter}`) for your application to easily inject values.

-----

## 1\. Smart Cost-Waste Detector

```sql
"smart_cost_waste_detector": {
    "query": """
        WITH user_waste_analysis AS (
            SELECT
                USER_NAME,
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS = 'SUCCESS' 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS PRODUCTIVE_COMPUTE_HOURS,
                COUNT(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN 1 END) AS FAILED_QUERIES,
                COUNT(CASE WHEN EXECUTION_STATUS = 'SUCCESS' THEN 1 END) AS SUCCESS_QUERIES,
                COUNT(DISTINCT ERROR_CODE) AS UNIQUE_ERROR_TYPES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            WASTED_COMPUTE_HOURS,
            PRODUCTIVE_COMPUTE_HOURS,
            ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_WASTED_DOLLARS, -- Assuming $2.5/credit hour for a medium warehouse; adjust as needed
            ROUND(CASE WHEN (WASTED_COMPUTE_HOURS + PRODUCTIVE_COMPUTE_HOURS) > 0 
                THEN (WASTED_COMPUTE_HOURS * 100.0) / (WASTED_COMPUTE_HOURS + PRODUCTIVE_COMPUTE_HOURS) 
                ELSE 0 END, 2) AS WASTE_PERCENTAGE,
            FAILED_QUERIES,
            SUCCESS_QUERIES,
            UNIQUE_ERROR_TYPES,
            CASE 
                WHEN WASTE_PERCENTAGE > 25 AND WASTED_COMPUTE_HOURS > 10 THEN 'CRITICAL'
                WHEN WASTE_PERCENTAGE > 15 AND WASTED_COMPUTE_HOURS > 5 THEN 'HIGH'
                WHEN WASTE_PERCENTAGE > 10 OR WASTED_COMPUTE_HOURS > 2 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM user_waste_analysis
        WHERE WASTED_COMPUTE_HOURS > 0.1 -- Focus on users with significant waste
        ORDER BY WASTED_COMPUTE_HOURS DESC
    """,
    "description": "Identifies users burning credits on failed queries with intelligent prioritization",
    "apply_object_filter": True
}
```

-----

## 2\. Data Scan Efficiency Analyzer

```sql
"data_scan_efficiency_analyzer": {
    "query": """
        WITH scan_efficiency AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0)), 0) / POW(1024, 4) AS AVG_DATA_SCANNED_TB,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)), 0) / POW(1024, 3) AS AVG_DATA_WRITTEN_GB,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(PARTITIONS_SCANNED, 38, 0), 0)), 0) AS AVG_PARTITIONS_SCANNED,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(PARTITIONS_TOTAL, 38, 0), 0)), 0) AS AVG_PARTITIONS_TOTAL,
                COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) > TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0) * 1000 AND BYTES_WRITTEN > 0 THEN 1 END) AS INEFFICIENT_SCANS_COUNT -- Scanned > 1000x Written
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND BYTES_SCANNED > 0
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            AVG_DATA_SCANNED_TB,
            AVG_DATA_WRITTEN_GB,
            ROUND(CASE WHEN AVG_DATA_WRITTEN_GB > 0 
                THEN (AVG_DATA_SCANNED_TB * 1024) / AVG_DATA_WRITTEN_GB 
                ELSE 0 END, 2) AS SCAN_TO_OUTPUT_RATIO,
            ROUND(CASE WHEN AVG_PARTITIONS_TOTAL > 0 
                THEN (AVG_PARTITIONS_SCANNED * 100.0) / AVG_PARTITIONS_TOTAL 
                ELSE 0 END, 2) AS PARTITION_SCAN_EFFICIENCY_PCT,
            INEFFICIENT_SCANS_COUNT,
            ROUND((INEFFICIENT_SCANS_COUNT * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS INEFFICIENCY_RATE_PCT,
            CASE 
                WHEN SCAN_TO_OUTPUT_RATIO > 1000 AND INEFFICIENCY_RATE_PCT > 50 THEN 'CRITICAL'
                WHEN SCAN_TO_OUTPUT_RATIO > 500 AND INEFFICIENCY_RATE_PCT > 30 THEN 'HIGH'
                WHEN SCAN_TO_OUTPUT_RATIO > 100 OR INEFFICIENCY_RATE_PCT > 20 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM scan_efficiency
        WHERE AVG_DATA_SCANNED_TB > 0.01 -- Focus on users scanning significant data
        ORDER BY SCAN_TO_OUTPUT_RATIO DESC
    """,
    "description": "Identifies users with poor data scanning patterns and missing filters, suggesting query and data model optimizations.",
    "apply_object_filter": True
}
```

-----

## 3\. Memory Pressure Intelligence

```sql
"memory_pressure_intelligence": {
    "query": """
        WITH memory_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0) > 0 
                    OR COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) > 0 THEN 1 END) AS SPILL_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0)), 0) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0)), 0) / POW(1024, 3) AS AVG_LOCAL_SPILL_GB,
                COUNT(CASE WHEN WAREHOUSE_SIZE IN ('X-SMALL', 'SMALL') 
                    AND COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) > 0 THEN 1 END) AS UNDERSIZED_WAREHOUSE_SPILLS,
                AVG(COALESCE(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)) / 1000 AS AVG_EXECUTION_TIME_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            SPILL_QUERIES,
            ROUND((SPILL_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS SPILL_RATE_PCT,
            AVG_REMOTE_SPILL_GB,
            AVG_LOCAL_SPILL_GB,
            UNDERSIZED_WAREHOUSE_SPILLS,
            AVG_EXECUTION_TIME_SEC,
            -- Estimated spill cost is tricky as it's part of compute, but indicates inefficiency
            -- A heuristic: Remote spills incur more I/O and thus consume more warehouse time relative to effective work.
            ROUND((AVG_REMOTE_SPILL_GB * 0.05 + AVG_LOCAL_SPILL_GB * 0.01) * 2.5, 2) AS ESTIMATED_SPILL_COST_DOLLARS, -- Heuristic cost, adjust as needed
            CASE 
                WHEN SPILL_RATE_PCT > 40 AND AVG_REMOTE_SPILL_GB > 10 THEN 'CRITICAL'
                WHEN SPILL_RATE_PCT > 25 AND AVG_REMOTE_SPILL_GB > 5 THEN 'HIGH'
                WHEN SPILL_RATE_PCT > 15 OR AVG_REMOTE_SPILL_GB > 2 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM memory_analysis
        WHERE TOTAL_QUERIES > 20 AND SPILL_QUERIES > 0
        ORDER BY SPILL_RATE_PCT DESC
    """,
    "description": "Detects users causing memory pressure and warehouse undersizing, leading to slower queries and increased compute costs.",
    "apply_object_filter": True
}
```

-----

## 4\. Query Compilation Overhead Detector

```sql
"query_compilation_overhead_detector": {
    "query": """
        WITH compilation_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_COMPILE_TIME_SEC,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC,
                COUNT(CASE WHEN TRY_TO_NUMBER(COMPILATION_TIME, 38, 0) > 30000 THEN 1 END) AS SLOW_COMPILE_QUERIES,
                COUNT(DISTINCT QUERY_TEXT) AS UNIQUE_QUERY_TEXTS, -- Better name for clarity
                COUNT(DISTINCT DATABASE_NAME) AS DATABASES_ACCESSED,
                COUNT(DISTINCT SCHEMA_NAME) AS SCHEMAS_ACCESSED
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND COMPILATION_TIME > 0
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            AVG_COMPILE_TIME_SEC,
            AVG_EXECUTION_TIME_SEC,
            ROUND(CASE WHEN AVG_EXECUTION_TIME_SEC > 0 
                THEN AVG_COMPILE_TIME_SEC / AVG_EXECUTION_TIME_SEC 
                ELSE 0 END, 4) AS COMPILE_TO_EXEC_RATIO,
            SLOW_COMPILE_QUERIES,
            UNIQUE_QUERY_TEXTS,
            ROUND((TOTAL_QUERIES * 100.0) / NULLIF(UNIQUE_QUERY_TEXTS, 0), 2) AS QUERY_REUSE_RATE_PCT, -- Renamed for clarity
            DATABASES_ACCESSED,
            SCHEMAS_ACCESSED,
            CASE 
                WHEN COMPILE_TO_EXEC_RATIO > 0.8 AND AVG_COMPILE_TIME_SEC > 20 THEN 'CRITICAL'
                WHEN COMPILE_TO_EXEC_RATIO > 0.5 AND AVG_COMPILE_TIME_SEC > 10 THEN 'HIGH'
                WHEN COMPILE_TO_EXEC_RATIO > 0.3 OR AVG_COMPILE_TIME_SEC > 5 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM compilation_analysis
        WHERE TOTAL_QUERIES > 50 -- Focus on users with significant query volume
        ORDER BY COMPILE_TO_EXEC_RATIO DESC
    """,
    "description": "Identifies users with excessive compilation overhead, often due to dynamic SQL or lack of query reuse, impacting performance and cost.",
    "apply_object_filter": True
}
```

-----

## 5\. Concurrency Impact Analyzer

```sql
"concurrency_impact_analyzer": {
    "query": """
        WITH concurrency_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0)), 0) / 1000 AS AVG_QUEUE_OVERLOAD_TIME_SEC, -- Renamed for clarity
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0), 0)), 0) / 1000 AS AVG_BLOCKED_TIME_SEC,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC,
                COUNT(CASE WHEN TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0) > 60000 THEN 1 END) AS HIGH_QUEUE_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
                COUNT(DISTINCT WAREHOUSE_NAME) AS WAREHOUSES_USED
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            AVG_QUEUE_OVERLOAD_TIME_SEC,
            AVG_BLOCKED_TIME_SEC,
            AVG_EXECUTION_TIME_SEC,
            HIGH_QUEUE_QUERIES,
            ROUND((HIGH_QUEUE_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS HIGH_QUEUE_RATE_PCT,
            PEAK_HOUR_QUERIES,
            ROUND((PEAK_HOUR_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS PEAK_HOUR_QUERY_RATE_PCT, -- Renamed for clarity
            WAREHOUSES_USED,
            ROUND((AVG_QUEUE_OVERLOAD_TIME_SEC + AVG_BLOCKED_TIME_SEC) * 0.0007, 4) AS ESTIMATED_WAIT_COST_DOLLARS, -- Heuristic cost for wait time
            CASE 
                WHEN AVG_QUEUE_OVERLOAD_TIME_SEC > 60 AND PEAK_HOUR_QUERY_RATE_PCT > 70 THEN 'CRITICAL'
                WHEN AVG_QUEUE_OVERLOAD_TIME_SEC > 30 AND PEAK_HOUR_QUERY_RATE_PCT > 50 THEN 'HIGH'
                WHEN AVG_QUEUE_OVERLOAD_TIME_SEC > 15 OR PEAK_HOUR_QUERY_RATE_PCT > 30 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM concurrency_analysis
        WHERE TOTAL_QUERIES > 20 AND AVG_QUEUE_OVERLOAD_TIME_SEC > 5 -- Focus on users experiencing significant queuing
        ORDER BY AVG_QUEUE_OVERLOAD_TIME_SEC DESC
    """,
    "description": "Identifies users whose queries frequently experience queuing or blocking, indicating warehouse contention or inefficient scheduling.",
    "apply_object_filter": True
}
```

-----

## 6\. Smart Data Hotspot Detector

```sql
"smart_data_hotspot_detector": {
    "query": """
        WITH hotspot_raw_analysis AS (
            SELECT
                USER_NAME,
                COALESCE(DATABASE_NAME, 'UNKNOWN_DB') AS DATABASE_NAME,
                COALESCE(SCHEMA_NAME, 'UNKNOWN_SCHEMA') AS SCHEMA_NAME,
                COALESCE(TABLE_NAME, 'UNKNOWN_TABLE') AS TABLE_NAME,
                COUNT(*) AS ACCESS_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
            WHERE QUERY_START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND QUERY_START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                -- Object filter needs careful consideration for ACCESS_HISTORY.
                -- If {object_filter} specifies a table, it will filter access for *that* table.
                -- If it's a general object filter, it might not directly apply to ACCESS_HISTORY's granular output.
                -- For now, assuming {object_filter} might apply to DATABASE_NAME, SCHEMA_NAME, TABLE_NAME if provided
                -- For robust filtering, {object_filter} would need to be parsed and applied to BASE_OBJECT_NAME or other columns in ACCESS_HISTORY.
                -- We'll keep it simple for now, as ACCESS_HISTORY structure differs from QUERY_HISTORY.
                -- For a true object filter, you might need to join with other views or parse QUERY_TEXT.
            GROUP BY USER_NAME, DATABASE_NAME, SCHEMA_NAME, TABLE_NAME
        ),
        hotspot_summary AS (
            SELECT
                USER_NAME,
                SUM(ACCESS_COUNT) AS TOTAL_ACCESSES,
                COUNT(DISTINCT DATABASE_NAME) AS UNIQUE_DATABASES,
                COUNT(DISTINCT CONCAT(DATABASE_NAME, '.', SCHEMA_NAME)) AS UNIQUE_SCHEMAS,
                COUNT(DISTINCT CONCAT(DATABASE_NAME, '.', SCHEMA_NAME, '.', TABLE_NAME)) AS UNIQUE_OBJECTS_ACCESSED,
                MAX(ACCESS_COUNT) AS MAX_SINGLE_OBJECT_ACCESSES
            FROM hotspot_raw_analysis
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_ACCESSES,
            UNIQUE_DATABASES,
            UNIQUE_SCHEMAS,
            UNIQUE_OBJECTS_ACCESSED,
            MAX_SINGLE_OBJECT_ACCESSES,
            ROUND(TOTAL_ACCESSES / NULLIF(UNIQUE_OBJECTS_ACCESSED, 0), 2) AS ACCESS_CONCENTRATION_RATIO,
            ROUND((MAX_SINGLE_OBJECT_ACCESSES * 100.0) / NULLIF(TOTAL_ACCESSES, 0), 2) AS TOP_OBJECT_CONCENTRATION_PCT,
            CASE 
                WHEN ACCESS_CONCENTRATION_RATIO > 200 AND TOP_OBJECT_CONCENTRATION_PCT > 60 THEN 'CRITICAL'
                WHEN ACCESS_CONCENTRATION_RATIO > 100 AND TOP_OBJECT_CONCENTRATION_PCT > 40 THEN 'HIGH'
                WHEN ACCESS_CONCENTRATION_RATIO > 50 OR TOP_OBJECT_CONCENTRATION_PCT > 25 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM hotspot_summary
        WHERE TOTAL_ACCESSES > 50 -- Focus on users with significant access patterns
        ORDER BY ACCESS_CONCENTRATION_RATIO DESC
    """,
    "description": "Identifies users with highly concentrated data access patterns to specific tables or objects, suitable for caching, materialized views, or specific table optimizations.",
    "apply_object_filter": True
}
```

-----

## 7\. Peak Hour Resource Abuse Score

```sql
"peak_hour_resource_abuse_score": {
    "query": """
        WITH peak_hour_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) NOT BETWEEN 9 AND 17 THEN 1 END) AS OFF_PEAK_QUERIES,
                COALESCE(AVG(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PEAK_AVG_EXECUTION_HOURS,
                COALESCE(AVG(CASE WHEN HOUR(START_TIME) NOT BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS OFF_PEAK_AVG_EXECUTION_HOURS,
                COALESCE(SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PEAK_TOTAL_EXECUTION_HOURS,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    AND TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) > 1800000 THEN 1 END) AS PEAK_LONG_RUNNING_QUERIES -- Queries > 30 mins
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            PEAK_HOUR_QUERIES,
            OFF_PEAK_QUERIES,
            ROUND((PEAK_HOUR_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS PEAK_HOUR_QUERY_RATE_PCT,
            PEAK_AVG_EXECUTION_HOURS,
            OFF_PEAK_AVG_EXECUTION_HOURS,
            PEAK_TOTAL_EXECUTION_HOURS,
            PEAK_LONG_RUNNING_QUERIES,
            ROUND(PEAK_TOTAL_EXECUTION_HOURS * 3.0, 2) AS ESTIMATED_PEAK_COST_DOLLARS, -- Adjust cost multiplier as needed
            CASE 
                WHEN PEAK_HOUR_QUERY_RATE_PCT > 80 AND PEAK_AVG_EXECUTION_HOURS > 0.5 THEN 'CRITICAL'
                WHEN PEAK_HOUR_QUERY_RATE_PCT > 60 AND PEAK_AVG_EXECUTION_HOURS > 0.25 THEN 'HIGH'
                WHEN PEAK_HOUR_QUERY_RATE_PCT > 40 OR PEAK_AVG_EXECUTION_HOURS > 0.1 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM peak_hour_analysis
        WHERE TOTAL_QUERIES > 20 AND PEAK_HOUR_QUERIES > 10 -- Focus on users with significant peak hour activity
        ORDER BY PEAK_HOUR_QUERY_RATE_PCT DESC
    """,
    "description": "Identifies users consuming significant compute resources during peak business hours, potentially leading to increased costs and reduced concurrency for others.",
    "apply_object_filter": True
}
```

-----

## 8\. Optimization Opportunity Scoring (Unified Score)

This is the core of your "bad user pattern" detection. It normalizes the various optimization factors into a single, digestible score.

```sql
"optimization_opportunity_scoring": {
    "query": """
        WITH user_metrics AS (
            SELECT
                USER_NAME,
                -- Waste Score Calculation: More wasted time means higher score. Max 10 hours wasted = 100 score.
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                -- Scan Inefficiency Score: Higher scan-to-output ratio means higher score. Ratio 1000 = 100 score.
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0)) / POW(1024, 4), 0) AS AVG_DATA_SCANNED_TB,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)) / POW(1024, 3), 0) AS AVG_DATA_WRITTEN_GB,
                -- Memory Pressure Score: Higher spill rate means higher score. 50% spill rate = 100 score.
                COUNT(CASE WHEN COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) > 0 OR COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0) > 0 THEN 1 END) AS SPILL_QUERIES_COUNT,
                COUNT(*) AS TOTAL_QUERIES_FOR_SCORES,
                -- Peak Hour Abuse Score: Higher percentage of peak hour queries means higher score. 80% peak hour = 100 score.
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES_COUNT,
                -- Compilation Overhead Score: Higher compile-to-exec ratio means higher score. Ratio 1.0 = 100 score.
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_COMPILE_TIME_SEC,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC,
                -- Concurrency Impact Score: Higher queue time means higher score. 60 seconds average queue = 100 score.
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0)), 0) / 1000 AS AVG_QUEUE_OVERLOAD_TIME_SEC,
                -- Error Persistence Score: Higher persistence rate for errors means higher score. 60% persistence = 100 score.
                COUNT(DISTINCT CASE WHEN EXECUTION_STATUS = 'FAILED' AND TO_DATE(START_TIME) >= CURRENT_DATE - 7 THEN TO_DATE(START_TIME) END) AS DAYS_WITH_FAILED_QUERIES_LAST_7D,
                COUNT(DISTINCT CASE WHEN EXECUTION_STATUS = 'FAILED' THEN ERROR_CODE END) AS UNIQUE_FAILED_ERROR_CODES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY USER_NAME
            HAVING TOTAL_QUERIES_FOR_SCORES > 20 -- Ensure sufficient data for scoring
        )
        SELECT
            USER_NAME,
            -- Calculate individual scores, scaling them to 0-100
            -- WASTE SCORE: 0-100, where 10 hours of waste = 100. (WASTED_COMPUTE_HOURS / 10) * 100
            LEAST(100, GREATEST(0, ROUND((WASTED_COMPUTE_HOURS / 10) * 100, 2))) AS WASTE_SCORE,
            
            -- SCAN INEFFICIENCY SCORE: 0-100. High ratio indicates inefficiency. Ratio 1000 (1TB scanned/1GB written) = 100.
            LEAST(100, GREATEST(0, ROUND((CASE WHEN AVG_DATA_WRITTEN_GB > 0 THEN (AVG_DATA_SCANNED_TB * 1024) / AVG_DATA_WRITTEN_GB ELSE 0 END / 1000) * 100, 2))) AS SCAN_INEFFICIENCY_SCORE,
            
            -- MEMORY PRESSURE SCORE: 0-100. Spill rate 50% = 100.
            LEAST(100, GREATEST(0, ROUND((SPILL_QUERIES_COUNT * 100.0 / NULLIF(TOTAL_QUERIES_FOR_SCORES, 0)) * 2, 2))) AS MEMORY_PRESSURE_SCORE,
            
            -- PEAK HOUR ABUSE SCORE: 0-100. Peak hour query rate 80% = 100.
            LEAST(100, GREATEST(0, ROUND((PEAK_HOUR_QUERIES_COUNT * 100.0 / NULLIF(TOTAL_QUERIES_FOR_SCORES, 0)) / 0.8, 2))) AS PEAK_HOUR_ABUSE_SCORE,
            
            -- COMPILATION OVERHEAD SCORE: 0-100. Compile to exec ratio 1.0 (equal time) = 100.
            LEAST(100, GREATEST(0, ROUND((CASE WHEN AVG_EXECUTION_TIME_SEC > 0 THEN AVG_COMPILE_TIME_SEC / AVG_EXECUTION_TIME_SEC ELSE 0 END) * 100, 2))) AS COMPILATION_OVERHEAD_SCORE,
            
            -- CONCURRENCY IMPACT SCORE: 0-100. Average queue time 60 seconds = 100.
            LEAST(100, GREATEST(0, ROUND((AVG_QUEUE_OVERLOAD_TIME_SEC / 60) * 100, 2))) AS CONCURRENCY_IMPACT_SCORE,

            -- ERROR PERSISTENCE SCORE: 0-100. If errors occur on 5+ days in a week and >2 unique error codes, score rises.
            LEAST(100, GREATEST(0, ROUND(CASE 
                WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 5 AND UNIQUE_FAILED_ERROR_CODES >= 3 THEN 100 -- Highly persistent and varied errors
                WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 3 AND UNIQUE_FAILED_ERROR_CODES >= 2 THEN 75 -- Persistent with some variety
                WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 2 AND UNIQUE_FAILED_ERROR_CODES >= 1 THEN 50 -- Some persistence
                ELSE 0 END, 2))) AS ERROR_PERSISTENCE_SCORE,

            TOTAL_QUERIES_FOR_SCORES AS TOTAL_QUERIES_CONSIDERED,
            
            -- Total Opportunity Score: Average of relevant individual scores.
            ROUND((
                WASTE_SCORE + 
                SCAN_INEFFICIENCY_SCORE + 
                MEMORY_PRESSURE_SCORE + 
                PEAK_HOUR_ABUSE_SCORE +
                COMPILATION_OVERHEAD_SCORE +
                CONCURRENCY_IMPACT_SCORE +
                ERROR_PERSISTENCE_SCORE
            ) / 7, 2) AS TOTAL_OPTIMIZATION_SCORE
        FROM user_metrics
        ORDER BY TOTAL_OPTIMIZATION_SCORE DESC
    """,
    "label": "Optimization Opportunity Scoring",
    "description": "Aggregated score (0-100) indicating a user's overall optimization potential across various dimensions. A score >60 indicates high optimization potential requiring immediate action.",
    "chart_type": "stacked_bar",
    "x_col": "USER_NAME",
    "y_col": ["WASTE_SCORE", "SCAN_INEFFICIENCY_SCORE", "MEMORY_PRESSURE_SCORE", "PEAK_HOUR_ABUSE_SCORE", "COMPILATION_OVERHEAD_SCORE", "CONCURRENCY_IMPACT_SCORE", "ERROR_PERSISTENCE_SCORE"],
    "hover_data": ["TOTAL_OPTIMIZATION_SCORE", "TOTAL_QUERIES_CONSIDERED"],
    "show_table_toggle": True,
    "apply_object_filter": True,
    "bad_user_pattern": "Users with a 'TOTAL_OPTIMIZATION_SCORE' above 60 are considered to have high optimization potential.",
    "recommendation_step": "Prioritize users with a 'TOTAL_OPTIMIZATION_SCORE' above 60. For these high-risk users, schedule immediate, comprehensive performance reviews of their queries and workflows. Implement a mandatory peer review process for their new queries and consider assigning them an optimization mentor to guide them towards more efficient practices. Review individual score components to pinpoint specific areas of inefficiency."
}
```

-----

## TOP 6-8 SNOWFLAKE USER OPTIMIZATION CHARTS

These charts will visualize the "why" by showing trends, distributions, and comparisons related to the optimization metrics. They are enhanced to support dynamic date and object filtering for production use.

### 1\. User Cost-Efficiency Matrix (Scatter Plot)

```sql
"user_cost_efficiency_matrix_chart": {
    "query": """
        WITH user_efficiency AS (
            SELECT
                USER_NAME,
                COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
                COALESCE(SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)), 0) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN EXECUTION_STATUS = 'SUCCESS' THEN 1 END) AS SUCCESS_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0)), 0) / POW(1024, 4) AS AVG_SCAN_PER_QUERY_TB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS IN ('SUCCESS', 'FAILED', 'CANCELED')
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_COMPUTE_HOURS,
            TOTAL_DATA_SCANNED_TB,
            TOTAL_QUERIES,
            SUCCESS_QUERIES,
            ROUND((SUCCESS_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS SUCCESS_RATE_PCT,
            ROUND(TOTAL_COMPUTE_HOURS / NULLIF(TOTAL_DATA_SCANNED_TB, 0), 4) AS COMPUTE_EFFICIENCY_RATIO,
            ROUND(TOTAL_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_COST_DOLLARS, -- Adjust cost per hour as needed
            AVG_SCAN_PER_QUERY_TB,
            CASE 
                WHEN TOTAL_COMPUTE_HOURS > 5 AND SUCCESS_RATE_PCT < 80 THEN 'High Cost, Low Efficiency'
                WHEN TOTAL_COMPUTE_HOURS > 5 AND SUCCESS_RATE_PCT >= 80 THEN 'High Cost, High Efficiency'
                WHEN TOTAL_COMPUTE_HOURS <= 5 AND SUCCESS_RATE_PCT < 80 THEN 'Low Cost, Low Efficiency'
                ELSE 'Low Cost, High Efficiency'
            END AS EFFICIENCY_QUADRANT
        FROM user_efficiency
        WHERE TOTAL_COMPUTE_HOURS > 0.5 AND TOTAL_DATA_SCANNED_TB > 0.001 -- Filter for meaningful activity
        ORDER BY TOTAL_COMPUTE_HOURS DESC
    """,
    "chart_type": "scatter",
    "description": "Scatter plot showing user cost vs efficiency, with point size representing total queries or success rate, categorizing users into efficiency quadrants.",
    "apply_object_filter": True
}
```

-----

### 2\. Weekly Waste Trend Analysis (Multi-line chart)

```sql
"weekly_waste_trend_analysis_chart": {
    "query": """
        WITH weekly_waste AS (
            SELECT
                USER_NAME,
                DATE_TRUNC('WEEK', START_TIME) AS WEEK_START,
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS WASTED_HOURS,
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS = 'SUCCESS' 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PRODUCTIVE_HOURS,
                COUNT(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN 1 END) AS FAILED_QUERIES,
                COUNT(CASE WHEN EXECUTION_STATUS = 'SUCCESS' THEN 1 END) AS SUCCESS_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') - INTERVAL '8 weeks' -- Look at last 8 weeks for trend
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY USER_NAME, DATE_TRUNC('WEEK', START_TIME)
        )
        SELECT
            USER_NAME,
            WEEK_START,
            WASTED_HOURS,
            PRODUCTIVE_HOURS,
            FAILED_QUERIES,
            SUCCESS_QUERIES,
            ROUND(WASTED_HOURS * 2.5, 2) AS WASTED_COST_DOLLARS, -- Adjust cost multiplier
            ROUND(CASE WHEN (WASTED_HOURS + PRODUCTIVE_HOURS) > 0 
                THEN (WASTED_HOURS * 100.0) / (WASTED_HOURS + PRODUCTIVE_HOURS) 
                ELSE 0 END, 2) AS WASTE_PERCENTAGE,
            LAG(WASTED_HOURS, 1) OVER (PARTITION BY USER_NAME ORDER BY WEEK_START) AS PREV_WEEK_WASTE,
            ROUND(WASTED_HOURS - LAG(WASTED_HOURS, 1) OVER (PARTITION BY USER_NAME ORDER BY WEEK_START), 2) AS WASTE_TREND_CHANGE
        FROM weekly_waste
        WHERE WASTED_HOURS > 0.1 OR PRODUCTIVE_HOURS > 0.1 -- Filter for active users
        ORDER BY USER_NAME, WEEK_START
    """,
    "chart_type": "line",
    "description": "Multi-line chart showing weekly trends in wasted compute hours and cost for each user, identifying improvement or degradation patterns.",
    "apply_object_filter": True
}
```

-----

### 3\. Query Lifecycle Bottleneck Waterfall Chart

```sql
"query_lifecycle_bottleneck_waterfall_chart": {
    "query": """
        WITH user_query_stages AS (
            SELECT
                USER_NAME,
                QUERY_ID,
                WAREHOUSE_NAME,
                COALESCE(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0) AS COMPILATION_MS,
                COALESCE(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0) AS QUEUED_OVERLOAD_MS,
                COALESCE(TRY_TO_NUMBER(QUEUED_REPAIR_TIME, 38, 0), 0) AS QUEUED_REPAIR_MS,
                COALESCE(TRY_TO_NUMBER(QUEUED_PROVISIONING_TIME, 38, 0), 0) AS QUEUED_PROVISIONING_MS,
                COALESCE(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0), 0) AS BLOCKED_MS,
                COALESCE(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0) AS EXECUTION_MS,
                (COMPILATION_MS + QUEUED_OVERLOAD_MS + QUEUED_REPAIR_MS + QUEUED_PROVISIONING_MS + BLOCKED_MS + EXECUTION_MS) AS TOTAL_QUERY_DURATION_MS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND TOTAL_QUERY_DURATION_MS > 0
                {object_filter}
        )
        SELECT
            USER_NAME,
            ROUND(AVG(COMPILATION_MS) / 1000, 2) AS AVG_COMPILATION_SEC,
            ROUND(AVG(QUEUED_OVERLOAD_MS) / 1000, 2) AS AVG_QUEUED_OVERLOAD_SEC,
            ROUND(AVG(QUEUED_REPAIR_MS) / 1000, 2) AS AVG_QUEUED_REPAIR_SEC,
            ROUND(AVG(QUEUED_PROVISIONING_MS) / 1000, 2) AS AVG_QUEUED_PROVISIONING_SEC,
            ROUND(AVG(BLOCKED_MS) / 1000, 2) AS AVG_BLOCKED_SEC,
            ROUND(AVG(EXECUTION_MS) / 1000, 2) AS AVG_EXECUTION_SEC,
            ROUND(AVG(TOTAL_QUERY_DURATION_MS) / 1000, 2) AS AVG_TOTAL_DURATION_SEC
        FROM user_query_stages
        GROUP BY USER_NAME
        HAVING AVG_TOTAL_DURATION_SEC > 0.1 -- Filter for users with measurable query time
        ORDER BY AVG_TOTAL_DURATION_SEC DESC
    """,
    "chart_type": "waterfall",
    "description": "Waterfall chart illustrating the average time spent by a user's queries in different lifecycle stages (compilation, queuing, execution, etc.), highlighting where bottlenecks occur.",
    "apply_object_filter": True
}
```

-----

### 4\. Top N Most Expensive Queries by User (Bar Chart)

```sql
"top_expensive_queries_by_user_chart": {
    "query": """
        WITH user_query_cost AS (
            SELECT
                USER_NAME,
                QUERY_ID,
                LEFT(QUERY_TEXT, 250) AS SHORT_QUERY_TEXT, -- Truncate for display in chart
                WAREHOUSE_NAME,
                DATABASE_NAME,
                SCHEMA_NAME,
                TOTAL_ELAPSED_TIME / (1000 * 60 * 60) AS ELAPSED_HOURS,
                COALESCE(TRY_TO_NUMBER(CREDITS_USED_CLOUD_SERVICES, 38, 0), 0) AS CLOUD_SERVICES_CREDITS_RAW,
                -- Estimate query cost. This is a crucial part.
                -- Base compute cost (ELAPSED_HOURS * $per_hour) + Cloud services cost (CLOUD_SERVICES_CREDITS_RAW * $per_credit_cloud_services_equivalent)
                -- Snowflake pricing varies, typically $2.5/credit for standard. Cloud services sometimes consume a small fraction of a credit per operation.
                -- For precise cost, you would integrate with Snowflake's billing data or have a robust credit-to-dollar mapping.
                -- Let's assume a simplified average for now:
                (ELAPSED_HOURS * 2.5 + CLOUD_SERVICES_CREDITS_RAW * 0.00000278) AS ESTIMATED_QUERY_COST_DOLLARS, -- Example: $2.5/credit-hour, 1 credit = 3600 seconds, so 0.00000278 $/ms roughly for cloud services.
                ROW_NUMBER() OVER (PARTITION BY USER_NAME ORDER BY ESTIMATED_QUERY_COST_DOLLARS DESC) AS RN
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                AND ELAPSED_HOURS > 0.001 -- Filter for queries that ran for a significant duration
                {object_filter}
        )
        SELECT
            USER_NAME,
            QUERY_ID,
            SHORT_QUERY_TEXT,
            WAREHOUSE_NAME,
            DATABASE_NAME,
            SCHEMA_NAME,
            ESTIMATED_QUERY_COST_DOLLARS,
            ELAPSED_HOURS
        FROM user_query_cost
        WHERE RN <= 5 -- Top 5 most expensive queries per user to show in a bar chart
        ORDER BY USER_NAME, ESTIMATED_QUERY_COST_DOLLARS DESC
    """,
    "chart_type": "bar",
    "description": "Bar chart displaying the top N most expensive successful queries for each user, allowing for identification of specific high-cost operations and their associated details.",
    "apply_object_filter": True
}
```

-----

### 5\. Warehouse Utilization by User & Time (Stacked Area Chart)

```sql
"warehouse_utilization_by_user_chart": {
    "query": """
        WITH user_warehouse_usage_hourly AS (
            SELECT
                USER_NAME,
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS USAGE_HOUR,
                SUM(COALESCE(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)) / (1000 * 60) AS TOTAL_EXECUTION_MINUTES_HOURLY
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            GROUP BY USER_NAME, WAREHOUSE_NAME, USAGE_HOUR
        )
        SELECT
            USER_NAME,
            WAREHOUSE_NAME,
            USAGE_HOUR,
            TOTAL_EXECUTION_MINUTES_HOURLY
        FROM user_warehouse_usage_hourly
        WHERE TOTAL_EXECUTION_MINUTES_HOURLY > 0.1 -- Filter for measurable activity
        ORDER BY USAGE_HOUR, WAREHOUSE_NAME, USER_NAME
    """,
    "chart_type": "stacked_area",
    "description": "Stacked area chart illustrating hourly compute consumption (execution minutes) by each user across different warehouses, useful for identifying peak loads and resource contention.",
    "apply_object_filter": True
}
```

-----

### 6\. Data Scanned vs. Query Execution Time (Scatter Plot)

This helps identify queries that scan a lot of data but are fast (good filtering/indexing) versus those that scan a lot and are slow (poorly optimized).

```sql
"data_scan_execution_time_scatter_chart": {
    "query": """
        SELECT
            USER_NAME,
            QUERY_ID,
            LEFT(QUERY_TEXT, 100) AS SHORT_QUERY_TEXT,
            COALESCE(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0) / POW(1024, 4) AS BYTES_SCANNED_TB,
            COALESCE(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0) / 1000 AS EXECUTION_TIME_SEC,
            WAREHOUSE_SIZE,
            CASE
                WHEN BYTES_SCANNED_TB > 1 AND EXECUTION_TIME_SEC > 60 THEN 'High Scan, Slow Query'
                WHEN BYTES_SCANNED_TB > 1 AND EXECUTION_TIME_SEC <= 60 THEN 'High Scan, Fast Query (Efficient)'
                WHEN BYTES_SCANNED_TB <= 1 AND EXECUTION_TIME_SEC > 60 THEN 'Low Scan, Slow Query (Other Bottleneck)'
                ELSE 'Efficient Query'
            END AS QUERY_PERFORMANCE_CATEGORY
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'SUCCESS'
            AND BYTES_SCANNED > 0 -- Only consider queries that scanned data
            AND EXECUTION_TIME_SEC > 0 -- Only consider queries that actually ran
            {object_filter}
        ORDER BY BYTES_SCANNED_TB DESC, EXECUTION_TIME_SEC DESC
        LIMIT 1000 -- Limit for charting performance if many queries
    """,
    "chart_type": "scatter",
    "description": "Scatter plot showing average data scanned versus average execution time per query for each user, helping identify queries with disproportionate data access patterns.",
    "apply_object_filter": True
}
```

-----

## TOP 4-6 SNOWFLAKE USER OPTIMIZATION RECOMMENDATION TABLES

These tables provide concrete, actionable "what to do" steps, grounded in the data from your metrics and charts.

### 1\. High-Priority User Optimization Recommendations

This table uses the `TOTAL_OPTIMIZATION_SCORE` to guide high-level recommendations.

```sql
"high_priority_user_recommendations_table": {
    "query": """
        WITH user_optimization_scores AS (
            SELECT
                USER_NAME,
                WASTE_SCORE,
                SCAN_INEFFICIENCY_SCORE,
                MEMORY_PRESSURE_SCORE,
                PEAK_HOUR_ABUSE_SCORE,
                COMPILATION_OVERHEAD_SCORE,
                CONCURRENCY_IMPACT_SCORE,
                ERROR_PERSISTENCE_SCORE,
                TOTAL_OPTIMIZATION_SCORE
            FROM (
                -- This subquery is the full "optimization_opportunity_scoring" query
                -- For production, consider materializing this into a daily/hourly table
                -- to avoid re-computing for every dashboard load.
                WITH user_metrics AS (
                    SELECT
                        USER_NAME,
                        COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                        COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0)) / POW(1024, 4), 0) AS AVG_DATA_SCANNED_TB,
                        COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)) / POW(1024, 3), 0) AS AVG_DATA_WRITTEN_GB,
                        COUNT(CASE WHEN COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) > 0 OR COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0) > 0 THEN 1 END) AS SPILL_QUERIES_COUNT,
                        COUNT(*) AS TOTAL_QUERIES_FOR_SCORES,
                        COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES_COUNT,
                        COALESCE(AVG(NULLIF(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_COMPILE_TIME_SEC,
                        COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC,
                        COALESCE(AVG(NULLIF(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0)), 0) / 1000 AS AVG_QUEUE_OVERLOAD_TIME_SEC,
                        COUNT(DISTINCT CASE WHEN EXECUTION_STATUS = 'FAILED' AND TO_DATE(START_TIME) >= CURRENT_DATE - 7 THEN TO_DATE(START_TIME) END) AS DAYS_WITH_FAILED_QUERIES_LAST_7D,
                        COUNT(DISTINCT CASE WHEN EXECUTION_STATUS = 'FAILED' THEN ERROR_CODE END) AS UNIQUE_FAILED_ERROR_CODES
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                        AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                        {object_filter}
                    GROUP BY USER_NAME
                    HAVING TOTAL_QUERIES_FOR_SCORES > 20
                )
                SELECT
                    USER_NAME,
                    LEAST(100, GREATEST(0, ROUND((WASTED_COMPUTE_HOURS / 10) * 100, 2))) AS WASTE_SCORE,
                    LEAST(100, GREATEST(0, ROUND((CASE WHEN AVG_DATA_WRITTEN_GB > 0 THEN (AVG_DATA_SCANNED_TB * 1024) / AVG_DATA_WRITTEN_GB ELSE 0 END / 1000) * 100, 2))) AS SCAN_INEFFICIENCY_SCORE,
                    LEAST(100, GREATEST(0, ROUND((SPILL_QUERIES_COUNT * 100.0 / NULLIF(TOTAL_QUERIES_FOR_SCORES, 0)) * 2, 2))) AS MEMORY_PRESSURE_SCORE,
                    LEAST(100, GREATEST(0, ROUND((PEAK_HOUR_QUERIES_COUNT * 100.0 / NULLIF(TOTAL_QUERIES_FOR_SCORES, 0)) / 0.8, 2))) AS PEAK_HOUR_ABUSE_SCORE,
                    LEAST(100, GREATEST(0, ROUND((CASE WHEN AVG_EXECUTION_TIME_SEC > 0 THEN AVG_COMPILE_TIME_SEC / AVG_EXECUTION_TIME_SEC ELSE 0 END) * 100, 2))) AS COMPILATION_OVERHEAD_SCORE,
                    LEAST(100, GREATEST(0, ROUND((AVG_QUEUE_OVERLOAD_TIME_SEC / 60) * 100, 2))) AS CONCURRENCY_IMPACT_SCORE,
                    LEAST(100, GREATEST(0, ROUND(CASE 
                        WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 5 AND UNIQUE_FAILED_ERROR_CODES >= 3 THEN 100 
                        WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 3 AND UNIQUE_FAILED_ERROR_CODES >= 2 THEN 75 
                        WHEN DAYS_WITH_FAILED_QUERIES_LAST_7D >= 2 AND UNIQUE_FAILED_ERROR_CODES >= 1 THEN 50 
                        ELSE 0 END, 2))) AS ERROR_PERSISTENCE_SCORE,
                    TOTAL_QUERIES_FOR_SCORES,
                    ROUND((
                        WASTE_SCORE + 
                        SCAN_INEFFICIENCY_SCORE + 
                        MEMORY_PRESSURE_SCORE + 
                        PEAK_HOUR_ABUSE_SCORE +
                        COMPILATION_OVERHEAD_SCORE +
                        CONCURRENCY_IMPACT_SCORE +
                        ERROR_PERSISTENCE_SCORE
                    ) / 7, 2) AS TOTAL_OPTIMIZATION_SCORE
                FROM user_metrics
            )
        )
        SELECT
            uos.USER_NAME,
            uos.TOTAL_OPTIMIZATION_SCORE,
            CASE
                WHEN uos.TOTAL_OPTIMIZATION_SCORE >= 80 THEN 'CRITICAL: Immediate attention required due to severe cost inefficiencies and performance issues.'
                WHEN uos.TOTAL_OPTIMIZATION_SCORE >= 60 THEN 'HIGH: Significant optimization opportunities available. Prioritize review.'
                WHEN uos.TOTAL_OPTIMIZATION_SCORE >= 40 THEN 'MEDIUM: Noticeable areas for improvement. Monitor closely and provide guidance.'
                WHEN uos.TOTAL_OPTIMIZATION_SCORE >= 20 THEN 'LOW: Minor inefficiencies. Consider general best practices training.'
                ELSE 'VERY LOW: User queries are generally well-optimized.'
            END AS OVERALL_OPTIMIZATION_PRIORITY,
            CASE
                WHEN uos.WASTE_SCORE >= 70 THEN '- **High Query Waste:** Focus on resolving frequently failed/canceled queries. Review query syntax, data dependencies, and permissions.'
                WHEN uos.SCAN_INEFFICIENCY_SCORE >= 70 THEN '- **Inefficient Scans:** Optimize WHERE clauses, consider clustering keys on large tables, or leverage materialized views.'
                WHEN uos.MEMORY_PRESSURE_SCORE >= 70 THEN '- **Memory Spilling:** Refactor complex queries to reduce intermediate data, or consider a larger warehouse size for their workload.'
                WHEN uos.PEAK_HOUR_ABUSE_SCORE >= 70 THEN '- **Peak Hour Overload:** Encourage scheduling non-critical queries during off-peak hours or using dedicated smaller warehouses for specific tasks.'
                WHEN uos.COMPILATION_OVERHEAD_SCORE >= 70 THEN '- **High Compilation Time:** Identify dynamic SQL patterns. Encourage use of prepared statements and common table expressions for query reuse.'
                WHEN uos.CONCURRENCY_IMPACT_SCORE >= 70 THEN '- **Concurrency Bottleneck:** Investigate query queuing. Recommend optimizing long-running queries or potentially increasing warehouse concurrency.'
                WHEN uos.ERROR_PERSISTENCE_SCORE >= 70 THEN '- **Persistent Errors:** Deep dive into recurring error messages. Provide targeted training or update documentation based on common error patterns.'
                ELSE 'Review individual score components for specific areas of focus.'
            END AS PRIMARY_RECOMMENDATION_AREA,
            uos.WASTE_SCORE,
            uos.SCAN_INEFFICIENCY_SCORE,
            uos.MEMORY_PRESSURE_SCORE,
            uos.PEAK_HOUR_ABUSE_SCORE,
            uos.COMPILATION_OVERHEAD_SCORE,
            uos.CONCURRENCY_IMPACT_SCORE,
            uos.ERROR_PERSISTENCE_SCORE
        FROM user_optimization_scores uos
        WHERE uos.TOTAL_OPTIMIZATION_SCORE > 20 -- Only show users with some level of optimization opportunity
        ORDER BY uos.TOTAL_OPTIMIZATION_SCORE DESC
    """,
    "description": "Aggregated table presenting the overall optimization score for each user with a high-level prioritization and primary recommendation area.",
    "apply_object_filter": True
}
```

-----

### 2\. Detailed Query-Level Optimization Actions

This table drills down into specific queries.

```sql
"detailed_query_optimization_actions_table": {
    "query": """
        WITH problematic_queries AS (
            SELECT
                USER_NAME,
                QUERY_ID,
                LEFT(QUERY_TEXT, 500) AS QUERY_TEXT_SNIPPET, -- Truncate for display
                WAREHOUSE_NAME,
                DATABASE_NAME,
                SCHEMA_NAME,
                TOTAL_ELAPSED_TIME / 1000 AS TOTAL_ELAPSED_SEC,
                COALESCE(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0) AS BYTES_SCANNED,
                COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0) AS LOCAL_SPILL_BYTES,
                COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) AS REMOTE_SPILL_BYTES,
                COALESCE(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0) AS COMPILATION_MS,
                COALESCE(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0) AS QUEUED_OVERLOAD_MS,
                EXECUTION_STATUS,
                ERROR_CODE,
                ERROR_MESSAGE,
                -- A heuristic "problem score" for ranking individual queries
                (CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN 20 ELSE 0 END) +
                (CASE WHEN (LOCAL_SPILL_BYTES + REMOTE_SPILL_BYTES) > (1024 * 1024 * 1024) * 50 THEN 15 ELSE 0 END) + -- >50GB spill
                (CASE WHEN BYTES_SCANNED > POW(1024, 4) * 10 THEN 10 ELSE 0 END) + -- >10TB scanned
                (CASE WHEN COMPILATION_MS > 60000 THEN 8 ELSE 0 END) + -- >60s compilation
                (CASE WHEN QUEUED_OVERLOAD_MS > 120000 THEN 8 ELSE 0 END) + -- >120s queue time
                (CASE WHEN TOTAL_ELAPSED_TIME > 3600000 THEN 10 ELSE 0 END) -- >1 hour execution
                AS PROBLEM_SEVERITY_SCORE
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND (EXECUTION_STATUS != 'SUCCESS' 
                     OR BYTES_SCANNED > POW(1024, 3) * 1000 -- over 1TB scanned
                     OR (LOCAL_SPILL_BYTES + REMOTE_SPILL_BYTES) > (1024 * 1024 * 1024) * 10 -- over 10GB spill
                     OR COMPILATION_TIME > 30000 -- over 30s compilation
                     OR QUEUED_OVERLOAD_TIME > 60000 -- over 60s queue
                     OR TOTAL_ELAPSED_TIME > 600000) -- over 10 minutes total elapsed
                {object_filter}
        )
        SELECT
            pq.USER_NAME,
            pq.QUERY_ID,
            pq.QUERY_TEXT_SNIPPET,
            pq.WAREHOUSE_NAME,
            pq.DATABASE_NAME,
            pq.SCHEMA_NAME,
            pq.TOTAL_ELAPSED_SEC,
            pq.EXECUTION_STATUS,
            pq.ERROR_CODE,
            pq.ERROR_MESSAGE,
            CASE
                WHEN pq.EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') AND pq.ERROR_CODE IS NOT NULL THEN 'ACTION: Review query syntax, permissions, data validity related to error code ' || pq.ERROR_CODE || '. Consider setting up alerts for this error pattern.'
                WHEN pq.BYTES_SCANNED > POW(1024, 4) * 5 AND pq.REMOTE_SPILL_BYTES > POW(1024,3) * 50 THEN 'ACTION: High data scanned & spill. **Critical re-write needed.** Add more selective WHERE clauses, ensure proper join conditions, consider clustering on large tables, or explore Materialized Views.'
                WHEN pq.BYTES_SCANNED > POW(1024, 4) * 2 THEN 'ACTION: Reduce data scanned. Improve WHERE clause filters, analyze join efficiency, or leverage search optimization for frequently filtered columns.'
                WHEN (pq.LOCAL_SPILL_BYTES + pq.REMOTE_SPILL_BYTES) > (1024 * 1024 * 1024) * 10 THEN 'ACTION: Significant memory spill. Refactor query to reduce intermediate data (e.g., limit large JOINs/GROUP BYs), or consider using a larger warehouse for this specific query.'
                WHEN pq.COMPILATION_MS > 45000 THEN 'ACTION: Excessive compilation time. Simplify complex CTEs, avoid highly dynamic SQL generation, and investigate if this query can use prepared statements.'
                WHEN pq.QUEUED_OVERLOAD_MS > 90000 THEN 'ACTION: Long queuing time. This indicates warehouse contention. Consider if this query can be scheduled during off-peak hours, or if warehouse scaling policy needs adjustment.'
                WHEN pq.TOTAL_ELAPSED_SEC > 1800 THEN 'ACTION: Long running query. Analyze query profile for multi-stage bottlenecks. Consider breaking into smaller steps or optimizing for specific bottlenecks (I/O, CPU, network).'
                ELSE 'ACTION: Review this query for general performance tuning. Analyze its query profile for further insights.'
            END AS OPTIMIZATION_ACTION,
            pq.PROBLEM_SEVERITY_SCORE
        FROM problematic_queries pq
        WHERE pq.PROBLEM_SEVERITY_SCORE > 0
        ORDER BY pq.PROBLEM_SEVERITY_SCORE DESC, pq.TOTAL_ELAPSED_SEC DESC
        LIMIT 50 -- Limit the number of detailed recommendations for practical review
    """,
    "description": "Provides specific, actionable optimization recommendations for individual queries, identifying the root cause (e.g., inefficient scans, memory spills, long compilation) and suggesting fixes.",
    "apply_object_filter": True
}
```

-----

### 3\. Warehouse Usage Optimization Recommendations

This table gives specific advice on warehouse sizing and allocation.

```sql
"warehouse_usage_optimization_recommendations_table": {
    "query": """
        WITH warehouse_performance_summary AS (
            SELECT
                USER_NAME,
                WAREHOUSE_NAME,
                WAREHOUSE_SIZE,
                COUNT(QUERY_ID) AS TOTAL_QUERIES,
                AVG(COALESCE(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
                AVG(COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0)) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB,
                SUM(COALESCE(TRY_TO_NUMBER(CREDITS_USED, 38, 0), 0)) AS TOTAL_CREDITS_USED_WAREHOUSE,
                MAX(END_TIME) AS LAST_USED_TIME
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                AND EXECUTION_STATUS = 'SUCCESS'
                {object_filter}
            GROUP BY USER_NAME, WAREHOUSE_NAME, WAREHOUSE_SIZE
            HAVING TOTAL_QUERIES > 10 -- Only consider warehouses with some activity
        )
        SELECT
            wps.USER_NAME,
            wps.WAREHOUSE_NAME,
            wps.WAREHOUSE_SIZE,
            wps.TOTAL_QUERIES,
            ROUND(wps.AVG_QUEUE_TIME_SEC, 2) AS AVG_QUEUE_TIME_SEC,
            ROUND(wps.AVG_REMOTE_SPILL_GB, 2) AS AVG_REMOTE_SPILL_GB,
            ROUND(wps.TOTAL_CREDITS_USED_WAREHOUSE, 2) AS TOTAL_CREDITS_USED_WAREHOUSE,
            CASE
                WHEN wps.AVG_QUEUE_TIME_SEC > 30 AND wps.WAREHOUSE_SIZE IN ('X-SMALL', 'SMALL', 'MEDIUM') THEN 
                    'RECOMMENDATION: **Increase Warehouse Size** for this user''s typical workload on ' || wps.WAREHOUSE_NAME || '. High queue times indicate undersizing or contention. Consider scaling up or using a dedicated larger warehouse.'
                WHEN wps.AVG_REMOTE_SPILL_GB > 10 AND wps.WAREHOUSE_SIZE IN ('X-SMALL', 'SMALL', 'MEDIUM') THEN
                    'RECOMMENDATION: **Increase Warehouse Size** for ' || wps.WAREHOUSE_NAME || '. Significant remote spilling suggests insufficient memory for queries. Scale up to reduce I/O to storage.'
                WHEN wps.TOTAL_CREDITS_USED_WAREHOUSE > 50 AND wps.TOTAL_QUERIES < 50 AND wps.WAREHOUSE_SIZE IN ('LARGE', 'X-LARGE') THEN
                    'RECOMMENDATION: **Review Warehouse Sizing/Auto-suspend** for ' || wps.WAREHOUSE_NAME || '. High credits for low query volume might mean the warehouse is oversized or staying active unnecessarily. Consider rightsizing or aggressive auto-suspend.'
                WHEN wps.TOTAL_QUERIES < 5 AND DATEDIFF('day', wps.LAST_USED_TIME, CURRENT_TIMESTAMP()) > 7 THEN
                    'RECOMMENDATION: **Consider Deactivating/Archiving Warehouse** ' || wps.WAREHOUSE_NAME || '. Very low recent activity suggests it may no longer be needed or is misconfigured.'
                WHEN wps.TOTAL_CREDITS_USED_WAREHOUSE < 1 AND wps.TOTAL_QUERIES > 50 THEN
                    'OBSERVATION: User is very efficient on ' || wps.WAREHOUSE_NAME || '. Continue current practices.'
                ELSE 'RECOMMENDATION: Current warehouse usage patterns for ' || wps.WAREHOUSE_NAME || ' appear reasonable. Continue monitoring.'
            END AS WAREHOUSE_OPTIMIZATION_ACTION
        FROM warehouse_performance_summary wps
        ORDER BY wps.TOTAL_CREDITS_USED_WAREHOUSE DESC, wps.AVG_QUEUE_TIME_SEC DESC
    """,
    "description": "Provides explicit recommendations for optimizing warehouse configurations (sizing, auto-suspend) based on individual user usage patterns, queue times, and memory spills.",
    "apply_object_filter": True
}
```

-----

### 4\. Training & Best Practices Recommendations

This table identifies common user anti-patterns and suggests educational interventions.

```sql
"training_best_practices_recommendations_table": {
    "query": """
        WITH user_behavior_analysis AS (
            SELECT
                u.USER_NAME,
                -- From Smart Cost-Waste Detector
                u.FAILED_QUERIES,
                u.WASTE_PERCENTAGE,
                -- From Data Scan Efficiency Analyzer
                d.INEFFICIENCY_RATE_PCT,
                d.SCAN_TO_OUTPUT_RATIO,
                -- From Query Compilation Overhead Detector
                c.QUERY_REUSE_RATE_PCT,
                c.SLOW_COMPILE_QUERIES,
                -- From Advanced Error Pattern Intelligence
                e.PERSISTENCE_RATE_PCT AS ERROR_PERSISTENCE_RATE_PCT,
                e.UNIQUE_ERROR_TYPES,
                SUM(uh.TOTAL_QUERIES) AS USER_TOTAL_QUERIES -- Joining with a subquery that has total queries
            FROM (
                SELECT USER_NAME, FAILED_QUERIES, WASTE_PERCENTAGE FROM (SELECT USER_NAME, COUNT(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN 1 END) AS FAILED_QUERIES, ROUND(COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) * 100.0 / NULLIF(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0), 2) AS WASTE_PERCENTAGE FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59') GROUP BY USER_NAME)
            ) u
            LEFT JOIN (SELECT USER_NAME, INEFFICIENCY_RATE_PCT, SCAN_TO_OUTPUT_RATIO FROM (WITH scan_efficiency AS (SELECT USER_NAME, COUNT(*) AS TOTAL_QUERIES, COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0), 0)), 0) / POW(1024, 4) AS AVG_DATA_SCANNED_TB, COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)), 0) / POW(1024, 3) AS AVG_DATA_WRITTEN_GB, COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) > TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0) * 1000 AND BYTES_WRITTEN > 0 THEN 1 END) AS INEFFICIENT_SCANS_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59') AND EXECUTION_STATUS = 'SUCCESS' AND BYTES_SCANNED > 0 GROUP BY USER_NAME) SELECT USER_NAME, ROUND((INEFFICIENT_SCANS_COUNT * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS INEFFICIENCY_RATE_PCT, ROUND(CASE WHEN AVG_DATA_WRITTEN_GB > 0 THEN (AVG_DATA_SCANNED_TB * 1024) / AVG_DATA_WRITTEN_GB ELSE 0 END, 2) AS SCAN_TO_OUTPUT_RATIO FROM scan_efficiency WHERE AVG_DATA_SCANNED_TB > 0.01)
            ) d ON u.USER_NAME = d.USER_NAME
            LEFT JOIN (SELECT USER_NAME, QUERY_REUSE_RATE_PCT, SLOW_COMPILE_QUERIES FROM (WITH compilation_analysis AS (SELECT USER_NAME, COUNT(*) AS TOTAL_QUERIES, COALESCE(AVG(NULLIF(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_COMPILE_TIME_SEC, COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC, COUNT(CASE WHEN TRY_TO_NUMBER(COMPILATION_TIME, 38, 0) > 30000 THEN 1 END) AS SLOW_COMPILE_QUERIES, COUNT(DISTINCT QUERY_TEXT) AS UNIQUE_QUERY_TEXTS FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59') AND EXECUTION_STATUS = 'SUCCESS' AND COMPILATION_TIME > 0 GROUP BY USER_NAME) SELECT USER_NAME, ROUND((TOTAL_QUERIES * 100.0) / NULLIF(UNIQUE_QUERY_TEXTS, 0), 2) AS QUERY_REUSE_RATE_PCT, SLOW_COMPILE_QUERIES FROM compilation_analysis WHERE TOTAL_QUERIES > 50)
            ) c ON u.USER_NAME = c.USER_NAME
            LEFT JOIN (SELECT USER_NAME, PERSISTENCE_RATE_PCT, UNIQUE_ERROR_TYPES FROM (WITH error_analysis AS (SELECT USER_NAME, COUNT(*) AS ERROR_COUNT, COUNT(DISTINCT TO_DATE(START_TIME)) AS DAYS_WITH_ERROR, COUNT(DISTINCT ERROR_CODE) AS UNIQUE_ERROR_TYPES FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59') AND EXECUTION_STATUS = 'FAILED' AND ERROR_CODE IS NOT NULL GROUP BY USER_NAME) SELECT USER_NAME, ROUND((COUNT(CASE WHEN DAYS_WITH_ERROR > 7 THEN 1 END) * 100.0) / NULLIF(UNIQUE_ERROR_TYPES, 0), 2) AS PERSISTENCE_RATE_PCT, UNIQUE_ERROR_TYPES FROM error_analysis GROUP BY USER_NAME)
            ) e ON u.USER_NAME = e.USER_NAME
            JOIN (SELECT USER_NAME, COUNT(*) AS TOTAL_QUERIES FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}') AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59') GROUP BY USER_NAME) uh ON u.USER_NAME = uh.USER_NAME
            WHERE USER_TOTAL_QUERIES > 50 -- Only recommend for active users
            GROUP BY u.USER_NAME, u.FAILED_QUERIES, u.WASTE_PERCENTAGE, d.INEFFICIENCY_RATE_PCT, d.SCAN_TO_OUTPUT_RATIO, c.QUERY_REUSE_RATE_PCT, c.SLOW_COMPILE_QUERIES, e.PERSISTENCE_RATE_PCT, e.UNIQUE_ERROR_TYPES
        )
        SELECT
            uba.USER_NAME,
            CASE
                WHEN uba.FAILED_QUERIES > 100 AND uba.WASTE_PERCENTAGE > 20 THEN '**Training Focus: Error Handling & Debugging.** User frequently encounters query failures. Provide training on common Snowflake error codes, debugging techniques, and best practices for robust SQL development.'
                WHEN uba.INEFFICIENCY_RATE_PCT > 30 AND uba.SCAN_TO_OUTPUT_RATIO > 100 THEN '**Training Focus: Data Filtering & Pruning.** User queries are scanning excessive data. Train on effective WHERE clause usage, understanding micro-partitions, and benefits of clustering/search optimization.'
                WHEN uba.QUERY_REUSE_RATE_PCT < 50 AND uba.SLOW_COMPILE_QUERIES > 10 THEN '**Training Focus: Query Reusability & Dynamic SQL Best Practices.** User may be generating too many unique queries or using inefficient dynamic SQL. Educate on CTEs, views, and prepared statements.'
                WHEN uba.ERROR_PERSISTENCE_RATE_PCT > 50 AND uba.UNIQUE_ERROR_TYPES > 2 THEN '**Training Focus: Problem Solving & Documentation.** User repeatedly encounters the same or similar errors. Encourage documenting solutions, utilizing internal knowledge bases, and escalating persistent issues.'
                WHEN uba.USER_TOTAL_QUERIES > 200 AND (uba.FAILED_QUERIES > 50 OR uba.INEFFICIENCY_RATE_PCT > 20) THEN '**General Performance Best Practices Workshop.** For highly active users, a comprehensive session on overall Snowflake optimization principles (warehousing, query structure, data loading/unloading).'
                ELSE 'No immediate training recommendation based on current patterns. Encourage continuous learning on Snowflake features.'
            END AS RECOMMENDED_TRAINING_ACTION
        FROM user_behavior_analysis uba
        WHERE RECOMMENDED_TRAINING_ACTION IS NOT NULL AND RECOMMENDED_TRAINING_ACTION != 'No immediate training recommendation based on current patterns. Encourage continuous learning on Snowflake features.'
        ORDER BY USER_TOTAL_QUERIES DESC
    """,
    "description": "Suggests specific training and best practices interventions for users based on recurring anti-patterns identified in their query behavior (e.g., persistent errors, low query reuse, inefficient data scans).",
    "apply_object_filter": True
}
```

-----

### 5\. Potential Cost Savings by Optimization Area

This table breaks down potential cost savings by the type of optimization.

```sql
"potential_cost_savings_by_optimization_area_table": {
    "query": """
        WITH user_cost_drivers AS (
            SELECT
                USER_NAME,
                COALESCE(SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED') 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
                COALESCE(SUM(CASE WHEN COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0), 0) > 0 OR COALESCE(TRY_TO_NUMBER(BYTES_SPILLED_TO_LOCAL_STORAGE, 38, 0), 0) > 0 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END), 0) / (1000 * 60 * 60) AS SPILL_IMPACT_HOURS,
                COALESCE(SUM(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0) + TRY_TO_NUMBER(BLOCKED_TIME, 38, 0), 0)) / (1000 * 60 * 60) AS WAIT_IMPACT_HOURS,
                COALESCE(SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PEAK_HOUR_EXECUTION_HOURS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
                AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
                {object_filter}
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_SAVINGS_FROM_WASTE, -- Failed/Canceled queries
            ROUND(SPILL_IMPACT_HOURS * 2.5 * 0.5, 2) AS ESTIMATED_SAVINGS_FROM_SPILLS, -- Heuristic: 50% of spill-impacted time could be saved
            ROUND(WAIT_IMPACT_HOURS * 2.5 * 0.75, 2) AS ESTIMATED_SAVINGS_FROM_CONCURRENCY, -- Heuristic: 75% of wait time could be saved by better concurrency
            ROUND(PEAK_HOUR_EXECUTION_HOURS * 2.5 * 0.2, 2) AS ESTIMATED_SAVINGS_FROM_PEAK_SHIFT, -- Heuristic: 20% of peak hour cost could be shifted/saved
            ROUND((WASTED_COMPUTE_HOURS * 2.5) + (SPILL_IMPACT_HOURS * 2.5 * 0.5) + 
                  (WAIT_IMPACT_HOURS * 2.5 * 0.75) + (PEAK_HOUR_EXECUTION_HOURS * 2.5 * 0.2), 2) AS TOTAL_ESTIMATED_SAVINGS_DOLLARS
        FROM user_cost_drivers
        WHERE (WASTED_COMPUTE_HOURS + SPILL_IMPACT_HOURS + WAIT_IMPACT_HOURS + PEAK_HOUR_EXECUTION_HOURS) > 0.1 -- Only show users with potential savings
        ORDER BY TOTAL_ESTIMATED_SAVINGS_DOLLARS DESC
    """,
    "description": "Quantifies potential cost savings per user by different optimization categories (e.g., reducing failed queries, mitigating spills, improving concurrency, shifting peak workloads).",
    "apply_object_filter": True
}
```

-----

This comprehensive suite of metrics, charts, and recommendation tables, integrated with dynamic date and object filtering, provides a powerful and actionable "User 360" dashboard for your Snowflake native application. This approach directly addresses your need for **robust, non-basic logic** to identify unoptimized users, explain **why** they are unoptimized, and provide concrete steps on **what to do** to optimize and reduce cost.