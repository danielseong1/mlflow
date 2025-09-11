# MLflow Insights: Product Requirements Document

## Executive Summary

MLflow Insights is a structured investigation framework built on top of MLflow's tracking capabilities. It provides a systematic way to conduct, document, and track investigative analyses of ML system behaviors, particularly focused on trace analysis for debugging and optimization.

## Problem Statement

When investigating issues in ML systems, particularly those involving distributed traces, teams need:
- A structured way to document hypotheses and findings
- Ability to link evidence (traces) to specific investigations
- Hierarchical organization of analyses within experiments
- Fast access to investigation metadata without scanning all runs
- Integration with existing MLflow trace infrastructure

## Solution Overview

MLflow Insights introduces three core concepts with distinct scoping:

**Experiment-Level (Global Singleton)**:
- **Issues**: Validated problems discovered across all analyses in the experiment
- Stored in the parent "Insights" run (singleton per experiment)
- Provides unified view of all discovered problems

**Run-Level (Analysis-Specific)**:
- **Hypotheses**: Testable theories being investigated in a specific analysis
- **Analysis Metadata**: Description and context for each investigation
- Stored in individual nested analysis runs

```
Experiment
└── Insights (Parent Run - Singleton)
    ├── issue_001.yaml  # EXPERIMENT-LEVEL: Issues visible across all analyses
    ├── issue_002.yaml
    ├── issue_003.yaml
    ├── Analysis Run 1  # RUN-LEVEL: Specific investigation
    │   ├── analysis.yaml
    │   ├── hypothesis_001.yaml
    │   └── hypothesis_002.yaml
    └── Analysis Run 2  # RUN-LEVEL: Another investigation
        ├── analysis.yaml
        └── hypothesis_003.yaml
```

## Data Model

### 1. Analysis
**Purpose**: High-level investigation container that defines what is being analyzed.

**Fields**:
- `name`: Human-readable name for the analysis
- `description`: Detailed description of investigation goals and guidance
- `status`: Current state (ACTIVE, COMPLETED, ARCHIVED)
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `metadata`: Extensible dictionary for custom fields

**Storage**: `insights/analysis.yaml` in the run artifacts

### 2. Hypothesis
**Purpose**: A testable statement or theory being investigated.

**Fields**:
- `hypothesis_id`: UUID unique within the run
- `statement`: The hypothesis being tested
- `testing_plan`: **CRITICAL** - Detailed plan for how to test this hypothesis:
  - How to find supporting traces (filter criteria, patterns to look for)
  - How to find refuting traces (counter-examples, control cases)
  - What evidence threshold validates/invalidates the hypothesis
  - Example: "To validate this hypothesis, I will search for traces with execution_time > 30s and examine their spans for database-related operations, specifically looking for keywords like 'lock wait', 'deadlock', or 'timeout' in span attributes. Supporting evidence would include spans showing extended wait times (>5s) on database locks or explicit lock timeout errors. To find refuting evidence, I will search for slow traces (>30s) that have no database operations at all, or fast traces (<5s) that DO have database operations with locks, which would suggest the locks aren't the root cause. I will also look for patterns in time-of-day correlation - if slowness occurs during peak hours when DB load is highest, this supports the hypothesis. The hypothesis is validated if >80% of slow traces contain database lock indicators and <20% of fast traces with DB operations show lock contention. It's invalidated if I find significant numbers of slow traces without any database involvement or if lock patterns don't correlate with performance degradation."
- `status`: Current state (TESTING, VALIDATED, REJECTED)
- `evidence`: List of evidence entries, each containing:
  - `trace_id`: The specific trace ID
  - `rationale`: Explanation of why this trace supports/refutes the hypothesis
  - `supports`: Boolean indicating if evidence supports (true) or refutes (false)
- `metrics`: Dictionary of relevant metrics
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `metadata`: Extensible dictionary for custom fields

**Storage**: `insights/hypothesis_{id}.yaml` in the run artifacts

