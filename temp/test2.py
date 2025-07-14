{
    "executive_summary_and_anomaly_detection": {
        "title": "Executive Summary & Anomaly Detection (The 'What's Broken Right Now?')",
        "description": "This section gives a high-level, immediate view of the most pressing issues.",
        "global_anomaly_alerts": {
            "description": "Automated alerts based on significant deviations from historical baselines for key metrics. This is what you want your FinOps team to see first thing.",
            "alerts": [
                {
                    "name": "Unusual Credit Spikes",
                    "description": "Identify users/warehouses whose daily credit consumption is >3σ from their 30-day average.",
                    "metric_example": "Daily credit consumption > 3 standard deviations from 30-day average for a user/warehouse.",
                    "recommendation": {
                        "summary": "User `[User_Name]` consumed `X` credits today, `Y%` above average. Investigate recent queries (Query IDs: `Q1, Q2`). Consider a per-user resource monitor.",
                        "action_type": "Resource Monitor / Query Optimization"
                    }
                },
                {
                    "name": "Rising Query Queue Times",
                    "description": "Warehouses showing a consistent increase in `QUEUED_OVERLOAD_TIME` over the last 72 hours, indicating approaching concurrency limits.",
                    "metric_example": "Consistent increase in `QUEUED_OVERLOAD_TIME` over 72 hours for a specific warehouse.",
                    "recommendation": {
                        "summary": "Warehouse `[WH_Name]` average queue time increased `Z%` in last 3 days. Recommend increasing `MAX_CLUSTER_COUNT` or reviewing auto-suspend for faster resume.",
                        "action_type": "Warehouse Configuration"
                    }
                },
                {
                    "name": "Persistent Remote Spilling",
                    "description": "Users or queries consistently spilling significant bytes to remote storage, signaling memory-intensive operations.",
                    "metric_example": "Consistent significant bytes spilled to remote storage by queries/users.",
                    "recommendation": {
                        "summary": "Query `[Query_ID]` by `[User_Name]` consistently spills `N` GB to remote. Review query plan for large joins/sorts. Consider larger warehouse or query re-write.",
                        "action_type": "Query Optimization / Warehouse Sizing"
                    }
                }
            ]
        }
    },
    "deep_dive_user_analytics": {
        "title": "Deep Dive User Analytics (The 'Who's Driving What Cost/Performance?')",
        "description": "This focuses on individual user behavior, as user habits are often the root cause.",
        "enhanced_user_centric_metrics": {
            "description": "These are not just aggregates but insightful ratios and trend indicators designed to flag specific Snowflake anti-patterns.",
            "metrics": [
                {
                    "name": "Credit Consumption Volatility Index (CCVI)",
                    "description": "A measure of how much a user's daily credit consumption deviates from their rolling average, adjusted for volume. High volatility (without explanation) suggests unpredictable spend.",
                    "formula": "STDDEV(DAILY_CREDITS) / AVG(DAILY_CREDITS) over a 30-day window. Multiply by AVG(DAILY_CREDITS) for volume weighting.",
                    "snowflake_wisdom": "Accounts for `AUTO_SUSPEND` and `AUTO_RESUME` behavior. High CCVI might mean frequent, short, small queries on a large warehouse that doesn't suspend fast enough.",
                    "conceptual_sql_snippet": """
                        WITH UserDailyCredits AS (
                            SELECT
                                USER_NAME,
                                TO_DATE(START_TIME) AS DAY,
                                SUM(CREDITS_USED) AS DAILY_CREDITS
                            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                            WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
                            GROUP BY 1, 2
                        ),
                        UserCreditStats AS (
                            SELECT
                                USER_NAME,
                                AVG(DAILY_CREDITS) AS AVG_CREDITS,
                                STDDEV(DAILY_CREDITS) AS STDDEV_CREDITS
                            FROM UserDailyCredits
                            GROUP BY 1
                        )
                        SELECT
                            d.USER_NAME,
                            ROUND(s.STDDEV_CREDITS / NULLIF(s.AVG_CREDITS, 0) * s.AVG_CREDITS, 2) AS CCVI -- Weighted by average
                        FROM UserCreditStats s
                        JOIN UserDailyCredits d ON s.USER_NAME = d.USER_NAME
                        QUALIFY ROW_NUMBER() OVER (PARTITION BY d.USER_NAME ORDER BY CCVI DESC) = 1 -- Get highest CCVI if daily
                        ORDER BY CCVI DESC;
                    """,
                    "actionable_insight": {
                        "summary": "Users with high CCVI. Recommendation: 'Review `AUTO_SUSPEND` settings on warehouses used by `[User_Name]`. Consider dedicated smaller warehouses for bursty ad-hoc queries, or implement a `resource monitor` with `NOTIFY`.'",
                        "tags": ["Cost Optimization", "Warehouse Management"]
                    }
                },
                {
                    "name": "Query Lifecycle Efficiency Score (QLES)",
                    "description": "Composite score reflecting a user's average efficiency across query compilation, queueing, and execution. Lower is better.",
                    "formula": "(AVG_COMPILATION_TIME + AVG_QUEUED_TIME + AVG_BLOCKED_TIME) / AVG_EXECUTION_TIME. Penalizes high overheads relative to actual work.",
                    "snowflake_wisdom": "Compilation time can indicate complex views or UDFs. Queue/blocked time indicates warehouse contention. This metric isolates pre-execution overhead from execution work.",
                    "conceptual_sql_snippet": """
                        SELECT
                            USER_NAME,
                            ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000, 2) AS AVG_TOTAL_SEC,
                            ROUND(AVG(COMPILATION_TIME) / 1000, 2) AS AVG_COMPILE_SEC,
                            ROUND(AVG(QUEUED_OVERLOAD_TIME + QUEUED_PROVISIONING_TIME + QUEUED_REPAIR_TIME) / 1000, 2) AS AVG_QUEUED_SEC,
                            ROUND(AVG(BLOCKED_TIME) / 1000, 2) AS AVG_BLOCKED_SEC,
                            ROUND(AVG(EXECUTION_TIME) / 1000, 2) AS AVG_EXEC_SEC,
                            -- QLES: (Overhead) / Execution
                            ROUND((AVG_COMPILE_SEC + AVG_QUEUED_SEC + AVG_BLOCKED_SEC) / NULLIF(AVG_EXEC_SEC, 0), 2) AS QLES
                        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
                        AND EXECUTION_STATUS = 'SUCCESS'
                        GROUP BY USER_NAME
                        HAVING AVG_TOTAL_SEC > 10 -- Focus on non-trivial queries
                        ORDER BY QLES DESC;
                    """,
                    "actionable_insight": {
                        "summary": "Users with high QLES. Recommendation: 'User `[User_Name]` has high QLES. Investigate queries with high `COMPILATION_TIME` (optimize complex views/UDFs). If `QUEUED_TIME` is high, analyze concurrent query patterns or increase `MAX_CLUSTER_COUNT`.'",
                        "tags": ["Performance Optimization", "Query Optimization", "Warehouse Configuration"]
                    }
                },
                {
                    "name": "Data Scan-to-Pruning Inefficiency Index (DSPII)",
                    "description": "Quantifies how much more data is scanned than strictly necessary due to poor predicate pushdown, lack of clustering, or inefficient joins.",
                    "formula": "SUM(BYTES_SCANNED) / NULLIF(SUM(BYTES_WRITTEN + BYTES_SENT_OVER_NETWORK), 0). Higher values mean more data is scanned but not used.",
                    "snowflake_wisdom": "Directly points to micro-partition pruning issues or full table scans when only a subset of data is needed.",
                    "conceptual_sql_snippet": """
                        SELECT
                            USER_NAME,
                            QUERY_ID,
                            ROUND(BYTES_SCANNED / POW(1024, 3), 2) AS SCANNED_GB,
                            ROUND((BYTES_WRITTEN + BYTES_SENT_OVER_NETWORK) / POW(1024, 3), 2) AS OUTPUT_GB,
                            ROUND(BYTES_SCANNED / NULLIF((BYTES_WRITTEN + BYTES_SENT_OVER_NETWORK), 0), 2) AS DSPII
                        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                        WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
                        AND EXECUTION_STATUS = 'SUCCESS'
                        AND SCANNED_GB > 100 -- Focus on large scans
                        ORDER BY DSPII DESC;
                    """,
                    "actionable_insight": {
                        "summary": "Queries/users with high DSPII. Recommendation: 'Query `[Query_ID]` by `[User_Name]` has a high DSPII. Analyze `QUERY_PLAN`. Consider `CLUSTERING KEYS` on source tables, optimize `WHERE` clauses for better pruning, or use `MATERIALIZED VIEWS` for aggregated data.'",
                        "tags": ["Cost Optimization", "Performance Optimization", "Data Modeling"]
                    }
                },
                {
                    "name": "Warehouse Size Over-Provisioning Index (WSPI)",
                    "description": "Identifies users who are consistently running small/short queries on warehouses significantly larger than required, leading to idle credits.",
                    "formula": "(Credits consumed on large WH with short queries) / (Total credits).",
                    "snowflake_wisdom": "Leverages `WAREHOUSE_SIZE`, `TOTAL_ELAPSED_TIME`, and `CREDITS_USED`.",
                    "conceptual_sql_snippet": """
                        SELECT
                            QH.USER_NAME,
                            WH.WAREHOUSE_SIZE,
                            SUM(QH.CREDITS_USED) AS CREDITS_ON_WH_SIZE,
                            COUNT(CASE WHEN QH.TOTAL_ELAPSED_TIME < 60000 THEN 1 ELSE NULL END) AS SHORT_QUERY_COUNT,
                            COUNT(*) AS TOTAL_QUERY_COUNT,
                            ROUND(SUM(CASE WHEN QH.TOTAL_ELAPSED_TIME < 60000 THEN QH.CREDITS_USED ELSE 0 END) / NULLIF(SUM(QH.CREDITS_USED),0), 2) AS PCT_CREDITS_FROM_SHORT_QUERIES
                        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY QH
                        JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES WH ON QH.WAREHOUSE_ID = WH.WAREHOUSE_ID
                        WHERE QH.START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
                        AND WH.WAREHOUSE_SIZE IN ('MEDIUM', 'LARGE', 'X-LARGE') -- Focus on larger warehouses
                        GROUP BY 1, 2
                        HAVING CREDITS_ON_WH_SIZE > 10 AND PCT_CREDITS_FROM_SHORT_QUERIES > 0.5 -- Significant spend on large WH with many short queries
                        ORDER BY PCT_CREDITS_FROM_SHORT_QUERIES DESC;
                    """,
                    "actionable_insight": {
                        "summary": "Users with high WSPI. Recommendation: 'User `[User_Name]` frequently uses `[Warehouse_Size]` for short queries. Consider assigning them to an `X-SMALL` or `SMALL` warehouse for their default operations, or configuring `AUTO_SUSPEND` to a very low value (e.g., 60 seconds) on the larger warehouse.'",
                        "tags": ["Cost Optimization", "Warehouse Sizing"]
                    }
                }
            ]
        },
        "visualizations": {
            "title": "Visualizations (Smarter Charts)",
            "charts": [
                {
                    "name": "User Credit Consumption & Forecast",
                    "type": "Line + Prediction Plot",
                    "description": "Not just 'what happened,' but 'what's likely to happen' and 'what's unusual.' Helps FinOps plan.",
                    "axes": {
                        "x_axis": "Date",
                        "y_axis": "Daily Credits Consumed"
                    },
                    "series": ["Actual Daily Credits", "7-Day Rolling Average", "30-Day Rolling Average", "Linear Regression/ARIMA Forecast (next 7-14 days)"],
                    "features": ["Confidence Intervals", "Anomaly Markers (e.g., 2-sigma deviation)"]
                },
                {
                    "name": "User Query Performance Distribution",
                    "type": "Violin Plot",
                    "description": "Quickly spot users with a wide range of query performance (inconsistent behavior) or consistently slow queries (systemic issues). Better than just an average.",
                    "axes": {
                        "x_axis": "User Name",
                        "y_axis": "Query Execution Time (log scale)"
                    },
                    "plot_features": ["Distribution Shape", "Median Line", "75th/95th Percentile Lines"]
                },
                {
                    "name": "Top N User Cost Drivers",
                    "type": "Treemap",
                    "description": "Visually identifies which users are costing the most, on which warehouses, and for what type of operations, highlighting where contention is happening.",
                    "hierarchy": ["User", "Warehouse", "Query Tag/Statement Type (e.g., SELECT, INSERT)"],
                    "sizing": "Credits Used",
                    "coloring": "Average Query Queue Time (heatmap for contention)"
                }
            ]
        }
    },
    "predictive_and_prescriptive_recommendations": {
        "title": "Predictive & Prescriptive Recommendations (The 'How to Fix & Prevent?')",
        "description": "This is the most critical section for enterprise value. It moves from diagnosis to actionable strategy.",
        "recommendations_table": {
            "columns": [
                "Recommendation ID",
                "User / Warehouse / Table",
                "Primary Issue Identified",
                "Detailed Analysis & Root Cause",
                "Prescriptive Action (SQL/Policy)",
                "Estimated Impact (Credits/Performance)",
                "Priority (High/Medium/Low)"
            ],
            "rows": [
                {
                    "recommendation_id": "R1",
                    "target": "User: `analytics_user_01`",
                    "primary_issue": "High Spill-to-Remote Escalation",
                    "detailed_analysis_root_cause": "User's `SELECT` queries on `SALES_FACT` table increasingly spill to remote storage (trend: +50% week-over-week). Query profiles show large joins and sorts. No clustering key on `SALES_FACT`.",
                    "prescriptive_action": "`ALTER TABLE SALES_FACT CLUSTER BY (ORDER_DATE, CUSTOMER_ID);` AND `CREATE MATERIALIZED VIEW MV_SALES_AGG AS SELECT ORDER_DATE, SUM(SALES) FROM SALES_FACT GROUP BY 1;` Advise user to use MV.",
                    "estimated_impact": "~15% credit reduction, `2x` query speedup for common aggregates.",
                    "priority": "HIGH"
                },
                {
                    "recommendation_id": "R2",
                    "target": "WH: `REPORTING_WH`",
                    "primary_issue": "Peak Hour Queueing",
                    "detailed_analysis_root_cause": "`REPORTING_WH` experiences `>2 min` average `QUEUED_OVERLOAD_TIME` between 9 AM - 11 AM daily. `MAX_CLUSTER_COUNT` is set to 1. Concurrent query count frequently exceeds 8 during this period.",
                    "prescriptive_action": "`ALTER WAREHOUSE REPORTING_WH SET MIN_CLUSTER_COUNT = 1 MAX_CLUSTER_COUNT = 3;` Configure resource monitor: `ALTER RESOURCE MONITOR RP_MONITOR SET NOTIFY_USERS = ('finops_admin') THRESHOLD 90% TYPE ALL;`",
                    "estimated_impact": "~50% reduction in queue time, improved user experience.",
                    "priority": "HIGH"
                },
                {
                    "recommendation_id": "R3",
                    "target": "User: `dev_user_03`",
                    "primary_issue": "Inefficient Ad-hoc Query Pattern",
                    "detailed_analysis_root_cause": "`dev_user_03` frequently runs `SELECT *` from large tables, followed by complex `GROUP BY`s, leading to high `BYTES_SCANNED` and `COMPILATION_TIME`. `RESULT_SCAN` is rarely leveraged.",
                    "prescriptive_action": "Provide training on `SELECT` specific columns, using `WITH` clauses for complex logic, and understanding `RESULT_CACHE`. Share `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` patterns showing their least efficient queries.",
                    "estimated_impact": "~20% credit reduction, `1.5x` query speedup for specific patterns.",
                    "priority": "MEDIUM"
                },
                {
                    "recommendation_id": "R4",
                    "target": "Table: `CUSTOMER_RAW`",
                    "primary_issue": "Lack of Effective Pruning",
                    "detailed_analysis_root_cause": "Queries accessing `CUSTOMER_RAW` by `REGION` or `SIGNUP_DATE` scan full partitions. No clustering key defined. High `BYTES_SCANNED` across many users.",
                    "prescriptive_action": "`ALTER TABLE CUSTOMER_RAW CLUSTER BY (REGION, SIGNUP_DATE);` Monitor `AUTOMATIC_CLUSTERING`.",
                    "estimated_impact": "~30% reduction in scan costs for relevant queries.",
                    "priority": "MEDIUM"
                },
                {
                    "recommendation_id": "R5",
                    "target": "WH: `ETL_LOAD_WH`",
                    "primary_issue": "Suboptimal Auto-Suspend",
                    "detailed_analysis_root_cause": "`ETL_LOAD_WH` runs a batch load once every 4 hours, but `AUTO_SUSPEND` is set to 600 seconds (10 minutes). The warehouse stays active unnecessarily between loads.",
                    "prescriptive_action": "`ALTER WAREHOUSE ETL_LOAD_WH SET AUTO_SUSPEND = 60;` (1 minute).",
                    "estimated_impact": "~10% credit reduction (daily).",
                    "priority": "LOW"
                }
            ]
        },
        "ai_driven_anomaly_root_cause_analysis_resolution": {
            "title": "AI-Driven Anomaly Root Cause Analysis & Resolution (Future State / Advanced)",
            "concept": "Instead of just flagging an anomaly, the system attempts to infer the root cause.",
            "logic_steps": [
                "1. **Identify Anomaly**: E.g., Credit spike for `User A`.",
                "2. **Contextualize**: What warehouses did `User A` use? Were there new/changed queries (`QUERY_HASH`)? Were there large `BYTES_SCANNED`/`BYTES_WRITTEN`? Did `QUEUED_OVERLOAD_TIME` increase on those warehouses? Any `FAILED` or `CANCELED` queries consuming credits?",
                "3. **Pattern Matching**: 'If `Credit Spike` AND `New Query Hash` AND `High Bytes Scanned` THEN `New Inefficient Query`.'",
                "4. **Prescribe**: 'New query `QID` by `User A` is inefficient. See `QUERY_PROFILE_JSON` for details. Suggest optimizing join order or adding filters.'"
            ]
        }
    },
    "implementation_considerations_for_production_readiness": {
        "title": "Implementation Considerations for Production Readiness:",
        "considerations": [
            {
                "name": "Data Latency",
                "details": "`ACCOUNT_USAGE` views have a latency of up to 45 minutes to 3 hours. Critical for real-time alerts. For production, consider using `QUERY_HISTORY` and `WAREHOUSE_METERING_HISTORY` tables directly in a more frequent polling manner, or leveraging Snowpipe for event-driven processing if custom logging is implemented."
            },
            {
                "name": "Role-Based Access",
                "details": "The solution should support granular access, so FinOps sees cost, Data Engineers see query plans, and Developers see their specific query recommendations."
            },
            {
                "name": "Historical Baselines",
                "details": "Robust anomaly detection requires sufficient historical data (90-180 days is ideal)."
            },
            {
                "name": "Customization",
                "details": "Allow organizations to define their 'value' metrics (e.g., is data loaded more valuable than data scanned?), thresholds for 'high' cost, and specific business hours for peak analysis."
            },
            {
                "name": "Integration",
                "details": "Output recommendations in formats consumable by alert systems (PagerDuty, Slack), ticketing systems (Jira), or even automated workflow tools (Terraform for warehouse scaling)."
            },
            {
                "name": "Security",
                "details": "Ensure queries against `ACCOUNT_USAGE` are run by a dedicated, minimal-privilege role."
            }
        ]
    }
}