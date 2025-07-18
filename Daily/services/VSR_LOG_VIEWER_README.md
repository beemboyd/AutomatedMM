# VSR Log Viewer

## Overview
A web-based log viewer for VSR (Volume Spread Ratio) logs with auto-refresh capability. Displays the last 100 lines of VSR Anomaly and VSR Tracker logs in a formatted, easy-to-read interface.

## Features
- **Dual Log Support**: Switch between VSR Anomaly and VSR Tracker logs
- **Auto-Refresh**: Automatically refreshes every 60 seconds (configurable)
- **Syntax Highlighting**: Color-coded log levels, timestamps, and tickers
- **Dark Theme**: Easy on the eyes for extended monitoring
- **REST API**: JSON endpoint for programmatic access

## Access
- **Web Interface**: http://localhost:9901
- **API Endpoint**: http://localhost:9901/api/logs?type=anomaly
- **API Endpoint**: http://localhost:9901/api/logs?type=tracker

## Usage

### Start the Log Viewer
```bash
# Using the start script
./Daily/services/start_vsr_log_viewer.sh

# Or directly with Python
python3 Daily/services/vsr_log_viewer.py

# With custom options
python3 Daily/services/vsr_log_viewer.py --port 9901 --lines 200 --refresh 30
```

### Command Line Options
- `--port PORT`: Port to run on (default: 9901)
- `--lines N`: Number of lines to display (default: 100)
- `--refresh N`: Refresh interval in seconds (default: 60)

### Stop the Log Viewer
```bash
pkill -f "vsr_log_viewer.py"
```

## Log Files Monitored
1. **VSR Anomaly Logs**
   - Path: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_anomaly/`
   - Pattern: `vsr_anomaly_YYYYMMDD.log`
   - Contains: Anomaly detection events, unusual volume patterns

2. **VSR Tracker Logs**
   - Path: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/`
   - Pattern: `vsr_tracker_YYYYMMDD.log`
   - Contains: Real-time VSR tracking, momentum signals

## Color Coding
- **Timestamps**: Blue
- **INFO Level**: Cyan
- **WARNING Level**: Yellow
- **ERROR Level**: Red
- **Anomaly Detected**: Bold Red
- **Ticker Symbols**: Purple

## API Usage

### Get Anomaly Logs
```bash
curl http://localhost:9901/api/logs?type=anomaly
```

### Get Tracker Logs
```bash
curl http://localhost:9901/api/logs?type=tracker
```

### Response Format
```json
{
    "status": "success",
    "log_type": "anomaly",
    "log_file": "vsr_anomaly_20250718.log",
    "last_updated": "2025-07-18 09:30:00",
    "lines_count": 100,
    "log_lines": [
        "2025-07-18 09:29:45,123 - INFO - VSR Anomaly Detection Started",
        "..."
    ]
}
```

## Integration with Job Manager
The VSR Log Viewer can be added to the Job Manager Dashboard for centralized monitoring. It provides real-time insights into:
- Volume anomalies detected
- Momentum signals triggered
- System health and performance

## Troubleshooting

### No Log Data Available
- Check if log files exist in the specified directories
- Ensure VSR services are running and generating logs
- Verify file permissions

### Port Already in Use
```bash
# Find process using port 9901
lsof -i :9901

# Kill the process
kill -9 <PID>
```

### Auto-refresh Not Working
- Check browser console for JavaScript errors
- Ensure browser allows auto-refresh
- Try manually refreshing the page

## Future Enhancements
- Search functionality
- Log filtering by date/time range
- Export logs to CSV/PDF
- Email alerts for critical anomalies
- Historical log analysis