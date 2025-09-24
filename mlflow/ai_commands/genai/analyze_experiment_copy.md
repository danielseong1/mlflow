# Analyze Experiment

Analyzes traces in an MLflow experiment for quality issues, performance problems, and patterns using the MLflow Insights CLI as a memory system for tracking hypotheses and findings.

## Key Concepts

This workflow uses the **MLflow Insights CLI** as an external memory system:

- **Analysis Run**: A special MLflow run that contains all investigation artifactsx`
- **Hypotheses**: Testable statements about patterns in the traces (stored as YAML artifacts)
- **Issues**: Validated problems with supporting evidence and trace IDs (stored as YAML artifacts)

**CRITICAL PRINCIPLES**

1. **No Internal Memory**: Do NOT track hypotheses, evidence, counts, or trace lists internally—always use the CLI.
2. **Link Everything**: EVERY trace accessed via `search` or `get` must be linked to the analysis run.
3. **Read State from CLI**: Always read hypothesis/issue state from CLI commands, not from memory.
4. **Testing Plans are CRITICAL**: Every hypothesis MUST have a detailed testing plan that guides subsequent trace searches.
5. **Census-Driven Hypotheses (Default)**: Generate hypotheses primarily from census buckets; also allow user/prior/anomaly sources, but anchor them back to census-style counts and denominators.

---

## Step 0: Understanding the CLI (CRITICAL)

Before beginning any investigation, confirm CLI syntax:

```bash
# Trace CLI help (searching/filtering)
uv run --env-file <env_file_path> python -m mlflow traces --help

# Insights CLI help (analyses, hypotheses, issues)
uv run --env-file <env_file_path> python -m mlflow insights --help

# Linking traces to runs
uv run --env-file <env_file_path> python -m mlflow runs link-traces --help
```

**IMPORTANT**: Understand the difference between `mlflow traces search` and `mlflow traces execute-sql`. Both commands can search traces but have different pros/cons. Use `mlflow traces search` when:

- Simple filtering by single fields (trace_id, status, execution_time_ms)
- Known trace IDs to retrieve specific traces
- Small result sets (< 100 traces)
- Quick exploration with built-in filters
- Direct field access without complex logic

Use `mlflow traces execute-sql` when:

- Complex queries with multiple conditions, JOINs, or aggregations
- Pattern matching in text fields (LIKE '%pattern%')
- Statistical analysis (COUNT, AVG, percentiles)
- Cross-span analysis (finding traces where multiple spans have errors)
- Large-scale analysis across entire dataset
- **IMPORTANT**: first check the table schema by running `mlflow traces execute-sql --help`

## Step 1: Setup and Configuration

### 1.1 Collect Experiment Information

**FIRST**: Check if `.env` file exists in current dir

**If .env file exists Skip to 1.2 Test Trace Retrieval using `--env-file .env`**

**If .env file does not exist**, proceed with manual configuration:

- **REQUIRED**: Ask user "How do you want to authenticate to MLflow?"

  **Option 1: Local/Self-hosted MLflow**

  - Ask for tracking URI (one of):
    - SQLite: `sqlite:////path/to/mlflow.db`
    - PostgreSQL: `postgresql://user:password@host:port/database`
    - MySQL: `mysql://user:password@host:port/database`
    - File Store: `file:///path/to/mlruns` or just `/path/to/mlruns`
  - Ask user to create an environment file (e.g., `mlflow.env`) containing:
    ```
    MLFLOW_TRACKING_URI=<provided_uri>
    ```

  **Option 2: Databricks**

  - Ask which authentication method:
    - **PAT Auth**: Request `DATABRICKS_HOST` and `DATABRICKS_TOKEN`
    - **Profile Auth**: Request `DATABRICKS_CONFIG_PROFILE` name
  - Ask user to create an environment file (e.g., `mlflow.env`) containing:

    ```
    # For PAT Auth:
    MLFLOW_TRACKING_URI=databricks
    DATABRICKS_HOST=<provided_host>
    DATABRICKS_TOKEN=<provided_token>

    # OR for Profile Auth:
    MLFLOW_TRACKING_URI=databricks
    DATABRICKS_CONFIG_PROFILE=<provided_profile>
    ```

  **Option 3: Environment Variables Already Set**

  - Ask user "Do you already have MLflow environment variables set in your shell (bashrc/zshrc)?"
  - If yes, get the path to the env file.

