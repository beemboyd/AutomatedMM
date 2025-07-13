#!/usr/bin/env python3
"""
Analyze Long Reversal Daily scanner results to identify volume exhaustion patterns.
Simplified version that focuses on scanner data patterns without Zerodha integration.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from collections import defaultdict
import glob
import json
import matplotlib.pyplot as plt
import seaborn as sns

def analyze_scanner_patterns():
    # Path to results directory
    results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
    
    # Get all Long Reversal Daily files
    pattern = os.path.join(results_dir, "Long_Reversal_Daily_*.xlsx")
    files = sorted(glob.glob(pattern))
    
    print(f"Found {len(files)} Long Reversal Daily files")
    
    # Dictionary to store ticker appearances and their scores over time
    ticker_history = defaultdict(list)
    
    # Process each file
    for file_path in files:
        # Extract date from filename
        filename = os.path.basename(file_path)
        date_str = filename.replace("Long_Reversal_Daily_", "").replace(".xlsx", "")
        
        try:
            # Parse date
            file_date = datetime.strptime(date_str[:8], "%Y%m%d")
            file_time = date_str[9:15]
            
            # Don't fix the year - 2025 is the current year
            
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Store data for each ticker
            for _, row in df.iterrows():
                ticker = row.get('Ticker', row.get('ticker', row.get('TICKER', None)))
                if ticker:
                    ticker_data = {
                        'date': file_date,
                        'time': file_time,
                        'filename': filename,
                        'data': row.to_dict()
                    }
                    ticker_history[ticker].append(ticker_data)
                    
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    
    # Analyze patterns for tickers that appear multiple times
    print("\n" + "="*80)
    print("VOLUME EXHAUSTION PATTERN ANALYSIS - LONG REVERSAL SIGNALS")
    print("="*80)
    
    # First, let's understand the column structure
    if ticker_history:
        sample_ticker = list(ticker_history.keys())[0]
        sample_data = ticker_history[sample_ticker][0]['data']
        print("\nAvailable columns in data:")
        for col in sorted(sample_data.keys()):
            print(f"  - {col}: {type(sample_data[col]).__name__}")
    
    # Find tickers with multiple appearances
    multi_appearance_tickers = {ticker: history for ticker, history in ticker_history.items() 
                               if len(history) >= 3}
    
    print(f"\nFound {len(multi_appearance_tickers)} tickers with 3+ appearances")
    
    # Debug: Show a sample ticker's score progression
    if multi_appearance_tickers:
        sample_ticker = list(multi_appearance_tickers.keys())[0]
        sample_history = multi_appearance_tickers[sample_ticker]
        print(f"\nDebug - Sample ticker {sample_ticker}:")
        for i, entry in enumerate(sample_history[:5]):
            score = entry['data'].get('Score', 'N/A')
            print(f"  Entry {i+1}: Date={entry['date'].strftime('%Y-%m-%d')}, Score={score} (type: {type(score).__name__})")
    
    # Analyze each ticker for patterns
    exhaustion_patterns = []
    score_decline_patterns = []
    
    for ticker, history in multi_appearance_tickers.items():
        # Sort by date
        history.sort(key=lambda x: (x['date'], x['time']))
        
        # Extract scores and other metrics
        scores = []
        volumes = []
        dates = []
        all_data = []
        
        for entry in history:
            data = entry['data']
            dates.append(entry['date'])
            all_data.append(data)
            
            # Try different possible score column names
            score = data.get('Score', data.get('score', data.get('SCORE', 
                            data.get('Total Score', data.get('Total_Score', 
                            data.get('total_score', 0))))))
            
            # Convert to float - handle "6/7" format
            try:
                if isinstance(score, str) and '/' in score:
                    # Extract numerator from "6/7" format
                    numerator = int(score.split('/')[0])
                    denominator = int(score.split('/')[1])
                    score = (numerator / denominator) * 100  # Convert to percentage
                else:
                    score = float(score)
            except (ValueError, TypeError):
                score = 0.0
            scores.append(score)
            
            # Try different possible volume column names
            volume = data.get('Volume', data.get('volume', data.get('VOLUME',
                            data.get('Vol', data.get('vol', data.get('Avg Volume',
                            data.get('Avg_Volume', 0)))))))
            volumes.append(volume)
        
        # Analyze patterns
        if len(scores) >= 3 and max(scores) > 0:
            max_score = max(scores)
            max_score_idx = scores.index(max_score)
            latest_score = scores[-1]
            first_score = scores[0]
            
            pattern_info = {
                'ticker': ticker,
                'appearances': len(history),
                'first_date': dates[0],
                'last_date': dates[-1],
                'days_span': (dates[-1] - dates[0]).days,
                'score_progression': scores,
                'first_score': first_score,
                'max_score': max_score,
                'latest_score': latest_score,
                'peak_position': max_score_idx,
                'score_decline': max_score - latest_score,
                'decline_pct': (max_score - latest_score) / max_score * 100 if max_score > 0 else 0,
                'volume_progression': volumes if any(volumes) else None,
                'all_data': all_data
            }
            
            # Check for Entry → Build → Peak → Exit pattern
            if max_score_idx > 0 and max_score_idx < len(scores) - 1:
                # Found a peak that's not at the beginning or end
                pre_peak_trend = scores[:max_score_idx+1]
                post_peak_trend = scores[max_score_idx:]
                
                # Check if there's a build-up to peak and decline after
                if len(pre_peak_trend) >= 2 and len(post_peak_trend) >= 2:
                    # Calculate trend
                    pre_peak_increasing = sum(1 for i in range(1, len(pre_peak_trend)) 
                                            if pre_peak_trend[i] > pre_peak_trend[i-1])
                    post_peak_decreasing = sum(1 for i in range(1, len(post_peak_trend)) 
                                             if post_peak_trend[i] < post_peak_trend[i-1])
                    
                    if pre_peak_increasing > 0 and post_peak_decreasing > 0:
                        pattern_info['pattern_type'] = 'Entry-Build-Peak-Exit'
                        pattern_info['pre_peak_rises'] = pre_peak_increasing
                        pattern_info['post_peak_declines'] = post_peak_decreasing
                        exhaustion_patterns.append(pattern_info)
            
            # Also track simple score decline patterns
            if pattern_info['decline_pct'] > 20:  # 20% decline from peak
                score_decline_patterns.append(pattern_info)
    
    # Display findings
    print("\n" + "="*80)
    print("TICKERS SHOWING ENTRY → BUILD → PEAK → EXIT PATTERNS")
    print("="*80)
    
    if exhaustion_patterns:
        # Sort by decline percentage
        exhaustion_patterns.sort(key=lambda x: x['decline_pct'], reverse=True)
        
        for i, pattern in enumerate(exhaustion_patterns[:20], 1):  # Show top 20
            print(f"\n{i}. {pattern['ticker']}")
            print(f"  Appearances: {pattern['appearances']} over {pattern['days_span']} days")
            print(f"  Date Range: {pattern['first_date'].strftime('%Y-%m-%d')} to {pattern['last_date'].strftime('%Y-%m-%d')}")
            print(f"  Score Progression: {' → '.join([f'{s:.1f}' for s in pattern['score_progression']])}")
            print(f"  Peak Position: Day {pattern['peak_position'] + 1} of {pattern['appearances']}")
            print(f"  Peak Score: {pattern['max_score']:.1f}")
            print(f"  Current Score: {pattern['latest_score']:.1f}")
            print(f"  Decline: {pattern['score_decline']:.1f} points ({pattern['decline_pct']:.1f}%)")
            
            if pattern['volume_progression'] and any(pattern['volume_progression']):
                non_zero_volumes = [v for v in pattern['volume_progression'] if v]
                if non_zero_volumes:
                    print(f"  Volume Trend: {' → '.join([f'{int(v):,}' if v else '0' for v in pattern['volume_progression'][-3:]])}")
    else:
        print("\nNo clear Entry-Build-Peak-Exit patterns found.")
    
    # Show score decline patterns
    print("\n" + "="*80)
    print("TICKERS WITH SIGNIFICANT SCORE DECLINE (>20%)")
    print("="*80)
    
    if score_decline_patterns:
        # Remove duplicates from exhaustion patterns
        decline_only = [p for p in score_decline_patterns if p not in exhaustion_patterns]
        decline_only.sort(key=lambda x: x['decline_pct'], reverse=True)
        
        for i, pattern in enumerate(decline_only[:15], 1):
            print(f"\n{i}. {pattern['ticker']}")
            print(f"  Appearances: {pattern['appearances']} over {pattern['days_span']} days")
            print(f"  Score Progression: {' → '.join([f'{s:.1f}' for s in pattern['score_progression'][-5:]])}")
            print(f"  Peak Score: {pattern['max_score']:.1f}")
            print(f"  Current Score: {pattern['latest_score']:.1f}")
            print(f"  Decline: {pattern['decline_pct']:.1f}%")
    
    # Analyze tickers that disappeared
    print("\n" + "="*80)
    print("TICKERS THAT DISAPPEARED AFTER HIGH SCORES")
    print("="*80)
    
    # Get the most recent file date
    all_dates = []
    for ticker, history in ticker_history.items():
        for entry in history:
            all_dates.append(entry['date'])
    
    if all_dates:
        most_recent_date = max(all_dates)
        
        # Find tickers that haven't appeared recently
        disappeared_tickers = []
        
        for ticker, history in ticker_history.items():
            history.sort(key=lambda x: (x['date'], x['time']))
            last_appearance = history[-1]['date']
            
            # If last appearance was more than 5 days ago
            days_since_appearance = (most_recent_date - last_appearance).days
            
            if days_since_appearance > 5 and len(history) >= 2:
                # Get scores
                scores = []
                for entry in history:
                    data = entry['data']
                    score = data.get('Score', data.get('score', data.get('SCORE', 
                                    data.get('Total Score', data.get('Total_Score', 
                                    data.get('total_score', 0))))))
                    try:
                        if isinstance(score, str) and '/' in score:
                            # Extract numerator from "6/7" format
                            numerator = int(score.split('/')[0])
                            denominator = int(score.split('/')[1])
                            score = (numerator / denominator) * 100  # Convert to percentage
                        else:
                            score = float(score)
                    except:
                        score = 0.0
                    scores.append(score)
                
                if scores and max(scores) > 0:
                    max_score = max(scores)
                    last_score = scores[-1]
                    
                    # Check if it had a high score before disappearing
                    if max_score > 70:  # High score threshold
                        disappeared_tickers.append({
                            'ticker': ticker,
                            'last_date': last_appearance,
                            'days_absent': days_since_appearance,
                            'max_score': max_score,
                            'last_score': last_score,
                            'appearances': len(history),
                            'score_decline': (max_score - last_score) / max_score * 100 if max_score > 0 else 0
                        })
        
        # Sort by days absent
        disappeared_tickers.sort(key=lambda x: x['max_score'], reverse=True)
        
        print(f"\nFound {len(disappeared_tickers)} high-scoring tickers that disappeared")
        
        for ticker_info in disappeared_tickers[:15]:  # Show top 15
            print(f"\n{ticker_info['ticker']}:")
            print(f"  Last Seen: {ticker_info['last_date'].strftime('%Y-%m-%d')} ({ticker_info['days_absent']} days ago)")
            print(f"  Total Appearances: {ticker_info['appearances']}")
            print(f"  Max Score: {ticker_info['max_score']:.1f}")
            print(f"  Last Score: {ticker_info['last_score']:.1f}")
            if ticker_info['score_decline'] > 0:
                print(f"  Score Decline: {ticker_info['score_decline']:.1f}%")
    
    # Create visualizations
    create_visualizations(exhaustion_patterns, score_decline_patterns, ticker_history)
    
    # Save results
    save_results(exhaustion_patterns, score_decline_patterns, disappeared_tickers)
    
    print("\n" + "="*80)
    print("TRADING INSIGHTS")
    print("="*80)
    print("\n1. EXHAUSTION PATTERNS:")
    print("   - Tickers showing Entry-Build-Peak-Exit cycle are prime exit candidates")
    print("   - Score decline >20% from peak suggests momentum exhaustion")
    print("\n2. DISAPPEARED TICKERS:")
    print("   - High-scoring tickers that disappeared likely hit stops or targets")
    print("   - These may re-emerge after consolidation")
    print("\n3. ACTIONABLE SIGNALS:")
    print("   - Exit positions showing consistent score decline")
    print("   - Avoid new entries in declining score tickers")
    print("   - Monitor disappeared tickers for re-entry opportunities")

def create_visualizations(exhaustion_patterns, score_decline_patterns, ticker_history):
    """Create visualization plots"""
    if not exhaustion_patterns and not score_decline_patterns:
        return
        
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. Score progression for top exhaustion patterns
    ax1 = axes[0, 0]
    for i, pattern in enumerate(exhaustion_patterns[:5]):  # Top 5
        scores = pattern['score_progression']
        x = range(len(scores))
        ax1.plot(x, scores, marker='o', label=pattern['ticker'])
    
    ax1.set_title('Score Progression - Top Exhaustion Patterns')
    ax1.set_xlabel('Appearance Number')
    ax1.set_ylabel('Score')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Score decline distribution
    ax2 = axes[0, 1]
    all_patterns = exhaustion_patterns + score_decline_patterns
    declines = [p['decline_pct'] for p in all_patterns if p['decline_pct'] > 0]
    
    if declines:
        ax2.hist(declines, bins=20, edgecolor='black', alpha=0.7)
        ax2.set_title('Distribution of Score Declines')
        ax2.set_xlabel('Score Decline (%)')
        ax2.set_ylabel('Count')
        ax2.axvline(x=np.median(declines), color='red', linestyle='--', 
                   label=f'Median: {np.median(declines):.1f}%')
        ax2.legend()
    
    # 3. Days to peak distribution
    ax3 = axes[1, 0]
    peak_positions = [p['peak_position'] for p in exhaustion_patterns]
    
    if peak_positions:
        ax3.hist(peak_positions, bins=15, edgecolor='black', alpha=0.7)
        ax3.set_title('Days to Peak Score')
        ax3.set_xlabel('Appearance Number of Peak')
        ax3.set_ylabel('Count')
    
    # 4. Appearance count distribution
    ax4 = axes[1, 1]
    appearance_counts = [len(history) for history in ticker_history.values() if len(history) >= 3]
    
    if appearance_counts:
        ax4.hist(appearance_counts, bins=20, edgecolor='black', alpha=0.7)
        ax4.set_title('Distribution of Ticker Appearances')
        ax4.set_xlabel('Number of Appearances')
        ax4.set_ylabel('Count')
    
    plt.tight_layout()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plt.savefig(f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/scanner_pattern_analysis_{timestamp}.png', dpi=300)
    plt.close()
    print(f"\nVisualizations saved to scanner_pattern_analysis_{timestamp}.png")

def save_results(exhaustion_patterns, score_decline_patterns, disappeared_tickers):
    """Save analysis results"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Prepare summary data
    results = {
        'analysis_date': datetime.now().isoformat(),
        'exhaustion_patterns': exhaustion_patterns,
        'score_decline_patterns': score_decline_patterns,
        'disappeared_tickers': disappeared_tickers,
        'summary': {
            'total_exhaustion_patterns': len(exhaustion_patterns),
            'total_decline_patterns': len(score_decline_patterns),
            'total_disappeared': len(disappeared_tickers)
        }
    }
    
    # Save JSON
    json_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/scanner_patterns_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=4, default=str)
    
    # Save Excel summary
    if exhaustion_patterns or score_decline_patterns:
        all_patterns = exhaustion_patterns + [p for p in score_decline_patterns if p not in exhaustion_patterns]
        
        excel_data = []
        for pattern in all_patterns:
            excel_data.append({
                'Ticker': pattern['ticker'],
                'Pattern_Type': pattern.get('pattern_type', 'Score Decline'),
                'Appearances': pattern['appearances'],
                'Days_Span': pattern['days_span'],
                'First_Date': pattern['first_date'],
                'Last_Date': pattern['last_date'],
                'First_Score': pattern['first_score'],
                'Peak_Score': pattern['max_score'],
                'Latest_Score': pattern['latest_score'],
                'Score_Decline': pattern['score_decline'],
                'Decline_Pct': pattern['decline_pct'],
                'Peak_Position': pattern['peak_position']
            })
        
        df = pd.DataFrame(excel_data)
        excel_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/scanner_patterns_{timestamp}.xlsx'
        df.to_excel(excel_file, index=False)
        
        print(f"\nResults saved to:")
        print(f"  - {json_file}")
        print(f"  - {excel_file}")

if __name__ == "__main__":
    analyze_scanner_patterns()