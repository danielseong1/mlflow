"""
MLflow Insights CLI - Commands for managing analysis, hypotheses, and issues.
"""

import json
import os
from typing import Optional

import click

from mlflow.environment_variables import MLFLOW_EXPERIMENT_ID
from mlflow.insights import InsightsClient
from mlflow.utils.string_utils import _create_table


# Define reusable options
RUN_ID = click.option(
    "--run-id", 
    type=click.STRING, 
    required=True, 
    help="Insights run ID containing the analysis"
)
EXPERIMENT_ID = click.option(
    "--experiment-id",
    envvar=MLFLOW_EXPERIMENT_ID.name,
    type=click.STRING,
    help="Experiment ID. Can be set via MLFLOW_EXPERIMENT_ID env var.",
)


@click.group("insights")
def commands():
    """
    Manage MLflow Insights - Analysis, Hypotheses, and Issues.
    
    Insights provides a structured way to track investigative analyses,
    test hypotheses with traces, and document validated issues.
    """


# ============================================================================
# Creation Commands
# ============================================================================

@commands.command("create-analysis")
@EXPERIMENT_ID
@click.option("--run-name", type=click.STRING, required=True, help="Short name (3-4 words) for the MLflow run")
@click.option("--name", type=click.STRING, required=True, help="Name for the analysis")
@click.option("--description", type=click.STRING, required=True, help="Description of what this analysis is investigating")
def create_analysis(
    experiment_id: Optional[str],
    run_name: str,
    name: str,
    description: str
) -> None:
    """
    Create a new analysis run.
    
    This creates a new MLflow run and initializes it with analysis metadata.
    """
    if not experiment_id:
        raise click.UsageError("--experiment-id is required or set MLFLOW_EXPERIMENT_ID")
    
    # Validate run name is short
    word_count = len(run_name.split())
    if word_count > 5:
        click.echo(f"Warning: Run name '{run_name}' has {word_count} words. Consider using 3-4 words for better display.")
    
    client = InsightsClient()
    
    # Create analysis
    run_id = client.create_analysis(
        experiment_id=experiment_id,
        run_name=run_name,
        name=name,
        description=description
    )
    
    click.echo(f"Created analysis '{name}' with run ID: {run_id}")


@commands.command("create-hypothesis")
@RUN_ID
@click.option("--statement", type=click.STRING, required=True, help="Hypothesis statement to test")
@click.option("--rationale", type=click.STRING, required=True, help="Detailed rationale for the hypothesis")
@click.option("--testing-plan", type=click.STRING, required=True, help="Detailed plan for testing the hypothesis")
@click.option("--evidence", multiple=True, help="Evidence as JSON dict with trace_id, rationale, and supports fields")
def create_hypothesis(
    run_id: str,
    statement: str,
    rationale: str,
    testing_plan: str,
    evidence: tuple[str, ...],
) -> None:
    """
    Create a new hypothesis within an analysis.

    Example:
        mlflow insights create-hypothesis \\
            --run-id abc123 \\
            --statement "Database locks cause timeouts" \\
            --rationale "Investigation into database connection timeouts" \\
            --testing-plan "Search for traces with timeout errors..." \\
            --evidence '{"trace_id": "tr-001", "rationale": "Shows lock timeout", "supports": true}' \\
            --evidence '{"trace_id": "tr-002", "rationale": "No DB involvement", "supports": false}' \\
    """
    client = InsightsClient()

    # Parse evidence JSON
    evidence_list = []
    for ev_str in evidence:
        try:
            ev = json.loads(ev_str)
            evidence_list.append(ev)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"Invalid JSON in evidence: {ev_str}. Error: {e}")

    # Create hypothesis
    hypothesis_id = client.create_hypothesis(
        insights_run_id=run_id,
        statement=statement,
        rationale=rationale,
        testing_plan=testing_plan,
        evidence=evidence_list if evidence_list else None,
    )

    click.echo(f"Created hypothesis with ID: {hypothesis_id}")
    if evidence_list:
        click.echo(f"Added {len(evidence_list)} evidence entries")


