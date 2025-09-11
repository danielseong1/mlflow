"""
Index management for MLflow Insights - maintains a registry of all analyses in an experiment.
"""

import json
from typing import Dict, List, Optional

import yaml

from mlflow import MlflowClient
from mlflow.cli.insights.utils import save_to_yaml, load_from_yaml


INSIGHTS_INDEX_TAG = "mlflow.insights.index_run_id"
INDEX_FILENAME = "insights_index.yaml"


class InsightsIndex:
    """
    Index of all analysis runs in an experiment.
    Stored in a dedicated index run for efficient lookup.
    """
    
    def __init__(self, analyses: Optional[Dict[str, Dict]] = None):
        """
        Initialize the insights index.
        
        Args:
            analyses: Dictionary mapping run_id to analysis metadata
        """
        self.analyses = analyses or {}
    
    def add_analysis(self, run_id: str, name: str, description: str) -> None:
        """Add an analysis to the index."""
        self.analyses[run_id] = {
            "name": name,
            "description": description,
            "created_at": None,  # Will be set from Analysis object
        }
    
    def remove_analysis(self, run_id: str) -> None:
        """Remove an analysis from the index."""
        if run_id in self.analyses:
            del self.analyses[run_id]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for YAML serialization."""
        return {"analyses": self.analyses}
    
    @classmethod
    def from_dict(cls, data: Dict) -> "InsightsIndex":
        """Create from dictionary."""
        return cls(analyses=data.get("analyses", {}))


def get_or_create_index_run(client: MlflowClient, experiment_id: str) -> str:
    """
    Get or create the index run for an experiment.
    
    Args:
        client: MLflow client
        experiment_id: Experiment ID
    
    Returns:
        Run ID of the index run
    """
    # Check if experiment has an index run tag
    experiment = client.get_experiment(experiment_id)
    
    index_run_id = None
    if experiment.tags:
        index_run_id = experiment.tags.get(INSIGHTS_INDEX_TAG)
    
    # Verify the index run still exists
    if index_run_id:
        try:
            run = client.get_run(index_run_id)
            if run.info.lifecycle_stage == "active":
                return index_run_id
        except Exception:
            # Index run doesn't exist or is deleted
            index_run_id = None
    
    # Create new index run
    import mlflow
    
    # End any active run to avoid conflicts
    try:
        mlflow.end_run()
    except Exception:
        pass
    
    mlflow.set_experiment(experiment_id=experiment_id)
    
    with mlflow.start_run(run_name="insights-index") as run:
        index_run_id = run.info.run_id
        
        # Tag the run as an index
        mlflow.set_tag("mlflow.insights.type", "index")
        mlflow.set_tag("mlflow.note", "This run maintains the index of all insights analyses for this experiment")
        
        # Initialize empty index
        index = InsightsIndex()
        save_index(client, index_run_id, index)
    
    # Tag the experiment with the index run ID
    client.set_experiment_tag(experiment_id, INSIGHTS_INDEX_TAG, index_run_id)
    
    return index_run_id


def get_index(client: MlflowClient, experiment_id: str) -> Optional[InsightsIndex]:
    """
    Get the insights index for an experiment.
    
    Args:
        client: MLflow client
        experiment_id: Experiment ID
    
    Returns:
        InsightsIndex or None if not found
    """
    try:
        index_run_id = get_or_create_index_run(client, experiment_id)
        
        # Download and parse index
        artifact_path = f"insights/{INDEX_FILENAME}"
        local_path = client.download_artifacts(index_run_id, artifact_path)
        
        with open(local_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return InsightsIndex.from_dict(data)
    except Exception:
        return None


def save_index(client: MlflowClient, index_run_id: str, index: InsightsIndex) -> None:
    """
    Save the insights index to the index run.
    
    Args:
        client: MLflow client
        index_run_id: Run ID of the index run
        index: InsightsIndex to save
    """
    import os
    import tempfile
    
    data = index.to_dict()
    yaml_content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
    
    # Create temp file with specific name
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, INDEX_FILENAME)
    
    try:
        with open(temp_path, 'w') as f:
            f.write(yaml_content)
        
        # Log artifact to the insights directory
        client.log_artifact(index_run_id, temp_path, "insights")
    finally:
        # Clean up temp file and directory
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


def register_analysis(
    client: MlflowClient, 
    experiment_id: str, 
    run_id: str, 
    name: str, 
    description: str
) -> None:
    """
    Register an analysis run in the experiment's index.
    
    Args:
        client: MLflow client
        experiment_id: Experiment ID
        run_id: Run ID of the analysis
        name: Analysis name
        description: Analysis description
    """
    index_run_id = get_or_create_index_run(client, experiment_id)
    
    # Get current index
    index = get_index(client, experiment_id) or InsightsIndex()
    
    # Add analysis to index
    index.add_analysis(run_id, name, description)
    
    # Save updated index
    save_index(client, index_run_id, index)


def unregister_analysis(client: MlflowClient, experiment_id: str, run_id: str) -> None:
    """
    Remove an analysis run from the experiment's index.
    
    Args:
        client: MLflow client
        experiment_id: Experiment ID
        run_id: Run ID of the analysis to remove
    """
    index_run_id = get_or_create_index_run(client, experiment_id)
    
    # Get current index
    index = get_index(client, experiment_id)
    if not index:
        return
    
    # Remove analysis from index
    index.remove_analysis(run_id)
    
    # Save updated index
    save_index(client, index_run_id, index)


def list_analyses_from_index(client: MlflowClient, experiment_id: str) -> List[Dict]:
    """
    List all analyses from the experiment's index.
    
    Args:
        client: MLflow client
        experiment_id: Experiment ID
    
    Returns:
        List of analysis metadata dictionaries
    """
    index = get_index(client, experiment_id)
    if not index:
        return []
    
    # Convert to list format with run_id included
    analyses = []
    for run_id, metadata in index.analyses.items():
        analysis_info = metadata.copy()
        analysis_info["run_id"] = run_id
        analyses.append(analysis_info)
    
    return analyses