---
namespace: genai
description: Analyzes the traces logged in an MLflow experiment to find operational and quality issues automatically, generating a markdown report.
---

# Analyze Experiment

Analyzes traces in an MLflow experiment for quality issues, performance problems, and patterns.

# EXECUTION CONTEXT

**MCP**: Skip to Section 1.2 (auth is pre-configured). Use MCP trace tools.
**CLI**: Start with Section 1.1 for auth setup. Use `mlflow traces` commands.

## Step 0: Understanding the CLI (CRITICAL - DO THIS FIRST)

**BEFORE asking the user ANY questions**, review the CLI syntax by running these commands:

```bash
# Review trace CLI overview and schema
uv run python -m mlflow traces --help

# Review search command syntax
uv run python -m mlflow traces search --help

# Review get command syntax
uv run python -m mlflow traces get --help
```

**IMPORTANT CLI USAGE NOTE:**

- **ALWAYS use `--extract-fields` flag** to filter output from `mlflow traces search` and `mlflow traces get`
- **NEVER pipe to grep, python, jq, or other tools** for field extraction
- The `--extract-fields` flag is more efficient, cleaner, and handles JSON paths natively

## Step 1: Setup and Configuration

### 1.1 Collect Tracking Server Information (CLI Only)

- **NOW ask user**: "How do you want to authenticate to MLflow?"

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
  - If yes, test connection directly: `uv run python -m mlflow experiments search --max-results 10`
  - If this works, skip env file creation and use commands without `--env-file` flag
  - If not, fall back to Options 1 or 2

- Ask user for the path to their environment file (if using Options 1-2)
- Test connection: `uv run --env-file <env_file_path> python -m mlflow experiments search --max-results 5`

### 1.2 Select Experiment and Test Trace Retrieval

- If MLFLOW_EXPERIMENT_ID not already set, list available experiments and ask user to select one:

  - **Option to search by name**: Use filter_string parameter for name search
  - Ask user for experiment ID or let them choose from the list
  - **WAIT for user response** - do not continue until they provide the experiment ID
  - For CLI: Add `MLFLOW_EXPERIMENT_ID=<experiment_id>` to environment file

- Call `uv run --env-file <env_file> python -m mlflow traces search --max-results 5 --extract-fields "info.trace_id"` to verify:
  - Traces exist in the experiment
  - Tools are working properly
  - Connection is valid
- Extract sample trace IDs for testing
- Get one full trace by trace_id that has state OK to understand the data structure (errors might not have the structure)
  - Use: `uv run --env-file <env_file_path> python -m mlflow traces get --trace-id <id>`

## Step 2: Analysis Phase

### 2.1 Understand Agent Purpose and Capabilities

- Analyze trace inputs/outputs to understand the agent's task:

  - Extract key fields:

    ```bash
    uv run --env-file <env_file> python -m mlflow traces search --max-results 20 --extract-fields 'info.trace_id,info.trace_metadata.`mlflow.traceInputs`,info.trace_metadata.`mlflow.traceOutputs`' --output json
    ```

  - Examine these fields to understand:
    - Types of questions users ask
    - Types of responses the agent provides
    - Common patterns in user interactions
  - Identify available tools by examining spans:
    ```bash
    uv run --env-file .env python -m mlflow traces get --trace-id tr-56e0559110fc332d228e2220e68c5862 --extract-fields 'data.spans.*.name,data.spans.*.attributes.`mlflow.spanType`'
    ```
    - Look for spans with type TOOL
    - What tools are available to the agent?
    - What data sources can the agent access?
    - What capabilities do these tools provide?

### 2.2 Review Baseline census

Review the existing baseline census to get an overview of the agent's metrics.

```bash
uv run --env-file <env_file> python -m mlflow insights get-baseline-census \
  --run-id 735002a0a8b841168e29152bcb2787b1
```

### 2.3 Generate Agent Summary and Observations

- Using results from step 2.1 and 2.2, generate a 1-paragraph agent description covering:
  - **What the agent's job is** (e.g., "a boating agent that answers questions about weather and helps users plan trips")
  - **What data sources it has access to** (APIs, databases, etc.)
  - **Observations**: Areas with potential issues that need further investigation. You will focus on these areas in the Issues Analysis in next step.