### 3. Issue
**Purpose**: A validated problem discovered through investigation.

**Fields**:
- `issue_id`: UUID unique within the container
- `source_run_id`: The analysis run that created this issue
- `hypothesis_id`: Optional source hypothesis if validated from one
- `title`: Brief issue title
- `description`: Detailed description of the problem
- `severity`: Issue severity (CRITICAL, HIGH, MEDIUM, LOW)
- `status`: Current state (OPEN, IN_PROGRESS, RESOLVED, REJECTED)
- `evidence`: List of evidence entries, each containing:
  - `trace_id`: The specific trace ID
  - `rationale`: Explanation of why this trace demonstrates the issue
- `assessments`: List of assessment names/IDs related to the issue
- `resolution`: Resolution description when resolved
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `metadata`: Extensible dictionary for custom fields

**Storage**: `insights/issue_{id}.yaml` in the PARENT (container) run artifacts

## Architecture

### Run Hierarchy

```
insights-parent (Singleton per experiment)
├── Tags:
│   ├── mlflow.insights.type: "parent"
│   ├── mlflow.insights.parent: "true"
│   └── mlflow.runName: "Insights"
└── Nested Runs:
    ├── analysis-run-1
    │   └── Tags:
    │       ├── mlflow.insights.type: "analysis"
    │       └── mlflow.insights.name: "{analysis_name}"
    └── analysis-run-2
        └── Tags: ...
```

### Key Design Decisions

1. **Nested Runs**: All analysis runs are nested under a single parent "Insights" run per experiment
   - Provides natural hierarchical organization
   - Enables fast listing without scanning all experiment runs
   - Maintains clear separation from regular ML training runs

2. **Issue Storage in Parent**: Issues are stored in the parent container run, not analysis runs
   - Provides experiment-wide view of all discovered issues
   - Allows issues to be shared across multiple analyses
   - Centralizes validated problems for easier tracking

3. **YAML Storage**: All entities stored as YAML files in artifacts
   - Human-readable format for investigations
   - Version-controlled through MLflow artifacts
   - Supports complex nested structures

4. **Trace Linking**: Traces are linked to runs via MLflow's native `link_traces_to_run()` API
   - Maintains bidirectional relationship
   - Enables trace-based filtering and analysis

5. **Flat Artifact Structure**: All files stored directly in `insights/` directory
   - Simplifies artifact management
   - Clear naming convention: `{entity_type}_{id}.yaml`

## Python SDK

### Core Classes

```python
from mlflow.insights import InsightsClient

# Initialize client
client = InsightsClient()
```

### Creation Methods

```python
# Create analysis (run-level)
run_id = client.create_analysis(
    experiment_id="123",
    run_name="Error Investigation",  # Short 3-4 word name
    name="Production Error Analysis",
    description="Investigating 500 errors in production"
)

# Create hypothesis (run-level)
hypothesis_id = client.create_hypothesis(
    insights_run_id=run_id,
    statement="Database connection pooling causes latency",
    testing_plan="To test whether database connection pooling is causing latency spikes, I will first identify all traces with execution_time > 30s and examine their database-related spans for connection acquisition delays, looking for patterns like 'waiting for connection', 'pool exhausted', or connection timeouts in span attributes. Supporting evidence would include spans showing >500ms delays in obtaining connections from the pool, or explicit pool exhaustion errors. For refutation, I'll search for slow traces (>30s) that have no database operations whatsoever, and fast traces (<5s) that do use the database connection pool successfully, which would indicate the pool isn't the bottleneck. Additionally, I'll correlate trace timing with system metrics - if slowness aligns with periods of high concurrent requests (>100 concurrent), this supports pool exhaustion. The hypothesis is validated if >70% of slow traces show connection pool delays and these delays account for >50% of the total execution time. It's invalidated if slow traces occur without database involvement or if connection acquisition time is consistently <100ms even in slow traces."
)

# Create issue (experiment-level - stored in parent singleton)
issue_id = client.create_issue(
    insights_run_id=run_id,  # Source run, but stored in parent
    title="Database Connection Pool Exhaustion",
    description="Pool size too small for peak traffic",
    severity="HIGH",
    hypothesis_id=hypothesis_id
)
```

