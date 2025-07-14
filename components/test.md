# Top 8 Snowflake User Optimization Metrics

## 1. **Wasted Compute (Failed/Cancelled Hours)**
```sql
-- High-impact metric showing users burning credits on failed queries
SELECT
    USER_NAME,
    COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
    COUNT(*) AS FAILED_QUERIES,
    ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_WASTED_CREDITS -- Assume $2.5/credit
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED')
GROUP BY USER_NAME
ORDER BY WASTED_COMPUTE_HOURS DESC
```
**Bad User Pattern**: Users with >10 wasted hours/month are likely writing untested queries or have poor error handling
**Action**: Code review, query testing in dev environment, timeout settings

## 2. **Query Efficiency Ratio (Data Scanned vs Results)**
```sql
-- Identifies users scanning massive amounts of data for small results
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)) AS SCAN_TO_OUTPUT_RATIO,
    AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) AS AVG_DATA_SCANNED_TB,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS' AND BYTES_SCANNED > 0 AND BYTES_WRITTEN > 0
GROUP BY USER_NAME
HAVING AVG_DATA_SCANNED_TB > 0.1 -- Focus on significant data scanners
ORDER BY SCAN_TO_OUTPUT_RATIO DESC
```
**Bad User Pattern**: Ratio >1000 indicates poor filtering, missing WHERE clauses, or full table scans
**Action**: Implement clustering keys, add proper WHERE clauses, create summary tables

## 3. **Memory Pressure Index (Spill Rate)**
```sql
-- Shows users consistently causing memory issues
SELECT
    USER_NAME,
    COUNT(CASE WHEN (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0) THEN 1 END) AS SPILL_QUERIES,
    COUNT(*) AS TOTAL_QUERIES,
    ROUND(100.0 * SPILL_QUERIES / TOTAL_QUERIES, 2) AS SPILL_RATE_PCT,
    AVG(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0)) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING TOTAL_QUERIES > 50 AND SPILL_RATE_PCT > 10
ORDER BY SPILL_RATE_PCT DESC
```
**Bad User Pattern**: >20% spill rate indicates complex joins without proper optimization
**Action**: Optimize JOIN order, use appropriate warehouse size, implement query hints

## 4. **Compilation Overhead Score**
```sql
-- Identifies users with inefficient query patterns causing compilation bottlenecks
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0) / NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)) AS COMPILE_TO_EXEC_RATIO,
    AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS AVG_COMPILE_TIME_SEC,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS' AND COMPILATION_TIME > 0
GROUP BY USER_NAME
HAVING TOTAL_QUERIES > 100 AND AVG_COMPILE_TIME_SEC > 5
ORDER BY COMPILE_TO_EXEC_RATIO DESC
```
**Bad User Pattern**: Ratio >0.5 suggests dynamic SQL, frequent DDL, or schema changes
**Action**: Use prepared statements, avoid dynamic SQL, implement query caching

## 5. **Concurrency Contention Impact**
```sql
-- Shows users causing warehouse queuing and blocking others
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
    COUNT(CASE WHEN QUEUED_OVERLOAD_TIME > 30000 THEN 1 END) AS HIGH_QUEUE_QUERIES,
    AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING AVG_QUEUE_TIME_SEC > 10 AND TOTAL_QUERIES > 50
ORDER BY AVG_QUEUE_TIME_SEC DESC
```
**Bad User Pattern**: High queue times during business hours indicate poor query scheduling
**Action**: Implement query scheduling, use separate warehouses for heavy workloads

## 6. **Data Hotspot Concentration**
```sql
-- Identifies users repeatedly hitting the same objects (potential for optimization)
SELECT
    USER_NAME,
    COUNT(DISTINCT DATABASE_NAME || '.' || SCHEMA_NAME || '.' || TABLE_NAME) AS UNIQUE_OBJECTS,
    COUNT(*) AS TOTAL_ACCESSES,
    ROUND(TOTAL_ACCESSES::FLOAT / UNIQUE_OBJECTS, 2) AS ACCESS_CONCENTRATION_RATIO
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
WHERE QUERY_START_TIME >= CURRENT_DATE - 30
GROUP BY USER_NAME
HAVING TOTAL_ACCESSES > 100 AND ACCESS_CONCENTRATION_RATIO > 50
ORDER BY ACCESS_CONCENTRATION_RATIO DESC
```
**Bad User Pattern**: High concentration (>100) on few objects without result caching
**Action**: Implement result caching, create materialized views, use query result cache

