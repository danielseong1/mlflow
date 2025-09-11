# Analyze Experiment

Analyzes traces in an MLflow experiment for quality issues, performance problems, and patterns using the MLflow Insights CLI as a memory system for tracking hypotheses and findings.

## Key Concepts

This workflow uses the **MLflow Insights CLI** as an external memory system:
- **Analysis Run**: A special MLflow run that contains all investigation artifacts
- **Hypotheses**: Testable statements about patterns in the traces (stored as YAML artifacts)
- **Issues**: Validated problems with supporting evidence and trace IDs (stored as YAML artifacts)
- **Trace Linking**: Every trace examined is linked to the analysis run for full lineage

**CRITICAL PRINCIPLES**:
1. **No Internal Memory**: Do NOT track hypotheses, evidence, or trace lists internally - always use the CLI
2. **Link Everything**: EVERY trace accessed via `search` or `get` must be linked to the analysis run
3. **Defer Assessments**: Store trace IDs in issues, log assessments later in batch (not during analysis)
4. **Read State from CLI**: Always read hypothesis/issue state from CLI commands, not from memory
5. **Testing Plans are CRITICAL**: Every hypothesis MUST have a detailed testing plan that guides all subsequent trace searches

## Step 0: Understanding the CLI (CRITICAL STEP)

Before beginning any investigation, you MUST understand the exact CLI syntax:

```bash
# Understand trace CLI capabilities for searching and filtering
uv run --env-file <env_file_path> python -m mlflow traces --help

# Understand insights CLI commands and their exact parameters  
uv run --env-file <env_file_path> python -m mlflow insights --help

# Understand how to link traces to runs
uv run --env-file <env_file_path> python -m mlflow runs link-traces --help
```

This ensures you know:
- Exact parameter names and formats
- Available filtering options for traces
- Proper JSON structure for --evidence flags
- How to link traces to analysis runs
- How to chain commands together

## Step 1: Setup and Configuration

### 1.1 Collect Experiment Information
- **REQUIRED FIRST**: Ask user "How do you want to authenticate to MLflow?"
  
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
- Extract sample trace IDs for testing
- Get one full trace by trace_id that has state OK to understand the data structure (errors might not have the structure)
  - Use: `uv run --env-file <env_file_path> python -m mlflow traces get --trace-id <id>`

## Step 2: Analysis Phase

**CRITICAL: Memory Management via MLflow Insights CLI**
- **DO NOT** keep hypotheses, evidence, or trace lists in your internal memory
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

**Testing Plan is CRITICAL**:
- Every hypothesis MUST have a detailed testing plan
- The plan guides ALL subsequent trace searches
- Show the plan to the user before executing
- Update the plan if new patterns emerge

### 2.1 Bulk Trace Collection

- Search for a larger sample using `--max-results` parameter (start with 20-50 traces for initial analysis)
- **IMPORTANT**: Use `--max-results` to limit results for users with hundreds of thousands of experiments/traces
- Extract key fields: trace_id, state, execution_duration_ms, request_preview, response_preview
- **LINK ALL TRACES**: After searching, immediately link found traces to the analysis run:
  ```bash
  uv run --env-file <env_file_path> python -m mlflow runs link-traces \
    --run-id <analysis_run_id> \
    --trace-ids <comma-separated-trace-ids>
  ```

### 2.1.5 Understand Agent Purpose and Capabilities
- Analyze trace inputs/outputs to understand the agent's task:
  - Extract trace inputs/outputs: `--extract-fields info.trace_metadata.\`mlflow.traceInputs\`,info.trace_metadata.\`mlflow.traceOutputs\``
  - **LINK these traces** if you get specific trace IDs
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
- **Present this description to the user** and ask for confirmation/corrections
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

### 2.2 Operational Issues Analysis (Hypothesis-Driven Approach)
**NOTE: Use MLflow CLI commands for trace exploration - DO NOT use inline Python scripts during this phase**
**CRITICAL: Use MLflow Insights CLI as your memory - DO NOT track hypotheses internally**

