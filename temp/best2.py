# Snowflake User 360 Dashboard - Advanced Charts & Recommendation Tables

## 📊 TOP 8 ADVANCED CHARTS

### 🔍 **SECTION A: Aggregate User Analysis (4 Charts)**

---

#### **Chart 1: User Cost-Value Efficiency Matrix**
*Identifies high-cost low-value users and optimization opportunities*

```sql
WITH user_metrics AS (
    SELECT 
        user_name,
        SUM(total_elapsed_time/1000) as total_runtime_seconds,
        SUM(bytes_scanned) as total_bytes_scanned,
        SUM(bytes_written) as total_bytes_written,
        COUNT(*) as total_queries,
        SUM(credits_used) as total_credits,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        COUNT(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN 1 END) as failed_queries,
        AVG(bytes_scanned/NULLIF(bytes_written, 0)) as avg_scan_efficiency,
        SUM(CASE WHEN total_elapsed_time > 300000 THEN 1 ELSE 0 END) as long_running_queries
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name
),
user_efficiency AS (
    SELECT 
        user_name,
        total_credits,
        total_queries,
        (successful_queries::float / NULLIF(total_queries, 0)) * 100 as success_rate,
        (total_bytes_written::float / NULLIF(total_bytes_scanned, 0)) * 100 as data_efficiency,
        (total_credits::float / NULLIF(successful_queries, 0)) as cost_per_success,
        CASE 
            WHEN total_credits > 100 AND (successful_queries::float / NULLIF(total_queries, 0)) < 0.8 THEN 'High Cost - Low Value'
            WHEN total_credits > 100 AND (successful_queries::float / NULLIF(total_queries, 0)) >= 0.8 THEN 'High Cost - High Value'
            WHEN total_credits <= 100 AND (successful_queries::float / NULLIF(total_queries, 0)) >= 0.8 THEN 'Low Cost - High Value'
            ELSE 'Low Cost - Low Value'
        END as user_segment
    FROM user_metrics
)
SELECT 
    user_name,
    total_credits as x_axis_credits,
    success_rate as y_axis_success_rate,
    data_efficiency as bubble_size,
    cost_per_success,
    user_segment as color_category
FROM user_efficiency
ORDER BY total_credits DESC;
```

---

#### **Chart 2: Query Pattern Anomaly Detection**
*Reveals users with suspicious or inefficient query patterns*

```sql
WITH query_patterns AS (
    SELECT 
        user_name,
        DATE_TRUNC('hour', start_time) as hour_bucket,
        COUNT(*) as queries_per_hour,
        AVG(total_elapsed_time/1000) as avg_runtime_seconds,
        SUM(bytes_scanned) as bytes_scanned_per_hour,
        SUM(credits_used) as credits_per_hour,
        COUNT(CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN 1 END) as select_star_queries,
        COUNT(CASE WHEN query_text ILIKE '%LIMIT%' THEN 1 END) as limited_queries
    FROM query_history
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name, hour_bucket
),
user_anomalies AS (
    SELECT 
        user_name,
        AVG(queries_per_hour) as avg_queries_per_hour,
        STDDEV(queries_per_hour) as query_variance,
        MAX(queries_per_hour) as peak_queries_per_hour,
        AVG(credits_per_hour) as avg_credits_per_hour,
        SUM(select_star_queries) as total_select_star,
        SUM(limited_queries) as total_limited,
        COUNT(*) as active_hours,
        -- Anomaly scores
        (MAX(queries_per_hour) - AVG(queries_per_hour)) / NULLIF(STDDEV(queries_per_hour), 0) as query_spike_score,
        (SUM(select_star_queries)::float / NULLIF(SUM(queries_per_hour), 0)) * 100 as select_star_percentage,
        CASE 
            WHEN (MAX(queries_per_hour) - AVG(queries_per_hour)) / NULLIF(STDDEV(queries_per_hour), 0) > 3 THEN 'High Spike Risk'
            WHEN (SUM(select_star_queries)::float / NULLIF(SUM(queries_per_hour), 0)) * 100 > 30 THEN 'Poor Query Practices'
            WHEN AVG(queries_per_hour) > 50 THEN 'High Frequency User'
            ELSE 'Normal Pattern'
        END as anomaly_type
    FROM query_patterns
    GROUP BY user_name
)
SELECT 
    user_name,
    avg_queries_per_hour as x_axis,
    query_spike_score as y_axis,
    select_star_percentage as bubble_size,
    avg_credits_per_hour as tooltip_credits,
    anomaly_type as color_category
FROM user_anomalies
WHERE query_spike_score IS NOT NULL
ORDER BY query_spike_score DESC;
```

---

#### **Chart 3: Resource Waste Heat Map**
*Shows users wasting resources through inefficient scanning and failed queries*

```sql
WITH resource_waste AS (
    SELECT 
        user_name,
        warehouse_name,
        SUM(bytes_scanned) as total_scanned,
        SUM(bytes_written) as total_written,
        SUM(credits_used) as total_credits,
        COUNT(*) as total_queries,
        COUNT(CASE WHEN execution_status = 'FAILED' THEN 1 END) as failed_queries,
        COUNT(CASE WHEN execution_status = 'ABORTED' THEN 1 END) as aborted_queries,
        -- Waste metrics
        SUM(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN credits_used ELSE 0 END) as wasted_credits,
        SUM(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN bytes_scanned ELSE 0 END) as unproductive_scans,
        AVG(bytes_scanned::float / NULLIF(bytes_written, 0)) as avg_scan_ratio
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name, warehouse_name
),
waste_analysis AS (
    SELECT 
        user_name,
        warehouse_name,
        total_credits,
        wasted_credits,
        (wasted_credits::float / NULLIF(total_credits, 0)) * 100 as waste_percentage,
        (unproductive_scans::float / NULLIF(total_scanned, 0)) * 100 as unproductive_scan_percentage,
        (failed_queries + aborted_queries)::float / NULLIF(total_queries, 0) * 100 as failure_rate,
        -- Waste severity score
        ((wasted_credits::float / NULLIF(total_credits, 0)) * 0.4 + 
         (unproductive_scans::float / NULLIF(total_scanned, 0)) * 0.3 + 
         ((failed_queries + aborted_queries)::float / NULLIF(total_queries, 0)) * 0.3) * 100 as waste_severity_score
    FROM resource_waste
)
SELECT 
    user_name,
    warehouse_name,
    waste_percentage,
    unproductive_scan_percentage,
    failure_rate,
    waste_severity_score,
    total_credits as bubble_size,
    CASE 
        WHEN waste_severity_score > 30 THEN 'Critical Waste'
        WHEN waste_severity_score > 15 THEN 'High Waste'
        WHEN waste_severity_score > 5 THEN 'Medium Waste'
        ELSE 'Low Waste'
    END as waste_category
FROM waste_analysis
ORDER BY waste_severity_score DESC;
```

