#!/usr/bin/env python3
"""
Get Current Trading Recommendations
===================================
Identifies and ranks tickers based on frequency analysis from past 10 days
of Brooks Higher Probability LONG Reversal reports.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Frequent_ticker_performance import FrequentTickerPerformanceAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_trading_recommendations():
    """Get current trading recommendations based on frequency analysis"""
    
    # Initialize analyzer for 10 days
    analyzer = FrequentTickerPerformanceAnalyzer(user_name="Sai", days_back=10)
    
    # Run analysis
    logger.info("Analyzing past 10 days of Brooks reports...")
    returns_data = analyzer.analyze_reports()
    
    if not returns_data:
        logger.error("No data available for analysis")
        return
    
    # Create recommendation tiers
    tiers = {
        'maximum_conviction': [],  # 16+ appearances
        'strong_buy': [],         # 11-15 appearances
        'consider': [],           # 6-10 appearances
        'avoid': []               # <6 appearances
    }
    
    # Categorize tickers
    for ticker, data in returns_data.items():
        ticker_info = {
            'ticker': ticker,
            'appearances': data['appearances'],
            'return': data['return_pct'],
            'first_date': data['first_appearance'].strftime('%Y-%m-%d'),
            'current_price': data.get('current_price', 0),
            'score': data['appearances'] * 10 + data['return_pct']  # Composite score
        }
        
        if data['appearances'] >= 16:
            tiers['maximum_conviction'].append(ticker_info)
        elif data['appearances'] >= 11:
            tiers['strong_buy'].append(ticker_info)
        elif data['appearances'] >= 6:
            tiers['consider'].append(ticker_info)
        else:
            tiers['avoid'].append(ticker_info)
    
    # Sort each tier by composite score
    for tier in tiers:
        tiers[tier].sort(key=lambda x: x['score'], reverse=True)
    
    # Generate report
    output_lines = []
    output_lines.append("=" * 100)
    output_lines.append("BROOKS REVERSAL TRADING RECOMMENDATIONS")
    output_lines.append(f"Based on Past 10 Days Analysis (as of {datetime.now().strftime('%Y-%m-%d %H:%M')})")
    output_lines.append("=" * 100)
    
    # Maximum Conviction (16+ appearances)
    output_lines.append("\n" + "═" * 100)
    output_lines.append("TIER 1: MAXIMUM CONVICTION (16+ appearances, 100% historical win rate)")
    output_lines.append("═" * 100)
    
    if tiers['maximum_conviction']:
        output_lines.append(f"\n{'Rank':<5} {'Ticker':<10} {'Freq':<6} {'Return %':<10} {'Current Price':<14} {'First Seen':<12} {'Action':<20}")
        output_lines.append("-" * 100)
        
        for i, ticker in enumerate(tiers['maximum_conviction'], 1):
            action = "BUY - Full Position" if ticker['return'] > 0 else "BUY - Monitor closely"
            output_lines.append(
                f"{i:<5} {ticker['ticker']:<10} {ticker['appearances']:<6} "
                f"{ticker['return']:<10.2f} ₹{ticker['current_price']:<13.2f} "
                f"{ticker['first_date']:<12} {action:<20}"
            )
    else:
        output_lines.append("\nNo tickers currently meet this criteria")
    
    # Strong Buy (11-15 appearances)
    output_lines.append("\n" + "═" * 100)
    output_lines.append("TIER 2: STRONG BUY (11-15 appearances, 96.7% historical win rate)")
    output_lines.append("═" * 100)
    
    if tiers['strong_buy']:
        output_lines.append(f"\n{'Rank':<5} {'Ticker':<10} {'Freq':<6} {'Return %':<10} {'Current Price':<14} {'First Seen':<12} {'Action':<20}")
        output_lines.append("-" * 100)
        
        for i, ticker in enumerate(tiers['strong_buy'], 1):
            action = "BUY - 75% Position" if ticker['return'] > 0 else "BUY - Small Position"
            output_lines.append(
                f"{i:<5} {ticker['ticker']:<10} {ticker['appearances']:<6} "
                f"{ticker['return']:<10.2f} ₹{ticker['current_price']:<13.2f} "
                f"{ticker['first_date']:<12} {action:<20}"
            )
    else:
        output_lines.append("\nNo tickers currently meet this criteria")
    
    # Consider (6-10 appearances)
    output_lines.append("\n" + "═" * 100)
    output_lines.append("TIER 3: CONSIDER (6-10 appearances, 80.6% historical win rate)")
    output_lines.append("═" * 100)
    
    if tiers['consider']:
        # Show only top 10
        output_lines.append(f"\n{'Rank':<5} {'Ticker':<10} {'Freq':<6} {'Return %':<10} {'Current Price':<14} {'First Seen':<12} {'Action':<20}")
        output_lines.append("-" * 100)
        
        for i, ticker in enumerate(tiers['consider'][:10], 1):
            if ticker['return'] > 5:
                action = "CONSIDER - 50% Pos"
            elif ticker['return'] > 0:
                action = "WATCH - Wait"
            else:
                action = "AVOID"
            
            output_lines.append(
                f"{i:<5} {ticker['ticker']:<10} {ticker['appearances']:<6} "
                f"{ticker['return']:<10.2f} ₹{ticker['current_price']:<13.2f} "
                f"{ticker['first_date']:<12} {action:<20}"
            )
        
        if len(tiers['consider']) > 10:
            output_lines.append(f"\n... and {len(tiers['consider']) - 10} more tickers in this tier")
    else:
        output_lines.append("\nNo tickers currently meet this criteria")
    
    # Summary Statistics
    output_lines.append("\n" + "=" * 100)
    output_lines.append("SUMMARY STATISTICS")
    output_lines.append("=" * 100)
    
    total_max_conviction = len(tiers['maximum_conviction'])
    total_strong_buy = len(tiers['strong_buy'])
    total_consider = len(tiers['consider'])
    total_avoid = len(tiers['avoid'])
    
    output_lines.append(f"\nMaximum Conviction (16+): {total_max_conviction} tickers")
    output_lines.append(f"Strong Buy (11-15): {total_strong_buy} tickers")
    output_lines.append(f"Consider (6-10): {total_consider} tickers")
    output_lines.append(f"Avoid (<6): {total_avoid} tickers")
    output_lines.append(f"\nTotal Actionable (6+): {total_max_conviction + total_strong_buy + total_consider} tickers")
    
    # Top 5 Overall Recommendations
    output_lines.append("\n" + "=" * 100)
    output_lines.append("TOP 5 OVERALL RECOMMENDATIONS FOR TOMORROW")
    output_lines.append("=" * 100)
    
    # Combine all actionable tickers
    all_actionable = tiers['maximum_conviction'] + tiers['strong_buy'] + tiers['consider']
    all_actionable.sort(key=lambda x: x['score'], reverse=True)
    
    output_lines.append(f"\n{'Rank':<5} {'Ticker':<10} {'Freq':<6} {'Return %':<10} {'Tier':<20} {'Recommended Action':<30}")
    output_lines.append("-" * 100)
    
    for i, ticker in enumerate(all_actionable[:5], 1):
        if ticker['appearances'] >= 16:
            tier = "Maximum Conviction"
            action = "BUY NOW - Full Position"
        elif ticker['appearances'] >= 11:
            tier = "Strong Buy"
            action = "BUY - 75% Position"
        else:
            tier = "Consider"
            action = "BUY - 50% Position" if ticker['return'] > 5 else "WATCH"
        
        output_lines.append(
            f"{i:<5} {ticker['ticker']:<10} {ticker['appearances']:<6} "
            f"{ticker['return']:<10.2f} {tier:<20} {action:<30}"
        )
    
    # Trading Instructions
    output_lines.append("\n" + "=" * 100)
    output_lines.append("TRADING INSTRUCTIONS FOR TOMORROW")
    output_lines.append("=" * 100)
    
    output_lines.append("\n1. PRIORITY ORDER:")
    output_lines.append("   - First: All Maximum Conviction tickers (16+ appearances)")
    output_lines.append("   - Second: Strong Buy tickers with positive returns")
    output_lines.append("   - Third: Consider tickers with returns > 5%")
    
    output_lines.append("\n2. POSITION SIZING:")
    output_lines.append("   - Maximum Conviction: 100% of intended position size")
    output_lines.append("   - Strong Buy: 75% of intended position size")
    output_lines.append("   - Consider: 50% of intended position size")
    
    output_lines.append("\n3. ENTRY STRATEGY:")
    output_lines.append("   - Place orders at market open")
    output_lines.append("   - Use limit orders at or slightly above current price")
    output_lines.append("   - Don't chase if price gaps up > 2%")
    
    output_lines.append("\n4. RISK MANAGEMENT:")
    output_lines.append("   - Set stop loss at -3% for all positions")
    output_lines.append("   - Take partial profits at +5%")
    output_lines.append("   - Exit completely if ticker drops below 6 appearances")
    
    # Save report
    output_dir = "/Users/maverick/PycharmProjects/India-TS/ML/results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"trading_recommendations_{timestamp}.txt")
    
    with open(report_path, 'w') as f:
        f.write('\n'.join(output_lines))
    
    logger.info(f"Recommendations saved to: {report_path}")
    
    # Print report
    print('\n'.join(output_lines))
    
    return tiers

if __name__ == "__main__":
    get_trading_recommendations()