### Update Methods

```python
# Update analysis metadata
client.update_analysis(
    run_id=run_id,
    name="Updated Analysis Name",
    description="Updated description with new findings"
)

# Update hypothesis
client.update_hypothesis(
    insights_run_id=run_id,
    hypothesis_id=hypothesis_id,
    status="VALIDATED",
    add_traces=["tr-004", "tr-005"],
    add_evidence=["Found 50ms delay in connection acquisition"]
)

# Update issue (in parent singleton)
client.update_issue(
    insights_run_id=run_id,
    issue_id=issue_id,
    severity="CRITICAL",
    add_traces=["tr-006"],
    resolution="Increased pool size from 10 to 50"
)
```

### Read Methods

```python
# List all analyses in experiment
analyses = client.list_analyses(experiment_id="123")

# List hypotheses in a specific analysis run
hypotheses = client.list_hypotheses(insights_run_id=run_id)

# List issues (experiment-level from parent) - sorted by number of traces
issues = client.list_issues(experiment_id="123")  # Or from env: MLFLOW_EXPERIMENT_ID
# Note: Issues are automatically sorted by len(trace_ids) descending

# Get specific entities
analysis = client.get_analysis(insights_run_id=run_id)
hypothesis = client.get_hypothesis(insights_run_id=run_id, hypothesis_id=hypothesis_id)
issue = client.get_issue(issue_id=issue_id)  # No run_id needed - issues are experiment-level
```

### Preview Methods (Returns Traces)

```python
# Preview hypotheses - returns list of traces associated with all hypotheses
hypothesis_traces = client.preview_hypotheses(
    insights_run_id=run_id,
    max_traces=100  # Optional limit
)

# Preview issues - returns list of traces associated with all issues
issue_traces = client.preview_issues(
    experiment_id="123",  # Or from env: MLFLOW_EXPERIMENT_ID
    max_traces=100  # Optional limit
)

# Preview returns actual trace objects for further analysis
for trace in hypothesis_traces:
    print(f"Trace {trace.info.request_id}: {trace.info.status}")
```

## CLI Commands

The CLI commands are a direct reflection of the Python SDK methods:

### Creation Commands

- `mlflow insights create-analysis` - Creates new nested analysis run (requires --run-name)
- `mlflow insights create-hypothesis` - Adds hypothesis to analysis (use multiple --evidence flags with JSON)
- `mlflow insights create-issue` - Documents validated issue in parent container (use multiple --evidence flags with JSON)

### Update Commands

- `mlflow insights update-analysis` - Modifies analysis metadata
- `mlflow insights update-hypothesis` - Updates hypothesis (status, traces, evidence) - use multiple --evidence flags with JSON
- `mlflow insights update-issue` - Updates issue details or resolution in parent container - use multiple --evidence flags with JSON

### Read Commands

- `mlflow insights list-analyses` - Lists all analyses in experiment
- `mlflow insights list-hypotheses` - Lists hypotheses in a specific analysis run
- `mlflow insights list-issues` - Lists issues for an experiment (sorted by trace count)
- `mlflow insights get-analysis` - Gets detailed analysis info
- `mlflow insights get-hypothesis` - Gets specific hypothesis details
- `mlflow insights get-issue` - Gets specific issue details (experiment-level)

### Preview Commands (Returns Traces)

- `mlflow insights preview-hypotheses` - Returns traces associated with hypotheses in a run
- `mlflow insights preview-issues` - Returns traces associated with issues in an experiment

## Usage Example

