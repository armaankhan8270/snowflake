query_payload = {
    "title": "User Cost Efficiency Risk Report",#all users 
    "description": "Analyzes cost per GB, scan-result efficiency, and success rate to identify high-cost, low-efficiency users in Snowflake.",
    "sql_query": """
WITH base_metrics AS (
  SELECT 
    qh.user_name,
    ROUND(SUM(wh.credits_used_compute * 0.00056), 2) AS total_cost_usd,
    COUNT(DISTINCT qh.query_id) AS total_queries,
    SUM(qh.bytes_scanned) AS bytes_scanned,
    SUM(qh.bytes_written) AS bytes_written,
    ROUND(AVG(qh.execution_time_ms), 2) AS avg_execution_time_ms,
    ROUND(AVG(qh.queued_provisioning_time_ms + qh.queued_repair_time_ms + qh.queued_overload_time_ms), 2) AS avg_queue_time_ms,
    SUM(CASE WHEN qh.execution_status = 'SUCCESS' THEN 1 ELSE 0 END) AS success_count,
    COUNT(*) AS total_execs
  FROM snowflake.account_usage.query_history qh
  JOIN snowflake.account_usage.warehouse_metering_history wh 
    ON qh.warehouse_name = wh.warehouse_name 
   AND qh.start_time BETWEEN wh.start_time AND wh.start_time + INTERVAL '1 hour'
  WHERE qh.start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
    {% if object_filter != 'ALL' %}
    AND qh.user_name = '{{ object_filter }}'
    {% endif %}
    AND qh.user_name IS NOT NULL
  GROUP BY qh.user_name
  HAVING COUNT(DISTINCT qh.query_id) >= 10
),

user_efficiency AS (
  SELECT 
    *,
    ROUND(bytes_scanned / POWER(1024, 3), 2) AS total_gb_scanned,
    ROUND(bytes_written / POWER(1024, 3), 2) AS total_gb_written,
    ROUND(CASE 
      WHEN bytes_scanned > 0 THEN (bytes_written / NULLIF(bytes_scanned, 0)) * 100
      ELSE 0
    END, 2) AS result_efficiency_pct,
    ROUND(CASE 
      WHEN bytes_scanned > 0 THEN total_cost_usd / NULLIF(bytes_scanned / POWER(1024, 3), 0)
      ELSE NULL
    END, 2) AS cost_per_gb_processed,
    ROUND((success_count * 100.0 / NULLIF(total_execs, 0)), 2) AS success_rate_pct
  FROM base_metrics
),

efficiency_quartiles AS (
  SELECT 
    *,
    NTILE(4) OVER (ORDER BY cost_per_gb_processed DESC NULLS LAST) AS cost_efficiency_quartile,
    NTILE(4) OVER (ORDER BY result_efficiency_pct ASC NULLS LAST) AS result_efficiency_quartile,
    NTILE(4) OVER (ORDER BY total_cost_usd DESC) AS cost_quartile
  FROM user_efficiency
)

SELECT 
  user_name,
  total_cost_usd,
  cost_per_gb_processed,
  result_efficiency_pct,
  total_queries,
  success_rate_pct,
  total_gb_scanned,
  total_gb_written,
  avg_execution_time_ms,
  avg_queue_time_ms,

  -- Optimization Risk Score
  (cost_efficiency_quartile + result_efficiency_quartile + 
   CASE WHEN success_rate_pct < 90 THEN 2 ELSE 0 END) AS optimization_risk_score,

  -- Classification
  CASE 
    WHEN cost_efficiency_quartile = 4 AND result_efficiency_quartile >= 3 THEN 'HIGH_COST_LOW_EFFICIENCY'
    WHEN cost_quartile = 4 AND result_efficiency_pct < 50 THEN 'HIGH_COST_POOR_RESULTS'
    WHEN cost_per_gb_processed > 10 AND success_rate_pct < 85 THEN 'INEFFICIENT_EXECUTION'
    WHEN total_cost_usd > 1000 AND result_efficiency_pct < 30 THEN 'WASTE_GENERATOR'
    ELSE 'ACCEPTABLE'
  END AS user_classification

FROM efficiency_quartiles
ORDER BY optimization_risk_score DESC, total_cost_usd DESC;
"""
}
business_value_query = {
    "title": "User Business Value vs Cost Matrix",#all users
    "description": "Classifies Snowflake users by business value score vs cost impact to identify optimization priorities.",
    "sql_query": """
WITH user_business_metrics AS (
    SELECT 
        qh.user_name,
        
        -- Cost Impact
        ROUND(SUM(wh.credits_used_compute * 0.00056), 2) AS total_cost_usd,
        COUNT(DISTINCT qh.query_id) AS total_queries,
        
        -- Business Value Indicators
        COUNT(DISTINCT qh.database_name) AS databases_accessed,
        COUNT(DISTINCT qh.schema_name) AS schemas_accessed,
        COUNT(DISTINCT DATE_TRUNC('day', qh.start_time)) AS active_days,
        COUNT(DISTINCT qh.warehouse_name) AS warehouses_used,
        ROUND(AVG(LENGTH(qh.query_text)), 1) AS avg_query_length,
        COUNT(DISTINCT qh.query_type) AS query_types_used,
        
        -- Data Processing
        ROUND(SUM(qh.bytes_scanned) / POWER(1024, 3), 2) AS total_gb_processed,
        ROUND(SUM(qh.bytes_written) / POWER(1024, 3), 2) AS total_gb_output,
        
        -- Collaboration
        SUM(CASE WHEN qh.query_type IN ('CREATE_TABLE', 'CREATE_VIEW', 'CREATE_MATERIALIZED_VIEW') THEN 1 ELSE 0 END) AS collaborative_queries,
        
        -- Consistency
        ROUND(STDDEV(EXTRACT(EPOCH FROM qh.start_time)), 2) AS usage_consistency,
        
        -- Success Rate
        ROUND((SUM(CASE WHEN qh.execution_status = 'SUCCESS' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0)), 2) AS success_rate
        
    FROM snowflake.account_usage.query_history qh
    JOIN snowflake.account_usage.warehouse_metering_history wh 
      ON qh.warehouse_name = wh.warehouse_name 
     AND qh.start_time BETWEEN wh.start_time AND wh.start_time + INTERVAL '1 hour'
    WHERE qh.start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
      {% if object_filter != 'ALL' %}
      AND qh.user_name = '{{ object_filter }}'
      {% endif %}
      AND qh.user_name IS NOT NULL
    GROUP BY qh.user_name
    HAVING COUNT(DISTINCT qh.query_id) >= 10
),

value_scoring AS (
    SELECT 
        *,
        LEAST(
            ((databases_accessed * 5) + 
             (schemas_accessed * 3) + 
             (LEAST(active_days, 30) * 2) + 
             (warehouses_used * 4) + 
             (LEAST(avg_query_length / 100, 20)) + 
             (query_types_used * 8) + 
             (LEAST(total_gb_processed, 100) * 0.5) + 
             (collaborative_queries * 10) + 
             (CASE WHEN success_rate > 95 THEN 15 ELSE success_rate * 0.15 END)
            ), 
            100
        ) AS business_value_score,
        
        LEAST(
            (total_cost_usd * 0.1) + 
            (LEAST(total_queries / 10, 30)) + 
            (LEAST(total_gb_processed * 0.5, 40)),
            100
        ) AS cost_impact_score
    FROM user_business_metrics
),

quadrant_classification AS (
    SELECT 
        *,
        CASE 
            WHEN business_value_score >= 50 AND cost_impact_score >= 50 THEN 'HIGH_VALUE_HIGH_COST'
            WHEN business_value_score >= 50 AND cost_impact_score < 50 THEN 'HIGH_VALUE_LOW_COST'
            WHEN business_value_score < 50 AND cost_impact_score >= 50 THEN 'LOW_VALUE_HIGH_COST'
            ELSE 'LOW_VALUE_LOW_COST'
        END AS user_quadrant,
        
        CASE 
            WHEN business_value_score < 50 AND cost_impact_score >= 50 THEN 100
            WHEN business_value_score >= 50 AND cost_impact_score >= 50 THEN 60
            WHEN business_value_score < 50 AND cost_impact_score < 50 THEN 40
            ELSE 20
        END AS optimization_priority
    FROM value_scoring
)

SELECT 
    user_name,
    total_cost_usd,
    total_queries,
    ROUND(business_value_score, 2) AS business_value_score,
    ROUND(cost_impact_score, 2) AS cost_impact_score,
    user_quadrant,
    optimization_priority,
    
    CASE 
        WHEN user_quadrant = 'LOW_VALUE_HIGH_COST' THEN 'IMMEDIATE_OPTIMIZATION_REQUIRED'
        WHEN user_quadrant = 'HIGH_VALUE_HIGH_COST' THEN 'CAREFUL_OPTIMIZATION_PRESERVE_VALUE'
        WHEN user_quadrant = 'LOW_VALUE_LOW_COST' THEN 'MONITOR_FOR_GROWTH'
        ELSE 'MAINTAIN_CURRENT_STATE'
    END AS recommendation,
    
    databases_accessed,
    active_days,
    success_rate,
    collaborative_queries

FROM quadrant_classification
ORDER BY optimization_priority DESC, cost_impact_score DESC;
"""
}
waste_analysis_query = {
    "title": "User Query Waste Analysis",#all users 
    "description": "Detects query inefficiencies: queue time, scan waste, failure cost, redundancy, and time-of-day usage.",
    "sql_query": """
WITH user_waste_analysis AS (
    SELECT 
        qh.user_name,

        -- Compute Inefficiency: Time spent queued vs executing
        AVG(
            CASE 
                WHEN qh.execution_time_ms > 0 
                THEN (qh.queued_provisioning_time_ms + qh.queued_repair_time_ms + qh.queued_overload_time_ms) / qh.execution_time_ms 
                ELSE NULL 
            END
        ) AS avg_queue_to_execution_ratio,

        -- Scan Waste: Reading far more than written (ignore small scans)
        AVG(
            CASE 
                WHEN qh.bytes_written > 10*1024*1024 AND qh.bytes_scanned > 10*1024*1024
                THEN qh.bytes_scanned / NULLIF(qh.bytes_written, 0)
                ELSE NULL 
            END
        ) AS avg_scan_to_result_ratio,

        -- Failure Waste: Failed query credits as % of total
        (SUM(CASE WHEN qh.execution_status != 'SUCCESS' THEN wh.credits_used_compute ELSE 0 END) / 
         NULLIF(SUM(wh.credits_used_compute), 0)) * 100 AS failed_query_cost_pct,

        -- Redundancy: Repeating same query too often (avoid penalizing scheduled jobs)
        COUNT(DISTINCT CONCAT(qh.query_text_checksum, DATE_TRUNC('minute', qh.start_time))) 
        / NULLIF(COUNT(qh.query_id), 0) AS adjusted_query_uniqueness_ratio,

        -- Business Hour Usage: Queries executed between 9 AM - 5 PM (in IST)
        SUM(
            CASE 
              WHEN HOUR(CONVERT_TIMEZONE('UTC', 'Asia/Kolkata', qh.start_time)) BETWEEN 9 AND 17 
              THEN wh.credits_used_compute 
              ELSE 0 
            END
        ) / NULLIF(SUM(wh.credits_used_compute), 0) AS business_hour_usage_pct,

        -- Total Cost
        ROUND(SUM(wh.credits_used_compute * 0.00056), 2) AS total_cost_usd

    FROM snowflake.account_usage.query_history qh
    JOIN snowflake.account_usage.warehouse_metering_history wh 
        ON qh.warehouse_name = wh.warehouse_name 
       AND qh.start_time BETWEEN wh.start_time AND wh.start_time + INTERVAL '1 hour'

    WHERE qh.start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
      {% if object_filter != 'ALL' %}
      AND qh.user_name = '{{ object_filter }}'
      {% endif %}
      AND qh.user_name IS NOT NULL

    GROUP BY qh.user_name
    HAVING COUNT(qh.query_id) >= 10
),

waste_scores AS (
    SELECT 
        user_name,

        -- Normalized waste scores (0–100 range)
        LEAST(avg_queue_to_execution_ratio * 100, 100) AS queue_waste_score,
        LEAST(GREATEST((avg_scan_to_result_ratio - 1) * 10, 0), 100) AS scan_waste_score,
        COALESCE(failed_query_cost_pct, 0) AS failure_waste_score,
        GREATEST((1 - adjusted_query_uniqueness_ratio) * 100, 0) AS redundancy_waste_score,
        GREATEST((business_hour_usage_pct - 0.6) * 250, 0) AS timing_waste_score,

        total_cost_usd,

        -- Final composite score
        (
            LEAST(avg_queue_to_execution_ratio * 100, 100) +
            LEAST(GREATEST((avg_scan_to_result_ratio - 1) * 10, 0), 100) +
            COALESCE(failed_query_cost_pct, 0) +
            GREATEST((1 - adjusted_query_uniqueness_ratio) * 100, 0) +
            GREATEST((business_hour_usage_pct - 0.6) * 250, 0)
        ) / 5 AS overall_waste_score
)

SELECT 
    user_name,
    ROUND(queue_waste_score, 1) AS queue_waste_score,
    ROUND(scan_waste_score, 1) AS scan_waste_score,
    ROUND(failure_waste_score, 1) AS failure_waste_score,
    ROUND(redundancy_waste_score, 1) AS redundancy_waste_score,
    ROUND(timing_waste_score, 1) AS timing_waste_score,
    ROUND(overall_waste_score, 1) AS overall_waste_score,
    total_cost_usd,

    -- Risk bucket
    CASE 
        WHEN overall_waste_score > 75 THEN 'CRITICAL_WASTE'
        WHEN overall_waste_score > 50 THEN 'HIGH_WASTE'
        WHEN overall_waste_score > 25 THEN 'MODERATE_WASTE'
        ELSE 'LOW_WASTE'
    END AS waste_category

FROM waste_scores
ORDER BY overall_waste_score DESC;
"""
}

