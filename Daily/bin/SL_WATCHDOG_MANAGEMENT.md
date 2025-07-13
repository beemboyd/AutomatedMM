# SL Watchdog Management Guide

## Overview

This directory contains shell scripts for managing SL (Stop Loss) Watchdog processes. The system ensures that only one SL watchdog runs at a time and provides easy switching between standard and regime-based versions.

## Available Scripts

### 1. **check_sl_watchdog_status.sh**
Check the status of all SL watchdog processes.

```bash
./check_sl_watchdog_status.sh
```

Features:
- Shows running status of both standard and regime watchdogs
- Displays process details (PID, runtime, CPU/memory usage)
- Detects orphaned processes
- Provides recommendations

### 2. **start_sl_watchdog_regime.sh**
Start the intelligent regime-based SL watchdog.

```bash
./start_sl_watchdog_regime.sh
```

Features:
- Checks for existing watchdog processes
- Prompts to stop conflicting processes
- User selection menu
- Optional orders file specification
- Creates logs in `Daily/logs/<username>/`

### 3. **stop_sl_watchdog_regime.sh**
Stop the regime-based SL watchdog gracefully.

```bash
./stop_sl_watchdog_regime.sh
```

Features:
- Graceful shutdown with SIGTERM
- Force kill if needed
- Confirmation prompt
- Cleans up PID files

### 4. **start_sl_watchdog.sh**
Start the standard ATR-based SL watchdog.

```bash
./start_sl_watchdog.sh
```

### 5. **stop_sl_watchdog.sh**
Stop the standard SL watchdog.

```bash
./stop_sl_watchdog.sh
```

## Process Management

### PID Files
- Standard watchdog: `Daily/pids/sl_watchdog.pid`
- Regime watchdog: `Daily/pids/sl_watchdog_regime.pid`

### Log Files
- Location: `Daily/logs/<username>/SL_watchdog_*.log`
- Format: `SL_watchdog_<type>_<username>_YYYYMMDD_HHMMSS.log`

## Usage Examples

### 1. Check Current Status
```bash
cd Daily/bin
./check_sl_watchdog_status.sh
```

### 2. Switch from Standard to Regime
```bash
# The start script will detect and handle the switch
./start_sl_watchdog_regime.sh
```

### 3. Monitor Logs
```bash
# Find the log file from status check
tail -f ../logs/Sai/SL_watchdog_regime_Sai_20250709_140000.log
```

### 4. Emergency Stop
```bash
# If scripts fail, manually kill process
kill -9 $(cat ../pids/sl_watchdog_regime.pid)
rm ../pids/sl_watchdog_regime.pid
```

## Safety Features

1. **Single Instance**: Only one SL watchdog can run at a time
2. **Conflict Detection**: Automatically detects running processes
3. **Graceful Switching**: Prompts before stopping existing processes
4. **Process Verification**: Checks if process started successfully
5. **Orphan Detection**: Finds processes not tracked by PID files

## Troubleshooting

### Process Won't Start
1. Check if another instance is running:
   ```bash
   ./check_sl_watchdog_status.sh
   ```
2. Check for orphaned processes:
   ```bash
   ps aux | grep -E "[p]ython.*SL_watchdog"
   ```
3. Check log files for errors

### Process Won't Stop
1. Try force kill:
   ```bash
   kill -9 <PID>
   ```
2. Remove stale PID file:
   ```bash
   rm ../pids/sl_watchdog*.pid
   ```

### Wrong User Selected
1. Stop the current process
2. Restart with correct user

## Best Practices

1. **Always Check Status First**: Run status check before starting/stopping
2. **Use Regime Version**: Preferred for intelligent stop losses
3. **Monitor Logs**: Keep an eye on logs for the first few minutes
4. **Clean Shutdown**: Always use stop scripts instead of kill -9
5. **Review Volume Anomaly Warnings**: Check logs for exhaustion pattern warnings

## Cron Setup (Optional)

To automatically start on system boot:

```bash
# Add to crontab
@reboot sleep 60 && /path/to/Daily/bin/start_sl_watchdog_regime.sh
```

## Volume-Price Anomaly Detection (NEW)

Both SL watchdog versions now include volume-price anomaly detection to identify potential exhaustion patterns:

### Features:
- **Automatic Detection**: Checks every 5 minutes for volume-price divergences
- **Exhaustion Scoring**: 0-8 scale based on multiple patterns
- **Warning Levels**:
  - HIGH RISK (Score ≥4): Strong exhaustion warning
  - MEDIUM RISK (Score 3): Monitor closely
  - LOW RISK (Score 2): Informational only

### Patterns Detected:
1. **Volume Exhaustion**: High volume (>3x) with low momentum (<5%)
2. **Efficiency Breakdown**: Low momentum per unit volume
3. **Narrow Range**: High volume with narrow daily range (<1.5%)
4. **Price Rejection**: Close near day's low with high volume

### Log Output Example:
```
🚨 HIGH EXHAUSTION RISK - JAGSNPHARM: Score 5/8
   Volume: 7.5x | Momentum: 4.7% | Efficiency: 0.63
   - Volume exhaustion: 7.5x volume but only 4.7% move
   - Efficiency breakdown: 0.63 momentum/volume ratio
   ⚠️ RECOMMENDATION: Consider tightening stops or reducing position
```

This feature helps identify tops and potential reversals before positions hit stop losses.

## Notes

- The regime version requires Market Regime Analysis to be running
- Falls back to standard ATR logic if regime data unavailable
- Processes automatically shut down at market close (3:30 PM IST)
- Supports all users configured in config.ini
- Volume anomaly detection requires historical data access via Zerodha API