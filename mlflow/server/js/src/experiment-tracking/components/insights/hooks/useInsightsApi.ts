/**
 * React Query hooks for MLflow Trace Insights API
 * 
 * All data fetching MUST use these hooks - NO useEffect patterns!
 * These hooks follow the exact REST API specifications from insights_rest_api.md
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { 
  // Traffic types
  VolumeRequest, VolumeResponse,
  LatencyRequest, LatencyResponse,
  ErrorRequest, ErrorResponse,
  // Assessment types
  AssessmentDiscoveryRequest, AssessmentDiscoveryResponse,
  AssessmentMetricsRequest, AssessmentMetricsResponse,
  // Tool types
  ToolDiscoveryRequest, ToolDiscoveryResponse,
  ToolMetricsRequest, ToolMetricsResponse,
  // Tag types
  TagDiscoveryRequest, TagDiscoveryResponse,
  TagMetricsRequest, TagMetricsResponse,
  // Dimension types
  DimensionDiscoveryRequest, DimensionDiscoveryResponse,
  NPMIRequest, NPMIResponse,
  CorrelationsRequest, CorrelationsResponse,
} from '../types/insights';
import { useInsightsTimeRange } from './useInsightsTimeRange';

// Base URL for all insights API calls
const INSIGHTS_API_BASE = '/ajax-api/2.0/mlflow/traces/insights';

/**
 * Get the user's timezone (IANA timezone name)
 */
function getUserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    // Fallback to UTC if timezone detection fails
    return 'UTC';
  }
}

/**
 * Generic POST request helper
 */
async function postInsightsApi<TRequest, TResponse>(
  endpoint: string, 
  request: TRequest
): Promise<TResponse> {
  const response = await fetch(`${INSIGHTS_API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`);
  }
  
  return response.json();
}

// ============================================================================
// Traffic & Cost Hooks
// ============================================================================

/**
 * Hook for fetching trace volume data
 * Automatically includes time range parameters from URL state
 */
export function useTraceVolume(
  baseRequest: Omit<VolumeRequest, 'start_time' | 'end_time' | 'timezone'>,
  options?: { enabled?: boolean; refetchInterval?: number }
): UseQueryResult<VolumeResponse> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  const timezone = getUserTimezone();
  const request: VolumeRequest = {
    ...baseRequest,
    start_time: timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null,
    end_time: timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null,
    timezone: timezone,
  };

  return useQuery({
    queryKey: ['trace-insights', 'traffic', 'volume', request],
    queryFn: () => postInsightsApi<VolumeRequest, VolumeResponse>('/traffic-cost/volume', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000, // 30 seconds
  });
}

/**
 * Hook for fetching latency percentile data
 * Automatically includes time range parameters from URL state
 */
