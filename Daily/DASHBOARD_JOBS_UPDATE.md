# India-TS Health Dashboard Jobs Update

## What was added to the Health Dashboard

The health dashboard at http://localhost:7080 now displays all India-TS system jobs with their current status.

### New Features Added:

1. **India-TS System Jobs Section**
   - Shows all 13 India-TS jobs with their schedules
   - Real-time status updates every 30 seconds
   - Color-coded status indicators:
     - Green: Running jobs
     - Light Green: Successful (last run)
     - Red: Error status
     - Gray: Not loaded

2. **Jobs Summary Panel**
   - Total Jobs count
   - Running jobs count (green)
   - Successful jobs count (light green)
   - Error jobs count (red)

3. **Job Details Display**
   - Job name (cleaned up for readability)
   - Schedule information
   - Process ID (PID) for running jobs
   - Exit code for completed jobs

### How it Works:

1. The dashboard queries `launchctl list` every 30 seconds
2. Parses the output to get job status
3. Updates the web interface dynamically
4. No page refresh needed - updates automatically

### Jobs Currently Monitored:

#### Trading Scanners & Analysis:
- **brooks_reversal_4times** - Runs at 9:30, 11:30, 13:30, 16:00 (Mon-Fri)
  - Script: Al_Brooks_Higher_Probability_Reversal.py
- **brooks_reversal_simple** - Every 30 minutes (RunAtLoad: true)
  - Script: brooks_reversal_scheduler.py
- **consolidated_score** - 9:00 AM daily (Mon-Fri)
  - Script: Action_Plan_Score.py
- **daily_action_plan** - 8:30 AM daily (Mon-Fri, RunAtLoad: true)
  - Script: Action_plan.py
- **long_reversal_daily** - Every 30 min (9:00-15:30, Mon-Fri)
  - Script: Long_Reversal_Daily.py
- **short_reversal_daily** - Every 30 min (9:00-15:30, Mon-Fri)
  - Script: Short_Reversal_Daily.py
- **market_breadth_scanner** - Every 30 min (9:00-15:30, Mon-Fri)
  - Script: Market_Breadth_Scanner.py

#### Market Analysis & Dashboards:
- **health_dashboard** - 24/7 (KeepAlive: true, RunAtLoad: true)
  - Script: dashboard_health_check.py
  - Port: 7080 (http://localhost:7080)
- **market_regime_dashboard** - 24/7 (KeepAlive: true, RunAtLoad: true)
  - Script: dashboard_enhanced.py
  - Port: 8080 (default)
- **market_breadth_dashboard** - Manual start/stop via shell scripts
  - Script: market_breadth_dashboard.py
  - Port: 5001 (http://localhost:5001)
  - Start: ./start_market_breadth_dashboard.sh
  - Stop: ./stop_market_breadth_dashboard.sh
- **market_regime_analysis** - Every 30 min (9:15-15:30, Mon-Fri)
  - Script: market_regime_analyzer.py

#### Position Management & Trading:
- **sl_watchdog_stop** - 3:30 PM daily (Mon-Fri)
  - Command: pkill -f "SL_watchdog.py.*India-TS"
- **strategyc_filter** - Runs at 9:45, 11:45, 13:45, 16:15 (Mon-Fri)
  - Script: StrategyC_Auto.py
  - Runs 15 minutes after each brooks_reversal_4times run

#### System Maintenance:
- **synch_zerodha_local** - Every 15 min (9:15-15:30, Mon-Fri)
  - Script: synch_zerodha_cnc_positions.py --force
- **weekly_backup** - Sundays 3:00 AM
  - Script: weekly_backup.sh

### Dashboard Access Points:
- **Health Dashboard**: http://localhost:7080 - Shows all job statuses, system health
- **Market Regime Dashboard**: http://localhost:8080 - Market regime analysis visualization
- **Market Breadth Dashboard**: http://localhost:5001 - Comprehensive market internals display

### Current Status (as of implementation):

- Total Jobs: 13
- Running: 1 (health_dashboard)
- Successful: 11
- Errors: 1 (synch_zerodha_local - expected behavior)

### Files Modified:

- `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_health_check.py`
  - Added CSS styles for jobs display
  - Added JavaScript functions for jobs updates
  - Added `get_jobs_status()` function to query launchctl
  - Added jobs section to HTML template

### Backup Created:

- `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_health_check.py.backup`

The dashboard will now provide a complete view of the India-TS system health including both market regime analysis and system jobs status.

## Market Breadth Dashboard Details

### Overview:
The Market Breadth Dashboard provides real-time visualization of market internals and breadth indicators collected by the Market Breadth Scanner job.

### Features:
- **Real-time Market Internals**: Updates every 30 minutes during market hours
- **Breadth Indicators**: Advance/Decline ratio, Up/Down volume, New Highs/Lows
- **Sector Analysis**: Sector rotation analysis with performance metrics
- **Position Recommendations**: Based on market breadth conditions
- **Historical Charts**: Trend visualization for breadth indicators

### Access:
- **URL**: http://localhost:5001
- **Start Command**: `./utils/start_market_breadth_dashboard.sh`
- **Stop Command**: `./utils/stop_market_breadth_dashboard.sh`
- **Data Source**: `/Daily/Market_Regime/breadth_data/market_breadth_latest.json`

### Integration:
- Works alongside the Health Dashboard (port 7080) and Market Regime Dashboard (port 8080)
- Consumes data from Market Breadth Scanner job (runs every 30 min)
- Can be accessed remotely using solutions outlined in DASHBOARD_HOSTING_GUIDE.md

---

Created: 2025-07-04
Updated: 2025-07-11 - Added complete job schedules and Market Breadth Dashboard details