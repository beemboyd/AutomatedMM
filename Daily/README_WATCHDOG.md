# Multi-User Watchdog Management System

This directory contains a comprehensive multi-user watchdog management system that automatically detects users with active orders and manages risk monitoring for all of them simultaneously.

## Enhanced Features

### 🔥 **ATR-Based Multi-Tranche Exit Strategy**
- **Volatility-Adaptive**: Different exit strategies based on stock volatility (ATR)
- **Multiple Exit Points**: Sells portions of position at different price levels
- **Profit Target Exits**: Automatically takes profits at predefined ATR multiples
- **True Trailing Stops**: Stop losses only move upward as prices rise, never downward
- **Position Sizing Optimization**: Reduces exposure as profits grow

### 🚀 **Multi-User Support**
- **Auto-Detection**: Automatically finds users with recent orders (last 7 days)
- **Independent Processes**: Each user gets their own watchdog process with isolated state
- **Separate Logging**: User-specific log files and PID management
- **Resource Monitoring**: Track CPU and memory usage per user

## Main Scripts

### Primary Management Script
- **`manage_watchdogs.sh`** - Master script with full functionality

### Simple Wrapper Scripts (for convenience)
- **`start_watchdogs.sh`** - Start watchdogs for all users
- **`stop_watchdogs.sh`** - Stop all running watchdogs  
- **`watchdog_status.sh`** - Show status of all watchdogs

## Command Reference

### Start/Stop Operations
```bash
# Start watchdogs for all users with active orders
./manage_watchdogs.sh start

# Start with custom polling interval (3 seconds)
./manage_watchdogs.sh start -i 3.0

# Start with verbose logging
./manage_watchdogs.sh start -v

# Stop all watchdogs gracefully
./manage_watchdogs.sh stop

# Force stop all watchdogs
./manage_watchdogs.sh stop -f

# Restart all watchdogs
./manage_watchdogs.sh restart
```

### Monitoring Operations
```bash
# Show detailed status of all watchdogs
./manage_watchdogs.sh status

# List users with active orders
./manage_watchdogs.sh list-users

# View recent logs for a specific user
./manage_watchdogs.sh logs Sai

# Follow logs in real-time
./manage_watchdogs.sh follow Sai
```

### Maintenance Operations
```bash
# Clean up stale processes and PID files
./manage_watchdogs.sh cleanup

# Force cleanup including orphaned processes
./manage_watchdogs.sh cleanup -f
```

## File Structure

```
Daily/
├── manage_watchdogs.sh         # Main multi-user management script
├── start_watchdogs.sh          # Quick start wrapper
├── stop_watchdogs.sh           # Quick stop wrapper  
├── watchdog_status.sh          # Quick status wrapper
├── pids/                       # PID files for each user
│   ├── watchdog_Sai.pid
│   └── watchdog_Som.pid
├── logs/                       # User-specific log directories
│   ├── Sai/
│   │   ├── hourly_candle_watchdog_Sai.log
│   │   └── startup.log
│   └── Som/
│       ├── hourly_candle_watchdog_Som.log
│       └── startup.log
├── Current_Orders/             # Orders files by user
│   ├── Sai/
│   │   └── orders_Sai_*.json
│   └── Som/
│       └── orders_Som_*.json
└── archive_scripts/            # Legacy scripts (archived)
    ├── start_hourly_watchdog.sh
    ├── stop_hourly_watchdog.sh
    └── check_watchdog_logs.sh
```

## Advanced Usage

### Custom Intervals and Verbose Mode
```bash
# Start with 2-second polling and verbose logging
./manage_watchdogs.sh start -i 2.0 -v
```

