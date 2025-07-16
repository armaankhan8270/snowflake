# Snowflake User 360 Dashboard - Advanced Charts

## Part 1: Aggregate User Analysis Charts (All Users)

### Chart 1: User Efficiency Matrix (Scatter Plot)
**Purpose**: Identifies users with poor cost-to-value ratio using robust efficiency scoring
**Chart Type**: Scatter Plot with Bubble Size
**X-Axis**: Cost Efficiency Score (0-100)
**Y-Axis**: Performance Efficiency Score (0-100)
**Bubble Size**: Total Cost Impact
**Color Coding**: User Risk Level (Red=High Risk, Yellow=Medium, Green=Optimized)

```sql
-- User Efficiency Matrix Query
WITH user_metrics AS (
    SELECT 
        qh.user_name,
        COUNT(DISTINCT qh.query_id) as total_queries,
        SUM(qh.total_elapsed_time) as total_execution_time,
        SUM(qh.bytes_scanned) as total_bytes_scanned,
        SUM(qh.rows_produced) as total_rows_produced,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as total_cost,
        AVG(qh.compilation_time) as avg_compilation_time,
        COUNT(CASE WHEN qh.error_code IS NOT NULL THEN 1 END) as error_count,
        COUNT(CASE WHEN qh.total_elapsed_time > 300000 THEN 1 END) as long_running_queries,
        COUNT(CASE WHEN qh.bytes_scanned > 0 AND qh.rows_produced = 0 THEN 1 END) as zero_result_scans
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
    GROUP BY qh.user_name
),
efficiency_scores AS (
    SELECT 
        user_name,
        total_cost,
        -- Cost Efficiency Score (0-100)
        GREATEST(0, LEAST(100, 
            100 - (
                (total_cost / NULLIF(total_queries, 0) * 20) +
                (zero_result_scans / NULLIF(total_queries, 0) * 100 * 30) +
                (error_count / NULLIF(total_queries, 0) * 100 * 25) +
                (long_running_queries / NULLIF(total_queries, 0) * 100 * 15) +
                (CASE WHEN total_bytes_scanned > 0 AND total_rows_produced = 0 THEN 10 ELSE 0 END)
            )
        )) as cost_efficiency_score,
        
        -- Performance Efficiency Score (0-100)
        GREATEST(0, LEAST(100,
            100 - (
                (avg_compilation_time / 10000 * 20) +
                (total_execution_time / NULLIF(total_queries, 0) / 10000 * 25) +
                (total_bytes_scanned / NULLIF(total_rows_produced, 0) / 1000000 * 15) +
                (error_count / NULLIF(total_queries, 0) * 100 * 25) +
                (long_running_queries / NULLIF(total_queries, 0) * 100 * 15)
            )
        )) as performance_efficiency_score,
        
        total_queries,
        CASE 
            WHEN total_cost > 100 AND cost_efficiency_score < 40 THEN 'HIGH_RISK'
            WHEN total_cost > 50 AND cost_efficiency_score < 60 THEN 'MEDIUM_RISK'
            ELSE 'OPTIMIZED'
        END as risk_level
    FROM user_metrics
)
SELECT 
    user_name,
    cost_efficiency_score,
    performance_efficiency_score,
    total_cost,
    risk_level
FROM efficiency_scores
ORDER BY cost_efficiency_score ASC, performance_efficiency_score ASC;
```

**Why This Logic is Robust**:
- Combines multiple factors: cost per query, zero-result scans, error rates, long-running queries
- Uses weighted scoring system rather than single thresholds
- Considers both absolute cost and efficiency ratio
- Identifies users who scan data but produce no results (waste)

---

### Chart 2: Query Pattern Inefficiency Heatmap
**Purpose**: Shows time-based patterns of inefficient query execution
**Chart Type**: Heatmap
**X-Axis**: Hour of Day (0-23)
**Y-Axis**: Day of Week
**Color Intensity**: Inefficiency Score
**Tooltip**: Query count, avg cost, failure rate

