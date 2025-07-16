-- =====================================================
-- SNOWFLAKE USER 360 DASHBOARD - ADVANCED ANALYTICS
-- =====================================================
-- Purpose: Deep insights into user behavior, cost impact, and optimization opportunities
-- Focus: Actionable intelligence beyond basic usage stats

-- =====================================================
-- SECTION 1: ADVANCED CHARTS (8 Charts)
-- =====================================================

-- CHART 1: User Value vs Cost Quadrant Analysis
-- Purpose: Identify high-value vs high-cost users to distinguish optimization targets
WITH user_metrics AS (
    SELECT 
        user_name,
        SUM(total_elapsed_time/1000) as total_compute_seconds,
        SUM(credits_used) as total_credits,
        COUNT(DISTINCT query_id) as query_count,
        COUNT(DISTINCT date_trunc('day', start_time)) as active_days,
        AVG(execution_time/1000) as avg_query_time_sec,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) as successful_queries,
        SUM(rows_produced) as total_rows_produced,
        SUM(bytes_scanned) as total_bytes_scanned
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name
),
user_value_score AS (
    SELECT 
        user_name,
        total_credits,
        -- Value Score: Combines productivity, reliability, and data impact
        (
            (successful_queries * 1.0 / NULLIF(query_count, 0)) * 40 +  -- Success rate weight
            (total_rows_produced / NULLIF(query_count, 0) / 1000) * 30 + -- Avg rows per query
            (active_days * 2) * 20 +  -- Consistency weight
            LEAST(query_count / 10, 10) * 10  -- Query volume (capped)
        ) as value_score,
        query_count,
        active_days,
        avg_query_time_sec
    FROM user_metrics
)
SELECT 
    user_name,
    total_credits as cost_impact,
    value_score,
    CASE 
        WHEN total_credits > 100 AND value_score > 60 THEN 'High Value - High Cost'
        WHEN total_credits > 100 AND value_score <= 60 THEN 'Low Value - High Cost (OPTIMIZE)'
        WHEN total_credits <= 100 AND value_score > 60 THEN 'High Value - Low Cost (IDEAL)'
        ELSE 'Low Value - Low Cost (MONITOR)'
    END as user_segment,
    query_count,
    active_days,
    ROUND(avg_query_time_sec, 2) as avg_query_time_sec
FROM user_value_score
ORDER BY total_credits DESC;

-- CHART 2: User Efficiency Trend Over Time
-- Purpose: Show user performance trends to identify degrading or improving users
WITH daily_user_metrics AS (
    SELECT 
        user_name,
        date_trunc('day', start_time) as query_date,
        COUNT(query_id) as daily_queries,
        SUM(credits_used) as daily_credits,
        AVG(execution_time/1000) as avg_execution_time,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
        SUM(rows_produced) / COUNT(*) as avg_rows_per_query
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name, date_trunc('day', start_time)
),
user_efficiency AS (
    SELECT 
        user_name,
        query_date,
        daily_queries,
        daily_credits,
        -- Efficiency Score: Output per unit of cost
        CASE 
            WHEN daily_credits > 0 THEN (avg_rows_per_query * success_rate) / daily_credits
            ELSE 0 
        END as efficiency_score,
        success_rate,
        avg_execution_time
    FROM daily_user_metrics
)
SELECT 
    user_name,
    query_date,
    daily_queries,
    daily_credits,
    ROUND(efficiency_score, 4) as efficiency_score,
    ROUND(success_rate, 2) as success_rate_pct,
    ROUND(avg_execution_time, 2) as avg_execution_time_sec
FROM user_efficiency
WHERE daily_queries >= 5  -- Filter for meaningful analysis
ORDER BY user_name, query_date;

-- CHART 3: Query Pattern Analysis by User
-- Purpose: Identify users with problematic query patterns (long-running, frequent failures)
WITH query_patterns AS (
    SELECT 
        user_name,
        CASE 
            WHEN execution_time >= 300000 THEN 'Long Running (5+ min)'
            WHEN execution_time >= 60000 THEN 'Medium (1-5 min)'
            WHEN execution_time >= 10000 THEN 'Short (10s-1min)'
            ELSE 'Very Short (<10s)'
        END as query_duration_bucket,
        CASE 
            WHEN error_code IS NOT NULL THEN 'Failed'
            ELSE 'Success'
        END as query_status,
        COUNT(*) as query_count,
        SUM(credits_used) as total_credits,
        AVG(execution_time/1000) as avg_execution_time_sec
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name, query_duration_bucket, query_status
)
SELECT 
    user_name,
    query_duration_bucket,
    query_status,
    query_count,
    ROUND(total_credits, 2) as credits_used,
    ROUND(avg_execution_time_sec, 2) as avg_execution_time_sec,
    -- Risk Score: Higher for users with many long-running or failed queries
    CASE 
        WHEN query_duration_bucket = 'Long Running (5+ min)' AND query_status = 'Failed' THEN 10
        WHEN query_duration_bucket = 'Long Running (5+ min)' THEN 7
        WHEN query_status = 'Failed' THEN 5
        WHEN query_duration_bucket = 'Medium (1-5 min)' THEN 3
        ELSE 1
    END as risk_score
