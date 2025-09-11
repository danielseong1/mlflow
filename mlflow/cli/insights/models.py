"""
Pydantic models for MLflow Insights - Analysis, Hypothesis, and Issue tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """Status of an analysis."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class HypothesisStatus(str, Enum):
    """Status of a hypothesis."""
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class IssueSeverity(str, Enum):
    """Severity level of an issue."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IssueStatus(str, Enum):
    """Status of an issue."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class Analysis(BaseModel):
    """
    Analysis model representing a high-level investigation.
    Stored as analysis.yaml in the insights/ artifact directory.
    """
    name: str = Field(description="Human-readable name for the analysis")
    description: str = Field(description="Agent description and user guidance - what is this analysis trying to achieve")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    status: AnalysisStatus = Field(default=AnalysisStatus.ACTIVE, description="Current status of the analysis")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class Hypothesis(BaseModel):
    """
    Hypothesis model representing a theory being tested.
    Stored as hypothesis_<id>.yaml in the insights/ artifact directory.
    """
    hypothesis_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the hypothesis")
    statement: str = Field(description="String describing the hypothesis being tested")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    status: HypothesisStatus = Field(default=HypothesisStatus.TESTING, description="Current status of the hypothesis")
    trace_ids: List[str] = Field(default_factory=list, description="List of associated trace IDs")
    evidence: List[str] = Field(default_factory=list, description="List of evidence/observations supporting or refuting the hypothesis")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Relevant metrics for the hypothesis")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")
    
    def add_trace(self, trace_id: str) -> None:
        """Add a trace ID to the hypothesis."""
        if trace_id not in self.trace_ids:
            self.trace_ids.append(trace_id)
            self.update_timestamp()
    
    def add_evidence(self, evidence: str) -> None:
        """Add evidence to the hypothesis."""
        self.evidence.append(evidence)
        self.update_timestamp()
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class Issue(BaseModel):
    """
    Issue model representing a validated problem.
    Stored as issue_<id>.yaml in the insights/ artifact directory.
    """
    issue_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the issue")
    hypothesis_id: Optional[str] = Field(None, description="Source hypothesis ID if validated from a hypothesis")
    title: str = Field(description="Issue title")
    description: str = Field(description="Detailed description of the issue")
    severity: IssueSeverity = Field(description="Severity level of the issue")
    status: IssueStatus = Field(default=IssueStatus.OPEN, description="Current status of the issue")
    trace_ids: List[str] = Field(default_factory=list, description="List of trace IDs that validate this issue")
    assessments: List[str] = Field(default_factory=list, description="List of assessment names/IDs related to this issue")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    resolution: Optional[str] = Field(None, description="Resolution description if issue is resolved")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")
    
    def add_trace(self, trace_id: str) -> None:
        """Add a trace ID to the issue."""
        if trace_id not in self.trace_ids:
            self.trace_ids.append(trace_id)
            self.update_timestamp()
    
    def add_assessment(self, assessment: str) -> None:
        """Add an assessment to the issue."""
        if assessment not in self.assessments:
            self.assessments.append(assessment)
            self.update_timestamp()
    
    def resolve(self, resolution: str) -> None:
        """Mark the issue as resolved with a resolution description."""
        self.status = IssueStatus.RESOLVED
        self.resolution = resolution
        self.update_timestamp()
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


# Summary models for list operations
class HypothesisSummary(BaseModel):
    """Summary view of a hypothesis for list operations."""
    hypothesis_id: str
    statement: str
    status: HypothesisStatus
    trace_count: int
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_hypothesis(cls, hypothesis: Hypothesis) -> "HypothesisSummary":
        """Create a summary from a full hypothesis."""
        return cls(
            hypothesis_id=hypothesis.hypothesis_id,
            statement=hypothesis.statement,
            status=hypothesis.status,
            trace_count=len(hypothesis.trace_ids),
            created_at=hypothesis.created_at,
            updated_at=hypothesis.updated_at
        )


class IssueSummary(BaseModel):
    """Summary view of an issue for list operations."""
    issue_id: str
    title: str
    severity: IssueSeverity
    status: IssueStatus
    trace_count: int
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_issue(cls, issue: Issue) -> "IssueSummary":
        """Create a summary from a full issue."""
        return cls(
            issue_id=issue.issue_id,
            title=issue.title,
            severity=issue.severity,
            status=issue.status,
            trace_count=len(issue.trace_ids),
            created_at=issue.created_at,
            updated_at=issue.updated_at
        )