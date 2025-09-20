# ADR-001: Wave Scoring Algorithm Design

**Status**: Accepted  
**Date**: 2023-12-01  
**Authors**: Development Team  
**Reviewers**: Technical Lead  

## Context

The Elliott Wave Analyzer requires a systematic method to evaluate and score the quality of detected wave patterns. Users need confidence metrics to distinguish between high-quality and low-quality wave counts, enabling informed decision-making in their analysis.

## Problem Statement

Elliott Wave analysis is inherently subjective, with multiple valid interpretations possible for the same price data. We need an objective scoring system that:

1. Evaluates adherence to core Elliott Wave rules
2. Measures Fibonacci ratio conformance
3. Provides comparable scores across different patterns
4. Remains deterministic and reproducible

## Decision

We will implement a composite scoring algorithm with the following components:

### Core Algorithm

```python
Score = 100 - (
    w1 * mean_fibonacci_error +
    w2 * overlap_penalties + 
    w3 * channel_deviation +
    w4 * shortest_wave_penalty
)

Where weights are:
w1 = 0.4  # Fibonacci conformance (40%)
w2 = 0.3  # Rule violations (30%) 
w3 = 0.2  # Channel adherence (20%)
w4 = 0.1  # Wave proportion penalties (10%)
```

### Component Details

#### 1. Fibonacci Error Component (40% weight)
Measures how closely wave relationships match expected Fibonacci ratios:

**For Impulse Patterns**:
- Wave 2 to Wave 1: Expected 0.382, 0.5, or 0.618
- Wave 3 to Wave 1: Expected 1.0, 1.618, or 2.618  
- Wave 4 to Wave 3: Expected 0.236, 0.382, or 0.5
- Wave 5 to Wave 1: Expected 0.618, 1.0, or 1.618

**Error Calculation**:
```python
ratio_error = |observed_ratio - ideal_ratio| / ideal_ratio
ratio_error = min(1.0, ratio_error)  # Clamp to [0,1]
```

#### 2. Rule Violation Penalties (30% weight)
Binary penalties for violating core Elliott Wave rules:

**Impulse Rules**:
- Wave 2 retracing >100% of Wave 1: -50 points
- Wave 3 being shortest wave: -30 points
- Wave 4 overlapping Wave 1: -40 points

**Corrective Rules**:
- Wave B retracing <30% or >90% of Wave A: -20 points
- Wave C ratio to Wave A outside 0.7-1.8 range: -15 points

#### 3. Channel Deviation (20% weight)
Evaluates how well waves respect trend channel boundaries (future implementation):
- Measures deviation of Wave 3 and 5 endpoints from projected channels
- Currently simplified to basic trend line analysis

#### 4. Wave Proportion Penalties (10% weight)
Additional penalties for unusual wave proportions:
- Extremely short or long waves relative to pattern average
- Unnatural time duration ratios between waves

### Score Interpretation

| Score Range | Quality | Description |
|-------------|---------|-------------|
| 80-100 | Excellent | Strong rule compliance and Fibonacci conformance |
| 60-79 | Good | Moderate conformance with minor violations |
| 40-59 | Fair | Some rule violations but recognizable pattern |
| 20-39 | Poor | Multiple violations, questionable pattern |
| 0-19 | Invalid | Severe violations, likely false pattern |

## Rationale

### Why This Approach?

1. **Objective Measurement**: Removes subjective bias from pattern evaluation
2. **Educational Value**: Helps users understand what makes a "good" wave count
3. **Weighted Components**: Reflects relative importance of different Elliott Wave principles
4. **Extensible Design**: Can accommodate additional criteria in future versions

### Alternative Approaches Considered

**Machine Learning Approach**: 
- Pros: Could learn from expert labelings
- Cons: Requires large training dataset, less interpretable
- Decision: Rejected for v1.0 due to complexity and interpretability concerns

**Pure Rule-Based Binary**: 
- Pros: Simple, clear pass/fail criteria
- Cons: Loses nuance, doesn't rank acceptable patterns
- Decision: Rejected as too restrictive for practical use

