"""
Enhanced Volume-Price Anomaly Analysis with Stop Loss Correlation
=================================================================
This script performs detailed analysis of volume-price patterns and their
correlation with actual stop loss events and price reversals.
"""

import pandas as pd
import numpy as np
import os
import re
from datetime import datetime, timedelta
import json
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

# Configuration
DAILY_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily"
RESULTS_DIR = os.path.join(DAILY_DIR, "results")
LOGS_DIR = os.path.join(DAILY_DIR, "logs", "Sai")
OUTPUT_DIR = os.path.join(DAILY_DIR, "Market_Regime", "volume_analysis")
DATA_DIR = "/Users/maverick/PycharmProjects/India-TS/data"

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_scan_results(days_back=30):
    """Load Long Reversal Daily scan results from the past N days"""
    all_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Find all Long_Reversal_Daily files
    for root, dirs, files in os.walk(DAILY_DIR):
        if 'backup' in root:
            continue
        for file in files:
            if 'Long_Reversal_Daily' in file and file.endswith('.xlsx'):
                try:
                    # Extract date from filename
                    date_str = file.split('_')[3].split('.')[0]
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    if start_date <= file_date <= end_date:
                        filepath = os.path.join(root, file)
                        df = pd.read_excel(filepath)
                        df['Scan_Date'] = file_date.date()
                        df['Scan_Time'] = file.split('_')[4].split('.')[0]
                        df['Scan_Hour'] = int(df['Scan_Time'][:2])
                        all_data.append(df)
                except Exception as e:
                    continue
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"Loaded {len(combined_df)} scan records from {len(all_data)} files")
        return combined_df
    else:
        print("No scan data found")
        return pd.DataFrame()

def extract_stop_loss_events(log_file):
    """Extract actual stop loss trigger events from log"""
    events = []
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return pd.DataFrame()
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        # Look for ATR stop loss updates
        if 'ATR Stop Loss Updated' in line:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(\w+): ATR Stop Loss Updated.*?Position High: ₹([\d.]+), Stop Loss: ₹([\d.]+)', line)
            if match:
                events.append({
                    'Timestamp': match.group(1),
                    'Ticker': match.group(2),
                    'Position_High': float(match.group(3)),
                    'Stop_Loss': float(match.group(4)),
                    'Event_Type': 'SL_Update'
                })
        
        # Look for position closes
        elif 'Position closed' in line or 'Exit' in line:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(\w+).*?(Position closed|Exit)', line)
            if match:
                events.append({
                    'Timestamp': match.group(1),
                    'Ticker': match.group(2),
                    'Event_Type': 'Position_Close'
                })
    
    return pd.DataFrame(events)

def calculate_advanced_metrics(df):
    """Calculate advanced volume-price metrics"""
    if df.empty:
        return df
    
    # Basic metrics
    df['Price_Spread_Pct'] = (df['ATR'] / df['Entry_Price']) * 100
    df['Volume_Price_Ratio'] = df['Volume_Ratio'] / df['Price_Spread_Pct']
    
    # Volume efficiency with protection against division by zero
    df['Volume_Efficiency'] = np.where(
        df['Volume_Ratio'] > 0,
        df['Momentum_5D'] / df['Volume_Ratio'],
        0
    )
    
    # Price rejection indicator (high volume but low momentum)
    df['Price_Rejection'] = (
        (df['Volume_Ratio'] > df['Volume_Ratio'].quantile(0.75)) & 
        (df['Momentum_5D'] < df['Momentum_5D'].quantile(0.25))
    )
    
    # Volume exhaustion (very high volume with weak price action)
    df['Volume_Exhaustion'] = (
        (df['Volume_Ratio'] > 3) & 
        (df['Momentum_5D'] < 5)
    )
    
    # Narrow range high volume
    df['Narrow_Range_High_Vol'] = (
        (df['Volume_Ratio'] > 2) & 
        (df['Price_Spread_Pct'] < df['Price_Spread_Pct'].quantile(0.25))
    )
    
    # Combined exhaustion score
    df['Exhaustion_Score'] = (
        df['Price_Rejection'].astype(int) * 2 +
        df['Volume_Exhaustion'].astype(int) * 3 +
        df['Narrow_Range_High_Vol'].astype(int) * 1
    )
    
    return df