FROM query_patterns
ORDER BY user_name, risk_score DESC;

-- CHART 4: Warehouse Usage Distribution by User
-- Purpose: Show which users are monopolizing expensive warehouses
WITH user_warehouse_usage AS (
    SELECT 
        qh.user_name,
        qh.warehouse_name,
        wh.warehouse_size,
        COUNT(qh.query_id) as query_count,
        SUM(qh.credits_used) as credits_consumed,
        SUM(qh.total_elapsed_time/1000) as total_compute_seconds,
        AVG(qh.execution_time/1000) as avg_query_time_sec
    FROM snowflake.account_usage.query_history qh
    LEFT JOIN snowflake.account_usage.warehouse_events_history wh
        ON qh.warehouse_name = wh.warehouse_name
        AND wh.timestamp >= dateadd('day', -30, current_date())
    WHERE qh.start_time >= dateadd('day', -30, current_date())
    AND qh.user_name IS NOT NULL
    AND qh.warehouse_name IS NOT NULL
    GROUP BY qh.user_name, qh.warehouse_name, wh.warehouse_size
),
warehouse_costs AS (
    SELECT 
        warehouse_size,
        CASE 
            WHEN warehouse_size = 'X-Small' THEN 1
            WHEN warehouse_size = 'Small' THEN 2
            WHEN warehouse_size = 'Medium' THEN 4
            WHEN warehouse_size = 'Large' THEN 8
            WHEN warehouse_size = 'X-Large' THEN 16
            WHEN warehouse_size = '2X-Large' THEN 32
            WHEN warehouse_size = '3X-Large' THEN 64
            WHEN warehouse_size = '4X-Large' THEN 128
            ELSE 4
        END as size_multiplier
    FROM (SELECT DISTINCT warehouse_size FROM user_warehouse_usage) t
)
SELECT 
    uwu.user_name,
    uwu.warehouse_name,
    uwu.warehouse_size,
    uwu.query_count,
    ROUND(uwu.credits_consumed, 2) as credits_consumed,
    ROUND(uwu.total_compute_seconds, 2) as compute_seconds,
    ROUND(uwu.avg_query_time_sec, 2) as avg_query_time_sec,
    wc.size_multiplier,
    -- Cost Efficiency: Credits per successful query
    ROUND(uwu.credits_consumed / NULLIF(uwu.query_count, 0), 4) as cost_per_query
FROM user_warehouse_usage uwu
JOIN warehouse_costs wc ON uwu.warehouse_size = wc.warehouse_size
ORDER BY uwu.user_name, uwu.credits_consumed DESC;

-- CHART 5: Peak Usage Hours by User
-- Purpose: Identify users causing peak hour congestion and higher costs
WITH hourly_usage AS (
    SELECT 
        user_name,
        EXTRACT(hour FROM start_time) as hour_of_day,
        COUNT(query_id) as query_count,
        SUM(credits_used) as hourly_credits,
        AVG(execution_time/1000) as avg_execution_time_sec,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name, EXTRACT(hour FROM start_time)
),
peak_hours AS (
    SELECT hour_of_day,
           SUM(hourly_credits) as total_hourly_credits
    FROM hourly_usage
    GROUP BY hour_of_day
    ORDER BY total_hourly_credits DESC
    LIMIT 8  -- Top 8 peak hours
)
SELECT 
    hu.user_name,
    hu.hour_of_day,
    hu.query_count,
    ROUND(hu.hourly_credits, 2) as hourly_credits,
    ROUND(hu.avg_execution_time_sec, 2) as avg_execution_time_sec,
    ROUND(hu.success_rate, 2) as success_rate_pct,
    CASE 
        WHEN ph.hour_of_day IS NOT NULL THEN 'Peak Hour'
        ELSE 'Off-Peak'
    END as peak_indicator,
    -- Peak penalty: Higher cost during peak hours
    CASE 
        WHEN ph.hour_of_day IS NOT NULL THEN hu.hourly_credits * 1.5
        ELSE hu.hourly_credits
    END as adjusted_cost
FROM hourly_usage hu
LEFT JOIN peak_hours ph ON hu.hour_of_day = ph.hour_of_day
WHERE hu.query_count >= 3  -- Filter for meaningful analysis
ORDER BY hu.user_name, hu.hourly_credits DESC;