```bash
# 1. Create an analysis (run-name is now REQUIRED)
mlflow insights create-analysis \
  --experiment-id 123 \
  --run-name "Latency Investigation" \
  --name "Production Latency Investigation - Agent X" \
  --description "Investigating high p99 latency in production traces for Agent X"

# 2. Create a hypothesis (use multiple --evidence flags with JSON)
mlflow insights create-hypothesis \
  --run-id abc123 \
  --statement "Database connection pooling is causing latency spikes" \
  --evidence '{"trace_id": "tr-001", "rationale": "Shows 45s delay acquiring connection from exhausted pool", "supports": true}' \
  --evidence '{"trace_id": "tr-002", "rationale": "Connection timeout after 30s wait for available connection", "supports": true}' \
  --evidence '{"trace_id": "tr-003", "rationale": "Fast response despite heavy DB usage - pool not exhausted", "supports": false}'

# 3. Update hypothesis with evidence and more traces
mlflow insights update-hypothesis \
  --run-id abc123 \
  --hypothesis-id xyz789 \
  --status VALIDATED \
  --evidence '{"trace_id": "tr-004", "rationale": "Pool metrics show 0 available connections for 50s period", "supports": true}' \
  --evidence '{"trace_id": "tr-005", "rationale": "Deadlock in connection pool management thread", "supports": true}'

# 4. Create an issue from validated hypothesis (stored in parent container)
mlflow insights create-issue \
  --run-id abc123 \
  --title "Database Connection Pool Exhaustion" \
  --description "Connection pool size too small for peak traffic" \
  --severity HIGH \
  --hypothesis-id xyz789 \
  --evidence '{"trace_id": "tr-001", "rationale": "Shows 45s delay acquiring connection from exhausted pool"}' \
  --evidence '{"trace_id": "tr-002", "rationale": "Connection timeout after 30s wait for available connection"}' \
  --evidence '{"trace_id": "tr-003", "rationale": "Pool metrics show 0 available connections during incident"}' \
  --evidence '{"trace_id": "tr-004", "rationale": "Deadlock in connection pool management causing total freeze"}'

# 5. List issues for the experiment (sorted by trace count)
mlflow insights list-issues \
  --experiment-id 123

# 6. Preview traces for all issues in the experiment
mlflow insights preview-issues \
  --experiment-id 123 \
  --max-traces 100
```

## Workflow

### 0. Understanding the CLI (CRITICAL STEP)

Before beginning any investigation, the agent MUST understand the exact CLI syntax:

```bash
# Understand trace CLI capabilities for searching and filtering
mlflow traces --help

# Understand insights CLI commands and their exact parameters  
mlflow insights --help
```

This ensures the agent knows:
- Exact parameter names and formats
- Available filtering options for traces
- Proper JSON structure for --evidence flags
- How to chain commands together

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
  
**Example of Showing Work**:
```bash
# Currently testing hypothesis H1
mlflow insights get-hypothesis --run-id ${run_id} --hypothesis-id ${h1_id}
# Output: "API timeouts correlate with database locks"

# Filtering traces to test H1
mlflow traces search --filter "status = 'ERROR' AND execution_time_ms > 30000" --max-results 20

# Found 15 traces matching pattern, updating hypothesis
mlflow insights update-hypothesis --run-id ${run_id} --hypothesis-id ${h1_id} \
  --add-evidence "tr-123: 32s timeout with DB lock visible in span" \
  --status TESTING

# Preview current state
mlflow insights list-hypotheses --run-id ${run_id}
# Shows: H1 (TESTING, 15 traces), H2 (VALIDATED, 23 traces), H3 (REJECTED, 2 traces)
```

### 1. Initial Request and Context Gathering

**User Request**: User asks for insights on an experiment with optional focus areas:

- Time window filtering (e.g., last 24 hours)
- Specific run or set of runs
- Particular error patterns or performance issues
- General quality assessment

**Agent Understanding**:

- Analyzes sample traces to understand the agent's purpose
- Identifies available tools and data sources
- Confirms understanding with user

### 2. Analysis Creation

