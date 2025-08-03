# Price-Volume Analysis Tool Usage Guide

This document explains how to run price-volume analysis using the ML/data/ohlc_data directory as the data source.

## Overview

The Price-Volume Analysis tools detect accumulation and distribution patterns in stock price data by analyzing the relationship between price movements and volume. These patterns can help identify institutional activity and potential future price movements.

The analysis is based on four specific rules:
1. **Bullish Accumulation**: Price increases with abnormally high volume
2. **Bearish Distribution**: Price decreases with abnormally high volume
3. **Stealth Distribution**: Price increases with abnormally low volume
4. **Stealth Accumulation**: Price decreases with abnormally low volume

## Data Source

The tools now support multiple data sources:
1. **OHLC Data Directory**: Data in ML/data/ohlc_data/ organized by timeframe (daily, hour, 5min)
2. **BT Data Directory**: Legacy data storage in BT/data/
3. **Mock Data**: Generated when no data is available (for testing purposes)

## Available Scripts

### 1. Optimized Analysis with Local Data

For fastest performance and batch processing of all tickers with available data:

```bash
python ML/PV/run_using_ohlc_data.py --timeframe daily --days 20 --threads 8
```

This script:
- Uses data from ML/data/ohlc_data/ folder
- Runs analysis in parallel using multiple threads
- Generates two Excel files (accumulation and distribution signals)
- Prints a summary of the strongest signals

**Options:**
- `--timeframe`: Choose from 'daily', 'hourly', or '5min'
- `--days`: Number of days to analyze (adjust based on timeframe)
- `--sensitivity`: Detection sensitivity ('low', 'medium', 'high')
- `--min-strength`: Minimum strength threshold for signals (default: 5.0)
- `--threads`: Number of threads for parallel processing
- `--file`: Optional path to Excel file with specific tickers to analyze

### 2. Legacy Script with Multiple Data Sources

The original script modified to support the OHLC data directory:

```bash
python ML/PV/generate_accumulation_excel.py --timeframe daily --use-ohlc-data
```

This script:
- Reads tickers from an Excel file (default: ML/data/Ticker.xlsx)
- Uses ohlc_data folder by default (can be disabled with --no-ohlc-data)
- Generates an Excel file with strong accumulation signals

**Options:**
- `--file`: Path to Excel file with tickers (default: ML/data/Ticker.xlsx)
- `--timeframe`: Choose from 'daily', 'hourly', or '5min' 
- `--days`: Number of days to analyze
- `--sensitivity`: Detection sensitivity ('low', 'medium', 'high')
- `--min-strength`: Minimum strength threshold (default: 5.0)
- `--batch-size`: Number of tickers to process in each batch
- `--use-ohlc-data`: Use data from ML/data/ohlc_data (default)
- `--no-ohlc-data`: Do not use ML/data/ohlc_data (fall back to BT/data)

## Recommended Workflow

1. **Download Data**: First, download data for all tickers using the data downloader utility:
   ```bash
   python ML/data/download_data.py --all
   ```

2. **Run Analysis**: Then run the analysis using the optimized parallel script:
   ```bash
   python ML/PV/run_using_ohlc_data.py --timeframe daily
   ```

3. **Review Results**: Open the generated Excel files to review the strongest signals

## Interpreting Results

The analysis provides several metrics:

- **Strength**: Overall strength of the accumulation/distribution pattern (higher is stronger)
- **P/V Correlation**: Correlation between price and volume changes
- **Pattern Strength**: Qualitative assessment (weak, moderate, strong)
- **Conviction**: Confidence level based on multiple metrics (low, medium, high)
- **Price Trend (%)**: Percentage change in price over the analyzed period

Strong accumulation patterns with high conviction may indicate future bullish moves,
while strong distribution patterns may indicate future bearish moves.

## Timeframe Considerations

- **Daily**: Best for medium to long-term signals (2+ weeks)
- **Hourly**: Good for swing trading signals (2-5 days)
- **5min**: Suitable for day trading but more prone to noise

For most reliable signals, look for patterns that show up across multiple timeframes.