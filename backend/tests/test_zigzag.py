"""
Unit tests for ZigZag pivot detection algorithm.
"""

import pytest
import pandas as pd
import numpy as np
from analysis.zigzag import detect_zigzag, validate_zigzag, calculate_pivot_strength


class TestZigZagDetection:
    """Test ZigZag pivot detection functionality."""

    def test_simple_zigzag_detection(self):
        """Test ZigZag detection on a simple synthetic series."""
        # Create a simple series with known peaks and troughs
        data = {
            'high': [100, 105, 110, 108, 105, 102, 95, 98, 103, 108, 112, 109],
            'low':  [98,  103, 107, 105, 102, 98,  92, 95,  100, 105, 109, 106],
            'open': [99,  104, 108, 107, 103, 100, 93, 96,  101, 106, 110, 107],
            'close':[104, 108, 109, 106, 101, 97,  94, 97,  102, 107, 111, 108],
            'volume': [1000] * 12
        }
        df = pd.DataFrame(data)
        
        # Use 3% threshold to catch the main swings
        pivots = detect_zigzag(df, pct_threshold=3.0)
        
        # Should detect at least a few pivots
        assert len(pivots) >= 2
        
        # Check that pivots alternate between high and low
        directions = [p['direction'] for p in pivots]
        for i in range(1, len(directions)):
            assert directions[i] != directions[i-1], "Pivots should alternate between high and low"
        
        # Check that all pivot prices are reasonable
        for pivot in pivots:
            assert 90 <= pivot['price'] <= 115, f"Pivot price {pivot['price']} is outside expected range"

    def test_no_pivots_flat_series(self):
        """Test that flat series produces minimal pivots."""
        data = {
            'high': [100.1] * 10,
            'low':  [99.9] * 10,
            'open': [100.0] * 10,
            'close':[100.0] * 10,
            'volume': [1000] * 10
        }
        df = pd.DataFrame(data)
        
        pivots = detect_zigzag(df, pct_threshold=2.0)
        
        # Should produce very few or no pivots for a flat series
        assert len(pivots) <= 2

    def test_threshold_sensitivity(self):
        """Test that different thresholds produce different numbers of pivots."""
        data = {
            'high': [100, 102, 105, 103, 106, 104, 108, 105, 110, 107],
            'low':  [98,  100, 103, 101, 104, 102, 106, 103, 108, 105],
            'open': [99,  101, 104, 102, 105, 103, 107, 104, 109, 106],
            'close':[101, 103, 104, 103, 105, 104, 107, 105, 109, 107],
            'volume': [1000] * 10
        }
        df = pd.DataFrame(data)
        
        # Lower threshold should detect more pivots
        pivots_1pct = detect_zigzag(df, pct_threshold=1.0)
        pivots_3pct = detect_zigzag(df, pct_threshold=3.0)
        
        assert len(pivots_1pct) >= len(pivots_3pct), "Lower threshold should detect equal or more pivots"

    def test_validate_zigzag_removes_small_moves(self):
        """Test that validation removes insignificant pivots."""
        # Create test pivots with one small move
        test_pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 5, 'price': 105.0, 'direction': 'high'},   # 5% move - good
            {'index': 10, 'price': 104.5, 'direction': 'low'},   # 0.5% move - should be filtered
            {'index': 15, 'price': 110.0, 'direction': 'high'}   # 5.2% move - good
        ]
        
        # Create dummy DataFrame
        df = pd.DataFrame({
            'high': [105, 110],
            'low': [100, 104.5],
            'close': [102, 108]
        })
        
        validated_pivots = validate_zigzag(df, test_pivots, min_move_pct=2.0)
        
        # Should remove the small 0.5% move
        assert len(validated_pivots) < len(test_pivots)
        
        # Remaining pivots should have significant moves
        for i in range(1, len(validated_pivots)):
            prev_price = validated_pivots[i-1]['price']
            curr_price = validated_pivots[i]['price']
            move_pct = abs(curr_price - prev_price) / prev_price * 100
            assert move_pct >= 1.8  # Allow small tolerance

    def test_calculate_pivot_strength(self):
        """Test pivot strength calculation."""
        # Create test data where index 2 is clearly the highest point
        data = {
            'high': [100, 102, 110, 103, 101],  # Index 2 is clearly highest
            'low':  [98,  100, 108, 101, 99],
            'close':[99,  101, 109, 102, 100]
        }
        df = pd.DataFrame(data)
        
        high_pivot = {'index': 2, 'price': 110, 'direction': 'high'}
        strength = calculate_pivot_strength(df, high_pivot, lookback=2)
        
        # Should have high strength since it's clearly the highest point
        assert strength > 50, f"High pivot strength should be > 50, got {strength}"
        
        # Test a less significant pivot
        weak_pivot = {'index': 1, 'price': 102, 'direction': 'high'}
        weak_strength = calculate_pivot_strength(df, weak_pivot, lookback=2)
        
        # Should have lower strength
        assert weak_strength < strength, "Weaker pivot should have lower strength score"

    def test_edge_case_insufficient_data(self):
        """Test behavior with insufficient data."""
        # Very small dataset
        data = {
            'high': [100, 101],
            'low': [99, 100],
            'close': [100, 100.5],
            'volume': [1000, 1000]
        }
        df = pd.DataFrame(data)
        
        pivots = detect_zigzag(df, pct_threshold=1.0)
        
        # Should handle gracefully without errors
        assert isinstance(pivots, list)

    def test_pivot_indices_valid(self):
        """Test that pivot indices are within the valid range of the dataset."""
        data = {
            'high': [100 + i + np.sin(i/2)*5 for i in range(20)],
            'low':  [98 + i + np.sin(i/2)*5 for i in range(20)],
            'open': [99 + i + np.sin(i/2)*5 for i in range(20)],
            'close':[99.5 + i + np.sin(i/2)*5 for i in range(20)],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        pivots = detect_zigzag(df, pct_threshold=2.0)
        
        for pivot in pivots:
            assert 0 <= pivot['index'] < len(df), f"Pivot index {pivot['index']} is out of bounds"
            
            # Verify the price matches the actual data at that index
            if pivot['direction'] == 'high':
                assert abs(pivot['price'] - df.iloc[pivot['index']]['high']) < 0.01
            else:
                assert abs(pivot['price'] - df.iloc[pivot['index']]['low']) < 0.01


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])