def analyze_ticker_patterns(scan_df, sl_events_df):
    """Analyze patterns for each ticker"""
    pattern_analysis = []
    
    # Group by ticker
    for ticker in scan_df['Ticker'].unique():
        ticker_scans = scan_df[scan_df['Ticker'] == ticker].sort_values(['Scan_Date', 'Scan_Hour'])
        ticker_sl = sl_events_df[sl_events_df['Ticker'] == ticker] if not sl_events_df.empty else pd.DataFrame()
        
        # Analyze each scan appearance
        for idx, scan in ticker_scans.iterrows():
            # Calculate metrics
            metrics = {
                'Ticker': ticker,
                'Scan_Date': scan['Scan_Date'],
                'Scan_Hour': scan['Scan_Hour'],
                'Volume_Ratio': scan['Volume_Ratio'],
                'Momentum_5D': scan['Momentum_5D'],
                'Price_Spread_Pct': scan.get('Price_Spread_Pct', 0),
                'Volume_Efficiency': scan.get('Volume_Efficiency', 0),
                'Exhaustion_Score': scan.get('Exhaustion_Score', 0),
                'Entry_Price': scan['Entry_Price'],
                'Stop_Loss': scan['Stop_Loss']
            }
            
            # Check for subsequent events
            scan_datetime = pd.to_datetime(str(scan['Scan_Date']) + ' ' + str(scan['Scan_Hour']).zfill(2) + ':00:00')
            
            # Look for stop loss updates within next 5 days
            future_window = scan_datetime + timedelta(days=5)
            
            if not ticker_sl.empty:
                future_sl_events = ticker_sl[
                    (pd.to_datetime(ticker_sl['Timestamp']) > scan_datetime) &
                    (pd.to_datetime(ticker_sl['Timestamp']) <= future_window)
                ]
                
                if len(future_sl_events) > 0:
                    first_event = future_sl_events.iloc[0]
                    event_time = pd.to_datetime(first_event['Timestamp'])
                    hours_to_event = (event_time - scan_datetime).total_seconds() / 3600
                    
                    metrics['Had_SL_Event'] = True
                    metrics['Hours_to_Event'] = hours_to_event
                    metrics['Event_Type'] = first_event['Event_Type']
                else:
                    metrics['Had_SL_Event'] = False
                    metrics['Hours_to_Event'] = None
                    metrics['Event_Type'] = None
            else:
                metrics['Had_SL_Event'] = False
                metrics['Hours_to_Event'] = None
                metrics['Event_Type'] = None
            
            pattern_analysis.append(metrics)
    
    return pd.DataFrame(pattern_analysis)