---

#### **Chart 4: User Performance Trajectory**
*Tracks user performance trends over time to identify degrading efficiency*

```sql
WITH daily_performance AS (
    SELECT 
        user_name,
        DATE_TRUNC('day', start_time) as query_date,
        COUNT(*) as daily_queries,
        SUM(credits_used) as daily_credits,
        AVG(total_elapsed_time/1000) as avg_runtime,
        SUM(bytes_scanned) as daily_bytes_scanned,
        SUM(bytes_written) as daily_bytes_written,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        -- Daily efficiency metrics
        (COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END)::float / NULLIF(COUNT(*), 0)) * 100 as daily_success_rate,
        (SUM(bytes_written)::float / NULLIF(SUM(bytes_scanned), 0)) * 100 as daily_data_efficiency,
        (SUM(credits_used)::float / NULLIF(COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END), 0)) as daily_cost_per_success
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name, query_date
),
performance_trends AS (
    SELECT 
        user_name,
        query_date,
        daily_success_rate,
        daily_data_efficiency,
        daily_cost_per_success,
        daily_credits,
        -- 7-day rolling averages
        AVG(daily_success_rate) OVER (PARTITION BY user_name ORDER BY query_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_success_rate,
        AVG(daily_data_efficiency) OVER (PARTITION BY user_name ORDER BY query_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_data_efficiency,
        AVG(daily_cost_per_success) OVER (PARTITION BY user_name ORDER BY query_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_cost_efficiency,
        -- Trend indicators
        (daily_success_rate - LAG(daily_success_rate, 7) OVER (PARTITION BY user_name ORDER BY query_date)) as success_rate_trend,
        (daily_cost_per_success - LAG(daily_cost_per_success, 7) OVER (PARTITION BY user_name ORDER BY query_date)) as cost_trend
    FROM daily_performance
)
SELECT 
    user_name,
    query_date,
    rolling_success_rate,
    rolling_data_efficiency,
    rolling_cost_efficiency,
    daily_credits as line_thickness,
    CASE 
        WHEN success_rate_trend < -10 AND cost_trend > 0 THEN 'Degrading Performance'
        WHEN success_rate_trend > 10 AND cost_trend < 0 THEN 'Improving Performance'
        WHEN success_rate_trend > -5 AND success_rate_trend < 5 THEN 'Stable Performance'
        ELSE 'Volatile Performance'
    END as performance_trend_category
FROM performance_trends
WHERE query_date >= CURRENT_DATE - 30
ORDER BY user_name, query_date;
```

---

### 🔍 **SECTION B: Single User Deep Dive (4 Charts)**

---

#### **Chart 5: Individual User Query Execution Timeline**
*Deep dive into a specific user's query patterns and bottlenecks*

```sql
WITH user_timeline AS (
    SELECT 
        query_id,
        user_name,
        start_time,
        end_time,
        total_elapsed_time/1000 as runtime_seconds,
        queued_provisioning_time/1000 as queue_time_seconds,
        bytes_scanned,
        bytes_written,
        credits_used,
        warehouse_name,
        execution_status,
        query_type,
        -- Categorize query performance
        CASE 
            WHEN total_elapsed_time > 300000 THEN 'Long Running (>5min)'
            WHEN total_elapsed_time > 60000 THEN 'Medium Runtime (1-5min)'
            WHEN total_elapsed_time > 10000 THEN 'Quick Runtime (10s-1min)'
            ELSE 'Very Quick (<10s)'
        END as runtime_category,
        -- Efficiency metrics
        bytes_scanned::float / NULLIF(bytes_written, 0) as scan_efficiency_ratio,
        credits_used::float / NULLIF(total_elapsed_time/1000, 0) as credits_per_second
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
),
query_analysis AS (
    SELECT 
        *,
        -- Identify problematic queries
        CASE 
            WHEN execution_status IN ('FAILED', 'ABORTED') THEN 'Failed Query'
            WHEN scan_efficiency_ratio > 1000 THEN 'High Scan Waste'
            WHEN runtime_seconds > 300 AND bytes_written = 0 THEN 'Long Running No Output'
            WHEN credits_per_second > 1 THEN 'High Cost Query'
            ELSE 'Normal Query'
        END as query_issue_type,
        ROW_NUMBER() OVER (ORDER BY start_time) as query_sequence
    FROM user_timeline
)
SELECT 
    query_sequence,
    start_time,
    runtime_seconds as y_axis_runtime,
    credits_used as bubble_size,
    scan_efficiency_ratio as tooltip_efficiency,
    warehouse_name,
    query_issue_type as color_category,
    execution_status,
    query_type
FROM query_analysis
ORDER BY start_time;
```

---

#### **Chart 6: User Warehouse Resource Distribution**
*Shows how a user distributes workload across warehouses and identifies optimization opportunities*

