# Analyze Experiment (LLM Workflow)

## A. DESCRIPTION

Analyze MLflow traces in a single experiment for **quality issues**, **performance problems**, and **patterns** using the **MLflow Insights CLI** as the single source of truth and external memory.

## B. KEY CONCEPTS (Glossary)

### Analysis Run

**Purpose**: Container for each investigation that will contain all the hypotheses, census, and linked traces.

**Required fields**:

- experiment_id
- run_id
- name
- description: A brief description of the agent's task that should be inferred after analyzing ~10 trace inputs/outputs

**Invariants**:

- All inspected traces during this investigation must be linked here (see Trace Linking).
- Artifacts (census, hypotheses list, report) live under this run.

**Anti-patterns**: Writing ad-hoc notes in internal memory.

### Census (Baseline)

**Purpose**: Quantitative snapshot of the traces in the experiment used to guide hypotheses generation.

**Required fields**:

- ok_count, error_count, error_rate
- latency percentiles: p50, p90, p95, p99
- span/tool frequencies, timeout/error buckets
- quality markers (e.g., uncertainty/apology flags, long-response tails)

**Invariants**:

- Must be computed at the start of analysis run before generating any hypotheses.

### Hypothesis

**Purpose**: Testable claim about patterns in traces; the only valid unit of exploratory work.

**Required fields**:

- statement: Hypothesis title
- rationale: Rationale for testing this hypothesis; cite census results
- testing_plan: A detailed step by step plan of how the hypothesis will be tested.
- status: VALIDATED | REJECTED | TESTING (inconclusive)
- evidence[]: Individual traces that either support or reject the hypothesis with detailed reasoning.
- sql_queries[]: Any sql queries that were run while validating this hypothesis. Used for logging and lineage pruposes.

**Invariants**:

- No manual counting—derive results via SEARCH (T2) or SQL (T4).
- All traces that are inspected must be linked to the analysis run.
- Status changes require evidence.

**Anti-patterns**: Hunches without a testing plan; changing status without evidence; ad-hoc inline Python during exploration.

### Issue

**Purpose**: Actionable, validated problem promoted from a VALIDATED hypothesis.

**Required fields**:

- title: 5–8 words, specific and fix-oriented
- description: Includes the what, why, and impact (hard numbers from census or hypothesis validation process)
- severity: LOW | MEDIUM | HIGH | CRITICAL
- hypothesis_id: source hypothesis
- evidence[]: linked trace_ids with detailed reasoning.

**Invariants**:

- Evidence traces must already be linked to the analysis run.

**Anti-patterns**: Creating issues from untested hypotheses; missing denominators/ratios; vague titles.

### Traces table

**Purpose**: Databricks Delta table that contains all traces in the experiment. Can issue Databricks SQL queries against it using execute-sql CLI tool (T4).

**Schema**

BASIC TRACE METADATA

- trace_id (string): Unique trace identifier (e.g., tr-\*)
- client_request_id (string): Optional client-provided request ID
- request_time (timestamp): When the trace was created
- state (string): Trace status (e.g., OK, ERROR)
- execution_duration_ms (bigint): Total execution time in milliseconds

CONTENT FIELDS

- request (string): Full input content/prompt
- response (string): Full output/response content
- request_preview (string): Truncated version of request
- response_preview (string): Truncated version of response

NESTED STRUCTURES

- trace_metadata (map<string,string>): Custom metadata key–value pairs
- tags (map<string,string>): Custom tags (e.g., mlflow.traceName)
- trace_location (struct): MLflow experiment/table location info

SPANS (array<struct>)

- name (string): Span name
- span_id (string): Unique span identifier
- trace_id (string): Parent trace identifier
- parent_id (string): Parent span identifier (if any)
- start_time (timestamp): Span start
- end_time (timestamp): Span end
- status_code (string): Execution status code
- status_message (string): Execution status message/details
- attributes (map<string,string>): Custom span attributes
- events (array<struct>): Span events
  - name (string): Event name
  - timestamp (timestamp): Event time
  - attributes (map<string,string>): Event attributes

ASSESSMENTS (array<struct>)

