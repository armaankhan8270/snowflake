# pages/roles_360_dashboard.py - PROPOSED MODIFICATIONS
import streamlit as st
import logging

from components.common_ui import common_ui
from components.metric_renderer import MetricRenderer
from components.chart_renderer import ChartRenderer
from core.query_executor import query_executor
from queries.roles_360_queries import ROLES_360_QUERIES

logger = logging.getLogger(__name__)

def render_roles_360_dashboard():
    """
    Renders the Roles 360 Dashboard, providing insights into role usage and associated activity.
    """
    # Initialize renderers with the global query_executor instance
    metric_renderer_instance = MetricRenderer(query_executor)
    chart_renderer_instance = ChartRenderer(query_executor)

    # 1. Page Header
    common_ui.render_page_header(
        "Roles 360 Dashboard",
        "Analyze role activity, associated users, and resource consumption within Snowflake.",
        icon="🔑"
    )

    # 2. Filters (Object filter defaults to 'role' for this page)
    filters = common_ui.render_filters(
        query_executor_instance=query_executor,
        default_object_type="role" # Specific default for Roles 360 Dashboard
    )

    st.markdown("---") # Visual separator

    # 3. Metrics Section
    st.markdown("### 📊 Role Activity Metrics")
    st.markdown("Key performance indicators for the selected role or overall role activity.")

    # Define metrics to render
    metric_configs = [
        # Basic counts for the selected role
        "total_roles", # This metric will count ALL roles if 'All' selected, else 1 if a specific role is selected
        "users_with_role",
        {"query_key": "queries_by_role", "delta_query_key": "queries_by_role"},
        {"query_key": "avg_query_time_by_role", "delta_query_key": "avg_query_time_by_role"},
    ]

    metrics = metric_renderer_instance.render_multiple(
        metric_configs, ROLES_360_QUERIES, filters
    )
    common_ui.render_metric_grid(metrics, columns=4) # Display metrics in 4 columns


    st.markdown("---") # Visual separator

    # 4. Charts Section
    st.markdown("### 📈 Role Activity Visualizations")
    st.markdown("Visual representations of role usage trends and associated resource patterns.")

    # Define charts to render
    chart_configs = [
        # Global chart (always shows top roles globally)
        {"query_key": "top_roles_by_total_queries", "show_table_toggle": True},

        # Role-specific charts (respect selected role filter, or show all if "All" is selected)
        {"query_key": "top_users_in_role_by_queries", "show_table_toggle": True},
        {"query_key": "queries_by_warehouse_for_role", "show_table_toggle": True},
        {"query_key": "role_grants_history", "show_table_toggle": True},
        {"query_key": "role_privilege_summary", "show_table_toggle": True},
        {"query_key": "role_cost_by_warehouse_heatmap", "show_table_toggle": True},
    ]

    charts = chart_renderer_instance.render_multiple(
        chart_configs, ROLES_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts, columns=2) # Display charts in 2 columns

    # Optional: Debugging information (can be commented out in production)
    # with st.expander("Debug Filters"):
    #     st.json(filters)