import React, { useState } from 'react';
import { Download, TrendingUp } from 'lucide-react';

const ControlPanel = ({ onAnalyze, loading, analysis, onExport }) => {
  const [ticker, setTicker] = useState('AAPL');
  const [timeframe, setTimeframe] = useState('daily');
  const [range, setRange] = useState('5y');
  const [zigzagPct, setZigzagPct] = useState(4.0);
  const [activeTab, setActiveTab] = useState('primary');

  const handleSubmit = (e) => {
    e.preventDefault();
    onAnalyze({
      ticker: ticker.toUpperCase(),
      timeframe,
      range,
      zigzagPct
    });
  };

  const getScoreClass = (score) => {
    if (score >= 70) return 'score-high';
    if (score >= 40) return 'score-medium';
    return 'score-low';
  };

  return (
    <div className="control-panel">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="ticker">Stock Symbol</label>
          <input
            type="text"
            id="ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="e.g., AAPL, TSLA, SPY"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="timeframe">Timeframe</label>
          <select
            id="timeframe"
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
          >
            <option value="daily">Daily</option>
            <option value="4H">4 Hours</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="range">Date Range</label>
          <select
            id="range"
            value={range}
            onChange={(e) => setRange(e.target.value)}
          >
            <option value="1y">1 Year</option>
            <option value="2y">2 Years</option>
            <option value="5y">5 Years</option>
            <option value="10y">10 Years</option>
          </select>
        </div>

        <div className="slider-container">
          <label>ZigZag Threshold: {zigzagPct}%</label>
          <input
            type="range"
            className="slider"
            min="1"
            max="10"
            step="0.5"
            value={zigzagPct}
            onChange={(e) => setZigzagPct(parseFloat(e.target.value))}
          />
          <div className="slider-value">
            {timeframe === 'daily' ? '4% typical for daily' : '2% typical for 4H'}
          </div>
        </div>

        <button
          type="submit"
          className="analyze-button"
          disabled={loading || !ticker.trim()}
        >
          {loading ? (
            'Analyzing...'
          ) : (
            <>
              <TrendingUp size={16} style={{ marginRight: '8px' }} />
              Analyze Waves
            </>
          )}
        </button>
      </form>

      {analysis && (
        <div className="analysis-results">
          <div className="wave-count-tabs">
            <button
              className={`tab-button ${activeTab === 'primary' ? 'active' : ''}`}
              onClick={() => setActiveTab('primary')}
            >
              Primary
            </button>
            <button
              className={`tab-button ${activeTab === 'alternate' ? 'active' : ''}`}
              onClick={() => setActiveTab('alternate')}
            >
              Alternate
            </button>
          </div>

          <div className="wave-count-content">
            {activeTab === 'primary' && (
              <div>
                <div className={`score-display ${getScoreClass(analysis.primary.score)}`}>
                  Score: {analysis.primary.score.toFixed(1)}/100
                </div>
                <div className="summary">
                  {analysis.primary.summary}
                </div>
                <div className="invalidation">
                  <strong>Invalidation:</strong> {analysis.primary.invalidation.reason}
                </div>
              </div>
            )}

            {activeTab === 'alternate' && (
              <div>
                <div className={`score-display ${getScoreClass(analysis.alternate.score)}`}>
                  Score: {analysis.alternate.score.toFixed(1)}/100
                </div>
                <div className="summary">
                  {analysis.alternate.summary}
                </div>
                <div className="invalidation">
                  <strong>Invalidation:</strong> {analysis.alternate.invalidation.reason}
                </div>
              </div>
            )}
          </div>

          <button className="export-button" onClick={onExport}>
            <Download size={16} style={{ marginRight: '8px' }} />
            Export Report
          </button>
        </div>
      )}
    </div>
  );
};

export default ControlPanel;