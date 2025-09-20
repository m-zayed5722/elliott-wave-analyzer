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
    .wave-score {
        font-size: 1.2em;
        font-weight: bold;
        color: #1f77b4;
    }
    
    /* Ensure all text is visible */
    .stApp {
        color: #262730;
    }
    
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #262730;
    }
    
    /* Custom card styling for better visibility */
    .price-card {
        background-color: #ffffff;
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Risk management specific styling */
    .risk-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 12px;
        margin: 8px 0;
        transition: all 0.3s ease;
    }
    
    .risk-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .risk-metric {
        text-align: center;
        padding: 10px;
    }
    
    /* Confidence analysis styling */
    .confidence-factor {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 4px solid #007bff;
    }
    
    .confidence-score {
        font-size: 2.5em;
        font-weight: bold;
        text-align: center;
        margin: 20px 0;
    }
    
    /* Wave validation styling */
    .validation-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #007bff;
        transition: all 0.3s ease;
    }
    
    .validation-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .rule-violation {
        border-left-color: #dc3545;
        background-color: #f8d7da;
    }
    
    .rule-confirmation {
        border-left-color: #28a745;
        background-color: #d4edda;
    }
    
    /* Market Sentiment Dashboard styling */
    .sentiment-gauge {
        background: linear-gradient(45deg, #1f1f1f, #2f2f2f);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin: 15px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    
    .sentiment-gauge:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }
    
    .sentiment-component {
        background: #1e1e1e;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .sentiment-component:hover {
        background: #262626;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    .fear-greed-extreme-fear {
        border-left: 5px solid #ff4757;
    }
    
    .fear-greed-fear {
        border-left: 5px solid #ff6b6b;
    }
    
    .fear-greed-neutral {
        border-left: 5px solid #74b9ff;
    }
    
    .fear-greed-greed {
        border-left: 5px solid #00cec9;
    }
    
    .fear-greed-extreme-greed {
        border-left: 5px solid #00b894;
    }
    
    .integration-card {
        background: #1e1e1e;
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        transition: all 0.3s ease;
    }
    
    .integration-card:hover {
        background: #262626;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .confidence-adjusted {
        text-align: center;
        padding: 15px;
        background: #2e2e2e;
        border-radius: 10px;
        margin: 10px 0;
    }
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
        name="📊 Price Candles",
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
                name='🔗 ZigZag Pivots',
                line=dict(color='cyan', width=3),
                marker=dict(size=8, color='cyan', symbol='diamond'),
                hovertemplate="<b>Pivot Point</b><br>" +
                            "Price: $%{y:.2f}<br>" +
                            "Date: %{x}<br>" +
                            "<extra></extra>"
            ))
        
        # Add wave labels for primary count
        primary_count = analysis_results.get('primary_count')
        if primary_count and primary_count.get('labels'):
            for i, label in enumerate(primary_count['labels']):
                if i < len(pivots):
                    fig.add_annotation(
                        x=pivots[i]['timestamp'],
                        y=pivots[i]['price'],
                        text=f"<b>{label}</b>",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=3,
                        arrowcolor='white',
                        bgcolor='#1f77b4',
                        bordercolor='white',
                        borderwidth=2,
                        font=dict(color='white', size=14, family='Arial Black'),
                        opacity=0.9
                    )
        
        # Add Fibonacci levels with enhanced styling
        fib_levels = analysis_results.get('fibonacci_levels', {})
        retracements = fib_levels.get('retracements', [])
        extensions = fib_levels.get('extensions', [])
        
        # Add retracement levels with gradient colors
        fib_colors = {
            0.236: "#FFD700",  # Gold
            0.382: "#FFA500",  # Orange  
            0.500: "#FF6347",  # Tomato
            0.618: "#FF4500",  # OrangeRed
            0.786: "#FF0000"   # Red
        }
        
        for level in retracements:
            level_pct = level['level']
            color = fib_colors.get(level_pct, "#FFFF00")
            
            fig.add_hline(
                y=level['price'],
                line_dash="dot",
                line_color=color,
                line_width=2,
                annotation_text=f"📐 Fib {level_pct:.1%} (${level['price']:.2f})",
                annotation_position="right",
                annotation=dict(
                    bgcolor=color,
                    bordercolor="white",
                    font=dict(color="black", size=10)
                )
            )
        
        # Add extension levels with distinct styling
        for level in extensions:
            level_pct = level['level']
            
            fig.add_hline(
                y=level['price'],
                line_dash="dash",
                line_color="#00CED1",  # Dark Turquoise
                line_width=2,
                annotation_text=f"🎯 Ext {level_pct:.1%} (${level['price']:.2f})",
                annotation_position="right",
                annotation=dict(
                    bgcolor="#00CED1",
                    bordercolor="white", 
                    font=dict(color="black", size=10)
                )
            )
        
        # Add invalidation level with warning styling
        invalidation = analysis_results.get('invalidation_levels', {})
        if invalidation.get('primary_invalidation'):
            fig.add_hline(
                y=invalidation['primary_invalidation'],
                line_dash="solid",
                line_color="#DC143C",  # Crimson
                line_width=4,
                annotation_text=f"⚠️ INVALIDATION: ${invalidation['primary_invalidation']:.2f}",
                annotation_position="left",
                annotation=dict(
                    bgcolor="#DC143C",
                    bordercolor="white",
                    font=dict(color="white", size=12, family="Arial Black")
                )
            )
    
    # Update layout
    fig.update_layout(
        title=dict(
            text="📈 Elliott Wave Analysis - Interactive Chart",
            font=dict(size=20, color='white'),
            x=0.5
        ),
        yaxis_title="Price ($)",
        xaxis_title="Date/Time",
        template="plotly_dark",
        height=700,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(0,0,0,0.8)",
            bordercolor="white",
            borderwidth=1
        ),
        annotations=[
            dict(
                text="Chart Legend:<br>" +
                     "📊 <span style='color:#00ff88'>Green</span>/<span style='color:#ff4444'>Red</span> Candles: Price movement<br>" +
                     "🔗 <span style='color:cyan'>Cyan Line</span>: ZigZag pivot points<br>" +
                     "<span style='color:#1f77b4'>Blue Labels</span>: Elliott Wave numbers (1-5) or letters (A-C)<br>" +
                     "📐 <span style='color:#FFD700'>Dotted Lines</span>: Fibonacci retracements<br>" +
                     "🎯 <span style='color:#00CED1'>Dashed Lines</span>: Fibonacci extensions<br>" +
                     "⚠️ <span style='color:#DC143C'>Red Solid</span>: Wave count invalidation level",
                xref="paper", yref="paper",
                x=1.02, y=0.98,
                showarrow=False,
                font=dict(size=10, color="white"),
                bgcolor="rgba(0,0,0,0.7)",
                bordercolor="white",
                borderwidth=1,
                align="left"
            )
        ]
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
    """Generate comprehensive human-readable analysis summary with detailed insights"""
    
    primary = wave_analysis.get('primary_count')
    alternate = wave_analysis.get('alternate_count')
    
    summary = "# 📊 Elliott Wave Analysis Report\n\n"
    
    # Primary Count Analysis
    if primary:
        primary_score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
        primary_pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
        
        summary += f"## 🎯 Primary Wave Count\n"
        summary += f"**Confidence Score:** {primary_score:.1f}/100\n"
        summary += f"**Pattern Type:** {primary_pattern}\n"
        summary += f"**Assessment:** "
        
        if primary_score > 80:
            summary += "🟢 **Very High Confidence** - Strong adherence to Elliott Wave principles\n"
        elif primary_score > 70:
            summary += "🟡 **High Confidence** - Good wave structure with minor irregularities\n"
        elif primary_score > 50:
            summary += "🟠 **Medium Confidence** - Acceptable count but watch for alternatives\n"
        else:
            summary += "🔴 **Low Confidence** - Weak structure, consider alternate interpretations\n"
        
        summary += f"\n**Pattern Interpretation:**\n"
        if "impulse" in primary_pattern.lower():
            summary += "- This is an **impulse wave** pattern (5 waves in the direction of the main trend)\n"
            summary += "- Waves 1, 3, 5 move in the trend direction; waves 2, 4 are corrections\n"
            summary += "- Wave 3 is typically the strongest and longest wave\n"
            summary += "- After completion, expect a 3-wave correction (A-B-C)\n"
        elif "corrective" in primary_pattern.lower():
            summary += "- This is a **corrective wave** pattern (3 waves against the main trend)\n"
            summary += "- Waves A and C move against the trend; wave B is a counter-correction\n"
            summary += "- After completion, expect resumption of the main trend\n"
        elif "diagonal" in primary_pattern.lower():
            summary += "- This is a **diagonal pattern** (wedge-like structure)\n"
            summary += "- Often appears in wave 5 or wave C positions\n"
            summary += "- Signals potential trend exhaustion and reversal\n"
        
        summary += "\n"
    
    # Alternate Count Analysis
    if alternate and alternate.get('confidence_score', 0) > 30:
        alternate_score = getattr(alternate, 'confidence_score', 0) if hasattr(alternate, 'confidence_score') else alternate.get('confidence_score', 0)
        alternate_pattern = getattr(alternate, 'pattern_type', 'Unknown') if hasattr(alternate, 'pattern_type') else alternate.get('pattern_type', 'Unknown')
        
        summary += f"## 🔄 Alternate Wave Count\n"
        summary += f"**Confidence Score:** {alternate_score:.1f}/100\n"
        summary += f"**Pattern Type:** {alternate_pattern}\n"
        summary += f"**Note:** Consider this count if the primary count gets invalidated\n\n"
    
    # Fibonacci Analysis
    summary += f"## 📐 Fibonacci Analysis\n"
    summary += f"**Retracement Levels** (Support/Resistance):\n"
    summary += f"- 23.6% - Minor support/resistance, shallow correction\n"
    summary += f"- 38.2% - Moderate retracement level, common for wave 2\n"
    summary += f"- 50.0% - Psychological level, not a true Fibonacci ratio\n"
    summary += f"- 61.8% - **Golden ratio**, strong support/resistance\n"
    summary += f"- 78.6% - Deep retracement, often seen in wave 4\n\n"
    
    summary += f"**Extension Levels** (Price targets):\n"
    summary += f"- 127.2% - Minimum target for wave 3 or C\n"
    summary += f"- 161.8% - **Golden extension**, common target for wave 3\n"
    summary += f"- 261.8% - Extended target for strong trending moves\n\n"
    
    # Risk Management
    if invalidation_levels.get('primary_invalidation'):
        summary += f"## ⚠️ Risk Management\n"
        summary += f"**Primary Invalidation Level:** ${invalidation_levels['primary_invalidation']:.2f}\n"
        summary += f"**Risk Assessment:**\n"
        summary += f"- A break below/above this level invalidates the primary wave count\n"
        summary += f"- Use this level for stop-loss placement in trading strategies\n"
        summary += f"- If invalidated, reassess the market structure and consider alternate counts\n\n"
    
    # Trading Implications  
    summary += f"## 📈 Trading Implications\n"
    
    if primary:
        primary_pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
        
        if "impulse" in primary_pattern.lower():
            summary += f"**For Impulse Patterns:**\n"
            summary += f"- Look for buying opportunities on wave 2 and 4 corrections\n"
            summary += f"- Wave 3 typically offers the strongest trending moves\n"
            summary += f"- Wave 5 may show divergence and signal trend exhaustion\n"
        elif "corrective" in primary_pattern.lower():
            summary += f"**For Corrective Patterns:**\n"
            summary += f"- Counter-trend movements, trade with caution\n"
            summary += f"- Look for reversal signals at completion of wave C\n"
            summary += f"- Use Fibonacci levels for entry and exit points\n"
    
    summary += f"- **Fibonacci retracements** act as dynamic support/resistance\n"
    summary += f"- **Extension levels** provide potential profit targets\n"
    summary += f"- Monitor price action at key Fibonacci levels for reversal signals\n\n"
    
    # Market Psychology
    summary += f"## 🧠 Market Psychology Insights\n"
    summary += f"**Elliott Wave reflects crowd psychology:**\n"
    summary += f"- **Wave 1:** Initial move, often unnoticed by the crowd\n"
    summary += f"- **Wave 2:** Sharp correction, pessimism returns\n"
    summary += f"- **Wave 3:** Strongest move, media attention, FOMO kicks in\n"
    summary += f"- **Wave 4:** Sideways/shallow correction, complacency\n"
    summary += f"- **Wave 5:** Final push, extreme optimism, distribution\n\n"
    
    # Key Rules Reminder
    summary += f"## 📋 Key Elliott Wave Rules\n"
    summary += f"1. **Wave 2 cannot retrace more than 100% of wave 1**\n"
    summary += f"2. **Wave 3 is never the shortest among waves 1, 3, and 5**\n"
    summary += f"3. **Wave 4 cannot overlap wave 1 price territory** (except in diagonals)\n"
    summary += f"4. **Alternation:** Waves 2 and 4 tend to be different in structure\n"
    summary += f"5. **Wave 5 often shows momentum divergence**\n\n"
    
    # Disclaimer
    summary += f"---\n"
    summary += f"## ⚖️ Important Disclaimer\n"
    summary += f"📌 **This Elliott Wave analysis is for educational and informational purposes only.**\n"
    summary += f"- Not financial advice - consult a qualified financial advisor\n"
    summary += f"- Elliott Wave analysis is subjective and interpretations can vary\n"
    summary += f"- Always use proper risk management in any trading decisions\n"
    summary += f"- Past performance does not guarantee future results\n"
    summary += f"- Consider multiple timeframes and technical indicators for confirmation\n"
    
    return summary

def generate_chart_summary(wave_analysis, invalidation_levels, ticker, primary_count_labels=None):
    """Generate a concise paragraph summarizing the Elliott Wave analysis for display next to chart"""
    
    primary = wave_analysis.get('primary_count')
    pivots = wave_analysis.get('zigzag_pivots', []) if isinstance(wave_analysis, dict) else []
    
    # Check if we have any analysis data at all
    if not primary and len(pivots) == 0:
        return f"⚠️ **Analysis Status**: No clear Elliott Wave patterns detected for **{ticker}**. This could indicate sideways/consolidating price action or insufficient pivot points. Try adjusting the ZigZag threshold (lower for more sensitivity, higher for major moves only) or selecting a different timeframe for clearer trend structure."
    
    # If we have pivots but weak wave analysis
    if len(pivots) > 0 and (not primary or getattr(primary, 'confidence_score', 0) < 30):
        # Use same trend logic as price targets for consistency
        trend_direction = determine_wave_trend_direction(pivots)
        pivot_count = len(pivots)
        
        trend_desc = f"**{trend_direction}**" if "trend" in trend_direction else f"**{trend_direction}**"
        return f"📊 **{ticker} Market Structure Analysis**: Detected **{pivot_count} pivot points** showing {trend_desc} market structure. While no definitive Elliott Wave pattern emerges (confidence too low), the price action suggests {'continued momentum' if 'trend' in trend_direction else 'consolidation or complex correction'}. **Recommendation**: Monitor for clearer pattern development or adjust ZigZag sensitivity. Current structure may be in early wave formation or complex corrective phase requiring more price development for proper classification."
    
    # Standard analysis when we have good primary count
    primary_score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
    primary_pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
    
    # Determine current wave position from labels
    current_wave = "unknown"
    if primary_count_labels and len(primary_count_labels) > 0:
        current_wave = str(primary_count_labels[-1])
    elif hasattr(primary, 'labels') and len(primary.labels) > 0:
        current_wave = str(primary.labels[-1].wave) if hasattr(primary.labels[-1], 'wave') else str(primary.labels[-1])
    
    # Build the summary paragraph
    summary = f"**📈 {ticker} Elliott Wave Analysis:** "
    
    # Confidence assessment
    if primary_score > 75:
        confidence_text = "shows a **strong Elliott Wave pattern**"
        emoji = "🟢"
    elif primary_score > 60:
        confidence_text = "displays a **moderate Elliott Wave structure**"
        emoji = "🟡"
    elif primary_score > 40:
        confidence_text = "exhibits a **developing Elliott Wave pattern**"
        emoji = "�"
    else:
        confidence_text = "shows **early-stage wave formation**"
        emoji = "�🔴"
    
    summary += f"The analysis {confidence_text} with {primary_score:.0f}% confidence {emoji}. "
    
    # Add consistent trend context based on actual wave direction
    wave_trend_direction = determine_wave_trend_direction(pivots) if len(pivots) >= 3 else "neutral"
    if "upward" in wave_trend_direction:
        trend_context = "The overall wave structure indicates **bullish momentum** with potential for higher prices. "
    elif "downward" in wave_trend_direction:
        trend_context = "The overall wave structure indicates **bearish pressure** with potential for lower prices. "
    else:
        trend_context = "The wave structure shows **sideways/consolidating** price action without clear directional bias. "
    
    summary += trend_context
    
    # Pattern interpretation with more detail
    if "impulse" in primary_pattern.lower():
        if current_wave in ["1", "3", "5"]:
            wave_context = {
                "1": "the initial impulse wave, often unnoticed by the broader market",
                "3": "the strongest trending wave, typically with high volume and momentum", 
                "5": "the final impulse wave, often showing momentum divergence"
            }
            summary += f"Currently positioned in **Wave {current_wave}** ({wave_context.get(current_wave, 'an impulse wave')}). "
        elif current_wave in ["2", "4"]:
            wave_context = {
                "2": "a corrective pullback after the initial impulse, often retracing 50-78.6%",
                "4": "a sideways or shallow correction, typically alternating with wave 2's structure"
            }
            summary += f"Currently in **Wave {current_wave}** correction ({wave_context.get(current_wave, 'a corrective phase')}). "
        else:
            summary += "The pattern suggests a **5-wave impulse structure** developing in the primary trend direction. "
    elif "corrective" in primary_pattern.lower():
        if current_wave in ["A", "C"]:
            wave_context = {
                "A": "the initial corrective decline, breaking the previous trend",
                "C": "the final corrective wave, often targeting Fibonacci extensions"
            }
            summary += f"Currently in **Wave {current_wave}** ({wave_context.get(current_wave, 'a corrective wave')} against the main trend). "
        elif current_wave == "B":
            summary += f"Currently in **Wave B** counter-correction, providing a temporary bounce that often confuses market participants. "
        else:
            summary += "The pattern indicates a **3-wave correction** running counter to the primary trend. "
    elif "diagonal" in primary_pattern.lower():
        summary += "A **diagonal (wedge) pattern** is forming, typically appearing in final wave positions and signaling potential trend exhaustion. "
    else:
        summary += f"The analysis identifies a **{primary_pattern}** pattern with {len(pivots)} significant pivot points. "
    
    # Add invalidation level context
    invalidation_price = invalidation_levels.get('primary_invalidation')
    if invalidation_price:
        summary += f"**Critical Level**: ${invalidation_price:.2f} - a break of this level would invalidate the current wave count. "
    
    # Enhanced trading context
    if primary_score > 60:  # Only give specific trading advice for higher confidence
        if "impulse" in primary_pattern.lower():
            if current_wave in ["2", "4"]:
                summary += "**Trading Opportunity**: Corrections offer potential entry points for trend continuation - watch for reversal signals at Fibonacci levels."
            elif current_wave == "5":
                summary += "**Trading Caution**: Final wave territory - monitor for completion signals and potential reversal patterns."
            elif current_wave in ["1", "3"]:
                summary += "**Trading Context**: Strong trending phase - align positions with primary direction and use pullbacks for entries."
        elif "corrective" in primary_pattern.lower():
            summary += "**Trading Strategy**: Counter-trend movement - expect eventual reversal, use tight stops, consider contrarian positioning."
    else:
        summary += "**Trading Approach**: Pattern still developing - wait for higher confidence or clearer directional signals before major positioning."
    
    return summary