```sql
WITH warehouse_usage AS (
    SELECT 
        user_name,
        warehouse_name,
        warehouse_size,
        COUNT(*) as query_count,
        SUM(credits_used) as total_credits,
        SUM(total_elapsed_time/1000) as total_runtime,
        AVG(total_elapsed_time/1000) as avg_runtime,
        SUM(bytes_scanned) as total_bytes_scanned,
        SUM(bytes_written) as total_bytes_written,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        -- Warehouse efficiency metrics
        SUM(credits_used)::float / NULLIF(COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END), 0) as cost_per_success,
        AVG(queued_provisioning_time/1000) as avg_queue_time,
        SUM(bytes_written)::float / NULLIF(SUM(bytes_scanned), 0) * 100 as data_efficiency_pct
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
    GROUP BY user_name, warehouse_name, warehouse_size
),
warehouse_analysis AS (
    SELECT 
        warehouse_name,
        warehouse_size,
        query_count,
        total_credits,
        cost_per_success,
        avg_queue_time,
        data_efficiency_pct,
        -- Calculate warehouse utilization score
        (query_count::float / SUM(query_count) OVER ()) * 100 as usage_distribution_pct,
        -- Identify optimization opportunities
        CASE 
            WHEN warehouse_size = 'LARGE' AND avg_queue_time < 1 AND query_count < 10 THEN 'Oversized Warehouse'
            WHEN warehouse_size = 'XSMALL' AND avg_queue_time > 30 THEN 'Undersized Warehouse'
            WHEN cost_per_success > 5 THEN 'High Cost Warehouse'
            WHEN data_efficiency_pct < 10 THEN 'Low Efficiency Warehouse'
            ELSE 'Optimal Usage'
        END as optimization_recommendation
    FROM warehouse_usage
)
SELECT 
    warehouse_name,
    warehouse_size,
    usage_distribution_pct as x_axis,
    cost_per_success as y_axis,
    total_credits as bubble_size,
    avg_queue_time as tooltip_queue_time,
    data_efficiency_pct as tooltip_efficiency,
    optimization_recommendation as color_category
FROM warehouse_analysis
ORDER BY usage_distribution_pct DESC;
```

---

#### **Chart 7: User Query Complexity vs Performance**
*Analyzes relationship between query complexity and performance for optimization*

```sql
WITH query_complexity AS (
    SELECT 
        query_id,
        user_name,
        query_text,
        total_elapsed_time/1000 as runtime_seconds,
        credits_used,
        bytes_scanned,
        bytes_written,
        partitions_scanned,
        partitions_total,
        -- Complexity indicators
        LENGTH(query_text) as query_length,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'JOIN', ''))) / 4 as join_count,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'SELECT', ''))) / 6 as select_count,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'WHERE', ''))) / 5 as where_count,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'GROUP BY', ''))) / 8 as groupby_count,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'ORDER BY', ''))) / 8 as orderby_count,
        CASE WHEN query_text ILIKE '%WINDOW%' OR query_text ILIKE '%OVER(%' THEN 1 ELSE 0 END as has_window_functions,
        CASE WHEN query_text ILIKE '%CTE%' OR query_text ILIKE '%WITH%' THEN 1 ELSE 0 END as has_cte
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
    AND query_text IS NOT NULL
),
complexity_analysis AS (
    SELECT 
        query_id,
        runtime_seconds,
        credits_used,
        bytes_scanned,
        bytes_written,
        -- Complexity score calculation
        (join_count * 2 + select_count * 1 + where_count * 1 + 
         groupby_count * 3 + orderby_count * 2 + has_window_functions * 5 + has_cte * 3) as complexity_score,
        -- Performance efficiency
        credits_used::float / NULLIF(runtime_seconds, 0) as credits_per_second,
        bytes_scanned::float / NULLIF(bytes_written, 0) as scan_efficiency_ratio,
        -- Categorization
        CASE 
            WHEN join_count >= 5 THEN 'High Join Complexity'
            WHEN has_window_functions = 1 THEN 'Window Function Query'
            WHEN groupby_count >= 3 THEN 'Heavy Aggregation'
            WHEN has_cte = 1 THEN 'CTE Query'
            ELSE 'Simple Query'
        END as complexity_category,
        -- Performance category
        CASE 
            WHEN credits_per_second > 1 AND scan_efficiency_ratio > 100 THEN 'High Cost + Inefficient'
            WHEN credits_per_second > 1 THEN 'High Cost'
            WHEN scan_efficiency_ratio > 100 THEN 'Inefficient Scanning'
            ELSE 'Good Performance'
        END as performance_category
    FROM query_complexity
)
SELECT 
    query_id,
    complexity_score as x_axis,
    runtime_seconds as y_axis,
    credits_used as bubble_size,
    scan_efficiency_ratio as tooltip_scan_ratio,
    complexity_category,
    performance_category as color_category
FROM complexity_analysis
ORDER BY complexity_score DESC;
```

---

#### **Chart 8: User Cost Breakdown & Optimization Potential**
*Shows detailed cost breakdown and quantifies optimization opportunities*

