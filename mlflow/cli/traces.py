"""
Comprehensive MLflow Traces CLI for managing trace data, assessments, and metadata.

This module provides a complete command-line interface for working with MLflow traces,
including search, retrieval, deletion, tagging, and assessment management. It supports
both table and JSON output formats with flexible field selection capabilities.

AVAILABLE COMMANDS:
    search              Search traces with filtering, sorting, and field selection
    get                 Retrieve detailed trace information as JSON
    delete              Delete traces by ID or timestamp criteria
    set-tag             Add tags to traces
    delete-tag          Remove tags from traces
    log-feedback        Log evaluation feedback/scores to traces
    log-expectation     Log ground truth expectations to traces
    get-assessment      Retrieve assessment details
    update-assessment   Modify existing assessments
    delete-assessment   Remove assessments from traces

EXAMPLE USAGE:
    # Search traces across multiple experiments
    mlflow traces search --experiment-ids 1,2,3 --max-results 50

    # Filter traces by status and timestamp
    mlflow traces search --experiment-ids 1 \
        --filter-string "status = 'OK' AND timestamp_ms > 1700000000000"

    # Get specific fields in JSON format
    mlflow traces search --experiment-ids 1 \
        --extract-fields "info.trace_id,info.assessments.*,data.spans.*.name" \
        --output json

    # Extract trace names (using backticks for dots in field names)
    mlflow traces search --experiment-ids 1 \
        --extract-fields "info.trace_id,info.tags.`mlflow.traceName`" \
        --output json

    # Get full trace details
    mlflow traces get --trace-id tr-1234567890abcdef

    # Log feedback to a trace
    mlflow traces log-feedback --trace-id tr-abc123 \
        --name relevance --value 0.9 \
        --source-type HUMAN --source-id reviewer@example.com \
        --rationale "Highly relevant response"

    # Delete old traces
    mlflow traces delete --experiment-ids 1 \
        --max-timestamp-millis 1700000000000 --max-traces 100

    # Add custom tags
    mlflow traces set-tag --trace-id tr-abc123 \
        --key environment --value production

ASSESSMENT TYPES:
    • Feedback: Evaluation scores, ratings, or judgments
    • Expectations: Ground truth labels or expected outputs
    • Sources: HUMAN, LLM_JUDGE, or CODE with source identification

For detailed help on any command, use:
    mlflow traces COMMAND --help
"""

import json

import click
from mlflow.entities import AssessmentSource, AssessmentSourceType
from mlflow.environment_variables import MLFLOW_EXPERIMENT_ID
from mlflow.tracing.assessment import (
    log_expectation as _log_expectation,
)
from mlflow.tracing.assessment import (
    log_feedback as _log_feedback,
)
from mlflow.tracing.client import TracingClient
from mlflow.utils.jsonpath_utils import (
    filter_json_by_fields,
    jsonpath_extract_values,
    validate_field_paths,
)
from mlflow.utils.string_utils import _create_table, format_table_cell_value

# Define reusable options following mlflow/runs.py pattern
EXPERIMENT_ID = click.option(
    "--experiment-id",
    "-x",
    envvar=MLFLOW_EXPERIMENT_ID.name,
    type=click.STRING,
    required=True,
    help="Experiment ID to search within. Can be set via MLFLOW_EXPERIMENT_ID env var.",
)
TRACE_ID = click.option("--trace-id", type=click.STRING, required=True)


@click.group("traces")
def commands():
    """
    Manage traces. To manage traces associated with a tracking server, set the
    MLFLOW_TRACKING_URI environment variable to the URL of the desired server.

    TRACE SCHEMA:
    info.trace_id                           # Unique trace identifier
    info.experiment_id                      # MLflow experiment ID
    info.request_time                       # Request timestamp (milliseconds)
    info.execution_duration                 # Total execution time (milliseconds)
    info.state                              # Trace status: OK, ERROR, etc.
    info.client_request_id                  # Optional client-provided request ID
    info.request_preview                    # Truncated request preview
    info.response_preview                   # Truncated response preview
    info.trace_metadata.mlflow.*           # MLflow-specific metadata
    info.trace_metadata.*                  # Custom metadata fields
    info.tags.mlflow.traceName             # Trace name tag
    info.tags.<key>                         # Custom tags
    info.assessments.*.assessment_id        # Assessment identifiers
    info.assessments.*.feedback.name        # Feedback names
    info.assessments.*.feedback.value       # Feedback scores/values
    info.assessments.*.feedback.rationale   # Feedback explanations
    info.assessments.*.expectation.name     # Ground truth names
    info.assessments.*.expectation.value    # Expected values
    info.assessments.*.source.source_type   # HUMAN, LLM_JUDGE, CODE
    info.assessments.*.source.source_id     # Source identifier
    info.token_usage                        # Token usage (property, not searchable via fields)
    data.spans.*.span_id                    # Individual span IDs
    data.spans.*.name                       # Span operation names
    data.spans.*.parent_id                  # Parent span relationships
    data.spans.*.start_time                 # Span start timestamps
    data.spans.*.end_time                   # Span end timestamps
    data.spans.*.status_code                # Span status codes
    data.spans.*.attributes.mlflow.spanType # AGENT, TOOL, LLM, etc.
    data.spans.*.attributes.<key>           # Custom span attributes
    data.spans.*.events.*.name              # Event names
    data.spans.*.events.*.timestamp         # Event timestamps
    data.spans.*.events.*.attributes.<key>  # Event attributes

    For additional details, see:
    https://mlflow.org/docs/latest/genai/tracing/concepts/trace/#traceinfo-metadata-and-context

    \b
    FIELD SELECTION:
    Use --extract-fields with dot notation to select specific fields.

    \b
    Examples:
      info.trace_id                           # Single field
      info.assessments.*                      # All assessment data
      info.assessments.*.feedback.value       # Just feedback scores
      info.assessments.*.source.source_type   # Assessment sources
      info.trace_metadata.mlflow.traceInputs  # Original inputs
      info.trace_metadata.mlflow.source.type  # Source type
      info.tags.`mlflow.traceName`            # Trace name (backticks for dots)
      data.spans.*                            # All span data
      data.spans.*.name                       # Span operation names
      data.spans.*.attributes.mlflow.spanType # Span types
      data.spans.*.events.*.name              # Event names
      info.trace_id,info.state,info.execution_duration  # Multiple fields
    """


