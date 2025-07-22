# VSR Tracker Start Script Guide

## Overview
The `start_vsr_tracker.sh` script is a bash script that launches the VSR (Volume Spread Ratio) Tracker Service as a background daemon process. It handles process management, logging, and ensures only one instance runs per user.

## How It Works

### 1. Script Initialization
```bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
```
- Determines the script's directory location
- Changes to that directory to ensure relative paths work correctly

### 2. User Configuration
```bash
USER="Sai"  # Default user
```
- Sets default user to "Sai"
- Can be overridden with command-line arguments

### 3. Command Line Argument Parsing
```bash
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER="$2"
            shift 2
            ;;
```
- Accepts `-u` or `--user` flag to specify different user
- Example: `./start_vsr_tracker.sh -u John`

### 4. PID (Process ID) Management
```bash
PID_DIR="../pids"
PID_FILE="$PID_DIR/vsr_tracker_${USER}.pid"
```
- Creates a PID directory at `Daily/pids/`
- Stores process ID in `vsr_tracker_USERNAME.pid` file
- Prevents multiple instances from running simultaneously

### 5. Duplicate Process Check
```bash
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "VSR Tracker is already running..."
        exit 1
    else
        rm "$PID_FILE"  # Remove stale PID file
    fi
fi
```
- Checks if a PID file exists
- Verifies if the process is actually running
- Removes stale PID files from crashed processes

### 6. Logging Setup
```bash
LOG_DIR="../logs/vsr_tracker"
LOG_FILE="$LOG_DIR/vsr_tracker_$(date +%Y%m%d).log"
```
- Creates log directory at `Daily/logs/vsr_tracker/`
- Creates daily log files named `vsr_tracker_YYYYMMDD.log`
- All output from the Python script goes to this log

### 7. Service Launch
```bash
nohup python3 vsr_tracker_service.py -u "$USER" >> "$LOG_FILE" 2>&1 &
PID=$!
```
- `nohup`: Prevents the process from terminating when terminal closes
- `python3 vsr_tracker_service.py`: The actual VSR tracker Python script
- `-u "$USER"`: Passes the user parameter to Python script
- `>> "$LOG_FILE" 2>&1`: Redirects both stdout and stderr to log file
- `&`: Runs the process in background
- `$!`: Captures the process ID of the launched background process

### 8. Success Verification
```bash
sleep 3
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ VSR Tracker started successfully (PID: $PID)"
    echo "View logs: tail -f $LOG_FILE"
    echo "High scores: tail -f $LOG_FILE | grep -E 'Score: [5-9][0-9]|Score: 100'"
else
    echo "✗ Failed to start VSR Tracker"
    rm "$PID_FILE"
    exit 1
fi
```
- Waits 3 seconds for process to initialize
- Checks if process is still running
- Provides helpful commands for monitoring:
  - View real-time logs
  - Filter for high-scoring stocks (50+ score)

## Usage Examples

### Start with default user (Sai):
```bash
./start_vsr_tracker.sh
```

### Start for different user:
```bash
./start_vsr_tracker.sh -u Som
```

### Monitor the service:
```bash
# View real-time logs
tail -f ../logs/vsr_tracker/vsr_tracker_20250121.log

# See only high-scoring stocks
tail -f ../logs/vsr_tracker/vsr_tracker_20250121.log | grep -E 'Score: [5-9][0-9]|Score: 100'

# Check if running
./status_vsr_tracker.sh -u Sai
```

## File Locations

- **PID File**: `Daily/pids/vsr_tracker_USERNAME.pid`
- **Log Files**: `Daily/logs/vsr_tracker/vsr_tracker_YYYYMMDD.log`
- **Python Script**: `Daily/services/vsr_tracker_service.py`

## Key Features

1. **Single Instance Enforcement**: Only one VSR tracker can run per user
2. **Daily Log Rotation**: New log file created each day
3. **Background Execution**: Runs as daemon, survives terminal closure
4. **Clean Process Management**: Tracks PID for easy stop/status checks
5. **User Isolation**: Multiple users can run separate instances

## Troubleshooting

### Service won't start:
1. Check if already running: `ps aux | grep vsr_tracker`
2. Remove stale PID: `rm ../pids/vsr_tracker_USERNAME.pid`
3. Check Python errors in log file

### High CPU/Memory usage:
- The service runs minute-by-minute scoring
- Check log file size, rotate if needed
- Verify market hours logic is working

### Missing dependencies:
- Ensure Python 3 is installed
- Check that vsr_tracker_service.py exists
- Verify user has write permissions for logs/pids directories