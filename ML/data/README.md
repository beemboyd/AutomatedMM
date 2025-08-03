# OHLC Data Download Utility

This utility downloads OHLC (Open, High, Low, Close) data for stocks from Zerodha and organizes it in a structured folder hierarchy. The data can be used for various analyses including price-volume analysis, market regime detection, and dynamic stop loss calculation.

## Features

- Downloads historical price data for multiple tickers
- Supports multiple timeframes: 5-minute, hourly, and daily
- Updates existing data files with new data
- Organizes data in a clean folder structure
- Handles data integrity and error recovery
- Uses the existing data_handler to maintain consistency with the trading system

## Directory Structure

The data will be organized as follows:

```
ML/data/ohlc_data/
  ├── 5min/
  │   ├── TCS_5minute.csv
  │   ├── RELIANCE_5minute.csv
  │   └── ...
  ├── hour/
  │   ├── TCS_60minute.csv
  │   ├── RELIANCE_60minute.csv
  │   └── ...
  └── daily/
      ├── TCS_day.csv
      ├── RELIANCE_day.csv
      └── ...
```

## Usage

### Simple Usage

```bash
# Download daily data for all tickers in Ticker.xlsx
python download_data.py

# Download all timeframes (5min, hourly, daily) for all tickers
python download_data.py --all

# Download daily data for TCS only
python download_data.py --ticker TCS

# Download hourly data only
python download_data.py --hourly
```

### Advanced Usage

For more advanced options, you can use the main script directly:

```bash
# Download specific timeframes for specific tickers
python download_ohlc_data.py --tickers RELIANCE,TCS,HDFCBANK --timeframes day,hour

# Download data from a custom Excel file
python download_ohlc_data.py --tickers-file custom_tickers.xlsx --timeframes day

# Force refresh all data (don't update existing)
python download_ohlc_data.py --force-refresh
```

## Using the Data in Your Analysis

The downloaded data can be directly used in your price-volume analysis and market regime detection code. For example:

```python
import os
import pandas as pd

def load_ticker_data(ticker, timeframe="day"):
    """Load ticker data from the OHLC data directory."""
    folder_map = {
        "day": "daily",
        "hour": "hour",
        "5minute": "5min"
    }
    folder = folder_map.get(timeframe, "daily")
    
    # Construct the file path
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ohlc_data", 
        folder, 
        f"{ticker}_{timeframe}.csv"
    )
    
    if os.path.exists(file_path):
        data = pd.read_csv(file_path)
        data['date'] = pd.to_datetime(data['date'])
        return data
    
    return None
```

## Maintenance

- The utility automatically updates existing data files with new data
- It's recommended to run the download script daily to keep data up to date
- Consider running it as a scheduled task or cron job

## Troubleshooting

1. **No data downloaded:**
   - Check your internet connection
   - Verify that the ticker symbols are valid
   - Ensure your Zerodha API credentials are valid

2. **Missing API credentials:**
   - The script uses the existing data_handler which should have API credentials configured

3. **Script fails to run:**
   - Make sure you're running from the project root
   - Verify that all required Python packages are installed
   - Check that the data_handler module is accessible