### Log Analysis
```bash
# View portfolio summaries only
./manage_watchdogs.sh logs Sai | grep "Portfolio Summary"

# Monitor tranche exits
./manage_watchdogs.sh follow Sai | grep "TRIGGERED"

# Monitor only stop loss exits
./manage_watchdogs.sh follow Sai | grep "ATR STOP LOSS TRIGGERED"

# Monitor profit target exits
./manage_watchdogs.sh follow Sai | grep "PROFIT TARGET.*REACHED"

# View exit strategies for each stock
./manage_watchdogs.sh logs Sai | grep "Exit Strategy"

# Monitor trailing stop updates
./manage_watchdogs.sh logs Sai | grep "TRAILING STOP UPDATED"

# Check for errors
./manage_watchdogs.sh logs Sai | grep -E "(ERROR|WARNING)"
```

### System Integration
```bash
# Add to crontab for automatic startup
# @reboot /path/to/Daily/start_watchdogs.sh

# Check status from any script
if ./manage_watchdogs.sh status | grep -q "2/2 watchdogs running"; then
    echo "All watchdogs are running"
fi
```

## Multi-Tranche Exit Strategy Details

### ATR-Based Volatility Categories
The system categorizes stocks by their 20-day ATR (Average True Range) as a percentage of price:
- **Low Volatility**: ATR < 2% of price
- **Medium Volatility**: ATR 2-4% of price
- **High Volatility**: ATR > 4% of price

### Exit Tranches by Volatility
Each volatility category has its own optimized exit strategy with three tranches:

#### Low Volatility Stocks (Conservative)
- **First Exit (50%)**: At ATR-based stop loss (1.0x ATR below high)
- **Second Exit (30%)**: When profit reaches 2.0x ATR
- **Third Exit (20%)**: When profit reaches 3.0x ATR

#### Medium Volatility Stocks (Balanced)
- **First Exit (40%)**: At ATR-based stop loss (1.5x ATR below high)
- **Second Exit (30%)**: When profit reaches 2.5x ATR
- **Third Exit (30%)**: When profit reaches 4.0x ATR

#### High Volatility Stocks (Aggressive)
- **First Exit (30%)**: At ATR-based stop loss (2.0x ATR below high)
- **Second Exit (30%)**: When profit reaches 3.0x ATR
- **Third Exit (40%)**: When profit reaches 5.0x ATR

### True Trailing Stop Logic
- Stop losses are calculated from the highest price reached (daily high)
- Stop losses only move upward as prices rise, never downward
- Formula: `stop_loss = daily_high - (atr_value * multiplier)`

### Example Multi-Tranche Exit
```
Stock: INFY (Medium Volatility)
Original Position: 100 shares @ ₹1500
20-day ATR: ₹30 (2% of price)
Daily High: ₹1545

Tranche 1 (40%): Stop Loss at ₹1500 (1545 - 1.5 × 30)
Tranche 2 (30%): Profit Target at ₹1575 (1500 + 2.5 × 30)
Tranche 3 (30%): Profit Target at ₹1620 (1500 + 4.0 × 30)

Scenario 1: Price drops to ₹1498
✅ Triggers Tranche 1: Sell 40 shares (40%)
Remaining: 60 shares

Scenario 2: Price rises to ₹1580
✅ Triggers Tranche 2: Sell 30 shares (30%)
Remaining: 30 shares

Scenario 3: Price continues to ₹1625
✅ Triggers Tranche 3: Sell remaining 30 shares (30%)
Position closed with optimal exits
```

### Benefits of Multi-Tranche Exits
- **Risk Management**: Scale out gradually rather than all-or-nothing
- **Profit Locking**: Secure profits at predefined levels
- **Psychology**: Less emotional attachment to positions
- **Position Sizing**: Reduces exposure as profit increases
- **Volatility Adaptation**: Strategy adapts to each stock's volatility profile
- **Average Price Improvement**: Better average exit price vs single exit

## Enhanced Stop Loss Logic Details

### Traditional Logic (Previous)
- Trigger: `current_price < previous_hourly_low`
- Risk: Could trigger on temporary dips or market noise

### Enhanced Logic (Current)
- Trigger: `current_price < previous_hourly_low AND current_price < penultimate_hourly_low`
- Sell Price: `min(previous_low, penultimate_low) * 0.995` (with tick size rounding)
- Benefits:
  - More conservative approach
  - Reduces false signals
  - Better risk management
  - Dual-candle confirmation