def determine_overall_trend(pivots):
    """Determine overall market trend from pivot points"""
    if len(pivots) < 3:
        return "insufficient data for trend determination"
    
    # Compare first few and last few pivots to determine overall direction
    start_prices = [p['price'] for p in pivots[:3]]
    end_prices = [p['price'] for p in pivots[-3:]]
    
    start_avg = sum(start_prices) / len(start_prices)
    end_avg = sum(end_prices) / len(end_prices)
    
    if end_avg > start_avg * 1.02:  # 2% threshold
        return "an **upward trending**"
    elif end_avg < start_avg * 0.98:  # 2% threshold
        return "a **downward trending**" 
    else:
        return "a **sideways/consolidating**"

def determine_wave_trend_direction(pivots):
    """Determine wave trend direction consistent with price target calculations"""
    if len(pivots) < 3:
        return "neutral"
    
    # Use the same logic as calculate_price_targets for consistency
    recent_pivots = pivots[-5:] if len(pivots) >= 5 else pivots
    if len(recent_pivots) >= 3:
        wave_1_start = recent_pivots[0]['price']
        wave_1_end = recent_pivots[1]['price'] 
        
        if wave_1_end > wave_1_start:
            return "upward trending"
        elif wave_1_end < wave_1_start:
            return "downward trending"
    
    return "sideways/consolidating"

def calculate_price_targets(analysis_results, current_price):
    """Calculate Elliott Wave price targets based on current analysis"""
    
    if not analysis_results:
        return {}
    
    primary = analysis_results.get('primary_count', {})
    pivots = analysis_results.get('zigzag_pivots', [])
    
    if len(pivots) < 3:
        return {}
    
    targets = {
        'wave_targets': {},
        'fibonacci_targets': {},
        'support_resistance': {}
    }
    
    try:
        # Get recent pivot prices
        recent_pivots = pivots[-5:] if len(pivots) >= 5 else pivots
        pivot_prices = [p['price'] for p in recent_pivots]
        
        # Calculate Wave targets based on Elliott Wave principles
        if len(pivot_prices) >= 3:
            # Assume we have at least Wave 1 and Wave 2
            wave_1_start = pivot_prices[0]
            wave_1_end = pivot_prices[1] 
            wave_2_end = pivot_prices[2] if len(pivot_prices) > 2 else current_price
            
            wave_1_length = abs(wave_1_end - wave_1_start)
            
            # Wave 3 targets (typically 1.618 x Wave 1)
            if wave_1_end > wave_1_start:  # Uptrend
                targets['wave_targets']['wave_3_minimum'] = wave_2_end + wave_1_length
                targets['wave_targets']['wave_3_target'] = wave_2_end + (wave_1_length * 1.618)
                targets['wave_targets']['wave_3_extension'] = wave_2_end + (wave_1_length * 2.618)
                
                # Wave 5 targets (often equal to Wave 1 or 0.618 of Wave 1-3)
                wave_1_to_3_length = abs(targets['wave_targets']['wave_3_target'] - wave_1_start)
                targets['wave_targets']['wave_5_target'] = targets['wave_targets']['wave_3_target'] + wave_1_length
                targets['wave_targets']['wave_5_extension'] = wave_1_start + (wave_1_to_3_length * 1.618)
                
            else:  # Downtrend
                targets['wave_targets']['wave_3_minimum'] = wave_2_end - wave_1_length
                targets['wave_targets']['wave_3_target'] = wave_2_end - (wave_1_length * 1.618)
                targets['wave_targets']['wave_3_extension'] = wave_2_end - (wave_1_length * 2.618)
                
                wave_1_to_3_length = abs(targets['wave_targets']['wave_3_target'] - wave_1_start)
                targets['wave_targets']['wave_5_target'] = targets['wave_targets']['wave_3_target'] - wave_1_length
                targets['wave_targets']['wave_5_extension'] = wave_1_start - (wave_1_to_3_length * 1.618)
        
        # Support and Resistance from recent pivots
        targets['support_resistance']['major_support'] = min(pivot_prices[-3:])
        targets['support_resistance']['major_resistance'] = max(pivot_prices[-3:])
        targets['support_resistance']['immediate_support'] = min(pivot_prices[-2:])
        targets['support_resistance']['immediate_resistance'] = max(pivot_prices[-2:])
        
        # Enhanced Fibonacci targets
        fib_levels = analysis_results.get('fibonacci_levels', {})
        if fib_levels:
            targets['fibonacci_targets'] = fib_levels
            
    except Exception as e:
        st.error(f"Error calculating price targets: {str(e)}")
        
    return targets

def calculate_risk_management(current_price, invalidation_level, price_targets, account_size=10000, risk_percentage=2):
    """Calculate comprehensive risk management metrics for Elliott Wave trades"""
    
    if not invalidation_level or not price_targets:
        return {}
    
    risk_mgmt = {
        'position_sizing': {},
        'stop_loss': {},
        'take_profit': {},
        'risk_reward': {},
        'trade_analysis': {}
    }
    
    try:
        # Calculate risk per trade (account size * risk percentage)
        risk_amount = account_size * (risk_percentage / 100)
        
        # Stop loss calculation based on invalidation level
        stop_loss_distance = abs(current_price - invalidation_level)
        stop_loss_percentage = (stop_loss_distance / current_price) * 100
        
        # Position sizing based on risk amount and stop loss distance
        if stop_loss_distance > 0:
            # For stocks: number of shares = risk amount / stop loss distance
            position_size_shares = int(risk_amount / stop_loss_distance)
            position_value = position_size_shares * current_price
            
            risk_mgmt['position_sizing'] = {
                'shares': position_size_shares,
                'position_value': position_value,
                'risk_amount': risk_amount,
                'risk_percentage': risk_percentage
            }
        
        # Stop loss details
        risk_mgmt['stop_loss'] = {
            'price': invalidation_level,
            'distance': stop_loss_distance,
            'percentage': stop_loss_percentage,
            'description': f"Elliott Wave invalidation level at ${invalidation_level:.2f}"
        }
        
        # Take profit levels from price targets
        take_profits = []
        if 'wave_targets' in price_targets:
            wave_targets = price_targets['wave_targets']
            for target_name, target_price in wave_targets.items():
                if target_price and target_price != current_price:
                    profit_distance = abs(target_price - current_price)
                    profit_percentage = (profit_distance / current_price) * 100
                    
                    # Calculate risk-reward ratio
                    if stop_loss_distance > 0:
                        risk_reward_ratio = profit_distance / stop_loss_distance
                    else:
                        risk_reward_ratio = 0
                    
                    take_profits.append({
                        'target': target_name.replace('_', ' ').title(),
                        'price': target_price,
                        'distance': profit_distance,
                        'percentage': profit_percentage,
                        'risk_reward_ratio': risk_reward_ratio
                    })
        
        risk_mgmt['take_profit'] = take_profits
        
        # Overall risk-reward analysis
        if take_profits:
            best_rr = max(tp['risk_reward_ratio'] for tp in take_profits if tp['risk_reward_ratio'] > 0)
            avg_rr = np.mean([tp['risk_reward_ratio'] for tp in take_profits if tp['risk_reward_ratio'] > 0]) if take_profits else 0
            
            risk_mgmt['risk_reward'] = {
                'best_ratio': best_rr,
                'average_ratio': avg_rr,
                'acceptable': best_rr >= 2.0,  # Professional standard
                'grade': 'A' if best_rr >= 3.0 else 'B' if best_rr >= 2.0 else 'C' if best_rr >= 1.5 else 'D'
            }
        
        # Trade quality analysis
        risk_mgmt['trade_analysis'] = {
            'stop_loss_reasonable': stop_loss_percentage <= 10,  # Stop loss should be reasonable
            'position_size_reasonable': position_value <= account_size * 0.2,  # Max 20% of account per trade
            'risk_appropriate': risk_percentage <= 3,  # Max 3% risk per trade
            'overall_quality': 'Good' if stop_loss_percentage <= 8 and best_rr >= 2.0 else 'Fair' if stop_loss_percentage <= 12 and best_rr >= 1.5 else 'Poor'
        }
        
    except Exception as e:
        st.error(f"Error calculating risk management: {str(e)}")
    
    return risk_mgmt

