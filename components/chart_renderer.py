# components/chart_renderer.py
"""
Chart renderer for dashboard
Handles chart creation and rendering with toggle support
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List, Union # Added Union for type hinting

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configure logging
logger = logging.getLogger(__name__)


class ChartRenderer:
    """Handles chart rendering with toggle support and advanced chart types"""

    def __init__(self, query_executor_instance: Any):
        self.query_executor = query_executor_instance
        self.default_colors = px.colors.qualitative.Plotly # More professional color set
        logger.info("ChartRenderer initialized with professional color set.")

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
        hover_data: Optional[List[str]] = None,
        path_cols: Optional[List[str]] = None, # New: for hierarchical charts like treemap, sunburst
        dimensions_cols: Optional[List[str]] = None, # New: for scatter matrix
        show_table_toggle: bool = False,
        container_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Render a chart from query store.

        Args:
            query_key: Key to identify query in store.
            query_store: Dictionary containing all queries.
            filters: Filter values from UI (date, object type, object value).
            chart_type: Override chart type from query_store.
            label: Override label for chart.
            x_col: Override x column.
            y_col: Override y column.
            value_col: Override value column (for e.g., treemap, heatmap).
            color_col: Override color column (for multi-series).
            hover_data: Override hover_data columns.
            path_cols: Override path columns for hierarchical charts (list of column names).
            dimensions_cols: Override dimensions for scatter matrix (list of column names).
            show_table_toggle: Flag to indicate if a table toggle should be shown for this chart.
            container_key: Unique key for container (used internally for session state management).

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
            # This is where the formatted_params for execute_queries_parallel are prepared.
            # The 'object_filter' string is built here for string.format().
            params = self._build_query_params(filters, query_config)

            # Execute query using the unified parallel execution method
            # We call execute_queries_parallel with a list containing only this one query job.
            query_job = (query_config, params, current_label) # Tuple: (config, formatted_params, label)
            results = self.query_executor.execute_queries_parallel([query_job])
            
            # Extract the result for this single query
            if results and results[0].get("data") is not None:
                df = results[0]["data"]
            else:
                # Handle cases where the query failed or returned no data
                error_from_executor = results[0].get("error", "Unknown error during query execution.") if results else "No result from query executor."
                
                # Check if the error came from query_executor (logged there) or just no data
                # If there's an error message from the executor, use it
                if "error" in results[0]:
                    return {"error": error_from_executor, "label": current_label}
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

            # Get final chart configuration including potential toggle overrides and render() overrides
            chart_final_config = self._get_chart_config(
                query_config, current_toggle_option, chart_type, x_col, y_col,
                current_label, value_col, color_col, hover_data, path_cols, dimensions_cols
            )

            # Create chart figure
            figure_or_error = self._create_chart(df, chart_final_config)

            # If _create_chart returned an error dictionary
            if "error" in figure_or_error:
                return {"error": figure_or_error["error"], "label": current_label}


            return {
                "figure": figure_or_error, # It's a go.Figure object now
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
        self, chart_configs: List[Union[str, Dict[str, Any]]], query_store: Dict[str, Any], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Render multiple charts in parallel.

        Args:
            chart_configs: List of chart configuration dictionaries or simple string keys.
                           Each dict must contain 'query_key' and can override other render args.
            query_store: Dictionary containing all queries.
            filters: Filter values from UI.

        Returns:
            List of chart dictionaries, each containing chart data and Plotly figure, or error info.
        """
        query_jobs = []
        # Store original chart_configs to map results back in order
        original_configs = [] 

        for i, config_item in enumerate(chart_configs):
            chart_args = {}
            if isinstance(config_item, str):
                query_key = config_item
                # Attempt to get default show_table_toggle from query_store config
                default_show_table = query_store.get(query_key, {}).get("show_table_toggle", False)
                chart_args = {
                    "query_key": query_key,
                    "show_table_toggle": default_show_table,
                    "container_key": f"chart_multi_{i}"
                }
            elif isinstance(config_item, dict):
                chart_args = {**config_item} # Copy the dict to avoid modifying original
                chart_args["container_key"] = f"chart_multi_{i}"
            else:
                logger.warning(f"Invalid chart config type: {type(config_item)}. Skipping.")
                continue
            
            original_configs.append(chart_args) # Keep track of original request

            query_key_to_render = chart_args.get("query_key")
            if not query_key_to_render or query_key_to_render not in query_store:
                logger.error(f"Chart config at index {i} is missing 'query_key' or key '{query_key_to_render}' not found. Skipping.")
                query_jobs.append(None) # Placeholder for invalid job to maintain index
                continue
            
            query_config = query_store[query_key_to_render]
            current_label = chart_args.get("label") or query_config.get("label", "Chart")

            # Build query parameters for this specific chart
            params = self._build_query_params(filters, query_config)
            query_jobs.append((query_config, params, current_label))
        
        # Filter out None entries (invalid jobs) before parallel execution
        valid_query_jobs = [job for job in query_jobs if job is not None]
        
        # Execute all valid queries in parallel
        # The result from execute_queries_parallel is a list of {"data": df} or {"error": msg} dicts
        parallel_query_results = self.query_executor.execute_queries_parallel(valid_query_jobs)

        charts = []
        # Iterate through original configurations to match results, handling skipped/errored ones
        valid_job_index = 0
        for i, original_config_item in enumerate(original_configs):
            if query_jobs[i] is None: # This was a skipped/invalid config
                charts.append({"error": "Invalid chart configuration provided.", "label": "Unnamed Chart"})
                continue

            query_key = original_config_item.get("query_key")
            query_config = query_store.get(query_key, {}) # Get config for label/description
            current_label = original_config_item.get("label") or query_config.get("label", "Chart")

            # Retrieve the result from the parallel execution results list
            query_result = parallel_query_results[valid_job_index]
            valid_job_index += 1 # Move to the next result for the next valid job

            if "error" in query_result:
                charts.append({"error": query_result["error"], "label": current_label})
                continue
            
            df = query_result["data"]

            if df.empty:
                charts.append({
                    "error": f"No data found for '{current_label}' with selected filters.",
                    "label": current_label,
                })
                continue

            # Create unique key for Streamlit elements like toggles within this chart
            chart_unique_key = original_config_item.get("container_key") or f"chart_render_multi_{query_key}_{i}"

            # Handle toggle options for chart data presentation
            current_toggle_option = self._handle_toggle_options(
                query_config, chart_unique_key
            )

            # Get final chart configuration including toggle and render_multiple overrides
            chart_final_config = self._get_chart_config(
                query_config,
                current_toggle_option,
                original_config_item.get("chart_type"),
                original_config_item.get("x_col"),
                original_config_item.get("y_col"),
                current_label,
                original_config_item.get("value_col"),
                original_config_item.get("color_col"),
                original_config_item.get("hover_data"),
                original_config_item.get("path_cols"), # Pass through
                original_config_item.get("dimensions_cols"), # Pass through
            )

            figure_or_error = self._create_chart(df, chart_final_config)

            if "error" in figure_or_error:
                charts.append({"error": figure_or_error["error"], "label": current_label})
            else:
                charts.append({
                    "figure": figure_or_error,
                    "data": df,
                    "label": current_label,
                    "description": query_config.get("description", ""),
                    "show_table_toggle": original_config_item.get("show_table_toggle", False),
                })
        return charts

    def _build_query_params(self, filters: Dict[str, Any], query_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Builds query parameters as a dictionary of strings suitable for SQL string formatting.
        This includes date range and the dynamic object filter clause.
        """
        start_date_str, end_date_str = self.query_executor.get_date_range(
            filters.get("date_filter", "7_days"),
            filters.get("custom_start"),
            filters.get("custom_end"),
        )

        object_filter_clause = ""
        apply_filter_for_this_query = query_config.get("apply_object_filter", True)

        if apply_filter_for_this_query:
            object_type = filters.get("object_type", "all")
            object_value = filters.get("object_value", "").strip()

            if object_type != "all" and object_value and object_value.lower() != "all":
                col_map = {
                    "user": "USER_NAME",
                    "warehouse": "WAREHOUSE_NAME",
                    "role": "ROLE_NAME",
                    "database": "DATABASE_NAME",
                }
                column_name = col_map.get(object_type.lower()) # Ensure lower() for matching
                if column_name:
                    # Sanitize object_value for SQL injection prevention when direct string formatting.
                    # IMPORTANT SECURITY NOTE: For robust production systems, prefer parameterized queries
                    # with Snowpark's DataFrame API filters (e.g., df.filter(col(column_name) == object_value))
                    # instead of string formatting directly into SQL.
                    sanitized_object_value = object_value.replace("'", "''")
                    object_filter_clause = f"AND {column_name} = '{sanitized_object_value}'"
                else:
                    logger.warning(f"No column mapping for object type: {object_type}. Object filter will not be applied.")

        return {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "object_filter": object_filter_clause, # This will be injected directly into SQL
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
        
        # Max 4 columns for buttons, adjust if more toggles
        num_toggles = len(toggle_options)
        toggle_cols = st.columns(min(num_toggles, 4)) # Limit columns to prevent tiny buttons

        for i, (key, config) in enumerate(toggle_options.items()):
            with toggle_cols[i % 4]: # Use modulo for wrapping if more than 4 toggles
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
        chart_type_override: Optional[str] = None, # Renamed to avoid shadowing
        x_col_override: Optional[str] = None,
        y_col_override: Optional[str] = None,
        label_override: Optional[str] = None,
        value_col_override: Optional[str] = None,
        color_col_override: Optional[str] = None,
        hover_data_override: Optional[List[str]] = None,
        path_cols_override: Optional[List[str]] = None, # New
        dimensions_cols_override: Optional[List[str]] = None, # New
    ) -> Dict[str, Any]:
        """
        Get final chart configuration based on toggle state and explicit overrides.
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
            "path_cols": query_config.get("path_cols", []), # Default for hierarchical
            "dimensions_cols": query_config.get("dimensions_cols", []), # Default for scatter matrix
            "color_continuous_scale": query_config.get("color_continuous_scale", "Viridis"), # For heatmaps
            "nbins": query_config.get("nbins", 50), # For histograms
            "points": query_config.get("points", "all"), # For box plots
        }

        # Apply toggle-specific config if it exists and is not 'default'
        toggle_options = query_config.get("toggle_options", {})
        if current_toggle != "default" and current_toggle in toggle_options:
            toggle_config = toggle_options[current_toggle]
            config.update(toggle_config)

        # Apply explicit override arguments from render() call (highest priority)
        if chart_type_override is not None: config["chart_type"] = chart_type_override
        if x_col_override is not None: config["x_col"] = x_col_override
        if y_col_override is not None: config["y_col"] = y_col_override
        if value_col_override is not None: config["value_col"] = value_col_override
        if color_col_override is not None: config["color_col"] = color_col_override
        if hover_data_override is not None: config["hover_data"] = hover_data_override
        if path_cols_override is not None: config["path_cols"] = path_cols_override
        if dimensions_cols_override is not None: config["dimensions_cols"] = dimensions_cols_override
        if label_override is not None: config["label"] = label_override

        return config

    def _create_chart(self, df: pd.DataFrame, config: Dict[str, Any]) -> Union[go.Figure, Dict[str, str]]:
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
        path_cols = config.get("path_cols", []) # For hierarchical charts
        dimensions_cols = config.get("dimensions_cols", []) # For scatter matrix
        color_continuous_scale = config.get("color_continuous_scale", "Viridis")
        nbins = config.get("nbins", 50)
        points = config.get("points", "all")


        # --- Column Validation before plotting ---
        required_cols_map = {
            "bar": [x_col, y_col],
            "line": [x_col, y_col],
            "area": [x_col, y_col],
            "box": [x_col, y_col],
            "histogram": [x_col],
            "pie": [x_col, y_col], # names, values
            "scatter": [x_col, y_col],
            "heatmap": [x_col, y_col, value_col],
            "treemap": [value_col] + path_cols, # path_cols handles x_col and others
            "sunburst": [value_col] + path_cols,
            "violin": [x_col, y_col],
            "funnel": [x_col, y_col], # names, values
            "scatter_matrix": dimensions_cols,
            "waterfall": [x_col, y_col],
            "table": [] # No specific required plotting columns, all df columns can be shown
        }
        
        # Get required columns based on chart type
        # Filter out None values and ensure uniqueness for required checks
        required_for_plot = [col for col in required_cols_map.get(chart_type, []) if col is not None]
        
        # Add color_col if it's used for the chart type (and not already in required)
        if color_col and chart_type not in ["heatmap", "table", "treemap", "sunburst"] and color_col not in required_for_plot:
             required_for_plot.append(color_col)

        missing_cols = [col for col in required_for_plot if col not in df.columns]

        if missing_cols:
            error_msg = (
                f"Missing required columns for chart '{label}' (type: {chart_type}): "
                f"{', '.join(missing_cols)}. Available columns: {df.columns.tolist()}"
            )
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Validate hover_data columns
        valid_hover_data = [col for col in hover_data if col in df.columns]
        if len(valid_hover_data) != len(hover_data):
            logger.warning(
                f"Some requested hover_data columns not found for chart '{label}': "
                f"{list(set(hover_data) - set(valid_hover_data))}. Using valid columns: {valid_hover_data}"
            )

        # --- Data Type Coercion ---
        # Ensure proper types for columns for plotting
        cols_to_coerce = list(set([x_col, y_col, value_col, color_col] + path_cols + dimensions_cols + valid_hover_data))
        for col_name in cols_to_coerce:
            if col_name and col_name in df.columns:
                try:
                    # Attempt to coerce numeric columns to numeric types if they aren't already
                    if pd.api.types.is_numeric_dtype(df[col_name]):
                        df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                    # Attempt to coerce date columns to datetime
                    elif 'DATE' in col_name.upper() and not pd.api.types.is_datetime64_any_dtype(df[col_name]):
                        df[col_name] = pd.to_datetime(df[col_name], errors='coerce')
                except Exception as e:
                    logger.warning(f"Could not coerce column '{col_name}' to appropriate type for plotting in chart '{label}': {e}")


        # --- Chart Rendering Logic ---
        try:
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
                    points=points, # Use points from config (e.g., "all", False, "suspectedoutliers")
                    hover_data=valid_hover_data,
                )
            elif chart_type == "histogram":
                fig = px.histogram(
                    df,
                    x=x_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    nbins=nbins, # Use nbins from config
                    hover_data=valid_hover_data,
                )
            elif chart_type == "pie":
                fig = px.pie(
                    df,
                    names=x_col, # Column for categories/names
                    values=y_col, # Column for numerical values
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
                fig = px.treemap(
                    df,
                    path=path_cols, # Expects a list of column names for hierarchy
                    values=value_col,
                    title=label,
                    hover_data=valid_hover_data,
                    color_discrete_sequence=self.default_colors,
                )
            elif chart_type == "sunburst":
                fig = px.sunburst(
                    df,
                    path=path_cols, # Expects a list of column names for hierarchy
                    values=value_col,
                    title=label,
                    hover_data=valid_hover_data,
                    color_discrete_sequence=self.default_colors,
                )
            elif chart_type == "violin":
                fig = px.violin(
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    box=True, # Show box plot inside violin
                    points=points, # Can be 'all', 'outliers', False
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "funnel":
                fig = px.funnel(
                    df,
                    x=x_col, # Values column for the funnel
                    y=y_col, # Stages/names column for the funnel
                    title=label,
                    color=color_col, # Optional: color by a category
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
            elif chart_type == "waterfall":
                # Waterfall charts are typically go.Figure based, as px.waterfall isn't standard.
                # Requires 'x' for categories/labels and 'y' for values (positive/negative changes).
                # This is a more manual Plotly Graph Objects approach.
                if not x_col or not y_col or x_col not in df.columns or y_col not in df.columns:
                    raise ValueError(f"Waterfall chart requires 'x_col' ({x_col}) and 'y_col' ({y_col}) to be present in data.")
                
                # Assuming y_col contains the changes, and x_col the categories
                fig = go.Figure(
                    go.Waterfall(
                        x = df[x_col],
                        y = df[y_col],
                        # Define how to calculate totals and intermediate sums
                        # Can be customized based on requirements
                        # measure=[...], text=[...], increasing/decreasing colors etc.
                        connector={"line": {"color": "rgb(63, 63, 63)"}},
                        increasing={"marker":{"color":self.default_colors[0]}},
                        decreasing={"marker":{"color":self.default_colors[1]}},
                        totals={"marker":{"color":self.default_colors[2]}},
                    )
                )
                fig.update_layout(title_text=label, title_x=0.5, showlegend=False) # No legend for basic waterfall
            elif chart_type == "scatter_matrix":
                if not dimensions_cols:
                    raise ValueError("Scatter Matrix requires 'dimensions_cols' (list of columns to plot against each other).")
                
                # Ensure all dimensions columns exist
                missing_dim_cols = [col for col in dimensions_cols if col not in df.columns]
                if missing_dim_cols:
                    raise ValueError(f"Scatter Matrix missing dimension columns: {', '.join(missing_dim_cols)}.")

                fig = px.scatter_matrix(
                    df,
                    dimensions=dimensions_cols,
                    color=color_col, # Optional: color by a category
                    title=label,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )
                # Apply specific updates for scatter matrix
                fig.update_traces(diagonal_visible=False) # Hide diagonal histograms for cleaner view

            elif chart_type == "table":
                # Ensure all columns for the table exist
                table_cols = df.columns.tolist() # All columns in the DataFrame
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
                    return {"error": f"No valid columns found for table chart '{label}'."}
            else:
                logger.warning(
                    f"Unsupported chart type '{chart_type}'. Defaulting to bar chart."
                )
                fig = px.bar( # Fallback to bar chart if type is unrecognized
                    df,
                    x=x_col,
                    y=y_col,
                    title=label,
                    color=color_col,
                    color_discrete_sequence=self.default_colors,
                    hover_data=valid_hover_data,
                )

            # Apply common layout updates (avoid for Table and Scatter Matrix unless explicitly handled)
            if chart_type not in ["table", "scatter_matrix", "waterfall"]: # Waterfall handled above
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
            elif chart_type == "scatter_matrix":
                # Specific layout for scatter matrix (no individual axes titles usually)
                 fig.update_layout(
                    showlegend=True,
                    height=700, # Often taller for scatter matrix
                    margin=dict(l=20, r=20, t=50, b=20),
                    title_font_size=20,
                    title_x=0.5,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    legend_title_font_size=14,
                    hoverlabel=dict(
                        bgcolor="white",
                        font_size=12,
                        font_family="Arial"
                    )
                )

            return fig

        except Exception as e:
            error_msg = f"Error creating Plotly chart for '{label}' (type: {chart_type}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}