# SNOWFLAKE USER 360 DASHBOARD - CHARTS & TABLES

## 6 KEY CHARTS

### CHART_1: User Cost Efficiency Matrix
```sql
"user_cost_efficiency_matrix": {
    "query": """
        SELECT
            USER_NAME,
            SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
            SUM(COALESCE(BYTES_SCANNED, 0)) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB,
            CASE 
                WHEN SUM(COALESCE(BYTES_SCANNED, 0)) = 0 THEN 0
                ELSE ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) / (SUM(COALESCE(BYTES_SCANNED, 0)) / POW(1024, 4)), 4)
            END AS COMPUTE_EFFICIENCY_RATIO,
            COUNT(*) AS TOTAL_QUERIES,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) * 2.5, 2) AS ESTIMATED_COST_USD
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
            AND BYTES_SCANNED > 0
        GROUP BY USER_NAME
        HAVING TOTAL_COMPUTE_HOURS > 0.5 AND TOTAL_DATA_SCANNED_TB > 0.01
        ORDER BY COMPUTE_EFFICIENCY_RATIO DESC
        LIMIT 50
    """,
    "chart_type": "scatter",
    "x_axis": "TOTAL_DATA_SCANNED_TB",
    "y_axis": "TOTAL_COMPUTE_HOURS",
    "size_by": "TOTAL_QUERIES",
    "color_by": "COMPUTE_EFFICIENCY_RATIO",
    "description": "Identifies inefficient users with high compute cost per TB scanned"
}
```

### CHART_2: Daily Waste Pattern Heatmap
```sql
"daily_waste_heatmap": {
    "query": """
        SELECT
            USER_NAME,
            DAYNAME(START_TIME) AS DAY_OF_WEEK,
            SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
            COUNT(*) AS FAILED_QUERIES,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) * 2.5, 2) AS WASTED_COST_USD
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED')
        GROUP BY USER_NAME, DAYNAME(START_TIME)
        HAVING WASTED_COMPUTE_HOURS > 0.1
        ORDER BY USER_NAME, 
            CASE DAYNAME(START_TIME)
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    """,
    "chart_type": "heatmap",
    "x_axis": "DAY_OF_WEEK",
    "y_axis": "USER_NAME",
    "color_by": "WASTED_COMPUTE_HOURS",
    "description": "Shows users with consistent daily waste patterns requiring intervention"
}
```

### CHART_3: Query Lifecycle Bottleneck Analysis
```sql
"query_lifecycle_bottleneck": {
    "query": """
        SELECT
            USER_NAME,
            DATE_TRUNC('day', START_TIME) AS QUERY_DATE,
            AVG(COALESCE(COMPILATION_TIME, 0)) / 1000 AS AVG_COMPILE_TIME_SEC,
            AVG(COALESCE(QUEUED_OVERLOAD_TIME, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
            AVG(COALESCE(BLOCKED_TIME, 0)) / 1000 AS AVG_BLOCKED_TIME_SEC,
            AVG(COALESCE(EXECUTION_TIME, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
            COUNT(*) AS DAILY_QUERIES
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY USER_NAME, DATE_TRUNC('day', START_TIME)
        HAVING DAILY_QUERIES > 10
        ORDER BY USER_NAME, QUERY_DATE
    """,
    "chart_type": "line",
    "x_axis": "QUERY_DATE",
    "y_axis": ["AVG_COMPILE_TIME_SEC", "AVG_QUEUE_TIME_SEC", "AVG_BLOCKED_TIME_SEC", "AVG_EXECUTION_TIME_SEC"],
    "group_by": "USER_NAME",
    "description": "Identifies bottlenecks in query execution lifecycle by user"
}
```

### CHART_4: Spill Impact by Query Duration
```sql
"spill_impact_analysis": {
    "query": """
        SELECT
            USER_NAME,
            CASE 
                WHEN EXECUTION_TIME < 60000 THEN '<1min'
                WHEN EXECUTION_TIME < 300000 THEN '1-5min'
                WHEN EXECUTION_TIME < 1800000 THEN '5-30min'
                ELSE '>30min'
            END AS EXECUTION_TIME_BUCKET,
            COUNT(*) AS TOTAL_QUERIES,
            COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) AS SPILL_QUERIES,
            ROUND(100.0 * COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) / COUNT(*), 2) AS SPILL_RATE_PCT,
            AVG(COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0)) / POW(1024, 3) AS AVG_SPILL_GB
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY USER_NAME, EXECUTION_TIME_BUCKET
        HAVING TOTAL_QUERIES > 5
        ORDER BY USER_NAME, EXECUTION_TIME_BUCKET
    """,
    "chart_type": "grouped_bar",
    "x_axis": "EXECUTION_TIME_BUCKET",
    "y_axis": "SPILL_RATE_PCT",
    "group_by": "USER_NAME",
    "description": "Shows memory spill patterns indicating poor query optimization"
}
```

