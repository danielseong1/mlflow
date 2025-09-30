"""
Databricks SQL Store implementation that extends RestStore for trace searches.

This store uses direct Databricks SQL queries for search_traces while delegating
all other operations to the parent RestStore.

Trace Table Schema:
- trace_id: string
- client_request_id: string
- request_time: timestamp
- state: string (OK, ERROR, etc.)
- execution_duration_ms: bigint
- request: string
- response: string
- trace_metadata: map<string,string>
- tags: map<string,string>
- trace_location: struct
- assessments: array<struct>
  - assessment_id: string
  - trace_id: string
  - name: string (e.g., 'relevance_to_query')
  - source: struct
    - source_id: string (e.g., 'databricks')
    - source_type: string (e.g., 'LLM_JUDGE')
  - create_time: timestamp
  - last_update_time: timestamp
  - expectation: string (nullable)
  - feedback: struct
    - value: string (e.g., '"yes"' or '"no"')
    - error: string (nullable)
  - rationale: string
  - metadata: map<string,string> (nullable)
  - span_id: string
- spans: array<struct>
- request_preview: string
- response_preview: string
"""

import json
import logging
from functools import lru_cache, partial
from typing import Optional

from databricks.connect import DatabricksSession

from mlflow.entities.trace_info import TraceInfo
from mlflow.entities.trace_location import (
    TraceLocation,
    TraceLocationType,
    MlflowExperimentLocation,
)
from mlflow.entities.trace_state import TraceState
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.store.tracking import SEARCH_TRACES_DEFAULT_MAX_RESULTS
from mlflow.store.tracking.rest_store import RestStore
from mlflow.tracing.analysis import TraceFilterCorrelationResult
from mlflow.utils.databricks_sql_filter import TraceFilterParser
from mlflow.utils.databricks_utils import get_databricks_host_creds

_logger = logging.getLogger(__name__)


