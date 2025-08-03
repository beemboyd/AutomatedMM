#!/usr/bin/env python3
"""
Run price-volume analysis on top tickers and identify strong accumulation signals.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging

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

# Top tickers from Nifty 50, Nifty Next 50, and key sectors
TOP_TICKERS = [
    # Nifty 50 components
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "BHARTIARTL", "ITC", 
    "KOTAKBANK", "SBIN", "AXISBANK", "BAJFINANCE", "MARUTI", "ASIANPAINT", "LT", "HCLTECH", 
    "TATAMOTORS", "TITAN", "TECHM", "NTPC", "WIPRO", "BAJAJFINSV", "ULTRACEMCO", "SUNPHARMA", 
    "POWERGRID", "ADANIENT", "JSWSTEEL", "ONGC", "HINDALCO", "TATASTEEL",
    
    # Additional interesting tickers
    "RRKABEL", "TIMKEN", "SCHAEFFLER", "CREDITACC", "ELECON", "ACI", "CCL", "COFORGE",
    "FIVESTAR", "HAPPYFORGE", "HONASA", "KAYNES", "MTARTECH", "POLYCAB", "TIMKEN", "SYRMA",
    "LATENTVIEW", "SONACOMS", "HAL", "BEL", "CAMS", "IRCTC", "POLICYBZR", "PAYTM", "NYKAA"
]

def analyze_top_tickers(timeframe="daily", days=20, sensitivity="high", strength_threshold=15):
    """
    Run price-volume analysis on top tickers and identify those with strong accumulation signals.
    
    Args:
        timeframe (str): Timeframe for analysis (5min, hourly, daily)
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level for pattern detection
        strength_threshold (float): Minimum strength to consider a signal strong
    
    Returns:
        dict: Dictionary with analysis results for strong accumulation tickers
    """
    logger.info(f"Running analysis on {len(TOP_TICKERS)} tickers with {timeframe} timeframe")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"top_tickers_accum_dist_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Analyze each ticker
    all_results = {}
    strong_accumulation = {}
    
    for ticker in TOP_TICKERS:
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
                
                # Check if it shows accumulation
                summary = result['summary']
                
                if summary['recent_trend'] == "ACCUMULATION":
                    # Add to results with strength info
                    strong_accumulation[ticker] = {
                        'strength': summary['net_strength'],
                        'phase': summary['current_phase'],
                        'pv_correlation': summary.get('price_vol_correlation', 0),
                        'conviction': summary['conviction'],
                        'pattern_strength': summary['pattern_strength']
                    }
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
    
    # Write all accumulation signals to a file
    write_accumulation_signals_to_file(strong_accumulation, output_dir, timeframe, strength_threshold)
    
    # Filter for strong signals
    strong_signals = {k: v for k, v in strong_accumulation.items() if v['strength'] >= strength_threshold}
    
    logger.info(f"Analysis complete. Found {len(strong_signals)} tickers with strong accumulation signals (strength >= {strength_threshold})")
    logger.info(f"Results saved to {output_dir}")
    
    return strong_signals

def write_accumulation_signals_to_file(accumulation_data, output_dir, timeframe, strength_threshold):
    """
    Write accumulation signals to a file, sorted by strength.
    
    Args:
        accumulation_data (dict): Dictionary with accumulation results
        output_dir (str): Output directory
        timeframe (str): Timeframe used for analysis
        strength_threshold (float): Threshold for strong signals
    """
    if not accumulation_data:
        logger.warning("No accumulation signals found")
        return
    
    # Sort by strength (descending)
    sorted_tickers = sorted(
        accumulation_data.items(), 
        key=lambda x: x[1]['strength'], 
        reverse=True
    )
    
    # Write to file
    output_file = os.path.join(output_dir, f"accumulation_signals_{timeframe}.txt")
    
    with open(output_file, 'w') as f:
        f.write(f"ACCUMULATION SIGNALS ({timeframe.upper()})\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Current Phase':<15} {'Conviction':<10}\n")
        f.write("-" * 80 + "\n")
        
        for ticker, data in sorted_tickers:
            strength_marker = "** STRONG **" if data['strength'] >= strength_threshold else ""
            f.write(f"{ticker:<10} {data['strength']:>10.2f} {data['pv_correlation']:>10.2f} {data['phase']:<15} {data['conviction']:<10} {strength_marker}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("Timeframe explanation:\n")
        f.write("- 5min: Short-term intraday patterns\n")
        f.write("- hourly: Medium-term patterns (1-3 days)\n")
        f.write("- daily: Longer-term patterns (weeks)\n\n")
        
        f.write("Stronger signals at higher timeframes (hourly, daily) generally represent\n")
        f.write("larger institutional money flows and may be more reliable.\n")
    
    logger.info(f"Accumulation signals written to {output_file}")
    
    # Also write a summary to console
    print("\nACCUMULATION SIGNALS SUMMARY\n" + "=" * 40)
    print(f"Timeframe: {timeframe.upper()}")
    print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Conviction'}")
    print("-" * 40)
    
    strong_count = 0
    for ticker, data in sorted_tickers:
        strength_marker = "**" if data['strength'] >= strength_threshold else ""
        print(f"{ticker:<10} {data['strength']:>10.2f} {data['pv_correlation']:>10.2f} {data['conviction']} {strength_marker}")
        if data['strength'] >= strength_threshold:
            strong_count += 1
    
    print(f"\nFound {strong_count} tickers with strong accumulation signals (strength >= {strength_threshold})")
    print(f"Detailed results saved to: {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run price-volume analysis on top tickers'
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
        '--strength',
        type=float,
        default=15.0,
        help='Minimum strength to consider a signal strong'
    )
    
    args = parser.parse_args()
    
    # Run analysis
    analyze_top_tickers(
        args.timeframe,
        args.days,
        args.sensitivity,
        args.strength
    )