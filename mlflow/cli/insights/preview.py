"""
Preview functions for MLflow Insights - Trace analysis and visualization.
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from mlflow import MlflowClient
from mlflow.cli.insights.models import Hypothesis, Issue
from mlflow.cli.insights.utils import get_hypothesis, get_issue
from mlflow.entities import Trace
from mlflow.tracing.client import TracingClient


def calculate_error_rate(traces: List[Trace]) -> float:
    """
    Calculate the error rate from a list of traces.
    
    Args:
        traces: List of Trace objects
    
    Returns:
        Error rate as a percentage
    """
    if not traces:
        return 0.0
    
    error_count = sum(1 for trace in traces if trace.info.state == "ERROR")
    return (error_count / len(traces)) * 100


def calculate_avg_latency(traces: List[Trace]) -> float:
    """
    Calculate average latency from a list of traces.
    
    Args:
        traces: List of Trace objects
    
    Returns:
        Average latency in milliseconds
    """
    if not traces:
        return 0.0
    
    total_latency = sum(trace.info.execution_duration or 0 for trace in traces)
    return total_latency / len(traces)


def format_trace_samples(traces: List[Trace], max_samples: int = 5) -> List[Dict[str, Any]]:
    """
    Format trace samples for display.
    
    Args:
        traces: List of Trace objects
        max_samples: Maximum number of samples to return
    
    Returns:
        List of formatted trace dictionaries
    """
    samples = []
    for trace in traces[:max_samples]:
        samples.append({
            "trace_id": trace.info.trace_id,
            "state": trace.info.state,
            "latency_ms": trace.info.execution_duration,
            "timestamp": trace.info.request_time,
            "request_preview": trace.info.request_preview[:100] if trace.info.request_preview else None,
            "response_preview": trace.info.response_preview[:100] if trace.info.response_preview else None,
        })
    return samples


def find_common_errors(traces: List[Trace]) -> Dict[str, int]:
    """
    Find common error patterns in traces.
    
    Args:
        traces: List of Trace objects
    
    Returns:
        Dictionary of error patterns and their counts
    """
    error_patterns = Counter()
    
    for trace in traces:
        if trace.info.state == "ERROR":
            # Extract error information from spans
            if trace.data and trace.data.spans:
                for span in trace.data.spans:
                    if span.status_code == "ERROR":
                        # Use span name as error pattern
                        error_patterns[span.name] += 1
    
    return dict(error_patterns.most_common(10))


def extract_assessments(traces: List[Trace], assessment_names: List[str]) -> Dict[str, List[Any]]:
    """
    Extract assessment values from traces.
    
    Args:
        traces: List of Trace objects
        assessment_names: List of assessment names to extract
    
    Returns:
        Dictionary mapping assessment names to lists of values
    """
    assessments = {name: [] for name in assessment_names}
    
    for trace in traces:
        if trace.info.assessments:
            for assessment in trace.info.assessments:
                # Check if this assessment is one we're looking for
                if hasattr(assessment, 'feedback') and assessment.feedback:
                    if assessment.feedback.name in assessment_names:
                        assessments[assessment.feedback.name].append(assessment.feedback.value)
                elif hasattr(assessment, 'expectation') and assessment.expectation:
                    if assessment.expectation.name in assessment_names:
                        assessments[assessment.expectation.name].append(assessment.expectation.value)
    
    return assessments


def summarize_assessments(assessments: Dict[str, List[Any]]) -> Dict[str, Any]:
    """
    Summarize assessment values.
    
    Args:
        assessments: Dictionary of assessment names to values
    
    Returns:
        Summary statistics for each assessment
    """
    summary = {}
    
    for name, values in assessments.items():
        if not values:
            summary[name] = {"count": 0}
            continue
        
        # Determine type of values
        if all(isinstance(v, (int, float)) for v in values):
            # Numeric assessment
            summary[name] = {
                "count": len(values),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }
        elif all(isinstance(v, bool) for v in values):
            # Boolean assessment
            true_count = sum(values)
            summary[name] = {
                "count": len(values),
                "true_count": true_count,
                "false_count": len(values) - true_count,
                "true_rate": (true_count / len(values)) * 100,
            }
        else:
            # String/categorical assessment
            value_counts = Counter(values)
            summary[name] = {
                "count": len(values),
                "unique_values": len(value_counts),
                "top_values": dict(value_counts.most_common(5)),
            }
    
    return summary


def calculate_correlations(traces: List[Trace]) -> Dict[str, Any]:
    """
    Calculate correlations between trace attributes.
    
    Args:
        traces: List of Trace objects
    
    Returns:
        Dictionary of correlation insights
    """
    correlations = {}
    
    # Correlate error state with latency
    error_traces = [t for t in traces if t.info.state == "ERROR"]
    ok_traces = [t for t in traces if t.info.state == "OK"]
    
    if error_traces and ok_traces:
        error_avg_latency = calculate_avg_latency(error_traces)
        ok_avg_latency = calculate_avg_latency(ok_traces)
        
        correlations["error_latency_correlation"] = {
            "error_avg_latency_ms": error_avg_latency,
            "ok_avg_latency_ms": ok_avg_latency,
            "difference_ms": error_avg_latency - ok_avg_latency,
        }
    
    # Analyze span types if available
    span_types = Counter()
    for trace in traces:
        if trace.data and trace.data.spans:
            for span in trace.data.spans:
                if span.attributes and "mlflow.spanType" in span.attributes:
                    span_types[span.attributes["mlflow.spanType"]] += 1
    
    if span_types:
        correlations["span_type_distribution"] = dict(span_types)
    
    return correlations


def apply_filter(traces: List[Trace], filter_string: str) -> List[Trace]:
    """
    Apply a filter string to traces.
    
    Args:
        traces: List of Trace objects
        filter_string: Filter expression (simplified for now)
    
    Returns:
        Filtered list of traces
    """
    # Simple implementation - can be enhanced with proper filter parsing
    filtered = []
    
    for trace in traces:
        # Example simple filters
        if "status = 'ERROR'" in filter_string and trace.info.state != "ERROR":
            continue
        if "status = 'OK'" in filter_string and trace.info.state != "OK":
            continue
        # Add more filter conditions as needed
        
        filtered.append(trace)
    
    return filtered


def preview_hypothesis(
    client: MlflowClient,
    tracing_client: TracingClient,
    run_id: str,
    hypothesis_id: str,
    filter_string: Optional[str] = None,
    max_traces: int = 10
) -> Tuple[Hypothesis, Dict[str, Any], List[Trace]]:
    """
    Preview a hypothesis with actual trace data.
    
    Args:
        client: MLflow client instance
        tracing_client: Tracing client instance
        run_id: Run ID
        hypothesis_id: Hypothesis ID
        filter_string: Optional filter string for traces
        max_traces: Maximum number of traces to fetch
    
    Returns:
        Tuple of (hypothesis, statistics, traces)
    """
    # Get hypothesis metadata
    hypothesis = get_hypothesis(client, run_id, hypothesis_id)
    if not hypothesis:
        raise ValueError(f"Hypothesis {hypothesis_id} not found in run {run_id}")
    
    # Fetch associated traces
    traces = []
    for trace_id in hypothesis.trace_ids[:max_traces]:
        try:
            trace = tracing_client.get_trace(trace_id)
            traces.append(trace)
        except Exception:
            # Skip traces that can't be fetched
            continue
    
    # Apply filter if provided
    if filter_string:
        traces = apply_filter(traces, filter_string)
    
    # Compute statistics
    stats = {
        "total_traces": len(hypothesis.trace_ids),
        "fetched_traces": len(traces),
        "error_rate": calculate_error_rate(traces),
        "avg_latency_ms": calculate_avg_latency(traces),
        "trace_samples": format_trace_samples(traces, 5),
        "common_errors": find_common_errors(traces) if any(t.info.state == "ERROR" for t in traces) else {},
    }
    
    return hypothesis, stats, traces


def preview_issue(
    client: MlflowClient,
    tracing_client: TracingClient,
    run_id: str,
    issue_id: str,
    filter_string: Optional[str] = None
) -> Tuple[Issue, Dict[str, Any], List[Trace]]:
    """
    Preview an issue with trace validation data.
    
    Args:
        client: MLflow client instance
        tracing_client: Tracing client instance
        run_id: Run ID
        issue_id: Issue ID
        filter_string: Optional filter string for traces
    
    Returns:
        Tuple of (issue, patterns, traces)
    """
    # Get issue metadata
    issue = get_issue(client, run_id, issue_id)
    if not issue:
        raise ValueError(f"Issue {issue_id} not found in run {run_id}")
    
    # Fetch all associated traces
    traces = []
    for trace_id in issue.trace_ids:
        try:
            trace = tracing_client.get_trace(trace_id)
            traces.append(trace)
        except Exception:
            # Skip traces that can't be fetched
            continue
    
    # Apply filter if provided
    if filter_string:
        traces = apply_filter(traces, filter_string)
    
    # Extract assessments if specified
    assessments = {}
    if issue.assessments:
        assessments = extract_assessments(traces, issue.assessments)
    
    # Analyze patterns
    patterns = {
        "total_traces": len(issue.trace_ids),
        "fetched_traces": len(traces),
        "error_rate": calculate_error_rate(traces),
        "avg_latency_ms": calculate_avg_latency(traces),
        "common_errors": find_common_errors(traces),
        "assessment_summary": summarize_assessments(assessments) if assessments else {},
        "trace_correlation": calculate_correlations(traces),
        "trace_samples": format_trace_samples(traces, 5),
    }
    
    return issue, patterns, traces


def get_traces_for_hypothesis(
    tracing_client: TracingClient,
    hypothesis: Hypothesis,
    max_traces: Optional[int] = None
) -> List[Trace]:
    """
    Get all traces for a hypothesis.
    
    Args:
        tracing_client: Tracing client instance
        hypothesis: Hypothesis object
        max_traces: Optional maximum number of traces to fetch
    
    Returns:
        List of Trace objects
    """
    traces = []
    trace_ids = hypothesis.trace_ids[:max_traces] if max_traces else hypothesis.trace_ids
    
    for trace_id in trace_ids:
        try:
            trace = tracing_client.get_trace(trace_id)
            traces.append(trace)
        except Exception:
            # Skip traces that can't be fetched
            continue
    
    return traces


def get_traces_for_issue(
    tracing_client: TracingClient,
    issue: Issue,
    max_traces: Optional[int] = None
) -> List[Trace]:
    """
    Get all traces for an issue.
    
    Args:
        tracing_client: Tracing client instance
        issue: Issue object
        max_traces: Optional maximum number of traces to fetch
    
    Returns:
        List of Trace objects
    """
    traces = []
    trace_ids = issue.trace_ids[:max_traces] if max_traces else issue.trace_ids
    
    for trace_id in trace_ids:
        try:
            trace = tracing_client.get_trace(trace_id)
            traces.append(trace)
        except Exception:
            # Skip traces that can't be fetched
            continue
    
    return traces