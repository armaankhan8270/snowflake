queries={
    """WITH user_metrics AS (
    SELECT 
        user_name,
        SUM(total_elapsed_time / 1000) AS total_elapsed_seconds,
        SUM(execution_time / 1000) AS total_exec_seconds,
        SUM(total_elapsed_time - execution_time) / 1000 AS total_idle_seconds,
        SUM(credits_used) AS total_credits,
        COUNT(DISTINCT query_id) AS query_count,
        COUNT(DISTINCT DATE_TRUNC('day', start_time)) AS active_days,
        AVG(execution_time / 1000) AS avg_exec_time_sec,
        AVG(bytes_scanned) AS avg_bytes_scanned,
        SUM(bytes_scanned) AS total_bytes_scanned,
        SUM(rows_produced) AS total_rows_produced,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) AS successful_queries
    FROM snowflake.account_usage.query_history
    WHERE 
        start_time >= DATEADD('day', -30, CURRENT_DATE())
        AND user_name IS NOT NULL
        AND user_name NOT ILIKE 'SYS%' 
        AND user_name NOT ILIKE 'SERVICE%' 
    GROUP BY user_name
),

user_value_score AS (
    SELECT 
        user_name,
        total_credits,
        total_elapsed_seconds,
        total_exec_seconds,
        total_idle_seconds,
        query_count,
        active_days,
        avg_exec_time_sec,
        total_rows_produced,
        total_bytes_scanned,
        ROUND(SAFE_DIVIDE(total_rows_produced, NULLIF(total_bytes_scanned, 0)), 3) AS data_efficiency_ratio,
        ROUND(SAFE_DIVIDE(total_credits, NULLIF(total_rows_produced, 0)), 6) AS credits_per_row,
        ROUND(SAFE_DIVIDE(total_credits, NULLIF(total_bytes_scanned, 0)), 6) AS credits_per_byte,
        ROUND(SAFE_DIVIDE(total_idle_seconds, NULLIF(total_elapsed_seconds, 0)), 2) AS idle_ratio,
        ROUND((successful_queries * 1.0 / NULLIF(query_count, 0)), 3) AS success_rate,
        
        -- Updated weighted value score
        (
            COALESCE(successful_queries * 1.0 / NULLIF(query_count, 0), 0) * 35 + -- Success Rate
            COALESCE(total_rows_produced / NULLIF(query_count, 0) / 1000, 0) * 25 + -- Avg rows per query
            COALESCE(active_days * 2, 0) * 20 + -- Consistency
            LEAST(query_count / 10.0, 10) * 10 + -- Volume
            (1 - COALESCE(total_idle_seconds / NULLIF(total_elapsed_seconds, 1), 0)) * 10 -- Efficiency
        ) AS value_score
    FROM user_metrics
)

SELECT 
    user_name,
    total_credits AS cost_impact,
    ROUND(value_score, 2) AS value_score,
    query_count,
    active_days,
    ROUND(avg_exec_time_sec, 2) AS avg_query_time_sec,
    ROUND(success_rate * 100, 1) AS success_rate_percent,
    ROUND(idle_ratio * 100, 1) AS idle_time_percent,
    credits_per_row,
    credits_per_byte,
    data_efficiency_ratio,

    -- Segmentation Logic
    CASE 
        WHEN total_credits > 100 AND value_score > 60 THEN 'High Value - High Cost'
        WHEN total_credits > 100 AND value_score <= 60 THEN 'Low Value - High Cost (OPTIMIZE)'
        WHEN total_credits <= 100 AND value_score > 60 THEN 'High Value - Low Cost (IDEAL)'
        ELSE 'Low Value - Low Cost (MONITOR)'
    END AS user_segment

FROM user_value_score
ORDER BY total_credits DESC;
"""
,



"""
WITH daily_user_metrics AS (
    SELECT 
        user_name,
        DATE_TRUNC('day', start_time) AS query_date,
        COUNT(query_id) AS daily_queries,
        SUM(credits_used) AS daily_credits,
        AVG(execution_time / 1000.0) AS avg_execution_time_sec,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS success_rate,
        SUM(rows_produced) * 1.0 / NULLIF(COUNT(*), 0) AS avg_rows_per_query
    FROM snowflake.account_usage.query_history
    WHERE 
        start_time >= DATEADD('day', -30, CURRENT_DATE())
        AND user_name IS NOT NULL
        AND user_name NOT ILIKE 'SYS%' 
        AND user_name NOT ILIKE 'SERVICE%' 
    GROUP BY user_name, DATE_TRUNC('day', start_time)
),
user_efficiency AS (
    SELECT 
        user_name,
        query_date,
        daily_queries,
        daily_credits,
        -- Efficiency Score: Output per credit adjusted by success
        CASE 
            WHEN daily_credits > 0 THEN ROUND((avg_rows_per_query * success_rate) / NULLIF(daily_credits, 0), 4)
            ELSE 0 
        END AS efficiency_score,
        ROUND(success_rate, 2) AS success_rate_pct,
        ROUND(avg_execution_time_sec, 2) AS avg_exec_time_sec
    FROM daily_user_metrics
)
SELECT 
    user_name,
    query_date,
    daily_queries,
    daily_credits,
    efficiency_score,
    success_rate_pct,
    avg_exec_time_sec
FROM user_efficiency
WHERE daily_queries >= 5
ORDER BY user_name, query_date;

""",



# User recomstion query best 
"""
WITH base_metrics AS (
    SELECT 
        user_name,
        role_name,
        client_type,
        COUNT(DISTINCT query_id) AS total_queries,
        ROUND(SUM(TRY_CAST(credits_used AS FLOAT)), 2) AS total_credits,
        ROUND(AVG(TRY_CAST(execution_time / 1000.0 AS FLOAT)), 2) AS avg_exec_time_sec,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY TRY_CAST(execution_time / 1000.0 AS FLOAT)) AS median_exec_time_sec,
        ROUND(SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 2) AS success_rate_pct,
        COUNT(DISTINCT warehouse_name) AS warehouses_used,
        COUNT(DISTINCT DATE_TRUNC('day', start_time)) AS active_days,
        MAX(DATE_TRUNC('day', start_time)) AS last_active_day,
        ROUND(SUM(bytes_scanned) / NULLIF(COUNT(*), 0), 2) AS avg_bytes_per_query,
        ROUND(SUM(rows_produced) / NULLIF(COUNT(*), 0), 2) AS avg_rows_per_query,
        ROUND(SUM(credits_used) / NULLIF(COUNT(*), 0), 4) AS credits_per_query,
        ROUND(SUM(credits_used) / NULLIF(SUM(rows_produced), 0), 6) AS credits_per_row
    FROM snowflake.account_usage.query_history
    WHERE 
        start_time >= DATEADD('day', -30, CURRENT_DATE())
        AND user_name IS NOT NULL
        AND user_name NOT ILIKE 'SYS%'  
        AND user_name NOT ILIKE 'SERVICE%'  
    GROUP BY user_name, role_name, client_type
),

statistical_baselines AS (
    SELECT 
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_exec_time_sec) AS exec_time_high,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY success_rate_pct) AS success_rate_low,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY credits_per_query) AS high_cost_query,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_bytes_per_query) AS large_scan_bytes
    FROM base_metrics
),

scored_metrics AS (
    SELECT 
        bm.*,
        sb.*,

        -- Dynamic scoring logic using statistical baselines
        CASE WHEN avg_exec_time_sec > exec_time_high THEN 1 ELSE 0 END AS slow_query_flag,
        CASE WHEN success_rate_pct < success_rate_low THEN 1 ELSE 0 END AS low_success_flag,
        CASE WHEN credits_per_query > high_cost_query THEN 1 ELSE 0 END AS high_cost_flag,
        CASE WHEN warehouses_used > 3 THEN 1 ELSE 0 END AS warehouse_sprawl_flag,
        CASE WHEN avg_bytes_per_query > large_scan_bytes THEN 1 ELSE 0 END AS large_scan_flag,
        CASE WHEN total_queries < 10 THEN 1 ELSE 0 END AS idle_user_flag,
        CASE WHEN total_queries > 10000 THEN 1 ELSE 0 END AS overloaded_user_flag,

        (
            CASE WHEN avg_exec_time_sec > exec_time_high THEN 1 ELSE 0 END +
            CASE WHEN success_rate_pct < success_rate_low THEN 1 ELSE 0 END +
            CASE WHEN credits_per_query > high_cost_query THEN 1 ELSE 0 END +
            CASE WHEN warehouses_used > 3 THEN 1 ELSE 0 END +
            CASE WHEN avg_bytes_per_query > large_scan_bytes THEN 1 ELSE 0 END
        ) AS optimization_score
    FROM base_metrics bm
    CROSS JOIN statistical_baselines sb
),

final_output AS (
    SELECT 
        *,
        CASE
            WHEN idle_user_flag = 1 THEN 'Low activity user – review access/role'
            WHEN overloaded_user_flag = 1 THEN 'High volume user – check for automation/misuse'
            WHEN slow_query_flag = 1 AND large_scan_flag = 1 THEN 'Review large scans and optimize joins/filters'
            WHEN slow_query_flag = 1 THEN 'Review long-running queries'
            WHEN low_success_flag = 1 THEN 'Improve query success – review failure causes'
            WHEN high_cost_flag = 1 THEN 'High-cost user – reduce warehouse size or optimize logic'
            WHEN warehouse_sprawl_flag = 1 THEN 'Too many warehouses – consolidate usage'
            WHEN large_scan_flag = 1 THEN 'Optimize queries to reduce scanned data'
            ELSE 'User appears optimized – monitor only'
        END AS primary_recommendation,

        CASE 
            WHEN optimization_score >= 4 THEN ROUND(total_credits * 0.35, 2)
            WHEN optimization_score = 3 THEN ROUND(total_credits * 0.25, 2)
            WHEN optimization_score = 2 THEN ROUND(total_credits * 0.15, 2)
            WHEN optimization_score = 1 THEN ROUND(total_credits * 0.05, 2)
            ELSE 0
        END AS estimated_monthly_savings
    FROM scored_metrics
)

-- ✅ Final Enterprise Output
SELECT 
    user_name,
    role_name,
    client_type,
    total_queries,
    total_credits,
    avg_exec_time_sec,
    median_exec_time_sec,
    success_rate_pct,
    warehouses_used,
    active_days,
    last_active_day,
    ROUND(avg_bytes_per_query / 1073741824, 2) AS avg_gb_scanned,
    avg_rows_per_query,
    credits_per_query,
    credits_per_row,
    optimization_score,
    primary_recommendation,
    estimated_monthly_savings
FROM final_output
WHERE 
    total_credits > 50
    AND optimization_score >= 2
ORDER BY total_credits DESC, optimization_score DESC;


"""
}