class DatabricksSqlStore(RestStore):
    """
    Store implementation that uses Databricks SQL for trace searches.

    This store extends RestStore and overrides search_traces to directly
    query Databricks SQL tables for better performance and flexibility.

    Requires environment variables:
        DATABRICKS_HOST: The Databricks workspace URL
        DATABRICKS_TOKEN: The Databricks access token
    """

    def __init__(self, store_uri):
        """
        Initialize the Databricks SQL Store.

        Args:
            store_uri: The URI for the REST store backend
        """
        # Initialize parent RestStore with Databricks host credentials
        super().__init__(partial(get_databricks_host_creds, store_uri))
        self._spark_session = None

    def __del__(self):
        """Close Spark session when store is deleted."""
        self.close_spark_session()

    def close_spark_session(self):
        """Close the Spark session if it exists."""
        if self._spark_session:
            try:
                self._spark_session.stop()
            except:
                pass
            finally:
                self._spark_session = None

    def _get_or_create_spark_session(self):
        """
        Get or create a Spark session for Databricks SQL queries.

        Returns:
            A DatabricksSession configured for serverless compute.
        """
        if self._spark_session is None or not self._is_spark_session_healthy():
            self._create_new_spark_session()
        return self._spark_session

    def _is_spark_session_healthy(self):
        """
        Check if the current Spark session is healthy by running a simple query.

        Returns:
            bool: True if the session is healthy, False otherwise
        """
        if self._spark_session is None:
            return False

        try:
            # Simple health check query
            self._spark_session.sql("SELECT 1").collect()
            return True
        except Exception as e:
            _logger.warning(f"Spark session health check failed: {e}")
            return False

    def _create_new_spark_session(self):
        """
        Create a new Spark session, cleaning up the old one if it exists.
        """
        # Clean up existing session
        if self._spark_session is not None:
            try:
                self._spark_session.stop()
            except Exception as e:
                _logger.warning(f"Error stopping previous Spark session: {e}")
            finally:
                self._spark_session = None

        try:
            # Use environment variables for configuration
            # These should be set by the caller
            self._spark_session = DatabricksSession.builder.serverless(
                True
            ).getOrCreate()
            _logger.debug("Created new Databricks Spark session")
        except Exception as e:
            raise MlflowException(
                f"Failed to create Databricks session: {e}",
                error_code=INVALID_PARAMETER_VALUE,
            )

    def restart_spark_session(self):
        """
        Restart the Spark session by stopping the current one and creating a new one.
        This method can be called when the session becomes stale or encounters errors.
        """
        _logger.debug("Restarting Spark session")
        self._create_new_spark_session()

    def execute_sql(self, query: str, params: Optional[dict] = None):
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query to execute
            params: Optional parameters for the query

        Returns:
            List of Row objects with results
        """
        spark = self._get_or_create_spark_session()
        if params:
            return spark.sql(query, params).collect()
        else:
            return spark.sql(query).collect()

    def _parse_filter_string(
        self, filter_string: str, table_name: str, params: dict
    ) -> list[str]:
        """
        Parse a filter string and return parameterized WHERE conditions.

        Args:
            filter_string: The filter string to parse
            table_name: The table name for the parser
            params: Dictionary to add parameter values to

        Returns:
            List of WHERE condition strings with parameter placeholders
        """
        if not filter_string:
            return []

        # Use the filter parser to convert DSL to SQL
        parser = TraceFilterParser(table_name)
        conditions, filter_params = parser.parse(filter_string)

        # Update the params dict with filter parameters
        params.update(filter_params)

        return conditions

    def _build_safe_order_clause(self, order_by: Optional[list[str]]) -> str:
        """
        Build a safe ORDER BY clause from a list of order specifications.

        Args:
            order_by: List of order specifications (e.g., ["request_time DESC", "trace_id ASC"])

        Returns:
            Safe ORDER BY clause string
        """
        if not order_by:
            # Default ordering
            return "ORDER BY request_time DESC"

        # Define allowed columns for ordering to prevent injection
        ALLOWED_ORDER_COLUMNS = {
            "trace_id",
            "request_time",
            "execution_duration_ms",
            "state",
            "client_request_id",
        }

        # Define allowed directions
        ALLOWED_DIRECTIONS = {"ASC", "DESC"}

        safe_orders = []
        for order_spec in order_by:
            # Parse the order specification
            parts = order_spec.strip().split()
            if not parts:
                continue

            column = parts[0]
            direction = parts[1].upper() if len(parts) > 1 else "ASC"

            # Validate column and direction
            if column in ALLOWED_ORDER_COLUMNS and direction in ALLOWED_DIRECTIONS:
                safe_orders.append(f"{column} {direction}")
            else:
                # Log warning about invalid order specification
                # In production, you might want to raise an exception or log this
                pass

        if safe_orders:
            return f"ORDER BY {', '.join(safe_orders)}"
        else:
            # Fallback to default if no valid orders
            return "ORDER BY request_time DESC"

    @lru_cache(maxsize=128)
    def _get_trace_table_for_experiment(self, experiment_id: str) -> Optional[str]:
        """
        Get the trace archive table name for an experiment from Databricks monitors API.

        This method calls the /api/2.0/managed-evals/monitors endpoint to retrieve
        monitor information for an experiment, and extracts the trace_archive_table if available.

        Args:
            experiment_id: The experiment ID to get the trace table for

        Returns:
            The trace table name (without backticks) if found, None otherwise
        """
        try:
            import requests

            # Get host credentials for making the API call
            host_creds = self.get_host_creds()

            # Prepare request
            url = f"{host_creds.host}/api/2.0/managed-evals/monitors"
            headers = {"Content-Type": "application/json"}
            if host_creds.token:
                headers["Authorization"] = f"Bearer {host_creds.token}"

            request_body = json.dumps({"experiment_id": experiment_id})

            _logger.debug(
                f"Calling GetMonitor API for experiment {experiment_id}: {url}"
            )

            # Make the API call
            resp = requests.post(
                url,
                data=request_body,
                headers=headers,
                verify=not getattr(host_creds, "ignore_tls_verification", False),
            )

            _logger.debug(f"GetMonitor API response status: {resp.status_code}")
            if resp.status_code != 200:
                _logger.warning(
                    f"GetMonitor API failed with status {resp.status_code}: {resp.text}"
                )
                # API call failed, return None to fall back to default behavior
                return None

            response_json = resp.json()
            _logger.debug(f"GetMonitor API response: {response_json}")

            # Extract trace_archive_table from response
            monitor_infos = response_json.get("monitor_infos", [])
            if monitor_infos and len(monitor_infos) > 0:
                monitor = monitor_infos[0].get("monitor", {})
                trace_table = monitor.get("trace_archive_table")
                _logger.debug(f"Found trace_archive_table: {trace_table}")

                if trace_table:
                    # Remove backticks from table name if present
                    return trace_table.replace("`", "")

            return None

        except Exception:
            # If anything goes wrong, return None to fall back to default behavior
            # We don't want to break the search_traces functionality
            return None

    def search_traces(
        self,
        experiment_ids: list[str],
        filter_string: Optional[str] = None,
        max_results: int = SEARCH_TRACES_DEFAULT_MAX_RESULTS,
        order_by: Optional[list[str]] = None,
        page_token: Optional[str] = None,
        model_id: Optional[str] = None,
        sql_warehouse_id: Optional[str] = None,
    ) -> tuple[list[TraceInfo], Optional[str]]:
        """
        Search for traces using direct Databricks SQL queries.

        Args:
            experiment_ids: List of experiment IDs to search
            filter_string: Optional filter string for trace search
            max_results: Maximum number of results to return
            order_by: Optional list of fields to order by
            page_token: Optional pagination token
            model_id: Optional model ID for unified search
            sql_warehouse_id: Optional SQL warehouse ID for unified search

        Returns:
            Tuple of (list of TraceInfo objects, next page token)
        """
        # If sql_warehouse_id is provided, raise not implemented error
        if sql_warehouse_id is not None:
            raise NotImplementedError(
                "Unified search with sql_warehouse_id is not yet implemented in DatabricksSqlStore"
            )

        # Try to get the trace table for single-experiment queries
        table_name = None
        if experiment_ids and len(experiment_ids) == 1:
            # Try to discover the table name from monitors API
            table_name = self._get_trace_table_for_experiment(experiment_ids[0])

        # If no table found, fall back to REST API
        if not table_name:
            # No trace table available, use parent REST implementation
            return super().search_traces(
                experiment_ids=experiment_ids,
                filter_string=filter_string,
                max_results=max_results,
                order_by=order_by,
                page_token=page_token,
                model_id=model_id,
                sql_warehouse_id=sql_warehouse_id,
            )

        # Otherwise, use direct Databricks SQL query
        spark = self._get_or_create_spark_session()

        # Use the discovered table name
        # For testing, allow override via _TABLE_NAME attribute
        table_name = getattr(self, "_TABLE_NAME", table_name)

        # Build parameterized query components
        params = {}

        # Build WHERE clause
        # Note: We don't need to filter by experiment_id since the table
        # is already specific to an experiment (discovered via monitors API)
        where_conditions = []

        # Parse and add filter string conditions if provided
        if filter_string:
            # Parse filter_string and add conditions with parameters
            filter_conditions = self._parse_filter_string(
                filter_string, table_name, params
            )
            if filter_conditions:
                where_conditions.extend(filter_conditions)

        # Build ORDER BY clause safely
        # Validate and sanitize the order_by fields to prevent injection
        safe_order_clause = self._build_safe_order_clause(order_by)

        # Construct the WHERE clause
        where_clause = (
            f" WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Use parameterized limit
        params["limit_value"] = max_results

        # Build the query with all parameterized components
        query = f"""
            SELECT
                trace_id,
                request_time,
                execution_duration_ms,
                state,
                tags,
                trace_metadata,
                request_preview,
                response_preview
            FROM {table_name}
            {where_clause}
            {safe_order_clause}
            LIMIT :limit_value
        """

        # Execute query with parameters to prevent SQL injection
        result_df = spark.sql(query, params)
        rows = result_df.collect()

        # Convert rows to TraceInfo objects
        traces = []
        for row in rows:
            # Create TraceInfo from row data
            # Extract experiment_id from trace_location
            exp_id = experiment_ids[0] if experiment_ids else "0"
            if hasattr(row, "trace_location") and row.trace_location:
                if hasattr(row.trace_location, "mlflow_experiment"):
                    exp_id = row.trace_location.mlflow_experiment.experiment_id

            # Create trace location with proper enum type
            trace_location = TraceLocation(
                type=TraceLocationType.MLFLOW_EXPERIMENT,
                mlflow_experiment=MlflowExperimentLocation(experiment_id=exp_id),
            )

            # Map state string to TraceState enum
            state_map = {
                "OK": TraceState.OK,
                "ERROR": TraceState.ERROR,
                "FAILED": TraceState.ERROR,
                "IN_PROGRESS": TraceState.IN_PROGRESS,
            }
            state = state_map.get(row["state"], TraceState.STATE_UNSPECIFIED)

            # PySpark Row objects don't have .get() method, use getattr with default
            trace_info = TraceInfo(
                trace_id=row["trace_id"],
                trace_location=trace_location,
                request_time=int(row["request_time"].timestamp() * 1000),
                state=state,
                client_request_id=getattr(row, "client_request_id", row["trace_id"]),
                execution_duration=row["execution_duration_ms"] or 0,
                trace_metadata=getattr(row, "trace_metadata", {}),
                tags=row["tags"] or {},
                request_preview=getattr(row, "request_preview", None),
                response_preview=getattr(row, "response_preview", None),
            )
            traces.append(trace_info)

        # For now, no pagination
        next_page_token = None

        return traces, next_page_token

    def calculate_trace_filter_correlation(
        self,
        experiment_ids: list[str],
        filter_string1: str,
        filter_string2: str,
    ) -> TraceFilterCorrelationResult:
        """
        Calculate the correlation (NPMI) between two trace filter conditions.

        This implementation uses direct Databricks SQL queries to compute NPMI
        (Normalized Pointwise Mutual Information) between traces matching two
        different filter conditions.

        Args:
            experiment_ids: List of experiment IDs to search traces in.
            filter_string1: First filter condition (e.g., "status = 'ERROR'").
            filter_string2: Second filter condition (e.g., "tags.tool = 'langchain'").

        Returns:
            TraceFilterCorrelationResult containing NPMI score and counts.
        """
        # If more than one experiment, fall back to REST API
        if not experiment_ids or len(experiment_ids) != 1:
            return super().calculate_trace_filter_correlation(
                experiment_ids, filter_string1, filter_string2
            )

        # Try to get the trace table
        table_name = self._get_trace_table_for_experiment(experiment_ids[0])
        if not table_name:
            # No trace table available, use parent REST implementation
            return super().calculate_trace_filter_correlation(
                experiment_ids, filter_string1, filter_string2
            )

        # Get Spark session
        spark = self._get_or_create_spark_session()

        # Build parameterized query components
        params = {}

        # Parse filter strings into SQL conditions
        parser1 = TraceFilterParser(table_name)
        conditions1, params1 = parser1.parse(filter_string1)

        parser2 = TraceFilterParser(table_name)
        conditions2, params2 = parser2.parse(filter_string2)

        # Combine parameters (ensure no overlap in param names)
        for key, value in params1.items():
            params[f"f1_{key}"] = value
        for key, value in params2.items():
            params[f"f2_{key}"] = value

        # Build WHERE clauses for each filter
        # Replace param references to use f1_ and f2_ prefixes
        where_clause1 = ""
        if conditions1:
            adjusted_conditions1 = []
            for cond in conditions1:
                # Replace :param_N with :f1_param_N in condition
                import re

                adjusted_cond = re.sub(r":param_(\d+)", r":f1_param_\1", cond)
                adjusted_conditions1.append(adjusted_cond)
            where_clause1 = " AND ".join(adjusted_conditions1)

        where_clause2 = ""
        if conditions2:
            adjusted_conditions2 = []
            for cond in conditions2:
                # Replace :param_N with :f2_param_N in condition
                import re

                adjusted_cond = re.sub(r":param_(\d+)", r":f2_param_\1", cond)
                adjusted_conditions2.append(adjusted_cond)
            where_clause2 = " AND ".join(adjusted_conditions2)

        # Build the NPMI calculation query
        query = f"""
        WITH 
        -- Total count of traces
        total_counts AS (
            SELECT COUNT(DISTINCT trace_id) as total 
            FROM {table_name}
        ),
        
        -- Traces matching filter 1
        filter1_matches AS (
            SELECT DISTINCT trace_id
            FROM {table_name}
            WHERE {where_clause1 if where_clause1 else "1=1"}
        ),
        
        -- Traces matching filter 2
        filter2_matches AS (
            SELECT DISTINCT trace_id
            FROM {table_name}
            WHERE {where_clause2 if where_clause2 else "1=1"}
        ),
        
        -- Joint matches (intersection)
        joint_matches AS (
            SELECT trace_id FROM filter1_matches
            INTERSECT
            SELECT trace_id FROM filter2_matches
        ),
        
        -- Calculate counts
        counts AS (
            SELECT 
                (SELECT total FROM total_counts) as total_count,
                (SELECT COUNT(*) FROM filter1_matches) as filter1_count,
                (SELECT COUNT(*) FROM filter2_matches) as filter2_count,
                (SELECT COUNT(*) FROM joint_matches) as joint_count
        ),
        
        -- Calculate probabilities and NPMI
        probabilities AS (
            SELECT 
                *,
                CAST(filter1_count AS DOUBLE) / total_count as p_filter1,
                CAST(filter2_count AS DOUBLE) / total_count as p_filter2,
                CAST(joint_count AS DOUBLE) / total_count as p_joint
            FROM counts
        )
        SELECT 
            total_count,
            filter1_count,
            filter2_count,
            joint_count,
            p_filter1,
            p_filter2,
            p_joint,
            -- NPMI calculation
            CASE 
                WHEN joint_count = 0 THEN -1.0
                WHEN joint_count = filter1_count AND joint_count = filter2_count THEN 1.0
                WHEN p_joint = 0 THEN -1.0
                ELSE LOG2(p_joint / (p_filter1 * p_filter2)) / (-LOG2(p_joint))
            END as npmi,
            -- Calculate confidence intervals using Wilson score (z=1.96 for 95% confidence)
            -- Lower bound calculation
            CASE 
                WHEN joint_count = 0 THEN -1.0
                WHEN joint_count = filter1_count AND joint_count = filter2_count THEN 1.0
                ELSE 
                    LOG2(
                        GREATEST(0.0001, 
                            (joint_count - 1.96 * SQRT(joint_count * (1 - p_joint))) / total_count
                        ) / (
                            LEAST(1.0, (filter1_count + 1.96 * SQRT(filter1_count * (1 - p_filter1))) / total_count) *
                            LEAST(1.0, (filter2_count + 1.96 * SQRT(filter2_count * (1 - p_filter2))) / total_count)
                        )
                    ) / (
                        -LOG2(GREATEST(0.0001, 
                            (joint_count - 1.96 * SQRT(joint_count * (1 - p_joint))) / total_count
                        ))
                    )
            END as npmi_lower,
            -- Upper bound calculation
            CASE 
                WHEN joint_count = 0 THEN -1.0
                WHEN joint_count = filter1_count AND joint_count = filter2_count THEN 1.0
                ELSE 
                    LOG2(
                        LEAST(1.0, 
                            (joint_count + 1.96 * SQRT(joint_count * (1 - p_joint))) / total_count
                        ) / (
                            GREATEST(0.0001, (filter1_count - 1.96 * SQRT(filter1_count * (1 - p_filter1))) / total_count) *
                            GREATEST(0.0001, (filter2_count - 1.96 * SQRT(filter2_count * (1 - p_filter2))) / total_count)
                        )
                    ) / (
                        -LOG2(LEAST(1.0, 
                            (joint_count + 1.96 * SQRT(joint_count * (1 - p_joint))) / total_count
                        ))
                    )
            END as npmi_upper
        FROM probabilities
        """

        # Execute query with parameters
        result_df = spark.sql(query, params)
        rows = result_df.collect()

        if not rows:
            # No data found
            return TraceFilterCorrelationResult(
                npmi=0.0,
                confidence_lower=None,
                confidence_upper=None,
                filter_string1_count=0,
                filter_string2_count=0,
                joint_count=0,
                total_count=0,
            )

        row = rows[0]

        # Extract values from row
        return TraceFilterCorrelationResult(
            npmi=float(row["npmi"]),
            confidence_lower=float(row["npmi_lower"])
            if row["npmi_lower"] is not None
            else None,
            confidence_upper=float(row["npmi_upper"])
            if row["npmi_upper"] is not None
            else None,
            filter_string1_count=int(row["filter1_count"]),
            filter_string2_count=int(row["filter2_count"]),
            joint_count=int(row["joint_count"]),
            total_count=int(row["total_count"]),
        )

    def __del__(self):
        """Clean up Spark session when store is destroyed."""
        if self._spark_session:
            try:
                self._spark_session.stop()
            except Exception:
                pass
