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
│   ├── start_dashboards.sh    # Start both dashboards
│   ├── stop_dashboards.sh     # Stop both dashboards
│   └── check_jobs_status.sh   # Check all jobs status
└── Market_Regime/
    ├── dashboard_enhanced.py   # Main dashboard (8080)
    └── dashboard_health_check.py # Health dashboard (7080)
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