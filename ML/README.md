# ML Trading Tools - Market Regime Analysis and Dynamic Stop Loss

This module provides advanced machine learning tools for market analysis, regime detection, and dynamic stop loss management for trading systems.

## Key Features

- **Market Regime Detection**: Identifies the current market environment (trending, ranging, volatility conditions)
- **Portfolio-Aware Analysis**: Analyzes each stock in your portfolio relative to its market reference
- **ATR-based Stop Loss Calculation**: Dynamically adjusts stop losses based on volatility and market regime
- **Machine Learning Models**: Uses time series analysis and statistical pattern recognition
- **Integration with Trading System**: Seamlessly integrates with your existing positions
- **Detailed Visualization**: Creates comprehensive HTML reports with charts and metrics
- **CNC Position Recommendations**: Specialized recommendations for delivery positions

## Directory Structure

```
ML/
├── data/                  # Data storage for ML models
├── models/                # ML model implementations
│   └── dynamic_stop_loss.py  # Core stop loss calculation algorithm
├── utils/                 # Utility modules
│   ├── atr_calculator.py  # ATR calculation utilities
│   └── market_regime.py   # Market regime detection algorithms
├── tests/                 # Testing framework
│   └── test_dynamic_stop_loss.py  # Test cases for stop loss system
├── results/               # Analysis results, plots and HTML reports
├── integration.py         # Integration with trading system
├── analyze_market_regimes.py  # Main script for market regime analysis
├── cnc_stop_loss_recommendation.py  # CNC position stop loss tools
├── example.py             # Usage examples
└── README.md              # This file
```

## Main Tools

### 1. Market Regime Analysis

The `analyze_market_regimes.py` script provides comprehensive market regime detection and analysis:

```bash
# Run the market regime analysis for your portfolio positions
python ML/analyze_market_regimes.py
```

This script:
- Automatically detects all positions in your portfolio from trading_state.json
- Analyzes each position against appropriate market references (SMALLCAP, MIDCAP, TOP100CASE)
- Generates detailed reports with regime classifications and stop loss recommendations
- Creates visualization charts for each position showing regime transitions
- Produces an HTML dashboard with all analysis results

#### Market Regime Classifications

The system identifies these market regimes:

- **Trending Bullish**: Strong upward price movement, positive momentum
- **Trending Bearish**: Strong downward price movement, negative momentum
- **Ranging Low Volatility**: Sideways movement with low volatility
- **Ranging High Volatility**: Sideways movement with high volatility
- **Transitioning**: Changing between regimes, mixed signals

### 2. Dynamic Stop Loss System

The dynamic stop loss system (`models/dynamic_stop_loss.py`) provides adaptive stop loss recommendations based on:

- Current market regime for the stock
- Stock's volatility (ATR-based)
- Position type (LONG/SHORT)

#### Stop Loss Strategies by Regime

Different market regimes require different stop loss approaches:

- **Trending Bullish**: Wider stops for long positions (2.0x ATR), tighter for shorts (1.5x ATR)
- **Trending Bearish**: Tighter stops for long positions (1.5x ATR), wider for shorts (2.0x ATR)
- **Ranging Low Volatility**: Medium stops (1.5x ATR) for both directions
- **Ranging High Volatility**: Wider stops (2.5x ATR) for both directions
- **Transitioning Markets**: Medium stops (2.0x ATR) for both directions

### 3. CNC Stop Loss Recommendations

The `cnc_stop_loss_recommendation.py` script provides specialized stop loss recommendations for delivery positions:

```bash
# Get CNC-specific stop loss recommendations
python ML/cnc_stop_loss_recommendation.py
```

## Machine Learning Approach

The market regime detection uses multiple approaches:

1. **Time Series Analysis**:
   - Moving average relationships and slopes
   - Volatility patterns (ATR-based)
   - Trend strength metrics

2. **Statistical Pattern Recognition**:
   - Hurst exponent calculation to identify trending vs. mean-reverting behavior
   - Volatility clustering analysis
   - Price structure classification

3. **Technical Analysis Factors**:
   - Price action relative to moving averages
   - Volume characteristics during price movements
   - Support/resistance level behavior

## Usage Examples

### Basic Market Regime Analysis

```python
from ML.utils.market_regime import MarketRegimeDetector

# Initialize detector
detector = MarketRegimeDetector()

# Load price data for a stock
import pandas as pd
data = pd.read_csv('data/RELIANCE_day.csv')
data['date'] = pd.to_datetime(data['date'])
data.set_index('date', inplace=True)

# Detect market regime
regime, metrics = detector.detect_consolidated_regime(data)

# Get current regime
current_regime = regime.iloc[-1]
print(f"Current market regime: {current_regime}")
```

### Calculating Dynamic Stop Loss

```python
from ML.models.dynamic_stop_loss import DynamicStopLoss

# Initialize
dsl = DynamicStopLoss()

# Calculate stop loss
ticker = "RELIANCE"
position_type = "LONG"
entry_price = 1450.0

stop_loss = dsl.calculate_dynamic_stop_loss(
    ticker=ticker,
    position_type=position_type,
    entry_price=entry_price
)

print(f"Dynamic stop loss for {ticker}: {stop_loss}")
```

### Automatic Stop Loss Updates for Portfolio

```python
from ML.integration import update_portfolio_stop_losses

# Update all stop losses in portfolio based on current market regimes
updated_positions = update_portfolio_stop_losses()

for ticker, position in updated_positions.items():
    print(f"{ticker}: New stop loss = {position['stop_loss']}")
```

## Output Formats

The system produces several types of outputs:

1. **Terminal Output**: Detailed market regime analysis for each portfolio position
2. **Chart Images**: Saved in the results/ directory, showing regime transitions for each stock
3. **HTML Dashboard**: Comprehensive report with all analysis and recommendations
4. **JSON Data**: Raw analysis data for programmatic use

## How to Interpret Results

For each position, the analysis provides:

- **Current Regime**: The detected market regime for the stock
- **Quantitative Metrics**: Volatility, trend strength, and Hurst exponent
- **Market History**: Previous significant trends and dominant regimes
- **Stop Loss Recommendations**: Specific ATR multiplier and strategy
- **Position Analysis**: Comparison of current stop loss to recommended levels

## Running the Analysis

To run the full market regime analysis for your portfolio:

```bash
cd /Users/maverick/PycharmProjects/India-TS/ML
python analyze_market_regimes.py
```

The results will be displayed in the terminal and saved as an HTML report in the results/ directory.

## Best Practices for Using These Tools

1. **Run the analysis at least weekly** to detect regime changes
2. **Pay attention to regime divergences** between stocks and their reference indices
3. **Adjust stop losses promptly** when the analysis recommends changes
4. **Be cautious with bearish regime stocks** in your long portfolio
5. **Use the HTML dashboard** to get a comprehensive view of your portfolio

## Requirements

- Python 3.7+
- pandas
- numpy
- matplotlib
- scikit-learn