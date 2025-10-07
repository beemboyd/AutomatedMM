# PSAR Watchdog - Log Monitoring Guide

## 📁 Log File Locations

### Main Log File
The PSAR watchdog logs are written to user-specific directories:

```
/Users/maverick/PycharmProjects/India-TS/Daily/logs/{USER_NAME}/SL_watchdog_PSAR_{USER_NAME}.log
```

### Example for User "Sai"
```bash
/Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

## 📊 Log Configuration

### Log Format
```
%(asctime)s - %(levelname)s - %(message)s
```

**Example:**
```
2025-10-07 15:30:45 - INFO - PARABOLIC SAR (PSAR) TRAILING STOP LOSS ENABLED
2025-10-07 15:30:46 - INFO - Subscribed RELIANCE (token: 738561) to websocket for PSAR monitoring
2025-10-07 15:31:12 - INFO - RELIANCE: New 1000-tick candle - O: ₹2456.20, H: ₹2458.50, L: ₹2455.10, C: ₹2457.80 | PSAR: ₹2450.15 (LONG)
```

### Log Rotation
- **Max File Size**: 10 MB per log file
- **Backup Count**: 5 backup files kept
- **Total Storage**: Up to 60 MB per user (10 MB × 6 files)

### Log Levels
- **INFO**: Normal operations, position updates, PSAR calculations
- **WARNING**: Configuration issues, missing positions
- **ERROR**: Websocket errors, API failures, calculation errors
- **DEBUG**: Detailed tick data, candle formation (only with `-v` flag)

## 🔍 Monitoring Commands

### 1. Real-Time Log Monitoring (Tail)
```bash
# For user "Sai"
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# With color highlighting (if installed)
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log | grep --color=auto -E 'ERROR|WARNING|PSAR'
```

### 2. Filter by Log Level
```bash
# Show only errors
grep "ERROR" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Show only warnings
grep "WARNING" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Show PSAR-specific events
grep "PSAR" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

### 3. Search for Specific Ticker
```bash
# Find all RELIANCE activity
grep "RELIANCE" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Find PSAR exits for a ticker
grep -E "RELIANCE.*PSAR Exit" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

### 4. Count Events
```bash
# Count PSAR trend reversals
grep -c "PSAR TREND REVERSAL" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Count exit orders
grep -c "Queuing SELL order" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

### 5. View Last N Lines
```bash
# Last 50 lines
tail -n 50 /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Last 100 lines with grep filter
tail -n 100 /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log | grep "PSAR"
```

### 6. Check Log File Size
```bash
ls -lh /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log*
```

## 📝 Key Log Messages to Monitor

### 1. **Startup Messages**
```
PARABOLIC SAR (PSAR) TRAILING STOP LOSS ENABLED
- Initial Acceleration Factor: 0.02
- AF Increment per new extreme: 0.02
- Maximum AF: 0.2
- Tick Aggregate Size: 1000 ticks per candle
PRODUCT TYPE FILTER: CNC
Websocket connected: 200
Subscribed to 5 instruments for PSAR monitoring
```

### 2. **Position Loading**
```
Fetching all CNC positions from Zerodha account for user: Sai
Found 5 CNC positions from positions API
Tracking CNC position - RELIANCE: 50 shares @ ₹2450.00
Subscribed RELIANCE (token: 738561) to websocket for PSAR monitoring
```

### 3. **Tick Aggregation & PSAR Updates**
```
RELIANCE: New 1000-tick candle - O: ₹2456.20, H: ₹2458.50, L: ₹2455.10, C: ₹2457.80 | PSAR: ₹2450.15 (LONG)
```

### 4. **PSAR Trend Reversals** ⚠️
```
RELIANCE: PSAR TREND REVERSAL - Now SHORT @ ₹2460.00
```

### 5. **Exit Signals** 🚨
```
RELIANCE: PSAR Exit - LONG position: Price ₹2448.50 below PSAR ₹2450.15
Queuing SELL order for 50 shares at ₹2445.95
```

### 6. **Order Execution**
```
Order placed successfully for RELIANCE with ID 250101234567
Order execution completed for RELIANCE
```

### 7. **Websocket Events**
```
# Connection
Websocket connected: 200

# Disconnection
Websocket closed: 1006 - Connection lost
Attempting to reconnect websocket in 5 seconds...

# Reconnection
Websocket thread started for real-time tick data
```

### 8. **Errors to Watch** ❌
```
# Position not found
ERROR - RELIANCE: Position not found in broker account. Removing from tracking.

# Websocket errors
ERROR - Websocket error: 1002 - Authentication failed

# API errors
ERROR - Error fetching batch of prices: Rate limit exceeded

# Calculation errors
ERROR - Error calculating PSAR for RELIANCE: insufficient data
```

## 🎛️ Verbose Mode (Debug Logging)

To enable detailed debug logging:
```bash
python SL_watchdog_PSAR.py --verbose --product-type CNC
```

