import React, { useState } from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Scatter
} from 'recharts';
import CandlestickChart from './CandlestickChart';
import { Eye, EyeOff } from 'lucide-react';

const ChartContainer = ({ priceData, analysis, loading, error }) => {
  const [showFib, setShowFib] = useState(true);
  const [showInvalidation, setShowInvalidation] = useState(true);
  const [showPivots, setShowPivots] = useState(true);
  const [activeWaveCount, setActiveWaveCount] = useState('primary');

  if (loading) {
    return (
      <div className="chart-container">
        <div className="loading">
          <div>Loading and analyzing data...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="chart-container">
        <div className="error">
          Error: {error}
        </div>
      </div>
    );
  }

  if (!priceData || priceData.length === 0) {
    return (
      <div className="chart-container">
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          height: '100%',
          color: 'var(--text-muted)'
        }}>
          Enter a stock symbol and click "Analyze Waves" to begin
        </div>
      </div>
    );
  }

  // Prepare chart data
  const chartData = priceData.map((item, index) => ({
    index,
    timestamp: new Date(item.timestamp).toLocaleDateString(),
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume
  }));

  // Get wave labels for active count
  const waveLabels = analysis?.[activeWaveCount]?.labels || [];
  
  // Get Fibonacci levels
  const fibRetracements = analysis?.[activeWaveCount]?.fib_retracements || [];
  const fibExtensions = analysis?.[activeWaveCount]?.fib_extensions || [];
  
  // Get invalidation level
  const invalidationLevel = analysis?.[activeWaveCount]?.invalidation;

  // Get pivots for display
  const pivots = analysis?.pivots || [];

  // Create pivot data for scatter plot
  const pivotData = pivots.map(pivot => {
    const dataPoint = chartData.find(d => d.index === pivot.index);
    return dataPoint ? {
      ...dataPoint,
      pivotPrice: pivot.price,
      pivotDirection: pivot.direction
    } : null;
  }).filter(Boolean);

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div style={{
          backgroundColor: 'var(--bg-tertiary)',
          border: '1px solid var(--border-color)',
          borderRadius: '4px',
          padding: '8px',
          fontSize: '12px'
        }}>
          <p>{`Date: ${data.timestamp}`}</p>
          <p>{`Open: ${data.open?.toFixed(2)}`}</p>
          <p>{`High: ${data.high?.toFixed(2)}`}</p>
          <p>{`Low: ${data.low?.toFixed(2)}`}</p>
          <p>{`Close: ${data.close?.toFixed(2)}`}</p>
          {data.pivotPrice && (
            <p style={{ color: 'var(--accent-yellow)' }}>
              {`Pivot ${data.pivotDirection}: ${data.pivotPrice.toFixed(2)}`}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-container">
      <div className="chart-options">
        <label className="chart-toggle">
          <input
            type="checkbox"
            checked={showFib}
            onChange={(e) => setShowFib(e.target.checked)}
          />
          Show Fibonacci Levels
        </label>
        
        <label className="chart-toggle">
          <input
            type="checkbox"
            checked={showInvalidation}
            onChange={(e) => setShowInvalidation(e.target.checked)}
          />
          Show Invalidation
        </label>

        <label className="chart-toggle">
          <input
            type="checkbox"
            checked={showPivots}
            onChange={(e) => setShowPivots(e.target.checked)}
          />
          Show Pivots
        </label>

        {analysis && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className={`tab-button ${activeWaveCount === 'primary' ? 'active' : ''}`}
              onClick={() => setActiveWaveCount('primary')}
              style={{ padding: '4px 8px', fontSize: '12px' }}
            >
              Primary Count
            </button>
            <button
              className={`tab-button ${activeWaveCount === 'alternate' ? 'active' : ''}`}
              onClick={() => setActiveWaveCount('alternate')}
              style={{ padding: '4px 8px', fontSize: '12px' }}
            >
              Alternate Count
            </button>
          </div>
        )}
      </div>

      <div style={{ height: '500px', width: '100%' }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
            <XAxis 
              dataKey="timestamp"
              stroke="var(--text-muted)"
              fontSize={10}
              interval="preserveStartEnd"
            />
            <YAxis 
              stroke="var(--text-muted)"
              fontSize={12}
              domain={['dataMin - 5', 'dataMax + 5']}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Candlestick representation using Line for simplicity */}
            <Line
              type="monotone"
              dataKey="close"
              stroke="var(--accent-blue)"
              strokeWidth={1.5}
              dot={false}
              name="Close Price"
            />
            
            {/* High/Low lines */}
            <Line
              type="monotone"
              dataKey="high"
              stroke="var(--accent-green)"
              strokeWidth={0.5}
              dot={false}
              name="High"
            />
            <Line
              type="monotone"
              dataKey="low"
              stroke="var(--accent-red)"
              strokeWidth={0.5}
              dot={false}
              name="Low"
            />

            {/* Pivot points */}
            {showPivots && (
              <Scatter
                dataKey="pivotPrice"
                data={pivotData}
                fill="var(--accent-yellow)"
                shape="circle"
              />
            )}

            {/* Fibonacci retracement levels */}
            {showFib && fibRetracements.map((fib, index) => (
              <ReferenceLine
                key={`ret-${index}`}
                y={fib.price}
                stroke="var(--accent-yellow)"
                strokeDasharray="5 5"
                strokeOpacity={0.7}
                label={{
                  value: fib.label,
                  position: 'right',
                  fill: 'var(--accent-yellow)',
                  fontSize: 10
                }}
              />
            ))}

            {/* Fibonacci extension levels */}
            {showFib && fibExtensions.map((fib, index) => (
              <ReferenceLine
                key={`ext-${index}`}
                y={fib.price}
                stroke="var(--accent-green)"
                strokeDasharray="8 4"
                strokeOpacity={0.7}
                label={{
                  value: fib.label,
                  position: 'right',
                  fill: 'var(--accent-green)',
                  fontSize: 10
                }}
              />
            ))}

            {/* Invalidation level */}
            {showInvalidation && invalidationLevel && (
              <ReferenceLine
                y={invalidationLevel.price}
                stroke="var(--accent-red)"
                strokeDasharray="10 2"
                strokeWidth={2}
                label={{
                  value: 'Invalidation',
                  position: 'right',
                  fill: 'var(--accent-red)',
                  fontSize: 12,
                  fontWeight: 'bold'
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Wave labels overlay */}
      {analysis && waveLabels.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '60px',
          left: '60px',
          pointerEvents: 'none'
        }}>
          {waveLabels.map((label, index) => {
            const dataPoint = chartData.find(d => d.index === label.index);
            if (!dataPoint) return null;
            
            // Calculate approximate position (this would need more sophisticated positioning in a real implementation)
            const xPercent = (label.index / (chartData.length - 1)) * 100;
            
            return (
              <div
                key={index}
                style={{
                  position: 'absolute',
                  left: `${xPercent}%`,
                  top: '10px',
                  backgroundColor: 'var(--accent-blue)',
                  color: 'white',
                  padding: '2px 6px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  transform: 'translateX(-50%)',
                  zIndex: 10
                }}
              >
                {label.wave}
              </div>
            );
          })}
        </div>
      )}

      {/* Analysis info */}
      {analysis && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          backgroundColor: 'var(--bg-tertiary)',
          border: '1px solid var(--border-color)',
          borderRadius: '4px',
          fontSize: '14px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span>Pivots Detected: {pivots.length}</span>
            <span>Active Pattern: {activeWaveCount === 'primary' ? 'Primary' : 'Alternate'}</span>
          </div>
          <div>
            Current Analysis: {analysis[activeWaveCount].summary}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChartContainer;