# Market Breadth Dashboard Access Guide

## Dashboard Access

### Primary URL
- **Local Access**: http://localhost:5001 or http://127.0.0.1:5001
- **Status**: Currently running and accessible
- **Auto-refresh**: Every 2 minutes

### Dashboard Process Management
```bash
# Check if dashboard is running
ps aux | grep 5001
ps aux | grep market_breadth_dashboard

# View dashboard process details
launchctl list | grep market_regime_dashboard

# Start dashboard manually (if not running)
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python market_breadth_dashboard.py

# Stop dashboard
# Find PID from ps aux output, then:
kill <PID>
```

## Supporting Jobs Schedule

### 1. Market Breadth Scanner
- **Schedule**: Every 30 minutes during market hours
  - Start: 9:00 AM IST
  - End: 3:30 PM IST
  - Days: Monday through Friday
  - Frequency: Runs at :00 and :30 of each hour
- **Job Name**: `com.india-ts.market_breadth_scanner`
- **Script**: `/Daily/scanners/Market_Breadth_Scanner.py`
- **Purpose**: Scans all tickers for breadth indicators and updates dashboard data

### 2. Dashboard Service
- **Job Name**: `com.india-ts.market_regime_dashboard`
- **Port**: 5001
- **Auto-start**: Yes (managed by launchd)
- **Restart on failure**: Yes

## Data Flow

1. **Market Breadth Scanner** (every 30 minutes)
   - Scans 598 tickers
   - Calculates SMA20/50, RSI, momentum, volume metrics
   - Generates sector performance analysis
   - Saves to `breadth_data/market_breadth_latest.json`
   - Updates sector rotation database

2. **Dashboard** (continuous)
   - Serves web interface on port 5001
   - Auto-refreshes every 2 minutes
   - Reads latest data from JSON files
   - Provides real-time API endpoints

## Dashboard Features

### Main Views
1. **Market Overview**
   - Market regime (Uptrend/Downtrend/Sideways)
   - Market score and confidence level
   - Position sizing recommendations
   - Stop loss adjustments

2. **Breadth Indicators**
   - SMA20/50 breadth percentages
   - RSI distribution (Overbought/Neutral/Oversold)
   - 5-day momentum analysis
   - Volume participation metrics
   - Advance/Decline ratios

3. **Enhanced Sector Performance**
   - Compact grid layout (reduces scrolling)
   - Bullish/Bearish stance classification
   - Key metrics: SMA20%, RSI, 5D momentum
   - Color-coded for quick interpretation

4. **Stock Lists**
   - Top gainers (5-day)
   - Top losers (5-day)
   - High volume stocks
   - Overbought stocks (RSI > 70)
   - Oversold stocks (RSI < 30)

### API Endpoints

#### Breadth Data
- `GET /api/breadth-data` - Complete market breadth data with recommendations
- `GET /api/sector-performance` - Enhanced sector performance with classifications
- `GET /api/stock-details` - Individual stock metrics and lists
- `GET /api/historical-breadth` - Last 10 scans for trend analysis

#### Sector Rotation (New)
- `GET /api/sector-rotation` - Rotation events, statistics, and predictions
- `GET /api/sector-cycles/<sector>` - Cycle history for specific sector
- `GET /api/rotation-report` - Comprehensive rotation analysis report

#### System
- `GET /health` - Health check endpoint
- `GET /test` - Test page for diagnostics

## Log Files and Monitoring

### Scanner Logs
```bash
# View latest scanner activity
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log

# Check for errors
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner_error.log

# View today's scans
grep "$(date +%Y-%m-%d)" /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log
```

### Dashboard Logs
```bash
# If running in terminal, logs appear in console
# For background process, check system logs:
log show --predicate 'process == "Python" && eventMessage contains "market_breadth_dashboard"' --last 1h
```

## Data Files

### Latest Data
- **Location**: `/Daily/Market_Regime/breadth_data/`
- **Latest snapshot**: `market_breadth_latest.json`
- **Historical files**: `market_breadth_YYYYMMDD_HHMMSS.json`
- **Excel reports**: `market_breadth_scan_YYYYMMDD_HHMMSS.xlsx`

### Sector Rotation Database
- **Location**: `/Daily/Market_Regime/sector_rotation.db`
- **Tables**:
  - `sector_performance` - Daily metrics
  - `rotation_events` - Detected rotations
  - `sector_cycles` - Bull/bear cycles

## Troubleshooting

### Dashboard Not Accessible
```bash
# Check if process is running
ps aux | grep 5001

# Check if port is in use
lsof -i :5001

# Restart dashboard
launchctl stop com.india-ts.market_regime_dashboard
launchctl start com.india-ts.market_regime_dashboard

# Or manually:
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python market_breadth_dashboard.py
```

### Scanner Not Running
```bash
# Check last run
tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log

# Check job status
launchctl list com.india-ts.market_breadth_scanner

# Run manually
cd /Users/maverick/PycharmProjects/India-TS/Daily
python scanners/Market_Breadth_Scanner.py -u Sai
```

### Data Not Updating
1. Check scanner is running during market hours
2. Verify internet connection for market data
3. Check Kite API credentials in config.ini
4. Ensure sufficient disk space for data files

## Quick Commands Reference

```bash
# Open dashboard in browser
open http://localhost:5001

# Monitor scanner in real-time
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log

# Check latest market breadth data
cat /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/breadth_data/market_breadth_latest.json | jq '.market_regime'

# View sector rotation events
curl http://localhost:5001/api/sector-rotation | jq '.rotation_events'

# Get current market statistics
curl http://localhost:5001/api/breadth-data | jq '.market_score, .market_regime'
```

## Performance Notes

- Scanner takes ~4 minutes to complete (598 tickers × 0.35s delay)
- Dashboard uses minimal resources (~80MB RAM)
- Database grows ~1MB per month of historical data
- API responses are typically < 100ms

## Future Enhancements Planned

1. **Real-time Updates**: WebSocket for live data during market hours
2. **Historical Charts**: D3.js visualizations for trends
3. **Custom Alerts**: Configurable thresholds for regime changes
4. **Mobile View**: Responsive design optimization
5. **Export Features**: PDF reports and CSV data dumps