## 7. **Peak Hour Resource Abuse**
```sql
-- Shows users running expensive queries during peak business hours
SELECT
    USER_NAME,
    COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
    AVG(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END) / (1000 * 60 * 60) AS PEAK_AVG_HOURS,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING PEAK_HOUR_QUERIES > 100 AND PEAK_AVG_HOURS > 0.5
ORDER BY PEAK_AVG_HOURS DESC
```
**Bad User Pattern**: Running >30min queries during 9-5 business hours
**Action**: Schedule heavy queries for off-peak hours, implement query governance

## 8. **Error Pattern Frequency**
```sql
-- Advanced error analysis showing users with recurring issues
SELECT
    USER_NAME,
    ERROR_CODE,
    ERROR_MESSAGE,
    COUNT(*) AS ERROR_COUNT,
    COUNT(DISTINCT TO_DATE(START_TIME)) AS DAYS_WITH_ERROR,
    ROUND(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000, 2) AS AVG_FAIL_TIME_SEC
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'FAILED' AND ERROR_CODE IS NOT NULL
GROUP BY USER_NAME, ERROR_CODE, ERROR_MESSAGE
HAVING ERROR_COUNT > 10 AND DAYS_WITH_ERROR > 3
ORDER BY USER_NAME, ERROR_COUNT DESC
```
**Bad User Pattern**: Repeated same errors over multiple days
**Action**: Targeted training, code review, implement error handling patterns

---

MPILE_TIME_SEC,
    AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
    AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
    COUNT(*) AS DAILY_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME, TO_DATE(START_TIME)
HAVING DAILY_QUERIES > 10
ORDER BY USER_NAME, QUERY_DATE
```
**Chart Type**: Multi-line time series (separate lines for compile, queue, execution)
**Bad User Pattern**: High compile time suggests dynamic SQL abuse

## 4. **Spill Cascade Impact Chart**
```sql
-- Shows correlation between query complexity and spill behavior
SELECT
    USER_NAME,
    CASE 
        WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 60000 THEN '<1min'
        WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 300000 THEN '1-5min'
        WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 1800000 THEN '5-30min'
        ELSE '>30min'
    END AS EXECUTION_TIME_BUCKET,
    COUNT(*) AS TOTAL_QUERIES,
    COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) AS SPILL_QUERIES,
    ROUND(100.0 * SPILL_QUERIES / TOTAL_QUERIES, 2) AS SPILL_RATE_PCT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME, EXECUTION_TIME_BUCKET
ORDER BY USER_NAME, EXECUTION_TIME_BUCKET
```
**Chart Type**: Grouped bar chart (X: Execution Time Bucket, Y: Spill Rate %, Group: User)
**Bad User Pattern**: High spill rates in short queries indicate poor query design

## 5. **Hourly Resource Contention Map**
```sql
-- Shows when users are causing resource contention
SELECT
    USER_NAME,
    HOUR(START_TIME) AS HOUR_OF_DAY,
    AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
    COUNT(*) AS QUERIES_COUNT,
    SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME, HOUR(START_TIME)