def generate_detailed_report(scan_df, pattern_df):
    """Generate comprehensive analysis report with actionable insights"""
    report = []
    
    report.append("=" * 100)
    report.append("ENHANCED VOLUME-PRICE ANOMALY ANALYSIS REPORT")
    report.append("=" * 100)
    report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Scan Records: {len(scan_df)}")
    report.append(f"Unique Tickers: {scan_df['Ticker'].nunique()}")
    report.append(f"Date Range: {scan_df['Scan_Date'].min()} to {scan_df['Scan_Date'].max()}")
    report.append("")
    
    # Volume Analysis
    report.append("VOLUME ANALYSIS:")
    report.append("-" * 50)
    report.append(f"Average Volume Ratio: {scan_df['Volume_Ratio'].mean():.2f}")
    report.append(f"Median Volume Ratio: {scan_df['Volume_Ratio'].median():.2f}")
    report.append(f"High Volume (>2x) Cases: {(scan_df['Volume_Ratio'] > 2).sum()} ({(scan_df['Volume_Ratio'] > 2).sum()/len(scan_df)*100:.1f}%)")
    report.append(f"Extreme Volume (>3x) Cases: {(scan_df['Volume_Ratio'] > 3).sum()} ({(scan_df['Volume_Ratio'] > 3).sum()/len(scan_df)*100:.1f}%)")
    report.append("")
    
    # Exhaustion Patterns
    report.append("EXHAUSTION PATTERNS IDENTIFIED:")
    report.append("-" * 50)
    
    if 'Price_Rejection' in scan_df.columns:
        pr_count = scan_df['Price_Rejection'].sum()
        report.append(f"Price Rejection Patterns: {pr_count} ({pr_count/len(scan_df)*100:.1f}%)")
    
    if 'Volume_Exhaustion' in scan_df.columns:
        ve_count = scan_df['Volume_Exhaustion'].sum()
        report.append(f"Volume Exhaustion Patterns: {ve_count} ({ve_count/len(scan_df)*100:.1f}%)")
    
    if 'Narrow_Range_High_Vol' in scan_df.columns:
        nr_count = scan_df['Narrow_Range_High_Vol'].sum()
        report.append(f"Narrow Range + High Volume: {nr_count} ({nr_count/len(scan_df)*100:.1f}%)")
    
    report.append("")
    
    # Pattern Success Analysis
    if not pattern_df.empty and 'Had_SL_Event' in pattern_df.columns:
        report.append("PATTERN SUCCESS ANALYSIS:")
        report.append("-" * 50)
        
        # Group by exhaustion score
        for score in sorted(pattern_df['Exhaustion_Score'].unique()):
            score_df = pattern_df[pattern_df['Exhaustion_Score'] == score]
            if len(score_df) > 0:
                sl_rate = (score_df['Had_SL_Event'].sum() / len(score_df)) * 100
                avg_hours = score_df[score_df['Had_SL_Event']]['Hours_to_Event'].mean() if score_df['Had_SL_Event'].any() else 0
                report.append(f"Exhaustion Score {score}: {len(score_df)} cases, {sl_rate:.1f}% SL rate, Avg {avg_hours:.1f} hours to event")
        
        report.append("")
        
        # High-risk patterns
        high_risk = pattern_df[pattern_df['Exhaustion_Score'] >= 3]
        if len(high_risk) > 0:
            report.append("HIGH-RISK PATTERNS (Score >= 3):")
            report.append(f"Total Cases: {len(high_risk)}")
            report.append(f"Stop Loss Rate: {(high_risk['Had_SL_Event'].sum() / len(high_risk)) * 100:.1f}%")
            
            # Recent high-risk candidates
            latest_date = pattern_df['Scan_Date'].max()
            recent_high_risk = high_risk[high_risk['Scan_Date'] == latest_date].sort_values('Exhaustion_Score', ascending=False)
            
            if len(recent_high_risk) > 0:
                report.append("\nRecent High-Risk Candidates:")
                for _, row in recent_high_risk.head(10).iterrows():
                    report.append(f"  {row['Ticker']}: Score={row['Exhaustion_Score']}, "
                                 f"Vol={row['Volume_Ratio']:.1f}x, Mom={row['Momentum_5D']:.1f}%")
    
    report.append("")
    
    # Key Findings
    report.append("KEY FINDINGS & ACTIONABLE INSIGHTS:")
    report.append("-" * 50)
    report.append("1. IMMEDIATE EXIT SIGNALS:")
    report.append("   - Exhaustion Score >= 4 (multiple red flags)")
    report.append("   - Volume > 3x with Momentum < 3%")
    report.append("   - Volume Efficiency < 0.5 with Volume > 2x")
    report.append("")
    report.append("2. WARNING SIGNALS (Tighten Stops):")
    report.append("   - Exhaustion Score = 3")
    report.append("   - Narrow range with volume > 2x average")
    report.append("   - Momentum divergence (high volume, weak price)")
    report.append("")
    report.append("3. OPTIMAL PATTERNS (Continue Holding):")
    report.append("   - Volume 1.5-2x with strong momentum (>10%)")
    report.append("   - Volume efficiency > 3")
    report.append("   - No exhaustion flags")
    
    # Save report
    report_text = "\n".join(report)
    report_file = os.path.join(OUTPUT_DIR, f"enhanced_volume_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_file, 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nReport saved to: {report_file}")
    
    return report_text

