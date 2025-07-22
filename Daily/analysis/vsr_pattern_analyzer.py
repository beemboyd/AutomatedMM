#!/usr/bin/env python
"""
VSR Pattern Analyzer - Analyze VSR tracker logs for entry timing patterns
Use this after market hours to analyze the day's VSR tracking data
"""

import os
import sys
import re
import pandas as pd
from datetime import datetime
import argparse

def parse_vsr_log_line(line):
    """Parse a single VSR tracker log line"""
    # Pattern: 2025-07-22 10:07:08,962 - INFO - [Sai] RHIM         | Score: 100 | VSR: 18.66 | Price: ₹514.00  | Vol: 35,355     | Momentum:    6.3% | Build: 📈20 | Trend: NEW | Sector: Unknown
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - INFO - \[.*?\] (\S+)\s+\| Score:\s*(\d+) \| VSR:\s*([\d.]+) \| Price: ₹([\d.,]+)\s*\| Vol:\s*([\d,]+)\s*\| Momentum:\s*([\d.-]+)% \| Build: ([^\|]+) \| Trend: ([^\|]+) \| Sector: (.+?)$'
    
    match = re.match(pattern, line)
    if match:
        return {
            'timestamp': datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S'),
            'ticker': match.group(2),
            'score': int(match.group(3)),
            'vsr': float(match.group(4)),
            'price': float(match.group(5).replace(',', '')),
            'volume': int(match.group(6).replace(',', '')),
            'momentum': float(match.group(7)),
            'build': match.group(8).strip(),
            'trend': match.group(9).strip(),
            'sector': match.group(10).strip()
        }
    return None

def analyze_ticker_journey(ticker_data):
    """Analyze the journey of a ticker from first detection to end"""
    if len(ticker_data) < 2:
        return None
    
    # Sort by timestamp
    ticker_data = ticker_data.sort_values('timestamp')
    
    # Get key metrics
    first_entry = ticker_data.iloc[0]
    last_entry = ticker_data.iloc[-1]
    max_price_entry = ticker_data.loc[ticker_data['price'].idxmax()]
    max_vsr_entry = ticker_data.loc[ticker_data['vsr'].idxmax()]
    
    # Calculate time-based metrics
    duration = (last_entry['timestamp'] - first_entry['timestamp']).total_seconds() / 60  # minutes
    
    # Price movement analysis
    price_change_pct = ((last_entry['price'] - first_entry['price']) / first_entry['price']) * 100
    max_price_change_pct = ((max_price_entry['price'] - first_entry['price']) / first_entry['price']) * 100
    
    # Time to peak
    time_to_max_price = (max_price_entry['timestamp'] - first_entry['timestamp']).total_seconds() / 60
    time_to_max_vsr = (max_vsr_entry['timestamp'] - first_entry['timestamp']).total_seconds() / 60
    
    # Volume analysis
    total_volume = ticker_data['volume'].sum()
    avg_volume = ticker_data['volume'].mean()
    
    return {
        'ticker': first_entry['ticker'],
        'first_detection': first_entry['timestamp'],
        'initial_score': first_entry['score'],
        'initial_vsr': first_entry['vsr'],
        'initial_price': first_entry['price'],
        'initial_momentum': first_entry['momentum'],
        'max_vsr': max_vsr_entry['vsr'],
        'max_vsr_time_minutes': time_to_max_vsr,
        'max_price': max_price_entry['price'],
        'max_price_time_minutes': time_to_max_price,
        'max_price_change_pct': max_price_change_pct,
        'final_price': last_entry['price'],
        'final_price_change_pct': price_change_pct,
        'duration_minutes': duration,
        'total_volume': total_volume,
        'avg_volume': avg_volume,
        'data_points': len(ticker_data),
        'sector': first_entry['sector']
    }

def analyze_entry_timing(df, threshold_score=80, threshold_vsr=3.0):
    """Analyze optimal entry timing for high-momentum stocks"""
    # Filter for high-momentum stocks at first detection
    high_momentum_tickers = df[
        (df['score'] >= threshold_score) & 
        (df['vsr'] >= threshold_vsr)
    ]['ticker'].unique()
    
    timing_analysis = []
    
    for ticker in high_momentum_tickers:
        ticker_df = df[df['ticker'] == ticker].copy()
        if len(ticker_df) < 5:  # Need at least 5 data points
            continue
            
        ticker_df = ticker_df.sort_values('timestamp')
        first_entry = ticker_df.iloc[0]
        
        # Calculate price changes at different time intervals
        results = {
            'ticker': ticker,
            'initial_time': first_entry['timestamp'],
            'initial_price': first_entry['price'],
            'initial_vsr': first_entry['vsr'],
            'initial_score': first_entry['score']
        }
        
        # Check price at specific intervals (in minutes)
        intervals = [1, 3, 5, 10, 15, 30, 60]
        for interval in intervals:
            target_time = first_entry['timestamp'] + pd.Timedelta(minutes=interval)
            
            # Find closest entry to target time
            time_diff = abs((ticker_df['timestamp'] - target_time).dt.total_seconds())
            if time_diff.min() < 120:  # Within 2 minutes of target
                closest_idx = time_diff.idxmin()
                entry = ticker_df.loc[closest_idx]
                
                price_change = ((entry['price'] - first_entry['price']) / first_entry['price']) * 100
                results[f'price_change_{interval}min'] = price_change
                results[f'vsr_{interval}min'] = entry['vsr']
                results[f'volume_{interval}min'] = entry['volume']
        
        timing_analysis.append(results)
    
    return pd.DataFrame(timing_analysis)

