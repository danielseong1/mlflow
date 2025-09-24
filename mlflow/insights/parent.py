"""
Parent run management for MLflow Insights - maintains a single parent run for all analyses.
"""

from typing import Optional

import mlflow
from mlflow import MlflowClient
from mlflow.entities import ViewType

INSIGHTS_PARENT_TAG = "mlflow.insights.parent"
INSIGHTS_TYPE_TAG = "mlflow.insights.type"


def get_or_create_parent_run(client: MlflowClient, experiment_id: str) -> str:
    """
    Get or create the parent insights run for an experiment.
    All analysis runs will be nested under this parent.
    Issues are stored in this parent run.

    Args:
        client: MLflow client
        experiment_id: Experiment ID

    Returns:
        Run ID of the parent insights run
    """

    # Daniel Insights baseline
    # return "7c4a9013e6264703862a91de4fe13197"

    # Daniel Insights
    # return "2b8c2e0b9e08404ab0fdfa653112ee88"

    # Daniel Insights codex
    # return "a523df8148b04ef1a23bdee95468930e"


    # Search for existing parent run
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.{INSIGHTS_TYPE_TAG} = 'parent'",
        run_view_type=ViewType.ACTIVE_ONLY,
        max_results=1,
    )

    if runs:
        # Found existing parent run
        parent_run = runs[0]
        return parent_run.info.run_id

    # Create new parent run
    mlflow.set_experiment(experiment_id=experiment_id)

    # Make sure no run is active
    try:
        mlflow.end_run()
    except Exception:
        pass

    parent_run = mlflow.start_run(run_name="Insights")
    parent_run_id = parent_run.info.run_id

    # Tag the run as the insights parent
    mlflow.set_tag(INSIGHTS_TYPE_TAG, "parent")
    mlflow.set_tag(INSIGHTS_PARENT_TAG, "true")
    mlflow.set_tag(
        "mlflow.note",
        "Parent run for all insights analyses and issues in this experiment",
    )
    mlflow.set_tag("mlflow.runName", "Insights")

    # End the parent run - we'll reopen it when needed
    mlflow.end_run()

    return parent_run_id


def get_parent_run_id(client: MlflowClient, insights_run_id: str) -> Optional[str]:
    """
    Get the parent run ID for a given analysis run.

    Args:
        client: MLflow client
        insights_run_id: Analysis run ID

    Returns:
        Parent run ID or None if not found
    """
    try:
        run = client.get_run(insights_run_id)
        if run.data.tags:
            return run.data.tags.get("mlflow.parentRunId")
    except Exception:
        pass
    return None


def create_nested_analysis_run(client: MlflowClient, experiment_id: str, run_name: str) -> str:
    """
    Create a new analysis run nested under the parent insights run.

    Args:
        client: MLflow client
        experiment_id: Experiment ID
        run_name: Name for the analysis run (short 3-4 words)

    Returns:
        Run ID of the new nested analysis run
    """
    parent_run_id = get_or_create_parent_run(client, experiment_id)

    # Set the experiment
    mlflow.set_experiment(experiment_id=experiment_id)

    # Start nested run under the parent
    nested_run = mlflow.start_run(run_name=run_name, nested=True, parent_run_id=parent_run_id)

    # Tag as analysis run
    mlflow.set_tag(INSIGHTS_TYPE_TAG, "analysis")

    return nested_run.info.run_id


def list_analysis_runs(client: MlflowClient, experiment_id: str) -> list:
    """
    List all analysis runs (nested under the parent insights run).

    Args:
        client: MLflow client
        experiment_id: Experiment ID

    Returns:
        List of analysis run infos
    """
    # First get the parent run
    parent_run_id = get_or_create_parent_run(client, experiment_id)

    # Search for all nested runs under this parent
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        filter_string=f"tags.mlflow.parentRunId = '{parent_run_id}' AND tags.{INSIGHTS_TYPE_TAG} = 'analysis'",
        run_view_type=ViewType.ACTIVE_ONLY,
    )

    return runs


def is_insights_parent_run(run_id: str, client: MlflowClient) -> bool:
    """
    Check if a run is the insights parent run.

    Args:
        run_id: Run ID to check
        client: MLflow client

    Returns:
        True if this is the insights parent run
    """
    try:
        run = client.get_run(run_id)
        if run.data.tags:
            return run.data.tags.get(INSIGHTS_TYPE_TAG) == "parent"
    except Exception:
        pass
    return False
