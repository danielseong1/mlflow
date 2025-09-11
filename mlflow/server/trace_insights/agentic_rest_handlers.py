"""MLflow Trace Insights - Agentic REST API Handlers

REST API handlers for agentic insights features (analyses, hypotheses, issues).
These handlers provide a thin wrapper around the InsightsClient SDK.
"""

import logging
from flask import jsonify, request
from mlflow.server.handlers import catch_mlflow_exception, _disable_if_artifacts_only
from mlflow.insights.client import InsightsClient
from mlflow.server.trace_insights.agentic_models import (
    ListAnalysesRequest,
    ListAnalysesResponse,
    GetAnalysisRequest,
    GetAnalysisResponse,
    ListHypothesesRequest,
    ListHypothesesResponse,
    GetHypothesisRequest,
    GetHypothesisResponse,
    PreviewHypothesesRequest,
    PreviewHypothesesResponse,
    ListIssuesRequest,
    ListIssuesResponse,
    GetIssueRequest,
    GetIssueResponse,
    PreviewIssuesRequest,
    PreviewIssuesResponse,
)

# Set up logging
logger = logging.getLogger(__name__)


# ============================================================================
# Analyses Endpoints
# ============================================================================

@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_analyses_list_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/analyses/list`
    Returns list of analyses in an experiment.
    """
    try:
        data = request.get_json() or {}
        req = ListAnalysesRequest(**data)
        
        client = InsightsClient()
        analyses = client.list_analyses(experiment_id=req.experiment_id)
        
        response = ListAnalysesResponse(analyses=analyses)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_analyses_list_handler: {e}")
        return jsonify({"error": str(e)}), 500


@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_analyses_get_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/analyses/get`
    Returns details of a specific analysis.
    """
    try:
        data = request.get_json() or {}
        req = GetAnalysisRequest(**data)
        
        client = InsightsClient()
        analysis = client.get_analysis(insights_run_id=req.insights_run_id)
        
        response = GetAnalysisResponse(analysis=analysis)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_analyses_get_handler: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Hypotheses Endpoints
# ============================================================================

@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_hypotheses_list_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/hypotheses/list`
    Returns list of hypotheses in an analysis run.
    """
    try:
        data = request.get_json() or {}
        req = ListHypothesesRequest(**data)
        
        client = InsightsClient()
        hypotheses = client.list_hypotheses(insights_run_id=req.insights_run_id)
        
        response = ListHypothesesResponse(hypotheses=hypotheses)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_hypotheses_list_handler: {e}")
        return jsonify({"error": str(e)}), 500


@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_hypotheses_get_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/hypotheses/get`
    Returns details of a specific hypothesis.
    """
    try:
        data = request.get_json() or {}
        req = GetHypothesisRequest(**data)
        
        client = InsightsClient()
        hypothesis = client.get_hypothesis(
            insights_run_id=req.insights_run_id,
            hypothesis_id=req.hypothesis_id
        )
        
        response = GetHypothesisResponse(hypothesis=hypothesis)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_hypotheses_get_handler: {e}")
        return jsonify({"error": str(e)}), 500


@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_hypotheses_preview_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/hypotheses/preview`
    Returns traces associated with hypotheses in a run.
    """
    try:
        data = request.get_json() or {}
        req = PreviewHypothesesRequest(**data)
        
        client = InsightsClient()
        traces = client.preview_hypotheses(
            insights_run_id=req.insights_run_id,
            max_traces=req.max_traces
        )
        
        # Convert Trace objects to dictionaries
        trace_dicts = []
        for trace in traces:
            trace_dict = {
                "trace_id": trace.info.request_id,
                "request_id": trace.info.request_id,
                "status": trace.info.status.value if trace.info.status else None,
                "execution_time_ms": trace.info.execution_time_ms,
                "timestamp": trace.info.timestamp_ms,
            }
            trace_dicts.append(trace_dict)
        
        response = PreviewHypothesesResponse(
            traces=trace_dicts,
            total_count=len(traces),
            returned_count=len(trace_dicts)
        )
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_hypotheses_preview_handler: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Issues Endpoints
# ============================================================================

@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_issues_list_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/issues/list`
    Returns list of issues in an experiment sorted by trace count.
    """
    try:
        data = request.get_json() or {}
        req = ListIssuesRequest(**data)
        
        client = InsightsClient()
        issues = client.list_issues(experiment_id=req.experiment_id)
        
        response = ListIssuesResponse(issues=issues)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_issues_list_handler: {e}")
        return jsonify({"error": str(e)}), 500


@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_issues_get_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/issues/get`
    Returns details of a specific issue.
    """
    try:
        data = request.get_json() or {}
        req = GetIssueRequest(**data)
        
        client = InsightsClient()
        issue = client.get_issue(issue_id=req.issue_id)
        
        response = GetIssueResponse(issue=issue)
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_issues_get_handler: {e}")
        return jsonify({"error": str(e)}), 500


@catch_mlflow_exception
@_disable_if_artifacts_only
def agentic_issues_preview_handler():
    """
    Handler for `POST /api/3.0/mlflow/traces/insights/agentic/issues/preview`
    Returns traces associated with issues in an experiment.
    """
    try:
        data = request.get_json() or {}
        req = PreviewIssuesRequest(**data)
        
        client = InsightsClient()
        traces = client.preview_issues(
            experiment_id=req.experiment_id,
            max_traces=req.max_traces
        )
        
        # Convert Trace objects to dictionaries
        trace_dicts = []
        for trace in traces:
            trace_dict = {
                "trace_id": trace.info.request_id,
                "request_id": trace.info.request_id,
                "status": trace.info.status.value if trace.info.status else None,
                "execution_time_ms": trace.info.execution_time_ms,
                "timestamp": trace.info.timestamp_ms,
            }
            trace_dicts.append(trace_dict)
        
        response = PreviewIssuesResponse(
            traces=trace_dicts,
            total_count=len(traces),
            returned_count=len(trace_dicts)
        )
        return jsonify(response.model_dump())
    except Exception as e:
        logger.error(f"Error in agentic_issues_preview_handler: {e}")
        return jsonify({"error": str(e)}), 500