- **Present this description to the user**

### 2.4 Initialize Report Template

Before beginning hypothesis testing, create the report template:

- Ask user where to save the report (markdown file path, e.g., `experiment_analysis.md`)
- Create the report using the CLI:

```bash
uv run --env-file <env_file> python -m mlflow insights create-analysis-report \
  --filepath <report_filepath> \
  --agent-name "<Agent Name>" \
  --agent-overview "<agent overview from step 2.3>"
```

Remember the file path. You will use it later as <report_filepath> when updating the analysis report.

### 2.5 Issues Analysis (Hypothesis-Driven Approach)

**IMPORTANT**: Make sure you have completed steps 2.1, 2.2, 2.3, and 2.4 before moving forward.

Use the results from the census and the traces you've analyzed to identify issues with the agent using a hypothesis-driven approach.

#### Step 1: Choose Analysis Area

Systematically investigate issues across THREE distinct areas:

1. **Operational Issues**: Errors, latency, performance problems

   - _Error Analysis_: Any errors MUST be examined. examine tool/API failures, rate limiting, authentication errors, timeouts, input validation failures, resource unavailability
   - _Performance Problems_: abnormaly long latencies, examine tool call duration patterns, sequential vs parallel execution, slow APIs/tools, cold start patterns, resource contention

2. **Quality Issues**: Response quality, content problems, user experience

   - _Content Quality_: examine verbosity, repetition, context carryover, question-asking vs task-completion, response consistency, information accuracy, format appropriateness

3. **Strengths & Successes**: What's working well
   - _Successful Interactions_: Filter for OK traces with good outcomes; identify comprehensive responses, consistent high-quality answers, appropriate tool usage
   - _Effective Tool Usage_: Examine successful tool usage; identify appropriate tool selection, beneficial multi-step usage, effective tool combinations

#### Step 2: Form Specific Hypothesis

Based on census data and trace patterns, form a specific, testable hypothesis.

**IMPORTANT**: Clearly state the hypothesis you are testing before proceeding to validation.

**Example format:**

- **Hypothesis**: "High-latency traces (>20s) are caused by excessive sequential tool calls"

**Example hypotheses:**

- "High-latency traces (>20s) are caused by excessive sequential tool calls"
- "Error traces fail due to rate limiting from external APIs"
- "Responses are overly verbose when multi-step reasoning is required"
- "Agent successfully handles simple factual queries with 1-2 tool calls"

#### Step 3: Validate Hypothesis

**Use the following tools for your analysis:**

1. `mlflow traces search`: Search for traces matching specific criteria

   - Use filter_string to narrow down to relevant traces
   - Use `--extract-fields` to filter output. AVOID piping result to python or grep commands

2. `mlflow traces get`: Get full details of specific traces
   - Use to examine detailed trace structure
   - Use `--extract-fields` to filter output. AVOID piping result to python or grep commands

**Show your thinking as you go**: Always explain:

- Current hypothesis being tested
- Evidence found: ALWAYS show BOTH trace input (user request) AND trace output (agent response), plus tools called
- Reasoning for supporting/refuting the hypothesis

**You MUST complete this checklist for EVERY hypothesis before marking it as CONFIRMED:**

- [ ] **5-10 representative trace examples with full context**

  - Each trace example MUST include a rationale for why this trace confirms/refutes the hypothesis

- [ ] **Mechanistic explanation of WHY pattern occurs**
  - Examine the detailed trace structure to understand WHY the pattern occurs
  - Answer: What is the causal chain that leads to this issue?
  - Answer: What specific agent behaviors or tool interactions cause the problem?
  - Answer: Is this correlation or causation? How do you know?
  - Explain causal chain, not just correlation
  - Example: "Sequential tool execution occurs because the agent waits for each tool result before deciding on the next action, rather than batching independent queries"

#### Step 4: Mark Hypothesis Status

Based on checklist completion:

- **CONFIRMED**: All checklist items complete
- **POSSIBLE**: 1 checklist items complete, strong supporting evidence
- **REFUTED**: Evidence contradicts hypothesis

#### Step 4.5: Update Report Incrementally

**If hypothesis is CONFIRMED**, immediately add it to the report file using the CLI:

For **Operational or Quality Issues**:

```bash
uv run --env-file <env_file> python -m mlflow insights add-report-issue \
  --filepath <report_filepath> \
  --category operational  # or "quality" \
  --title "Issue Title" \
  --finding "Summary of the issue including potential user impact" \
  --evidence '[
    {
      "trace_id": "<trace_id>",
      "latency_ms": <number>,  # Optional - include for operational issues only
      "request": "<user request text>",
      "response": "<agent response text>",
      "rationale": "DETAILED explanation of how this trace supports the hypothesis. Must include: (1) Which specific parts of trace demonstrate the issue (2) What behaviors/patterns show the problem (3) Relevant details like tool calls, durations, errors"
    },
    {...additional traces...}
  ]' \
  --root-cause "Detailed explanation of WHY this pattern occurs" \
  --impact "Quantified impact with specific numbers"
```

**IMPORTANT**: The evidence rationale field is REQUIRED and must be detailed. It should clearly explain:
- Which specific parts of the trace support your hypothesis
- What agent behaviors or patterns demonstrate the issue
- How this trace exemplifies the problem (include tool calls, durations, error messages, etc.)

For **Strengths**:

```bash
uv run --env-file <env_file> python -m mlflow insights add-report-strength \
  --filepath <report_filepath> \
  --title "Strength Title" \
  --description "What's working well" \
  --evidence '[
    "<metric or observation 1>",
    "<metric or observation 2>",
    "Example: <trace_id> completed in <duration>ms"
  ]'
```

**If hypothesis is REFUTED**, add it to the report:

```bash
uv run --env-file <env_file> python -m mlflow insights add-report-refuted \
  --filepath <report_filepath> \
  --hypothesis "Hypothesis statement" \
  --reason "Brief explanation of why it was refuted"
```

**If hypothesis is POSSIBLE**, hold off on adding to report - continue investigation or note for future work.

#### Step 5: Repeat for Next Hypothesis

Return to Step 2 and repeat the process for the next hypothesis. Continue until you have investigated all relevant patterns across the three analysis areas (Operational Issues, Quality Issues, Strengths & Successes). **Do not stop until you have gone through > 20 hypotheses OR you cannot come up with more hypotheses.**

### 2.6 Finalize Report

At this point, the report should already contain all confirmed hypotheses added incrementally during step 4.5 of section 2.5. Now complete the remaining sections.

**Steps to prepare the finalization data:**

1. **Calculate Summary Statistics** using Python:

   - Use trace data collected during analysis to compute exact statistics
   - Format statistics as JSON object

2. **Draft Executive Summary**:

   - Brief overview of agent purpose (from step 2.3)
   - Top 3 most critical issues identified (from confirmed hypotheses)
   - Overall assessment

3. **Organize Recommendations**:

   - Based on all confirmed issues, categorize recommendations
   - Organize by: Immediate Actions, Performance Improvements, Quality Enhancements, Monitoring Recommendations

4. **Write Conclusion**:
   - Summarize key findings
   - Highlight most impactful improvements
   - Suggest metrics to track post-improvements

**Once you have prepared all the data, finalize the report using the CLI:**

```bash
uv run --env-file <env_file> python -m mlflow insights finalize-report \
  --filepath <report_filepath> \
  --executive-summary "Brief overview of agent purpose and top 3 critical issues. Overall assessment." \
  --statistics '{
    "total_traces": <number>,
    "success_rate": "<percentage>",
    "p50_latency": "<value>ms",
    "p90_latency": "<value>ms",
    "p95_latency": "<value>ms",
    "p99_latency": "<value>ms",
    "max_latency": "<value>ms",
    "analysis_period": "<start date> - <end date>"
  }' \
  --recommendations '{
    "immediate_actions": [
      "<action 1>",
      "<action 2>"
    ],
    "performance_improvements": [
      "<improvement 1>",
      "<improvement 2>"
    ],
    "quality_enhancements": [
      "<enhancement 1>",
      "<enhancement 2>"
    ],
    "monitoring_recommendations": [
      "<recommendation 1>",
      "<recommendation 2>"
    ]
  }' \
  --conclusion "Summarize key findings, highlight most impactful improvements, and suggest metrics to track post-improvements."
```