-- CHART 6: Data Access Patterns and Table Impact
-- Purpose: Show which users are accessing large tables inefficiently
WITH user_table_access AS (
    SELECT 
        qh.user_name,
        qh.query_type,
        oau.direct_objects_accessed,
        COUNT(qh.query_id) as query_count,
        SUM(qh.credits_used) as total_credits,
        SUM(qh.bytes_scanned) as total_bytes_scanned,
        AVG(qh.bytes_scanned) as avg_bytes_per_query,
        SUM(qh.rows_produced) as total_rows_produced,
        AVG(qh.execution_time/1000) as avg_execution_time_sec
    FROM snowflake.account_usage.query_history qh
    JOIN snowflake.account_usage.access_history ah ON qh.query_id = ah.query_id
    JOIN snowflake.account_usage.object_access_usage oau ON ah.query_id = oau.query_id
    WHERE qh.start_time >= dateadd('day', -30, current_date())
    AND qh.user_name IS NOT NULL
    AND qh.bytes_scanned > 0
    GROUP BY qh.user_name, qh.query_type, oau.direct_objects_accessed
),
table_efficiency AS (
    SELECT 
        user_name,
        query_type,
        direct_objects_accessed,
        query_count,
        total_credits,
        total_bytes_scanned,
        avg_bytes_per_query,
        total_rows_produced,
        avg_execution_time_sec,
        -- Efficiency metrics
        CASE 
            WHEN total_bytes_scanned > 0 THEN total_rows_produced / (total_bytes_scanned / 1048576)  -- Rows per MB
            ELSE 0 
        END as rows_per_mb_scanned,
        CASE 
            WHEN total_rows_produced > 0 THEN total_credits / total_rows_produced * 1000  -- Cost per 1K rows
            ELSE 0 
        END as cost_per_1k_rows
    FROM user_table_access
)
SELECT 
    user_name,
    query_type,
    direct_objects_accessed as tables_accessed,
    query_count,
    ROUND(total_credits, 2) as total_credits,
    ROUND(total_bytes_scanned / 1073741824, 2) as total_gb_scanned,  -- Convert to GB
    ROUND(avg_bytes_per_query / 1048576, 2) as avg_mb_per_query,
    total_rows_produced,
    ROUND(avg_execution_time_sec, 2) as avg_execution_time_sec,
    ROUND(rows_per_mb_scanned, 2) as efficiency_rows_per_mb,
    ROUND(cost_per_1k_rows, 6) as cost_per_1k_rows,
    -- Optimization flag
    CASE 
        WHEN cost_per_1k_rows > 0.01 AND rows_per_mb_scanned < 1000 THEN 'High Cost - Low Efficiency'
        WHEN cost_per_1k_rows > 0.01 THEN 'High Cost'
        WHEN rows_per_mb_scanned < 1000 THEN 'Low Efficiency'
        ELSE 'Acceptable'
    END as optimization_status
FROM table_efficiency
WHERE query_count >= 5
ORDER BY total_credits DESC;

-- CHART 7: User Query Complexity and Resource Consumption
-- Purpose: Analyze relationship between query complexity and resource usage
WITH query_complexity AS (
    SELECT 
        user_name,
        query_id,
        query_type,
        credits_used,
        execution_time/1000 as execution_time_sec,
        bytes_scanned,
        rows_produced,
        -- Complexity indicators
        CASE 
            WHEN query_text ILIKE '%join%' THEN 1 ELSE 0 
        END as has_joins,
        CASE 
            WHEN query_text ILIKE '%window%' OR query_text ILIKE '%over(%' THEN 1 ELSE 0 
        END as has_window_functions,
        CASE 
            WHEN query_text ILIKE '%group by%' THEN 1 ELSE 0 
        END as has_groupby,
        CASE 
            WHEN query_text ILIKE '%order by%' THEN 1 ELSE 0 
        END as has_orderby,
        CASE 
            WHEN query_text ILIKE '%union%' THEN 1 ELSE 0 
        END as has_union,
        CASE 
            WHEN query_text ILIKE '%subquery%' OR query_text ILIKE '%(%select%' THEN 1 ELSE 0 
        END as has_subquery,
        LEN(query_text) as query_length
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    AND query_text IS NOT NULL
    AND execution_time > 1000  -- Focus on queries > 1 second
),
user_complexity_analysis AS (
    SELECT 
        user_name,
        COUNT(*) as total_queries,
        AVG(execution_time_sec) as avg_execution_time_sec,
        AVG(credits_used) as avg_credits_per_query,
        SUM(credits_used) as total_credits,
        -- Complexity score
        AVG(has_joins + has_window_functions + has_groupby + has_orderby + has_union + has_subquery) as avg_complexity_score,
        AVG(query_length) as avg_query_length,
        -- Resource efficiency
        AVG(CASE WHEN execution_time_sec > 0 THEN credits_used / execution_time_sec ELSE 0 END) as credits_per_second,
        AVG(CASE WHEN bytes_scanned > 0 THEN rows_produced / (bytes_scanned / 1048576) ELSE 0 END) as rows_per_mb
    FROM query_complexity
    GROUP BY user_name
)
SELECT 
    user_name,
    total_queries,
    ROUND(avg_execution_time_sec, 2) as avg_execution_time_sec,
    ROUND(avg_credits_per_query, 4) as avg_credits_per_query,
    ROUND(total_credits, 2) as total_credits,
    ROUND(avg_complexity_score, 2) as avg_complexity_score,
    ROUND(avg_query_length, 0) as avg_query_length,
    ROUND(credits_per_second, 6) as credits_per_second,
    ROUND(rows_per_mb, 2) as rows_per_mb,
    -- Performance vs Complexity Analysis
    CASE 
        WHEN avg_complexity_score > 3 AND avg_credits_per_query > 0.1 THEN 'Complex & Expensive'
        WHEN avg_complexity_score > 3 THEN 'Complex but Efficient'
        WHEN avg_credits_per_query > 0.1 THEN 'Simple but Expensive'
        ELSE 'Simple & Efficient'
    END as user_profile
