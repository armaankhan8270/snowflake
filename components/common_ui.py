# components/common_ui.py - PROPOSED MODIFICATIONS
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

class CommonUI:
    """
    Provides common UI components and utilities for the Snowflake Analytics Dashboard.
    Ensures a consistent, elegant, and user-friendly design.
    """

    def render_page_header(self, title: str, description: str, icon: str = "✨"):
        """
        Renders a sleek and informative page header with an icon.

        Args:
            title (str): The main title of the page.
            description (str): A brief description of the dashboard's purpose.
            icon (str): An emoji icon to display next to the title.
        """
        st.markdown(
            f"""
            <div style="
                display: flex;
                align-items: center;
                gap: 15px;
                padding: 20px;
                border-bottom: 2px solid #e0e0e0;
                margin-bottom: 30px;
                background-color: #f9f9f9;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            ">
                <span style="font-size: 3rem;">{icon}</span>
                <div>
                    <h1 style="margin: 0; padding: 0; font-size: 2.5rem; color: #333;">{title}</h1>
                    <p style="margin: 0; padding: 0; color: #666; font-size: 1.1rem;">{description}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render_filters(
        self,
        query_executor_instance: Any,
        default_object_type: str = "all", # 'user', 'role', 'warehouse', 'database', 'all'
        default_date_filter: str = "7_days", # '1_day', '7_days', '14_days', '1_month', '3_months', '6_months', '1_year', 'custom'
    ) -> Dict[str, Any]:
        """
        Renders interactive date and object type filters in a visually appealing container.
        Includes search functionality for object values and intelligent defaults.

        Args:
            query_executor_instance: An instance of QueryExecutor to fetch filter options.
            default_object_type (str): The default object type to select in the filter (e.g., 'user', 'role').
                                       Use 'all' if no specific object type is preferred for the page.
            default_date_filter (str): The default date range filter to apply.

        Returns:
            Dict[str, Any]: A dictionary containing the selected filter values.
        """
        filters = {}

        st.markdown("### 🔍 Dashboard Filters")
        st.markdown("Easily refine your data by selecting specific time ranges or objects.")

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
                
                # Find the default index for date filter
                default_date_index = list(date_filter_options.values()).index(default_date_filter) \
                    if default_date_filter in list(date_filter_options.values()) else 1 # Default to 7 days if not found

                selected_date_filter_label = st.selectbox(
                    "Select a preset date range or define a custom one:",
                    options=list(date_filter_options.keys()),
                    index=default_date_index,
                    key="date_range_selector",
                    help="Choose a predefined period or set exact start/end dates for your analysis."
                )
                filters["date_filter"] = date_filter_options[selected_date_filter_label]

                custom_start_date: Optional[datetime.date] = None
                custom_end_date: Optional[datetime.date] = None

                if filters["date_filter"] == "custom":
                    current_end_date = datetime.now().date()
                    default_custom_start = current_end_date - timedelta(days=7)

                    # Initialize custom date values in session state only if they don't exist
                    # This prevents resetting values if user has already picked them
                    if 'custom_start_date_val' not in st.session_state:
                        st.session_state['custom_start_date_val'] = default_custom_start
                    if 'custom_end_date_val' not in st.session_state:
                        st.session_state['custom_end_date_val'] = current_end_date

                    custom_date_col1, custom_date_col2 = st.columns(2)
                    with custom_date_col1:
                        custom_start_date = st.date_input(
                            "Start date",
                            value=st.session_state['custom_start_date_val'], # Read from session state
                            key="custom_start_date",
                            help="Select the beginning date for your custom range."
                        )
                    with custom_date_col2:
                        custom_end_date = st.date_input(
                            "End date",
                            value=st.session_state['custom_end_date_val'], # Read from session state
                            key="custom_end_date",
                            help="Select the end date for your custom range. Must be after start date."
                        )
                    
                    # Update session state values after st.date_input returns (this is how date_input works)
                    st.session_state['custom_start_date_val'] = custom_start_date
                    st.session_state['custom_end_date_val'] = custom_end_date


                    # Basic validation for custom dates
                    if custom_start_date and custom_end_date and custom_start_date > custom_end_date:
                        self.render_warning_message(
                            "Invalid Date Range", "Start date cannot be after end date. Please adjust."
                        )
                        # Optionally, set a default valid range to prevent errors downstream
                        filters["custom_start"] = current_end_date - timedelta(days=7)
                        filters["custom_end"] = current_end_date
                    else:
                        filters["custom_start"] = custom_start_date
                        filters["custom_end"] = custom_end_date
                else:
                    # Clear custom date session state if not in custom mode
                    # This avoids carrying over custom dates when switching to preset ranges
                    if 'custom_start_date_val' in st.session_state:
                        del st.session_state['custom_start_date_val']
                    if 'custom_end_date_val' in st.session_state:
                        del st.session_state['custom_end_date_val']


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
                # Ensure default_object_type is a valid key in object_type_options values
                if default_object_type not in object_type_options.values():
                    default_object_type = "all" # Fallback if invalid

                # Find the label for the default object type value
                default_object_label = next(
                    (label for label, val in object_type_options.items() if val == default_object_type),
                    "All Objects" # Default to "All Objects" if not found
                )
                
                # The object_type_selector widget. Its value is now in st.session_state.object_type_selector
                selected_object_type_label = st.selectbox(
                    "Filter by a specific object type:",
                    options=list(object_type_options.keys()),
                    index=list(object_type_options.keys()).index(default_object_label),
                    key="object_type_selector",
                    help="Select a type (e.g., User, Warehouse) to focus your analysis on specific entities."
                )
                filters["object_type"] = object_type_options[selected_object_type_label]

                filters["object_value"] = "All" # Default object value

                if filters["object_type"] != "all":
                    search_term = st.text_input(
                        f"Search for a specific {filters['object_type']}:",
                        key=f"search_input_{filters['object_type']}",
                        placeholder=f"Type to search {filters['object_type']}...",
                        help=f"Begin typing to filter the dropdown list for a specific {filters['object_type']}.",
                    ).strip()

                    # Fetch object values using the query executor
                    object_values = query_executor_instance.get_object_values(
                        filters["object_type"], search_term
                    )
                    
                    # Ensure 'All' is always the first option and selected by default
                    if "All" not in object_values:
                        object_values.insert(0, "All")
                    
                    session_state_key = f"object_value_{filters['object_type']}_selector"

                    # --- CRITICAL RE-REFINEMENT HERE ---
                    # 1. Check if the session state key exists.
                    # 2. If it exists, check if its value is still valid in the current `object_values` list.
                    # 3. If it doesn't exist OR it's not valid, *then* initialize/reset it to "All" (or a suitable default).
                    # This must happen *before* the st.selectbox is called.

                    if session_state_key not in st.session_state or \
                       st.session_state[session_state_key] not in object_values:
                        # Initialize or reset the session state value *before* widget instantiation
                        st.session_state[session_state_key] = "All"
                    
                    # Now, the session state value is guaranteed to be valid and initialized correctly.
                    # Use the value from session state to find the correct index for the selectbox.
                    # `st.session_state[session_state_key]` will now hold either "All"
                    # or the user's previously selected, still valid, object.
                    default_index_for_selectbox = object_values.index(st.session_state[session_state_key])
                    # --- END CRITICAL RE-REFINEMENT ---

                    selected_object_value = st.selectbox(
                        f"Select {filters['object_type']}:",
                        options=object_values,
                        index=default_index_for_selectbox, # Use the correctly determined index
                        key=session_state_key, # Streamlit will automatically update this session state key
                        help=f"Select 'All' to view aggregated data, or choose a specific {filters['object_type']}."
                    )
                    
                    # Streamlit automatically updates st.session_state[session_state_key]
                    # with selected_object_value on the *next* rerun.
                    # So, we can directly read from it for the current `filters` dictionary.
                    filters["object_value"] = selected_object_value
                else:
                    # If object_type is 'all', ensure the object_value is 'All' and clear specific keys
                    filters["object_value"] = "All"
                    # Clean up specific object_value session state keys when 'All Objects' is selected
                    for key in list(st.session_state.keys()):
                        if key.startswith("object_value_") and key.endswith("_selector"):
                            # Check if the key corresponds to the object_type that *was* selected
                            # before switching to 'All Objects'. This is a bit tricky to manage perfectly.
                            # For simplicity, we can just ensure the 'All' value is set for the current context.
                            # A more robust solution might clear all previous object_value selectors,
                            # but that could be complex if multiple selectors are used elsewhere.
                            # For now, let's rely on the conditional initialization above.
                            pass # No need to delete here, the init logic handles it
    def render_metric_grid(self, metrics: List[Dict[str, Any]], columns: int = 3):
        """
        Renders metrics in a responsive grid layout using Streamlit columns.
        Enhanced styling for a cleaner look.

        Args:
            metrics (List[Dict[str, Any]]): A list of metric dictionaries,
                                            each ideally containing 'label', 'value', 'delta', 'description', 'error'.
            columns (int): Number of columns in the grid.
        """
        if not metrics:
            self.render_info_message("No Metrics Available", "No metric data to display for the selected filters.")
            return

        st.markdown(f"### 📊 Key Performance Indicators")
        st.markdown("At-a-glance overview of critical metrics related to your selection.")

        # Create columns for the grid
        metric_cols = st.columns(columns)

        for i, metric_data in enumerate(metrics):
            with metric_cols[i % columns]:
                if "error" in metric_data:
                    self.render_error_message(
                        metric_data.get("label", "Metric Error"),
                        metric_data["error"]
                    )
                else:
                    label = metric_data.get("label", "N/A")
                    value = metric_data.get("value", "N/A")
                    delta = metric_data.get("delta")
                    description = metric_data.get("description", "")

                    st.markdown(
                        f"""
                        <div style="
                            padding: 15px 20px;
                            border-radius: 8px;
                            background-color: #ffffff;
                            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                            border-left: 5px solid #4CAF50; /* Green accent for good health */
                            margin-bottom: 15px;
                            transition: transform 0.2s ease-in-out;
                        ">
                            <small style="color: #555; font-weight: bold; text-transform: uppercase;">{label}</small>
                            <h2 style="margin: 5px 0 10px 0; color: #333; font-size: 2.2rem;">{value}</h2>
                            {f'<p style="color: #28a745; font-size: 0.9rem; margin: 0;">Δ {delta}</p>' if delta else '<p style="color: #999; font-size: 0.9rem; margin: 0;">No delta available</p>'}
                            <p style="color: #888; font-size: 0.85rem; margin-top: 10px;">{description}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    def render_chart_grid(self, charts: List[Dict[str, Any]], columns: int = 2):
        """
        Renders charts in a responsive grid layout, with options to toggle data table view.

        Args:
            charts (List[Dict[str, Any]]): A list of chart dictionaries,
                                           each ideally containing 'figure', 'data', 'label', 'description', 'error', 'show_table_toggle'.
            columns (int): Number of columns in the grid.
        """
        if not charts:
            self.render_info_message("No Charts Available", "No chart data to display for the selected filters.")
            return

        st.markdown(f"### 📈 Visual Analytics")
        st.markdown("Interactive charts to visualize trends, distributions, and patterns.")

        chart_cols = st.columns(columns)

        for i, chart_data in enumerate(charts):
            with chart_cols[i % columns]:
                with st.container(border=True): # Use a container for each chart
                    if "error" in chart_data:
                        self.render_error_message(
                            chart_data.get("label", "Chart Error"),
                            chart_data["error"]
                        )
                    else:
                        label = chart_data.get("label", "Chart")
                        description = chart_data.get("description", "")
                        figure = chart_data.get("figure")
                        data_df = chart_data.get("data")
                        show_table_toggle = chart_data.get("show_table_toggle", False)

                        st.markdown(f"**{label}**")
                        if description:
                            st.caption(description)

                        if figure:
                            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
                        else:
                            self.render_warning_message(label, "Chart figure could not be generated.")

                        if show_table_toggle and data_df is not None and not data_df.empty:
                            # Use st.checkbox or st.toggle for a cleaner look
                            if st.button(
                                "Show Data Table",
                                key=f"toggle_table_{label.replace(' ', '_').replace('/', '')}_{i}"
                            ):
                                with st.expander(f"Data for '{label}'", expanded=True):
                                    st.dataframe(data_df, use_container_width=True)
                        elif show_table_toggle and (data_df is None or data_df.empty):
                             st.info("No data available for table view.")


    def render_info_message(self, title: str, message: str):
        """Renders an informative message in a distinct Streamlit info box."""
        st.info(f"**{title}**\n\n{message}", icon="ℹ️")

    def render_warning_message(self, title: str, message: str):
        """Renders a warning message in a distinct Streamlit warning box."""
        st.warning(f"**{title}**\n\n{message}", icon="⚠️")

    def render_error_message(self, title: str, message: str):
        """Renders an error message in a distinct Streamlit error box."""
        st.error(f"**{title}**\n\n{message}", icon="❌")

    def render_loading_spinner(self, text: str):
        """
        Renders a loading spinner. Use with 'with' statement.
        Example: `with common_ui.render_loading_spinner("Loading data..."):`
        """
        return st.spinner(text)

# Instantiate the CommonUI class for global access
common_ui = CommonUI()