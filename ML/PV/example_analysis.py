#!/usr/bin/env python3
"""
Example script for using the Accumulation/Distribution Analyzer

This script demonstrates how to use the accumulation/distribution analyzer on a list of tickers.
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ML.PV.accumulation_distribution_analyzer import analyze_ticker, print_analysis_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_analysis_for_tickers(tickers, days=20, sensitivity='high', strength_lookback=10, timeframe="5min"):
    """
    Run accumulation/distribution analysis for a list of tickers.
    
    Args:
        tickers (list): List of ticker symbols
        days (int): Number of days of data to analyze
    """
    print(f"\n{'='*80}")
    print(f"ACCUMULATION/DISTRIBUTION ANALYSIS")
    print(f"{'='*80}")
    print(f"Running analysis for {len(tickers)} tickers: {', '.join(tickers)}")
    print(f"Analyzing {days} days of {timeframe} data")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"accum_dist_analysis_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Run analysis for each ticker
    results = {}
    
    for ticker in tickers:
        print(f"\nAnalyzing {ticker}...")
        ticker_results = analyze_ticker(ticker, days, output_dir, sensitivity, strength_lookback, timeframe)
        
        if ticker_results:
            results[ticker] = ticker_results
            print_analysis_summary(ticker_results, timeframe=timeframe)
        else:
            print(f"Analysis failed for {ticker}")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY OF ANALYSES")
    print(f"{'='*80}")
    
    # Print summary table
    print(f"\n{'Ticker':<10} {'Current':<12} {'Recent Trend':<15} {'Strength':<10} {'Conviction':<10} {'Reversal':<8} {'P/V Corr':<8}")
    print(f"{'-'*10} {'-'*12} {'-'*15} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")

    for ticker, result in results.items():
        summary = result['summary']
        print(f"{ticker:<10} {summary['current_phase']:<12} {summary['recent_trend']:<15} {summary['pattern_strength']:<10} {summary['conviction']:<10} {'YES' if summary['potential_reversal'] else 'NO':<8} {summary['price_vol_correlation']:>7.2f}")
    
    print(f"\n{'='*80}")
    print(f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*80}")
    
    return results


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Run accumulation/distribution analysis for a list of tickers')
    parser.add_argument('--tickers', type=str, nargs='+', help='Ticker symbols to analyze')
    parser.add_argument('--days', type=int, default=20, help='Number of days of data to analyze')
    parser.add_argument('--sensitivity', type=str, default='high', choices=['low', 'medium', 'high'], help='Sensitivity of pattern detection')
    parser.add_argument('--lookback', type=int, default=10, help='Number of periods to look back for strength calculation')
    parser.add_argument('--timeframe', type=str, default='5min', choices=['5min', 'hourly', 'daily'], help='Timeframe for analysis')
    
    args = parser.parse_args()
    
    if not args.tickers:
        # Default tickers if none provided
        args.tickers = [
            "RELIANCE", "HDFCBANK", "TCS", "INFY", "HINDUNILVR",
            "RRKABEL", "CREDITACC", "ELECON", "TIMKEN", "SUNPHARMA"
        ]
    
    # Run analysis
    run_analysis_for_tickers(args.tickers, args.days, args.sensitivity, args.lookback, args.timeframe)