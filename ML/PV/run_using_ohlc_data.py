#!/usr/bin/env python3
"""
Run price-volume analysis using data from the ohlc_data folder in ML/data.
This is an optimized version that directly works with local data files without
requiring API calls.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import argparse
import concurrent.futures

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import analyzer
from ML.PV.accumulation_distribution_analyzer import analyze_ticker
from ML.PV.generate_accumulation_excel import extract_tickers_from_excel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_available_tickers(timeframe="daily"):
    """
    Get a list of tickers that have data available in the ohlc_data folder.
    
    Args:
        timeframe (str): Timeframe to check for (5min, hourly, daily)
        
    Returns:
        list: List of available tickers
    """
    # Map timeframe to folder name
    folder_map = {
        "5min": "5min",
        "hourly": "hour",
        "daily": "daily"
    }
    folder = folder_map.get(timeframe, "daily")
    
    # Path to the data folder
    ohlc_data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'ohlc_data', folder
    )
    
    if not os.path.exists(ohlc_data_path):
        logger.error(f"ohlc_data/{folder} folder does not exist")
        return []
    
    # Get all CSV files in the folder
    files = [f for f in os.listdir(ohlc_data_path) if f.endswith('.csv')]
    
    # Extract ticker symbols from filenames
    suffix = "_day.csv" if timeframe == "daily" else ("_60minute.csv" if timeframe == "hourly" else "_5minute.csv")
    tickers = []
    
    for file in files:
        if file.endswith(suffix):
            ticker = file[:-len(suffix)]
            tickers.append(ticker)
    
    logger.info(f"Found {len(tickers)} tickers with {timeframe} data in ohlc_data/{folder}")
    return tickers

def analyze_ticker_parallel(ticker, timeframe, days, sensitivity, strength_lookback):
    """
    Analyze a single ticker for price-volume patterns.
    This function is designed to be run in parallel.
    
    Args:
        ticker (str): Ticker symbol
        timeframe (str): Timeframe for analysis
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level
        strength_lookback (int): Number of periods for strength calculation
        
    Returns:
        dict: Analysis result or None if error
    """
    try:
        logger.info(f"Analyzing {ticker}...")
        
        # Run analysis
        result = analyze_ticker(
            ticker=ticker, 
            days=days, 
            output_dir=None,  # Don't save charts
            sensitivity=sensitivity,
            strength_lookback=strength_lookback,
            timeframe=timeframe
        )
        
        if result and 'summary' in result:
            summary = result['summary']
            
            # Create a result dictionary with important metrics
            return {
                'ticker': ticker,
                'phase': summary.get('current_phase', 'UNKNOWN'),
                'recent_trend': summary.get('recent_trend', 'UNKNOWN'),
                'net_strength': summary.get('net_strength', 0),
                'price_vol_correlation': summary.get('price_vol_correlation', 0),
                'pattern_strength': summary.get('pattern_strength', 'weak'),
                'conviction': summary.get('conviction', 'low'),
                'price_trend': summary.get('price_trend', 0)
            }
        
        return None
    
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return None

def run_parallel_analysis(tickers, timeframe="daily", days=20, sensitivity="high", max_workers=8):
    """
    Run price-volume analysis in parallel using multiple threads.
    
    Args:
        tickers (list): List of tickers to analyze
        timeframe (str): Timeframe for analysis
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level
        max_workers (int): Maximum number of threads to use
        
    Returns:
        tuple: (accumulation_results, distribution_results)
    """
    # Set strength lookback based on timeframe
    if timeframe == "5min":
        strength_lookback = 20
    elif timeframe == "hourly":
        strength_lookback = 10
    else:  # daily
        strength_lookback = 5
    
    # Results containers
    all_results = []
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a dictionary of futures to ticker
        future_to_ticker = {
            executor.submit(
                analyze_ticker_parallel, 
                ticker, 
                timeframe, 
                days, 
                sensitivity, 
                strength_lookback
            ): ticker for ticker in tickers
        }
        
        # Process completed futures
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    all_results.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
    
    # Sort and filter results
    accumulation_results = [r for r in all_results if r['recent_trend'] == 'ACCUMULATION']
    distribution_results = [r for r in all_results if r['recent_trend'] == 'DISTRIBUTION']
    
    # Sort by strength
    accumulation_results = sorted(accumulation_results, key=lambda x: x['net_strength'], reverse=True)
    distribution_results = sorted(distribution_results, key=lambda x: abs(x['net_strength']), reverse=True)
    
    return accumulation_results, distribution_results

def save_results_to_excel(results, output_dir, filename):
    """
    Save results to an Excel file.
    
    Args:
        results (list): List of result dictionaries
        output_dir (str): Output directory
        filename (str): Filename
        
    Returns:
        str: Path to the saved file
    """
    if not results:
        logger.warning(f"No results to save for {filename}")
        return None
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Rename columns for better readability
    column_mapping = {
        'ticker': 'Ticker',
        'phase': 'Current Phase',
        'recent_trend': 'Recent Trend',
        'net_strength': 'Strength',
        'price_vol_correlation': 'P/V Correlation',
        'pattern_strength': 'Pattern Strength',
        'conviction': 'Conviction',
        'price_trend': 'Price Trend (%)'
    }
    df.rename(columns=column_mapping, inplace=True)
    
    # Round numeric columns
    numeric_columns = ['Strength', 'P/V Correlation', 'Price Trend (%)']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].round(2)
    
    # Save to Excel
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, filename)
    df.to_excel(output_file, index=False)
    
    logger.info(f"Saved {len(results)} results to {output_file}")
    return output_file

def check_data_files(tickers, timeframe="daily"):
    """
    Check data files for common issues like timezone inconsistencies.

    Args:
        tickers (list): List of tickers to check
        timeframe (str): Timeframe to check

    Returns:
        list: List of tickers with valid data files
    """
    # Map timeframe to folder name
    folder_map = {
        "5min": "5min",
        "hourly": "hour",
        "daily": "daily"
    }
    folder = folder_map.get(timeframe, "daily")

    # Map timeframe to file suffix
    suffix_map = {
        "5min": "_5minute.csv",
        "hourly": "_60minute.csv",
        "daily": "_day.csv"
    }
    suffix = suffix_map.get(timeframe, "_day.csv")

    # Path to the data folder
    ohlc_data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'ohlc_data', folder
    )

    valid_tickers = []
    problem_tickers = []

    for ticker in tickers:
        file_path = os.path.join(ohlc_data_path, f"{ticker}{suffix}")
        if not os.path.exists(file_path):
            continue

        try:
            # Try to read the file
            df = pd.read_csv(file_path)

            # Check for date column
            date_column = None
            for col in ["date", "datetime", "Date", "DateTime"]:
                if col in df.columns:
                    date_column = col
                    break

            if date_column is None:
                logger.warning(f"No date column found in {ticker}{suffix}")
                problem_tickers.append(ticker)
                continue

            # Try converting to datetime
            try:
                # Convert to datetime and test for timezone issues
                df[date_column] = pd.to_datetime(df[date_column])

                # If timezone-aware, test for issues
                if hasattr(df[date_column].dtype, 'tz') and df[date_column].dtype.tz is not None:
                    # Try sorting to see if it works
                    df.sort_values(date_column, inplace=True)

                # No issues, add to valid list
                valid_tickers.append(ticker)

            except Exception as e:
                logger.warning(f"Datetime issue in {ticker}{suffix}: {e}")
                problem_tickers.append(ticker)

        except Exception as e:
            logger.warning(f"Error reading {ticker}{suffix}: {e}")
            problem_tickers.append(ticker)

    if problem_tickers:
        logger.warning(f"Found {len(problem_tickers)} tickers with potential data issues")
        logger.warning(f"Examples of problem tickers: {problem_tickers[:5]}")

    logger.info(f"Verified {len(valid_tickers)} tickers with valid data files")
    return valid_tickers

def main():
    parser = argparse.ArgumentParser(
        description='Run price-volume analysis using data from ohlc_data folder'
    )
    
    parser.add_argument(
        '--file', 
        type=str, 
        default=None,
        help='Path to Excel file with tickers (optional, if not provided all available tickers will be used)'
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
        '--threads',
        type=int,
        default=8,
        help='Number of threads to use for parallel processing'
    )

    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip data validation (faster, but may fail on some tickers)'
    )
    
    args = parser.parse_args()
    
    # Get tickers to analyze
    if args.file:
        tickers = extract_tickers_from_excel(args.file)
        logger.info(f"Extracted {len(tickers)} tickers from {args.file}")
    else:
        tickers = get_available_tickers(args.timeframe)

    if not tickers:
        logger.error("No tickers to analyze")
        return 1

    # Check for data issues and filter out problematic tickers
    if not args.skip_validation:
        logger.info("Checking data files for potential issues...")
        valid_tickers = check_data_files(tickers, args.timeframe)
    else:
        logger.info("Skipping data validation (--skip-validation flag used)")
        logger.warning("Some tickers may fail during analysis if they have data issues")
        valid_tickers = tickers

    if not valid_tickers:
        logger.error("No valid tickers found after data validation")
        return 1

    # Update the tickers list to only include valid tickers
    tickers = valid_tickers
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"pv_analysis_{args.timeframe}_{timestamp}"
    )
    
    # Run parallel analysis
    logger.info(f"Starting parallel analysis of {len(tickers)} tickers using {args.threads} threads")
    accumulation_results, distribution_results = run_parallel_analysis(
        tickers,
        args.timeframe,
        args.days,
        args.sensitivity,
        args.threads
    )
    
    # Filter by strength
    strong_accumulation = [r for r in accumulation_results if r['net_strength'] >= args.min_strength]
    strong_distribution = [r for r in distribution_results if abs(r['net_strength']) >= args.min_strength]
    
    logger.info(f"Found {len(strong_accumulation)} tickers with strong accumulation (>= {args.min_strength})")
    logger.info(f"Found {len(strong_distribution)} tickers with strong distribution (>= {args.min_strength})")
    
    # Save results to Excel
    accumulation_file = save_results_to_excel(
        strong_accumulation,
        output_dir,
        f"strong_accumulation_{args.timeframe}.xlsx"
    )
    
    distribution_file = save_results_to_excel(
        strong_distribution,
        output_dir,
        f"strong_distribution_{args.timeframe}.xlsx"
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"PRICE-VOLUME ANALYSIS SUMMARY ({args.timeframe.upper()})")
    print("=" * 60)
    
    if strong_accumulation:
        print(f"\nSTRONG ACCUMULATION SIGNALS ({len(strong_accumulation)} tickers)")
        print("-" * 60)
        print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Pattern':<10} {'Conviction':<10}")
        print("-" * 60)
        
        for result in strong_accumulation[:10]:  # Show top 10
            print(f"{result['ticker']:<10} {result['net_strength']:>10.2f} {result['price_vol_correlation']:>10.2f} {result['pattern_strength']:<10} {result['conviction']:<10}")
        
        print(f"\nFull results saved to: {accumulation_file}")
    
    if strong_distribution:
        print(f"\nSTRONG DISTRIBUTION SIGNALS ({len(strong_distribution)} tickers)")
        print("-" * 60)
        print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Pattern':<10} {'Conviction':<10}")
        print("-" * 60)
        
        for result in strong_distribution[:10]:  # Show top 10
            print(f"{result['ticker']:<10} {result['net_strength']:>10.2f} {result['price_vol_correlation']:>10.2f} {result['pattern_strength']:<10} {result['conviction']:<10}")
        
        print(f"\nFull results saved to: {distribution_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())