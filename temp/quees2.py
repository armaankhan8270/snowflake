# TOP 8 SNOWFLAKE USER OPTIMIZATION METRICS

## 1. Smart Cost-Waste Detector
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
            WHERE START_TIME >= CURRENT_DATE - 30
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            WASTED_COMPUTE_HOURS,
            PRODUCTIVE_COMPUTE_HOURS,
            ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_WASTED_DOLLARS,
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
        WHERE WASTED_COMPUTE_HOURS > 0.1
        ORDER BY WASTED_COMPUTE_HOURS DESC
    """,
    "description": "Identifies users burning credits on failed queries with intelligent prioritization"
}
```

## 2. Data Scan Efficiency Analyzer
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
                COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) > TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0) * 1000 THEN 1 END) AS INEFFICIENT_SCANS
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'SUCCESS'
                AND BYTES_SCANNED > 0
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
                ELSE 0 END, 2) AS PARTITION_SCAN_EFFICIENCY,
            INEFFICIENT_SCANS,
            ROUND((INEFFICIENT_SCANS * 100.0) / TOTAL_QUERIES, 2) AS INEFFICIENCY_RATE,
            CASE 
                WHEN SCAN_TO_OUTPUT_RATIO > 1000 AND INEFFICIENCY_RATE > 50 THEN 'CRITICAL'
                WHEN SCAN_TO_OUTPUT_RATIO > 500 AND INEFFICIENCY_RATE > 30 THEN 'HIGH'
                WHEN SCAN_TO_OUTPUT_RATIO > 100 OR INEFFICIENCY_RATE > 20 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM scan_efficiency
        WHERE AVG_DATA_SCANNED_TB > 0.01
        ORDER BY SCAN_TO_OUTPUT_RATIO DESC
    """,
    "description": "Identifies users with poor data scanning patterns and missing filters"
}
```

## 3. Memory Pressure Intelligence
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
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'SUCCESS'
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
            ROUND((AVG_REMOTE_SPILL_GB + AVG_LOCAL_SPILL_GB) * 0.023, 2) AS ESTIMATED_SPILL_COST_DOLLARS,
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
    "description": "Detects users causing memory pressure and warehouse undersizing"
}
```

