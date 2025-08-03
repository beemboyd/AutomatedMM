#!/usr/bin/env python3
"""
Brooks Higher Probability Reversal - Ticker Frequency Analysis

This script measures the average number of tickers that appeared as filtered tickers 
using the Al Brooks Higher Probability Reversal strategy for the past 12 weeks.

Author: AI Assistant
Date: 2025-05-24
"""

import os
import sys
import glob
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BrooksTickerFrequencyAnalyzer:
    def __init__(self):
        """Initialize the Brooks Ticker Frequency Analyzer"""
        # Set up paths
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.script_dir)
        self.results_dir = os.path.join(self.project_root, "Daily", "results")
        self.logs_dir = os.path.join(self.project_root, "Daily", "logs")
        
        # Patterns for all Brooks-related files
        self.brooks_patterns = [
            "Brooks_Higher_Probability_LONG_Reversal_*.xlsx",
            "Brooks_Filter_*.xlsx",
            "Brooks_vWAP_SMA20_H2_*.xlsx"
        ]
        self.log_file = os.path.join(self.logs_dir, "al_brooks_higher_probability.log")
        
        logger.info("Initialized Brooks Ticker Frequency Analyzer")
        logger.info(f"Results directory: {self.results_dir}")
        logger.info(f"Log file: {self.log_file}")
    
    def parse_filename_date(self, filename):
        """Extract date and time from Brooks strategy filename"""
        # Multiple patterns for different Brooks file types
        patterns = [
            # Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
            r'Brooks_Higher_Probability_LONG_Reversal_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx',
            # Brooks_Filter_DD_MM_YYYY_HH_MM.xlsx
            r'Brooks_Filter_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx',
            # Brooks_vWAP_SMA20_H2_DD_MM_YYYY_HH_MM.xlsx
            r'Brooks_vWAP_SMA20_H2_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx'
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                day, month, year, hour, minute = match.groups()
                try:
                    return datetime(int(year), int(month), int(day), int(hour), int(minute))
                except ValueError as e:
                    logger.warning(f"Invalid date in filename {filename}: {e}")
                    continue

        logger.warning(f"Could not parse date from filename: {filename}")
        return None
    
    def get_brooks_files_in_period(self, start_date, end_date):
        """Get all Brooks strategy files within the specified period"""
        all_files = []
        for pattern in self.brooks_patterns:
            pattern_path = os.path.join(self.results_dir, pattern)
            all_files.extend(glob.glob(pattern_path))
        
        period_files = []
        for file_path in all_files:
            filename = os.path.basename(file_path)
            file_date = self.parse_filename_date(filename)

            # Determine strategy type
            strategy_type = "Unknown"
            if "Higher_Probability_LONG_Reversal" in filename:
                strategy_type = "Higher_Probability_LONG"
            elif "Brooks_Filter" in filename:
                strategy_type = "Brooks_Filter"
            elif "vWAP_SMA20_H2" in filename:
                strategy_type = "vWAP_SMA20_H2"

            if file_date and start_date <= file_date <= end_date:
                period_files.append({
                    'filename': filename,
                    'filepath': file_path,
                    'date': file_date,
                    'strategy_type': strategy_type,
                    'week_start': file_date - timedelta(days=file_date.weekday())  # Monday of that week
                })
        
        return sorted(period_files, key=lambda x: x['date'])
    
    def analyze_file(self, file_path):
        """Analyze a single Brooks strategy file and return ticker count"""
        try:
            df = pd.read_excel(file_path)
            ticker_count = len(df)
            
            # Extract ticker symbols if available
            tickers = []
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].tolist()
            elif 'Symbol' in df.columns:
                tickers = df['Symbol'].tolist()
            elif len(df.columns) > 0:
                # Assume first column contains tickers
                tickers = df.iloc[:, 0].tolist()
            
            return {
                'ticker_count': ticker_count,
                'tickers': tickers
            }
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {
                'ticker_count': 0,
                'tickers': []
            }
    
    def analyze_log_file(self, start_date, end_date):
        """Analyze log file for additional insights"""
        log_data = []
        
        if not os.path.exists(self.log_file):
            logger.warning(f"Log file not found: {self.log_file}")
            return log_data
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    # Look for lines that indicate filtering results
                    if 'tickers found' in line.lower() or 'filtered' in line.lower():
                        # Try to extract timestamp and ticker count
                        parts = line.strip().split(' - ')
                        if len(parts) >= 3:
                            timestamp_str = parts[0]
                            try:
                                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                                if start_date <= timestamp <= end_date:
                                    log_data.append({
                                        'timestamp': timestamp,
                                        'message': ' - '.join(parts[2:])
                                    })
                            except ValueError:
                                continue
        
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        return log_data
    
    def generate_weekly_summary(self, files_data):
        """Generate weekly summary of ticker counts"""
        weekly_data = {}

        for file_info in files_data:
            week_start = file_info['week_start']
            week_key = week_start.strftime('%Y-%m-%d')  # Monday date as key

            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    'week_start': week_start,
                    'week_end': week_start + timedelta(days=4),  # Friday
                    'files': [],
                    'total_runs': 0,
                    'total_tickers': 0,
                    'daily_counts': [],
                    'strategy_breakdown': {}
                }

            # Track strategy type breakdown
            strategy_type = file_info.get('strategy_type', 'Unknown')
            if strategy_type not in weekly_data[week_key]['strategy_breakdown']:
                weekly_data[week_key]['strategy_breakdown'][strategy_type] = {
                    'runs': 0,
                    'total_tickers': 0
                }

            ticker_count = file_info.get('analysis', {}).get('ticker_count', 0)

            weekly_data[week_key]['files'].append(file_info)
            weekly_data[week_key]['total_runs'] += 1
            weekly_data[week_key]['total_tickers'] += ticker_count
            weekly_data[week_key]['daily_counts'].append(ticker_count)

            weekly_data[week_key]['strategy_breakdown'][strategy_type]['runs'] += 1
            weekly_data[week_key]['strategy_breakdown'][strategy_type]['total_tickers'] += ticker_count
        
        # Calculate averages
        for week_key in weekly_data:
            week_data = weekly_data[week_key]
            if week_data['total_runs'] > 0:
                week_data['avg_tickers_per_run'] = week_data['total_tickers'] / week_data['total_runs']
            else:
                week_data['avg_tickers_per_run'] = 0
            
            if week_data['daily_counts']:
                week_data['min_tickers'] = min(week_data['daily_counts'])
                week_data['max_tickers'] = max(week_data['daily_counts'])
                week_data['std_tickers'] = np.std(week_data['daily_counts']) if len(week_data['daily_counts']) > 1 else 0
            else:
                week_data['min_tickers'] = 0
                week_data['max_tickers'] = 0
                week_data['std_tickers'] = 0
        
        return weekly_data
    
    def analyze_12_weeks(self):
        """Analyze Brooks strategy ticker frequency for past 12 weeks"""
        # Calculate date range (past 12 weeks)
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=12)
        
        logger.info(f"Analyzing Brooks Higher Probability strategy from {start_date.date()} to {end_date.date()}")
        
        # Get all Brooks files in the period
        files_data = self.get_brooks_files_in_period(start_date, end_date)
        logger.info(f"Found {len(files_data)} Brooks strategy files in the period")
        
        # Analyze each file
        for file_info in files_data:
            logger.info(f"Analyzing {file_info['filename']} - {file_info['date']}")
            analysis = self.analyze_file(file_info['filepath'])
            file_info['analysis'] = analysis
        
        # Generate weekly summary
        weekly_summary = self.generate_weekly_summary(files_data)
        
        # Analyze logs
        log_data = self.analyze_log_file(start_date, end_date)
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_weeks': 12
            },
            'files_analyzed': len(files_data),
            'weekly_summary': weekly_summary,
            'detailed_files': files_data,
            'log_insights': log_data
        }
    
    def print_weekly_table(self, analysis_results):
        """Print a formatted table of weekly results"""
        weekly_summary = analysis_results['weekly_summary']
        
        print("\n" + "="*80)
        print("BROOKS STRATEGY - 12 WEEK TICKER FREQUENCY ANALYSIS")
        print("="*80)
        
        print(f"Analysis Period: {analysis_results['period']['start_date'].date()} to {analysis_results['period']['end_date'].date()}")
        print(f"Total Files Analyzed: {analysis_results['files_analyzed']}")

        # Determine actual data range
        if analysis_results['detailed_files']:
            earliest_date = min(f['date'] for f in analysis_results['detailed_files'])
            latest_date = max(f['date'] for f in analysis_results['detailed_files'])
            actual_weeks = (latest_date - earliest_date).days / 7
            print(f"Actual Data Range: {earliest_date.date()} to {latest_date.date()} ({actual_weeks:.1f} weeks)")

            # Strategy type breakdown
            strategy_counts = {}
            for file_info in analysis_results['detailed_files']:
                strategy_type = file_info.get('strategy_type', 'Unknown')
                strategy_counts[strategy_type] = strategy_counts.get(strategy_type, 0) + 1

            print(f"Strategy Types: {', '.join([f'{k}: {v} files' for k, v in strategy_counts.items()])}")

        print()
        
        # Sort weeks chronologically
        sorted_weeks = sorted(weekly_summary.items(), key=lambda x: x[1]['week_start'])
        
        if not sorted_weeks:
            print("No Brooks strategy files found in the 12-week period.")
            return
        
        # Print table header
        print(f"{'Week (Mon-Fri)':<20} {'Runs':<6} {'Avg Tickers':<12} {'Min':<6} {'Max':<6} {'Std Dev':<8} {'Strategy Breakdown':<30}")
        print("-" * 110)

        total_runs = 0
        total_avg_tickers = 0
        valid_weeks = 0

        for week_key, week_data in sorted_weeks:
            week_range = f"{week_data['week_start'].strftime('%m/%d')}-{week_data['week_end'].strftime('%m/%d')}"
            runs = week_data['total_runs']
            avg_tickers = week_data['avg_tickers_per_run']
            min_tickers = week_data['min_tickers']
            max_tickers = week_data['max_tickers']
            std_dev = week_data['std_tickers']

            # Strategy breakdown summary
            strategy_summary = []
            for strategy_type, strategy_data in week_data['strategy_breakdown'].items():
                avg_strategy_tickers = strategy_data['total_tickers'] / strategy_data['runs'] if strategy_data['runs'] > 0 else 0
                strategy_summary.append(f"{strategy_type}: {avg_strategy_tickers:.1f}")
            strategy_breakdown = ", ".join(strategy_summary[:2])  # Limit to first 2 for space

            print(f"{week_range:<20} {runs:<6} {avg_tickers:<12.1f} {min_tickers:<6} {max_tickers:<6} {std_dev:<8.1f} {strategy_breakdown:<30}")

            if runs > 0:
                total_runs += runs
                total_avg_tickers += avg_tickers
                valid_weeks += 1
        
        # Print summary statistics
        print("-" * 110)
        if valid_weeks > 0:
            overall_avg = total_avg_tickers / valid_weeks
            print(f"{'OVERALL AVERAGE':<20} {total_runs:<6} {overall_avg:<12.1f}")
        
        print()
        
        # Additional insights
        if analysis_results['log_insights']:
            print(f"Log File Insights: {len(analysis_results['log_insights'])} relevant log entries found")

        # Add note about data availability
        if analysis_results['detailed_files']:
            earliest_date = min(f['date'] for f in analysis_results['detailed_files'])
            latest_date = max(f['date'] for f in analysis_results['detailed_files'])
            actual_weeks = (latest_date - earliest_date).days / 7
            if actual_weeks < 4:
                print(f"\nNOTE: Brooks strategies appear to be relatively new with only {actual_weeks:.1f} weeks of data.")
                print("Historical analysis limited to available data from May 20-24, 2025.")

        print("="*110)
    
    def save_detailed_report(self, analysis_results, output_file=None):
        """Save detailed analysis to Excel file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.script_dir, f"brooks_ticker_frequency_analysis_{timestamp}.xlsx")
        
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Weekly Summary Sheet
                weekly_data = []
                for week_key, week_info in analysis_results['weekly_summary'].items():
                    weekly_data.append({
                        'Week_Start': week_info['week_start'].strftime('%Y-%m-%d'),
                        'Week_End': week_info['week_end'].strftime('%Y-%m-%d'),
                        'Total_Runs': week_info['total_runs'],
                        'Total_Tickers': week_info['total_tickers'],
                        'Avg_Tickers_Per_Run': round(week_info['avg_tickers_per_run'], 2),
                        'Min_Tickers': week_info['min_tickers'],
                        'Max_Tickers': week_info['max_tickers'],
                        'Std_Dev': round(week_info['std_tickers'], 2)
                    })
                
                weekly_df = pd.DataFrame(weekly_data)
                weekly_df.to_excel(writer, sheet_name='Weekly_Summary', index=False)
                
                # Detailed Files Sheet
                detailed_data = []
                for file_info in analysis_results['detailed_files']:
                    detailed_data.append({
                        'Filename': file_info['filename'],
                        'Date': file_info['date'].strftime('%Y-%m-%d %H:%M'),
                        'Week_Start': file_info['week_start'].strftime('%Y-%m-%d'),
                        'Ticker_Count': file_info['analysis']['ticker_count'],
                        'Tickers': ', '.join(file_info['analysis']['tickers'][:10]) + ('...' if len(file_info['analysis']['tickers']) > 10 else '')
                    })
                
                detailed_df = pd.DataFrame(detailed_data)
                detailed_df.to_excel(writer, sheet_name='Detailed_Files', index=False)
                
                # Log Insights Sheet (if available)
                if analysis_results['log_insights']:
                    log_data = []
                    for log_entry in analysis_results['log_insights']:
                        log_data.append({
                            'Timestamp': log_entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                            'Message': log_entry['message']
                        })
                    
                    log_df = pd.DataFrame(log_data)
                    log_df.to_excel(writer, sheet_name='Log_Insights', index=False)
            
            logger.info(f"Detailed report saved to: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error saving detailed report: {e}")
            return None

def main():
    """Main function to run the Brooks ticker frequency analysis"""
    try:
        # Initialize analyzer
        analyzer = BrooksTickerFrequencyAnalyzer()
        
        # Run 12-week analysis
        logger.info("Starting 12-week Brooks ticker frequency analysis...")
        results = analyzer.analyze_12_weeks()
        
        # Print results table
        analyzer.print_weekly_table(results)
        
        # Save detailed report
        report_file = analyzer.save_detailed_report(results)
        if report_file:
            print(f"\nDetailed report saved to: {report_file}")
        
        logger.info("Brooks ticker frequency analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error in Brooks ticker frequency analysis: {e}")
        raise

if __name__ == "__main__":
    main()