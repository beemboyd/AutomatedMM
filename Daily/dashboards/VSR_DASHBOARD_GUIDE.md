# VSR Tracker Dashboard Guide

## Overview
The VSR Tracker Dashboard provides real-time insights into trending stocks based on Volume Spread Ratio (VSR) analysis. It monitors the VSR tracker logs and displays high-scoring opportunities in an intuitive web interface.

**Port:** 3001  
**URL:** http://localhost:3001

## Features

### 1. Real-time Trend Monitoring
- Parses VSR tracker logs every minute
- Shows stocks from the last 2 hours by default
- Auto-refreshes every 60 seconds
- **NEW**: Auto-detects new Long_Reversal_Daily files every 5 minutes

### 2. Categorized View
The dashboard organizes tickers into four main categories:

#### Perfect Scores (Score = 100)
- Stocks with perfect VSR scores
- Highest confidence opportunities

#### High VSR (VSR ≥ 10)
- Stocks with exceptional volume-to-spread ratios
- Indicates strong directional movement

#### High Momentum (Momentum ≥ 5%)
- Stocks showing strong price momentum
- Good for trend-following strategies

#### Strong Build (Build ≥ 10)
- Stocks with sustained momentum over multiple periods
- Indicates trend strength

### 3. Key Metrics Displayed
- **Score:** Overall VSR score (0-100)
- **VSR:** Volume Spread Ratio value
- **Momentum:** Percentage price movement
- **Price:** Current stock price
- **Volume:** Trading volume
- **Build:** Momentum build indicator

## Installation & Usage

### Starting the Dashboard
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards
./start_vsr_dashboard.sh
```

### Stopping the Dashboard
```bash
./stop_vsr_dashboard.sh
```

### Manual Start
```bash
python vsr_tracker_dashboard.py
```

## API Endpoints

### `/api/trending-tickers`
Returns all trending tickers categorized by criteria:
```json
{
    "timestamp": "2025-07-21 14:30:00 IST",
    "categories": {
        "perfect_scores": [...],
        "high_vsr": [...],
        "high_momentum": [...],
        "strong_build": [...],
        "all_tickers": [...]
    },
    "total_tickers": 25
}
```

### `/api/ticker-details/<ticker>`
Returns detailed information for a specific ticker (24-hour history)

## Configuration

### Filtering Criteria
Tickers are included if they meet any of these criteria:
- Score ≥ 75
- Momentum ≥ 5.0%
- VSR ≥ 10.0

### Time Window
- Default: Last 2 hours of logs
- Configurable in `parse_vsr_logs()` function

## Color Coding

### Score Colors
- 🟢 Green: Score = 100 (Perfect)
- 🟡 Orange: Score ≥ 85 (High)
- 🔵 Blue: Score < 85 (Medium)

### Momentum Colors
- 🔴 Red: Momentum ≥ 7% (Very High)
- 🟡 Orange: Momentum ≥ 4% (High)
- 🔘 Gray: Momentum < 4% (Normal)

### VSR Colors
- 🟣 Purple: VSR ≥ 15 (Very High)
- 🔵 Blue: VSR ≥ 8 (High)
- 🔘 Gray: VSR < 8 (Normal)

## Troubleshooting

### Dashboard Not Starting
1. Check if port 3001 is already in use:
   ```bash
   lsof -i :3001
   ```
2. Check log file:
   ```bash
   tail -f vsr_dashboard.log
   ```

### No Data Showing
1. Verify VSR tracker is running
2. Check log files exist in:
   ```
   /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/
   ```
3. Ensure logs are from today

### Manual Refresh
Click the "🔄 Refresh" button to manually update data

## Auto-Reload Feature (NEW)

### Automatic Ticker Updates
The VSR Enhanced Tracker now automatically checks for new Long_Reversal_Daily files every 5 minutes:
- **No Restart Required**: New tickers are loaded automatically
- **Detection Indicator**: Look for `🆕 New Long_Reversal_Daily file detected` in logs
- **New Ticker Alert**: `✨ New tickers found: TICKER1, TICKER2...`
- **Dashboard Update**: New tickers appear on dashboard within 1-2 minutes

### How It Works
1. Every 5 minutes, the tracker checks the results folder
2. If a newer Long_Reversal_Daily file exists, it loads the tickers
3. New tickers are immediately added to tracking
4. High-scoring new tickers appear on the dashboard

## Integration with Trading System

The VSR Dashboard complements other trading tools:
- **VSR Tracker Service:** Provides the raw data with auto-reload
- **VSR Momentum Trading:** Uses dashboard data for order placement
- **Market Breadth Dashboard (5001):** Shows market internals
- **Market Regime Dashboard (8080):** Shows ML-based regime analysis
- **SL Watchdog Dashboard (2001):** Monitors stop losses with 2% warnings

## Best Practices

1. **Morning Review:** Check for early momentum builders
2. **Intraday Monitoring:** Watch for new entries and momentum changes
3. **Combine with Other Indicators:** Use alongside market regime analysis
4. **Volume Confirmation:** Ensure adequate volume for liquidity

## Files Structure
```
Daily/dashboards/
├── vsr_tracker_dashboard.py    # Main dashboard application
├── templates/
│   └── vsr_tracker_dashboard.html  # Dashboard UI
├── start_vsr_dashboard.sh      # Startup script
├── stop_vsr_dashboard.sh       # Stop script
└── VSR_DASHBOARD_GUIDE.md      # This documentation
```