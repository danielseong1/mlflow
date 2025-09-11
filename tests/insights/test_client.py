"""
Tests for InsightsClient.
"""

import json
from unittest.mock import Mock, patch

import pytest
import yaml

from mlflow.insights import InsightsClient
from mlflow.insights.models import (
    AnalysisStatus,
    HypothesisStatus,
    IssueSeverity,
    IssueStatus,
)
from tests.insights.conftest import create_mock_run


class TestInsightsClient:
    """Test InsightsClient methods."""

    @patch("mlflow.insights.client.mlflow")
    def test_create_analysis(self, mock_mlflow, mock_mlflow_client):
        """Test creating an analysis."""
        # Setup
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Create parent run
        parent_run = create_mock_run("parent-run-id", run_type="parent")
        mock_mlflow_client._runs["parent-run-id"] = parent_run
        
        # Setup mlflow mocks
        mock_run = Mock()
        mock_run.info.run_id = "analysis-run-id"
        mock_mlflow.start_run.return_value = mock_run
        
        # Create analysis
        run_id = client.create_analysis(
            experiment_id="123",
            run_name="Test Analysis",
            name="Production Error Analysis",
            description="Investigating production errors",
        )
        
        # Verify run was created
        assert run_id == "analysis-run-id"
        mock_mlflow.start_run.assert_called_once()
        mock_mlflow.set_tag.assert_any_call("mlflow.insights.name", "Production Error Analysis")
        mock_mlflow.end_run.assert_called_once()
        
        # Verify analysis was saved
        artifact_key = "analysis-run-id/insights/analysis.yaml"
        assert artifact_key in mock_mlflow_client._artifacts
        
        # Parse and verify content
        content = mock_mlflow_client._artifacts[artifact_key]
        data = yaml.safe_load(content)
        assert data["name"] == "Production Error Analysis"
        assert data["description"] == "Investigating production errors"
        assert data["status"] == "ACTIVE"

    @patch("mlflow.insights.client.mlflow")
    def test_create_hypothesis(self, mock_mlflow, mock_mlflow_client):
        """Test creating a hypothesis with required testing_plan."""
        # Setup
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Create analysis first
        analysis_run = create_mock_run("analysis-run-id", parent_run_id="parent-run-id")
        mock_mlflow_client._runs["analysis-run-id"] = analysis_run
        
        # Save a mock analysis to make validation pass
        analysis_yaml = yaml.safe_dump({
            "name": "Test Analysis",
            "description": "Test",
            "status": "ACTIVE",
        })
        mock_mlflow_client._artifacts["analysis-run-id/insights/analysis.yaml"] = analysis_yaml
        
        # Create hypothesis with evidence
        evidence = [
            {
                "trace_id": "tr-001",
                "rationale": "Shows timeout waiting for DB lock",
                "supports": True,
            },
            {
                "trace_id": "tr-002",
                "rationale": "Fast response without DB operations",
                "supports": False,
            },
        ]
        
        hypothesis_id = client.create_hypothesis(
            insights_run_id="analysis-run-id",
            statement="Database locks cause timeouts",
            testing_plan="To test this hypothesis, I will search for traces with execution_time > 30s and look for database lock messages. Supporting evidence would include lock wait timeouts. To refute, I'll find slow traces without DB operations. Threshold: >70% correlation validates.",
            evidence=evidence,
        )
        
        # Verify hypothesis was created
        assert hypothesis_id is not None
        assert len(hypothesis_id) == 36  # UUID length
        
        # Verify hypothesis was saved
        artifact_key = f"analysis-run-id/insights/hypothesis_{hypothesis_id}.yaml"
        assert artifact_key in mock_mlflow_client._artifacts
        
        # Parse and verify content
        content = mock_mlflow_client._artifacts[artifact_key]
        data = yaml.safe_load(content)
        assert data["statement"] == "Database locks cause timeouts"
        assert "To test this hypothesis" in data["testing_plan"]
        assert data["status"] == "TESTING"
        assert len(data["evidence"]) == 2
        assert data["evidence"][0]["trace_id"] == "tr-001"
        assert data["evidence"][0]["supports"] is True
        assert data["evidence"][1]["trace_id"] == "tr-002"
        assert data["evidence"][1]["supports"] is False

    @patch("mlflow.insights.client.mlflow")
    def test_create_hypothesis_without_testing_plan_fails(self, mock_mlflow, mock_mlflow_client):
        """Test that creating a hypothesis without testing_plan fails."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Setup analysis
        analysis_run = create_mock_run("analysis-run-id")
        mock_mlflow_client._runs["analysis-run-id"] = analysis_run
        analysis_yaml = yaml.safe_dump({"name": "Test", "status": "ACTIVE"})
        mock_mlflow_client._artifacts["analysis-run-id/insights/analysis.yaml"] = analysis_yaml
        
        # Try to create hypothesis without testing_plan - should fail at validation
        with pytest.raises(TypeError) as exc_info:
            client.create_hypothesis(
                insights_run_id="analysis-run-id",
                statement="Database locks cause timeouts",
                # Missing testing_plan - this is required!
            )
        assert "testing_plan" in str(exc_info.value)

    @patch("mlflow.insights.client.mlflow")  
    def test_create_issue_in_parent_run(self, mock_mlflow, mock_mlflow_client):
        """Test that issues are stored in the parent run, not analysis run."""
        # Setup
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Create parent and analysis runs
        parent_run = create_mock_run("parent-run-id", run_type="parent")
        analysis_run = create_mock_run("analysis-run-id", parent_run_id="parent-run-id")
        mock_mlflow_client._runs["parent-run-id"] = parent_run
        mock_mlflow_client._runs["analysis-run-id"] = analysis_run
        
        # Save mock analysis
        analysis_yaml = yaml.safe_dump({"name": "Test", "status": "ACTIVE"})
        mock_mlflow_client._artifacts["analysis-run-id/insights/analysis.yaml"] = analysis_yaml
        
        # Create issue with evidence
        evidence = [
            {"trace_id": "tr-001", "rationale": "User query blocked for 32s"},
            {"trace_id": "tr-002", "rationale": "Deadlock detected"},
        ]
        
        issue_id = client.create_issue(
            insights_run_id="analysis-run-id",  # Source run
            title="Database Lock Contention",
            description="Locks causing timeouts",
            severity="HIGH",
            hypothesis_id="hyp-123",
            evidence=evidence,
        )
        
        # Verify issue was created
        assert issue_id is not None
        
        # CRITICAL: Verify issue was saved to PARENT run, not analysis run
        parent_artifact_key = f"parent-run-id/insights/issue_{issue_id}.yaml"
        assert parent_artifact_key in mock_mlflow_client._artifacts
        
        # Verify it was NOT saved to analysis run
        analysis_artifact_key = f"analysis-run-id/insights/issue_{issue_id}.yaml"
        assert analysis_artifact_key not in mock_mlflow_client._artifacts
        
        # Parse and verify content
        content = mock_mlflow_client._artifacts[parent_artifact_key]
        data = yaml.safe_load(content)
        assert data["title"] == "Database Lock Contention"
        assert data["severity"] == "HIGH"
        assert data["source_run_id"] == "analysis-run-id"  # Tracks source
        assert data["hypothesis_id"] == "hyp-123"
        assert len(data["evidence"]) == 2
        assert data["evidence"][0]["supports"] is None  # Issues don't use supports

    def test_update_hypothesis(self, mock_mlflow_client):
        """Test updating a hypothesis."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Setup existing hypothesis
        hypothesis_data = {
            "hypothesis_id": "hyp-123",
            "statement": "Original statement",
            "testing_plan": "Original plan",
            "status": "TESTING",
            "evidence": [],
        }
        mock_mlflow_client._artifacts["run-123/insights/hypothesis_hyp-123.yaml"] = yaml.safe_dump(hypothesis_data)
        
        # Update hypothesis
        new_evidence = [
            {"trace_id": "tr-003", "rationale": "New evidence", "supports": True}
        ]
        
        client.update_hypothesis(
            insights_run_id="run-123",
            hypothesis_id="hyp-123",
            status="VALIDATED",
            testing_plan="Updated testing plan",
            evidence=new_evidence,
        )
        
        # Verify update
        content = mock_mlflow_client._artifacts["run-123/insights/hypothesis_hyp-123.yaml"]
        data = yaml.safe_load(content)
        assert data["status"] == "VALIDATED"
        assert data["testing_plan"] == "Updated testing plan"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["trace_id"] == "tr-003"

    def test_list_issues_sorted_by_trace_count(self, mock_mlflow_client):
        """Test that list_issues returns issues sorted by trace count descending."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Create parent run
        parent_run = create_mock_run("parent-run-id", run_type="parent")
        mock_mlflow_client._runs["parent-run-id"] = parent_run
        
        # Create issues with different trace counts
        issue1 = {
            "issue_id": "issue-1",
            "title": "Issue 1",
            "severity": "LOW",
            "status": "OPEN",
            "source_run_id": "run-1",
            "evidence": [
                {"trace_id": "tr-1", "rationale": "Evidence 1", "supports": None},
                {"trace_id": "tr-2", "rationale": "Evidence 2", "supports": None},
            ],
        }
        issue2 = {
            "issue_id": "issue-2",
            "title": "Issue 2",
            "severity": "HIGH",
            "status": "OPEN",
            "source_run_id": "run-2",
            "evidence": [
                {"trace_id": "tr-3", "rationale": "Evidence 3", "supports": None},
                {"trace_id": "tr-4", "rationale": "Evidence 4", "supports": None},
                {"trace_id": "tr-5", "rationale": "Evidence 5", "supports": None},
                {"trace_id": "tr-6", "rationale": "Evidence 6", "supports": None},
                {"trace_id": "tr-7", "rationale": "Evidence 7", "supports": None},
            ],
        }
        issue3 = {
            "issue_id": "issue-3",
            "title": "Issue 3",
            "severity": "MEDIUM",
            "status": "OPEN",
            "source_run_id": "run-3",
            "evidence": [
                {"trace_id": "tr-8", "rationale": "Evidence 8", "supports": None},
            ],
        }
        
        # Save issues to parent run
        mock_mlflow_client._artifacts["parent-run-id/insights/issue_issue-1.yaml"] = yaml.safe_dump(issue1)
        mock_mlflow_client._artifacts["parent-run-id/insights/issue_issue-2.yaml"] = yaml.safe_dump(issue2)
        mock_mlflow_client._artifacts["parent-run-id/insights/issue_issue-3.yaml"] = yaml.safe_dump(issue3)
        
        # List issues
        issues = client.list_issues(experiment_id="123")
        
        # Verify sorting by trace count (descending)
        assert len(issues) == 3
        assert issues[0].issue_id == "issue-2"  # 5 traces
        assert issues[0].trace_count == 5
        assert issues[1].issue_id == "issue-1"  # 2 traces
        assert issues[1].trace_count == 2
        assert issues[2].issue_id == "issue-3"  # 1 trace
        assert issues[2].trace_count == 1

    def test_get_analysis(self, mock_mlflow_client):
        """Test getting an analysis."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Setup analysis
        analysis_data = {
            "name": "Test Analysis",
            "description": "Test description",
            "status": "ACTIVE",
        }
        mock_mlflow_client._artifacts["run-123/insights/analysis.yaml"] = yaml.safe_dump(analysis_data)
        
        # Get analysis
        analysis = client.get_analysis("run-123")
        
        assert analysis is not None
        assert analysis.name == "Test Analysis"
        assert analysis.description == "Test description"
        assert analysis.status == AnalysisStatus.ACTIVE

    def test_preview_hypotheses_returns_traces(self, mock_mlflow_client):
        """Test that preview_hypotheses returns actual trace objects."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Setup hypothesis with trace IDs
        hypothesis_data = {
            "hypothesis_id": "hyp-123",
            "statement": "Test",
            "testing_plan": "Test plan",
            "status": "TESTING",
            "evidence": [
                {"trace_id": "tr-001", "rationale": "Evidence 1", "supports": True},
                {"trace_id": "tr-002", "rationale": "Evidence 2", "supports": False},
                {"trace_id": "tr-003", "rationale": "Evidence 3", "supports": True},
            ],
        }
        mock_mlflow_client._artifacts["run-123/insights/hypothesis_hyp-123.yaml"] = yaml.safe_dump(hypothesis_data)
        
        # Preview hypotheses
        traces = client.preview_hypotheses("run-123", max_traces=2)
        
        # Verify traces returned
        assert len(traces) == 2  # Limited by max_traces
        assert all(hasattr(trace, "info") for trace in traces)
        assert traces[0].info.request_id in ["tr-001", "tr-002"]

    def test_preview_issues_returns_traces(self, mock_mlflow_client):
        """Test that preview_issues returns actual trace objects."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Create parent run
        parent_run = create_mock_run("parent-run-id", run_type="parent")
        mock_mlflow_client._runs["parent-run-id"] = parent_run
        
        # Setup issue with trace IDs
        issue_data = {
            "issue_id": "issue-123",
            "title": "Test Issue",
            "severity": "HIGH",
            "status": "OPEN",
            "source_run_id": "run-123",
            "evidence": [
                {"trace_id": "tr-004", "rationale": "Evidence 4", "supports": None},
                {"trace_id": "tr-005", "rationale": "Evidence 5", "supports": None},
                {"trace_id": "tr-006", "rationale": "Evidence 6", "supports": None},
            ],
        }
        mock_mlflow_client._artifacts["parent-run-id/insights/issue_issue-123.yaml"] = yaml.safe_dump(issue_data)
        
        # Preview issues
        traces = client.preview_issues("123", max_traces=2)
        
        # Verify traces returned
        assert len(traces) == 2  # Limited by max_traces
        assert all(hasattr(trace, "info") for trace in traces)

    def test_evidence_structure_validation(self, mock_mlflow_client):
        """Test that evidence structure is properly validated."""
        client = InsightsClient(tracking_client=mock_mlflow_client)
        
        # Setup
        analysis_run = create_mock_run("analysis-run-id")
        mock_mlflow_client._runs["analysis-run-id"] = analysis_run
        analysis_yaml = yaml.safe_dump({"name": "Test", "status": "ACTIVE"})
        mock_mlflow_client._artifacts["analysis-run-id/insights/analysis.yaml"] = analysis_yaml
        
        # Test invalid evidence (missing required fields)
        with pytest.raises(ValueError) as exc_info:
            client.create_hypothesis(
                insights_run_id="analysis-run-id",
                statement="Test",
                testing_plan="Test plan",
                evidence=[{"trace_id": "tr-001"}],  # Missing rationale
            )
        assert "rationale" in str(exc_info.value)
        
        # Test invalid evidence type
        with pytest.raises(ValueError) as exc_info:
            client.create_hypothesis(
                insights_run_id="analysis-run-id",
                statement="Test",
                testing_plan="Test plan",
                evidence=["not a dict"],  # Wrong type
            )
        assert "dict" in str(exc_info.value)