FROM user_complexity_analysis
WHERE total_queries >= 10
ORDER BY total_credits DESC;

-- CHART 8: User Session Patterns and Concurrency Impact
-- Purpose: Identify users creating concurrency issues and resource conflicts
WITH user_sessions AS (
    SELECT 
        user_name,
        session_id,
        warehouse_name,
        MIN(start_time) as session_start,
        MAX(end_time) as session_end,
        COUNT(query_id) as queries_in_session,
        SUM(credits_used) as session_credits,
        AVG(execution_time/1000) as avg_query_time_sec
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    AND session_id IS NOT NULL
    GROUP BY user_name, session_id, warehouse_name
),
session_analysis AS (
    SELECT 
        user_name,
        COUNT(DISTINCT session_id) as total_sessions,
        AVG(queries_in_session) as avg_queries_per_session,
        AVG(session_credits) as avg_credits_per_session,
        SUM(session_credits) as total_credits,
        AVG(DATEDIFF('minute', session_start, session_end)) as avg_session_duration_min,
        AVG(avg_query_time_sec) as avg_query_time_sec,
        COUNT(DISTINCT warehouse_name) as warehouses_used
    FROM user_sessions
    WHERE queries_in_session >= 3  -- Filter for meaningful sessions
    GROUP BY user_name
),
concurrency_analysis AS (
    SELECT 
        user_name,
        start_time,
        end_time,
        warehouse_name,
        COUNT(*) OVER (
            PARTITION BY user_name, warehouse_name 
            ORDER BY start_time 
            RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ) as concurrent_queries
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
),
max_concurrency AS (
    SELECT 
        user_name,
        MAX(concurrent_queries) as max_concurrent_queries,
        AVG(concurrent_queries) as avg_concurrent_queries
    FROM concurrency_analysis
    GROUP BY user_name
)
SELECT 
    sa.user_name,
    sa.total_sessions,
    ROUND(sa.avg_queries_per_session, 2) as avg_queries_per_session,
    ROUND(sa.avg_credits_per_session, 4) as avg_credits_per_session,
    ROUND(sa.total_credits, 2) as total_credits,
    ROUND(sa.avg_session_duration_min, 2) as avg_session_duration_min,
    ROUND(sa.avg_query_time_sec, 2) as avg_query_time_sec,
    sa.warehouses_used,
    mc.max_concurrent_queries,
    ROUND(mc.avg_concurrent_queries, 2) as avg_concurrent_queries,
    -- Concurrency risk score
    CASE 
        WHEN mc.max_concurrent_queries > 10 THEN 'High Concurrency Risk'
        WHEN mc.max_concurrent_queries > 5 THEN 'Medium Concurrency Risk'
        ELSE 'Low Concurrency Risk'
    END as concurrency_risk_level
FROM session_analysis sa
JOIN max_concurrency mc ON sa.user_name = mc.user_name
WHERE sa.total_sessions >= 5
ORDER BY sa.total_credits DESC;

-- =====================================================
-- SECTION 2: RECOMMENDATION TABLES (4 Tables)
-- =====================================================