### CHART_5: Hourly Resource Contention
```sql
"hourly_resource_contention": {
    "query": """
        SELECT
            USER_NAME,
            HOUR(START_TIME) AS HOUR_OF_DAY,
            AVG(COALESCE(QUEUED_OVERLOAD_TIME, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
            COUNT(*) AS QUERIES_COUNT,
            SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
            CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 'Business Hours' ELSE 'Off Hours' END AS TIME_CATEGORY
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY USER_NAME, HOUR(START_TIME)
        HAVING QUERIES_COUNT > 5
        ORDER BY USER_NAME, HOUR_OF_DAY
    """,
    "chart_type": "heatmap",
    "x_axis": "HOUR_OF_DAY",
    "y_axis": "USER_NAME",
    "color_by": "AVG_QUEUE_TIME_SEC",
    "description": "Identifies users causing resource contention during peak hours"
}
```

### CHART_6: Optimization Opportunity Scoring
```sql
"optimization_opportunity_scoring": {
    "query": """
        SELECT
            USER_NAME,
            LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN COALESCE(EXECUTION_TIME, 0) ELSE 0 END) / (1000 * 60 * 60)) * 10)) AS WASTE_SCORE,
            LEAST(100, GREATEST(0, (AVG(COALESCE(BYTES_SCANNED, 0)) / POW(1024, 4)) * 20)) AS SCAN_INEFFICIENCY_SCORE,
            LEAST(100, GREATEST(0, (COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)))) AS MEMORY_PRESSURE_SCORE,
            LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)))) AS PEAK_HOUR_ABUSE_SCORE,
            ROUND((
                LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN COALESCE(EXECUTION_TIME, 0) ELSE 0 END) / (1000 * 60 * 60)) * 10)) +
                LEAST(100, GREATEST(0, (AVG(COALESCE(BYTES_SCANNED, 0)) / POW(1024, 4)) * 20)) +
                LEAST(100, GREATEST(0, (COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)))) +
                LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0))))
            ) / 4, 2) AS TOTAL_OPTIMIZATION_SCORE,
            COUNT(*) AS TOTAL_QUERIES
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
        GROUP BY USER_NAME
        HAVING COUNT(*) > 20
        ORDER BY TOTAL_OPTIMIZATION_SCORE DESC
        LIMIT 50
    """,
    "chart_type": "stacked_bar",
    "x_axis": "USER_NAME",
    "y_axis": ["WASTE_SCORE", "SCAN_INEFFICIENCY_SCORE", "MEMORY_PRESSURE_SCORE", "PEAK_HOUR_ABUSE_SCORE"],
    "description": "Composite scoring showing optimization potential by user"
}
```

## 6 KEY TABLES

### TABLE_1: Top Wasted Compute Users
```sql
"top_wasted_compute_users": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(*) AS FAILED_QUERIES,
            SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) * 2.5, 2) AS WASTED_COST_USD,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS FAILURE_RATE_PCT,
            ROUND(AVG(COALESCE(EXECUTION_TIME, 0)) / 1000, 2) AS AVG_FAILURE_TIME_SEC,
            'Implement query testing and error handling' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED')
        GROUP BY USER_NAME
        HAVING WASTED_COMPUTE_HOURS > 0.5
        ORDER BY WASTED_COMPUTE_HOURS DESC
        LIMIT 25
    """,
    "description": "Users burning credits on failed queries - immediate intervention needed"
}
```

### TABLE_2: Inefficient Data Scanners
```sql
"inefficient_data_scanners": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(*) AS TOTAL_QUERIES,
            ROUND(AVG(COALESCE(BYTES_SCANNED, 0)) / POW(1024, 4), 4) AS AVG_DATA_SCANNED_TB,
            ROUND(AVG(COALESCE(BYTES_WRITTEN, 0)) / POW(1024, 3), 4) AS AVG_DATA_OUTPUT_GB,
            ROUND(AVG(COALESCE(BYTES_SCANNED, 0)) / NULLIF(AVG(COALESCE(BYTES_WRITTEN, 0)), 0), 0) AS SCAN_TO_OUTPUT_RATIO,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60), 2) AS TOTAL_COMPUTE_HOURS,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) * 2.5, 2) AS TOTAL_COST_USD,
            'Add WHERE clauses, implement clustering, create summary tables' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
            AND BYTES_SCANNED > 0
            AND BYTES_WRITTEN > 0
        GROUP BY USER_NAME
        HAVING AVG_DATA_SCANNED_TB > 0.1 AND SCAN_TO_OUTPUT_RATIO > 1000
        ORDER BY SCAN_TO_OUTPUT_RATIO DESC
        LIMIT 25
    """,
    "description": "Users scanning massive data for minimal output - poor query design"
}
```

