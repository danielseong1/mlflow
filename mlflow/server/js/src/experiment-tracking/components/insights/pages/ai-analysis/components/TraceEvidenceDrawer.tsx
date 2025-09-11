/**
 * Trace Evidence Drawer component
 * 
 * Shows trace details in a modal with request/response preview
 */

import React, { useState } from 'react';
import {
  useDesignSystemTheme,
  Modal,
  Tabs,
  ParagraphSkeleton,
  TitleSkeleton,
  Button,
} from '@databricks/design-system';
import { useQuery } from '@tanstack/react-query';

interface TraceEvidenceDrawerProps {
  traceId: string;
  onClose: () => void;
}

interface TraceData {
  info: {
    request_id: string;
    experiment_id: string;
    timestamp_ms: number;
    execution_time_ms: number;
    status: string;
    status_message?: string;
    request_metadata?: Record<string, any>;
    tags?: Record<string, string>;
  };
  data: {
    request?: string;
    response?: string;
    spans?: Array<{
      name: string;
      span_id: string;
      parent_id?: string;
      start_time_ns: number;
      end_time_ns: number;
      status_code: string;
      status_message?: string;
      attributes?: Record<string, any>;
      events?: Array<{
        name: string;
        timestamp_ns: number;
        attributes?: Record<string, any>;
      }>;
    }>;
  };
}

const fetchTrace = async (traceId: string): Promise<TraceData> => {
  const response = await fetch(`/ajax-api/2.0/mlflow/traces/get?request_id=${traceId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch trace: ${response.statusText}`);
  }
  const data = await response.json();
  return data.trace;
};

