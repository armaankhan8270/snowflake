# pages/user_360_dashboard.py

import streamlit as st
import logging

from components.common_ui import common_ui
from components.metric_renderer import MetricRenderer
from components.chart_renderer import ChartRenderer
from core.query_executor import query_executor
from queries.user_360_queries import USER_360_QUERIES # Assuming your queries are in this file

logger = logging.getLogger(__name__)

def render_user_360_dashboard():
    """
    Renders the User 360 Dashboard, providing insights into individual user activity.

    Goal:
    1. Identify **who** is costing much (overall top users).
    2. Understand **why** they are costing (deep dive into selected user's usage patterns).
    3. Suggest **what** actions to take to reduce cost and optimize user behavior.
    """
    # Initialize renderers with the global query_executor instance
    metric_renderer_instance = MetricRenderer(query_executor)
    chart_renderer_instance = ChartRenderer(query_executor)

    # 1. Page Header
    common_ui.render_page_header(
        "User 360 Dashboard",
        "Deep dive into individual user activity, performance, and resource consumption within Snowflake.",
        icon="👤"
    )

    # 2. Filters (Object filter defaults to 'user' for this page)
    # The default date filter is set in common_ui to '7_days'
    filters = common_ui.render_filters(
        query_executor_instance=query_executor,
        default_object_type="user" # Specific default for User 360 Dashboard
    )

    st.markdown("---") # Visual separator

    # Determine if a specific user is selected (i.e., not 'All')
    is_specific_user_selected = filters.get("object_type") == "user" and \
                                filters.get("object_value") not in ["All", None, ""]

    selected_user_display_name = filters.get("object_value", "All")
    if selected_user_display_name == "All":
        selected_user_display_name = "All Users"


    # --- Section 1: Who is Costing Much? (Overview) ---
    st.markdown("### 💸 Who is Costing Much? (Overview)")
    st.markdown(f"Identify the primary drivers of cost and resource consumption across {selected_user_display_name} within the selected time range. These metrics provide a high-level health check.")

    # A. Core Metrics for overall user activity and cost
    st.markdown("#### Key User Activity & Cost Metrics")
    metric_configs_overview = [
        {"query_key": "total_estimated_cost_usd"},
        {"query_key": "total_queries_run"},
        {"query_key": "query_success_rate_percentage"},
        {"query_key": "avg_cost_per_query_usd"},
        {"query_key": "avg_query_queue_time_sec"},
        {"query_key": "avg_query_spill_to_disk_mb"},
        # Added placeholders for other general metrics previously in your dashboard if still desired
        {"query_key": "total_active_users"}, # Assuming this query exists in USER_360_QUERIES
        {"query_key": "avg_cost_per_user"}, # Assuming this query exists
        {"query_key": "percentage_high_cost_users"}, # Assuming this query exists
        {"query_key": "high_cost_users_count"}, # Assuming this query exists
        {"query_key": "failed_queries_percentage"}, # Assuming this query exists (or replaced by query_success_rate_percentage)
        {"query_key": "avg_query_duration"}, # Assuming this query exists
        {"query_key": "total_users_defined"}, # Assuming this query exists
    ]

    metrics_overview = metric_renderer_instance.render_multiple(
        metric_configs_overview, USER_360_QUERIES, filters
    )
    common_ui.render_metric_grid(metrics_overview, metrics_per_row=4)


    # --- Section 2: Why are they Costing Much? (Deep Dive into {selected_user_display_name}) ---
    st.markdown("---")
    st.markdown(f"### 📈 Why Are They Costing? ({selected_user_display_name} Specifics)")
    st.markdown("Dive into the specific behaviors and activities of the selected user(s) contributing to resource consumption.")

    # A. Table: User FinOps Efficiency & Actionable Insights
    st.markdown("#### User Cost Efficiency & Priority Analysis")
    st.markdown("A comprehensive breakdown of user costs, performance metrics, and a calculated FinOps priority level with initial recommendations. Use this table to quickly identify and categorize users needing attention.")
    chart_configs_user_efficiency = [
        {"query_key": "user_cost_efficiency_table", "show_table_toggle": True},
    ]
    charts_user_efficiency = chart_renderer_instance.render_multiple(
        chart_configs_user_efficiency, USER_360_QUERIES, filters
    )
    # Render tables individually for better layout and custom subheaders/captions
    for table_chart in charts_user_efficiency:
        if "error" in table_chart:
             common_ui.render_error_message(f"Error Loading {table_chart.get('label', 'User Efficiency Table')}", table_chart["error"])
        else:
            with st.container(border=True):
                st.subheader(table_chart.get("label", "User Efficiency Table"))
                st.caption(table_chart.get("description", ""))
                st.dataframe(table_chart["data"], use_container_width=True)

    # B. Chart: Daily Cost Trend by User
    st.markdown("#### Daily Cost Trend")
    st.markdown(f"Visualize the daily estimated cost trend for {selected_user_display_name}. This helps in understanding usage patterns and identifying cost spikes over time.")
    chart_configs_daily_trend = [
        {"query_key": "daily_cost_trend_by_user", "show_table_toggle": True},
    ]
    charts_daily_trend = chart_renderer_instance.render_multiple(
        chart_configs_daily_trend, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts_daily_trend, charts_per_row=1)


    # C. Chart: Cost Distribution by Warehouse Size
    st.markdown("#### Cost Distribution by Warehouse Size")
    st.markdown(f"Shows how the estimated costs for {selected_user_display_name} are distributed across different warehouse sizes. This can highlight if larger warehouses are being used inefficiently or are genuinely necessary.")
    chart_configs_warehouse_distribution = [
        {"query_key": "cost_by_warehouse_size_distribution", "show_table_toggle": True},
    ]
    charts_warehouse_distribution = chart_renderer_instance.render_multiple(
        chart_configs_warehouse_distribution, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts_warehouse_distribution, charts_per_row=1)


    # D. Chart: Query Cost vs. Performance Scatter Analysis
    st.markdown("#### Query Performance & Cost Scatter Analysis")
    st.markdown(f"A scatter plot showing individual queries by {selected_user_display_name}, plotting duration against bytes scanned, with bubble size representing estimated cost. Identify outlier queries that are slow, scan too much data, or are unexpectedly expensive.")
    chart_configs_scatter_analysis = [
        {"query_key": "query_performance_scatter_analysis", "show_table_toggle": True},
    ]
    charts_scatter_analysis = chart_renderer_instance.render_multiple(
        chart_configs_scatter_analysis, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts_scatter_analysis, charts_per_row=1)


    # --- Section 3: What Actions Can Be Taken? (Optimization Opportunities) ---
    st.markdown("---")
    st.markdown(f"### 🚀 Optimization Opportunities ({selected_user_display_name})")
    st.markdown("Specific recommendations and insights to reduce costs and improve performance based on the identified patterns.")

    # A. Table: Top N Most Impactful Queries for Optimization
    st.markdown("#### Top 50 Most Impactful Queries for Optimization")
    st.markdown(f"This table lists the top 50 most expensive queries run by {selected_user_display_name}, providing detailed metrics like duration, data scanned/spilled, queue time, and specific, actionable recommendations for FinOps engineers to investigate.")
    chart_configs_top_queries_detailed = [
        {"query_key": "top_n_expensive_queries_detailed", "show_table_toggle": True},
    ]
    charts_top_queries_detailed = chart_renderer_instance.render_multiple(
        chart_configs_top_queries_detailed, USER_360_QUERIES, filters
    )
    for table_chart in charts_top_queries_detailed:
        if "error" in table_chart:
             common_ui.render_error_message(f"Error Loading {table_chart.get('label', 'Top Queries Table')}", table_chart["error"])
        else:
            with st.container(border=True):
                st.subheader(table_chart.get("label", "Top Queries Table"))
                st.caption(table_chart.get("description", ""))
                st.dataframe(table_chart["data"], use_container_width=True)


    # Optional: Debugging information (can be commented out in production)
    # with st.expander("Debug Filters"):
    #     st.json(filters)