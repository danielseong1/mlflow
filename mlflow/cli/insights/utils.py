"""
Utility functions for MLflow Insights - YAML operations and artifact management.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml

from mlflow import MlflowClient
from mlflow.cli.insights.models import (
    Analysis,
    Hypothesis,
    HypothesisSummary,
    Issue,
    IssueSummary,
)

T = TypeVar("T", Analysis, Hypothesis, Issue)

INSIGHTS_DIR = "insights"


def save_to_yaml(client: MlflowClient, run_id: str, filename: str, data: T) -> None:
    """
    Save a Pydantic model as YAML to the insights/ artifact directory.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to save artifact to
        filename: Name of the YAML file (without directory prefix)
        data: Pydantic model instance to save
    """
    # Convert Pydantic model to dict, handling datetime serialization
    data_dict = data.model_dump(mode="json")
    
    yaml_content = yaml.safe_dump(data_dict, default_flow_style=False, sort_keys=False)
    
    # Create temp file with specific name
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, filename)
    
    try:
        with open(temp_path, 'w') as f:
            f.write(yaml_content)
        
        # Log artifact to the insights directory
        client.log_artifact(run_id, temp_path, INSIGHTS_DIR)
    finally:
        # Clean up temp file and directory
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


def load_from_yaml(
    client: MlflowClient, 
    run_id: str, 
    filename: str, 
    model_class: Type[T]
) -> T:
    """
    Load YAML from insights/ directory and parse to Pydantic model.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to load artifact from
        filename: Name of the YAML file (without directory prefix)
        model_class: Pydantic model class to parse into
    
    Returns:
        Parsed Pydantic model instance
    """
    artifact_path = f"{INSIGHTS_DIR}/{filename}"
    local_path = client.download_artifacts(run_id, artifact_path)
    
    with open(local_path, 'r') as f:
        data = yaml.safe_load(f)
    
    return model_class(**data)


def list_insights_artifacts(
    client: MlflowClient, 
    run_id: str, 
    prefix: str = ""
) -> List[str]:
    """
    List all artifacts in insights/ directory with optional prefix filter.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to list artifacts from
        prefix: Optional prefix to filter artifacts (e.g., "hypothesis_", "issue_")
    
    Returns:
        List of artifact filenames (without directory prefix)
    """
    try:
        artifacts = client.list_artifacts(run_id, INSIGHTS_DIR)
        filenames = []
        
        for artifact in artifacts:
            # Extract just the filename from the path
            filename = os.path.basename(artifact.path)
            if not prefix or filename.startswith(prefix):
                filenames.append(filename)
        
        return sorted(filenames)
    except Exception:
        # If insights directory doesn't exist yet
        return []


def get_analysis(client: MlflowClient, run_id: str) -> Optional[Analysis]:
    """
    Get the analysis metadata for a run.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to get analysis from
    
    Returns:
        Analysis object or None if not found
    """
    try:
        return load_from_yaml(client, run_id, "analysis.yaml", Analysis)
    except Exception:
        return None


def get_hypothesis(client: MlflowClient, run_id: str, hypothesis_id: str) -> Optional[Hypothesis]:
    """
    Get a specific hypothesis by ID.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to get hypothesis from
        hypothesis_id: Hypothesis ID
    
    Returns:
        Hypothesis object or None if not found
    """
    try:
        filename = f"hypothesis_{hypothesis_id}.yaml"
        return load_from_yaml(client, run_id, filename, Hypothesis)
    except Exception:
        return None


def get_issue(client: MlflowClient, run_id: str, issue_id: str) -> Optional[Issue]:
    """
    Get a specific issue by ID.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to get issue from
        issue_id: Issue ID
    
    Returns:
        Issue object or None if not found
    """
    try:
        filename = f"issue_{issue_id}.yaml"
        return load_from_yaml(client, run_id, filename, Issue)
    except Exception:
        return None


def list_hypotheses(client: MlflowClient, run_id: str) -> List[HypothesisSummary]:
    """
    List all hypotheses in a run (metadata only).
    
    Args:
        client: MLflow client instance
        run_id: Run ID to list hypotheses from
    
    Returns:
        List of HypothesisSummary objects
    """
    hypothesis_files = list_insights_artifacts(client, run_id, "hypothesis_")
    summaries = []
    
    for filename in hypothesis_files:
        try:
            hypothesis = load_from_yaml(client, run_id, filename, Hypothesis)
            summaries.append(HypothesisSummary.from_hypothesis(hypothesis))
        except Exception:
            # Skip files that can't be parsed
            continue
    
    return summaries


def list_issues(client: MlflowClient, run_id: str) -> List[IssueSummary]:
    """
    List all issues in a run (metadata only).
    
    Args:
        client: MLflow client instance
        run_id: Run ID to list issues from
    
    Returns:
        List of IssueSummary objects
    """
    issue_files = list_insights_artifacts(client, run_id, "issue_")
    summaries = []
    
    for filename in issue_files:
        try:
            issue = load_from_yaml(client, run_id, filename, Issue)
            summaries.append(IssueSummary.from_issue(issue))
        except Exception:
            # Skip files that can't be parsed
            continue
    
    return summaries


def find_analysis_runs(
    client: MlflowClient, 
    experiment_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Find all runs that contain analysis artifacts.
    
    Args:
        client: MLflow client instance
        experiment_id: Optional experiment ID to search within
    
    Returns:
        List of run info dictionaries with analysis metadata
    """
    from mlflow.entities import ViewType
    
    # Search for runs
    if experiment_id:
        runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string="",
            run_view_type=ViewType.ACTIVE_ONLY
        )
    else:
        # This would need to be implemented differently to search across all experiments
        # For now, require experiment_id
        return []
    
    analysis_runs = []
    for run in runs:
        analysis = get_analysis(client, run.info.run_id)
        if analysis:
            analysis_runs.append({
                "run_id": run.info.run_id,
                "run_name": run.info.run_name,
                "experiment_id": run.info.experiment_id,
                "analysis": analysis,
                "start_time": run.info.start_time,
                "status": run.info.status
            })
    
    return analysis_runs


def validate_run_has_analysis(client: MlflowClient, run_id: str) -> bool:
    """
    Check if a run has an analysis artifact.
    
    Args:
        client: MLflow client instance
        run_id: Run ID to check
    
    Returns:
        True if run has analysis, False otherwise
    """
    return get_analysis(client, run_id) is not None