# components/metric_renderer.py - PROPOSED MINOR REFINEMENTS FOR ERROR HANDLING
"""
Metric renderer for dashboard
Handles metric calculation and rendering
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


class MetricRenderer:
    """Handles metric rendering and calculation"""

    def __init__(self, query_executor_instance: Any):
        self.query_executor = query_executor_instance

    def render(
        self,
        query_key: str,
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
        label: Optional[str] = None,
        description: Optional[str] = None,
        format_type: Optional[str] = None,
        delta_query_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Render a single metric from query store

        Args:
            query_key: Key to identify query in store
            query_store: Dictionary containing all queries
            filters: Filter values from UI (date, object type, object value)
            label: Override label for metric from query_store
            description: Override description for metric from query_store
            format_type: Override format type (number, percentage, currency, duration)
            delta_query_key: Optional query key to fetch data for the delta value

        Returns:
            Dictionary containing metric data (label, value, delta, description, error)
        """
        current_label = label or query_key # Default label for error reporting

        try:
            if not isinstance(query_key, str) or query_key not in query_store:
                error_msg = f"Metric query key '{query_key}' not found or invalid in query store."
                logger.error(error_msg)
                return {"error": error_msg, "label": current_label}

            query_config = query_store[query_key]
            current_label = label or query_config.get("label", "Metric") # Update label if config has it

            # Determine the effective format type
            effective_format_type = format_type or query_config.get("format", "number")

            # Build query parameters, considering `apply_object_filter`
            params = self._build_query_params(filters, query_config)

            # Execute query for current value
            df_current = self.query_executor.execute_query(query_config["query"], params)

            value = "N/A" # Default to N/A for display
            if not df_current.empty:
                value = self._extract_metric_value(df_current, effective_format_type)
            else:
                # If df_current is empty, check if query_executor had an error.
                # (Assuming query_executor shows a global st.error for critical failures)
                # If not, it's just no data.
                logger.warning(f"No data returned for metric '{current_label}'. Displaying 'N/A'.")


            # Calculate delta if delta_query_key is provided
            delta_value = None
            if delta_query_key and delta_query_key in query_store:
                delta_query_config = query_store[delta_query_key]

                previous_period_filters = self._get_previous_period_filters(filters)
                params_prev = self._build_query_params(previous_period_filters, delta_query_config)

                df_previous = self.query_executor.execute_query(
                    delta_query_config["query"], params_prev
                )

                if not df_previous.empty:
                    comparison_value = self._extract_metric_value(
                        df_previous, effective_format_type
                    )

                    try:
                        numeric_value = self._parse_formatted_value(value)
                        numeric_comparison_value = self._parse_formatted_value(comparison_value)

                        if numeric_comparison_value is not None and numeric_value is not None:
                            if numeric_comparison_value != 0:
                                delta_calc = (
                                    (numeric_value - numeric_comparison_value)
                                    / abs(numeric_comparison_value)
                                ) * 100
                                # Format delta with proper sign and percentage
                                delta_value = f"{delta_calc:+.1f}%" # + sign for positive
                            else:
                                if numeric_value != 0:
                                    # If previous was 0, and current is not 0, show current as a positive change.
                                    # Format based on current metric value, not percentage.
                                    delta_value = f"+{self._format_number(numeric_value)} (new)"
                                else:
                                    delta_value = None # Both are 0, no change
                        else:
                            delta_value = None # Cannot calculate delta if values are not numeric
                    except ValueError: # _parse_formatted_value logs its own warnings
                        delta_value = None
                else:
                    logger.info(f"No data returned for delta metric '{delta_query_key}'. Delta will not be calculated.")

            return {
                "label": current_label,
                "value": value,
                "delta": delta_value,
                "description": description or query_config.get("description", ""),
            }

        except Exception as e:
            error_msg = f"An unexpected error occurred while rendering metric '{current_label}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg, "label": current_label}


    def render_multiple(
        self, metric_configs: list, query_store: Dict[str, Any], filters: Dict[str, Any]
    ) -> list:
        """
        Render multiple metrics

        Args:
            metric_configs: List of metric configurations.
                            Each dict must contain 'query_key' and can override other render args.
            query_store: Dictionary containing all queries
            filters: Filter values from UI

        Returns:
            List of metric dictionaries
        """
        metrics = []
        for i, config_item in enumerate(metric_configs):
            if isinstance(config_item, str):
                # Simple string key - fetch config from query_store
                query_key = config_item
                metric_args = {"query_key": query_key}
            elif isinstance(config_item, dict):
                # Dictionary with additional options
                metric_args = {**config_item} # Copy the dict to avoid modifying original
            else:
                logger.warning(f"Invalid metric config type: {type(config_item)}. Skipping.")
                continue

            query_key_to_render = metric_args.get("query_key")
            if not query_key_to_render:
                logger.error(f"Metric config at index {i} is missing 'query_key'. Skipping.")
                metrics.append({"error": "Missing 'query_key' in metric configuration.", "label": "Unnamed Metric"})
                continue

            metric = self.render(
                query_key=query_key_to_render,
                query_store=query_store,
                filters=filters,
                label=metric_args.get("label"),
                description=metric_args.get("description"),
                format_type=metric_args.get("format_type"),
                delta_query_key=metric_args.get("delta_query_key"),
            )
            metrics.append(metric)
        return metrics

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

    def _get_previous_period_filters(self, current_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates filters for the previous period based on the current filters.
        This is a common requirement for delta calculations.
        """
        prev_filters = current_filters.copy()
        current_date_filter = current_filters.get("date_filter", "7_days")
        current_start = current_filters.get("custom_start")
        current_end = current_filters.get("custom_end")

        start_date_str, end_date_str = self.query_executor.get_date_range(
            current_date_filter, current_start, current_end
        )
        # Convert back to datetime.date objects for calculation
        current_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        current_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        duration = current_end_date - current_start_date
        
        # Calculate previous period's dates
        prev_end_date = current_start_date - timedelta(days=1)
        prev_start_date = prev_end_date - duration

        # Update custom start/end in prev_filters
        prev_filters["custom_start"] = prev_start_date
        prev_filters["custom_end"] = prev_end_date
        
        # Set date_filter to 'custom' to ensure the new custom dates are used
        prev_filters["date_filter"] = "custom" 
        
        return prev_filters


    def _parse_formatted_value(self, value: Any) -> Optional[float]:
        """
        Parses a potentially formatted metric value (e.g., '1.2K', '$500', '1.5h') into a float.
        Returns None if parsing fails.
        """
        if value is None:
            return None
        s_value = str(value).strip().lower()

        # Handle numeric formats with units
        if s_value.endswith('b'): # Billions
            try: return float(s_value[:-1]) * 1_000_000_000
            except ValueError: pass
        if s_value.endswith('m'): # Millions
            try: return float(s_value[:-1]) * 1_000_000
            except ValueError: pass
        if s_value.endswith('k'): # Thousands
            try: return float(s_value[:-1]) * 1_000
            except ValueError: pass
        if s_value.endswith('h'): # Hours
            try: return float(s_value[:-1]) * 3600
            except ValueError: pass
        if s_value.endswith('m') and len(s_value) > 1 and not s_value.endswith('m '): # Minutes (ensure not 'M' for millions)
            try: return float(s_value[:-1]) * 60
            except ValueError: pass
        if s_value.endswith('s'): # Seconds
            try: return float(s_value[:-1])
            except ValueError: pass

        # Remove common non-numeric characters for direct float conversion
        s_value = s_value.replace('$', '').replace('%', '').replace(',', '')

        try:
            return float(s_value)
        except ValueError:
            logger.warning(f"Could not parse metric value '{value}' to a number for delta calculation.")
            return None

    def _extract_metric_value(self, df: pd.DataFrame, format_type: str = "number"):
        """
        Extract and format metric value from DataFrame.
        Improved handling for empty or single-row dataframes and non-numeric results.
        """
        if df.empty:
            logger.warning("Attempted to extract metric value from an empty DataFrame for formatting.")
            return "N/A" # Return N/A if DataFrame is empty, rather than 0 for all types

        # Try to get the first numeric column, or the first column if no numeric
        value = None
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                value = df.loc[0, col]
                break
        if value is None and not df.empty: # If no numeric column, take the first column's first value
            value = df.iloc[0, 0]

        # Handle None/null values from dataframe
        if pd.isna(value) or value is None:
            logger.warning(f"Extracted metric value is NaN or None for formatting: {value}")
            return "N/A"

        # Try to convert to float for formatting, if it's not already
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Metric value '{value}' is not numeric and cannot be formatted as {format_type}. Returning as is.")
            return str(value) # Return non-numeric values as string directly

        # Format based on type
        if format_type == "number":
            return self._format_number(numeric_value)
        elif format_type == "percentage":
            return f"{numeric_value:.1f}%"
        elif format_type == "currency":
            return f"${numeric_value:,.2f}"
        elif format_type == "duration":
            return self._format_duration(numeric_value)
        else:
            return str(numeric_value) # Fallback

    def _format_number(self, value) -> str:
        """Format number with appropriate units (B, M, K) and comma separators."""
        # Ensure value is a float/int before formatting
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert value to number for formatting: {value}")
                return str(value)

        if value == 0:
            return "0"

        abs_num_value = abs(value)

        if abs_num_value >= 1_000_000_000:
            return f"{value/1_000_000_000:.1f}B"
        elif abs_num_value >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif abs_num_value >= 1_000:
            return f"{value/1_000:.1f}K"
        else:
            # Only show decimals if it's not a whole number. Max 2 decimal places.
            if value == int(value):
                return f"{int(value):,}"
            else:
                return f"{value:,.2f}".rstrip('0').rstrip('.') if '.' in f"{value:,.2f}" else f"{value:,.0f}"

    def _format_duration(self, seconds) -> str:
        """Format duration in seconds to human readable format (h, m, s)."""
        # Ensure seconds is a float/int before formatting
        if not isinstance(seconds, (int, float)):
            try:
                seconds = float(seconds)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert value to seconds for duration formatting: {seconds}")
                return str(seconds)

        if seconds == 0:
            return "0s"

        abs_seconds = abs(seconds)

        if abs_seconds >= 3600:
            return f"{seconds/3600:.1f}h"
        elif abs_seconds >= 60:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds:.1f}s" if seconds != int(seconds) else f"{int(seconds)}s"

