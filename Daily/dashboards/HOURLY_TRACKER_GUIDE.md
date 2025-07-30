# Hourly Tracker Dashboard Guide

## Overview
The Hourly Tracker Dashboard monitors Long Reversal Hourly scanner results with VSR analysis, functioning exactly like the VSR tracker but for hourly data.

**Port:** 3002  
**URL:** http://localhost:3002  
**Telegram:** DISABLED (for manual monitoring)

## Features

### 1. Real-time Hourly Monitoring
- Tracks Long_Reversal_Hourly scanner results
- Updates every 60 seconds
- Shows tickers from the last 2 hours
- Auto-detects new hourly scan files every 5 minutes

### 2. Categories (Same as VSR Dashboard)

#### Perfect Scores (Score = 100)
- Stocks with perfect hourly VSR scores
- Highest confidence opportunities

#### High VSR (VSR ≥ 10)
- Exceptional volume-to-spread ratios in hourly timeframe
- Strong directional movement indicators

#### High Momentum (Momentum ≥ 5%)
- Strong price momentum in hourly data
- Early trend detection

#### All Hourly Tickers
- Complete list of all hourly scan results
- Includes appearance count badges

### 3. Key Differences from VSR Dashboard
- **Data Source**: Long_Reversal_Hourly files from `results-h/` directory
- **Timeframe**: Hourly instead of daily
- **Hours**: 8 AM - 4 PM (extended for pre/post market)
- **No Telegram**: Notifications disabled for quiet monitoring

## Installation & Usage

### Starting the System

1. **Start Hourly Tracker Service**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/services
./start_hourly_tracker.sh
```

2. **Start Hourly Dashboard**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards
./start_hourly_dashboard.sh
```

### Stopping the System

1. **Stop Dashboard**
```bash
./stop_hourly_dashboard.sh
```

2. **Stop Service**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/services
./stop_hourly_tracker.sh
```

## API Endpoints

### `/api/trending-tickers`
Returns hourly trending tickers categorized by criteria

### `/api/ticker-details/<ticker>`
Returns 24-hour history for a specific ticker

### `/api/hourly-persistence`
Returns hourly persistence data from `vsr_ticker_persistence_hourly_long.json`

## Files Structure
```
Daily/services/
├── hourly_tracker_service.py    # Main tracking service
├── start_hourly_tracker.sh      # Service startup script
└── stop_hourly_tracker.sh       # Service stop script

Daily/dashboards/
├── hourly_tracker_dashboard.py  # Dashboard application
├── templates/
│   └── hourly_tracker_dashboard.html  # Dashboard UI
├── start_hourly_dashboard.sh    # Dashboard startup script
└── stop_hourly_dashboard.sh     # Dashboard stop script

Daily/logs/hourly_tracker/       # Service logs
Daily/data/hourly_tracker_state.json  # Current state
```

## Monitoring Workflow

1. **Morning Setup (8:00 AM)**
   - Start hourly tracker service
   - Start dashboard
   - Monitor for early movers

2. **Intraday Monitoring**
   - Watch for confluence with daily signals
   - Track persistence across multiple hourly scans
   - Note emerging patterns

3. **Data Collection**
   - Service logs all high-scoring opportunities
   - State saved for analysis
   - No Telegram noise - pure data collection

## Integration with VSR System

The hourly tracker complements the VSR daily tracker:
- **VSR Dashboard (3001)**: Daily timeframe monitoring
- **Hourly Dashboard (3002)**: Hourly timeframe monitoring
- **Confluence Analysis**: Run separately to find overlaps

## Best Practices

1. **Manual Monitoring Phase**
   - Run for several days without alerts
   - Collect data on hourly-to-daily transitions
   - Identify optimal confluence patterns

2. **Pattern Recognition**
   - Note tickers appearing in multiple hourly scans
   - Track which hourly signals convert to daily
   - Measure momentum persistence

3. **Future Enhancements**
   - After data collection, design alert criteria
   - Integrate confluence detection
   - Add selective notifications

## Troubleshooting

### Dashboard Not Loading
1. Check if service is running: `ps aux | grep hourly_tracker`
2. Check logs: `tail -f Daily/services/hourly_tracker.log`
3. Verify port 3002 is free: `lsof -i :3002`

### No Data Showing
1. Check for hourly scan files in `Daily/results-h/`
2. Verify scanner is running and producing files
3. Check log files for errors

### Service Crashes
1. Check Python dependencies
2. Verify Kite credentials in config
3. Review error logs for specific issues