HAVING QUERIES_COUNT > 5
ORDER BY USER_NAME, HOUR_OF_DAY
```
**Chart Type**: Heatmap (X: Hour of Day, Y: User, Color: Queue Time)
**Bad User Pattern**: Heavy usage during business hours (9-17) indicates poor scheduling

## 6. **Error Recovery Velocity**
```sql
-- Shows how quickly users recover from errors (learning curve)
SELECT
    USER_NAME,
    TO_DATE(START_TIME) AS ERROR_DATE,
    COUNT(*) AS DAILY_ERRORS,
    LAG(COUNT(*), 1) OVER (PARTITION BY USER_NAME ORDER BY TO_DATE(START_TIME)) AS PREV_DAY_ERRORS,
    COUNT(*) - PREV_DAY_ERRORS AS ERROR_TREND
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'FAILED'
GROUP BY USER_NAME, TO_DATE(START_TIME)
ORDER BY USER_NAME, ERROR_DATE
```
**Chart Type**: Line chart with trend arrows (X: Date, Y: Error Count, Trend: Up/Down arrows)
**Bad User Pattern**: Increasing or flat error trends indicate learning issues

## 7. **Data Access Pattern Efficiency**
```sql
-- Radar chart showing user's data access patterns
SELECT
    USER_NAME,
    COUNT(DISTINCT DATABASE_NAME) AS DATABASE_SPREAD,
    COUNT(DISTINCT SCHEMA_NAME) AS SCHEMA_SPREAD,
    COUNT(DISTINCT TABLE_NAME) AS TABLE_SPREAD,
    COUNT(*) AS TOTAL_ACCESSES,
    ROUND(TOTAL_ACCESSES::FLOAT / COUNT(DISTINCT DATABASE_NAME || SCHEMA_NAME || TABLE_NAME), 2) AS ACCESS_CONCENTRATION
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
WHERE QUERY_START_TIME >= CURRENT_DATE - 30
GROUP BY USER_NAME
HAVING TOTAL_ACCESSES > 100
ORDER BY ACCESS_CONCENTRATION DESC
```
**Chart Type**: Radar chart (axes: DB spread, schema spread, table spread, concentration)
**Bad User Pattern**: High spread with low concentration indicates unfocused data access

## 8. **Optimization Opportunity Scoring**
```sql
-- Comprehensive scoring system for optimization potential
SELECT
    USER_NAME,
    -- Waste Score (0-100)
    LEAST(100, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60)) * 10) AS WASTE_SCORE,
    -- Efficiency Score (0-100)
    LEAST(100, AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) * 20) AS SCAN_INEFFICIENCY_SCORE,
    -- Memory Score (0-100)
    LEAST(100, COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) * 100.0 / COUNT(*)) AS MEMORY_PRESSURE_SCORE,
    -- Peak Hour Score (0-100)
    LEAST(100, COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) * 100.0 / COUNT(*)) AS PEAK_HOUR_ABUSE_SCORE,
    -- Total Opportunity Score
    (WASTE_SCORE + SCAN_INEFFICIENCY_SCORE + MEMORY_PRESSURE_SCORE + PEAK_HOUR_ABUSE_SCORE) / 4 AS TOTAL_OPTIMIZATION_SCORE
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= CURRENT_DATE - 30
GROUP BY USER_NAME
HAVING COUNT(*) > 50
ORDER BY TOTAL_OPTIMIZATION_SCORE DESC
```
**Chart Type**: Stacked bar chart (X: User, Y: Score components stacked, Total height: Combined score)
**Bad User Pattern**: Score >60 indicates high optimization potential

---

## Key Optimization Actions by Pattern:

### 🔴 **High-Risk Users (Score >80)**
- Immediate query review and optimization
- Implement query governance and approval process
- Separate warehouse for heavy workloads
- Mandatory training on query optimization

### 🟡 **Medium-Risk Users (Score 40-80)**
- Schedule regular query performance reviews
- Implement query caching strategies
- Optimize most frequently accessed objects
- Set up monitoring alerts for resource usage

### 🟢 **Low-Risk Users (Score <40)**
- Maintain current practices
- Share best practices with high-risk users
- Consider as optimization mentors

These metrics and charts provide deep insights into user behavior patterns and specific, actionable optimization opportunities rather than just basic performance statistics.


# Top 8 Snowflake User Optimization Metrics

## 1. **Wasted Compute (Failed/Cancelled Hours)**
```sql
-- High-impact metric showing users burning credits on failed queries
SELECT
    USER_NAME,
    COALESCE(SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)), 0) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
    COUNT(*) AS FAILED_QUERIES,
    ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_WASTED_CREDITS -- Assume $2.5/credit
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED')
GROUP BY USER_NAME
ORDER BY WASTED_COMPUTE_HOURS DESC
```
**Bad User Pattern**: Users with >10 wasted hours/month are likely writing untested queries or have poor error handling
**Action**: Code review, query testing in dev environment, timeout settings

## 2. **Query Efficiency Ratio (Data Scanned vs Results)**
```sql
-- Identifies users scanning massive amounts of data for small results
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0) / NULLIF(TRY_TO_NUMBER(BYTES_WRITTEN, 38, 0), 0)) AS SCAN_TO_OUTPUT_RATIO,
    AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) AS AVG_DATA_SCANNED_TB,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS' AND BYTES_SCANNED > 0 AND BYTES_WRITTEN > 0