-- TABLE 1: Enterprise-Grade Unoptimized Users Detection & Prioritization
-- Purpose: Comprehensive analysis to identify cost-bleeding users with robust scoring logic
WITH user_base_metrics AS (
    SELECT 
        user_name,
        COUNT(DISTINCT query_id) as total_queries,
        SUM(credits_used) as total_credits,
        AVG(execution_time/1000) as avg_execution_time_sec,
        MEDIAN(execution_time/1000) as median_execution_time_sec,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time/1000) as p95_execution_time_sec,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
        COUNT(DISTINCT warehouse_name) as warehouses_used,
        COUNT(DISTINCT date_trunc('day', start_time)) as active_days,
        SUM(bytes_scanned) as total_bytes_scanned,
        SUM(rows_produced) as total_rows_produced,
        AVG(bytes_scanned) as avg_bytes_per_query,
        AVG(rows_produced) as avg_rows_per_query,
        COUNT(CASE WHEN execution_time >= 300000 THEN 1 END) as long_running_queries,  -- >5 min
        COUNT(CASE WHEN execution_time >= 60000 AND execution_time < 300000 THEN 1 END) as medium_queries,
        COUNT(CASE WHEN error_code IS NOT NULL THEN 1 END) as failed_queries,
        COUNT(CASE WHEN bytes_scanned > 5368709120 THEN 1 END) as large_scan_queries,  -- >5GB
        COUNT(CASE WHEN rows_produced = 0 THEN 1 END) as zero_result_queries,
        COUNT(CASE WHEN bytes_scanned > 0 AND rows_produced = 0 THEN 1 END) as wasteful_scans,
        SUM(CASE WHEN query_type = 'SELECT' THEN credits_used ELSE 0 END) as select_credits,
        SUM(CASE WHEN query_type IN ('INSERT', 'UPDATE', 'DELETE', 'MERGE') THEN credits_used ELSE 0 END) as dml_credits
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name
),
user_advanced_metrics AS (
    SELECT 
        *,
        -- Data efficiency metrics
        CASE 
            WHEN total_bytes_scanned > 0 THEN total_rows_produced / (total_bytes_scanned / 1048576)  -- Rows per MB
            ELSE 0 
        END as data_efficiency_ratio,
        
        -- Cost efficiency metrics
        CASE 
            WHEN total_rows_produced > 0 THEN total_credits / (total_rows_produced / 1000)  -- Cost per 1K rows
            ELSE total_credits / NULLIF(total_queries, 0) * 10  -- Penalty for zero results
        END as cost_efficiency_ratio,
        
        -- Query pattern analysis
        long_running_queries * 100.0 / NULLIF(total_queries, 0) as long_running_pct,
        failed_queries * 100.0 / NULLIF(total_queries, 0) as failure_rate,
        large_scan_queries * 100.0 / NULLIF(total_queries, 0) as large_scan_pct,
        zero_result_queries * 100.0 / NULLIF(total_queries, 0) as zero_result_pct,
        wasteful_scans * 100.0 / NULLIF(total_queries, 0) as wasteful_scan_pct,
        
        -- Resource utilization patterns
        CASE 
            WHEN active_days > 0 THEN total_credits / active_days
            ELSE 0 
        END as daily_avg_credits,
        
        -- Warehouse efficiency
        CASE 
            WHEN warehouses_used > 0 THEN total_credits / warehouses_used
            ELSE 0 
        END as credits_per_warehouse
        
    FROM user_base_metrics
),
user_scoring AS (
    SELECT 
        *,
        -- ROBUST SCORING SYSTEM (0-100, higher is worse)
        -- Performance Issues (0-30 points)
        LEAST(30, 
            (CASE WHEN avg_execution_time_sec > 300 THEN 10 ELSE avg_execution_time_sec / 30 END) +
            (CASE WHEN p95_execution_time_sec > 600 THEN 10 ELSE p95_execution_time_sec / 60 END) +
            (long_running_pct * 0.3)
        ) as performance_score,
        
        -- Data Waste Issues (0-25 points)
        LEAST(25,
            (CASE WHEN data_efficiency_ratio < 100 THEN 10 ELSE 0 END) +
            (CASE WHEN large_scan_pct > 20 THEN 8 ELSE large_scan_pct * 0.4 END) +
            (CASE WHEN zero_result_pct > 15 THEN 7 ELSE zero_result_pct * 0.47 END)
        ) as data_waste_score,
        
        -- Cost Inefficiency (0-25 points)
        LEAST(25,
            (CASE WHEN cost_efficiency_ratio > 0.01 THEN 10 ELSE cost_efficiency_ratio * 1000 END) +
            (CASE WHEN total_credits / NULLIF(total_queries, 0) > 0.1 THEN 8 ELSE (total_credits / NULLIF(total_queries, 0)) * 80 END) +
            (CASE WHEN daily_avg_credits > 50 THEN 7 ELSE daily_avg_credits * 0.14 END)
        ) as cost_inefficiency_score,
        
        -- Reliability Issues (0-20 points)
        LEAST(20,
            (CASE WHEN failure_rate > 10 THEN 15 ELSE failure_rate * 1.5 END) +
            (CASE WHEN wasteful_scan_pct > 10 THEN 5 ELSE wasteful_scan_pct * 0.5 END)
        ) as reliability_score
        
    FROM user_advanced_metrics
),
final_user_analysis AS (
    SELECT 
        *,
        -- Total optimization score
        performance_score + data_waste_score + cost_inefficiency_score + reliability_score as total_optimization_score,
        
        -- Priority classification
        CASE 
            WHEN total_credits > 500 AND (performance_score + data_waste_score + cost_inefficiency_score + reliability_score) > 60 THEN 'CRITICAL'
            WHEN total_credits > 200 AND (performance_score + data_waste_score + cost_inefficiency_score + reliability_score) > 50 THEN 'HIGH'
            WHEN total_credits > 100 AND (performance_score + data_waste_score + cost_inefficiency_score + reliability_score) > 40 THEN 'MEDIUM'
            WHEN (performance_score + data_waste_score + cost_inefficiency_score + reliability_score) > 35 THEN 'LOW'
            ELSE 'MONITOR'
        END as priority_level,
        
        -- Dominant issue identification
        CASE 
            WHEN performance_score >= data_waste_score AND performance_score >= cost_inefficiency_score AND performance_score >= reliability_score THEN 'PERFORMANCE'
            WHEN data_waste_score >= cost_inefficiency_score AND data_waste_score >= reliability_score THEN 'DATA_WASTE'
            WHEN cost_inefficiency_score >= reliability_score THEN 'COST_INEFFICIENCY'
            ELSE 'RELIABILITY'
        END as primary_issue_type,
        
        -- Specific recommendations based on scoring
        CASE 
            WHEN performance_score > 20 AND data_waste_score > 15 THEN 'Optimize queries + Implement data filtering + Add result caching'
            WHEN performance_score > 20 AND cost_inefficiency_score > 15 THEN 'Query optimization + Warehouse right-sizing + Usage scheduling'
            WHEN performance_score > 20 THEN 'Query performance tuning + Execution plan optimization + Resource allocation review'
            WHEN data_waste_score > 15 AND zero_result_pct > 20 THEN 'Data access patterns review + Query validation + Result set optimization'
            WHEN data_waste_score > 15 THEN 'Implement data filtering + Use clustering keys + Optimize scan patterns'
            WHEN cost_inefficiency_score > 15 AND warehouses_used > 3 THEN 'Warehouse consolidation + Resource optimization + Usage pattern analysis'
            WHEN cost_inefficiency_score > 15 THEN 'Cost optimization + Resource right-sizing + Usage efficiency review'
            WHEN reliability_score > 15 THEN 'Error handling + Query validation + Monitoring implementation'
            ELSE 'General optimization review + Best practices implementation'
        END as detailed_recommendation,
        
        -- Estimated savings calculation
        CASE 
            WHEN total_optimization_score >= 70 THEN ROUND(total_credits * 0.55, 2)  -- 55% savings potential
            WHEN total_optimization_score >= 60 THEN ROUND(total_credits * 0.45, 2)  -- 45% savings potential
            WHEN total_optimization_score >= 50 THEN ROUND(total_credits * 0.35, 2)  -- 35% savings potential
            WHEN total_optimization_score >= 40 THEN ROUND(total_credits * 0.25, 2)  -- 25% savings potential
            WHEN total_optimization_score >= 30 THEN ROUND(total_credits * 0.15, 2)  -- 15% savings potential
            ELSE ROUND(total_credits * 0.05, 2)  -- 5% savings potential
        END as estimated_monthly_savings
        
    FROM user_scoring
)
SELECT 
    user_name,
    priority_level,
    ROUND(total_optimization_score, 1) as optimization_score,
    primary_issue_type,
    ROUND(total_credits, 2) as total_credits,
    total_queries,
    ROUND(avg_execution_time_sec, 2) as avg_execution_time_sec,
    ROUND(success_rate, 2) as success_rate_pct,
    ROUND(data_efficiency_ratio, 2) as rows_per_mb_scanned,
    ROUND(cost_efficiency_ratio, 6) as cost_per_1k_rows,
    ROUND(long_running_pct, 2) as long_running_pct,
    ROUND(failure_rate, 2) as failure_rate_pct,
    ROUND(zero_result_pct, 2) as zero_result_pct,
    ROUND(wasteful_scan_pct, 2) as wasteful_scan_pct,
    warehouses_used,
    active_days,
    detailed_recommendation,
    estimated_monthly_savings,
    -- Breakdown scores for detailed analysis
    ROUND(performance_score, 1) as performance_score,
    ROUND(data_waste_score, 1) as data_waste_score,
    ROUND(cost_inefficiency_score, 1) as cost_inefficiency_score,
    ROUND(reliability_score, 1) as reliability_score
