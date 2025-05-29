# Migration Guide

This guide explains how to migrate from the previous multi-file state system to the new consolidated state system.

## Background

The trading system previously used multiple state files to track positions and GTT orders:

1. `data/daily_ticker_tracker.json` - tracked which tickers were traded each day
2. `data/gttz_gtt_tracker.json` - tracked GTT orders
3. `data/position_data.json` - tracked position data for trailing stops 
4. `data/long_positions.txt` - tracked active long positions
5. `data/short_positions.txt` - tracked active short positions

This created problems with synchronization and could lead to duplicate orders. The new system uses a single `data/trading_state.json` file to store all state information.

## Migration Process

To migrate to the new system:

1. Back up all your existing state files
2. Run the migration script to create the new consolidated state file
3. Test that everything works correctly
4. Optionally, remove the old state files

## Migration Steps

### 1. Back up your state files

```bash
mkdir -p data/backup_$(date +%Y%m%d)
cp data/daily_ticker_tracker.json data/gttz_gtt_tracker.json data/position_data.json data/long_positions.txt data/short_positions.txt data/backup_$(date +%Y%m%d)/
```

### 2. Run the migration script

```bash
python utils/migrate_state.py --backup
```

This will:
- Create a new `data/trading_state.json` file
- Make additional backups of your state files
- Display a summary of the migrated data

### 3. Test the system

Run the risk management script to verify everything works correctly:

```bash
python scripts/manage_risk.py --verbose
```

Check that:
- All your positions are correctly tracked
- GTT orders are properly recognized
- No duplicate GTT orders are created

### 4. (Optional) Remove old state files

Once you've verified everything works correctly, you can remove the old state files:

```bash
rm data/daily_ticker_tracker.json data/gttz_gtt_tracker.json data/position_data.json data/long_positions.txt data/short_positions.txt
```

## Troubleshooting

If you encounter issues:

1. Check the logs in `logs/manage_risk.log`
2. Run with --verbose to see detailed output
3. If needed, restore the backup files and try again
4. Contact support for assistance

## New State File Format

The new state file uses a JSON format with this structure:

```json
{
  "meta": {
    "date": "2025-04-25",
    "last_updated": "2025-04-25T12:35:13.715921"
  },
  "positions": {
    "TICKER1": {
      "type": "SHORT",
      "entry_price": 502.5,
      "best_price": 502.75,
      "quantity": 199,
      "timestamp": "2025-04-25T12:29:13.419823",
      "gtt": {
        "trigger_id": 270552594,
        "trigger_price": 494.1,
        "timestamp": "2025-04-25T12:35:13.715921"
      }
    },
    "TICKER2": {
      "type": "LONG",
      "entry_price": 141.85,
      "best_price": 141.62,
      "quantity": 350,
      "timestamp": "2025-04-24T15:42:22.390695",
      "gtt": {
        "trigger_id": 270430662,
        "trigger_price": 141.20,
        "timestamp": "2025-04-24T15:42:22.390695"
      }
    }
  },
  "daily_tickers": {
    "long": ["TICKER2", "TICKER3", "TICKER4"],
    "short": ["TICKER1", "TICKER5"]
  }
}
```

This consolidation simplifies the state management and reduces the chance of synchronization errors or duplicate orders.