- Ask user for the path to their environment file (if using Options 1-2)
- Verify connection by listing experiments: `uv run --env-file <env_file_path> python -m mlflow experiments search --max-results 10`
- **Option to search by name**: If user knows the experiment name, use `--filter-string` parameter:
  - `uv run --env-file <env_file_path> python -m mlflow experiments search --filter-string "name LIKE '%experiment_name%'" --max-results 10`
- Ask user for experiment ID or let them choose from the list
- **WAIT for user response** - do not continue until they provide the experiment ID
- Add `MLFLOW_EXPERIMENT_ID=<experiment_id>` to their environment file

### 1.2 Test Trace Retrieval

- Call `uv run --env-file <env_file_path> python -m mlflow traces search --max-results 5` to verify:
  - Traces exist in the experiment
  - CLI is working properly (using local MLflow installation)
  - Database connection is valid

## Step 2: Analysis Phase

**CRITICAL: Memory Management via MLflow Insights CLI**

- **DO NOT** keep hypotheses, evidence, or trace lists in your internal memory
- **DO NOT** use inline Python scripts during this phase. Use MLflow CLI commands instead
- **ALWAYS** use MLflow Insights CLI commands to create, update, and read investigation state
- **EVERY** trace you access must be linked to the analysis run

### High-Level Principles

**User Control and Interruption**:

- User can interrupt at ANY time to:
  - Introduce a new hypothesis → immediately create via `mlflow insights create-hypothesis`
  - Ignore/abandon a hypothesis → immediately update via `mlflow insights update-hypothesis --status REJECTED`
  - When user says to ignore a hypothesis, STOP all work on it immediately
- All user inputs MUST be committed to MLflow Insights immediately via CLI

**Transparency and Visibility**:

- **ALWAYS show your work** as investigation progresses:
  - Display which hypothesis is currently being tested
  - **Show the testing plan** before executing it
  - Show preview of hypotheses periodically: `mlflow insights list-hypotheses --run-id ${run_id}`
  - Show preview of issues as created: `mlflow insights get-issue --issue-id ${issue_id}`
  - Display filtering logic used to validate/invalidate hypotheses

### 2.1.5 Understand Agent Purpose and Capabilities

- Analyze ~20 trace inputs/outputs to understand the agent's task:
  - Extract trace inputs/outputs: `--extract-fields info.trace_metadata.\`mlflow.traceInputs\`,info.trace_metadata.\`mlflow.traceOutputs\``
  - **LINK these traces** if you get specific trace IDs
  - Use: `uv run --env-file <env_file_path> python -m mlflow traces get --trace-id <id>` to examine traces in detail
  - Examine these fields to understand:
    - Types of questions users ask
    - Types of responses the agent provides
    - Common patterns in user interactions
  - Identify available tools by examining spans with type "TOOL":
    - What tools are available to the agent?
    - What data sources can the agent access?
    - What capabilities do these tools provide?
- Generate a 1-paragraph agent description covering:
  - **What the agent's job is** (e.g., "a boating agent that answers questions about weather and helps users plan trips")
  - **What data sources it has access to** (APIs, databases, etc.)
    **Present this description to the user** and ask for confirmation/corrections
- **WAIT for user response** - do not proceed until they confirm or provide corrections
- **Ask if they want to focus the analysis on anything specific** (or do a general report)
  - Their specific concerns should become initial hypotheses
- **WAIT for user response** before proceeding

### 2.1.6 Create MLflow Insights Analysis

Now that you understand the agent and user's focus, create an analysis run to track your investigation:

- **Create a short run name (3-4 words)** that captures the essence:

  - For general analysis: `"Full Analysis"`
  - For error investigation: `"Error Investigation"`
  - For performance issues: `"Latency Analysis"`
  - For quality issues: `"Quality Review"`
  - For user-specified focus: `"<Focus> Investigation"`

