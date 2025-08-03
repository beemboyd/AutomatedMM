#!/usr/bin/env python3
"""
Run price-volume analysis on top 50 tickers and generate Excel output with strong accumulation signals.
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

# Top 50 tickers (India's largest companies by market cap + CNC positions)
TOP_50_TICKERS = [
    # Large Cap - Top 15
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "BHARTIARTL", 
    "ITC", "SBIN", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "HCLTECH", "ASIANPAINT",
    
    # Mid Cap - Top 15
    "TATAMOTORS", "MARUTI", "SUNPHARMA", "TITAN", "BAJAJFINSV", "ADANIENT", "NTPC", 
    "TATASTEEL", "POWERGRID", "ULTRACEMCO", "HINDALCO", "JSWSTEEL", "ONGC", "TECHM", "WIPRO",
    
    # Additional interesting tickers including CNC positions
    "RRKABEL", "TIMKEN", "SCHAEFFLER", "CREDITACC", "ELECON", "ACI", "CCL", "COFORGE",
    "HAL", "BEL", "POLICYBZR", "SONACOMS", "LATENTVIEW", "DMART", "NAUKRI", 
    "LTIM", "BAJAJ-AUTO", "M&M", "NESTLEIND", "TATAPOWER"
]

def analyze_top_tickers(timeframe="daily", days=20, sensitivity="high", min_strength=5.0):
    """
    Run price-volume analysis on top tickers and generate Excel output with strong accumulation signals.
    
    Args:
        timeframe (str): Timeframe for analysis (5min, hourly, daily)
        days (int): Number of days to analyze
        sensitivity (str): Sensitivity level for pattern detection
        min_strength (float): Minimum strength to include in the output
    
    Returns:
        str: Path to the generated Excel file
    """
    logger.info(f"Running analysis on {len(TOP_50_TICKERS)} tickers with {timeframe} timeframe")
    
    # Create output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results',
        f"accumulation_excel_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare for analysis
    all_results = []
    
    # Analyze each ticker
    for ticker in TOP_50_TICKERS:
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
                summary = result['summary']
                
                # Add all results (both accumulation and distribution)
                all_results.append({
                    'Ticker': ticker,
                    'Trend': summary['recent_trend'],
                    'Strength': summary['net_strength'],
                    'P/V Correlation': summary.get('price_vol_correlation', 0),
                    'Current Phase': summary['current_phase'],
                    'Pattern Strength': summary['pattern_strength'],
                    'Conviction': summary['conviction'],
                    'Price Trend (%)': summary.get('price_trend', 0)
                })
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
    
    # Convert to DataFrame
    if all_results:
        df = pd.DataFrame(all_results)
        
        # Round numeric columns
        if 'Strength' in df.columns:
            df['Strength'] = df['Strength'].round(2)
        if 'P/V Correlation' in df.columns:
            df['P/V Correlation'] = df['P/V Correlation'].round(2)
        if 'Price Trend (%)' in df.columns:
            df['Price Trend (%)'] = df['Price Trend (%)'].round(2)
        
        # Filter and sort accumulation results
        acc_df = df[df['Trend'] == 'ACCUMULATION'].copy()
        acc_df = acc_df[acc_df['Strength'] >= min_strength].sort_values('Strength', ascending=False)
        
        # Filter and sort distribution results
        dist_df = df[df['Trend'] == 'DISTRIBUTION'].copy()
        dist_df = dist_df[dist_df['Strength'].abs() >= min_strength].sort_values('Strength')
        
        # Save full results 
        full_output_file = os.path.join(output_dir, f"all_signals_{timeframe}.xlsx")
        df.to_excel(full_output_file, index=False)
        
        # Save accumulation-only results
        acc_output_file = os.path.join(output_dir, f"accumulation_signals_{timeframe}.xlsx")
        acc_df.to_excel(acc_output_file, index=False)
        
        logger.info(f"All results saved to {full_output_file}")
        logger.info(f"Accumulation results saved to {acc_output_file}")
        
        # Show summary on console
        print("\nACCUMULATION SIGNALS SUMMARY\n" + "=" * 60)
        print(f"Timeframe: {timeframe.upper()}")
        print(f"Found {len(acc_df)} tickers with accumulation signals (strength >= {min_strength})")
        print("\nTop Accumulation Signals:")
        print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Phase':<15} {'Conviction'}")
        print("-" * 60)
        
        for _, row in acc_df.iterrows():
            print(f"{row['Ticker']:<10} {row['Strength']:>10.2f} {row['P/V Correlation']:>10.2f} {row['Current Phase']:<15} {row['Conviction']}")
        
        print("\nDISTRIBUTION SIGNALS SUMMARY\n" + "=" * 60)
        print(f"Found {len(dist_df)} tickers with distribution signals (strength <= -{min_strength})")
        
        if not dist_df.empty:
            print("\nTop Distribution Signals:")
            print(f"{'Ticker':<10} {'Strength':>10} {'P/V Corr':>10} {'Phase':<15} {'Conviction'}")
            print("-" * 60)
            
            for _, row in dist_df.iterrows():
                print(f"{row['Ticker']:<10} {row['Strength']:>10.2f} {row['P/V Correlation']:>10.2f} {row['Current Phase']:<15} {row['Conviction']}")
        
        return acc_output_file
    else:
        logger.warning("No results found")
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run price-volume analysis on top 50 tickers and generate Excel output'
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
    
    args = parser.parse_args()
    
    # Run analysis
    analyze_top_tickers(
        args.timeframe,
        args.days,
        args.sensitivity,
        args.min_strength
    )