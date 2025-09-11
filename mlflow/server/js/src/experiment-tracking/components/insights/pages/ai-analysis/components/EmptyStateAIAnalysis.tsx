/**
 * Empty state component for AI Analysis
 */

import React from 'react';
import { useDesignSystemTheme, Button, SparkleFillIcon } from '@databricks/design-system';

interface EmptyStateAIAnalysisProps {
  type: 'analyses' | 'issues';
}

export const EmptyStateAIAnalysis: React.FC<EmptyStateAIAnalysisProps> = ({ type }) => {
  const { theme } = useDesignSystemTheme();
  
  const title = type === 'analyses' 
    ? 'No analyses found' 
    : 'No issues found';
    
  const description = type === 'analyses'
    ? 'Get started by running an AI analysis on your experiment traces'
    : 'Issues will appear here once an AI analysis discovers and validates them';

  return (
    <div css={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: theme.spacing.lg * 2,
      textAlign: 'center',
      minHeight: '400px',
    }}>
      <div css={{
        width: 64,
        height: 64,
        borderRadius: '50%',
        background: theme.colors.backgroundSecondary,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: theme.spacing.lg,
      }}>
        <SparkleFillIcon color="ai" css={{ 
          fontSize: 32,
        }} />
      </div>
      
      <h3 css={{
        fontSize: theme.typography.fontSizeLg,
        fontWeight: 600,
        color: theme.colors.textPrimary,
        marginBottom: theme.spacing.sm,
      }}>
        {title}
      </h3>
      
      <p css={{
        fontSize: theme.typography.fontSizeBase,
        color: theme.colors.textSecondary,
        marginBottom: theme.spacing.lg,
        maxWidth: '400px',
      }}>
        {description}
      </p>
      
      {type === 'analyses' && (
        <div css={{
          background: theme.colors.backgroundSecondary,
          borderRadius: theme.general.borderRadiusBase,
          padding: theme.spacing.lg,
          maxWidth: '600px',
          textAlign: 'left',
        }}>
          <h4 css={{
            fontSize: theme.typography.fontSizeBase,
            fontWeight: 600,
            marginBottom: theme.spacing.sm,
            color: theme.colors.textPrimary,
          }}>
            Get Started
          </h4>
          <div css={{
            fontFamily: 'monospace',
            fontSize: theme.typography.fontSizeSm,
            background: theme.colors.backgroundPrimary,
            padding: theme.spacing.md,
            borderRadius: theme.general.borderRadiusBase,
            border: `1px solid ${theme.colors.border}`,
            color: theme.colors.textPrimary,
          }}>
            <div>1. Open Claude</div>
            <div>2. Run: <code css={{ 
              background: theme.colors.backgroundSecondary,
              padding: '2px 4px',
              borderRadius: '3px',
            }}>/analyze-experiment</code></div>
            <div>3. Follow the prompts to analyze your traces</div>
          </div>
        </div>
      )}
    </div>
  );
};