```bash
# Create analysis run with descriptive name based on focus
mlflow insights create-analysis \
  --experiment-id 123 \
  --run-name "Error Investigation" \
  --name "Production Error Spike Analysis" \
  --description "Agent: ${agent_desc}. Focus: ${user_focus}. Initial patterns: ${patterns}"

# Save the returned run_id for subsequent commands
```

The analysis run serves as persistent memory for the entire investigation.

### 3. Hypothesis Generation and Testing

**Continuous Process** (using CLI/MCP as memory):

```bash
# Show user what hypothesis is being created WITH testing plan
echo "Creating hypothesis: API timeouts correlate with database locks"
echo "Testing Plan: To investigate whether API timeouts are caused by database locks, I will search for traces with execution_time > 30s and analyze their database spans for lock-related indicators such as 'lock wait timeout', 'deadlock detected', or extended wait times in acquiring row/table locks. Supporting evidence includes spans showing database operations waiting >5s for locks, explicit lock timeout errors, or multiple concurrent transactions competing for the same resources. For refutation, I'll identify slow API calls (>30s) that have no database interactions at all, or fast API calls (<5s) that successfully complete database operations with locks, suggesting locks aren't the root cause. I'll also examine temporal patterns - if timeouts cluster during high-traffic periods when database contention is expected, this strengthens the hypothesis. The hypothesis is validated if >70% of timeout traces show database lock indicators and these lock waits account for >60% of total request time. It's invalidated if significant timeout traces lack database operations entirely or if lock acquisition times remain under 500ms even in slow traces."
mlflow insights create-hypothesis \
  --run-id ${run_id} \
  --statement "API timeouts correlate with database locks" \
  --testing-plan "To investigate whether API timeouts are caused by database locks, I will search for traces with execution_time > 30s and analyze their database spans for lock-related indicators such as 'lock wait timeout', 'deadlock detected', or extended wait times in acquiring row/table locks. Supporting evidence includes spans showing database operations waiting >5s for locks, explicit lock timeout errors, or multiple concurrent transactions competing for the same resources. For refutation, I'll identify slow API calls (>30s) that have no database interactions at all, or fast API calls (<5s) that successfully complete database operations with locks, suggesting locks aren't the root cause. I'll also examine temporal patterns - if timeouts cluster during high-traffic periods when database contention is expected, this strengthens the hypothesis. The hypothesis is validated if >70% of timeout traces show database lock indicators and these lock waits account for >60% of total request time. It's invalidated if significant timeout traces lack database operations entirely or if lock acquisition times remain under 500ms even in slow traces." \
  --evidence '{"trace_id": "tr-001", "rationale": "32s timeout with explicit lock wait on users table", "supports": true}' \
  --evidence '{"trace_id": "tr-002", "rationale": "Deadlock detected between two update transactions", "supports": true}' \
  --evidence '{"trace_id": "tr-003", "rationale": "35s timeout but no database operations found", "supports": false}'

# Execute the testing plan - show filtering strategy to user
echo "Executing testing plan for H1:"
echo "Step 1: Finding slow traces with database operations"
mlflow traces search \
  --filter "execution_time_ms > 30000 AND spans.name CONTAINS 'database'" \
  --max-results 50

echo "Step 2: Finding control group - fast traces with database operations"  
mlflow traces search \
  --filter "execution_time_ms < 5000 AND spans.name CONTAINS 'database'" \
  --max-results 20

# Show evidence collection process
echo "Found supporting evidence in tr-123"
mlflow traces get --trace-id tr-123 \
  --extract-fields "data.spans[].name,data.spans[].attributes.db.statement"

# Update hypothesis with evidence
mlflow insights update-hypothesis \
  --run-id ${run_id} \
  --hypothesis-id ${hypothesis_id} \
  --evidence '{"trace_id": "tr-123", "rationale": "Shows 30s timeout waiting for DB lock on users table", "supports": true}' \
  --evidence '{"trace_id": "tr-456", "rationale": "Fast response when no DB lock contention", "supports": false}'

# Show current hypothesis state to user
mlflow insights get-hypothesis --run-id ${run_id} --hypothesis-id ${hypothesis_id}
```

