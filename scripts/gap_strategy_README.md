# Gap Strategy Trading System

## Overview

The Gap Strategy Trading System identifies potential trading opportunities based on price gaps between market sessions combined with intraday trend analysis. The system scans the market during the first 45 minutes of trading (9:15 AM to 10:00 AM) to find stocks that have gapped up or down from the previous day's close and are showing specific trend patterns.

## Strategy Logic

The system identifies four primary trading setups:

1. **Gap Up + Downtrend (SHORT)**: Stocks that have gapped up from the previous day's close but are showing a downtrend pattern (Lower Highs, Lower Lows) in the first few 5-minute candles of the day.

2. **Gap Down + Uptrend (LONG)**: Stocks that have gapped down from the previous day's close but are showing an uptrend pattern (Higher Highs, Higher Lows) in the first few 5-minute candles of the day.

3. **Gap Up + Uptrend (LONG)**: Stocks that have gapped up and are continuing to trend higher, showing Higher Highs and Higher Lows.

4. **Gap Down + Downtrend (SHORT)**: Stocks that have gapped down and are continuing to trend lower, showing Lower Highs and Lower Lows.

## Technical Implementation

- **Gap Detection**: Calculates the percentage difference between the previous day's closing price and the current day's opening price.
- **Trend Analysis**: Examines the most recent 5-minute candles to identify Higher Highs/Higher Lows (uptrend) or Lower Highs/Lower Lows (downtrend) patterns.
- **Scheduled Execution**: Starts at 9:30 AM and runs every 3 minutes until 9:45 AM on weekdays (Monday-Friday) to capture evolving opportunities after market open.
- **Output**: Generates two Excel files with timestamp in the data directory:
  - `Gap_Strategy_Long_[TIMESTAMP].xlsx`: Long trade candidates
  - `Gap_Strategy_Short_[TIMESTAMP].xlsx`: Short trade candidates

## Installation and Usage

### Automated Service (Recommended)

The gap strategy scanner is designed to run as a scheduled service on macOS:

1. **Install the service**:
   ```
   python3 utils/install_gap_strategy_service.py install
   ```

2. **Start the service**:
   ```
   python3 utils/install_gap_strategy_service.py start
   ```

3. **Check service status**:
   ```
   python3 utils/install_gap_strategy_service.py status
   ```

4. **Stop the service** (if needed):
   ```
   python3 utils/install_gap_strategy_service.py stop
   ```

5. **Uninstall the service** (if needed):
   ```
   python3 utils/install_gap_strategy_service.py uninstall
   ```

### Manual Execution

You can also run the scanner manually:

```
python3 scripts/scan_markets_gap.py [options]
```

Options:
- `-i, --input PATH`: Specify an alternative input Excel file with ticker list (default: data/Ticker.xlsx)
- `-v, --verbose`: Increase output verbosity
- `--gap-up-threshold VALUE`: Minimum gap up percentage to consider (default: 1.0%)
- `--gap-down-threshold VALUE`: Maximum gap down percentage to consider (default: -1.0%)

## Output Format

Both output files contain the following columns:

- **Ticker**: Stock symbol
- **Date**: Timestamp of the scan
- **Gap%**: Gap percentage from previous day's close to current day's open
- **Open**: Opening price of the day
- **High**: High price of the reference candle
- **Low**: Low price of the reference candle
- **Close**: Close price of the reference candle
- **Current**: Current price at time of scan
- **Uptrend**: Boolean indicating uptrend pattern
- **Downtrend**: Boolean indicating downtrend pattern

## Log Files

- Service installation and management logs: `logs/service_management.log`
- Scanner execution logs: `logs/scan_markets_gap.log`
- Service standard output: `logs/gap_strategy.stdout`
- Service standard error: `logs/gap_strategy.stderr`

## Trading Notes

- This scanner is intended as a screening tool to identify potential candidates for further analysis.
- Always confirm signals with additional technical analysis and risk management strategies.
- Performance is typically best in the first 45 minutes of the trading day when gaps are most influential.
- Signals may vary between the 9:15, 9:30, and 9:45 scans as price patterns develop.