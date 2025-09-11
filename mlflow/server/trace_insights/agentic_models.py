"""MLflow Trace Insights - Agentic API Request/Response Models

This module defines request and response models for the agentic insights REST API.
These models wrap the existing Pydantic models from mlflow.insights.models.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from mlflow.insights.models import (
    Analysis,
    AnalysisSummary,
    Hypothesis,
    HypothesisSummary,
    Issue,
    IssueSummary,
)
from mlflow.entities import Trace


# ============================================================================
# Analyses Endpoints
# ============================================================================

class ListAnalysesRequest(BaseModel):
    """Request for listing analyses in an experiment."""
    experiment_id: str = Field(description="Experiment ID to list analyses for")


class ListAnalysesResponse(BaseModel):
    """Response containing list of analyses."""
    analyses: List[AnalysisSummary] = Field(description="List of analysis summaries")


class GetAnalysisRequest(BaseModel):
    """Request for getting a specific analysis."""
    insights_run_id: str = Field(description="Run ID of the analysis")


class GetAnalysisResponse(BaseModel):
    """Response containing analysis details."""
    analysis: Optional[Analysis] = Field(description="Analysis details, None if not found")


# ============================================================================
# Hypotheses Endpoints
# ============================================================================

class ListHypothesesRequest(BaseModel):
    """Request for listing hypotheses in an analysis run."""
    insights_run_id: str = Field(description="Run ID of the analysis")


class ListHypothesesResponse(BaseModel):
    """Response containing list of hypotheses."""
    hypotheses: List[HypothesisSummary] = Field(description="List of hypothesis summaries")


class GetHypothesisRequest(BaseModel):
    """Request for getting a specific hypothesis."""
    insights_run_id: str = Field(description="Run ID of the analysis")
    hypothesis_id: str = Field(description="Hypothesis ID")


class GetHypothesisResponse(BaseModel):
    """Response containing hypothesis details."""
    hypothesis: Optional[Hypothesis] = Field(description="Hypothesis details, None if not found")


class PreviewHypothesesRequest(BaseModel):
    """Request for previewing traces associated with hypotheses."""
    insights_run_id: str = Field(description="Run ID of the analysis")
    max_traces: int = Field(default=100, description="Maximum number of traces to return")


class PreviewHypothesesResponse(BaseModel):
    """Response containing traces for hypotheses."""
    traces: List[dict] = Field(description="List of trace data")
    total_count: int = Field(description="Total number of traces across all hypotheses")
    returned_count: int = Field(description="Number of traces returned")


# ============================================================================
# Issues Endpoints
# ============================================================================

class ListIssuesRequest(BaseModel):
    """Request for listing issues in an experiment."""
    experiment_id: str = Field(description="Experiment ID to list issues for")


class ListIssuesResponse(BaseModel):
    """Response containing list of issues sorted by trace count."""
    issues: List[IssueSummary] = Field(description="List of issue summaries sorted by trace count")


class GetIssueRequest(BaseModel):
    """Request for getting a specific issue."""
    issue_id: str = Field(description="Issue ID")


class GetIssueResponse(BaseModel):
    """Response containing issue details."""
    issue: Optional[Issue] = Field(description="Issue details, None if not found")


class PreviewIssuesRequest(BaseModel):
    """Request for previewing traces associated with issues."""
    experiment_id: str = Field(description="Experiment ID")
    max_traces: int = Field(default=100, description="Maximum number of traces to return")


class PreviewIssuesResponse(BaseModel):
    """Response containing traces for issues."""
    traces: List[dict] = Field(description="List of trace data")
    total_count: int = Field(description="Total number of traces across all issues")
    returned_count: int = Field(description="Number of traces returned")