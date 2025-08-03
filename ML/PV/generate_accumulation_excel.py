#!/usr/bin/env python3
"""
Run price-volume analysis on tickers from an Excel file 
and generate a simple Excel output with strong accumulation signals.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import analyzer
from ML.PV.accumulation_distribution_analyzer import analyze_ticker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_tickers_from_excel(excel_path):
    """
    Extract ticker symbols from an Excel file.
    
    Args:
        excel_path (str): Path to the Excel file
        
    Returns:
        list: List of ticker symbols
    """
    try:
        # Read the Excel file
        df = pd.read_excel(excel_path)
        
        # Look for columns that might contain ticker symbols
        ticker_columns = ["Ticker", "Symbol", "Stock", "Name", "ticker", "symbol", "stock", "name"]
        
        for col in ticker_columns:
            if col in df.columns:
                logger.info(f"Found ticker column: {col}")
                # Get unique tickers, remove NaN values, and convert to list
                tickers = df[col].dropna().unique().tolist()
                # Convert to strings if needed
                tickers = [str(ticker).strip() for ticker in tickers]
                logger.info(f"Extracted {len(tickers)} tickers from {excel_path}")
                return tickers
        
        # If no known column names found, try the first column
        first_col = df.columns[0]
        logger.info(f"Using first column as ticker column: {first_col}")
        tickers = df[first_col].dropna().unique().tolist()
        tickers = [str(ticker).strip() for ticker in tickers]
        logger.info(f"Extracted {len(tickers)} tickers from {excel_path}")
        return tickers
        
    except Exception as e:
        logger.error(f"Error extracting tickers from Excel: {e}")
        return []

def analyze_and_generate_excel(excel_path, timeframe="daily", days=20, sensitivity="high", min_strength=5.0, batch_size=50, use_ohlc_data=True):
    """
    Run price-volume analysis on tickers from an Excel file
    and generate a simple Excel output with strong accumulation signals.

    Args:
        excel_path (str): Path to the Excel file
        timeframe (str): Timeframe for analysis (5min, hourly, daily)
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level for pattern detection
        min_strength (float): Minimum strength to include in the output
        batch_size (int): Number of tickers to analyze in each batch
        use_ohlc_data (bool): Whether to use data from the ohlc_data folder

    Returns:
        str: Path to the generated Excel file
    """
    # Extract tickers from the Excel file
    all_tickers = extract_tickers_from_excel(excel_path)

    if not all_tickers:
        logger.error("No tickers found in the Excel file")
        return None

    logger.info(f"Running analysis on {len(all_tickers)} tickers with {timeframe} timeframe")

    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"excel_accumulation_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Prepare for analysis
    accumulation_results = []

    # Check if ohlc_data is available
    folder_map = {
        "5min": "5min",
        "hourly": "hour",
        "daily": "daily"
    }
    folder = folder_map.get(timeframe, "daily")
    ohlc_data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'ohlc_data', folder
    )

    # Verify which tickers have data in ohlc_data folder
    if use_ohlc_data and os.path.exists(ohlc_data_path):
        available_tickers = []
        suffix = "_day.csv" if timeframe == "daily" else ("_60minute.csv" if timeframe == "hourly" else "_5minute.csv")

        # Scan the directory for available data files
        for ticker in all_tickers:
            if os.path.exists(os.path.join(ohlc_data_path, f"{ticker}{suffix}")):
                available_tickers.append(ticker)

        # Report on availability
        if available_tickers:
            logger.info(f"Found {len(available_tickers)}/{len(all_tickers)} tickers with data in ohlc_data/{folder}")
            all_tickers = available_tickers
        else:
            logger.warning(f"No tickers found in ohlc_data/{folder}, using alternative data sources")

    # Process tickers in batches to avoid timeouts
    for i in range(0, len(all_tickers), batch_size):
        batch_tickers = all_tickers[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{len(all_tickers)//batch_size + 1} ({len(batch_tickers)} tickers)")

        # Analyze each ticker in the batch
        for ticker in batch_tickers:
            try:
                logger.info(f"Analyzing {ticker}...")

                # Set strength lookback based on timeframe
                if timeframe == "5min":
                    strength_lookback = 20
                elif timeframe == "hourly":
                    strength_lookback = 10
                else:  # daily
                    strength_lookback = 5

                # Run analysis
                result = analyze_ticker(
                    ticker=ticker,
                    days=days,
                    output_dir=None,  # Don't save charts
                    sensitivity=sensitivity,
                    strength_lookback=strength_lookback,
                    timeframe=timeframe
                )
                
                if result:
                    # Check if it shows accumulation
                    summary = result['summary']
                    
                    if summary['recent_trend'] == "ACCUMULATION":
                        # Add to results with all required info
                        accumulation_results.append({
                            'Ticker': ticker,
                            'Strength': summary['net_strength'],
                            'P/V Correlation': summary.get('price_vol_correlation', 0),
                            'Current Phase': summary['current_phase'],
                            'Pattern Strength': summary['pattern_strength'],
                            'Conviction': summary['conviction'],
                            'Price Trend (%)': summary.get('price_trend', 0)
                        })
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
    
    # Filter by minimum strength and sort by strength (descending)
    filtered_results = [r for r in accumulation_results if r['Strength'] >= min_strength]
    sorted_results = sorted(filtered_results, key=lambda x: x['Strength'], reverse=True)
    
    logger.info(f"Found {len(sorted_results)} tickers with accumulation signals (strength >= {min_strength})")
    
    # Convert to DataFrame
    if sorted_results:
        df = pd.DataFrame(sorted_results)
        
        # Round numeric columns
        if 'Strength' in df.columns:
            df['Strength'] = df['Strength'].round(2)
        if 'P/V Correlation' in df.columns:
            df['P/V Correlation'] = df['P/V Correlation'].round(2)
        if 'Price Trend (%)' in df.columns:
            df['Price Trend (%)'] = df['Price Trend (%)'].round(2)
        
        # Save to Excel
        output_file = os.path.join(output_dir, f"strong_accumulation_{timeframe}.xlsx")
        df.to_excel(output_file, index=False)
        logger.info(f"Results saved to {output_file}")
        
        # Show summary on console
        print("\nSTRONG ACCUMULATION SIGNALS SUMMARY\n" + "=" * 60)
        print(f"Timeframe: {timeframe.upper()}")
        print(f"Found {len(sorted_results)} tickers with accumulation signals (strength >= {min_strength})")
        print("\nTop 10 Signals:")
        print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Phase':<15} {'Conviction'}")
        print("-" * 60)
        
        for result in sorted_results[:10]:
            print(f"{result['Ticker']:<10} {result['Strength']:>10.2f} {result['P/V Correlation']:>10.2f} {result['Current Phase']:<15} {result['Conviction']}")
        
        print(f"\nComplete results saved to: {output_file}")
        
        return output_file
    else:
        logger.warning(f"No tickers with accumulation strength >= {min_strength} found")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run price-volume analysis on tickers from an Excel file and generate Excel output'
    )
    
    parser.add_argument(
        '--file', 
        type=str, 
        default="/Users/maverick/PycharmProjects/India-TS/ML/data/Ticker.xlsx",
        help='Path to the Excel file containing tickers'
    )
    
    parser.add_argument(
        '--timeframe',
        type=str,
        choices=['5min', 'hourly', 'daily'],
        default='daily',
        help='Timeframe for analysis'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=20,
        help='Number of days to analyze'
    )
    
    parser.add_argument(
        '--sensitivity',
        type=str,
        choices=['low', 'medium', 'high'],
        default='high',
        help='Sensitivity level for pattern detection'
    )
    
    parser.add_argument(
        '--min-strength',
        type=float,
        default=5.0,
        help='Minimum strength to include in the output'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of tickers to analyze in each batch'
    )

    parser.add_argument(
        '--use-ohlc-data',
        action='store_true',
        default=True,
        help='Use data from the ML/data/ohlc_data folder (default: True)'
    )

    parser.add_argument(
        '--no-ohlc-data',
        action='store_false',
        dest='use_ohlc_data',
        help='Do not use data from ML/data/ohlc_data folder'
    )

    args = parser.parse_args()

    # Run analysis and generate Excel
    analyze_and_generate_excel(
        args.file,
        args.timeframe,
        args.days,
        args.sensitivity,
        args.min_strength,
        args.batch_size,
        args.use_ohlc_data
    )