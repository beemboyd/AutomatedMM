"""
Volume-Price Anomaly Analysis for Exit Signal Improvement
=========================================================
This script analyzes volume-price anomalies to identify exhaustion patterns
and correlate them with subsequent stop loss hits or price reversals.
"""

import pandas as pd
import numpy as np
import os
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

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_scan_results(days_back=30):
    """Load Long Reversal Daily scan results from the past N days"""
    all_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Find all Long_Reversal_Daily files
    for root, dirs, files in os.walk(RESULTS_DIR):
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
                        all_data.append(df)
                except Exception as e:
                    print(f"Error loading {file}: {e}")
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"Loaded {len(combined_df)} scan records from {len(all_data)} files")
        return combined_df
    else:
        print("No scan data found")
        return pd.DataFrame()

def calculate_volume_price_metrics(df):
    """Calculate volume-price anomaly metrics"""
    if df.empty:
        return df
    
    # Volume/Price Spread ratio
    df['Price_Spread'] = (df['Entry_Price'] * df['ATR']) / df['Entry_Price'] * 100  # ATR as % of price
    df['Volume_Price_Ratio'] = df['Volume_Ratio'] / df['Price_Spread']
    
    # Volume efficiency (momentum per unit volume)
    df['Volume_Efficiency'] = df['Momentum_5D'] / df['Volume_Ratio']
    
    # Classify volume anomalies
    df['High_Volume_Low_Spread'] = (df['Volume_Ratio'] > 2) & (df['Price_Spread'] < 2)
    df['Volume_Divergence'] = (df['Volume_Ratio'] > 3) & (df['Momentum_5D'] < 5)
    df['Exhaustion_Pattern'] = (df['Volume_Ratio'] > df['Volume_Ratio'].quantile(0.8)) & \
                               (df['Volume_Efficiency'] < df['Volume_Efficiency'].quantile(0.2))
    
    return df

def analyze_stop_loss_patterns(scan_df, log_file):
    """Analyze patterns from SL watchdog logs"""
    stop_loss_events = []
    
    # Parse log file for stop loss events
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            if 'Stop Loss Updated' in line or 'stop loss triggered' in line.lower():
                try:
                    # Extract ticker and details
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        timestamp = parts[0]
                        ticker = parts[2].split(':')[0] if ':' in parts[2] else None
                        
                        if ticker:
                            stop_loss_events.append({
                                'Timestamp': timestamp,
                                'Ticker': ticker,
                                'Event': 'Stop Loss',
                                'Details': line.strip()
                            })
                except Exception as e:
                    continue
    
    return pd.DataFrame(stop_loss_events)

def correlate_anomalies_with_exits(scan_df, sl_events_df):
    """Correlate volume anomalies with subsequent stop loss hits"""
    correlation_results = []
    
    # Group by ticker
    for ticker in scan_df['Ticker'].unique():
        ticker_scans = scan_df[scan_df['Ticker'] == ticker].sort_values('Scan_Date')
        ticker_sl_events = sl_events_df[sl_events_df['Ticker'] == ticker]
        
        for _, scan in ticker_scans.iterrows():
            # Check if this ticker had anomalies
            anomalies = {
                'High_Volume_Low_Spread': scan.get('High_Volume_Low_Spread', False),
                'Volume_Divergence': scan.get('Volume_Divergence', False),
                'Exhaustion_Pattern': scan.get('Exhaustion_Pattern', False)
            }
            
            # Look for stop loss events within next 5 days
            scan_date = pd.to_datetime(scan['Scan_Date'])
            future_window = scan_date + timedelta(days=5)
            
            # Check if stop loss was hit
            sl_hit = False
            days_to_sl = None
            
            for _, sl_event in ticker_sl_events.iterrows():
                try:
                    sl_date = pd.to_datetime(sl_event['Timestamp'].split()[0])
                    if scan_date <= sl_date <= future_window:
                        sl_hit = True
                        days_to_sl = (sl_date - scan_date).days
                        break
                except:
                    continue
            
            correlation_results.append({
                'Ticker': ticker,
                'Scan_Date': scan['Scan_Date'],
                'Volume_Ratio': scan['Volume_Ratio'],
                'Momentum_5D': scan['Momentum_5D'],
                'Volume_Efficiency': scan.get('Volume_Efficiency', None),
                'Has_Anomaly': any(anomalies.values()),
                'Anomaly_Types': [k for k, v in anomalies.items() if v],
                'SL_Hit': sl_hit,
                'Days_to_SL': days_to_sl
            })
    
    return pd.DataFrame(correlation_results)

