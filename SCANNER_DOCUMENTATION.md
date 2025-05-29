# India-TS Scanner Documentation

This document describes the different market scanners available in the India-TS system and their filtering criteria.

## Available Scanners

The system supports two types of scanners:

1. **Default Scanner** (`scan_market.py`): Based on Keltner Channel breakouts with volume confirmation
2. **Bull Trend Pullback Scanner** (`scan_market_BTPB.py`): Identifies bull trends with pullbacks and reversal patterns

You can configure which scanner to use and the timeframe in the `config.ini` file under the `[Scanner]` section:

```ini
[Scanner]
# Possible values: default, bull_trend_pullback
scanner_type = default
# Possible values: day, hour
timeframe = day
max_workers = 8
```

Alternatively, you can use the scanner launcher with command-line options:

```bash
# Using launcher with config settings
python scripts/scan_market_launcher.py

# Override scanner type and timeframe
python scripts/scan_market_launcher.py --scanner bull_trend_pullback --timeframe hour

# Run specific scanner directly
python scripts/scan_market_BTPB.py
```

## Default Scanner (Keltner Channel Breakout)

### Timeframe
- Uses hourly data by default (`60minute` in Zerodha's API)
- Fetches 6 weeks of historical data for analysis

### Indicators Calculated
- EMA 20: 20-period Exponential Moving Average
- ATR: Average True Range (20-period)
- Keltner Channels: EMA 20 ± (2 × ATR)
- Volume change percentage and price change percentage
- Price gaps between trading sessions
- Slope of price movement (using 8-period linear regression)
- Alpha (ratio of Slope to ATR)

### Long Signal Criteria
Long signals are generated when either:
1. The current price closes above the upper Keltner Channel with volume spike confirmation, OR
2. The price breaks above the upper Keltner Channel (previous close below, current close above)

Additional filters:
- Gap down filter: Stocks that gap down more than the configured threshold (default -1.0%) are filtered out
- Volume spike threshold: By default, requires average volume change of 4.0x for primary signals

### Short Signal Criteria
Short signals are generated when either:
1. The current price closes below the lower Keltner Channel with volume spike confirmation, OR
2. The price breaks below the lower Keltner Channel (previous close above, current close below)

### Market Breadth Analysis
- Counts advancing and declining tickers
- Calculates advances/declines ratio
- Uses ratio to determine market direction bias
- Can potentially disable long or short trades based on extreme market conditions

## Bull Trend Pullback Scanner

### Timeframe
- Configurable to use daily (`day`) or hourly (`60minute`) data
- Fetches 12 weeks of data for daily timeframe, 30 days for hourly timeframe

### Indicators Calculated
- EMA 20: 20-period Exponential Moving Average
- RSI: 14-period Relative Strength Index
- ATR: 14-period Average True Range
- Swing points (highs and lows)
- Bullish/bearish bar patterns

### Entry Signal Criteria
The scanner implements a multi-step filtering process:

1. **Bull Trend Identification** (requires at least 2 of these 3 conditions):
   - Series of 3 consecutive higher swing lows
   - Price above 20 EMA
   - Upward sloping 20 EMA (current EMA > EMA 5 bars ago)

2. **Pullback Identification**:
   - 2-3 consecutive bearish bars (close < open) in a bull trend

3. **Reversal Bar Patterns** (any of these):
   - Higher low pattern: Current bar's low > previous bar's low with bullish close
   - Inside bar pattern: Current bar is contained within previous bar's range
   - Bullish engulfing pattern: Current bar engulfs previous bar with bullish close

4. **Confirmation Indicators**:
   - Volume confirmation: Current bar's volume > 5-period average volume × 1.2
   - RSI confirmation: RSI ≤ 40 during pullback (oversold in bull trend)

5. **Signal Strength Calculation**:
   - Base strength of 1 for any valid signal
   - +1 for volume confirmation
   - +1 for RSI confirmation
   - +1 for engulfing pattern

### Risk Management Parameters
For each signal, the scanner calculates:
- Entry price: High of the reversal bar
- Stop loss: Low of the reversal bar - (0.1 × ATR)
- Target 1: Previous swing high or 1:1 risk-reward
- Target 2: Entry + (2 × initial risk)
- Target 3: Entry + (3 × initial risk)
- Position size: Based on account size and 1% risk per trade

## Rate Limiting

To prevent API rate limit errors, both scanners implement:
1. Limited concurrent workers (max 4-8 threads)
2. Batch processing (20 tickers at a time)
3. Delays between batches