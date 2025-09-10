import { useDesignSystemTheme } from '@databricks/design-system';
import { FormattedMessage } from '@databricks/i18n';
import type { Config, Data, Layout } from 'plotly.js';
import React from 'react';

import { LazyPlot } from '../../LazyPlot';
import { TimeBucket } from '../types/insightsTypes';
import { createThemedPlotlyLayout } from '../../runs-charts/components/RunsCharts.common';
import { getPlotlyTickConfig, getPlotlyTickConfigForRange, formatTooltipDate } from '../utils/chartDateFormatting';
import { getChartRenderConfig, shouldShowChart, createEmptyTimeSeriesPoints, adjustTimezoneForTimeBucket, type TimeSeriesPoint } from '../utils/chartUtils';

export interface TrendsLineChartDataPoint {
  timeBucket: Date;
  value: number;
  seriesName?: string;
}

export interface TrendsLineChartProps {
  title?: string;
  yAxisTitle: string;
  yAxisFormat?: string;
  points: TrendsLineChartDataPoint[];
  timeBucket?: TimeBucket;
  lineColors?: string[];
  isLoading?: boolean;
  height?: number;
  xDomain?: [number | undefined, number | undefined];
  yDomain?: [number | undefined, number | undefined];
  leftMargin?: number;
  yAxisOptions?: Partial<Layout['yaxis']>; // Additional y-axis configuration
  connectGaps?: boolean; // Whether to connect lines across missing data points
  showLegend?: boolean; // Whether to show the legend
}

export const TrendsLineChart = ({
  title,
  yAxisTitle,
  yAxisFormat,
  points,
  timeBucket = 'hour',
  lineColors = ['#1f77b4'],
  isLoading = false,
  height = 300,
  xDomain,
  yDomain,
  leftMargin = 60,
  yAxisOptions,
  connectGaps = false,
}: TrendsLineChartProps) => {
  const { theme } = useDesignSystemTheme();

  // Group points by series name if provided
  const seriesData = React.useMemo(() => {
    const grouped = new Map<string, TrendsLineChartDataPoint[]>();
    
    points.forEach(point => {
      const series = point.seriesName || 'default';
      if (!grouped.has(series)) {
        grouped.set(series, []);
      }
      grouped.get(series)!.push(point);
    });

    return Array.from(grouped.entries());
  }, [points]);

  // Get smart tick configuration for x-axis
  const tickConfig = React.useMemo(() => {
    let config;
    // Always use xDomain for tick generation when available - this shows x-axis even with no data
    if (xDomain && xDomain[0] && xDomain[1]) {
      config = getPlotlyTickConfigForRange(xDomain[0], xDomain[1], timeBucket);
    }
    // If no xDomain but have data points, use the data points  
    else if (points.length > 0) {
      config = getPlotlyTickConfig(points, timeBucket);
    }
    // No data and no domain - return empty
    else {
      config = { ticktext: [], tickvals: [], tickangle: 0 };
    }
    
    
    return config;
  }, [points, timeBucket, xDomain]);

  // Create Plotly data traces
  const plotlyData: Data[] = seriesData.map(([seriesName, seriesPoints], index) => {
    return {
      type: 'scatter',
      mode: 'lines+markers',
      x: seriesPoints.map(p => p.timeBucket),
      y: seriesPoints.map(p => p.value),
      name: seriesName === 'default' ? '' : seriesName,
      connectgaps: connectGaps, // Configurable line connection across missing data points
      line: {
        color: lineColors[index] || lineColors[0] || '#1f77b4',
        width: 2,
      },
      marker: {
        size: 6,
        color: lineColors[index] || lineColors[0] || '#1f77b4',
      },
      hovertemplate: seriesPoints.map(p => 
        `<b>${yAxisTitle}</b>: %{y}<br><b>Date</b>: ${formatTooltipDate(p.timeBucket, timeBucket)}<extra></extra>`
      )[0], // Use first point's format as template
    };
  });

  // Create Plotly layout with smart date formatting
  const layout: Partial<Layout> = {
    ...createThemedPlotlyLayout(theme),
    height,
    autosize: true,
    margin: { l: 0, r: 0, t: 0, b: 0 },
    xaxis: {
      gridcolor: theme.colors.borderDecorative,
      tickcolor: theme.colors.textPlaceholder,
      range: xDomain,
      tickmode: 'array',
      ticktext: tickConfig.ticktext,
      tickvals: tickConfig.tickvals,
      tickangle: tickConfig.tickangle,
      automargin: true,
    },
    yaxis: {
      gridcolor: theme.colors.borderDecorative,
      tickcolor: theme.colors.textPlaceholder,
      tickformat: yAxisFormat,
      range: yDomain,
      automargin: true,
      ...yAxisOptions,
    },
    showlegend: seriesData.length > 1 && seriesData[0][0] !== 'default',
  };

  // Plotly config
  const config: Partial<Config> = {
    displayModeBar: false,
    responsive: true,
  };

  return (
    <div
      css={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        position: 'relative',
      }}
    >
      {isLoading ? (
        <div css={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height }}>
          Loading...
        </div>
      ) : points.length === 0 ? (
        <FormattedMessage
          defaultMessage="No data found for this time range"
          description="Description for when there is no data to show."
        />
      ) : (
        <div css={{ width: '100%', position: 'relative' }}>
          <LazyPlot
            key={`${points.length}-${JSON.stringify(yAxisOptions)}-${JSON.stringify(xDomain)}`}
            data={plotlyData}
            layout={layout}
            config={config}
            style={{ width: '100%' }}
            useResizeHandler
          />
        </div>
      )}
    </div>
  );
};