```sql
WITH cost_breakdown AS (
    SELECT 
        user_name,
        warehouse_name,
        query_type,
        DATE_TRUNC('day', start_time) as query_date,
        SUM(credits_used) as daily_credits,
        COUNT(*) as daily_queries,
        SUM(total_elapsed_time/1000) as daily_runtime,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        COUNT(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN 1 END) as failed_queries,
        SUM(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN credits_used ELSE 0 END) as wasted_credits,
        SUM(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN credits_used ELSE 0 END) as unproductive_credits,
        SUM(CASE WHEN total_elapsed_time > 300000 THEN credits_used ELSE 0 END) as long_query_credits
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
    GROUP BY user_name, warehouse_name, query_type, query_date
),
optimization_potential AS (
    SELECT 
        warehouse_name,
        query_type,
        SUM(daily_credits) as total_credits,
        SUM(wasted_credits) as total_wasted_credits,
        SUM(unproductive_credits) as total_unproductive_credits,
        SUM(long_query_credits) as total_long_query_credits,
        -- Calculate optimization potential
        (SUM(wasted_credits) + SUM(unproductive_credits) + SUM(long_query_credits) * 0.3) as optimization_potential_credits,
        SUM(daily_queries) as total_queries,
        SUM(successful_queries) as total_successful,
        -- Performance metrics
        (SUM(wasted_credits)::float / NULLIF(SUM(daily_credits), 0)) * 100 as waste_percentage,
        (SUM(successful_queries)::float / NULLIF(SUM(daily_queries), 0)) * 100 as success_rate,
        AVG(daily_runtime::float / NULLIF(daily_queries, 0)) as avg_query_runtime
    FROM cost_breakdown
    GROUP BY warehouse_name, query_type
)
SELECT 
    warehouse_name,
    query_type,
    total_credits as current_cost,
    optimization_potential_credits as potential_savings,
    (optimization_potential_credits::float / NULLIF(total_credits, 0)) * 100 as savings_percentage,
    waste_percentage,
    success_rate,
    avg_query_runtime,
    -- Optimization priority
    CASE 
        WHEN (optimization_potential_credits::float / NULLIF(total_credits, 0)) * 100 > 30 THEN 'High Priority'
        WHEN (optimization_potential_credits::float / NULLIF(total_credits, 0)) * 100 > 15 THEN 'Medium Priority'
        WHEN (optimization_potential_credits::float / NULLIF(total_credits, 0)) * 100 > 5 THEN 'Low Priority'
        ELSE 'Optimized'
    END as optimization_priority,
    total_queries as bar_thickness
FROM optimization_potential
ORDER BY savings_percentage DESC;
```

---

## 📋 RECOMMENDATION TABLES

### **Table 1: Unoptimized Users Priority Matrix**
*Comprehensive scoring system to identify and prioritize users needing optimization*

```sql
WITH user_comprehensive_metrics AS (
    SELECT 
        user_name,
        COUNT(*) as total_queries,
        SUM(credits_used) as total_credits,
        SUM(total_elapsed_time/1000) as total_runtime_seconds,
        SUM(bytes_scanned) as total_bytes_scanned,
        SUM(bytes_written) as total_bytes_written,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        COUNT(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN 1 END) as failed_queries,
        COUNT(CASE WHEN total_elapsed_time > 300000 THEN 1 END) as long_running_queries,
        COUNT(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN 1 END) as unproductive_queries,
        SUM(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN credits_used ELSE 0 END) as wasted_credits,
        COUNT(CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN 1 END) as select_star_queries,
        COUNT(DISTINCT warehouse_name) as warehouses_used,
        AVG(bytes_scanned::float / NULLIF(bytes_written, 0)) as avg_scan_efficiency
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name
),
user_scoring AS (
    SELECT 
        user_name,
        total_credits,
        total_queries,
        -- Cost Impact Score (0-100)
        LEAST(100, (total_credits / 1000) * 10) as cost_impact_score,
        -- Efficiency Score (0-100, lower is worse)
        GREATEST(0, 100 - (
            (failed_queries::float / NULLIF(total_queries, 0)) * 40 +
            (unproductive_queries::float / NULLIF(total_queries, 0)) * 30 +
            (long_running_queries::float / NULLIF(total_queries, 0)) * 20 +
            (select_star_queries::float / NULLIF(total_queries, 0)) * 10
        )) as efficiency_score,
        -- Resource Waste Score (0-100)
        LEAST(100, (
            (wasted_credits::float / NULLIF(total_credits, 0)) * 50 +
            (CASE WHEN avg_scan_efficiency > 100 THEN 30 ELSE 0 END) +
            (CASE WHEN warehouses_used > 5 THEN 20 ELSE 0 END)
        )) as waste_score,
        -- Success Rate
        (successful_queries::float / NULLIF(total_queries, 0)) * 100 as success_rate,
        -- Calculate optimization potential
        (wasted_credits + (total_credits * 0.2)) as optimization_potential_credits,
        -- Issue identification
        CASE 
            WHEN failed_queries::float / NULLIF(total_queries, 0) > 0.2 THEN 'High Failure Rate'
            WHEN select_star_queries::float / NULLIF(total_queries, 0) > 0.3 THEN 'Poor Query Practices'
            WHEN long_running_queries::float / NULLIF(total_queries, 0) > 0.1 THEN 'Performance Issues'
            WHEN avg_scan_efficiency > 500 THEN 'Data Scanning Issues'
            WHEN warehouses_used > 8 THEN 'Warehouse Sprawl'
            ELSE 'Multiple Issues'
        END as primary_issue
    FROM user_comprehensive_metrics
),
final_scoring AS (
    SELECT 
        user_name,
        total_credits,
        total_queries,
        cost_impact_score,
        efficiency_score,
        waste_score,
        success_rate,
        optimization_potential_credits,
        primary_issue,
        -- Overall Priority Score (weighted combination)
        (cost_impact_score * 0.4 + (100 - efficiency_score) * 0.35 + waste_score * 0.25) as priority_score,
        -- Priority Level
        CASE 
            WHEN (cost_impact_score * 0.4 + (100 - efficiency_score) * 0.35 + waste_score * 0.25) > 70 THEN 'CRITICAL'
            WHEN (cost_impact_score * 0.4 + (100 - efficiency_score) * 0.35 + waste_score * 0.25) > 50 THEN 'HIGH'
            WHEN (cost_impact_score * 0.4 + (100 - efficiency_score) * 0.35 + waste_score * 0.25) > 30 THEN 'MEDIUM'
            ELSE 'LOW'
        END as priority_level,
        -- Specific Recommendations
        CASE 
            WHEN efficiency_score < 40 THEN 'Immediate query optimization training required'
            WHEN waste_score > 60 THEN 'Implement query review process and resource monitoring'
            WHEN cost_impact_score > 80 THEN 'Cost governance and approval workflow needed'
            WHEN success_rate < 60 THEN 'Debug failed queries and improve development practices'
            ELSE 'Standard optimization techniques applicable'
        END as recommended_action
    FROM user_scoring
)
SELECT 
    user_name,
    priority_level,
    ROUND(priority_score, 2) as priority_score,
    ROUND(total_credits, 2) as total_cost_credits,
    ROUND(optimization_potential_credits, 2) as potential_savings_credits,
    ROUND(success_rate, 1) as success_rate_pct,
    primary_issue,
    recommended_action
FROM final_scoring
WHERE priority_score > 20  -- Filter out very low priority users
ORDER BY priority_score DESC;
```