```sql
-- Query Pattern Inefficiency Heatmap
WITH hourly_patterns AS (
    SELECT 
        qh.user_name,
        EXTRACT(HOUR FROM qh.start_time) as hour_of_day,
        EXTRACT(DAYOFWEEK FROM qh.start_time) as day_of_week,
        COUNT(*) as query_count,
        AVG(qh.total_elapsed_time) as avg_execution_time,
        SUM(qh.bytes_scanned) as total_bytes_scanned,
        SUM(qh.rows_produced) as total_rows_produced,
        COUNT(CASE WHEN qh.error_code IS NOT NULL THEN 1 END) as error_count,
        AVG(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as avg_cost
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
    GROUP BY qh.user_name, hour_of_day, day_of_week
),
inefficiency_calc AS (
    SELECT 
        user_name,
        hour_of_day,
        day_of_week,
        query_count,
        avg_cost,
        error_count,
        -- Inefficiency Score: Higher = More Inefficient
        (
            (avg_execution_time / 10000 * 0.3) +
            (total_bytes_scanned / NULLIF(total_rows_produced, 0) / 1000000 * 0.4) +
            (error_count / NULLIF(query_count, 0) * 100 * 0.3)
        ) as inefficiency_score
    FROM hourly_patterns
)
SELECT 
    user_name,
    hour_of_day,
    CASE day_of_week
        WHEN 1 THEN 'Sunday'
        WHEN 2 THEN 'Monday'
        WHEN 3 THEN 'Tuesday'
        WHEN 4 THEN 'Wednesday'
        WHEN 5 THEN 'Thursday'
        WHEN 6 THEN 'Friday'
        WHEN 7 THEN 'Saturday'
    END as day_name,
    query_count,
    ROUND(avg_cost, 2) as avg_cost,
    error_count,
    ROUND(inefficiency_score, 2) as inefficiency_score
FROM inefficiency_calc
WHERE ('{user_filter}' = 'ALL' OR user_name = '{user_filter}')
ORDER BY inefficiency_score DESC;
```

**Why This Logic is Robust**:
- Identifies temporal patterns of inefficiency
- Combines execution time, scan-to-result ratio, and error rates
- Helps identify users running inefficient queries during peak hours
- Weighted scoring prevents single-metric bias

---

### Chart 3: Resource Waste Waterfall Chart
**Purpose**: Shows breakdown of wasted resources across user categories
**Chart Type**: Waterfall Chart
**Categories**: Failed Queries, Zero-Result Scans, Redundant Queries, Long-Running Simple Queries
**Values**: Cost Impact of Each Waste Category

```sql
-- Resource Waste Waterfall Analysis
WITH waste_categories AS (
    SELECT 
        'Failed Queries' as category,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as waste_cost,
        COUNT(*) as query_count,
        'Queries that failed but still consumed resources' as description
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.error_code IS NOT NULL
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
    
    UNION ALL
    
    SELECT 
        'Zero-Result Scans' as category,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as waste_cost,
        COUNT(*) as query_count,
        'Queries that scanned data but returned no results' as description
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.bytes_scanned > 0 
    AND qh.rows_produced = 0
    AND qh.error_code IS NULL
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
    
    UNION ALL
    
    SELECT 
        'Redundant Queries' as category,
        SUM(duplicate_cost) as waste_cost,
        SUM(duplicate_count) as query_count,
        'Identical queries executed multiple times' as description
    FROM (
        SELECT 
            qh.query_text_hash,
            COUNT(*) as duplicate_count,
            SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as duplicate_cost
        FROM snowflake.account_usage.query_history qh
        WHERE qh.start_time >= '{start_date}'
        AND qh.end_time <= '{end_date}'
        AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
        GROUP BY qh.query_text_hash
        HAVING COUNT(*) > 1
    ) duplicates
    
    UNION ALL
    
    SELECT 
        'Oversized Warehouses' as category,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as waste_cost,
        COUNT(*) as query_count,
        'Simple queries using large warehouses' as description
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.warehouse_size > 2  -- Assuming size codes: 1=XS, 2=S, 3=M, etc.
    AND qh.total_elapsed_time < 10000  -- Less than 10 seconds
    AND qh.bytes_scanned < 1000000  -- Less than 1MB
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
)
SELECT 
    category,
    ROUND(waste_cost, 2) as waste_cost,
    query_count,
    description,
    ROUND(waste_cost / SUM(waste_cost) OVER() * 100, 1) as percentage_of_total_waste
FROM waste_categories
ORDER BY waste_cost DESC;
```

