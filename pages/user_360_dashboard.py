# pages/user_360_dashboard.py

import streamlit as st
import logging

# Import necessary components
from core.query_executor import QueryExecutor
from components.common_ui import common_ui # We use the instantiated object
from components.metric_renderer import MetricRenderer
from components.chart_renderer import ChartRenderer
from queries.user_360_queries import USER_360_QUERIES # Our new query store

# Configure logging for the page
logger = logging.getLogger(__name__)

# Set Streamlit page configuration
st.set_page_config(
    page_title="User 360 Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components (using st.session_state for singletons across reruns)
if 'query_executor' not in st.session_state:
    st.session_state.query_executor = QueryExecutor()
if 'metric_renderer' not in st.session_state:
    st.session_state.metric_renderer = MetricRenderer(st.session_state.query_executor)
if 'chart_renderer' not in st.session_state:
    st.session_state.chart_renderer = ChartRenderer(st.session_state.query_executor)

query_executor = st.session_state.query_executor
metric_renderer = st.session_state.metric_renderer
chart_renderer = st.session_state.chart_renderer

# ----------------------------------------------------------------------
# Page Header
# ----------------------------------------------------------------------
common_ui.render_page_header(
    title="User 360 Dashboard",
    description="Deep dive into a specific user's Snowflake consumption patterns, query performance, and potential cost optimization areas.",
    icon="👤"
)

# ----------------------------------------------------------------------
# Filters Section
# ----------------------------------------------------------------------
st.sidebar.markdown("## Configuration & Filters")
st.sidebar.markdown("---")

filters = common_ui.render_filters(
    query_executor_instance=query_executor,
    default_object_type="user", # This page specifically focuses on users
    default_date_filter="30_days"
)

# Check if there was an error rendering filters
if filters.get("error_rendering_filters"):
    common_ui.render_error_message("Filter Error", filters["error_rendering_filters"])
    st.stop() # Stop execution if filters couldn't be rendered properly

st.sidebar.markdown("---")

# ----------------------------------------------------------------------
# Conditional Rendering based on User Selection
# ----------------------------------------------------------------------

selected_object_type = filters.get("object_type")
selected_object_value = filters.get("object_value")

if selected_object_type != "user" or selected_object_value == "All":
    common_ui.render_info_message(
        "Select a Specific User",
        "To view the detailed User 360 dashboard, please select 'User' as the Object Type and choose a specific user from the dropdown in the sidebar."
    )
    # Optionally, you could display some aggregate "All Users" metrics here
    # For a true "360" view, we need a single entity, so we'll stop here.
    st.stop() # Stop further rendering until a specific user is selected

# Display selected user for context
st.markdown(f"### Analyzing **`{selected_object_value}`**")
st.info(f"Displaying insights for user: **`{selected_object_value}`** from **`{filters['start_date_str']}`** to **`{filters['end_date_str']}`**.")


# ----------------------------------------------------------------------
# Metrics Section
# ----------------------------------------------------------------------
st.markdown("---")
st.markdown("### Key Performance Metrics")
st.markdown("Understand the core resource consumption and efficiency indicators for this user.")

# Define the metric keys to render
user_metrics_to_render = [
    "total_queries_run_by_user",
    "total_execution_time_min_by_user",
    "avg_execution_time_sec_per_query_by_user",
    "total_data_scanned_tb_by_user",
    "total_compilation_time_sec_by_user",
    "failed_query_count_by_user",
    "distinct_warehouses_used_by_user",
    "longest_running_query_min_by_user",
]

# Render metrics using the common_ui and metric_renderer
with st.spinner("Fetching and rendering user metrics..."):
    user_metrics_output = metric_renderer.render_multiple(
        metric_configs=user_metrics_to_render,
        query_store=USER_360_QUERIES,
        filters=filters
    )
    common_ui.render_metric_grid(user_metrics_output, metrics_per_row=4)

# Store rendered metrics in session state for recommendations
st.session_state['user_360_metrics'] = {metric['label']: metric for metric in user_metrics_output if 'error' not in metric}


# ----------------------------------------------------------------------
# Charts Section
# ----------------------------------------------------------------------
st.markdown("---")
st.markdown("### Visual Performance Analysis")
st.markdown("Dive deeper into trends and distributions of the user's Snowflake activity.")

# Define the chart keys to render
user_charts_to_render = [
    "daily_total_execution_time_by_user_chart",
    "queries_by_execution_status_chart",
    "top_10_most_expensive_queries_by_user_chart",
    "execution_time_by_warehouse_chart",
    "daily_data_scanned_tb_by_user_chart",
    "query_type_distribution_by_user_chart",
    "daily_compile_time_by_user_chart",
    # Note on 'daily_queueing_blocked_time_by_user_chart': this chart has toggle options.
    # We can render it normally, and its internal logic in chart_renderer will handle the toggles.
    "daily_queueing_blocked_time_by_user_chart",
]

# Render charts using the common_ui and chart_renderer
with st.spinner("Fetching and rendering user charts..."):
    user_charts_output = chart_renderer.render_multiple(
        chart_configs=user_charts_to_render,
        query_store=USER_360_QUERIES,
        filters=filters
    )
    common_ui.render_chart_grid(user_charts_output, charts_per_row=2)


# ----------------------------------------------------------------------
# Recommendations Section
# ----------------------------------------------------------------------
st.markdown("---")
st.markdown("### Recommendations for Optimization")
st.markdown("Based on the data, here are some actionable recommendations to optimize this user's Snowflake usage and costs.")

if st.session_state.get('user_360_metrics'):
    metrics = st.session_state['user_360_metrics']
    recommendations_list = []

    # Recommendation 1: High Execution Time
    total_exec_time = metrics.get("Total Execution Time")
    if total_exec_time and 'value' in total_exec_time and total_exec_time['value'] > 1000: # Example threshold: > 1000 minutes
        recommendations_list.append(
            "**High Total Execution Time:** This user's queries consume a significant amount of compute time. "
            "Focus on optimizing their long-running queries (see 'Top 10 Expensive Queries' chart) and review warehouse sizing during peak usage."
        )

    # Recommendation 2: High Data Scanned
    total_data_scanned = metrics.get("Total Data Scanned")
    if total_data_scanned and 'value' in total_data_scanned and total_data_scanned['value'] > 0.5: # Example threshold: > 0.5 TB
        recommendations_list.append(
            "**High Data Scanned:** The user is scanning a large volume of data. "
            "Encourage them to use more selective filters (WHERE clauses), consider clustering tables they frequently query, or explore materialized views for common aggregates."
        )

    # Recommendation 3: High Failed Query Rate
    failed_queries = metrics.get("Failed Queries")
    total_queries = metrics.get("Total Queries Run")
    if (failed_queries and 'value' in failed_queries and total_queries and 'value' in total_queries and
        total_queries['value'] > 0 and (failed_queries['value'] / total_queries['value']) > 0.15): # Example threshold: > 15% failed
        recommendations_list.append(
            "**High Failed Query Rate:** A significant portion of this user's queries are failing. "
            "This could indicate syntax errors, permission issues, or attempts to query non-existent data. "
            "Consider providing targeted training or reviewing their query patterns for common mistakes."
        )

    # Recommendation 4: Long Compilation Time
    total_compile_time = metrics.get("Total Compile Time")
    if total_compile_time and 'value' in total_compile_time and total_compile_time['value'] > 300: # Example threshold: > 300 seconds
        recommendations_list.append(
            "**Significant Compilation Time:** This user's queries are taking a notable amount of time to compile. "
            "This can happen with very complex SQL, deeply nested views, or large numbers of joins. "
            "Recommend simplifying queries, using `QUALIFY` for window functions instead of subqueries, or reviewing view definitions."
        )
            
    # Recommendation 5: Queueing/Blocked Time
    # This metric is from the chart, so we can't directly get it from 'metrics' state.
    # We would need to parse chart_output or execute a mini-query.
    # For simplicity, let's make a generic recommendation here if the chart shows high values.
    # Or, if you want direct data, add a separate metric for this.
    
    # Generic suggestion if specific conditions aren't met
    if not recommendations_list:
        recommendations_list.append(
            "The selected user's usage patterns appear efficient for the chosen period. "
            "Continue monitoring their activity, or explore different time ranges for deeper insights. "
            "General best practices include: optimizing SQL queries, using appropriate warehouse sizes, and leveraging caching."
        )

    for i, rec in enumerate(recommendations_list):
        st.markdown(f"- {rec}")
else:
    common_ui.render_info_message(
        "No Recommendations Yet",
        "Recommendations will appear here once metrics are loaded successfully."
    )

st.markdown("---")
st.caption("Data from Snowflake ACCOUNT_USAGE views. Latency may apply.")