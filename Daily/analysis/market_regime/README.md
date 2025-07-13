# Market Regime Detection Module

## Overview

The Market Regime Detection module provides comprehensive analysis of market conditions to identify different market regimes (Bull, Bear, Volatile, Range-bound) and offers actionable insights for position sizing and risk management within the India-TS Daily trading framework.

## Features

### 1. Regime Detection
- **Multiple Regime Types**: STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR, VOLATILE
- **Confidence Scoring**: Each regime detection includes a confidence score
- **Persistence Tracking**: Monitors regime stability over time

### 2. Market Indicators
- **Market Breadth**: Advance/decline ratios, bullish/bearish percentages
- **Momentum Analysis**: Average momentum, extreme movements, distribution
- **Volatility Metrics**: Range-based volatility, pattern-based volatility
- **Sector Analysis**: Sector rotation, momentum by sector
- **Composite Scores**: Market strength index, volatility index, risk score

### 3. Regime Change Detection
- **Signal Analysis**: Detects momentum shifts, breadth changes, volatility expansions
- **Transition Patterns**: Identifies regime transitions with confidence levels
- **Alerts**: Generates alerts for significant market changes

### 4. Position Sizing Recommendations
- **Dynamic Adjustments**: Position size multipliers based on regime
- **Risk Controls**: Stop-loss multipliers adjusted for market conditions
- **Exposure Limits**: Maximum portfolio exposure recommendations
- **Sector Preferences**: Preferred sectors for each regime

### 5. Reporting & Visualization
- **Multiple Formats**: Text, Excel, and HTML reports
- **Visual Dashboards**: Market regime gauges and indicators
- **Historical Analysis**: Regime history tracking and visualization

## Installation

The module is already integrated into the Daily folder structure. No additional installation required.

## Usage

### Basic Usage

```python
from analysis.market_regime import RegimeDetector

# Initialize detector
detector = RegimeDetector()

# Detect current regime
regime, confidence = detector.detect_current_regime()
print(f"Current regime: {regime} (confidence: {confidence:.1%})")

# Get recommendations
recommendations = detector.get_regime_recommendations()
```

### Generating Reports

```python
from analysis.market_regime import RegimeReporter

# Initialize reporter
reporter = RegimeReporter()

# Generate daily report
saved_files = reporter.generate_daily_report(
    regime_data,
    recommendations,
    save_format=['text', 'excel', 'html']
)
```

### Running the Test Script

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/analysis
python test_market_regime.py
```

## Configuration

Configuration is stored in `config/regime_config.json`. Key parameters:

- **Regime Thresholds**: Momentum, breadth, and volatility thresholds for each regime
- **Position Adjustments**: Size multipliers and exposure limits per regime
- **Indicators**: Technical indicator periods and parameters
- **Reporting**: Report formats and visualization options

## Regime Definitions

### STRONG_BULL
- High momentum (>10%)
- Strong breadth (>70% bullish)
- Low volatility (<25%)
- **Action**: Increase position sizes, focus on growth

### BULL
- Positive momentum (>5%)
- Good breadth (>55% bullish)
- Normal volatility (<30%)
- **Action**: Normal positioning, balanced approach

### NEUTRAL
- Sideways momentum (-5% to 5%)
- Mixed breadth (45-55% bullish)
- Moderate volatility (<35%)
- **Action**: Selective positioning, quality focus

### BEAR
- Negative momentum (<-5%)
- Weak breadth (<45% bullish)
- Elevated volatility (<40%)
- **Action**: Reduce exposure, defensive sectors

### STRONG_BEAR
- Very negative momentum (<-10%)
- Very weak breadth (<30% bullish)
- High volatility (<50%)
- **Action**: Minimal exposure, capital preservation

### VOLATILE
- Any momentum level
- High volatility (>40%)
- **Action**: Reduce sizes, wider stops

## Output Files

Reports are saved in `/Daily/reports/market_regime/`:

- `regime_report_YYYYMMDD_HHMMSS.txt` - Text format report
- `regime_report_YYYYMMDD_HHMMSS.xlsx` - Excel format with multiple sheets
- `regime_report_YYYYMMDD_HHMMSS.html` - HTML format for web viewing
- `regime_history_YYYYMMDD.png` - Regime history visualization
- `regime_dashboard_YYYYMMDD_HHMMSS.png` - Comprehensive dashboard

## Integration with Daily Workflow

1. **Morning Analysis**: Run regime detection before market open
2. **Position Sizing**: Use recommendations for new positions
3. **Risk Management**: Apply stop-loss multipliers
4. **Sector Selection**: Focus on preferred sectors
5. **Monitor Alerts**: Watch for regime change signals

## Dependencies

- pandas
- numpy
- matplotlib
- seaborn
- openpyxl
- Standard Daily folder structure and data

## Future Enhancements

1. Integration with ML-Framework for advanced regime detection
2. Real-time regime monitoring
3. Backtesting regime-based strategies
4. API endpoints for regime data
5. Integration with position sizing in place_orders scripts

## Support

For issues or questions, refer to the main India-TS documentation or contact the development team.