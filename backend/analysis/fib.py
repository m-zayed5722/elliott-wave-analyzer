"""
Fibonacci retracement and extension calculations for Elliott Wave analysis.
Calculates key Fibonacci levels based on detected wave patterns.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple


# Standard Fibonacci ratios
FIBONACCI_RETRACEMENTS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIBONACCI_EXTENSIONS = [1.0, 1.272, 1.618, 2.0, 2.618]


def calculate_retracement_levels(start_price: float, end_price: float, 
                               ratios: List[float] = None) -> List[Dict]:
    """
    Calculate Fibonacci retracement levels between two price points.
    
    Args:
        start_price: Starting price level
        end_price: Ending price level  
        ratios: List of Fibonacci ratios to calculate (default: standard retracements)
        
    Returns:
        List of dictionaries with level, price, and label
    """
    if ratios is None:
        ratios = FIBONACCI_RETRACEMENTS
    
    price_range = end_price - start_price
    retracements = []
    
    for ratio in ratios:
        retracement_price = end_price - (price_range * ratio)
        retracements.append({
            'level': ratio,
            'price': retracement_price,
            'label': f'{ratio:.1%} Retracement'
        })
    
    return retracements


def calculate_extension_levels(wave_start: float, wave_end: float, 
                             extension_start: float,
                             ratios: List[float] = None) -> List[Dict]:
    """
    Calculate Fibonacci extension levels.
    
    Args:
        wave_start: Start price of the reference wave
        wave_end: End price of the reference wave
        extension_start: Starting point for extensions
        ratios: List of Fibonacci ratios to calculate
        
    Returns:
        List of dictionaries with level, price, and label
    """
    if ratios is None:
        ratios = FIBONACCI_EXTENSIONS
    
    wave_length = abs(wave_end - wave_start)
    direction = 1 if wave_end > wave_start else -1
    
    extensions = []
    
    for ratio in ratios:
        extension_price = extension_start + (direction * wave_length * ratio)
        extensions.append({
            'level': ratio,
            'price': extension_price,
            'label': f'{ratio:.3f} Extension'
        })
    
    return extensions


def calculate_swing_retracements(df: pd.DataFrame, pivots: List[Dict]) -> List[Dict]:
    """
    Calculate retracement levels for the most recent significant swing.
    
    Args:
        df: OHLCV DataFrame
        pivots: List of detected pivots
        
    Returns:
        List of retracement level dictionaries
    """
    if len(pivots) < 2:
        return []
    
    # Get the last two pivots to define the most recent swing
    last_pivot = pivots[-1]
    second_last_pivot = pivots[-2]
    
    start_price = second_last_pivot['price']
    end_price = last_pivot['price']
    
    return calculate_retracement_levels(start_price, end_price)


def calculate_wave_extensions(pivots: List[Dict], wave_labels: List[Dict]) -> List[Dict]:
    """
    Calculate extension levels for Elliott Wave patterns.
    
    Args:
        pivots: List of detected pivots
        wave_labels: List of wave labels from wave analysis
        
    Returns:
        List of extension level dictionaries
    """
    if len(pivots) < 3:
        return []
    
    extensions = []
    
    # Try to identify Wave 1 and Wave 3 for extensions
    wave1_pivots = []
    wave3_pivots = []
    
    # Simple approach: use recent pivot sequences
    if len(pivots) >= 5:
        # Assume 5-wave structure for extensions
        wave1_start = pivots[-5]['price']
        wave1_end = pivots[-4]['price']
        wave3_start = pivots[-3]['price'] 
        wave3_end = pivots[-2]['price']
        wave5_start = pivots[-1]['price']
        
        # Wave 3 extensions (from Wave 1)
        wave3_extensions = calculate_extension_levels(
            wave1_start, wave1_end, wave3_start,
            ratios=[1.618, 2.618, 4.236]  # Common Wave 3 targets
        )
        
        for ext in wave3_extensions:
            ext['label'] = f'Wave 3 {ext["label"]}'
            extensions.append(ext)
        
        # Wave 5 extensions (from Wave 1)
        wave5_extensions = calculate_extension_levels(
            wave1_start, wave1_end, wave5_start,
            ratios=[0.618, 1.0, 1.618]  # Common Wave 5 targets
        )
        
        for ext in wave5_extensions:
            ext['label'] = f'Wave 5 {ext["label"]}'
            extensions.append(ext)
    
    return extensions


def calculate_abc_targets(pivots: List[Dict]) -> List[Dict]:
    """
    Calculate target levels for ABC corrective patterns.
    
    Args:
        pivots: List of detected pivots
        
    Returns:
        List of target level dictionaries
    """
    if len(pivots) < 3:
        return []
    
    # Get A, B, C points (last 3 pivots)
    wave_a_start = pivots[-3]['price']
    wave_a_end = pivots[-2]['price']  # This is also Wave B start
    wave_b_end = pivots[-1]['price']  # This is also Wave C start
    
    wave_a_length = abs(wave_a_end - wave_a_start)
    direction = 1 if wave_a_end < wave_a_start else -1  # Direction of C wave
    
    # Common C wave targets relative to A wave
    c_ratios = [0.618, 1.0, 1.618]
    targets = []
    
    for ratio in c_ratios:
        target_price = wave_b_end + (direction * wave_a_length * ratio)
        targets.append({
            'level': ratio,
            'price': target_price,
            'label': f'Wave C {ratio:.3f} of A'
        })
    
    return targets


def calculate_fibonacci_levels(df: pd.DataFrame, pivots: List[Dict]) -> Dict:
    """
    Main function to calculate all Fibonacci levels for a given analysis.
    
    Args:
        df: OHLCV DataFrame
        pivots: List of detected pivots
        
    Returns:
        Dictionary containing retracements and extensions
    """
    result = {
        'retracements': [],
        'extensions': [],
        'abc_targets': []
    }
    
    # Calculate swing retracements
    result['retracements'] = calculate_swing_retracements(df, pivots)
    
    # Calculate wave extensions (for impulse patterns)
    result['extensions'] = calculate_wave_extensions(pivots, [])
    
    # Calculate ABC targets (for corrective patterns)
    result['abc_targets'] = calculate_abc_targets(pivots)
    
    return result


def find_fibonacci_confluences(levels_list: List[List[Dict]], 
                              tolerance_pct: float = 2.0) -> List[Dict]:
    """
    Find price levels where multiple Fibonacci calculations converge.
    
    Args:
        levels_list: List of lists containing Fibonacci level dictionaries
        tolerance_pct: Percentage tolerance for considering levels as confluent
        
    Returns:
        List of confluence level dictionaries
    """
    if not levels_list:
        return []
    
    # Flatten all levels into a single list
    all_levels = []
    for level_group in levels_list:
        all_levels.extend(level_group)
    
    if len(all_levels) < 2:
        return []
    
    confluences = []
    processed_indices = set()
    
    for i, level1 in enumerate(all_levels):
        if i in processed_indices:
            continue
            
        confluence_group = [level1]
        group_indices = {i}
        
        for j, level2 in enumerate(all_levels[i+1:], i+1):
            if j in processed_indices:
                continue
                
            # Check if prices are within tolerance
            price_diff_pct = abs(level1['price'] - level2['price']) / level1['price'] * 100
            
            if price_diff_pct <= tolerance_pct:
                confluence_group.append(level2)
                group_indices.add(j)
        
        # If we found a confluence (2+ levels close together)
        if len(confluence_group) >= 2:
            processed_indices.update(group_indices)
            
            # Calculate average price and create confluence entry
            avg_price = sum(level['price'] for level in confluence_group) / len(confluence_group)
            labels = [level['label'] for level in confluence_group]
            
            confluences.append({
                'price': avg_price,
                'count': len(confluence_group),
                'labels': labels,
                'label': f'Confluence ({len(confluence_group)} levels)',
                'strength': len(confluence_group)  # Higher count = stronger confluence
            })
    
    # Sort by strength (descending)
    confluences.sort(key=lambda x: x['strength'], reverse=True)
    
    return confluences


def filter_relevant_levels(levels: List[Dict], current_price: float, 
                          max_distance_pct: float = 50.0) -> List[Dict]:
    """
    Filter Fibonacci levels to only include those within a reasonable distance of current price.
    
    Args:
        levels: List of Fibonacci level dictionaries
        current_price: Current market price
        max_distance_pct: Maximum percentage distance from current price
        
    Returns:
        Filtered list of relevant levels
    """
    if current_price <= 0:
        return levels
    
    relevant_levels = []
    
    for level in levels:
        distance_pct = abs(level['price'] - current_price) / current_price * 100
        if distance_pct <= max_distance_pct:
            level['distance_pct'] = distance_pct
            relevant_levels.append(level)
    
    # Sort by distance from current price
    relevant_levels.sort(key=lambda x: x.get('distance_pct', float('inf')))
    
    return relevant_levels


def calculate_support_resistance_levels(df: pd.DataFrame, pivots: List[Dict], 
                                      lookback_periods: int = 50) -> List[Dict]:
    """
    Calculate support and resistance levels from historical pivot points.
    
    Args:
        df: OHLCV DataFrame
        pivots: List of detected pivots
        lookback_periods: Number of recent periods to analyze
        
    Returns:
        List of support/resistance level dictionaries
    """
    if len(pivots) < 3:
        return []
    
    # Get recent data
    recent_data = df.tail(lookback_periods) if len(df) > lookback_periods else df
    current_price = recent_data['close'].iloc[-1]
    
    # Separate high and low pivots
    high_pivots = [p for p in pivots if p['direction'] == 'high']
    low_pivots = [p for p in pivots if p['direction'] == 'low']
    
    levels = []
    
    # Identify resistance levels (from high pivots)
    for pivot in high_pivots[-10:]:  # Last 10 high pivots
        if pivot['price'] > current_price:  # Above current price = resistance
            levels.append({
                'price': pivot['price'],
                'type': 'resistance',
                'label': f'Resistance at {pivot["price"]:.2f}',
                'strength': 1  # Could be enhanced with touch count
            })
    
    # Identify support levels (from low pivots)  
    for pivot in low_pivots[-10:]:  # Last 10 low pivots
        if pivot['price'] < current_price:  # Below current price = support
            levels.append({
                'price': pivot['price'],
                'type': 'support',
                'label': f'Support at {pivot["price"]:.2f}',
                'strength': 1
            })
    
    return levels


if __name__ == "__main__":
    # Simple test
    test_pivots = [
        {'index': 0, 'price': 100.0, 'direction': 'low'},
        {'index': 5, 'price': 120.0, 'direction': 'high'},
        {'index': 10, 'price': 110.0, 'direction': 'low'},
        {'index': 15, 'price': 135.0, 'direction': 'high'},
        {'index': 20, 'price': 125.0, 'direction': 'low'}
    ]
    
    # Test retracements
    retracements = calculate_retracement_levels(100.0, 120.0)
    print("Retracement levels from 100 to 120:")
    for level in retracements:
        print(f"  {level['label']}: {level['price']:.2f}")
    
    # Test extensions  
    extensions = calculate_extension_levels(100.0, 120.0, 110.0)
    print("\nExtension levels:")
    for level in extensions:
        print(f"  {level['label']}: {level['price']:.2f}")