### Example Enhanced Stop Loss
```
Previous Hourly Low: ₹414.05
Penultimate Hourly Low: ₹416.05
Trigger Price: ₹414.05 (minimum of both)

Current Price: ₹413.75
✅ Trigger Condition: 413.75 < 414.05 AND 413.75 < 416.05
Sell Order Price: ₹412.0 (414.05 * 0.995, rounded to tick size)
```

## Troubleshooting

### Watchdog Not Starting
```bash
# Check for stale processes
./manage_watchdogs.sh cleanup

# Verify orders files exist
./manage_watchdogs.sh list-users

# Check startup logs
cat logs/Sai/startup.log
```

### High Resource Usage
```bash
# Monitor resource usage
./manage_watchdogs.sh status

# Adjust polling interval
./manage_watchdogs.sh restart -i 10.0  # 10-second interval
```

### Log File Issues
```bash
# Check disk space
df -h

# Rotate logs if needed
./manage_watchdogs.sh stop
mv logs/Sai/hourly_candle_watchdog_Sai.log logs/Sai/hourly_candle_watchdog_Sai.log.old
./manage_watchdogs.sh start
```

## Migration from Legacy Scripts

If you were using the old scripts, the new system provides these equivalents:

| Legacy Script | New Equivalent |
|---------------|----------------|
| `start_hourly_watchdog.sh` | `./manage_watchdogs.sh start` |
| `stop_hourly_watchdog.sh` | `./manage_watchdogs.sh stop` |
| `check_watchdog_logs.sh` | `./manage_watchdogs.sh logs <user>` |

The legacy scripts have been moved to `archive_scripts/` for reference.

## Performance Notes

- **Memory Usage**: ~30-50MB per watchdog process
- **CPU Usage**: ~0.1-0.3% per watchdog during normal operation
- **Network**: Minimal API calls (price updates every 5 seconds by default)
- **Disk I/O**: Log rotation recommended for long-running systems

## Customizing Multi-Tranche Exits

You can customize the multi-tranche exit strategy by modifying the `SL_watchdog.py` script:

### Adjusting Tranche Percentages
Edit the tranche percentages in the `check_atr_stop_loss` method:

```python
# For Low Volatility stocks
exit_tranches = {
    "stop_loss": {"percent_of_position": 50, "triggered": False},  # Change 50 to desired percentage
    "profit_target_1": {"percent_of_position": 30, "triggered": False, "price_multiple": 2.0},
    "profit_target_2": {"percent_of_position": 20, "triggered": False, "price_multiple": 3.0}
}
```

### Modifying ATR Multipliers
To adjust how aggressively profit targets are set:

```python
# For Medium Volatility stocks
exit_tranches = {
    "stop_loss": {"percent_of_position": 40, "triggered": False},
    "profit_target_1": {"percent_of_position": 30, "triggered": False, "price_multiple": 2.5},  # Change 2.5 to desired multiple
    "profit_target_2": {"percent_of_position": 30, "triggered": False, "price_multiple": 4.0}
}
```

### Changing Volatility Thresholds
To redefine what counts as low, medium, or high volatility:

```python
# Calculate ATR as percentage of price
atr_percentage = (latest_atr / latest_close) * 100

# Determine volatility category and multiplier
if atr_percentage < 2.0:  # Change threshold (low volatility)
    # Low volatility
    multiplier = 1.0
    volatility_category = "Low"
elif atr_percentage <= 4.0:  # Change threshold (medium volatility)
    # Medium volatility
    multiplier = 1.5
    volatility_category = "Medium"
else:
    # High volatility
    multiplier = 2.0
    volatility_category = "High"
```

## Support

For issues or questions:
1. Check the logs: `./manage_watchdogs.sh logs <user>`
2. Verify status: `./manage_watchdogs.sh status`
3. Clean up if needed: `./manage_watchdogs.sh cleanup -f`
4. Review this README for common solutions