## 4. Query Compilation Overhead Detector
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
                COUNT(DISTINCT QUERY_TEXT) AS UNIQUE_QUERIES,
                COUNT(DISTINCT DATABASE_NAME) AS DATABASES_ACCESSED,
                COUNT(DISTINCT SCHEMA_NAME) AS SCHEMAS_ACCESSED
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'SUCCESS'
                AND COMPILATION_TIME > 0
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
            UNIQUE_QUERIES,
            ROUND((TOTAL_QUERIES * 100.0) / NULLIF(UNIQUE_QUERIES, 0), 2) AS QUERY_REUSE_RATIO,
            DATABASES_ACCESSED,
            SCHEMAS_ACCESSED,
            CASE 
                WHEN COMPILE_TO_EXEC_RATIO > 0.8 AND AVG_COMPILE_TIME_SEC > 20 THEN 'CRITICAL'
                WHEN COMPILE_TO_EXEC_RATIO > 0.5 AND AVG_COMPILE_TIME_SEC > 10 THEN 'HIGH'
                WHEN COMPILE_TO_EXEC_RATIO > 0.3 OR AVG_COMPILE_TIME_SEC > 5 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM compilation_analysis
        WHERE TOTAL_QUERIES > 50
        ORDER BY COMPILE_TO_EXEC_RATIO DESC
    """,
    "description": "Identifies users with excessive compilation overhead and dynamic SQL patterns"
}
```

## 5. Concurrency Impact Analyzer
```sql
"concurrency_impact_analyzer": {
    "query": """
        WITH concurrency_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0), 0)), 0) / 1000 AS AVG_QUEUE_TIME_SEC,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0), 0)), 0) / 1000 AS AVG_BLOCKED_TIME_SEC,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)), 0) / 1000 AS AVG_EXECUTION_TIME_SEC,
                COUNT(CASE WHEN TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0) > 60000 THEN 1 END) AS HIGH_QUEUE_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
                COUNT(DISTINCT WAREHOUSE_NAME) AS WAREHOUSES_USED
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'SUCCESS'
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            AVG_QUEUE_TIME_SEC,
            AVG_BLOCKED_TIME_SEC,
            AVG_EXECUTION_TIME_SEC,
            HIGH_QUEUE_QUERIES,
            ROUND((HIGH_QUEUE_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS HIGH_QUEUE_RATE_PCT,
            PEAK_HOUR_QUERIES,
            ROUND((PEAK_HOUR_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS PEAK_HOUR_RATE_PCT,
            WAREHOUSES_USED,
            ROUND((AVG_QUEUE_TIME_SEC + AVG_BLOCKED_TIME_SEC) * 0.0007, 4) AS ESTIMATED_WAIT_COST_DOLLARS,
            CASE 
                WHEN AVG_QUEUE_TIME_SEC > 60 AND PEAK_HOUR_RATE_PCT > 70 THEN 'CRITICAL'
                WHEN AVG_QUEUE_TIME_SEC > 30 AND PEAK_HOUR_RATE_PCT > 50 THEN 'HIGH'
                WHEN AVG_QUEUE_TIME_SEC > 15 OR PEAK_HOUR_RATE_PCT > 30 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM concurrency_analysis
        WHERE TOTAL_QUERIES > 20 AND AVG_QUEUE_TIME_SEC > 5
        ORDER BY AVG_QUEUE_TIME_SEC DESC
    """,
    "description": "Identifies users causing warehouse contention and blocking others"
}
```

## 6. Smart Data Hotspot Detector
```sql
"smart_data_hotspot_detector": {
    "query": """
        WITH hotspot_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_ACCESSES,
                COUNT(DISTINCT COALESCE(DATABASE_NAME, 'UNKNOWN')) AS UNIQUE_DATABASES,
                COUNT(DISTINCT COALESCE(SCHEMA_NAME, 'UNKNOWN')) AS UNIQUE_SCHEMAS,
                COUNT(DISTINCT COALESCE(TABLE_NAME, 'UNKNOWN')) AS UNIQUE_TABLES,
                COUNT(DISTINCT CONCAT(COALESCE(DATABASE_NAME, 'UNKNOWN'), '.', 
                    COALESCE(SCHEMA_NAME, 'UNKNOWN'), '.', COALESCE(TABLE_NAME, 'UNKNOWN'))) AS UNIQUE_OBJECTS,
                MAX(COUNT(*)) OVER (PARTITION BY USER_NAME) AS MAX_OBJECT_ACCESSES
            FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
            WHERE QUERY_START_TIME >= CURRENT_DATE - 30
            GROUP BY USER_NAME, DATABASE_NAME, SCHEMA_NAME, TABLE_NAME
        )
        SELECT
            USER_NAME,
            SUM(TOTAL_ACCESSES) AS TOTAL_ACCESSES,
            MAX(UNIQUE_DATABASES) AS UNIQUE_DATABASES,
            MAX(UNIQUE_SCHEMAS) AS UNIQUE_SCHEMAS,
            MAX(UNIQUE_TABLES) AS UNIQUE_TABLES,
            MAX(UNIQUE_OBJECTS) AS UNIQUE_OBJECTS,
            ROUND(SUM(TOTAL_ACCESSES) / NULLIF(MAX(UNIQUE_OBJECTS), 0), 2) AS ACCESS_CONCENTRATION_RATIO,
            MAX(MAX_OBJECT_ACCESSES) AS TOP_OBJECT_ACCESSES,
            ROUND((MAX(MAX_OBJECT_ACCESSES) * 100.0) / NULLIF(SUM(TOTAL_ACCESSES), 0), 2) AS TOP_OBJECT_CONCENTRATION_PCT,
            CASE 
                WHEN ACCESS_CONCENTRATION_RATIO > 200 AND TOP_OBJECT_CONCENTRATION_PCT > 60 THEN 'CRITICAL'
                WHEN ACCESS_CONCENTRATION_RATIO > 100 AND TOP_OBJECT_CONCENTRATION_PCT > 40 THEN 'HIGH'
                WHEN ACCESS_CONCENTRATION_RATIO > 50 OR TOP_OBJECT_CONCENTRATION_PCT > 25 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM hotspot_analysis
        GROUP BY USER_NAME
        HAVING SUM(TOTAL_ACCESSES) > 50
        ORDER BY ACCESS_CONCENTRATION_RATIO DESC
    """,
    "description": "Identifies users with concentrated data access patterns suitable for optimization"
}
```

## 7. Peak Hour Resource Abuse Score
```sql
"peak_hour_resource_abuse_score": {
    "query": """
        WITH peak_hour_analysis AS (
            SELECT
                USER_NAME,
                COUNT(*) AS TOTAL_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 18 AND 8 THEN 1 END) AS OFF_PEAK_QUERIES,
                COALESCE(AVG(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PEAK_AVG_HOURS,
                COALESCE(AVG(CASE WHEN HOUR(START_TIME) BETWEEN 18 AND 8 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS OFF_PEAK_AVG_HOURS,
                COALESCE(SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END), 0) / (1000 * 60 * 60) AS PEAK_TOTAL_HOURS,
                COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 
                    AND TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) > 1800000 THEN 1 END) AS PEAK_LONG_QUERIES
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'SUCCESS'
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            TOTAL_QUERIES,
            PEAK_HOUR_QUERIES,
            OFF_PEAK_QUERIES,
            ROUND((PEAK_HOUR_QUERIES * 100.0) / NULLIF(TOTAL_QUERIES, 0), 2) AS PEAK_HOUR_RATE_PCT,
            PEAK_AVG_HOURS,
            OFF_PEAK_AVG_HOURS,
            PEAK_TOTAL_HOURS,
            PEAK_LONG_QUERIES,
            ROUND(PEAK_TOTAL_HOURS * 3.0, 2) AS ESTIMATED_PEAK_COST_DOLLARS,
            CASE 
                WHEN PEAK_HOUR_RATE_PCT > 80 AND PEAK_AVG_HOURS > 0.5 THEN 'CRITICAL'
                WHEN PEAK_HOUR_RATE_PCT > 60 AND PEAK_AVG_HOURS > 0.25 THEN 'HIGH'
                WHEN PEAK_HOUR_RATE_PCT > 40 OR PEAK_AVG_HOURS > 0.1 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM peak_hour_analysis
        WHERE TOTAL_QUERIES > 20 AND PEAK_HOUR_QUERIES > 10
        ORDER BY PEAK_HOUR_RATE_PCT DESC
    """,
    "description": "Identifies users abusing resources during peak business hours"
}
```

## 8. Advanced Error Pattern Intelligence
```sql
"advanced_error_pattern_intelligence": {
    "query": """
        WITH error_analysis AS (
            SELECT
                USER_NAME,
                ERROR_CODE,
                ERROR_MESSAGE,
                COUNT(*) AS ERROR_COUNT,
                COUNT(DISTINCT TO_DATE(START_TIME)) AS DAYS_WITH_ERROR,
                COALESCE(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / 1000 AS AVG_FAIL_TIME_SEC,
                COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60 * 60) AS TOTAL_WASTED_HOURS,
                MIN(START_TIME) AS FIRST_ERROR_DATE,
                MAX(START_TIME) AS LAST_ERROR_DATE
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS = 'FAILED'
                AND ERROR_CODE IS NOT NULL
            GROUP BY USER_NAME, ERROR_CODE, ERROR_MESSAGE
        ),
        user_error_summary AS (
            SELECT
                USER_NAME,
                COUNT(DISTINCT ERROR_CODE) AS UNIQUE_ERROR_TYPES,
                SUM(ERROR_COUNT) AS TOTAL_ERRORS,
                SUM(TOTAL_WASTED_HOURS) AS TOTAL_WASTED_HOURS,
                MAX(DAYS_WITH_ERROR) AS MAX_ERROR_PERSISTENCE,
                AVG(AVG_FAIL_TIME_SEC) AS AVG_FAIL_TIME_SEC,
                COUNT(CASE WHEN DAYS_WITH_ERROR > 7 THEN 1 END) AS PERSISTENT_ERROR_TYPES
            FROM error_analysis
            GROUP BY USER_NAME
        )
        SELECT
            USER_NAME,
            UNIQUE_ERROR_TYPES,
            TOTAL_ERRORS,
            TOTAL_WASTED_HOURS,
            MAX_ERROR_PERSISTENCE,
            AVG_FAIL_TIME_SEC,
            PERSISTENT_ERROR_TYPES,
            ROUND(TOTAL_WASTED_HOURS * 2.5, 2) AS ESTIMATED_ERROR_COST_DOLLARS,
            ROUND((PERSISTENT_ERROR_TYPES * 100.0) / NULLIF(UNIQUE_ERROR_TYPES, 0), 2) AS PERSISTENCE_RATE_PCT,
            CASE 
                WHEN PERSISTENCE_RATE_PCT > 60 AND TOTAL_WASTED_HOURS > 5 THEN 'CRITICAL'
                WHEN PERSISTENCE_RATE_PCT > 40 AND TOTAL_WASTED_HOURS > 2 THEN 'HIGH'
                WHEN PERSISTENCE_RATE_PCT > 20 OR TOTAL_WASTED_HOURS > 1 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS OPTIMIZATION_PRIORITY
        FROM user_error_summary
        WHERE TOTAL_ERRORS > 5
        ORDER BY PERSISTENCE_RATE_PCT DESC, TOTAL_WASTED_HOURS DESC
    """,
    "description": "Identifies users with persistent error patterns indicating learning or process issues"
}
```

# TOP 8 SNOWFLAKE USER OPTIMIZATION CHARTS

## 1. User Cost-Efficiency Matrix
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
            WHERE START_TIME >= CURRENT_DATE - 30
                AND EXECUTION_STATUS IN ('SUCCESS', 'FAILED', 'CANCELED')
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
            ROUND(TOTAL_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_COST_DOLLARS,
            AVG_SCAN_PER_QUERY_TB,
            CASE 
                WHEN COMPUTE_EFFICIENCY_RATIO > 50 AND SUCCESS_RATE_PCT < 80 THEN 'High Cost, Low Efficiency'
                WHEN COMPUTE_EFFICIENCY_RATIO > 50 AND SUCCESS_RATE_PCT >= 80 THEN 'High Cost, High Efficiency'
                WHEN COMPUTE_EFFICIENCY_RATIO <= 50 AND SUCCESS_RATE_PCT < 80 THEN 'Low Cost, Low Efficiency'
                ELSE 'Low Cost, High Efficiency'
            END AS EFFICIENCY_QUADRANT
        FROM user_efficiency
        WHERE TOTAL_COMPUTE_HOURS > 0.5 AND TOTAL_DATA_SCANNED_TB > 0.001
        ORDER BY TOTAL_COMPUTE_HOURS DESC
    """,
    "chart_type": "scatter",
    "description": "Scatter plot showing user cost vs efficiency with success rate sizing"
}
```

## 2. Weekly Waste Trend Analysis
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
            WHERE START_TIME >= CURRENT_DATE - 56
            GROUP BY USER_NAME, DATE_TRUNC('WEEK', START_TIME)
        )
        SELECT
            USER_NAME,
            WEEK_START,
            WASTED_HOURS,
            PRODUCTIVE_HOURS,
            FAILED_QUERIES,
            SUCCESS_QUERIES,
            ROUND(WASTED_HOURS * 2.5, 2) AS WASTED_COST_DOLLARS,
            ROUND(CASE WHEN (WASTED_HOURS + PRODUCTIVE_HOURS) > 0 
                THEN (WASTED_HOURS * 100.0) / (WASTED_HOURS + PRODUCTIVE_HOURS) 
                ELSE 0 END, 2) AS WASTE_PERCENTAGE,
            LAG(WASTED_HOURS, 1) OVER (PARTITION BY USER_NAME ORDER BY WEEK_START) AS PREV_WEEK_WASTE,
            ROUND(WASTED_HOURS - LAG(WASTED_HOURS, 1) OVER (PARTITION BY USER_NAME ORDER BY WEEK_START), 2) AS WASTE_TREND
        FROM weekly_waste
        WHERE WASTED_HOURS > 0.1 OR PRODUCTIVE_HOURS > 0.1
        ORDER BY USER_NAME, WEEK_START
    """,
    "chart_type": "line",
    "description": "Multi-line chart showing waste trends over time with improvement/degradation indicators"
}
```

## 3. Query Lifecycle Bottleneck Waterfall
```sql
"query_lifecycle_bottleneck_waterfall_chart": {
    "query": """
        WITH lifecycle_analysis AS (
            SELECT
                USER_NAME,
                COALESCE(AVG(NULLIF(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0), 0)), 0) /