### **Table 2: Single User Deep Profile**
*Comprehensive analysis of individual user behavior and patterns*

```sql
WITH user_detailed_analysis AS (
    SELECT 
        user_name,
        -- Basic metrics
        COUNT(*) as total_queries,
        SUM(credits_used) as total_credits,
        AVG(credits_used) as avg_credits_per_query,
        SUM(total_elapsed_time/1000) as total_runtime_seconds,
        AVG(total_elapsed_time/1000) as avg_runtime_seconds,
        -- Success metrics
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        COUNT(CASE WHEN execution_status = 'FAILED' THEN 1 END) as failed_queries,
        COUNT(CASE WHEN execution_status = 'ABORTED' THEN 1 END) as aborted_queries,
        -- Data processing metrics
        SUM(bytes_scanned) as total_bytes_scanned,
        SUM(bytes_written) as total_bytes_written,
        AVG(bytes_scanned::float / NULLIF(bytes_written, 0)) as avg_scan_efficiency,
        -- Query pattern analysis
        COUNT(CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN 1 END) as select_star_count,
        COUNT(CASE WHEN query_text ILIKE '%LIMIT%' THEN 1 END) as limited_queries,
        COUNT(CASE WHEN total_elapsed_time > 300000 THEN 1 END) as long_running_queries,
        COUNT(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN 1 END) as unproductive_queries,
        -- Resource usage
        COUNT(DISTINCT warehouse_name) as warehouses_used,
        COUNT(DISTINCT DATE_TRUNC('day', start_time)) as active_days,
        -- Cost analysis
        SUM(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN credits_used ELSE 0 END) as wasted_credits,
        MAX(credits_used) as max_single_query_cost,
        MIN(start_time) as first_query_date,
        MAX(start_time) as last_query_date
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
    GROUP BY user_name
),
user_behavior_patterns AS (
    SELECT 
        user_name,
        -- Time-based patterns
        COUNT(CASE WHEN EXTRACT(HOUR FROM start_time) BETWEEN 9 AND 17 THEN 1 END) as business_hours_queries,
        COUNT(CASE WHEN EXTRACT(HOUR FROM start_time) NOT BETWEEN 9 AND 17 THEN 1 END) as after_hours_queries,
        COUNT(CASE WHEN EXTRACT(DOW FROM start_time) IN (0, 6) THEN 1 END) as weekend_queries,
        -- Query type distribution
        COUNT(CASE WHEN query_type = 'SELECT' THEN 1 END) as select_queries,
        COUNT(CASE WHEN query_type = 'INSERT' THEN 1 END) as insert_queries,
        COUNT(CASE WHEN query_type = 'UPDATE' THEN 1 END) as update_queries,
        COUNT(CASE WHEN query_type = 'DELETE' THEN 1 END) as delete_queries,
        COUNT(CASE WHEN query_type = 'CREATE' THEN 1 END) as create_queries,
        -- Most used warehouse
        MODE() WITHIN GROUP (ORDER BY warehouse_name) as primary_warehouse,
        -- Average session length estimation
        AVG(total_elapsed_time/1000) as avg_session_duration
    FROM query_history 
    WHERE user_name = :selected_user 
    AND start_time >= :start_date 
    AND start_time <= :end_date
    GROUP BY user_name
),
user_profile_final AS (
    SELECT 
        d.user_name,
        d.total_queries,
        d.total_credits,
        d.avg_credits_per_query,
        d.total_runtime_seconds,
        d.avg_runtime_seconds,
        (d.successful_queries::float / NULLIF(d.total_queries, 0)) * 100 as success_rate,
        (d.failed_queries::float / NULLIF(d.total_queries, 0)) * 100 as failure_rate,
        d.avg_scan_efficiency,
        d.warehouses_used,
        d.active_days,
        d.wasted_credits,
        d.max_single_query_cost,
        -- Behavior classification
        CASE 
            WHEN d.total_queries > 1000 THEN 'Heavy User'
            WHEN d.total_queries > 100 THEN 'Regular User'
            WHEN d.total_queries > 10 THEN 'Light User'
            ELSE 'Occasional User'
        END as user_type,
        -- Performance classification
        CASE 
            WHEN (d.successful_queries::float / NULLIF(d.total_queries, 0)) > 0.9 AND d.avg_scan_efficiency < 10 THEN 'Excellent'
            WHEN (d.successful_queries::float / NULLIF(d.total_queries, 0)) > 0.8 AND d.avg_scan_efficiency < 50 THEN 'Good'
            WHEN (d.successful_queries::float / NULLIF(d.total_queries, 0)) > 0.6 THEN 'Average'
            ELSE 'Poor'
        END as performance_rating,
        -- Cost efficiency
        CASE 
            WHEN d.avg_credits_per_query < 0.1 THEN 'Very Efficient'
            WHEN d.avg_credits_per_query < 0.5 THEN 'Efficient'
            WHEN d.avg_credits_per_query < 2 THEN 'Moderate'
            ELSE 'Expensive'
        END as cost_efficiency,
        -- Working pattern
        CASE 
            WHEN b.business_hours_queries::float / NULLIF(d.total_queries, 0) > 0.8 THEN 'Business Hours'
            WHEN b.after_hours_queries::float / NULLIF(d.total_queries, 0) > 0.5 THEN 'Extended Hours'
            WHEN b.weekend_queries::float / NULLIF(d.total_queries, 0) > 0.3 THEN 'Weekend Worker'
            ELSE 'Mixed Schedule'
        END as work_pattern,
        -- Primary activity
        CASE 
            WHEN b.select_queries::float / NULLIF(d.total_queries, 0) > 0.8 THEN 'Data Analysis'
            WHEN b.insert_queries::float / NULLIF(d.total_queries, 0) > 0.3 THEN 'Data Loading'
            WHEN b.create_queries::float / NULLIF(d.total_queries, 0) > 0.2 THEN 'Development'
            ELSE 'Mixed Operations'
        END as primary_activity,
        b.primary_warehouse,
        -- Optimization recommendations
        CASE 
            WHEN d.select_star_count::float / NULLIF(d.total_queries, 0) > 0.3 THEN 'Train on selective querying'
            WHEN d.long_running_queries::float / NULLIF(d.total_queries, 0) > 0.1 THEN 'Optimize query performance'
            WHEN d.warehouses_used > 5 THEN 'Standardize warehouse usage'
            WHEN d.wasted_credits > d.total_credits * 0.1 THEN 'Improve error handling'
            ELSE 'General best practices'
        END as optimization_focus
    FROM user_detailed_analysis d
    LEFT JOIN user_behavior_patterns b ON d.user_name = b.user_name
)
SELECT 
    user_name,
    user_type,
    performance_rating,
    cost_efficiency,
    work_pattern,
    primary_activity,
    ROUND(total_credits, 2) as total_cost_credits,
    total_queries,
    ROUND(success_rate, 1) as success_rate_pct,
    ROUND(avg_credits_per_query, 3) as avg_cost_per_query,
    warehouses_used,
    active_days,
    primary_warehouse,
    optimization_focus,
    ROUND(wasted_credits, 2) as wasted_credits,
    ROUND(max_single_query_cost, 2) as highest_single_query_cost
FROM user_profile_final;
```

