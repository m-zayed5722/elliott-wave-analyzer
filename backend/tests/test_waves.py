"""
Unit tests for Elliott Wave pattern recognition and scoring.
"""

import pytest
import pandas as pd
from analysis.waves import (
    analyze_waves, 
    check_impulse_rules, 
    check_corrective_rules,
    calculate_fibonacci_score,
    generate_wave_labels,
    calculate_invalidation_levels
)


class TestWaveAnalysis:
    """Test Elliott Wave analysis functionality."""

    def create_impulse_pattern(self):
        """Create a synthetic 5-wave impulse pattern."""
        return [
            {'index': 0, 'price': 100.0, 'direction': 'low'},    # Wave 1 start
            {'index': 10, 'price': 120.0, 'direction': 'high'},  # Wave 1 end
            {'index': 20, 'price': 110.0, 'direction': 'low'},   # Wave 2 end (50% retracement)
            {'index': 30, 'price': 145.0, 'direction': 'high'},  # Wave 3 end (1.618 x Wave 1)
            {'index': 40, 'price': 130.0, 'direction': 'low'},   # Wave 4 end (38% retracement)
            {'index': 50, 'price': 150.0, 'direction': 'high'}   # Wave 5 end
        ]

    def create_corrective_pattern(self):
        """Create a synthetic ABC corrective pattern."""
        return [
            {'index': 0, 'price': 150.0, 'direction': 'high'},   # Wave A start
            {'index': 10, 'price': 120.0, 'direction': 'low'},   # Wave A end
            {'index': 20, 'price': 135.0, 'direction': 'high'},  # Wave B end (50% retracement)
            {'index': 30, 'price': 110.0, 'direction': 'low'}    # Wave C end (equal to A)
        ]

    def test_impulse_rule_validation_success(self):
        """Test that a valid impulse pattern passes rule validation."""
        pivots = self.create_impulse_pattern()
        
        is_valid, score, violations = check_impulse_rules(pivots)
        
        assert is_valid, f"Valid impulse should pass validation. Violations: {violations}"
        assert score > 50, f"Valid impulse should have score > 50, got {score}"
        assert len(violations) == 0, f"Valid impulse should have no violations, got: {violations}"

    def test_impulse_rule_wave2_violation(self):
        """Test that Wave 2 retracing beyond 100% of Wave 1 is caught."""
        # Create invalid pattern where Wave 2 retraces beyond Wave 1 start
        invalid_pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 10, 'price': 120.0, 'direction': 'high'},
            {'index': 20, 'price': 95.0, 'direction': 'low'},    # Retraces beyond start of Wave 1
            {'index': 30, 'price': 145.0, 'direction': 'high'},
            {'index': 40, 'price': 130.0, 'direction': 'low'}
        ]
        
        is_valid, score, violations = check_impulse_rules(invalid_pivots)
        
        assert not is_valid, "Invalid impulse with Wave 2 > 100% should fail validation"
        assert any("Wave 2" in violation for violation in violations), "Should catch Wave 2 violation"

    def test_impulse_rule_wave3_shortest_violation(self):
        """Test that Wave 3 being shortest is caught."""
        # Create pattern where Wave 3 is shorter than Wave 1 and Wave 5
        invalid_pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 10, 'price': 130.0, 'direction': 'high'},  # Wave 1: 30 points
            {'index': 20, 'price': 115.0, 'direction': 'low'},
            {'index': 30, 'price': 125.0, 'direction': 'high'},  # Wave 3: only 10 points (shortest!)
            {'index': 40, 'price': 110.0, 'direction': 'low'},
            {'index': 50, 'price': 135.0, 'direction': 'high'}   # Wave 5: 25 points
        ]
        
        is_valid, score, violations = check_impulse_rules(invalid_pivots)
        
        assert not is_valid, "Invalid impulse with shortest Wave 3 should fail validation"
        assert any("Wave 3" in violation and "shortest" in violation for violation in violations)

    def test_impulse_rule_wave4_overlap_violation(self):
        """Test that Wave 4 overlapping Wave 1 territory is caught."""
        # Create uptrend pattern where Wave 4 goes below Wave 1 end
        invalid_pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 10, 'price': 120.0, 'direction': 'high'},  # Wave 1 end
            {'index': 20, 'price': 110.0, 'direction': 'low'},
            {'index': 30, 'price': 145.0, 'direction': 'high'},
            {'index': 40, 'price': 115.0, 'direction': 'low'}    # Wave 4 below Wave 1 end (overlap!)
        ]
        
        is_valid, score, violations = check_impulse_rules(invalid_pivots)
        
        assert not is_valid, "Invalid impulse with Wave 4 overlap should fail validation"
        assert any("Wave 4" in violation and "overlap" in violation for violation in violations)

    def test_corrective_rule_validation(self):
        """Test ABC corrective pattern validation."""
        pivots = self.create_corrective_pattern()
        
        is_valid, score, violations = check_corrective_rules(pivots)
        
        assert is_valid, f"Valid corrective should pass validation. Violations: {violations}"
        assert score > 50, f"Valid corrective should have score > 50, got {score}"

    def test_fibonacci_score_calculation(self):
        """Test Fibonacci ratio scoring for impulse patterns."""
        # Create pattern with good Fibonacci relationships
        good_fib_pivots = [
            {'index': 0, 'price': 100.0, 'direction': 'low'},
            {'index': 10, 'price': 120.0, 'direction': 'high'},  # Wave 1: 20 points
            {'index': 20, 'price': 110.0, 'direction': 'low'},   # Wave 2: 10 points (50% of Wave 1)
            {'index': 30, 'price': 142.4, 'direction': 'high'},  # Wave 3: 32.4 points (1.618 x Wave 1)
            {'index': 40, 'price': 127.6, 'direction': 'low'},   # Wave 4: 14.8 points (38.2% of Wave 3)
            {'index': 50, 'price': 140.0, 'direction': 'high'}   # Wave 5: 12.4 points (62% of Wave 1)
        ]
        
        fib_score = calculate_fibonacci_score(good_fib_pivots)
        
        assert fib_score > 60, f"Good Fibonacci ratios should score > 60, got {fib_score}"

    def test_wave_label_generation_impulse(self):
        """Test wave label generation for impulse patterns."""
        pivots = self.create_impulse_pattern()
        
        labels = generate_wave_labels(pivots, 'impulse')
        
        assert len(labels) == 5, f"Impulse should generate 5 labels, got {len(labels)}"
        
        expected_waves = ['1', '2', '3', '4', '5']
        actual_waves = [label.wave for label in labels]
        
        assert actual_waves == expected_waves, f"Expected {expected_waves}, got {actual_waves}"

    def test_wave_label_generation_corrective(self):
        """Test wave label generation for corrective patterns."""
        pivots = self.create_corrective_pattern()
        
        labels = generate_wave_labels(pivots, 'corrective')
        
        assert len(labels) == 3, f"Corrective should generate 3 labels, got {len(labels)}"
        
        expected_waves = ['A', 'B', 'C']
        actual_waves = [label.wave for label in labels]
        
        assert actual_waves == expected_waves, f"Expected {expected_waves}, got {actual_waves}"

    def test_analyze_waves_integration(self):
        """Test the main analyze_waves function integration."""
        # Create dummy DataFrame
        df = pd.DataFrame({
            'high': [120, 145, 150],
            'low': [100, 110, 130],
            'close': [115, 135, 140]
        })
        
        pivots = self.create_impulse_pattern()
        
        result = analyze_waves(df, pivots)
        
        # Should return both primary and alternate analyses
        assert 'primary' in result
        assert 'alternate' in result
        
        # Both should have required attributes
        for key in ['primary', 'alternate']:
            wave_count = result[key]
            assert hasattr(wave_count, 'labels')
            assert hasattr(wave_count, 'score')
            assert hasattr(wave_count, 'pattern_type')
            assert hasattr(wave_count, 'summary')
            
            assert isinstance(wave_count.score, (int, float))
            assert 0 <= wave_count.score <= 100

    def test_invalidation_levels_impulse(self):
        """Test invalidation level calculation for impulse patterns."""
        from analysis.waves import WaveCount, WaveLabel
        
        pivots = self.create_impulse_pattern()
        
        # Create a mock wave count
        labels = [
            WaveLabel(index=0, wave='1', price=100.0),
            WaveLabel(index=10, wave='2', price=120.0),
            WaveLabel(index=20, wave='3', price=110.0),
            WaveLabel(index=30, wave='4', price=145.0),
            WaveLabel(index=40, wave='5', price=130.0)
        ]
        
        wave_count = WaveCount(
            labels=labels,
            score=80.0,
            pattern_type='impulse',
            summary="Test impulse"
        )
        
        invalidation = calculate_invalidation_levels(wave_count, pivots)
        
        assert 'price' in invalidation
        assert 'reason' in invalidation
        assert isinstance(invalidation['price'], (int, float))
        assert isinstance(invalidation['reason'], str)

    def test_insufficient_data_handling(self):
        """Test behavior with insufficient pivot data."""
        df = pd.DataFrame({
            'high': [100, 101],
            'low': [99, 100],
            'close': [100, 100.5]
        })
        
        # Only one pivot
        minimal_pivots = [{'index': 0, 'price': 100.0, 'direction': 'low'}]
        
        result = analyze_waves(df, minimal_pivots)
        
        # Should handle gracefully without errors
        assert 'primary' in result
        assert 'alternate' in result
        
        # Scores should be low for insufficient data
        assert result['primary'].score <= 20
        assert result['alternate'].score <= 20

    def test_score_stability(self):
        """Test that wave scores are relatively stable with small data changes."""
        base_pivots = self.create_impulse_pattern()
        
        # Create slightly modified versions
        modified_pivots = base_pivots.copy()
        modified_pivots[-1]['price'] = 151.0  # Small change to last price
        
        df = pd.DataFrame({
            'high': [120, 145, 150],
            'low': [100, 110, 130], 
            'close': [115, 135, 140]
        })
        
        base_result = analyze_waves(df, base_pivots)
        modified_result = analyze_waves(df, modified_pivots)
        
        # Scores should be within reasonable range of each other
        score_diff = abs(base_result['primary'].score - modified_result['primary'].score)
        assert score_diff <= 10, f"Score should be stable, difference was {score_diff}"


if __name__ == "__main__":
    # Run tests if executed directly  
    pytest.main([__file__, "-v"])