def main():
    parser = argparse.ArgumentParser(description='Analyze VSR tracker patterns')
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'),
                        help='Date to analyze (YYYYMMDD format)')
    parser.add_argument('--min-score', type=int, default=80,
                        help='Minimum score threshold for analysis')
    parser.add_argument('--min-vsr', type=float, default=3.0,
                        help='Minimum VSR threshold for analysis')
    
    args = parser.parse_args()
    
    # Read log file
    log_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_{args.date}.log'
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    print(f"Analyzing VSR patterns from: {log_file}")
    
    # Parse log file
    data = []
    with open(log_file, 'r') as f:
        for line in f:
            if '| Score:' in line and 'VSR:' in line:
                parsed = parse_vsr_log_line(line.strip())
                if parsed:
                    data.append(parsed)
    
    if not data:
        print("No valid VSR data found in log file")
        return
    
    df = pd.DataFrame(data)
    print(f"\nTotal data points: {len(df)}")
    print(f"Unique tickers tracked: {df['ticker'].nunique()}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Analyze high-momentum stocks
    high_momentum = df[(df['score'] >= args.min_score) & (df['vsr'] >= args.min_vsr)]
    print(f"\nHigh momentum detections (Score>={args.min_score}, VSR>={args.min_vsr}): {high_momentum['ticker'].nunique()} tickers")
    
    if not high_momentum.empty:
        print("\nHigh Momentum Tickers:")
        for ticker in high_momentum['ticker'].unique():
            first_detection = high_momentum[high_momentum['ticker'] == ticker].iloc[0]
            print(f"  {ticker}: First detected at {first_detection['timestamp'].strftime('%H:%M:%S')}, "
                  f"VSR={first_detection['vsr']:.2f}, Score={first_detection['score']}, "
                  f"Price=₹{first_detection['price']:.2f}")
    
    # Analyze ticker journeys
    print("\n" + "="*80)
    print("TICKER JOURNEY ANALYSIS")
    print("="*80)
    
    journeys = []
    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker]
        journey = analyze_ticker_journey(ticker_data)
        if journey:
            journeys.append(journey)
    
    if journeys:
        journey_df = pd.DataFrame(journeys)
        
        # Sort by max price change
        journey_df = journey_df.sort_values('max_price_change_pct', ascending=False)
        
        print("\nTop 10 Movers by Maximum Price Change:")
        for idx, row in journey_df.head(10).iterrows():
            print(f"\n{row['ticker']} ({row['sector']})")
            print(f"  First detected: {row['first_detection'].strftime('%H:%M:%S')}")
            print(f"  Initial: Score={row['initial_score']}, VSR={row['initial_vsr']:.2f}, Price=₹{row['initial_price']:.2f}")
            print(f"  Max Price: ₹{row['max_price']:.2f} (+{row['max_price_change_pct']:.2f}%) at {row['max_price_time_minutes']:.1f} min")
            print(f"  Max VSR: {row['max_vsr']:.2f} at {row['max_vsr_time_minutes']:.1f} min")
            print(f"  Final: +{row['final_price_change_pct']:.2f}% after {row['duration_minutes']:.1f} min")
    
    # Entry timing analysis
    print("\n" + "="*80)
    print("ENTRY TIMING ANALYSIS")
    print("="*80)
    
    timing_df = analyze_entry_timing(df, args.min_score, args.min_vsr)
    
    if not timing_df.empty:
        # Calculate average moves at each interval
        intervals = [1, 3, 5, 10, 15, 30, 60]
        
        print("\nAverage Price Movement After Initial Detection:")
        for interval in intervals:
            col = f'price_change_{interval}min'
            if col in timing_df.columns:
                avg_move = timing_df[col].mean()
                max_move = timing_df[col].max()
                min_move = timing_df[col].min()
                print(f"  {interval:2d} minutes: Avg={avg_move:+.2f}%, Max={max_move:+.2f}%, Min={min_move:+.2f}%")
        
        # Save detailed results
        output_file = f'vsr_analysis_{args.date}.xlsx'
        with pd.ExcelWriter(output_file) as writer:
            df.to_excel(writer, sheet_name='Raw Data', index=False)
            journey_df.to_excel(writer, sheet_name='Ticker Journeys', index=False)
            timing_df.to_excel(writer, sheet_name='Entry Timing', index=False)
        
        print(f"\nDetailed analysis saved to: {output_file}")
    
    # Scaling strategy recommendations
    print("\n" + "="*80)
    print("SCALING STRATEGY INSIGHTS")
    print("="*80)
    
    if not timing_df.empty:
        # Check how many stocks maintain momentum
        maintain_momentum = timing_df[
            (timing_df.get('price_change_5min', 0) > 0) &
            (timing_df.get('price_change_15min', 0) > timing_df.get('price_change_5min', 0))
        ]
        
        momentum_rate = len(maintain_momentum) / len(timing_df) * 100
        print(f"\nMomentum Continuation Rate: {momentum_rate:.1f}% of high VSR stocks continued moving up after 15 min")
        
        # Optimal entry analysis
        if 'price_change_3min' in timing_df.columns and 'price_change_15min' in timing_df.columns:
            immediate_entry_gain = timing_df['price_change_15min'].mean()
            delayed_entry_gain = (timing_df['price_change_15min'] - timing_df['price_change_3min']).mean()
            
            print(f"\nEntry Timing Comparison (15-min horizon):")
            print(f"  Immediate entry average gain: {immediate_entry_gain:+.2f}%")
            print(f"  3-min delayed entry average gain: {delayed_entry_gain:+.2f}%")
            print(f"  Opportunity cost of waiting: {immediate_entry_gain - delayed_entry_gain:.2f}%")

if __name__ == '__main__':
    main()