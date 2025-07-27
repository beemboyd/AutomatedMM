# Kelly Criterion Position Sizing in Dashboard

## Overview

The India-TS dashboard at http://localhost:8080 now implements Kelly Criterion for mathematically optimal position sizing. This replaces the previous simple multiplier system with a probabilistic approach based on win rates and payoff ratios.

## What is Kelly Criterion?

The Kelly Criterion is a formula for determining optimal bet size to maximize long-term growth while avoiding ruin:

```
f* = (p × b - q) / b
```

Where:
- `f*` = fraction of capital to wager
- `p` = probability of winning
- `q` = probability of losing (1 - p)
- `b` = odds (win/loss ratio)

## Implementation Details

### Location
- **Module**: `/Daily/Market_Regime/kelly_position_recommender.py`
- **Class**: `KellyPositionRecommender`
- **Integration**: Replaces `PositionRecommender` in `market_regime_analyzer.py`

### Key Components

1. **Win Probability Calculation**
   - Base win rate by regime (65% for strong trends, 50% for choppy)
   - Adjusted by market score (-10% to +10%)
   - Further adjusted by confidence level
   - Final range: 10% to 90%

2. **Win/Loss Ratio**
   - Base ratios: 1.8:1 (strong trends) to 1.0:1 (choppy)
   - Adjusted by volatility (lower volatility = higher ratio)
   - Range: 0.5:1 to 3.0:1

3. **Safety Measures**
   - Kelly Safety Factor: 25% (uses only 1/4 of full Kelly)
   - Maximum position limits by regime
   - Minimum position size: 1%
   - Maximum total exposure: 100%

4. **Breadth Integration**
   - Poor breadth (<30%): Kelly × 0.5
   - Strong breadth (>70%): Kelly × 1.2

## Dashboard Display

### Position Sizing Section Shows:

```
Kelly Criterion Position Sizing
┌─────────────────┬─────────────────┐
│ Kelly %: 15.99% │ Expected Value: │
│                 │ +115.1%         │
├─────────────────┼─────────────────┤
│ Win Probability:│ Win/Loss Ratio: │
│ 76.8%          │ 1.8:1           │
├─────────────────┼─────────────────┤
│ Max Positions:  │ Stop Loss:      │
│ 6              │ 4.0%            │
└─────────────────┴─────────────────┘
Direction: SHORT
```

### Color Coding
- **Green**: Favorable conditions (Kelly > 15%, Win Prob > 60%, EV > 0)
- **Yellow**: Moderate conditions (Kelly 5-15%, Win Prob 50-60%)
- **Red**: Unfavorable conditions (Kelly < 5%, Win Prob < 50%, EV < 0)

## API Response Format

```json
{
  "position_recommendations": {
    "kelly_fraction": 0.1599,
    "position_size_percent": 15.99,
    "win_probability": 0.768,
    "win_loss_ratio": 1.8,
    "expected_value": 1.151,
    "position_size_multiplier": 3.2,
    "max_positions": 6,
    "total_exposure_limit": 0.96,
    "stop_loss_percent": 4.0,
    "stop_loss_multiplier": 2.0,
    "risk_per_trade": 0.0064,
    "preferred_direction": "short",
    "confidence_level": "high",
    "volatility_regime": "normal",
    "kelly_components": {
      "raw_kelly": 0.6397,
      "safety_factor": 0.25,
      "regime_limit": 0.25,
      "breadth_adjustment": 1.0
    },
    "specific_guidance": [...]
  }
}
```

## Tuning Parameters

### In `kelly_position_recommender.py`:

```python
# Regime-specific parameters
self.regime_parameters = {
    'strong_uptrend': {
        'base_win_rate': 0.65,      # Tune based on actual win rate
        'win_loss_ratio': 1.8,       # Tune based on actual P&L
        'max_kelly_fraction': 0.25,  # Maximum position size
        'confidence_weight': 0.3     # How much confidence affects win rate
    },
    ...
}

# Global safety parameters
self.kelly_safety_factor = 0.25  # Conservative: use 25% of full Kelly
self.max_total_exposure = 1.0    # Maximum 100% exposure
self.min_position_size = 0.01    # Minimum 1% position
```

## P&L-Based Tuning Guide

### 1. Collect Data (Minimum 30 days)
```python
# Track for each regime:
- Actual win rate
- Average win size
- Average loss size
- Maximum drawdown
```

### 2. Update Base Win Rates
```python
# If actual win rate differs from model:
'base_win_rate': actual_win_rate  # Update in regime_parameters
```

### 3. Adjust Win/Loss Ratios
```python
# Calculate from P&L:
win_loss_ratio = avg_win_size / avg_loss_size
```

### 4. Tune Safety Factor
```python
# If experiencing large drawdowns:
self.kelly_safety_factor = 0.15  # More conservative

# If results are too conservative:
self.kelly_safety_factor = 0.35  # More aggressive
```

### 5. Adjust Confidence Weights
```python
# If confidence doesn't correlate with outcomes:
'confidence_weight': 0.2  # Reduce impact

# If confidence strongly predicts outcomes:
'confidence_weight': 0.5  # Increase impact
```

## Monitoring & Adjustment

### Key Metrics to Track:
1. **Actual vs Predicted Win Rate** by regime
2. **Actual vs Predicted Win/Loss Ratio** by regime
3. **Maximum Drawdown** vs Kelly recommendations
4. **Sharpe Ratio** by position size bucket

### Adjustment Schedule:
- **Weekly**: Review position size effectiveness
- **Monthly**: Update win rates and ratios
- **Quarterly**: Major parameter adjustments

### Warning Signs:
- Actual win rate < predicted by >10%
- Drawdowns exceeding 2× expected
- Sharpe ratio declining with larger positions

## Integration with Trading System

### For Manual Trading:
```python
# Use dashboard recommendations directly
position_size = account_value * kelly_percent
```

### For Automated Trading:
```python
# Import and use the recommender
from kelly_position_recommender import KellyPositionRecommender

recommender = KellyPositionRecommender()
recs = recommender.get_recommendations(
    regime='uptrend',
    confidence=0.75,
    volatility={'volatility_score': 0.5},
    market_score=0.3,
    breadth_score=0.6
)

position_size = capital * recs['kelly_fraction']
```

## Future Enhancements

1. **Regime-Specific P&L Tracking**
   - Automatic parameter updates based on results
   - Regime transition analysis

2. **Multi-Asset Kelly**
   - Correlation-adjusted position sizing
   - Portfolio-level Kelly optimization

3. **Dynamic Safety Factor**
   - Increase during drawdowns
   - Decrease during winning streaks

4. **Machine Learning Integration**
   - Learn optimal parameters from historical data
   - Predict regime-specific win rates

## Troubleshooting

### Issue: Shows 0% Kelly
- Check if market regime is determined
- Verify scanner results are recent
- Check for breadth data availability

### Issue: Recommendations seem too aggressive
- Reduce `kelly_safety_factor` to 0.15
- Lower `max_kelly_fraction` in regime parameters
- Check if volatility adjustment is working

### Issue: Not matching actual P&L
- Update base win rates from actual data
- Recalculate win/loss ratios
- Consider regime classification accuracy

## Conclusion

The Kelly Criterion implementation provides a mathematical framework for position sizing that:
- Maximizes long-term growth
- Prevents ruin through conservative sizing
- Adapts to market conditions
- Integrates with existing regime analysis

Regular tuning based on actual P&L will improve accuracy and profitability over time.