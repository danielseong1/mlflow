/**
 * TypeScript types for AI Analysis (Agentic Insights)
 */

export interface Analysis {
  run_id: string;
  name: string;
  description?: string;
  status: 'ACTIVE' | 'COMPLETED' | 'ARCHIVED';
  hypothesis_count?: number;
  validated_count?: number;
  created_at: number;
  updated_at: number;
  metadata?: Record<string, any>;
}

export interface Hypothesis {
  hypothesis_id: string;
  statement: string;
  testing_plan?: string;
  status: 'TESTING' | 'VALIDATED' | 'REJECTED';
  evidence?: Evidence[];  // Optional - may not be present in all responses
  evidence_count?: number;
  trace_count?: number;
  supports_count?: number;
  refutes_count?: number;
  metrics?: Record<string, any>;
  created_at: number;
  updated_at: number;
  metadata?: Record<string, any>;
}

export interface Evidence {
  trace_id: string;
  rationale: string;
  supports: boolean;
}

export interface Issue {
  issue_id: string;
  source_run_id?: string;
  hypothesis_id?: string;
  title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'REJECTED';
  evidence?: IssueEvidence[];
  trace_count?: number;  // Backend returns this instead of trace_ids
  assessments?: string[];
  resolution?: string;
  created_at: number;
  updated_at: number;
  metadata?: Record<string, any>;
}

export interface IssueEvidence {
  trace_id: string;
  rationale: string;
}

export interface TracePreview {
  trace_id: string;
  request_id: string;
  status: string;
  execution_time_ms: number;
  timestamp: number;
  evidence_rationale?: string;
}

// API Response types
export interface ListAnalysesResponse {
  analyses: Analysis[];
}

export interface ListHypothesesResponse {
  hypotheses: Hypothesis[];
}

export interface ListIssuesResponse {
  issues: Issue[];
}

export interface PreviewTracesResponse {
  traces: TracePreview[];
  total_count: number;
  returned_count: number;
}