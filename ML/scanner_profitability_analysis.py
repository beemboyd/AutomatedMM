#!/usr/bin/env python
"""
Scanner File Profitability Analysis
====================================
This script analyzes the profitability of tickers from Daily/scanner_files by date.
It tracks performance over different holding periods and provides comprehensive statistics.

Features:
- Analyzes all scanner files chronologically
- Tracks 1-day, 3-day, 5-day, and 10-day performance
- Calculates win/loss ratios and average returns
- Generates detailed reports and visualizations
- Exports results to Excel and HTML

Author: Claude Code Assistant
Created: 2025-05-24
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
from pathlib import Path
import logging
import glob
import re
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import timedelta

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'scanner_profitability_analysis.log'))
    ]
)
logger = logging.getLogger(__name__)

class ScannerProfitabilityAnalyzer:
    """Analyze profitability of tickers from scanner files"""
    
    def __init__(self):
        """Initialize the analyzer"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.join(os.path.dirname(self.script_dir), "Daily")
        self.scanner_files_dir = os.path.join(self.daily_dir, "scanner_files")
        self.data_dir = os.path.join(self.script_dir, "data", "ohlc_data", "daily")
        self.results_dir = os.path.join(self.script_dir, "results")
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Performance tracking periods
        self.holding_periods = [1, 3, 5, 10]  # days
        
        logger.info(f"Initialized Scanner Profitability Analyzer")
        logger.info(f"Scanner files directory: {self.scanner_files_dir}")
        logger.info(f"OHLC data directory: {self.data_dir}")
    
    def get_scanner_files(self) -> List[Tuple[str, datetime.datetime]]:
        """Get all scanner files sorted by date"""
        try:
            files = glob.glob(os.path.join(self.scanner_files_dir, "Custom_Scanner_*.xlsx"))
            
            file_dates = []
            for file_path in files:
                filename = os.path.basename(file_path)
                # Extract date from filename: Custom_Scanner_DD_MM_YYYY_HH_MM.xlsx
                date_match = re.search(r'Custom_Scanner_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx', filename)
                if date_match:
                    day, month, year, hour, minute = date_match.groups()
                    scan_date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                    file_dates.append((file_path, scan_date))
            
            # Sort by date
            file_dates.sort(key=lambda x: x[1])
            
            logger.info(f"Found {len(file_dates)} scanner files")
            return file_dates
            
        except Exception as e:
            logger.error(f"Error getting scanner files: {e}")
            return []
    
    def read_scanner_file(self, file_path: str) -> List[str]:
        """Read tickers from a scanner file"""
        try:
            # Try to read the Excel file
            df = pd.read_excel(file_path)
            
            # Look for ticker column (common names)
            ticker_columns = ['Ticker', 'Symbol', 'Stock', 'Name', 'tradingsymbol']
            ticker_column = None
            
            for col in ticker_columns:
                if col in df.columns:
                    ticker_column = col
                    break
            
            if ticker_column is None:
                # If no standard column found, use the first column
                ticker_column = df.columns[0]
                logger.warning(f"No standard ticker column found in {os.path.basename(file_path)}, using {ticker_column}")
            
            # Extract tickers and clean them
            tickers = df[ticker_column].dropna().astype(str).tolist()
            tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
            
            logger.info(f"Read {len(tickers)} tickers from {os.path.basename(file_path)}")
            return tickers
            
        except Exception as e:
            logger.error(f"Error reading scanner file {file_path}: {e}")
            return []
    
    def get_ticker_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """Get OHLC data for a ticker"""
        try:
            csv_file = os.path.join(self.data_dir, f"{ticker}_day.csv")
            
            if not os.path.exists(csv_file):
                logger.warning(f"No data file found for {ticker}")
                return None
            
            df = pd.read_csv(csv_file)
            
            # Standardize column names
            columns_map = {
                'date': 'Date',
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
            
            df = df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns})
            
            # Ensure Date is datetime
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            df = df.reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting data for {ticker}: {e}")
            return None
    
    def calculate_performance(self, ticker_data: pd.DataFrame, entry_date: datetime.datetime, 
                            holding_periods: List[int]) -> Dict[int, float]:
        """Calculate performance for different holding periods"""
        try:
            # Find the entry date or the next available trading day
            entry_date_only = entry_date.date()
            
            # Find the closest trading day on or after entry date
            entry_row = None
            for idx, row in ticker_data.iterrows():
                if row['Date'].date() >= entry_date_only:
                    entry_row = idx
                    break
            
            if entry_row is None:
                return {}
            
            entry_price = ticker_data.iloc[entry_row]['Close']
            performances = {}
            
            for period in holding_periods:
                exit_row = entry_row + period
                
                if exit_row < len(ticker_data):
                    exit_price = ticker_data.iloc[exit_row]['Close']
                    performance = ((exit_price - entry_price) / entry_price) * 100
                    performances[period] = performance
                else:
                    # If we don't have enough future data, skip this period
                    performances[period] = None
            
            return performances
            
        except Exception as e:
            logger.error(f"Error calculating performance: {e}")
            return {}
    
    def analyze_scanner_file(self, file_path: str, scan_date: datetime.datetime) -> Dict:
        """Analyze a single scanner file"""
        try:
            tickers = self.read_scanner_file(file_path)
            
            if not tickers:
                return {
                    'file': os.path.basename(file_path),
                    'scan_date': scan_date,
                    'total_tickers': 0,
                    'analyzed_tickers': 0,
                    'results': []
                }
            
            results = []
            analyzed_count = 0
            
            for ticker in tickers:
                ticker_data = self.get_ticker_data(ticker)
                
                if ticker_data is not None:
                    performances = self.calculate_performance(ticker_data, scan_date, self.holding_periods)
                    
                    if performances:
                        result = {
                            'ticker': ticker,
                            'scan_date': scan_date,
                            **{f'performance_{period}d': performances.get(period) for period in self.holding_periods}
                        }
                        results.append(result)
                        analyzed_count += 1
            
            analysis = {
                'file': os.path.basename(file_path),
                'scan_date': scan_date,
                'total_tickers': len(tickers),
                'analyzed_tickers': analyzed_count,
                'results': results
            }
            
            logger.info(f"Analyzed {analyzed_count}/{len(tickers)} tickers from {os.path.basename(file_path)}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing scanner file {file_path}: {e}")
            return {}
    
    def calculate_statistics(self, all_results: List[Dict]) -> Dict:
        """Calculate comprehensive statistics"""
        try:
            if not all_results:
                return {}
            
            # Flatten all results
            all_performances = []
            for file_result in all_results:
                all_performances.extend(file_result.get('results', []))
            
            if not all_performances:
                return {}
            
            df = pd.DataFrame(all_performances)
            
            stats = {
                'overall': {
                    'total_scans': len(all_results),
                    'total_tickers_scanned': sum([r.get('total_tickers', 0) for r in all_results]),
                    'total_tickers_analyzed': sum([r.get('analyzed_tickers', 0) for r in all_results]),
                    'date_range': {
                        'start': min([r.get('scan_date') for r in all_results if r.get('scan_date')]),
                        'end': max([r.get('scan_date') for r in all_results if r.get('scan_date')])
                    }
                }
            }
            
            # Calculate statistics for each holding period
            for period in self.holding_periods:
                col = f'performance_{period}d'
                if col in df.columns:
                    valid_data = df[col].dropna()
                    
                    if len(valid_data) > 0:
                        positive_returns = valid_data[valid_data > 0]
                        negative_returns = valid_data[valid_data <= 0]
                        
                        period_stats = {
                            'total_trades': len(valid_data),
                            'profitable_trades': len(positive_returns),
                            'unprofitable_trades': len(negative_returns),
                            'win_rate': (len(positive_returns) / len(valid_data)) * 100 if len(valid_data) > 0 else 0,
                            'average_return': valid_data.mean(),
                            'median_return': valid_data.median(),
                            'std_return': valid_data.std(),
                            'max_return': valid_data.max(),
                            'min_return': valid_data.min(),
                            'average_winning_return': positive_returns.mean() if len(positive_returns) > 0 else 0,
                            'average_losing_return': negative_returns.mean() if len(negative_returns) > 0 else 0,
                            'profit_factor': abs(positive_returns.sum() / negative_returns.sum()) if negative_returns.sum() != 0 else float('inf') if positive_returns.sum() > 0 else 0
                        }
                        
                        stats[f'{period}_day'] = period_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {}
    
    def create_visualizations(self, all_results: List[Dict], stats: Dict) -> List[str]:
        """Create visualization plots"""
        try:
            plot_files = []
            
            # Flatten all results
            all_performances = []
            for file_result in all_results:
                all_performances.extend(file_result.get('results', []))
            
            if not all_performances:
                return plot_files
            
            df = pd.DataFrame(all_performances)
            
            # Set style
            plt.style.use('seaborn-v0_8')
            fig_size = (15, 10)
            
            # 1. Performance Distribution by Holding Period
            fig, axes = plt.subplots(2, 2, figsize=fig_size)
            fig.suptitle('Performance Distribution by Holding Period', fontsize=16, fontweight='bold')
            
            for i, period in enumerate(self.holding_periods):
                row, col = i // 2, i % 2
                col_name = f'performance_{period}d'
                
                if col_name in df.columns:
                    valid_data = df[col_name].dropna()
                    
                    if len(valid_data) > 0:
                        axes[row, col].hist(valid_data, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
                        axes[row, col].axvline(valid_data.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {valid_data.mean():.2f}%')
                        axes[row, col].axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
                        axes[row, col].set_title(f'{period}-Day Performance')
                        axes[row, col].set_xlabel('Return (%)')
                        axes[row, col].set_ylabel('Frequency')
                        axes[row, col].legend()
                        axes[row, col].grid(True, alpha=0.3)
            
            plt.tight_layout()
            plot_file = os.path.join(self.results_dir, 'performance_distribution.png')
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(plot_file)
            
            # 2. Win Rate Comparison
            fig, ax = plt.subplots(figsize=(10, 6))
            periods = []
            win_rates = []
            
            for period in self.holding_periods:
                if f'{period}_day' in stats:
                    periods.append(f'{period}D')
                    win_rates.append(stats[f'{period}_day']['win_rate'])
            
            bars = ax.bar(periods, win_rates, color=['green' if rate >= 50 else 'red' for rate in win_rates], alpha=0.7)
            ax.set_title('Win Rate by Holding Period', fontsize=14, fontweight='bold')
            ax.set_ylabel('Win Rate (%)')
            ax.set_ylim(0, 100)
            ax.axhline(50, color='black', linestyle='--', alpha=0.5, label='Break-even (50%)')
            
            # Add value labels on bars
            for bar, rate in zip(bars, win_rates):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plot_file = os.path.join(self.results_dir, 'win_rate_comparison.png')
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(plot_file)
            
            # 3. Average Returns Comparison
            fig, ax = plt.subplots(figsize=(10, 6))
            avg_returns = []
            
            for period in self.holding_periods:
                if f'{period}_day' in stats:
                    avg_returns.append(stats[f'{period}_day']['average_return'])
                else:
                    avg_returns.append(0)
            
            bars = ax.bar(periods, avg_returns, color=['green' if ret >= 0 else 'red' for ret in avg_returns], alpha=0.7)
            ax.set_title('Average Return by Holding Period', fontsize=14, fontweight='bold')
            ax.set_ylabel('Average Return (%)')
            ax.axhline(0, color='black', linestyle='-', alpha=0.5)
            
            # Add value labels on bars
            for bar, ret in zip(bars, avg_returns):
                height = bar.get_height()
                y_pos = height + 0.1 if height >= 0 else height - 0.3
                ax.text(bar.get_x() + bar.get_width()/2., y_pos,
                       f'{ret:.2f}%', ha='center', va='bottom' if height >= 0 else 'top', fontweight='bold')
            
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plot_file = os.path.join(self.results_dir, 'average_returns_comparison.png')
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(plot_file)
            
            # 4. Performance Over Time
            if len(all_results) > 1:
                fig, ax = plt.subplots(figsize=(15, 8))
                
                for period in self.holding_periods:
                    col_name = f'performance_{period}d'
                    daily_avg = []
                    dates = []
                    
                    for file_result in all_results:
                        if file_result.get('results'):
                            file_df = pd.DataFrame(file_result['results'])
                            if col_name in file_df.columns:
                                avg_performance = file_df[col_name].mean()
                                if not pd.isna(avg_performance):
                                    daily_avg.append(avg_performance)
                                    dates.append(file_result['scan_date'])
                    
                    if daily_avg:
                        ax.plot(dates, daily_avg, marker='o', label=f'{period}D Holding', linewidth=2, markersize=4)
                
                ax.set_title('Average Performance Over Time', fontsize=14, fontweight='bold')
                ax.set_xlabel('Scan Date')
                ax.set_ylabel('Average Return (%)')
                ax.axhline(0, color='black', linestyle='--', alpha=0.5)
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.tight_layout()
                plot_file = os.path.join(self.results_dir, 'performance_over_time.png')
                plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                plt.close()
                plot_files.append(plot_file)
            
            logger.info(f"Created {len(plot_files)} visualization plots")
            return plot_files
            
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")
            return []
    
    def export_to_excel(self, all_results: List[Dict], stats: Dict) -> str:
        """Export results to Excel"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(self.results_dir, f"scanner_profitability_analysis_{timestamp}.xlsx")
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Summary statistics
                summary_data = []
                for period in self.holding_periods:
                    if f'{period}_day' in stats:
                        period_stats = stats[f'{period}_day']
                        summary_data.append({
                            'Holding_Period': f'{period} Days',
                            'Total_Trades': period_stats['total_trades'],
                            'Profitable_Trades': period_stats['profitable_trades'],
                            'Unprofitable_Trades': period_stats['unprofitable_trades'],
                            'Win_Rate_%': round(period_stats['win_rate'], 2),
                            'Average_Return_%': round(period_stats['average_return'], 2),
                            'Median_Return_%': round(period_stats['median_return'], 2),
                            'Max_Return_%': round(period_stats['max_return'], 2),
                            'Min_Return_%': round(period_stats['min_return'], 2),
                            'Avg_Winning_Return_%': round(period_stats['average_winning_return'], 2),
                            'Avg_Losing_Return_%': round(period_stats['average_losing_return'], 2),
                            'Profit_Factor': round(period_stats['profit_factor'], 2)
                        })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary_Statistics', index=False)
                
                # Individual file results
                file_summary = []
                for file_result in all_results:
                    file_summary.append({
                        'File': file_result['file'],
                        'Scan_Date': file_result['scan_date'].strftime('%Y-%m-%d %H:%M'),
                        'Total_Tickers': file_result['total_tickers'],
                        'Analyzed_Tickers': file_result['analyzed_tickers'],
                        'Analysis_Rate_%': round((file_result['analyzed_tickers'] / file_result['total_tickers'] * 100) if file_result['total_tickers'] > 0 else 0, 2)
                    })
                
                if file_summary:
                    file_df = pd.DataFrame(file_summary)
                    file_df.to_excel(writer, sheet_name='File_Summary', index=False)
                
                # All individual ticker results
                all_ticker_results = []
                for file_result in all_results:
                    for result in file_result.get('results', []):
                        ticker_result = {
                            'File': file_result['file'],
                            'Scan_Date': file_result['scan_date'].strftime('%Y-%m-%d %H:%M'),
                            'Ticker': result['ticker']
                        }
                        
                        for period in self.holding_periods:
                            col_name = f'performance_{period}d'
                            if col_name in result:
                                ticker_result[f'{period}D_Return_%'] = round(result[col_name], 2) if result[col_name] is not None else None
                        
                        all_ticker_results.append(ticker_result)
                
                if all_ticker_results:
                    ticker_df = pd.DataFrame(all_ticker_results)
                    ticker_df.to_excel(writer, sheet_name='All_Ticker_Results', index=False)
            
            logger.info(f"Exported results to Excel: {excel_file}")
            return excel_file
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return ""
    
    def generate_html_report(self, all_results: List[Dict], stats: Dict, plot_files: List[str], excel_file: str) -> str:
        """Generate HTML report"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = os.path.join(self.results_dir, f"scanner_profitability_report_{timestamp}.html")
            
            # Calculate overall statistics
            overall = stats.get('overall', {})
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Scanner Profitability Analysis Report</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f9f9f9;
                    }}
                    h1, h2, h3 {{
                        color: #2c3e50;
                    }}
                    h1 {{
                        border-bottom: 2px solid #3498db;
                        padding-bottom: 10px;
                    }}
                    .summary-stats {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin: 20px 0;
                    }}
                    .stat-card {{
                        background-color: white;
                        border-radius: 8px;
                        padding: 20px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        border-left: 5px solid #3498db;
                    }}
                    .stat-value {{
                        font-size: 2em;
                        font-weight: bold;
                        color: #3498db;
                    }}
                    .stat-label {{
                        color: #7f8c8d;
                        font-size: 0.9em;
                        margin-top: 5px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin: 20px 0;
                        background-color: white;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }}
                    th, td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #3498db;
                        color: white;
                        font-weight: bold;
                    }}
                    .positive {{
                        color: #27ae60;
                        font-weight: bold;
                    }}
                    .negative {{
                        color: #e74c3c;
                        font-weight: bold;
                    }}
                    .chart-container {{
                        text-align: center;
                        margin: 30px 0;
                        background-color: white;
                        border-radius: 8px;
                        padding: 20px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }}
                    .chart-container img {{
                        max-width: 100%;
                        height: auto;
                        border-radius: 4px;
                    }}
                </style>
            </head>
            <body>
                <h1>📊 Scanner Profitability Analysis Report</h1>
                <p><strong>Generated:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <h2>📈 Overall Summary</h2>
                <div class="summary-stats">
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('total_scans', 0)}</div>
                        <div class="stat-label">Total Scanner Files Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('total_tickers_analyzed', 0):,}</div>
                        <div class="stat-label">Total Tickers Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('date_range', {}).get('start', 'N/A')}</div>
                        <div class="stat-label">Analysis Start Date</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('date_range', {}).get('end', 'N/A')}</div>
                        <div class="stat-label">Analysis End Date</div>
                    </div>
                </div>
            """
            
            # Performance statistics table
            html_content += """
                <h2>🎯 Performance Statistics by Holding Period</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Holding Period</th>
                            <th>Total Trades</th>
                            <th>Win Rate (%)</th>
                            <th>Avg Return (%)</th>
                            <th>Avg Win (%)</th>
                            <th>Avg Loss (%)</th>
                            <th>Max Return (%)</th>
                            <th>Min Return (%)</th>
                            <th>Profit Factor</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for period in self.holding_periods:
                if f'{period}_day' in stats:
                    period_stats = stats[f'{period}_day']
                    win_rate = period_stats['win_rate']
                    avg_return = period_stats['average_return']
                    
                    html_content += f"""
                        <tr>
                            <td>{period} Day{'s' if period > 1 else ''}</td>
                            <td>{period_stats['total_trades']:,}</td>
                            <td class="{'positive' if win_rate >= 50 else 'negative'}">{win_rate:.1f}%</td>
                            <td class="{'positive' if avg_return >= 0 else 'negative'}">{avg_return:.2f}%</td>
                            <td class="positive">{period_stats['average_winning_return']:.2f}%</td>
                            <td class="negative">{period_stats['average_losing_return']:.2f}%</td>
                            <td class="positive">{period_stats['max_return']:.2f}%</td>
                            <td class="negative">{period_stats['min_return']:.2f}%</td>
                            <td>{period_stats['profit_factor']:.2f}</td>
                        </tr>
                    """
            
            html_content += """
                    </tbody>
                </table>
            """
            
            # Add charts
            if plot_files:
                html_content += "<h2>📊 Performance Visualizations</h2>"
                for plot_file in plot_files:
                    if os.path.exists(plot_file):
                        plot_name = os.path.basename(plot_file).replace('_', ' ').replace('.png', '').title()
                        html_content += f"""
                        <div class="chart-container">
                            <h3>{plot_name}</h3>
                            <img src="{os.path.basename(plot_file)}" alt="{plot_name}">
                        </div>
                        """
            
            # Add download links
            html_content += f"""
                <h2>📁 Download Results</h2>
                <p><a href="{os.path.basename(excel_file)}" target="_blank">Download Excel Report</a></p>
                
                <div style="margin-top: 50px; text-align: center; color: #7f8c8d; font-size: 0.9em;">
                    <p>Report generated by Scanner Profitability Analyzer</p>
                    <p>Analysis covers {overall.get('total_scans', 0)} scanner files from {overall.get('date_range', {}).get('start', 'N/A')} to {overall.get('date_range', {}).get('end', 'N/A')}</p>
                </div>
            </body>
            </html>
            """
            
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            logger.info(f"Generated HTML report: {html_file}")
            return html_file
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return ""
    
    def run_analysis(self) -> Dict:
        """Run the complete profitability analysis"""
        try:
            logger.info("Starting Scanner Profitability Analysis")
            
            # Get all scanner files
            scanner_files = self.get_scanner_files()
            
            if not scanner_files:
                logger.error("No scanner files found")
                return {}
            
            # Analyze each file
            all_results = []
            for file_path, scan_date in scanner_files:
                logger.info(f"Analyzing {os.path.basename(file_path)} - {scan_date.strftime('%Y-%m-%d %H:%M')}")
                result = self.analyze_scanner_file(file_path, scan_date)
                if result:
                    all_results.append(result)
            
            if not all_results:
                logger.error("No successful analyses")
                return {}
            
            # Calculate statistics
            logger.info("Calculating comprehensive statistics")
            stats = self.calculate_statistics(all_results)
            
            # Create visualizations
            logger.info("Creating visualizations")
            plot_files = self.create_visualizations(all_results, stats)
            
            # Export to Excel
            logger.info("Exporting to Excel")
            excel_file = self.export_to_excel(all_results, stats)
            
            # Generate HTML report
            logger.info("Generating HTML report")
            html_file = self.generate_html_report(all_results, stats, plot_files, excel_file)
            
            # Print summary
            self.print_summary(stats, excel_file, html_file)
            
            logger.info("Analysis completed successfully")
            
            return {
                'stats': stats,
                'excel_file': excel_file,
                'html_file': html_file,
                'plot_files': plot_files,
                'total_files_analyzed': len(all_results)
            }
            
        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            return {}
    
    def print_summary(self, stats: Dict, excel_file: str, html_file: str):
        """Print analysis summary to console"""
        print("\\n" + "="*80)
        print("SCANNER PROFITABILITY ANALYSIS SUMMARY")
        print("="*80)
        
        overall = stats.get('overall', {})
        print(f"Analysis Period: {overall.get('date_range', {}).get('start', 'N/A')} to {overall.get('date_range', {}).get('end', 'N/A')}")
        print(f"Total Scanner Files: {overall.get('total_scans', 0)}")
        print(f"Total Tickers Analyzed: {overall.get('total_tickers_analyzed', 0):,}")
        print("-"*80)
        
        print("PERFORMANCE BY HOLDING PERIOD:")
        for period in self.holding_periods:
            if f'{period}_day' in stats:
                period_stats = stats[f'{period}_day']
                print(f"\\n{period} Day{'s' if period > 1 else ''} Holding:")
                print(f"  Win Rate: {period_stats['win_rate']:.1f}% ({period_stats['profitable_trades']}/{period_stats['total_trades']} trades)")
                print(f"  Average Return: {period_stats['average_return']:.2f}%")
                print(f"  Average Win: {period_stats['average_winning_return']:.2f}%")
                print(f"  Average Loss: {period_stats['average_losing_return']:.2f}%")
                print(f"  Max Return: {period_stats['max_return']:.2f}%")
                print(f"  Min Return: {period_stats['min_return']:.2f}%")
                print(f"  Profit Factor: {period_stats['profit_factor']:.2f}")
        
        print("\\n" + "-"*80)
        print("OUTPUT FILES:")
        print(f"Excel Report: {os.path.basename(excel_file)}")
        print(f"HTML Report: {os.path.basename(html_file)}")
        print(f"Results Directory: {self.results_dir}")
        print("="*80)


def main():
    """Main function"""
    try:
        # Create logs directory
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
        
        analyzer = ScannerProfitabilityAnalyzer()
        results = analyzer.run_analysis()
        
        if results:
            print(f"\\nAnalysis completed successfully!")
            print(f"Results saved to: {analyzer.results_dir}")
        else:
            print("Analysis failed. Check logs for details.")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())