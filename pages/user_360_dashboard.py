# pages/user_360_dashboard.py - PROPOSED MODIFICATIONS
import streamlit as st
import logging

from components.common_ui import common_ui
from components.metric_renderer import MetricRenderer
from components.chart_renderer import ChartRenderer
from core.query_executor import query_executor
from queries.user_360_queries import USER_360_QUERIES

logger = logging.getLogger(__name__)

def render_user_360_dashboard():
    """
    Renders the User 360 Dashboard, providing insights into user activity.
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

    # 3. Metrics Section
    st.markdown("### 📊 User Activity Metrics")
    st.markdown("Key performance indicators for the selected user or overall user activity.")

    # Define metrics to render
    # 'delta_query_key' automatically fetches data for the previous period for comparison
    metric_configs = [
        {"query_key": "total_queries_by_user", "delta_query_key": "total_queries_by_user"},
        {"query_key": "total_execution_time_by_user", "delta_query_key": "total_execution_time_by_user"},
        {"query_key": "avg_execution_time_by_user", "delta_query_key": "avg_execution_time_by_user"},
        {"query_key": "data_scanned_by_user", "delta_query_key": "data_scanned_by_user"},
        {"query_key": "failed_queries_by_user_metric", "delta_query_key": "failed_queries_by_user_metric"},
        {"query_key": "long_running_queries_by_user_metric", "delta_query_key": "long_running_queries_by_user_metric"},
        "distinct_warehouses_used_by_user", # No delta needed for distinct count
    ]

    metrics = metric_renderer_instance.render_multiple(
        metric_configs, USER_360_QUERIES, filters
    )
    common_ui.render_metric_grid(metrics, columns=4) # Display metrics in 4 columns


    st.markdown("---") # Visual separator

    # 4. Charts Section
    st.markdown("### 📈 User Activity Visualizations")
    st.markdown("Visual representations of user trends, resource consumption, and query patterns.")

    # Define charts to render
    # Note: Charts like "top_users_by_data_scanned" have "apply_object_filter: False" in USER_360_QUERIES
    # meaning they will always show global top users, irrespective of single user selection in filters.
    chart_configs = [
        # Global charts (always show top N across all users)
        {"query_key": "top_users_by_query_count", "show_table_toggle": True},
        {"query_key": "top_users_by_execution_time", "show_table_toggle": True},
        {"query_key": "top_users_by_data_scanned", "show_table_toggle": True},

        # User-specific charts (respect selected user filter, or show all if "All" is selected)
        {"query_key": "daily_query_trend_by_user", "show_table_toggle": True}, # Line chart shows trends
        {"query_key": "execution_time_vs_query_count_scatter", "show_table_toggle": True},
        {"query_key": "user_warehouse_heatmap", "show_table_toggle": True},
        {"query_key": "query_failures_by_user_chart", "show_table_toggle": True},
        {"query_key": "long_running_queries_by_user_chart", "show_table_toggle": True},
    ]

    charts = chart_renderer_instance.render_multiple(
        chart_configs, USER_360_QUERIES, filters
    )
    common_ui.render_chart_grid(charts, columns=2) # Display charts in 2 columns

    # Optional: Debugging information (can be commented out in production)
    # with st.expander("Debug Filters"):
    #     st.json(filters)