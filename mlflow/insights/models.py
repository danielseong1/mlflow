"""
Data models for MLflow Insights - Analysis, Hypothesis, and Issue tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


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
    REJECTED = "REJECTED"


class Analysis(BaseModel):
    """
    Analysis model representing a high-level investigation.
    Stored as analysis.yaml in the insights/ artifact directory.
    """

    name: str = Field(description="Human-readable name for the analysis")
    description: str = Field(description="Detailed description of investigation goals and guidance")
    status: AnalysisStatus = Field(
        default=AnalysisStatus.ACTIVE, description="Current status of the analysis"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible dictionary for custom fields"
    )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class EvidenceEntry(BaseModel):
    """Evidence entry for hypotheses and issues."""

    trace_id: str = Field(description="The specific trace ID")
    rationale: str = Field(
        description="Explanation of why this trace supports/refutes the hypothesis or issue"
    )
    supports: Optional[bool] = Field(
        default=None,
        description="Boolean indicating if evidence supports (true) or refutes (false). None for issues.",
    )


class Hypothesis(BaseModel):
    """
    Hypothesis model representing a testable statement or theory.
    Stored as hypothesis_<id>.yaml in the insights/ artifact directory.
    """

    hypothesis_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="UUID unique within the run",
    )
    statement: str = Field(description="The hypothesis being tested")
    testing_plan: str = Field(
        description="Detailed plan for how to test this hypothesis including validation/refutation criteria"
    )
    status: HypothesisStatus = Field(default=HypothesisStatus.TESTING, description="Current state")
    evidence: list[EvidenceEntry] = Field(
        default_factory=list,
        description="List of evidence entries with trace_id, rationale, and supports",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Dictionary of relevant metrics"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last modification timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible dictionary for custom fields"
    )

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, v):
        """Convert dict evidence entries to EvidenceEntry objects."""
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(EvidenceEntry(**item))
                elif isinstance(item, EvidenceEntry):
                    result.append(item)
                else:
                    raise ValueError(f"Invalid evidence entry type: {type(item)}")
            return result
        return v

    def add_evidence(self, trace_id: str, rationale: str, supports: bool) -> None:
        """Add an evidence entry to the hypothesis."""
        entry = EvidenceEntry(trace_id=trace_id, rationale=rationale, supports=supports)
        self.evidence.append(entry)
        self.update_timestamp()

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()

    @property
    def trace_count(self) -> int:
        """Get the number of traces associated with this hypothesis."""
        # Count unique trace IDs from evidence
        unique_traces = set(e.trace_id for e in self.evidence)
        return len(unique_traces)

    @property
    def evidence_count(self) -> int:
        """Get the number of evidence entries."""
        return len(self.evidence)

    @property
    def supports_count(self) -> int:
        """Get the number of supporting evidence entries."""
        return sum(1 for e in self.evidence if e.supports is True)

    @property
    def refutes_count(self) -> int:
        """Get the number of refuting evidence entries."""
        return sum(1 for e in self.evidence if e.supports is False)


class Issue(BaseModel):
    """
    Issue model representing a validated problem discovered through investigation.
    Stored as issue_<id>.yaml in the PARENT (container) run artifacts.
    """

    issue_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="UUID unique within the container",
    )
    source_run_id: str = Field(description="The analysis run that created this issue")
    hypothesis_id: Optional[str] = Field(
        default=None, description="Optional source hypothesis if validated from one"
    )
    title: str = Field(description="Brief issue title")
    description: str = Field(description="Detailed description of the problem")
    severity: IssueSeverity = Field(description="Issue severity")
    status: IssueStatus = Field(default=IssueStatus.OPEN, description="Current state")
    evidence: list[EvidenceEntry] = Field(
        default_factory=list,
        description="List of evidence entries with trace_id and rationale",
    )
    assessments: list[str] = Field(
        default_factory=list,
        description="List of assessment names/IDs related to the issue",
    )
    resolution: Optional[str] = Field(
        default=None, description="Resolution description when resolved"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last modification timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible dictionary for custom fields"
    )

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, v):
        """Convert dict evidence entries to EvidenceEntry objects."""
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    # For issues, supports field should be None
                    entry_dict = item.copy()
                    entry_dict["supports"] = None
                    result.append(EvidenceEntry(**entry_dict))
                elif isinstance(item, EvidenceEntry):
                    # Ensure supports is None for issues
                    item.supports = None
                    result.append(item)
                else:
                    raise ValueError(f"Invalid evidence entry type: {type(item)}")
            return result
        return v

    def add_evidence(self, trace_id: str, rationale: str) -> None:
        """Add an evidence entry to the issue."""
        entry = EvidenceEntry(trace_id=trace_id, rationale=rationale, supports=None)
        self.evidence.append(entry)
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

    @property
    def trace_count(self) -> int:
        """Get the number of traces associated with this issue."""
        # Count unique trace IDs from evidence
        unique_traces = set(e.trace_id for e in self.evidence)
        return len(unique_traces)


# Summary models for list operations
class AnalysisSummary(BaseModel):
    """Summary view of an analysis for list operations."""

    run_id: str
    name: str
    description: str
    status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
    hypothesis_count: Optional[int] = 0
    validated_count: Optional[int] = 0
    hypotheses: Optional[list["HypothesisSummary"]] = Field(
        default_factory=list,
        description="List of hypothesis summaries for this analysis"
    )

    @classmethod
    def from_analysis(
        cls, 
        run_id: str, 
        analysis: Analysis, 
        hypothesis_count: int = 0,
        validated_count: int = 0,
        hypotheses: Optional[list["HypothesisSummary"]] = None
    ) -> "AnalysisSummary":
        """Create a summary from a full analysis."""
        return cls(
            run_id=run_id,
            name=analysis.name,
            description=analysis.description,
            status=analysis.status,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            hypothesis_count=hypothesis_count,
            validated_count=validated_count,
            hypotheses=hypotheses or [],
        )


class HypothesisSummary(BaseModel):
    """Summary view of a hypothesis for list operations."""

    hypothesis_id: str
    statement: str
    testing_plan: Optional[str] = None  # Include testing plan in summary
    status: HypothesisStatus
    trace_count: int
    evidence_count: int
    supports_count: int
    refutes_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_hypothesis(cls, hypothesis: Hypothesis) -> "HypothesisSummary":
        """Create a summary from a full hypothesis."""
        return cls(
            hypothesis_id=hypothesis.hypothesis_id,
            statement=hypothesis.statement,
            testing_plan=hypothesis.testing_plan,  # Include testing plan
            status=hypothesis.status,
            trace_count=hypothesis.trace_count,
            evidence_count=hypothesis.evidence_count,
            supports_count=hypothesis.supports_count,
            refutes_count=hypothesis.refutes_count,
            created_at=hypothesis.created_at,
            updated_at=hypothesis.updated_at,
        )


class IssueSummary(BaseModel):
    """Summary view of an issue for list operations."""

    issue_id: str
    title: str
    severity: IssueSeverity
    status: IssueStatus
    trace_count: int
    source_run_id: str
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
            trace_count=issue.trace_count,
            source_run_id=issue.source_run_id,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
        )