**Why This Logic is Robust**:
- Identifies specific types of waste, not just high costs
- Quantifies actual financial impact of each waste category
- Distinguishes between legitimate high-cost queries and wasteful ones
- Provides actionable categories for optimization

---

### Chart 4: User Optimization Opportunity Ranking
**Purpose**: Ranks users by optimization potential (high impact, easy wins)
**Chart Type**: Horizontal Bar Chart with Dual Axis
**Primary Axis**: Optimization Score (0-100)
**Secondary Axis**: Potential Cost Savings
**Color Coding**: Difficulty Level (Green=Easy, Yellow=Medium, Red=Hard)

```sql
-- User Optimization Opportunity Ranking
WITH user_analysis AS (
    SELECT 
        qh.user_name,
        COUNT(*) as total_queries,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as total_cost,
        AVG(qh.total_elapsed_time) as avg_execution_time,
        COUNT(CASE WHEN qh.error_code IS NOT NULL THEN 1 END) as error_count,
        COUNT(CASE WHEN qh.bytes_scanned > 0 AND qh.rows_produced = 0 THEN 1 END) as zero_result_queries,
        COUNT(CASE WHEN qh.warehouse_size > 2 AND qh.total_elapsed_time < 10000 THEN 1 END) as oversized_warehouse_queries,
        COUNT(CASE WHEN qh.total_elapsed_time > 300000 THEN 1 END) as long_running_queries,
        COUNT(DISTINCT qh.query_text_hash) as unique_queries,
        SUM(qh.bytes_scanned) as total_bytes_scanned,
        SUM(qh.rows_produced) as total_rows_produced
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND ('{user_filter}' = 'ALL' OR qh.user_name = '{user_filter}')
    GROUP BY qh.user_name
),
optimization_scoring AS (
    SELECT 
        user_name,
        total_cost,
        -- Optimization Score (higher = more opportunity)
        (
            (error_count / NULLIF(total_queries, 0) * 100 * 25) +  -- Error rate impact
            (zero_result_queries / NULLIF(total_queries, 0) * 100 * 30) +  -- Zero result impact
            (oversized_warehouse_queries / NULLIF(total_queries, 0) * 100 * 20) +  -- Warehouse sizing
            ((total_queries - unique_queries) / NULLIF(total_queries, 0) * 100 * 15) +  -- Query duplication
            (CASE WHEN total_bytes_scanned > 0 AND total_rows_produced > 0 
                  THEN LEAST(10, total_bytes_scanned / total_rows_produced / 1000000) 
                  ELSE 0 END)  -- Scan efficiency
        ) as optimization_score,
        
        -- Potential savings calculation
        (
            (error_count * (total_cost / NULLIF(total_queries, 0))) +  -- Savings from fixing errors
            (zero_result_queries * (total_cost / NULLIF(total_queries, 0))) +  -- Savings from zero results
            (oversized_warehouse_queries * (total_cost / NULLIF(total_queries, 0)) * 0.7) +  -- Warehouse rightsizing
            ((total_queries - unique_queries) * (total_cost / NULLIF(total_queries, 0)) * 0.8)  -- Duplicate query savings
        ) as potential_savings,
        
        -- Difficulty assessment
        CASE 
            WHEN oversized_warehouse_queries > (total_queries * 0.3) THEN 'Easy'  -- Warehouse sizing is easy
            WHEN zero_result_queries > (total_queries * 0.2) THEN 'Medium'  -- Query optimization
            ELSE 'Hard'  -- Complex performance tuning
        END as difficulty_level,
        
        total_queries,
        error_count,
        zero_result_queries,
        oversized_warehouse_queries
    FROM user_analysis
)
SELECT 
    user_name,
    ROUND(optimization_score, 1) as optimization_score,
    ROUND(potential_savings, 2) as potential_savings,
    difficulty_level,
    total_queries,
    error_count,
    zero_result_queries,
    oversized_warehouse_queries,
    ROUND(total_cost, 2) as current_total_cost,
    ROUND(potential_savings / NULLIF(total_cost, 0) * 100, 1) as savings_percentage
FROM optimization_scoring
WHERE total_cost > 10  -- Focus on users with meaningful cost
ORDER BY optimization_score DESC, potential_savings DESC;
```

