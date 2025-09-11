/**
 * MLflow Trace Insights - AI Analysis Page
 * 
 * Main container for AI Analysis with secondary navigation between Issues and Runs
 */

import React, { useState } from 'react';
import { useDesignSystemTheme, Tabs } from '@databricks/design-system';
import { useSearchParams } from '../../../../../common/utils/RoutingUtils';
import { IssuesView } from './IssuesView';
import { RunsView } from './RunsView';

interface InsightsPageAIAnalysisProps {
  experimentId?: string;
}

type AIAnalysisSubpage = 'issues' | 'runs';

const AI_ANALYSIS_SUBPAGE_PARAM = 'aiAnalysisSubpage';

export const InsightsPageAIAnalysis: React.FC<InsightsPageAIAnalysisProps> = ({ experimentId }) => {
  const { theme } = useDesignSystemTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Get current subpage from URL params, default to 'issues'
  const currentSubpage = (searchParams.get(AI_ANALYSIS_SUBPAGE_PARAM) as AIAnalysisSubpage) || 'issues';
  
  const handleTabChange = (value: string) => {
    setSearchParams((params) => {
      if (value === 'issues') {
        // Remove param for default value to keep URL clean
        params.delete(AI_ANALYSIS_SUBPAGE_PARAM);
      } else {
        params.set(AI_ANALYSIS_SUBPAGE_PARAM, value);
      }
      return params;
    }, { replace: true });
  };

  return (
    <div css={{ 
      padding: theme.spacing.lg,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Tabs.Root componentId="ai-analysis-tabs" value={currentSubpage} onValueChange={handleTabChange}>
        <Tabs.List css={{ marginBottom: theme.spacing.lg }}>
          <Tabs.Trigger value="issues">Issues</Tabs.Trigger>
          <Tabs.Trigger value="runs">Runs</Tabs.Trigger>
        </Tabs.List>
        
        <Tabs.Content value="issues">
          <IssuesView experimentId={experimentId} />
        </Tabs.Content>
        
        <Tabs.Content value="runs">
          <RunsView experimentId={experimentId} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
};