Debug logs include:
- Individual tick processing
- Tick buffer states
- Detailed PSAR calculations
- Candle OHLC values
- Stop loss checks for each tick

## 📈 Log Analysis Scripts

### Quick Status Check
```bash
#!/bin/bash
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log"

echo "=== PSAR Watchdog Status ==="
echo "Last 5 entries:"
tail -5 "$LOG_FILE"
echo ""
echo "Errors in last hour:"
grep "ERROR" "$LOG_FILE" | tail -10
echo ""
echo "Active positions:"
grep "Tracking.*position" "$LOG_FILE" | tail -10
```

### Exit Summary
```bash
#!/bin/bash
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log"

echo "=== PSAR Exit Summary (Today) ==="
TODAY=$(date "+%Y-%m-%d")
grep "$TODAY.*PSAR Exit" "$LOG_FILE" | while read line; do
    echo "$line"
done
```

## 🔔 Alert Setup (Optional)

### Monitor for Critical Events
```bash
#!/bin/bash
# watch_psar_alerts.sh

LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log"

tail -f "$LOG_FILE" | while read line; do
    case "$line" in
        *"ERROR"*)
            osascript -e "display notification \"PSAR Error: $line\" with title \"PSAR Watchdog Alert\""
            ;;
        *"PSAR Exit"*)
            osascript -e "display notification \"Exit Signal: $line\" with title \"PSAR Exit Alert\""
            ;;
        *"PSAR TREND REVERSAL"*)
            osascript -e "display notification \"Trend Reversal: $line\" with title \"PSAR Alert\""
            ;;
    esac
done
```

## 📊 Common Log Patterns

### Pattern 1: Normal Operation
```
15:30:45 - INFO - Websocket connected
15:30:46 - INFO - Subscribed to 5 instruments
15:31:12 - INFO - New 1000-tick candle (normal)
15:31:45 - INFO - New 1000-tick candle (normal)
```

### Pattern 2: Exit Triggered
```
15:32:18 - INFO - RELIANCE: New candle | PSAR: ₹2450.15 (LONG)
15:32:19 - INFO - RELIANCE: PSAR Exit - LONG position: Price ₹2448.50 below PSAR ₹2450.15
15:32:19 - INFO - Queuing SELL order for 50 shares at ₹2445.95
15:32:20 - INFO - Order placed successfully for RELIANCE with ID 250101234567
```

### Pattern 3: Websocket Reconnection
```
15:45:00 - WARNING - Websocket closed: 1006 - Connection lost
15:45:00 - INFO - Attempting to reconnect websocket in 5 seconds...
15:45:05 - INFO - Websocket connected: 200
15:45:06 - INFO - Subscribed to 5 instruments for PSAR monitoring
```

## 🛠️ Troubleshooting

### Issue: No log file created
**Solution:** Check if user directory exists
```bash
mkdir -p /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai
```

### Issue: Log file too large
**Solution:** Logs rotate automatically at 10MB. Check rotation:
```bash
ls -lh /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log*
```

### Issue: Missing recent logs
**Solution:** Check if watchdog is running
```bash
ps aux | grep SL_watchdog_PSAR
```

### Issue: Too many errors
**Solution:** Check specific error types
```bash
grep "ERROR" /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log | cut -d'-' -f3 | sort | uniq -c | sort -rn
```

## 📱 Integration with Monitoring Tools

### LogTail (macOS)
```bash
# Install logtail if needed
brew install logtail

# Monitor with highlights
logtail /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

### VS Code
1. Open log file in VS Code
2. Install "Log File Highlighter" extension
3. Auto-detects log levels and highlights

### Terminal Dashboard
```bash
# Simple dashboard
watch -n 5 'tail -20 /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log'
```

## 🔗 Related Logs

When debugging issues, also check:

1. **Original ATR Watchdog** (for comparison):
   ```
   /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_Sai.log
   ```

2. **Token Refresh Logs**:
   ```
   /Users/maverick/PycharmProjects/India-TS/Daily/logs/token_refresh/
   ```

3. **Pre-Market Setup**:
   ```
   /Users/maverick/PycharmProjects/India-TS/Daily/logs/pre_market/
   ```

## 📋 Log Retention Policy

- **Active Log**: Current `SL_watchdog_PSAR_{USER}.log`
- **Rotated Logs**: `.log.1` through `.log.5`
- **Auto-cleanup**: Oldest backup deleted when 6th rotation occurs
- **Manual Archive**: Move old logs to `archive/` directory if needed

## 🚀 Quick Reference

```bash
# Real-time monitoring
tail -f ~/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Search for ticker
grep "RELIANCE" ~/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Check errors
grep "ERROR" ~/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log | tail -20

# View exits
grep "PSAR Exit" ~/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log

# Count trend reversals today
grep "$(date +%Y-%m-%d).*PSAR TREND REVERSAL" ~/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log | wc -l
```