FROM final_user_analysis
WHERE total_credits > 25  -- Focus on users with meaningful cost impact
AND total_optimization_score > 25  -- Only users with optimization opportunities
ORDER BY 
    CASE priority_level 
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
        ELSE 5
    END,
    total_optimization_score DESC,
    total_credits DESC;

-- TABLE 2: Single User Deep Dive Analysis
-- Purpose: Comprehensive 360-degree view of individual user behavior and classification
WITH user_comprehensive_analysis AS (
    SELECT 
        user_name,
        -- Basic metrics
        COUNT(DISTINCT query_id) as total_queries,
        SUM(credits_used) as total_credits,
        COUNT(DISTINCT date_trunc('day', start_time)) as active_days,
        COUNT(DISTINCT warehouse_name) as warehouses_used,
        COUNT(DISTINCT database_name) as databases_accessed,
        COUNT(DISTINCT schema_name) as schemas_accessed,
        
        -- Query type breakdown
        COUNT(CASE WHEN query_type = 'SELECT' THEN 1 END) as select_queries,
        COUNT(CASE WHEN query_type IN ('INSERT', 'UPDATE', 'DELETE', 'MERGE') THEN 1 END) as dml_queries,
        COUNT(CASE WHEN query_type IN ('CREATE', 'ALTER', 'DROP') THEN 1 END) as ddl_queries,
        COUNT(CASE WHEN query_type = 'COPY' THEN 1 END) as copy_queries,
        
        -- Performance metrics
        AVG(execution_time/1000) as avg_execution_time_sec,
        MEDIAN(execution_time/1000) as median_execution_time_sec,
        MAX(execution_time/1000) as max_execution_time_sec,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time/1000) as p95_execution_time_sec,
        
        -- Data access patterns
        SUM(bytes_scanned) as total_bytes_scanned,
        AVG(bytes_scanned) as avg_bytes_per_query,
        SUM(rows_produced) as total_rows_produced,
        AVG(rows_produced) as avg_rows_per_query,
        
        -- Cost analysis
        SUM(credits_used) / COUNT(DISTINCT query_id) as avg_cost_per_query,
        SUM(credits_used) / COUNT(DISTINCT date_trunc('day', start_time)) as avg_daily_cost,
        
        -- Quality metrics
        COUNT(CASE WHEN error_code IS NULL THEN 1 END) * 100.0 / COUNT(*) as success_rate,
        COUNT(CASE WHEN compilation_time > 5000 THEN 1 END) as slow_compilation_queries,
        COUNT(CASE WHEN execution_time > 300000 THEN 1 END) as very_long_queries,
        COUNT(CASE WHEN rows_produced = 0 THEN 1 END) as zero_result_queries,
        COUNT(CASE WHEN bytes_scanned > 0 AND rows_produced = 0 THEN 1 END) as wasteful_queries,
        
        -- Timing patterns
        COUNT(CASE WHEN EXTRACT(hour FROM start_time) BETWEEN 9 AND 17 THEN 1 END) as business_hours_queries,
        COUNT(CASE WHEN EXTRACT(hour FROM start_time) NOT BETWEEN 9 AND 17 THEN 1 END) as off_hours_queries,
        
        -- Warehouse usage patterns
        SUM(CASE WHEN warehouse_name ILIKE '%SMALL%' THEN credits_used ELSE 0 END) as small_warehouse_credits,
        SUM(CASE WHEN warehouse_name ILIKE '%MEDIUM%' THEN credits_used ELSE 0 END) as medium_warehouse_credits,
        SUM(CASE WHEN warehouse_name ILIKE '%LARGE%' THEN credits_used ELSE 0 END) as large_warehouse_credits,
        
        -- Session patterns
        COUNT(DISTINCT session_id) as unique_sessions,
        AVG(COUNT(query_id)) OVER (PARTITION BY user_name, session_id) as avg_queries_per_session
        
    FROM snowflake.account_usage.query_history
    WHERE start_time >= dateadd('day', -30, current_date())
    AND user_name IS NOT NULL
    GROUP BY user_name
),
user_behavior_classification AS (
    SELECT 
        *,
        -- Data efficiency calculation
        CASE 
            WHEN total_bytes_scanned > 0 THEN total_rows_produced / (total_bytes_scanned / 1048576)
            ELSE 0 
        END as data_efficiency_ratio,
        
        -- User type classification
        CASE 
            WHEN select_queries * 100.0 / total_queries > 90 AND avg_execution_time_sec < 60 THEN 'Analytics User'
            WHEN dml_queries * 100.0 / total_queries > 50 THEN 'Data Engineer'
            WHEN ddl_queries * 100.0 / total_queries > 20 THEN 'Database Developer'
            WHEN copy_queries * 100.0 / total_queries > 30 THEN 'Data Loader'
            WHEN avg_execution_time_sec > 300 THEN 'Heavy Processing User'
            WHEN total_queries > 1000 THEN 'High Volume User'
            ELSE 'General User'
        END as user_type,
        
        -- Performance classification
        CASE 
            WHEN avg_execution_time_sec > 300 AND success_rate < 85 THEN 'Poor Performance'
            WHEN avg_execution_time_sec > 180 THEN 'Slow Performance'
            WHEN avg_execution_time_sec > 60 THEN 'Moderate Performance'
            WHEN success_rate > 95 AND avg_execution_time_sec < 30 THEN 'Excellent Performance'
            ELSE 'Good Performance'
        END as performance_classification,
        
        -- Cost classification
        CASE 
            WHEN total_credits > 1000 THEN 'Very High Cost'
            WHEN total_credits > 500 THEN 'High Cost'
            WHEN total_credits > 200 THEN 'Medium Cost'
            WHEN total_credits > 50 THEN 'Low Cost'
            ELSE 'Very Low Cost'
        END as cost_classification,
        
        -- Usage pattern classification
        CASE 
            WHEN active_days > 25 THEN 'Daily Active'
            WHEN active_days > 15 THEN 'Regular User'
            WHEN active_days > 5 THEN 'Occasional User'
            ELSE 'Infrequent User'
        END as usage_pattern,
        
        -- Overall user health score (0-100)
        LEAST(100, 
            (success_rate * 0.3) +
            (CASE WHEN avg_execution_time_sec < 60 THEN 25 ELSE GREATEST(0, 25 - (avg_execution_time_sec / 60 * 5)) END) +
            (CASE WHEN data_efficiency_ratio > 1000 THEN 25 ELSE data_efficiency_ratio / 1000 * 25 END) +
            (CASE WHEN zero_result_queries * 100.0 / total_queries < 10 THEN 20 ELSE GREATEST(0, 20 - (zero_result_queries * 100.0 / total_queries * 2)) END)
        ) as user_health_score
        
    FROM user_comprehensive_analysis
),
user_recommendations AS (
    SELECT 
        *,
        -- Specific recommendations based on user profile
        CASE 
            WHEN user_type = 'Analytics User' AND performance_classification = 'Poor Performance' THEN 'Optimize SELECT queries, implement result caching, consider query acceleration'
            WHEN user_type = 'Data Engineer' AND cost_classification IN ('High Cost', 'Very High Cost') THEN 'Optimize DML operations, use efficient loading patterns, implement incremental processing'
            WHEN user_type = 'Database Developer' AND success_rate < 90 THEN 'Review DDL scripts, implement proper error handling, validate syntax before execution'
            WHEN user_type = 'Data Loader' AND avg_execution_time_sec > 300 THEN 'Optimize COPY operations, use parallel loading, implement file size management'
            WHEN user_type = 'Heavy Processing User' THEN 'Implement query optimization, consider warehouse scaling, use result caching'
            WHEN user_type = 'High Volume User' AND cost_classification IN ('High Cost', 'Very High Cost') THEN 'Implement query batching, use connection pooling, optimize query patterns'
            WHEN performance_classification = 'Poor Performance' THEN 'General performance optimization, query tuning, resource allocation review'
            WHEN cost_classification IN ('High Cost', 'Very High Cost') AND user_health_score < 60 THEN 'Comprehensive optimization: query tuning, resource optimization, usage pattern review'
            ELSE 'Monitor and maintain current good practices'
        END as primary_recommendation,
        
        -- Action items based on specific metrics
        CASE 
            WHEN wasteful_queries > 0 THEN 'HIGH: Review queries that scan data but return no results'
            WHEN very_long_queries > 10 THEN 'HIGH: Optimize queries taking more than 5 minutes'
            WHEN success_rate < 85 THEN 'MEDIUM: Investigate and fix failing queries'
            WHEN warehouses_used > 5 THEN 'MEDIUM: Consolidate warehouse usage'
            WHEN zero_result_queries * 100.0 / total_queries > 20 THEN 'MEDIUM: Review queries with no results'
            ELSE 'LOW: General monitoring and optimization'
        END as action_priority,
        
        -- User classification for management
        CASE 
            WHEN user_health_score >= 80 AND cost_classification IN ('Low Cost', 'Very Low Cost') THEN 'Ideal User'
            WHEN user_health_score >= 70 AND cost_classification IN ('Medium Cost', 'Low Cost') THEN 'Good User'
            WHEN user_health_score >= 60 OR cost_classification IN ('High Cost', 'Very High Cost') THEN 'Needs Attention'
            ELSE 'Requires Optimization'
        END as user_classification
        
    FROM user_behavior_classification
)
SELECT 
    user_name,
    user_type,
    user_classification,
    performance_classification,
    cost_classification,
    usage_pattern,
    ROUND(user_health_score, 1) as user_health_score,
    
    -- Key metrics
    total_queries,
    ROUND(total_credits, 2) as total_credits,
    active_days,
    warehouses_used,
    
    -- Performance details
    ROUND(avg_execution_