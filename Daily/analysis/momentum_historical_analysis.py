#!/usr/bin/env python3
"""
Historical Momentum Analysis
Runs momentum scanner for past 2 months and generates trend plots
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner_historical import HistoricalMomentumScanner

class HistoricalMomentumAnalyzer:
    def __init__(self):
        """Initialize the analyzer"""
        self.scanner = HistoricalMomentumScanner(user_name='Sai')
        self.results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       'analysis', 'momentum_historical')
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_file = os.path.join(self.results_dir, f'momentum_historical_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_trading_days(self, start_date, end_date):
        """Get list of trading days between start and end date"""
        trading_days = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                trading_days.append(current_date)
            current_date += timedelta(days=1)
        
        return trading_days
    
    def run_historical_scan(self, days_back=60):
        """Run momentum scan for past N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        trading_days = self.get_trading_days(start_date, end_date)
        
        self.logger.info(f"Running historical momentum scan for {len(trading_days)} trading days")
        self.logger.info(f"From {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Store results
        historical_data = []
        
        for i, scan_date in enumerate(trading_days):
            self.logger.info(f"\nProcessing {i+1}/{len(trading_days)}: {scan_date.strftime('%Y-%m-%d')}")
            
            try:
                # Run scan for specific date
                results = self.scanner.run_scan_for_date(scan_date)
                
                # Extract counts
                daily_count = len(results.get('Daily', []))
                weekly_count = len(results.get('Weekly', []))
                
                # Get ticker lists
                daily_tickers = [r['Ticker'] for r in results.get('Daily', [])]
                weekly_tickers = [r['Ticker'] for r in results.get('Weekly', [])]
                
                historical_data.append({
                    'date': scan_date,
                    'daily_count': daily_count,
                    'weekly_count': weekly_count,
                    'daily_tickers': daily_tickers,
                    'weekly_tickers': weekly_tickers
                })
                
                self.logger.info(f"Daily: {daily_count} tickers, Weekly: {weekly_count} tickers")
                
                # Add small delay to avoid rate limits
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error processing {scan_date}: {e}")
                historical_data.append({
                    'date': scan_date,
                    'daily_count': 0,
                    'weekly_count': 0,
                    'daily_tickers': [],
                    'weekly_tickers': []
                })
        
        # Save results
        self.save_results(historical_data)
        
        # Generate plots
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
                'Date': entry['date'],
                'Daily_Count': entry['daily_count'],
                'Weekly_Count': entry['weekly_count'],
                'Daily_Tickers': ', '.join(entry['daily_tickers'][:10]),  # First 10
                'Weekly_Tickers': ', '.join(entry['weekly_tickers'][:10])  # First 10
            })
        
        df = pd.DataFrame(df_data)
        excel_file = os.path.join(self.results_dir, f'momentum_historical_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df.to_excel(excel_file, index=False)
        
        self.logger.info(f"Results saved to {json_file} and {excel_file}")
    
    def generate_plots(self, historical_data):
        """Generate trend plots for daily and weekly momentum"""
        # Prepare data
        dates = [entry['date'] for entry in historical_data]
        daily_counts = [entry['daily_count'] for entry in historical_data]
        weekly_counts = [entry['weekly_count'] for entry in historical_data]
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Daily momentum plot
        ax1.plot(dates, daily_counts, 'b-', linewidth=2, label='Daily Momentum')
        ax1.fill_between(dates, daily_counts, alpha=0.3)
        ax1.set_title('Daily Momentum Trend (Past 2 Months)', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Tickers')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Add moving average
        if len(daily_counts) > 7:
            ma7 = pd.Series(daily_counts).rolling(window=7).mean()
            ax1.plot(dates, ma7, 'r--', linewidth=1, label='7-day MA')
            ax1.legend()
        
        # Weekly momentum plot
        ax2.plot(dates, weekly_counts, 'g-', linewidth=2, label='Weekly Momentum')
        ax2.fill_between(dates, weekly_counts, alpha=0.3)
        ax2.set_title('Weekly Momentum Trend (Past 2 Months)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Number of Tickers')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Add moving average
        if len(weekly_counts) > 7:
            ma7 = pd.Series(weekly_counts).rolling(window=7).mean()
            ax2.plot(dates, ma7, 'r--', linewidth=1, label='7-day MA')
            ax2.legend()
        
        # Rotate x-axis labels
        for ax in [ax1, ax2]:
            ax.tick_params(axis='x', rotation=45)
            # Show every nth date label to avoid crowding
            n = max(1, len(dates) // 20)
            ax.set_xticks(dates[::n])
        
        # Add statistics
        daily_avg = np.mean(daily_counts)
        weekly_avg = np.mean(weekly_counts)
        
        # Add text box with statistics
        stats_text = f'Daily Avg: {daily_avg:.1f}\nWeekly Avg: {weekly_avg:.1f}'
        fig.text(0.02, 0.98, stats_text, transform=fig.transFigure, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        # Save plot
        plot_file = os.path.join(self.results_dir, f'momentum_trend_{datetime.now().strftime("%Y%m%d")}.png')
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        self.logger.info(f"Plot saved to {plot_file}")
        
        # Also save as PDF
        pdf_file = os.path.join(self.results_dir, f'momentum_trend_{datetime.now().strftime("%Y%m%d")}.pdf')
        plt.savefig(pdf_file, bbox_inches='tight')
        
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
        ax1.plot(dates, daily_counts, 'b-', linewidth=2, label='Daily')
        ax1.plot(dates, weekly_counts, 'g-', linewidth=2, label='Weekly')
        ax1.set_title('Daily vs Weekly Momentum Comparison', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Tickers')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Distribution histogram
        ax2.hist(daily_counts, bins=20, alpha=0.5, label='Daily', color='blue')
        ax2.hist(weekly_counts, bins=20, alpha=0.5, label='Weekly', color='green')
        ax2.set_title('Distribution of Momentum Counts', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Number of Tickers')
        ax2.set_ylabel('Frequency')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Day of week analysis
        dow_data = {'Mon': [], 'Tue': [], 'Wed': [], 'Thu': [], 'Fri': []}
        dow_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri'}
        
        for i, entry in enumerate(historical_data):
            dow = entry['date'].weekday()
            if dow < 5:  # Weekday
                dow_data[dow_map[dow]].append(daily_counts[i])
        
        # Box plot for day of week
        ax3.boxplot([dow_data[day] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']], 
                   labels=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
        ax3.set_title('Daily Momentum by Day of Week', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Day of Week')
        ax3.set_ylabel('Number of Tickers')
        ax3.grid(True, alpha=0.3)
        
        # 4. Correlation scatter plot
        ax4.scatter(daily_counts, weekly_counts, alpha=0.6)
        ax4.set_title('Daily vs Weekly Correlation', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Daily Count')
        ax4.set_ylabel('Weekly Count')
        ax4.grid(True, alpha=0.3)
        
        # Add correlation coefficient
        if len(daily_counts) > 1:
            corr = np.corrcoef(daily_counts, weekly_counts)[0, 1]
            ax4.text(0.05, 0.95, f'Correlation: {corr:.3f}', 
                    transform=ax4.transAxes, fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        # Save analysis plot
        analysis_file = os.path.join(self.results_dir, 
                                   f'momentum_analysis_{datetime.now().strftime("%Y%m%d")}.png')
        plt.savefig(analysis_file, dpi=150, bbox_inches='tight')
        self.logger.info(f"Analysis plot saved to {analysis_file}")
        
        plt.close()

def main():
    """Main function"""
    print("Starting Historical Momentum Analysis...")
    print("This will analyze momentum data for the past 2 months")
    print("Expected runtime: 15-30 minutes depending on rate limits")
    print("-" * 50)
    
    analyzer = HistoricalMomentumAnalyzer()
    
    # Run for past 60 days (approximately 2 months)
    historical_data = analyzer.run_historical_scan(days_back=60)
    
    print("\nAnalysis complete!")
    print(f"Processed {len(historical_data)} days of data")
    print(f"Results saved in: {analyzer.results_dir}")

if __name__ == "__main__":
    main()