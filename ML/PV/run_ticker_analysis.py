#!/usr/bin/env python3
"""
Run price-volume analysis on tickers from an Excel file
and write output focusing on strong accumulation signals.
"""

import os
import sys
import pandas as pd
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

def analyze_tickers_from_file(excel_path, timeframe="hourly", days=20, sensitivity="high", strength_threshold=15):
    """
    Run price-volume analysis on tickers from an Excel file
    and identify those with strong accumulation signals.
    
    Args:
        excel_path (str): Path to the Excel file
        timeframe (str): Timeframe for analysis (5min, hourly, daily)
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level for pattern detection
        strength_threshold (float): Minimum strength to consider a signal strong
    
    Returns:
        dict: Dictionary with analysis results for strong accumulation tickers
    """
    # Extract tickers from the Excel file
    tickers = extract_tickers_from_excel(excel_path)
    
    if not tickers:
        logger.error("No tickers found in the Excel file")
        return {}
    
    logger.info(f"Running analysis on {len(tickers)} tickers with {timeframe} timeframe")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"accum_dist_analysis_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Analyze each ticker
    all_results = {}
    strong_accumulation = {}
    
    for ticker in tickers:
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
                output_dir=output_dir,
                sensitivity=sensitivity,
                strength_lookback=strength_lookback,
                timeframe=timeframe
            )
            
            if result:
                all_results[ticker] = result
                
                # Check if it shows strong accumulation
                summary = result['summary']
                
                if (summary['recent_trend'] == "ACCUMULATION" and 
                    summary['net_strength'] >= strength_threshold):
                    
                    strong_accumulation[ticker] = {
                        'strength': summary['net_strength'],
                        'phase': summary['current_phase'],
                        'pv_correlation': summary.get('price_vol_correlation', 0),
                        'conviction': summary['conviction'],
                        'pattern_strength': summary['pattern_strength']
                    }
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
    
    # Write results to a file
    write_strong_signals_to_file(strong_accumulation, output_dir, timeframe)
    
    logger.info(f"Analysis complete. Found {len(strong_accumulation)} tickers with strong accumulation signals")
    logger.info(f"Results saved to {output_dir}")
    
    return strong_accumulation

def write_strong_signals_to_file(strong_accumulation, output_dir, timeframe):
    """
    Write strong accumulation signals to a file.
    
    Args:
        strong_accumulation (dict): Dictionary with strong accumulation results
        output_dir (str): Output directory
        timeframe (str): Timeframe used for analysis
    """
    if not strong_accumulation:
        logger.warning("No strong accumulation signals found")
        return
    
    # Sort by strength (descending)
    sorted_tickers = sorted(
        strong_accumulation.items(), 
        key=lambda x: x[1]['strength'], 
        reverse=True
    )
    
    # Write to file
    output_file = os.path.join(output_dir, f"strong_accumulation_{timeframe}.txt")
    
    with open(output_file, 'w') as f:
        f.write(f"STRONG ACCUMULATION SIGNALS ({timeframe.upper()})\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Current Phase':<15} {'Conviction':<10}\n")
        f.write("-" * 80 + "\n")
        
        for ticker, data in sorted_tickers:
            f.write(f"{ticker:<10} {data['strength']:>10.2f} {data['pv_correlation']:>10.2f} {data['phase']:<15} {data['conviction']:<10}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("Timeframe explanation:\n")
        f.write("- 5min: Short-term intraday patterns\n")
        f.write("- hourly: Medium-term patterns (1-3 days)\n")
        f.write("- daily: Longer-term patterns (weeks)\n\n")
        
        f.write("Stronger signals at higher timeframes (hourly, daily) generally represent\n")
        f.write("larger institutional money flows and may be more reliable.\n")
    
    logger.info(f"Strong accumulation signals written to {output_file}")
    
    # Also write a summary to console
    print("\nSTRONG ACCUMULATION SIGNALS SUMMARY\n" + "=" * 40)
    print(f"Timeframe: {timeframe.upper()}")
    print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10}")
    print("-" * 40)
    
    for ticker, data in sorted_tickers[:10]:  # Show top 10
        print(f"{ticker:<10} {data['strength']:>10.2f} {data['pv_correlation']:>10.2f}")
    
    if len(sorted_tickers) > 10:
        print(f"\n...and {len(sorted_tickers)-10} more tickers with strong signals")
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run price-volume analysis on tickers from an Excel file'
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
        default='hourly',
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
        '--strength',
        type=float,
        default=15.0,
        help='Minimum strength to consider a signal strong'
    )
    
    args = parser.parse_args()
    
    # Run analysis
    analyze_tickers_from_file(
        args.file,
        args.timeframe,
        args.days,
        args.sensitivity,
        args.strength
    )