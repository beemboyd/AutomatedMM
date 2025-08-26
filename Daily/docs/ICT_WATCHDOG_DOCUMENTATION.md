# ICT Stop Loss Watchdog Documentation

## Overview
The ICT Stop Loss Watchdog is an automated system that analyzes CNC (delivery) positions using Inner Circle Trader (ICT) concepts to provide optimal stop-loss recommendations. It runs every 15 minutes during market hours and performs analysis on both hourly and daily timeframes.

## Features

### 1. ICT Concept Analysis
- **Market Structure Analysis**: Identifies bullish/bearish trends, pullbacks, and corrections
- **Order Block Detection**: Finds institutional supply/demand zones
- **Fair Value Gap (FVG) Identification**: Locates price inefficiencies
- **Liquidity Level Mapping**: Identifies key liquidity pools (equal highs/lows)
- **Optimal Trade Entry (OTE) Zones**: Calculates Fibonacci-based entry/exit levels

### 2. Multi-Timeframe Analysis
- **Hourly Analysis**: Short-term market structure and immediate support/resistance
- **Daily Analysis**: Long-term trend and major levels
- **Combined Recommendation**: Conservative stop loss using both timeframes

### 3. Automated Monitoring
- Runs every 15 minutes during market hours (9:15 AM - 3:30 PM)
- Automatic position fetching from Zerodha
- Critical alert detection for bearish structures
- Comprehensive logging and status tracking

## Installation

### Prerequisites
1. Python 3.8+ with required packages:
   ```bash
   pip install pandas numpy kiteconnect
   ```

2. Valid Zerodha API credentials in `config.ini`

### Setup Steps

1. **Install the watchdog service**:
   ```bash
   cd /Users/maverick/PycharmProjects/India-TS/Daily/portfolio
   ./start_ict_watchdog.sh
   ```

2. **Verify installation**:
   ```bash
   ./status_ict_watchdog.sh
   ```

## Usage

### Manual Analysis
Run ICT analysis manually:
```bash
python3 portfolio/SL_Watch_ICT.py --user Sai
```

### Automated Monitoring
The watchdog runs automatically every 15 minutes when started. No manual intervention required.

### Testing
Test with sample or actual positions:
```bash
# Test with sample position
python3 portfolio/test_ict_analysis.py --sample

# Test with actual positions
python3 portfolio/test_ict_analysis.py --actual
```

## File Structure

```
Daily/portfolio/
├── SL_Watch_ICT.py                 # Main ICT analysis engine
├── sl_watch_ict_15min.sh          # 15-minute scheduler script
├── start_ict_watchdog.sh          # Service starter
├── stop_ict_watchdog.sh           # Service stopper
├── status_ict_watchdog.sh         # Status checker
├── test_ict_analysis.py           # Test script
└── ict_analysis/                  # Analysis results directory
    ├── ict_sl_analysis_*.json     # JSON analysis results
    └── watchdog_status.json       # Service status file

Daily/logs/ict_watchdog/
├── ict_watchdog_YYYYMMDD.log     # Daily log files
├── sl_watch_ict_YYYYMMDD.log     # Detailed analysis logs
├── stdout.log                     # Standard output
└── stderr.log                     # Error output

Daily/scheduler/plists/
└── com.india-ts.ict-sl-watchdog.plist  # LaunchAgent configuration
```

## ICT Concepts Explained

### Market Structure Types
1. **BULLISH_TRENDING**: Clear uptrend with higher highs and higher lows
2. **BEARISH_TRENDING**: Clear downtrend with lower lows and lower highs
3. **BULLISH_PULLBACK**: Temporary retracement in uptrend (<61.8% Fibonacci)
4. **BEARISH_PULLBACK**: Temporary retracement in downtrend (<61.8% Fibonacci)
5. **BULLISH_CORRECTION**: Deep retracement in uptrend (>61.8% Fibonacci)
6. **BEARISH_CORRECTION**: Deep retracement in downtrend (>61.8% Fibonacci)
7. **RANGING**: Sideways consolidation with no clear trend

### Key Level Types
- **Order Blocks (OB)**: Last opposite candle before structure break
- **Fair Value Gaps (FVG)**: Price gaps between candles indicating inefficiency
- **Liquidity Levels**: Areas with multiple touches (equal highs/lows)
- **OTE Zones**: 61.8%-79% Fibonacci retracement areas

## Stop Loss Logic