@commands.command("search")
@EXPERIMENT_ID
@click.option(
    "--filter-string",
    type=click.STRING,
    help="""Filter string for trace search.

Examples:
- Filter by run ID: "run_id = '123abc'"
- Filter by status: "status = 'OK'"
- Filter by timestamp: "timestamp_ms > 1700000000000"
- Filter by metadata: "metadata.`mlflow.modelId` = 'model123'"
- Filter by tags: "tags.environment = 'production'"
- Multiple conditions: "run_id = '123' AND status = 'OK'"

Available fields:
- run_id: Associated MLflow run ID
- status: Trace status (OK, ERROR, etc.)
- timestamp_ms: Trace timestamp in milliseconds
- execution_time_ms: Trace execution time in milliseconds
- name: Trace name
- metadata.<key>: Custom metadata fields (use backticks for keys with dots)
- tags.<key>: Custom tag fields""",
)
@click.option(
    "--max-results",
    type=click.INT,
    default=100,
    help="Maximum number of traces to return (default: 100)",
)
@click.option(
    "--order-by",
    type=click.STRING,
    help="Comma-separated list of fields to order by (e.g., 'timestamp_ms DESC, status')",
)
@click.option("--page-token", type=click.STRING, help="Token for pagination from previous search")
@click.option(
    "--run-id",
    type=click.STRING,
    help="Filter traces by run ID (convenience option, adds to filter-string)",
)
@click.option(
    "--include-spans/--no-include-spans",
    default=True,
    help="Include span data in results (default: include)",
)
@click.option("--model-id", type=click.STRING, help="Filter traces by model ID")
@click.option(
    "--sql-warehouse-id",
    type=click.STRING,
    help="SQL warehouse ID for searching inference tables (Databricks only)",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format: 'table' for formatted table (default) or 'json' for JSON format",
)
@click.option(
    "--extract-fields",
    type=click.STRING,
    help="Filter and select specific fields using dot notation. "
    'Examples: "info.trace_id", "info.assessments.*", "data.spans.*.name". '
    'For field names with dots, use backticks: "info.tags.`mlflow.traceName`". '
    "Comma-separated for multiple fields. "
    "Defaults to standard columns for table mode, all fields for JSON mode.",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show all available fields in error messages when invalid fields are specified.",
)
def search_traces(
    experiment_id: str,
    filter_string: str | None,
    max_results: int,
    order_by: str | None,
    page_token: str | None,
    run_id: str | None,
    include_spans: bool,
    model_id: str | None,
    sql_warehouse_id: str | None,
    output: str,
    extract_fields: str | None,
    verbose: bool,
) -> None:
    """
    Search for traces in the specified experiment.

    Examples:

    \b
    # Search all traces in experiment 1
    mlflow traces search --experiment-id 1

    \b
    # Using environment variable
    export MLFLOW_EXPERIMENT_ID=1
    mlflow traces search --max-results 50

    \b
    # Filter traces by run ID
    mlflow traces search --experiment-id 1 --run-id abc123def

    \b
    # Use filter string for complex queries
    mlflow traces search --experiment-id 1 \\
        --filter-string "run_id = 'abc123' AND timestamp_ms > 1700000000000"

    \b
    # Order results and use pagination
    mlflow traces search --experiment-id 1 \\
        --order-by "timestamp_ms DESC" \\
        --max-results 10 \\
        --page-token <token_from_previous>

    \b
    # Search without span data (faster for metadata-only queries)
    mlflow traces search --experiment-id 1 --no-include-spans
    """
    client = TracingClient()
    order_by_list = order_by.split(",") if order_by else None

    traces = client.search_traces(
        experiment_ids=[experiment_id],
        filter_string=filter_string,
        max_results=max_results,
        order_by=order_by_list,
        page_token=page_token,
        run_id=run_id,
        include_spans=include_spans,
        model_id=model_id,
        sql_warehouse_id=sql_warehouse_id,
    )

    # Determine which fields to show
    if extract_fields:
        field_list = [f.strip() for f in extract_fields.split(",")]
        # Validate fields against actual trace data
        if traces:
            try:
                validate_field_paths(field_list, traces[0].to_dict(), verbose=verbose)
            except ValueError as e:
                raise click.UsageError(str(e))
    elif output == "json":
        # JSON mode defaults to all fields (full trace data)
        field_list = None  # Will output full JSON
    else:
        # Table mode defaults to standard columns
        field_list = [
            "info.trace_id",
            "info.request_time",
            "info.state",
            "info.execution_duration",
            "info.request_preview",
            "info.response_preview",
        ]

    if output == "json":
        if field_list is None:
            # Full JSON output
            result = {
                "traces": [trace.to_dict() for trace in traces],
                "next_page_token": traces.token,
            }
        else:
            # Custom fields JSON output - filter original structure
            traces_data = []
            for trace in traces:
                trace_dict = trace.to_dict()
                filtered_trace = filter_json_by_fields(trace_dict, field_list)
                traces_data.append(filtered_trace)
            result = {"traces": traces_data, "next_page_token": traces.token}
        click.echo(json.dumps(result, indent=2))
    else:
        # Table output format
        table = []
        for trace in traces:
            trace_dict = trace.to_dict()
            row = []

            for field in field_list:
                values = jsonpath_extract_values(trace_dict, field)
                cell_value = format_table_cell_value(field, None, values)
                row.append(cell_value)

            table.append(row)

        click.echo(_create_table(table, headers=field_list))

        if traces.token:
            click.echo(f"\nNext page token: {traces.token}")