**Key Points**:

- **Show filtering logic**: Display exact filter criteria being used
- **Show evidence as found**: Display trace excerpts that support/refute
- **Regular status updates**: Show hypothesis list after each major update
- Can add new hypotheses at any time during investigation
- Continuously collect supporting and refuting evidence
- Store trace_id + rationale for EVERY piece of evidence
- Use `preview-hypotheses` to retrieve traces when needed

### 4. Issue Creation from Validated Hypotheses

When sufficient evidence validates a hypothesis:

```bash
# Create issue with all supporting evidence
mlflow insights create-issue \
  --run-id ${run_id} \
  --title "Database Lock Contention Causing Timeouts" \
  --description "User table locks causing 30s+ delays during peak traffic" \
  --severity HIGH \
  --hypothesis-id ${hypothesis_id} \
  --evidence '{"trace_id": "tr-123", "rationale": "User query blocked for 32s on exclusive lock"}' \
  --evidence '{"trace_id": "tr-789", "rationale": "Batch update holding lock for 45s"}' \
  --evidence '{"trace_id": "tr-234", "rationale": "Deadlock detected between two transactions"}'
```

### 5. Issue Presentation to User

**List Issues** (sorted by trace count):

```bash
# List all issues for the experiment
mlflow insights list-issues --experiment-id 123
```

**Present Each Issue** with trace examples:

```bash
# Get specific trace fields for clarity
mlflow traces get --trace-id tr-123 \
  --extract-fields "info.status,data.spans[0].name,data.spans[0].attributes.error"
```

Display as:

- Issue title and severity
- 1-2 example traces showing the problem
- Rationale explaining why these traces demonstrate the issue
- Total trace count affected

### 6. User Review and Decision

User reviews each issue and decides:

- **ACCEPT**: Issue is valid and should be tracked
- **REJECT**: Issue is not relevant or incorrect

```bash
# User accepts/rejects issue
mlflow insights update-issue \
  --run-id ${run_id} \
  --issue-id ${issue_id} \
  --status RESOLVED  # or REJECTED
```

### 7. Assessment Logging (Optional)

If user chooses to log assessments for accepted issues:

```bash
# For each accepted issue, log assessments on ALL traces
for trace_id in issue.trace_ids:
    mlflow traces log-feedback \
      --trace-id ${trace_id} \
      --name "database_lock_timeout" \
      --value "true" \
      --source-type LLM_JUDGE \
      --source-id insights-analysis \
      --rationale "${issue.evidence[trace_id].rationale}"
```

This creates permanent assessments on traces for:
- Future analysis and filtering
- Training data for automated detection
- Metrics and monitoring

### 8. Analysis Completion

Once all hypotheses have been tested and issues reviewed:

```bash
# Mark the analysis as completed
mlflow insights update-analysis \
  --run-id ${run_id} \
  --status COMPLETED
```

This indicates:
- The investigation is complete
- All hypotheses have been tested (validated/rejected)
- Issues have been created and reviewed
- No further active investigation is planned

**Note**: An analysis can be reopened later by updating status back to ACTIVE if new evidence emerges.

### Example End-to-End Flow

1. **User**: "Analyze experiment 123 for errors in the last 24 hours"
2. **System**: Creates analysis "Error Investigation" (status: ACTIVE)
3. **System**: Generates hypotheses:
   - H1: "Database timeouts during peak load"
   - H2: "Missing error handling for null inputs"
   - H3: "Rate limiting from external API"
4. **System**: Tests each hypothesis with trace evidence
5. **System**: Validates H1 and H2, rejects H3
6. **System**: Creates issues for H1 and H2 with evidence
7. **User**: Reviews and accepts both issues
8. **System**: Logs assessments on 47 traces for H1, 23 traces for H2
9. **System**: Marks analysis as COMPLETED
10. **Result**: Experiment now has tagged traces and a completed analysis for future reference

