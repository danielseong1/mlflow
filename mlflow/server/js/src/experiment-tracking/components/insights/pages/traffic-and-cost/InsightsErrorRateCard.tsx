/**
 * MLflow Trace Insights - Error Rate Card Component
 * 
 * Uses React Query hooks for data fetching with MANDATORY correlations
 */

import React from 'react';
import { useDesignSystemTheme } from '@databricks/design-system';
import { useTraceErrors, useErrorCorrelations } from '../../hooks/useInsightsApi';
import { useInsightsChartTimeRange } from '../../hooks/useInsightsChartTimeRange';
import { useTimeBucket } from '../../hooks/useAutomaticTimeBucket';
import { InsightsCard } from '../../components/InsightsCard';
import { TrendsLineChart } from '../../components/TrendsLineChart';
import { TrendsCorrelationsChart } from '../../components/TrendsCorrelationsChart';
import { TrendsCardSkeleton } from '../../components/TrendsSkeleton';
import { NoDataFoundMessage } from '../../components/NoDataFoundMessage';

interface InsightsErrorRateCardProps {
  experimentId?: string;
}

export const InsightsErrorRateCard = ({ experimentId }: InsightsErrorRateCardProps) => {
  const { theme } = useDesignSystemTheme();
  
  // Get chart time domain from global time range
  const { xDomain } = useInsightsChartTimeRange();
  
  // Get automatic time bucket based on time range duration
  const timeBucket = useTimeBucket();
  
  // Fetch error data using React Query hook
  const { data: errorData, isLoading, error } = useTraceErrors(
    {
      experiment_ids: experimentId ? [experimentId] : [],
      time_bucket: timeBucket,
    },
    { refetchInterval: 30000 } // Auto-refresh every 30 seconds
  );

  // Fetch correlations for error traces
  const { data: correlationsData } = useErrorCorrelations(
    experimentId ? [experimentId] : [],
    { enabled: !!errorData && errorData.summary.error_count > 0 }
  );

  if (isLoading) {
    return <TrendsCardSkeleton />;
  }

  if (error) {
    return (
      <InsightsCard title="Error Rate" error={error}>
        <div style={{ color: theme.colors.textValidationDanger, padding: theme.spacing.lg }}>
          Error loading error rate data
        </div>
      </InsightsCard>
    );
  }

  if (!errorData) {
    return null;
  }

  // Check if there's no data
  const hasData = errorData.summary.total_count > 0;

  // Transform time series data for chart
  // Backend already provides error_rate as percentage (0-100), so divide by 100 for decimal format
  // Server now returns timezone-aligned timestamps, no adjustment needed
  const chartData = errorData.time_series.map(point => ({
    timeBucket: new Date(point.time_bucket),
    value: point.error_rate / 100, // Convert percentage to decimal for .1% format
  }));

  // Transform correlations for display
  const correlations = correlationsData?.data.map(item => ({
    label: `${item.dimension}: ${item.value}`,
    count: item.trace_count,
    npmi: item.npmi_score,
    percentage: item.percentage_of_slice,
    type: 'tag' as const,
  })) || [];

  const getErrorRateColor = (rate: number) => {
    if (rate < 1) return theme.colors.textValidationSuccess;
    if (rate < 5) return theme.colors.yellow400;
    return theme.colors.textValidationDanger;
  };

  return (
    <InsightsCard
      title="Error Rate"
      subtitle={
        hasData ? (
          <div css={{ 
            fontSize: '18px', 
            fontWeight: 300, 
            color: getErrorRateColor(errorData.summary.error_rate),
          }}>
            {errorData.summary.error_rate.toFixed(1)}%
          </div>
        ) : undefined
      }
    >
      {hasData ? (
        <>

      {/* Time Series Chart */}
      <div>
        <TrendsLineChart
          points={chartData}
          yAxisTitle="Error Rate (%)"
          yAxisFormat=".1%"
          title="Error Rate Over Time"
          timeBucket={timeBucket}
          lineColors={[theme.colors.textValidationDanger]}
          height={250}
          xDomain={xDomain}
          yAxisOptions={{
            rangemode: 'tozero', // Always include zero but auto-scale the maximum
          }}
        />
      </div>

      {/* MANDATORY Correlations Section for Errors */}
      {correlations.length > 0 && (
        <div>
          <h4 css={{ 
            margin: `0 0 ${theme.spacing.sm}px 0`,
            fontSize: '14px',
            fontWeight: 600,
            color: theme.colors.textPrimary,
          }}>
            Error Correlations (NPMI)
          </h4>
          <TrendsCorrelationsChart
            title="Error Correlations"
            data={correlations}
            onItemClick={(item) => {
              // TODO: Open trace explorer with filter
            }}
          />
          <div css={{ 
            marginTop: theme.spacing.xs,
            fontSize: '11px',
            color: theme.colors.textSecondary,
          }}>
            Showing top {correlations.length} correlations with error status. 
            Higher NPMI scores indicate stronger correlation with errors.
          </div>
        </div>
      )}
        </>
      ) : (
        <NoDataFoundMessage />
      )}
    </InsightsCard>
  );
};