**Why This Logic is Robust**:
- Considers multiple optimization vectors simultaneously
- Weighs opportunity against difficulty for practical prioritization
- Calculates actual financial impact, not just scores
- Focuses on actionable improvements with clear ROI

---

## Part 2: Single User Deep-Dive Charts

### Chart 5: Query Performance Distribution (Single User)
**Purpose**: Shows distribution of query performance for detailed user analysis
**Chart Type**: Violin Plot with Box Plot Overlay
**X-Axis**: Query Categories (Simple, Complex, Analytical, Failed)
**Y-Axis**: Execution Time (log scale)
**Width**: Query Count Distribution

```sql
-- Single User Query Performance Distribution
WITH query_categorization AS (
    SELECT 
        qh.query_id,
        qh.user_name,
        qh.total_elapsed_time,
        qh.bytes_scanned,
        qh.rows_produced,
        qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000) as query_cost,
        qh.error_code,
        qh.query_type,
        -- Categorize queries
        CASE 
            WHEN qh.error_code IS NOT NULL THEN 'Failed'
            WHEN qh.total_elapsed_time > 300000 THEN 'Long-Running'
            WHEN qh.bytes_scanned > 1000000000 THEN 'Complex'
            WHEN qh.query_type IN ('SELECT', 'SHOW', 'DESCRIBE') AND qh.total_elapsed_time < 10000 THEN 'Simple'
            ELSE 'Analytical'
        END as query_category,
        -- Performance metrics
        qh.compilation_time,
        qh.execution_time,
        qh.queued_provisioning_time,
        qh.queued_repair_time,
        qh.queued_overload_time
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.user_name = '{user_filter}'
),
performance_stats AS (
    SELECT 
        query_category,
        COUNT(*) as query_count,
        AVG(total_elapsed_time) as avg_execution_time,
        MEDIAN(total_elapsed_time) as median_execution_time,
        MIN(total_elapsed_time) as min_execution_time,
        MAX(total_elapsed_time) as max_execution_time,
        STDDEV(total_elapsed_time) as stddev_execution_time,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total_elapsed_time) as q1_execution_time,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_elapsed_time) as q3_execution_time,
        SUM(query_cost) as total_category_cost,
        AVG(query_cost) as avg_category_cost,
        AVG(compilation_time) as avg_compilation_time,
        AVG(execution_time) as avg_execution_time_only,
        AVG(queued_provisioning_time + queued_repair_time + queued_overload_time) as avg_queue_time
    FROM query_categorization
    GROUP BY query_category
)
SELECT 
    query_category,
    query_count,
    ROUND(avg_execution_time, 0) as avg_execution_time,
    ROUND(median_execution_time, 0) as median_execution_time,
    ROUND(min_execution_time, 0) as min_execution_time,
    ROUND(max_execution_time, 0) as max_execution_time,
    ROUND(stddev_execution_time, 0) as stddev_execution_time,
    ROUND(q1_execution_time, 0) as q1_execution_time,
    ROUND(q3_execution_time, 0) as q3_execution_time,
    ROUND(total_category_cost, 2) as total_category_cost,
    ROUND(avg_category_cost, 4) as avg_category_cost,
    ROUND(avg_compilation_time, 0) as avg_compilation_time,
    ROUND(avg_execution_time_only, 0) as avg_execution_time_only,
    ROUND(avg_queue_time, 0) as avg_queue_time
FROM performance_stats
ORDER BY query_count DESC;
```

**Why This Logic is Robust**:
- Categorizes queries by complexity, not just duration
- Provides statistical distribution analysis
- Separates compilation, execution, and queue times
- Identifies performance bottlenecks across different query types

---

