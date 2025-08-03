# ML Dashboard Integration Guide

## Overview
The Market Regime Dashboard at port 8080 now includes ML-powered insights and recommendations. This integration provides real-time strategy recommendations based on market breadth conditions.

## Features

### 1. ML Strategy Recommendations
- **Real-time predictions** updated every 5 minutes
- **Color-coded strategy box**: 
  - Green for LONG recommendation
  - Red for SHORT recommendation
  - Gray for NEUTRAL
- **Confidence level** displayed as percentage

### 2. Expected Returns
- **Long PnL**: Expected return if taking long positions
- **Short PnL**: Expected return if taking short positions
- Based on ML model trained on historical data

### 3. Market Conditions
- **Current SMA20 breadth** percentage
- **Breadth trend** (Uptrend/Downtrend/Neutral)
- Real-time updates from market data

### 4. ML-Based Alerts
Dynamic alerts for:
- **Strategy changes**: When ML recommendation switches
- **Extreme conditions**: When breadth <20% or >80%
- **Optimal conditions**: When market enters optimal ranges
  - Long: 55-70% breadth
  - Short: 35-50% breadth

### 5. Actionable Insights
Provides specific actions based on current conditions:
- Position recommendations
- Risk management suggestions
- Market regime guidance

## API Endpoints

### `/api/ml_insights`
Returns comprehensive ML analysis:
```json
{
  "strategy": {
    "recommended": "SHORT",
    "confidence": 0.75,
    "long_expected_pnl": -1.5,
    "short_expected_pnl": 2.3
  },
  "market_conditions": {
    "sma20_breadth": 42.5,
    "breadth_trend": "Downtrend"
  },
  "actionable_insights": [...],
  "risk_assessment": {...}
}
```

### `/api/ml_alerts`
Returns active ML-based alerts:
```json
[
  {
    "type": "optimal_condition",
    "severity": "info",
    "title": "Optimal Short Conditions",
    "message": "Market breadth in optimal range (35-50%) for short positions"
  }
]
```

### `/api/ml_performance`
Returns ML model performance metrics:
```json
{
  "model_version": "20250803",
  "performance": {
    "long_model_r2": 0.78,
    "short_model_r2": 0.83
  }
}
```

## How It Works

### 1. Data Flow
```
Market Data → Breadth Calculation → ML Model → Predictions → Dashboard
     ↑                                              ↓
     └──────── Updates every 5 minutes ←────────────┘
```

### 2. ML Model
- **Algorithm**: GradientBoostingRegressor
- **Features**: SMA20/50 breadth, momentum, volatility
- **Training**: Weekly retraining with latest data
- **Validation**: R² scores > 0.78

### 3. Decision Logic
The ML model considers:
- Current breadth levels
- Breadth momentum (1-day, 5-day changes)
- Historical performance patterns
- Market regime indicators

## Usage Guidelines

### For Traders
1. **Check ML recommendation** before placing trades
2. **Monitor confidence levels** - higher confidence = stronger signal
3. **Review actionable insights** for specific guidance
4. **Watch for alerts** indicating strategy changes

### For Risk Management
1. **Position sizing** based on confidence levels
2. **Stop-loss placement** considering expected PnL
3. **Portfolio allocation** aligned with ML recommendations

### Best Practices
1. **Don't rely solely on ML** - use as one input among many
2. **Monitor model performance** regularly
3. **Understand the limitations** - ML works best in normal market conditions
4. **Review weekly reports** for model updates

## Configuration

### Update Frequency
- ML insights: Every 5 minutes
- Alerts: Real-time
- Model retraining: Weekly (Sundays)

### Customization
Edit `ml_dashboard_integration.py` to:
- Adjust cache timeout (default: 5 minutes)
- Modify alert thresholds
- Change position sizing logic

## Troubleshooting

### ML Service Unavailable
- Check if ML models exist in `Daily/ML/models/`
- Verify Python dependencies installed
- Review logs in `Daily/ML/logs/`

### Incorrect Predictions
- Ensure latest market data available
- Check model last training date
- Verify breadth data accuracy

### Performance Issues
- ML predictions cached for 5 minutes
- Reduce update frequency if needed
- Monitor server resources

## Future Enhancements
1. Add more ML models (LSTM, XGBoost)
2. Include volume analysis
3. Multi-timeframe predictions
4. Backtesting integration
5. Performance attribution