### **Table 3: Query Inefficiency Detection**
*Identifies specific problematic queries and patterns for targeted optimization*

```sql
WITH query_inefficiency_analysis AS (
    SELECT 
        user_name,
        query_id,
        query_text,
        start_time,
        total_elapsed_time/1000 as runtime_seconds,
        credits_used,
        bytes_scanned,
        bytes_written,
        execution_status,
        warehouse_name,
        query_type,
        -- Inefficiency indicators
        bytes_scanned::float / NULLIF(bytes_written, 0) as scan_efficiency_ratio,
        credits_used::float / NULLIF(total_elapsed_time/1000, 0) as credits_per_second,
        partitions_scanned::float / NULLIF(partitions_total, 0) as partition_efficiency,
        -- Query complexity analysis
        LENGTH(query_text) as query_length,
        (LENGTH(query_text) - LENGTH(REPLACE(UPPER(query_text), 'JOIN', ''))) / 4 as join_count,
        CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN 1 ELSE 0 END as has_select_star,
        CASE WHEN query_text ILIKE '%ORDER BY%' AND query_text NOT ILIKE '%LIMIT%' THEN 1 ELSE 0 END as unlimited_order_by,
        CASE WHEN query_text ILIKE '%GROUP BY%' AND query_text NOT ILIKE '%HAVING%' THEN 1 ELSE 0 END as unfiltered_group_by,
        -- Performance categorization
        CASE 
            WHEN execution_status IN ('FAILED', 'ABORTED') THEN 'Failed Query'
            WHEN total_elapsed_time > 1800000 THEN 'Extremely Long Running'
            WHEN total_elapsed_time > 300000 THEN 'Long Running'
            WHEN bytes_scanned > 0 AND bytes_written = 0 THEN 'No Output Generated'
            WHEN bytes_scanned::float / NULLIF(bytes_written, 0) > 1000 THEN 'High Data Waste'
            WHEN credits_used::float / NULLIF(total_elapsed_time/1000, 0) > 1 THEN 'High Cost Rate'
            ELSE 'Normal Performance'
        END as inefficiency_type
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    AND (
        execution_status IN ('FAILED', 'ABORTED') OR
        total_elapsed_time > 300000 OR
        bytes_scanned::float / NULLIF(bytes_written, 0) > 100 OR
        credits_used > 10 OR
        (bytes_scanned > 0 AND bytes_written = 0)
    )
),
inefficiency_scoring AS (
    SELECT 
        user_name,
        query_id,
        LEFT(query_text, 100) as query_preview,
        start_time,
        runtime_seconds,
        credits_used,
        inefficiency_type,
        warehouse_name,
        scan_efficiency_ratio,
        credits_per_second,
        -- Calculate inefficiency score
        (
            CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN 25 ELSE 0 END +
            CASE WHEN runtime_seconds > 1800 THEN 20 WHEN runtime_seconds > 300 THEN 10 ELSE 0 END +
            CASE WHEN scan_efficiency_ratio > 1000 THEN 20 WHEN scan_efficiency_ratio > 100 THEN 10 ELSE 0 END +
            CASE WHEN credits_per_second > 2 THEN 15 WHEN credits_per_second > 1 THEN 10 ELSE 0 END +
            CASE WHEN has_select_star = 1 THEN 10 ELSE 0 END +
            CASE WHEN unlimited_order_by = 1 THEN 8 ELSE 0 END +
            CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN 15 ELSE 0 END
        ) as inefficiency_score,
        -- Optimization recommendations
        CASE 
            WHEN has_select_star = 1 THEN 'Replace SELECT * with specific columns'
            WHEN unlimited_order_by = 1 THEN 'Add LIMIT clause to ORDER BY queries'
            WHEN scan_efficiency_ratio > 1000 THEN 'Add WHERE clauses to filter data early'
            WHEN join_count > 5 THEN 'Consider breaking down complex joins'
            WHEN execution_status = 'FAILED' THEN 'Debug and fix query syntax/logic errors'
            WHEN runtime_seconds > 1800 THEN 'Optimize for performance - consider indexing/partitioning'
            ELSE 'General query optimization techniques'
        END as optimization_recommendation,
        -- Impact assessment
        CASE 
            WHEN credits_used > 50 THEN 'High Cost Impact'
            WHEN credits_used > 10 THEN 'Medium Cost Impact'
            WHEN execution_status IN ('FAILED', 'ABORTED') THEN 'Reliability Impact'
            ELSE 'Low Impact'
        END as impact_level
    FROM query_inefficiency_analysis
)
SELECT 
    user_name,
    query_id,
    query_preview,
    start_time,
    inefficiency_type,
    ROUND(inefficiency_score, 0) as inefficiency_score,
    ROUND(credits_used, 2) as cost_credits,
    ROUND(runtime_seconds, 0) as runtime_seconds,
    warehouse_name,
    optimization_recommendation,
    impact_level,
    ROUND(scan_efficiency_ratio, 1) as scan_waste_ratio
FROM inefficiency_scoring
WHERE inefficiency_score > 20  -- Focus on significant inefficiencies
ORDER BY inefficiency_score DESC, credits_used DESC;
```

