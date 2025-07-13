# Market Regime Detection System

A sophisticated market regime detection system that continuously learns and provides actionable trading insights for the India-TS trading framework.

## Overview

The Market Regime Detection System identifies current market conditions and provides dynamic trading recommendations based on seven distinct market regimes:
- **Strong Bull**: Strong uptrend with positive momentum
- **Bull**: Moderate uptrend
- **Neutral**: Sideways or ranging market
- **Bear**: Moderate downtrend
- **Strong Bear**: Strong downtrend with negative momentum
- **Volatile**: High volatility, uncertain direction
- **Crisis**: Extreme market stress conditions

## Features

### 1. Regime Detection Engine
- Multi-factor analysis using price action, volatility, breadth, and momentum
- Confidence scoring for each regime determination
- Real-time regime change detection
- Integration with scanner data for enhanced accuracy

### 2. Adaptive Learning System
- Continuously improves detection accuracy based on outcomes
- Tracks prediction performance and adjusts parameters
- Feature importance ranking that evolves over time
- Machine learning models for enhanced predictions

### 3. Action Recommendation Engine
- Dynamic position sizing based on regime
- Stop-loss adjustments for risk management
- Capital deployment strategies
- Sector rotation recommendations
- Specific actionable trading guidance

## Installation

1. Ensure the Market_Regime folder is in your India-TS directory
2. Install required dependencies:
   ```bash
   pip install pandas numpy scikit-learn
   ```

## Usage

### Basic Regime Detection

```python
from Market_Regime.core.regime_detector import RegimeDetector
from Market_Regime.core.market_indicators import MarketIndicators

# Initialize detector
detector = RegimeDetector()

# Analyze market
regime_analysis = detector.detect_regime(market_data, scanner_data)

print(f"Current Regime: {regime_analysis['regime']}")
print(f"Confidence: {regime_analysis['confidence']:.1%}")
```

### Integration with Daily Trading System

```python
from Market_Regime.integration.daily_integration import DailyTradingIntegration

# Initialize integration
integration = DailyTradingIntegration()

# Run full analysis
analysis = integration.analyze_current_market_regime()

# Check if order should be placed
should_place, reason = integration.should_place_order(ticker, signal)

# Get position size adjustment
size_multiplier = integration.get_position_size_multiplier(ticker, base_size)
```

### Command Line Usage

```bash
# Run regime analysis and update trading parameters
python -m Market_Regime.integration.daily_integration

# Run test suite
python Market_Regime/test_regime_system.py
```

## Configuration

Edit `config/regime_config.json` to customize:

- **Regime thresholds**: Adjust detection sensitivity
- **Learning parameters**: Control adaptive learning behavior
- **Action parameters**: Modify position sizing and risk limits
- **Sector preferences**: Set preferred sectors for each regime
- **Alert settings**: Configure notification preferences

## Integration Points

### 1. Scanner Integration
- Reads scanner results from `Daily/results/`
- Analyzes bullish/bearish percentages
- Tracks sector momentum

### 2. Position Management
- Updates position sizing in order placement
- Adjusts stop losses in watchdog
- Manages portfolio exposure limits

### 3. Risk Management
- Dynamic risk per trade based on regime
- Portfolio heat limits
- Capital preservation in adverse regimes

## Regime-Specific Guidelines

### Strong Bull / Bull
- **Position Sizing**: 100-120% of normal
- **Stop Losses**: Wider, use trailing stops
- **Capital Deployment**: Aggressive on pullbacks
- **Sectors**: Growth, IT, Banking, Auto

### Neutral
- **Position Sizing**: 80% of normal
- **Stop Losses**: Normal width
- **Capital Deployment**: Selective
- **Sectors**: FMCG, Pharma, IT

### Bear / Strong Bear
- **Position Sizing**: 30-50% of normal
- **Stop Losses**: Tighter stops
- **Capital Deployment**: Minimal
- **Sectors**: Defensive only

### Volatile
- **Position Sizing**: 60% of normal
- **Stop Losses**: Very tight
- **Capital Deployment**: Small positions
- **Sectors**: Low beta stocks

### Crisis
- **Position Sizing**: 0% (no new positions)
- **Stop Losses**: Exit all positions
- **Capital Deployment**: None
- **Sectors**: Cash only

## Output Files

The system generates several output files:

- `reports/regime_analysis_latest.json`: Most recent analysis
- `reports/regime_analysis_YYYYMMDD_HHMMSS.json`: Timestamped analyses
- `data/regime_learning.db`: Learning database
- `data/models/`: Trained ML models

## Monitoring and Maintenance

### Daily Tasks
1. Review regime analysis report
2. Check for regime change alerts
3. Verify parameter updates applied

### Weekly Tasks
1. Review regime accuracy statistics
2. Check feature importance rankings
3. Analyze learning suggestions

### Monthly Tasks
1. Review and adjust thresholds if needed
2. Retrain models with latest data
3. Evaluate overall system performance

## Troubleshooting

### Common Issues

1. **Low Confidence Detections**
   - Check if market data is complete
   - Verify scanner data is recent
   - Review indicator calculations

2. **Frequent Regime Changes**
   - Increase confidence thresholds
   - Add regime persistence requirements
   - Check for data quality issues

3. **Learning Not Improving**
   - Ensure outcomes are being recorded
   - Check minimum sample requirements
   - Review feature engineering

## Advanced Features

### Custom Indicators
Add custom indicators by extending `MarketIndicators`:

```python
class CustomIndicators(MarketIndicators):
    def calculate_custom_indicator(self, data):
        # Your custom logic
        return indicator_value
```

### Custom Regimes
Define additional regimes by modifying configuration and detection logic.

### Integration with Other Systems
The modular design allows easy integration with other trading systems and data sources.

## Performance Metrics

The system tracks:
- Regime detection accuracy
- Prediction confidence calibration
- Feature importance evolution
- Trading performance by regime

## Future Enhancements

Planned improvements:
- Deep learning models for regime prediction
- Multi-timeframe regime analysis
- Global market correlation
- Automated threshold optimization
- Real-time streaming updates

## Support

For issues or questions:
1. Check the logs in `Market_Regime/logs/`
2. Review test output from `test_regime_system.py`
3. Examine the latest analysis in `reports/`

## License

Part of the India-TS Trading System