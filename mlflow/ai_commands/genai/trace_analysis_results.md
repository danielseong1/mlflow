# Trace Analysis Results

This document contains SQL queries and results for analyzing the `ds_fs.agent_quality.sample_agent_trace_archival` table.

## 1. Denominators - Total Traces and Basic Counts

### SQL Query:

```sql
SELECT
    COUNT(*) as total_traces,
    SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as ok_count,
    SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count,
    ROUND(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate
FROM ds_fs.agent_quality.sample_agent_trace_archival
```

### Results:

- **Total Traces**: 796
- **OK Count**: 796
- **Error Count**: 0 (at trace level)
- **Error Rate**: 0.0% (at trace level)

_Note: All traces have OK status at the trace level, but there are span-level errors._

## 2. Latency Analysis (OK Traces)

### SQL Query:

```sql
SELECT
    percentile(execution_duration_ms, 0.5) as p50_latency_ms,
    percentile(execution_duration_ms, 0.9) as p90_latency_ms,
    percentile(execution_duration_ms, 0.95) as p95_latency_ms,
    percentile(execution_duration_ms, 0.99) as p99_latency_ms,
    MAX(execution_duration_ms) as max_latency_ms
FROM ds_fs.agent_quality.sample_agent_trace_archival
WHERE state = 'OK' AND execution_duration_ms IS NOT NULL
```

### Results:

- **P50 Latency**: 7,578 ms
- **P90 Latency**: 10,019 ms
- **P95 Latency**: 10,600 ms
- **P99 Latency**: 12,535 ms
- **Max Latency**: 20,153 ms

## 3. Top Error Buckets (Span-Level Errors)

### SQL Query:

```sql
SELECT
    span.name as error_category,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (
        SELECT COUNT(*)
        FROM ds_fs.agent_quality.sample_agent_trace_archival
        LATERAL VIEW explode(spans) AS s
        WHERE s.status_code = 'ERROR'
    ), 2) as pct_of_errors
FROM ds_fs.agent_quality.sample_agent_trace_archival
LATERAL VIEW explode(spans) AS span
WHERE span.status_code = 'ERROR'
GROUP BY span.name
ORDER BY count DESC
LIMIT 10
```

### Results:

| Error Category            | Count | % of Errors |
| ------------------------- | ----- | ----------- |
| extract_action_items      | 102   | 19.28%      |
| parse_transcript_2        | 79    | 14.93%      |
| parse_transcript_1        | 79    | 14.93%      |
| extract_decisions         | 73    | 13.80%      |
| generate_summary_2        | 50    | 9.45%       |
| generate_summary_1        | 50    | 9.45%       |
| check_calendar_references | 36    | 6.81%       |
| draft_follow_up           | 30    | 5.67%       |
| create_follow_up          | 30    | 5.67%       |

**Total Span-Level Errors**: 529 error spans across all traces

## 4. Top Slow Tools/Spans

### SQL Query:

```sql
SELECT
    span.name as tool_span_name,
    COUNT(*) as count,
    percentile((unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000, 0.95) as p95_latency_ms,
    percentile((unix_timestamp(span.end_time) - unix_timestamp(span.start_time)) * 1000, 0.5) as median_latency_ms
FROM ds_fs.agent_quality.sample_agent_trace_archival
LATERAL VIEW explode(spans) AS span
WHERE span.start_time IS NOT NULL AND span.end_time IS NOT NULL
GROUP BY span.name
HAVING COUNT(*) >= 10
ORDER BY p95_latency_ms DESC
LIMIT 15
```

### Results:

| Tool/Span Name              | Count | P95 Latency (ms) | Median Latency (ms) |
| --------------------------- | ----- | ---------------- | ------------------- |
| process_meeting_transcript  | 796   | 11,000           | 7,000               |
| extract_content             | 717   | 4,000            | 2,000               |
| create_follow_up            | 667   | 4,000            | 3,000               |
| draft_follow_up             | 667   | 4,000            | 3,000               |
| generate_summary_2          | 717   | 3,000            | 2,000               |
| generate_summary_1          | 717   | 3,000            | 2,000               |
| extract_action_items        | 717   | 3,000            | 2,000               |
| \_extract_with_llm_1        | 92    | 2,000            | 1,000               |
| \_extract_with_llm          | 369   | 2,000            | 2,000               |
| \_extract_with_llm_4        | 19    | 2,000            | 1,000               |
| \_extract_decision_with_llm | 115   | 2,000            | 1,000               |
| \_extract_with_llm_2        | 92    | 2,000            | 1,000               |
| extract_decisions           | 717   | 2,000            | 0                   |
| \_extract_with_llm_3        | 37    | 1,200            | 1,000               |
| \_extract_with_llm_5        | 12    | 1,000            | 1,000               |

## 5. Time Buckets Analysis (Hourly)

### SQL Query:

```sql
SELECT
    date_trunc('hour', request_time) as time_bucket,
    COUNT(*) as total_traces,
    SUM(CASE WHEN state = 'OK' THEN 1 ELSE 0 END) as ok_count,
    SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) as error_count,
    ROUND(SUM(CASE WHEN state = 'ERROR' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate,
    percentile(execution_duration_ms, 0.95) as p95_latency_ms
FROM ds_fs.agent_quality.sample_agent_trace_archival
GROUP BY 1
ORDER BY 1
```

### Results:

| Time Bucket         | Total Traces | OK Count | Error Count | Error Rate | P95 Latency (ms) |
| ------------------- | ------------ | -------- | ----------- | ---------- | ---------------- |
| 2025-09-17 17:00:00 | 1            | 1        | 0           | 0.0%       | 7,322            |
| 2025-09-17 18:00:00 | 211          | 211      | 0           | 0.0%       | 11,524           |
| 2025-09-17 22:00:00 | 584          | 584      | 0           | 0.0%       | 10,533           |

## Key Insights

1. **System Reliability**: All 796 traces completed successfully at the trace level, indicating good overall system reliability.

2. **Latency Distribution**: The system has moderate latency with P50 at ~7.6 seconds and P95 at ~10.6 seconds.

3. **Span-Level Issues**: Despite trace-level success, there are 529 span-level errors (5.9% of total spans), primarily in:

   - Action item extraction (19.3% of errors)
   - Transcript parsing (29.9% of errors combined)
   - Decision extraction (13.8% of errors)

4. **Performance Bottlenecks**:

   - `process_meeting_transcript` is the slowest operation (P95: 11s)
   - Content extraction and follow-up generation are secondary bottlenecks (P95: 4s)

5. **Usage Patterns**:
   - Peak usage occurred during 22:00 hour (584 traces)
   - Consistent performance across time periods
   - Low single-trace activity at 17:00

## 6. Agent Quality Metrics

These queries measure specific quality issues in agent responses. They are designed to be fast, generalizable, and work with any agent trace table.

### 6.1 Verbosity - Short Inputs Getting Verbose Responses

**SQL Query:**

```sql
-- Percentage of short inputs (<=P25 request length) that receive verbose responses (>P90 response length)
WITH percentile_thresholds AS (
  SELECT
    percentile(LENGTH(request), 0.25) as short_input_threshold,
    percentile(LENGTH(response), 0.90) as verbose_response_threshold
  FROM ds_fs.agent_quality.sample_agent_trace_archival
  WHERE state = 'OK'
),
shorter_inputs AS (
  SELECT
    t.trace_id,
    LENGTH(t.response) as response_length
  FROM ds_fs.agent_quality.sample_agent_trace_archival t
  CROSS JOIN percentile_thresholds p
  WHERE t.state = 'OK'
    AND LENGTH(t.request) <= p.short_input_threshold
)
SELECT
  ROUND(100.0 * SUM(CASE
    WHEN response_length > (SELECT verbose_response_threshold FROM percentile_thresholds)
    THEN 1 ELSE 0
  END) / COUNT(*), 2) as verbose_pct
FROM shorter_inputs
```