def display_risk_management(risk_mgmt, ticker):
    """Display comprehensive risk management analysis"""
    
    if not risk_mgmt:
        st.info("💡 Risk management requires price targets and invalidation levels")
        return
    
    st.markdown("### 🛡️ **Risk Management Analysis**")
    
    # Position Sizing Section
    if 'position_sizing' in risk_mgmt and risk_mgmt['position_sizing']:
        ps = risk_mgmt['position_sizing']
        
        st.markdown("#### 📊 Position Sizing")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="price-card" style="background-color: #e8f4fd; border-left: 4px solid #1f77b4;">
                <h4 style="color: #1f77b4; margin-bottom: 10px;">Recommended Shares</h4>
                <h3 style="color: #212529; margin: 0;">{ps['shares']:,}</h3>
                <p style="color: #6c757d; margin: 5px 0 0 0;">shares of {ticker}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="price-card" style="background-color: #f8f9fa; border-left: 4px solid #6c757d;">
                <h4 style="color: #6c757d; margin-bottom: 10px;">Position Value</h4>
                <h3 style="color: #212529; margin: 0;">${ps['position_value']:,.2f}</h3>
                <p style="color: #6c757d; margin: 5px 0 0 0;">total investment</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="price-card" style="background-color: #fff3cd; border-left: 4px solid #ffc107;">
                <h4 style="color: #856404; margin-bottom: 10px;">Risk Amount</h4>
                <h3 style="color: #212529; margin: 0;">${ps['risk_amount']:,.2f}</h3>
                <p style="color: #6c757d; margin: 5px 0 0 0;">max loss ({ps['risk_percentage']}%)</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            quality = risk_mgmt.get('trade_analysis', {}).get('overall_quality', 'Unknown')
            quality_color = {'Good': '#28a745', 'Fair': '#ffc107', 'Poor': '#dc3545'}.get(quality, '#6c757d')
            
            st.markdown(f"""
            <div class="price-card" style="background-color: #f8f9fa; border-left: 4px solid {quality_color};">
                <h4 style="color: {quality_color}; margin-bottom: 10px;">Trade Quality</h4>
                <h3 style="color: #212529; margin: 0;">{quality}</h3>
                <p style="color: #6c757d; margin: 5px 0 0 0;">assessment</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Stop Loss Section
    if 'stop_loss' in risk_mgmt and risk_mgmt['stop_loss']:
        sl = risk_mgmt['stop_loss']
        
        st.markdown("#### 🛑 Stop Loss Strategy")
        st.markdown(f"""
        <div class="price-card" style="background-color: #f8d7da; border: 2px solid #dc3545; border-radius: 8px;">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 1.5em; margin-right: 10px;">🛑</span>
                <div>
                    <h4 style="color: #721c24; margin: 0;">Stop Loss: ${sl['price']:.2f}</h4>
                    <p style="color: #721c24; margin: 0; font-size: 0.9em;">{sl['description']}</p>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span><strong>Distance:</strong> ${sl['distance']:.2f}</span>
                <span><strong>Risk:</strong> {sl['percentage']:.1f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Take Profit Targets
    if 'take_profit' in risk_mgmt and risk_mgmt['take_profit']:
        st.markdown("#### 🎯 Take Profit Targets")
        
        for tp in risk_mgmt['take_profit']:
            rr_color = '#28a745' if tp['risk_reward_ratio'] >= 2.0 else '#ffc107' if tp['risk_reward_ratio'] >= 1.5 else '#dc3545'
            
            st.markdown(f"""
            <div class="price-card" style="background-color: #d1ecf1; border: 2px solid {rr_color}; border-radius: 8px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: between; align-items: center;">
                    <div style="flex: 1;">
                        <h4 style="color: #0c5460; margin: 0 0 5px 0;">{tp['target']}</h4>
                        <p style="color: #0c5460; margin: 0; font-size: 0.9em;">
                            Price: <strong>${tp['price']:.2f}</strong> | 
                            Distance: <strong>${tp['distance']:.2f}</strong> ({tp['percentage']:.1f}%)
                        </p>
                    </div>
                    <div style="text-align: right;">
                        <span style="background: {rr_color}; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold;">
                            R:R {tp['risk_reward_ratio']:.1f}:1
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Risk-Reward Summary
    if 'risk_reward' in risk_mgmt and risk_mgmt['risk_reward']:
        rr = risk_mgmt['risk_reward']
        
        st.markdown("#### ⚖️ Risk-Reward Analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            grade_color = {'A': '#28a745', 'B': '#17a2b8', 'C': '#ffc107', 'D': '#dc3545'}.get(rr['grade'], '#6c757d')
            st.markdown(f"""
            <div class="price-card" style="background-color: #f8f9fa; border-left: 4px solid {grade_color};">
                <h4 style="color: {grade_color}; margin-bottom: 10px;">Trade Grade</h4>
                <h2 style="color: #212529; margin: 0;">{rr['grade']}</h2>
                <p style="color: #6c757d; margin: 5px 0 0 0;">overall rating</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="price-card" style="background-color: #d4edda; border-left: 4px solid #28a745;">
                <h4 style="color: #155724; margin-bottom: 10px;">Best R:R Ratio</h4>
                <h2 style="color: #212529; margin: 0;">{rr['best_ratio']:.1f}:1</h2>
                <p style="color: #6c757d; margin: 5px 0 0 0;">max potential</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            acceptable_color = '#28a745' if rr['acceptable'] else '#dc3545'
            acceptable_text = 'Yes' if rr['acceptable'] else 'No'
            
            st.markdown(f"""
            <div class="price-card" style="background-color: #f8f9fa; border-left: 4px solid {acceptable_color};">
                <h4 style="color: {acceptable_color}; margin-bottom: 10px;">Professional Grade</h4>
                <h2 style="color: #212529; margin: 0;">{acceptable_text}</h2>
                <p style="color: #6c757d; margin: 5px 0 0 0;">≥ 2:1 ratio</p>
            </div>
            """, unsafe_allow_html=True)

def calculate_detailed_confidence_score(analysis_results, pivots, price_data=None):
    """Calculate detailed confidence scoring with breakdown of factors"""
    
    if not analysis_results or not pivots:
        return {}
    
    primary = analysis_results.get('primary_count', {})
    if not primary:
        return {}
    
    confidence_breakdown = {
        'overall_score': 0,
        'factors': {},
        'recommendations': [],
        'strengths': [],
        'weaknesses': []
    }
    
    try:
        # Factor 1: Wave Count Integrity (30% weight)
        wave_integrity_score = 0
        if len(pivots) >= 5:  # Minimum for a complete 5-wave pattern
            wave_integrity_score = min(100, (len(pivots) / 8) * 100)  # Ideal is 8+ pivots
            if len(pivots) >= 8:
                confidence_breakdown['strengths'].append("✅ Complete wave structure with sufficient pivots")
            elif len(pivots) >= 5:
                confidence_breakdown['strengths'].append("✅ Adequate pivot count for analysis")
            else:
                confidence_breakdown['weaknesses'].append("⚠️ Limited pivot points - pattern may be incomplete")
        
        confidence_breakdown['factors']['wave_integrity'] = {
            'score': wave_integrity_score,
            'weight': 30,
            'description': f"Wave structure completeness ({len(pivots)} pivots)"
        }
        
        # Factor 2: Fibonacci Relationships (25% weight)
        fib_score = 0
        fib_levels = analysis_results.get('fibonacci_levels', {})
        if fib_levels:
            # Check for common Fibonacci relationships
            fib_relationships = 0
            
            # Check retracement levels
            if 'retracement' in fib_levels:
                ret_levels = fib_levels['retracement']
                common_rets = [0.382, 0.5, 0.618, 0.786]
                for level_data in ret_levels:
                    if isinstance(level_data, dict) and 'level' in level_data:
                        level = level_data['level']
                        if any(abs(level - common) < 0.05 for common in common_rets):
                            fib_relationships += 1
            
            # Check extension levels  
            if 'extension' in fib_levels:
                ext_levels = fib_levels['extension']
                common_exts = [1.0, 1.272, 1.618, 2.618]
                for level_data in ext_levels:
                    if isinstance(level_data, dict) and 'level' in level_data:
                        level = level_data['level']
                        if any(abs(level - common) < 0.1 for common in common_exts):
                            fib_relationships += 1
            
            fib_score = min(100, fib_relationships * 25)  # Up to 4 relationships
            
            if fib_score >= 75:
                confidence_breakdown['strengths'].append("✅ Strong Fibonacci relationships present")
            elif fib_score >= 50:
                confidence_breakdown['strengths'].append("✅ Good Fibonacci support")
            else:
                confidence_breakdown['weaknesses'].append("⚠️ Limited Fibonacci confirmation")
        else:
            confidence_breakdown['weaknesses'].append("❌ No Fibonacci analysis available")
        
        confidence_breakdown['factors']['fibonacci'] = {
            'score': fib_score,
            'weight': 25,
            'description': "Fibonacci relationship strength"
        }
        
        # Factor 3: Wave Proportions (20% weight)
        proportion_score = 0
        if len(pivots) >= 5:
            # Calculate wave lengths
            wave_lengths = []
            for i in range(len(pivots) - 1):
                length = abs(pivots[i+1]['price'] - pivots[i]['price'])
                wave_lengths.append(length)
            
            if len(wave_lengths) >= 4:
                # Check Elliott Wave rules
                # Wave 3 should not be the shortest
                if len(wave_lengths) >= 3:
                    wave_3_length = wave_lengths[2] if len(wave_lengths) > 2 else 0
                    wave_1_length = wave_lengths[0] if len(wave_lengths) > 0 else 0
                    wave_5_length = wave_lengths[4] if len(wave_lengths) > 4 else 0
                    
                    if wave_3_length > 0:
                        if wave_1_length > 0 and wave_3_length > wave_1_length:
                            proportion_score += 40
                            confidence_breakdown['strengths'].append("✅ Wave 3 longer than Wave 1")
                        else:
                            confidence_breakdown['weaknesses'].append("❌ Wave 3 may be too short")
                        
                        if wave_5_length > 0 and wave_3_length > wave_5_length:
                            proportion_score += 40
                        elif wave_5_length == 0:
                            proportion_score += 20  # Wave 5 not complete yet
                        
                        # Additional points for reasonable proportions
                        if wave_1_length > 0:
                            ratio_3_to_1 = wave_3_length / wave_1_length
                            if 1.2 <= ratio_3_to_1 <= 4.0:  # Reasonable range
                                proportion_score += 20
                                confidence_breakdown['strengths'].append("✅ Good Wave 3/Wave 1 proportion")
        
        confidence_breakdown['factors']['proportions'] = {
            'score': proportion_score,
            'weight': 20,
            'description': "Elliott Wave proportion rules compliance"
        }
        
        # Factor 4: Trend Clarity (15% weight)
        trend_score = 0
        wave_trend = determine_wave_trend_direction(pivots)
        if "trending" in wave_trend:
            if len(pivots) >= 3:
                # Check for clear trend progression
                recent_prices = [p['price'] for p in pivots[-5:]]
                if len(recent_prices) >= 3:
                    if "upward" in wave_trend:
                        if recent_prices[-1] > recent_prices[0]:  # Higher high
                            trend_score = 85
                            confidence_breakdown['strengths'].append("✅ Clear upward trend structure")
                        else:
                            trend_score = 40
                    elif "downward" in wave_trend:
                        if recent_prices[-1] < recent_prices[0]:  # Lower low
                            trend_score = 85
                            confidence_breakdown['strengths'].append("✅ Clear downward trend structure")
                        else:
                            trend_score = 40
        else:
            trend_score = 30
            confidence_breakdown['weaknesses'].append("⚠️ Sideways/unclear trend direction")
        
        confidence_breakdown['factors']['trend_clarity'] = {
            'score': trend_score,
            'weight': 15,
            'description': "Trend direction clarity"
        }
        
        # Factor 5: Pattern Recognition (10% weight)
        pattern_score = 0
        primary_pattern = getattr(primary, 'pattern_type', '') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', '')
        
        if primary_pattern:
            if primary_pattern.lower() in ['impulse', 'motive']:
                pattern_score = 90
                confidence_breakdown['strengths'].append("✅ Clear impulse pattern identified")
            elif primary_pattern.lower() in ['corrective', 'correction']:
                pattern_score = 75
                confidence_breakdown['strengths'].append("✅ Corrective pattern identified")
            elif primary_pattern.lower() == 'diagonal':
                pattern_score = 70
                confidence_breakdown['strengths'].append("✅ Diagonal pattern identified")
            else:
                pattern_score = 50
        else:
            pattern_score = 30
            confidence_breakdown['weaknesses'].append("⚠️ Pattern type unclear")
        
        confidence_breakdown['factors']['pattern'] = {
            'score': pattern_score,
            'weight': 10,
            'description': "Pattern recognition clarity"
        }
        
        # Calculate weighted overall score
        total_weighted_score = 0
        total_weight = 0
        
        for factor, data in confidence_breakdown['factors'].items():
            weighted_contribution = (data['score'] * data['weight']) / 100
            total_weighted_score += weighted_contribution
            total_weight += data['weight']
        
        confidence_breakdown['overall_score'] = min(100, total_weighted_score)
        
        # Generate recommendations based on score
        if confidence_breakdown['overall_score'] >= 80:
            confidence_breakdown['recommendations'].extend([
                "🎯 High-confidence trade setup - consider position sizing",
                "📈 Monitor for entry signals on any pullbacks",
                "⚖️ Use standard risk management (2-3% risk)"
            ])
        elif confidence_breakdown['overall_score'] >= 60:
            confidence_breakdown['recommendations'].extend([
                "✅ Moderate confidence - suitable for trading with caution", 
                "🔍 Wait for additional confirmation signals",
                "⚖️ Consider reduced position sizing (1-2% risk)"
            ])
        elif confidence_breakdown['overall_score'] >= 40:
            confidence_breakdown['recommendations'].extend([
                "⚠️ Low confidence - paper trade or wait for improvement",
                "🔍 Look for additional timeframe confluence",
                "📚 Consider this a learning opportunity"
            ])
        else:
            confidence_breakdown['recommendations'].extend([
                "❌ Very low confidence - avoid trading this setup",
                "📊 Try different timeframes or wait for clearer patterns",
                "🔧 Adjust ZigZag sensitivity for better pattern detection"
            ])
        
    except Exception as e:
        st.error(f"Error calculating confidence score: {str(e)}")
    
    return confidence_breakdown

def display_confidence_analysis(confidence_data):
    """Display detailed confidence analysis breakdown"""
    
    if not confidence_data or 'overall_score' not in confidence_data:
        st.info("💡 Confidence analysis requires completed Elliott Wave analysis")
        return
    
    overall_score = confidence_data['overall_score']
    
    st.markdown("### 🎯 **Wave Confidence Analysis**")
    
    # Overall Score Display
    score_color = '#28a745' if overall_score >= 70 else '#ffc107' if overall_score >= 50 else '#dc3545'
    score_grade = 'High' if overall_score >= 70 else 'Moderate' if overall_score >= 50 else 'Low'
    
    st.markdown(f"""
    <div class="price-card" style="background: linear-gradient(135deg, {score_color}22, {score_color}11); border: 3px solid {score_color}; text-align: center;">
        <h2 style="color: {score_color}; margin-bottom: 10px;">Overall Confidence Score</h2>
        <h1 style="color: #212529; margin: 10px 0; font-size: 3em;">{overall_score:.0f}%</h1>
        <h3 style="color: {score_color}; margin: 0;">{score_grade} Confidence</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Factor Breakdown
    st.markdown("#### 📊 Confidence Factor Breakdown")
    
    if 'factors' in confidence_data:
        for factor_name, factor_data in confidence_data['factors'].items():
            score = factor_data['score']
            weight = factor_data['weight']
            description = factor_data['description']
            
            # Calculate contribution to overall score
            contribution = (score * weight) / 100
            
            # Color coding for factor scores
            factor_color = '#28a745' if score >= 70 else '#ffc107' if score >= 50 else '#dc3545'
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {factor_color}; margin: 5px 0;">
                    <h4 style="color: {factor_color}; margin-bottom: 5px;">{factor_name.replace('_', ' ').title()}</h4>
                    <p style="color: #6c757d; margin: 0; font-size: 0.9em;">{description}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="risk-metric">
                    <strong style="color: {factor_color}; font-size: 1.2em;">{score:.0f}%</strong><br>
                    <small style="color: #6c757d;">Score</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="risk-metric">
                    <strong style="color: #6c757d; font-size: 1.2em;">{weight}%</strong><br>
                    <small style="color: #6c757d;">Weight</small>
                </div>
                """, unsafe_allow_html=True)
    
    # Strengths and Weaknesses
    col1, col2 = st.columns(2)
    
    with col1:
        if confidence_data.get('strengths'):
            st.markdown("#### 💪 **Analysis Strengths**")
            for strength in confidence_data['strengths']:
                st.markdown(f"- {strength}")
    
    with col2:
        if confidence_data.get('weaknesses'):
            st.markdown("#### ⚠️ **Areas for Improvement**")
            for weakness in confidence_data['weaknesses']:
                st.markdown(f"- {weakness}")
    
    # Recommendations
    if confidence_data.get('recommendations'):
        st.markdown("#### 🎯 **Trading Recommendations**")
        for i, rec in enumerate(confidence_data['recommendations'], 1):
            st.markdown(f"{i}. {rec}")

def calculate_technical_indicators(df):
    """Calculate comprehensive technical indicators for confluence analysis"""
    
    if df is None or df.empty or len(df) < 20:
        return {}
    
    indicators = {}
    
    try:
        # RSI (Relative Strength Index)
        def calculate_rsi(prices, window=14):
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        indicators['rsi'] = calculate_rsi(df['close'])
        current_rsi = indicators['rsi'].iloc[-1] if not indicators['rsi'].empty else 50
        
        # MACD (Moving Average Convergence Divergence)
        def calculate_macd(prices, fast=12, slow=26, signal=9):
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line
            return macd_line, signal_line, histogram
        
        macd_line, signal_line, histogram = calculate_macd(df['close'])
        indicators['macd'] = macd_line
        indicators['macd_signal'] = signal_line
        indicators['macd_histogram'] = histogram
        
        # Moving Averages
        indicators['sma_20'] = df['close'].rolling(window=20).mean()
        indicators['sma_50'] = df['close'].rolling(window=50).mean()
        indicators['ema_20'] = df['close'].ewm(span=20).mean()
        indicators['ema_50'] = df['close'].ewm(span=50).mean()
        
        # Volume indicators
        if 'volume' in df.columns:
            indicators['volume_sma'] = df['volume'].rolling(window=20).mean()
            indicators['volume_ratio'] = df['volume'] / indicators['volume_sma']
            
            # Volume-Price Trend (VPT)
            indicators['vpt'] = (df['volume'] * (df['close'].pct_change())).cumsum()
        
        # Bollinger Bands
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        indicators['bb_upper'] = sma_20 + (std_20 * 2)
        indicators['bb_lower'] = sma_20 - (std_20 * 2)
        indicators['bb_middle'] = sma_20
        
        # Stochastic Oscillator
        def calculate_stochastic(df, k_window=14, d_window=3):
            lowest_low = df['low'].rolling(window=k_window).min()
            highest_high = df['high'].rolling(window=k_window).max()
            k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_window).mean()
            return k_percent, d_percent
        
        indicators['stoch_k'], indicators['stoch_d'] = calculate_stochastic(df)
        
    except Exception as e:
        st.error(f"Error calculating technical indicators: {str(e)}")
    
    return indicators

def analyze_indicator_confluence(indicators, current_price, wave_analysis):
    """Analyze confluence between technical indicators and Elliott Wave analysis"""
    
    if not indicators:
        return {}
    
    confluence = {
        'overall_score': 0,
        'bullish_signals': [],
        'bearish_signals': [],
        'neutral_signals': [],
        'indicator_analysis': {},
        'wave_alignment': 'neutral'
    }
    
    try:
        # RSI Analysis
        if 'rsi' in indicators and not indicators['rsi'].empty:
            current_rsi = indicators['rsi'].iloc[-1]
            rsi_analysis = {
                'value': current_rsi,
                'signal': 'neutral',
                'strength': 'moderate'
            }
            
            if current_rsi > 70:
                rsi_analysis['signal'] = 'bearish'
                rsi_analysis['strength'] = 'strong' if current_rsi > 80 else 'moderate'
                confluence['bearish_signals'].append(f"📉 RSI Overbought ({current_rsi:.1f})")
            elif current_rsi < 30:
                rsi_analysis['signal'] = 'bullish'
                rsi_analysis['strength'] = 'strong' if current_rsi < 20 else 'moderate'
                confluence['bullish_signals'].append(f"📈 RSI Oversold ({current_rsi:.1f})")
            else:
                confluence['neutral_signals'].append(f"➖ RSI Neutral ({current_rsi:.1f})")
            
            confluence['indicator_analysis']['rsi'] = rsi_analysis
        
        # MACD Analysis
        if all(key in indicators for key in ['macd', 'macd_signal', 'macd_histogram']):
            current_macd = indicators['macd'].iloc[-1]
            current_signal = indicators['macd_signal'].iloc[-1]
            current_hist = indicators['macd_histogram'].iloc[-1]
            prev_hist = indicators['macd_histogram'].iloc[-2] if len(indicators['macd_histogram']) > 1 else current_hist
            
            macd_analysis = {
                'macd_line': current_macd,
                'signal_line': current_signal,
                'histogram': current_hist,
                'signal': 'neutral',
                'crossover': False
            }
            
            # MACD Line vs Signal Line
            if current_macd > current_signal:
                if current_hist > prev_hist:
                    macd_analysis['signal'] = 'bullish'
                    confluence['bullish_signals'].append("📈 MACD Bullish Momentum")
                else:
                    confluence['neutral_signals'].append("➖ MACD Above Signal (Weakening)")
            else:
                if current_hist < prev_hist:
                    macd_analysis['signal'] = 'bearish'
                    confluence['bearish_signals'].append("📉 MACD Bearish Momentum")
                else:
                    confluence['neutral_signals'].append("➖ MACD Below Signal (Weakening)")
            
            # Check for crossovers
            if len(indicators['macd']) > 1 and len(indicators['macd_signal']) > 1:
                prev_macd = indicators['macd'].iloc[-2]
                prev_signal = indicators['macd_signal'].iloc[-2]
                
                if prev_macd <= prev_signal and current_macd > current_signal:
                    macd_analysis['crossover'] = True
                    confluence['bullish_signals'].append("🔥 MACD Bullish Crossover")
                elif prev_macd >= prev_signal and current_macd < current_signal:
                    macd_analysis['crossover'] = True
                    confluence['bearish_signals'].append("🔥 MACD Bearish Crossover")
            
            confluence['indicator_analysis']['macd'] = macd_analysis
        
        # Moving Average Analysis
        if all(key in indicators for key in ['sma_20', 'sma_50']):
            current_sma20 = indicators['sma_20'].iloc[-1]
            current_sma50 = indicators['sma_50'].iloc[-1]
            
            ma_analysis = {
                'sma_20': current_sma20,
                'sma_50': current_sma50,
                'price_vs_ma20': 'above' if current_price > current_sma20 else 'below',
                'price_vs_ma50': 'above' if current_price > current_sma50 else 'below',
                'ma_trend': 'bullish' if current_sma20 > current_sma50 else 'bearish'
            }
            
            # Price vs Moving Averages
            if current_price > current_sma20 > current_sma50:
                confluence['bullish_signals'].append("📈 Price Above Both MAs (Bullish)")
            elif current_price < current_sma20 < current_sma50:
                confluence['bearish_signals'].append("📉 Price Below Both MAs (Bearish)")
            else:
                confluence['neutral_signals'].append("➖ Mixed Moving Average Signals")
            
            confluence['indicator_analysis']['moving_averages'] = ma_analysis
        
        # Volume Analysis
        if 'volume_ratio' in indicators and not indicators['volume_ratio'].empty:
            current_volume_ratio = indicators['volume_ratio'].iloc[-1]
            
            volume_analysis = {
                'volume_ratio': current_volume_ratio,
                'signal': 'neutral'
            }
            
            if current_volume_ratio > 1.5:
                volume_analysis['signal'] = 'strong_interest'
                confluence['bullish_signals'].append(f"📊 High Volume Confirmation ({current_volume_ratio:.1f}x)")
            elif current_volume_ratio < 0.7:
                volume_analysis['signal'] = 'low_interest'
                confluence['neutral_signals'].append(f"📊 Low Volume ({current_volume_ratio:.1f}x)")
            else:
                confluence['neutral_signals'].append(f"📊 Average Volume ({current_volume_ratio:.1f}x)")
            
            confluence['indicator_analysis']['volume'] = volume_analysis
        
        # Stochastic Analysis
        if all(key in indicators for key in ['stoch_k', 'stoch_d']):
            current_stoch_k = indicators['stoch_k'].iloc[-1]
            current_stoch_d = indicators['stoch_d'].iloc[-1]
            
            stoch_analysis = {
                'k': current_stoch_k,
                'd': current_stoch_d,
                'signal': 'neutral'
            }
            
            if current_stoch_k > 80 and current_stoch_d > 80:
                stoch_analysis['signal'] = 'bearish'
                confluence['bearish_signals'].append(f"📉 Stochastic Overbought ({current_stoch_k:.1f})")
            elif current_stoch_k < 20 and current_stoch_d < 20:
                stoch_analysis['signal'] = 'bullish'
                confluence['bullish_signals'].append(f"📈 Stochastic Oversold ({current_stoch_k:.1f})")
            
            confluence['indicator_analysis']['stochastic'] = stoch_analysis
        
        # Calculate overall confluence score
        bullish_count = len(confluence['bullish_signals'])
        bearish_count = len(confluence['bearish_signals'])
        total_signals = bullish_count + bearish_count + len(confluence['neutral_signals'])
        
        if total_signals > 0:
            confluence['overall_score'] = ((bullish_count - bearish_count) / total_signals) * 100
            
            if confluence['overall_score'] > 30:
                confluence['wave_alignment'] = 'bullish'
            elif confluence['overall_score'] < -30:
                confluence['wave_alignment'] = 'bearish'
            else:
                confluence['wave_alignment'] = 'neutral'
        
        # Wave Analysis Alignment
        if wave_analysis:
            wave_trend = determine_wave_trend_direction(wave_analysis.get('zigzag_pivots', []))
            
            if 'upward' in wave_trend and confluence['wave_alignment'] == 'bullish':
                confluence['bullish_signals'].append("🎯 Elliott Wave & Technical Indicators Aligned (Bullish)")
            elif 'downward' in wave_trend and confluence['wave_alignment'] == 'bearish':
                confluence['bearish_signals'].append("🎯 Elliott Wave & Technical Indicators Aligned (Bearish)")
            elif 'upward' in wave_trend and confluence['wave_alignment'] == 'bearish':
                confluence['neutral_signals'].append("⚠️ Elliott Wave Bullish vs Technical Bearish - Mixed Signals")
            elif 'downward' in wave_trend and confluence['wave_alignment'] == 'bullish':
                confluence['neutral_signals'].append("⚠️ Elliott Wave Bearish vs Technical Bullish - Mixed Signals")
        
    except Exception as e:
        st.error(f"Error analyzing indicator confluence: {str(e)}")
    
    return confluence

def display_technical_indicators(indicators, confluence, current_price):
    """Display technical indicators analysis with confluence"""
    
    if not indicators:
        st.info("💡 Technical indicators require sufficient price data")
        return
    
    st.markdown("### 📊 **Technical Indicator Analysis**")
    
    # Confluence Score
    if confluence and 'overall_score' in confluence:
        score = confluence['overall_score']
        alignment = confluence['wave_alignment']
        
        score_color = '#28a745' if score > 30 else '#dc3545' if score < -30 else '#ffc107'
        alignment_text = alignment.title()
        
        st.markdown(f"""
        <div class="price-card" style="background: linear-gradient(135deg, {score_color}22, {score_color}11); border: 3px solid {score_color}; text-align: center;">
            <h3 style="color: {score_color}; margin-bottom: 10px;">Technical Confluence Score</h3>
            <h2 style="color: #212529; margin: 10px 0;">{score:+.0f}%</h2>
            <h4 style="color: {score_color}; margin: 0;">{alignment_text} Bias</h4>
        </div>
        """, unsafe_allow_html=True)
    
    # Create tabs for different indicator categories
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Momentum", "📊 Trend", "📉 Oscillators", "🔄 Confluence"])
    
    with tab1:
        st.markdown("#### 🚀 Momentum Indicators")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # RSI
            if 'rsi' in indicators and not indicators['rsi'].empty:
                current_rsi = indicators['rsi'].iloc[-1]
                rsi_color = '#dc3545' if current_rsi > 70 else '#28a745' if current_rsi < 30 else '#ffc107'
                rsi_status = 'Overbought' if current_rsi > 70 else 'Oversold' if current_rsi < 30 else 'Neutral'
                
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {rsi_color};">
                    <h4 style="color: {rsi_color}; margin-bottom: 10px;">RSI (14)</h4>
                    <h3 style="color: #212529; margin: 0;">{current_rsi:.1f}</h3>
                    <p style="color: #6c757d; margin: 5px 0 0 0;">{rsi_status}</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Stochastic
            if 'stoch_k' in indicators and not indicators['stoch_k'].empty:
                current_stoch = indicators['stoch_k'].iloc[-1]
                stoch_color = '#dc3545' if current_stoch > 80 else '#28a745' if current_stoch < 20 else '#ffc107'
                stoch_status = 'Overbought' if current_stoch > 80 else 'Oversold' if current_stoch < 20 else 'Neutral'
                
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {stoch_color};">
                    <h4 style="color: {stoch_color}; margin-bottom: 10px;">Stochastic %K</h4>
                    <h3 style="color: #212529; margin: 0;">{current_stoch:.1f}%</h3>
                    <p style="color: #6c757d; margin: 5px 0 0 0;">{stoch_status}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # MACD
        if all(key in indicators for key in ['macd', 'macd_signal']):
            current_macd = indicators['macd'].iloc[-1]
            current_signal = indicators['macd_signal'].iloc[-1]
            macd_color = '#28a745' if current_macd > current_signal else '#dc3545'
            macd_status = 'Bullish' if current_macd > current_signal else 'Bearish'
            
            st.markdown(f"""
            <div class="price-card" style="border-left: 4px solid {macd_color};">
                <h4 style="color: {macd_color}; margin-bottom: 10px;">MACD</h4>
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <strong>MACD:</strong> {current_macd:.4f}<br>
                        <strong>Signal:</strong> {current_signal:.4f}
                    </div>
                    <div style="text-align: right;">
                        <h4 style="color: {macd_color}; margin: 0;">{macd_status}</h4>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with tab2:
        st.markdown("#### 📈 Trend Indicators")
        
        # Moving Averages
        if 'sma_20' in indicators and 'sma_50' in indicators:
            sma20 = indicators['sma_20'].iloc[-1]
            sma50 = indicators['sma_50'].iloc[-1]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                price_vs_sma20_color = '#28a745' if current_price > sma20 else '#dc3545'
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {price_vs_sma20_color};">
                    <h4 style="color: #6c757d; margin-bottom: 10px;">SMA 20</h4>
                    <h3 style="color: #212529; margin: 0;">${sma20:.2f}</h3>
                    <p style="color: {price_vs_sma20_color}; margin: 5px 0 0 0;">
                        {'Above' if current_price > sma20 else 'Below'} Price
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                price_vs_sma50_color = '#28a745' if current_price > sma50 else '#dc3545'
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {price_vs_sma50_color};">
                    <h4 style="color: #6c757d; margin-bottom: 10px;">SMA 50</h4>
                    <h3 style="color: #212529; margin: 0;">${sma50:.2f}</h3>
                    <p style="color: {price_vs_sma50_color}; margin: 5px 0 0 0;">
                        {'Above' if current_price > sma50 else 'Below'} Price
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                ma_trend_color = '#28a745' if sma20 > sma50 else '#dc3545'
                ma_trend = 'Bullish' if sma20 > sma50 else 'Bearish'
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {ma_trend_color};">
                    <h4 style="color: #6c757d; margin-bottom: 10px;">MA Trend</h4>
                    <h3 style="color: {ma_trend_color}; margin: 0;">{ma_trend}</h3>
                    <p style="color: #6c757d; margin: 5px 0 0 0;">SMA 20 vs 50</p>
                </div>
                """, unsafe_allow_html=True)
    
    with tab3:
        st.markdown("#### 📊 Oscillators & Volume")
        
        # Bollinger Bands Position
        if all(key in indicators for key in ['bb_upper', 'bb_lower', 'bb_middle']):
            bb_upper = indicators['bb_upper'].iloc[-1]
            bb_lower = indicators['bb_lower'].iloc[-1]
            bb_middle = indicators['bb_middle'].iloc[-1]
            
            bb_position = 'Upper' if current_price > bb_middle else 'Lower'
            bb_squeeze = (bb_upper - bb_lower) / bb_middle < 0.1
            bb_color = '#dc3545' if current_price > bb_upper else '#28a745' if current_price < bb_lower else '#ffc107'
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {bb_color};">
                    <h4 style="color: #6c757d; margin-bottom: 10px;">Bollinger Position</h4>
                    <h3 style="color: {bb_color}; margin: 0;">{bb_position} Band</h3>
                    <p style="color: #6c757d; margin: 5px 0 0 0;">
                        {'Squeeze' if bb_squeeze else 'Normal'} Width
                    </p>
                </div>
                """, unsafe_allow_html=True)
        
        # Volume Analysis
        if 'volume_ratio' in indicators:
            volume_ratio = indicators['volume_ratio'].iloc[-1]
            volume_color = '#28a745' if volume_ratio > 1.2 else '#ffc107' if volume_ratio > 0.8 else '#dc3545'
            volume_status = 'High' if volume_ratio > 1.2 else 'Normal' if volume_ratio > 0.8 else 'Low'
            
            with col2 if 'col2' in locals() else st.columns(1)[0]:
                st.markdown(f"""
                <div class="price-card" style="border-left: 4px solid {volume_color};">
                    <h4 style="color: #6c757d; margin-bottom: 10px;">Volume</h4>
                    <h3 style="color: {volume_color}; margin: 0;">{volume_ratio:.1f}x</h3>
                    <p style="color: #6c757d; margin: 5px 0 0 0;">{volume_status} vs Average</p>
                </div>
                """, unsafe_allow_html=True)
    
    with tab4:
        st.markdown("#### 🔄 Signal Confluence")
        
        if confluence:
            # Bullish Signals
            if confluence.get('bullish_signals'):
                st.markdown("##### 📈 **Bullish Signals**")
                for signal in confluence['bullish_signals']:
                    st.markdown(f"- {signal}")
            
            # Bearish Signals  
            if confluence.get('bearish_signals'):
                st.markdown("##### 📉 **Bearish Signals**")
                for signal in confluence['bearish_signals']:
                    st.markdown(f"- {signal}")
            
            # Neutral/Mixed Signals
            if confluence.get('neutral_signals'):
                st.markdown("##### ➖ **Neutral/Mixed Signals**")
                for signal in confluence['neutral_signals']:
                    st.markdown(f"- {signal}")

def validate_elliott_wave_rules(pivots, wave_labels=None):
    """Comprehensive Elliott Wave rule validation system"""
    
    if not pivots or len(pivots) < 5:
        return {
            'overall_validity': False,
            'rule_violations': [],
            'rule_confirmations': [],
            'guidelines_check': [],
            'educational_notes': [],
            'validity_score': 0
        }
    
    validation = {
        'overall_validity': True,
        'rule_violations': [],
        'rule_confirmations': [],
        'guidelines_check': [],
        'educational_notes': [],
        'validity_score': 0
    }
    
    try:
        # Extract wave data for analysis
        wave_prices = [pivot['price'] for pivot in pivots]
        wave_times = [pivot.get('timestamp', i) for i, pivot in enumerate(pivots)]
        
        # Assume we're analyzing a 5-wave impulse structure
        if len(wave_prices) >= 5:
            wave_0 = wave_prices[0]  # Start
            wave_1 = wave_prices[1]  # Wave 1 end
            wave_2 = wave_prices[2]  # Wave 2 end
            wave_3 = wave_prices[3]  # Wave 3 end
            wave_4 = wave_prices[4]  # Wave 4 end
            wave_5 = wave_prices[5] if len(wave_prices) > 5 else None  # Wave 5 end
            
            # Calculate wave lengths
            wave_1_length = abs(wave_1 - wave_0)
            wave_2_length = abs(wave_2 - wave_1)
            wave_3_length = abs(wave_3 - wave_2)
            wave_4_length = abs(wave_4 - wave_3)
            wave_5_length = abs(wave_5 - wave_4) if wave_5 else None
            
            # RULE 1: Wave 3 is never the shortest impulse wave
            rule1_valid = True
            if wave_5_length:  # Only check if we have Wave 5
                if wave_3_length < wave_1_length and wave_3_length < wave_5_length:
                    rule1_valid = False
                    validation['rule_violations'].append({
                        'rule': 'Wave 3 Not Shortest',
                        'severity': 'critical',
                        'description': f'Wave 3 ({wave_3_length:.2f}) is shorter than both Wave 1 ({wave_1_length:.2f}) and Wave 5 ({wave_5_length:.2f})',
                        'explanation': 'Elliott Wave Rule: Wave 3 must never be the shortest impulse wave (1, 3, or 5). This is a fundamental rule that, if broken, invalidates the wave count.',
                        'suggestion': 'Reconsider wave labeling or look for alternative wave count. Wave 3 is typically the strongest and longest wave.'
                    })
            elif wave_3_length < wave_1_length:  # Partial check if Wave 5 not complete
                validation['guidelines_check'].append({
                    'guideline': 'Wave 3 Length Concern',
                    'description': f'Wave 3 ({wave_3_length:.2f}) is shorter than Wave 1 ({wave_1_length:.2f})',
                    'note': 'Monitor Wave 5 completion - ensure Wave 3 is not the shortest when pattern completes'
                })
            
            if rule1_valid:
                validation['rule_confirmations'].append({
                    'rule': 'Wave 3 Not Shortest ✅',
                    'description': f'Wave 3 ({wave_3_length:.2f}) is properly longer than other impulse waves'
                })
            
            # RULE 2: Wave 4 cannot overlap Wave 1 territory
            rule2_valid = True
            # Determine trend direction
            is_uptrend = wave_1 > wave_0
            
            if is_uptrend:
                # In uptrend: Wave 4 low cannot go below Wave 1 high
                wave_1_high = max(wave_0, wave_1)
                wave_4_low = min(wave_3, wave_4)
                if wave_4_low < wave_1_high:
                    rule2_valid = False
                    overlap_amount = wave_1_high - wave_4_low
                    validation['rule_violations'].append({
                        'rule': 'Wave 4 Overlap Violation',
                        'severity': 'critical',
                        'description': f'Wave 4 low ({wave_4_low:.2f}) overlaps Wave 1 high ({wave_1_high:.2f}) by {overlap_amount:.2f}',
                        'explanation': 'Elliott Wave Rule: In a 5-wave impulse, Wave 4 cannot enter the price territory of Wave 1. This maintains the impulse wave structure.',
                        'suggestion': 'This suggests the pattern may be a diagonal (wedge) rather than a standard impulse, or the wave count needs revision.'
                    })
            else:
                # In downtrend: Wave 4 high cannot go above Wave 1 low
                wave_1_low = min(wave_0, wave_1)
                wave_4_high = max(wave_3, wave_4)
                if wave_4_high > wave_1_low:
                    rule2_valid = False
                    overlap_amount = wave_4_high - wave_1_low
                    validation['rule_violations'].append({
                        'rule': 'Wave 4 Overlap Violation',
                        'severity': 'critical', 
                        'description': f'Wave 4 high ({wave_4_high:.2f}) overlaps Wave 1 low ({wave_1_low:.2f}) by {overlap_amount:.2f}',
                        'explanation': 'Elliott Wave Rule: In a 5-wave impulse, Wave 4 cannot enter the price territory of Wave 1.',
                        'suggestion': 'Consider diagonal pattern or revise wave count.'
                    })
            
            if rule2_valid:
                validation['rule_confirmations'].append({
                    'rule': 'No Wave 4 Overlap ✅',
                    'description': 'Wave 4 correctly stays out of Wave 1 territory'
                })
            
            # RULE 3: Wave 2 cannot retrace more than 100% of Wave 1
            rule3_valid = True
            wave_2_retracement = abs(wave_2 - wave_1) / wave_1_length if wave_1_length > 0 else 0
            
            if wave_2_retracement > 1.0:
                rule3_valid = False
                validation['rule_violations'].append({
                    'rule': 'Wave 2 Over-Retracement',
                    'severity': 'critical',
                    'description': f'Wave 2 retraces {wave_2_retracement*100:.1f}% of Wave 1 (>100%)',
                    'explanation': 'Elliott Wave Rule: Wave 2 cannot retrace more than 100% of Wave 1, or it would invalidate the impulse pattern.',
                    'suggestion': 'Revise wave count - this may be part of a larger corrective structure.'
                })
            else:
                validation['rule_confirmations'].append({
                    'rule': 'Wave 2 Valid Retracement ✅',
                    'description': f'Wave 2 retraces {wave_2_retracement*100:.1f}% of Wave 1 (acceptable)'
                })
            
            # GUIDELINE: Fibonacci relationships
            fib_relationships = []
            
            # Wave 3 often extends to 1.618 of Wave 1
            if wave_1_length > 0:
                wave_3_ratio = wave_3_length / wave_1_length
                if 1.5 <= wave_3_ratio <= 1.7:
                    fib_relationships.append(f'Wave 3 = {wave_3_ratio:.2f} × Wave 1 (near 1.618 extension)')
                elif 2.5 <= wave_3_ratio <= 2.7:
                    fib_relationships.append(f'Wave 3 = {wave_3_ratio:.2f} × Wave 1 (near 2.618 extension)')
            
            # Wave 5 often equals Wave 1 or relates by Fibonacci
            if wave_5_length and wave_1_length > 0:
                wave_5_ratio = wave_5_length / wave_1_length
                if 0.9 <= wave_5_ratio <= 1.1:
                    fib_relationships.append(f'Wave 5 ≈ Wave 1 (ratio: {wave_5_ratio:.2f})')
                elif 0.6 <= wave_5_ratio <= 0.65:
                    fib_relationships.append(f'Wave 5 = {wave_5_ratio:.2f} × Wave 1 (near 0.618)')
            
            # Wave 2 and 4 retracement guidelines
            if wave_2_retracement > 0:
                if 0.5 <= wave_2_retracement <= 0.65:
                    fib_relationships.append(f'Wave 2 retraces {wave_2_retracement*100:.1f}% (healthy 50-61.8%)')
                elif wave_2_retracement > 0.8:
                    validation['guidelines_check'].append({
                        'guideline': 'Deep Wave 2 Retracement',
                        'description': f'Wave 2 retraces {wave_2_retracement*100:.1f}% (>80% is deep)',
                        'note': 'Deep retracements are valid but suggest strong correction'
                    })
            
            if fib_relationships:
                validation['guidelines_check'].extend([{
                    'guideline': 'Fibonacci Relationships',
                    'description': rel,
                    'note': 'Strong Fibonacci relationships increase pattern validity'
                } for rel in fib_relationships])
            
            # GUIDELINE: Alternation principle
            # Wave 2 and Wave 4 should alternate in form
            wave_2_type = 'sharp' if wave_2_retracement > 0.618 else 'sideways'
            
            if len(wave_times) >= 5:
                wave_2_time = abs(wave_times[2] - wave_times[1]) if len(wave_times) > 2 else 1
                wave_4_time = abs(wave_times[4] - wave_times[3]) if len(wave_times) > 4 else 1
                
                wave_4_retracement = abs(wave_4 - wave_3) / wave_3_length if wave_3_length > 0 else 0
                wave_4_type = 'sharp' if wave_4_retracement > 0.618 else 'sideways'
                
                if wave_2_type != wave_4_type:
                    validation['guidelines_check'].append({
                        'guideline': 'Alternation Principle ✅',
                        'description': f'Wave 2 is {wave_2_type}, Wave 4 is {wave_4_type} (alternating forms)',
                        'note': 'Alternation strengthens the wave count validity'
                    })
                else:
                    validation['guidelines_check'].append({
                        'guideline': 'Alternation Concern',
                        'description': f'Both Wave 2 and Wave 4 appear {wave_2_type}',
                        'note': 'Lack of alternation weakens the pattern (guideline, not rule)'
                    })
            
            # Calculate overall validity score
            critical_violations = len([v for v in validation['rule_violations'] if v.get('severity') == 'critical'])
            confirmations = len(validation['rule_confirmations'])
            guidelines_met = len([g for g in validation['guidelines_check'] if '✅' in g.get('description', '')])
            
            if critical_violations > 0:
                validation['overall_validity'] = False
                validation['validity_score'] = max(0, 30 - (critical_violations * 20))
            else:
                validation['validity_score'] = min(100, 70 + (confirmations * 10) + (guidelines_met * 5))
                validation['overall_validity'] = validation['validity_score'] >= 60
            
            # Educational notes
            validation['educational_notes'] = [
                "🎓 Elliott Wave Rules vs Guidelines: Rules are absolute and cannot be violated. Guidelines are preferences that increase pattern reliability.",
                "📚 The three cardinal rules: (1) Wave 3 never shortest, (2) Wave 4 doesn't overlap Wave 1, (3) Wave 2 doesn't exceed 100% retracement.",
                "🔍 Alternation Principle: Wave 2 and Wave 4 should differ in form - if one is sharp, the other should be sideways/complex.",
                "📊 Fibonacci relationships are common but not required - they add confidence when present.",
                "⚡ Diagonal patterns (wedges) have different rules - Wave 4 can overlap Wave 1 in diagonals."
            ]
        
        else:
            validation['educational_notes'].append("📊 Need at least 5 pivot points to perform comprehensive Elliott Wave rule validation")
            validation['validity_score'] = 20
    
    except Exception as e:
        st.error(f"Error in Elliott Wave validation: {str(e)}")
        validation['overall_validity'] = False
        validation['validity_score'] = 0
    
    return validation

def display_wave_validation(validation_results):
    """Display Elliott Wave rule validation results"""
    
    if not validation_results:
        st.info("💡 Wave validation requires sufficient wave data")
        return
    
    st.markdown("### ⚖️ **Elliott Wave Rule Validation**")
    
    # Overall Validity Score
    validity_score = validation_results.get('validity_score', 0)
    is_valid = validation_results.get('overall_validity', False)
    
    score_color = '#28a745' if validity_score >= 80 else '#ffc107' if validity_score >= 60 else '#dc3545'
    validity_text = 'Valid' if is_valid else 'Invalid'
    
    if validity_score >= 80:
        grade_text = 'Excellent'
        grade_icon = '🏆'
    elif validity_score >= 60:
        grade_text = 'Good'
        grade_icon = '✅'
    elif validity_score >= 40:
        grade_text = 'Fair'  
        grade_icon = '⚠️'
    else:
        grade_text = 'Poor'
        grade_icon = '❌'
    
    st.markdown(f"""
    <div class="price-card" style="background: linear-gradient(135deg, {score_color}22, {score_color}11); border: 3px solid {score_color}; text-align: center;">
        <h3 style="color: {score_color}; margin-bottom: 10px;">Wave Count Validity</h3>
        <h1 style="color: #212529; margin: 10px 0; font-size: 2.5em;">{grade_icon} {validity_score:.0f}%</h1>
        <h4 style="color: {score_color}; margin: 0;">{validity_text} - {grade_text}</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # Rule Violations (Critical Issues)
    if validation_results.get('rule_violations'):
        st.markdown("#### 🚨 **Critical Rule Violations**")
        
        for violation in validation_results['rule_violations']:
            severity_color = '#dc3545' if violation.get('severity') == 'critical' else '#ffc107'
            
            with st.expander(f"❌ {violation['rule']}", expanded=True):
                st.markdown(f"""
                <div class="price-card" style="border: 2px solid {severity_color}; background-color: {severity_color}22;">
                    <h4 style="color: {severity_color}; margin-bottom: 10px;">⚠️ {violation['rule']}</h4>
                    <p style="margin-bottom: 10px;"><strong>Issue:</strong> {violation['description']}</p>
                    <p style="margin-bottom: 10px;"><strong>Explanation:</strong> {violation['explanation']}</p>
                    <p style="margin: 0;"><strong>Suggestion:</strong> {violation['suggestion']}</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Rule Confirmations
    if validation_results.get('rule_confirmations'):
        st.markdown("#### ✅ **Rule Confirmations**")
        
        for confirmation in validation_results['rule_confirmations']:
            st.markdown(f"""
            <div class="price-card" style="border-left: 4px solid #28a745; background-color: #d4edda;">
                <h5 style="color: #155724; margin-bottom: 5px;">{confirmation['rule']}</h5>
                <p style="color: #155724; margin: 0;">{confirmation['description']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Guidelines Check
    if validation_results.get('guidelines_check'):
        st.markdown("#### 📋 **Guidelines Assessment**")
        
        col1, col2 = st.columns(2)
        
        positive_guidelines = [g for g in validation_results['guidelines_check'] if '✅' in g.get('description', '')]
        concerns = [g for g in validation_results['guidelines_check'] if '✅' not in g.get('description', '')]
        
        with col1:
            if positive_guidelines:
                st.markdown("##### 💪 **Strengths**")
                for guideline in positive_guidelines:
                    st.markdown(f"""
                    <div class="price-card" style="border-left: 3px solid #28a745; padding: 10px; margin: 5px 0;">
                        <strong>{guideline['guideline']}</strong><br>
                        <small>{guideline['description']}</small>
                    </div>
                    """, unsafe_allow_html=True)
        
        with col2:
            if concerns:
                st.markdown("##### ⚠️ **Areas of Concern**")
                for concern in concerns:
                    st.markdown(f"""
                    <div class="price-card" style="border-left: 3px solid #ffc107; padding: 10px; margin: 5px 0;">
                        <strong>{concern['guideline']}</strong><br>
                        <small>{concern['description']}</small><br>
                        <em style="color: #6c757d;">{concern.get('note', '')}</em>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Educational Notes
    if validation_results.get('educational_notes'):
        with st.expander("📚 **Educational Notes - Elliott Wave Theory**", expanded=False):
            for note in validation_results['educational_notes']:
                st.markdown(f"- {note}")
            
            st.markdown("---")
            st.markdown("**Additional Resources:**")
            st.markdown("- Elliott Wave Principle by Frost & Prechter (definitive guide)")
            st.markdown("- Elliott Wave rules are universal and apply to all timeframes")
            st.markdown("- Guidelines increase probability but are not absolute requirements")

def create_multi_timeframe_analysis(ticker, timeframes=['daily', '4h', '1h']):
    """Create multi-timeframe Elliott Wave analysis"""
    
    multi_analysis = {}
    
    for tf in timeframes:
        try:
            # Adjust range based on timeframe
            if tf == 'daily':
                range_period = '2y'
                threshold = 4.0
            elif tf == '4h':
                range_period = '6mo'  
                threshold = 2.5
            else:  # 1h
                range_period = '3mo'
                threshold = 1.5
                
            # Fetch data
            df = fetch_stock_data(ticker, tf, range_period)
            
            if not df.empty:
                # Analyze waves
                analysis = analyze_elliott_waves(df, threshold)
                multi_analysis[tf] = {
                    'data': df,
                    'analysis': analysis,
                    'threshold': threshold
                }
            
        except Exception as e:
            st.warning(f"Could not analyze {tf} timeframe: {str(e)}")
            
    return multi_analysis

def display_price_targets(targets, current_price):
    """Display price targets in an organized format with better visibility"""
    
    if not targets:
        st.info("No price targets calculated - need more pivot data")
        return
    
    st.subheader("🎯 Price Targets & Levels")
    
    # Wave Targets - Use HTML cards instead of metrics for better visibility
    wave_targets = targets.get('wave_targets', {})
    if wave_targets:
        st.markdown("**📈 Elliott Wave Price Targets:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'wave_3_target' in wave_targets:
                target = wave_targets['wave_3_target']
                distance = ((target - current_price) / current_price) * 100
                
                # Create custom styled card
                color = "#28a745" if distance > 0 else "#dc3545"
                st.markdown(f"""
                <div style="
                    background-color: #f8f9fa;
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #343a40; margin: 0 0 5px 0; font-size: 16px;">🎯 Wave 3 Target</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${target:.2f}</h3>
                    <p style="color: {color}; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Primary Wave 3 target (1.618x Wave 1)</small>
                </div>
                """, unsafe_allow_html=True)
            
            if 'wave_5_target' in wave_targets:
                target = wave_targets['wave_5_target'] 
                distance = ((target - current_price) / current_price) * 100
                
                color = "#28a745" if distance > 0 else "#dc3545"
                st.markdown(f"""
                <div style="
                    background-color: #f8f9fa;
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #343a40; margin: 0 0 5px 0; font-size: 16px;">🏁 Wave 5 Target</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${target:.2f}</h3>
                    <p style="color: {color}; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Wave 5 target (equality with Wave 1)</small>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if 'wave_3_extension' in wave_targets:
                target = wave_targets['wave_3_extension']
                distance = ((target - current_price) / current_price) * 100
                
                color = "#28a745" if distance > 0 else "#dc3545"
                st.markdown(f"""
                <div style="
                    background-color: #f8f9fa;
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #343a40; margin: 0 0 5px 0; font-size: 16px;">🚀 Wave 3 Extension</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${target:.2f}</h3>
                    <p style="color: {color}; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Extended Wave 3 target (2.618x Wave 1)</small>
                </div>
                """, unsafe_allow_html=True)
                
            if 'wave_5_extension' in wave_targets:
                target = wave_targets['wave_5_extension']
                distance = ((target - current_price) / current_price) * 100
                
                color = "#28a745" if distance > 0 else "#dc3545"
                st.markdown(f"""
                <div style="
                    background-color: #f8f9fa;
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #343a40; margin: 0 0 5px 0; font-size: 16px;">🎯 Wave 5 Extension</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${target:.2f}</h3>
                    <p style="color: {color}; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Extended Wave 5 target</small>
                </div>
                """, unsafe_allow_html=True)
    
    # Support/Resistance with custom styling
    sr_levels = targets.get('support_resistance', {})
    if sr_levels:
        st.markdown("---")
        st.markdown("**🛡️ Support & Resistance Levels:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'major_support' in sr_levels:
                level = sr_levels['major_support']
                distance = ((level - current_price) / current_price) * 100
                
                st.markdown(f"""
                <div style="
                    background-color: #fff3cd;
                    border: 2px solid #856404;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #856404; margin: 0 0 5px 0; font-size: 16px;">🔻 Major Support</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${level:.2f}</h3>
                    <p style="color: #856404; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Strong support level from pivots</small>
                </div>
                """, unsafe_allow_html=True)
                
            if 'immediate_support' in sr_levels:
                level = sr_levels['immediate_support']
                distance = ((level - current_price) / current_price) * 100
                
                st.markdown(f"""
                <div style="
                    background-color: #f8d7da;
                    border: 2px solid #721c24;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #721c24; margin: 0 0 5px 0; font-size: 16px;">📉 Immediate Support</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${level:.2f}</h3>
                    <p style="color: #721c24; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Nearest support level</small>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if 'major_resistance' in sr_levels:
                level = sr_levels['major_resistance']
                distance = ((level - current_price) / current_price) * 100
                
                st.markdown(f"""
                <div style="
                    background-color: #d1ecf1;
                    border: 2px solid #0c5460;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #0c5460; margin: 0 0 5px 0; font-size: 16px;">🔺 Major Resistance</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${level:.2f}</h3>
                    <p style="color: #0c5460; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Strong resistance level from pivots</small>
                </div>
                """, unsafe_allow_html=True)
                
            if 'immediate_resistance' in sr_levels:
                level = sr_levels['immediate_resistance']
                distance = ((level - current_price) / current_price) * 100
                
                st.markdown(f"""
                <div style="
                    background-color: #d4edda;
                    border: 2px solid #155724;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #155724; margin: 0 0 5px 0; font-size: 16px;">📈 Immediate Resistance</h4>
                    <h3 style="color: #212529; margin: 0; font-size: 24px; font-weight: bold;">${level:.2f}</h3>
                    <p style="color: #155724; margin: 5px 0 0 0; font-size: 16px; font-weight: bold;">{distance:+.1f}%</p>
                    <small style="color: #6c757d;">Nearest resistance level</small>
                </div>
                """, unsafe_allow_html=True)

def scan_multiple_stocks(symbols, timeframe='daily', threshold=4.0):
    """Scan multiple stocks for Elliott Wave patterns"""
    
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        try:
            status_text.text(f"Analyzing {symbol}... ({i+1}/{len(symbols)})")
            progress_bar.progress((i + 1) / len(symbols))
            
            # Fetch data
            df = fetch_stock_data(symbol, timeframe, '1y')
            
            if not df.empty:
                # Analyze waves
                analysis = analyze_elliott_waves(df, threshold)
                
                if analysis and analysis.get('primary_count'):
                    primary = analysis.get('primary_count', {})
                    score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
                    pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
                    
                    current_price = df['close'].iloc[-1] if not df.empty else 0
                    
                    # Calculate price targets
                    targets = calculate_price_targets(analysis, current_price)
                    
                    results.append({
                        'symbol': symbol,
                        'confidence': score,
                        'pattern': pattern,
                        'current_price': current_price,
                        'analysis': analysis,
                        'targets': targets
                    })
                    
        except Exception as e:
            st.warning(f"Could not analyze {symbol}: {str(e)}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    return results

def display_scanner_results(scan_results):
    """Display pattern scanner results in organized format"""
    
    if not scan_results:
        st.warning("No patterns found in scanned symbols")
        return
    
    # Sort by confidence score
    scan_results.sort(key=lambda x: x['confidence'], reverse=True)
    
    st.subheader(f"🔍 Pattern Scanner Results ({len(scan_results)} symbols analyzed)")
    
    # Create filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_confidence = st.slider("Minimum Confidence %", 0, 100, 50)
    with col2:
        pattern_filter = st.selectbox("Pattern Type", ['All', 'impulse', 'corrective', 'diagonal'])
    with col3:
        max_results = st.number_input("Max Results", 1, 50, 10)
    
    # Filter results
    filtered_results = []
    for result in scan_results:
        if result['confidence'] >= min_confidence:
            if pattern_filter == 'All' or pattern_filter.lower() in result['pattern'].lower():
                filtered_results.append(result)
    
    # Limit results
    filtered_results = filtered_results[:max_results]
    
    if not filtered_results:
        st.info("No symbols match the current filters")
        return
    
    # Display results in expandable cards
    for result in filtered_results:
        confidence = result['confidence']
        symbol = result['symbol']
        pattern = result['pattern']
        price = result['current_price']
        
        # Determine emoji based on confidence
        if confidence > 75:
            emoji = "🟢"
        elif confidence > 60:
            emoji = "🟡"
        else:
            emoji = "🔴"
        
        with st.expander(f"{emoji} {symbol} - {pattern.title()} ({confidence:.1f}%) - ${price:.2f}"):
            
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.metric("Confidence Score", f"{confidence:.1f}%")
                st.metric("Current Price", f"${price:.2f}")
            
            with col_b:
                st.metric("Pattern Type", pattern.title())
                
                # Show key levels if available
                targets = result.get('targets', {})
                wave_targets = targets.get('wave_targets', {})
                if 'wave_3_target' in wave_targets:
                    target = wave_targets['wave_3_target']
                    upside = ((target - price) / price) * 100
                    st.metric("Wave 3 Target", f"${target:.2f}", f"+{upside:.1f}%")
            
            with col_c:
                # Support/Resistance
                sr_levels = targets.get('support_resistance', {})
                if 'major_support' in sr_levels:
                    support = sr_levels['major_support']
                    downside = ((support - price) / price) * 100
                    st.metric("Major Support", f"${support:.2f}", f"{downside:.1f}%")
                
                if 'major_resistance' in sr_levels:
                    resistance = sr_levels['major_resistance'] 
                    upside = ((resistance - price) / price) * 100
                    st.metric("Major Resistance", f"${resistance:.2f}", f"+{upside:.1f}%")
            
            # Analysis summary for this symbol
            analysis = result.get('analysis', {})
            if analysis:
                invalidation = analysis.get('invalidation_levels', {})
                summary = generate_chart_summary(
                    {'primary_count': analysis.get('primary_count'), 'zigzag_pivots': analysis.get('zigzag_pivots', [])},
                    invalidation,
                    symbol,
                    []
                )
                st.markdown("**Analysis Summary:**")
                st.markdown(summary)# Initialize database
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
        "📈 Stock Symbol",
        value="AAPL",
        help="Enter a valid stock ticker symbol (e.g., AAPL, GOOGL, TSLA, SPY, BTC-USD)"
    ).upper()
    
    # Timeframe selection with detailed explanations
    st.sidebar.markdown("**⏰ Chart Timeframe**")
    timeframe = st.sidebar.selectbox(
        "Select Analysis Timeframe",
        ["daily", "1h", "4h"],
        index=0,
        help="Daily: Long-term trends, weeks/months. 1h/4h: Short-term, intraday patterns"
    )
    
    # Add timeframe-specific guidance
    if timeframe == "daily":
        st.sidebar.info("📅 **Daily Charts**: Best for swing trading and long-term analysis")
    elif timeframe == "1h":
        st.sidebar.info("⚡ **1-Hour Charts**: Good for day trading and short-term patterns")
    else:  # 4h
        st.sidebar.info("🕐 **4-Hour Charts**: Medium-term analysis, position trading")
    
    # Date range - adjust options based on timeframe
    if timeframe in ["1h", "4h"]:
        range_options = ["5d", "1mo", "3mo", "6mo", "1y"]
        default_range = 2  # 3mo
        help_text = "⚠️ Intraday data is limited to shorter periods due to API constraints"
    else:
        range_options = ["1y", "2y", "5y", "10y", "max"]
        default_range = 2  # 5y
        help_text = "📊 More data = better long-term pattern recognition"
    
    range_period = st.sidebar.selectbox(
        "📅 Historical Data Range",
        range_options,
        index=default_range,
        help=help_text
    )
    
    # ZigZag threshold with detailed explanation
    st.sidebar.markdown("**🔗 ZigZag Configuration**")
    if timeframe == "daily":
        default_threshold = 4.0
        threshold_help = "Daily: 3-6% filters major swings. Lower = more pivots, Higher = fewer pivots"
    else:
        default_threshold = 2.0
        threshold_help = "Intraday: 1-3% captures short-term swings. Adjust based on volatility"
    
    zigzag_threshold = st.sidebar.slider(
        "Minimum Price Move (%)",
        min_value=1.0,
        max_value=10.0,
        value=default_threshold,
        step=0.5,
        help=threshold_help
    )
    
    # Add threshold guidance
    if zigzag_threshold < 2.0:
        st.sidebar.warning("🔍 Very sensitive - may create noise")
    elif zigzag_threshold > 7.0:
        st.sidebar.warning("🎯 Very selective - may miss important moves")
    else:
        st.sidebar.success("✅ Good balance for most situations")
    
    # Analysis button
    analyze_button = st.sidebar.button(
        "🚀 Analyze Elliott Waves", 
        type="primary",
        help="Click to fetch data and perform Elliott Wave analysis"
    )
    
    # Sidebar information panel
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📚 Elliott Wave Basics")
    
    with st.sidebar.expander("🌊 What are Elliott Waves?"):
        st.markdown("""
        **Elliott Wave Theory** identifies recurring patterns in market movements:
        
        **5-Wave Impulse Pattern:**
        - Waves 1, 3, 5: Move with the trend
        - Waves 2, 4: Counter-trend corrections
        
        **3-Wave Corrective Pattern:**
        - Waves A, C: Move against the trend  
        - Wave B: Counter-correction
        
        **Key Rules:**
        1. Wave 2 < 100% of Wave 1
        2. Wave 3 ≠ shortest of 1,3,5  
        3. Wave 4 doesn't overlap Wave 1
        """)
    
    with st.sidebar.expander("📐 Fibonacci Levels"):
        st.markdown("""
        **Retracement Levels** (Support/Resistance):
        - 23.6%: Shallow correction
        - 38.2%: Common Wave 2 target
        - 50.0%: Psychological level
        - 61.8%: **Golden Ratio** - strongest
        - 78.6%: Deep correction (Wave 4)
        
        **Extension Levels** (Price Targets):
        - 127.2%: Minimum Wave 3/C target
        - 161.8%: **Golden Extension** 
        - 261.8%: Extended target
        """)
    
    with st.sidebar.expander("⚠️ Risk Management"):
        st.markdown("""
        **Invalidation Levels:**
        - Critical price levels that void the wave count
        - Use for stop-loss placement
        - If broken, reassess the pattern
        
        **Trading Tips:**
        - Never risk more than you can afford
        - Use position sizing
        - Combine with other technical analysis
        - Practice on paper before real money
        """)
    
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 **Tip**: Start with major indices (SPY, QQQ) to learn patterns before individual stocks")
    
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
                st.plotly_chart(fig, width="stretch")
                
                # Add concise analysis summary next to the chart
                if analysis:
                    primary_labels = analysis.get('primary_count', {}).get('labels', [])
                    invalidation_levels = analysis.get('invalidation_levels', {})
                    
                    # Prepare analysis data with pivots for better context
                    analysis_with_pivots = {
                        'primary_count': analysis.get('primary_count'),
                        'zigzag_pivots': analysis.get('zigzag_pivots', [])
                    }
                    
                    chart_summary = generate_chart_summary(
                        analysis_with_pivots, 
                        invalidation_levels, 
                        ticker,
                        primary_labels
                    )
                    
                    st.markdown("---")
                    st.markdown("### 🎯 Chart Analysis Summary")
                    st.markdown(chart_summary)
                    
                    # Add debug info in an expander (temporary)
                    with st.expander("🔍 Debug Info (Development)", expanded=False):
                        st.write("**Analysis Results:**")
                        primary_count = analysis.get('primary_count')
                        if primary_count:
                            st.json({
                                'primary_confidence': getattr(primary_count, 'confidence_score', 'N/A'),
                                'primary_pattern': getattr(primary_count, 'pattern_type', 'N/A'),
                                'primary_labels': getattr(primary_count, 'labels', 'N/A')
                            })
                        else:
                            st.write("No primary count found")
                        
                        st.write(f"**Pivot count:** {len(analysis.get('zigzag_pivots', []))}")
                        st.write(f"**Invalidation levels:** {analysis.get('invalidation_levels', {})}")
                    
                    st.markdown("---")
                
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
                    help="Confidence score based on Elliott Wave rules compliance"
                )
                
                pattern_type = primary.get('pattern_type', 'Unknown')
                st.info(f"**🎯 Pattern**: {pattern_type}")
            
            # Alternate count metrics  
            alternate = analysis.get('alternate_count', {})
            if alternate:
                alternate_score = alternate.get('confidence_score', 0)
                st.metric(
                    "Alternate Count Score", 
                    f"{alternate_score:.1f}/100",
                    help="Secondary interpretation confidence"
                )
            
            # Invalidation level
            invalidation = analysis.get('invalidation_levels', {})
            if invalidation.get('primary_invalidation'):
                st.metric(
                    "⚠️ Invalidation Level",
                    f"${invalidation['primary_invalidation']:.2f}",
                    help="Price level where the primary count becomes invalid - use for risk management"
                )
            
            # Pivot information
            pivots = analysis.get('zigzag_pivots', [])
            if pivots:
                st.metric(
                    "🔗 Pivot Points",
                    f"{len(pivots)} detected",
                    help="Number of significant turning points identified by ZigZag algorithm"
                )
            
            # Fibonacci levels info
            fib_levels = analysis.get('fibonacci_levels', {})
            retracements = fib_levels.get('retracements', [])
            extensions = fib_levels.get('extensions', [])
            
            if retracements or extensions:
                st.info(f"📐 **Fibonacci Levels**\n\n" +
                       f"• {len(retracements)} retracement levels\n" +
                       f"• {len(extensions)} extension targets")
            
            # Add Price Targets section
            st.markdown("---")
            current_price = st.session_state.price_data['close'].iloc[-1] if st.session_state.price_data is not None and not st.session_state.price_data.empty else 0
            
            if current_price > 0:
                price_targets = calculate_price_targets(analysis, current_price)
                display_price_targets(price_targets, current_price)
                
                # Risk Management Section
                st.markdown("---")
                with st.expander("🛡️ **Risk Management Calculator**", expanded=False):
                    st.markdown("#### ⚙️ Risk Management Settings")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        account_size = st.number_input(
                            "💰 Account Size ($)", 
                            min_value=1000, 
                            max_value=10000000, 
                            value=10000, 
                            step=1000,
                            help="Total trading account size"
                        )
                    with col2:
                        risk_percentage = st.slider(
                            "📊 Risk Per Trade (%)", 
                            min_value=0.5, 
                            max_value=5.0, 
                            value=2.0, 
                            step=0.25,
                            help="Maximum percentage of account to risk per trade"
                        )
                    
                    # Get invalidation level for stop loss
                    invalidation_level = None
                    if analysis and 'invalidation_levels' in st.session_state:
                        invalidation_data = st.session_state.invalidation_levels
                        invalidation_level = invalidation_data.get('primary_invalidation')
                    
                    if invalidation_level and price_targets:
                        # Calculate and display risk management
                        risk_mgmt = calculate_risk_management(
                            current_price, 
                            invalidation_level, 
                            price_targets, 
                            account_size, 
                            risk_percentage
                        )
                        
                        if risk_mgmt:
                            display_risk_management(risk_mgmt, ticker)
                    else:
                        st.info("💡 Risk management requires Elliott Wave analysis with invalidation levels")
                
                # Confidence Analysis Section
                st.markdown("---")
                with st.expander("🎯 **Advanced Confidence Analysis**", expanded=False):
                    pivots = analysis.get('zigzag_pivots', [])
                    price_data = st.session_state.price_data
                    
                    if pivots and len(pivots) >= 3:
                        with st.spinner("Calculating detailed confidence metrics..."):
                            confidence_data = calculate_detailed_confidence_score(analysis, pivots, price_data)
                        
                        if confidence_data:
                            display_confidence_analysis(confidence_data)
                    else:
                        st.info("💡 Advanced confidence analysis requires sufficient wave data (minimum 3 pivots)")
                
                # Technical Indicators Section
                st.markdown("---")
                with st.expander("📊 **Technical Indicator Analysis**", expanded=False):
                    price_data = st.session_state.price_data
                    
                    if price_data is not None and not price_data.empty and len(price_data) >= 50:
                        with st.spinner("Calculating technical indicators..."):
                            # Calculate all technical indicators
                            indicators = calculate_technical_indicators(price_data)
                            
                            if indicators:
                                # Analyze confluence with Elliott Wave
                                current_price = price_data['close'].iloc[-1]
                                confluence = analyze_indicator_confluence(indicators, current_price, analysis)
                                
                                # Display technical analysis
                                display_technical_indicators(indicators, confluence, current_price)
                                
                                # Add summary insight
                                if confluence and confluence.get('overall_score') is not None:
                                    score = confluence['overall_score']
                                    alignment = confluence['wave_alignment']
                                    
                                    st.markdown("#### 🎯 **Technical Summary**")
                                    if alignment == 'bullish' and score > 30:
                                        st.success(f"✅ **Strong Bullish Confluence** ({score:+.0f}%) - Technical indicators support Elliott Wave analysis")
                                    elif alignment == 'bearish' and score < -30:
                                        st.error(f"⚠️ **Strong Bearish Confluence** ({score:+.0f}%) - Technical indicators support Elliott Wave analysis")
                                    else:
                                        st.warning(f"⚡ **Mixed Signals** ({score:+.0f}%) - Technical indicators show conflicting signals with Elliott Wave")
                            else:
                                st.info("💡 Unable to calculate technical indicators with current data")
                    else:
                        st.info("💡 Technical indicators require at least 50 data points for accurate analysis")
                
                # Elliott Wave Rule Validation Section
                st.markdown("---")
                with st.expander("⚖️ **Elliott Wave Rule Validation**", expanded=False):
                    pivots = analysis.get('zigzag_pivots', [])
                    
                    if pivots and len(pivots) >= 3:
                        with st.spinner("Validating Elliott Wave rules and guidelines..."):
                            # Get wave labels if available
                            primary_count = analysis.get('primary_count', {})
                            wave_labels = primary_count.get('labels', []) if hasattr(primary_count, 'get') else None
                            
                            # Validate Elliott Wave rules
                            validation_results = validate_elliott_wave_rules(pivots, wave_labels)
                        
                        if validation_results:
                            display_wave_validation(validation_results)
                            
                            # Add actionable insights based on validation
                            validity_score = validation_results.get('validity_score', 0)
                            is_valid = validation_results.get('overall_validity', False)
                            
                            st.markdown("#### 🎯 **Validation Summary & Trading Implications**")
                            
                            if is_valid and validity_score >= 80:
                                st.success(f"✅ **Excellent Wave Count** ({validity_score}%) - This Elliott Wave pattern meets all major rules and guidelines. High confidence for trading decisions.")
                            elif is_valid and validity_score >= 60:
                                st.warning(f"✅ **Valid Wave Count** ({validity_score}%) - Pattern is valid but consider additional confirmation before major positions.")
                            else:
                                st.error(f"❌ **Invalid Wave Count** ({validity_score}%) - Critical rule violations detected. Avoid trading this pattern or seek alternative wave counts.")
                            
                            # Trading recommendations based on validation
                            violations = validation_results.get('rule_violations', [])
                            if violations:
                                st.markdown("**🚨 Trading Recommendations:**")
                                st.markdown("- ❌ **Do not trade** this wave count due to rule violations")
                                st.markdown("- 🔍 **Reassess** wave labeling or look for alternative counts")
                                st.markdown("- ⏳ **Wait** for pattern completion or confirmation")
                                st.markdown("- 📚 **Study** Elliott Wave theory for proper pattern recognition")
                            else:
                                confirmations = validation_results.get('rule_confirmations', [])
                                guidelines_met = len([g for g in validation_results.get('guidelines_check', []) if '✅' in g.get('description', '')])
                                
                                st.markdown("**✅ Trading Recommendations:**")
                                if len(confirmations) >= 3 and guidelines_met >= 2:
                                    st.markdown("- 🎯 **High-confidence setup** - All major rules confirmed")
                                    st.markdown("- 💰 **Consider standard position sizing** with proper risk management")
                                    st.markdown("- 📈 **Monitor for entry signals** at Fibonacci levels")
                                elif len(confirmations) >= 2:
                                    st.markdown("- ✅ **Good setup** - Major rules confirmed")
                                    st.markdown("- ⚖️ **Use conservative position sizing**")
                                    st.markdown("- 🔍 **Seek additional confirmation** before entry")
                                else:
                                    st.markdown("- ⚠️ **Proceed with caution** - Limited rule confirmation")
                                    st.markdown("- 📊 **Consider paper trading** first")
                                    st.markdown("- 🔍 **Wait for clearer signals**")
                    else:
                        st.info("💡 Elliott Wave rule validation requires at least 3 pivot points (minimum wave structure)")
                
                # Market Sentiment Dashboard Section
                st.markdown("---")
                with st.expander("🧠 **Market Sentiment Dashboard**", expanded=False):
                    with st.spinner(f"Analyzing market sentiment for {ticker}..."):
                        sentiment_data = calculate_market_sentiment(ticker, period_days=30)
                        display_market_sentiment(sentiment_data, ticker)
                
                # Sentiment-Wave Integration Section
                st.markdown("---") 
                with st.expander("🔗 **Sentiment-Wave Integration**", expanded=False):
                    with st.spinner("Integrating sentiment with Elliott Wave analysis..."):
                        sentiment_data = calculate_market_sentiment(ticker, period_days=30)
                        integration = integrate_sentiment_with_waves(analysis, sentiment_data, ticker)
                        if integration:
                            display_sentiment_wave_integration(integration, ticker)
                        else:
                            st.info("💡 Integration analysis requires both wave and sentiment data")
            
            
            
            
            
        else:
            st.info("👈 Select a stock symbol and click 'Analyze Waves' to begin")
            
        # Multi-timeframe Analysis Toggle
        st.markdown("---")
        if st.checkbox("🔄 Multi-Timeframe Analysis", help="Analyze multiple timeframes for confluence"):
            if st.session_state.analysis_results:
                with st.spinner("Analyzing multiple timeframes..."):
                    multi_tf_analysis = create_multi_timeframe_analysis(ticker)
                    
                if multi_tf_analysis:
                    st.subheader("📊 Multi-Timeframe Elliott Wave Analysis")
                    
                    # Create tabs for different timeframes
                    if len(multi_tf_analysis) > 1:
                        tf_tabs = st.tabs([f"📅 {tf.upper()}" for tf in multi_tf_analysis.keys()])
                        
                        for i, (tf, tf_data) in enumerate(multi_tf_analysis.items()):
                            with tf_tabs[i]:
                                tf_analysis = tf_data.get('analysis')
                                if tf_analysis and tf_analysis.get('primary_count'):
                                    primary = tf_analysis.get('primary_count', {})
                                    score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
                                    pattern = getattr(primary, 'pattern_type', 'Unknown') if hasattr(primary, 'pattern_type') else primary.get('pattern_type', 'Unknown')
                                    
                                    col_a, col_b = st.columns(2)
                                    
                                    with col_a:
                                        st.metric(f"{tf.upper()} Confidence", f"{score:.1f}%")
                                        
                                    with col_b:
                                        st.metric(f"{tf.upper()} Pattern", pattern)
                                    
                                    # Mini chart for this timeframe
                                    tf_df = tf_data.get('data')
                                    if tf_df is not None and not tf_df.empty:
                                        fig_mini = create_candlestick_chart(tf_df, tf_analysis)
                                        fig_mini.update_layout(height=300)
                                        st.plotly_chart(fig_mini, width="stretch")
                                else:
                                    st.warning(f"No clear pattern detected in {tf.upper()} timeframe")
                    
                    # Timeframe confluence analysis
                    st.markdown("### 🎯 Timeframe Confluence")
                    confluence_scores = []
                    for tf, tf_data in multi_tf_analysis.items():
                        tf_analysis = tf_data.get('analysis')
                        if tf_analysis and tf_analysis.get('primary_count'):
                            primary = tf_analysis.get('primary_count', {})
                            score = getattr(primary, 'confidence_score', 0) if hasattr(primary, 'confidence_score') else primary.get('confidence_score', 0)
                            confluence_scores.append(score)
                    
                    if confluence_scores:
                        avg_confidence = sum(confluence_scores) / len(confluence_scores)
                        if avg_confidence > 70:
                            st.success(f"🟢 **Strong Confluence** ({avg_confidence:.1f}%) - Multiple timeframes align!")
                        elif avg_confidence > 50:
                            st.warning(f"🟡 **Moderate Confluence** ({avg_confidence:.1f}%) - Some timeframe alignment")
                        else:
                            st.error(f"🔴 **Weak Confluence** ({avg_confidence:.1f}%) - Timeframes show conflicting patterns")
                else:
                    st.warning("Could not perform multi-timeframe analysis - check connection or try different symbol")
            
        # Chart Legend - Always visible
        st.subheader("🗺️ Chart Legend")
        st.markdown("""
        **📊 Price Candles:**
        - 🟢 Green: Bullish (Close > Open)  
        - 🔴 Red: Bearish (Close < Open)
        
        **🔗 ZigZag Line (Cyan):**
        - Connects significant pivot points
        - Filters out minor price noise
        - Diamond markers show exact pivot locations
        
        **🎯 Wave Labels (Blue):**
        - Numbers (1,2,3,4,5): Impulse waves
        - Letters (A,B,C): Corrective waves
        - Show Elliott Wave count progression
        
        **📐 Fibonacci Lines:**
        - 🟡 Dotted: Retracement levels (support/resistance)
        - � Dashed: Extension levels (price targets)
        - Color-coded by importance (Golden ratio = 61.8%)
        
        **⚠️ Invalidation (Red Solid):**
        - Critical level for wave count validity
        - Use for stop-loss placement
        - Break = reassess wave structure
        """)
        
        # Quick help section
        with st.expander("💡 Quick Help"):
            st.markdown("""
            **How to Use This Tool:**
            
            1. **Enter Symbol**: Type any stock ticker (AAPL, TSLA, etc.)
            2. **Choose Timeframe**: Daily for long-term, 1h/4h for short-term
            3. **Set ZigZag %**: Higher % = fewer, stronger pivots
            4. **Click Analyze**: Generate Elliott Wave analysis
            
            **Interpreting Results:**
            - **High Score (>70)**: Strong wave pattern confidence
            - **Medium Score (50-70)**: Acceptable but watch alternatives  
            - **Low Score (<50)**: Weak pattern, be cautious
            
            **Key Tips:**
            - Wave 3 is never the shortest (Rule #2)
            - Wave 4 cannot overlap Wave 1 (Rule #3)
            - Use Fibonacci levels for entry/exit points
            - Always respect invalidation levels for risk control
            """)
    
    # Add a section below the chart for detailed analysis
    if st.session_state.analysis_results:
        st.subheader("📝 Detailed Analysis Report")
        
        # Create tabs for different sections
        tab1, tab2, tab3 = st.tabs(["📊 Summary", "📐 Fibonacci Details", "⚙️ Technical Data"])
        
        with tab1:
            summary = analysis.get('summary', '')
            st.markdown(summary)
        
        with tab2:
            fib_levels = analysis.get('fibonacci_levels', {})
            
            col_ret, col_ext = st.columns(2)
            
            with col_ret:
                st.write("**🔽 Retracement Levels**")
                retracements = fib_levels.get('retracements', [])
                if retracements:
                    ret_df = pd.DataFrame(retracements)
                    ret_df['level_pct'] = ret_df['level'].apply(lambda x: f"{x:.1%}")
                    ret_df['price_formatted'] = ret_df['price'].apply(lambda x: f"${x:.2f}")
                    st.dataframe(
                        ret_df[['level_pct', 'price_formatted']], 
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info("No retracement levels calculated")
            
            with col_ext:
                st.write("**🔼 Extension Levels**")  
                extensions = fib_levels.get('extensions', [])
                if extensions:
                    ext_df = pd.DataFrame(extensions)
                    ext_df['level_pct'] = ext_df['level'].apply(lambda x: f"{x:.1%}")
                    ext_df['price_formatted'] = ext_df['price'].apply(lambda x: f"${x:.2f}")
                    st.dataframe(
                        ext_df[['level_pct', 'price_formatted']], 
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info("No extension levels calculated")
        
        with tab3:
            st.write("**🔗 Pivot Points Data**")
            pivots = analysis.get('zigzag_pivots', [])
            if pivots:
                pivot_df = pd.DataFrame(pivots)
                pivot_df['price_formatted'] = pivot_df['price'].apply(lambda x: f"${x:.2f}")
                pivot_df = pivot_df[['timestamp', 'price_formatted', 'type']]
                pivot_df.columns = ['Date/Time', 'Price', 'Type']
                st.dataframe(pivot_df, width="stretch", hide_index=True)
            
            st.write("**⚙️ Analysis Parameters**")
            st.json({
                "Symbol": ticker,
                "Timeframe": timeframe,
                "Date Range": range_period,
                "ZigZag Threshold": f"{zigzag_threshold}%",
                "Analysis Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Export functionality
            st.subheader("💾 Export Analysis")
            if st.button("📄 Generate Export Report", type="primary"):
                export_data = {
                    'ticker': ticker,
                    'timeframe': timeframe, 
                    'range': range_period,
                    'zigzag_threshold': zigzag_threshold,
                    'analysis_date': datetime.now().isoformat(),
                    'analysis': analysis,
                    'chart_legend': {
                        'price_candles': 'Green (bullish) / Red (bearish) candlesticks',
                        'zigzag_line': 'Cyan line connecting pivot points',
                        'wave_labels': 'Blue numbered/lettered Elliott Wave labels',
                        'fibonacci_retracements': 'Colored dotted lines (23.6%, 38.2%, 50%, 61.8%, 78.6%)',
                        'fibonacci_extensions': 'Turquoise dashed lines (127.2%, 161.8%, 261.8%)',
                        'invalidation_level': 'Red solid line - critical level for wave count'
                    }
                }
                
                st.download_button(
                    label="📥 Download Complete JSON Report",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"elliott_wave_analysis_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    help="Download complete analysis data including chart descriptions"
                )
    
    # Footer with new features
    st.markdown("---")
    
    # Pattern Scanner Section  
    st.subheader("🔍 Elliott Wave Pattern Scanner")
    
    with st.expander("📊 Scan Multiple Stocks for Elliott Wave Setups", expanded=False):
        st.markdown("**Search for Elliott Wave patterns across multiple stocks simultaneously**")
        
        # Predefined stock lists
        stock_lists = {
            "S&P 500 Top 10": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "TSLA", "META", "GOOG", "BRK-B", "UNH"],
            "FAANG Stocks": ["META", "AAPL", "AMZN", "NFLX", "GOOGL"],
            "Tech Leaders": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "CRM", "ORCL", "ADBE"],
            "Crypto Leaders": ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "ADA-USD"],
            "Custom": []
        }
        
        col_scan1, col_scan2 = st.columns(2)
        
        with col_scan1:
            selected_list = st.selectbox("Select Stock List", list(stock_lists.keys()))
            
            if selected_list == "Custom":
                custom_symbols = st.text_area(
                    "Enter symbols (comma-separated)",
                    placeholder="AAPL, MSFT, TSLA, GOOGL",
                    help="Enter stock symbols separated by commas"
                )
                symbols_to_scan = [s.strip().upper() for s in custom_symbols.split(",") if s.strip()]
            else:
                symbols_to_scan = stock_lists[selected_list]
                st.info(f"Will scan: {', '.join(symbols_to_scan)}")
        
        with col_scan2:
            scan_timeframe = st.selectbox("Scanner Timeframe", ["daily", "4h", "1h"], key="scanner_tf")
            scan_threshold = st.slider("Scanner ZigZag %", 1.0, 8.0, 4.0, key="scanner_threshold")
        
        if st.button("🚀 Start Pattern Scan", type="primary"):
            if symbols_to_scan:
                with st.spinner(f"Scanning {len(symbols_to_scan)} symbols for Elliott Wave patterns..."):
                    scan_results = scan_multiple_stocks(symbols_to_scan, scan_timeframe, scan_threshold)
                
                if scan_results:
                    display_scanner_results(scan_results)
                else:
                    st.warning("No Elliott Wave patterns found in the scanned symbols. Try adjusting the threshold or selecting different symbols.")
            else:
                st.error("Please select or enter symbols to scan")
    
    # Additional Tools Section
    with st.expander("🛠️ Additional Elliott Wave Tools", expanded=False):
        st.markdown("### 🔧 Professional Trading Tools")
        
        tool_col1, tool_col2 = st.columns(2)
        
        with tool_col1:
            st.markdown("""
            **📊 Analysis Features:**
            - Multi-timeframe confirmation
            - Price target calculations  
            - Support/resistance levels
            - Pattern confidence scoring
            - Risk management levels
            """)
            
        with tool_col2:
            st.markdown("""
            **🎯 Trading Applications:**
            - Entry/exit point identification
            - Position sizing guidance
            - Stop-loss placement
            - Profit target setting
            - Risk-reward analysis
            """)
        
        st.markdown("### 📚 Elliott Wave Education")
        
        edu_col1, edu_col2 = st.columns(2)
        
        with edu_col1:
            st.markdown("""
            **📖 Wave Patterns:**
            - **Impulse Waves**: 1-2-3-4-5 structure
            - **Corrective Waves**: A-B-C structure  
            - **Diagonal Patterns**: Wedge formations
            - **Triangle Patterns**: Consolidation phases
            """)
            
        with edu_col2:
            st.markdown("""
            **🎯 Key Rules:**
            1. Wave 2 cannot retrace more than 100% of Wave 1
            2. Wave 3 is never the shortest impulse wave
            3. Wave 4 cannot overlap Wave 1 territory
            4. Corrections alternate between simple and complex
            """)
    
    st.markdown("---")
    
    # Get GitHub info safely without secrets dependency
    try:
        github_user = st.secrets.get('GITHUB_USER', 'm-zayed5722')
    except:
        github_user = 'm-zayed5722'
    
    st.markdown(
        "*Built with Streamlit • Powered by Yahoo Finance • "
        f"[View Source Code](https://github.com/{github_user}/elliott-wave-analyzer)*"
    )

def calculate_market_sentiment(symbol, period_days=30):
    """
    Calculate comprehensive market sentiment indicators
    Includes Fear & Greed components, VIX analysis, and custom sentiment scoring
    """
    try:
        sentiment_data = {
            'overall_sentiment': 'Neutral',
            'sentiment_score': 50,  # 0-100 scale
            'fear_greed_components': {},
            'vix_analysis': {},
            'market_breadth': {},
            'sentiment_history': [],
            'recommendations': []
        }
        
        # Get VIX data for fear/greed analysis
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_data = vix_ticker.history(period=f"{period_days}d")
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                vix_avg = vix_data['Close'].mean()
                vix_std = vix_data['Close'].std()
                
                # VIX analysis
                if current_vix > 30:
                    vix_sentiment = "Extreme Fear"
                    vix_score = 10
                elif current_vix > 20:
                    vix_sentiment = "Fear"
                    vix_score = 25
                elif current_vix < 12:
                    vix_sentiment = "Extreme Greed"
                    vix_score = 90
                elif current_vix < 16:
                    vix_sentiment = "Greed"
                    vix_score = 75
                else:
                    vix_sentiment = "Neutral"
                    vix_score = 50
                
                sentiment_data['vix_analysis'] = {
                    'current_vix': current_vix,
                    'average_vix': vix_avg,
                    'vix_percentile': ((current_vix - vix_data['Close'].min()) / 
                                     (vix_data['Close'].max() - vix_data['Close'].min())) * 100,
                    'sentiment': vix_sentiment,
                    'score': vix_score,
                    'interpretation': f"VIX at {current_vix:.2f} indicates {vix_sentiment.lower()}"
                }
        except:
            sentiment_data['vix_analysis'] = {
                'current_vix': None,
                'sentiment': 'Unknown',
                'score': 50,
                'interpretation': 'VIX data unavailable'
            }
        
        # Get stock data for additional sentiment analysis
        try:
            stock = yf.Ticker(symbol)
            stock_data = stock.history(period=f"{period_days}d")
            
            if not stock_data.empty:
                # Price momentum analysis
                returns = stock_data['Close'].pct_change().dropna()
                positive_days = (returns > 0).sum()
                total_days = len(returns)
                positive_ratio = positive_days / total_days if total_days > 0 else 0.5
                
                # Volatility analysis
                volatility = returns.std() * (252 ** 0.5)  # Annualized volatility
                
                # Volume analysis
                avg_volume = stock_data['Volume'].mean()
                recent_volume = stock_data['Volume'].tail(5).mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                # RSI-based sentiment
                def calculate_rsi(prices, period=14):
                    delta = prices.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    return rsi.iloc[-1] if not rsi.empty else 50
                
                rsi = calculate_rsi(stock_data['Close'])
                
                # Fear & Greed components
                sentiment_data['fear_greed_components'] = {
                    'price_momentum': {
                        'value': positive_ratio * 100,
                        'score': positive_ratio * 100,
                        'interpretation': f"{positive_ratio*100:.1f}% positive days in last {period_days} days"
                    },
                    'price_strength': {
                        'value': rsi,
                        'score': rsi,
                        'interpretation': f"RSI at {rsi:.1f} - {'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'}"
                    },
                    'volatility': {
                        'value': volatility * 100,
                        'score': max(0, min(100, 100 - volatility * 200)),  # Lower volatility = higher score
                        'interpretation': f"Annualized volatility: {volatility*100:.1f}%"
                    },
                    'volume': {
                        'value': volume_ratio,
                        'score': min(100, volume_ratio * 50),
                        'interpretation': f"Recent volume {volume_ratio:.1f}x average"
                    }
                }
        except:
            sentiment_data['fear_greed_components'] = {
                'price_momentum': {'value': 50, 'score': 50, 'interpretation': 'Data unavailable'},
                'price_strength': {'value': 50, 'score': 50, 'interpretation': 'Data unavailable'},
                'volatility': {'value': 20, 'score': 50, 'interpretation': 'Data unavailable'},
                'volume': {'value': 1, 'score': 50, 'interpretation': 'Data unavailable'}
            }
        
        # Market breadth indicators (simplified)
        try:
            # Get major indices for breadth analysis
            indices_data = {}
            for index_symbol in ['^GSPC', '^DJI', '^IXIC']:  # S&P 500, Dow, NASDAQ
                try:
                    index_ticker = yf.Ticker(index_symbol)
                    index_hist = index_ticker.history(period="5d")
                    if not index_hist.empty:
                        daily_change = ((index_hist['Close'].iloc[-1] / index_hist['Close'].iloc[0]) - 1) * 100
                        indices_data[index_symbol] = daily_change
                except:
                    continue
            
            if indices_data:
                avg_index_performance = sum(indices_data.values()) / len(indices_data)
                breadth_score = min(100, max(0, 50 + avg_index_performance * 10))
                
                sentiment_data['market_breadth'] = {
                    'indices_performance': indices_data,
                    'average_performance': avg_index_performance,
                    'breadth_score': breadth_score,
                    'interpretation': f"Major indices average: {avg_index_performance:.1f}%"
                }
        except:
            sentiment_data['market_breadth'] = {
                'breadth_score': 50,
                'interpretation': 'Market breadth data unavailable'
            }
        
        # Calculate overall sentiment score
        component_scores = []
        
        # VIX weight: 30%
        if sentiment_data['vix_analysis'].get('score'):
            component_scores.append(sentiment_data['vix_analysis']['score'] * 0.3)
        
        # Fear & Greed components weight: 50%
        fg_scores = []
        for component in sentiment_data['fear_greed_components'].values():
            fg_scores.append(component['score'])
        if fg_scores:
            avg_fg_score = sum(fg_scores) / len(fg_scores)
            component_scores.append(avg_fg_score * 0.5)
        
        # Market breadth weight: 20%
        if sentiment_data['market_breadth'].get('breadth_score'):
            component_scores.append(sentiment_data['market_breadth']['breadth_score'] * 0.2)
        
        if component_scores:
            sentiment_data['sentiment_score'] = sum(component_scores)
        else:
            sentiment_data['sentiment_score'] = 50
        
        # Determine overall sentiment
        score = sentiment_data['sentiment_score']
        if score >= 80:
            sentiment_data['overall_sentiment'] = "Extreme Greed"
        elif score >= 60:
            sentiment_data['overall_sentiment'] = "Greed"
        elif score >= 40:
            sentiment_data['overall_sentiment'] = "Neutral"
        elif score >= 20:
            sentiment_data['overall_sentiment'] = "Fear"
        else:
            sentiment_data['overall_sentiment'] = "Extreme Fear"
        
        # Generate recommendations
        if score >= 75:
            sentiment_data['recommendations'] = [
                "🔴 Extreme greed detected - consider taking profits",
                "⚠️ Market may be overextended - watch for reversal signals",
                "📈 If trend is strong, consider trailing stops"
            ]
        elif score >= 55:
            sentiment_data['recommendations'] = [
                "🟡 Moderate optimism - normal market conditions",
                "✅ Good environment for trend-following strategies",
                "📊 Monitor key support/resistance levels"
            ]
        elif score <= 25:
            sentiment_data['recommendations'] = [
                "🟢 Extreme fear detected - potential buying opportunity",
                "💡 Contrarian investors may find value here",
                "⏳ Wait for confirmation signals before entering"
            ]
        else:
            sentiment_data['recommendations'] = [
                "🔵 Fear present - market may find support soon",
                "🎯 Look for oversold bounce opportunities",
                "📉 Defensive positioning may be appropriate"
            ]
        
        return sentiment_data
        
    except Exception as e:
        return {
            'overall_sentiment': 'Error',
            'sentiment_score': 50,
            'error': str(e),
            'fear_greed_components': {},
            'vix_analysis': {},
            'market_breadth': {},
            'recommendations': ['Error calculating sentiment data']
        }

def display_market_sentiment(sentiment_data, symbol):
    """Display comprehensive market sentiment dashboard"""
    
    if not sentiment_data or sentiment_data.get('error'):
        st.error(f"Error loading sentiment data: {sentiment_data.get('error', 'Unknown error')}")
        return
    
    st.markdown("### 🧠 **Market Sentiment Dashboard**")
    
    # Overall sentiment gauge
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col2:
        score = sentiment_data['sentiment_score']
        sentiment = sentiment_data['overall_sentiment']
        
        # Create sentiment gauge
        if score >= 80:
            gauge_color = "red"
            gauge_emoji = "🔥"
        elif score >= 60:
            gauge_color = "orange" 
            gauge_emoji = "📈"
        elif score >= 40:
            gauge_color = "blue"
            gauge_emoji = "😐"
        elif score >= 20:
            gauge_color = "purple"
            gauge_emoji = "📉"
        else:
            gauge_color = "green"
            gauge_emoji = "❄️"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background: linear-gradient(45deg, #1f1f1f, #2f2f2f); 
                    border-radius: 15px; border: 2px solid {gauge_color};">
            <h2 style="color: {gauge_color}; margin: 0;">{gauge_emoji} {sentiment}</h2>
            <h1 style="color: {gauge_color}; margin: 10px 0; font-size: 3em;">{score:.0f}</h1>
            <p style="color: #888; margin: 0;">Sentiment Score (0-100)</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Fear & Greed Components
    if sentiment_data.get('fear_greed_components'):
        st.markdown("#### 📊 **Fear & Greed Components**")
        
        components = sentiment_data['fear_greed_components']
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'price_momentum' in components:
                momentum = components['price_momentum']
                st.markdown(f"""
                <div style="padding: 15px; background: #1e1e1e; border-radius: 10px; border-left: 4px solid #00ff41;">
                    <h5 style="color: #00ff41; margin: 0;">📈 Price Momentum</h5>
                    <h3 style="color: white; margin: 10px 0;">{momentum['score']:.1f}/100</h3>
                    <p style="color: #888; margin: 0; font-size: 0.9em;">{momentum['interpretation']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            if 'volatility' in components:
                volatility = components['volatility']
                st.markdown(f"""
                <div style="padding: 15px; background: #1e1e1e; border-radius: 10px; border-left: 4px solid #ff6b6b; margin-top: 10px;">
                    <h5 style="color: #ff6b6b; margin: 0;">⚡ Volatility</h5>
                    <h3 style="color: white; margin: 10px 0;">{volatility['score']:.1f}/100</h3>
                    <p style="color: #888; margin: 0; font-size: 0.9em;">{volatility['interpretation']}</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if 'price_strength' in components:
                strength = components['price_strength']
                st.markdown(f"""
                <div style="padding: 15px; background: #1e1e1e; border-radius: 10px; border-left: 4px solid #4ecdc4;">
                    <h5 style="color: #4ecdc4; margin: 0;">💪 Price Strength (RSI)</h5>
                    <h3 style="color: white; margin: 10px 0;">{strength['score']:.1f}/100</h3>
                    <p style="color: #888; margin: 0; font-size: 0.9em;">{strength['interpretation']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            if 'volume' in components:
                volume = components['volume']
                st.markdown(f"""
                <div style="padding: 15px; background: #1e1e1e; border-radius: 10px; border-left: 4px solid #ffd93d; margin-top: 10px;">
                    <h5 style="color: #ffd93d; margin: 0;">📊 Volume Activity</h5>
                    <h3 style="color: white; margin: 10px 0;">{volume['score']:.1f}/100</h3>
                    <p style="color: #888; margin: 0; font-size: 0.9em;">{volume['interpretation']}</p>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # VIX Analysis & Market Breadth
    col1, col2 = st.columns(2)
    
    with col1:
        if sentiment_data.get('vix_analysis'):
            vix = sentiment_data['vix_analysis']
            st.markdown("#### 😨 **VIX Fear Index**")
            
            vix_color = "green" if vix.get('current_vix', 20) > 25 else "red" if vix.get('current_vix', 20) < 15 else "orange"
            
            st.markdown(f"""
            <div style="padding: 20px; background: #1e1e1e; border-radius: 10px; border: 2px solid {vix_color};">
                <h3 style="color: {vix_color}; margin: 0;">Current VIX: {vix.get('current_vix', 'N/A'):.2f if vix.get('current_vix') else 'N/A'}</h3>
                <p style="color: white; margin: 10px 0;">Status: {vix.get('sentiment', 'Unknown')}</p>
                <p style="color: #888; margin: 0; font-size: 0.9em;">{vix.get('interpretation', 'No data')}</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        if sentiment_data.get('market_breadth'):
            breadth = sentiment_data['market_breadth']
            st.markdown("#### 📊 **Market Breadth**")
            
            breadth_color = "green" if breadth.get('breadth_score', 50) > 60 else "red" if breadth.get('breadth_score', 50) < 40 else "orange"
            
            st.markdown(f"""
            <div style="padding: 20px; background: #1e1e1e; border-radius: 10px; border: 2px solid {breadth_color};">
                <h3 style="color: {breadth_color}; margin: 0;">Breadth Score: {breadth.get('breadth_score', 50):.1f}</h3>
                <p style="color: white; margin: 10px 0;">Market Health</p>
                <p style="color: #888; margin: 0; font-size: 0.9em;">{breadth.get('interpretation', 'No data')}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Sentiment-based Recommendations
    if sentiment_data.get('recommendations'):
        st.markdown("#### 💡 **Market Psychology Insights**")
        
        for recommendation in sentiment_data['recommendations']:
            st.markdown(f"• {recommendation}")
    
    # Educational content
    st.markdown("---")
    st.markdown("#### 📚 **Understanding Market Sentiment**")
    
    with st.expander("📖 Learn About Market Sentiment Indicators"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Fear & Greed Components:**
            - **Price Momentum**: Percentage of positive vs negative days
            - **Price Strength**: RSI indicator showing overbought/oversold conditions
            - **Volatility**: Market stability measured by price fluctuations
            - **Volume**: Trading activity compared to historical averages
            """)
        
        with col2:
            st.markdown("""
            **Key Indicators:**
            - **VIX (Fear Index)**: Measures market fear and uncertainty
            - **Market Breadth**: Performance across major market indices  
            - **Sentiment Score**: Composite 0-100 scale of market psychology
            - **Contrarian Signals**: Extreme readings often signal reversals
            """)
        
        st.markdown("""
        **💡 Trading with Sentiment:**
        - **Extreme Fear (0-25)**: Often presents buying opportunities for contrarian traders
        - **Fear (25-40)**: Market may find support, look for oversold bounces
        - **Neutral (40-60)**: Balanced conditions, trend-following strategies work well
        - **Greed (60-80)**: Caution advised, market may be overextended
        - **Extreme Greed (80-100)**: Consider profit-taking, watch for reversal signals
        
        ⚠️ **Important**: Sentiment analysis works best when combined with technical analysis and Elliott Wave patterns. 
        Extreme sentiment readings can persist longer than expected in strong trends.
        """)

def integrate_sentiment_with_waves(analysis, sentiment_data, ticker):
    """
    Integrate market sentiment analysis with Elliott Wave patterns
    Provide sentiment-enhanced trading recommendations
    """
    if not sentiment_data or not analysis:
        return None
    
    integration = {
        'sentiment_score': sentiment_data.get('sentiment_score', 50),
        'sentiment_label': sentiment_data.get('overall_sentiment', 'Neutral'),
        'wave_sentiment_alignment': {},
        'enhanced_recommendations': [],
        'risk_adjustments': [],
        'timing_insights': []
    }
    
    # Get current wave analysis
    primary_count = analysis.get('primary_count', {})
    current_wave = primary_count.get('current_wave', 'Unknown')
    wave_confidence = analysis.get('confidence_metrics', {}).get('overall_confidence', 0)
    
    score = integration['sentiment_score']
    sentiment = integration['sentiment_label']
    
    # Analyze sentiment-wave alignment
    if "1" in str(current_wave) or "3" in str(current_wave) or "5" in str(current_wave):
        # Impulse waves - bullish waves
        if score >= 60:  # Greed/Extreme Greed
            integration['wave_sentiment_alignment'] = {
                'status': 'ALIGNED',
                'strength': 'Strong',
                'description': f"Bullish sentiment ({sentiment}) aligns with impulse Wave {current_wave}",
                'confidence_boost': 15
            }
            integration['enhanced_recommendations'].extend([
                f"🟢 Sentiment-Wave ALIGNMENT: {sentiment} supports Wave {current_wave} development",
                "💪 Strong psychological backing for continued upward movement",
                "📈 Consider standard position sizing - sentiment supports trend"
            ])
        elif score <= 40:  # Fear/Extreme Fear
            integration['wave_sentiment_alignment'] = {
                'status': 'CONTRARIAN',
                'strength': 'Moderate',
                'description': f"Bearish sentiment ({sentiment}) during Wave {current_wave} may signal opportunity",
                'confidence_boost': 10
            }
            integration['enhanced_recommendations'].extend([
                f"🟡 CONTRARIAN SIGNAL: {sentiment} during Wave {current_wave} may create opportunity",
                "🎯 Oversold conditions could fuel next impulse move",
                "⚖️ Consider smaller position sizes until sentiment improves"
            ])
        else:
            integration['wave_sentiment_alignment'] = {
                'status': 'NEUTRAL',
                'strength': 'Moderate',
                'description': f"Neutral sentiment during Wave {current_wave}",
                'confidence_boost': 5
            }
    
    elif "2" in str(current_wave) or "4" in str(current_wave):
        # Corrective waves - expect pullbacks
        if score <= 40:  # Fear/Extreme Fear
            integration['wave_sentiment_alignment'] = {
                'status': 'ALIGNED',
                'strength': 'Strong', 
                'description': f"Bearish sentiment ({sentiment}) aligns with corrective Wave {current_wave}",
                'confidence_boost': 15
            }
            integration['enhanced_recommendations'].extend([
                f"🔴 Sentiment-Wave ALIGNMENT: {sentiment} confirms Wave {current_wave} correction",
                "📉 Psychology supports the expected pullback/correction",
                "🎯 Ideal conditions to prepare for next impulse wave entry"
            ])
        elif score >= 60:  # Greed/Extreme Greed
            integration['wave_sentiment_alignment'] = {
                'status': 'DIVERGENCE',
                'strength': 'Warning',
                'description': f"Bullish sentiment ({sentiment}) conflicts with corrective Wave {current_wave}",
                'confidence_boost': -10
            }
            integration['enhanced_recommendations'].extend([
                f"⚠️ SENTIMENT DIVERGENCE: {sentiment} conflicts with Wave {current_wave} correction",
                "🔍 Market may not correct as expected - watch for truncation or extension",
                "🛡️ Use smaller position sizes due to sentiment-wave mismatch"
            ])
        else:
            integration['wave_sentiment_alignment'] = {
                'status': 'NEUTRAL',
                'strength': 'Moderate',
                'description': f"Neutral sentiment during Wave {current_wave} correction",
                'confidence_boost': 5
            }
    
    # VIX-specific insights
    vix_analysis = sentiment_data.get('vix_analysis', {})
    current_vix = vix_analysis.get('current_vix')
    if current_vix:
        if current_vix > 30:
            integration['timing_insights'].append("🔥 Extreme VIX spike - Often marks major turning points")
            integration['timing_insights'].append("💡 High volatility favors breakout/breakdown scenarios")
        elif current_vix < 12:
            integration['timing_insights'].append("😴 Very low VIX - Market complacency, potential for surprise moves")
            integration['timing_insights'].append("⚠️ Low volatility may precede significant price action")
    
    # Risk adjustments based on sentiment
    if score >= 80 or score <= 20:  # Extreme readings
        integration['risk_adjustments'].append("🎯 EXTREME SENTIMENT: Reduce position sizes by 30-50%")
        integration['risk_adjustments'].append("⏰ Extreme readings often precede reversals - be prepared")
        integration['risk_adjustments'].append("🔍 Watch for divergences between price and sentiment")
    elif score >= 70 or score <= 30:  # High readings
        integration['risk_adjustments'].append("⚖️ HIGH SENTIMENT: Consider reducing position sizes by 20%")
        integration['risk_adjustments'].append("📊 Monitor closely for shifts in market psychology")
    
    # Enhanced recommendations based on combined analysis
    confidence_adjustment = integration['wave_sentiment_alignment'].get('confidence_boost', 0)
    adjusted_confidence = max(0, min(100, wave_confidence + confidence_adjustment))
    
    integration['adjusted_confidence'] = adjusted_confidence
    
    if adjusted_confidence >= 80:
        integration['enhanced_recommendations'].append("✅ HIGH CONFIDENCE SETUP: Both sentiment and waves align favorably")
    elif adjusted_confidence >= 60:
        integration['enhanced_recommendations'].append("✅ MODERATE CONFIDENCE: Good setup with minor concerns")
    elif adjusted_confidence >= 40:
        integration['enhanced_recommendations'].append("⚠️ LOW CONFIDENCE: Proceed with caution and tight risk management")
    else:
        integration['enhanced_recommendations'].append("❌ POOR SETUP: Avoid trading until better alignment emerges")
    
    return integration

def display_sentiment_wave_integration(integration, ticker):
    """Display the integrated sentiment and wave analysis"""
    
    if not integration:
        st.info("💡 Sentiment integration requires both wave and sentiment data")
        return
    
    st.markdown("### 🔗 **Sentiment-Wave Integration Analysis**")
    
    # Alignment status
    alignment = integration.get('wave_sentiment_alignment', {})
    status = alignment.get('status', 'UNKNOWN')
    strength = alignment.get('strength', 'Unknown')
    description = alignment.get('description', 'No description available')
    
    if status == 'ALIGNED':
        status_color = "green"
        status_emoji = "✅"
    elif status == 'CONTRARIAN':
        status_color = "orange"
        status_emoji = "🔄"
    elif status == 'DIVERGENCE':
        status_color = "red"
        status_emoji = "⚠️"
    else:
        status_color = "blue"
        status_emoji = "😐"
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"""
        <div style="padding: 20px; background: #1e1e1e; border-radius: 10px; border-left: 5px solid {status_color};">
            <h4 style="color: {status_color}; margin: 0;">{status_emoji} {status} - {strength} Signal</h4>
            <p style="color: white; margin: 10px 0 0 0;">{description}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        adjusted_confidence = integration.get('adjusted_confidence', 50)
        confidence_color = "green" if adjusted_confidence >= 70 else "orange" if adjusted_confidence >= 50 else "red"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; background: #2e2e2e; border-radius: 10px;">
            <h5 style="color: {confidence_color}; margin: 0;">Adjusted Confidence</h5>
            <h2 style="color: {confidence_color}; margin: 10px 0;">{adjusted_confidence:.0f}%</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Enhanced recommendations
    if integration.get('enhanced_recommendations'):
        st.markdown("#### 🎯 **Enhanced Trading Recommendations**")
        for rec in integration['enhanced_recommendations']:
            st.markdown(f"• {rec}")
    
    # Risk adjustments
    if integration.get('risk_adjustments'):
        st.markdown("#### ⚖️ **Risk Management Adjustments**")
        for risk in integration['risk_adjustments']:
            st.markdown(f"• {risk}")
    
    # Timing insights
    if integration.get('timing_insights'):
        st.markdown("#### ⏰ **Market Timing Insights**")
        for insight in integration['timing_insights']:
            st.markdown(f"• {insight}")
    
    st.markdown("---")
    st.markdown("*💡 Integration analysis combines Elliott Wave patterns with market sentiment psychology for enhanced decision-making.*")

if __name__ == "__main__":
    main()