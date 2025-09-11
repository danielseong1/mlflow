/**
 * Trace Preview Component
 * Shows input/output preview for a trace and opens ModelTraceExplorer when clicked
 */

import React, { useState } from 'react';
import { useDesignSystemTheme, ParagraphSkeleton, Modal } from '@databricks/design-system';
import { useExperimentTraceData } from '../../../../traces/hooks/useExperimentTraceData';
import { useExperimentTraceInfo } from '../../../../traces/hooks/useExperimentTraceInfo';
import { ModelTraceExplorer, ModelTraceInfo } from '@databricks/web-shared/model-trace-explorer';

interface TracePreviewProps {
  traceId: string;
  rationale?: string;
}

export const TracePreview: React.FC<TracePreviewProps> = ({ traceId, rationale }) => {
  const { theme } = useDesignSystemTheme();
  const [showExplorer, setShowExplorer] = useState(false);
  
  // Fetch trace info and data
  const { traceInfo, loading: loadingInfo } = useExperimentTraceInfo(traceId);
  const { traceData, loading: loadingData } = useExperimentTraceData(traceId);
  
  // Extract input/output from root span
  const rootSpan = traceData?.spans?.find(span => !(span as any).parent_id);
  const inputs = (rootSpan as any)?.inputs;
  const outputs = (rootSpan as any)?.outputs;
  
  const formatValue = (value: any, maxLength: number = 150): string => {
    if (value === null || value === undefined) return 'null';
    
    let str = '';
    if (typeof value === 'string') {
      str = value;
    } else if (typeof value === 'object') {
      try {
        str = JSON.stringify(value, null, 2);
      } catch {
        str = String(value);
      }
    } else {
      str = String(value);
    }
    
    if (str.length > maxLength) {
      return str.substring(0, maxLength) + '...';
    }
    return str;
  };
  
  const combinedModelTrace = React.useMemo(
    () =>
      traceData && traceInfo
        ? {
            info: traceInfo as ModelTraceInfo,
            data: traceData,
          }
        : undefined,
    [traceData, traceInfo],
  );
  
  if (loadingInfo || loadingData) {
    return (
      <div css={{ padding: theme.spacing.sm }}>
        <ParagraphSkeleton />
      </div>
    );
  }
  
  return (
    <>
      <div
        css={{
          cursor: 'pointer',
          '&:hover': {
            opacity: 0.9,
          },
        }}
        onClick={() => setShowExplorer(true)}
      >
        {rationale && (
          <div css={{ 
            marginBottom: theme.spacing.sm,
            fontSize: theme.typography.fontSizeSm,
            color: theme.colors.textSecondary,
          }}>
            {rationale}
          </div>
        )}
        
        <div css={{
          display: 'flex',
          gap: theme.spacing.md,
          padding: theme.spacing.sm,
          background: theme.colors.backgroundPrimary,
          border: `1px solid ${theme.colors.border}`,
          borderRadius: theme.general.borderRadiusBase,
          fontSize: theme.typography.fontSizeSm,
        }}>
          {/* Input preview */}
          <div css={{ flex: 1 }}>
            <div css={{ 
              fontWeight: 600,
              marginBottom: theme.spacing.xs,
              color: theme.colors.textSecondary,
              textTransform: 'uppercase',
              fontSize: '11px',
            }}>
              Input
            </div>
            <div css={{
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: theme.colors.textPrimary,
              maxHeight: '100px',
              overflow: 'hidden',
            }}>
              {inputs ? formatValue(inputs) : <span css={{ color: theme.colors.textSecondary }}>No input</span>}
            </div>
          </div>
          
          {/* Arrow */}
          <div css={{ 
            display: 'flex', 
            alignItems: 'center',
            color: theme.colors.textSecondary,
          }}>
            →
          </div>
          
          {/* Output preview */}
          <div css={{ flex: 1 }}>
            <div css={{ 
              fontWeight: 600,
              marginBottom: theme.spacing.xs,
              color: theme.colors.textSecondary,
              textTransform: 'uppercase',
              fontSize: '11px',
            }}>
              Output
            </div>
            <div css={{
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: theme.colors.textPrimary,
              maxHeight: '100px',
              overflow: 'hidden',
            }}>
              {outputs ? formatValue(outputs) : <span css={{ color: theme.colors.textSecondary }}>No output</span>}
            </div>
          </div>
        </div>
        
        <div css={{
          marginTop: theme.spacing.xs,
          fontSize: theme.typography.fontSizeSm,
          color: theme.colors.actionDefaultBackgroundDefault,
          textAlign: 'center',
        }}>
          Click to explore trace details →
        </div>
      </div>
      
      {/* Model Trace Explorer Modal */}
      {showExplorer && combinedModelTrace && (
        <Modal
          componentId="trace-explorer-modal"
          visible={showExplorer}
          onCancel={() => setShowExplorer(false)}
          title={`Trace: ${traceId}`}
          footer={null}
        >
          <div css={{ height: '80vh', width: '90vw', maxWidth: '1400px' }}>
            <ModelTraceExplorer modelTrace={combinedModelTrace} />
          </div>
        </Modal>
      )}
    </>
  );
};