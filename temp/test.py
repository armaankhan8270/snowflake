{
    "DASHBOARD_NAME": "User FinOps Dashboard",
    "DESCRIPTION": "Dedicated dashboard for analyzing and optimizing Snowflake user behavior and associated costs.",
    "FILTER_MECHANISM": {
        "PRIMARY_FILTER": {
            "NAME": "User Name Selector",
            "TYPE": "Dropdown/Search Box",
            "OPTIONS": [
                "--- ALL USERS ---",
                "user_john_doe",
                "user_jane_smith",
                # ... populate with actual user names from ACCOUNT_USAGE.USERS
            ],
            "DEFAULT_SELECTION": "--- ALL USERS ---"
        },
        "SECONDARY_FILTERS": [
            {
                "NAME": "Date Range",
                "TYPE": "Date Picker",
                "OPTIONS": ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom"],
                "DEFAULT": "Last 30 Days"
            },
            {
                "NAME": "Warehouse Name",
                "TYPE": "Multi-Select Dropdown",
                "OPTIONS": ["ANALYTICS_WH", "ETL_WH", "REPORTING_WH"],
                "DEFAULT": "All"
            }
        ]
    },

    "ALL_USERS_DASHBOARD": {
        "VIEW_TITLE": "All Users: Strategic User Cost & Efficiency Overview",
        "PURPOSE": (
            "Provides a holistic, account-level perspective to identify top cost drivers across "
            "the organization, spot systemic user-driven inefficiencies, and highlight immediate anomalies. "
            "Helps prioritize FinOps efforts effectively."
        ),
        "SECTIONS": [
            {
                "SECTION_TITLE": "Overall User Consumption KPIs",
                "DISPLAY_TYPE": "KPIs (Key Performance Indicators)",
                "KPI_LIST": [
                    {
                        "METRIC_NAME": "Total Credits Consumed by Users",
                        "TIME_PERIOD": "Last 30 Days",
                        "DESCRIPTION": "Aggregated sum of credits directly attributable to user queries.",
                        "ENTERPRISE_TOUCH": "Includes MoM/WoW growth percentage."
                    },
                    {
                        "METRIC_NAME": "Average Credits per Active User",
                        "TIME_PERIOD": "Last 30 Days",
                        "DESCRIPTION": "Total user credits divided by the number of distinct active users.",
                        "ENTERPRISE_TOUCH": "Indicates per-user efficiency and scalability; rising trend signals increasing individual consumption."
                    },
                    {
                        "METRIC_NAME": "Aggregate User Cloud Services Credit Ratio",
                        "DESCRIPTION": "Percentage of total user-attributable credits spent on Cloud Services.",
                        "WHY_IMPORTANT": "High or increasing ratio suggests pervasive inefficiencies (e.g., too many small queries, redundant metadata calls).",
                        "ENTERPRISE_TOUCH": "Benchmark against internal target (e.g., <10%)."
                    }
                ]
            },
            {
                "SECTION_TITLE": "Top User Contribution & Anomaly Detection",
                "DISPLAY_TYPE": "Comparative Charts & Tables",
                "COMPONENTS": [
                    {
                        "NAME": "Top N Users by Total Credit Consumption",
                        "CHART_TYPE": "Segmented Bar Chart",
                        "METRICS": ["TOTAL_CREDITS_USED", "COMPUTE_CREDITS", "CLOUD_SERVICES_CREDITS"],
                        "DESCRIPTION": "Identifies primary cost drivers among users; segments bars to show compute vs. cloud services spend.",
                        "ENTERPRISE_TOUCH": "Allows sorting, includes sparkline for 7-day trend, and drill-down action to 'Single User' view."
                    },
                    {
                        "NAME": "Top N Users by Credit Consumption Volatility Index (CCVI)",
                        "CHART_TYPE": "Table with Sparklines/Heatmap",
                        "METRICS": ["USER_NAME", "CCVI Score", "Average Daily Credits"],
                        "DESCRIPTION": "Pinpoints users with erratic, potentially wasteful usage patterns (e.g., leaving large warehouses on sporadically).",
                        "ENTERPRISE_TOUCH": "Filters to show users above a specific CCVI threshold and minimum average credits for impactful outliers."
                    },
                    {
                        "NAME": "User Efficiency Matrix",
                        "CHART_TYPE": "Scatter Plot",
                        "X_AXIS": "TOTAL_CREDITS_USED",
                        "Y_AXIS": "AVG_QLES (higher is better)",
                        "BUBBLE_SIZE": "NUMBER_OF_QUERIES",
                        "DESCRIPTION": "Visually segments users into quadrants (e.g., high cost/low efficiency, low cost/high efficiency).",
                        "ENTERPRISE_TOUCH": "Can color-code bubbles by user role or department to identify team behaviors."
                    },
                    {
                        "NAME": "Cost of Failed/Canceled Queries by User",
                        "CHART_TYPE": "Bar Chart or Treemap",
                        "METRICS": ["USER_NAME", "TOTAL_CREDITS_WASTED (Cloud Services)"],
                        "DESCRIPTION": "Direct identification of pure waste and users who may need help with query debugging or data understanding."
                    }
                ]
            },
            {
                "SECTION_TITLE": "Systemic User-Driven Inefficiencies",
                "DISPLAY_TYPE": "Diagnostic Tables",
                "COMPONENTS": [
                    {
                        "NAME": "Top N Inefficient Query Hashes Across All Users",
                        "TABLE_COLUMNS": ["QUERY_HASH", "SAMPLE_QUERY_TEXT", "TOTAL_CREDITS_USED", "EXECUTION_COUNT", "AVG_OVERHEAD_RATIO"],
                        "DESCRIPTION": "Identifies common, recurring problematic SQL patterns executed by multiple users, suggesting shared best practices or code library updates.",
                        "ENTERPRISE_TOUCH": "Includes direct links to Snowflake UI's Query Profile for sample Query IDs."
                    },
                    {
                        "NAME": "Top N Tables/Views Causing Inefficient Scans by Users",
                        "TABLE_COLUMNS": ["TABLE_NAME", "DATABASE_SCHEMA", "AVG_PARTITION_SCAN_RATIO", "TOTAL_BYTES_SCANNED_BY_ALL_USERS_ON_THIS_TABLE"],
                        "DESCRIPTION": "Highlights data objects being scanned inefficiently by users, suggesting clustering, materialized views, or user training on filtering.",
                        "ENTERPRISE_TOUCH": "Allows sorting by inefficiency score or total bytes scanned."
                    }
                ]
            }
        ]
    },

    "SINGLE_USER_DASHBOARD": {
        "VIEW_TITLE": "Single User: Deep Dive & Targeted Coaching",
        "PURPOSE": (
            "Provides a highly granular 'user performance profile' for a selected user. "
            "It diagnoses specific reasons behind their high costs or inefficiencies, identifies their problematic queries, "
            "and gathers evidence for data-backed, constructive coaching."
        ),
        "SECTIONS": [
            {
                "SECTION_TITLE": "User Summary & Impact",
                "DISPLAY_TYPE": "KPIs",
                "KPI_LIST": [
                    {
                        "METRIC_NAME": "Selected User Name",
                        "DESCRIPTION": "The specific user whose data is displayed."
                    },
                    {
                        "METRIC_NAME": "Total Credits Consumed (Selected Period)",
                        "DESCRIPTION": "Total credits by this specific user, with percentage change vs. prior period."
                    },
                    {
                        "METRIC_NAME": "Credits per Hour Active",
                        "DESCRIPTION": "Total credits for this user / Total hours this user's queries kept a warehouse active. Refined efficiency metric.",
                    },
                    {
                        "METRIC_NAME": "User's Cloud Services Credit Ratio",
                        "DESCRIPTION": "Percentage of this user's credits spent on Cloud Services."
                    },
                    {
                        "METRIC_NAME": "User's Average QLES",
                        "DESCRIPTION": "Average Query Lifecycle Efficiency Score for this user's queries."
                    },
                    {
                        "METRIC_NAME": "User's Result Cache Hit Rate",
                        "DESCRIPTION": "Percentage of this user's SELECT queries served from cache."
                    },
                    {
                        "METRIC_NAME": "Failed/Canceled Query Count & Credits",
                        "DESCRIPTION": "Absolute counts and estimated credits wasted by this user due to incomplete operations."
                    }
                ]
            },
            {
                "SECTION_TITLE": "User's Activity & Consumption Patterns",
                "DISPLAY_TYPE": "Detailed Visuals",
                "COMPONENTS": [
                    {
                        "NAME": "Daily Credit Consumption Trend",
                        "CHART_TYPE": "Line Chart",
                        "METRICS": ["Daily CREDITS_USED"],
                        "DESCRIPTION": "Visualizes the user's historical spending habits and identifies spikes.",
                        "ENTERPRISE_TOUCH": "Overlays account-wide average or peer group average for context."
                    },
                    {
                        "NAME": "Credits by Warehouse & Sizing Context",
                        "CHART_TYPE": "Bar Chart",
                        "METRICS": ["TOTAL_CREDITS_USED_BY_USER_ON_WAREHOUSE"],
                        "DESCRIPTION": "Shows which warehouses the user utilizes most and correlates with warehouse size/auto-suspend settings.",
                        "ENTERPRISE_TOUCH": "Displays WAREHOUSE_SIZE and AUTO_SUSPEND settings directly on/near each bar."
                    },
                    {
                        "NAME": "User's Query Duration Distribution",
                        "CHART_TYPE": "Histogram / Violin Plot",
                        "METRICS": ["TOTAL_ELAPSED_TIME (query durations)"],
                        "DESCRIPTION": "Reveals if the user frequently runs very short (potentially inefficient) or very long queries."
                    }
                ]
            },
            {
                "SECTION_TITLE": "User's Query & Data Inefficiency",
                "DISPLAY_TYPE": "Actionable Tables",
                "COMPONENTS": [
                    {
                        "NAME": "Top N Costliest Queries",
                        "TABLE_COLUMNS": [
                            "QUERY_ID", "QUERY_TEXT (truncated, expand)", "WAREHOUSE_NAME",
                            "TOTAL_ELAPSED_SECONDS", "CREDITS_USED_CLOUD_SERVICES", "BYTES_SCANNED",
                            "PARTITIONS_SCANNED", "PARTITIONS_TOTAL", "OVERHEAD_RATIO"
                        ],
                        "DESCRIPTION": "Direct evidence of this user's most expensive individual queries, enabling deep dive into Query Profile.",
                        "ENTERPRISE_TOUCH": "Sorted by CREDITS_USED_CLOUD_SERVICES; includes direct links to Snowflake UI's Query Profile."
                    },
                    {
                        "NAME": "Top N Inefficient Query Patterns by User",
                        "TABLE_COLUMNS": [
                            "QUERY_HASH", "SAMPLE_QUERY_TEXT", "EXECUTION_COUNT",
                            "AVG_COMPILATION_TIME_RATIO", "AVG_QUEUED_TIME_RATIO", "AVG_BYTES_SCANNED_PER_EXEC"
                        ],
                        "DESCRIPTION": "Identifies recurring suboptimal coding patterns specific to this user, enabling targeted coaching on SQL best practices."
                    },
                    {
                        "NAME": "Queries with High Data Spillage to Remote Storage",
                        "TABLE_COLUMNS": ["QUERY_ID", "QUERY_TEXT", "BYTES_SPILLED_TO_REMOTE_STORAGE", "TOTAL_ELAPSED_SECONDS"],
                        "DESCRIPTION": "Highlights specific queries from this user that are memory-intensive and causing performance bottlenecks."
                    },
                    {
                        "NAME": "User's Activity on Inefficient Tables/Views",
                        "TABLE_COLUMNS": ["TABLE_NAME", "TOTAL_BYTES_SCANNED_BY_THIS_USER_ON_THIS_TABLE", "AVG_PARTITION_SCAN_RATIO_ON_THIS_TABLE"],
                        "DESCRIPTION": "Shows which tables this user frequently interacts with inefficiently, guiding data model optimization or user training."
                    }
                ]
            },
            {
                "SECTION_TITLE": "Prescriptive Actions & Coaching Plan",
                "DISPLAY_TYPE": "Dynamic, Action-Oriented Table",
                "COMPONENTS": [
                    {
                        "NAME": "Tailored Recommendations for User",
                        "TABLE_COLUMNS": [
                            "Recommendation", "Problem Context", "Estimated Impact",
                            "Specific Evidence (Links to Q_ID/Hash)", "Suggested Action",
                            "Responsible Party/Status/Next Review"
                        ],
                        "DESCRIPTION": "Provides concrete, data-backed recommendations to optimize this specific user's Snowflake consumption and efficiency."
                    }
                ]
            }
        ]
    }
}