- assessment_id (string): Assessment identifier
- name (string): Assessment name
- source (struct): Assessment source
  - source_type (string): One of {HUMAN, LLM_JUDGE, CODE}
  - source_id (string): Identifier of the source (e.g., user ID, judge ID)
- feedback (struct): Outcome of the assessment
  - value (string|numeric|boolean): Assessment result
  - error (string, optional): Error details if assessment failed
- expectation (struct): Ground-truth/expected value (if applicable)
  - value (string|numeric|boolean): Expected result
- rationale (string): Free-text explanation/notes
- metadata (map<string,string>): Additional context
- span_id (string, optional): Associated span ID (if scoped to a span)

## C. TOOLS (CLI Canon)

Use the short labels below from inside the workflow to avoid redefining commands.

### Traces

These tools help with analyzing traces. Each command contains a `--help` for clarification.

- **T1 (help)**: `uv run --env-file <env_file_path> python -m mlflow traces --help`
- **T2 (search)**: `uv run --env-file <env_file_path> python -m mlflow traces search --max-results N`
- **T3 (get)**: `uv run --env-file <env_file_path> python -m mlflow traces get --trace-id <id>`
- **T4 (SQL against the traces table)**: `uv run --env-file <env_file_path> python -m mlflow traces execute-sql --sql "<SQL>" --output "json"`
  - use sparingly only if search (T2) does not support the necessary filtering

### Insights

These tools help with interacting with Mlflow Insights. All state MUST be read/written through this CLI.

- **I1 (help)**: `uv run --env-file <env_file_path> python -m mlflow insights --help`

(Not an exhaustive list):

- **I2 (create analysis)**: `uv run --env-file <env_file_path> python -m mlflow insights create-analysis ...`
- **I4 (create baseline census)**: `uv run --env-file <env_file_path> python -m mlflow insights create-baseline-census --run-id <analysis_run_id>`
- **I5 (get baseline census)**: `uv run --env-file <env_file_path> python -m mlflow insights get-baseline-census --run-id <analysis_run_id>`
- **I6 (create hypothesis)**: `uv run --env-file <env_file_path> python -m mlflow insights create-hypothesis ... --sql-query '{"id":"Q1","query":"..."}'`
- **I7 (list hypotheses)**: `uv run --env-file <env> python -m mlflow insights list-hypotheses --run-id <rid> --output json`
- **I8 (update hypothesis)**: `uv run --env-file <env_file_path> python -m mlflow insights update-hypothesis --run-id <analysis_run_id> --hypothesis-id <hypothesis_id> --status VALIDATED|REJECTED|TESTING --evidence '{...}'`
- **I9 (create issue)**: `uv run --env-file <env_file_path> python -m mlflow insights create-issue --run-id <analysis_run_id> --hypothesis-id <hypothesis_id> ...`
- **I10 (get issue)**: `uv run --env-file <env_file_path> python -m mlflow insights get-issue --issue-id <issue_id>`

### Runs

- **R1 (link traces)**: `uv run --env-file <env_file_path> python -m mlflow runs link-traces --run-id <analysis_run_id> -t <trace-id-1> -t <trace-id-2> ...`

## D. GENERAL RULES (CRITICAL)

1. **No Internal Memory**: Do NOT track hypotheses, evidence, counts, or trace lists internally—always use the Insights CLI tools.
2. **Link Everything**: EVERY trace accessed via `search` or `get` must be linked to the analysis run (use R1) before deeper examination.
3. **Read State from CLI**: Always read hypothesis/issue state from CLI commands (I7/I10), not from internal memory.
4. **Testing Plans are CRITICAL**: Every hypothesis MUST have a detailed testing plan that references query IDs and attached SQL.
5. **Transparency and Visibility**: Announce the current hypothesis, show the testing plan and filters, periodically list hypotheses/issues (I7/I10).
6. **User Control and Interruption**: Immediately persist user adds/edits/rejections via I6/I8 and stop work on rejected items.
7. **Inline Python Only in Final Reporting Math**: never for exploration.

---

## E. WORKFLOW

### 1) Setup and Configuration

**1.1 Collect Experiment Information**