## UI

### Overview

The MLflow Insights UI provides a visual interface for exploring and managing AI-driven analyses within the MLflow experiment tracking interface.

### Navigation Structure

**Location**: Insights tab → AI Analysis subpage

The AI Analysis page contains two sub-sections:
- **Issues**: Experiment-level validated problems
- **Runs**: Individual analysis investigations

### Issues Page

**Purpose**: Display and manage all discovered issues across the experiment.

**Features**:
- List view showing all issues with:
  - Issue title and severity badge (CRITICAL/HIGH/MEDIUM/LOW)
  - Status indicator (OPEN/IN_PROGRESS/RESOLVED/REJECTED)
  - Number of associated traces
  - Creation timestamp
  - Source analysis run link
- Sorting options:
  - By trace count (default - most traces first)
  - By severity
  - By creation date
  - By status
- Filtering options:
  - By severity level
  - By status
  - By date range

**Issue Detail View**:
When clicking on an issue, users see:
- Full issue description
- Severity and status controls (editable)
- Evidence list with:
  - Each trace ID as a clickable link
  - Rationale for why the trace demonstrates the issue
  - Embedded trace explorer UI showing the actual trace
- Source hypothesis (if created from one)
- Resolution notes field (for resolved issues)
- Action buttons:
  - Update Status
  - Add Evidence
  - Export to JIRA/GitHub Issues
  - Log Assessments (batch operation on all traces)

### Runs Page

**Purpose**: Monitor and explore individual analysis investigations.

**Features**:
- List view showing all analysis runs with:
  - Run name and analysis name
  - Status badge (ACTIVE/COMPLETED/ARCHIVED)
  - Number of hypotheses
  - Number of validated hypotheses
  - Creation timestamp
  - Last updated timestamp
- Real-time status indicators:
  - 🟢 Running (actively being updated)
  - ⏸️ Paused
  - ✅ Completed
  - 📦 Archived

**Run Detail View**:
When clicking on a run, users see:
- Analysis metadata:
  - Name and description
  - Status controls
  - Creation/update timestamps
- **Live Hypothesis Dashboard** (auto-refreshes every second):
  - List of all hypotheses with:
    - Statement text
    - Status badge (TESTING/VALIDATED/REJECTED)
    - Testing plan (expandable)
    - Evidence count with support/refute breakdown
    - Last update timestamp with "live" indicator if being updated
  - For each hypothesis, expandable section showing:
    - Full testing plan
    - Evidence entries with:
      - Trace ID (clickable)
      - Rationale text
      - Support/Refute indicator
      - Timestamp
    - Embedded trace explorer for selected traces
    - Metrics and custom metadata
- Action buttons:
  - Create New Hypothesis
  - Create Issue from Hypothesis
  - Export Analysis Report
  - Archive Run

### Trace Integration

Both Issues and Runs pages integrate the existing MLflow trace explorer UI:
- **Inline Trace Viewer**: Traces can be viewed directly within the issue/hypothesis context
- **Trace Comparison**: Select multiple traces to compare side-by-side
- **Span Analysis**: Drill down into specific spans mentioned in evidence
- **Filter by Evidence**: Quickly filter to show only traces that support or refute

### Real-Time Updates

The UI implements real-time updates for active investigations:
- **WebSocket/Polling**: Auto-refresh every 1-2 seconds for runs marked as "ACTIVE"
- **Live Indicators**: Visual cues (pulsing dots, timestamps) show when data is being updated
- **Notification Toasts**: Brief notifications when new hypotheses or evidence are added
- **Progress Tracking**: Show number of traces analyzed, hypotheses tested, etc.

### User Interactions

**Quick Actions from UI**:
- **Accept/Reject Issues**: Single-click status updates
- **Validate/Reject Hypotheses**: Update hypothesis status with reason
- **Link Additional Traces**: Drag-and-drop or search to add trace evidence
- **Bulk Operations**: Select multiple issues/hypotheses for batch updates
- **Export Options**: Download analyses as PDF/Markdown reports

