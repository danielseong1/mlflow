"""
Utility functions for MLflow Insights.
"""

import os
import tempfile
from typing import Optional

import yaml
from pydantic import BaseModel

from mlflow import MlflowClient


def save_to_yaml(client: MlflowClient, run_id: str, filename: str, obj: BaseModel) -> None:
    """
    Save a Pydantic model to YAML in the insights/ artifact directory.

    Args:
        client: MLflow client
        run_id: Run ID to save artifact to
        filename: Name of the YAML file (e.g., 'analysis.yaml')
        obj: Pydantic model instance to save
    """
    # Convert Pydantic model to dict with JSON-compatible types
    data = obj.model_dump(mode="json")

    # Convert to YAML string
    yaml_content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    # Create temp file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, filename)

    try:
        with open(temp_path, "w") as f:
            f.write(yaml_content)

        # Log artifact to the insights directory
        client.log_artifact(run_id, temp_path, "insights")
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
    model_class: type[BaseModel],
) -> Optional[BaseModel]:
    """
    Load a Pydantic model from YAML in the insights/ artifact directory.

    Args:
        client: MLflow client
        run_id: Run ID to load artifact from
        filename: Name of the YAML file (e.g., 'analysis.yaml')
        model_class: Pydantic model class to instantiate

    Returns:
        Model instance or None if not found
    """
    try:
        # Download artifact
        artifact_path = f"insights/{filename}"
        local_path = client.download_artifacts(run_id, artifact_path)

        # Load YAML
        with open(local_path) as f:
            data = yaml.safe_load(f)

        # Create model instance
        return model_class(**data)
    except Exception:
        return None


def list_yaml_files(client: MlflowClient, run_id: str, prefix: str) -> list[str]:
    """
    List all YAML files in the insights/ directory with a given prefix.

    Args:
        client: MLflow client
        run_id: Run ID to list artifacts from
        prefix: Filename prefix to filter (e.g., 'hypothesis_', 'issue_')

    Returns:
        List of filenames matching the prefix
    """
    try:
        artifacts = client.list_artifacts(run_id, "insights")
        return [
            artifact.path.split("/")[-1]
            for artifact in artifacts
            if artifact.path.endswith(".yaml") and artifact.path.split("/")[-1].startswith(prefix)
        ]
    except Exception:
        return []


def validate_run_has_analysis(client: MlflowClient, run_id: str) -> bool:
    """
    Check if a run contains an analysis.

    Args:
        client: MLflow client
        run_id: Run ID to check

    Returns:
        True if the run contains an analysis
    """
    try:
        # Check if analysis.yaml exists
        artifact_path = "insights/analysis.yaml"
        client.download_artifacts(run_id, artifact_path)
        return True
    except Exception:
        return False


def get_experiment_for_run(client: MlflowClient, run_id: str) -> Optional[str]:
    """
    Get the experiment ID for a given run.

    Args:
        client: MLflow client
        run_id: Run ID

    Returns:
        Experiment ID or None if not found
    """
    try:
        run = client.get_run(run_id)
        return run.info.experiment_id
    except Exception:
        return None
