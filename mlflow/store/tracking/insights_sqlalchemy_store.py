"""
SQLAlchemy implementation of the insights store.

This module provides insights analytics using SQLAlchemy queries
for better performance and flexibility compared to REST API calls.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.orm import Session

from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
from mlflow.store.tracking.insights_abstract_store import InsightsAbstractStore
from mlflow.store.tracking.dbmodels.models import (
    SqlTraceInfo, 
    SqlTraceTag,
    SqlAssessments,
    SqlSpan
)
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE


class InsightsSqlAlchemyStore(InsightsAbstractStore, SqlAlchemyStore):
    """SQLAlchemy implementation of the insights store.
    
    This class extends both InsightsAbstractStore and SqlAlchemyStore to provide 
    insights analytics using direct SQL queries against the MLflow database.
    Since InsightsAbstractStore now extends AbstractStore, we put it first
    in the inheritance order to ensure proper method resolution order (MRO).
    """
    
    def __init__(self, db_uri, default_artifact_root):
        """Initialize the SQLAlchemy insights store.
        
        Args:
            db_uri: The database URI (e.g., 'sqlite:///mlflow.db')
            default_artifact_root: Default location for artifacts
        """
        # Call parent SqlAlchemyStore __init__
        super().__init__(db_uri, default_artifact_root)
        self._experiment_ids = None
    
    def _get_experiment_ids(self) -> List[str]:
        """Get experiment IDs from environment or configuration.
        
        Returns:
            List of experiment IDs to analyze
        """
        if self._experiment_ids is None:
            # Try to get from environment variable
            exp_ids = os.environ.get('MLFLOW_EXPERIMENT_IDS', '')
            if exp_ids:
                self._experiment_ids = [e.strip() for e in exp_ids.split(',')]
            else:
                # Default to experiment 0 for now
                self._experiment_ids = ['0']
        return self._experiment_ids
    
    # Traffic & Cost Methods
    
    def get_traffic_volume(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get trace volume statistics using SQLAlchemy queries."""
        experiment_ids = self._get_experiment_ids()
        
        with self.ManagedSessionMaker() as session:
            # Build base query
            query = session.query(SqlTraceInfo)
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters
            if start_time:
                query = query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                query = query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            # Get summary statistics
            summary_query = query.with_entities(
                func.count().label('count'),
                func.sum(case((SqlTraceInfo.status == 'OK', 1), else_=0)).label('ok_count'),
                func.sum(case((SqlTraceInfo.status == 'ERROR', 1), else_=0)).label('error_count')
            ).first()
            
            # Build time bucket expression based on database dialect
            dialect = self._get_dialect()
            if dialect == 'sqlite':
                # SQLite time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'day':
                    bucket_expr = func.strftime('%Y-%m-%d', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'week':
                    bucket_expr = func.strftime('%Y-%W', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                else:
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
            else:
                # PostgreSQL/MySQL time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'day':
                    bucket_expr = func.date_trunc('day', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'week':
                    bucket_expr = func.date_trunc('week', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                else:
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
            
            # Get time series data
            time_series_query = query.with_entities(
                bucket_expr.label('time_bucket'),
                func.count().label('count'),
                func.sum(case((SqlTraceInfo.status == 'OK', 1), else_=0)).label('ok_count'),
                func.sum(case((SqlTraceInfo.status == 'ERROR', 1), else_=0)).label('error_count')
            ).group_by('time_bucket').order_by('time_bucket').all()
            
            # Convert time bucket strings to milliseconds
            time_series = []
            if time_series_query:
                for row in time_series_query:
                    # Parse the time bucket based on format
                    if dialect == 'sqlite':
                        from datetime import datetime
                        if time_bucket == 'week':
                            # For week format 'YYYY-WW', convert to first day of that week
                            year, week = row.time_bucket.split('-')
                            dt = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
                            timestamp_ms = int(dt.timestamp() * 1000)
                        elif time_bucket == 'day':
                            # For day format 'YYYY-MM-DD'
                            dt = datetime.strptime(row.time_bucket, '%Y-%m-%d')
                            timestamp_ms = int(dt.timestamp() * 1000)
                        else:
                            # For hour format 'YYYY-MM-DD HH:00:00'
                            dt = datetime.strptime(row.time_bucket, '%Y-%m-%d %H:%M:%S')
                            timestamp_ms = int(dt.timestamp() * 1000)
                    else:
                        # For PostgreSQL/MySQL, the result is already a datetime
                        timestamp_ms = int(row.time_bucket.timestamp() * 1000)
                    
                    time_series.append({
                        'time_bucket': timestamp_ms,
                        'count': row.count or 0,
                        'ok_count': row.ok_count or 0,
                        'error_count': row.error_count or 0
                    })
            
            # Format response
            return {
                'summary': {
                    'count': summary_query.count or 0 if summary_query else 0,
                    'ok_count': summary_query.ok_count or 0 if summary_query else 0,
                    'error_count': summary_query.error_count or 0 if summary_query else 0
                },
                'time_series': time_series
            }
    
    def get_traffic_latency(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get latency percentile statistics using SQLAlchemy queries."""
        experiment_ids = self._get_experiment_ids()
        
        with self.ManagedSessionMaker() as session:
            # Build base query for successful traces
            query = session.query(SqlTraceInfo).filter(
                SqlTraceInfo.status == 'OK',
                SqlTraceInfo.execution_time_ms.isnot(None)
            )
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters
            if start_time:
                query = query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                query = query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            # Get all execution times for percentile calculation
            execution_times = [row.execution_time_ms for row in query.all()]
            
            if execution_times:
                # Calculate percentiles
                sorted_times = sorted(execution_times)
                count = len(sorted_times)
                p50_idx = min(int(count * 0.5), count - 1)
                p90_idx = min(int(count * 0.9), count - 1)
                p99_idx = min(int(count * 0.99), count - 1)
                p50 = sorted_times[p50_idx]
                p90 = sorted_times[p90_idx]
                p99 = sorted_times[p99_idx]
                avg_latency = sum(sorted_times) / count
                min_latency = sorted_times[0]
                max_latency = sorted_times[-1]
            else:
                p50 = p90 = p99 = avg_latency = min_latency = max_latency = None
                count = 0
            
            # Get time series data with percentiles per bucket
            dialect = self._get_dialect()
            if dialect == 'sqlite':
                # SQLite time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'day':
                    bucket_expr = func.strftime('%Y-%m-%d', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'week':
                    bucket_expr = func.strftime('%Y-%W', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                else:
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
            else:
                # PostgreSQL/MySQL time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'day':
                    bucket_expr = func.date_trunc('day', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'week':
                    bucket_expr = func.date_trunc('week', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                else:
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
            
            # Get time series with grouped execution times
            time_series_query = query.with_entities(
                bucket_expr.label('time_bucket'),
                SqlTraceInfo.execution_time_ms
            ).all()
            
            # Group by time bucket and calculate percentiles
            from collections import defaultdict
            from datetime import datetime
            
            time_buckets = defaultdict(list)
            for row in time_series_query:
                if dialect == 'sqlite':
                    # Parse the time bucket string
                    if time_bucket == 'week':
                        year, week = row.time_bucket.split('-')
                        dt = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
                        timestamp_ms = int(dt.timestamp() * 1000)
                    elif time_bucket == 'day':
                        dt = datetime.strptime(row.time_bucket, '%Y-%m-%d')
                        timestamp_ms = int(dt.timestamp() * 1000)
                    else:
                        dt = datetime.strptime(row.time_bucket, '%Y-%m-%d %H:%M:%S')
                        timestamp_ms = int(dt.timestamp() * 1000)
                else:
                    timestamp_ms = int(row.time_bucket.timestamp() * 1000)
                
                time_buckets[timestamp_ms].append(row.execution_time_ms)
            
            # Calculate percentiles for each bucket
            time_series = []
            for ts, times in sorted(time_buckets.items()):
                sorted_bucket_times = sorted(times)
                bucket_count = len(sorted_bucket_times)
                if bucket_count > 0:
                    p50_idx = min(int(bucket_count * 0.5), bucket_count - 1)
                    p90_idx = min(int(bucket_count * 0.9), bucket_count - 1)
                    p99_idx = min(int(bucket_count * 0.99), bucket_count - 1)
                    
                    time_series.append({
                        'time_bucket': ts,
                        'p50_latency': sorted_bucket_times[p50_idx],
                        'p90_latency': sorted_bucket_times[p90_idx],
                        'p99_latency': sorted_bucket_times[p99_idx],
                        'avg_latency': sum(sorted_bucket_times) / bucket_count,
                        'min_latency': sorted_bucket_times[0],
                        'max_latency': sorted_bucket_times[-1],
                        'count': bucket_count
                    })
            
            # Return with correct keys matching API expectations
            return {
                'summary': {
                    'p50_latency': p50,
                    'p90_latency': p90,
                    'p99_latency': p99,
                    'avg_latency': avg_latency,
                    'min_latency': min_latency,
                    'max_latency': max_latency
                },
                'time_series': time_series
            }
    
    def get_traffic_errors(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get error statistics using SQLAlchemy queries."""
        experiment_ids = self._get_experiment_ids()
        
        with self.ManagedSessionMaker() as session:
            # Build base query
            query = session.query(SqlTraceInfo)
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters
            if start_time:
                query = query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                query = query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            # Get error summary
            summary_query = query.with_entities(
                func.count().label('total_count'),
                func.sum(case((SqlTraceInfo.status == 'ERROR', 1), else_=0)).label('error_count')
            ).first()
            
            total_count = summary_query.total_count or 0 if summary_query else 0
            error_count = summary_query.error_count or 0 if summary_query else 0
            error_rate = (error_count / total_count * 100) if total_count > 0 else 0.0
            
            # Build time bucket expression
            dialect = self._get_dialect()
            if dialect == 'sqlite':
                # SQLite time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'day':
                    bucket_expr = func.strftime('%Y-%m-%d', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                elif time_bucket == 'week':
                    bucket_expr = func.strftime('%Y-%W', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
                else:
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlTraceInfo.timestamp_ms / 1000, 'unixepoch'))
            else:
                # PostgreSQL/MySQL time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'day':
                    bucket_expr = func.date_trunc('day', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                elif time_bucket == 'week':
                    bucket_expr = func.date_trunc('week', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
                else:
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlTraceInfo.timestamp_ms / 1000))
            
            # Get time series data
            time_series_query = query.with_entities(
                bucket_expr.label('time_bucket'),
                func.count().label('total_count'),
                func.sum(case((SqlTraceInfo.status == 'ERROR', 1), else_=0)).label('error_count')
            ).group_by('time_bucket').order_by('time_bucket').all()
            
            # Convert time bucket strings to milliseconds
            time_series = []
            if time_series_query:
                from datetime import datetime
                for row in time_series_query:
                    # Parse the time bucket based on format
                    if dialect == 'sqlite':
                        if time_bucket == 'week':
                            # For week format 'YYYY-WW', convert to first day of that week
                            year, week = row.time_bucket.split('-')
                            dt = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
                            timestamp_ms = int(dt.timestamp() * 1000)
                        elif time_bucket == 'day':
                            # For day format 'YYYY-MM-DD'
                            dt = datetime.strptime(row.time_bucket, '%Y-%m-%d')
                            timestamp_ms = int(dt.timestamp() * 1000)
                        else:
                            # For hour format 'YYYY-MM-DD HH:00:00'
                            dt = datetime.strptime(row.time_bucket, '%Y-%m-%d %H:%M:%S')
                            timestamp_ms = int(dt.timestamp() * 1000)
                    else:
                        # For PostgreSQL/MySQL, the result is already a datetime
                        timestamp_ms = int(row.time_bucket.timestamp() * 1000)
                    
                    total = row.total_count or 0
                    errors = row.error_count or 0
                    time_series.append({
                        'time_bucket': timestamp_ms,
                        'total_count': total,
                        'error_count': errors,
                        'error_rate': (errors / total * 100) if total > 0 else 0.0
                    })
            
            return {
                'summary': {
                    'total_count': total_count,
                    'error_count': error_count,
                    'error_rate': error_rate
                },
                'time_series': time_series
            }
    
    # Assessment Methods
    
    def discover_assessments(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover assessments using SQLAlchemy queries."""
        experiment_ids = self._get_experiment_ids()
        
        with self.ManagedSessionMaker() as session:
            # Query assessments joined with traces
            query = session.query(
                SqlAssessments.name,
                func.count(func.distinct(SqlAssessments.trace_id)).label('trace_count')
            ).join(
                SqlTraceInfo,
                SqlAssessments.trace_id == SqlTraceInfo.request_id
            )
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters
            if start_time:
                query = query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                query = query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            # Group by assessment name and filter by min_count
            results = query.group_by(SqlAssessments.name).having(
                func.count(func.distinct(SqlAssessments.trace_id)) >= min_count
            ).order_by(func.count(func.distinct(SqlAssessments.trace_id)).desc()).all()
            
            return [
                {
                    'assessment_name': row.name,
                    'trace_count': row.trace_count
                }
                for row in results
            ]
    
    def get_assessment_metrics(
        self,
        assessment_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get assessment metrics - TODO: Implement detailed metrics."""
        return {'summary': {}, 'time_series': []}
    
    # Tool Methods
    
    def discover_tools(
        self,
        experiment_ids: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover tools used in traces using SQLAlchemy queries."""
        
        with self.ManagedSessionMaker() as session:
            # Query spans for tool information
            query = session.query(
                SqlSpan.name.label('tool_name'),
                func.count(func.distinct(SqlSpan.trace_id)).label('trace_count')
            ).join(
                SqlTraceInfo,
                SqlSpan.trace_id == SqlTraceInfo.request_id
            ).filter(
                SqlSpan.type == 'TOOL'
            )
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters (convert nanoseconds to milliseconds for spans)
            if start_time:
                query = query.filter(SqlSpan.start_time_unix_nano >= start_time * 1000000)
            if end_time:
                query = query.filter(SqlSpan.start_time_unix_nano <= end_time * 1000000)
            
            # Group by tool name and filter by min_count
            results = query.group_by(SqlSpan.name).having(
                func.count(func.distinct(SqlSpan.trace_id)) >= min_count
            ).order_by(func.count(func.distinct(SqlSpan.trace_id)).desc()).all()
            
            # Calculate total traces for percentage
            total_traces_query = session.query(
                func.count(func.distinct(SqlTraceInfo.request_id))
            ).filter(SqlTraceInfo.experiment_id.in_(
                [int(eid) for eid in experiment_ids]
            ))
            
            if start_time:
                total_traces_query = total_traces_query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                total_traces_query = total_traces_query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            total_traces = total_traces_query.scalar() or 1
            
            # Get detailed metrics for each tool
            tool_details = []
            for row in results:
                # Query spans for this specific tool to get metrics
                tool_spans = session.query(SqlSpan).join(
                    SqlTraceInfo,
                    SqlSpan.trace_id == SqlTraceInfo.request_id
                ).filter(
                    SqlSpan.type == 'TOOL',
                    SqlSpan.name == row.tool_name
                )
                
                if experiment_ids:
                    tool_spans = tool_spans.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
                
                if start_time:
                    tool_spans = tool_spans.filter(SqlSpan.start_time_unix_nano >= start_time * 1000000)
                if end_time:
                    tool_spans = tool_spans.filter(SqlSpan.start_time_unix_nano <= end_time * 1000000)
                
                spans_list = tool_spans.all()
                
                # Calculate metrics
                total_calls = len(spans_list)
                error_count = sum(1 for s in spans_list if s.status == 'ERROR')
                success_count = total_calls - error_count
                error_rate = (error_count / total_calls * 100) if total_calls > 0 else 0.0
                
                # Calculate latencies
                latencies = []
                for span in spans_list:
                    if span.end_time_unix_nano and span.start_time_unix_nano:
                        latency_ms = (span.end_time_unix_nano - span.start_time_unix_nano) / 1000000
                        latencies.append(latency_ms)
                
                if latencies:
                    sorted_latencies = sorted(latencies)
                    count = len(sorted_latencies)
                    p50_idx = min(int(count * 0.5), count - 1)
                    p90_idx = min(int(count * 0.9), count - 1)
                    p99_idx = min(int(count * 0.99), count - 1)
                    p50 = sorted_latencies[p50_idx]
                    p90 = sorted_latencies[p90_idx]
                    p99 = sorted_latencies[p99_idx]
                    avg_latency = sum(sorted_latencies) / count
                else:
                    p50 = p90 = p99 = avg_latency = 0.0
                
                # Get first and last seen timestamps
                first_span = min((s.start_time_unix_nano for s in spans_list), default=0)
                last_span = max((s.start_time_unix_nano for s in spans_list), default=0)
                
                tool_details.append({
                    'tool_name': row.tool_name,
                    'total_calls': total_calls,
                    'trace_count': row.trace_count,  # Keep for backward compatibility
                    'success_count': success_count,
                    'error_count': error_count,
                    'error_rate': error_rate,
                    'avg_latency_ms': avg_latency,
                    'p50_latency_ms': p50,
                    'p90_latency_ms': p90,
                    'p99_latency_ms': p99,
                    'first_seen': str(first_span // 1000000) if first_span else '',  # Convert to ms timestamp string
                    'last_seen': str(last_span // 1000000) if last_span else '',
                    'percentage': (row.trace_count / total_traces) * 100 if total_traces > 0 else 0
                })
            
            return tool_details
    
    def get_tool_metrics(
        self,
        experiment_ids: List[str],
        tool_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get metrics for a specific tool including usage count and latency."""
        with self.ManagedSessionMaker() as session:
            # Query spans for tool metrics
            query = session.query(SqlSpan).join(
                SqlTraceInfo,
                SqlSpan.trace_id == SqlTraceInfo.request_id
            ).filter(
                SqlSpan.type == 'TOOL',
                SqlSpan.name == tool_name
            )
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters (convert nanoseconds to milliseconds for spans)
            if start_time:
                query = query.filter(SqlSpan.start_time_unix_nano >= start_time * 1000000)
            if end_time:
                query = query.filter(SqlSpan.start_time_unix_nano <= end_time * 1000000)
            
            # Get all tool spans for metrics calculation
            tool_spans = query.all()
            
            if not tool_spans:
                return {
                    'summary': {
                        'usage_count': 0,
                        'trace_count': 0,
                        'avg_latency': None,
                        'p50_latency': None,
                        'p90_latency': None,
                        'p99_latency': None,
                        'error_rate': 0.0
                    },
                    'time_series': []
                }
            
            # Calculate summary metrics
            usage_count = len(tool_spans)
            trace_count = len(set(span.trace_id for span in tool_spans))
            
            # Calculate latencies (convert nanoseconds to milliseconds)
            latencies = []
            error_count = 0
            for span in tool_spans:
                if span.status == 'ERROR':
                    error_count += 1
                if span.end_time_unix_nano and span.start_time_unix_nano:
                    latency_ms = (span.end_time_unix_nano - span.start_time_unix_nano) / 1000000
                    latencies.append(latency_ms)
            
            # Calculate percentiles
            if latencies:
                sorted_latencies = sorted(latencies)
                count = len(sorted_latencies)
                p50_idx = min(int(count * 0.5), count - 1)
                p90_idx = min(int(count * 0.9), count - 1)
                p99_idx = min(int(count * 0.99), count - 1)
                p50 = sorted_latencies[p50_idx]
                p90 = sorted_latencies[p90_idx]
                p99 = sorted_latencies[p99_idx]
                avg_latency = sum(sorted_latencies) / count
            else:
                p50 = p90 = p99 = avg_latency = None
            
            error_rate = (error_count / usage_count * 100) if usage_count > 0 else 0.0
            
            # Build time bucket expression
            dialect = self._get_dialect()
            if dialect == 'sqlite':
                # SQLite time bucketing (convert nanoseconds to seconds for datetime)
                if time_bucket == 'hour':
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlSpan.start_time_unix_nano / 1000000000, 'unixepoch'))
                elif time_bucket == 'day':
                    bucket_expr = func.strftime('%Y-%m-%d', 
                                               func.datetime(SqlSpan.start_time_unix_nano / 1000000000, 'unixepoch'))
                elif time_bucket == 'week':
                    bucket_expr = func.strftime('%Y-%W', 
                                               func.datetime(SqlSpan.start_time_unix_nano / 1000000000, 'unixepoch'))
                else:
                    bucket_expr = func.strftime('%Y-%m-%d %H:00:00', 
                                               func.datetime(SqlSpan.start_time_unix_nano / 1000000000, 'unixepoch'))
            else:
                # PostgreSQL/MySQL time bucketing
                if time_bucket == 'hour':
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlSpan.start_time_unix_nano / 1000000000))
                elif time_bucket == 'day':
                    bucket_expr = func.date_trunc('day', 
                                                 func.to_timestamp(SqlSpan.start_time_unix_nano / 1000000000))
                elif time_bucket == 'week':
                    bucket_expr = func.date_trunc('week', 
                                                 func.to_timestamp(SqlSpan.start_time_unix_nano / 1000000000))
                else:
                    bucket_expr = func.date_trunc('hour', 
                                                 func.to_timestamp(SqlSpan.start_time_unix_nano / 1000000000))
            
            # Create a fresh query for time series data
            time_series_base = session.query(SqlSpan).join(
                SqlTraceInfo,
                SqlSpan.trace_id == SqlTraceInfo.request_id
            ).filter(
                SqlSpan.type == 'TOOL',
                SqlSpan.name == tool_name
            )
            
            # Apply the same filters as the main query
            if experiment_ids:
                time_series_base = time_series_base.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            if start_time:
                time_series_base = time_series_base.filter(SqlSpan.start_time_unix_nano >= start_time * 1000000)
            if end_time:
                time_series_base = time_series_base.filter(SqlSpan.start_time_unix_nano <= end_time * 1000000)
            
            # Get time series data with grouped execution times
            time_series_query = time_series_base.with_entities(
                bucket_expr.label('time_bucket'),
                SqlSpan.start_time_unix_nano,
                SqlSpan.end_time_unix_nano,
                SqlSpan.status
            ).all()
            
            # Group by time bucket and calculate metrics
            from collections import defaultdict
            from datetime import datetime
            
            time_buckets = defaultdict(lambda: {'latencies': [], 'count': 0, 'error_count': 0})
            for row in time_series_query:
                # Parse the time bucket string
                if dialect == 'sqlite':
                    if time_bucket == 'week':
                        year, week = row.time_bucket.split('-')
                        dt = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
                        timestamp_ms = int(dt.timestamp() * 1000)
                    elif time_bucket == 'day':
                        dt = datetime.strptime(row.time_bucket, '%Y-%m-%d')
                        timestamp_ms = int(dt.timestamp() * 1000)
                    else:
                        dt = datetime.strptime(row.time_bucket, '%Y-%m-%d %H:%M:%S')
                        timestamp_ms = int(dt.timestamp() * 1000)
                else:
                    timestamp_ms = int(row.time_bucket.timestamp() * 1000)
                
                time_buckets[timestamp_ms]['count'] += 1
                if row.status == 'ERROR':
                    time_buckets[timestamp_ms]['error_count'] += 1
                
                if row.end_time_unix_nano and row.start_time_unix_nano:
                    latency_ms = (row.end_time_unix_nano - row.start_time_unix_nano) / 1000000
                    time_buckets[timestamp_ms]['latencies'].append(latency_ms)
            
            # Calculate percentiles for each bucket
            time_series = []
            for ts, data in sorted(time_buckets.items()):
                bucket_data = {
                    'time_bucket': ts,
                    'usage_count': data['count'],
                    'error_count': data['error_count'],
                    'error_rate': (data['error_count'] / data['count'] * 100) if data['count'] > 0 else 0.0
                }
                
                if data['latencies']:
                    sorted_bucket_latencies = sorted(data['latencies'])
                    bucket_count = len(sorted_bucket_latencies)
                    p50_idx = min(int(bucket_count * 0.5), bucket_count - 1)
                    p90_idx = min(int(bucket_count * 0.9), bucket_count - 1)
                    p99_idx = min(int(bucket_count * 0.99), bucket_count - 1)
                    
                    bucket_data.update({
                        'p50_latency': sorted_bucket_latencies[p50_idx],
                        'p90_latency': sorted_bucket_latencies[p90_idx],
                        'p99_latency': sorted_bucket_latencies[p99_idx],
                        'avg_latency': sum(sorted_bucket_latencies) / bucket_count
                    })
                else:
                    bucket_data.update({
                        'p50_latency': None,
                        'p90_latency': None,
                        'p99_latency': None,
                        'avg_latency': None
                    })
                
                time_series.append(bucket_data)
            
            return {
                'summary': {
                    'usage_count': usage_count,
                    'trace_count': trace_count,
                    'avg_latency': avg_latency,
                    'p50_latency': p50,
                    'p90_latency': p90,
                    'p99_latency': p99,
                    'error_rate': error_rate
                },
                'time_series': time_series
            }
    
    # Tag Methods
    
    def discover_tags(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_count: int = 1
    ) -> List[Dict[str, Any]]:
        """Discover tags using SQLAlchemy queries."""
        experiment_ids = self._get_experiment_ids()
        
        with self.ManagedSessionMaker() as session:
            # Query distinct tag keys
            query = session.query(
                SqlTraceTag.key.label('tag_key'),
                func.count(func.distinct(SqlTraceTag.value)).label('unique_values'),
                func.count(func.distinct(SqlTraceTag.trace_id)).label('trace_count')
            ).join(
                SqlTraceInfo,
                SqlTraceTag.trace_id == SqlTraceInfo.request_id
            )
            
            # Filter by experiment IDs (stored as TEXT in database)
            if experiment_ids:
                query = query.filter(SqlTraceInfo.experiment_id.in_(experiment_ids))
            
            # Apply time filters
            if start_time:
                query = query.filter(SqlTraceInfo.timestamp_ms >= start_time)
            if end_time:
                query = query.filter(SqlTraceInfo.timestamp_ms <= end_time)
            
            # Group by tag key and filter by min_count
            results = query.group_by(SqlTraceTag.key).having(
                func.count(func.distinct(SqlTraceTag.trace_id)) >= min_count
            ).order_by(func.count(func.distinct(SqlTraceTag.trace_id)).desc()).all()
            
            return [
                {
                    'tag_key': row.tag_key,
                    'unique_values': row.unique_values,
                    'trace_count': row.trace_count
                }
                for row in results
            ]
    
    def get_tag_metrics(
        self,
        tag_key: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_bucket: str = 'hour',
        timezone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get tag metrics - TODO: Implement detailed metrics."""
        return {'tag_values': [], 'time_series': []}
    
    # Dimension & Correlation Methods
    
    def discover_dimensions(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        filter_string: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Discover dimensions - TODO: Implement using SQLAlchemy."""
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
        """Calculate NPMI - TODO: Implement using SQLAlchemy."""
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
        """Get correlations - TODO: Implement using SQLAlchemy."""
        return []
    
    def get_assessments(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Get assessments for an experiment."""
        # TODO: Implement assessment discovery using SQLAlchemy
        return []