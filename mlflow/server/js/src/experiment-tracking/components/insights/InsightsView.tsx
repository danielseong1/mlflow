/**
 * MLflow Trace Insights - Main View Component
 *
 * Main entry point for insights feature with left sidebar navigation.
 * Matches reference implementation structure.
 */

import React from 'react';
import { useDesignSystemTheme, BarChartIcon, PlusMinusSquareIcon, WrenchIcon, TagIcon, SparkleFillIcon } from '@databricks/design-system';
import { InsightsPageTrafficAndCost } from './TrafficAndCost';
import { InsightsPageQualityMetrics } from './pages/quality-metrics/InsightsPageQualityMetrics';
import { InsightsPageTools } from './pages/tools/InsightsPageTools';
import { InsightsPageTags } from './pages/tags/InsightsPageTags';
import { InsightsPageAIAnalysis } from './pages/ai-analysis/InsightsPageAIAnalysis';
import { InsightsPageBaseProps } from './types/insightsTypes';
import { useInsightsPageMode, type InsightsPageMode } from './hooks/useInsightsPageMode';
import { InsightsTimeConfigProvider } from './hooks/useInsightsTimeContext';
import { InsightsToolbar } from './components/InsightsToolbar';

interface InsightsViewProps extends InsightsPageBaseProps {
  subpage?: string | null;
}

interface NavigationItem {
  id: InsightsPageMode;
  title: string;
  key: string;
  icon: React.ReactElement;
  implemented: boolean;
}

const navigationItems: NavigationItem[] = [
  { id: 'traffic', title: 'Traffic and cost', key: 'traffic-cost', icon: <BarChartIcon />, implemented: true },
  { id: 'quality', title: 'Quality metrics', key: 'quality-metrics', icon: <PlusMinusSquareIcon />, implemented: true },
  { id: 'tools', title: 'Tools', key: 'tools', icon: <WrenchIcon />, implemented: true },
  { id: 'tags', title: 'Tags', key: 'tags', icon: <TagIcon />, implemented: true },
  { id: 'ai-analysis', title: 'AI Analysis', key: 'ai-analysis', icon: <SparkleFillIcon color="ai" />, implemented: true },
];

const InsightsViewImpl: React.FC<InsightsViewProps> = ({ experimentId, subpage }) => {
  const { theme } = useDesignSystemTheme();
  const [activePage, setActivePage] = useInsightsPageMode();

  const renderActivePage = () => {
    switch (activePage) {
      case 'traffic':
        return <InsightsPageTrafficAndCost experimentId={experimentId} />;
      case 'quality':
        return <InsightsPageQualityMetrics experimentId={experimentId} />;
      case 'tools':
        return <InsightsPageTools experimentId={experimentId} />;
      case 'tags':
        return <InsightsPageTags experimentId={experimentId} />;
      case 'ai-analysis':
        return <InsightsPageAIAnalysis experimentId={experimentId} />;
      default:
        return null;
    }
  };

  return (
    <div
      css={{
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: theme.colors.backgroundPrimary,
      }}
    >
      {/* Top Toolbar */}
      <InsightsToolbar />

      {/* Main Content - Sidebar + Main Area */}
      <div
        css={{
          flex: 1,
          display: 'flex',
          flexDirection: 'row',
          overflow: 'hidden',
        }}
      >
        {/* Left Sidebar Navigation */}
        <div
          css={{
            width: '200px',
            borderRight: `1px solid ${theme.colors.border}`,
            background: theme.colors.backgroundPrimary,
            display: 'flex',
            flexDirection: 'column',
            padding: theme.spacing.sm,
          }}
        >
          {/* Navigation Items */}
          <nav css={{ flex: 1 }}>
            {navigationItems.map((item) => (
              <button
                key={item.id}
                css={{
                  width: '100%',
                  padding: `${theme.spacing.sm}px ${theme.spacing.md}px`,
                  border: 'none',
                  background: activePage === item.id ? theme.colors.actionDefaultBackgroundPress : 'transparent',
                  color:
                    activePage === item.id
                      ? theme.colors.textPrimary
                      : item.implemented
                      ? theme.colors.textSecondary
                      : theme.colors.textPlaceholder,
                  borderRadius: theme.general.borderRadiusBase,
                  cursor: item.implemented ? 'pointer' : 'not-allowed',
                  fontSize: theme.typography.fontSizeBase,
                  fontWeight: activePage === item.id ? 600 : 400,
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: theme.spacing.xs,
                  marginBottom: theme.spacing.xs,
                  transition: 'all 0.2s ease',
                  '&:hover': item.implemented
                    ? {
                        background: activePage !== item.id ? theme.colors.actionDefaultBackgroundHover : undefined,
                      }
                    : {},
                }}
                onClick={() => item.implemented && setActivePage(item.id)}
                disabled={!item.implemented}
              >
                {item.icon}
                <span>{item.title}</span>
                {!item.implemented && (
                  <span
                    css={{
                      marginLeft: 'auto',
                      fontSize: theme.typography.fontSizeSm,
                      color: theme.colors.textPlaceholder,
                      fontStyle: 'italic',
                    }}
                  >
                    Soon
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Main Content Area */}
        <div
          css={{
            flex: 1,
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {renderActivePage()}
        </div>
      </div>
    </div>
  );
};

export const InsightsView: React.FC<InsightsViewProps> = (props) => (
  <InsightsTimeConfigProvider>
    <InsightsViewImpl {...props} />
  </InsightsTimeConfigProvider>
);
