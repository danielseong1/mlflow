"""
Utility functions for MLflow Insights.
"""

import os
import tempfile
from datetime import datetime
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


def delete_yaml_file(client: MlflowClient, run_id: str, filename: str) -> bool:
    """
    Delete a YAML file from the insights/ artifact directory.

    Args:
        client: MLflow client
        run_id: Run ID to delete artifact from
        filename: Name of the YAML file (e.g., 'analysis.yaml')

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Get the artifact repository for this run
        run = client.get_run(run_id)
        artifact_repo = client._get_artifact_repository(run.info.artifact_uri)

        # Delete the specific file in the insights directory
        artifact_path = f"insights/{filename}"
        artifact_repo.delete_artifacts(artifact_path)

        return True
    except Exception:
        return False


def save_sql_queries_to_yaml(run_id: str, sql_query: str) -> None:
    """
    Log a SQL query to the sql_queries.yaml artifact in append-only mode.

    Args:
        run_id: Run ID to log the query to
        sql_query: SQL query string to log
    """
    client = MlflowClient()
    filename = "sql_queries.yaml"
    queries_list = []

    # Try to load existing queries
    try:
        # Get existing artifact content
        artifact_path = f"insights/{filename}"
        local_path = client.download_artifacts(run_id, artifact_path)

        with open(local_path, 'r') as f:
            existing_data = yaml.safe_load(f) or []
            if isinstance(existing_data, list):
                queries_list = existing_data
    except Exception:
        # File doesn't exist yet, start with empty list
        pass

    # Append new query with timestamp
    new_query = {
        "timestamp": datetime.now().isoformat(),
        "query": sql_query
    }
    queries_list.append(new_query)

    # Save back to artifact
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, filename)

    try:
        with open(temp_path, 'w') as f:
            yaml.safe_dump(queries_list, f, default_flow_style=False, sort_keys=False)

        # Log artifact to insights directory
        client.log_artifact(run_id, temp_path, "insights")
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
