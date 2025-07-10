# components/chart_renderer.py - PROPOSED MINOR REFINEMENTS FOR ERROR HANDLING
"""
Chart renderer for dashboard
Handles chart creation and rendering with toggle support
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)


class ChartRenderer:
    """Handles chart rendering with toggle support"""

    def __init__(self, query_executor_instance: Any):
        self.query_executor = query_executor_instance
        self.default_colors = px.colors.qualitative.Plotly # More professional color set

    def render(
        self,
        query_key: str,
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        chart_type: Optional[str] = None,
        label: Optional[str] = None,
        x_col: Optional[str] = None,
        y_col: Optional[str] = None,
        value_col: Optional[str] = None,
        color_col: Optional[str] = None,
        hover_data: Optional[list] = None,
        show_table_toggle: bool = False,
        container_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Render a chart from query store

        Args:
            query_key: Key to identify query in store
            query_store: Dictionary containing all queries
            filters: Filter values from UI (date, object type, object value)
            chart_type: Override chart type from query_store
            label: Override label for chart
            x_col: Override x column
            y_col: Override y column
            value_col: Override value column (for e.g., treemap, heatmap)
            color_col: Override color column (for multi-series)
            hover_data: Override hover_data columns
            show_table_toggle: Flag to indicate if a table toggle should be shown for this chart.
            container_key: Unique key for container (used internally for session state management)

        Returns:
            Dictionary containing chart data and Plotly figure, or error info.
        """
        current_label = label or query_key # Default label for error reporting

        try:
            if not isinstance(query_key, str) or query_key not in query_store:
                error_msg = f"Chart query key '{query_key}' not found or invalid in query store."
                logger.error(error_msg)
                return {"error": error_msg, "label": current_label}

            query_config = query_store[query_key]
            current_label = label or query_config.get("label", "Chart") # Update label if config has it

            # Build query parameters, considering `apply_object_filter`
            params = self._build_query_params(filters, query_config)

            # Execute query
            df = self.query_executor.execute_query(query_config["query"], params)

            if df.empty:
                # Check if the error came from query_executor (logged there) or just no data
                if "error" in st.session_state and "Query Execution Error" in st.session_state.get("last_error", ""):
                     # This indicates a query execution error, let common_ui pick it up from there
                     return {"error": st.session_state.get("last_error", "An unexpected query error occurred."), "label": current_label}
                else:
                    return {
                        "error": f"No data found for '{current_label}' with selected filters.",
                        "label": current_label,
                    }

            # Create unique key for this chart (for Streamlit elements like toggles)
            chart_unique_key = container_key or f"chart_render_{query_key}"

            # Handle toggle options for chart data presentation (e.g., by count vs. by time)
            current_toggle_option = self._handle_toggle_options(
                query_config, chart_unique_key
            )

            # Get final chart configuration including potential toggle overrides
            chart_final_config = self._get_chart_config(
                query_config, current_toggle_option, chart_type, x_col, y_col, value_col, color_col, hover_data
            )

            # Create chart figure
            figure = self._create_chart(df, chart_final_config)

            # If _create_chart returned an error figure/message
            if "error" in figure: # This is a custom check within this class
                return {"error": figure["error"], "label": current_label}


            return {
                "figure": figure,
                "data": df,  # Include data for table toggle in common_ui
                "label": current_label,
                "description": query_config.get("description", ""),
                "show_table_toggle": show_table_toggle,  # Pass this flag
            }

        except Exception as e:
            error_msg = f"An unexpected error occurred while rendering chart '{current_label}': {str(e)}"
            logger.error(error_msg, exc_info=True) # Log full traceback
            return {
                "error": error_msg,
                "label": current_label,
            }

    def render_multiple(
        self, chart_configs: list, query_store: Dict[str, Any], filters: Dict[str, Any]
    ) -> list:
        """
        Render multiple charts

        Args:
            chart_configs: List of chart configuration dictionaries.
                           Each dict must contain 'query_key' and can override other render args.
            query_store: Dictionary containing all queries
            filters: Filter values from UI

        Returns:
            List of chart dictionaries
        """
        charts = []
        for i, config_item in enumerate(chart_configs):
            if isinstance(config_item, str):
                # Simple string key - fetch config from query_store
                query_key = config_item
                # Attempt to get default show_table_toggle from query_store config
                default_show_table = query_store.get(query_key, {}).get("show_table_toggle", False)
                chart_args = {
                    "query_key": query_key,
                    "show_table_toggle": default_show_table,
                    "container_key": f"chart_multi_{i}"
                }
            elif isinstance(config_item, dict):
                # Dictionary with additional options
                chart_args = {**config_item} # Copy the dict to avoid modifying original
                chart_args["container_key"] = f"chart_multi_{i}"
            else:
                logger.warning(f"Invalid chart config type: {type(config_item)}. Skipping.")
                continue

            query_key_to_render = chart_args.get("query_key")
            if not query_key_to_render:
                logger.error(f"Chart config at index {i} is missing 'query_key'. Skipping.")
                charts.append({"error": "Missing 'query_key' in chart configuration.", "label": "Unnamed Chart"})
                continue

            chart = self.render(
                query_key=query_key_to_render,
                query_store=query_store,
                filters=filters,
                chart_type=chart_args.get("chart_type"),
                label=chart_args.get("label"),
                x_col=chart_args.get("x_col"),
                y_col=chart_args.get("y_col"),
                value_col=chart_args.get("value_col"),
                color_col=chart_args.get("color_col"),
                hover_data=chart_args.get("hover_data"),
                show_table_toggle=chart_args.get("show_table_toggle", False),
                container_key=chart_args.get("container_key"),
            )
            charts.append(chart)
        return charts

    def _build_query_params(self, filters: Dict[str, Any], query_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build query parameters from filters, respecting the `apply_object_filter` flag in query_config.
        """
        start_date, end_date = self.query_executor.get_date_range(
            filters.get("date_filter", "7_days"), # Default to '7_days'
            filters.get("custom_start"),
            filters.get("custom_end"),
        )

        object_filter_clause = ""
        # Determine if the object filter should be applied for this specific query
        apply_filter_for_this_query = query_config.get("apply_object_filter", True)

        if apply_filter_for_this_query:
            object_type = filters.get("object_type", "all")
            object_value = filters.get("object_value", "").strip()

            # Only apply filter if a specific object is selected AND it's not 'All'
            if object_type != "all" and object_value and object_value.lower() != "all":
                col_map = {
                    "user": "USER_NAME",
                    "warehouse": "WAREHOUSE_NAME",
                    "role": "ROLE_NAME",
                    "database": "DATABASE_NAME",
                }
                column_name = col_map.get(object_type)
                if column_name:
                    # Sanitize object_value to prevent SQL injection (basic, for user-provided string)
                    # For production, consider using Snowpark's parameter binding fully or more robust sanitization.
                    sanitized_object_value = object_value.replace("'", "''")
                    object_filter_clause = f"AND {column_name} = '{sanitized_object_value}'"
                else:
                    logger.warning(f"No column mapping for object type: {object_type}. Object filter will not be applied.")
            # else: object_filter_clause remains empty if object_type is 'all' or object_value is 'All' or empty

        return {
            "start_date": start_date,
            "end_date": end_date,
            "object_filter": object_filter_clause,
        }


    def _handle_toggle_options(
        self, query_config: Dict[str, Any], chart_key: str
    ) -> str:
        """
        Handle toggle options for charts, storing state in session_state.

        Args:
            query_config: The configuration dictionary for the current chart query.
            chart_key: A unique key for Streamlit elements to maintain state.

        Returns:
            str: The key of the currently selected toggle option.
        """
        toggle_options = query_config.get("toggle_options", {})

        if not toggle_options:
            return "default"  # No toggles defined

        # Initialize session state for this chart's toggle if not already present
        session_state_key = f"{chart_key}_current_toggle"
        if session_state_key not in st.session_state:
            # Set default to the first option if available, otherwise 'default'
            st.session_state[session_state_key] = list(toggle_options.keys())[0] if toggle_options else "default"

        # Create a container for the buttons to keep them together visually
        st.write(f"**Toggle View:**") # Label for the toggle buttons
        toggle_cols = st.columns(len(toggle_options))

        for i, (key, config) in enumerate(toggle_options.items()):
            with toggle_cols[i]:
                # Check if this button is currently selected
                is_selected = st.session_state[session_state_key] == key

                if st.button(
                    config.get("label", key.replace("_", " ").title()),
                    key=f"{chart_key}_toggle_{key}",
                    type=("primary" if is_selected else "secondary"),  # Highlight selected button
                ):
                    # If a different button is clicked, update state and rerun
                    if not is_selected:
                        st.session_state[session_state_key] = key
                        st.rerun()  # Rerun to apply new toggle state and redraw chart

        return st.session_state[session_state_key]

    def _get_chart_config(
        self,
        query_config: Dict[str, Any],
        current_toggle: str,
        chart_type: Optional[str] = None,
        x_col: Optional[str] = None,
        y_col: Optional[str] = None,
        value_col: Optional[str] = None, # New parameter
        color_col: Optional[str] = None, # New parameter
        hover_data: Optional[list] = None, # New parameter
    ) -> Dict[str, Any]:
        """
        Get chart configuration based on toggle state and overrides.
        Prioritizes explicit `render` call arguments, then toggle config, then base query config.
        """
        # Start with base query config
        config = {
            "chart_type": query_config.get("chart_type", "bar"),
            "x_col": query_config.get("x_col"),
            "y_col": query_config.get("y_col"),
            "value_col": query_config.get("value_col"),
            "label": query_config.get("label", "Chart Title"),
            "color_col": query_config.get("color_col", None),
            "hover_data": query_config.get("hover_data", []),
            "color_continuous_scale": query_config.get("color_continuous_scale", "Viridis") # For heatmaps
        }

        # Apply toggle-specific config if it exists and is not 'default'
        toggle_options = query_config.get("toggle_options", {})
        if current_toggle != "default" and current_toggle in toggle_options:
            toggle_config = toggle_options[current_toggle]
            # Update specific keys from toggle config, allowing overrides for chart type, x, y, value, color, hover, format etc.
            config.update(toggle_config)

        # Apply explicit override arguments from render() call (highest priority)
        if chart_type is not None: config["chart_type"] = chart_type
        if x_col is not None: config["x_col"] = x_col
        if y_col is not None: config["y_col"] = y_col
        if value_col is not None: config["value_col"] = value_col
        if color_col is not None: config["color_col"] = color_col
        if hover_data is not None: config["hover_data"] = hover_data
        if label is not None: config["label"] = label # Label override from render call

        return config

    def _create_chart(self, df: pd.DataFrame, config: Dict[str, Any]) -> go.Figure | Dict[str, str]:
        """
        Create a Plotly figure based on the provided DataFrame and configuration.
        Improved robustness for missing columns and various chart types.
        Returns a Plotly Figure or a dictionary with an "error" key.
        """
        chart_type = config.get("chart_type", "bar").lower()
        x_col = config.get("x_col")
        y_col = config.get("y_col")
        label = config.get("label", "Chart")
        color_col = config.get("color_col")
        value_col = config.get("value_col")
        hover_data = config.get("hover_data", [])
        color_continuous_scale = config.get("color_continuous_scale", "Viridis")

        # Ensure columns exist in DataFrame, if not, log a warning and return error dict.
        required_cols = []
        if chart_type in ["bar", "line", "scatter", "box", "area", "histogram"]:
            if x_col: required_cols.append(x_col)
            if y_col: required_cols.append(y_col) # y_col for histogram is optional (count)
            if color_col: required_cols.append(color_col)
        elif chart_type == "pie":
            if x_col: required_cols.append(x_col) # names
            if y_col: required_cols.append(y_col) # values
        elif chart_type == "heatmap":
            if x_col: required_cols.append(x_col)
            if y_col: required_cols.append(y_col)
            if value_col: required_cols.append(value_col)
        elif chart_type == "treemap":
            # Treemap path can be multiple columns. x_col is first path element, y_col can be second.
            if x_col: required_cols.append(x_col) # primary path
            if y_col and y_col in df.columns: required_cols.append(y_col) # secondary path
            if value_col: required_cols.append(value_col)

        # Check for required columns and hover data columns
        missing_cols = [col for col in required_cols if col and col not in df.columns]
        if missing_cols:
            error_msg = f"Missing required columns for chart '{label}' (type: {chart_type}): {', '.join(missing_cols)}. Available columns: {df.columns.tolist()}"
            logger.error(error_msg)
            # Return an error dictionary so the calling function can display it.
            return {"error": error_msg}


        valid_hover_data = [col for col in hover_data if col in df.columns]
        if len(valid_hover_data) != len(hover_data):
            logger.warning(f"Some requested hover_data columns not found for chart '{label}': {list(set(hover_data) - set(valid_hover_data))}. Using valid columns: {valid_hover_data}")


        # Chart rendering logic
        try:
            # Ensure proper types for columns for plotting
            for col in [x_col, y_col, value_col, color_col] + valid_hover_data:
                if col and col in df.columns:
                    try:
                        # Attempt to coerce numeric columns to numeric types if they aren't already
                        if pd.api.types.is_numeric_dtype(df[col]):
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        # Attempt to coerce date columns to datetime
                        elif 'DATE' in col.upper() and not pd.api.types.is_datetime64_any_dtype(df[col]):
                            df[col] = pd.to_datetime(df[col], errors='coerce')
                    except Exception as e:
                        logger.warning(f"Could not coerce column '{col}' to appropriate type for plotting in chart '{label}': {e}")


            fig = go.Figure() # Initialize empty figure for generic updates if needed

            if chart_type == "bar":
                fig = px.bar(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "line":
                fig = px.line(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    markers=True,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "area":
                fig = px.area(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "box":
                fig = px.box(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    points="all",
                    hover_data=valid_hover_data,
                )
            elif chart_type == "histogram":
                fig = px.histogram(
                    df,
                    x=x_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    nbins=50,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "pie":
                fig = px.pie(
                    df,
                    names=x_col,
                    values=y_col,
                    title=label,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "scatter":
                fig = px.scatter(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "heatmap":
                if not all([x_col, y_col, value_col]): # Redundant check but good for clarity
                    raise ValueError("Heatmap requires x_col, y_col, and value_col.")
                fig = px.density_heatmap(
                    df,
                    x=x_col,
                    y=y_col,
                    z=value_col,
                    title=label,
                    color_continuous_scale=color_continuous_scale,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "treemap":
                if not all([x_col, value_col]):
                    raise ValueError("Treemap requires x_col (for path) and value_col (for values).")
                path_cols = [x_col]
                if y_col and y_col in df.columns: # Allow a second level for path if y_col is provided
                    path_cols.append(y_col)
                fig = px.treemap(
                    df,
                    path=path_cols,
                    values=value_col,
                    title=label,
                    hover_data=valid_hover_data,
                    color_discrete_sequence=self.default_colors,
                )
            elif chart_type == "table":
                # Ensure all columns for the table exist
                table_cols = [c for c in df.columns if c in df.columns] # All existing columns
                if table_cols:
                    header_values = table_cols
                    cell_values = [df[col].tolist() for col in table_cols]
                    fig = go.Figure(
                        data=[
                            go.Table(
                                header=dict(
                                    values=header_values,
                                    fill_color="paleturquoise",
                                    align="left",
                                    font=dict(size=12, color="black")
                                ),
                                cells=dict(
                                    values=cell_values, fill_color="lavender", align="left",
                                    font=dict(size=11, color="black")
                                ),
                            )
                        ]
                    )
                    fig.update_layout(title_text=label, title_x=0.5, height=400, margin=dict(l=10, r=10, t=50, b=10))
                else:
                    # If somehow no columns are left after validation (shouldn't happen here, but defensive)
                    return {"error": f"No valid columns found for table chart '{label}'."}
            else:
                logger.warning(
                    f"Unsupported chart type '{chart_type}'. Defaulting to bar chart."
                )
                fig = px.bar(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )

            # Apply common layout updates
            fig.update_layout(
                showlegend=True,
                height=400,
                margin=dict(l=20, r=20, t=50, b=20),
                title_font_size=20,
                title_x=0.5,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title_font_size=14,
                yaxis_title_font_size=14,
                legend_title_font_size=14,
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=12,
                    font_family="Arial"
                )
            )
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGrey', zeroline=True, zerolinewidth=1, zerolinecolor='LightGrey', showline=False)
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGrey', zeroline=True, zerolinewidth=1, zerolinecolor='LightGrey', showline=False)


            return fig

        except Exception as e:
            error_msg = f"Error creating Plotly chart for '{label}' (type: {chart_type}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Return an error dictionary instead of a Plotly figure for consistent error handling
            return {"error": error_msg}

        