### Chart 6: Cost Trend Analysis with Anomaly Detection (Single User)
**Purpose**: Shows user's cost trends over time with anomaly detection
**Chart Type**: Line Chart with Confidence Bands
**X-Axis**: Time (Daily)
**Y-Axis**: Daily Cost
**Lines**: Actual Cost, Trend Line, Anomaly Threshold
**Markers**: Anomaly Points

```sql
-- Single User Cost Trend with Anomaly Detection
WITH daily_costs AS (
    SELECT 
        DATE(qh.start_time) as query_date,
        qh.user_name,
        COUNT(*) as daily_query_count,
        SUM(qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) as daily_cost,
        AVG(qh.total_elapsed_time) as avg_daily_execution_time,
        COUNT(CASE WHEN qh.error_code IS NOT NULL THEN 1 END) as daily_errors,
        SUM(qh.bytes_scanned) as daily_bytes_scanned,
        SUM(qh.rows_produced) as daily_rows_produced
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.user_name = '{user_filter}'
    GROUP BY DATE(qh.start_time), qh.user_name
),
cost_statistics AS (
    SELECT 
        user_name,
        AVG(daily_cost) as avg_daily_cost,
        STDDEV(daily_cost) as stddev_daily_cost,
        MIN(daily_cost) as min_daily_cost,
        MAX(daily_cost) as max_daily_cost,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY daily_cost) as q1_daily_cost,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY daily_cost) as q3_daily_cost
    FROM daily_costs
    GROUP BY user_name
),
anomaly_detection AS (
    SELECT 
        dc.query_date,
        dc.user_name,
        dc.daily_cost,
        dc.daily_query_count,
        dc.avg_daily_execution_time,
        dc.daily_errors,
        dc.daily_bytes_scanned,
        dc.daily_rows_produced,
        cs.avg_daily_cost,
        cs.stddev_daily_cost,
        -- Anomaly detection using Z-score and IQR
        CASE 
            WHEN ABS(dc.daily_cost - cs.avg_daily_cost) > (2 * cs.stddev_daily_cost) THEN 'High_Anomaly'
            WHEN dc.daily_cost > (cs.q3_daily_cost + 1.5 * (cs.q3_daily_cost - cs.q1_daily_cost)) THEN 'Moderate_Anomaly'
            ELSE 'Normal'
        END as anomaly_level,
        -- Trend calculation (7-day moving average)
        AVG(dc.daily_cost) OVER (
            PARTITION BY dc.user_name 
            ORDER BY dc.query_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as seven_day_avg,
        -- Upper and lower bounds
        cs.avg_daily_cost + (2 * cs.stddev_daily_cost) as upper_bound,
        cs.avg_daily_cost - (2 * cs.stddev_daily_cost) as lower_bound
    FROM daily_costs dc
    JOIN cost_statistics cs ON dc.user_name = cs.user_name
)
SELECT 
    query_date,
    user_name,
    ROUND(daily_cost, 2) as daily_cost,
    daily_query_count,
    ROUND(avg_daily_execution_time, 0) as avg_daily_execution_time,
    daily_errors,
    daily_bytes_scanned,
    daily_rows_produced,
    anomaly_level,
    ROUND(seven_day_avg, 2) as seven_day_avg,
    ROUND(upper_bound, 2) as upper_bound,
    ROUND(lower_bound, 2) as lower_bound,
    ROUND(avg_daily_cost, 2) as baseline_avg_cost
FROM anomaly_detection
ORDER BY query_date;
```

**Why This Logic is Robust**:
- Uses statistical methods (Z-score, IQR) for anomaly detection
- Provides context with moving averages and confidence bands
- Correlates cost spikes with execution patterns and errors
- Identifies both statistical and business-logic anomalies

---

### Chart 7: Query Complexity vs Resource Utilization (Single User)
**Purpose**: Shows relationship between query complexity and resource efficiency
**Chart Type**: Scatter Plot with Regression Line
**X-Axis**: Query Complexity Score
**Y-Axis**: Resource Efficiency Score
**Bubble Size**: Query Cost
**Color**: Query Type

