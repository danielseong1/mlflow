"""
Shared fixtures for Insights tests.
"""

import os
import tempfile
from unittest.mock import MagicMock, Mock

import pytest
import yaml

from mlflow.entities import Run, RunInfo
from mlflow.insights.models import Analysis, Hypothesis, Issue


@pytest.fixture
def mock_mlflow_client():
    """
    Mock MLflow client with in-memory artifact storage.
    """
    client = Mock()
    
    # In-memory storage for artifacts
    artifacts = {}
    
    # Mock run storage
    runs = {}
    
    def log_artifact_side_effect(run_id, local_path, artifact_path):
        """Store artifact in memory."""
        with open(local_path, "r") as f:
            content = f.read()
        key = f"{run_id}/{artifact_path}/{os.path.basename(local_path)}"
        artifacts[key] = content
    
    def download_artifacts_side_effect(run_id, path):
        """Retrieve artifact from memory."""
        # Look for the artifact
        key = f"{run_id}/{path}"
        if key in artifacts:
            content = artifacts[key]
        else:
            # Try without the basename (for full paths)
            for k, v in artifacts.items():
                if k.startswith(f"{run_id}/{path}"):
                    content = v
                    break
            else:
                raise Exception(f"Artifact not found: {key}")
        
        # Write to temp file and return path
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, os.path.basename(path))
        with open(temp_path, "w") as f:
            f.write(content)
        return temp_path
    
    def list_artifacts_side_effect(run_id, path):
        """List artifacts in a path."""
        from mlflow.entities import FileInfo
        
        prefix = f"{run_id}/{path}/"
        files = []
        for key in artifacts:
            if key.startswith(prefix):
                # Extract filename from key
                remaining = key[len(prefix):]
                if "/" not in remaining:  # Only direct children
                    files.append(
                        FileInfo(
                            path=f"{path}/{remaining}",
                            is_dir=False,
                            file_size=len(artifacts[key]),
                        )
                    )
        return files
    
    def get_run_side_effect(run_id):
        """Get run info."""
        if run_id in runs:
            return runs[run_id]
        raise Exception(f"Run not found: {run_id}")
    
    def search_runs_side_effect(experiment_ids, filter_string="", **kwargs):
        """Search for runs."""
        results = []
        for run_id, run in runs.items():
            # Simple filter matching for parent tag
            if "parent" in filter_string and run.data.tags.get("mlflow.insights.type") == "parent":
                results.append(run)
            elif "analysis" in filter_string:
                if run.data.tags.get("mlflow.insights.type") == "analysis":
                    # Check parent ID if specified
                    if "mlflow.parentRunId" in filter_string:
                        parent_id = filter_string.split("'")[1]
                        if run.data.tags.get("mlflow.parentRunId") == parent_id:
                            results.append(run)
                    else:
                        results.append(run)
        return results[:kwargs.get("max_results", 100)]
    
    def get_experiment_side_effect(experiment_id):
        """Get experiment info."""
        from mlflow.entities import Experiment
        
        return Experiment(
            experiment_id=experiment_id,
            name=f"Experiment {experiment_id}",
            artifact_location="/tmp",
            lifecycle_stage="active",
            tags={},
        )
    
    def search_experiments_side_effect(**kwargs):
        """Search experiments."""
        from mlflow.entities import Experiment
        
        return [
            Experiment(
                experiment_id="123",
                name="Test Experiment",
                artifact_location="/tmp",
                lifecycle_stage="active",
                tags={},
            )
        ]
    
    def link_traces_to_run_side_effect(trace_ids, run_id):
        """Mock linking traces."""
        # Just succeed silently
        pass
    
    def get_trace_side_effect(trace_id):
        """Mock getting a trace."""
        from mlflow.entities import Trace, TraceInfo
        
        # Return a mock trace
        return Trace(
            info=TraceInfo(
                request_id=trace_id,
                experiment_id="123",
                timestamp_ms=1000000,
                execution_time_ms=100,
                status="OK",
                request_metadata={},
                tags={},
            ),
            data=None,  # Simplified for testing
        )
    
    # Set up mock methods
    client.log_artifact.side_effect = log_artifact_side_effect
    client.download_artifacts.side_effect = download_artifacts_side_effect
    client.list_artifacts.side_effect = list_artifacts_side_effect
    client.get_run.side_effect = get_run_side_effect
    client.search_runs.side_effect = search_runs_side_effect
    client.get_experiment.side_effect = get_experiment_side_effect
    client.search_experiments.side_effect = search_experiments_side_effect
    client.link_traces_to_run.side_effect = link_traces_to_run_side_effect
    client.get_trace.side_effect = get_trace_side_effect
    
    # Store references for test access
    client._artifacts = artifacts
    client._runs = runs
    
    return client


@pytest.fixture
def mock_mlflow_module():
    """Mock mlflow module functions."""
    import mlflow
    
    with Mock() as mock_mlflow:
        mock_mlflow.set_experiment.return_value = None
        mock_mlflow.end_run.return_value = None
        
        # Mock start_run to return a run with ID
        mock_run = Mock()
        mock_run.info.run_id = "test-run-id"
        mock_mlflow.start_run.return_value = mock_run
        
        mock_mlflow.set_tag.return_value = None
        
        # Patch the module
        import sys
        original_mlflow = sys.modules["mlflow"]
        
        # Keep original attributes but override specific functions
        for attr in dir(original_mlflow):
            if not attr.startswith("_"):
                try:
                    setattr(mock_mlflow, attr, getattr(original_mlflow, attr))
                except Exception:
                    pass
        
        mock_mlflow.set_experiment = Mock(return_value=None)
        mock_mlflow.end_run = Mock(return_value=None)
        mock_mlflow.start_run = Mock(return_value=mock_run)
        mock_mlflow.set_tag = Mock(return_value=None)
        
        sys.modules["mlflow"] = mock_mlflow
        
        yield mock_mlflow
        
        # Restore original
        sys.modules["mlflow"] = original_mlflow


def create_mock_run(run_id, parent_run_id=None, run_type="analysis", experiment_id="123"):
    """Helper to create a mock run."""
    from mlflow.entities import Run, RunData, RunInfo
    
    tags = {"mlflow.insights.type": run_type}
    if parent_run_id:
        tags["mlflow.parentRunId"] = parent_run_id
    
    run_info = RunInfo(
        run_id=run_id,
        experiment_id=experiment_id,
        run_name=f"Run {run_id}",
        user_id="test_user",
        status="FINISHED",
        start_time=1000000,
        end_time=1001000,
        lifecycle_stage="active",
        artifact_uri=f"/tmp/{run_id}",
    )
    
    run_data = RunData(tags=tags, params={}, metrics={})
    
    return Run(run_info=run_info, data=run_data)