# ML-Based Breadth Optimization Module

## Overview
This ML module continuously learns and optimizes trading strategies based on market breadth conditions. It uses historical performance data to predict optimal long/short strategies.

## Components

### 1. `breadth_optimization_model.py`
- Main ML model using GradientBoostingRegressor
- Trains separate models for long and short strategies
- Features include:
  - SMA20/SMA50 breadth percentages
  - Breadth momentum (1-day, 3-day, 5-day rate of change)
  - Breadth volatility metrics
  - Trend indicators
  - Days since extremes

### 2. `breadth_strategy_predictor.py`
- Real-time strategy predictions
- Integrates with dashboard
- Provides:
  - Current strategy recommendation (LONG/SHORT)
  - Expected PnL for both strategies
  - Confidence levels
  - Market condition analysis

### 3. `retrain_breadth_model.py`
- Weekly retraining script
- Collects actual performance data
- Updates models with new patterns
- Generates performance reports

## Key Features

### Model Performance
- Long Model R²: 0.78
- Short Model R²: 0.83
- Top feature: SMA20 breadth percentage (93.7% importance for long, 89.1% for short)

### Optimal Conditions (ML-Validated)
**Long Strategy:**
- Best: SMA20 breadth 55-70%
- Avoid: Below 45% or above 70%

**Short Strategy:**
- Best: SMA20 breadth 35-50%
- Good: 25-35%
- Avoid: Below 20% or above 50%

## Usage

### Get Current Recommendation
```python
from breadth_strategy_predictor import BreadthStrategyPredictor

predictor = BreadthStrategyPredictor()
recommendation = predictor.get_strategy_recommendation()
print(f"Strategy: {recommendation['recommended_strategy']}")
print(f"Confidence: {recommendation['confidence']}")
```

### Weekly Retraining
```bash
python3 retrain_breadth_model.py
```

## Integration Points

1. **Dashboard Integration**: The predictor provides HTML widgets for real-time display
2. **Trading System**: Can be integrated with order placement logic
3. **Risk Management**: Confidence levels can adjust position sizing

## Future Enhancements

1. Include actual ticker performance data instead of simulated
2. Add more market regime indicators
3. Implement ensemble models for better predictions
4. Add backtesting validation before model updates
5. Create alerts for significant strategy changes

## Model Files
- Models saved in: `Daily/ML/models/`
- Training logs in: `Daily/ML/logs/`
- Weekly reports in: `Daily/ML/reports/`