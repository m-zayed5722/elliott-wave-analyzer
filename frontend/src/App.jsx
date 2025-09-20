import React, { useState } from 'react';
import ControlPanel from './components/ControlPanel';
import ChartContainer from './components/ChartContainer';
import { analyzeWaves, getPrices } from './services/api';

function App() {
  const [priceData, setPriceData] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async (params) => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch price data
      const prices = await getPrices(params.ticker, params.timeframe, params.range);
      setPriceData(prices);
      
      // Perform analysis
      const analysisResult = await analyzeWaves({
        ticker: params.ticker,
        timeframe: params.timeframe,
        range: params.range,
        zigzag_pct: params.zigzagPct
      });
      
      setAnalysis(analysisResult);
    } catch (err) {
      setError(err.message || 'An error occurred during analysis');
      console.error('Analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (!analysis) return;
    
    try {
      // Create JSON report
      const report = {
        timestamp: new Date().toISOString(),
        analysis: analysis,
        priceData: priceData.slice(-100) // Last 100 data points
      };
      
      // Download JSON file
      const blob = new Blob([JSON.stringify(report, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `elliott-wave-analysis-${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Elliott Wave Analyzer</h1>
        <p>Educational Elliott Wave pattern analysis tool</p>
      </header>
      
      <main className="main-content">
        <ControlPanel 
          onAnalyze={handleAnalyze}
          loading={loading}
          analysis={analysis}
          onExport={handleExport}
        />
        
        <ChartContainer
          priceData={priceData}
          analysis={analysis}
          loading={loading}
          error={error}
        />
      </main>
      
      <footer className="footer">
        <p>
          <strong>Disclaimer:</strong> This tool is for educational/illustrative analysis only 
          and is not financial advice. Elliott Wave analysis is subjective and should not be 
          used as the sole basis for investment decisions.
        </p>
      </footer>
    </div>
  );
}

export default App;