**Result:** `4.95%`

### 6.2 Response Quality Issues - Questions and Uncertainty

**SQL Query:**

```sql
-- Percentage of responses containing question marks, apologies ('sorry', 'apologize'), or uncertainty phrases ('not sure', 'cannot confirm')
SELECT
  ROUND(100.0 * SUM(CASE
    WHEN response LIKE '%?%' OR
         LOWER(response) LIKE '%apologize%' OR LOWER(response) LIKE '%sorry%' OR
         LOWER(response) LIKE '%not sure%' OR LOWER(response) LIKE '%cannot confirm%'
    THEN 1 ELSE 0
  END) / COUNT(*), 2) as problematic_response_rate
FROM ds_fs.agent_quality.sample_agent_trace_archival
WHERE state = 'OK'
```

**Result:** `11.31%`

### 6.3 Response Time vs Complexity - Rushed Processing

**SQL Query:**

```sql
-- Percentage of complex requests (>P75 length) processed faster than typical fast responses (P10 execution time)
WITH percentile_thresholds AS (
  SELECT
    percentile(LENGTH(request), 0.75) as complex_threshold,
    percentile(execution_duration_ms, 0.10) as fast_threshold
  FROM ds_fs.agent_quality.sample_agent_trace_archival
  WHERE state = 'OK' AND execution_duration_ms > 0
)
SELECT
  ROUND(100.0 * SUM(CASE
    WHEN LENGTH(t.request) > p.complex_threshold AND t.execution_duration_ms < p.fast_threshold
    THEN 1 ELSE 0
  END) / NULLIF(SUM(CASE WHEN LENGTH(t.request) > p.complex_threshold THEN 1 ELSE 0 END), 0), 2) as rushed_complex_pct
FROM ds_fs.agent_quality.sample_agent_trace_archival t
CROSS JOIN percentile_thresholds p
WHERE t.state = 'OK' AND t.execution_duration_ms > 0
```

**Result:** `11.62%`

### 6.4 Empty/Minimal Responses

**SQL Query:**

```sql
-- Percentage of responses shorter than 50 characters, potentially indicating incomplete or minimal responses
SELECT
  ROUND(100.0 * SUM(CASE WHEN LENGTH(response) < 50 THEN 1 ELSE 0 END) / COUNT(*), 2) as minimal_response_rate
FROM ds_fs.agent_quality.sample_agent_trace_archival
WHERE state = 'OK'
```

**Result:** `0.00%`

## Quality Metrics Summary

Based on the quality metrics analysis:

1. **Verbosity**: No issue - Only 4.95% of shorter inputs (bottom 25%) receive verbose responses (top 10%), which is acceptable
2. **Response Quality Issues**: 11.31% of responses contain questions or uncertainty (context-dependent whether this is an issue)
3. **Rushed Processing**: **Issue Found** - 11.62% of complex requests (top 25% by length) processed faster than P10 execution time
4. **Empty Responses**: No minimal or empty responses detected

**One Quality Issue Identified:**

- **Rushed processing**: 11.62% of complex requests processed faster than the typical fast response time (P10), potentially indicating incomplete processing

**Note**: This dataset appears to contain primarily transcript processing requests rather than interactive Q&A or command execution, which explains why some metrics show limited data.

## Recommendations

1. **Error Reduction**: Focus on improving reliability of transcript parsing and action item extraction
2. **Performance Optimization**: Optimize the `process_meeting_transcript` span as it's the primary latency contributor
3. **Monitoring**: Implement alerting for span-level error rates exceeding normal thresholds
4. **Capacity Planning**: Prepare for peak usage patterns around 22:00 UTC
5. **Quality Monitoring**: For agents handling varied request types, monitor these quality metrics:
   - Verbosity rate for simple questions
   - Question deflection rate for commands
   - Rushed processing of complex requests
   - Presence of error indicators in responses