export const TraceEvidenceDrawer: React.FC<TraceEvidenceDrawerProps> = ({ traceId, onClose }) => {
  const { theme } = useDesignSystemTheme();
  const [activeTab, setActiveTab] = useState<'overview' | 'request' | 'response' | 'spans'>('overview');
  
  const { data: trace, isLoading, error } = useQuery({
    queryKey: ['trace', traceId],
    queryFn: () => fetchTrace(traceId),
    staleTime: 60000, // 1 minute
  });
  
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };
  
  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };
  
  // Simple status badge component
  const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const getColor = () => {
      switch (status.toUpperCase()) {
        case 'OK':
        case 'SUCCESS':
          return { bg: '#52c41a', text: 'white' };
        case 'ERROR':
        case 'FAILED':
          return { bg: '#f5222d', text: 'white' };
        default:
          return { bg: theme.colors.backgroundSecondary, text: theme.colors.textPrimary };
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
        {status}
      </span>
    );
  };
  
  return (
    <Modal
      componentId="trace-evidence-modal"
      visible={true}
      onCancel={onClose}
      title={
        <div css={{ display: 'flex', alignItems: 'center', gap: theme.spacing.sm }}>
          <span>Trace Evidence</span>
          <span css={{ 
            fontFamily: 'monospace',
            fontSize: theme.typography.fontSizeSm,
            color: theme.colors.textSecondary,
          }}>
            {traceId}
          </span>
        </div>
      }
      footer={null}
    >
      <div css={{ padding: theme.spacing.lg }}>
        {isLoading && (
          <div>
            <TitleSkeleton />
            <ParagraphSkeleton />
          </div>
        )}
        
        {error && (
          <div css={{
            padding: theme.spacing.lg,
            textAlign: 'center',
            color: theme.colors.textSecondary,
          }}>
            <p>Error loading trace: {(error as Error).message}</p>
          </div>
        )}
        
        {trace && (
          <>
            {/* Trace summary */}
            <div css={{
              display: 'flex',
              gap: theme.spacing.md,
              marginBottom: theme.spacing.lg,
              padding: theme.spacing.md,
              background: theme.colors.backgroundSecondary,
              borderRadius: theme.general.borderRadiusBase,
            }}>
              <StatusBadge status={trace.info.status} />
              <span css={{ fontSize: theme.typography.fontSizeSm }}>
                Duration: {formatDuration(trace.info.execution_time_ms)}
              </span>
              <span css={{ fontSize: theme.typography.fontSizeSm }}>
                {formatTimestamp(trace.info.timestamp_ms)}
              </span>
              {trace.data.spans && (
                <span css={{ fontSize: theme.typography.fontSizeSm }}>
                  {trace.data.spans.length} spans
                </span>
              )}
            </div>
            
            {/* Tabs for different views */}
            <Tabs.Root componentId="trace-tabs" value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
              <Tabs.List css={{ marginBottom: theme.spacing.md }}>
                <Tabs.Trigger value="overview">Overview</Tabs.Trigger>
                <Tabs.Trigger value="request">Request</Tabs.Trigger>
                <Tabs.Trigger value="response">Response</Tabs.Trigger>
                {trace.data.spans && <Tabs.Trigger value="spans">Spans</Tabs.Trigger>}
              </Tabs.List>
              
              {/* Overview Tab */}
              <Tabs.Content value="overview">
                <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
                  <div>
                    <h4 css={{ marginBottom: theme.spacing.sm }}>Trace Information</h4>
                    <div css={{
                      padding: theme.spacing.md,
                      background: theme.colors.backgroundSecondary,
                      borderRadius: theme.general.borderRadiusBase,
                      fontFamily: 'monospace',
                      fontSize: theme.typography.fontSizeSm,
                    }}>
                      <div>Request ID: {trace.info.request_id}</div>
                      <div>Experiment ID: {trace.info.experiment_id}</div>
                      <div>Status: {trace.info.status}</div>
                      {trace.info.status_message && <div>Message: {trace.info.status_message}</div>}
                      <div>Duration: {formatDuration(trace.info.execution_time_ms)}</div>
                      <div>Timestamp: {formatTimestamp(trace.info.timestamp_ms)}</div>
                    </div>
                  </div>
                  
                  {trace.info.tags && Object.keys(trace.info.tags).length > 0 && (
                    <div>
                      <h4 css={{ marginBottom: theme.spacing.sm }}>Tags</h4>
                      <div css={{
                        padding: theme.spacing.md,
                        background: theme.colors.backgroundSecondary,
                        borderRadius: theme.general.borderRadiusBase,
                      }}>
                        {Object.entries(trace.info.tags).map(([key, value]) => (
                          <div key={key} css={{ 
                            fontSize: theme.typography.fontSizeSm,
                            marginBottom: theme.spacing.xs,
                          }}>
                            <span css={{ fontWeight: 500 }}>{key}:</span> {value}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Tabs.Content>
              
              {/* Request Tab */}
              <Tabs.Content value="request">
                <div css={{
                  padding: theme.spacing.md,
                  background: theme.colors.backgroundSecondary,
                  borderRadius: theme.general.borderRadiusBase,
                  fontFamily: 'monospace',
                  fontSize: theme.typography.fontSizeSm,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: '500px',
                  overflow: 'auto',
                }}>
                  {trace.data.request ? (
                    typeof trace.data.request === 'string' 
                      ? trace.data.request 
                      : JSON.stringify(trace.data.request, null, 2)
                  ) : (
                    <span css={{ color: theme.colors.textSecondary }}>No request data</span>
                  )}
                </div>
              </Tabs.Content>
              
              {/* Response Tab */}
              <Tabs.Content value="response">
                <div css={{
                  padding: theme.spacing.md,
                  background: theme.colors.backgroundSecondary,
                  borderRadius: theme.general.borderRadiusBase,
                  fontFamily: 'monospace',
                  fontSize: theme.typography.fontSizeSm,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: '500px',
                  overflow: 'auto',
                }}>
                  {trace.data.response ? (
                    typeof trace.data.response === 'string'
                      ? trace.data.response
                      : JSON.stringify(trace.data.response, null, 2)
                  ) : (
                    <span css={{ color: theme.colors.textSecondary }}>No response data</span>
                  )}
                </div>
              </Tabs.Content>
              
              {/* Spans Tab */}
              {trace.data.spans && (
                <Tabs.Content value="spans">
                  <div css={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.sm }}>
                    {trace.data.spans.map((span) => (
                      <div
                        key={span.span_id}
                        css={{
                          padding: theme.spacing.md,
                          background: theme.colors.backgroundSecondary,
                          borderRadius: theme.general.borderRadiusBase,
                        }}
                      >
                        <div css={{ 
                          fontWeight: 500,
                          marginBottom: theme.spacing.xs,
                        }}>
                          {span.name}
                        </div>
                        <div css={{ 
                          fontSize: theme.typography.fontSizeSm,
                          color: theme.colors.textSecondary,
                        }}>
                          <div>Span ID: {span.span_id}</div>
                          {span.parent_id && <div>Parent: {span.parent_id}</div>}
                          <div>Duration: {formatDuration((span.end_time_ns - span.start_time_ns) / 1000000)}</div>
                          <div>Status: {span.status_code}</div>
                          {span.status_message && <div>Message: {span.status_message}</div>}
                        </div>
                        
                        {span.attributes && Object.keys(span.attributes).length > 0 && (
                          <details css={{ marginTop: theme.spacing.sm }}>
                            <summary css={{ 
                              cursor: 'pointer',
                              fontSize: theme.typography.fontSizeSm,
                            }}>
                              Attributes ({Object.keys(span.attributes).length})
                            </summary>
                            <div css={{
                              marginTop: theme.spacing.xs,
                              padding: theme.spacing.sm,
                              background: theme.colors.backgroundPrimary,
                              borderRadius: theme.general.borderRadiusBase,
                              fontSize: theme.typography.fontSizeSm,
                              fontFamily: 'monospace',
                            }}>
                              {JSON.stringify(span.attributes, null, 2)}
                            </div>
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                </Tabs.Content>
              )}
            </Tabs.Root>
          </>
        )}
      </div>
    </Modal>
  );
};