@commands.command("get")
@TRACE_ID
@click.option(
    "--extract-fields",
    type=click.STRING,
    help="Filter and select specific fields using dot notation. "
    "Examples: 'info.trace_id', 'info.assessments.*', 'data.spans.*.name'. "
    "Comma-separated for multiple fields. "
    "If not specified, returns all trace data.",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show all available fields in error messages when invalid fields are specified.",
)
def get_trace(trace_id: str, extract_fields: str | None, verbose: bool) -> None:
    """
    All trace details will print to stdout as JSON format.

    \b
    Examples:
    # Get full trace
    mlflow traces get --trace-id tr-1234567890abcdef

    \b
    # Get specific fields only
    mlflow traces get --trace-id tr-1234567890abcdef \\
        --extract-fields "info.trace_id,info.assessments.*,data.spans.*.name"
    """
    client = TracingClient()
    trace = client.get_trace(trace_id)
    trace_dict = trace.to_dict()

    if extract_fields:
        field_list = [f.strip() for f in extract_fields.split(",")]
        # Validate fields against trace data
        try:
            validate_field_paths(field_list, trace_dict, verbose=verbose)
        except ValueError as e:
            raise click.UsageError(str(e))
        # Filter to selected fields only
        filtered_trace = filter_json_by_fields(trace_dict, field_list)
        json_trace = json.dumps(filtered_trace, indent=2)
    else:
        # Return full trace
        json_trace = json.dumps(trace_dict, indent=2)

    click.echo(json_trace)


@commands.command("delete")
@EXPERIMENT_ID
@click.option("--trace-ids", type=click.STRING, help="Comma-separated list of trace IDs to delete")
@click.option(
    "--max-timestamp-millis",
    type=click.INT,
    help="Delete traces older than this timestamp (milliseconds since epoch)",
)
@click.option("--max-traces", type=click.INT, help="Maximum number of traces to delete")
def delete_traces(
    experiment_id: str,
    trace_ids: str | None,
    max_timestamp_millis: int | None,
    max_traces: int | None,
) -> None:
    """
    Delete traces from an experiment.

    Either --trace-ids or timestamp criteria can be specified, but not both.

    \b
    Examples:
    # Delete specific traces
    mlflow traces delete --experiment-id 1 --trace-ids tr-abc123,tr-def456

    \b
    # Delete traces older than a timestamp
    mlflow traces delete --experiment-id 1 --max-timestamp-millis 1700000000000

    \b
    # Delete up to 100 old traces
    mlflow traces delete --experiment-id 1 --max-timestamp-millis 1700000000000 --max-traces 100
    """
    client = TracingClient()
    trace_id_list = trace_ids.split(",") if trace_ids else None

    count = client.delete_traces(
        experiment_id=experiment_id,
        trace_ids=trace_id_list,
        max_timestamp_millis=max_timestamp_millis,
        max_traces=max_traces,
    )
    click.echo(f"Deleted {count} trace(s) from experiment {experiment_id}.")


