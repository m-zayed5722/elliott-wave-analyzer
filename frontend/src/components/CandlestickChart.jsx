import React from 'react';

const CandlestickChart = ({ data, width, height }) => {
  if (!data || data.length === 0) {
    return <div>No data available</div>;
  }

  const margin = { top: 20, right: 30, bottom: 40, left: 60 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  // Calculate price range
  const minPrice = Math.min(...data.map(d => d.low));
  const maxPrice = Math.max(...data.map(d => d.high));
  const priceRange = maxPrice - minPrice;
  const padding = priceRange * 0.1;

  // Scale functions
  const xScale = (index) => (index / (data.length - 1)) * chartWidth;
  const yScale = (price) => chartHeight - ((price - minPrice + padding) / (priceRange + 2 * padding)) * chartHeight;

  const candleWidth = Math.max(1, chartWidth / data.length * 0.8);

  return (
    <svg width={width} height={height}>
      <g transform={`translate(${margin.left}, ${margin.top})`}>
        {/* Grid lines */}
        <defs>
          <pattern id="grid" width="1" height="1" patternUnits="userSpaceOnUse">
            <path d="M 1 0 L 0 0 0 1" fill="none" stroke="var(--border-color)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width={chartWidth} height={chartHeight} fill="url(#grid)" />

        {/* Candlesticks */}
        {data.map((candle, index) => {
          const x = xScale(index);
          const isGreen = candle.close > candle.open;
          const bodyTop = yScale(Math.max(candle.open, candle.close));
          const bodyBottom = yScale(Math.min(candle.open, candle.close));
          const bodyHeight = Math.max(1, bodyBottom - bodyTop);

          return (
            <g key={index}>
              {/* High-Low wick */}
              <line
                x1={x}
                y1={yScale(candle.high)}
                x2={x}
                y2={yScale(candle.low)}
                stroke={isGreen ? 'var(--accent-green)' : 'var(--accent-red)'}
                strokeWidth={1}
              />
              
              {/* Body */}
              <rect
                x={x - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                fill={isGreen ? 'var(--accent-green)' : 'var(--accent-red)'}
                stroke={isGreen ? 'var(--accent-green)' : 'var(--accent-red)'}
                strokeWidth={1}
              />
            </g>
          );
        })}

        {/* Y-axis */}
        <line
          x1={0}
          y1={0}
          x2={0}
          y2={chartHeight}
          stroke="var(--text-muted)"
          strokeWidth={1}
        />

        {/* X-axis */}
        <line
          x1={0}
          y1={chartHeight}
          x2={chartWidth}
          y2={chartHeight}
          stroke="var(--text-muted)"
          strokeWidth={1}
        />

        {/* Y-axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map(ratio => {
          const price = minPrice + (maxPrice - minPrice) * ratio;
          const y = yScale(price);
          return (
            <g key={ratio}>
              <text
                x={-10}
                y={y + 4}
                textAnchor="end"
                fill="var(--text-muted)"
                fontSize={10}
              >
                {price.toFixed(2)}
              </text>
              <line
                x1={-5}
                y1={y}
                x2={0}
                y2={y}
                stroke="var(--text-muted)"
                strokeWidth={1}
              />
            </g>
          );
        })}
      </g>
    </svg>
  );
};

export default CandlestickChart;