```sql
-- Single User Query Complexity vs Resource Utilization
WITH query_complexity AS (
    SELECT 
        qh.query_id,
        qh.user_name,
        qh.query_type,
        qh.total_elapsed_time,
        qh.bytes_scanned,
        qh.rows_produced,
        qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000) as query_cost,
        qh.compilation_time,
        qh.execution_time,
        qh.partitions_scanned,
        qh.partitions_total,
        -- Complexity Score Calculation
        (
            LOG(1 + qh.bytes_scanned / 1000000) * 20 +  -- Data volume factor
            LOG(1 + qh.compilation_time / 1000) * 15 +   -- Compilation complexity
            LOG(1 + qh.execution_time / 1000) * 10 +     -- Execution complexity
            (qh.partitions_scanned / NULLIF(qh.partitions_total, 0) * 100) * 0.1 +  -- Partition scanning
            CASE 
                WHEN qh.query_type IN ('INSERT', 'UPDATE', 'DELETE', 'MERGE') THEN 15
                WHEN qh.query_type IN ('CREATE', 'ALTER', 'DROP') THEN 10
                ELSE 5
            END  -- Query type complexity
        ) as complexity_score,
        
        -- Resource Efficiency Score
        (
            100 - (
                (qh.total_elapsed_time / 10000 * 20) +  -- Time efficiency
                (qh.bytes_scanned / NULLIF(qh.rows_produced, 0) / 1000000 * 30) +  -- Scan efficiency
                (qh.compilation_time / NULLIF(qh.execution_time, 0) * 100 * 25) +  -- Compilation overhead
                ((qh.credits_used_cloud_services + qh.warehouse_size * (qh.total_elapsed_time/3600000)) / 
                 NULLIF(qh.rows_produced, 0) * 1000000 * 25)  -- Cost per row
            )
        ) as resource_efficiency_score
    FROM snowflake.account_usage.query_history qh
    WHERE qh.start_time >= '{start_date}'
    AND qh.end_time <= '{end_date}'
    AND qh.user_name = '{user_filter}'
    AND qh.error_code IS NULL
),
efficiency_analysis AS (
    SELECT 
        query_id,
        user_name,
        query_type,
        ROUND(complexity_score, 1) as complexity_score,
        ROUND(GREATEST(0, LEAST(100, resource_efficiency_score)), 1) as resource_efficiency_score,
        ROUND(query_cost, 4) as query_cost,
        total_elapsed_time,
        bytes_scanned,
        rows_produced,
        compilation_time,
        execution_time,
        -- Efficiency Category
        CASE 
            WHEN complexity_score > 80 AND resource_efficiency_score > 70 THEN 'High_Complexity_Efficient'
            WHEN complexity_score > 80 AND resource_efficiency_score <= 70 THEN 'High_Complexity_Inefficient'
            WHEN complexity_score <= 80 AND resource_efficiency_score > 70 THEN 'Low_Complexity_Efficient'
            ELSE 'Low_Complexity_Inefficient'
        END as efficiency_category
    FROM query_complexity
)
SELECT 
    query_id,
    user_name,
    query_type,
    complexity_score,
    resource_efficiency_score,
    query_cost,
    total_elapsed_time,
    bytes_scanned,
    rows_produced,
    compilation_time,
    execution_time,
    efficiency_category
FROM efficiency_analysis
ORDER BY complexity_score DESC, resource_efficiency_score ASC;
```

**Why This Logic is Robust**:
- Multi-dimensional complexity scoring beyond simple metrics
- Considers compilation overhead and partition scanning efficiency
- Correlates resource usage with actual business value (rows produced)
- Identifies queries that are complex but efficient vs simple but wasteful

---

### Chart 8: Query Execution Timeline with Bottleneck Analysis (Single User)
**Purpose**: Shows detailed execution timeline to identify bottlenecks
**Chart Type**: Gantt Chart / Timeline
**X-Axis**: Time
**Y-Axis**: Query ID
**Bars**: Execution Phases (Queue, Compile, Execute)
**Color**: Bottleneck Type

```sql
-- Single User Query Execution Timeline with Bottleneck Analysis
WITH execution_breakdown AS (
    SELECT 
        qh.query_id,
        qh.user_name,
        qh.start_time,
        qh.end_time,
        qh.total_elapsed_time,
        qh.compilation_time,
        qh