@commands.command("set-tag")
@TRACE_ID
@click.option("--key", type=click.STRING, required=True, help="Tag key")
@click.option("--value", type=click.STRING, required=True, help="Tag value")
def set_tag(trace_id: str, key: str, value: str) -> None:
    """
    Set a tag on a trace.

    \b
    Example:
    mlflow traces set-tag --trace-id tr-abc123 --key environment --value production
    """
    client = TracingClient()
    client.set_trace_tag(trace_id, key, value)
    click.echo(f"Set tag '{key}' on trace {trace_id}.")


@commands.command("delete-tag")
@TRACE_ID
@click.option("--key", type=click.STRING, required=True, help="Tag key to delete")
def delete_tag(trace_id: str, key: str) -> None:
    """
    Delete a tag from a trace.

    \b
    Example:
    mlflow traces delete-tag --trace-id tr-abc123 --key environment
    """
    client = TracingClient()
    client.delete_trace_tag(trace_id, key)
    click.echo(f"Deleted tag '{key}' from trace {trace_id}.")


@commands.command("log-feedback")
@TRACE_ID
@click.option(
    "--name", type=click.STRING, default="feedback", help="Feedback name (default: 'feedback')"
)
@click.option(
    "--value",
    type=click.STRING,
    help="Feedback value (number, string, bool, or JSON for complex values)",
)
@click.option(
    "--source-type",
    type=click.Choice(
        [AssessmentSourceType.HUMAN, AssessmentSourceType.LLM_JUDGE, AssessmentSourceType.CODE]
    ),
    help="Source type of the feedback",
)
@click.option(
    "--source-id",
    type=click.STRING,
    help="Source identifier (e.g., email for HUMAN, model name for LLM)",
)
@click.option("--rationale", type=click.STRING, help="Explanation/justification for the feedback")
@click.option("--metadata", type=click.STRING, help="Additional metadata as JSON string")
@click.option("--span-id", type=click.STRING, help="Associate feedback with a specific span ID")
def log_feedback(
    trace_id: str,
    name: str,
    value: str | None,
    source_type: str | None,
    source_id: str | None,
    rationale: str | None,
    metadata: str | None,
    span_id: str | None,
) -> None:
    """
    Log feedback (evaluation score) to a trace.

    \b
    Examples:
    # Simple numeric feedback
    mlflow traces log-feedback --trace-id tr-abc123 \\
        --name relevance --value 0.9 \\
        --rationale "Highly relevant response"

    \b
    # Human feedback with source
    mlflow traces log-feedback --trace-id tr-abc123 \\
        --name quality --value good \\
        --source-type HUMAN --source-id reviewer@example.com

    \b
    # Complex feedback with JSON value and metadata
    mlflow traces log-feedback --trace-id tr-abc123 \\
        --name metrics \\
        --value '{"accuracy": 0.95, "f1": 0.88}' \\
        --metadata '{"model": "gpt-4", "temperature": 0.7}'

    \b
    # LLM judge feedback
    mlflow traces log-feedback --trace-id tr-abc123 \\
        --name faithfulness --value 0.85 \\
        --source-type LLM_JUDGE --source-id gpt-4 \\
        --rationale "Response is faithful to context"
    """
    # Parse value if it's JSON
    if value:
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass  # Keep as string

    # Parse metadata
    metadata_dict = json.loads(metadata) if metadata else None

    # Create source if provided
    source = None
    if source_type and source_id:
        # Map CLI choices to AssessmentSourceType constants
        source_type_value = getattr(AssessmentSourceType, source_type)
        source = AssessmentSource(
            source_type=source_type_value,
            source_id=source_id,
        )

    assessment = _log_feedback(
        trace_id=trace_id,
        name=name,
        value=value,
        source=source,
        rationale=rationale,
        metadata=metadata_dict,
        span_id=span_id,
    )
    click.echo(
        f"Logged feedback '{name}' to trace {trace_id}. Assessment ID: {assessment.assessment_id}"
    )