### Design Considerations

1. **Performance**: 
   - Lazy load trace data only when expanded
   - Pagination for large numbers of issues/hypotheses
   - Cache hypothesis data with smart invalidation

2. **Accessibility**:
   - Keyboard navigation support
   - Screen reader friendly status updates
   - High contrast mode for severity indicators

3. **Mobile Responsiveness**:
   - Responsive grid layouts
   - Touch-friendly expand/collapse controls
   - Swipe gestures for navigation

## REST API

### Overview

The MLflow Insights Agentic API provides programmatic access to analysis data for the UI and external integrations. These endpoints mirror the Python SDK read operations.

### Base Path

All endpoints are under: `/api/3.0/mlflow/traces/insights/agentic/`

### Endpoint Organization

```
/api/3.0/mlflow/traces/insights/agentic/
├── analyses/
│   ├── list         # List all analyses in experiment
│   └── get          # Get specific analysis details
├── hypotheses/
│   ├── list         # List hypotheses in a run
│   ├── get          # Get specific hypothesis
│   └── preview      # Get traces for hypotheses
└── issues/
    ├── list         # List issues in experiment
    ├── get          # Get specific issue
    └── preview      # Get traces for issues
```

### Common Request Format

All endpoints accept POST requests with standard parameters:

```json
{
    "experiment_id": "123",           // Required for experiment-level operations
    "insights_run_id": "abc-123",     // Required for run-level operations
    "hypothesis_id": "xyz-789",       // Required for hypothesis operations
    "issue_id": "def-456",           // Required for issue operations
    "max_traces": 100                 // Optional limit for preview endpoints
}
```

### Key Endpoints

#### List Analyses
**Endpoint**: `POST /api/3.0/mlflow/traces/insights/agentic/analyses/list`

**Response**:
```json
{
    "analyses": [
        {
            "run_id": "abc-123",
            "name": "Production Error Analysis",
            "status": "ACTIVE",
            "hypothesis_count": 5,
            "created_at": 1704110400000,
            "updated_at": 1704114000000
        }
    ]
}
```

#### List Hypotheses
**Endpoint**: `POST /api/3.0/mlflow/traces/insights/agentic/hypotheses/list`

**Response**:
```json
{
    "hypotheses": [
        {
            "hypothesis_id": "xyz-789",
            "statement": "Database locks cause timeouts",
            "status": "VALIDATED",
            "trace_count": 15,
            "evidence_count": 8,
            "supports_count": 6,
            "refutes_count": 2
        }
    ]
}
```

#### List Issues
**Endpoint**: `POST /api/3.0/mlflow/traces/insights/agentic/issues/list`

**Response** (sorted by trace_count descending):
```json
{
    "issues": [
        {
            "issue_id": "def-456",
            "title": "Database Connection Pool Exhaustion",
            "severity": "HIGH",
            "status": "OPEN",
            "trace_count": 47,
            "source_run_id": "abc-123",
            "created_at": 1704110400000
        }
    ]
}
```

#### Preview Traces
**Endpoint**: `POST /api/3.0/mlflow/traces/insights/agentic/issues/preview`

**Response**:
```json
{
    "traces": [
        {
            "trace_id": "tr-001",
            "request_id": "req-abc-123",
            "status": "ERROR",
            "execution_time_ms": 32000,
            "timestamp": 1704110400000,
            "evidence_rationale": "Shows 32s timeout waiting for DB lock"
        }
    ],
    "total_count": 47,
    "returned_count": 10
}
```

### Error Handling

Standard MLflow error responses:
```json
{
    "error": {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Analysis run 'abc-123' not found"
    }
}
```

### Implementation Notes

- All endpoints return YAML data parsed into JSON format
- Real-time updates achieved through polling these endpoints
- Trace data is fetched separately using existing MLflow trace APIs
- Issues are always sorted by trace_count (most traces first)
- Preview endpoints return actual trace objects with metadata