def generate_analysis_report(scan_df, correlation_df):
    """Generate comprehensive analysis report"""
    report = []
    
    report.append("=" * 80)
    report.append("VOLUME-PRICE ANOMALY ANALYSIS REPORT")
    report.append("=" * 80)
    report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Scan Records: {len(scan_df)}")
    report.append(f"Unique Tickers: {scan_df['Ticker'].nunique()}")
    report.append("")
    
    # Volume Statistics
    report.append("VOLUME RATIO STATISTICS:")
    report.append("-" * 40)
    report.append(f"Mean Volume Ratio: {scan_df['Volume_Ratio'].mean():.2f}")
    report.append(f"Median Volume Ratio: {scan_df['Volume_Ratio'].median():.2f}")
    report.append(f"Max Volume Ratio: {scan_df['Volume_Ratio'].max():.2f}")
    report.append("")
    
    # Anomaly Detection Results
    report.append("ANOMALY DETECTION RESULTS:")
    report.append("-" * 40)
    
    if 'High_Volume_Low_Spread' in scan_df.columns:
        hvls_count = scan_df['High_Volume_Low_Spread'].sum()
        hvls_pct = (hvls_count / len(scan_df)) * 100
        report.append(f"High Volume + Low Spread: {hvls_count} ({hvls_pct:.1f}%)")
    
    if 'Volume_Divergence' in scan_df.columns:
        vd_count = scan_df['Volume_Divergence'].sum()
        vd_pct = (vd_count / len(scan_df)) * 100
        report.append(f"Volume Divergence: {vd_count} ({vd_pct:.1f}%)")
    
    if 'Exhaustion_Pattern' in scan_df.columns:
        ep_count = scan_df['Exhaustion_Pattern'].sum()
        ep_pct = (ep_count / len(scan_df)) * 100
        report.append(f"Exhaustion Patterns: {ep_count} ({ep_pct:.1f}%)")
    
    report.append("")
    
    # Correlation with Stop Losses
    if not correlation_df.empty:
        report.append("CORRELATION WITH STOP LOSSES:")
        report.append("-" * 40)
        
        # Calculate hit rates
        anomaly_df = correlation_df[correlation_df['Has_Anomaly'] == True]
        no_anomaly_df = correlation_df[correlation_df['Has_Anomaly'] == False]
        
        if len(anomaly_df) > 0:
            anomaly_sl_rate = (anomaly_df['SL_Hit'].sum() / len(anomaly_df)) * 100
            report.append(f"Stop Loss Hit Rate (WITH anomalies): {anomaly_sl_rate:.1f}%")
        
        if len(no_anomaly_df) > 0:
            no_anomaly_sl_rate = (no_anomaly_df['SL_Hit'].sum() / len(no_anomaly_df)) * 100
            report.append(f"Stop Loss Hit Rate (WITHOUT anomalies): {no_anomaly_sl_rate:.1f}%")
        
        # Average days to stop loss
        sl_hits_with_days = correlation_df[(correlation_df['SL_Hit'] == True) & (correlation_df['Days_to_SL'].notna())]
        if len(sl_hits_with_days) > 0:
            avg_days_to_sl = sl_hits_with_days['Days_to_SL'].mean()
            report.append(f"Average Days to Stop Loss: {avg_days_to_sl:.1f}")
    
    report.append("")
    
    # Top Exhaustion Candidates
    report.append("TOP EXHAUSTION CANDIDATES (Latest Scan):")
    report.append("-" * 40)
    
    latest_scan_date = scan_df['Scan_Date'].max()
    latest_df = scan_df[scan_df['Scan_Date'] == latest_scan_date]
    
    if 'Exhaustion_Pattern' in latest_df.columns:
        exhaustion_tickers = latest_df[latest_df['Exhaustion_Pattern'] == True].sort_values('Volume_Ratio', ascending=False)
        
        for _, row in exhaustion_tickers.head(10).iterrows():
            report.append(f"  {row['Ticker']}: Volume {row['Volume_Ratio']:.1f}x, "
                         f"Momentum {row['Momentum_5D']:.1f}%, "
                         f"Efficiency {row.get('Volume_Efficiency', 0):.2f}")
    
    report.append("")
    
    # Actionable Patterns
    report.append("ACTIONABLE PATTERNS IDENTIFIED:")
    report.append("-" * 40)
    report.append("1. Volume > 3x average with momentum < 5% → High exhaustion risk")
    report.append("2. Volume > 2x average with price spread < 2% → Potential rejection")
    report.append("3. Volume efficiency < 0.2 with high volume → Weak follow-through")
    report.append("")
    
    # Save report
    report_text = "\n".join(report)
    report_file = os.path.join(OUTPUT_DIR, f"volume_anomaly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_file, 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nReport saved to: {report_file}")
    
    return report_text

