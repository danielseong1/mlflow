"""
Tests for Insights data models.
"""

import json
from datetime import datetime

import pytest
import yaml

from mlflow.insights.models import (
    Analysis,
    AnalysisStatus,
    AnalysisSummary,
    EvidenceEntry,
    Hypothesis,
    HypothesisStatus,
    HypothesisSummary,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueSummary,
)


class TestAnalysisModel:
    """Test Analysis model."""

    def test_analysis_creation(self):
        """Test creating an analysis."""
        analysis = Analysis(
            name="Production Error Analysis",
            description="Investigating production errors",
        )
        
        assert analysis.name == "Production Error Analysis"
        assert analysis.description == "Investigating production errors"
        assert analysis.status == AnalysisStatus.ACTIVE
        assert isinstance(analysis.created_at, datetime)
        assert isinstance(analysis.updated_at, datetime)
        assert analysis.metadata == {}

    def test_analysis_update_timestamp(self):
        """Test updating analysis timestamp."""
        analysis = Analysis(name="Test", description="Test")
        original_time = analysis.updated_at
        
        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)
        
        analysis.update_timestamp()
        assert analysis.updated_at > original_time

    def test_analysis_serialization(self):
        """Test analysis can be serialized to JSON."""
        analysis = Analysis(
            name="Test",
            description="Test description",
            metadata={"custom": "field"},
        )
        
        # Convert to dict with JSON-compatible types
        data = analysis.model_dump(mode="json")
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        assert json_str is not None
        
        # Can be loaded back
        loaded_data = json.loads(json_str)
        assert loaded_data["name"] == "Test"


class TestHypothesisModel:
    """Test Hypothesis model."""

    def test_hypothesis_requires_testing_plan(self):
        """Test that hypothesis requires testing_plan and rationale fields."""
        # Should fail without testing_plan and rationale
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            Hypothesis(statement="Test statement")
        
        # Should succeed with testing_plan and rationale
        hypothesis = Hypothesis(
            statement="Test statement",
            rationale="Detailed rationale for the hypothesis",
            testing_plan="Detailed testing plan",
        )
        assert hypothesis.testing_plan == "Detailed testing plan"

    def test_hypothesis_evidence_structure(self):
        """Test hypothesis evidence is structured correctly."""
        evidence = [
            EvidenceEntry(
                trace_id="tr-001",
                rationale="Shows timeout",
                supports=True,
            ),
            EvidenceEntry(
                trace_id="tr-002",
                rationale="Fast response",
                supports=False,
            ),
        ]
        
        hypothesis = Hypothesis(
            statement="DB locks cause timeouts",
            rationale="Investigating database lock issues",
            testing_plan="Test plan",
            evidence=evidence,
        )
        
        assert len(hypothesis.evidence) == 2
        assert hypothesis.evidence[0].trace_id == "tr-001"
        assert hypothesis.evidence[0].supports is True
        assert hypothesis.evidence[1].supports is False

    def test_hypothesis_evidence_from_dict(self):
        """Test hypothesis can accept evidence as dicts."""
        evidence_dicts = [
            {"trace_id": "tr-001", "rationale": "Shows timeout", "supports": True},
            {"trace_id": "tr-002", "rationale": "Fast response", "supports": False},
        ]
        
        hypothesis = Hypothesis(
            statement="Test",
            rationale="Test rationale",
            testing_plan="Test plan",
            evidence=evidence_dicts,
        )
        
        assert len(hypothesis.evidence) == 2
        assert all(isinstance(e, EvidenceEntry) for e in hypothesis.evidence)

    def test_hypothesis_add_evidence(self):
        """Test adding evidence to hypothesis."""
        hypothesis = Hypothesis(
            statement="Test",
            rationale="Test rationale",
            testing_plan="Test plan",
        )
        
        hypothesis.add_evidence("tr-001", "Evidence 1", True)
        hypothesis.add_evidence("tr-002", "Evidence 2", False)
        
        assert hypothesis.evidence_count == 2
        assert hypothesis.supports_count == 1
        assert hypothesis.refutes_count == 1
        # Trace count should be based on unique trace IDs in evidence
        assert hypothesis.trace_count == 2

    def test_hypothesis_summary(self):
        """Test creating hypothesis summary."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp-123",
            statement="Test statement",
            rationale="Test rationale",
            testing_plan="Test plan",
            status=HypothesisStatus.VALIDATED,
        )
        hypothesis.add_evidence("tr-001", "Evidence", True)
        
        summary = HypothesisSummary.from_hypothesis(hypothesis)
        
        assert summary.hypothesis_id == "hyp-123"
        assert summary.statement == "Test statement"
        assert summary.status == HypothesisStatus.VALIDATED
        assert summary.trace_count == 1
        assert summary.evidence_count == 1


class TestIssueModel:
    """Test Issue model."""

    def test_issue_requires_source_run_id(self):
        """Test that issue requires source_run_id field."""
        # Should fail without source_run_id
        with pytest.raises(TypeError):
            Issue(
                title="Test Issue",
                description="Test",
                severity=IssueSeverity.HIGH,
            )
        
        # Should succeed with source_run_id
        issue = Issue(
            source_run_id="run-123",
            title="Test Issue",
            description="Test",
            severity=IssueSeverity.HIGH,
        )
        assert issue.source_run_id == "run-123"

    def test_issue_evidence_no_supports_field(self):
        """Test that issue evidence doesn't use supports field."""
        evidence = [
            {"trace_id": "tr-001", "rationale": "Shows the issue"},
            {"trace_id": "tr-002", "rationale": "Another example"},
        ]
        
        issue = Issue(
            source_run_id="run-123",
            title="Test Issue",
            description="Test",
            severity=IssueSeverity.HIGH,
            evidence=evidence,
        )
        
        # All evidence should have supports=None for issues
        assert all(e.supports is None for e in issue.evidence)

    def test_issue_add_evidence(self):
        """Test adding evidence to issue."""
        issue = Issue(
            source_run_id="run-123",
            title="Test",
            description="Test",
            severity=IssueSeverity.MEDIUM,
        )
        
        issue.add_evidence("tr-001", "Evidence 1")
        issue.add_evidence("tr-002", "Evidence 2")
        
        assert len(issue.evidence) == 2
        assert issue.trace_count == 2
        assert all(e.supports is None for e in issue.evidence)

    def test_issue_resolution(self):
        """Test resolving an issue."""
        issue = Issue(
            source_run_id="run-123",
            title="Test",
            description="Test",
            severity=IssueSeverity.HIGH,
        )
        
        assert issue.status == IssueStatus.OPEN
        assert issue.resolution is None
        
        issue.resolve("Fixed by increasing pool size")
        
        assert issue.status == IssueStatus.RESOLVED
        assert issue.resolution == "Fixed by increasing pool size"

    def test_issue_summary(self):
        """Test creating issue summary."""
        issue = Issue(
            issue_id="issue-123",
            source_run_id="run-456",
            title="Database Lock Issue",
            description="Locks causing timeouts",
            severity=IssueSeverity.CRITICAL,
        )
        
        summary = IssueSummary.from_issue(issue)
        
        assert summary.issue_id == "issue-123"
        assert summary.title == "Database Lock Issue"
        assert summary.severity == IssueSeverity.CRITICAL
        assert summary.trace_count == 3
        assert summary.source_run_id == "run-456"


