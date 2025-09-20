"""
Elliott Wave pattern recognition and enumeration.
Implements core Elliott Wave rules for impulse and corrective patterns.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WaveLabel:
    index: int
    wave: str  # 1,2,3,4,5,A,B,C
    price: float


@dataclass
class WaveCount:
    labels: List[WaveLabel]
    score: float
    pattern_type: str  # 'impulse' or 'corrective'
    summary: str


def calculate_fibonacci_ratio_error(observed: float, expected: float) -> float:
    """Calculate the error between observed and expected Fibonacci ratio."""
    if expected == 0:
        return 1.0
    error = abs(observed - expected) / expected
    return min(1.0, error)  # Clamp to [0,1]


def check_impulse_rules(pivots: List[Dict]) -> Tuple[bool, float, List[str]]:
    """
    Check if a sequence of pivots follows impulse wave rules.
    
    Returns:
        (is_valid, score, violations)
    """
    if len(pivots) < 5:
        return False, 0.0, ["Not enough pivots for impulse"]
    
    # Take last 5 pivots for 5-wave impulse
    wave_pivots = pivots[-5:]
    violations = []
    penalty_score = 0.0
    
    # Rule 1: Wave 2 never retraces more than 100% of wave 1
    wave1_start = wave_pivots[0]['price']
    wave1_end = wave_pivots[1]['price']
    wave2_end = wave_pivots[2]['price']
    
    wave1_length = abs(wave1_end - wave1_start)
    if wave1_length > 0:
        retracement_pct = abs(wave2_end - wave1_end) / wave1_length
        if retracement_pct > 1.0:
            violations.append("Wave 2 retraces more than 100% of wave 1")
            penalty_score += 50.0
    
    # Rule 2: Wave 3 is never the shortest wave
    wave3_start = wave_pivots[2]['price']
    wave3_end = wave_pivots[3]['price']
    wave5_start = wave_pivots[4]['price']
    wave5_end = wave_pivots[-1]['price'] if len(pivots) > 5 else wave_pivots[4]['price']
    
    wave1_size = abs(wave1_end - wave1_start)
    wave3_size = abs(wave3_end - wave3_start)
    wave5_size = abs(wave5_end - wave5_start)
    
    if wave3_size <= wave1_size or wave3_size <= wave5_size:
        violations.append("Wave 3 is the shortest wave")
        penalty_score += 30.0
    
    # Rule 3: Wave 4 does not overlap wave 1 price territory
    wave4_end = wave_pivots[4]['price']
    
    # Determine trend direction
    is_uptrend = wave1_end > wave1_start
    
    if is_uptrend:
        if wave4_end <= wave1_end:
            violations.append("Wave 4 overlaps wave 1 territory")
            penalty_score += 40.0
    else:
        if wave4_end >= wave1_end:
            violations.append("Wave 4 overlaps wave 1 territory")
            penalty_score += 40.0
    
    is_valid = len(violations) == 0
    score = max(0.0, 100.0 - penalty_score)
    
    return is_valid, score, violations


def calculate_fibonacci_score(pivots: List[Dict]) -> float:
    """Calculate score based on Fibonacci ratio conformance."""
    if len(pivots) < 5:
        return 0.0
    
    wave_pivots = pivots[-5:]
    
    # Expected Fibonacci ratios for impulse waves
    fib_ratios = {
        'wave2_to_wave1': [0.382, 0.5, 0.618],  # Common retracement levels
        'wave3_to_wave1': [1.618, 2.618, 1.0],  # Common extension levels
        'wave4_to_wave3': [0.236, 0.382, 0.5],  # Common retracement levels
        'wave5_to_wave1': [0.618, 1.0, 1.618]   # Common extension levels
    }
    
    wave1_size = abs(wave_pivots[1]['price'] - wave_pivots[0]['price'])
    wave2_size = abs(wave_pivots[2]['price'] - wave_pivots[1]['price'])
    wave3_size = abs(wave_pivots[3]['price'] - wave_pivots[2]['price'])
    wave4_size = abs(wave_pivots[4]['price'] - wave_pivots[3]['price'])
    
    # Calculate wave 5 size (use last pivot if available)
    if len(pivots) > 5:
        wave5_size = abs(pivots[-1]['price'] - wave_pivots[4]['price'])
    else:
        wave5_size = wave1_size  # Assume equal to wave 1 if no data
    
    total_error = 0.0
    comparisons = 0
    
    if wave1_size > 0:
        # Wave 2 to Wave 1 ratio
        ratio = wave2_size / wave1_size
        min_error = min([calculate_fibonacci_ratio_error(ratio, expected) 
                        for expected in fib_ratios['wave2_to_wave1']])
        total_error += min_error
        comparisons += 1
        
        # Wave 3 to Wave 1 ratio
        ratio = wave3_size / wave1_size
        min_error = min([calculate_fibonacci_ratio_error(ratio, expected) 
                        for expected in fib_ratios['wave3_to_wave1']])
        total_error += min_error
        comparisons += 1
        
        # Wave 5 to Wave 1 ratio
        ratio = wave5_size / wave1_size
        min_error = min([calculate_fibonacci_ratio_error(ratio, expected) 
                        for expected in fib_ratios['wave5_to_wave1']])
        total_error += min_error
        comparisons += 1
    
    if wave3_size > 0:
        # Wave 4 to Wave 3 ratio
        ratio = wave4_size / wave3_size
        min_error = min([calculate_fibonacci_ratio_error(ratio, expected) 
                        for expected in fib_ratios['wave4_to_wave3']])
        total_error += min_error
        comparisons += 1
    
    if comparisons == 0:
        return 0.0
    
    # Convert error to score (lower error = higher score)
    avg_error = total_error / comparisons
    score = (1.0 - avg_error) * 100.0
    
    return max(0.0, score)


def check_corrective_rules(pivots: List[Dict]) -> Tuple[bool, float, List[str]]:
    """
    Check if a sequence of pivots follows corrective wave rules (ABC).
    """
    if len(pivots) < 3:
        return False, 0.0, ["Not enough pivots for corrective"]
    
    # Take last 3 pivots for ABC corrective
    wave_pivots = pivots[-3:]
    violations = []
    penalty_score = 0.0
    
    # Basic ABC structure validation
    wave_a_size = abs(wave_pivots[1]['price'] - wave_pivots[0]['price'])
    wave_b_size = abs(wave_pivots[2]['price'] - wave_pivots[1]['price'])
    wave_c_size = abs(wave_pivots[-1]['price'] - wave_pivots[2]['price']) if len(pivots) > 3 else wave_a_size
    
    # Rule: Wave B typically retraces 38-78% of Wave A
    if wave_a_size > 0:
        b_retracement = wave_b_size / wave_a_size
        if b_retracement < 0.3 or b_retracement > 0.9:
            penalty_score += 20.0
    
    # Rule: Wave C often equals Wave A or is 1.618 times Wave A
    if wave_a_size > 0:
        c_to_a_ratio = wave_c_size / wave_a_size
        # Check if close to 1.0 or 1.618
        error_1 = abs(c_to_a_ratio - 1.0)
        error_618 = abs(c_to_a_ratio - 1.618)
        min_error = min(error_1, error_618)
        if min_error > 0.3:  # Allow 30% deviation
            penalty_score += 15.0
    
    is_valid = penalty_score < 50.0
    score = max(0.0, 100.0 - penalty_score)
    
    return is_valid, score, violations


def generate_wave_labels(pivots: List[Dict], pattern_type: str) -> List[WaveLabel]:
    """Generate wave labels for a given pattern."""
    labels = []
    
    if pattern_type == 'impulse' and len(pivots) >= 5:
        wave_names = ['1', '2', '3', '4', '5']
        for i, pivot in enumerate(pivots[-5:]):
            labels.append(WaveLabel(
                index=pivot['index'],
                wave=wave_names[i],
                price=pivot['price']
            ))
    
    elif pattern_type == 'corrective' and len(pivots) >= 3:
        wave_names = ['A', 'B', 'C']
        for i, pivot in enumerate(pivots[-3:]):
            labels.append(WaveLabel(
                index=pivot['index'],
                wave=wave_names[i],
                price=pivot['price']
            ))
    
    return labels


def generate_summary(wave_count: WaveCount, pattern_type: str) -> str:
    """Generate a human-readable summary of the wave count."""
    if pattern_type == 'impulse':
        if len(wave_count.labels) >= 5:
            wave5 = wave_count.labels[-1]
            wave1 = wave_count.labels[-5]
            trend = "upward" if wave5.price > wave1.price else "downward"
            
            summary = f"5-wave {trend} impulse structure detected with Wave 5 at {wave5.price:.2f}. "
            
            if wave_count.score >= 80:
                summary += "Strong Fibonacci conformance supports this count. "
            elif wave_count.score >= 60:
                summary += "Moderate Fibonacci conformance. "
            else:
                summary += "Weak Fibonacci relationships. "
                
            summary += f"Score: {wave_count.score:.1f}/100."
        else:
            summary = "Incomplete impulse pattern detected."
    
    elif pattern_type == 'corrective':
        if len(wave_count.labels) >= 3:
            wave_c = wave_count.labels[-1]
            wave_a = wave_count.labels[-3]
            trend = "upward" if wave_c.price > wave_a.price else "downward"
            
            summary = f"3-wave {trend} corrective ABC structure with Wave C at {wave_c.price:.2f}. "
            
            if wave_count.score >= 70:
                summary += "Good proportional relationships. "
            else:
                summary += "Irregular corrective proportions. "
                
            summary += f"Score: {wave_count.score:.1f}/100."
        else:
            summary = "Incomplete corrective pattern detected."
    
    else:
        summary = f"Pattern analysis incomplete. Score: {wave_count.score:.1f}/100."
    
    return summary


def analyze_waves(df: pd.DataFrame, pivots: List[Dict]) -> Dict:
    """
    Main function to analyze Elliott Wave patterns from pivot data.
    
    Returns:
        Dictionary with 'primary' and 'alternate' wave counts
    """
    if len(pivots) < 3:
        # Return empty analysis if not enough data
        empty_count = WaveCount(
            labels=[],
            score=0.0,
            pattern_type='unknown',
            summary="Insufficient data for wave analysis."
        )
        return {'primary': empty_count, 'alternate': empty_count}
    
    # Limit to most recent pivots for analysis
    recent_pivots = pivots[-120:] if len(pivots) > 120 else pivots
    
    # Try impulse pattern first
    impulse_valid, impulse_score, impulse_violations = check_impulse_rules(recent_pivots)
    if impulse_valid:
        fib_score = calculate_fibonacci_score(recent_pivots)
        combined_impulse_score = (impulse_score + fib_score) / 2
    else:
        combined_impulse_score = impulse_score * 0.5  # Penalize invalid patterns
    
    # Try corrective pattern
    corrective_valid, corrective_score, corrective_violations = check_corrective_rules(recent_pivots)
    
    # Create wave counts
    impulse_labels = generate_wave_labels(recent_pivots, 'impulse')
    corrective_labels = generate_wave_labels(recent_pivots, 'corrective')
    
    impulse_count = WaveCount(
        labels=impulse_labels,
        score=combined_impulse_score,
        pattern_type='impulse',
        summary=""
    )
    impulse_count.summary = generate_summary(impulse_count, 'impulse')
    
    corrective_count = WaveCount(
        labels=corrective_labels,
        score=corrective_score,
        pattern_type='corrective',
        summary=""
    )
    corrective_count.summary = generate_summary(corrective_count, 'corrective')
    
    # Determine primary and alternate based on scores
    if combined_impulse_score >= corrective_score:
        primary = impulse_count
        alternate = corrective_count
    else:
        primary = corrective_count
        alternate = impulse_count
    
    return {
        'primary': primary,
        'alternate': alternate
    }


def calculate_invalidation_levels(wave_count: WaveCount, pivots: List[Dict]) -> Dict:
    """
    Calculate invalidation levels for a wave count.
    
    Returns:
        Dictionary with 'price' and 'reason' for invalidation
    """
    if not wave_count.labels or len(pivots) < 2:
        return {'price': 0.0, 'reason': 'Insufficient data'}
    
    if wave_count.pattern_type == 'impulse' and len(wave_count.labels) >= 4:
        # For impulse: invalidation if Wave 4 overlaps Wave 1 territory
        wave1_labels = [l for l in wave_count.labels if l.wave == '1']
        wave2_labels = [l for l in wave_count.labels if l.wave == '2']
        
        if wave1_labels and wave2_labels:
            wave1_start = None
            wave1_end = wave1_labels[0].price
            
            # Find wave 1 start (previous pivot before wave 1)
            wave1_idx = wave1_labels[0].index
            for pivot in reversed(pivots):
                if pivot['index'] < wave1_idx:
                    wave1_start = pivot['price']
                    break
            
            if wave1_start is not None:
                is_uptrend = wave1_end > wave1_start
                if is_uptrend:
                    invalidation_price = wave1_end
                    reason = f"Invalidation below {invalidation_price:.2f} (Wave 1 high)"
                else:
                    invalidation_price = wave1_end
                    reason = f"Invalidation above {invalidation_price:.2f} (Wave 1 low)"
                    
                return {'price': invalidation_price, 'reason': reason}
    
    elif wave_count.pattern_type == 'corrective' and len(wave_count.labels) >= 2:
        # For corrective: invalidation beyond Wave A start
        wave_a_labels = [l for l in wave_count.labels if l.wave == 'A']
        
        if wave_a_labels:
            wave_a_end = wave_a_labels[0].price
            
            # Find Wave A start
            wave_a_idx = wave_a_labels[0].index
            for pivot in reversed(pivots):
                if pivot['index'] < wave_a_idx:
                    wave_a_start = pivot['price']
                    is_uptrend = wave_a_end > wave_a_start
                    
                    if is_uptrend:
                        invalidation_price = wave_a_start
                        reason = f"Invalidation below {invalidation_price:.2f} (Wave A start)"
                    else:
                        invalidation_price = wave_a_start
                        reason = f"Invalidation above {invalidation_price:.2f} (Wave A start)"
                        
                    return {'price': invalidation_price, 'reason': reason}
                    break
    
    # Default invalidation
    last_pivot = pivots[-1]
    return {
        'price': last_pivot['price'],
        'reason': 'Pattern invalidation at current extreme'
    }


if __name__ == "__main__":
    # Simple test
    test_pivots = [
        {'index': 0, 'price': 100.0, 'direction': 'low'},
        {'index': 5, 'price': 120.0, 'direction': 'high'},
        {'index': 10, 'price': 110.0, 'direction': 'low'},
        {'index': 15, 'price': 135.0, 'direction': 'high'},
        {'index': 20, 'price': 125.0, 'direction': 'low'},
        {'index': 25, 'price': 140.0, 'direction': 'high'}
    ]
    
    # Create dummy DataFrame
    test_df = pd.DataFrame({
        'high': [120, 135, 140],
        'low': [100, 110, 125],
        'close': [115, 130, 138]
    })
    
    result = analyze_waves(test_df, test_pivots)
    print("Primary pattern:", result['primary'].pattern_type, 
          "Score:", result['primary'].score)
    print("Summary:", result['primary'].summary)