export function useTraceLatency(
  baseRequest: Omit<LatencyRequest, 'start_time' | 'end_time' | 'timezone'>,
  options?: { enabled?: boolean; refetchInterval?: number }
): UseQueryResult<LatencyResponse> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  const request: LatencyRequest = {
    ...baseRequest,
    start_time: timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null,
    end_time: timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null,
    timezone: getUserTimezone(),
  };

  return useQuery({
    queryKey: ['trace-insights', 'traffic', 'latency', request],
    queryFn: () => postInsightsApi<LatencyRequest, LatencyResponse>('/traffic-cost/latency', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

/**
 * Hook for fetching error rate data
 * Automatically includes time range parameters from URL state
 */
export function useTraceErrors(
  baseRequest: Omit<ErrorRequest, 'start_time' | 'end_time' | 'timezone'>,
  options?: { enabled?: boolean; refetchInterval?: number }
): UseQueryResult<ErrorResponse> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  const request: ErrorRequest = {
    ...baseRequest,
    start_time: timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null,
    end_time: timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null,
    timezone: getUserTimezone(),
  };

  return useQuery({
    queryKey: ['trace-insights', 'traffic', 'errors', request],
    queryFn: () => postInsightsApi<ErrorRequest, ErrorResponse>('/traffic-cost/errors', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

// ============================================================================
// Assessment Hooks
// ============================================================================

/**
 * Hook for discovering available assessments
 */
export function useAssessmentDiscovery(
  experimentIds: string[],
  options?: { refetchInterval?: number }
): UseQueryResult<{ assessments: Array<{ name: string; data_type: 'boolean' | 'numeric' | 'string'; source: string; count: number }> }> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  return useQuery({
    queryKey: ['trace-insights', 'assessments', 'discovery', experimentIds, timeRangeFilters.startTime, timeRangeFilters.endTime],
    queryFn: async () => {
      const requestData = {
        experiment_ids: experimentIds,
        start_time: timeRangeFilters.startTime,
        end_time: timeRangeFilters.endTime
      };
      
      const response: any = await postInsightsApi('/quality/assessments/discovery', requestData);
      
      // Transform API response from {data: [...]} to {assessments: [...]} format
      // and map field names from API response to expected UI format
      const transformedData = {
        assessments: response.data.map((item: any) => ({
          name: item.assessment_name,
          data_type: item.assessment_type, // Now properly returns 'boolean', 'pass-fail', 'numeric', or 'string'
          source: Array.isArray(item.sources) ? item.sources.join(', ') : item.sources || 'Unknown',
          count: item.trace_count
        }))
      };
      
      return transformedData;
    },
    enabled: experimentIds.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 60000, // 1 minute
  });
}

/**
 * Hook for fetching detailed assessment metrics
 */
export function useAssessmentMetrics(
  request: AssessmentMetricsRequest,
  options?: { enabled?: boolean; refetchInterval?: number }
): UseQueryResult<AssessmentMetricsResponse> {
  return useQuery({
    queryKey: ['trace-insights', 'assessments', 'metrics', request],
    queryFn: () => postInsightsApi<AssessmentMetricsRequest, AssessmentMetricsResponse>('/quality/assessments/metrics', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0 && !!request.assessment_name,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

/**
 * Hook for fetching assessment data (simplified)
 * Automatically includes time range parameters from URL state
 */
export function useAssessmentData(
  assessmentName: string,
  experimentIds: string[],
  options?: { refetchInterval?: number; enabled?: boolean },
  timeBucket: 'hour' | 'day' | 'week' = 'hour'
): UseQueryResult<{
  summary: { 
    total_count?: number; 
    failure_count?: number; 
    failure_rate?: number;
    below_p50_count?: number;
    p50_value?: number;
    p90_value?: number;
    p99_value?: number;
  };
  time_series: Array<{ 
    time_bucket: string; 
    count: number; 
    failure_rate?: number;
    p50_value?: number;
  }>;
}> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  const request = {
    assessment_name: assessmentName,
    experiment_ids: experimentIds,
    time_bucket: timeBucket,
    start_time: timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null,
    end_time: timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null,
    timezone: getUserTimezone(),
  };

  return useQuery({
    queryKey: ['trace-insights', 'assessments', 'data', assessmentName, experimentIds, timeBucket, timeRangeFilters.startTime, timeRangeFilters.endTime],
    queryFn: () => postInsightsApi('/assessments/data', request),
    enabled: (options?.enabled !== false) && experimentIds.length > 0 && !!assessmentName,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

// ============================================================================
// Tool Hooks
// ============================================================================

/**
 * Hook for discovering tools used in traces
 */
export function useToolDiscovery(
  request: { experiment_ids: string[]; start_time?: number; end_time?: number; limit?: number },
  options?: { enabled?: boolean }
): UseQueryResult<{ tools: Array<{ 
  tool_name: string; 
  total_calls: number; 
  success_count: number;
  error_count: number; 
  error_rate: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p90_latency_ms: number;
  p99_latency_ms: number;
  first_seen: string;
  last_seen: string;
}> }> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  // Use the request time range if provided, otherwise fall back to global time range
  // Convert time strings to Unix timestamps (milliseconds) like other hooks do
  const requestWithTimeRange = {
    ...request,
    start_time: request.start_time ?? (timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null),
    end_time: request.end_time ?? (timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null),
  };


  return useQuery({
    queryKey: ['trace-insights', 'tools', 'discovery', requestWithTimeRange],
    queryFn: () => postInsightsApi('/tools/discovery', requestWithTimeRange),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    staleTime: 60000,
  });
}

/**
 * Hook for fetching detailed tool metrics
 */
export function useToolMetrics(
  baseRequest: { tool_name?: string; experiment_ids: string[]; time_bucket?: string },
  options?: { enabled?: boolean; refetchInterval?: number }
): UseQueryResult<{ 
  summary?: {
    avg_latency?: number;
    p50_latency?: number;
    p90_latency?: number; 
    p99_latency?: number;
    usage_count?: number;
    error_count?: number;
    error_rate?: number;
  };
  time_series: Array<{ 
    time_bucket: number; 
    usage_count: number; 
    error_count: number;
    error_rate: number;
    avg_latency?: number;
    p50_latency?: number;
    p90_latency?: number;
    p99_latency?: number;
  }> 
}> {
  const [timeRangeFilters] = useInsightsTimeRange();
  
  // Include time range parameters like other hooks do
  const request = {
    ...baseRequest,
    start_time: timeRangeFilters.startTime ? new Date(timeRangeFilters.startTime).getTime() : null,
    end_time: timeRangeFilters.endTime ? new Date(timeRangeFilters.endTime).getTime() : null,
    timezone: getUserTimezone(),
  };

  return useQuery({
    queryKey: ['trace-insights', 'tools', 'metrics', request],
    queryFn: () => postInsightsApi('/tools/metrics', request),
    enabled: options?.enabled !== false && baseRequest.experiment_ids.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

// The Assessment hooks are defined above (lines 106-140)

// ============================================================================
// Tag Hooks
// ============================================================================

/**
 * Hook for discovering tag keys
 */
export function useTagDiscovery(
  experimentIds: string[],
  options?: { refetchInterval?: number }
): UseQueryResult<{ tag_keys: Array<{ key: string; trace_count: number; unique_values_count: number }> }> {
  return useQuery({
    queryKey: ['trace-insights', 'tags', 'discovery', experimentIds],
    queryFn: () => postInsightsApi('/tags/discovery', { experiment_ids: experimentIds }),
    enabled: experimentIds.length > 0,
    refetchInterval: options?.refetchInterval,
    staleTime: 60000,
  });
}

/**
 * Hook for fetching tag values
 */
export function useTagValues(
  tagKey: string,
  experimentIds: string[],
  options?: { limit?: number; refetchInterval?: number }
): UseQueryResult<{ values: Array<{ value: string; count: number }> }> {
  return useQuery({
    queryKey: ['trace-insights', 'tags', 'values', tagKey, experimentIds, options?.limit],
    queryFn: () => postInsightsApi('/tags/values', { 
      tag_key: tagKey,
      experiment_ids: experimentIds,
      limit: options?.limit || 10,
    }),
    enabled: experimentIds.length > 0 && !!tagKey,
    refetchInterval: options?.refetchInterval,
    staleTime: 30000,
  });
}

/**
 * Hook for fetching tag value distribution
 */
export function useTagMetrics(
  request: TagMetricsRequest,
  options?: { enabled?: boolean }
): UseQueryResult<TagMetricsResponse> {
  return useQuery({
    queryKey: ['trace-insights', 'tags', 'metrics', request],
    queryFn: () => postInsightsApi<TagMetricsRequest, TagMetricsResponse>('/tags/metrics', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0 && !!request.tag_key,
    staleTime: 30000,
  });
}

// ============================================================================
// Dimension & Correlation Hooks
// ============================================================================

/**
 * Hook for discovering available dimensions
 */
export function useDimensionDiscovery(
  request: DimensionDiscoveryRequest,
  options?: { enabled?: boolean }
): UseQueryResult<DimensionDiscoveryResponse> {
  return useQuery({
    queryKey: ['trace-insights', 'dimensions', 'discovery', request],
    queryFn: () => postInsightsApi<DimensionDiscoveryRequest, DimensionDiscoveryResponse>('/dimensions/discovery', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    staleTime: 60000,
  });
}

/**
 * Hook for calculating NPMI correlation between two dimensions
 */
export function useNPMICalculation(
  request: NPMIRequest,
  options?: { enabled?: boolean }
): UseQueryResult<NPMIResponse> {
  return useQuery({
    queryKey: ['trace-insights', 'dimensions', 'npmi', request],
    queryFn: () => postInsightsApi<NPMIRequest, NPMIResponse>('/dimensions/npmi', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    staleTime: 30000,
  });
}

/**
 * Hook for getting correlations for a given filter
 * This is the main hook for populating correlation sections on cards
 */
export function useCorrelations(
  request: CorrelationsRequest,
  options?: { enabled?: boolean }
): UseQueryResult<CorrelationsResponse> {
  return useQuery({
    queryKey: ['trace-insights', 'correlations', request],
    queryFn: () => postInsightsApi<CorrelationsRequest, CorrelationsResponse>('/correlations', request),
    enabled: options?.enabled !== false && request.experiment_ids.length > 0,
    staleTime: 30000,
  });
}

// ============================================================================
// Compound Hooks for Common Patterns
// ============================================================================

/**
 * Hook to fetch all traffic metrics at once
 */
export function useTrafficMetrics(
  experimentIds: string[],
  timeRange?: { start_time?: number; end_time?: number },
  options?: { enabled?: boolean; refetchInterval?: number }
) {
  const baseRequest = {
    experiment_ids: experimentIds,
    start_time: timeRange?.start_time,
    end_time: timeRange?.end_time,
    time_bucket: 'hour' as const,
  };
  
  const volume = useTraceVolume(baseRequest, options);
  const latency = useTraceLatency(baseRequest, options);
  const errors = useTraceErrors(baseRequest, options);
  
  return {
    volume,
    latency,
    errors,
    isLoading: volume.isLoading || latency.isLoading || errors.isLoading,
    isError: volume.isError || latency.isError || errors.isError,
  };
}

/**
 * Hook to get correlations for error states
 */
export function useErrorCorrelations(
  experimentIds: string[],
  options?: { enabled?: boolean }
): UseQueryResult<CorrelationsResponse> {
  return useCorrelations({
    experiment_ids: experimentIds,
    filter_string: 'status:ERROR',
    correlation_dimensions: ['tag', 'span_attribute'],
    limit: 10,
  }, options);
}

/**
 * Hook to get correlations for high latency
 */
export function useLatencyCorrelations(
  experimentIds: string[],
  p99Threshold: number,
  options?: { enabled?: boolean }
): UseQueryResult<CorrelationsResponse> {
  return useCorrelations({
    experiment_ids: experimentIds,
    filter_string: `latency:>${p99Threshold}`,
    correlation_dimensions: ['tag', 'span_attribute'],
    limit: 10,
  }, options);
}