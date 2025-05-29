# Gap Strategy Scanner

This module provides a market scanner that identifies trading opportunities based on gap-up and gap-down price movements followed by specific trend patterns in the 5-minute timeframe.

## Strategy Logic

The Gap Strategy looks for the following patterns:

1. **Short Opportunities:**
   - Gap-up tickers that show a downtrend in the 5-minute timeframe
   - Two consecutive candles with Lower Highs (LH) and Lower Lows (LL) following the gap-up
   - Also includes gap-down tickers that continue with a downtrend

2. **Long Opportunities:**
   - Gap-down tickers that show an uptrend in the 5-minute timeframe
   - Two consecutive candles with Higher Highs (HH) and Higher Lows (HL) following the gap-down
   - Also includes gap-up tickers that continue with an uptrend

## Configuration

The strategy has several configurable parameters:

- `gap_up_threshold`: Minimum gap-up percentage to consider (default: 1.0%)
- `gap_down_threshold`: Maximum gap-down percentage to consider (default: -1.0%)

## Usage

### Running the Scanner Manually

```bash
# Run with default settings
python scripts/scan_markets_gap.py

# Run with verbose output
python scripts/scan_markets_gap.py -v

# Run with custom thresholds
python scripts/scan_markets_gap.py --gap-up-threshold 1.5 --gap-down-threshold -1.5

# Run with custom ticker list
python scripts/scan_markets_gap.py -i /path/to/ticker_list.xlsx
```

### Managing the Service

The gap strategy can be configured to run automatically at market open using the included service management script:

```bash
# Install the service
python utils/install_gap_strategy_service.py install

# Start the service
python utils/install_gap_strategy_service.py start

# Check service status
python utils/install_gap_strategy_service.py status

# Stop the service
python utils/install_gap_strategy_service.py stop

# Uninstall the service
python utils/install_gap_strategy_service.py uninstall
```

## Output

The scanner produces two Excel files with the naming pattern:

- `Gap_Strategy_Long_YYYY-MM-DD_HH-MM.xlsx`: Contains long trade opportunities
- `Gap_Strategy_Short_YYYY-MM-DD_HH-MM.xlsx`: Contains short trade opportunities

Each file contains the following information for each ticker:

- Ticker symbol
- Date and time of the scan
- Gap percentage
- OHLC prices of the gap candle
- Current price
- Trend indicators (uptrend/downtrend)

## Scheduled Execution

When installed as a service, the scanner runs at three specific times each trading day:

- 9:15 AM: Right after market open
- 9:30 AM: After initial market volatility has settled
- 9:45 AM: Final scan of the opening session

This ensures capturing gap opportunities during the critical first hour of trading.