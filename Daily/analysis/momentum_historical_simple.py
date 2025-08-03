#!/usr/bin/env python3
"""
Simple Historical Momentum Analysis
Runs momentum scanner for past existing reports and generates trend plots
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import glob

class SimpleHistoricalAnalyzer:
    def __init__(self):
        """Initialize the analyzer"""
        self.momentum_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Momentum')
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'momentum_historical')
        os.makedirs(self.results_dir, exist_ok=True)
    
    def analyze_existing_reports(self):
        """Analyze existing momentum reports"""
        print("Analyzing existing momentum reports...")
        
        # Find all momentum reports
        report_files = glob.glob(os.path.join(self.momentum_dir, "India-Momentum_Report_*.xlsx"))
        
        historical_data = []
        
        for report_file in sorted(report_files):
            try:
                # Extract date from filename
                filename = os.path.basename(report_file)
                date_str = filename.split('_')[2]  # Get date part
                
                # Parse date
                try:
                    report_date = datetime.strptime(date_str, '%Y%m%d')
                except:
                    continue
                
                # Skip if more than 2 months old
                if report_date < datetime.now() - timedelta(days=60):
                    continue
                
                print(f"Processing {report_date.strftime('%Y-%m-%d')}")
                
                # Read Excel file
                try:
                    # Read Daily sheet
                    df_daily = pd.read_excel(report_file, sheet_name='Daily_Summary')
                    daily_count = len(df_daily)
                    daily_tickers = df_daily['Ticker'].tolist() if 'Ticker' in df_daily.columns else []
                except:
                    daily_count = 0
                    daily_tickers = []
                
                try:
                    # Read Weekly sheet
                    df_weekly = pd.read_excel(report_file, sheet_name='Weekly_Summary')
                    weekly_count = len(df_weekly)
                    weekly_tickers = df_weekly['Ticker'].tolist() if 'Ticker' in df_weekly.columns else []
                except:
                    weekly_count = 0
                    weekly_tickers = []
                
                historical_data.append({
                    'date': report_date,
                    'daily_count': daily_count,
                    'weekly_count': weekly_count,
                    'daily_tickers': daily_tickers[:10],  # First 10
                    'weekly_tickers': weekly_tickers[:10],  # First 10
                    'filename': filename
                })
                
            except Exception as e:
                print(f"Error processing {report_file}: {e}")
                continue
        
        # Sort by date
        historical_data = sorted(historical_data, key=lambda x: x['date'])
        
        print(f"\nFound {len(historical_data)} reports in the past 2 months")
        
        # Save results
        self.save_results(historical_data)
        
        # Generate plots
        if historical_data:
            self.generate_plots(historical_data)
        
        return historical_data
    
    def save_results(self, historical_data):
        """Save historical data to files"""
        # Save as JSON
        json_file = os.path.join(self.results_dir, f'momentum_historical_{datetime.now().strftime("%Y%m%d")}.json')
        with open(json_file, 'w') as f:
            json.dump(historical_data, f, default=str, indent=2)
        
        # Convert to DataFrame for Excel
        df_data = []
        for entry in historical_data:
            df_data.append({
                'Date': entry['date'].strftime('%Y-%m-%d'),
                'Daily_Count': entry['daily_count'],
                'Weekly_Count': entry['weekly_count'],
                'Daily_Tickers': ', '.join(entry['daily_tickers'][:5]),  # First 5
                'Weekly_Tickers': ', '.join(entry['weekly_tickers'][:5])  # First 5
            })
        
        df = pd.DataFrame(df_data)
        excel_file = os.path.join(self.results_dir, f'momentum_historical_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df.to_excel(excel_file, index=False)
        
        print(f"\nResults saved to:")
        print(f"  {json_file}")
        print(f"  {excel_file}")
    
    def generate_plots(self, historical_data):
        """Generate trend plots for daily and weekly momentum"""
        # Prepare data
        dates = [entry['date'] for entry in historical_data]
        daily_counts = [entry['daily_count'] for entry in historical_data]
        weekly_counts = [entry['weekly_count'] for entry in historical_data]
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Daily momentum plot
        ax1.plot(dates, daily_counts, 'b-', linewidth=2, marker='o', markersize=6, label='Daily Momentum')
        ax1.fill_between(dates, daily_counts, alpha=0.3)
        ax1.set_title('Daily Momentum Trend (Past 2 Months)', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Tickers')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Add value labels
        for i, (date, count) in enumerate(zip(dates, daily_counts)):
            if i % max(1, len(dates) // 10) == 0:  # Show every nth label
                ax1.annotate(f'{count}', (date, count), textcoords="offset points", 
                           xytext=(0,10), ha='center', fontsize=8)
        
        # Add moving average if enough data points
        if len(daily_counts) > 7:
            ma7 = pd.Series(daily_counts).rolling(window=7, min_periods=1).mean()
            ax1.plot(dates, ma7, 'r--', linewidth=1, label='7-day MA')
            ax1.legend()
        
        # Weekly momentum plot
        ax2.plot(dates, weekly_counts, 'g-', linewidth=2, marker='s', markersize=6, label='Weekly Momentum')
        ax2.fill_between(dates, weekly_counts, alpha=0.3)
        ax2.set_title('Weekly Momentum Trend (Past 2 Months)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Number of Tickers')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Add value labels
        for i, (date, count) in enumerate(zip(dates, weekly_counts)):
            if i % max(1, len(dates) // 10) == 0:  # Show every nth label
                ax2.annotate(f'{count}', (date, count), textcoords="offset points", 
                           xytext=(0,10), ha='center', fontsize=8)
        
        # Add moving average if enough data points
        if len(weekly_counts) > 7:
            ma7 = pd.Series(weekly_counts).rolling(window=7, min_periods=1).mean()
            ax2.plot(dates, ma7, 'r--', linewidth=1, label='7-day MA')
            ax2.legend()
        
        # Rotate x-axis labels
        for ax in [ax1, ax2]:
            ax.tick_params(axis='x', rotation=45)
            # Show every nth date label to avoid crowding
            n = max(1, len(dates) // 10)
            ax.set_xticks(dates[::n])
        
        # Add statistics
        daily_avg = np.mean(daily_counts) if daily_counts else 0
        weekly_avg = np.mean(weekly_counts) if weekly_counts else 0
        daily_max = max(daily_counts) if daily_counts else 0
        weekly_max = max(weekly_counts) if weekly_counts else 0
        
        # Add text box with statistics
        stats_text = f'Daily: Avg={daily_avg:.1f}, Max={daily_max}\nWeekly: Avg={weekly_avg:.1f}, Max={weekly_max}'
        fig.text(0.02, 0.98, stats_text, transform=fig.transFigure, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        # Save plot
        plot_file = os.path.join(self.results_dir, f'momentum_trend_{datetime.now().strftime("%Y%m%d")}.png')
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"\nPlot saved to: {plot_file}")
        
        plt.close()
        
        # Generate additional analysis plot
        self.generate_analysis_plot(historical_data)
    
    def generate_analysis_plot(self, historical_data):
        """Generate additional analysis plots"""
        # Prepare data
        dates = [entry['date'] for entry in historical_data]
        daily_counts = [entry['daily_count'] for entry in historical_data]
        weekly_counts = [entry['weekly_count'] for entry in historical_data]
        
        # Create figure
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. Combined trend
        ax1.plot(dates, daily_counts, 'b-', linewidth=2, marker='o', label='Daily')
        ax1.plot(dates, weekly_counts, 'g-', linewidth=2, marker='s', label='Weekly')
        ax1.set_title('Daily vs Weekly Momentum Comparison', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Tickers')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Ratio plot (Daily/Weekly)
        ratios = []
        for d, w in zip(daily_counts, weekly_counts):
            if w > 0:
                ratios.append(d / w)
            else:
                ratios.append(0)
        
        ax2.plot(dates, ratios, 'purple', linewidth=2, marker='d')
        ax2.axhline(y=1, color='red', linestyle='--', alpha=0.5)
        ax2.set_title('Daily/Weekly Ratio', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Ratio')
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. Day of week analysis
        dow_data = {'Mon': [], 'Tue': [], 'Wed': [], 'Thu': [], 'Fri': []}
        dow_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri'}
        
        for i, entry in enumerate(historical_data):
            dow = entry['date'].weekday()
            if dow < 5:  # Weekday
                dow_data[dow_map[dow]].append(daily_counts[i])
        
        # Box plot for day of week
        box_data = [dow_data[day] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']]
        ax3.boxplot(box_data, labels=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
        ax3.set_title('Daily Momentum by Day of Week', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Day of Week')
        ax3.set_ylabel('Number of Tickers')
        ax3.grid(True, alpha=0.3)
        
        # 4. Histogram
        ax4.hist(daily_counts, bins=10, alpha=0.5, label='Daily', color='blue', edgecolor='black')
        ax4.hist(weekly_counts, bins=10, alpha=0.5, label='Weekly', color='green', edgecolor='black')
        ax4.set_title('Distribution of Momentum Counts', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Number of Tickers')
        ax4.set_ylabel('Frequency')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save analysis plot
        analysis_file = os.path.join(self.results_dir, 
                                   f'momentum_analysis_{datetime.now().strftime("%Y%m%d")}.png')
        plt.savefig(analysis_file, dpi=150, bbox_inches='tight')
        print(f"Analysis plot saved to: {analysis_file}")
        
        plt.close()

def main():
    """Main function"""
    print("=" * 60)
    print("Historical Momentum Analysis - Simple Version")
    print("Analyzing existing momentum reports from past 2 months")
    print("=" * 60)
    
    analyzer = SimpleHistoricalAnalyzer()
    historical_data = analyzer.analyze_existing_reports()
    
    print("\nAnalysis complete!")
    print(f"Results saved in: {analyzer.results_dir}")
    
    # Print summary
    if historical_data:
        daily_counts = [d['daily_count'] for d in historical_data]
        weekly_counts = [d['weekly_count'] for d in historical_data]
        
        print("\nSummary:")
        print(f"  Total reports analyzed: {len(historical_data)}")
        print(f"  Daily momentum - Avg: {np.mean(daily_counts):.1f}, Max: {max(daily_counts)}")
        print(f"  Weekly momentum - Avg: {np.mean(weekly_counts):.1f}, Max: {max(weekly_counts)}")

if __name__ == "__main__":
    main()