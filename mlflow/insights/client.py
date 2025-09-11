"""
MLflow Insights Client - Python SDK for managing analyses, hypotheses, and issues.
"""

from typing import Optional

import mlflow
from mlflow import MlflowClient
from mlflow.entities import Trace
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
from mlflow.insights.parent import (
    create_nested_analysis_run,
    get_or_create_parent_run,
    get_parent_run_id,
    list_analysis_runs,
)
from mlflow.insights.utils import (
    get_experiment_for_run,
    list_yaml_files,
    load_from_yaml,
    save_to_yaml,
    validate_run_has_analysis,
)


class InsightsClient:
    """
    Client for managing MLflow Insights - analyses, hypotheses, and issues.
    """

    def __init__(self, tracking_client: Optional[MlflowClient] = None):
        """
        Initialize the Insights client.

        Args:
            tracking_client: Optional MLflow tracking client. If not provided,
                           a default client will be created.
        """
        self._mlflow_client = tracking_client or MlflowClient()

    # =========================================================================
    # Creation Methods
    # =========================================================================

    def create_analysis(
        self, experiment_id: str, run_name: str, name: str, description: str
    ) -> str:
        """
        Create a new analysis run.

        Args:
            experiment_id: Experiment ID to create the analysis in
            run_name: Short name (3-4 words) for the MLflow run
            name: Human-readable name for the analysis
            description: Detailed description of investigation goals

        Returns:
            Run ID of the created analysis run
        """
        # Create nested run under parent
        run_id = create_nested_analysis_run(self._mlflow_client, experiment_id, run_name)

        try:
            # Create analysis metadata
            analysis = Analysis(name=name, description=description)

            # Save analysis to artifacts
            save_to_yaml(self._mlflow_client, run_id, "analysis.yaml", analysis)

            # Set tags for easier searching
            mlflow.set_tag("mlflow.insights.name", name)

            return run_id
        finally:
            mlflow.end_run()

    def create_hypothesis(
        self,
        insights_run_id: str,
        statement: str,
        testing_plan: str,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """
        Create a new hypothesis within an analysis.

        Args:
            insights_run_id: Run ID of the analysis
            statement: The hypothesis being tested
            testing_plan: Detailed plan for testing including validation/refutation criteria
            evidence: Optional list of evidence dicts with 'trace_id', 'rationale', 'supports'

        Returns:
            Hypothesis ID
        """
        # Validate run has analysis
        if not validate_run_has_analysis(self._mlflow_client, insights_run_id):
            raise ValueError(
                f"Run {insights_run_id} does not contain an analysis. Create an analysis first."
            )

        # Process evidence
        evidence_entries = []
        trace_ids = []
        if evidence:
            for ev in evidence:
                if not isinstance(ev, dict):
                    raise ValueError(f"Evidence must be a dict, got {type(ev)}")
                if "trace_id" not in ev or "rationale" not in ev:
                    raise ValueError("Evidence must have 'trace_id' and 'rationale' fields")
                # Default supports to True if not specified
                supports = ev.get("supports", True)
                evidence_entries.append(
                    EvidenceEntry(
                        trace_id=ev["trace_id"],
                        rationale=ev["rationale"],
                        supports=supports,
                    )
                )
                trace_ids.append(ev["trace_id"])

        # Create hypothesis
        hypothesis = Hypothesis(
            statement=statement,
            testing_plan=testing_plan,
            evidence=evidence_entries,
        )

        # Save hypothesis
        filename = f"hypothesis_{hypothesis.hypothesis_id}.yaml"
        save_to_yaml(self._mlflow_client, insights_run_id, filename, hypothesis)

        # Link traces to run if provided
        if trace_ids:
            try:
                self._mlflow_client.link_traces_to_run(trace_ids, insights_run_id)
            except Exception:
                # Linking traces is optional - don't fail if it doesn't work
                pass

        return hypothesis.hypothesis_id

    def create_issue(
        self,
        insights_run_id: str,
        title: str,
        description: str,
        severity: str,
        hypothesis_id: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """
        Create a validated issue. Issues are stored in the parent singleton run.

        Args:
            insights_run_id: Source run ID (analysis that created this issue)
            title: Brief issue title
            description: Detailed description of the problem
            severity: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
            hypothesis_id: Optional source hypothesis if validated from one
            evidence: Optional list of evidence dicts with 'trace_id' and 'rationale'

        Returns:
            Issue ID
        """
        # Validate run has analysis
        if not validate_run_has_analysis(self._mlflow_client, insights_run_id):
            raise ValueError(
                f"Run {insights_run_id} does not contain an analysis. Create an analysis first."
            )

        # Get parent run ID
        parent_run_id = get_parent_run_id(self._mlflow_client, insights_run_id)
        if not parent_run_id:
            # Get experiment ID and create parent
            experiment_id = get_experiment_for_run(self._mlflow_client, insights_run_id)
            if not experiment_id:
                raise ValueError(f"Could not find experiment for run {insights_run_id}")
            parent_run_id = get_or_create_parent_run(self._mlflow_client, experiment_id)

        # Process evidence
        evidence_entries = []
        trace_ids = []
        if evidence:
            for ev in evidence:
                if not isinstance(ev, dict):
                    raise ValueError(f"Evidence must be a dict, got {type(ev)}")
                if "trace_id" not in ev or "rationale" not in ev:
                    raise ValueError("Evidence must have 'trace_id' and 'rationale' fields")
                evidence_entries.append(
                    EvidenceEntry(
                        trace_id=ev["trace_id"],
                        rationale=ev["rationale"],
                        supports=None,  # Issues don't use supports field
                    )
                )
                trace_ids.append(ev["trace_id"])

        # Create issue with source_run_id
        issue = Issue(
            source_run_id=insights_run_id,
            title=title,
            description=description,
            severity=IssueSeverity(severity),
            hypothesis_id=hypothesis_id,
            evidence=evidence_entries,
        )

        # Save issue to PARENT run
        filename = f"issue_{issue.issue_id}.yaml"
        save_to_yaml(self._mlflow_client, parent_run_id, filename, issue)

        # Link traces to parent run if provided
        if trace_ids:
            try:
                self._mlflow_client.link_traces_to_run(trace_ids, parent_run_id)
            except Exception:
                # Linking traces is optional
                pass

        return issue.issue_id

    # =========================================================================
    # Update Methods
    # =========================================================================

    def update_analysis(
        self,
        run_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """
        Update an existing analysis.

        Args:
            run_id: Run ID containing the analysis
            name: New name for the analysis
            description: New description
            status: New status (ACTIVE, COMPLETED, ARCHIVED)
        """
        # Get existing analysis
        analysis = self.get_analysis(run_id)
        if not analysis:
            raise ValueError(f"No analysis found in run {run_id}")

        # Update fields
        if name is not None:
            analysis.name = name
        if description is not None:
            analysis.description = description
        if status is not None:
            analysis.status = AnalysisStatus(status)

        analysis.update_timestamp()

        # Save updated analysis
        save_to_yaml(self._mlflow_client, run_id, "analysis.yaml", analysis)

    def update_hypothesis(
        self,
        insights_run_id: str,
        hypothesis_id: str,
        status: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
        testing_plan: Optional[str] = None,
    ) -> None:
        """
        Update an existing hypothesis.

        Args:
            insights_run_id: Run ID containing the hypothesis
            hypothesis_id: Hypothesis ID to update
            status: New status (TESTING, VALIDATED, REJECTED)
            evidence: New evidence entries to add
            testing_plan: Updated testing plan
        """
        # Get existing hypothesis
        hypothesis = self.get_hypothesis(insights_run_id, hypothesis_id)
        if not hypothesis:
            raise ValueError(f"Hypothesis {hypothesis_id} not found in run {insights_run_id}")

        # Update fields
        if status is not None:
            hypothesis.status = HypothesisStatus(status)
        if testing_plan is not None:
            hypothesis.testing_plan = testing_plan

        # Add new evidence
        new_trace_ids = []
        if evidence:
            for ev in evidence:
                if not isinstance(ev, dict):
                    raise ValueError(f"Evidence must be a dict, got {type(ev)}")
                if "trace_id" not in ev or "rationale" not in ev:
                    raise ValueError("Evidence must have 'trace_id' and 'rationale' fields")
                supports = ev.get("supports", True)
                hypothesis.add_evidence(
                    trace_id=ev["trace_id"],
                    rationale=ev["rationale"],
                    supports=supports,
                )
                if ev["trace_id"] not in new_trace_ids:
                    new_trace_ids.append(ev["trace_id"])

        hypothesis.update_timestamp()

        # Save updated hypothesis
        filename = f"hypothesis_{hypothesis_id}.yaml"
        save_to_yaml(self._mlflow_client, insights_run_id, filename, hypothesis)

        # Link new traces
        if new_trace_ids:
            try:
                self._mlflow_client.link_traces_to_run(new_trace_ids, insights_run_id)
            except Exception:
                pass

    def update_issue(
        self,
        insights_run_id: str,
        issue_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
        resolution: Optional[str] = None,
    ) -> None:
        """
        Update an existing issue in the parent run.

        Args:
            insights_run_id: Any analysis run ID (used to find parent)
            issue_id: Issue ID to update
            severity: New severity level
            status: New status
            evidence: New evidence entries to add
            resolution: Resolution description (also sets status to RESOLVED)
        """
        # Get parent run ID
        parent_run_id = get_parent_run_id(self._mlflow_client, insights_run_id)
        if not parent_run_id:
            experiment_id = get_experiment_for_run(self._mlflow_client, insights_run_id)
            if not experiment_id:
                raise ValueError(f"Could not find experiment for run {insights_run_id}")
            parent_run_id = get_or_create_parent_run(self._mlflow_client, experiment_id)

        # Get existing issue from parent
        filename = f"issue_{issue_id}.yaml"
        issue = load_from_yaml(self._mlflow_client, parent_run_id, filename, Issue)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        # Update fields
        if severity is not None:
            issue.severity = IssueSeverity(severity)
        if status is not None:
            issue.status = IssueStatus(status)
        if resolution is not None:
            issue.resolve(resolution)

        # Add new evidence
        new_trace_ids = []
        if evidence:
            for ev in evidence:
                if not isinstance(ev, dict):
                    raise ValueError(f"Evidence must be a dict, got {type(ev)}")
                if "trace_id" not in ev or "rationale" not in ev:
                    raise ValueError("Evidence must have 'trace_id' and 'rationale' fields")
                issue.add_evidence(
                    trace_id=ev["trace_id"],
                    rationale=ev["rationale"],
                )
                if ev["trace_id"] not in new_trace_ids:
                    new_trace_ids.append(ev["trace_id"])

        issue.update_timestamp()

        # Save updated issue to parent
        save_to_yaml(self._mlflow_client, parent_run_id, filename, issue)

        # Link new traces to parent
        if new_trace_ids:
            try:
                self._mlflow_client.link_traces_to_run(new_trace_ids, parent_run_id)
            except Exception:
                pass

    # =========================================================================
    # Read Methods
    # =========================================================================

    def list_analyses(self, experiment_id: str) -> list[AnalysisSummary]:
        """
        List all analyses in an experiment.

        Args:
            experiment_id: Experiment ID

        Returns:
            List of analysis summaries with hypotheses
        """
        # Get all analysis runs
        runs = list_analysis_runs(self._mlflow_client, experiment_id)

        summaries = []
        for run in runs:
            analysis = self.get_analysis(run.info.run_id)
            if analysis:
                # Get all hypotheses for this analysis
                hypotheses = self.list_hypotheses(run.info.run_id)
                hypothesis_count = len(hypotheses)
                
                # Count validated hypotheses
                validated_count = sum(1 for h in hypotheses if h.status == HypothesisStatus.VALIDATED)

                summary = AnalysisSummary.from_analysis(
                    run.info.run_id, 
                    analysis, 
                    hypothesis_count,
                    validated_count,
                    hypotheses
                )
                summaries.append(summary)

        return summaries

    def list_hypotheses(self, insights_run_id: str) -> list[HypothesisSummary]:
        """
        List all hypotheses in an analysis run.

        Args:
            insights_run_id: Run ID of the analysis

        Returns:
            List of hypothesis summaries
        """
        # Get all hypothesis files
        hypothesis_files = list_yaml_files(self._mlflow_client, insights_run_id, "hypothesis_")

        summaries = []
        for filename in hypothesis_files:
            hypothesis = load_from_yaml(self._mlflow_client, insights_run_id, filename, Hypothesis)
            if hypothesis:
                summary = HypothesisSummary.from_hypothesis(hypothesis)
                summaries.append(summary)

        return summaries

    def list_issues(self, experiment_id: str) -> list[IssueSummary]:
        """
        List all issues in an experiment (from parent run).
        Results are sorted by trace_count in descending order.

        Args:
            experiment_id: Experiment ID

        Returns:
            List of issue summaries sorted by trace count (most traces first)
        """
        # Get parent run
        parent_run_id = get_or_create_parent_run(self._mlflow_client, experiment_id)

        # Get all issue files from parent
        issue_files = list_yaml_files(self._mlflow_client, parent_run_id, "issue_")

        summaries = []
        for filename in issue_files:
            issue = load_from_yaml(self._mlflow_client, parent_run_id, filename, Issue)
            if issue:
                summary = IssueSummary.from_issue(issue)
                summaries.append(summary)

        # Sort by trace_count descending
        summaries.sort(key=lambda x: x.trace_count, reverse=True)

        return summaries

    def get_analysis(self, insights_run_id: str) -> Optional[Analysis]:
        """
        Get detailed analysis information.

        Args:
            insights_run_id: Run ID containing the analysis

        Returns:
            Analysis object or None if not found
        """
        return load_from_yaml(self._mlflow_client, insights_run_id, "analysis.yaml", Analysis)

    def get_hypothesis(self, insights_run_id: str, hypothesis_id: str) -> Optional[Hypothesis]:
        """
        Get detailed hypothesis information.

        Args:
            insights_run_id: Run ID containing the hypothesis
            hypothesis_id: Hypothesis ID

        Returns:
            Hypothesis object or None if not found
        """
        filename = f"hypothesis_{hypothesis_id}.yaml"
        return load_from_yaml(self._mlflow_client, insights_run_id, filename, Hypothesis)

    def get_issue(self, issue_id: str) -> Optional[Issue]:
        """
        Get detailed issue information from any accessible experiment.
        Issues are stored in parent runs, so we search across experiments.

        Args:
            issue_id: Issue ID

        Returns:
            Issue object or None if not found
        """
        # This is a simplified implementation - in production you might want to
        # search across all accessible experiments or maintain an index
        # For now, we'll require the caller to know which experiment the issue is in
        # and use the update_issue pattern to find it

        # Search for parent runs across experiments
        from mlflow.entities import ViewType

        # Get all experiments
        experiments = self._mlflow_client.search_experiments()

        for exp in experiments:
            try:
                # Get parent run for this experiment
                runs = self._mlflow_client.search_runs(
                    experiment_ids=[exp.experiment_id],
                    filter_string="tags.mlflow.insights.type = 'parent'",
                    run_view_type=ViewType.ACTIVE_ONLY,
                    max_results=1,
                )

                if runs:
                    parent_run_id = runs[0].info.run_id
                    filename = f"issue_{issue_id}.yaml"
                    issue = load_from_yaml(self._mlflow_client, parent_run_id, filename, Issue)
                    if issue:
                        return issue
            except Exception:
                continue

        return None

    # =========================================================================
    # Preview Methods
    # =========================================================================

    def preview_hypotheses(self, insights_run_id: str, max_traces: int = 100) -> list[Trace]:
        """
        Get actual trace objects for all hypotheses in a run.

        Args:
            insights_run_id: Run ID of the analysis
            max_traces: Maximum number of traces to return

        Returns:
            List of Trace objects
        """
        # Collect all trace IDs from hypotheses
        all_trace_ids = set()
        hypotheses = self.list_hypotheses(insights_run_id)

        for hypothesis_summary in hypotheses:
            hypothesis = self.get_hypothesis(insights_run_id, hypothesis_summary.hypothesis_id)
            if hypothesis:
                all_trace_ids.update(hypothesis.trace_ids)

        # Limit traces
        trace_ids_to_fetch = list(all_trace_ids)[:max_traces]

        # Fetch traces
        traces = []
        for trace_id in trace_ids_to_fetch:
            try:
                trace = self._mlflow_client.get_trace(trace_id)
                if trace:
                    traces.append(trace)
            except Exception:
                # Skip traces that can't be fetched
                continue

        return traces

    def preview_issues(self, experiment_id: str, max_traces: int = 100) -> list[Trace]:
        """
        Get actual trace objects for all issues in an experiment.

        Args:
            experiment_id: Experiment ID
            max_traces: Maximum number of traces to return

        Returns:
            List of Trace objects
        """
        # Collect all trace IDs from issues
        all_trace_ids = set()
        issues = self.list_issues(experiment_id)

        for issue_summary in issues:
            issue = self.get_issue(issue_summary.issue_id)
            if issue:
                # Extract trace IDs from evidence
                trace_ids = [e.trace_id for e in issue.evidence]
                all_trace_ids.update(trace_ids)

        # Limit traces
        trace_ids_to_fetch = list(all_trace_ids)[:max_traces]

        # Fetch traces
        traces = []
        for trace_id in trace_ids_to_fetch:
            try:
                trace = self._mlflow_client.get_trace(trace_id)
                if trace:
                    traces.append(trace)
            except Exception:
                # Skip traces that can't be fetched
                continue

        return traces
