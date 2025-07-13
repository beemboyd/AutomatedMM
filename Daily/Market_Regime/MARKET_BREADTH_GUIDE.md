# Market Breadth Scanner & Dashboard Guide

## Overview

The Market Breadth Scanner and Dashboard provide comprehensive market internals analysis independent of reversal scanner timing. This system calculates real-time advance/decline ratios, RSI distributions, volume participation, and momentum indicators to give more accurate market regime shifts for optimal position sizing.

## Components

### 1. Market Breadth Scanner (`Market_Breadth_Scanner.py`)
- Scans all tickers from `Ticker_with_Sector.xlsx`
- Calculates:
  - Price vs SMA20/SMA50 positions
  - RSI levels (14-period)
  - Volume ratios (current vs 20-day average)
  - 5-day and 10-day momentum
  - Sector-wise performance
- Runs every 30 minutes during market hours (9:00 AM - 3:30 PM)
- Saves results to `Market_Regime/breadth_data/`

### 2. Enhanced Market Breadth Dashboard
- Runs on **port 5001** (separate from existing dashboard on port 5000)
- Displays:
  - Market regime and score
  - Position sizing recommendations
  - SMA20/50 breadth indicators
  - RSI distribution (Overbought/Neutral/Oversold)
  - Volume participation metrics
  - Sector performance rankings
  - Top gainers/losers
  - High volume stocks
  - Overbought/Oversold lists

## Key Metrics

### Market Score Calculation
```
SMA Score = (SMA20_breadth * 0.3 + SMA50_breadth * 0.2) / 50
Momentum Score = (Positive_5D / Total * 0.25) + (Positive_10D / Total * 0.25)
RSI Score = (Neutral_stocks / Total * 0.5) - Extremes_penalty
Market Score = SMA_Score + Momentum_Score + RSI_Score
```

### Position Sizing Recommendations
- **Strong Uptrend**: 1.5x position size, Aggressive Long strategy
- **Uptrend**: 1.25x position size, Long Bias strategy
- **Choppy/Sideways**: 1.0x position size, Neutral/Selective strategy
- **Downtrend**: 0.75x position size, Cautious strategy
- **Strong Downtrend**: 0.5x position size, Defensive/Short strategy

### Advance/Decline Ratio
- Based on stocks above/below SMA20
- More responsive than waiting for reversal signals
- Updates every 30 minutes with market data

## Setup Instructions

### 1. Test the Scanner Manually
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
python3 scanners/Market_Breadth_Scanner.py
```

### 2. Start the Dashboard
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/utils
./start_market_breadth_dashboard.sh
```

Access the dashboard at: http://localhost:5001

### 3. Schedule the Scanner
```bash
# Load the launchd job
launchctl load /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist

# Verify it's loaded
launchctl list | grep market_breadth_scanner
```

### 4. Stop the Dashboard
```bash
./stop_market_breadth_dashboard.sh
```

## Data Files

### Input
- `Daily/data/Ticker_with_Sector.xlsx` - List of tickers with sector information

### Output
- `Market_Regime/breadth_data/market_breadth_latest.json` - Latest scan results
- `Market_Regime/breadth_data/market_breadth_YYYYMMDD_HHMMSS.json` - Timestamped results
- `Market_Regime/breadth_data/market_breadth_scan_YYYYMMDD_HHMMSS.xlsx` - Detailed scan data

## API Endpoints (Port 5001)

- `/` - Main dashboard page
- `/api/breadth-data` - Latest market breadth data with recommendations
- `/api/sector-performance` - Sector-wise performance metrics
- `/api/stock-details` - Top gainers, losers, high volume stocks
- `/api/historical-breadth` - Last 10 scan results for trend analysis
- `/health` - Health check endpoint

## Integration with Existing System

This system runs parallel to the existing market regime analyzer:
1. Market Breadth Scanner provides real-time SMA-based A/D ratios
2. Existing reversal scanners continue to run as scheduled
3. Both dashboards can run simultaneously (ports 5000 and 5001)
4. After testing, the market regime analyzer can be updated to use breadth data

## Troubleshooting

### Scanner Issues
- Check logs: `Daily/logs/market_breadth_scanner.log`
- Verify Kite API connection
- Ensure `Ticker_with_Sector.xlsx` exists and has correct format

### Dashboard Issues
- Check if port 5001 is available
- Verify breadth data files exist in `Market_Regime/breadth_data/`
- Check dashboard process: `ps aux | grep market_breadth_dashboard`

### Scheduling Issues
- List scheduled jobs: `launchctl list | grep india-ts`
- Check job status: `launchctl print user/$(id -u)/com.india-ts.market_breadth_scanner`
- Unload/reload job if needed:
  ```bash
  launchctl unload /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist
  launchctl load /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist
  ```

## Benefits

1. **Independence from Scanner Jobs**: No need to wait for reversal scanners
2. **Real-time Market Regime**: Updates every 30 minutes with current market data
3. **Better Position Sizing**: More accurate regime detection leads to optimal position sizes
4. **Comprehensive View**: Multiple indicators (SMA, RSI, Volume, Momentum) for robust analysis
5. **Sector Insights**: Understand which sectors are leading/lagging

## Future Enhancements

- Add more technical indicators (MACD, Bollinger Bands)
- Include market cap weighted calculations
- Add intraday trend analysis
- Create alerts for regime changes
- Historical backtesting of regime accuracy