**Hypothesis Management Process**:
1. **Create hypothesis** in MLflow Insights for each pattern you want to test
2. **Search/get traces** to test the hypothesis (and link them!)
3. **Update hypothesis** with evidence and trace IDs
4. **Read hypothesis** state when needed (don't rely on memory)
5. **Convert to issue** when validated with sufficient evidence

**Show your thinking as you go**: Always explain your hypothesis development process including:
- Current hypothesis being tested (show the create-hypothesis command)
- **Display the testing plan** to the user before executing it
- Evidence found: ALWAYS show BOTH trace input (user request) AND trace output (agent response), plus tools called
- Reasoning for supporting/refuting the hypothesis (show the update-hypothesis command)

Process traces in batches of 10, building and refining hypotheses with each batch:
1. Form initial hypotheses from first batch - CREATE them via CLI
2. With each new batch: validate, refute, or expand hypotheses - UPDATE them via CLI
3. Continue until patterns stabilize - READ hypotheses via CLI to check status

- **Error Analysis**

  - Filter for ERROR traces: `uv run --env-file <env_file_path> python -m mlflow traces search --filter "info.state = 'ERROR'" --max-results 10`
  - **LINK these traces**: `uv run --env-file <env_file_path> python -m mlflow runs link-traces --run-id <analysis_run_id> --trace-ids <trace-ids>`
  - **Adjust --max-results as needed**: Start with 10-20, increase if you need more examples to identify patterns
  - **Create hypotheses** for patterns you want to test:
    ```bash
    # Show user what hypothesis is being created WITH testing plan
    echo "Creating hypothesis: Tool X consistently fails with timeout errors"
    echo "Testing Plan: To investigate whether Tool X is causing timeout failures, I will search for traces with execution_time > 30s and examine their tool spans for Tool X invocations..."
    
    uv run --env-file <env_file_path> python -m mlflow insights create-hypothesis \
      --run-id <analysis_run_id> \
      --statement "Tool X consistently fails with timeout errors" \
      --testing-plan "To investigate whether Tool X is causing timeout failures, I will search for traces with execution_time > 30s and examine their tool spans for Tool X invocations, specifically looking for patterns like 'timeout', 'connection refused', or execution times exceeding 30s. Supporting evidence would include multiple traces where Tool X takes >30s to respond or returns timeout errors. For refutation, I'll search for successful traces that use Tool X with response times <5s, which would indicate the tool itself isn't inherently broken. I'll also look for ERROR traces that don't involve Tool X at all. The hypothesis is validated if >70% of Tool X invocations result in timeouts and these timeouts account for the majority of ERROR traces. It's invalidated if Tool X works reliably in most cases or if errors occur without Tool X involvement." \
      --evidence '{"trace_id": "tr-001", "rationale": "Tool X timed out after 32s with connection timeout error", "supports": true}' \
      --evidence '{"trace_id": "tr-002", "rationale": "Tool X succeeded in 2s, showing it can work properly", "supports": false}'
    ```
  
  - **Execute the testing plan - show filtering strategy to user**:
    ```bash
    echo "Executing testing plan for hypothesis:"
    echo "Step 1: Finding traces with Tool X failures"
    uv run --env-file <env_file_path> python -m mlflow traces search \
      --filter "info.state = 'ERROR' AND spans.name CONTAINS 'Tool X'" \
      --max-results 20
    
    echo "Step 2: Finding control group - successful Tool X invocations"
    uv run --env-file <env_file_path> python -m mlflow traces search \
      --filter "info.state = 'OK' AND spans.name CONTAINS 'Tool X'" \
      --max-results 10
    ```
  
  - **Pattern Analysis Focus**: Identify WHY errors occur by examining:
    - Tool/API failures in spans (look for spans with type "TOOL" that failed)
    - Rate limiting responses from external APIs
    - Authentication/permission errors
    - Timeout patterns (compare execution_duration_ms)
    - Input validation failures
    - Resource unavailability (databases, services down)
  
  - Example hypotheses to test (CREATE each via CLI with detailed testing plans):
    - Certain types of queries consistently trigger tool failures
    - Errors cluster around specific time ranges (service outages)
    - Fast failures (~2s) indicate input validation vs slower failures (~30s) indicate timeouts
    - Specific tools/APIs are unreliable and cause cascading failures
    - Rate limiting from external services causes batch failures
  
  - **Update hypotheses** with evidence as you find it:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights update-hypothesis \
      --run-id <analysis_run_id> \
      --hypothesis-id <hypothesis_id> \
      --status VALIDATED \
      --evidence '{"trace_id": "tr-003", "rationale": "Tool X timeout after 35s during peak hours", "supports": true}' \
      --evidence '{"trace_id": "tr-004", "rationale": "Tool X connection refused, service appears down", "supports": true}' \
      --evidence '{"trace_id": "tr-005", "rationale": "Error occurred without Tool X being invoked", "supports": false}'
    ```
  
  - **Show current hypothesis state to user**:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights get-hypothesis \
      --run-id <analysis_run_id> \
      --hypothesis-id <hypothesis_id>
    ```
  
  - **Note**: You may discover other operational error patterns as you analyze the traces

- **Performance Problems (High Latency Analysis)**
  - Filter for OK traces with high latency: `uv run --env-file <env_file_path> python -m mlflow traces search --filter "info.state = 'OK'" --max-results 10`
  - **LINK these traces**: `uv run --env-file <env_file_path> python -m mlflow runs link-traces --run-id <analysis_run_id> --trace-ids <trace-ids>`
  - **Adjust --max-results as needed**: Start with 10-20, increase if you need more examples to identify patterns
  - **Create hypotheses** for performance patterns with detailed testing plans:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights create-hypothesis \
      --run-id <analysis_run_id> \
      --statement "Complex queries with multiple sequential tool calls have multiplicative latency" \
      --testing-plan "To investigate whether sequential tool calls cause multiplicative latency, I will search for traces with execution_time > 20s and count the number of sequential (non-parallel) tool invocations in their spans. Supporting evidence would include traces where total time equals roughly the sum of individual tool times, indicating no parallelization. For refutation, I'll look for complex queries with many tools that execute quickly (<5s), suggesting proper parallelization. I'll also examine simple queries with single tools that are still slow, which would indicate the problem isn't about sequencing. The hypothesis is validated if traces with 3+ sequential tools consistently take >20s and the execution time correlates linearly with tool count. It's invalidated if execution time doesn't correlate with sequential tool count or if parallel execution is observed." \
      --evidence '{"trace_id": "tr-010", "rationale": "5 sequential tool calls totaling 25s (5s each), no parallelization", "supports": true}'
    ```
  - **Pattern Analysis Focus**: Identify WHY traces are slow by examining:
    - Tool call duration patterns in spans
    - Number of sequential vs parallel tool calls
    - Specific slow APIs/tools (database queries, web requests, etc.)
    - Cold start vs warm execution patterns
    - Resource contention indicators
  - Example hypotheses to test (CREATE each via CLI with testing plans):
    - Complex queries with multiple sequential tool calls have multiplicative latency
    - Certain tools/APIs are consistent performance bottlenecks (>5s per call)
    - First queries in sessions are slower due to cold start overhead
    - Database queries without proper indexing cause delays
    - Network timeouts or retries inflate execution time
    - Parallel tool execution is not properly implemented
  - **Note**: You may discover other performance patterns as you analyze the traces

### 2.3 Quality Issues Analysis (Hypothesis-Driven Approach)
**NOTE: Use MLflow CLI commands for trace exploration - DO NOT use inline Python scripts during this phase**
**CRITICAL: Continue using MLflow Insights CLI as your memory**

Focus on response quality, not operational performance:

- **Content Quality Issues**
  - Sample both OK and ERROR traces
  - **LINK all accessed traces** to your analysis run
  - **Create hypotheses** for each quality pattern you want to investigate:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights create-hypothesis \
      --run-id <analysis_run_id> \
      --statement "Agent provides overly verbose responses for simple questions" \
      --testing-plan "To investigate whether the agent is overly verbose for simple questions, I will search for traces with simple yes/no or single-fact questions and measure their response lengths. Supporting evidence would include responses >500 words for questions that could be answered in a sentence. For refutation, I'll look for complex questions that receive appropriately detailed responses, and simple questions with concise answers. I'll also check if verbosity correlates with specific question types or user phrasings. The hypothesis is validated if >60% of simple questions receive responses over 200 words when <50 words would suffice. It's invalidated if response length appropriately matches question complexity or if verbose responses only occur for genuinely complex queries." \
      --evidence '{"trace_id": "tr-020", "rationale": "Yes/no question received 500+ word response with unnecessary context", "supports": true}' \
      --evidence '{"trace_id": "tr-021", "rationale": "Complex multi-part question received appropriately detailed response", "supports": false}'
    ```
  - Example hypotheses to test (CREATE each via CLI with testing plans):
    - Agent provides overly verbose responses for simple questions
    - Some text/information is repeated unnecessarily across responses
    - Conversation context carries over inappropriately
    - Agent asks follow-up questions instead of attempting tasks
    - Responses are inconsistent for similar queries
    - Agent provides incorrect or outdated information
    - Response format is inappropriate for the query type
  - **When you find evidence**, update the hypothesis:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights update-hypothesis \
      --run-id <analysis_run_id> \
      --hypothesis-id <hypothesis_id> \
      --evidence '{"trace_id": "tr-022", "rationale": "Another yes/no question with 600 word response", "supports": true}' \
      --evidence '{"trace_id": "tr-023", "rationale": "Simple factual question answered concisely in 2 sentences", "supports": false}'
    ```
  - **Note**: You may discover other quality issues as you analyze the traces

### 2.4 Strengths and Successes Analysis (Hypothesis-Driven Approach)
**NOTE: Use MLflow CLI commands for trace exploration - DO NOT use inline Python scripts during this phase**
**CRITICAL: Continue using MLflow Insights CLI as your memory**

Process successful traces to identify what's working well:

- **Successful Interactions**
  - Filter for OK traces with good outcomes
  - **LINK all accessed traces** to your analysis run
  - **Create hypotheses** for positive patterns:
    ```bash
    uv run --env-file <env_file_path> python -m mlflow insights create-hypothesis \
      --run-id <analysis_run_id> \
      --statement "Agent provides comprehensive, helpful responses for complex multi-tool queries" \
      --testing-plan "To validate that the agent excels at complex multi-tool queries, I will search for traces with 3+ tool invocations and execution_time < 10s with status OK. Supporting evidence would include traces where multiple tools are coordinated effectively to provide comprehensive answers. For refutation, I'll look for complex queries that fail or timeout, or simple queries that unnecessarily invoke multiple tools. The hypothesis is validated if >80% of multi-tool queries complete successfully with coherent integration of tool results. It's invalidated if multi-tool coordination frequently fails or if tools are invoked unnecessarily." \
      --evidence '{"trace_id": "tr-030", "rationale": "Coordinated 4 tools effectively to answer complex travel planning query", "supports": true}'
    ```
  - Example hypotheses to test (CREATE each via CLI with testing plans):
    - Agent provides comprehensive, helpful responses for complex queries
    - Certain types of questions consistently get high-quality answers
    - Tool usage is appropriate and effective for specific scenarios
    - Response format is well-structured for particular use cases

- **Effective Tool Usage**
  - Examine traces where tools are used successfully
  - Example hypotheses to test (CREATE each via CLI with testing plans):
    - Agent selects appropriate tools for different query types
    - Multi-step tool usage produces better outcomes
    - Certain tool combinations work particularly well together

- **Quality Responses**
  - Identify traces with good response quality
  - Example hypotheses to test (CREATE each via CLI with testing plans):
    - Agent provides right level of detail for complex questions
    - Safety/important information is appropriately included
    - Agent successfully handles follow-up questions in context

### 2.5 Convert Validated Hypotheses to Issues

After testing all hypotheses, convert validated ones to issues:

```bash
# For each validated hypothesis with problems/issues:
# IMPORTANT: Issue titles should be specific and actionable (5-8 words), like JIRA titles
# Good examples:
#   - "Database query tool exceeds 30s timeout threshold"
#   - "Weather API returns 500 errors during peak hours"
#   - "Response generation adds 500+ unnecessary words"
#   - "Authentication failures block 25% of user requests"
# Bad examples (too generic):
#   - "Tool timeout"
#   - "Performance issue"
#   - "Error handling"

uv run --env-file <env_file_path> python -m mlflow insights create-issue \
  --run-id <analysis_run_id> \
  --hypothesis-id <hypothesis_id> \
  --title "Tool X timeouts exceed 30s affecting queries" \
  --description "Tool X consistently times out after 30s, affecting 25% of queries during peak hours. Connection pool appears exhausted." \
  --severity HIGH \
  --evidence '{"trace_id": "tr-001", "rationale": "Tool X timeout after 32s during database query"}' \
  --evidence '{"trace_id": "tr-003", "rationale": "Tool X timeout after 35s during peak hours"}' \
  --evidence '{"trace_id": "tr-004", "rationale": "Tool X connection refused, service appears down"}'

# Read the issue to confirm it was created:
uv run --env-file <env_file_path> python -m mlflow insights get-issue \
  --issue-id <issue_id>
```

### 2.6 Generate Report

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

### 2.7 Analysis Completion

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