@commands.command("log-expectation")
@TRACE_ID
@click.option(
    "--name",
    type=click.STRING,
    required=True,
    help="Expectation name (e.g., 'expected_answer', 'ground_truth')",
)
@click.option(
    "--value",
    type=click.STRING,
    required=True,
    help="Expected value (string or JSON for complex values)",
)
@click.option(
    "--source-type",
    type=click.Choice(
        [AssessmentSourceType.HUMAN, AssessmentSourceType.LLM_JUDGE, AssessmentSourceType.CODE]
    ),
    help="Source type of the expectation",
)
@click.option("--source-id", type=click.STRING, help="Source identifier")
@click.option("--metadata", type=click.STRING, help="Additional metadata as JSON string")
@click.option("--span-id", type=click.STRING, help="Associate expectation with a specific span ID")
def log_expectation(
    trace_id: str,
    name: str,
    value: str,
    source_type: str | None,
    source_id: str | None,
    metadata: str | None,
    span_id: str | None,
) -> None:
    """
    Log an expectation (ground truth label) to a trace.

    \b
    Examples:
    # Simple expected answer
    mlflow traces log-expectation --trace-id tr-abc123 \\
        --name expected_answer --value "Paris"

    \b
    # Human-annotated ground truth
    mlflow traces log-expectation --trace-id tr-abc123 \\
        --name ground_truth --value "positive" \\
        --source-type HUMAN --source-id annotator@example.com

    \b
    # Complex expected output with metadata
    mlflow traces log-expectation --trace-id tr-abc123 \\
        --name expected_response \\
        --value '{"answer": "42", "confidence": 0.95}' \\
        --metadata '{"dataset": "test_set_v1", "difficulty": "hard"}'
    """
    # Parse value if it's JSON
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        pass  # Keep as string

    # Parse metadata
    metadata_dict = json.loads(metadata) if metadata else None

    # Create source if provided
    source = None
    if source_type and source_id:
        # Map CLI choices to AssessmentSourceType constants
        source_type_value = getattr(AssessmentSourceType, source_type)
        source = AssessmentSource(
            source_type=source_type_value,
            source_id=source_id,
        )

    assessment = _log_expectation(
        trace_id=trace_id,
        name=name,
        value=value,
        source=source,
        metadata=metadata_dict,
        span_id=span_id,
    )
    click.echo(
        f"Logged expectation '{name}' to trace {trace_id}. "
        f"Assessment ID: {assessment.assessment_id}"
    )


@commands.command("get-assessment")
@TRACE_ID
@click.option("--assessment-id", type=click.STRING, required=True, help="Assessment ID")
def get_assessment(trace_id: str, assessment_id: str) -> None:
    """
    Get assessment details as JSON.

    \b
    Example:
    mlflow traces get-assessment --trace-id tr-abc123 --assessment-id asmt-def456
    """
    client = TracingClient()
    assessment = client.get_assessment(trace_id, assessment_id)
    json_assessment = json.dumps(assessment.to_dictionary(), indent=2)
    click.echo(json_assessment)


@commands.command("update-assessment")
@TRACE_ID
@click.option("--assessment-id", type=click.STRING, required=True, help="Assessment ID to update")
@click.option("--value", type=click.STRING, help="Updated assessment value (JSON)")
@click.option("--rationale", type=click.STRING, help="Updated rationale")
@click.option("--metadata", type=click.STRING, help="Updated metadata as JSON")
def update_assessment(
    trace_id: str,
    assessment_id: str,
    value: str | None,
    rationale: str | None,
    metadata: str | None,
) -> None:
    """
    Update an existing assessment.

    NOTE: Assessment names cannot be changed once set. Only value, rationale,
    and metadata can be updated.

    \b
    Examples:
    # Update feedback value and rationale
    mlflow traces update-assessment --trace-id tr-abc123 --assessment-id asmt-def456 \\
        --value '{"accuracy": 0.98}' --rationale "Updated after review"

    \b
    # Update only the rationale
    mlflow traces update-assessment --trace-id tr-abc123 --assessment-id asmt-def456 \\
        --rationale "Revised evaluation"
    """
    client = TracingClient()

    # Get the existing assessment first
    existing = client.get_assessment(trace_id, assessment_id)

    # Parse value if provided
    parsed_value = value
    if value:
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            pass  # Keep as string

    # Parse metadata if provided
    parsed_metadata = metadata
    if metadata:
        parsed_metadata = json.loads(metadata)

    # Create updated assessment - determine if it's feedback or expectation
    if hasattr(existing, "feedback"):
        # It's feedback
        from mlflow.entities import Feedback

        updated_assessment = Feedback(
            name=existing.name,  # Always use existing name (cannot be changed)
            value=parsed_value if value else existing.value,
            rationale=rationale if rationale is not None else existing.rationale,
            metadata=parsed_metadata if metadata else existing.metadata,
        )
    else:
        # It's expectation
        from mlflow.entities import Expectation

        updated_assessment = Expectation(
            name=existing.name,  # Always use existing name (cannot be changed)
            value=parsed_value if value else existing.value,
            metadata=parsed_metadata if metadata else existing.metadata,
        )

    client.update_assessment(trace_id, assessment_id, updated_assessment)
    click.echo(f"Updated assessment {assessment_id} in trace {trace_id}.")


@commands.command("delete-assessment")
@TRACE_ID
@click.option("--assessment-id", type=click.STRING, required=True, help="Assessment ID to delete")
def delete_assessment(trace_id: str, assessment_id: str) -> None:
    """
    Delete an assessment from a trace.

    \b
    Example:
    mlflow traces delete-assessment --trace-id tr-abc123 --assessment-id asmt-def456
    """
    client = TracingClient()
    client.delete_assessment(trace_id, assessment_id)
    click.echo(f"Deleted assessment {assessment_id} from trace {trace_id}.")


