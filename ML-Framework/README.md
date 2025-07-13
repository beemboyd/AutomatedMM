# Market Regime Detection ML Framework

## Overview

This ML Framework implements an advanced market regime detection system that combines traditional technical analysis with machine learning clustering algorithms. The system identifies different market environments and provides actionable recommendations for position sizing and risk management.

## Architecture

### Core Components

1. **Clustering-based Regime Detector** (`models/clustering/cluster_regime_detector.py`)
   - Implements multiple clustering algorithms (K-Means, GMM, DBSCAN, Hierarchical)
   - Ensemble approach for robust regime identification
   - Identifies regimes: STRONG_BULLISH, WEAK_BULLISH, NEUTRAL, WEAK_BEARISH, STRONG_BEARISH, HIGH_VOLATILITY, CRISIS

2. **Feature Engineering Pipeline** (`features/feature_pipeline.py`)
   - Comprehensive feature extraction from OHLCV data
   - Technical indicators, statistical features, market microstructure
   - Feature selection and dimensionality reduction

3. **Market Regime ML Model** (`models/market_regime_ml.py`)
   - Combines traditional and ML-based approaches
   - Confidence scoring and regime persistence tracking
   - Position sizing and stop loss recommendations

4. **Daily Analysis Script** (`scripts/daily_regime_analysis.py`)
   - Automated daily regime detection
   - Report generation (JSON, CSV, TXT formats)
   - Integration with existing trading system

5. **Risk Integration** (`integration/regime_risk_integration.py`)
   - Bridges ML regime detection with risk management
   - Dynamic position sizing based on market conditions
   - Portfolio exposure management

## Market Regimes

The system identifies 7 distinct market regimes:

1. **STRONG_BULLISH**: Clear uptrend with strong momentum
2. **WEAK_BULLISH**: Mild uptrend or early bull market
3. **NEUTRAL**: Sideways market with no clear direction
4. **WEAK_BEARISH**: Mild downtrend or early bear market
5. **STRONG_BEARISH**: Clear downtrend with strong negative momentum
6. **HIGH_VOLATILITY**: Choppy market with large price swings
7. **CRISIS**: Extreme market conditions requiring maximum caution

## Features Used

### Price-based Features
- Moving averages (SMA, EMA) with multiple periods
- Price position relative to moving averages
- Trend strength using linear regression

### Volatility Features
- Historical volatility
- Parkinson volatility (using high-low range)
- Garman-Klass volatility
- Volatility of volatility

### Technical Indicators
- RSI, MACD, Bollinger Bands
- ATR, Stochastic, ADX, CCI

### Market Microstructure
- Bid-ask spread proxies
- Volume patterns
- Price-volume correlations

### Statistical Features
- Return distribution moments (skewness, kurtosis)
- Autocorrelation patterns
- Hurst exponent for trend persistence

## Usage

### Daily Regime Analysis

Run the daily analysis script:

```bash
python ML-Framework/scripts/daily_regime_analysis.py
```

This will:
- Analyze market indices (SMALLCAP, MIDCAP, TOP100CASE)
- Detect regimes for portfolio stocks
- Generate position sizing recommendations
- Create risk management reports

### Integration with Trading System

```python
from ML_Framework.integration.regime_risk_integration import RegimeRiskIntegration

# Initialize
regime_risk = RegimeRiskIntegration()

# Get regime-adjusted position size
position_info = regime_risk.calculate_regime_adjusted_position_size(
    ticker='RELIANCE',
    base_position_size=100000,
    entry_price=2500,
    account_value=1000000
)

# Get regime-adjusted stop loss
stop_info = regime_risk.calculate_regime_adjusted_stop_loss(
    ticker='RELIANCE',
    entry_price=2500,
    position_type='LONG',
    atr=50
)
```

## Position Sizing Adjustments

Position sizes are adjusted based on detected market regime:

| Regime | Position Size Factor | Max Position % |
|--------|---------------------|----------------|
| STRONG_BULLISH | 1.2x | 10% |
| WEAK_BULLISH | 1.0x | 8% |
| NEUTRAL | 0.8x | 7% |
| WEAK_BEARISH | 0.6x | 5% |
| STRONG_BEARISH | 0.4x | 3% |
| HIGH_VOLATILITY | 0.5x | 3% |
| CRISIS | 0.2x | 2% |

## Stop Loss Multipliers

Stop losses are adjusted using ATR multipliers based on regime:

| Regime | Long Multiplier | Short Multiplier |
|--------|----------------|------------------|
| STRONG_BULLISH | 2.0x | 1.2x |
| WEAK_BULLISH | 1.8x | 1.5x |
| NEUTRAL | 1.5x | 1.5x |
| WEAK_BEARISH | 1.2x | 1.8x |
| STRONG_BEARISH | 1.0x | 2.0x |
| HIGH_VOLATILITY | 2.5x | 2.5x |
| CRISIS | 3.0x | 3.0x |

## Output Reports

The system generates multiple report formats:

1. **Summary Report** (`regime_summary_YYYYMMDD.txt`)
   - Market outlook and confidence
   - Index regime summary
   - Risk alerts and opportunities

2. **Position Report** (`position_details_YYYYMMDD.csv`)
   - Detailed position-by-position analysis
   - Recommended actions and adjustments

3. **Risk Report** (`risk_report_YYYYMMDD.txt`)
   - Overall market risk assessment
   - Position sizing recommendations
   - Stop loss adjustments by regime

4. **JSON Report** (`regime_analysis_YYYYMMDD.json`)
   - Complete analysis data for automated systems

## Configuration

Edit `config/ml_config.json` to customize:
- Regime detection parameters
- Position adjustment factors
- Stop loss multipliers
- Risk management limits
- Feature engineering parameters

## Future Enhancements

1. **Hidden Markov Models** for regime transition probabilities
2. **LSTM networks** for sequential regime prediction
3. **Reinforcement learning** for optimal position sizing
4. **Real-time regime detection** with streaming data
5. **Multi-asset correlation** analysis
6. **Sentiment integration** from news and social media

## Dependencies

- pandas, numpy for data manipulation
- scikit-learn for clustering algorithms
- talib for technical indicators
- joblib for model persistence

## Backtesting

To backtest regime-based strategies:

```python
# Use the existing backtesting framework with regime filter
python BT/backtest.py --strategy regime_filtered --mode portfolio
```

The regime detection can be integrated into any existing strategy by adding regime filters to entry/exit logic.