/**
 * Issues View for AI Analysis
 * 
 * Displays list of validated issues from AI analyses
 */

import React, { useState } from 'react';
import {
  useDesignSystemTheme,
  ParagraphSkeleton,
  TitleSkeleton,
  Modal,
  Button,
  SimpleSelect,
  SimpleSelectOption,
} from '@databricks/design-system';
import { useIssuesList } from './hooks/useAgenticInsightsApi';
import { EmptyStateAIAnalysis } from './components/EmptyStateAIAnalysis';
import { TraceEvidenceDrawer } from './components/TraceEvidenceDrawer';
import { Issue } from './types';

interface IssuesViewProps {
  experimentId?: string;
}

type SortField = 'trace_count' | 'severity' | 'created_at' | 'status';
type SortOrder = 'asc' | 'desc';

// Simple Badge component
const Badge: React.FC<{ 
  children: React.ReactNode; 
  type: 'severity' | 'status';
  value: string;
}> = ({ children, type, value }) => {
  const { theme } = useDesignSystemTheme();
  
  const getColor = () => {
    if (type === 'severity') {
      switch (value) {
        case 'CRITICAL': return { bg: '#f5222d', text: 'white' };
        case 'HIGH': return { bg: '#fa8c16', text: 'white' };
        case 'MEDIUM': return { bg: '#fadb14', text: 'black' };
        case 'LOW': return { bg: '#52c41a', text: 'white' };
        default: return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
      }
    } else {
      switch (value) {
        case 'OPEN': return { bg: '#1890ff', text: 'white' };
        case 'IN_PROGRESS': return { bg: '#fa8c16', text: 'white' };
        case 'RESOLVED': return { bg: '#52c41a', text: 'white' };
        case 'REJECTED': return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
        default: return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
      }
    }
  };
  
  const colors = getColor();
  
  return (
    <span css={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: 600,
      textTransform: 'uppercase',
      background: colors.bg,
      color: colors.text,
    }}>
      {children}
    </span>
  );
};