def create_visualizations(scan_df, correlation_df):
    """Create visualization charts"""
    # Set up the plotting style
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Volume Ratio Distribution
    ax1 = axes[0, 0]
    scan_df['Volume_Ratio'].hist(bins=30, ax=ax1, alpha=0.7, color='blue')
    ax1.axvline(scan_df['Volume_Ratio'].mean(), color='red', linestyle='--', label=f'Mean: {scan_df["Volume_Ratio"].mean():.2f}')
    ax1.axvline(2, color='orange', linestyle='--', label='Anomaly Threshold: 2x')
    ax1.set_xlabel('Volume Ratio')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Volume Ratio Distribution')
    ax1.legend()
    
    # 2. Volume vs Momentum Scatter
    ax2 = axes[0, 1]
    colors = ['red' if x else 'blue' for x in scan_df.get('Exhaustion_Pattern', [False]*len(scan_df))]
    ax2.scatter(scan_df['Volume_Ratio'], scan_df['Momentum_5D'], alpha=0.6, c=colors)
    ax2.set_xlabel('Volume Ratio')
    ax2.set_ylabel('5-Day Momentum (%)')
    ax2.set_title('Volume vs Momentum (Red = Exhaustion Pattern)')
    ax2.axhline(5, color='orange', linestyle='--', alpha=0.5)
    ax2.axvline(3, color='orange', linestyle='--', alpha=0.5)
    
    # 3. Volume Efficiency Distribution
    if 'Volume_Efficiency' in scan_df.columns:
        ax3 = axes[1, 0]
        # Filter out inf and nan values
        ve_clean = scan_df['Volume_Efficiency'].replace([np.inf, -np.inf], np.nan).dropna()
        if len(ve_clean) > 0:
            ve_clean.hist(bins=30, ax=ax3, alpha=0.7, color='green')
            ax3.axvline(ve_clean.quantile(0.2), color='red', linestyle='--', 
                       label=f'20th Percentile: {ve_clean.quantile(0.2):.2f}')
            ax3.set_xlabel('Volume Efficiency (Momentum/Volume)')
            ax3.set_ylabel('Frequency')
            ax3.set_title('Volume Efficiency Distribution')
            ax3.legend()
    
    # 4. Anomaly Hit Rates
    if not correlation_df.empty and 'Has_Anomaly' in correlation_df.columns:
        ax4 = axes[1, 1]
        
        # Calculate hit rates by anomaly type
        hit_rates = []
        labels = []
        
        # Overall rates
        with_anomaly = correlation_df[correlation_df['Has_Anomaly'] == True]
        without_anomaly = correlation_df[correlation_df['Has_Anomaly'] == False]
        
        if len(with_anomaly) > 0:
            hit_rates.append((with_anomaly['SL_Hit'].sum() / len(with_anomaly)) * 100)
            labels.append('With Anomaly')
        
        if len(without_anomaly) > 0:
            hit_rates.append((without_anomaly['SL_Hit'].sum() / len(without_anomaly)) * 100)
            labels.append('Without Anomaly')
        
        if hit_rates:
            ax4.bar(labels, hit_rates, color=['red', 'blue'])
            ax4.set_ylabel('Stop Loss Hit Rate (%)')
            ax4.set_title('Stop Loss Hit Rates by Anomaly Presence')
            ax4.set_ylim(0, 100)
            
            # Add value labels on bars
            for i, v in enumerate(hit_rates):
                ax4.text(i, v + 1, f'{v:.1f}%', ha='center')
    
    plt.tight_layout()
    chart_file = os.path.join(OUTPUT_DIR, f"volume_anomaly_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    plt.savefig(chart_file, dpi=150)
    plt.close()
    
    print(f"Charts saved to: {chart_file}")

def main():
    """Main analysis function"""
    print("Starting Volume-Price Anomaly Analysis...")
    
    # Load scan results
    scan_df = load_scan_results(days_back=30)
    if scan_df.empty:
        print("No scan data available for analysis")
        return
    
    # Calculate volume-price metrics
    scan_df = calculate_volume_price_metrics(scan_df)
    
    # Load stop loss events
    log_file = os.path.join(LOGS_DIR, "SL_watchdog_Sai.log")
    sl_events_df = analyze_stop_loss_patterns(scan_df, log_file)
    
    # Correlate anomalies with exits
    correlation_df = correlate_anomalies_with_exits(scan_df, sl_events_df)
    
    # Generate report
    generate_analysis_report(scan_df, correlation_df)
    
    # Create visualizations
    create_visualizations(scan_df, correlation_df)
    
    # Save processed data
    scan_df.to_csv(os.path.join(OUTPUT_DIR, f"processed_scan_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"), index=False)
    
    if not correlation_df.empty:
        correlation_df.to_csv(os.path.join(OUTPUT_DIR, f"correlation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"), index=False)
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main()