user_cost_breakdown = {
    "title": "User Query Cost Breakdown",#singe users 
    "sql": """
    WITH user_cost_breakdown AS (
      SELECT 
        qh.user_name,
        COUNT(*) AS total_queries,
        SUM(wh.credits_used_compute * 0.00056) AS total_cost_usd,
        SUM(CASE WHEN qh.query_type = 'SELECT' THEN wh.credits_used_compute * 0.00056 ELSE 0 END) AS select_cost,
        SUM(CASE WHEN qh.query_type IN ('INSERT','UPDATE','DELETE') THEN wh.credits_used_compute * 0.00056 ELSE 0 END) AS dml_cost,
        SUM(CASE WHEN qh.query_type LIKE 'CREATE%' THEN wh.credits_used_compute * 0.00056 ELSE 0 END) AS ddl_cost,
        SUM(CASE WHEN qh.execution_status != 'SUCCESS' THEN wh.credits_used_compute * 0.00056 ELSE 0 END) AS failed_query_cost
      FROM query_history qh
      JOIN warehouse_metering_history wh 
        ON qh.warehouse_name = wh.warehouse_name 
        AND DATE_TRUNC('hour', qh.start_time) = wh.start_time
      WHERE qh.start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
        {% if object_filter != 'ALL' %}
        AND qh.user_name = '{{ object_filter }}'
        {% endif %}
        AND qh.user_name IS NOT NULL
      GROUP BY qh.user_name
    ),
    cost_percentages AS (
      SELECT *,
        ROUND((select_cost / NULLIF(total_cost_usd, 0)) * 100, 2) AS pct_select,
        ROUND((dml_cost / NULLIF(total_cost_usd, 0)) * 100, 2) AS pct_dml,
        ROUND((ddl_cost / NULLIF(total_cost_usd, 0)) * 100, 2) AS pct_ddl,
        ROUND((failed_query_cost / NULLIF(total_cost_usd, 0)) * 100, 2) AS pct_failed,
        ROUND(100 - (
          (select_cost + dml_cost + ddl_cost + failed_query_cost) / NULLIF(total_cost_usd, 0) * 100), 2
        ) AS pct_other
      FROM user_cost_breakdown
    )
    SELECT 
      user_name,
      total_queries,
      total_cost_usd,
      select_cost, pct_select,
      dml_cost, pct_dml,
      ddl_cost, pct_ddl,
      failed_query_cost, pct_failed,
      (total_cost_usd - (select_cost + dml_cost + ddl_cost + failed_query_cost)) AS other_cost,
      pct_other
    FROM cost_percentages
    ORDER BY total_cost_usd DESC;
    """
}
query_level_audit = {
    "title": "Query-Level Audit & Efficiency Tagging",#single user chart
    "sql": """
    WITH query_metrics AS (
      SELECT
        query_id,
        user_name,
        start_time,
        execution_status,
        execution_time_ms,
        total_elapsed_time,
        bytes_scanned / POWER(1024, 3) AS gb_scanned,
        bytes_written / POWER(1024, 3) AS gb_written,
        rows_produced,
        rows_inserted,
        rows_updated,
        rows_deleted,
        warehouse_name,
        query_type,
        error_code,
        error_message,
        CASE WHEN execution_status = 'SUCCESS' THEN 1 ELSE 0 END AS success_flag,
        wh.warehouse_size,
        wh.credits_used_compute * 0.00056 AS cost_usd
      FROM query_history qh
      JOIN warehouse_metering_history wh 
        ON qh.warehouse_name = wh.warehouse_name 
        AND DATE_TRUNC('hour', qh.start_time) = wh.start_time
      WHERE qh.start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
        {% if object_filter != 'ALL' %}
        AND qh.user_name = '{{ object_filter }}'
        {% endif %}
        AND qh.user_name IS NOT NULL
    )
    SELECT
      query_id,
      user_name,
      start_time,
      query_type,
      execution_time_ms,
      total_elapsed_time,
      gb_scanned,
      gb_written,
      rows_produced,
      rows_inserted,
      rows_updated,
      rows_deleted,
      cost_usd,
      execution_status,
      CASE 
        WHEN execution_status != 'SUCCESS' THEN 'FAILED'
        WHEN execution_time_ms > 60000 THEN 'SLOW'
        WHEN cost_usd > 0.10 THEN 'COSTLY'
        ELSE 'OPTIMAL'
      END AS efficiency_class
    FROM query_metrics
    ORDER BY cost_usd DESC;
    """
}
user_unoptimized_query = {
    "title": "High-Cost Unoptimized Users - Dynamic Benchmarking",#table 
    "sql": """
-- TABLE: High-Cost Unoptimized Users (Percentile-Based, Dynamic Thresholds)

WITH user_optimization_metrics AS (
    SELECT 
        user_name,
        COUNT(DISTINCT query_id) AS total_queries,
        SUM(credits_used) AS total_credits,
        AVG(execution_time/1000) AS avg_execution_time_sec,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS success_rate,
        COUNT(DISTINCT warehouse_name) AS warehouses_used,
        COUNT(DISTINCT DATE_TRUNC('day', start_time)) AS active_days,
        SUM(bytes_scanned) / COUNT(*) AS avg_bytes_per_query,
        SUM(rows_produced) / COUNT(*) AS avg_rows_per_query
    FROM snowflake.account_usage.query_history
    WHERE start_time BETWEEN '{{ start_date }}' AND '{{ end_date }}'
      {% if object_filter != 'ALL' %}
      AND user_name = '{{ object_filter }}'
      {% endif %}
      AND user_name IS NOT NULL
    GROUP BY user_name
),

percentile_thresholds AS (
    SELECT
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avg_execution_time_sec) AS p90_execution_time,
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY success_rate) AS p10_success_rate,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_credits / NULLIF(total_queries, 0)) AS p90_cost_per_query,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY warehouses_used) AS p90_warehouses_used,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avg_bytes_per_query) AS p90_bytes_scanned
    FROM user_optimization_metrics
),

scored_users AS (
    SELECT 
        u.*,
        t.p90_execution_time,
        t.p10_success_rate,
        t.p90_cost_per_query,
        t.p90_warehouses_used,
        t.p90_bytes_scanned,

        CASE WHEN u.avg_execution_time_sec > t.p90_execution_time THEN 1 ELSE 0 END AS slow_queries_flag,
        CASE WHEN u.success_rate < t.p10_success_rate THEN 1 ELSE 0 END AS low_success_flag,
        CASE WHEN (u.total_credits / NULLIF(u.total_queries, 0)) > t.p90_cost_per_query THEN 1 ELSE 0 END AS high_cost_per_query_flag,
        CASE WHEN u.warehouses_used > t.p90_warehouses_used THEN 1 ELSE 0 END AS warehouse_sprawl_flag,
        CASE WHEN u.avg_bytes_per_query > t.p90_bytes_scanned THEN 1 ELSE 0 END AS large_scan_flag,

        (
            CASE WHEN u.avg_execution_time_sec > t.p90_execution_time THEN 1 ELSE 0 END +
            CASE WHEN u.success_rate < t.p10_success_rate THEN 1 ELSE 0 END +
            CASE WHEN (u.total_credits / NULLIF(u.total_queries, 0)) > t.p90_cost_per_query THEN 1 ELSE 0 END +
            CASE WHEN u.warehouses_used > t.p90_warehouses_used THEN 1 ELSE 0 END +
            CASE WHEN u.avg_bytes_per_query > t.p90_bytes_scanned THEN 1 ELSE 0 END
        ) AS optimization_score
    FROM user_optimization_metrics u, percentile_thresholds t
)

SELECT 
    user_name,
    ROUND(total_credits, 2) AS total_credits,
    total_queries,
    ROUND(avg_execution_time_sec, 2) AS avg_execution_time_sec,
    ROUND(success_rate, 2) AS success_rate_pct,
    warehouses_used,
    active_days,
    ROUND(avg_bytes_per_query / 1073741824, 2) AS avg_gb_per_query,
    optimization_score,

    CASE 
        WHEN slow_queries_flag = 1 AND large_scan_flag = 1 THEN 'Optimize queries + Add filtering/indexing'
        WHEN slow_queries_flag = 1 THEN 'Review and optimize slow queries'
        WHEN low_success_flag = 1 THEN 'Investigate and fix failing queries'
        WHEN high_cost_per_query_flag = 1 THEN 'Reduce warehouse size or optimize queries'
        WHEN warehouse_sprawl_flag = 1 THEN 'Consolidate warehouse usage'
        WHEN large_scan_flag = 1 THEN 'Add filters and optimize data access'
        ELSE 'General optimization review'
    END AS primary_recommendation,

    CASE 
        WHEN optimization_score >= 3 THEN ROUND(total_credits * 0.4, 2)
        WHEN optimization_score = 2 THEN ROUND(total_credits * 0.25, 2)
        WHEN optimization_score = 1 THEN ROUND(total_credits * 0.15, 2)
        ELSE 0
    END AS estimated_monthly_savings

FROM scored_users
WHERE total_credits > 50 AND optimization_score >= 2
ORDER BY total_credits DESC, optimization_score DESC;
"""
}
user_profile_query = {
    "title": "User Deep Optimization Profile (Dynamic)",#table
    "sql": """
-- USER DEEP ANALYSIS PROFILE (ADAPTIVE VERSION)
-- Usage: Set parameter {{ user_name }}

WITH user_base_metrics AS (
    SELECT 
        user_name,
        COUNT(DISTINCT query_id) AS total_queries,
        COUNT(DISTINCT DATE_TRUNC('day', start_time)) AS active_days,
        COUNT(DISTINCT warehouse_name) AS warehouses_used,
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(credits_used) AS total_credits,
        SUM(execution_time / 1000) AS total_execution_time_sec,
        SUM(bytes_scanned) AS total_bytes_scanned,
        SUM(rows_produced) AS total_rows_produced,
        SUM(CASE WHEN error_code IS NULL THEN 1 ELSE 0 END) AS successful_queries,
        SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) AS failed_queries,
        SUM(CASE WHEN execution_time > 300000 THEN 1 ELSE 0 END) AS long_running_queries,
        SUM(CASE WHEN bytes_scanned > 1073741824 AND rows_produced < 1000 THEN 1 ELSE 0 END) AS inefficient_scans,
        SUM(CASE WHEN query_type = 'SELECT' THEN 1 ELSE 0 END) AS select_queries,
        SUM(CASE WHEN query_type IN ('INSERT', 'UPDATE', 'DELETE', 'MERGE') THEN 1 ELSE 0 END) AS dml_queries,
        MIN(start_time) AS first_query_date,
        MAX(start_time) AS last_query_date
    FROM snowflake.account_usage.query_history
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE())
      AND user_name = '{{ user_name }}'
    GROUP BY user_name
),

user_advanced_metrics AS (
    SELECT 
        ubm.*,
        ROUND(total_credits / NULLIF(total_queries, 0), 4) AS avg_credits_per_query,
        ROUND(total_execution_time_sec / NULLIF(total_queries, 0), 2) AS avg_execution_time_sec,
        ROUND(total_bytes_scanned / NULLIF(total_queries, 0) / 1073741824, 3) AS avg_gb_per_query,
        ROUND(total_rows_produced / NULLIF(total_queries, 0), 0) AS avg_rows_per_query,
        ROUND(successful_queries * 100.0 / NULLIF(total_queries, 0), 2) AS success_rate_pct,
        ROUND(long_running_queries * 100.0 / NULLIF(total_queries, 0), 2) AS long_query_pct,
        ROUND(inefficient_scans * 100.0 / NULLIF(total_queries, 0), 2) AS inefficient_scan_pct,
        ROUND(total_queries / NULLIF(active_days, 0), 1) AS avg_queries_per_day,
        ROUND(total_credits / NULLIF(active_days, 0), 2) AS avg_credits_per_day,
        ROUND(total_queries / NULLIF(total_sessions, 0), 1) AS avg_queries_per_session,
        CASE WHEN total_bytes_scanned > 0 THEN ROUND(total_rows_produced / (total_bytes_scanned / 1048576), 2) ELSE 0 END AS rows_per_mb_scanned,
        CASE WHEN total_rows_produced > 0 THEN ROUND(total_credits / total_rows_produced * 1000, 6) ELSE 0 END AS cost_per_1k_rows,
        ROUND(select_queries * 100.0 / NULLIF(total_queries, 0), 1) AS select_query_pct,
        ROUND(dml_queries * 100.0 / NULLIF(total_queries, 0), 1) AS dml_query_pct
    FROM user_base_metrics ubm
),

percentile_bounds AS (
    SELECT 
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY avg_execution_time_sec) AS p25_exec,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_execution_time_sec) AS p75_exec,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY avg_credits_per_query) AS p25_cost,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_credits_per_query) AS p75_cost,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY rows_per_mb_scanned) AS p25_eff,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY rows_per_mb_scanned) AS p75_eff
    FROM user_advanced_metrics
),

user_scoring AS (
    SELECT 
        uam.*,
        pb.*,

        GREATEST(0, LEAST(100,
            (success_rate_pct * 0.3) +
            (CASE WHEN avg_execution_time_sec <= pb.p25_exec THEN 25 
                  WHEN avg_execution_time_sec <= pb.p75_exec THEN 15 ELSE 5 END) +
            (CASE WHEN avg_credits_per_query <= pb.p25_cost THEN 20 
                  WHEN avg_credits_per_query <= pb.p75_cost THEN 15 ELSE 5 END) +
            (CASE WHEN rows_per_mb_scanned >= pb.p75_eff THEN 15 
                  WHEN rows_per_mb_scanned >= pb.p25_eff THEN 10 ELSE 5 END) +
            (CASE WHEN active_days >= 25 THEN 10 
                  WHEN active_days >= 15 THEN 8 ELSE 5 END)
        )) AS efficiency_score,

        CASE 
            WHEN total_credits > 500 AND efficiency_score < 50 THEN 'HIGH COST - CRITICAL OPTIMIZATION NEEDED'
            WHEN total_credits > 200 AND efficiency_score < 60 THEN 'MEDIUM COST - OPTIMIZATION REQUIRED'
            WHEN total_credits > 100 AND efficiency_score < 70 THEN 'MODERATE COST - IMPROVEMENT NEEDED'
            WHEN efficiency_score < 40 THEN 'LOW EFFICIENCY - TRAINING REQUIRED'
            WHEN total_credits > 300 AND efficiency_score >= 70 THEN 'HIGH VALUE - POWER USER'
            WHEN efficiency_score >= 80 THEN 'OPTIMAL - BEST PRACTICE USER'
            ELSE 'ACCEPTABLE - MONITOR'
        END AS user_classification,

        CASE 
            WHEN long_query_pct > 20 AND inefficient_scan_pct > 15 THEN 'Query Optimization + Data Access'
            WHEN long_query_pct > 20 THEN 'Query Performance'
            WHEN inefficient_scan_pct > 15 THEN 'Data Access Patterns'
            WHEN success_rate_pct < 85 THEN 'Query Reliability'
            WHEN avg_credits_per_query > pb.p75_cost THEN 'Cost Efficiency'
            WHEN warehouses_used > 5 THEN 'Resource Management'
            ELSE 'General Optimization'
        END AS primary_focus_area
    FROM user_advanced_metrics uam
    JOIN percentile_bounds pb ON TRUE
)

SELECT 
    user_name,
    user_classification,
    ROUND(efficiency_score, 1) AS efficiency_score,
    primary_focus_area,

    total_queries,
    active_days,
    warehouses_used,
    total_sessions,

    ROUND(total_credits, 2) AS total_credits,
    avg_credits_per_query,
    avg_credits_per_day,

    avg_execution_time_sec,
    success_rate_pct,
    long_query_pct,

    avg_gb_per_query,
    avg_rows_per_query,
    rows_per_mb_scanned,
    inefficient_scan_pct,
    cost_per_1k_rows,

    select_query_pct,
    dml_query_pct,
    avg_queries_per_day,
    avg_queries_per_session,

    CASE 
        WHEN user_classification LIKE '%CRITICAL%' THEN 'IMMEDIATE ACTION: Optimize queries, enable caching, tune warehouse usage'
        WHEN user_classification LIKE '%OPTIMIZATION REQUIRED%' THEN 'HIGH PRIORITY: Refactor slow and costly queries'
        WHEN user_classification LIKE '%IMPROVEMENT NEEDED%' THEN 'MEDIUM PRIORITY: Review filters, joins, and access patterns'
        WHEN user_classification LIKE '%TRAINING REQUIRED%' THEN 'TRAINING: Share SQL best practices'
        WHEN user_classification LIKE '%POWER USER%' THEN 'LEVERAGE: Include in performance reviews or mentor others'
        WHEN user_classification LIKE '%BEST PRACTICE%' THEN 'MAINTAIN: Promote as optimization example'
        ELSE 'NORMAL MONITORING: Keep an eye on trends'
    END AS detailed_recommendations,

    CASE 
        WHEN user_classification LIKE '%CRITICAL%' THEN ROUND(total_credits * 0.5, 2)
        WHEN user_classification LIKE '%OPTIMIZATION REQUIRED%' THEN ROUND(total_credits * 0.35, 2)
        WHEN user_classification LIKE '%IMPROVEMENT NEEDED%' THEN ROUND(total_credits * 0.25, 2)
        WHEN user_classification LIKE '%TRAINING REQUIRED%' THEN ROUND(total_credits * 0.4, 2)
        ELSE ROUND(total_credits * 0.1, 2)
    END AS estimated_monthly_savings,

    first_query_date,
    last_query_date,
    DATEDIFF('day', first_query_date, last_query_date) AS analysis_period_days

FROM user_scoring;
"""
}
