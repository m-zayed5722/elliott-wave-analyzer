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
    
    /* Fix for metric visibility issues */
    .metric-container {
        background-color: #fafafa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
    }
    
    /* Ensure metric text is visible */
    [data-testid="metric-container"] {
        background-color: #fafafa !important;
        border: 1px solid #e0e0e0 !important;
        padding: 1rem !important;
        border-radius: 0.5rem !important;
    }
    
    [data-testid="metric-container"] > div {
        color: #262730 !important;
    }
    
    [data-testid="metric-container"] label {
        color: #262730 !important;
        font-weight: 600 !important;
    }
    
    [data-testid="metric-container"] [data-testid="metric-value"] {
        color: #262730 !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
    }
    
    [data-testid="metric-container"] [data-testid="metric-delta"] {
        font-weight: 500 !important;
    }
    
    /* Dark theme compatibility */
    .stApp[data-theme="dark"] [data-testid="metric-container"] {
        background-color: #2e2e2e !important;
        border-color: #4a4a4a !important;
    }
    
    .stApp[data-theme="dark"] [data-testid="metric-container"] > div {
        color: #ffffff !important;
    }
    
    .stApp[data-theme="dark"] [data-testid="metric-container"] label {
        color: #ffffff !important;
    }
    
    .stApp[data-theme="dark"] [data-testid="metric-container"] [data-testid="metric-value"] {
        color: #ffffff !important;
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
        trend_direction = determine_overall_trend(pivots)
        pivot_count = len(pivots)
        
        return f"📊 **{ticker} Market Structure Analysis**: Detected **{pivot_count} pivot points** showing {trend_direction} market structure. While no definitive Elliott Wave pattern emerges (confidence too low), the price action suggests {'continued momentum' if 'trend' in trend_direction else 'consolidation or complex correction'}. **Recommendation**: Monitor for clearer pattern development or adjust ZigZag sensitivity. Current structure may be in early wave formation or complex corrective phase requiring more price development for proper classification."
    
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
    """Display price targets in an organized format"""
    
    if not targets:
        st.info("No price targets calculated - need more pivot data")
        return
    
    st.subheader("🎯 Price Targets & Levels")
    
    # Wave Targets
    wave_targets = targets.get('wave_targets', {})
    if wave_targets:
        st.markdown("**📈 Elliott Wave Price Targets:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'wave_3_target' in wave_targets:
                target = wave_targets['wave_3_target']
                distance = ((target - current_price) / current_price) * 100
                
                # Use colored container for better visibility
                if distance > 0:
                    delta_color = "normal"
                else:
                    delta_color = "inverse"
                
                st.metric(
                    "🎯 Wave 3 Target",
                    f"${target:.2f}",
                    f"{distance:+.1f}%",
                    delta_color=delta_color,
                    help="Primary Wave 3 target (1.618x Wave 1)"
                )
            
            if 'wave_5_target' in wave_targets:
                target = wave_targets['wave_5_target'] 
                distance = ((target - current_price) / current_price) * 100
                
                if distance > 0:
                    delta_color = "normal"
                else:
                    delta_color = "inverse"
                
                st.metric(
                    "🏁 Wave 5 Target", 
                    f"${target:.2f}",
                    f"{distance:+.1f}%",
                    delta_color=delta_color,
                    help="Wave 5 target (equality with Wave 1)"
                )
        
        with col2:
            if 'wave_3_extension' in wave_targets:
                target = wave_targets['wave_3_extension']
                distance = ((target - current_price) / current_price) * 100
                
                if distance > 0:
                    delta_color = "normal"
                else:
                    delta_color = "inverse"
                
                st.metric(
                    "🚀 Wave 3 Extension",
                    f"${target:.2f}", 
                    f"{distance:+.1f}%",
                    delta_color=delta_color,
                    help="Extended Wave 3 target (2.618x Wave 1)"
                )
                
            if 'wave_5_extension' in wave_targets:
                target = wave_targets['wave_5_extension']
                distance = ((target - current_price) / current_price) * 100
                
                if distance > 0:
                    delta_color = "normal"
                else:
                    delta_color = "inverse"
                
                st.metric(
                    "🎯 Wave 5 Extension",
                    f"${target:.2f}",
                    f"{distance:+.1f}%",
                    delta_color=delta_color,
                    help="Extended Wave 5 target"
                )
        
        # Alternative display using colored info boxes
        st.markdown("---")
        st.markdown("**📊 Quick Price Target Summary:**")
        
        target_summary = []
        if 'wave_3_target' in wave_targets:
            target = wave_targets['wave_3_target']
            distance = ((target - current_price) / current_price) * 100
            target_summary.append(f"• **Wave 3**: ${target:.2f} ({distance:+.1f}%)")
        
        if 'wave_5_target' in wave_targets:
            target = wave_targets['wave_5_target']
            distance = ((target - current_price) / current_price) * 100
            target_summary.append(f"• **Wave 5**: ${target:.2f} ({distance:+.1f}%)")
        
        if target_summary:
            for summary in target_summary:
                st.markdown(summary)
    
    # Support/Resistance with improved visibility
    sr_levels = targets.get('support_resistance', {})
    if sr_levels:
        st.markdown("---")
        st.markdown("**🛡️ Support & Resistance Levels:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'major_support' in sr_levels:
                level = sr_levels['major_support']
                distance = ((level - current_price) / current_price) * 100
                
                st.metric(
                    "🔻 Major Support",
                    f"${level:.2f}",
                    f"{distance:+.1f}%",
                    delta_color="inverse" if distance < 0 else "normal"
                )
                
            if 'immediate_support' in sr_levels:
                level = sr_levels['immediate_support']
                distance = ((level - current_price) / current_price) * 100  
                
                st.metric(
                    "📉 Immediate Support",
                    f"${level:.2f}",
                    f"{distance:+.1f}%",
                    delta_color="inverse" if distance < 0 else "normal"
                )
        
        with col2:
            if 'major_resistance' in sr_levels:
                level = sr_levels['major_resistance']
                distance = ((level - current_price) / current_price) * 100
                
                st.metric(
                    "🔺 Major Resistance", 
                    f"${level:.2f}",
                    f"{distance:+.1f}%",
                    delta_color="normal" if distance > 0 else "inverse"
                )
                
            if 'immediate_resistance' in sr_levels:
                level = sr_levels['immediate_resistance']
                distance = ((level - current_price) / current_price) * 100
                
                st.metric(
                    "📈 Immediate Resistance",
                    f"${level:.2f}",
                    f"{distance:+.1f}%",
                    delta_color="normal" if distance > 0 else "inverse"
                )
        
        # Alternative text-based summary for support/resistance
        st.markdown("**📋 Support/Resistance Summary:**")
        sr_summary = []
        
        if 'major_support' in sr_levels:
            level = sr_levels['major_support']
            distance = ((level - current_price) / current_price) * 100
            sr_summary.append(f"• **Major Support**: ${level:.2f} ({distance:+.1f}%)")
        
        if 'major_resistance' in sr_levels:
            level = sr_levels['major_resistance']
            distance = ((level - current_price) / current_price) * 100
            sr_summary.append(f"• **Major Resistance**: ${level:.2f} ({distance:+.1f}%)")
        
        if sr_summary:
            for summary in sr_summary:
                st.markdown(summary)

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
                st.plotly_chart(fig, use_container_width=True)
                
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
                                        st.plotly_chart(fig_mini, use_container_width=True)
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
                        use_container_width=True,
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
                        use_container_width=True,
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
                st.dataframe(pivot_df, use_container_width=True, hide_index=True)
            
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
    st.markdown(
        "*Built with Streamlit • Powered by Yahoo Finance • "
        f"[View Source Code](https://github.com/{st.secrets.get('GITHUB_USER', 'm-zayed5722')}/elliott-wave-analyzer)*"
    )

if __name__ == "__main__":
    main()