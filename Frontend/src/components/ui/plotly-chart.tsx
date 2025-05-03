import React from 'react';
import Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';

// Create a Plotly React component
const Plot = createPlotlyComponent(Plotly);

interface PlotlyChartProps {
  data: Array<any>;
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  className?: string;
}

export function PlotlyBarChart({
  data,
  layout = {},
  config = {},
  className,
}: PlotlyChartProps) {
  const defaultLayout: Partial<Plotly.Layout> = {
    autosize: true,
    margin: { l: 50, r: 20, t: 20, b: 50 },
    barmode: 'group',
    hovermode: 'closest',
    ...layout,
  };

  const defaultConfig: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: false,
    ...config,
  };

  return (
    <div className={`h-[300px] w-full ${className || ''}`}>
      <Plot
        data={data}
        layout={defaultLayout}
        config={defaultConfig}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}

export function PlotlyLineChart({
  data,
  layout = {},
  config = {},
  className,
}: PlotlyChartProps) {
  const defaultLayout: Partial<Plotly.Layout> = {
    autosize: true,
    margin: { l: 50, r: 20, t: 20, b: 50 },
    hovermode: 'closest',
    ...layout,
  };

  const defaultConfig: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: false,
    ...config,
  };

  return (
    <div className={`h-[300px] w-full ${className || ''}`}>
      <Plot
        data={data}
        layout={defaultLayout}
        config={defaultConfig}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
} 