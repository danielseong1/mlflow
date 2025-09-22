# MLflow Agent Analysis Setup

Quick setup to create analysis context for ongoing discussions about your agent.

# Step 0: Understanding the CLI (CRITICAL)

Before beginning any investigation, confirm CLI syntax:

```bash
# Trace CLI help (searching/filtering)
uv run --env-file <env_file_path> python -m mlflow traces --help
# Search traces (examples)
uv run --env-file <env_file_path> python -m mlflow traces search
uv run --env-file <env_file_path> python -m mlflow traces search --extract-fields "info.trace_id,info.state,info.execution_duration"

# Get specific trace
uv run --env-file <env_file_path> python -m mlflow traces get --trace-id <trace_id>

# Linking traces to runs
uv run --env-file <env_file_path> python -m mlflow runs link-traces --help

# Insights CLI (analyses, hypotheses, issues)
# Create analysis run
uv run --env-file <env_file_path> python -m mlflow insights create-analysis --run-name "Analysis Name" --name "Analysis" --description "Description of analysis"

# Create baseline census
uv run --env-file <env_file_path> python -m mlflow insights create-baseline-census --run-id <run_id>

# Get baseline census
uv run --env-file <env_file_path> python -m mlflow insights get-baseline-census --run-id <run_id>

# Create hypothesis
uv run --env-file .env python -m mlflow insights create-hypothesis \
  --run-id abc123 \
  --statement "High-latency traces are primarily caused by database timeout issues" \
  --description "Created because baseline census shows 23.4% of traces exceed 5000ms execution time, with 67% of these traces containing database-related spans that timeout. Census data indicates P95 latency is 8.2s vs expected 2s, suggesting systematic database performance issues during peak hours." \
  --testing-plan "Execute [query_database_timeouts] to identify traces with DB timeouts >30s. Use [query_peak_hour_latency] to analyze timestamp patterns. Compare error rates during peak vs off-peak hours using the retrieved trace samples." \
  --sql-query '{"id": "query_database_timeouts", "query": "SELECT trace_id, execution_duration_ms FROM traces WHERE spans LIKE '\''%database%'\'' AND execution_duration_ms > 30000 ORDER BY execution_duration_ms DESC LIMIT 50"}' \
  --sql-query '{"id": "query_peak_hour_latency", "query": "SELECT trace_id, request_time, execution_duration_ms FROM traces WHERE HOUR(request_time) BETWEEN 9 AND 17 AND execution_duration_ms > 5000 LIMIT 100"}' \

```

This ensures you know:

- Exact parameter names and formats
- Available filtering options for traces
- Proper JSON structure for --evidence flags
- How to link traces to analysis runs
- How to chain commands together

## Step 1: Setup and Configuration

### 1.1 Collect Experiment Information

**FIRST**: Check if `.env` file exists in current dir

**If .env file exists**:

- Skip to next step. Use `--env-file .env` for all future CLI commands

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

Once you completed the steps, let the user know you are ready to work with traces in Mlflow experiments!

```

```
