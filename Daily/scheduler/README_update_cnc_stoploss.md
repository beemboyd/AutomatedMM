# CNC Stoploss Updater

This tool uses Zerodha's GTT (Good Till Triggered) feature to place server-side stop-loss orders for all CNC (Delivery) positions. This ensures that stoploss orders remain active even if the trading platform is not running.

## Features

- Automatically detects all CNC positions from Zerodha holdings
- Calculates stoploss levels based on previous day's low 
- Uses server-side GTT orders that remain active until triggered, even if your system is offline
- Uses LIMIT orders (at 95% of trigger price) for more reliable execution
- Handles market-hours restrictions with `--force-place` option
- Can run continuously in loop mode, updating stoploss orders at specified intervals

## Usage

### Basic Usage

To update stoploss for all CNC positions based on previous day's low:

```bash
python update_cnc_stoploss.py
```

### Outside Market Hours

When running outside market hours, use the `--force-place` option:

```bash
python update_cnc_stoploss.py --force-place
```

This will use the latest available price data to place GTT orders.

### Dry Run Mode

To test what would happen without actually placing orders:

```bash
python update_cnc_stoploss.py --dry-run
```

### Continuous Mode

To run in continuous mode, updating GTT orders every hour:

```bash
python update_cnc_stoploss.py --loop --interval 60
```

### Options

- `--dry-run`: Simulation mode - shows what would be done without making actual changes
- `--test`: Use test data if no positions are found
- `--force`: Force update even if similar stoploss already exists
- `--refresh`: Force refresh data from API instead of using cached data
- `--force-place`: Force placement of GTT orders even outside market hours
- `--cleanup-only`: Only clean up duplicate GTT orders without placing new ones
- `--loop`: Run continuously with the specified interval
- `--interval`: Interval in minutes between runs when using `--loop` (default: 60)

### Cleaning Up Duplicate Orders

To clean up duplicate GTT orders without placing new ones:

```bash
python update_cnc_stoploss.py --cleanup-only
```

This will delete all existing GTT orders for your CNC positions without creating new ones.
You can then run the script again without the `--cleanup-only` flag to place new orders.

## Checking GTT Orders

To check existing GTT orders, use the `check_gtt_orders.py` script:

```bash
python check_gtt_orders.py
```

For detailed information:

```bash
python check_gtt_orders.py --verbose
```

To filter by ticker:

```bash
python check_gtt_orders.py --ticker RELIANCE
```

## Scheduling

For automatic daily updates, you can use the provided launchd plist file:

```bash
cp com.india-ts.update_cnc_stoploss.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.india-ts.update_cnc_stoploss.plist
```

This will run the stoploss updater every day at 2:00 PM.

## Important Notes

1. GTT orders remain active for 1 year from creation
2. GTT orders will be cancelled if the position is sold
3. If the stoploss is too close to current price, it will be adjusted to 5% below current price
4. LIMIT orders are used (at 95% of trigger price) for more reliable execution
5. For market hours restriction, consider scheduling the script to run after market hours with `--force-place` option