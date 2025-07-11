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
        """
        filters = {} # Initialize filters dictionary right at the start

        try:
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
                        if 'custom_start_date_val' not in st.session_state:
                            st.session_state['custom_start_date_val'] = default_custom_start
                        if 'custom_end_date_val' not in st.session_state:
                            st.session_state['custom_end_date_val'] = current_end_date

                        custom_date_col1, custom_date_col2 = st.columns(2)
                        with custom_date_col1:
                            custom_start_date = st.date_input(
                                "Start date",
                                value=st.session_state['custom_start_date_val'],
                                key="custom_start_date",
                                help="Select the beginning date for your custom range."
                            )
                        with custom_date_col2:
                            custom_end_date = st.date_input(
                                "End date",
                                value=st.session_state['custom_end_date_val'],
                                key="custom_end_date",
                                help="Select the end date for your custom range. Must be after start date."
                            )
                        
                        st.session_state['custom_start_date_val'] = custom_start_date
                        st.session_state['custom_end_date_val'] = custom_end_date

                        if custom_start_date and custom_end_date and custom_start_date > custom_end_date:
                            self.render_warning_message(
                                "Invalid Date Range", "Start date cannot be after end date. Please adjust."
                            )
                            # Set valid defaults for downstream, even if UI shows warning
                            filters["custom_start"] = current_end_date - timedelta(days=7)
                            filters["custom_end"] = current_end_date
                        else:
                            filters["custom_start"] = custom_start_date
                            filters["custom_end"] = custom_end_date
                    else:
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
                    if default_object_type not in object_type_options.values():
                        default_object_type = "all"

                    default_object_label = next(
                        (label for label, val in object_type_options.items() if val == default_object_type),
                        "All Objects"
                    )
                    
                    selected_object_type_label = st.selectbox(
                        "Filter by a specific object type:",
                        options=list(object_type_options.keys()),
                        index=list(object_type_options.keys()).index(default_object_label),
                        key="object_type_selector",
                        help="Select a type (e.g., User, Warehouse) to focus your analysis on specific entities."
                    )
                    filters["object_type"] = object_type_options[selected_object_type_label]

                    filters["object_value"] = "All"

                    if filters["object_type"] != "all":
                        search_term = st.text_input(
                            f"Search for a specific {filters['object_type']}:",
                            key=f"search_input_{filters['object_type']}",
                            placeholder=f"Type to search {filters['object_type']}...",
                            help=f"Begin typing to filter the dropdown list for a specific {filters['object_type']}."
                        ).strip()

                        object_values = query_executor_instance.get_object_values(
                            filters["object_type"], search_term
                        )
                        
                        if "All" not in object_values:
                            object_values.insert(0, "All")
                        
                        session_state_key = f"object_value_{filters['object_type']}_selector"

                        # Ensure session state for the specific object_value selector is initialized/valid
                        if session_state_key not in st.session_state or \
                           st.session_state[session_state_key] not in object_values:
                            st.session_state[session_state_key] = "All"
                        
                        default_index_for_selectbox = object_values.index(st.session_state[session_state_key])

                        selected_object_value = st.selectbox(
                            f"Select {filters['object_type']}:",
                            options=object_values,
                            index=default_index_for_selectbox,
                            key=session_state_key,
                            help=f"Select 'All' to view aggregated data, or choose a specific {filters['object_type']}."
                        )
                        
                        filters["object_value"] = selected_object_value
                    else:
                        filters["object_value"] = "All" # Explicitly set to 'All' if 'All Objects' is selected

            # Get date strings from query_executor.get_date_range()
            # This must happen after filters['date_filter'] and custom_start/end are set
            filters["start_date_str"], filters["end_date_str"] = query_executor_instance.get_date_range(
                filters["date_filter"],
                filters.get("custom_start"), # Use .get() defensively here as well
                filters.get("custom_end")
            )

            return filters # Ensure filters dictionary is always returned
            
        except Exception as e:
            logger.error(f"Error rendering filters in common_ui: {e}", exc_info=True)
            # IMPORTANT: Always return a dictionary even if an error occurs
            # This prevents the 'NoneType' error in downstream components
            return {
                "date_filter": default_date_filter,
                "start_date_str": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "end_date_str": datetime.now().strftime("%Y-%m-%d"),
                "object_type": default_object_type,
                "object_value": "All",
                "error_rendering_filters": f"Failed to render filters: {e}" # Add an error flag
            }

    
    
    
    
    
    
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