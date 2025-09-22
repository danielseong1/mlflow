# Agent Analysis & Hypothesis Generation Workflow

## Prerequisites
- Set environment variables in `.env` file
- Ensure `MLFLOW_EXPERIMENT_ID` is set

## Step 1: Create Analysis Run
```bash
uv run --env-file .env python -m mlflow insights create-analysis \
  --run-name "General Analysis Run" \
  --name "General Analysis" \
  --description "General analysis of traces and system behavior"
```
Save the run ID for subsequent steps.

## Step 2: Generate Baseline Census
```bash
uv run --env-file .env python -m mlflow insights create-baseline-census \
  --run-id <RUN_ID>
```

## Step 3: Sample Traces to Understand Agent
```bash
# Get 3-5 sample traces with key fields
uv run --env-file .env python -m mlflow traces search \
  --max-results 5 \
  --extract-fields 'info.trace_id,info.state,info.execution_duration_ms,info.tags.`mlflow.traceName`,info.trace_metadata,data.spans.*.name' \
  --output json
```

## Step 4: Review Baseline Census
```bash
uv run --env-file .env python -m mlflow insights get-baseline-census \
  --run-id <RUN_ID>
```

Analyze the census for:
- **Error patterns**: Top failing spans and error rates
- **Performance bottlenecks**: Slow tools and latency percentiles
- **Quality metrics**: Verbosity, uncertainty markers, rushed processing
- **Traffic patterns**: Load distribution over time

## Step 5: Generate Hypotheses

Based on census data, create hypotheses covering:

### Operational Issues
- Error cascades between related spans
- Input complexity correlations with failures
- Timeout and rate limiting patterns

### Quality Issues
- Rushed processing impact on output quality
- Uncertainty markers indicating real failures
- Peak load degradation patterns

### Testing Plan Structure
Each testing plan should be specific and actionable, including:
- Which traces to examine (sample IDs from census OR search criteria)
- Specific fields to extract and analyze
- Patterns or metrics to calculate
- Comparison approach (successful vs failed cases)

Example testing plans:
- "Read sample traces: tr-xxx, tr-yyy, tr-zzz from census. Check if both parsing spans have identical error status."
- "Use traces search to find traces with execution_time_ms > 12500. Analyze which spans contribute most to delay."
- "Read error traces: tr-aaa, tr-bbb. Count speakers and lines in input. Compare with successful traces."
- "Search traces from timestamp range 1758146400000-1758150000000 (peak hour). Calculate error rate and uncertainty markers."

### Template for Each Hypothesis
```bash
uv run --env-file .env python -m mlflow insights create-hypothesis \
  --run-id <RUN_ID> \
  --statement "<Hypothesis statement>" \
  --testing-plan "<Testing approach using sample trace IDs from census>"
```

## Step 6: View All Hypotheses
```bash
uv run --env-file .env python -m mlflow insights list-hypotheses \
  --run-id <RUN_ID>
```

## Key Patterns to Look For

1. **Error Cascades**: Same errors across multiple spans
2. **Complexity Correlations**: Long inputs → higher failure rates
3. **Time-based Patterns**: Performance/quality changes with load
4. **Dependency Failures**: Upstream errors causing downstream failures
5. **Format Sensitivities**: Specific input formats causing failures

## Example Hypothesis Generation

```bash
# Hypothesis: Parsing failures cascade
uv run --env-file .env python -m mlflow insights create-hypothesis \
  --run-id <RUN_ID> \
  --statement "When parse_1 fails, parse_2 always fails with identical errors" \
  --testing-plan "Read traces: tr-xxx, tr-yyy. Check both spans have same error status and message."

# Hypothesis: Complex inputs cause failures
uv run --env-file .env python -m mlflow insights create-hypothesis \
  --run-id <RUN_ID> \
  --statement "Meetings with >10 speakers cause extraction failures" \
  --testing-plan "Read error traces: tr-xxx, tr-yyy. Count speakers in input. Compare with successful extractions."
```

## Notes
- Use sample trace IDs from census instead of SQL queries
- Focus on both operational (errors, performance) and quality (output issues) aspects
- Each hypothesis should have clear, testable criteria
- Testing plans should be actionable with available CLI tools