### **Table 4: Actionable Optimization Roadmap**
*Prioritized action items with estimated impact and implementation difficulty*

```sql
WITH user_optimization_opportunities AS (
    SELECT 
        user_name,
        -- Current state metrics
        COUNT(*) as total_queries,
        SUM(credits_used) as total_credits,
        COUNT(CASE WHEN execution_status = 'SUCCESS' THEN 1 END) as successful_queries,
        COUNT(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN 1 END) as failed_queries,
        COUNT(CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN 1 END) as select_star_queries,
        COUNT(CASE WHEN total_elapsed_time > 300000 THEN 1 END) as long_running_queries,
        COUNT(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN 1 END) as unproductive_queries,
        SUM(CASE WHEN execution_status IN ('FAILED', 'ABORTED') THEN credits_used ELSE 0 END) as failed_query_costs,
        COUNT(DISTINCT warehouse_name) as warehouses_used,
        AVG(bytes_scanned::float / NULLIF(bytes_written, 0)) as avg_scan_efficiency,
        -- Identify specific opportunities
        SUM(CASE WHEN query_text ILIKE '%SELECT * FROM%' THEN credits_used ELSE 0 END) as select_star_costs,
        SUM(CASE WHEN total_elapsed_time > 300000 THEN credits_used ELSE 0 END) as long_query_costs,
        SUM(CASE WHEN bytes_scanned > 0 AND bytes_written = 0 THEN credits_used ELSE 0 END) as unproductive_costs
    FROM query_history 
    WHERE start_time >= :start_date AND start_time <= :end_date
    GROUP BY user_name
),
optimization_actions AS (
    SELECT 
        user_name,
        total_credits,
        -- Action 1: Fix Failed Queries
        CASE WHEN failed_queries > 0 THEN 'Fix Failed Queries' ELSE NULL END as action_1,
        CASE WHEN failed_queries > 0 THEN failed_query_costs ELSE 0 END as action_1_savings,
        CASE WHEN failed_queries > 0 THEN 'High' ELSE NULL END as action_1_priority,
        CASE WHEN failed_queries > 0 THEN 'Medium' ELSE NULL END as action_1_difficulty,
        CASE WHEN failed_queries > 0 THEN 'Debug and fix ' || failed_queries || ' failed queries' ELSE NULL END as action_1_description,
        
        -- Action 2: Optimize SELECT * Queries
        CASE WHEN select_star_queries > 0 THEN 'Replace SELECT * Queries' ELSE NULL END as action_2,
        CASE WHEN select_star_queries > 0 THEN select_star_costs * 0.4 ELSE 0 END as action_2_savings,
        CASE WHEN select_star_queries > total_queries * 0.3 THEN 'High' ELSE 'Medium' END as action_2_priority,
        'Low' as action_2_difficulty,
        CASE WHEN select_star_queries > 0 THEN 'Replace ' || select_star_queries || ' SELECT * queries with specific columns' ELSE NULL END as action_2_description,
        
        -- Action 3: Optimize Long Running Queries
        CASE WHEN long_running_queries > 0 THEN 'Optimize Long Running Queries' ELSE NULL END as action_3,
        CASE WHEN long_running_queries > 0 THEN long_query_costs * 0.3 ELSE 0 END as action_3_savings,
        CASE WHEN long_query_costs > total_credits * 0.2 THEN 'High' ELSE 'Medium' END as action_3_priority,
        'High' as action_3_difficulty,
        CASE WHEN long_running_queries > 0 THEN 'Optimize ' || long_running_queries || ' long running queries (>5 min)' ELSE NULL END as action_3_description,
        
        -- Action 4: Reduce Warehouse Sprawl
        CASE WHEN warehouses_used > 5 THEN 'Consolidate Warehouse Usage' ELSE NULL END as action_4,
        CASE WHEN warehouses_used > 5 THEN total_credits * 0.15 ELSE 0 END as action_4_savings,
        CASE WHEN warehouses_used > 8 THEN 'Medium' ELSE 'Low' END as action_4_priority,
        'Medium' as action_4_difficulty,
        CASE WHEN warehouses_used > 5 THEN 'Consolidate from ' || warehouses_used || ' warehouses to 2-3 primary ones' ELSE NULL END as action_4_description,
        
        -- Action 5: Eliminate Unproductive Queries
        CASE WHEN unproductive_queries > 0 THEN 'Fix Unproductive Queries' ELSE NULL END as action_5,
        CASE WHEN unproductive_queries > 0 THEN unproductive_costs ELSE 0 END as action_5_savings,
        CASE WHEN unproductive_costs > total_credits * 0.1 THEN 'High' ELSE 'Medium' END as action_5_priority,
        'Medium' as action_5_difficulty,
        CASE WHEN unproductive_queries > 0 THEN 'Fix ' || unproductive_queries || ' queries that scan data but produce no output' ELSE NULL END as action_5_description,
        
        -- Calculate total potential savings
        (
            CASE WHEN failed_queries > 0 THEN failed_query_costs ELSE 0 END +
            CASE WHEN select_star_queries > 0 THEN select_star_costs * 0.4 ELSE 0 END +
            CASE WHEN long_running_queries > 0 THEN long_query_costs * 0.3 ELSE 0 END +
            CASE WHEN warehouses_used > 5 THEN total_credits * 0.15 ELSE 0 END +
            CASE WHEN unproductive_queries > 0 THEN unproductive_costs ELSE 0 END
        ) as total_potential_savings,
        
        -- Implementation timeline
        CASE 
            WHEN failed_queries > total_queries * 0.2 THEN 'Immediate (1-2 weeks)'
            WHEN select_star_queries > total_queries * 0.5 THEN 'Short term (2-4 weeks)'
            WHEN long_running_queries > total_queries * 0.1 THEN 'Medium term (1-2 months)'
            ELSE 'Long term (2-3 months)'
        END as recommended_timeline
    FROM user_optimization_opportunities
)
-- Final output with actions unpivoted
SELECT 
    user_name,
    'Action 1' as action_sequence,
    action_1 as optimization_action,
    action_1_description as action_description,
    action_1_priority as priority_level,
    action_1_difficulty as implementation_difficulty,
    ROUND(action_1_savings, 2) as estimated_savings_credits,
    recommended_timeline,
    ROUND((action_1_savings::float / NULLIF(total_credits, 0)) * 100, 1) as savings_percentage
FROM optimization_actions
WHERE action_1 IS NOT NULL

UNION ALL

SELECT 
    user_name,
    'Action 2' as action_sequence,
    action_2 as optimization_action,
    action_2_description as action_description,
    action_2_priority as priority_level,
    action_2_difficulty as implementation_difficulty,
    ROUND(action_2_savings, 2) as estimated_savings_credits,
    recommended_timeline,
    ROUND((action_2_savings::float / NULLIF(total_credits, 0)) * 100, 1) as savings_percentage
FROM optimization_actions
WHERE action_2 IS NOT NULL

UNION ALL

SELECT 
    user_name,
    'Action 3' as action_sequence,
    action_3 as optimization_action,
    action_3_description as action_description,
    action_3_priority as priority_level,
    action_3_difficulty as implementation_difficulty,
    ROUND(action_3_savings, 2) as estimated_savings_credits,
    recommended_timeline,
    ROUND((action_3_savings::float / NULLIF(total_credits, 0)) * 100, 1) as savings_percentage
FROM optimization_actions
WHERE action_3 IS NOT NULL

UNION ALL

SELECT 
    user_name,
    'Action 4' as action_sequence,
    action_4 as optimization_action,
    action_4_description as action_description,
    action_4_priority as priority_level,
    action_4_difficulty as implementation_difficulty,
    ROUND(action_4_savings, 2) as estimated_savings_credits,
    recommended_timeline,
    ROUND((action_4_savings::float / NULLIF(total_credits, 0)) * 100, 1) as savings_percentage
FROM optimization_actions
WHERE action_4 IS NOT NULL

UNION ALL

SELECT 
    user_name,
    'Action 5' as action_sequence,
    action_5 as optimization_action,
    action_5_description as action_description,
    action_5_priority as priority_level,
    action_5_difficulty as implementation_difficulty,
    ROUND(action_5_savings, 2) as estimated_savings_credits,
    recommended_timeline,
    ROUND((action_5_savings::float / NULLIF(total_credits, 0)) * 100, 1) as savings_percentage
FROM optimization_actions
WHERE action_5 IS NOT NULL

ORDER BY 
    user_name,
    CASE 
        WHEN priority_level = 'High' THEN 1
        WHEN priority_level = 'Medium' THEN 2
        ELSE 3
    END,
    estimated_savings_credits DESC;
```