- **Create a descriptive analysis name** that provides full context:

  - General: `"Experiment <id> Comprehensive Analysis - <date>"`
  - Error focused: `"Error Pattern Analysis - <agent_name>"`
  - Performance: `"Latency Investigation - <agent_name>"`
  - Quality: `"Response Quality Analysis - <agent_name>"`
  - User focus: `"<User's Focus> Analysis - <agent_name>"`

  ```bash
  uv run --env-file <env_file_path> python -m mlflow insights create-analysis \
    --experiment-id <experiment_id> \
    --run-name "<Short 3-4 Word Title>" \
    --name "<Full Descriptive Analysis Name>" \
    --description "Agent: <agent description>. Focus: <user's specific areas or 'general analysis'>. Initial observations: <error rates, tools observed, patterns noticed>"
  ```

- **Save the returned run_id** - this will be your `<analysis_run_id>` for ALL subsequent commands
- **IMPORTANT**: This analysis run serves as your external memory for the entire investigation
- Use agent context + any specific focus areas for all subsequent hypothesis testing in sections 2.2+

### 2.1.7 Preliminary investigation

Goal is to identify areas that may need deeper investigation. You will generate hypotheses for these areas in the next step.

Compute a baseline census and review it:

```bash
uv run --env-file .env python -m mlflow insights create-baseline-census --run-id <analysis_run_id>
```

```bash
uv run --env-file .env python -m mlflow insights get-baseline-census \
  --run-id <analysis_run_id>
```

### 2.2 Document Known Issues from Census

After reviewing the census data, document any issues that are already validated facts. These are observable problems from the census that do not need further testing.

**IMPORTANT: Only create issues for OPERATIONAL METRICS from census, NOT quality metrics:**

**Valid issues from census (operational facts):**

- High trace error rate (e.g., "X% of traces have ERROR status")
- Specific span failures (e.g., "X spans fail in Y% of error cases")
- Extreme latency outliers (e.g., "Max latency reaches X+ minutes")
- Consistent tool/API errors (e.g., "X API fails 30% of the time")

**NOT valid issues from census (require hypothesis testing):**

- Quality metrics like verbosity percentages (proxy metric - needs manual validation)
- Response quality issues (requires examining actual content)
- Rushed processing metrics (needs investigation of actual processing quality)
- Minimal response rates (needs content analysis)

Create the issues:

```bash
# Create issue for each validated problem from census
uv run --env-file .env python -m mlflow insights create-issue \
  --run-id <analysis_run_id> \
  --title "<Concise issue title, e.g., 'Tool X Failures Affecting 30% of Traces'>" \
  --description "<Observable fact from census, e.g., '30% of traces (N out of M) have Y error'>. <User impact statement>. Impact: N traces affected. This issue was identified from census data." \
  --severity <HIGH|MEDIUM|LOW based on % affected> \
  --evidence '{"trace_id": "tr-sample-from-census", "rationale": "<span_name> span failed with ERROR status"}' \
  --evidence '{"trace_id": "another tr-sample-from-census", "rationale": ""}'
```

**IMPORTANT**: Summarize to the user the issues you created.

### 2.3 Generate Hypotheses for Investigation

Based on the census and sample traces you've examined, generate hypotheses about potential issues that need testing. These are suspected problems that require validation.

#### Testing Plan Requirements

**IMPORTANT**: Each hypothesis MUST have a detailed testing plan. The testing plan must:

- Be data-driven - each step produces specific trace IDs as evidence
- Be measurable - include a validation criteria that can definitively validate or reject the hypothesis
- Be systematic - list exact steps 1, 2, 3, etc. that will be followed. Write each step IN DETAIL.

#### Example hypotheses that need investigation

Example using manual verification:

```
Statement: Extract_action_items span failures cause "No action items identified" outputs despite transcripts containing clear action assignments

Rationale: 103 extract_action_items spans fail but traces show OK status - these may represent real action items that were missed

Testing Plan:

- Step 1: Query traces with extract_action_items span failures and link them to analysis
- Step 2: Examine transcript inputs from 10-15 sample traces to manually identify obvious action items (assignments, tasks, deadlines)
- Step 3: Compare manual findings with actual outputs to count missed action items
- Step 4: VALIDATE if number of traces with missed action items > 3.
```

Example using SQL queries:

