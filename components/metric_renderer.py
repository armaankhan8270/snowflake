# components/metric_renderer.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple

import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)


class MetricRenderer:
    """
    Handles the execution of queries for metrics and their deltas,
    formatting results, and preparing them for UI display.
    Leverages parallel query execution for efficiency.
    """

    def __init__(self, query_executor_instance: Any):
        self.query_executor = query_executor_instance
        logger.info("MetricRenderer initialized.")

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
        Renders a single metric, including its current value and an optional delta
        compared to a previous period. This method orchestrates a call to render_multiple
        for consistency with parallel execution.

        Args:
            query_key (str): The key of the metric in the query_store.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.
            label (Optional[str]): Override label for the metric.
            description (Optional[str]): Override description for the metric.
            format_type (Optional[str]): Override format type (e.g., 'number', 'percentage', 'currency', 'duration').
            delta_query_key (Optional[str]): Override key for the delta metric query.

        Returns:
            Dict[str, Any]: A dictionary containing the metric's 'label', 'value' (formatted),
                            'raw_value', 'delta' (formatted), 'raw_delta', 'description', and 'format'.
                            Includes an 'error' key if an issue occurs.
        """
        # Create a single-item list for render_multiple
        metric_configs = [{
            "query_key": query_key,
            "label": label,
            "description": description,
            "format_type": format_type,
            "delta_query_key": delta_query_key,
        }]
        
        # Call render_multiple and return the first (and only) result
        results = self.render_multiple(metric_configs, query_store, filters)
        return results[0] if results else {"error": "No metric returned.", "label": label or query_key}


    def render_multiple(
        self,
        metric_configs: List[Union[str, Dict[str, Any]]],
        query_store: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Renders multiple metrics, including their current values and optional deltas,
        by executing all necessary queries in parallel.

        Args:
            metric_configs (List[Union[str, Dict[str, Any]]]): A list of metric configurations.
                                                                Each item can be a string (query_key)
                                                                or a dictionary with 'query_key' and optional overrides.
            query_store (Dict[str, Any]): The dictionary containing all query configurations.
            filters (Dict[str, Any]): The current filter values from the UI.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dict represents a metric
                                  with its 'label', 'value' (formatted), 'raw_value',
                                  'delta' (formatted), 'raw_delta', 'description', and 'format'.
                                  'error' key included if an issue occurs. The order matches input configs.
        """
        all_query_jobs = [] # List to hold all (current and delta) query jobs for parallel execution
        # Map to store the relationship between the submitted query job and the original metric config index
        job_to_metric_map: Dict[int, Tuple[int, str]] = {} # {job_index: (metric_config_index, "current" | "delta")}
        
        # Track original positions to return results in the correct order
        metrics_results_placeholders = [None] * len(metric_configs)
        
        current_job_index = 0

        for metric_config_index, config_item in enumerate(metric_configs):
            metric_display_config = {} # This will store overrides for display

            if isinstance(config_item, str):
                query_key = config_item
            elif isinstance(config_item, dict):
                query_key = config_item.get("query_key")
                metric_display_config.update(config_item) # Copy overrides
            else:
                logger.warning(f"Invalid metric config type: {type(config_item)}. Skipping.")
                metrics_results_placeholders[metric_config_index] = {
                    "error": "Invalid metric configuration provided.",
                    "label": f"Metric {metric_config_index + 1}"
                }
                continue # Skip to next metric config

            if not query_key or query_key not in query_store:
                logger.error(f"Metric query key '{query_key}' not found or invalid in query store.")
                metrics_results_placeholders[metric_config_index] = {
                    "error": f"Query configuration for '{query_key}' not found.",
                    "label": metric_display_config.get("label", query_key)
                }
                continue # Skip to next metric config
            
            base_query_config = query_store[query_key]
            current_label = metric_display_config.get("label") or base_query_config.get("label", "Metric")
            
            # --- Prepare Current Metric Query Job ---
            current_params = self._build_query_params(filters, base_query_config, is_delta_query=False)
            all_query_jobs.append((base_query_config, current_params, f"{current_label} (Current)"))
            job_to_metric_map[current_job_index] = (metric_config_index, "current")
            current_job_index += 1

            # --- Prepare Delta Metric Query Job (if applicable) ---
            delta_key = metric_display_config.get("delta_query_key") or base_query_config.get("delta_query_key")
            if delta_key and delta_key in query_store:
                delta_query_config = query_store[delta_key]
                # Pass 'is_delta_query=True' to build_query_params to adjust dates for delta period
                delta_params = self._build_query_params(filters, delta_query_config, is_delta_query=True)
                all_query_jobs.append((delta_query_config, delta_params, f"{current_label} (Delta)"))
                job_to_metric_map[current_job_index] = (metric_config_index, "delta")
                current_job_index += 1
            else:
                # If no delta key or delta query not found, ensure delta data is marked as None
                # No actual job is added, but we need to track that no delta was requested/found.
                # The _process_results below will handle this by checking for delta_df emptiness.
                pass # No need for a "no_delta" placeholder job anymore, just rely on delta_df being empty/missing


        # --- Execute all queries in parallel ---
        # The result from execute_queries_parallel is a list of {"data": df} or {"error": msg} dicts
        parallel_query_results = self.query_executor.execute_queries_parallel(all_query_jobs)

        # --- Process results and build final metric dictionaries ---
        
        # Temporary storage for current and delta dataframes for each metric config
        temp_data_storage: Dict[int, Dict[str, pd.DataFrame]] = {i: {"current": pd.DataFrame(), "delta": pd.DataFrame()} for i in range(len(metric_configs))}
        temp_error_storage: Dict[int, Dict[str, str]] = {i: {"current_error": None, "delta_error": None} for i in range(len(metric_configs))}


        for job_idx, result in enumerate(parallel_query_results):
            if job_idx not in job_to_metric_map:
                logger.warning(f"Unexpected job_idx {job_idx} in parallel_query_results map.")
                continue

            metric_cfg_idx, job_type = job_to_metric_map[job_idx]

            if "error" in result:
                if job_type == "current":
                    temp_error_storage[metric_cfg_idx]["current_error"] = result["error"]
                elif job_type == "delta":
                    temp_error_storage[metric_cfg_idx]["delta_error"] = result["error"]
                logger.error(f"Error fetching data for {job_type} query for metric {metric_cfg_idx}: {result['error']}")
            elif "data" in result:
                if job_type == "current":
                    temp_data_storage[metric_cfg_idx]["current"] = result["data"]
                elif job_type == "delta":
                    temp_data_storage[metric_cfg_idx]["delta"] = result["data"]


        # Now, iterate through original metric configs and construct the final metric dictionaries
        for metric_config_index, config_item in enumerate(metric_configs):
            if metrics_results_placeholders[metric_config_index] is not None:
                # This config was skipped due to an earlier error
                metrics_results_placeholders[metric_config_index]["error"] = \
                    temp_error_storage[metric_config_index]["current_error"] or \
                    metrics_results_placeholders[metric_config_index]["error"]
                continue

            metric_display_config = {}
            if isinstance(config_item, str):
                query_key = config_item
            else:
                query_key = config_item.get("query_key")
                metric_display_config.update(config_item) # Copy overrides

            base_query_config = query_store.get(query_key, {}) # Use .get for safety
            
            # Use overrides or base config
            current_label = metric_display_config.get("label") or base_query_config.get("label", "Unknown Metric")
            description = metric_display_config.get("description") or base_query_config.get("description")
            format_type = metric_display_config.get("format_type") or base_query_config.get("format")

            current_df = temp_data_storage[metric_config_index]["current"]
            delta_df = temp_data_storage[metric_config_index]["delta"]
            current_error = temp_error_storage[metric_config_index]["current_error"]
            delta_error = temp_error_storage[metric_config_index]["delta_error"]

            if current_error:
                metrics_results_placeholders[metric_config_index] = {
                    "label": current_label,
                    "description": description,
                    "format": format_type,
                    "error": current_error,
                }
                continue # Skip to next metric if current value has an error

            raw_value = self._get_metric_value(current_df) # Get raw value
            value = self._format_value(raw_value, format_type) # Format for display

            raw_delta = self._get_delta_value(raw_value, delta_df, delta_error) # Get raw delta
            delta = self._format_delta(raw_delta, format_type) # Format for display

            metrics_results_placeholders[metric_config_index] = {
                "label": current_label,
                "value": value,          # Formatted string for display
                "raw_value": raw_value,  # Raw number for calculations
                "delta": delta,          # Formatted string for display
                "raw_delta": raw_delta,  # Raw number for delta calculations
                "description": description,
                "format": format_type,
            }

        return metrics_results_placeholders

    def _build_query_params(self, filters: Dict[str, Any], query_config: Dict[str, Any], is_delta_query: bool) -> Dict[str, str]:
        """
        Builds query parameters as a dictionary of strings suitable for SQL string formatting.
        This includes date range and the dynamic object filter clause.
        Adjusts date range for delta queries.
        """
        date_filter_type = filters.get("date_filter", "7_days")
        custom_start = filters.get("custom_start")
        custom_end = filters.get("custom_end")

        start_date_str, end_date_str = self.query_executor.get_date_range(
            date_filter_type, custom_start, custom_end
        )

        # Adjust dates for delta queries
        if is_delta_query:
            try:
                current_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                current_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                
                # Calculate the duration of the current period
                duration_days = (current_end_date - current_start_date).days + 1
                
                # Shift dates back by the duration for the delta period
                delta_end_date = current_start_date - timedelta(days=1)
                delta_start_date = delta_end_date - timedelta(days=duration_days - 1)

                start_date_str = delta_start_date.strftime("%Y-%m-%d")
                end_date_str = delta_end_date.strftime("%Y-%m-%d")
                logger.debug(f"Delta query dates adjusted: {start_date_str} to {end_date_str}")
            except Exception as e:
                logger.error(f"Error adjusting dates for delta query: {e}. Using current period dates.", exc_info=True)
                # Fallback to current dates if adjustment fails

        object_filter_clause = ""
        # Apply object filter only if the query config explicitly says so OR
        # if the query is a core KPI (like total_queries_run) and apply_object_filter isn't explicitly False.
        # This prevents global KPIs from being filtered by a specific user/warehouse.
        apply_filter_for_this_query = query_config.get("apply_object_filter", True) # Default to True if not specified

        if apply_filter_for_this_query:
            object_type = filters.get("object_type", "all")
            object_value = filters.get("object_value", "").strip()

            # The key change for "All" is here: if object_value is 'All' or empty, don't apply the filter
            if object_type != "all" and object_value and object_value.lower() != "all":
                col_map = {
                    "user": "USER_NAME",
                    "warehouse": "WAREHOUSE_NAME",
                    "role": "ROLE_NAME",
                    "database": "DATABASE_NAME",
                }
                column_name = col_map.get(object_type.lower())
                if column_name:
                    # Sanitize object_value to prevent SQL injection.
                    # IMPORTANT: For robust production systems, prefer parameterized queries
                    # or stronger sanitization methods. This is a basic escape.
                    sanitized_object_value = object_value.replace("'", "''")
                    object_filter_clause = f"AND {column_name} = '{sanitized_object_value}'"
                else:
                    logger.warning(f"No column mapping for object type: {object_type}. Object filter will not be applied.")

        return {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "object_filter": object_filter_clause, # This will be injected directly into SQL
        }

    def _get_metric_value(self, df: pd.DataFrame) -> Union[int, float, str, None]:
        """Extracts the metric value from the DataFrame, handling empty or multi-row results."""
        if df.empty:
            return None
        # Assuming the value is in the first column of the first row
        return df.iloc[0, 0] if not df.empty else None

    def _get_delta_value(
        self, current_value: Union[int, float, None], delta_df: pd.DataFrame, delta_error: Optional[str]
    ) -> Union[int, float, None]:
        """Calculates the delta value if previous data is available."""
        if delta_error:
            logger.warning(f"Delta calculation skipped due to error: {delta_error}")
            return None # Cannot calculate delta if there was an error fetching delta data

        previous_value = self._get_metric_value(delta_df)

        if current_value is None or previous_value is None:
            return None
        if not isinstance(current_value, (int, float)) or not isinstance(
            previous_value, (int, float)
        ):
            # If values are strings, attempt conversion if possible for common cases
            try:
                current_value = float(current_value) if isinstance(current_value, str) else current_value
                previous_value = float(previous_value) if isinstance(previous_value, str) else previous_value
            except ValueError:
                logger.warning(f"Cannot calculate delta for non-numeric or unconvertible string values: Current={current_value}, Previous={previous_value}")
                return None  # Cannot calculate delta for non-numeric or unconvertible values

        if previous_value == 0:
            return 0.0 if current_value == 0 else float("inf")  # Handle division by zero
        return ((current_value - previous_value) / previous_value) * 100

    def _format_value(
        self, value: Union[int, float, str, None], format_type: Optional[str]
    ) -> str:
        """Formats the metric value based on its type."""
        if value is None:
            return "N/A"
        
        # Ensure value is numeric for formatting if possible
        numeric_value = None
        if isinstance(value, (int, float)):
            numeric_value = value
        elif isinstance(value, str):
            try:
                numeric_value = float(value) # Try converting string to float
            except ValueError:
                pass # If conversion fails, keep as string

        if format_type == "number":
            return f"{numeric_value:,.0f}" if isinstance(numeric_value, (int, float)) else str(value)
        elif format_type == "percentage":
            return f"{numeric_value:.2f}%" if isinstance(numeric_value, (int, float)) else str(value)
        elif format_type == "currency":
            return f"${numeric_value:,.2f}" if isinstance(numeric_value, (int, float)) else str(value)
        elif format_type == "duration":
            # Assuming duration in seconds, format as HH:MM:SS or similar
            if isinstance(numeric_value, (int, float)):
                # Convert seconds to timedelta for formatting
                td = timedelta(seconds=int(numeric_value))
                hours, remainder = divmod(td.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{hours:02}:{minutes:02}:{seconds:02}"
            return str(value)
        return str(value)  # Default to string conversion

    def _format_delta(
        self, delta: Union[int, float, None], format_type: Optional[str]
    ) -> Optional[str]:
        """Formats the delta value as a percentage or difference."""
        if delta is None:
            return None
        if delta == float("inf"):
            return "∞%" # Infinite increase
        
        # For deltas, we usually want a percentage change indicator
        # Example: "+15.25%", "-3.10%"
        return f"{delta:+.2f}%" if isinstance(delta, (int, float)) else None