class TestEvidenceEntry:
    """Test EvidenceEntry model."""

    def test_evidence_entry_creation(self):
        """Test creating evidence entries."""
        # With supports=True
        entry1 = EvidenceEntry(
            trace_id="tr-001",
            rationale="Supporting evidence",
            supports=True,
        )
        assert entry1.supports is True
        
        # With supports=False
        entry2 = EvidenceEntry(
            trace_id="tr-002",
            rationale="Refuting evidence",
            supports=False,
        )
        assert entry2.supports is False
        
        # With supports=None (for issues)
        entry3 = EvidenceEntry(
            trace_id="tr-003",
            rationale="Issue evidence",
            supports=None,
        )
        assert entry3.supports is None

    def test_evidence_entry_serialization(self):
        """Test evidence entry can be serialized."""
        entry = EvidenceEntry(
            trace_id="tr-001",
            rationale="Test rationale",
            supports=True,
        )
        
        data = entry.model_dump()
        assert data["trace_id"] == "tr-001"
        assert data["rationale"] == "Test rationale"
        assert data["supports"] is True
        
        # Can be recreated from dict
        new_entry = EvidenceEntry(**data)
        assert new_entry.trace_id == entry.trace_id


class TestYAMLSerialization:
    """Test YAML serialization of models."""

    def test_hypothesis_yaml_roundtrip(self):
        """Test hypothesis can be saved and loaded from YAML."""
        hypothesis = Hypothesis(
            statement="Test hypothesis",
            rationale="Test rationale for hypothesis",
            testing_plan="Detailed testing plan with validation criteria",
            evidence=[
                {"trace_id": "tr-001", "rationale": "Evidence 1", "supports": True},
                {"trace_id": "tr-002", "rationale": "Evidence 2", "supports": False},
            ],
        )
        
        # Convert to YAML
        data = hypothesis.model_dump(mode="json")
        yaml_str = yaml.safe_dump(data)
        
        # Load back from YAML
        loaded_data = yaml.safe_load(yaml_str)
        loaded_hypothesis = Hypothesis(**loaded_data)
        
        assert loaded_hypothesis.statement == hypothesis.statement
        assert loaded_hypothesis.testing_plan == hypothesis.testing_plan
        assert len(loaded_hypothesis.evidence) == 2

    def test_issue_yaml_roundtrip(self):
        """Test issue can be saved and loaded from YAML."""
        issue = Issue(
            source_run_id="run-123",
            title="Test Issue",
            description="Issue description",
            severity=IssueSeverity.HIGH,
            evidence=[
                {"trace_id": "tr-001", "rationale": "Shows the problem"},
            ],
        )
        
        # Convert to YAML
        data = issue.model_dump(mode="json")
        yaml_str = yaml.safe_dump(data)
        
        # Load back from YAML
        loaded_data = yaml.safe_load(yaml_str)
        loaded_issue = Issue(**loaded_data)
        
        assert loaded_issue.source_run_id == issue.source_run_id
        assert loaded_issue.title == issue.title
        assert loaded_issue.severity == issue.severity