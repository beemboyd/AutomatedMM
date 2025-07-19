# Daily Scheduler Scripts

This directory contains automated scheduler scripts for running various trading scanners and analysis tools.

## FNO Scanner Scheduler

### Overview
The FNO scanner scheduler (`run_fno_scanners.py`) automatically runs Keltner Channel Upper and Lower Limit Trending scanners specifically for F&O (Futures & Options) stocks.

### Features
- Runs KC Upper and Lower scanners for F&O stocks only
- Executes hourly between 9:00 AM - 3:30 PM IST on weekdays
- Automatically skips weekends and market holidays
- Separate output folders for Long and Short opportunities
- Detailed logging of all operations

### Usage

#### Single Run (Manual)
```bash
python scheduler/run_fno_scanners.py --mode single
```

#### Continuous Mode (Hourly during market hours)
```bash
python scheduler/run_fno_scanners.py --mode continuous
```

#### With specific user credentials
```bash
python scheduler/run_fno_scanners.py --user Sai --mode continuous
```

### Command Line Options
- `-u, --user`: User name for API credentials (default: Sai)
- `-m, --mode`: Run mode - single or continuous (default: continuous)
- `-i, --interval`: Interval in minutes for continuous mode (default: 60)

### Output Structure
```
Daily/FNO/
├── Long/                          # Long opportunities (KC Upper breakouts)
│   ├── KC_Upper_Limit_Trending_FNO_*.xlsx
│   ├── Detailed_Analysis/
│   │   └── KC_Upper_Limit_Trending_FNO_*.html
│   └── PDF/
│       └── KC_Upper_Limit_Trending_FNO_*.pdf
└── Short/                         # Short opportunities (KC Lower breakdowns)
    ├── KC_Lower_Limit_Trending_FNO_*.xlsx
    ├── Detailed_Analysis/
    │   └── KC_Lower_Limit_Trending_FNO_*.html
    └── PDF/
        └── KC_Lower_Limit_Trending_FNO_*.pdf
```

### Scheduling with Cron (Linux/Mac)
To run the FNO scanner automatically every hour during market hours:

1. Open crontab:
```bash
crontab -e
```

2. Add the following line:
```bash
0 9-15 * * 1-5 cd /path/to/India-TS && /usr/bin/python3 Daily/scheduler/run_fno_scanners.py --mode single >> Daily/logs/fno_scanner_cron.log 2>&1
```

This runs the scanner at the start of every hour from 9 AM to 3 PM, Monday through Friday.

### Scheduling with Task Scheduler (Windows)
1. Open Task Scheduler
2. Create Basic Task
3. Name: "FNO KC Scanner"
4. Trigger: Weekly, Monday-Friday, Starting at 9:00 AM
5. Action: Start a program
   - Program: `python.exe` (full path)
   - Arguments: `"C:\path\to\India-TS\Daily\scheduler\run_fno_scanners.py" --mode continuous`
   - Start in: `C:\path\to\India-TS`

### Logs
All scheduler activities are logged to:
- `Daily/logs/fno_scanner_scheduler.log`

### Market Holidays
The scheduler checks for market holidays. To add holidays:
1. Edit `run_fno_scanners.py`
2. Update the `holidays` list in the `is_market_holiday()` function
3. Add dates in format: `datetime(YYYY, M, D).date()`

### Troubleshooting
1. **Scanner not running**: Check if market is open and it's a weekday
2. **Permission errors**: Ensure the script has execute permissions
3. **API errors**: Verify credentials in `config.ini` for the specified user
4. **No output**: Check the logs in `Daily/logs/fno_scanner_scheduler.log`

### Integration with Existing Systems
The FNO scanner integrates with:
- Market Regime Analysis for trend confirmation
- Position sizing based on F&O lot sizes
- Risk management with predefined stop losses
- Automated alert generation for high-probability setups