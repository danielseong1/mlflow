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
        run_id = create_nested_analysis_run(
            self._mlflow_client, experiment_id, run_name
        )

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
        rationale: str,
        testing_plan: str,
        evidence: Optional[list[dict]] = None,
    ) -> str:
        """
        Create a new hypothesis within an analysis.

        Args:
            insights_run_id: Run ID of the analysis
            statement: The hypothesis being tested
            description: Detailed description of the hypothesis
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
                    raise ValueError(
                        "Evidence must have 'trace_id' and 'rationale' fields"
                    )
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
            rationale=rationale,
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
                    raise ValueError(
                        "Evidence must have 'trace_id' and 'rationale' fields"
                    )
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

    def create_baseline_census(
        self,
        insights_run_id: str,
        table_name: str,
    ) -> str:
        """
        Create a baseline census from trace analysis data.

        Args:
            insights_run_id: Run ID of the analysis
            table_name: Name of the trace table to analyze

        Returns:
            Census filename
        """
        # Validate run has analysis
        if not validate_run_has_analysis(self._mlflow_client, insights_run_id):
            raise ValueError(
                f"Run {insights_run_id} does not contain an analysis. Create an analysis first."
            )

        from mlflow.insights.models import (
            BaselineCensus,
            BaselineCensusMetadata,
            BaselineCensusOperationalMetrics,
            BaselineCensusQualityMetrics,
        )
        from mlflow.store.tracking.insights_databricks_sql_store import (
            InsightsDatabricksSqlStore,
        )

        # Initialize the SQL store
        store = InsightsDatabricksSqlStore("databricks")

        # Collect all the census data by executing SQL queries
        # 1. Basic counts with sample error trace IDs
        basic_query = f"""
        WITH error_traces AS (
            SELECT
                trace_id,
                state,
                ROW_NUMBER() OVER (ORDER BY trace_id) as rn
            FROM {table_name}
            WHERE state = 'ERROR'
        )
        SELECT
            (SELECT COUNT(*) FROM {table_name}) as total_traces,
            (SELECT SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) FROM {table_name}) as ok_count,
            (SELECT SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) FROM {table_name}) as error_count,
            (SELECT ROUND(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) FROM {table_name}) as error_rate_percentage,
            collect_list(CASE WHEN rn <= 15 THEN trace_id END) as error_sample_trace_ids
        FROM error_traces
        """

        # 2. Latency percentiles
        latency_query = f"""
        SELECT
            percentile(execution_duration_ms, 0.5) as p50_latency_ms,
            percentile(execution_duration_ms, 0.9) as p90_latency_ms,
            percentile(execution_duration_ms, 0.95) as p95_latency_ms,
            percentile(execution_duration_ms, 0.99) as p99_latency_ms,
            MAX(execution_duration_ms) as max_latency_ms
        FROM {table_name}
        WHERE state = 'OK' AND execution_duration_ms IS NOT NULL
        """

        # 3. Top error spans with sample trace IDs
        error_query = f"""
        WITH error_spans_with_traces AS (
            SELECT
                span.name as error_span_name,
                t.trace_id,
                COUNT(*) OVER (PARTITION BY span.name) as count,
                ROUND(COUNT(*) OVER (PARTITION BY span.name) * 100.0 / (
                    SELECT COUNT(*)
                    FROM {table_name}
                    LATERAL VIEW explode(spans) AS s
                    WHERE s.status_code = 'ERROR'
                ), 2) as percentage_of_errors,
                ROW_NUMBER() OVER (PARTITION BY span.name ORDER BY t.trace_id) as rn
            FROM {table_name} t
            LATERAL VIEW explode(spans) AS span
            WHERE span.status_code = 'ERROR'
        ),
        error_spans_summary AS (
            SELECT
                error_span_name,
                count,
                percentage_of_errors,
                collect_list(CASE WHEN rn <= 15 THEN trace_id END) as sample_trace_ids
            FROM error_spans_with_traces
            GROUP BY error_span_name, count, percentage_of_errors
        )
        SELECT
            error_span_name,
            count,
            percentage_of_errors,
            sample_trace_ids
        FROM error_spans_summary
        ORDER BY count DESC
        LIMIT 5
        """

        # 4. Top slow tools with sample trace IDs
        slow_tools_query = f"""
        WITH slow_tools_with_traces AS (
            SELECT
                span.name as tool_span_name,
                t.trace_id,
                (unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000 as latency_ms,
                COUNT(*) OVER (PARTITION BY span.name) as count,
                percentile((unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000, 0.95) OVER (PARTITION BY span.name) as p95_latency_ms,
                percentile((unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000, 0.5) OVER (PARTITION BY span.name) as median_latency_ms,
                ROW_NUMBER() OVER (PARTITION BY span.name ORDER BY (unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000 DESC) as rn
            FROM {table_name} t
            LATERAL VIEW explode(spans) AS span
            WHERE span.start_time IS NOT NULL AND span.end_time IS NOT NULL
        ),
        slow_tools_summary AS (
            SELECT
                tool_span_name,
                count,
                p95_latency_ms,
                median_latency_ms,
                collect_list(CASE WHEN rn <= 15 THEN trace_id END) as sample_trace_ids
            FROM slow_tools_with_traces
            GROUP BY tool_span_name, count, p95_latency_ms, median_latency_ms
            HAVING count >= 10
        )
        SELECT
            tool_span_name,
            count,
            median_latency_ms,
            p95_latency_ms,
            sample_trace_ids
        FROM slow_tools_summary
        ORDER BY p95_latency_ms DESC
        LIMIT 5
        """

        # 5. Time buckets (max 10 buckets with adaptive intervals)
        time_buckets_query = f"""
        WITH time_range AS (
            SELECT
                MIN(request_time) as min_time,
                MAX(request_time) as max_time,
                CAST((UNIX_TIMESTAMP(MAX(request_time)) - UNIX_TIMESTAMP(MIN(request_time))) / 10 AS BIGINT) as bucket_width_seconds
            FROM {table_name}
        ),
        bucketed_data AS (
            SELECT
                -- Create bucket number (0-9) based on time position
                LEAST(9, FLOOR((UNIX_TIMESTAMP(t.request_time) - UNIX_TIMESTAMP(r.min_time)) / GREATEST(1, r.bucket_width_seconds))) as bucket_num,
                -- Calculate bucket start time
                FROM_UNIXTIME(
                    UNIX_TIMESTAMP(r.min_time) +
                    (LEAST(9, FLOOR((UNIX_TIMESTAMP(t.request_time) - UNIX_TIMESTAMP(r.min_time)) / GREATEST(1, r.bucket_width_seconds))) * r.bucket_width_seconds)
                ) as time_bucket,
                t.state,
                t.execution_duration_ms
            FROM {table_name} t
            CROSS JOIN time_range r
            WHERE t.request_time IS NOT NULL
        )
        SELECT
            time_bucket,
            COUNT(*) as total_traces,
            SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count,
            ROUND(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate_percentage,
            percentile(execution_duration_ms, 0.95) as p95_latency_ms
        FROM bucketed_data
        GROUP BY time_bucket
        ORDER BY time_bucket
        """

        # 6. Timestamp range
        timestamp_query = f"""
        SELECT
            MIN(request_time) as first_trace_timestamp,
            MAX(request_time) as last_trace_timestamp
        FROM {table_name}
        """

        # 7. Quality Metrics - Verbosity Analysis
        verbosity_query = f"""
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
        ),
        limited_samples AS (
          SELECT
            trace_id,
            is_verbose,
            ROW_NUMBER() OVER (PARTITION BY is_verbose ORDER BY trace_id) as rn
          FROM verbose_traces
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_verbose THEN 1 ELSE 0 END) / COUNT(*), 2) as verbose_percentage,
          collect_list(CASE WHEN is_verbose AND rn <= 15 THEN trace_id END) as sample_trace_ids
        FROM limited_samples
        """

        # 8. Quality Metrics - Response Quality Issues (Combined)
        response_quality_issues_query = f"""
        WITH quality_issues AS (
          SELECT
            trace_id,
            (response LIKE '%?%' OR
             LOWER(response) LIKE '%apologize%' OR LOWER(response) LIKE '%sorry%' OR
             LOWER(response) LIKE '%not sure%' OR LOWER(response) LIKE '%cannot confirm%') as has_quality_issue
          FROM {table_name}
          WHERE state = 'OK'
        ),
        limited_samples AS (
          SELECT
            trace_id,
            has_quality_issue,
            ROW_NUMBER() OVER (PARTITION BY has_quality_issue ORDER BY trace_id) as rn
          FROM quality_issues
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN has_quality_issue THEN 1 ELSE 0 END) / COUNT(*), 2) as problematic_response_rate_percentage,
          collect_list(CASE WHEN has_quality_issue AND rn <= 15 THEN trace_id END) as sample_trace_ids
        FROM limited_samples
        """

        # 9. Quality Metrics - Rushed Processing
        rushed_processing_query = f"""
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
        ),
        limited_samples AS (
          SELECT
            trace_id,
            is_complex,
            is_fast,
            ROW_NUMBER() OVER (PARTITION BY (is_complex AND is_fast) ORDER BY trace_id) as rn
          FROM complex_requests
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_complex AND is_fast THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN is_complex THEN 1 ELSE 0 END), 0), 2) as rushed_complex_pct,
          collect_list(CASE WHEN is_complex AND is_fast AND rn <= 15 THEN trace_id END) as sample_trace_ids
        FROM limited_samples
        """

        # 10. Quality Metrics - Empty/Minimal Responses
        minimal_responses_query = f"""
        WITH minimal_check AS (
          SELECT
            trace_id,
            LENGTH(response) < 50 as is_minimal
          FROM {table_name}
          WHERE state = 'OK'
        ),
        limited_samples AS (
          SELECT
            trace_id,
            is_minimal,
            ROW_NUMBER() OVER (PARTITION BY is_minimal ORDER BY trace_id) as rn
          FROM minimal_check
        )
        SELECT
          ROUND(100.0 * SUM(CASE WHEN is_minimal THEN 1 ELSE 0 END) / COUNT(*), 2) as minimal_response_rate,
          collect_list(CASE WHEN is_minimal AND rn <= 15 THEN trace_id END) as sample_trace_ids
        FROM limited_samples
        """

        # Execute queries
        basic_results = store.execute_sql(basic_query)
        latency_results = store.execute_sql(latency_query)
        error_results = store.execute_sql(error_query)
        slow_tools_results = store.execute_sql(slow_tools_query)
        time_buckets_results = store.execute_sql(time_buckets_query)
        timestamp_results = store.execute_sql(timestamp_query)
        verbosity_results = store.execute_sql(verbosity_query)
        response_quality_issues_results = store.execute_sql(
            response_quality_issues_query
        )
        rushed_processing_results = store.execute_sql(rushed_processing_query)
        minimal_responses_results = store.execute_sql(minimal_responses_query)

        # Extract basic metrics
        basic = basic_results[0] if basic_results else {}
        latency = latency_results[0] if latency_results else {}
        timestamps = timestamp_results[0] if timestamp_results else {}
        verbosity = verbosity_results[0] if verbosity_results else {}
        response_quality_issues = (
            response_quality_issues_results[0]
            if response_quality_issues_results
            else {}
        )
        rushed_processing = (
            rushed_processing_results[0] if rushed_processing_results else {}
        )
        minimal_responses = (
            minimal_responses_results[0] if minimal_responses_results else {}
        )

        # Create nested sections
        metadata_section = BaselineCensusMetadata(
            table_name=table_name, additional_metadata={}
        )

        operational_metrics_section = BaselineCensusOperationalMetrics(
            total_traces=basic.get("total_traces", 0),
            ok_count=basic.get("ok_count", 0),
            error_count=basic.get("error_count", 0),
            error_rate_percentage=basic.get("error_rate_percentage", 0.0),
            error_sample_trace_ids=basic.get("error_sample_trace_ids", [])[
                :15
            ],  # Sample error traces
            p50_latency_ms=latency.get("p50_latency_ms"),
            p90_latency_ms=latency.get("p90_latency_ms"),
            p95_latency_ms=latency.get("p95_latency_ms"),
            p99_latency_ms=latency.get("p99_latency_ms"),
            max_latency_ms=latency.get("max_latency_ms"),
            first_trace_timestamp=timestamps.get("first_trace_timestamp"),
            last_trace_timestamp=timestamps.get("last_trace_timestamp"),
            top_error_spans=error_results,
            top_slow_tools=slow_tools_results,
            time_buckets=time_buckets_results,
        )

        quality_metrics_section = BaselineCensusQualityMetrics(
            verbosity={
                "description": "Percentage of short inputs (<=P25 request length) that receive verbose responses (>P90 response length)",
                "value": verbosity.get("verbose_percentage", 0.0),
                "sample_trace_ids": verbosity.get("sample_trace_ids", [])[
                    :15
                ],  # Limit to 15
            },
            response_quality_issues={
                "description": "Percentage of responses containing question marks, apologies ('sorry', 'apologize'), or uncertainty phrases ('not sure', 'cannot confirm')",
                "value": response_quality_issues.get(
                    "problematic_response_rate_percentage", 0.0
                ),
                "sample_trace_ids": response_quality_issues.get("sample_trace_ids", [])[
                    :15
                ],  # Limit to 15
            },
            rushed_processing={
                "description": "Percentage of complex requests (>P75 length) processed faster than typical fast responses (P10 execution time)",
                "value": rushed_processing.get("rushed_complex_pct", 0.0),
                "sample_trace_ids": rushed_processing.get("sample_trace_ids", [])[
                    :15
                ],  # Limit to 15
            },
            minimal_responses={
                "description": "Percentage of responses shorter than 50 characters, potentially indicating incomplete or minimal responses",
                "value": minimal_responses.get("minimal_response_rate", 0.0),
                "sample_trace_ids": minimal_responses.get("sample_trace_ids", [])[
                    :15
                ],  # Limit to 15
            },
        )

        # Create census object with nested sections
        census = BaselineCensus(
            metadata=metadata_section,
            operational_metrics=operational_metrics_section,
            quality_metrics=quality_metrics_section,
        )

        # Save census to YAML with organized sections
        filename = "baseline_census.yaml"
        self._save_census_to_yaml(
            self._mlflow_client, insights_run_id, filename, census
        )

        return filename

    def _save_census_to_yaml(
        self, client, run_id: str, filename: str, census: "BaselineCensus"
    ) -> None:
        """
        Save census to YAML with organized sections and comments.
        Now the sections are preserved in the JSON structure as nested objects.
        """
        import os
        import tempfile

        import yaml

        # Convert census to dict
        data = census.model_dump(mode="json")

        # Create organized YAML content with section comments
        yaml_content = "# MLflow Insights Baseline Census\n"
        yaml_content += f"# Generated: {data['metadata']['created_at']}\n"
        yaml_content += f"# Source Table: {data['metadata']['table_name']}\n\n"

        # METADATA SECTION
        yaml_content += "# Information about the census and data source\n"
        yaml_content += yaml.safe_dump(
            {"metadata": data["metadata"]}, default_flow_style=False
        )
        yaml_content += "\n"

        # OPERATIONAL METRICS SECTION
        yaml_content += "# System performance, errors, and latency metrics\n"
        yaml_content += yaml.safe_dump(
            {"operational_metrics": data["operational_metrics"]},
            default_flow_style=False,
        )
        yaml_content += "\n"

        # QUALITY METRICS SECTION
        yaml_content += "# Agent response quality analysis\n"
        yaml_content += yaml.safe_dump(
            {"quality_metrics": data["quality_metrics"]}, default_flow_style=False
        )

        # Create temp file and save
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
        rationale: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
        testing_plan: Optional[str] = None,
    ) -> None:
        """
        Update an existing hypothesis.

        Args:
            insights_run_id: Run ID containing the hypothesis
            hypothesis_id: Hypothesis ID to update
            status: New status (TESTING, VALIDATED, REJECTED)
            rationale: New rationale
            evidence: New evidence entries to add
            testing_plan: Updated testing plan
        """
        # Get existing hypothesis
        hypothesis = self.get_hypothesis(insights_run_id, hypothesis_id)
        if not hypothesis:
            raise ValueError(
                f"Hypothesis {hypothesis_id} not found in run {insights_run_id}"
            )

        # Update fields
        if status is not None:
            hypothesis.status = HypothesisStatus(status)
        if rationale is not None:
            hypothesis.rationale = rationale
        if testing_plan is not None:
            hypothesis.testing_plan = testing_plan

        # Add new evidence
        new_trace_ids = []
        if evidence:
            for ev in evidence:
                if not isinstance(ev, dict):
                    raise ValueError(f"Evidence must be a dict, got {type(ev)}")
                if "trace_id" not in ev or "rationale" not in ev:
                    raise ValueError(
                        "Evidence must have 'trace_id' and 'rationale' fields"
                    )
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
                    raise ValueError(
                        "Evidence must have 'trace_id' and 'rationale' fields"
                    )
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
                validated_count = sum(
                    1 for h in hypotheses if h.status == HypothesisStatus.VALIDATED
                )

                summary = AnalysisSummary.from_analysis(
                    run.info.run_id,
                    analysis,
                    hypothesis_count,
                    validated_count,
                    hypotheses,
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
        hypothesis_files = list_yaml_files(
            self._mlflow_client, insights_run_id, "hypothesis_"
        )

        summaries = []
        for filename in hypothesis_files:
            hypothesis = load_from_yaml(
                self._mlflow_client, insights_run_id, filename, Hypothesis
            )
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
        return load_from_yaml(
            self._mlflow_client, insights_run_id, "analysis.yaml", Analysis
        )

    def get_hypothesis(
        self, insights_run_id: str, hypothesis_id: str
    ) -> Optional[Hypothesis]:
        """
        Get detailed hypothesis information.

        Args:
            insights_run_id: Run ID containing the hypothesis
            hypothesis_id: Hypothesis ID

        Returns:
            Hypothesis object or None if not found
        """
        filename = f"hypothesis_{hypothesis_id}.yaml"
        return load_from_yaml(
            self._mlflow_client, insights_run_id, filename, Hypothesis
        )

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
                    issue = load_from_yaml(
                        self._mlflow_client, parent_run_id, filename, Issue
                    )
                    if issue:
                        return issue
            except Exception:
                continue

        return None

    # =========================================================================
    # Preview Methods
    # =========================================================================

    def preview_hypotheses(
        self, insights_run_id: str, max_traces: int = 100
    ) -> list[Trace]:
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
            hypothesis = self.get_hypothesis(
                insights_run_id, hypothesis_summary.hypothesis_id
            )
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

    # =========================================================================
    # Baseline Census Methods
    # =========================================================================

    def get_baseline_census(self, insights_run_id: str) -> Optional["BaselineCensus"]:
        """
        Get baseline census information from a run.

        Args:
            insights_run_id: Run ID containing the baseline census

        Returns:
            BaselineCensus object or None if not found
        """
        from mlflow.insights.models import BaselineCensus

        return load_from_yaml(
            self._mlflow_client, insights_run_id, "baseline_census.yaml", BaselineCensus
        )

    def update_baseline_census(
        self,
        insights_run_id: str,
        table_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        regenerate: bool = False,
    ) -> str:
        """
        Update an existing baseline census.

        Args:
            insights_run_id: Run ID containing the baseline census
            table_name: Update the table name for the census
            metadata: Additional metadata to add/update
            regenerate: If True, regenerate all census data from the table

        Returns:
            Census filename
        """
        # Validate run has analysis
        if not validate_run_has_analysis(self._mlflow_client, insights_run_id):
            raise ValueError(
                f"Run {insights_run_id} does not contain an analysis. Create an analysis first."
            )

        if regenerate and table_name:
            # Regenerate entire census
            return self.create_baseline_census(insights_run_id, table_name)

        # Load existing census
        existing_census = self.get_baseline_census(insights_run_id)
        if not existing_census:
            raise ValueError(f"No baseline census found in run {insights_run_id}")

        # Update fields
        updated_census = existing_census.model_copy()

        if table_name:
            updated_census.table_name = table_name

        if metadata:
            updated_metadata = updated_census.metadata or {}
            updated_metadata.update(metadata)
            updated_census.metadata = updated_metadata

        # Update timestamp
        from datetime import datetime

        updated_census.created_at = datetime.utcnow()

        # Save updated census
        filename = "baseline_census.yaml"
        save_to_yaml(self._mlflow_client, insights_run_id, filename, updated_census)

        return filename

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

    # =========================================================================
    # Baseline Census Methods
    # =========================================================================

    def get_baseline_census(self, insights_run_id: str) -> Optional["BaselineCensus"]:
        """
        Get baseline census information from a run.

        Args:
            insights_run_id: Run ID containing the baseline census

        Returns:
            BaselineCensus object or None if not found
        """
        from mlflow.insights.models import BaselineCensus

        return load_from_yaml(
            self._mlflow_client, insights_run_id, "baseline_census.yaml", BaselineCensus
        )

    def update_baseline_census(
        self,
        insights_run_id: str,
        table_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        regenerate: bool = False,
    ) -> str:
        """
        Update an existing baseline census.

        Args:
            insights_run_id: Run ID containing the baseline census
            table_name: Update the table name for the census
            metadata: Additional metadata to add/update
            regenerate: If True, regenerate all census data from the table

        Returns:
            Census filename
        """
        # Validate run has analysis
        if not validate_run_has_analysis(self._mlflow_client, insights_run_id):
            raise ValueError(
                f"Run {insights_run_id} does not contain an analysis. Create an analysis first."
            )

        if regenerate and table_name:
            # Regenerate entire census
            return self.create_baseline_census(insights_run_id, table_name)

        # Load existing census
        existing_census = self.get_baseline_census(insights_run_id)
        if not existing_census:
            raise ValueError(f"No baseline census found in run {insights_run_id}")

        # Update fields
        updated_census = existing_census.model_copy()

        if table_name:
            updated_census.table_name = table_name

        if metadata:
            updated_metadata = updated_census.metadata or {}
            updated_metadata.update(metadata)
            updated_census.metadata = updated_metadata

        # Update timestamp
        from datetime import datetime

        updated_census.created_at = datetime.utcnow()

        # Save updated census
        filename = "baseline_census.yaml"
        save_to_yaml(self._mlflow_client, insights_run_id, filename, updated_census)

        return filename
