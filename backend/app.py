from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import yfinance as yf
import pandas as pd
import json
import sqlite3
import os
from datetime import datetime, timedelta
import hashlib
from analysis.zigzag import detect_zigzag, validate_zigzag, get_recent_pivots
from analysis.waves import analyze_waves, calculate_invalidation_levels
from analysis.fib import calculate_fibonacci_levels

app = FastAPI(title="Elliott Wave Analyzer API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DB_PATH = "cache.db"

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

# Initialize database on startup
init_db()

class PriceData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int

class AnalyzeRequest(BaseModel):
    ticker: str
    timeframe: str = "daily"  # daily, 4H
    range: str = "5y"
    zigzag_pct: Optional[float] = None

class WaveLabel(BaseModel):
    index: int
    wave: str  # 1,2,3,4,5,A,B,C

class FibLevel(BaseModel):
    level: float
    price: float
    label: str

class InvalidationLevel(BaseModel):
    price: float
    reason: str

class WaveCount(BaseModel):
    labels: List[WaveLabel]
    fib_retracements: List[FibLevel]
    fib_extensions: List[FibLevel]
    invalidation: InvalidationLevel
    score: float
    summary: str

class Pivot(BaseModel):
    index: int
    price: float
    timestamp: str
    direction: str  # "high" or "low"

class AnalyzeResponse(BaseModel):
    primary: WaveCount
    alternate: WaveCount
    pivots: List[Pivot]

def get_cache_key(ticker: str, timeframe: str, range_str: str) -> str:
    """Generate cache key for price data"""
    return hashlib.md5(f"{ticker}_{timeframe}_{range_str}".encode()).hexdigest()

def is_cache_valid(created_at: str, hours: int = 6) -> bool:
    """Check if cache entry is still valid"""
    cache_time = datetime.fromisoformat(created_at)
    return datetime.now() - cache_time < timedelta(hours=hours)

def get_cached_data(cache_key: str) -> Optional[List[Dict]]:
    """Retrieve cached price data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data, created_at FROM price_cache WHERE cache_key = ?", (cache_key,))
    result = cursor.fetchone()
    conn.close()
    
    if result and is_cache_valid(result[1]):
        return json.loads(result[0])
    return None

def cache_data(cache_key: str, data: List[Dict]):
    """Store price data in cache"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO price_cache (cache_key, data, created_at)
        VALUES (?, ?, ?)
    """, (cache_key, json.dumps(data), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def fetch_yahoo_data(ticker: str, period: str = "5y", interval: str = "1d") -> List[Dict]:
    """Fetch price data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        
        if hist.empty:
            raise ValueError(f"No data found for ticker {ticker}")
        
        # Convert to list of dictionaries
        data = []
        for timestamp, row in hist.iterrows():
            data.append({
                "timestamp": timestamp.isoformat(),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            })
        
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching data: {str(e)}")

def timeframe_to_interval(timeframe: str) -> str:
    """Convert timeframe to yfinance interval"""
    mapping = {
        "daily": "1d",
        "4H": "4h",
        "1H": "1h"
    }
    return mapping.get(timeframe, "1d")

@app.get("/")
async def root():
    return {"message": "Elliott Wave Analyzer API"}

@app.get("/prices/{ticker}")
async def get_prices(ticker: str, tf: str = "daily", range: str = "5y") -> List[PriceData]:
    """Get OHLCV price data for a ticker"""
    cache_key = get_cache_key(ticker.upper(), tf, range)
    
    # Try cache first
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return [PriceData(**item) for item in cached_data]
    
    # Fetch fresh data
    interval = timeframe_to_interval(tf)
    data = fetch_yahoo_data(ticker.upper(), period=range, interval=interval)
    
    # Cache the data
    cache_data(cache_key, data)
    
    return [PriceData(**item) for item in data]

@app.post("/analyze")
async def analyze_elliott_waves(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze Elliott Wave patterns for a ticker"""
    # Get price data
    cache_key = get_cache_key(request.ticker.upper(), request.timeframe, request.range)
    
    cached_data = get_cached_data(cache_key)
    if not cached_data:
        interval = timeframe_to_interval(request.timeframe)
        cached_data = fetch_yahoo_data(request.ticker.upper(), 
                                     period=request.range, 
                                     interval=interval)
        cache_data(cache_key, cached_data)
    
    if not cached_data:
        raise HTTPException(status_code=404, detail="No data found for ticker")
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(cached_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Set default zigzag percentage based on timeframe
    if request.zigzag_pct is None:
        request.zigzag_pct = 4.0 if request.timeframe == "daily" else 2.0
    
    # Detect zigzag pivots
    raw_pivots = detect_zigzag(df, request.zigzag_pct)
    
    # Validate and clean pivots
    pivots = validate_zigzag(df, raw_pivots, min_move_pct=1.0)
    
    # Get recent pivots for analysis
    recent_pivots = get_recent_pivots(pivots, max_count=120)
    
    # Analyze wave patterns
    wave_analysis = analyze_waves(df, recent_pivots)
    
    # Calculate Fibonacci levels
    fib_levels = calculate_fibonacci_levels(df, recent_pivots)
    
    # Calculate invalidation levels for both counts
    primary_invalidation = calculate_invalidation_levels(wave_analysis['primary'], recent_pivots)
    alternate_invalidation = calculate_invalidation_levels(wave_analysis['alternate'], recent_pivots)
    
    # Convert wave analysis to API response format
    primary_labels = [
        WaveLabel(index=label.index, wave=label.wave) 
        for label in wave_analysis['primary'].labels
    ]
    alternate_labels = [
        WaveLabel(index=label.index, wave=label.wave) 
        for label in wave_analysis['alternate'].labels
    ]
    
    # Convert Fibonacci levels to API format
    fib_retracements = [
        FibLevel(level=fib['level'], price=fib['price'], label=fib['label'])
        for fib in fib_levels.get('retracements', [])
    ]
    
    fib_extensions = [
        FibLevel(level=fib['level'], price=fib['price'], label=fib['label'])
        for fib in fib_levels.get('extensions', [])
    ]
    
    # Create primary and alternate wave counts
    primary_count = WaveCount(
        labels=primary_labels,
        fib_retracements=fib_retracements,
        fib_extensions=fib_extensions,
        invalidation=InvalidationLevel(
            price=primary_invalidation['price'],
            reason=primary_invalidation['reason']
        ),
        score=wave_analysis['primary'].score,
        summary=wave_analysis['primary'].summary
    )
    
    alternate_count = WaveCount(
        labels=alternate_labels,
        fib_retracements=fib_retracements,  # Same Fib levels for both
        fib_extensions=fib_extensions,
        invalidation=InvalidationLevel(
            price=alternate_invalidation['price'], 
            reason=alternate_invalidation['reason']
        ),
        score=wave_analysis['alternate'].score,
        summary=wave_analysis['alternate'].summary
    )
    
    # Convert pivots to response format
    pivot_response = []
    for pivot in pivots:
        pivot_response.append(Pivot(
            index=pivot['index'],
            price=pivot['price'],
            timestamp=df.iloc[pivot['index']]['timestamp'].isoformat(),
            direction=pivot['direction']
        ))
    
    return AnalyzeResponse(
        primary=primary_count,
        alternate=alternate_count,
        pivots=pivot_response
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)