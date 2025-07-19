# India-TS Job & Dashboard Manager

A comprehensive web-based dashboard for monitoring and controlling all India-TS scheduled jobs and dashboards.

## Features

- **Real-time Monitoring**: View status of all 20+ scheduled jobs and 4 dashboards
- **Job Control**: Reload, restart, or stop any job with a single click
- **Dashboard Management**: Start, restart, or stop any dashboard from one interface
- **Status Indicators**: Color-coded status badges (Running, Success, Error, Not Loaded, Stopped)
- **Auto-refresh**: Updates every 10 seconds automatically
- **Statistics**: Summary cards showing total items, running, successful, error counts, and dashboard count

## Access

- **URL**: http://localhost:9090
- **Port**: 9090

## Starting the Dashboard

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Health
./start_job_manager.sh
```

## Stopping the Dashboard

```bash
./stop_job_manager.sh
```

## Job Actions

### 1. Reload
- Unloads and reloads the job's launchd configuration
- Useful when job configuration has been updated
- Available for all jobs regardless of current status

### 2. Restart
- Stops and starts a running job
- Only available for jobs currently in "running" status
- Useful for troubleshooting stuck processes

### 3. Stop
- Stops a running job
- Only available for jobs currently in "running" status
- Job will not restart until manually started or scheduled time

## Dashboard Actions

### 1. Start
- Starts a stopped dashboard
- Only available when dashboard is not running
- Uses either start scripts or launchctl commands

### 2. Restart
- Stops and restarts a dashboard
- Only available for running dashboards
- Useful for applying configuration changes

### 3. Stop
- Stops a running dashboard
- Only available for running dashboards
- Dashboard remains stopped until manually started

## Managed Dashboards

1. **Health Dashboard (Port 7080)**
   - Managed by launchctl (com.india-ts.health_dashboard)
   - Shows system health and job statuses
   - Runs 24/7 with KeepAlive

2. **Market Regime Dashboard (Port 8080)**
   - Managed by launchctl (com.india-ts.market_regime_dashboard)
   - Displays market regime analysis
   - Runs 24/7 with KeepAlive

3. **Market Breadth Dashboard (Port 5001)**
   - Manual start/stop with shell scripts
   - Shows comprehensive market internals
   - Started on demand

4. **Job Manager Dashboard (Port 9090)**
   - This dashboard itself
   - Manual start/stop with shell scripts
   - Central control for all jobs and dashboards

## Security Note

This dashboard provides powerful system control capabilities. Ensure it's only accessible from trusted networks. The dashboard binds to all interfaces (0.0.0.0) by default for development convenience.

## Technical Details

- Built with Flask web framework
- Uses launchctl commands for job control
- Handles both launchctl-managed and script-based dashboards
- Refreshes status every 10 seconds
- No authentication (add if needed for production use)

## Dashboard Types

- **Launchctl-managed**: Health Dashboard (7080) and Market Regime Dashboard (8080) are controlled via launchctl commands
- **Script-based**: Market Breadth Dashboard (5001) and Job Manager Dashboard (9090) use start/stop shell scripts