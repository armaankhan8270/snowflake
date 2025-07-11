# pages/user_360_dashboard.py

import streamlit as st
import logging

from components.common_ui import common_ui
from components.metric_renderer import MetricRenderer
from components.chart_renderer import ChartRenderer
from core.query_executor import query_executor
from queries.user_360_new_quries import USER_360_QUERIES

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


    # --- Section 1: Who is Costing Much? ---
    st.markdown("### 💸 Who is Costing Much? (Overview)")
    st.markdown("Identify the primary drivers of cost and resource consumption across your Snowflake account.")

    # Core Metrics for overall health
    metric_configs_overview = [
        {"query_key": "total_queries_run", "delta_query_key": "total_queries_run"},
        {"query_key": "total_active_users", "delta_query_key": "total_active_users"},
        {"query_key": "avg_cost_per_user", "delta_query_key": "avg_cost_per_user"},
        {"query_key": "percentage_high_cost_users", "delta_query_key": "percentage_high_cost_users"},
        {"query_key": "high_cost_users_count", "delta_query_key": "high_cost_users_count"},
        {"query_key": "failed_queries_percentage", "delta_query_key": "failed_queries_percentage"},
        {"query_key": "avg_query_duration", "delta_query_key": "avg_query_duration"},
        {"query_key": "total_users_defined"}, # No delta typically for total defined users
    ]

    metrics_overview = metric_renderer_instance.render_multiple(
        metric_configs_overview, USER_360_QUERIES, filters
    )
    common_ui.render_metric_grid(metrics_overview, metrics_per_row=4) # Using 4 metrics per row


    # Chart: Top Users/Roles by Cost
    st.markdown("#### Top Cost Contributors")
    st.markdown("Visualizing the top users and roles by estimated cost to quickly pinpoint high spenders.")
    chart_configs_who_cost = [
        {"query_key": "cost_by_user_and_role", "show_table_toggle": True},
    ]
    charts_who_cost = chart_renderer_instance.render_multiple(
        chart_configs_who_cost, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts_who_cost, charts_per_row=1) # This chart is better on its own row


    # --- Section 2: Why are they Costing Much? ---
    st.markdown("---")
    st.markdown(f"### 📈 Why Are They Costing? ({selected_user_display_name})")
    st.markdown("Dive into the specific behaviors and activities of users contributing to resource consumption.")

    # Table: User Cost & Priority Level (Detailed breakdown of top/selected users)
    st.markdown("#### User Cost Analysis & Priority")
    st.markdown("Detailed breakdown of user costs, query counts, and a calculated priority level to guide investigation.")
    chart_configs_why_cost_table = [
        {"query_key": "cost_by_user_priority", "show_table_toggle": True},
    ]
    charts_why_cost_table = chart_renderer_instance.render_multiple(
        chart_configs_why_cost_table, USER_360_QUERIES, filters
    )
    # Render tables individually for better layout
    for table_chart in charts_why_cost_table:
        if "error" in table_chart:
             common_ui.render_error_message(f"Error Loading {table_chart.get('label', 'Table')}", table_chart["error"])
        else:
            with st.container(border=True):
                st.subheader(table_chart.get("label", "Table"))
                st.caption(table_chart.get("description", ""))
                st.dataframe(table_chart["data"], use_container_width=True)

    # Chart: User Behavior Patterns (Hourly Heatmap)
    st.markdown("#### User Activity Patterns")
    st.markdown("Visualize hourly query patterns to identify peak times and consistent usage trends.")
    chart_configs_user_behavior = [
        {"query_key": "user_behavior_patterns", "show_table_toggle": True},
    ]
    charts_user_behavior = chart_renderer_instance.render_multiple(
        chart_configs_user_behavior, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts_user_behavior, charts_per_row=1) # Heatmap is best on its own row

    # --- Section 3: What Actions Can Be Taken? ---
    st.markdown("---")
    st.markdown(f"### 🚀 Optimization Opportunities ({selected_user_display_name})")
    st.markdown("Specific recommendations and insights to reduce costs and improve performance.")

    # Table: Query Performance Bottlenecks & Actions
    st.markdown("#### Query Performance Bottlenecks")
    st.markdown("Identify common performance issues by user/warehouse/query type and get actionable recommendations.")
    chart_configs_bottlenecks = [
        {"query_key": "query_performance_bottlenecks", "show_table_toggle": True},
    ]
    charts_bottlenecks = chart_renderer_instance.render_multiple(
        chart_configs_bottlenecks, USER_360_QUERIES, filters
    )
    for table_chart in charts_bottlenecks:
        if "error" in table_chart:
             common_ui.render_error_message(f"Error Loading {table_chart.get('label', 'Table')}", table_chart["error"])
        else:
            with st.container(border=True):
                st.subheader(table_chart.get("label", "Table"))
                st.caption(table_chart.get("description", ""))
                st.dataframe(table_chart["data"], use_container_width=True)

    # Table: Overall Optimization Opportunities with Recommendations
    st.markdown("#### Comprehensive Optimization Recommendations")
    st.markdown("A summary of key optimization areas across users and warehouses with suggested actions.")
    chart_configs_optimization_summary = [
        {"query_key": "optimization_opportunities", "show_table_toggle": True},
    ]
    charts_optimization_summary = chart_renderer_instance.render_multiple(
        chart_configs_optimization_summary, USER_360_QUERIES, filters
    )
    for table_chart in charts_optimization_summary:
        if "error" in table_chart:
             common_ui.render_error_message(f"Error Loading {table_chart.get('label', 'Table')}", table_chart["error"])
        else:
            with st.container(border=True):
                st.subheader(table_chart.get("label", "Table"))
                st.caption(table_chart.get("description", ""))
                st.dataframe(table_chart["data"], use_container_width=True)

    # Optional: Debugging information (can be commented out in production)
    # with st.expander("Debug Filters"):
    #     st.json(filters)