import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import json
from datetime import datetime, timedelta
import hashlib
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.analysis.zigzag import detect_zigzag, validate_zigzag
    from backend.analysis.waves import analyze_waves, calculate_invalidation_levels  
    from backend.analysis.fib import calculate_fibonacci_levels
except ImportError:
    st.error("❌ Could not import analysis modules. Please ensure the backend directory exists.")
    st.stop()

# Page config
st.set_page_config(
    page_title="Elliott Wave Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #1f77b4;
    }
    .wave-score {
        font-size: 1.2em;
        font-weight: bold;
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'price_data' not in st.session_state:
    st.session_state.price_data = None

# Database setup
DB_PATH = "streamlit_cache.db"

@st.cache_resource
def init_db():
    """Initialize SQLite database for caching"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            cache_key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def generate_cache_key(ticker: str, timeframe: str, range_period: str) -> str:
    """Generate cache key for price data"""
    key_string = f"{ticker}_{timeframe}_{range_period}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cached_data(cache_key: str):
    """Get cached price data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if data exists and is not older than 6 hours
    cursor.execute("""
        SELECT data FROM price_cache 
        WHERE cache_key = ? AND 
        datetime(created_at) > datetime('now', '-6 hours')
    """, (cache_key,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return json.loads(result[0])
    return None

def cache_data(cache_key: str, data: dict):
    """Cache price data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO price_cache (cache_key, data)
        VALUES (?, ?)
    """, (cache_key, json.dumps(data)))
    
    conn.commit()
    conn.close()

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_stock_data(ticker: str, timeframe: str, range_period: str):
    """Fetch stock data with caching"""
    cache_key = generate_cache_key(ticker, timeframe, range_period)
    
    # Try to get from cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return pd.DataFrame(cached_data)
    
    try:
        # Map timeframe to yfinance interval and adjust period limits
        interval_map = {
            "daily": "1d",
            "4h": "1h",  # yfinance doesn't have 4h, use 1h
            "1h": "1h"
        }
        
        # Adjust period for intraday data limitations
        if timeframe in ["1h", "4h"]:
            if range_period in ["5y", "10y", "max"]:
                range_period = "2y"  # Limit intraday data to 2 years max
            elif range_period == "2y":
                range_period = "1y"  # Use 1 year for better data quality
        
        interval = interval_map.get(timeframe, "1d")
        
        # Fetch data from Yahoo Finance
        stock = yf.Ticker(ticker)
        hist = stock.history(period=range_period, interval=interval)
        
        if hist.empty:
            st.error(f"No data found for ticker {ticker}")
            return pd.DataFrame()
        
        # Reset index to get timestamp as column
        hist.reset_index(inplace=True)
        
        # Handle different index names based on timeframe
        # Daily data uses 'Date', intraday uses 'Datetime'
        timestamp_column = 'Date' if 'Date' in hist.columns else 'Datetime'
        
        # Map to our schema
        column_mapping = {
            timestamp_column: 'timestamp',
            'Open': 'open', 
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        
        # Rename the columns we need
        hist.rename(columns=column_mapping, inplace=True)
        
        # Keep only the columns we need
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        hist = hist[required_columns]
        
        # Convert timestamp to string for JSON serialization
        hist['timestamp'] = pd.to_datetime(hist['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Cache the data
        cache_data(cache_key, hist.to_dict('records'))
        
        return hist
        
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return pd.DataFrame()

def create_candlestick_chart(df: pd.DataFrame, analysis_results=None):
    """Create interactive candlestick chart with Elliott Wave overlays"""
    
    # Create candlestick chart
    fig = go.Figure()
    
    # Add candlestick
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="Price",
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444'
    ))
    
    if analysis_results:
        # Add ZigZag pivots
        pivots = analysis_results.get('zigzag_pivots', [])
        if pivots:
            pivot_times = [p['timestamp'] for p in pivots]
            pivot_prices = [p['price'] for p in pivots]
            
            # ZigZag line
            fig.add_trace(go.Scatter(
                x=pivot_times,
                y=pivot_prices,
                mode='lines+markers',
                name='ZigZag',
                line=dict(color='cyan', width=2),
                marker=dict(size=6, color='cyan')
            ))
        
        # Add wave labels for primary count
        primary_count = analysis_results.get('primary_count')
        if primary_count and primary_count.get('labels'):
            for i, label in enumerate(primary_count['labels']):
                if i < len(pivots):
                    fig.add_annotation(
                        x=pivots[i]['timestamp'],
                        y=pivots[i]['price'],
                        text=str(label),
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=2,
                        arrowcolor='white',
                        bgcolor='blue',
                        bordercolor='white',
                        borderwidth=2,
                        font=dict(color='white', size=12, family='Arial Black')
                    )
        
        # Add Fibonacci levels
        fib_levels = analysis_results.get('fibonacci_levels', {})
        retracements = fib_levels.get('retracements', [])
        extensions = fib_levels.get('extensions', [])
        
        # Add retracement levels
        for level in retracements:
            fig.add_hline(
                y=level['price'],
                line_dash="dot",
                line_color="yellow",
                annotation_text=f"{level['level']:.1%} ({level['price']:.2f})",
                annotation_position="right"
            )
        
        # Add extension levels
        for level in extensions:
            fig.add_hline(
                y=level['price'],
                line_dash="dash",
                line_color="orange",
                annotation_text=f"Ext {level['level']:.1%} ({level['price']:.2f})",
                annotation_position="right"
            )
        
        # Add invalidation level
        invalidation = analysis_results.get('invalidation_levels', {})
        if invalidation.get('primary_invalidation'):
            fig.add_hline(
                y=invalidation['primary_invalidation'],
                line_dash="solid",
                line_color="red",
                line_width=2,
                annotation_text=f"Invalidation: {invalidation['primary_invalidation']:.2f}",
                annotation_position="left"
            )
    
    # Update layout
    fig.update_layout(
        title="Elliott Wave Analysis Chart",
        yaxis_title="Price ($)",
        xaxis_title="Date",
        template="plotly_dark",
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Remove range slider and selector
    fig.update_layout(xaxis_rangeslider_visible=False)
    
    return fig

def analyze_elliott_waves(df: pd.DataFrame, zigzag_threshold: float):
    """Perform Elliott Wave analysis"""
    
    if df.empty:
        return None
    
    try:
        # Convert timestamp back to datetime for analysis
        df_analysis = df.copy()
        df_analysis['timestamp'] = pd.to_datetime(df_analysis['timestamp'])
        
        # Detect ZigZag pivots
        zigzag_pivots = detect_zigzag(df_analysis, pct_threshold=zigzag_threshold)
        
        if len(zigzag_pivots) < 5:
            st.warning("⚠️ Not enough pivot points detected for Elliott Wave analysis. Try adjusting the ZigZag threshold.")
            return None
        
        # Validate pivots
        validated_pivots = validate_zigzag(df_analysis, zigzag_pivots, min_move_pct=zigzag_threshold/2)
        
        # Analyze waves
        wave_analysis = analyze_waves(df_analysis, validated_pivots)
        
        # Calculate Fibonacci levels
        fibonacci_levels = calculate_fibonacci_levels(df_analysis, validated_pivots)
        
        # Calculate invalidation levels - need to get the primary wave count
        primary_count = wave_analysis.get('primary_count')
        if primary_count:
            invalidation_levels = calculate_invalidation_levels(primary_count, validated_pivots)
        else:
            invalidation_levels = {}
        
        # Format pivots for JSON serialization
        formatted_pivots = []
        for pivot in validated_pivots:
            # Get timestamp from the dataframe using the index
            pivot_timestamp = df_analysis.iloc[pivot['index']]['timestamp']
            formatted_pivots.append({
                'timestamp': pivot_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'price': float(pivot['price']),
                'type': pivot['direction']  # 'high' or 'low'
            })
        
        return {
            'zigzag_pivots': formatted_pivots,
            'primary_count': wave_analysis.get('primary_count', {}).__dict__ if hasattr(wave_analysis.get('primary_count', {}), '__dict__') else wave_analysis.get('primary_count', {}),
            'alternate_count': wave_analysis.get('alternate_count', {}).__dict__ if hasattr(wave_analysis.get('alternate_count', {}), '__dict__') else wave_analysis.get('alternate_count', {}),
            'fibonacci_levels': fibonacci_levels,
            'invalidation_levels': invalidation_levels,
            'summary': generate_analysis_summary(wave_analysis, invalidation_levels)
        }
        
    except Exception as e:
        st.error(f"Error during Elliott Wave analysis: {str(e)}")
        return None

def generate_analysis_summary(wave_analysis, invalidation_levels):
    """Generate human-readable analysis summary"""
    
    primary = wave_analysis.get('primary_count')
    alternate = wave_analysis.get('alternate_count')
    
    summary = "📊 **Elliott Wave Analysis Summary**\n\n"
    
    if primary:
        primary_score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
        primary_pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
        
        summary += f"**Primary Count** (Score: {primary_score:.1f}/100)\n"
        summary += f"- Pattern: {primary_pattern}\n"
        summary += f"- Confidence: {'High' if primary_score > 70 else 'Medium' if primary_score > 50 else 'Low'}\n\n"
    
    if alternate:
        alternate_score = getattr(alternate, 'confidence_score', 0) if hasattr(alternate, 'confidence_score') else alternate.get('confidence_score', 0)
        alternate_pattern = getattr(alternate, 'pattern_type', 'Unknown') if hasattr(alternate, 'pattern_type') else alternate.get('pattern_type', 'Unknown')
        
        summary += f"**Alternate Count** (Score: {alternate_score:.1f}/100)\n"
        summary += f"- Pattern: {alternate_pattern}\n"
        summary += f"- Confidence: {'High' if alternate_score > 70 else 'Medium' if alternate_score > 50 else 'Low'}\n\n"
    
    if invalidation_levels.get('primary_invalidation'):
        summary += f"**Risk Management**\n"
        summary += f"- Primary invalidation: ${invalidation_levels['primary_invalidation']:.2f}\n"
        summary += f"- Watch for breakdown below this level\n\n"
    
    summary += "⚠️ *This analysis is for educational purposes only and should not be considered as financial advice.*"
    
    return summary

# Initialize database
init_db()

# Main app
def main():
    # Header
    st.title("📈 Elliott Wave Analyzer")
    st.markdown("*Automated Elliott Wave pattern detection with Fibonacci analysis*")
    
    # Sidebar controls
    st.sidebar.header("🔧 Analysis Controls")
    
    # Stock ticker input
    ticker = st.sidebar.text_input(
        "Stock Symbol",
        value="AAPL",
        help="Enter a valid stock ticker symbol (e.g., AAPL, GOOGL, TSLA)"
    ).upper()
    
    # Timeframe selection
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        ["daily", "1h", "4h"],
        index=0,
        help="Select the chart timeframe for analysis. Note: Intraday data (1h, 4h) is limited to shorter periods."
    )
    
    # Date range - adjust options based on timeframe
    if timeframe in ["1h", "4h"]:
        range_options = ["5d", "1mo", "3mo", "6mo", "1y"]
        default_range = 2  # 3mo
        help_text = "Intraday data is limited to shorter periods due to API constraints"
    else:
        range_options = ["1y", "2y", "5y", "10y", "max"]
        default_range = 2  # 5y
        help_text = "Select how much historical data to analyze"
    
    range_period = st.sidebar.selectbox(
        "Date Range",
        range_options,
        index=default_range,
        help=help_text
    )
    
    # ZigZag threshold - adjust default based on timeframe
    if timeframe == "daily":
        default_threshold = 4.0
        threshold_help = "Daily charts: 3-6% works well for most stocks"
    else:
        default_threshold = 2.0
        threshold_help = "Intraday charts: 1-3% captures shorter-term swings"
    zigzag_threshold = st.sidebar.slider(
        "ZigZag Threshold (%)",
        min_value=1.0,
        max_value=10.0,
        value=default_threshold,
        step=0.5,
        help=threshold_help
    )
    
    # Analysis button
    analyze_button = st.sidebar.button("🚀 Analyze Waves", type="primary")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if analyze_button or st.session_state.price_data is not None:
            with st.spinner(f"Fetching data for {ticker}..."):
                df = fetch_stock_data(ticker, timeframe, range_period)
                st.session_state.price_data = df
            
            if not df.empty:
                with st.spinner("Performing Elliott Wave analysis..."):
                    analysis = analyze_elliott_waves(df, zigzag_threshold)
                    st.session_state.analysis_results = analysis
                
                # Display chart
                fig = create_candlestick_chart(df, analysis)
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.error("❌ Could not fetch data. Please check the ticker symbol and try again.")
    
    with col2:
        st.subheader("📊 Analysis Results")
        
        if st.session_state.analysis_results:
            analysis = st.session_state.analysis_results
            
            # Primary count metrics
            primary = analysis.get('primary_count', {})
            if primary:
                primary_score = primary.get('confidence_score', 0)
                st.metric(
                    "Primary Count Score",
                    f"{primary_score:.1f}/100",
                    help="Confidence score based on Elliott Wave rules"
                )
                
                pattern_type = primary.get('pattern_type', 'Unknown')
                st.info(f"**Pattern**: {pattern_type}")
            
            # Alternate count metrics  
            alternate = analysis.get('alternate_count', {})
            if alternate:
                alternate_score = alternate.get('confidence_score', 0)
                st.metric(
                    "Alternate Count Score", 
                    f"{alternate_score:.1f}/100"
                )
            
            # Invalidation level
            invalidation = analysis.get('invalidation_levels', {})
            if invalidation.get('primary_invalidation'):
                st.metric(
                    "Invalidation Level",
                    f"${invalidation['primary_invalidation']:.2f}",
                    help="Price level where the primary count becomes invalid"
                )
            
            # Analysis summary
            st.subheader("📝 Summary")
            summary = analysis.get('summary', '')
            st.markdown(summary)
            
            # Export button
            if st.button("💾 Export Analysis"):
                export_data = {
                    'ticker': ticker,
                    'timeframe': timeframe, 
                    'range': range_period,
                    'analysis_date': datetime.now().isoformat(),
                    'analysis': analysis
                }
                
                st.download_button(
                    label="Download JSON Report",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"elliott_wave_analysis_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                
        else:
            st.info("👈 Select a stock symbol and click 'Analyze Waves' to begin")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "*Built with Streamlit • Powered by Yahoo Finance • "
        "[View Source Code](https://github.com/yourusername/elliott-wave-analyzer)*"
    )

if __name__ == "__main__":
    main()