```
Statement: Verbosity issues are caused by extraction failures triggering verbose fallback responses

Rationale: When the agent's extraction tools fail, it may compensate by producing longer responses to appear thorough

Testing Plan:

- Step 1: Use verbosity query from mlflow traces execute-sql --help to identify traces with short inputs (≤P25 request length) but verbose responses (>P90 response length)
- Step 2: Compare average span failure counts between verbose traces vs normal traces using SQL with size(filter(spans, s -> s.status_code = 'ERROR'))
- Step 3: Calculate causation ratio (avg failures in verbose / avg failures in normal)
- Step 4: VALIDATE if ratio ≥ 1.5 OR REJECT if < 1.5

```

Create the hypotheses:

```bash
uv run --env-file .env python -m mlflow insights create-hypothesis \
  --run-id <analysis_run_id> \
  --statement "<Hypothesis about potential issue>" \
  --rationale "<Why this needs investigation and potential impact>" \
  --testing-plan "<Step 1: Specific query or analysis> <Step 2: What to examine> <Step 3: How to validate/reject>"
```

**IMPORTANT**: Summarize created hypotheses to the user:

```
## Proposed Hypotheses for Investigation

1. **Hypothesis**: [Observable pattern to investigate]
   **Rationale**: [Why this might be important]
   **Testing Plan**:
      - Step 1: [Specific query or analysis]
      - Step 2: [What to examine]
      - Step 3: [How to validate/reject]
```

### 2.4 Test Hypotheses

- **IMPORTANT**: Fetch all hypotheses from Insights. Do not rely on memory.

#### Retrieving Hypotheses from Analysis Run

```bash
# Get full details in JSON format with complete IDs and all fields
uv run --env-file .env python -m mlflow insights list-hypotheses --run-id <analysis_run_id> --output json
```

#### Validating hypotheses

Follow the testing plan to collect evidence to validate the hypothesis. You can use the `mlflow traces search`, `mlflow traces execute-sql`, and `mlflow traces get_trace` commands to execute the testing plan.

**IMPORTANT: Print each step in the testing plan clearly to the user as you follow the plan.**

**Important: Link all examined traces to the analysis run:**

```bash
# Link traces before examining them
uv run --env-file .env python -m mlflow runs link-traces \
  --run-id <analysis_run_id> \
  -t <trace-id-1> -t <trace-id-2> -t <trace-id-3>
```

Continue until you have enough evidence to VALIDATE or REJECT the hypothesis. The
The evidence **must** contain traces that support or refute the hypothesis.

```bash
# Update with supporting or refuting evidence
uv run --env-file .env python -m mlflow insights update-hypothesis \
  --run-id <analysis_run_id> \
  --hypothesis-id <hypothesis_id> \
  --status VALIDATED|REJECTED|TESTING \
  --evidence '{"trace_id": "tr-xxx", "rationale": "Description of finding", "supports": true|false}'
```

**Note**: If any new hypotheses come up during validation, add them and do validation on them as well

### 2.6 Convert Validated Hypotheses to Issues

After testing all hypotheses, convert validated ones to issues.

**IMPORTANT**: Issue titles should be specific and actionable (5-8 words), like JIRA titles
Good examples:

- "Database query tool exceeds 30s timeout threshold"
- "Weather API returns 500 errors during peak hours"
- "Response generation adds 500+ unnecessary words"
- "Authentication failures block 25% of user requests"

Bad examples (too generic):

- "Tool timeout"
- "Performance issue"
- "Error handling"

```bash
# First get evidence from the hypothesis
uv run --env-file <env_file_path> python -m mlflow insights get-hypothesis \
  --run-id <analysis_run_id> \
  --hypothesis-id <hypothesis_id>

# Create the issue using evidence from hypothesis or new evidence
uv run --env-file <env_file_path> python -m mlflow insights create-issue \
  --run-id <analysis_run_id> \
  --hypothesis-id <hypothesis_id> \
  --title "Tool X timeouts exceed 30s affecting queries" \
  --description "Tool X consistently times out after 30s, affecting 25% of queries during peak hours. Connection pool appears exhausted." \
  --severity <HIGH|MEDIUM|LOW depending on the impact> \
  --evidence '<use ones from hypothesis>' \
  --evidence '<use ones from hypothesis>' \
  ...

# Read the issue to confirm it was created:
uv run --env-file <env_file_path> python -m mlflow insights get-issue \
  --issue-id <issue_id>
```

### 2.7 Generate Report

**First, retrieve all analysis artifacts from MLflow Insights**:

```bash
# List all hypotheses from the analysis
uv run --env-file <env_file_path> python -m mlflow insights list-hypotheses \
  --run-id <analysis_run_id>

# List all issues from the experiment (no --run-id needed, issues are experiment-level)
uv run --env-file <env_file_path> python -m mlflow insights list-issues \
  --experiment-id <experiment_id>

# Get detailed information for each hypothesis/issue as needed
uv run --env-file <env_file_path> python -m mlflow insights get-hypothesis \
  --run-id <analysis_run_id> \
  --hypothesis-id <hypothesis_id>

# Preview traces for all issues to get trace data
uv run --env-file <env_file_path> python -m mlflow insights preview-issues \
  --experiment-id <experiment_id> \
  --max-traces 100

# Preview traces for hypotheses if needed
uv run --env-file <env_file_path> python -m mlflow insights preview-hypotheses \
  --run-id <analysis_run_id> \
  --max-traces 100
```

- Ask user where to save the report (markdown file path)
- **ONLY NOW use uv inline Python scripts for statistical calculations** - never compute stats manually
- Inline Python scripts are ONLY for final math/statistics, NOT for trace exploration
- Use `uv run --env-file <env_file_path> python -c "..."` for any Python calculations that need MLflow access
- Generate a single comprehensive markdown report with:

  - **Analysis Run Information**:
    - Analysis run ID and link to MLflow UI
    - Total hypotheses created and tested
    - Total issues identified and validated
  - **Summary statistics** (computed via `uv run --env-file <env_file_path> python -c "..."` with collected trace data):
    - Total traces analyzed (count linked traces)
    - Success rate (OK vs ERROR percentage)
    - Average, median, p95 latency for successful traces
    - Error rate distribution by duration (fast fails vs timeouts)
  - **Operational Issues** (errors, latency, performance):
    - For each ISSUE created from operational hypotheses:
      - Issue title and severity
      - Clear statement of the validated hypothesis
      - Number of supporting trace IDs
      - Example trace excerpts (input/output)
      - Root cause analysis: WHY the issue occurs
      - **Trace IDs stored**: List of trace IDs saved in the issue for future assessment logging
      - Quantitative evidence (frequency, timing patterns, etc.)
  - **Quality Issues** (content problems, user experience):
    - For each ISSUE created from quality hypotheses:
      - Issue title and severity
      - Clear statement of the validated hypothesis
      - Number of supporting trace IDs
      - Example trace excerpts (input/output)
      - **Trace IDs stored**: List of trace IDs saved in the issue for future assessment logging
      - Quantitative evidence (frequency patterns, etc.)
  - **Refuted Hypotheses** (from MLflow Insights):
    - List hypotheses with status REJECTED and brief reason
  - **Strengths** (validated positive hypotheses):
    - What's working well based on validated hypotheses
  - **Recommendations** for improvement based on confirmed issues
  - **Next Steps**:

    - How to retrieve traces for batch assessment logging:

      ```bash
      # For each issue, preview traces:
      uv run --env-file <env_file_path> python -m mlflow insights preview-issues \
        --experiment-id <experiment_id> \
        --max-traces 1000

      # Then log assessments on those traces as needed
      ```

### 2.8 Analysis Completion

Once all hypotheses have been tested, issues reviewed, and the report generated:

```bash
# Mark the analysis as completed
uv run --env-file <env_file_path> python -m mlflow insights update-analysis \
  --run-id <analysis_run_id> \
  --status COMPLETED
```

This indicates:

- The investigation is complete
- All hypotheses have been tested (validated/rejected)
- Issues have been created and reviewed
- No further active investigation is planned

**Note**: An analysis can be reopened later by updating status back to ACTIVE if new evidence emerges:

```bash
# Reopen analysis if needed
uv run --env-file <env_file_path> python -m mlflow insights update-analysis \
  --run-id <analysis_run_id> \
  --status ACTIVE
```
