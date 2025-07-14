# components/common_ui.py

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import streamlit as st

# We need to type hint these instances, but import them within the class methods
# to avoid circular dependencies if they also import CommonUI
# from components.metric_renderer import MetricRenderer
# from components.chart_renderer import ChartRenderer

logger = logging.getLogger(__name__)


class CommonUI:
    """
    A class to encapsulate common User Interface (UI) elements and rendering logic
    for Streamlit dashboards, promoting consistency and reusability.
    """

    def render_info_message(self, title: str, message: str):
        """Renders an informational message box."""
        with st.info(title):
            st.write(message)

    def render_warning_message(self, title: str, message: str):
        """Renders a warning message box."""
        with st.warning(title):
            st.write(message)

    def render_error_message(self, title: str, message: str):
        """Renders an error message box."""
        with st.error(title):
            st.write(message)

    def render_page_header(self, title: str, description: str, icon: str = "📊"):
        """Renders a consistent header for dashboard pages."""
        st.markdown(f"## {icon} {title}")
        st.markdown(description)
        st.markdown("---")

    def render_metric_grid(
        self, metrics: List[Dict[str, Any]], metrics_per_row: int = 4
    ):
        """
        Renders a grid of metric cards with a flexible number of metrics per row.

        Args:
            metrics (List[Dict[str, Any]]): A list of dictionaries, where each dict
                                            contains 'label', 'value', 'delta' (optional),
                                            'description' (optional), and 'error' (optional).
            metrics_per_row (int): The number of metric cards to display in a single row.
                                   Valid options are 2, 3, or 4. Defaults to 4.
        """
        if not metrics:
            self.render_info_message(
                "No Metrics Available", "No metrics were provided to display."
            )
            return

        # Validate metrics_per_row input
        if metrics_per_row not in [2, 3, 4]:
            logger.warning(
                f"Invalid metrics_per_row value: {metrics_per_row}. Defaulting to 4."
            )
            metrics_per_row = 4

        # Apply custom CSS for smaller metric font size
        st.markdown(
            """
            <style>
            [data-testid="stMetricValue"] {
                font-size: 1.5rem; /* Adjust as needed, e.g., 2rem for slightly larger, 1.2rem for smaller */
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Iterate through metrics and create columns
        for i in range(0, len(metrics), metrics_per_row):
            cols = st.columns(metrics_per_row)
            for j in range(metrics_per_row):
                if i + j < len(metrics):
                    metric = metrics[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            # Check for 'error' key first
                            if "error" in metric:
                                self.render_error_message(
                                    f"Error Loading {metric.get('label', 'Metric')}",
                                    metric["error"],
                                )
                            else:
                                st.subheader(metric.get("label", "N/A"))
                                # The st.metric value's font size is controlled by the CSS above
                                st.metric(
                                    label="Value",  # This 'label' is usually hidden by CSS if not needed, or is small.
                                    value=metric.get("value", "N/A"),
                                    delta=metric.get("delta"),
                                )
                                if metric.get("description"):
                                    st.caption(metric["description"])

    def render_chart_grid(self, charts: List[Dict[str, Any]], charts_per_row: int = 2):
        """
        Renders a grid of charts with optional data tables.

        Args:
            charts (List[Dict[str, Any]]): A list of dictionaries, where each dict
                                           contains 'figure', 'data', 'label',
                                           'description', 'show_table_toggle', and 'error'.
            charts_per_row (int): The number of charts to display in a single row. Defaults to 2.
        """
        if not charts:
            self.render_info_message(
                "No Charts Available", "No charts were provided to display."
            )
            return

        # Iterate through charts and create columns
        for i in range(0, len(charts), charts_per_row):
            cols = st.columns(charts_per_row)
            for j in range(charts_per_row):
                if i + j < len(charts):
                    chart = charts[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            if "error" in chart:
                                self.render_error_message(
                                    f"Error Loading {chart.get('label', 'Chart')}",
                                    chart["error"],
                                )
                            else:
                                st.subheader(chart.get("label", "Chart"))
                                if chart.get("description"):
                                    st.caption(chart["description"])

                                # Render the chart
                                st.plotly_chart(
                                    chart["figure"], use_container_width=True
                                )

                                # Optional: Toggle for data table
                                # Ensure 'data' key exists and is a DataFrame and not empty
                                if (
                                    chart.get("show_table_toggle", False)
                                    and isinstance(chart.get("data"), pd.DataFrame)
                                    and not chart["data"].empty
                                ):
                                    # Generate a unique key for the toggle
                                    toggle_key_safe_label = chart['label'].replace(' ', '_').replace('.', '').replace('-', '_').lower()
                                    if st.toggle(
                                        f"Show data for {chart['label']}",
                                        key=f"toggle_data_{toggle_key_safe_label}_{i}_{j}", # Unique key per toggle
                                    ):
                                        st.dataframe(chart["data"])
                                elif chart.get("show_table_toggle", False) and isinstance(chart.get("data"), pd.DataFrame) and chart["data"].empty:
                                    st.info(f"No data to display in table for {chart['label']}.")


    # --- New Modular Filter Rendering Methods ---

    def _render_date_filter(
        self, default_date_filter: str
    ) -> Tuple[str, Optional[date], Optional[date]]:
        """
        Renders the date filter section.
        Returns the selected date filter type, and custom start/end dates if 'custom' is selected.
        """
        st.subheader("Time Range")
        date_filter_options = {
            "Last 1 Day": "1_day",
            "Last 7 Days": "7_days",
            "Last 14 Days": "14_days",
            "Last 1 Month": "1_month",
            "Last 3 Months": "3_months",
            "Last 6 Months": "6_months",
            "Last 1 Year": "1_year",
            "Custom Range": "custom",
        }

        default_date_index = (
            list(date_filter_options.values()).index(default_date_filter)
            if default_date_filter in list(date_filter_options.values())
            else 1  # Default to 'Last 7 Days' if default_date_filter is not found
        )

        selected_date_filter_label = st.selectbox(
            "Select a preset date range or define a custom one:",
            options=list(date_filter_options.keys()),
            index=default_date_index,
            key="date_range_selector",
            help="Choose a predefined period or set exact start/end dates for your analysis.",
        )
        selected_date_filter_type = date_filter_options[selected_date_filter_label]

        custom_start_date: Optional[date] = None
        custom_end_date: Optional[date] = None

        if selected_date_filter_type == "custom":
            current_end_date: date = datetime.now().date()
            default_custom_start: date = current_end_date - timedelta(days=7)

            # Initialize custom date values in session state only if they don't exist
            # or if they are not of the expected datetime.date type
            if "custom_start_date_val" not in st.session_state or not isinstance(
                st.session_state["custom_start_date_val"], date
            ):
                st.session_state["custom_start_date_val"] = default_custom_start

            if "custom_end_date_val" not in st.session_state or not isinstance(
                st.session_state["custom_end_date_val"], date
            ):
                st.session_state["custom_end_date_val"] = current_end_date

            custom_date_col1, custom_date_col2 = st.columns(2)
            with custom_date_col1:
                custom_start_date_input = st.date_input(
                    "Start date",
                    value=st.session_state["custom_start_date_val"],
                    key="custom_start_date",
                    help="Select the beginning date for your custom range.",
                )
            with custom_date_col2:
                custom_end_date_input = st.date_input(
                    "End date",
                    value=st.session_state["custom_end_date_val"],
                    key="custom_end_date",
                    help="Select the end date for your custom range. Must be after start date.",
                )

            # Update session state with the *returned* values from date_input
            # Streamlit date_input can return a tuple if cleared, so ensure it's a date object
            custom_start_date = (
                custom_start_date_input[0]
                if isinstance(custom_start_date_input, tuple)
                else custom_start_date_input
            )
            custom_end_date = (
                custom_end_date_input[0]
                if isinstance(custom_end_date_input, tuple)
                else custom_end_date_input
            )

            st.session_state["custom_start_date_val"] = custom_start_date
            st.session_state["custom_end_date_val"] = custom_end_date

            if (
                custom_start_date
                and custom_end_date
                and custom_start_date > custom_end_date
            ):
                self.render_warning_message(
                    "Invalid Date Range",
                    "Start date cannot be after end date. Please adjust.",
                )
                # In case of invalid dates, return a sensible default range
                custom_start_date = current_end_date - timedelta(days=7)
                custom_end_date = current_end_date
        else:
            # Clear custom date session state keys when not in custom mode
            if "custom_start_date_val" in st.session_state:
                del st.session_state["custom_start_date_val"]
            if "custom_end_date_val" in st.session_state:
                del st.session_state["custom_end_date_val"]

        return selected_date_filter_type, custom_start_date, custom_end_date

    def _render_object_type_filter(self, default_object_type: str) -> str:
        """
        Renders the object type filter section.
        Returns the selected object type (e.g., 'user', 'warehouse').
        """
        st.subheader("Object Selection")
        object_type_options = {
            "All Objects": "all",
            "User": "user",
            "Warehouse": "warehouse",
            "Role": "role",
            "Database": "database",
        }
        if default_object_type not in object_type_options.values():
            default_object_type = "all"

        default_object_label = next(
            (
                label
                for label, val in object_type_options.items()
                if val == default_object_type
            ),
            "All Objects",
        )

        selected_object_type_label = st.selectbox(
            "Filter by a specific object type:",
            options=list(object_type_options.keys()),
            index=list(object_type_options.keys()).index(default_object_label),
            key="object_type_selector",
            help="Select a type (e.g., User, Warehouse) to focus your analysis on specific entities.",
        )
        return object_type_options[selected_object_type_label]

    def _render_object_value_search_and_select(
        self, query_executor_instance: Any, object_type: str, filters: Dict[str, Any] # Added filters
    ) -> str:
        """
        Renders the search bar and selectbox for specific object values.
        Returns the selected object value.
        """
        if object_type == "all":
            return (
                "All"  # No specific object selection needed if 'All Objects' is chosen
            )

        search_term = st.text_input(
            f"Search for a specific {object_type}:",
            key=f"search_input_{object_type}",
            placeholder=f"Type to search {object_type}...",
            help=f"Begin typing to filter the dropdown list for a specific {object_type}.",
        ).strip()

        # Pass current date filters to get_object_values for context-aware filtering
        date_filters_for_objects = {
            "start_date_str": filters.get("start_date_str"),
            "end_date_str": filters.get("end_date_str")
        }

        # Fetch object values using the query executor
        object_values = query_executor_instance.get_object_values(
            object_type, search_term, date_filters=date_filters_for_objects # Pass date_filters
        )

        if "All" not in object_values:
            object_values.insert(0, "All")

        session_state_key = f"object_value_{object_type}_selector"

        # Ensure session state for the specific object_value selector is initialized/valid
        # or if the previously selected value is no longer in the options
        if (
            session_state_key not in st.session_state
            or st.session_state[session_state_key] not in object_values
        ):
            st.session_state[session_state_key] = "All"

        default_index_for_selectbox = object_values.index(
            st.session_state[session_state_key]
        )

        selected_object_value = st.selectbox(
            f"Select {object_type}:",
            options=object_values,
            index=default_index_for_selectbox,
            key=session_state_key,
            help=f"Select 'All' to view aggregated data, or choose a specific {object_type}.",
        )
        return selected_object_value

    def render_filters(
        self,
        query_executor_instance: Any,
        default_object_type: str = "all",
        default_date_filter: str = "7_days",
    ) -> Dict[str, Any]:
        """
        Renders interactive date and object type filters in a visually appealing container.
        Includes search functionality for object values and intelligent defaults.

        Args:
            query_executor_instance: An instance of QueryExecutor to fetch filter options.
            default_object_type (str): The default object type to select in the filter.
            default_date_filter (str): The default date range filter to apply.

        Returns:
            Dict[str, Any]: A dictionary containing the selected filter values.
                            Always returns a dictionary, even on error, with default values.
        """
        filters: Dict[str, Any] = {}  # Initialize filters as an empty dictionary

        try:
            st.markdown("### 🔍 Dashboard Filters")
            st.markdown(
                "Easily refine your data by selecting specific time ranges or objects."
            )

            with st.container(border=True):
                col1, col2 = st.columns([1, 1])

                with col1:
                    # Leverage the new _render_date_filter method
                    (
                        selected_date_filter_type,
                        custom_start_date,
                        custom_end_date,
                    ) = self._render_date_filter(default_date_filter)

                    filters["date_filter"] = selected_date_filter_type
                    filters["custom_start"] = custom_start_date
                    filters["custom_end"] = custom_end_date

                # IMPORTANT: Get date strings from query_executor.get_date_range() immediately
                # after date filter selection, as _render_object_value_search_and_select
                # now requires them.
                filters["start_date_str"], filters["end_date_str"] = (
                    query_executor_instance.get_date_range(
                        filters.get("date_filter", default_date_filter),
                        filters.get("custom_start"),
                        filters.get("custom_end"),
                    )
                )

                with col2:
                    # Leverage the new _render_object_type_filter method
                    selected_object_type = self._render_object_type_filter(
                        default_object_type
                    )
                    filters["object_type"] = selected_object_type

                    # Leverage the new _render_object_value_search_and_select method
                    # Pass the 'filters' dictionary which now contains 'start_date_str'/'end_date_str'
                    selected_object_value = self._render_object_value_search_and_select(
                        query_executor_instance, filters["object_type"], filters
                    )
                    filters["object_value"] = selected_object_value

            return filters  # Always return the filters dictionary in the success path

        except Exception as e:
            logger.error(f"Error rendering filters in common_ui: {e}", exc_info=True)
            # IMPORTANT: Always return a dictionary even if an error occurs
            # This prevents the 'NoneType' error in downstream components
            # Return reasonable default filters to prevent cascading errors
            return {
                "date_filter": default_date_filter,
                "start_date_str": (datetime.now() - timedelta(days=7)).strftime(
                    "%Y-%m-%d"
                ),
                "end_date_str": datetime.now().strftime("%Y-%m-%d"),
                "object_type": default_object_type,
                "object_value": "All",
                "error_rendering_filters": f"An error occurred while setting up filters: {e}",
            }


    # --- New Helper Methods for simplified Metric/Chart Rendering from keys ---

    def render_single_metric_from_key(
        self,
        metric_key: str,
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        metric_renderer_instance: Any, # Type hint 'MetricRenderer' when importing it
        label: Optional[str] = None,
        description: Optional[str] = None,
        format_type: Optional[str] = None,
        delta_query_key: Optional[str] = None,
        metrics_per_row: int = 4,
    ):
        """
        Renders a single metric by its key from the query store.
        Automatically retrieves label, description, and format from query_store if not overridden.

        Args:
            metric_key (str): The key of the metric in the query_store.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.
            metric_renderer_instance (MetricRenderer): An instance of MetricRenderer.
            label (Optional[str]): Override label for the metric.
            description (Optional[str]): Override description for the metric.
            format_type (Optional[str]): Override format type (number, percentage, currency, duration).
            delta_query_key (Optional[str]): Override delta query key.
            metrics_per_row (int): Number of metrics per row for the grid layout.
        """
        metric_config = {
            "query_key": metric_key,
            "label": label,
            "description": description,
            "format_type": format_type,
            "delta_query_key": delta_query_key,
        }
        
        # metric_renderer_instance.render_multiple expects a list of configs
        metrics_to_render = metric_renderer_instance.render_multiple(
            [metric_config], query_store, filters
        )
        self.render_metric_grid(metrics_to_render, metrics_per_row=metrics_per_row)


    def render_metrics_from_keys(
        self,
        metric_configs: List[Union[str, Dict[str, Any]]], # Can be string key or dict config
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        metric_renderer_instance: Any, # Type hint 'MetricRenderer'
        metrics_per_row: int = 4,
    ):
        """
        Renders multiple metrics based on a list of keys or config dictionaries.

        Args:
            metric_configs (List[Union[str, Dict[str, Any]]]): A list of metric keys (strings)
                                                                or dictionaries specifying overrides.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.
            metric_renderer_instance (MetricRenderer): An instance of MetricRenderer.
            metrics_per_row (int): Number of metrics per row for the grid layout.
        """
        metrics_to_render = metric_renderer_instance.render_multiple(
            metric_configs, query_store, filters
        )
        self.render_metric_grid(metrics_to_render, metrics_per_row=metrics_per_row)


    def render_single_chart_from_key(
        self,
        chart_key: str,
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        chart_renderer_instance: Any, # Type hint 'ChartRenderer'
        chart_type: Optional[str] = None,
        label: Optional[str] = None,
        x_col: Optional[str] = None,
        y_col: Optional[str] = None,
        value_col: Optional[str] = None,
        color_col: Optional[str] = None,
        hover_data: Optional[list] = None,
        show_table_toggle: Optional[bool] = None, # Allow override for this
        charts_per_row: int = 2,
    ):
        """
        Renders a single chart by its key from the query store.
        Automatically retrieves chart type, label, description, etc., from query_store if not overridden.

        Args:
            chart_key (str): The key of the chart in the query_store.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.
            chart_renderer_instance (ChartRenderer): An instance of ChartRenderer.
            chart_type (Optional[str]): Override chart type.
            label (Optional[str]): Override label for the chart.
            x_col (Optional[str]): Override x-axis column.
            y_col (Optional[str]): Override y-axis column.
            value_col (Optional[str]): Override value column (for e.g., treemap, heatmap).
            color_col (Optional[str]): Override color column.
            hover_data (Optional[list]): Override hover data columns.
            show_table_toggle (Optional[bool]): Override default show_table_toggle behavior.
            charts_per_row (int): Number of charts per row for the grid layout.
        """
        chart_config = {
            "query_key": chart_key,
            "chart_type": chart_type,
            "label": label,
            "x_col": x_col,
            "y_col": y_col,
            "value_col": value_col,
            "color_col": color_col,
            "hover_data": hover_data,
            # Only set if provided, otherwise let chart_renderer default
            **({"show_table_toggle": show_table_toggle} if show_table_toggle is not None else {}),
        }

        # chart_renderer_instance.render_multiple expects a list of configs
        charts_to_render = chart_renderer_instance.render_multiple(
            [chart_config], query_store, filters
        )
        self.render_chart_grid(charts_to_render, charts_per_row=charts_per_row)


    def render_charts_from_keys(
        self,
        chart_configs: List[Union[str, Dict[str, Any]]], # Can be string key or dict config
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        chart_renderer_instance: Any, # Type hint 'ChartRenderer'
        charts_per_row: int = 2,
    ):
        """
        Renders multiple charts based on a list of keys or config dictionaries.

        Args:
            chart_configs (List[Union[str, Dict[str, Any]]]): A list of chart keys (strings)
                                                               or dictionaries specifying overrides.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.
            chart_renderer_instance (ChartRenderer): An instance of ChartRenderer.
            charts_per_row (int): Number of charts per row for the grid layout.
        """
        charts_to_render = chart_renderer_instance.render_multiple(
            chart_configs, query_store, filters
        )
        self.render_chart_grid(charts_to_render, charts_per_row=charts_per_row)

# Instantiate the CommonUI class for global access
common_ui = CommonUI()