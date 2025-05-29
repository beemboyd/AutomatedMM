# Current Orders Folder

This folder contains synchronized current positions data from your Zerodha account, organized by API key.

## Directory Structure

```
Current_Orders/
├── README.md
└── {api_key}/
    └── {api_key}_Current_Positions.json    # Current positions only (updated by scheduler)
```

## File Generated

### Current Positions File
- **`{api_key}_Current_Positions.json`** - Contains only current positions data
- **Purpose**: Designed for scheduler jobs and polling applications
- **Behavior**: File is overwritten on each sync (no historical data)
- **Usage**: Read by stop loss polling applications

## Current Positions Data Structure

The Current Positions file contains:

```json
{
  "metadata": {
    "timestamp": "2025-05-24T17:17:20.889240",
    "api_key": "ms2m54xupkjzvbwj",
    "account_id": "OQC356",
    "user_name": "Sai Kumar Reddy Kothavenkata",
    "available_cash": 17026472.8,
    "last_updated": "2025-05-24T17:17:20.889250"
  },
  "current_positions": [
    {
      "tradingsymbol": "TICKER",
      "exchange": "NSE",
      "product": "MIS",
      "quantity": 100,
      "average_price": 1500.0,
      "last_price": 1520.0,
      "pnl": 2000.0,
      "unrealised": 2000.0,
      "realised": 0.0,
      "position_type": "day",
      "instrument_token": 12345
    }
  ],
  "positions_summary": {
    "total_positions": 1,
    "total_pnl": 2000.0,
    "mis_positions": 1,
    "cnc_positions": 0,
    "long_positions": 1,
    "short_positions": 0
  }
}
```

## Usage

### Synchronize Current Positions (Manual)
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/scripts
python3 synch_zerodha_local.py
```

### Scheduler Job Example
```bash
# Run every 5 minutes during market hours
*/5 9-15 * * 1-5 cd /Users/maverick/PycharmProjects/India-TS/Daily/scripts && python3 synch_zerodha_local.py
```

### Polling Application Usage
```python
import json

# Read current positions
with open('/path/to/Current_Orders/ms2m54xupkjzvbwj/ms2m54xupkjzvbwj_Current_Positions.json', 'r') as f:
    positions_data = json.load(f)
    
current_positions = positions_data['current_positions']
available_cash = positions_data['metadata']['available_cash']
```

## Configuration

The script reads configuration from `/Users/maverick/PycharmProjects/India-TS/config.ini`:

```ini
[API]
api_key = ms2m54xupkjzvbwj
access_token = your_access_token
```

## Key Features

### Single File Design
- Only one JSON file per API key
- File is overwritten on each sync
- No historical data stored (ideal for real-time monitoring)

### API Key Organization
- Each API key gets its own subdirectory
- Prevents mixing data from different accounts
- Easy to manage multiple Zerodha accounts

### Scheduler Friendly
- Designed to be run by cron jobs or task schedulers
- Minimal overhead and fast execution
- Overwrites existing file to prevent disk space issues

### Polling Application Ready
- Simple JSON structure for easy parsing
- Contains all essential position information
- Includes summary statistics for quick overview

## Data Fields

### Metadata
- **timestamp**: When the sync was performed
- **api_key**: Zerodha API key
- **account_id**: Account identifier
- **user_name**: Account holder name
- **available_cash**: Available cash in INR
- **last_updated**: File update timestamp

### Current Positions
- **tradingsymbol**: Stock symbol
- **exchange**: Exchange (NSE/BSE)
- **product**: Product type (MIS/CNC)
- **quantity**: Position quantity (positive=long, negative=short)
- **average_price**: Average entry price
- **last_price**: Current market price
- **pnl**: Profit/Loss
- **unrealised**: Unrealized P&L
- **realised**: Realized P&L
- **position_type**: "day" (MIS) or "net" (CNC)
- **instrument_token**: Unique instrument identifier

### Positions Summary
- **total_positions**: Count of all positions
- **total_pnl**: Sum of all P&L
- **mis_positions**: Count of MIS positions
- **cnc_positions**: Count of CNC positions
- **long_positions**: Count of long positions
- **short_positions**: Count of short positions

## Use Cases

1. **Stop Loss Monitoring**: Polling applications can read positions and place stop loss orders
2. **Scheduler Jobs**: Run periodically to keep positions data updated
3. **Risk Management**: Monitor position sizes and P&L in real-time
4. **Account Monitoring**: Track available cash and position counts
5. **Multi-Account Management**: Each API key maintains separate position data

## Notes

- File is overwritten on each sync (no versioning)
- All monetary values are in INR (₹)
- Times are in ISO 8601 format
- Only non-zero positions are included
- Designed for real-time applications, not historical analysis