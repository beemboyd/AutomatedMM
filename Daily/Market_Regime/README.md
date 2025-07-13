# Market Regime Analysis System

This system analyzes market trend strength based on Long vs Short reversal scan counts to determine the overall market regime and provide trading bias recommendations.

## Components

### 1. `reversal_trend_scanner.py`
- Runs both Long and Short reversal daily scanners
- Collects scan results and counts
- Saves timestamped scan data in JSON format

### 2. `trend_strength_calculator.py`
- Analyzes Long/Short reversal count ratios
- Calculates trend strength with the following thresholds:
  - **Strong Bullish**: Ratio > 2.0
  - **Bullish**: Ratio > 1.5
  - **Neutral Bullish**: Ratio > 1.2
  - **Neutral**: Ratio between 0.8 - 1.2
  - **Neutral Bearish**: Ratio < 0.8
  - **Bearish**: Ratio < 0.67
  - **Strong Bearish**: Ratio < 0.5
- Tracks historical data for momentum analysis
- Generates trend reports with recommendations

### 3. `market_regime_analyzer.py`
- Main integration module that combines scanning and analysis
- Determines market regime based on trend strength
- Provides actionable trading insights
- Generates comprehensive regime reports
- Market regimes:
  - Strong Uptrend
  - Uptrend
  - Choppy Bullish
  - Choppy
  - Choppy Bearish
  - Downtrend
  - Strong Downtrend

### 4. `trend_dashboard.py`
- Generates visual HTML dashboard
- Shows current market regime with color coding
- Displays reversal counts and ratios
- Auto-refreshes every 5 minutes
- Mobile-responsive design

### 5. `run_market_regime_analysis.py`
- Simple runner script for scheduled execution
- Handles logging for scheduled runs

## Usage

### Manual Execution

Run the complete analysis:
```bash
python market_regime_analyzer.py
```

Generate dashboard only:
```bash
python trend_dashboard.py
```

### Scheduled Execution

The system includes a LaunchAgent plist file for macOS scheduling:
- Location: `../scheduler/com.india-ts.market_regime_analysis.plist`
- Schedule: Every 30 minutes from 9:00 AM to 3:30 PM on weekdays

To enable scheduling:
```bash
cp ../scheduler/com.india-ts.market_regime_analysis.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
```

To disable scheduling:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
```

## Output Files

### Scan Results
- Location: `scan_results/`
- Format: `reversal_scan_YYYYMMDD_HHMMSS.json`
- Contains: Long and short counts, file paths, timestamp

### Trend Analysis
- Location: `trend_analysis/`
- Format: `trend_report_YYYYMMDD_HHMMSS.json`
- Contains: Trend strength, ratio, momentum, recommendations

### Regime Analysis
- Location: `regime_analysis/`
- Files:
  - `regime_report_YYYYMMDD_HHMMSS.json` - Timestamped reports
  - `latest_regime_summary.json` - Always contains latest analysis
- Contains: Complete market regime analysis with insights

### Dashboard
- Location: `dashboards/`
- File: `market_regime_dashboard.html`
- Features: Visual representation of current market regime

## Trading Recommendations

The system provides specific trading recommendations based on market regime:

- **Strong Uptrend**: Focus on long setups, avoid shorts
- **Uptrend**: Prefer long setups, be selective with shorts
- **Choppy Bullish**: Slight preference for longs, both directions viable
- **Choppy**: No directional bias, trade both directions
- **Choppy Bearish**: Slight preference for shorts, both directions viable
- **Downtrend**: Prefer short setups, be selective with longs
- **Strong Downtrend**: Focus on short setups, avoid longs

## Integration with Trading System

The market regime analysis can be integrated with other trading components:

1. **Position Sizing**: Adjust position sizes based on regime confidence
2. **Trade Selection**: Filter trades based on regime bias
3. **Risk Management**: Tighter stops in low-confidence regimes
4. **Strategy Selection**: Choose strategies that align with current regime

## Monitoring

Check logs for system health:
- `reversal_trend_scanner.log` - Scanner execution logs
- `trend_strength_calculator.log` - Analysis logs
- `market_regime_analyzer.log` - Main system logs
- `scheduled_runs.log` - Scheduled execution history

## Troubleshooting

1. **No scan results found**
   - Check if reversal scanners are working properly
   - Verify data directories exist
   - Check scanner logs for errors

2. **Dashboard not updating**
   - Ensure `market_regime_analyzer.py` has run recently
   - Check for `latest_regime_summary.json` in regime_analysis/
   - Verify file permissions

3. **Scheduled runs not working**
   - Check LaunchAgent is loaded: `launchctl list | grep market_regime`
   - Review logs in Market_Regime directory
   - Verify Python path in plist file