def create_advanced_visualizations(scan_df, pattern_df):
    """Create advanced visualization charts"""
    plt.style.use('seaborn-v0_8-darkgrid')
    fig = plt.figure(figsize=(20, 15))
    
    # Create grid spec for custom layout
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. Volume vs Momentum Heatmap
    ax1 = fig.add_subplot(gs[0, :2])
    if 'Exhaustion_Score' in scan_df.columns:
        scatter = ax1.scatter(scan_df['Volume_Ratio'], scan_df['Momentum_5D'], 
                             c=scan_df['Exhaustion_Score'], cmap='RdYlBu_r', 
                             alpha=0.6, s=50)
        plt.colorbar(scatter, ax=ax1, label='Exhaustion Score')
        ax1.set_xlabel('Volume Ratio')
        ax1.set_ylabel('5-Day Momentum (%)')
        ax1.set_title('Volume vs Momentum (Color = Exhaustion Score)')
        ax1.axhline(5, color='red', linestyle='--', alpha=0.5, label='Low Momentum')
        ax1.axvline(3, color='red', linestyle='--', alpha=0.5, label='High Volume')
        ax1.legend()
    
    # 2. Exhaustion Score Distribution
    ax2 = fig.add_subplot(gs[0, 2])
    if 'Exhaustion_Score' in scan_df.columns:
        scan_df['Exhaustion_Score'].value_counts().sort_index().plot(kind='bar', ax=ax2)
        ax2.set_xlabel('Exhaustion Score')
        ax2.set_ylabel('Count')
        ax2.set_title('Distribution of Exhaustion Scores')
    
    # 3. Volume Efficiency Analysis
    ax3 = fig.add_subplot(gs[1, 0])
    if 'Volume_Efficiency' in scan_df.columns:
        # Clean data
        ve_clean = scan_df['Volume_Efficiency'].replace([np.inf, -np.inf], np.nan).dropna()
        ve_clean = ve_clean[ve_clean.between(ve_clean.quantile(0.05), ve_clean.quantile(0.95))]
        ve_clean.hist(bins=50, ax=ax3, alpha=0.7, color='green')
        ax3.axvline(ve_clean.median(), color='red', linestyle='--', label=f'Median: {ve_clean.median():.2f}')
        ax3.set_xlabel('Volume Efficiency')
        ax3.set_ylabel('Frequency')
        ax3.set_title('Volume Efficiency Distribution')
        ax3.legend()
    
    # 4. Time to Stop Loss Analysis
    ax4 = fig.add_subplot(gs[1, 1])
    if not pattern_df.empty and 'Hours_to_Event' in pattern_df.columns:
        event_df = pattern_df[pattern_df['Had_SL_Event'] == True]
        if len(event_df) > 0:
            event_df['Hours_to_Event'].hist(bins=30, ax=ax4, alpha=0.7, color='orange')
            ax4.axvline(event_df['Hours_to_Event'].median(), color='red', linestyle='--', 
                       label=f'Median: {event_df["Hours_to_Event"].median():.1f}h')
            ax4.set_xlabel('Hours to Stop Loss Event')
            ax4.set_ylabel('Frequency')
            ax4.set_title('Time to Stop Loss Distribution')
            ax4.legend()
    
    # 5. Success Rate by Exhaustion Score
    ax5 = fig.add_subplot(gs[1, 2])
    if not pattern_df.empty and 'Exhaustion_Score' in pattern_df.columns:
        success_by_score = pattern_df.groupby('Exhaustion_Score')['Had_SL_Event'].agg(['sum', 'count'])
        success_by_score['rate'] = (success_by_score['sum'] / success_by_score['count']) * 100
        success_by_score['rate'].plot(kind='bar', ax=ax5, color='red')
        ax5.set_xlabel('Exhaustion Score')
        ax5.set_ylabel('Stop Loss Hit Rate (%)')
        ax5.set_title('Stop Loss Rate by Exhaustion Score')
        
        # Add count labels
        for i, (idx, row) in enumerate(success_by_score.iterrows()):
            ax5.text(i, row['rate'] + 1, f'n={row["count"]}', ha='center', fontsize=9)
    
    # 6. Pattern Performance Matrix
    ax6 = fig.add_subplot(gs[2, :])
    if 'Price_Rejection' in scan_df.columns:
        # Create performance matrix
        patterns = ['Price_Rejection', 'Volume_Exhaustion', 'Narrow_Range_High_Vol']
        pattern_names = ['Price\nRejection', 'Volume\nExhaustion', 'Narrow Range\nHigh Vol']
        
        # Count occurrences
        counts = []
        for p in patterns:
            if p in scan_df.columns:
                counts.append(scan_df[p].sum())
            else:
                counts.append(0)
        
        # Create bar chart
        x = np.arange(len(pattern_names))
        ax6.bar(x, counts, color=['red', 'orange', 'yellow'])
        ax6.set_xticks(x)
        ax6.set_xticklabels(pattern_names)
        ax6.set_ylabel('Occurrences')
        ax6.set_title('Exhaustion Pattern Frequency')
        
        # Add value labels
        for i, v in enumerate(counts):
            ax6.text(i, v + 10, str(v), ha='center')
    
    plt.suptitle('Volume-Price Anomaly Analysis Dashboard', fontsize=16, y=0.98)
    
    # Save figure
    chart_file = os.path.join(OUTPUT_DIR, f"enhanced_volume_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    plt.savefig(chart_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Charts saved to: {chart_file}")