### Calculation Method
1. Identifies all key support/resistance levels using ICT concepts
2. Determines market structure (trend, pullback, or correction)
3. Selects appropriate stop level based on:
   - Nearest strong support for bullish structures
   - Below pullback support for pullbacks
   - Wide stops for corrections
   - Range boundaries for consolidation

### Conservative Approach
- Uses the lower of hourly and daily stop loss recommendations
- Maximum 10% stop loss from current price
- Minimum below entry price for long positions

## Output Format

### JSON Analysis Result
```json
{
  "ticker": "RELIANCE",
  "timeframe": "hourly",
  "current_price": 2550.0,
  "position_price": 2500.0,
  "market_structure": "Bullish Trending",
  "optimal_sl": 2475.0,
  "sl_reasoning": "Below OB_BULLISH support at 2480.00",
  "trend_strength": 75.5,
  "pullback_probability": 50.0,
  "correction_probability": 20.0,
  "recommendation": "HOLD - Bullish structure intact",
  "analysis_time": "2025-08-18 10:30:00"
}
```

### Log Format
```
[2025-08-18 10:30:00] ICT ANALYSIS REPORT - RELIANCE (HOURLY)
================================================================================
POSITION DETAILS:
  Entry Price: ₹2500.00
  Current Price: ₹2550.00
  P&L: ₹50.00 (2.00%)

MARKET STRUCTURE:
  Structure: Bullish Trending
  Trend Strength: 75.5%
  Pullback Probability: 50.0%
  Correction Probability: 20.0%

KEY ICT LEVELS:
  OB_BULLISH: ₹2480.00 (Strength: 3/5) [-2.75% away]
  FVG_BULLISH: ₹2490.00 (Strength: 2/5) [-2.35% away]
  LIQUIDITY_LOW: ₹2470.00 (Strength: 4/5) [-3.14% away]

STOP LOSS RECOMMENDATION:
  Optimal SL: ₹2475.00
  SL Distance: 2.94%
  Reasoning: Below OB_BULLISH support at 2480.00

ACTION RECOMMENDATION:
  HOLD - Bullish structure intact
================================================================================
```

## Monitoring & Maintenance

### Check Service Status
```bash
./status_ict_watchdog.sh
```

### View Today's Logs
```bash
tail -f logs/ict_watchdog/ict_watchdog_$(date +%Y%m%d).log
```

### Stop Service
```bash
./stop_ict_watchdog.sh
```

### Restart Service
```bash
./stop_ict_watchdog.sh
./start_ict_watchdog.sh
```

## Critical Alerts

The system generates critical alerts when:
- Market structure turns BEARISH
- Correction probability exceeds 60%
- Stop loss is very close to current price

Alerts appear in logs as:
```
CRITICAL ALERTS:
  - RELIANCE (hourly): CONSIDER EXIT - Bearish structure
  - INFY (daily): MONITOR CLOSELY - In correction phase
```

## Troubleshooting

### Service Not Running
```bash
# Check if plist is loaded
launchctl list | grep ict-sl-watchdog

# Reload service
launchctl unload ~/Library/LaunchAgents/com.india-ts.ict-sl-watchdog.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.ict-sl-watchdog.plist
```

### No Positions Found
- Verify Kite API credentials in config.ini
- Check if market is open
- Ensure CNC positions exist in portfolio

### Analysis Errors
- Check stderr.log for Python errors
- Verify network connectivity
- Ensure sufficient historical data available

## Best Practices

1. **Review Daily**: Check analysis results at least once daily
2. **Act on Alerts**: Respond promptly to critical alerts
3. **Verify Recommendations**: Cross-check with manual analysis
4. **Update Stop Losses**: Implement recommended stops in broker platform
5. **Monitor Logs**: Regular log review for system health

## Integration with Other Systems

The ICT Watchdog integrates with:
- **Position Watchdog**: Can trigger position exits based on ICT signals
- **VSR Tracker**: Combines momentum with structure analysis
- **Risk Management**: Provides dynamic stop loss levels

## Future Enhancements

Planned improvements:
- [ ] Telegram notifications for critical alerts
- [ ] Web dashboard for visual analysis
- [ ] Multi-strategy stop loss options
- [ ] Automatic stop loss order placement
- [ ] Backtesting of ICT stop loss effectiveness

## Support

For issues or questions:
1. Check logs in `logs/ict_watchdog/`
2. Run test script: `python3 portfolio/test_ict_analysis.py`
3. Review this documentation
4. Check Activity.md for recent changes

---

*Last Updated: 2025-08-18*
*Version: 1.0*