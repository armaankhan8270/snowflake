# components/common_ui.py - Comprehensive Fix to ensure filters is always a Dict

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


class CommonUI:
    def render_info_message(self, title: str, message: str):
        with st.info(title):
            st.write(message)

    def render_warning_message(self, title: str, message: str):
        with st.warning(title):
            st.write(message)

    def render_error_message(self, title: str, message: str):
        with st.error(title):
            st.write(message)

    def render_page_header(self, title: str, description: str, icon: str = "📊"):
        st.markdown(f"## {icon} {title}")
        st.markdown(description)
        st.markdown("---")

    def render_metric_grid(self, metrics: List[Dict[str, Any]]):
        """
        Renders a grid of metric cards.

        Args:
            metrics (List[Dict[str, Any]]): A list of dictionaries, where each dict
                                             contains 'label', 'value', 'delta' (optional),
                                             'description' (optional), and 'error' (optional).
        """
        if not metrics:
            self.render_info_message(
                "No Metrics Available", "No metrics were provided to display."
            )
            return

        cols = st.columns(len(metrics))
        for i, metric in enumerate(metrics):
            with cols[i]:
                with st.container(border=True):
                    # Check for 'error' key first
                    if "error" in metric:
                        self.render_error_message(
                            f"Error Loading {metric.get('label', 'Metric')}",
                            metric["error"],
                        )
                    else:
                        st.subheader(metric.get("label", "N/A"))
                        st.metric(
                            label="Value",
                            value=metric.get("value", "N/A"),
                            delta=metric.get("delta"),
                        )
                        if metric.get("description"):
                            st.caption(metric["description"])

    def render_chart_grid(self, charts: List[Dict[str, Any]]):
        """
        Renders a grid of charts with optional data tables.

        Args:
            charts (List[Dict[str, Any]]): A list of dictionaries, where each dict
                                            contains 'figure', 'data', 'label',
                                            'description', 'show_table_toggle', and 'error'.
        """
        if not charts:
            self.render_info_message(
                "No Charts Available", "No charts were provided to display."
            )
            return

        # Distribute charts evenly, up to 2 per row
        num_charts = len(charts)
        for i in range(0, num_charts, 2):
            cols = st.columns(min(2, num_charts - i))  # Ensure no more than 2 columns
            for j in range(min(2, num_charts - i)):
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
                            st.plotly_chart(chart["figure"], use_container_width=True)

                            # Optional: Toggle for data table
                            if (
                                chart.get("show_table_toggle", False)
                                and not chart["data"].empty
                            ):
                                if st.toggle(
                                    f"Show data for {chart['label']}",
                                    key=f"toggle_data_{chart['label'].replace(' ', '_')}",
                                ):
                                    st.dataframe(chart["data"])

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
        filters: Dict[str, Any] = {}  # Ensure filters is always initialized as a Dict

        try:
            st.markdown("### 🔍 Dashboard Filters")
            st.markdown(
                "Easily refine your data by selecting specific time ranges or objects."
            )

            with st.container(border=True):
                col1, col2 = st.columns([1, 1])

                with col1:
                    # --- Date Filter ---
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
                        else 1
                    )

                    selected_date_filter_label = st.selectbox(
                        "Select a preset date range or define a custom one:",
                        options=list(date_filter_options.keys()),
                        index=default_date_index,
                        key="date_range_selector",
                        help="Choose a predefined period or set exact start/end dates for your analysis.",
                    )
                    filters["date_filter"] = date_filter_options[
                        selected_date_filter_label
                    ]

                    custom_start_date: Optional[datetime.date] = None
                    custom_end_date: Optional[datetime.date] = None

                    if filters["date_filter"] == "custom":
                        current_end_date = datetime.now().date()
                        default_custom_start = current_end_date - timedelta(days=7)

                        # Initialize custom date values in session state only if they don't exist
                        if "custom_start_date_val" not in st.session_state:
                            st.session_state["custom_start_date_val"] = (
                                default_custom_start
                            )
                        if "custom_end_date_val" not in st.session_state:
                            st.session_state["custom_end_date_val"] = current_end_date

                        custom_date_col1, custom_date_col2 = st.columns(2)
                        with custom_date_col1:
                            custom_start_date = st.date_input(
                                "Start date",
                                value=st.session_state["custom_start_date_val"],
                                key="custom_start_date",
                                help="Select the beginning date for your custom range.",
                            )
                        with custom_date_col2:
                            custom_end_date = st.date_input(
                                "End date",
                                value=st.session_state["custom_end_date_val"],
                                key="custom_end_date",
                                help="Select the end date for your custom range. Must be after start date.",
                            )

                        # Crucially, update session state with the *returned* values from date_input
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
                            filters["custom_start"] = current_end_date - timedelta(
                                days=7
                            )
                            filters["custom_end"] = current_end_date
                        else:
                            filters["custom_start"] = custom_start_date
                            filters["custom_end"] = custom_end_date
                    else:
                        # Clear custom date session state keys when not in custom mode
                        # This avoids carrying over custom dates when switching to preset ranges
                        # Only delete if they exist to prevent KeyError
                        if "custom_start_date_val" in st.session_state:
                            del st.session_state["custom_start_date_val"]
                        if "custom_end_date_val" in st.session_state:
                            del st.session_state["custom_end_date_val"]

                with col2:
                    # --- Object Filter ---
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
                        index=list(object_type_options.keys()).index(
                            default_object_label
                        ),
                        key="object_type_selector",
                        help="Select a type (e.g., User, Warehouse) to focus your analysis on specific entities.",
                    )
                    filters["object_type"] = object_type_options[
                        selected_object_type_label
                    ]

                    # Initialize object_value here based on object_type
                    filters["object_value"] = (
                        "All"  # Default for 'all' or when no specific object is selected
                    )

                    if filters["object_type"] != "all":
                        search_term = st.text_input(
                            f"Search for a specific {filters['object_type']}:",
                            key=f"search_input_{filters['object_type']}",
                            placeholder=f"Type to search {filters['object_type']}...",
                            help=f"Begin typing to filter the dropdown list for a specific {filters['object_type']}.",
                        ).strip()

                        object_values = query_executor_instance.get_object_values(
                            filters["object_type"], search_term
                        )

                        if "All" not in object_values:
                            object_values.insert(0, "All")

                        session_state_key = (
                            f"object_value_{filters['object_type']}_selector"
                        )

                        # Ensure session state for the specific object_value selector is initialized/valid
                        if (
                            session_state_key not in st.session_state
                            or st.session_state[session_state_key] not in object_values
                        ):
                            st.session_state[session_state_key] = "All"

                        default_index_for_selectbox = object_values.index(
                            st.session_state[session_state_key]
                        )

                        selected_object_value = st.selectbox(
                            f"Select {filters['object_type']}:",
                            options=object_values,
                            index=default_index_for_selectbox,
                            key=session_state_key,
                            help=f"Select 'All' to view aggregated data, or choose a specific {filters['object_type']}.",
                        )

                        filters["object_value"] = selected_object_value
                    # No else needed here; filters["object_value"] is already "All" by default or set above.

            # Get date strings from query_executor.get_date_range()
            # This must happen after filters['date_filter'] and custom_start/end are set
            # Ensure filters.get() is used for custom_start/end as they might not always be in filters
            filters["start_date_str"], filters["end_date_str"] = (
                query_executor_instance.get_date_range(
                    filters.get(
                        "date_filter", default_date_filter
                    ),  # Use .get() defensively here too
                    filters.get("custom_start"),
                    filters.get("custom_end"),
                )
            )

            return filters  # Ensure filters dictionary is always returned in the success path

        except Exception as e:
            logger.error(f"Error rendering filters in common_ui: {e}", exc_info=True)
            # IMPORTANT: Always return a dictionary even if an error occurs
            # This prevents the 'NoneType' error in downstream components
            # Return reasonable default filters
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


# Instantiate the CommonUI class for global access
common_ui = CommonUI()
