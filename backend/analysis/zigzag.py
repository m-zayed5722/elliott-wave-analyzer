"""
ZigZag pivot detection for Elliott Wave analysis.
Identifies significant high and low points based on percentage thresholds.
"""

import pandas as pd
import numpy as np
from typing import List, Dict


def detect_zigzag(df: pd.DataFrame, pct_threshold: float = 4.0) -> List[Dict]:
    """
    Detect ZigZag pivots using percentage threshold method.
    
    Args:
        df: DataFrame with OHLCV data
        pct_threshold: Minimum percentage move to qualify as a pivot
        
    Returns:
        List of pivot dictionaries with index, price, and direction
    """
    if len(df) < 3:
        return []
    
    high_col = df['high'].values
    low_col = df['low'].values
    
    pivots = []
    
    # Find the first significant high or low as starting point
    start_idx = 0
    current_trend = None  # Will be 'up' or 'down'
    current_pivot_idx = 0
    current_pivot_price = high_col[0]
    
    # Determine initial trend direction
    for i in range(1, min(20, len(df))):  # Look at first 20 bars
        high_change = (high_col[i] - high_col[current_pivot_idx]) / high_col[current_pivot_idx] * 100
        low_change = (low_col[current_pivot_idx] - low_col[i]) / low_col[current_pivot_idx] * 100
        
        if high_change >= pct_threshold:
            current_trend = 'up'
            current_pivot_idx = 0
            current_pivot_price = low_col[0]
            break
        elif low_change >= pct_threshold:
            current_trend = 'down'
            current_pivot_idx = 0
            current_pivot_price = high_col[0]
            break
    
    if current_trend is None:
        # If no clear trend found, start with first bar as low
        current_trend = 'up'
        current_pivot_idx = 0
        current_pivot_price = low_col[0]
        pivots.append({
            'index': 0,
            'price': low_col[0],
            'direction': 'low'
        })
    
    # Scan for pivots
    i = 1
    while i < len(df):
        if current_trend == 'up':
            # Looking for highs
            if high_col[i] > current_pivot_price:
                current_pivot_idx = i
                current_pivot_price = high_col[i]
            else:
                # Check for reversal (significant move down from high)
                decline_pct = (current_pivot_price - low_col[i]) / current_pivot_price * 100
                if decline_pct >= pct_threshold:
                    # Found a high pivot
                    pivots.append({
                        'index': current_pivot_idx,
                        'price': current_pivot_price,
                        'direction': 'high'
                    })
                    # Switch to looking for lows
                    current_trend = 'down'
                    current_pivot_idx = i
                    current_pivot_price = low_col[i]
        
        else:  # current_trend == 'down'
            # Looking for lows
            if low_col[i] < current_pivot_price:
                current_pivot_idx = i
                current_pivot_price = low_col[i]
            else:
                # Check for reversal (significant move up from low)
                rally_pct = (high_col[i] - current_pivot_price) / current_pivot_price * 100
                if rally_pct >= pct_threshold:
                    # Found a low pivot
                    pivots.append({
                        'index': current_pivot_idx,
                        'price': current_pivot_price,
                        'direction': 'low'
                    })
                    # Switch to looking for highs
                    current_trend = 'up'
                    current_pivot_idx = i
                    current_pivot_price = high_col[i]
        
        i += 1
    
    # Add the final pivot if we ended on an extreme
    if len(pivots) == 0 or pivots[-1]['index'] != current_pivot_idx:
        direction = 'high' if current_trend == 'up' else 'low'
        pivots.append({
            'index': current_pivot_idx,
            'price': current_pivot_price,
            'direction': direction
        })
    
    return pivots


