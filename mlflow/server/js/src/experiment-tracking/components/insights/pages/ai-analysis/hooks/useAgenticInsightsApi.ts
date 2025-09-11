/**
 * React Query hooks for MLflow Agentic Insights API
 */

import { useQuery, UseQueryResult } from '@tanstack/react-query';
import { 
  Analysis,
  Hypothesis,
  Issue,
  ListAnalysesResponse,
  ListHypothesesResponse,
  ListIssuesResponse,
  PreviewTracesResponse,
} from '../types';

// Base URL for agentic insights API
const AGENTIC_API_BASE = '/ajax-api/2.0/mlflow/traces/insights/agentic';

/**
 * Generic POST request helper
 */
async function postAgenticApi<TRequest, TResponse>(
  endpoint: string, 
  request: TRequest
): Promise<TResponse> {
  const response = await fetch(`${AGENTIC_API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `API request failed: ${response.statusText}`);
  }
  
  return response.json();
}

// ============================================================================
// Analyses Hooks
// ============================================================================

/**
 * Hook for fetching list of analyses in an experiment
 */
export function useAnalysesList(
  experimentId: string | undefined,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<ListAnalysesResponse> {
  return useQuery({
    queryKey: ['agentic-insights', 'analyses', 'list', experimentId],
    queryFn: () => postAgenticApi<{ experiment_id: string }, ListAnalysesResponse>(
      '/analyses/list',
      { experiment_id: experimentId! }
    ),
    enabled: options?.enabled !== false && !!experimentId,
    refetchInterval: options?.refetchInterval ?? 30000, // Default 30s
    staleTime: 10000, // 10 seconds
  });
}

/**
 * Hook for fetching a specific analysis
 */
export function useAnalysis(
  runId: string | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<{ analysis: Analysis }> {
  return useQuery({
    queryKey: ['agentic-insights', 'analyses', 'get', runId],
    queryFn: () => postAgenticApi<{ insights_run_id: string }, { analysis: Analysis }>(
      '/analyses/get',
      { insights_run_id: runId! }
    ),
    enabled: options?.enabled !== false && !!runId,
    staleTime: 10000,
  });
}

// ============================================================================
// Hypotheses Hooks
// ============================================================================

/**
 * Hook for fetching list of hypotheses in a run
 */
export function useHypothesesList(
  runId: string | undefined,
  options?: { 
    enabled?: boolean; 
    refetchInterval?: number | false;
    isActiveRun?: boolean;
  }
): UseQueryResult<ListHypothesesResponse> {
  // Poll every 2 seconds for active runs, 30 seconds for others
  const refetchInterval = options?.isActiveRun ? 2000 : (options?.refetchInterval ?? 30000);
  
  return useQuery({
    queryKey: ['agentic-insights', 'hypotheses', 'list', runId],
    queryFn: () => postAgenticApi<{ insights_run_id: string }, ListHypothesesResponse>(
      '/hypotheses/list',
      { insights_run_id: runId! }  // Backend expects insights_run_id, we pass run_id value as insights_run_id
    ),
    enabled: options?.enabled !== false && !!runId,
    refetchInterval,
    staleTime: options?.isActiveRun ? 1000 : 10000,
  });
}

/**
 * Hook for fetching a specific hypothesis
 */
export function useHypothesis(
  runId: string | undefined,
  hypothesisId: string | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<{ hypothesis: Hypothesis }> {
  return useQuery({
    queryKey: ['agentic-insights', 'hypotheses', 'get', runId, hypothesisId],
    queryFn: () => postAgenticApi<
      { insights_run_id: string; hypothesis_id: string },
      { hypothesis: Hypothesis }
    >(
      '/hypotheses/get',
      { insights_run_id: runId!, hypothesis_id: hypothesisId! }
    ),
    enabled: options?.enabled !== false && !!runId && !!hypothesisId,
    staleTime: 10000,
  });
}

/**
 * Hook for previewing traces associated with hypotheses
 */
export function useHypothesesPreview(
  runId: string | undefined,
  maxTraces?: number,
  options?: { enabled?: boolean }
): UseQueryResult<PreviewTracesResponse> {
  return useQuery({
    queryKey: ['agentic-insights', 'hypotheses', 'preview', runId, maxTraces],
    queryFn: () => postAgenticApi<
      { insights_run_id: string; max_traces?: number },
      PreviewTracesResponse
    >(
      '/hypotheses/preview',
      { insights_run_id: runId!, ...(maxTraces && { max_traces: maxTraces }) }
    ),
    enabled: options?.enabled !== false && !!runId,
    staleTime: 30000,
  });
}

// ============================================================================
// Issues Hooks
// ============================================================================

/**
 * Hook for fetching list of issues in an experiment
 * Note: Issues are automatically sorted by trace_count (descending) on the backend
 */
export function useIssuesList(
  experimentId: string | undefined,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<ListIssuesResponse> {
  return useQuery({
    queryKey: ['agentic-insights', 'issues', 'list', experimentId],
    queryFn: () => postAgenticApi<{ experiment_id: string }, ListIssuesResponse>(
      '/issues/list',
      { experiment_id: experimentId! }
    ),
    enabled: options?.enabled !== false && !!experimentId,
    refetchInterval: options?.refetchInterval ?? 30000, // Default 30s
    staleTime: 10000,
  });
}

/**
 * Hook for fetching a specific issue
 */
export function useIssue(
  issueId: string | undefined,
  options?: { enabled?: boolean }
): UseQueryResult<{ issue: Issue }> {
  return useQuery({
    queryKey: ['agentic-insights', 'issues', 'get', issueId],
    queryFn: () => postAgenticApi<{ issue_id: string }, { issue: Issue }>(
      '/issues/get',
      { issue_id: issueId! }
    ),
    enabled: options?.enabled !== false && !!issueId,
    staleTime: 10000,
  });
}

/**
 * Hook for previewing traces associated with issues
 */
export function useIssuesPreview(
  experimentId: string | undefined,
  maxTraces?: number,
  options?: { enabled?: boolean }
): UseQueryResult<PreviewTracesResponse> {
  return useQuery({
    queryKey: ['agentic-insights', 'issues', 'preview', experimentId, maxTraces],
    queryFn: () => postAgenticApi<
      { experiment_id: string; max_traces?: number },
      PreviewTracesResponse
    >(
      '/issues/preview',
      { experiment_id: experimentId!, ...(maxTraces && { max_traces: maxTraces }) }
    ),
    enabled: options?.enabled !== false && !!experimentId,
    staleTime: 30000,
  });
}