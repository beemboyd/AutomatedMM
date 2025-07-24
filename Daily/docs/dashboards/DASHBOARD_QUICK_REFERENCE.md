# India-TS Dashboard Quick Reference

## 🚀 Quick Start
```bash
# Start both dashboards with one command
/Users/maverick/PycharmProjects/India-TS/Daily/utils/start_dashboards.sh
```

## 🌐 Dashboard URLs

| Dashboard | URL | Port | Purpose |
|-----------|-----|------|---------|
| **Main Dashboard** | http://localhost:8080 | 8080 | Market regime analysis, trends, visualizations |
| **Health Dashboard** | http://localhost:7080 | 7080 | System health, job monitoring, alerts |
| **VSR Tracker** | http://localhost:3001 | 3001 | VSR-based trending stocks, momentum analysis |
| **Market Breadth** | http://localhost:5001 | 5001 | Market internals, SMA breadth, sector analysis |
| **Job Manager** | http://localhost:9090 | 9090 | All system jobs monitoring and control |
| **SL Watchdog** | http://localhost:2001 | 2001 | Stop loss watchdog logs, position monitoring |

## 🎮 Control Commands

### Start Dashboards
```bash
# Using convenience script (recommended)
/Users/maverick/PycharmProjects/India-TS/Daily/utils/start_dashboards.sh

# Or manually
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

### Stop Dashboards
```bash
# Using convenience script (recommended)
/Users/maverick/PycharmProjects/India-TS/Daily/utils/stop_dashboards.sh

# Or manually
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

### Check Status
```bash
# Quick status check
launchctl list | grep dashboard

# Detailed port check
lsof -i :8080  # Main dashboard
lsof -i :7080  # Health dashboard
```

## 📊 Dashboard Features

### Main Dashboard (Port 8080)
- **Current Market Regime** with confidence level
- **Real-time Charts** for market metrics
- **Pattern Distribution** visualization
- **24-hour Historical Trends**
- **Auto-refresh** every 30 seconds

### Health Dashboard (Port 7080)
- **All 13 India-TS Jobs** status
- **System Health** indicators
- **Schedule Tracking** for jobs
- **Real-time Alerts** for issues
- **Job Summary** statistics

### VSR Tracker Dashboard (Port 3001)
- **Real-time VSR Analysis** from tracker logs
- **Perfect Score Stocks** (Score = 100)
- **High VSR Stocks** (VSR ≥ 10)
- **High Momentum Stocks** (≥ 5%)
- **Auto-refresh** every 60 seconds
- **Manual Refresh Button** for instant updates

### Market Breadth Dashboard (Port 5001)
- **SMA20/SMA50 Breadth** with % changes
- **Sector Performance** analysis
- **Market Internals** visualization
- **Early Bird** KC breakout patterns
- **Real-time Updates** from scanner

### SL Watchdog Dashboard (Port 2001)
- **Real-time Log Viewer** for SL watchdog service
- **User Selection** dropdown to switch between users
- **Start/Stop Controls** for SL watchdog service
- **Manual Refresh Button** for efficiency (loads last 300 lines)
- **Color-coded Logs** (errors, warnings, buy/sell orders)
- **Position Monitoring** with 2% peak drop warnings

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Dashboard won't start | Check if port is already in use: `lsof -i :8080` |
| No data showing | Ensure market regime analyzer is running |
| Jobs not updating | Restart health dashboard |
| Page not loading | Check error logs in `/Daily/Market_Regime/logs/` |

## 📁 Key Files

```
/Users/maverick/PycharmProjects/India-TS/Daily/
├── utils/
│   ├── start_dashboards.sh    # Start main dashboards
│   ├── stop_dashboards.sh     # Stop main dashboards
│   └── check_jobs_status.sh   # Check all jobs status
├── Market_Regime/
│   ├── dashboard_enhanced.py   # Main dashboard (8080)
│   ├── dashboard_health_check.py # Health dashboard (7080)
│   └── market_breadth_dashboard.py # Market breadth (5001)
├── dashboards/
│   ├── vsr_tracker_dashboard.py # VSR tracker (3001)
│   ├── start_vsr_dashboard.sh  # Start VSR dashboard
│   ├── stop_vsr_dashboard.sh   # Stop VSR dashboard
│   ├── sl_watchdog_dashboard.py # SL watchdog (2001)
│   └── start_sl_watchdog_dashboard.sh # Start SL watchdog dashboard
└── job_management/
    └── job_manager_dashboard.py # Job manager (9090)
```

## 🔄 After System Reboot

Dashboards should auto-start. If not:
```bash
# Option 1: Use the startup script
/Users/maverick/PycharmProjects/India-TS/Daily/utils/start_dashboards.sh

# Option 2: Load all India-TS jobs
/Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh
```

## 📝 Notes
- Both dashboards run persistently using LaunchAgents
- They automatically restart if they crash
- Logs are rotated to prevent disk space issues
- Dashboards are accessible from any device on the network

---
💡 **Tip**: Bookmark the dashboard URLs in your browser for quick access!