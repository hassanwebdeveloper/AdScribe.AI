import React from 'react';
import Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';

// Create a Plotly React component
const Plot = createPlotlyComponent(Plotly);

// Types for the charts
interface PlotlyLineChartProps {
  data: Array<any>;
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  onPlotClick?: (data: any) => void;
}

interface PlotlyBarChartProps {
  data: Array<any>;
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  className?: string;
}

// Line chart implementation using React-Plotly
export const PlotlyLineChart = ({
  data,
  layout = {},
  config = { responsive: true },
  onPlotClick
}: PlotlyLineChartProps) => {
  const defaultLayout: Partial<Plotly.Layout> = {
    autosize: true,
    margin: { l: 50, r: 20, t: 30, b: 50 },
    hovermode: 'closest',
    ...layout,
  };

  const defaultConfig: Partial<Plotly.Config> = {
    displayModeBar: false,
    displaylogo: false,
    responsive: true,
    ...config
  };

  // Handle click events if needed
  const handleClick = (data: any) => {
    if (onPlotClick) {
      onPlotClick(data);
    }
  };

  return (
    <Plot
      data={data}
      layout={defaultLayout}
      config={defaultConfig}
      onClick={handleClick}
      style={{ width: '100%', height: '100%' }}
    />
  );
};

// Bar chart implementation
export const PlotlyBarChart = ({
  data,
  layout = {},
  config = {},
  className,
}: PlotlyBarChartProps) => {
  const defaultLayout: Partial<Plotly.Layout> = {
    autosize: true,
    margin: { l: 50, r: 20, t: 30, b: 50 },
    ...layout,
  };

  return (
    <Plot
      data={data}
      layout={defaultLayout}
      config={{
        displayModeBar: false,
        responsive: true,
        ...config,
      }}
      className={className}
      style={{ width: '100%', height: '100%' }}
    />
  );
}; 