export const IssuesView: React.FC<IssuesViewProps> = ({ experimentId }) => {
  const { theme } = useDesignSystemTheme();
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('trace_count');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  
  // Fetch issues list
  const { data, isLoading, error } = useIssuesList(experimentId, {
    refetchInterval: 2000, // Refresh every 2 seconds
  });
  
  // Sort issues client-side (backend already sorts by trace_count by default)
  const sortedIssues = React.useMemo(() => {
    if (!data?.issues) return [];
    
    return [...data.issues].sort((a, b) => {
      let compareValue = 0;
      
      switch (sortField) {
        case 'trace_count':
          compareValue = (a.trace_count || 0) - (b.trace_count || 0);
          break;
        case 'severity':
          const severityOrder = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
          compareValue = severityOrder[a.severity] - severityOrder[b.severity];
          break;
        case 'created_at':
          compareValue = a.created_at - b.created_at;
          break;
        case 'status':
          compareValue = a.status.localeCompare(b.status);
          break;
      }
      
      return sortOrder === 'desc' ? -compareValue : compareValue;
    });
  }, [data?.issues, sortField, sortOrder]);
  
  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };
  
  if (isLoading) {
    return (
      <div css={{ padding: theme.spacing.md }}>
        <TitleSkeleton />
        <div css={{ marginTop: theme.spacing.lg }}>
          <ParagraphSkeleton />
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div css={{
        padding: theme.spacing.lg,
        textAlign: 'center',
        color: theme.colors.textSecondary,
      }}>
        <p>Error loading issues: {(error as Error).message}</p>
      </div>
    );
  }
  
  if (!sortedIssues.length) {
    return <EmptyStateAIAnalysis type="issues" />;
  }
  
  return (
    <>
      <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
        {/* Sorting controls */}
        <div css={{ 
          display: 'flex', 
          gap: theme.spacing.md,
          alignItems: 'center',
          marginBottom: theme.spacing.md,
        }}>
          <label css={{ fontSize: theme.typography.fontSizeSm }}>Sort by:</label>
          <SimpleSelect
            componentId="sort-field-select"
            id="sort-field-select"
            value={sortField}
            onChange={(value) => setSortField(value as unknown as SortField)}
          >
            <SimpleSelectOption value="trace_count">Trace Count</SimpleSelectOption>
            <SimpleSelectOption value="severity">Severity</SimpleSelectOption>
            <SimpleSelectOption value="created_at">Created</SimpleSelectOption>
            <SimpleSelectOption value="status">Status</SimpleSelectOption>
          </SimpleSelect>
          
          <SimpleSelect
            componentId="sort-order-select"
            id="sort-order-select"
            value={sortOrder}
            onChange={(value) => setSortOrder(value as unknown as SortOrder)}
          >
            <SimpleSelectOption value="desc">Descending</SimpleSelectOption>
            <SimpleSelectOption value="asc">Ascending</SimpleSelectOption>
          </SimpleSelect>
        </div>
        
        {/* Issues table using divs */}
        <div css={{
          border: `1px solid ${theme.colors.border}`,
          borderRadius: theme.general.borderRadiusBase,
          overflow: 'hidden',
        }}>
          {/* Table header */}
          <div css={{
            display: 'grid',
            gridTemplateColumns: '2fr 100px 100px 80px 150px 120px',
            background: theme.colors.backgroundSecondary,
            borderBottom: `1px solid ${theme.colors.border}`,
            padding: theme.spacing.sm,
            fontWeight: 600,
            fontSize: theme.typography.fontSizeSm,
          }}>
            <div>Title</div>
            <div>Severity</div>
            <div>Status</div>
            <div>Traces</div>
            <div>Created</div>
            <div>Source Run</div>
          </div>
          
          {/* Table body */}
          <div>
            {sortedIssues.map((issue) => (
              <div
                key={issue.issue_id}
                css={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 100px 100px 80px 150px 120px',
                  padding: theme.spacing.sm,
                  borderBottom: `1px solid ${theme.colors.border}`,
                  cursor: 'pointer',
                  '&:hover': {
                    background: theme.colors.backgroundSecondary,
                  },
                  '&:last-child': {
                    borderBottom: 'none',
                  },
                }}
                onClick={() => setSelectedIssue(issue)}
              >
                <div>
                  <div css={{ fontWeight: 500 }}>{issue.title}</div>
                  <div css={{ 
                    fontSize: theme.typography.fontSizeSm,
                    color: theme.colors.textSecondary,
                    marginTop: theme.spacing.xs,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: '400px',
                  }}>
                    {issue.description}
                  </div>
                </div>
                <div>
                  <Badge type="severity" value={issue.severity}>
                    {issue.severity}
                  </Badge>
                </div>
                <div>
                  <Badge type="status" value={issue.status}>
                    {issue.status}
                  </Badge>
                </div>
                <div>{issue.trace_count || 0}</div>
                <div css={{ fontSize: theme.typography.fontSizeSm }}>
                  {formatTimestamp(issue.created_at)}
                </div>
                <div>
                  {issue.source_run_id ? (
                    <span css={{ 
                      fontFamily: 'monospace',
                      fontSize: theme.typography.fontSizeSm,
                    }}>
                      {issue.source_run_id.slice(0, 8)}...
                    </span>
                  ) : '-'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Issue Detail Modal */}
      {selectedIssue && (
        <Modal
          componentId="issue-detail-modal"
          visible={!!selectedIssue}
          onCancel={() => setSelectedIssue(null)}
          title={selectedIssue.title}
          footer={null}
        >
          <div css={{ padding: theme.spacing.lg }}>
            {/* Issue metadata */}
            <div css={{ 
              display: 'flex', 
              gap: theme.spacing.md,
              marginBottom: theme.spacing.lg,
            }}>
              <Badge type="severity" value={selectedIssue.severity}>
                {selectedIssue.severity}
              </Badge>
              <Badge type="status" value={selectedIssue.status}>
                {selectedIssue.status}
              </Badge>
              <span css={{ color: theme.colors.textSecondary }}>
                {selectedIssue.trace_count || 0} traces
              </span>
            </div>
            
            {/* Description */}
            {selectedIssue.description && (
              <div css={{ marginBottom: theme.spacing.lg }}>
                <h4 css={{ marginBottom: theme.spacing.sm }}>Description</h4>
                <p css={{ color: theme.colors.textSecondary }}>
                  {selectedIssue.description}
                </p>
              </div>
            )}
            
            {/* Resolution (if resolved) */}
            {selectedIssue.resolution && (
              <div css={{ marginBottom: theme.spacing.lg }}>
                <h4 css={{ marginBottom: theme.spacing.sm }}>Resolution</h4>
                <p css={{ color: theme.colors.textSecondary }}>
                  {selectedIssue.resolution}
                </p>
              </div>
            )}
            
            {/* Evidence */}
            {selectedIssue.evidence && selectedIssue.evidence.length > 0 && (
              <div>
                <h4 css={{ marginBottom: theme.spacing.sm }}>Evidence</h4>
                <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.sm }}>
                  {selectedIssue.evidence.map((evidence) => (
                  <div
                    key={evidence.trace_id}
                    css={{
                      padding: theme.spacing.md,
                      background: theme.colors.backgroundSecondary,
                      borderRadius: theme.general.borderRadiusBase,
                      cursor: 'pointer',
                      '&:hover': {
                        background: theme.colors.actionDefaultBackgroundHover,
                      },
                    }}
                    onClick={() => setSelectedTraceId(evidence.trace_id)}
                  >
                    <div css={{ 
                      fontFamily: 'monospace',
                      fontSize: theme.typography.fontSizeSm,
                      marginBottom: theme.spacing.xs,
                    }}>
                      Trace: {evidence.trace_id}
                    </div>
                    <div css={{ 
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.textSecondary,
                    }}>
                      {evidence.rationale}
                    </div>
                  </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
      
      {/* Trace Evidence Drawer */}
      {selectedTraceId && (
        <TraceEvidenceDrawer
          traceId={selectedTraceId}
          onClose={() => setSelectedTraceId(null)}
        />
      )}
    </>
  );
};