GROUP BY USER_NAME
HAVING AVG_DATA_SCANNED_TB > 0.1 -- Focus on significant data scanners
ORDER BY SCAN_TO_OUTPUT_RATIO DESC
```
**Bad User Pattern**: Ratio >1000 indicates poor filtering, missing WHERE clauses, or full table scans
**Action**: Implement clustering keys, add proper WHERE clauses, create summary tables

## 3. **Memory Pressure Index (Spill Rate)**
```sql
-- Shows users consistently causing memory issues
SELECT
    USER_NAME,
    COUNT(CASE WHEN (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0) THEN 1 END) AS SPILL_QUERIES,
    COUNT(*) AS TOTAL_QUERIES,
    ROUND(100.0 * SPILL_QUERIES / TOTAL_QUERIES, 2) AS SPILL_RATE_PCT,
    AVG(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0)) / POW(1024, 3) AS AVG_REMOTE_SPILL_GB
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING TOTAL_QUERIES > 50 AND SPILL_RATE_PCT > 10
ORDER BY SPILL_RATE_PCT DESC
```
**Bad User Pattern**: >20% spill rate indicates complex joins without proper optimization
**Action**: Optimize JOIN order, use appropriate warehouse size, implement query hints

## 4. **Compilation Overhead Score**
```sql
-- Identifies users with inefficient query patterns causing compilation bottlenecks
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0) / NULLIF(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0), 0)) AS COMPILE_TO_EXEC_RATIO,
    AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS AVG_COMPILE_TIME_SEC,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS' AND COMPILATION_TIME > 0
GROUP BY USER_NAME
HAVING TOTAL_QUERIES > 100 AND AVG_COMPILE_TIME_SEC > 5
ORDER BY COMPILE_TO_EXEC_RATIO DESC
```
**Bad User Pattern**: Ratio >0.5 suggests dynamic SQL, frequent DDL, or schema changes
**Action**: Use prepared statements, avoid dynamic SQL, implement query caching

## 5. **Concurrency Contention Impact**
```sql
-- Shows users causing warehouse queuing and blocking others
SELECT
    USER_NAME,
    AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
    COUNT(CASE WHEN QUEUED_OVERLOAD_TIME > 30000 THEN 1 END) AS HIGH_QUEUE_QUERIES,
    AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING AVG_QUEUE_TIME_SEC > 10 AND TOTAL_QUERIES > 50