@commands.command("create-issue")
@RUN_ID
@click.option("--title", type=click.STRING, required=True, help="Issue title")
@click.option("--description", type=click.STRING, required=True, help="Issue description")
@click.option("--severity", type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), required=True, help="Issue severity")
@click.option("--hypothesis-id", type=click.STRING, help="Source hypothesis ID if validated from hypothesis")
@click.option("--evidence", multiple=True, help="Evidence as JSON dict with trace_id and rationale fields")
def create_issue(
    run_id: str,
    title: str,
    description: str,
    severity: str,
    hypothesis_id: Optional[str],
    evidence: tuple[str, ...]
) -> None:
    """
    Create a validated issue.
    
    Example:
        mlflow insights create-issue \\
            --run-id abc123 \\
            --title "Database Connection Pool Exhaustion" \\
            --description "Pool size too small for peak traffic" \\
            --severity HIGH \\
            --hypothesis-id xyz789 \\
            --evidence '{"trace_id": "tr-001", "rationale": "Shows 45s delay acquiring connection"}' \\
            --evidence '{"trace_id": "tr-002", "rationale": "Connection timeout after 30s wait"}'
    """
    client = InsightsClient()
    
    # Parse evidence JSON
    evidence_list = []
    for ev_str in evidence:
        try:
            ev = json.loads(ev_str)
            evidence_list.append(ev)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"Invalid JSON in evidence: {ev_str}. Error: {e}")
    
    # Create issue
    issue_id = client.create_issue(
        insights_run_id=run_id,
        title=title,
        description=description,
        severity=severity,
        hypothesis_id=hypothesis_id,
        evidence=evidence_list if evidence_list else None
    )
    
    click.echo(f"Created issue with ID: {issue_id}")
    click.echo(f"Title: {title}")
    click.echo(f"Severity: {severity}")
    if evidence_list:
        click.echo(f"Added {len(evidence_list)} evidence entries")


@commands.command("create-baseline-census")
@RUN_ID
@click.option("--table-name", envvar="MLFLOW_TRACE_TABLE_NAME", type=click.STRING, help="Name of the trace table to analyze. Can be set via MLFLOW_TRACE_TABLE_NAME env var.")
def create_baseline_census(
    run_id: str,
    table_name: str
) -> None:
    """
    Create a baseline census from trace analysis data.

    This command analyzes a trace table and generates a comprehensive baseline
    census YAML file containing performance metrics, error categories, and trends.

    Examples:
        # Using command line argument
        mlflow insights create-baseline-census \\
            --run-id abc123 \\
            --table-name ds_fs.agent_quality.sample_agent_trace_archival

        # Using environment variable
        export MLFLOW_TRACE_TABLE_NAME=ds_fs.agent_quality.sample_agent_trace_archival
        mlflow insights create-baseline-census --run-id abc123
    """
    if not table_name:
        raise click.UsageError("--table-name is required or set MLFLOW_TRACE_TABLE_NAME env var")

    client = InsightsClient()

    try:
        # Create baseline census
        filename = client.create_baseline_census(
            insights_run_id=run_id,
            table_name=table_name
        )

        click.echo(f"Created baseline census: {filename}")
        click.echo(f"Run ID: {run_id}")
        click.echo(f"Table: {table_name}")

    except Exception as e:
        click.echo(f"Error creating baseline census: {e}", err=True)
        raise click.Abort()


# ============================================================================
# Update Commands
# ============================================================================

@commands.command("update-analysis")
@RUN_ID
@click.option("--name", type=click.STRING, help="Update analysis name")
@click.option("--description", type=click.STRING, help="Update analysis description")
@click.option("--status", type=click.Choice(["ACTIVE", "COMPLETED", "ARCHIVED"]), help="Update analysis status")
def update_analysis(
    run_id: str,
    name: Optional[str],
    description: Optional[str],
    status: Optional[str]
) -> None:
    """
    Update an existing analysis.
    """
    client = InsightsClient()
    
    client.update_analysis(
        run_id=run_id,
        name=name,
        description=description,
        status=status
    )
    
    click.echo(f"Updated analysis in run {run_id}")