---

## 🎯 **DASHBOARD IMPLEMENTATION NOTES**

### **Chart Visualization Recommendations:**

1. **Chart 1**: Use scatter plot with bubble sizes for the cost-value efficiency matrix
2. **Chart 2**: Use scatter plot with color coding for anomaly detection
3. **Chart 3**: Use heat map visualization for resource waste analysis
4. **Chart 4**: Use multi-line time series chart for performance trajectories
5. **Chart 5**: Use timeline/Gantt chart for query execution patterns
6. **Chart 6**: Use pie chart or donut chart for warehouse distribution
7. **Chart 7**: Use scatter plot for complexity vs performance analysis
8. **Chart 8**: Use stacked bar chart for cost breakdown and optimization potential

### **Filter Parameters:**
- `:start_date` and `:end_date` for time range selection
- `:selected_user` for single user analysis
- Consider adding warehouse filter, query type filter, and minimum cost threshold filters

### **Key Performance Indicators (KPIs):**
- Total Cost Impact Score
- Optimization Potential (in credits and percentage)
- User Efficiency Score
- Success Rate Trends
- Resource Waste Percentage

### **Alert Thresholds:**
- Critical: Priority Score > 70
- High: Failed Query Rate > 20%
- Medium: Scan Efficiency Ratio > 500
- Low: Warehouse Sprawl > 8 warehouses

This dashboard provides a comprehensive view of user optimization opportunities with actionable insights and clear prioritization for cost reduction and performance improvement.