- If `.env` exists in current dir, use `--env-file .env`. Otherwise, collect auth and create an env file:

  - **Option 1: Local/Self-hosted MLflow**
    - Tracking URI examples: `sqlite:////path/to/mlflow.db`, `postgresql://user:pass@host:port/db`, `mysql://user:pass@host:port/db`, `file:///path/to/mlruns` or `/path/to/mlruns`
    - Env file (e.g., `mlflow.env`):
      ```
      MLFLOW_TRACKING_URI=<provided_uri>
      ```
  - **Option 2: Databricks**

    - **PAT Auth**: require `DATABRICKS_HOST` and `DATABRICKS_TOKEN`
    - **Profile Auth**: require `DATABRICKS_CONFIG_PROFILE`
    - Env file:

      ```
      # For PAT Auth:
      MLFLOW_TRACKING_URI=databricks
      DATABRICKS_HOST=<provided_host>
      DATABRICKS_TOKEN=<provided_token>

      # OR for Profile Auth:
      MLFLOW_TRACKING_URI=databricks
      DATABRICKS_CONFIG_PROFILE=<provided_profile>
      ```

  - **Option 3: Shell Env Already Set**
    - Ask for the path to the env file and reuse it.

**1.2 Test Trace Retrieval**

- Search 5 traces (T2) to verify existence and connectivity.

### 2) Analysis Phase

First, analyze a few traces to understand the agent's task. Write a short description (~1 paragraph) and present to the user. **WAIT** for confirmation from user.

Then start an analysis run, create a census, and generate hypotheses from what you know, the census, and other adhoc investigation that you would like to test. Present these to the user and **WAIT** for confirmation.

Sample commands:

```bash
uv run --env-file .env python -m mlflow insights create-analysis --run-name "<run name>" --name "Meeting Assistant Agent Quality Analysis" --description "<agent description>"

```

Then test the hypotheses, and create issues for the validated ones. Present the issues to the user and **WAIT** for confirmation.

**2.8 Generate Report**

- Retrieve artifacts:
  ```bash
  uv run --env-file <env_file_path> python -m mlflow insights list-hypotheses --run-id <analysis_run_id>
  uv run --env-file <env_file_path> python -m mlflow insights list-issues --experiment-id <experiment_id>
  uv run --env-file <env_file_path> python -m mlflow insights get-hypothesis --run-id <analysis_run_id> --hypothesis-id <hypothesis_id>
  uv run --env-file <env_file_path> python -m mlflow insights preview-issues --experiment-id <experiment_id> --max-traces 100
  uv run --env-file <env_file_path> python -m mlflow insights preview-hypotheses --run-id <analysis_run_id> --max-traces 100
  ```
- Ask user where to save the report (markdown file path).
- **Only now** use inline Python for statistics (never during exploration):
  - `uv run --env-file <env_file_path> python -c "..."`
- Report must include:
  - **Analysis Run Information**: run ID, UI link, counts (hypotheses created/tested; issues identified/validated).
  - **Summary statistics** (computed via inline Python): total traces analyzed; success rate (OK vs ERROR%); avg/median/p95 latency for successful traces; error-rate distribution by duration.
  - **Operational Issues**: title/severity; validated hypothesis; # supporting trace IDs; example excerpts; root cause; **trace IDs stored**; quantitative evidence.
  - **Quality Issues**: same structure as operational.
  - **Refuted Hypotheses**: status REJECTED + brief reason.
  - **Strengths**: validated positive hypotheses.
  - **Recommendations** and **Next Steps**:
    ```bash
    # For each issue, preview traces then log assessments in batch
    uv run --env-file <env_file_path> python -m mlflow insights preview-issues \
      --experiment-id <experiment_id> \
      --max-traces 1000
    ```

**2.9 Analysis Completion**

- Mark as completed (I3):
  ```bash
  uv run --env-file <env_file_path> python -m mlflow insights update-analysis \
    --run-id <analysis_run_id> \
    --status COMPLETED
  ```
- Reopen later if needed by setting `--status ACTIVE`.

## Example tool commands

### Search

`uv run --env-file .env python -m mlflow traces search --max-results 10 --extract-fields "info.trace_id,info.state,info.execution_duration_ms,info.trace_metadata.\`mlflow.traceInputs\`,info.trace_metadata.\`mlflow.traceOutputs\`" --output
json`