@commands.command("calculate-correlation")
@click.option(
    "--experiment-ids",
    type=click.STRING,
    required=True,
    help="Comma-separated list of experiment IDs to analyze",
)
@click.option(
    "--filter1",
    type=click.STRING,
    required=True,
    help="First filter condition (e.g., \"status = 'ERROR'\")",
)
@click.option(
    "--filter2",
    type=click.STRING,
    required=True,
    help="Second filter condition (e.g., \"execution_time > 5000\")",
)
@click.option(
    "--output",
    type=click.Choice(["json", "table", "csv"]),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed NPMI interpretation",
)
def calculate_correlation(
    experiment_ids: str,
    filter1: str,
    filter2: str,
    output: str,
    verbose: bool,
) -> None:
    """
    Calculate correlation (NPMI) between two trace filter conditions.
    
    NPMI (Normalized Pointwise Mutual Information) measures how much more (or less) 
    likely traces are to satisfy both conditions compared to if they were independent.
    
    NPMI Score Interpretation:
    • -1.0: Perfect negative correlation (mutually exclusive)
    • -0.5 to -1.0: Strong negative correlation
    • -0.2 to -0.5: Moderate negative correlation
    • -0.2 to 0.2: Weak or no correlation
    • 0.2 to 0.5: Moderate positive correlation
    • 0.5 to 1.0: Strong positive correlation
    • 1.0: Perfect positive correlation
    
    Examples:
    
    \b
    # Calculate correlation between errors and slow execution
    mlflow traces calculate-correlation \\
        --experiment-ids 123,456 \\
        --filter1 "status = 'ERROR'" \\
        --filter2 "execution_time > 5000"
    
    \b
    # Analyze correlation for specific tags
    mlflow traces calculate-correlation \\
        --experiment-ids 123 \\
        --filter1 "tags.tool = 'langchain'" \\
        --filter2 "tags.env = 'production'" \\
        --output json
    
    \b
    # Complex filters with verbose interpretation
    mlflow traces calculate-correlation \\
        --experiment-ids 123 \\
        --filter1 "status = 'OK' AND execution_time < 1000" \\
        --filter2 "tags.cache_hit = 'true'" \\
        --verbose
    """
    from mlflow.tracing.client import TracingClient
    from mlflow.tracing.analysis import TraceFilterCorrelationResult
    
    # Parse experiment IDs
    exp_ids = [exp_id.strip() for exp_id in experiment_ids.split(",")]
    
    # Get correlation result
    client = TracingClient()
    try:
        result = client.calculate_trace_filter_correlation(
            experiment_ids=exp_ids,
            filter_string1=filter1,
            filter_string2=filter2,
        )
    except Exception as e:
        click.echo(f"Error calculating correlation: {e}", err=True)
        raise click.Abort()
    
    # Interpret NPMI score
    def interpret_npmi(score: float) -> tuple[str, str]:
        """Return correlation strength and description."""
        if score == -1.0:
            return "Perfect Negative", "Filters are mutually exclusive"
        elif score < -0.5:
            return "Strong Negative", "Filters rarely co-occur"
        elif score < -0.2:
            return "Moderate Negative", "Filters tend not to co-occur"
        elif score < 0.2:
            return "Weak/None", "Filters are mostly independent"
        elif score < 0.5:
            return "Moderate Positive", "Filters tend to co-occur"
        elif score < 1.0:
            return "Strong Positive", "Filters frequently co-occur"
        else:
            return "Perfect Positive", "Filters always co-occur together"
    
    # Format output based on selection
    if output == "json":
        import json
        output_dict = {
            "npmi": result.npmi,
            "confidence_lower": result.confidence_lower,
            "confidence_upper": result.confidence_upper,
            "filter_string1_count": result.filter_string1_count,
            "filter_string2_count": result.filter_string2_count,
            "joint_count": result.joint_count,
            "total_count": result.total_count,
        }
        if verbose:
            strength, _ = interpret_npmi(result.npmi)
            output_dict["interpretation"] = strength.lower().replace(" ", "_")
        click.echo(json.dumps(output_dict, indent=2))
    
    elif output == "csv":
        # CSV format
        import csv
        import sys
        writer = csv.writer(sys.stdout)
        writer.writerow([
            "npmi", "confidence_lower", "confidence_upper", 
            "filter1_count", "filter2_count", "joint_count", "total_count"
        ])
        writer.writerow([
            result.npmi,
            result.confidence_lower or "",
            result.confidence_upper or "",
            result.filter_string1_count,
            result.filter_string2_count,
            result.joint_count,
            result.total_count,
        ])
    
    else:  # table format (default)
        click.echo("\nTrace Filter Correlation Analysis")
        click.echo("=" * 50)
        click.echo(f"Filter 1: {filter1}")
        click.echo(f"Filter 2: {filter2}")
        click.echo(f"Experiments: {', '.join(exp_ids)}")
        click.echo()
        
        # Results table
        click.echo("Results:")
        click.echo("┌─────────────────────────┬──────────────┐")
        click.echo("│ Metric                  │ Value        │")
        click.echo("├─────────────────────────┼──────────────┤")
        click.echo(f"│ NPMI Score              │ {result.npmi:12.4f} │")
        
        strength, description = interpret_npmi(result.npmi)
        click.echo(f"│ Correlation             │ {strength:12s} │")
        click.echo(f"│ Filter 1 Count          │ {result.filter_string1_count:12d} │")
        click.echo(f"│ Filter 2 Count          │ {result.filter_string2_count:12d} │")
        click.echo(f"│ Joint Count             │ {result.joint_count:12d} │")
        click.echo(f"│ Total Traces            │ {result.total_count:12d} │")
        
        if result.confidence_lower is not None and result.confidence_upper is not None:
            conf_str = f"[{result.confidence_lower:.2f}, {result.confidence_upper:.2f}]"
            click.echo(f"│ 95% Confidence Interval │ {conf_str:12s} │")
        
        click.echo("└─────────────────────────┴──────────────┘")
        
        if verbose:
            click.echo()
            click.echo(f"Interpretation: {description}")
            
            # Calculate percentages for better understanding
            if result.total_count > 0:
                pct1 = (result.filter_string1_count / result.total_count) * 100
                pct2 = (result.filter_string2_count / result.total_count) * 100
                joint_pct = (result.joint_count / result.total_count) * 100
                
                click.echo()
                click.echo("Coverage Statistics:")
                click.echo(f"• Filter 1 matches {pct1:.1f}% of traces")
                click.echo(f"• Filter 2 matches {pct2:.1f}% of traces")
                click.echo(f"• Both filters match {joint_pct:.1f}% of traces")
                
                if result.filter_string1_count > 0:
                    conditional_pct = (result.joint_count / result.filter_string1_count) * 100
                    click.echo(f"• Of traces matching Filter 1, {conditional_pct:.1f}% also match Filter 2")
                
                if result.filter_string2_count > 0:
                    conditional_pct = (result.joint_count / result.filter_string2_count) * 100
                    click.echo(f"• Of traces matching Filter 2, {conditional_pct:.1f}% also match Filter 1")