### TABLE_3: Memory Spill Offenders
```sql
"memory_spill_offenders": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(*) AS TOTAL_QUERIES,
            COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) AS SPILL_QUERIES,
            ROUND(100.0 * COUNT(CASE WHEN COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) > 0 THEN 1 END) / COUNT(*), 2) AS SPILL_RATE_PCT,
            ROUND(AVG(COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0)) / POW(1024, 3), 4) AS AVG_REMOTE_SPILL_GB,
            ROUND(AVG(COALESCE(BYTES_SPILLED_TO_LOCAL_STORAGE, 0)) / POW(1024, 3), 4) AS AVG_LOCAL_SPILL_GB,
            ROUND(AVG(COALESCE(EXECUTION_TIME, 0)) / 1000, 2) AS AVG_EXECUTION_TIME_SEC,
            'Optimize JOIN order, use larger warehouse, add query hints' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY USER_NAME
        HAVING TOTAL_QUERIES > 50 AND SPILL_RATE_PCT > 15
        ORDER BY SPILL_RATE_PCT DESC
        LIMIT 25
    """,
    "description": "Users with high memory spill rates causing performance degradation"
}
```

### TABLE_4: Peak Hour Resource Abusers
```sql
"peak_hour_resource_abusers": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(*) AS TOTAL_QUERIES,
            COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
            ROUND(100.0 * COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) / COUNT(*), 2) AS PEAK_HOUR_PCT,
            ROUND(AVG(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN COALESCE(EXECUTION_TIME, 0) END) / (1000 * 60), 2) AS AVG_PEAK_DURATION_MIN,
            ROUND(SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN COALESCE(EXECUTION_TIME, 0) END) / (1000 * 60 * 60), 2) AS PEAK_COMPUTE_HOURS,
            ROUND(SUM(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN COALESCE(EXECUTION_TIME, 0) END) / (1000 * 60 * 60) * 2.5, 2) AS PEAK_COST_USD,
            'Schedule heavy queries off-peak, implement query governance' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
        GROUP BY USER_NAME
        HAVING PEAK_HOUR_QUERIES > 100 AND AVG_PEAK_DURATION_MIN > 5
        ORDER BY PEAK_COMPUTE_HOURS DESC
        LIMIT 25
    """,
    "description": "Users running expensive queries during business hours"
}
```

### TABLE_5: Compilation Bottleneck Users
```sql
"compilation_bottleneck_users": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(*) AS TOTAL_QUERIES,
            ROUND(AVG(COALESCE(COMPILATION_TIME, 0)) / 1000, 2) AS AVG_COMPILE_TIME_SEC,
            ROUND(AVG(COALESCE(EXECUTION_TIME, 0)) / 1000, 2) AS AVG_EXECUTION_TIME_SEC,
            ROUND(AVG(COALESCE(COMPILATION_TIME, 0)) / NULLIF(AVG(COALESCE(EXECUTION_TIME, 0)), 0), 4) AS COMPILE_TO_EXEC_RATIO,
            ROUND(SUM(COALESCE(COMPILATION_TIME, 0)) / (1000 * 60 * 60), 2) AS TOTAL_COMPILE_HOURS,
            COUNT(DISTINCT QUERY_TEXT) AS UNIQUE_QUERIES,
            'Use prepared statements, avoid dynamic SQL, implement query caching' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'SUCCESS'
            AND COMPILATION_TIME > 0
        GROUP BY USER_NAME
        HAVING TOTAL_QUERIES > 100 AND AVG_COMPILE_TIME_SEC > 3
        ORDER BY COMPILE_TO_EXEC_RATIO DESC
        LIMIT 25
    """,
    "description": "Users with high compilation overhead indicating dynamic SQL abuse"
}
```

### TABLE_6: Recurring Error Pattern Users
```sql
"recurring_error_pattern_users": {
    "query": """
        SELECT
            USER_NAME,
            ERROR_CODE,
            LEFT(ERROR_MESSAGE, 100) AS ERROR_MESSAGE_TRUNCATED,
            COUNT(*) AS ERROR_COUNT,
            COUNT(DISTINCT DATE(START_TIME)) AS DAYS_WITH_ERROR,
            ROUND(AVG(COALESCE(EXECUTION_TIME, 0)) / 1000, 2) AS AVG_FAIL_TIME_SEC,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60), 2) AS TOTAL_WASTED_HOURS,
            ROUND(SUM(COALESCE(EXECUTION_TIME, 0)) / (1000 * 60 * 60) * 2.5, 2) AS TOTAL_WASTED_COST_USD,
            'Provide targeted training, implement error handling patterns' AS OPTIMIZATION_ACTION
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_DATE)
            AND EXECUTION_STATUS = 'FAILED'
            AND ERROR_CODE IS NOT NULL
        GROUP BY USER_NAME, ERROR_CODE, LEFT(ERROR_MESSAGE, 100)
        HAVING ERROR_COUNT > 5 AND DAYS_WITH_ERROR > 2
        ORDER BY USER_NAME, ERROR_COUNT DESC
        LIMIT 25
    """,
    "description": "Users with recurring error patterns requiring immediate intervention"
}
```