@commands.command("update-hypothesis")
@RUN_ID
@click.option("--hypothesis-id", type=click.STRING, required=True, help="Hypothesis ID to update")
@click.option("--status", type=click.Choice(["TESTING", "VALIDATED", "REJECTED"]), help="Update hypothesis status")
@click.option("--rationale", type=click.STRING, help="Update hypothesis rationale")
@click.option("--evidence", multiple=True, help="Additional evidence as JSON dict")
@click.option("--testing-plan", type=click.STRING, help="Update testing plan")
def update_hypothesis(
    run_id: str,
    hypothesis_id: str,
    status: Optional[str],
    rationale: Optional[str],
    evidence: tuple[str, ...],
    testing_plan: Optional[str]
) -> None:
    """
    Update an existing hypothesis.

    Example:
        mlflow insights update-hypothesis \\
            --run-id abc123 \\
            --hypothesis-id xyz789 \\
            --status VALIDATED \\
            --rationale "Updated investigation details" \\
            --evidence '{"trace_id": "tr-003", "rationale": "Additional evidence", "supports": true}' \\
    """
    client = InsightsClient()

    # Parse evidence JSON
    evidence_list = []
    for ev_str in evidence:
        try:
            ev = json.loads(ev_str)
            evidence_list.append(ev)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"Invalid JSON in evidence: {ev_str}. Error: {e}")

    client.update_hypothesis(
        insights_run_id=run_id,
        hypothesis_id=hypothesis_id,
        status=status,
        rationale=rationale,
        evidence=evidence_list if evidence_list else None,
        testing_plan=testing_plan
    )

    click.echo(f"Updated hypothesis {hypothesis_id}")
    if evidence_list:
        click.echo(f"Added {len(evidence_list)} new evidence entries")