@commands.command("execute-sql")
@click.option(
    "--sql",
    type=click.STRING,
    required=True,
    help="Databricks SQL query string to execute against traces delta table"
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format: 'table' for formatted table (default) or 'json' for JSON format"
)
@click.option(
    "--run-id",
    type=click.STRING,
    required=True,
    help="MLflow run ID to log the SQL query to as a YAML artifact"
)
def execute_sql(sql: str, output: str, run_id: str) -> None:
    """
    Execute a raw Databricks SQL query against the Databricks traces delta table.

    TABLE SCHEMA:

    SIMPLE COLUMNS:
    - trace_id: STRING - Unique trace identifier (format: tr-*)
    - client_request_id: STRING - Optional client-provided request ID
    - request_time: TIMESTAMP - When trace was created
    - state: STRING - Trace status ('OK' or 'ERROR')
    - execution_duration_ms: BIGINT - Total execution time in milliseconds
    - request: STRING - Full input content/prompt
    - response: STRING - Full output/response content
    - request_preview: STRING - Truncated version of request
    - response_preview: STRING - Truncated version of response

    MAP COLUMNS (access with bracket notation: column_name['key']):
    - trace_metadata: MAP<STRING, STRING>
        Common keys: 'mlflow.traceInputs', 'mlflow.traceOutputs', 'mlflow.user', 'mlflow.trace_schema'
        Example: trace_metadata['mlflow.traceOutputs']
    - tags: MAP<STRING, STRING>
        Common keys: 'mlflow.traceName', 'mlflow.user', 'mlflow.artifactLocation'
        Example: tags['mlflow.traceName']

    STRUCT COLUMNS:
    - trace_location: STRUCT
        Contains MLflow experiment/table location information

    ARRAY COLUMNS (use LATERAL VIEW explode or filter() functions):
    - spans: ARRAY<STRUCT>
        Each span contains:
        - name: STRING - Span name
        - span_id: STRING - Span identifier
        - trace_id: STRING - Parent trace ID
        - parent_id: STRING - Parent span ID (empty for root span)
        - start_time: BIGINT - Start timestamp (nanoseconds)
        - end_time: BIGINT - End timestamp (nanoseconds)
        - status_code: STRING - Span status ('OK' or 'ERROR')
        - status_message: STRING - Error details if status is ERROR
        - attributes: MAP<STRING, STRING> - Span metadata
        - events: ARRAY<STRUCT> - Span events with name, timestamp, attributes

    - assessments: ARRAY<STRUCT>
        Each assessment contains:
        - assessment_id: STRING - Assessment identifier
        - name: STRING - Assessment name
        - source: STRUCT - Source type (HUMAN/LLM_JUDGE/CODE) and source_id
        - feedback: STRUCT - Feedback value and error info
        - expectation: STRUCT - Expected value/ground truth
        - rationale: STRING - Explanation for assessment
        - metadata: MAP<STRING, STRING> - Additional context
        - span_id: STRING - Optional related span ID

    KEY SQL SYNTAX PATTERNS FOR NESTED DATA:

    Example: Analyzing Span Errors
    -------------------------------
    -- Access MAP fields using bracket notation:
    SELECT
        trace_id,
        trace_metadata['mlflow.traceOutputs'] as output,
        tags['mlflow.traceName'] as trace_name
    FROM {table_name}
    WHERE trace_metadata['mlflow.traceInputs'] LIKE '%error%'
    LIMIT 10

    -- Work with ARRAY fields using LATERAL VIEW explode:
    SELECT
        s.name as span_name,
        s.status_code,  -- Values are 'OK' or 'ERROR' (not 'STATUS_CODE_OK')
        COUNT(*) as error_count
    FROM {table_name} t
    LATERAL VIEW explode(spans) AS s
    WHERE s.status_code = 'ERROR'
    GROUP BY s.name, s.status_code

    -- Filter arrays inline using filter() and size():
    SELECT
        trace_id,
        size(filter(spans, s -> s.status_code = 'ERROR')) as error_span_count,
        size(filter(spans, s -> s.name = 'extract_action_items' AND s.status_code = 'ERROR')) as action_item_errors
    FROM {table_name}
    WHERE size(filter(spans, s -> s.status_code = 'ERROR')) > 0
    LIMIT 10

    Quality metric example queries:
        Verbosity Analysis: 
        -------------------
        WITH percentile_thresholds AS (
          SELECT
            percentile(LENGTH(request), 0.25) as short_input_threshold,
            percentile(LENGTH(response), 0.90) as verbose_response_threshold
          FROM {table_name}
          WHERE state = 'OK'
        ),
        shorter_inputs AS (
          SELECT
            t.trace_id,
            LENGTH(t.response) as response_length
          FROM {table_name} t
          CROSS JOIN percentile_thresholds p
          WHERE t.state = 'OK'
            AND LENGTH(t.request) <= p.short_input_threshold
        ),
        verbose_traces AS (
          SELECT
            trace_id,
            response_length > (SELECT verbose_response_threshold FROM percentile_thresholds) as is_verbose
          FROM shorter_inputs
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_verbose THEN 1 ELSE 0 END) / COUNT(*), 2) as verbose_pct,
        FROM verbose_traces

        Response Quality Issues
        ----------------------------
        WITH quality_issues AS (
          SELECT
            trace_id,
            (response LIKE '%?%' OR
             LOWER(response) LIKE '%apologize%' OR LOWER(response) LIKE '%sorry%' OR
             LOWER(response) LIKE '%not sure%' OR LOWER(response) LIKE '%cannot confirm%') as has_quality_issue
          FROM {table_name}
          WHERE state = 'OK'
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN has_quality_issue THEN 1 ELSE 0 END) / COUNT(*), 2) as problematic_response_rate,
        FROM quality_issues

        Rushed Processing
        ----------------------------
        WITH percentile_thresholds AS (
          SELECT
            percentile(LENGTH(request), 0.75) as complex_threshold,
            percentile(execution_duration_ms, 0.10) as fast_threshold
          FROM {table_name}
          WHERE state = 'OK' AND execution_duration_ms > 0
        ),
        complex_requests AS (
          SELECT
            t.trace_id,
            LENGTH(t.request) > p.complex_threshold as is_complex,
            t.execution_duration_ms < p.fast_threshold as is_fast
          FROM {table_name} t
          CROSS JOIN percentile_thresholds p
          WHERE t.state = 'OK' AND t.execution_duration_ms > 0
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_complex AND is_fast THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN is_complex THEN 1 ELSE 0 END), 0), 2) as rushed_complex_pct,
        FROM complex_requests

        Empty/Minimal Responses
        ----------------------------
        WITH minimal_check AS (
          SELECT
            trace_id,
            LENGTH(response) < 50 as is_minimal
          FROM {table_name}
          WHERE state = 'OK'
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_minimal THEN 1 ELSE 0 END) / COUNT(*), 2) as minimal_response_rate,
        FROM minimal_check
    
    """
    from mlflow.store.tracking.insights_databricks_sql_store import InsightsDatabricksSqlStore

    try:
        # Initialize the store
        store = InsightsDatabricksSqlStore("databricks")

        # Execute the SQL query
        results = store.execute_sql(sql)

        # Log the successful query to YAML artifact
        from mlflow.insights.utils import save_sql_queries_to_yaml
        save_sql_queries_to_yaml(run_id, sql)

        if output == "json":
            # JSON output
            click.echo(json.dumps(results, indent=2))
        else:
            # Table output
            if not results:
                click.echo("No results returned.")
                return

            # Extract headers from first row
            headers = list(results[0].keys())

            # Convert results to table format
            table_data = []
            for row in results:
                table_data.append([str(row.get(header, "")) for header in headers])

            # Display as table
            click.echo(_create_table(table_data, headers=headers))

    except Exception as e:
        click.echo(f"Error executing SQL query: {e}", err=True)
        raise click.Abort()
