"""
Unit tests for Fibonacci calculations.
"""

import pytest
from analysis.fib import (
    calculate_retracement_levels,
    calculate_extension_levels,
    calculate_fibonacci_levels,
    find_fibonacci_confluences,
    filter_relevant_levels
)


class TestFibonacciCalculations:
    """Test Fibonacci level calculations."""

    def test_retracement_levels_uptrend(self):
        """Test Fibonacci retracement calculation for uptrend."""
        start_price = 100.0
        end_price = 161.8  # 61.8 point move
        
        retracements = calculate_retracement_levels(start_price, end_price)
        
        # Should return the standard retracement levels
        assert len(retracements) == 5  # 23.6%, 38.2%, 50%, 61.8%, 78.6%
        
        # Check 50% retracement
        fifty_percent = next(r for r in retracements if abs(r['level'] - 0.5) < 0.01)
        expected_price = end_price - (end_price - start_price) * 0.5
        assert abs(fifty_percent['price'] - expected_price) < 0.01
        
        # Check 61.8% retracement  
        golden_ratio = next(r for r in retracements if abs(r['level'] - 0.618) < 0.01)
        expected_price = end_price - (end_price - start_price) * 0.618
        assert abs(golden_ratio['price'] - expected_price) < 0.01

    def test_retracement_levels_downtrend(self):
        """Test Fibonacci retracement calculation for downtrend."""
        start_price = 161.8
        end_price = 100.0  # Down move
        
        retracements = calculate_retracement_levels(start_price, end_price)
        
        # Should still return 5 levels
        assert len(retracements) == 5
        
        # In a downtrend, 50% retracement should be halfway back up
        fifty_percent = next(r for r in retracements if abs(r['level'] - 0.5) < 0.01)
        expected_price = end_price - (end_price - start_price) * 0.5  # Note: end_price - start_price is negative
        assert abs(fifty_percent['price'] - 130.9) < 0.1  # Should be around 130.9

    def test_extension_levels_uptrend(self):
        """Test Fibonacci extension calculation for uptrend."""
        wave_start = 100.0
        wave_end = 161.8    # 61.8 point wave
        extension_start = 130.9  # Starting point for extensions
        
        extensions = calculate_extension_levels(wave_start, wave_end, extension_start)
        
        assert len(extensions) == 4  # 100%, 127.2%, 161.8%, 200%
        
        # Check 161.8% extension
        golden_extension = next(e for e in extensions if abs(e['level'] - 1.618) < 0.01)
        wave_length = abs(wave_end - wave_start)  # 61.8 points
        expected_price = extension_start + wave_length * 1.618
        assert abs(golden_extension['price'] - expected_price) < 0.1

    def test_extension_levels_downtrend(self):
        """Test Fibonacci extension calculation for downtrend."""
        wave_start = 161.8
        wave_end = 100.0    # Down wave
        extension_start = 130.9
        
        extensions = calculate_extension_levels(wave_start, wave_end, extension_start)
        
        assert len(extensions) == 4
        
        # For down wave, extensions should project further down
        hundred_percent = next(e for e in extensions if abs(e['level'] - 1.0) < 0.01)
        wave_length = abs(wave_end - wave_start)  # 61.8 points
        expected_price = extension_start - wave_length * 1.0  # Should go down
        assert abs(hundred_percent['price'] - expected_price) < 0.1

    def test_calculate_fibonacci_levels_integration(self):
        """Test the main fibonacci levels calculation function."""
        import pandas as pd
        
        # Create sample data
        df = pd.DataFrame({
            'high': [120, 140, 160],
            'low': [100, 120, 140],
            'close': [110, 130, 150],
            'timestamp': pd.date_range('2023-01-01', periods=3)
        })
        
        pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 1, 'price': 140.0, 'direction': 'high'},
            {'index': 2, 'price': 120.0, 'direction': 'low'}
        ]
        
        result = calculate_fibonacci_levels(df, pivots)
        
        # Should return dictionary with required keys
        assert 'retracements' in result
        assert 'extensions' in result
        assert 'abc_targets' in result
        
        # Should have some levels calculated
        assert len(result['retracements']) > 0
        assert len(result['extensions']) > 0

    def test_find_fibonacci_confluences(self):
        """Test finding confluent Fibonacci levels."""
        # Create levels that are close to each other
        levels_group1 = [
            {'level': 0.618, 'price': 130.0, 'label': 'Retracement 61.8%'},
            {'level': 1.0, 'price': 131.5, 'label': 'Extension 100%'},  # Close to first level
        ]
        
        levels_group2 = [
            {'level': 0.5, 'price': 125.0, 'label': 'Retracement 50%'},
            {'level': 1.618, 'price': 180.0, 'label': 'Extension 161.8%'},  # Far from others
        ]
        
        confluences = find_fibonacci_confluences([levels_group1, levels_group2], tolerance_pct=2.0)
        
        # Should find one confluence around 130-131.5
        assert len(confluences) >= 1
        
        main_confluence = confluences[0]
        assert main_confluence['count'] == 2
        assert 129 < main_confluence['price'] < 133
        assert main_confluence['strength'] == 2

    def test_filter_relevant_levels(self):
        """Test filtering levels by distance from current price."""
        current_price = 150.0
        
        levels = [
            {'level': 0.236, 'price': 140.0, 'label': '23.6%'},  # 6.7% away - should be included
            {'level': 0.5, 'price': 125.0, 'label': '50%'},     # 16.7% away - should be included  
            {'level': 0.786, 'price': 80.0, 'label': '78.6%'},  # 46.7% away - should be included
            {'level': 1.618, 'price': 300.0, 'label': '161.8%'} # 100% away - should be excluded
        ]
        
        relevant = filter_relevant_levels(levels, current_price, max_distance_pct=50.0)
        
        # Should exclude the 300.0 level but include others
        assert len(relevant) == 3
        
        # Should be sorted by distance
        distances = [level.get('distance_pct', 0) for level in relevant]
        assert distances == sorted(distances), "Levels should be sorted by distance"

    def test_custom_fibonacci_ratios(self):
        """Test using custom Fibonacci ratios."""
        start_price = 100.0
        end_price = 200.0
        custom_ratios = [0.333, 0.667]  # Third and two-thirds
        
        retracements = calculate_retracement_levels(start_price, end_price, ratios=custom_ratios)
        
        assert len(retracements) == 2
        
        # Check custom ratios are applied correctly
        third_level = next(r for r in retracements if abs(r['level'] - 0.333) < 0.01)
        expected_price = end_price - (end_price - start_price) * 0.333
        assert abs(third_level['price'] - expected_price) < 0.01

    def test_edge_case_zero_move(self):
        """Test behavior with zero price move."""
        start_price = 100.0
        end_price = 100.0  # No move
        
        retracements = calculate_retracement_levels(start_price, end_price)
        
        # Should handle gracefully
        assert len(retracements) == 5
        
        # All retracement levels should equal the end price
        for level in retracements:
            assert abs(level['price'] - end_price) < 0.01

    def test_negative_prices_handling(self):
        """Test that negative prices are handled correctly."""
        # This is more of a theoretical test, but important for robustness
        start_price = -50.0
        end_price = -10.0
        
        retracements = calculate_retracement_levels(start_price, end_price)
        
        # Should still calculate levels correctly
        assert len(retracements) == 5
        
        # 50% retracement should be halfway
        fifty_percent = next(r for r in retracements if abs(r['level'] - 0.5) < 0.01)
        expected_price = end_price - (end_price - start_price) * 0.5
        assert abs(fifty_percent['price'] - expected_price) < 0.01

    def test_abc_targets_calculation(self):
        """Test ABC corrective target calculation."""
        from analysis.fib import calculate_abc_targets
        
        # A down from 150 to 120 (30 points), B up to 135, C target from 135
        pivots = [
            {'index': 0, 'price': 150.0, 'direction': 'high'},  # A start
            {'index': 10, 'price': 120.0, 'direction': 'low'},   # A end, B start  
            {'index': 20, 'price': 135.0, 'direction': 'high'}   # B end, C start
        ]
        
        targets = calculate_abc_targets(pivots)
        
        assert len(targets) == 3  # Should have 3 target ratios
        
        # Check 100% target (C = A in length)
        equal_target = next(t for t in targets if abs(t['level'] - 1.0) < 0.01)
        # Wave A was 30 points down, so C should also go 30 points down from B end (135)
        expected_price = 135 - 30  # = 105
        assert abs(equal_target['price'] - 105) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])