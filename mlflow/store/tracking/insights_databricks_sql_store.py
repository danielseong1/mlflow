"""
Databricks SQL implementation of the insights store.

This module provides insights analytics using direct Databricks SQL queries
for better performance and scalability compared to REST API calls.
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from functools import partial
from mlflow.store.tracking.databricks_sql_store import DatabricksSqlStore
from mlflow.store.tracking.insights_abstract_store import InsightsAbstractStore
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE
from mlflow.utils.databricks_utils import get_databricks_host_creds

_logger = logging.getLogger(__name__)


class InsightsDatabricksSqlStore(InsightsAbstractStore, DatabricksSqlStore):
    """Databricks SQL implementation of the insights store.
    
    This class extends both InsightsAbstractStore and DatabricksSqlStore to provide 
    insights analytics using direct SQL queries against Databricks tables.
    Since InsightsAbstractStore now extends AbstractStore, we put it first
    in the inheritance order to ensure proper method resolution order (MRO).
    """
    
    def __init__(self, store_uri):
        """Initialize the Databricks SQL insights store.
        
        Args:
            store_uri: The Databricks URI (e.g., 'databricks' or 'databricks://')
        """
        # Call parent DatabricksSqlStore __init__ which expects store_uri
        super().__init__(store_uri)
        self._experiment_ids = None
    
    def _get_experiment_ids(self) -> List[str]:
        """Get experiment IDs from environment or configuration.
        
        Returns:
            List of experiment IDs to analyze
        """
        # Always check environment variable for current experiment IDs
        exp_ids = os.environ.get('MLFLOW_EXPERIMENT_IDS', '')
        if exp_ids:
            return [e.strip() for e in exp_ids.split(',')]
        else:
            # No default - experiment IDs must be provided
            return []
    
    def _get_time_bucket_expression(self, time_expr: str, time_bucket: str, timezone: Optional[str] = None) -> str:
        """Generate SQL expression for time bucketing with timezone support.
        
        Args:
            time_expr: The timestamp column expression (e.g., 'request_time')
            time_bucket: Time aggregation bucket ('hour', 'day', 'week')
            timezone: Optional timezone for alignment (e.g., 'America/Los_Angeles')
            
        Returns:
            SQL expression that returns Unix timestamp in milliseconds for the bucket
        """
        if timezone:
            # When timezone is provided:
            # 1. Convert to user timezone
            # 2. Truncate to bucket boundary in that timezone
            # 3. Convert back to UTC for consistent timestamp representation
            if time_bucket == 'hour':
                return f"unix_timestamp(to_utc_timestamp(date_trunc('hour', {time_expr}), '{timezone}')) * 1000"
            elif time_bucket == 'day':
                return f"unix_timestamp(to_utc_timestamp(date_trunc('day', {time_expr}), '{timezone}')) * 1000"
            elif time_bucket == 'week':
                return f"unix_timestamp(to_utc_timestamp(date_trunc('week', {time_expr}), '{timezone}')) * 1000"
            else:
                return f"unix_timestamp(to_utc_timestamp(date_trunc('hour', {time_expr}), '{timezone}')) * 1000"
        else:
            # No timezone conversion needed - use UTC directly
            if time_bucket == 'hour':
                return f"unix_timestamp(date_trunc('hour', {time_expr})) * 1000"
            elif time_bucket == 'day':
                return f"unix_timestamp(date_trunc('day', {time_expr})) * 1000"
            elif time_bucket == 'week':
                return f"unix_timestamp(date_trunc('week', {time_expr})) * 1000"
            else:
                return f"unix_timestamp(date_trunc('hour', {time_expr})) * 1000"
    
    def _get_trace_table_name(self) -> str:
        """Get the trace table name for the current experiment.
        
        Returns:
            Fully qualified table name
        """
        experiment_ids = self._get_experiment_ids()
        if not experiment_ids:
            raise MlflowException(
                "No experiment IDs configured", 
                error_code=INVALID_PARAMETER_VALUE
            )
        
        # Use the first experiment ID
        experiment_id = experiment_ids[0]
        _logger.info(f"Getting trace table for experiment {experiment_id}")
        table_name = self._get_trace_table_for_experiment(experiment_id)
        
        _logger.info(f"Got trace table name: {table_name}")
        
        if not table_name:
            raise MlflowException(
                f"Failed to get trace table for experiment {experiment_id}. "
                "This experiment may not have tracing enabled or the GetMonitor API call failed.",
                error_code=RESOURCE_DOES_NOT_EXIST
            )
        
        return table_name
    
    # Traffic & Cost Methods
    
    def get_traffic_volume(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get trace volume statistics using Databricks SQL."""
        try:
            table_name = self._get_trace_table_name()
        except:
            # If we can't get table name, return empty result for now
            return {
                'summary': {'count': 0, 'ok_count': 0, 'error_count': 0},
                'time_series': []
            }
        
        if not table_name:
            # No table available, return empty result
            return {
                'summary': {'count': 0, 'ok_count': 0, 'error_count': 0},
                'time_series': []
            }
        
        spark = self._get_or_create_spark_session()
        
        # Build time filters
        time_conditions = []
        params = {}
        if start_time:
            time_conditions.append("unix_millis(request_time) >= :start_time")
            params['start_time'] = start_time
        if end_time:
            time_conditions.append("unix_millis(request_time) <= :end_time")
            params['end_time'] = end_time
        
        where_clause = " AND ".join(time_conditions) if time_conditions else "1=1"
        
        # Determine time expression based on timezone
        if timezone:
            # Convert milliseconds to timestamp with timezone
            time_expr = f"from_utc_timestamp(request_time, '{timezone}')"
        else:
            time_expr = "request_time"
        
        # Build time bucket expression using utility function
        bucket_expr = self._get_time_bucket_expression(time_expr, time_bucket, timezone)
        
        # Query for summary
        summary_query = f"""
        SELECT 
            COUNT(*) as count,
            SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count
        FROM {table_name}
        WHERE {where_clause}
        """
        
        # Query for time series
        time_series_query = f"""
        SELECT 
            {bucket_expr} as time_bucket,
            COUNT(*) as count,
            SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count
        FROM {table_name}
        WHERE {where_clause}
        GROUP BY 1
        ORDER BY 1
        """
        
        # Execute queries
        summary_df = spark.sql(summary_query, params).collect()
        time_series_df = spark.sql(time_series_query, params).collect()
        
        # Format response
        summary = summary_df[0] if summary_df else {'count': 0, 'ok_count': 0, 'error_count': 0}
        
        return {
            'summary': {
                'count': summary['count'] or 0,
                'ok_count': summary['ok_count'] or 0,
                'error_count': summary['error_count'] or 0
            },
            'time_series': [
                {
                    'time_bucket': int(row['time_bucket']) if row['time_bucket'] else 0,
                    'count': row['count'] or 0,
                    'ok_count': row['ok_count'] or 0,
                    'error_count': row['error_count'] or 0
                }
                for row in time_series_df
            ]
        }
    
    def get_traffic_latency(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get latency percentile statistics using Databricks SQL."""
        try:
            table_name = self._get_trace_table_name()
        except:
            # If we can't get table name, return empty result for now
            return {
                'summary': {'p50': None, 'p95': None, 'p99': None, 'avg_latency_ms': None, 'count': 0},
                'time_series': []
            }
        
        if not table_name:
            # No table available, return empty result
            return {
                'summary': {'p50': None, 'p95': None, 'p99': None, 'avg_latency_ms': None, 'count': 0},
                'time_series': []
            }
        
        spark = self._get_or_create_spark_session()
        
        # Build filters for successful traces with execution time
        conditions = ["state = 'OK'", "execution_duration_ms IS NOT NULL"]
        params = {}
        if start_time:
            conditions.append("unix_millis(request_time) >= :start_time")
            params['start_time'] = start_time
        if end_time:
            conditions.append("unix_millis(request_time) <= :end_time")
            params['end_time'] = end_time
        
        where_clause = " AND ".join(conditions)
        
        # Determine time expression and bucket expression
        if timezone:
            time_expr = f"from_utc_timestamp(request_time, '{timezone}')"
        else:
            time_expr = "request_time"
        
        bucket_expr = self._get_time_bucket_expression(time_expr, time_bucket, timezone)
        
        # Query for summary percentiles
        summary_query = f"""
        SELECT 
            percentile(execution_duration_ms, 0.5) as p50,
            percentile(execution_duration_ms, 0.9) as p90,
            percentile(execution_duration_ms, 0.99) as p99,
            AVG(execution_duration_ms) as avg_latency_ms,
            MIN(execution_duration_ms) as min_latency,
            MAX(execution_duration_ms) as max_latency,
            COUNT(*) as count
        FROM {table_name}
        WHERE {where_clause}
        """
        
        # Query for time series percentiles
        time_series_query = f"""
        SELECT 
            {bucket_expr} as time_bucket,
            percentile(execution_duration_ms, 0.5) as p50,
            percentile(execution_duration_ms, 0.9) as p90,
            percentile(execution_duration_ms, 0.99) as p99,
            AVG(execution_duration_ms) as avg_latency_ms,
            COUNT(*) as count
        FROM {table_name}
        WHERE {where_clause}
        GROUP BY 1
        ORDER BY 1
        """
        
        # Execute queries
        summary_df = spark.sql(summary_query, params).collect()
        time_series_df = spark.sql(time_series_query, params).collect()
        
        # Format response
        if summary_df:
            summary = summary_df[0]
            summary_dict = {
                'p50_latency': summary['p50'],
                'p90_latency': summary['p90'],
                'p99_latency': summary['p99'],
                'avg_latency': summary['avg_latency_ms'],
                'min_latency': summary['min_latency'] if hasattr(summary, 'min_latency') else None,
                'max_latency': summary['max_latency'] if hasattr(summary, 'max_latency') else None
            }
        else:
            summary_dict = {
                'p50_latency': None,
                'p90_latency': None,
                'p99_latency': None,
                'avg_latency': None,
                'min_latency': None,
                'max_latency': None
            }
        
        return {
            'summary': summary_dict,
            'time_series': [
                {
                    'time_bucket': int(row['time_bucket']) if row['time_bucket'] else 0,
                    'p50_latency': row['p50'],
                    'p90_latency': row['p90'],
                    'p99_latency': row['p99'],
                    'avg_latency': row['avg_latency_ms']
                }
                for row in time_series_df
            ]
        }
    
    def get_traffic_errors(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get error statistics using Databricks SQL."""
        try:
            table_name = self._get_trace_table_name()
        except:
            # If we can't get table name, return empty result for now
            return {
                'summary': {'total_count': 0, 'error_count': 0, 'error_rate': 0.0},
                'time_series': []
            }
        
        if not table_name:
            # No table available, return empty result
            return {
                'summary': {'total_count': 0, 'error_count': 0, 'error_rate': 0.0},
                'time_series': []
            }
        
        spark = self._get_or_create_spark_session()
        
        # Build time filters
        time_conditions = []
        params = {}
        if start_time:
            time_conditions.append("unix_millis(request_time) >= :start_time")
            params['start_time'] = start_time
        if end_time:
            time_conditions.append("unix_millis(request_time) <= :end_time")
            params['end_time'] = end_time
        
        where_clause = " AND ".join(time_conditions) if time_conditions else "1=1"
        
        # Determine time expression and bucket expression
        if timezone:
            time_expr = f"from_utc_timestamp(request_time, '{timezone}')"
        else:
            time_expr = "request_time"
        
        bucket_expr = self._get_time_bucket_expression(time_expr, time_bucket, timezone)
        
        # Query for error summary
        summary_query = f"""
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count,
            CAST(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100 as error_rate
        FROM {table_name}
        WHERE {where_clause}
        """
        
        # Query for time series
        time_series_query = f"""
        SELECT 
            {bucket_expr} as time_bucket,
            COUNT(*) as total_count,
            SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count,
            CAST(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100 as error_rate
        FROM {table_name}
        WHERE {where_clause}
        GROUP BY 1
        ORDER BY 1
        """
        
        # Execute queries
        summary_df = spark.sql(summary_query, params).collect()
        time_series_df = spark.sql(time_series_query, params).collect()
        
        # Format response
        summary = summary_df[0] if summary_df else {
            'total_count': 0, 'error_count': 0, 'error_rate': 0.0
        }
        
        return {
            'summary': {
                'total_count': summary['total_count'] or 0,
                'error_count': summary['error_count'] or 0,
                'error_rate': summary['error_rate'] or 0.0
            },
            'time_series': [
                {
                    'time_bucket': int(row['time_bucket']) if row['time_bucket'] else 0,
                    'total_count': row['total_count'] or 0,
                    'error_count': row['error_count'] or 0,
                    'error_rate': row['error_rate'] or 0.0
                }
                for row in time_series_df
            ]
        }
    
    # Stub implementations for other methods - to be implemented
    
    def discover_assessments(
        self,
        experiment_ids: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover assessments from the actual database."""
        # Use the existing get_assessments method which queries real data
        if experiment_ids:
            return self.get_assessments(experiment_ids[0])
        return []
    
    def get_assessment_metrics(
        self,
        assessment_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get assessment metrics using Databricks SQL."""
        try:
            # Get the trace table name
            experiment_ids = self._get_experiment_ids()
            if not experiment_ids:
                return {'summary': {}, 'time_series': []}
            
            trace_table = self._get_trace_table_for_experiment(experiment_ids[0])
            if not trace_table:
                return {'summary': {}, 'time_series': []}
            
            spark = self._get_or_create_spark_session()
            
            # Build time filters
            conditions = [f"assessment.name = '{assessment_name}'"]
            params = {}
            if start_time:
                conditions.append("unix_millis(request_time) >= :start_time")
                params['start_time'] = start_time
            if end_time:
                conditions.append("unix_millis(request_time) <= :end_time")
                params['end_time'] = end_time
            
            where_clause = " AND ".join(conditions)
            
            # Determine time expression and bucket expression
            if timezone:
                time_expr = f"from_utc_timestamp(request_time, '{timezone}')"
            else:
                time_expr = "request_time"
            
            bucket_expr = self._get_time_bucket_expression(time_expr, time_bucket, timezone)
            
            # Query for summary stats
            summary_query = f"""
            SELECT 
                COUNT(*) as total_count,
                SUM(CASE WHEN assessment.feedback.value = '"no"' OR assessment.feedback.value = 'false' THEN 1 ELSE 0 END) as failure_count,
                CAST(SUM(CASE WHEN assessment.feedback.value = '"no"' OR assessment.feedback.value = 'false' THEN 1 ELSE 0 END) AS DOUBLE) / 
                    NULLIF(COUNT(*), 0) * 100 as failure_rate
            FROM {trace_table}
            LATERAL VIEW explode(assessments) AS assessment
            WHERE {where_clause}
            AND state = 'OK'
            """
            
            # Query for time series
            time_series_query = f"""
            SELECT 
                {bucket_expr} as time_bucket,
                COUNT(*) as total_count,
                SUM(CASE WHEN assessment.feedback.value = '"no"' OR assessment.feedback.value = 'false' THEN 1 ELSE 0 END) as failure_count,
                CAST(SUM(CASE WHEN assessment.feedback.value = '"no"' OR assessment.feedback.value = 'false' THEN 1 ELSE 0 END) AS DOUBLE) / 
                    NULLIF(COUNT(*), 0) * 100 as failure_rate
            FROM {trace_table}
            LATERAL VIEW explode(assessments) AS assessment
            WHERE {where_clause}
            AND state = 'OK'
            GROUP BY 1
            ORDER BY 1
            """
            
            # Execute queries
            summary_df = spark.sql(summary_query, params).collect()
            time_series_df = spark.sql(time_series_query, params).collect()
            
            # Format response
            summary = {}
            if summary_df and summary_df[0]:
                row = summary_df[0]
                summary = {
                    'total_count': row['total_count'] or 0,
                    'failure_count': row['failure_count'] or 0,
                    'failure_rate': row['failure_rate'] or 0.0
                }
            
            time_series = []
            for row in time_series_df:
                time_series.append({
                    'time_bucket': int(row['time_bucket']) if row['time_bucket'] else 0,
                    'total_count': row['total_count'] or 0,
                    'failure_count': row['failure_count'] or 0,
                    'failure_rate': row['failure_rate'] or 0.0
                })
            
            return {
                'assessment_name': assessment_name,
                'assessment_type': 'boolean',
                'sources': ['databricks'],
                'summary': summary,
                'time_series': time_series
            }
        except Exception as e:
            _logger.error(f"Error getting assessment metrics: {e}")
            return {'summary': {}, 'time_series': []}
    
    def discover_tools(
        self,
        experiment_ids: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover tools used in traces using Databricks SQL."""
        # Get table name for the specified experiment
        table_name = None
        if experiment_ids:
            table_name = self._get_trace_table_for_experiment(experiment_ids[0])
        
        if not table_name:
            _logger.warning(f"No trace table found for experiment_ids: {experiment_ids}")
            return []
        
        spark = self._get_or_create_spark_session()
        
        # Build time filters
        time_conditions = []
        params = {}
        if start_time:
            time_conditions.append("unix_millis(request_time) >= :start_time")
            params['start_time'] = start_time
        if end_time:
            time_conditions.append("unix_millis(request_time) <= :end_time")
            params['end_time'] = end_time
        
        where_clause = " AND ".join(time_conditions) if time_conditions else "1=1"
        
        # Query to find tools from spans with attributes['mlflow.spanType'] = '"TOOL"'
        # Calculate duration in milliseconds from start/end timestamps
        # Consolidate tool names by removing _{integer} suffixes
        query = f"""
        WITH tool_traces AS (
            SELECT 
                t.trace_id,
                t.execution_duration_ms,
                t.state,
                t.request_time,
                CASE 
                    WHEN tool_span.name RLIKE '_[0-9]+$' THEN REGEXP_REPLACE(tool_span.name, '_[0-9]+$', '')
                    ELSE tool_span.name
                END as tool_name,
                (unix_timestamp(tool_span.end_time) - unix_timestamp(tool_span.start_time)) * 1000 as duration_ms
            FROM {table_name} t
            LATERAL VIEW explode(spans) AS tool_span
            WHERE tool_span.attributes['mlflow.spanType'] = '"TOOL"'
                AND {where_clause}
        ),
        tool_metrics AS (
            SELECT 
                tool_name,
                COUNT(*) as total_calls,
                SUM(CASE WHEN state != 'OK' THEN 1 ELSE 0 END) as error_count,
                SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as success_count,
                AVG(CASE WHEN duration_ms > 0 THEN duration_ms ELSE execution_duration_ms END) as avg_latency_ms,
                percentile(CASE WHEN duration_ms > 0 THEN duration_ms ELSE execution_duration_ms END, 0.5) as p50_latency_ms,
                percentile(CASE WHEN duration_ms > 0 THEN duration_ms ELSE execution_duration_ms END, 0.9) as p90_latency_ms,
                percentile(CASE WHEN duration_ms > 0 THEN duration_ms ELSE execution_duration_ms END, 0.99) as p99_latency_ms,
                CAST(SUM(CASE WHEN state != 'OK' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS DOUBLE) as error_rate,
                DATE_FORMAT(MIN(request_time), 'yyyy-MM-dd HH:mm:ss') as first_seen,
                DATE_FORMAT(MAX(request_time), 'yyyy-MM-dd HH:mm:ss') as last_seen
            FROM tool_traces
            GROUP BY tool_name
            HAVING COUNT(*) >= :min_count
        )
        SELECT 
            tool_name,
            total_calls,
            error_count,
            success_count,
            COALESCE(avg_latency_ms, 0.0) as avg_latency_ms,
            COALESCE(p50_latency_ms, 0.0) as p50_latency_ms,
            COALESCE(p90_latency_ms, 0.0) as p90_latency_ms,
            COALESCE(p99_latency_ms, 0.0) as p99_latency_ms,
            COALESCE(error_rate, 0.0) as error_rate,
            first_seen,
            last_seen
        FROM tool_metrics
        ORDER BY total_calls DESC
        """
        
        params['min_count'] = min_count
        
        # Execute query
        try:
            tools_df = spark.sql(query, params).collect()
            
            # Format results according to ToolDiscoveryInfo Pydantic model
            results = []
            for row in tools_df:
                results.append({
                    'tool_name': row['tool_name'],
                    'total_calls': row['total_calls'],
                    'error_count': row['error_count'],
                    'success_count': row['success_count'],
                    'avg_latency_ms': float(row['avg_latency_ms']) if row['avg_latency_ms'] else 0.0,
                    'p50_latency_ms': float(row['p50_latency_ms']) if row['p50_latency_ms'] else 0.0,
                    'p90_latency_ms': float(row['p90_latency_ms']) if row['p90_latency_ms'] else 0.0,
                    'p99_latency_ms': float(row['p99_latency_ms']) if row['p99_latency_ms'] else 0.0,
                    'error_rate': float(row['error_rate']) if row['error_rate'] else 0.0,
                    'first_seen': row['first_seen'] or '',
                    'last_seen': row['last_seen'] or ''
                })
            
            return results
        except Exception as e:
            # If query fails, return empty
            import logging
            logging.error(f"Failed to discover tools: {e}")
            return []
    
    def get_tool_metrics(
        self,
        experiment_ids: List[str],
        tool_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get metrics for a specific tool using Databricks SQL."""
        # Get table name for the specified experiment
        table_name = None
        if experiment_ids:
            table_name = self._get_trace_table_for_experiment(experiment_ids[0])
        
        if not table_name:
            _logger.warning(f"No trace table found for experiment_ids: {experiment_ids}")
            return {'summary': {}, 'time_series': []}
        
        spark = self._get_or_create_spark_session()
        
        # Build time filters
        conditions = []
        # For tool pattern matching, we need to handle both base name and variants
        params = {'tool_name': tool_name}
        
        if start_time:
            conditions.append("unix_millis(request_time) >= :start_time")
            params['start_time'] = start_time
        if end_time:
            conditions.append("unix_millis(request_time) <= :end_time")
            params['end_time'] = end_time
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Determine time expression and bucket expression
        if timezone:
            time_expr = f"from_utc_timestamp(request_time, '{timezone}')"
        else:
            time_expr = "request_time"
        
        bucket_expr = self._get_time_bucket_expression(time_expr, time_bucket, timezone)
        
        # Query for summary metrics  
        # Join with spans to get tool-specific metrics
        summary_query = f"""
        WITH tool_traces AS (
            SELECT 
                t.trace_id,
                t.execution_duration_ms,
                t.request_time,
                t.state,
                tool_span.name as tool_name,
                (unix_timestamp(tool_span.end_time) - unix_timestamp(tool_span.start_time)) * 1000 as span_duration_ms
            FROM {table_name} t
            LATERAL VIEW explode(spans) AS tool_span
            WHERE tool_span.attributes['mlflow.spanType'] = '"TOOL"'
                AND (tool_span.name = :tool_name OR tool_span.name RLIKE CONCAT(:tool_name, '_[0-9]+$'))
                AND {where_clause}
        )
        SELECT 
            COUNT(*) as usage_count,
            AVG(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END) as avg_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.5) as p50_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.9) as p90_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.99) as p99_latency
        FROM tool_traces
        """
        
        # Query for time series
        time_series_query = f"""
        WITH tool_traces AS (
            SELECT 
                t.trace_id,
                t.execution_duration_ms,
                t.request_time,
                t.state,
                tool_span.name as tool_name,
                tool_span.status_code as span_status,
                (unix_timestamp(tool_span.end_time) - unix_timestamp(tool_span.start_time)) * 1000 as span_duration_ms
            FROM {table_name} t
            LATERAL VIEW explode(spans) AS tool_span
            WHERE tool_span.attributes['mlflow.spanType'] = '"TOOL"'
                AND (tool_span.name = :tool_name OR tool_span.name RLIKE CONCAT(:tool_name, '_[0-9]+$'))
                AND {where_clause}
        )
        SELECT 
            {bucket_expr} as time_bucket,
            COUNT(*) as count,
            SUM(CASE WHEN span_status != 'OK' THEN 1 ELSE 0 END) as error_count,
            AVG(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END) as avg_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.5) as p50_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.9) as p90_latency,
            percentile(CASE WHEN span_duration_ms > 0 THEN span_duration_ms ELSE execution_duration_ms END, 0.99) as p99_latency
        FROM tool_traces
        GROUP BY 1
        ORDER BY 1
        """
        
        try:
            # Execute queries
            summary_df = spark.sql(summary_query, params).collect()
            time_series_df = spark.sql(time_series_query, params).collect()
            
            # Format summary
            if summary_df and summary_df[0]['usage_count'] > 0:
                summary = {
                    'usage_count': summary_df[0]['usage_count'],
                    'avg_latency': summary_df[0]['avg_latency'],
                    'p50_latency': summary_df[0]['p50_latency'],
                    'p90_latency': summary_df[0]['p90_latency'],
                    'p99_latency': summary_df[0]['p99_latency']
                }
            else:
                summary = {
                    'usage_count': 0,
                    'avg_latency': None,
                    'p50_latency': None,
                    'p90_latency': None,
                    'p99_latency': None
                }
            
            # Format time series
            time_series = [
                {
                    'time_bucket': int(row['time_bucket']) if row['time_bucket'] else 0,
                    'count': row['count'],
                    'error_count': row['error_count'] or 0,
                    'avg_latency': row['avg_latency'],
                    'p50_latency': row['p50_latency'],
                    'p90_latency': row['p90_latency'],
                    'p99_latency': row['p99_latency']
                }
                for row in time_series_df
            ]
            
            return {
                'summary': summary,
                'time_series': time_series
            }
        except Exception as e:
            import logging
            logging.error(f"Failed to get tool metrics: {e}")
            return {'summary': {}, 'time_series': []}
    
    def discover_tags(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover tags - TODO: Implement using Databricks SQL."""
        return []
    
    def get_tag_metrics(
        self,
        tag_key: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get tag metrics - TODO: Implement using Databricks SQL."""
        return {'tag_values': [], 'time_series': []}
    
    def discover_dimensions(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        filter_string: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Discover dimensions - TODO: Implement using Databricks SQL."""
        return []
    
    def calculate_npmi(
        self,
        dimension1: str,
        value1: str,
        dimension2: str,
        value2: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        filter_string: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate NPMI - TODO: Implement using Databricks SQL."""
        return {
            'npmi': 0.0,
            'count1': 0,
            'count2': 0,
            'joint_count': 0,
            'total_count': 0
        }
    
    def get_correlations(
        self,
        dimension: str,
        value: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        filter_string: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get correlations - TODO: Implement using Databricks SQL."""
        return []
    
    def execute_sql(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute a raw SQL query against the Databricks warehouse.

        Args:
            sql_query: The SQL query string to execute

        Returns:
            List of dictionaries representing the query results
        """
        try:
            import datetime
            from decimal import Decimal
            from pyspark.sql.types import Row

            spark = self._get_or_create_spark_session()
            result = spark.sql(sql_query).collect()

            def convert_value(value):
                """Recursively convert Spark SQL types to JSON-serializable types."""
                if value is None:
                    return None
                elif isinstance(value, (datetime.datetime, datetime.date)):
                    return value.isoformat()
                elif isinstance(value, Decimal):
                    return float(value)
                elif isinstance(value, Row):
                    # Convert nested Row objects to dicts
                    return {k: convert_value(v) for k, v in value.asDict().items()}
                elif isinstance(value, dict):
                    # Handle maps
                    return {k: convert_value(v) for k, v in value.items()}
                elif isinstance(value, (list, tuple)):
                    # Handle arrays
                    return [convert_value(item) for item in value]
                else:
                    return value

            # Convert Spark Row objects to dictionaries with proper type handling
            rows = []
            for row in result:
                row_dict = {}
                for key, value in row.asDict().items():
                    row_dict[key] = convert_value(value)
                rows.append(row_dict)

            return rows
        except Exception as e:
            _logger.error(f"Error executing SQL query: {e}")
            raise MlflowException(f"Failed to execute SQL query: {str(e)}")

    def get_assessments(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Get assessments for an experiment.

        Args:
            experiment_id: The experiment ID to get assessments for

        Returns:
            List of assessment info dictionaries
        """
        print(f"DEBUG: get_assessments called with experiment_id={experiment_id}")
        _logger.info(f"DEBUG: get_assessments called with experiment_id={experiment_id}")
        try:
            # Get the trace table name
            trace_table = self._get_trace_table_for_experiment(experiment_id)
            
            if not trace_table:
                error_msg = f"Failed to get trace table for experiment {experiment_id}. This experiment may not have tracing enabled or the GetMonitor API call failed."
                _logger.error(error_msg)
                raise MlflowException(error_msg, error_code=INVALID_PARAMETER_VALUE)
            
            # Query to discover assessments and detect their types using pure SQL
            # First get distinct (name, value) pairs, then infer type from those
            query = f"""
            WITH distinct_assessment_values AS (
                SELECT DISTINCT
                    assessment.name as assessment_name,
                    assessment.feedback.value as feedback_value,
                    assessment.source.source_type as source_type
                FROM {trace_table}
                LATERAL VIEW explode(assessments) AS assessment
                WHERE state = 'OK'
                AND size(assessments) > 0
                AND assessment.feedback.value IS NOT NULL
                AND assessment.feedback.value != 'null'
            ),
            assessment_stats AS (
                SELECT 
                    assessment_name,
                    source_type,
                    COUNT(DISTINCT feedback_value) as unique_value_count,
                    -- Check if all distinct values match pass/fail pattern
                    BOOL_AND(lower(feedback_value) IN ('"yes"', '"no"')) as is_pass_fail,
                    -- Check if all distinct values match boolean pattern  
                    BOOL_AND(lower(feedback_value) IN ('true', 'false', '"true"', '"false"')) as is_boolean,
                    -- Check if all distinct values are numeric
                    BOOL_AND(REGEXP_EXTRACT(feedback_value, '^"?(-?[0-9]+\\\\.?[0-9]*)"?$', 1) IS NOT NULL) as is_numeric
                FROM distinct_assessment_values
                GROUP BY assessment_name, source_type
            ),
            assessment_counts AS (
                SELECT 
                    assessment.name as assessment_name,
                    assessment.source.source_type as source_type,
                    COUNT(*) as trace_count
                FROM {trace_table}
                LATERAL VIEW explode(assessments) AS assessment
                WHERE state = 'OK'
                AND size(assessments) > 0
                GROUP BY assessment.name, assessment.source.source_type
            )
            SELECT 
                s.assessment_name,
                s.source_type,
                c.trace_count,
                s.unique_value_count,
                -- Determine type based on the distinct values
                CASE 
                    WHEN s.is_pass_fail THEN 'pass-fail'
                    WHEN s.is_boolean THEN 'boolean'
                    WHEN s.is_numeric THEN 'numeric'
                    ELSE 'string'
                END as assessment_type
            FROM assessment_stats s
            JOIN assessment_counts c 
                ON s.assessment_name = c.assessment_name 
                AND s.source_type = c.source_type
            ORDER BY c.trace_count DESC
            """
            
            # Execute query using parent class method
            spark = self._get_or_create_spark_session()
            result = spark.sql(query).collect()
            
            assessments = []
            for row in result:
                assessment_name = row['assessment_name'] or 'unknown'
                source_type = row['source_type'] or 'UNKNOWN'
                assessment_type = row['assessment_type'] or 'string'
                
                # Debug logging
                _logger.info(f"Assessment {assessment_name}: type={assessment_type}, count={row['trace_count']}")
                
                assessments.append({
                    'name': assessment_name,
                    'data_type': assessment_type,
                    'source': source_type.lower() if source_type else 'unknown',
                    'count': row['trace_count']
                })
            
            return assessments
        except Exception as e:
            _logger.error(f"Error getting assessments: {e}")
            return []