**Expert Weighting Survey**:
- Pros: Community-driven weights
- Cons: Hard to achieve consensus, cultural bias
- Decision: Deferred to future versions with user customization

## Implementation Details

### Code Structure
```python
def calculate_wave_score(pivots, pattern_type):
    fibonacci_score = calculate_fibonacci_conformance(pivots)
    rule_penalty = calculate_rule_violations(pivots, pattern_type)
    channel_score = calculate_channel_adherence(pivots)
    proportion_penalty = calculate_proportion_penalties(pivots)
    
    return max(0, 100 - (
        0.4 * (100 - fibonacci_score) +
        0.3 * rule_penalty +
        0.2 * (100 - channel_score) + 
        0.1 * proportion_penalty
    ))
```

### Testing Strategy
- Unit tests with synthetic data ensuring known patterns score appropriately
- Integration tests with historical data from well-documented wave counts
- Property-based tests ensuring score stability with minor data variations
- Performance tests ensuring scoring completes within acceptable time limits

### Configuration
Weights and thresholds will be configurable via environment variables:
```python
FIBONACCI_WEIGHT = float(os.getenv('FIBONACCI_WEIGHT', 0.4))
RULE_PENALTY_WEIGHT = float(os.getenv('RULE_PENALTY_WEIGHT', 0.3))
CHANNEL_WEIGHT = float(os.getenv('CHANNEL_WEIGHT', 0.2))
PROPORTION_WEIGHT = float(os.getenv('PROPORTION_WEIGHT', 0.1))
```

## Consequences

### Positive
- **Objective Pattern Quality**: Users get quantifiable confidence metrics
- **Educational Tool**: Scoring helps users learn Elliott Wave principles
- **Consistent Results**: Deterministic algorithm ensures reproducible analysis
- **Extensible Framework**: Easy to add new scoring components

### Negative
- **Computational Overhead**: Scoring adds processing time to analysis
- **Potential Over-Optimization**: Users might chase high scores over market reality
- **Simplification**: Complex wave analysis reduced to single number
- **Calibration Challenges**: Weights may need adjustment based on user feedback

### Neutral
- **Subjective to Objective Trade-off**: Gains consistency but loses human intuition
- **Version Evolution**: Scoring algorithm will likely evolve with user feedback

## Monitoring and Success Metrics

### Performance Metrics
- Average scoring time per analysis (target: <100ms)
- Score distribution across real market data
- User engagement with different score ranges

### Quality Metrics  
- Correlation between high-scoring patterns and subsequent market moves
- User feedback on score accuracy and usefulness
- Expert validation of high-scoring patterns

### Improvement Signals
- Patterns that score poorly but are obviously valid (false negatives)
- Patterns that score well but are questionable (false positives)
- User requests for scoring customization or alternative algorithms

## Future Considerations

### Version 1.1 Enhancements
- User-configurable weights for different scoring components
- Additional Fibonacci ratios (0.786, 2.618, 4.236)
- Time-based proportion analysis for wave duration ratios

### Version 2.0 Possibilities
- Machine learning augmentation using expert-labeled data
- Multi-timeframe scoring considering wave degree relationships
- Market regime-aware scoring (trending vs. sideways markets)
- Social validation through community scoring

### Research Areas
- Correlation studies between scores and predictive accuracy
- Cultural/regional differences in wave analysis preferences
- Integration with other technical analysis scoring systems

## References

- Frost, A.J. and Prechter, R.R. "Elliott Wave Principle" (2005)
- Neely, Glenn "Mastering Elliott Wave" (1990)
- Fischer, Jens "Elliott Waves: Trading with the Elliott Wave Theory" (2019)
- Community feedback from TradingView and ElliottWaveTrader forums

---

**Next Review Date**: 2024-03-01  
**Related ADRs**: ADR-002 (Fibonacci Level Calculations), ADR-003 (ZigZag Algorithm)  
**Implementation Status**: Complete in version 1.0.0