def save_actionable_candidates(scan_df, pattern_df):
    """Save current high-risk candidates for monitoring"""
    latest_date = scan_df['Scan_Date'].max()
    latest_scans = scan_df[scan_df['Scan_Date'] == latest_date]
    
    # Filter high-risk candidates
    high_risk = latest_scans[latest_scans['Exhaustion_Score'] >= 3].sort_values('Exhaustion_Score', ascending=False)
    
    if len(high_risk) > 0:
        # Prepare output
        output_data = []
        for _, row in high_risk.iterrows():
            output_data.append({
                'Ticker': row['Ticker'],
                'Exhaustion_Score': row['Exhaustion_Score'],
                'Volume_Ratio': round(row['Volume_Ratio'], 2),
                'Momentum_5D': round(row['Momentum_5D'], 2),
                'Volume_Efficiency': round(row.get('Volume_Efficiency', 0), 2),
                'Entry_Price': row['Entry_Price'],
                'Stop_Loss': row['Stop_Loss'],
                'Risk_Action': 'EXIT' if row['Exhaustion_Score'] >= 4 else 'TIGHTEN_STOP'
            })
        
        # Save to Excel
        output_df = pd.DataFrame(output_data)
        output_file = os.path.join(OUTPUT_DIR, f"high_risk_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        output_df.to_excel(output_file, index=False)
        print(f"\nHigh-risk candidates saved to: {output_file}")
        
        # Also save as JSON for programmatic access
        json_file = os.path.join(OUTPUT_DIR, "current_high_risk_candidates.json")
        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"JSON version saved to: {json_file}")

def main():
    """Main analysis function"""
    print("Starting Enhanced Volume-Price Anomaly Analysis...")
    
    # Load scan results
    scan_df = load_scan_results(days_back=30)
    if scan_df.empty:
        print("No scan data available for analysis")
        return
    
    # Calculate advanced metrics
    scan_df = calculate_advanced_metrics(scan_df)
    
    # Load stop loss events
    log_file = os.path.join(LOGS_DIR, "SL_watchdog_Sai.log")
    sl_events_df = extract_stop_loss_events(log_file)
    print(f"Extracted {len(sl_events_df)} stop loss events from log")
    
    # Analyze patterns
    pattern_df = analyze_ticker_patterns(scan_df, sl_events_df)
    
    # Generate report
    generate_detailed_report(scan_df, pattern_df)
    
    # Create visualizations
    create_advanced_visualizations(scan_df, pattern_df)
    
    # Save actionable candidates
    save_actionable_candidates(scan_df, pattern_df)
    
    # Save full analysis data
    scan_df.to_csv(os.path.join(OUTPUT_DIR, f"full_scan_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"), index=False)
    
    if not pattern_df.empty:
        pattern_df.to_csv(os.path.join(OUTPUT_DIR, f"pattern_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"), index=False)
    
    print("\nEnhanced analysis complete!")

if __name__ == "__main__":
    main()