def validate_zigzag(df: pd.DataFrame, pivots: List[Dict], min_move_pct: float = 1.0) -> List[Dict]:
    """
    Validate and clean up zigzag pivots by removing insignificant moves.
    
    Args:
        df: Original OHLCV DataFrame
        pivots: List of detected pivots
        min_move_pct: Minimum percentage move between consecutive pivots
        
    Returns:
        Cleaned list of pivots
    """
    if len(pivots) <= 2:
        return pivots
    
    cleaned_pivots = [pivots[0]]  # Always keep the first pivot
    
    for i in range(1, len(pivots)):
        prev_pivot = cleaned_pivots[-1]
        curr_pivot = pivots[i]
        
        # Calculate percentage move
        price_change = abs(curr_pivot['price'] - prev_pivot['price'])
        pct_change = (price_change / prev_pivot['price']) * 100
        
        if pct_change >= min_move_pct:
            cleaned_pivots.append(curr_pivot)
        else:
            # If move is too small, update the last pivot to the more extreme one
            if curr_pivot['direction'] == 'high' and curr_pivot['price'] > prev_pivot['price']:
                cleaned_pivots[-1] = curr_pivot
            elif curr_pivot['direction'] == 'low' and curr_pivot['price'] < prev_pivot['price']:
                cleaned_pivots[-1] = curr_pivot
    
    return cleaned_pivots


def get_recent_pivots(pivots: List[Dict], max_count: int = 120) -> List[Dict]:
    """
    Get the most recent N pivots for wave analysis.
    
    Args:
        pivots: Full list of pivots
        max_count: Maximum number of recent pivots to return
        
    Returns:
        List of recent pivots
    """
    return pivots[-max_count:] if len(pivots) > max_count else pivots


def calculate_pivot_strength(df: pd.DataFrame, pivot: Dict, lookback: int = 5) -> float:
    """
    Calculate the strength of a pivot based on surrounding price action.
    
    Args:
        df: OHLCV DataFrame
        pivot: Pivot dictionary
        lookback: Number of bars to look back/forward
        
    Returns:
        Strength score (0-100)
    """
    idx = pivot['index']
    direction = pivot['direction']
    price = pivot['price']
    
    # Get surrounding bars
    start_idx = max(0, idx - lookback)
    end_idx = min(len(df), idx + lookback + 1)
    
    surrounding_highs = df['high'].iloc[start_idx:end_idx]
    surrounding_lows = df['low'].iloc[start_idx:end_idx]
    
    if direction == 'high':
        # For high pivots, check how much higher this is than surrounding highs
        max_other_high = surrounding_highs.drop(surrounding_highs.index[idx - start_idx]).max()
        if pd.isna(max_other_high):
            return 50.0
        strength = min(100.0, ((price - max_other_high) / max_other_high) * 100 * 10)
    else:  # low pivot
        # For low pivots, check how much lower this is than surrounding lows
        min_other_low = surrounding_lows.drop(surrounding_lows.index[idx - start_idx]).min()
        if pd.isna(min_other_low):
            return 50.0
        strength = min(100.0, ((min_other_low - price) / min_other_low) * 100 * 10)
    
    return max(0.0, strength)


if __name__ == "__main__":
    # Simple test with synthetic data
    test_data = {
        'high': [100, 102, 105, 108, 104, 107, 111, 109, 106, 103, 101, 98, 95, 97, 100, 103, 106],
        'low': [98, 100, 103, 105, 101, 104, 108, 106, 103, 100, 98, 95, 92, 94, 97, 100, 103],
        'open': [99, 101, 104, 106, 102, 105, 109, 107, 104, 101, 99, 96, 93, 95, 98, 101, 104],
        'close': [101, 103, 106, 105, 103, 106, 110, 108, 105, 102, 100, 97, 94, 96, 99, 102, 105],
        'volume': [1000] * 17
    }
    
    df = pd.DataFrame(test_data)
    pivots = detect_zigzag(df, pct_threshold=3.0)
    
    print("Detected pivots:")
    for pivot in pivots:
        print(f"Index: {pivot['index']}, Price: {pivot['price']:.2f}, Direction: {pivot['direction']}")