ORDER BY AVG_QUEUE_TIME_SEC DESC
```
**Bad User Pattern**: High queue times during business hours indicate poor query scheduling
**Action**: Implement query scheduling, use separate warehouses for heavy workloads

## 6. **Data Hotspot Concentration**
```sql
-- Identifies users repeatedly hitting the same objects (potential for optimization)
SELECT
    USER_NAME,
    COUNT(DISTINCT DATABASE_NAME || '.' || SCHEMA_NAME || '.' || TABLE_NAME) AS UNIQUE_OBJECTS,
    COUNT(*) AS TOTAL_ACCESSES,
    ROUND(TOTAL_ACCESSES::FLOAT / UNIQUE_OBJECTS, 2) AS ACCESS_CONCENTRATION_RATIO
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
WHERE QUERY_START_TIME >= CURRENT_DATE - 30
GROUP BY USER_NAME
HAVING TOTAL_ACCESSES > 100 AND ACCESS_CONCENTRATION_RATIO > 50
ORDER BY ACCESS_CONCENTRATION_RATIO DESC
```
**Bad User Pattern**: High concentration (>100) on few objects without result caching
**Action**: Implement result caching, create materialized views, use query result cache

## 7. **Peak Hour Resource Abuse**
```sql
-- Shows users running expensive queries during peak business hours
SELECT
    USER_NAME,
    COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) AS PEAK_HOUR_QUERIES,
    AVG(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) END) / (1000 * 60 * 60) AS PEAK_AVG_HOURS,
    COUNT(*) AS TOTAL_QUERIES
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
GROUP BY USER_NAME
HAVING PEAK_HOUR_QUERIES > 100 AND PEAK_AVG_HOURS > 0.5
ORDER BY PEAK_AVG_HOURS DESC
```
**Bad User Pattern**: Running >30min queries during 9-5 business hours
**Action**: Schedule heavy queries for off-peak hours, implement query governance

## 8. **Error Pattern Frequency**
```sql
-- Advanced error analysis showing users with recurring issues
SELECT
    USER_NAME,
    ERROR_CODE,
    ERROR_MESSAGE,
    COUNT(*) AS ERROR_COUNT,
    COUNT(DISTINCT TO_DATE(START_TIME)) AS DAYS_WITH_ERROR,
    ROUND(AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000, 2) AS AVG_FAIL_TIME_SEC
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'FAILED' AND ERROR_CODE IS NOT NULL
GROUP BY USER_NAME, ERROR_CODE, ERROR_MESSAGE
HAVING ERROR_COUNT > 10 AND DAYS_WITH_ERROR > 3
ORDER BY USER_NAME, ERROR_COUNT DESC
```
**Bad User Pattern**: Repeated same errors over multiple days
**Action**: Targeted training, code review, implement error handling patterns

---

# Top 8 Snowflake User Optimization Charts

## 1. **User Compute Cost Efficiency Matrix**
```sql
"user_compute_efficiency_matrix_chart": {
    "query": """
        SELECT
            USER_NAME,
            SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
            SUM(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4) AS TOTAL_DATA_SCANNED_TB,
            ROUND(TOTAL_COMPUTE_HOURS / NULLIF(TOTAL_DATA_SCANNED_TB, 0), 4) AS COMPUTE_EFFICIENCY_RATIO,
            COUNT(*) AS TOTAL_QUERIES,
            ROUND(TOTAL_COMPUTE_HOURS * 2.5, 2) AS ESTIMATED_COST_DOLLARS
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'SUCCESS' 
            AND BYTES_SCANNED > 0
            {object_filter}
        GROUP BY USER_NAME
        HAVING TOTAL_COMPUTE_HOURS > 1 AND TOTAL_DATA_SCANNED_TB > 0.01
        ORDER BY COMPUTE_EFFICIENCY_RATIO DESC
    """,
    "label": "User Compute Cost Efficiency Matrix",
    "description": "Scatter plot showing users by cost efficiency (compute time vs data processed). Users in top-right quadrant need immediate optimization.",
    "chart_type": "scatter",
    "x_col": "TOTAL_DATA_SCANNED_TB",
    "y_col": "TOTAL_COMPUTE_HOURS",
    "size_col": "TOTAL_QUERIES",
    "color_col": "COMPUTE_EFFICIENCY_RATIO",
    "hover_data": ["USER_NAME", "ESTIMATED_COST_DOLLARS", "COMPUTE_EFFICIENCY_RATIO"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: Users in top-right quadrant (high compute, high data scan) need optimization

## 2. **Daily Waste Pattern Heatmap**
```sql
"daily_waste_pattern_heatmap_chart": {
    "query": """
        SELECT
            USER_NAME,
            DAYNAME(START_TIME) AS DAY_OF_WEEK,
            SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / (1000 * 60 * 60) AS WASTED_COMPUTE_HOURS,
            COUNT(*) AS FAILED_QUERIES,
            ROUND(WASTED_COMPUTE_HOURS * 2.5, 2) AS WASTED_COST_DOLLARS
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS IN ('FAILED', 'ABORTED', 'CANCELED')
            {object_filter}
        GROUP BY USER_NAME, DAYNAME(START_TIME)
        HAVING WASTED_COMPUTE_HOURS > 0.1
        ORDER BY USER_NAME, 
            CASE DAYNAME(START_TIME)
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    """,
    "label": "Daily Waste Pattern Heatmap",
    "description": "Heatmap showing wasted compute by user and day of week. Consistent daily waste indicates systemic issues requiring intervention.",
    "chart_type": "heatmap",
    "x_col": "DAY_OF_WEEK",
    "y_col": "USER_NAME",
    "color_col": "WASTED_COMPUTE_HOURS",
    "hover_data": ["FAILED_QUERIES", "WASTED_COST_DOLLARS"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: Consistent daily waste indicates systemic issues

## 3. **Query Lifecycle Bottleneck Analysis**
```sql
"query_lifecycle_bottleneck_chart": {
    "query": """
        SELECT
            USER_NAME,
            TO_DATE(START_TIME) AS QUERY_DATE,
            AVG(TRY_TO_NUMBER(COMPILATION_TIME, 38, 0)) / 1000 AS AVG_COMPILE_TIME_SEC,
            AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
            AVG(TRY_TO_NUMBER(BLOCKED_TIME, 38, 0)) / 1000 AS AVG_BLOCKED_TIME_SEC,
            AVG(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / 1000 AS AVG_EXECUTION_TIME_SEC,
            COUNT(*) AS DAILY_QUERIES
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'SUCCESS'
            {object_filter}
        GROUP BY USER_NAME, TO_DATE(START_TIME)
        HAVING DAILY_QUERIES > 5
        ORDER BY USER_NAME, QUERY_DATE
    """,
    "label": "Query Lifecycle Bottleneck Analysis",
    "description": "Multi-line chart showing where users spend time in query lifecycle. High compile time suggests dynamic SQL abuse.",
    "chart_type": "line",
    "x_col": "QUERY_DATE",
    "y_col": ["AVG_COMPILE_TIME_SEC", "AVG_QUEUE_TIME_SEC", "AVG_BLOCKED_TIME_SEC", "AVG_EXECUTION_TIME_SEC"],
    "color_col": "USER_NAME",
    "hover_data": ["DAILY_QUERIES"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: High compile time suggests dynamic SQL abuse

## 4. **Spill Cascade Impact Chart**
```sql
"spill_cascade_impact_chart": {
    "query": """
        SELECT
            USER_NAME,
            CASE 
                WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 60000 THEN '<1min'
                WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 300000 THEN '1-5min'
                WHEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) < 1800000 THEN '5-30min'
                ELSE '>30min'
            END AS EXECUTION_TIME_BUCKET,
            COUNT(*) AS TOTAL_QUERIES,
            COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 END) AS SPILL_QUERIES,
            ROUND(100.0 * SPILL_QUERIES / TOTAL_QUERIES, 2) AS SPILL_RATE_PCT,
            AVG(TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0)) / POW(1024, 3) AS AVG_SPILL_GB
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'SUCCESS'
            {object_filter}
        GROUP BY USER_NAME, EXECUTION_TIME_BUCKET
        HAVING TOTAL_QUERIES > 10
        ORDER BY USER_NAME, EXECUTION_TIME_BUCKET
    """,
    "label": "Spill Cascade Impact Chart",
    "description": "Grouped bar chart showing spill behavior by query duration. High spill rates in short queries indicate poor query design.",
    "chart_type": "grouped_bar",
    "x_col": "EXECUTION_TIME_BUCKET",
    "y_col": "SPILL_RATE_PCT",
    "color_col": "USER_NAME",
    "hover_data": ["TOTAL_QUERIES", "SPILL_QUERIES", "AVG_SPILL_GB"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: High spill rates in short queries indicate poor query design

## 5. **Hourly Resource Contention Map**
```sql
"hourly_resource_contention_chart": {
    "query": """
        SELECT
            USER_NAME,
            HOUR(START_TIME) AS HOUR_OF_DAY,
            AVG(TRY_TO_NUMBER(QUEUED_OVERLOAD_TIME, 38, 0)) / 1000 AS AVG_QUEUE_TIME_SEC,
            COUNT(*) AS QUERIES_COUNT,
            SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / (1000 * 60 * 60) AS TOTAL_COMPUTE_HOURS,
            CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 'Business Hours' ELSE 'Off Hours' END AS TIME_CATEGORY
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'SUCCESS'
            {object_filter}
        GROUP BY USER_NAME, HOUR(START_TIME)
        HAVING QUERIES_COUNT > 3
        ORDER BY USER_NAME, HOUR_OF_DAY
    """,
    "label": "Hourly Resource Contention Map",
    "description": "Heatmap showing when users are causing resource contention. Heavy usage during business hours indicates poor scheduling.",
    "chart_type": "heatmap",
    "x_col": "HOUR_OF_DAY",
    "y_col": "USER_NAME",
    "color_col": "AVG_QUEUE_TIME_SEC",
    "hover_data": ["QUERIES_COUNT", "TOTAL_COMPUTE_HOURS", "TIME_CATEGORY"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: Heavy usage during business hours (9-17) indicates poor scheduling

## 6. **Error Recovery Velocity**
```sql
"error_recovery_velocity_chart": {
    "query": """
        SELECT
            USER_NAME,
            TO_DATE(START_TIME) AS ERROR_DATE,
            COUNT(*) AS DAILY_ERRORS,
            LAG(COUNT(*), 1) OVER (PARTITION BY USER_NAME ORDER BY TO_DATE(START_TIME)) AS PREV_DAY_ERRORS,
            COUNT(*) - COALESCE(LAG(COUNT(*), 1) OVER (PARTITION BY USER_NAME ORDER BY TO_DATE(START_TIME)), 0) AS ERROR_TREND,
            SUM(TRY_TO_NUMBER(EXECUTION_TIME, 38, 0)) / (1000 * 60 * 60) AS DAILY_WASTED_HOURS
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND EXECUTION_STATUS = 'FAILED'
            {object_filter}
        GROUP BY USER_NAME, TO_DATE(START_TIME)
        HAVING DAILY_ERRORS > 0
        ORDER BY USER_NAME, ERROR_DATE
    """,
    "label": "Error Recovery Velocity",
    "description": "Line chart showing error trends over time. Increasing or flat error trends indicate learning issues requiring intervention.",
    "chart_type": "line",
    "x_col": "ERROR_DATE",
    "y_col": "DAILY_ERRORS",
    "color_col": "USER_NAME",
    "hover_data": ["ERROR_TREND", "DAILY_WASTED_HOURS"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: Increasing or flat error trends indicate learning issues

## 7. **Data Access Pattern Efficiency**
```sql
"data_access_pattern_efficiency_chart": {
    "query": """
        SELECT
            USER_NAME,
            COUNT(DISTINCT DATABASE_NAME) AS DATABASE_SPREAD,
            COUNT(DISTINCT SCHEMA_NAME) AS SCHEMA_SPREAD,
            COUNT(DISTINCT TABLE_NAME) AS TABLE_SPREAD,
            COUNT(*) AS TOTAL_ACCESSES,
            ROUND(TOTAL_ACCESSES::FLOAT / COUNT(DISTINCT DATABASE_NAME || '.' || SCHEMA_NAME || '.' || TABLE_NAME), 2) AS ACCESS_CONCENTRATION,
            COUNT(DISTINCT DATABASE_NAME || '.' || SCHEMA_NAME || '.' || TABLE_NAME) AS UNIQUE_OBJECTS
        FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
        WHERE
            QUERY_START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND QUERY_START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            AND USER_NAME = '{object_value}'
        GROUP BY USER_NAME
        HAVING TOTAL_ACCESSES > 10
        ORDER BY ACCESS_CONCENTRATION DESC
    """,
    "label": "Data Access Pattern Efficiency",
    "description": "Radar chart showing user's data access patterns. High spread with low concentration indicates unfocused data access.",
    "chart_type": "radar",
    "dimensions": ["DATABASE_SPREAD", "SCHEMA_SPREAD", "TABLE_SPREAD", "ACCESS_CONCENTRATION"],
    "hover_data": ["TOTAL_ACCESSES", "UNIQUE_OBJECTS"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: High spread with low concentration indicates unfocused data access

## 8. **Optimization Opportunity Scoring**
```sql
"optimization_opportunity_scoring_chart": {
    "query": """
        SELECT
            USER_NAME,
            -- Waste Score (0-100)
            LEAST(100, GREATEST(0, (SUM(CASE WHEN EXECUTION_STATUS IN ('FAILED', 'CANCELED') THEN TRY_TO_NUMBER(EXECUTION_TIME, 38, 0) ELSE 0 END) / (1000 * 60 * 60)) * 10)) AS WASTE_SCORE,
            -- Efficiency Score (0-100)
            LEAST(100, GREATEST(0, (AVG(TRY_TO_NUMBER(BYTES_SCANNED, 38, 0)) / POW(1024, 4)) * 20)) AS SCAN_INEFFICIENCY_SCORE,
            -- Memory Score (0-100)
            LEAST(100, GREATEST(0, (COUNT(CASE WHEN TRY_TO_NUMBER(BYTES_SPILLED_TO_REMOTE_STORAGE, 38, 0) > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)))) AS MEMORY_PRESSURE_SCORE,
            -- Peak Hour Score (0-100)
            LEAST(100, GREATEST(0, (COUNT(CASE WHEN HOUR(START_TIME) BETWEEN 9 AND 17 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)))) AS PEAK_HOUR_ABUSE_SCORE,
            -- Total Opportunity Score
            ROUND((WASTE_SCORE + SCAN_INEFFICIENCY_SCORE + MEMORY_PRESSURE_SCORE + PEAK_HOUR_ABUSE_SCORE) / 4, 2) AS TOTAL_OPTIMIZATION_SCORE,
            COUNT(*) AS TOTAL_QUERIES
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE
            START_TIME >= TRY_TO_TIMESTAMP_NTZ('{start_date}')
            AND START_TIME <= TRY_TO_TIMESTAMP_NTZ('{end_date} 23:59:59')
            {object_filter}
        GROUP BY USER_NAME
        HAVING COUNT(*) > 20
        ORDER BY TOTAL_OPTIMIZATION_SCORE DESC
    """,
    "label": "Optimization Opportunity Scoring",
    "description": "Stacked bar chart showing optimization potential by user. Score >60 indicates high optimization potential requiring immediate action.",
    "chart_type": "stacked_bar",
    "x_col": "USER_NAME",
    "y_col": ["WASTE_SCORE", "SCAN_INEFFICIENCY_SCORE", "MEMORY_PRESSURE_SCORE", "PEAK_HOUR_ABUSE_SCORE"],
    "hover_data": ["TOTAL_OPTIMIZATION_SCORE", "TOTAL_QUERIES"],
    "show_table_toggle": True,
    "apply_object_filter": True
}
```
**Bad User Pattern**: Score >60 indicates high optimization potential

---

## Key Optimization Actions by Pattern:

### 🔴 **High-Risk Users (Score >80)**
- Immediate query review and optimization
- Implement query governance and approval process
- Separate warehouse for heavy workloads
- Mandatory training on query optimization

### 🟡 **Medium-Risk Users (Score 40-80)**
- Schedule regular query performance reviews
- Implement query caching strategies
- Optimize most frequently accessed objects
- Set up monitoring alerts for resource usage

### 🟢 **Low-Risk Users (Score <40)**
- Maintain current practices
- Share best practices with high-risk users
- Consider as optimization mentors

These metrics and charts provide deep insights into user behavior patterns and specific, actionable optimization opportunities rather than just basic performance statistics.