@commands.command("update-issue")
@RUN_ID
@click.option("--issue-id", type=click.STRING, required=True, help="Issue ID to update")
@click.option("--severity", type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), help="Update severity")
@click.option("--status", type=click.Choice(["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]), help="Update status")
@click.option("--evidence", multiple=True, help="Additional evidence as JSON dict")
@click.option("--resolution", type=click.STRING, help="Resolution description (marks as resolved)")
def update_issue(
    run_id: str,
    issue_id: str,
    severity: Optional[str],
    status: Optional[str],
    evidence: tuple[str, ...],
    resolution: Optional[str]
) -> None:
    """
    Update an existing issue.
    
    Example:
        mlflow insights update-issue \\
            --run-id abc123 \\
            --issue-id def456 \\
            --status RESOLVED \\
            --resolution "Increased pool size from 10 to 50"
    """
    client = InsightsClient()
    
    # Parse evidence JSON
    evidence_list = []
    for ev_str in evidence:
        try:
            ev = json.loads(ev_str)
            evidence_list.append(ev)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"Invalid JSON in evidence: {ev_str}. Error: {e}")
    
    client.update_issue(
        insights_run_id=run_id,
        issue_id=issue_id,
        severity=severity,
        status=status,
        evidence=evidence_list if evidence_list else None,
        resolution=resolution
    )
    
    click.echo(f"Updated issue {issue_id}")
    if evidence_list:
        click.echo(f"Added {len(evidence_list)} new evidence entries")


# ============================================================================
# Read Commands
# ============================================================================

@commands.command("list-analyses")
@EXPERIMENT_ID
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def list_analyses(experiment_id: Optional[str], output: str) -> None:
    """
    List all analysis runs in an experiment.
    """
    if not experiment_id:
        raise click.UsageError("--experiment-id is required or set MLFLOW_EXPERIMENT_ID")
    
    client = InsightsClient()
    
    # Get all analysis summaries
    analyses = client.list_analyses(experiment_id=experiment_id)
    
    if output == "json":
        # JSON output
        data = [summary.model_dump(mode="json") for summary in analyses]
        click.echo(json.dumps(data, indent=2))
    else:
        # Table output
        if not analyses:
            click.echo("No analyses found.")
            return
        
        table = []
        for a in analyses:
            table.append([
                a.run_id[:8] + "...",
                a.name[:30] + "..." if len(a.name) > 30 else a.name,
                a.status.value,
                str(a.hypothesis_count),
                a.created_at.strftime("%Y-%m-%d %H:%M"),
            ])
        
        headers = ["Run ID", "Name", "Status", "Hypotheses", "Created"]
        click.echo(_create_table(table, headers=headers))


@commands.command("list-hypotheses")
@RUN_ID
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def list_hypotheses(run_id: str, output: str) -> None:
    """
    List all hypotheses in an analysis run.
    """
    client = InsightsClient()
    
    hypotheses = client.list_hypotheses(insights_run_id=run_id)
    
    if output == "json":
        data = [h.model_dump(mode="json") for h in hypotheses]
        click.echo(json.dumps(data, indent=2))
    else:
        if not hypotheses:
            click.echo("No hypotheses found.")
            return
        
        table = []
        for h in hypotheses:
            # Calculate support stats
            supports = h.supports_count if hasattr(h, 'supports_count') else 0
            refutes = h.refutes_count if hasattr(h, 'refutes_count') else 0
            evidence_str = f"+{supports}/-{refutes}" if (supports or refutes) else str(h.evidence_count)

            table.append([
                h.hypothesis_id[:8] + "...",
                h.statement[:30] + "..." if len(h.statement) > 30 else h.statement,
                h.status.value,
                str(h.trace_count),
                evidence_str,
            ])

        headers = ["ID", "Statement", "Status", "Traces", "Evidence"]
        click.echo(_create_table(table, headers=headers))


@commands.command("list-issues")
@EXPERIMENT_ID
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def list_issues(experiment_id: Optional[str], output: str) -> None:
    """
    List all issues in an experiment (sorted by trace count).
    """
    if not experiment_id:
        raise click.UsageError("--experiment-id is required or set MLFLOW_EXPERIMENT_ID")
    
    client = InsightsClient()
    
    issues = client.list_issues(experiment_id=experiment_id)
    
    if output == "json":
        data = [i.model_dump(mode="json") for i in issues]
        click.echo(json.dumps(data, indent=2))
    else:
        if not issues:
            click.echo("No issues found.")
            return
        
        table = []
        for i in issues:
            table.append([
                i.issue_id[:8] + "...",
                i.title[:35] + "..." if len(i.title) > 35 else i.title,
                i.severity.value,
                i.status.value,
                str(i.trace_count),
            ])
        
        headers = ["ID", "Title", "Severity", "Status", "Traces"]
        click.echo(_create_table(table, headers=headers))


@commands.command("get-analysis")
@RUN_ID
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def get_analysis(run_id: str, output: str) -> None:
    """
    Get analysis details for a run.
    """
    client = InsightsClient()
    
    analysis = client.get_analysis(insights_run_id=run_id)
    if not analysis:
        raise click.ClickException(f"No analysis found in run {run_id}")
    
    if output == "json":
        click.echo(json.dumps(analysis.model_dump(mode="json"), indent=2))
    else:
        # Table output
        click.echo(f"\nAnalysis: {analysis.name}")
        click.echo(f"Status: {analysis.status.value}")
        click.echo(f"Description: {analysis.description}")
        click.echo(f"Created: {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated: {analysis.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if analysis.metadata:
            click.echo(f"Metadata: {json.dumps(analysis.metadata, indent=2)}")


@commands.command("get-hypothesis")
@RUN_ID
@click.option("--hypothesis-id", type=click.STRING, required=True, help="Hypothesis ID")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def get_hypothesis(run_id: str, hypothesis_id: str, output: str) -> None:
    """
    Get specific hypothesis details.
    """
    client = InsightsClient()
    
    hypothesis = client.get_hypothesis(insights_run_id=run_id, hypothesis_id=hypothesis_id)
    if not hypothesis:
        raise click.ClickException(f"Hypothesis {hypothesis_id} not found in run {run_id}")
    
    if output == "json":
        click.echo(json.dumps(hypothesis.model_dump(mode="json"), indent=2))
    else:
        click.echo(f"\nHypothesis ID: {hypothesis.hypothesis_id}")
        click.echo(f"Statement: {hypothesis.statement}")
        click.echo(f"Rationale: {hypothesis.rationale}")
        click.echo(f"Testing Plan: {hypothesis.testing_plan}")
        click.echo(f"Status: {hypothesis.status.value}")
        click.echo(f"Traces: {hypothesis.trace_count}")
        click.echo(f"Created: {hypothesis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated: {hypothesis.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if hypothesis.evidence:
            click.echo(f"\nEvidence ({len(hypothesis.evidence)} entries):")
            for i, ev in enumerate(hypothesis.evidence[:5], 1):
                support_str = "✓ supports" if ev.supports else "✗ refutes" if ev.supports is False else "○ neutral"
                click.echo(f"  {i}. [{support_str}] {ev.trace_id}: {ev.rationale[:60]}...")
            if len(hypothesis.evidence) > 5:
                click.echo(f"  ... and {len(hypothesis.evidence) - 5} more")

        if hypothesis.metrics:
            click.echo(f"\nMetrics: {json.dumps(hypothesis.metrics, indent=2)}")


@commands.command("get-issue")
@click.option("--issue-id", type=click.STRING, required=True, help="Issue ID")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def get_issue(issue_id: str, output: str) -> None:
    """
    Get specific issue details.
    """
    client = InsightsClient()
    
    issue = client.get_issue(issue_id=issue_id)
    if not issue:
        raise click.ClickException(f"Issue {issue_id} not found")
    
    if output == "json":
        click.echo(json.dumps(issue.model_dump(mode="json"), indent=2))
    else:
        click.echo(f"\nIssue ID: {issue.issue_id}")
        click.echo(f"Title: {issue.title}")
        click.echo(f"Description: {issue.description}")
        click.echo(f"Severity: {issue.severity.value}")
        click.echo(f"Status: {issue.status.value}")
        click.echo(f"Source Run: {issue.source_run_id}")
        click.echo(f"Traces: {len(issue.trace_ids)}")
        click.echo(f"Created: {issue.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated: {issue.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if issue.hypothesis_id:
            click.echo(f"Source Hypothesis: {issue.hypothesis_id}")
        
        if issue.evidence:
            click.echo(f"\nEvidence ({len(issue.evidence)} entries):")
            for i, ev in enumerate(issue.evidence[:5], 1):
                click.echo(f"  {i}. {ev.trace_id}: {ev.rationale[:60]}...")
            if len(issue.evidence) > 5:
                click.echo(f"  ... and {len(issue.evidence) - 5} more")
        
        if issue.resolution:
            click.echo(f"\nResolution: {issue.resolution}")


# ============================================================================
# Preview Commands
# ============================================================================

@commands.command("preview-hypotheses")
@RUN_ID
@click.option("--max-traces", type=click.INT, default=100, help="Maximum traces to fetch")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def preview_hypotheses(run_id: str, max_traces: int, output: str) -> None:
    """
    Preview traces for all hypotheses in a run.
    """
    client = InsightsClient()
    
    # Get traces for all hypotheses
    traces = client.preview_hypotheses(
        insights_run_id=run_id,
        max_traces=max_traces
    )
    
    if output == "json":
        # Output trace IDs and basic info
        data = []
        for trace in traces:
            data.append({
                "trace_id": trace.info.request_id,
                "status": trace.info.status,
                "timestamp": trace.info.timestamp,
                "execution_time": trace.info.execution_time,
            })
        click.echo(json.dumps(data, indent=2))
    else:
        if not traces:
            click.echo("No traces found for hypotheses.")
            return
        
        click.echo(f"\nFound {len(traces)} traces across all hypotheses (max: {max_traces})")
        
        # Show sample traces
        table = []
        for trace in traces[:10]:
            status = trace.info.status if trace.info.status else "UNKNOWN"
            exec_time = f"{trace.info.execution_time:.0f}ms" if trace.info.execution_time else "N/A"
            
            table.append([
                trace.info.request_id[:12] + "...",
                status,
                exec_time,
            ])
        
        headers = ["Trace ID", "Status", "Execution Time"]
        click.echo(_create_table(table, headers=headers))
        
        if len(traces) > 10:
            click.echo(f"\n... and {len(traces) - 10} more traces")


# ============================================================================
# Baseline Census Commands
# ============================================================================

@commands.command("get-baseline-census")
@RUN_ID
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def get_baseline_census(run_id: str, output: str) -> None:
    """
    Get baseline census details for a run.

    Example:
        mlflow insights get-baseline-census --run-id abc123
    """
    client = InsightsClient()

    census = client.get_baseline_census(insights_run_id=run_id)
    if not census:
        raise click.ClickException(f"No baseline census found in run {run_id}")

    if output == "json":
        click.echo(json.dumps(census.model_dump(mode="json"), indent=2))
    else:
        # Table output
        click.echo(f"\nBaseline Census for Run: {run_id}")
        click.echo("=" * 50)
        click.echo(f"Table: {census.metadata.table_name}")
        click.echo(f"Created: {census.metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Time Range: {census.operational_metrics.first_trace_timestamp} to {census.operational_metrics.last_trace_timestamp}")
        click.echo()

        # Basic counts
        click.echo("TRACE COUNTS:")
        click.echo(f"  Total Traces: {census.operational_metrics.total_traces}")
        click.echo(f"  OK Count: {census.operational_metrics.ok_count}")
        click.echo(f"  Error Count: {census.operational_metrics.error_count}")
        click.echo(f"  Error Rate: {census.operational_metrics.error_rate}%")
        click.echo()

        # Latency metrics
        click.echo("LATENCY METRICS (ms):")
        click.echo(f"  P50: {census.operational_metrics.p50_latency_ms}")
        click.echo(f"  P90: {census.operational_metrics.p90_latency_ms}")
        click.echo(f"  P95: {census.operational_metrics.p95_latency_ms}")
        click.echo(f"  P99: {census.operational_metrics.p99_latency_ms}")
        click.echo(f"  Max: {census.operational_metrics.max_latency_ms}")
        click.echo()

        # Top error categories
        if census.operational_metrics.top_error_spans:
            click.echo("TOP ERROR CATEGORIES:")
            for error in census.operational_metrics.top_error_spans[:5]:
                click.echo(f"  {error.get('error_span_name', 'Unknown')}: {error.get('count', 0)} ({error.get('pct_of_errors', 0)}%)")
            click.echo()

        # Top slow tools
        if census.operational_metrics.top_slow_tools:
            click.echo("TOP SLOW TOOLS:")
            for tool in census.operational_metrics.top_slow_tools[:5]:
                click.echo(f"  {tool.get('tool_span_name', 'Unknown')}: P95={tool.get('p95_latency_ms', 0)}ms, Count={tool.get('count', 0)}")
            click.echo()

        # Time buckets
        if census.operational_metrics.time_buckets:
            click.echo(f"TIME BUCKETS ({len(census.operational_metrics.time_buckets)} total):")
            for bucket in census.operational_metrics.time_buckets[:3]:
                click.echo(f"  {bucket.get('time_bucket', 'Unknown')}: {bucket.get('total_traces', 0)} traces, {bucket.get('error_rate', 0)}% error rate")
            if len(census.operational_metrics.time_buckets) > 3:
                click.echo(f"  ... and {len(census.operational_metrics.time_buckets) - 3} more buckets")


@commands.command("update-baseline-census")
@RUN_ID
@click.option("--table-name", envvar="MLFLOW_TRACE_TABLE_NAME", type=click.STRING, help="Update the table name for the census. Can be set via MLFLOW_TRACE_TABLE_NAME env var.")
@click.option("--metadata", type=click.STRING, help="Additional metadata as JSON string")
@click.option("--regenerate", is_flag=True, help="Regenerate all census data from the table (requires --table-name)")
def update_baseline_census(
    run_id: str,
    table_name: Optional[str],
    metadata: Optional[str],
    regenerate: bool
) -> None:
    """
    Update an existing baseline census.

    Examples:
        # Update metadata
        mlflow insights update-baseline-census \\
            --run-id abc123 \\
            --metadata '{"environment": "production", "version": "1.2.0"}'

        # Regenerate entire census with new table
        mlflow insights update-baseline-census \\
            --run-id abc123 \\
            --table-name new_table_name \\
            --regenerate
    """
    client = InsightsClient()

    try:
        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError as e:
                raise click.UsageError(f"Invalid JSON in metadata: {metadata}. Error: {e}")

        # Validate regenerate flag
        if regenerate and not table_name:
            raise click.UsageError("--regenerate requires --table-name to be specified")

        # Update census
        filename = client.update_baseline_census(
            insights_run_id=run_id,
            table_name=table_name,
            metadata=metadata_dict,
            regenerate=regenerate
        )

        click.echo(f"Updated baseline census: {filename}")
        click.echo(f"Run ID: {run_id}")
        if table_name:
            click.echo(f"Table: {table_name}")
        if regenerate:
            click.echo("Regenerated all census data")
        if metadata_dict:
            click.echo(f"Added metadata: {list(metadata_dict.keys())}")

    except Exception as e:
        click.echo(f"Error updating baseline census: {e}", err=True)
        raise click.Abort()


@commands.command("preview-issues")
@EXPERIMENT_ID
@click.option("--max-traces", type=click.INT, default=100, help="Maximum traces to fetch")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", help="Output format")
def preview_issues(experiment_id: Optional[str], max_traces: int, output: str) -> None:
    """
    Preview traces for all issues in an experiment.
    """
    if not experiment_id:
        raise click.UsageError("--experiment-id is required or set MLFLOW_EXPERIMENT_ID")
    
    client = InsightsClient()
    
    # Get traces for all issues
    traces = client.preview_issues(
        experiment_id=experiment_id,
        max_traces=max_traces
    )
    
    if output == "json":
        # Output trace IDs and basic info
        data = []
        for trace in traces:
            data.append({
                "trace_id": trace.info.request_id,
                "status": trace.info.status,
                "timestamp": trace.info.timestamp,
                "execution_time": trace.info.execution_time,
            })
        click.echo(json.dumps(data, indent=2))
    else:
        if not traces:
            click.echo("No traces found for issues.")
            return
        
        click.echo(f"\nFound {len(traces)} traces across all issues (max: {max_traces})")
        
        # Calculate statistics
        error_traces = [t for t in traces if t.info.status == "ERROR"]
        error_rate = (len(error_traces) / len(traces) * 100) if traces else 0
        
        click.echo(f"Error Rate: {error_rate:.1f}%")
        
        # Show sample traces
        table = []
        for trace in traces[:10]:
            status = trace.info.status if trace.info.status else "UNKNOWN"
            exec_time = f"{trace.info.execution_time:.0f}ms" if trace.info.execution_time else "N/A"
            
            table.append([
                trace.info.request_id[:12] + "...",
                status,
                exec_time,
            ])
        
        headers = ["Trace ID", "Status", "Execution Time"]
        click.echo(_create_table(table, headers=headers))
        
        if len(traces) > 10:
            click.echo(f"\n... and {len(traces) - 10} more traces")


# ============================================================================
# Baseline Census Commands
# ============================================================================

@commands.command("get-baseline-census")
@RUN_ID
@click.option("--output", type=click.Choice(["json"]), default="json", help="Output format")
def get_baseline_census(run_id: str, output: str) -> None:
    """
    Get baseline census details for a run.

    Example:
        mlflow insights get-baseline-census --run-id abc123
    """
    client = InsightsClient()

    census = client.get_baseline_census(insights_run_id=run_id)
    if not census:
        raise click.ClickException(f"No baseline census found in run {run_id}")

    if output == "json":
        click.echo(json.dumps(census.model_dump(mode="json"), indent=2))
    

@commands.command("update-baseline-census")
@RUN_ID
@click.option("--table-name", envvar="MLFLOW_TRACE_TABLE_NAME", type=click.STRING, help="Update the table name for the census. Can be set via MLFLOW_TRACE_TABLE_NAME env var.")
@click.option("--metadata", type=click.STRING, help="Additional metadata as JSON string")
@click.option("--regenerate", is_flag=True, help="Regenerate all census data from the table (requires --table-name)")
def update_baseline_census(
    run_id: str,
    table_name: Optional[str],
    metadata: Optional[str],
    regenerate: bool
) -> None:
    """
    Update an existing baseline census.

    Examples:
        # Update metadata
        mlflow insights update-baseline-census \\
            --run-id abc123 \\
            --metadata '{"environment": "production", "version": "1.2.0"}'

        # Regenerate entire census with new table
        mlflow insights update-baseline-census \\
            --run-id abc123 \\
            --table-name new_table_name \\
            --regenerate
    """
    client = InsightsClient()

    try:
        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError as e:
                raise click.UsageError(f"Invalid JSON in metadata: {metadata}. Error: {e}")

        # Validate regenerate flag
        if regenerate and not table_name:
            raise click.UsageError("--regenerate requires --table-name to be specified")

        # Update census
        filename = client.update_baseline_census(
            insights_run_id=run_id,
            table_name=table_name,
            metadata=metadata_dict,
            regenerate=regenerate
        )

        click.echo(f"Updated baseline census: {filename}")
        click.echo(f"Run ID: {run_id}")
        if table_name:
            click.echo(f"Table: {table_name}")
        if regenerate:
            click.echo("Regenerated all census data")
        if metadata_dict:
            click.echo(f"Added metadata: {list(metadata_dict.keys())}")

    except Exception as e:
        click.echo(f"Error updating baseline census: {e}", err=True)
        raise click.Abort()