/**
 * Runs View for AI Analysis
 * 
 * Displays list of analysis runs with hypotheses
 */

import React, { useState } from 'react';
import {
  useDesignSystemTheme,
  ParagraphSkeleton,
  TitleSkeleton,
  Button,
  CheckCircleIcon,
  CloseIcon,
} from '@databricks/design-system';
import { useAnalysesList, useHypothesesList } from './hooks/useAgenticInsightsApi';
import { EmptyStateAIAnalysis } from './components/EmptyStateAIAnalysis';
import { TracePreview } from './components/TracePreview';
import { Analysis, Hypothesis } from './types';

interface RunsViewProps {
  experimentId?: string;
}

const getStatusIcon = (status: Analysis['status']) => {
  switch (status) {
    case 'ACTIVE':
      return <span css={{ color: '#1890ff', fontSize: '16px' }}>⏳</span>;
    case 'COMPLETED':
      return <CheckCircleIcon css={{ color: '#52c41a' }} />;
    case 'ARCHIVED':
      return <CloseIcon css={{ color: '#8c8c8c' }} />;
    default:
      return null;
  }
};

// Simple Badge component (same as in IssuesView)
const Badge: React.FC<{ 
  children: React.ReactNode; 
  type: 'hypothesis' | 'analysis' | 'evidence';
  value: string;
}> = ({ children, type, value }) => {
  const { theme } = useDesignSystemTheme();
  
  const getColor = () => {
    if (type === 'hypothesis') {
      switch (value) {
        case 'TESTING': return { bg: '#1890ff', text: 'white' };
        case 'VALIDATED': return { bg: '#52c41a', text: 'white' };
        case 'REJECTED': return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
        default: return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
      }
    } else if (type === 'analysis') {
      switch (value) {
        case 'ACTIVE': return { bg: '#1890ff', text: 'white' };
        case 'COMPLETED': return { bg: '#52c41a', text: 'white' };
        case 'ARCHIVED': return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
        default: return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
      }
    } else {
      // evidence
      return value === 'true' 
        ? { bg: '#52c41a', text: 'white' }
        : { bg: '#f5222d', text: 'white' };
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

interface HypothesisPanelProps {
  runId: string;
  isActive: boolean;
}

const HypothesisPanel: React.FC<HypothesisPanelProps> = ({ runId, isActive }) => {
  const { theme } = useDesignSystemTheme();
  const [expandedHypothesis, setExpandedHypothesis] = useState<string | null>(null);
  
  // Fetch hypotheses with polling for active runs
  const { data, isLoading, error } = useHypothesesList(runId, {
    isActiveRun: isActive,
  });
  
  if (isLoading) {
    return <ParagraphSkeleton />;
  }
  
  if (error) {
    return (
      <div css={{ 
        padding: theme.spacing.lg,
        color: theme.colors.textSecondary,
      }}>
        Error loading hypotheses: {(error as Error).message}
      </div>
    );
  }
  
  if (!data?.hypotheses?.length) {
    return (
      <div css={{ 
        padding: theme.spacing.lg,
        textAlign: 'center',
        color: theme.colors.textSecondary,
      }}>
        No hypotheses created yet
      </div>
    );
  }
  
  return (
    <>
      <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
        {data.hypotheses?.map((hypothesis) => (
          <div
            key={hypothesis.hypothesis_id}
            css={{
              border: `1px solid ${theme.colors.border}`,
              borderRadius: theme.general.borderRadiusBase,
              padding: theme.spacing.md,
            }}
          >
            {/* Hypothesis header */}
            <div css={{ 
              display: 'flex', 
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: theme.spacing.sm,
            }}>
              <div css={{ flex: 1 }}>
                <h4 css={{ 
                  margin: 0,
                  marginBottom: theme.spacing.xs,
                  fontSize: theme.typography.fontSizeMd,
                }}>
                  {hypothesis.statement}
                </h4>
                <div css={{ 
                  display: 'flex', 
                  gap: theme.spacing.sm,
                  alignItems: 'center',
                }}>
                  <Badge type="hypothesis" value={hypothesis.status}>
                    {hypothesis.status}
                  </Badge>
                  <span css={{ 
                    fontSize: theme.typography.fontSizeSm,
                    color: theme.colors.textSecondary,
                  }}>
                    {hypothesis.evidence_count || hypothesis.evidence?.length || 0} evidence items
                  </span>
                  {isActive && (
                    <span css={{ 
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.actionDefaultBackgroundDefault,
                      fontWeight: 500,
                    }}>
                      • Live
                    </span>
                  )}
                </div>
              </div>
              <Button
                componentId="hypothesis-expand-button"
                size="small"
                type="tertiary"
                onClick={() => setExpandedHypothesis(
                  expandedHypothesis === hypothesis.hypothesis_id 
                    ? null 
                    : hypothesis.hypothesis_id
                )}
              >
                {expandedHypothesis === hypothesis.hypothesis_id ? 'Hide' : 'Show'} Details
              </Button>
            </div>
            
            {/* Expanded details */}
            {expandedHypothesis === hypothesis.hypothesis_id && (
              <div css={{ marginTop: theme.spacing.md }}>
                {hypothesis.testing_plan ? (
                  <div css={{ marginBottom: theme.spacing.md }}>
                    <h5 css={{ 
                      marginBottom: theme.spacing.sm,
                      color: theme.colors.textSecondary,
                      fontSize: theme.typography.fontSizeSm,
                      textTransform: 'uppercase',
                    }}>
                      Testing Plan
                    </h5>
                    <p css={{ 
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.textSecondary,
                    }}>
                      {hypothesis.testing_plan}
                    </p>
                  </div>
                ) : (
                  <div css={{ marginBottom: theme.spacing.md }}>
                    <p css={{ 
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.textSecondary,
                      fontStyle: 'italic',
                    }}>
                      No testing plan available
                    </p>
                  </div>
                )}
                
                {hypothesis.evidence && hypothesis.evidence.length > 0 && (
                  <div>
                    <h5 css={{ 
                      marginBottom: theme.spacing.sm,
                      color: theme.colors.textSecondary,
                      fontSize: theme.typography.fontSizeSm,
                      textTransform: 'uppercase',
                    }}>
                      Evidence
                    </h5>
                    <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
                      {hypothesis.evidence?.map((evidence, idx) => (
                        <div
                          key={`${evidence.trace_id}-${idx}`}
                          css={{
                            padding: theme.spacing.md,
                            background: theme.colors.backgroundSecondary,
                            borderRadius: theme.general.borderRadiusBase,
                          }}
                        >
                          <div css={{ 
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            marginBottom: theme.spacing.sm,
                          }}>
                            <div>
                              <span css={{ 
                                fontFamily: 'monospace',
                                fontSize: theme.typography.fontSizeSm,
                              }}>
                                Trace: {evidence.trace_id}
                              </span>
                            </div>
                            <Badge type="evidence" value={evidence.supports ? 'true' : 'false'}>
                              {evidence.supports ? 'Supports' : 'Refutes'}
                            </Badge>
                          </div>
                          
                          {/* Trace preview with input/output */}
                          <TracePreview 
                            traceId={evidence.trace_id}
                            rationale={evidence.rationale}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
};

export const RunsView: React.FC<RunsViewProps> = ({ experimentId }) => {
  const { theme } = useDesignSystemTheme();
  const [selectedRun, setSelectedRun] = useState<Analysis | null>(null);
  
  // Fetch analyses list
  const { data, isLoading, error } = useAnalysesList(experimentId, {
    refetchInterval: 2000, // Refresh every 2 seconds
  });
  
  // Auto-select first run if none selected
  React.useEffect(() => {
    if (!selectedRun && data?.analyses && data.analyses.length > 0) {
      setSelectedRun(data.analyses[0]);
    }
  }, [data?.analyses, selectedRun]);
  
  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
    return date.toLocaleDateString();
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
        <p>Error loading analyses: {(error as Error).message}</p>
      </div>
    );
  }
  
  if (!data?.analyses?.length) {
    return <EmptyStateAIAnalysis type="analyses" />;
  }
  
  return (
    <div css={{ 
      display: 'flex', 
      gap: theme.spacing.lg,
      height: 'calc(100vh - 250px)', // Adjust based on your header/nav height
    }}>
      {/* Left side: Runs table as navigation */}
      <div css={{
        flex: '0 0 55%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <div css={{
          border: `1px solid ${theme.colors.border}`,
          borderRadius: theme.general.borderRadiusBase,
          overflow: 'hidden',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}>
          {/* Table header */}
          <div css={{
            display: 'grid',
            gridTemplateColumns: '40px 2fr 80px 80px 100px',
            background: theme.colors.backgroundSecondary,
            borderBottom: `1px solid ${theme.colors.border}`,
            padding: theme.spacing.sm,
            fontWeight: 600,
            fontSize: theme.typography.fontSizeSm,
            flexShrink: 0,
          }}>
            <div></div>
            <div>Analysis Run</div>
            <div>Hypotheses</div>
            <div>Validated</div>
            <div>Created</div>
          </div>
          
          {/* Table body - scrollable */}
          <div css={{
            flex: 1,
            overflow: 'auto',
          }}>
            {data.analyses?.map((analysis) => (
              <div
                key={analysis.run_id}
                css={{
                  display: 'grid',
                  gridTemplateColumns: '40px 2fr 80px 80px 100px',
                  padding: theme.spacing.sm,
                  borderBottom: `1px solid ${theme.colors.border}`,
                  cursor: 'pointer',
                  background: selectedRun?.run_id === analysis.run_id 
                    ? theme.colors.actionDefaultBackgroundDefault + '15' 
                    : 'transparent',
                  borderLeft: selectedRun?.run_id === analysis.run_id
                    ? `3px solid ${theme.colors.actionDefaultBackgroundDefault}`
                    : '3px solid transparent',
                  '&:hover': {
                    background: selectedRun?.run_id === analysis.run_id
                      ? theme.colors.actionDefaultBackgroundDefault + '20'
                      : theme.colors.backgroundSecondary,
                  },
                  '&:last-child': {
                    borderBottom: 'none',
                  },
                }}
                onClick={() => setSelectedRun(analysis)}
              >
                <div css={{ display: 'flex', alignItems: 'center' }}>
                  {getStatusIcon(analysis.status)}
                </div>
                <div>
                  <div css={{ fontWeight: 500 }}>{analysis.name}</div>
                  {analysis.description && (
                    <div css={{ 
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.textSecondary,
                      marginTop: theme.spacing.xs,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      lineHeight: '1.4',
                    }}>
                      {analysis.description}
                    </div>
                  )}
                  <div css={{ 
                    fontFamily: 'monospace',
                    fontSize: '11px',
                    color: theme.colors.textSecondary,
                    marginTop: theme.spacing.xs,
                  }}>
                    {analysis.run_id.slice(0, 8)}...
                  </div>
                </div>
                <div css={{ textAlign: 'center' }}>{analysis.hypothesis_count || 0}</div>
                <div css={{ textAlign: 'center' }}>{analysis.validated_count || 0}</div>
                <div css={{ fontSize: theme.typography.fontSizeSm }}>
                  {formatTimestamp(analysis.created_at)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Right side: Selected run details */}
      <div css={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {selectedRun ? (
          <div css={{
            border: `1px solid ${theme.colors.border}`,
            borderRadius: theme.general.borderRadiusBase,
            padding: theme.spacing.lg,
            height: '100%',
            overflow: 'auto',
          }}>
            {/* Run header */}
            <div css={{ marginBottom: theme.spacing.lg }}>
              <h3 css={{ 
                margin: 0,
                marginBottom: theme.spacing.md,
                display: 'flex',
                alignItems: 'center',
                gap: theme.spacing.sm,
              }}>
                {selectedRun.name}
                {selectedRun.status === 'ACTIVE' && (
                  <span css={{ 
                    fontSize: theme.typography.fontSizeSm,
                    color: theme.colors.actionDefaultBackgroundDefault,
                    fontWeight: 500,
                  }}>
                    (Live - refreshing every 2s)
                  </span>
                )}
              </h3>
              
              <div css={{ 
                display: 'flex', 
                gap: theme.spacing.md,
                alignItems: 'center',
                marginBottom: theme.spacing.md,
              }}>
                {getStatusIcon(selectedRun.status)}
                <Badge type="analysis" value={selectedRun.status}>{selectedRun.status}</Badge>
                <span css={{ color: theme.colors.textSecondary, fontSize: theme.typography.fontSizeSm }}>
                  {selectedRun.hypothesis_count || 0} hypotheses • {selectedRun.validated_count || 0} validated
                </span>
              </div>
              
              {selectedRun.description && (
                <p css={{ 
                  color: theme.colors.textSecondary,
                  margin: 0,
                }}>
                  {selectedRun.description}
                </p>
              )}
            </div>
            
            {/* Hypotheses section */}
            <div>
              <h4 css={{ 
                marginBottom: theme.spacing.md,
                borderBottom: `1px solid ${theme.colors.border}`,
                paddingBottom: theme.spacing.sm,
              }}>
                Hypotheses
              </h4>
              
              {selectedRun.run_id ? (
                <HypothesisPanel 
                  runId={selectedRun.run_id}
                  isActive={selectedRun.status === 'ACTIVE'}
                />
              ) : (
                <div css={{ color: theme.colors.textSecondary }}>
                  No run ID available
                </div>
              )}
            </div>
          </div>
        ) : (
          <div css={{
            border: `1px solid ${theme.colors.border}`,
            borderRadius: theme.general.borderRadiusBase,
            padding: theme.spacing.lg,
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: theme.colors.textSecondary,
          }}>
            Select a run from the left to view details
          </div>
        )}
      </div>
    </div>
  );
};