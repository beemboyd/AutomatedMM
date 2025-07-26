#!/usr/bin/env python
"""
Long Reversal 4-Week Performance Analyzer
Analyzes the performance of Long Reversal Daily signals over the past 4 weeks
and correlates with market regime predictions
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import glob
import configparser
from kiteconnect import KiteConnect
import logging
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_config
from user_aware_data_handler import UserAwareDataHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LongReversalPerformanceAnalyzer:
    def __init__(self, weeks_to_analyze=4, capital_per_position=500000, user='Sai'):
        """
        Initialize the analyzer
        
        Args:
            weeks_to_analyze: Number of weeks to analyze (default: 4)
            capital_per_position: Capital allocated per position (default: 500000)
            user: User name for API credentials (default: 'Sai')
        """
        self.weeks_to_analyze = weeks_to_analyze
        self.capital_per_position = capital_per_position
        self.user = user
        
        # Initialize Kite connection with user-specific credentials
        self.config = get_config()
        credential_section = f'API_CREDENTIALS_{user}'
        
        # Check if user credentials exist
        if not self.config.config.has_section(credential_section):
            raise ValueError(f"No credentials found for user {user}")
            
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Data handler for historical data with user-specific credentials
        self.data_handler = UserAwareDataHandler(self.api_key, self.access_token)
        
        # Paths
        self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
        self.regime_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis'
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
    def find_scan_files(self, start_date, end_date):
        """Find all Long Reversal scan files within date range"""
        scan_files = []
        pattern = os.path.join(self.results_dir, 'Long_Reversal_Daily_*.xlsx')
        
        # Ensure start_date and end_date are timezone-naive for comparison
        if hasattr(start_date, 'tzinfo') and start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        
        for file_path in glob.glob(pattern):
            # Extract date from filename
            filename = os.path.basename(file_path)
            try:
                # Format: Long_Reversal_Daily_YYYYMMDD_HHMMSS.xlsx
                date_str = filename.split('_')[3]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if start_date <= file_date <= end_date:
                    scan_files.append({
                        'file': file_path,
                        'date': file_date,
                        'filename': filename
                    })
            except (IndexError, ValueError):
                logger.warning(f"Could not parse date from filename: {filename}")
                continue
        
        # Sort by date
        scan_files.sort(key=lambda x: x['date'])
        return scan_files
    
    def get_regime_for_date(self, date):
        """Get market regime data for a specific date"""
        date_str = date.strftime('%Y%m%d')
        pattern = os.path.join(self.regime_dir, f'regime_report_{date_str}_*.json')
        
        regime_files = glob.glob(pattern)
        if not regime_files:
            return None
            
        # Get the report closest to market open (around 11:30 AM)
        best_file = None
        best_time_diff = float('inf')
        
        for file_path in regime_files:
            try:
                time_str = os.path.basename(file_path).split('_')[3].replace('.json', '')
                file_time = int(time_str[:4])  # HHMM format
                target_time = 1130  # 11:30 AM
                
                time_diff = abs(file_time - target_time)
                if time_diff < best_time_diff:
                    best_time_diff = time_diff
                    best_file = file_path
            except:
                continue
                
        if best_file:
            try:
                with open(best_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading regime file {best_file}: {e}")
                
        return None
    
    def analyze_ticker_performance(self, ticker, entry_date, entry_price, stop_loss, target1, target2, holding_days=5):
        """
        Analyze performance of a single ticker
        
        Args:
            ticker: Stock symbol
            entry_date: Date of signal
            entry_price: Recommended entry price
            stop_loss: Stop loss price
            target1: First target price
            target2: Second target price
            holding_days: Maximum holding period (default: 5 trading days)
            
        Returns:
            dict: Performance metrics
        """
        try:
            # Get historical data
            end_date = entry_date + timedelta(days=holding_days + 10)  # Extra days for weekends
            
            hist_df = self.data_handler.fetch_historical_data(
                ticker=ticker,
                interval="day",
                from_date=entry_date,
                to_date=end_date
            )
            
            if hist_df.empty:
                return None
                
            # Ensure columns are lowercase
            hist_df.columns = hist_df.columns.str.lower()
            hist_df['date'] = pd.to_datetime(hist_df['date'])
            hist_df = hist_df.sort_values('date')
            
            # Get only trading days after entry
            # Handle timezone-aware datetime comparison
            if pd.api.types.is_datetime64_any_dtype(hist_df['date']):
                # Convert entry_date to timezone-aware if hist_df dates are timezone-aware
                if hist_df['date'].dt.tz is not None:
                    # Convert timezone-aware dates to timezone-naive for comparison
                    hist_df['date'] = hist_df['date'].dt.tz_localize(None)
                hist_df = hist_df[hist_df['date'] > entry_date]
            else:
                hist_df = hist_df[hist_df['date'] > entry_date]
                
            if hist_df.empty:
                return None
                
            # Limit to holding period
            hist_df = hist_df.head(holding_days)
            
            # Calculate metrics
            shares = int(self.capital_per_position / entry_price)
            
            # Track if targets/SL were hit
            sl_hit = False
            target1_hit = False
            target2_hit = False
            exit_price = None
            exit_date = None
            exit_reason = None
            
            for _, row in hist_df.iterrows():
                # Check stop loss
                if row['low'] <= stop_loss and not sl_hit:
                    sl_hit = True
                    exit_price = stop_loss
                    exit_date = row['date']
                    exit_reason = 'Stop Loss'
                    break
                    
                # Check targets
                if row['high'] >= target2 and not target2_hit:
                    target2_hit = True
                    target1_hit = True
                    exit_price = target2
                    exit_date = row['date']
                    exit_reason = 'Target 2'
                    break
                elif row['high'] >= target1 and not target1_hit:
                    target1_hit = True
                    # For analysis, we'll consider partial exit at target1
                    # But continue to see if target2 is hit
            
            # If no exit triggered, use last day's close
            if exit_price is None:
                exit_price = hist_df.iloc[-1]['close']
                exit_date = hist_df.iloc[-1]['date']
                exit_reason = 'Time Exit'
            
            # Calculate P&L
            entry_value = shares * entry_price
            exit_value = shares * exit_price
            pnl = exit_value - entry_value
            pnl_percentage = (pnl / entry_value) * 100
            
            # Get max favorable and adverse excursion
            max_high = hist_df['high'].max()
            min_low = hist_df['low'].min()
            mfe = (max_high - entry_price) / entry_price * 100  # Max Favorable Excursion
            mae = (entry_price - min_low) / entry_price * 100   # Max Adverse Excursion
            
            return {
                'ticker': ticker,
                'entry_date': entry_date,
                'entry_price': entry_price,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'shares': shares,
                'capital': entry_value,
                'pnl': pnl,
                'pnl_percentage': pnl_percentage,
                'sl_hit': sl_hit,
                'target1_hit': target1_hit,
                'target2_hit': target2_hit,
                'mfe': mfe,
                'mae': mae,
                'holding_days': (exit_date - entry_date).days,
                'win': pnl > 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return None
    
    def analyze_scan_file(self, scan_file_info, score_filter='5/7', max_positions=10):
        """
        Analyze all tickers from a scan file
        
        Args:
            scan_file_info: Dict with file path and date
            score_filter: Score to filter (default: '5/7')
            max_positions: Maximum positions to take (default: 10)
            
        Returns:
            dict: Aggregated performance metrics
        """
        try:
            df = pd.read_excel(scan_file_info['file'])
            
            # Filter by score
            if score_filter:
                df_filtered = df[df['Score'] == score_filter]
            else:
                df_filtered = df
            
            # Take top positions
            df_filtered = df_filtered.head(max_positions)
            
            if df_filtered.empty:
                return None
            
            # Analyze each ticker
            trades = []
            for _, row in df_filtered.iterrows():
                result = self.analyze_ticker_performance(
                    ticker=row['Ticker'],
                    entry_date=scan_file_info['date'],
                    entry_price=row['Entry_Price'],
                    stop_loss=row['Stop_Loss'],
                    target1=row['Target1'],
                    target2=row.get('Target2', row['Target1'] * 1.5)  # Fallback if Target2 missing
                )
                
                if result:
                    trades.append(result)
            
            if not trades:
                return None
            
            # Calculate aggregate metrics
            total_trades = len(trades)
            winners = [t for t in trades if t['win']]
            losers = [t for t in trades if not t['win']]
            
            total_pnl = sum(t['pnl'] for t in trades)
            total_capital = sum(t['capital'] for t in trades)
            
            return {
                'date': scan_file_info['date'],
                'file': scan_file_info['filename'],
                'total_trades': total_trades,
                'winners': len(winners),
                'losers': len(losers),
                'win_rate': len(winners) / total_trades * 100 if total_trades > 0 else 0,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl / total_capital * 100 if total_capital > 0 else 0,
                'avg_win': np.mean([t['pnl_percentage'] for t in winners]) if winners else 0,
                'avg_loss': np.mean([t['pnl_percentage'] for t in losers]) if losers else 0,
                'avg_pnl': np.mean([t['pnl_percentage'] for t in trades]),
                'max_win': max([t['pnl_percentage'] for t in trades]),
                'max_loss': min([t['pnl_percentage'] for t in trades]),
                'sl_hits': sum(1 for t in trades if t['sl_hit']),
                'target1_hits': sum(1 for t in trades if t['target1_hit']),
                'target2_hits': sum(1 for t in trades if t['target2_hit']),
                'trades': trades
            }
            
        except Exception as e:
            logger.error(f"Error analyzing scan file {scan_file_info['file']}: {e}")
            return None
    
    def run_analysis(self):
        """Run the complete 4-week analysis"""
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=self.weeks_to_analyze)
        
        logger.info(f"Analyzing Long Reversal performance from {start_date.date()} to {end_date.date()}")
        
        # Find all scan files
        scan_files = self.find_scan_files(start_date, end_date)
        logger.info(f"Found {len(scan_files)} scan files")
        
        # Analyze each scan
        all_results = []
        weekly_results = defaultdict(list)
        
        for scan_file in scan_files:
            logger.info(f"Analyzing {scan_file['filename']}...")
            
            # Get regime data for the date
            regime_data = self.get_regime_for_date(scan_file['date'])
            
            # Analyze scan performance
            result = self.analyze_scan_file(scan_file)
            
            if result:
                # Add regime data
                if regime_data:
                    result['regime'] = regime_data['market_regime']['regime']
                    result['regime_confidence'] = regime_data['market_regime']['confidence']
                    result['breadth_bullish'] = regime_data.get('breadth_indicators', {}).get('bullish_percent', 0)
                    result['volatility_regime'] = regime_data.get('volatility', {}).get('volatility_regime', 'N/A')
                else:
                    result['regime'] = 'unknown'
                    result['regime_confidence'] = 0
                    result['breadth_bullish'] = 0
                    result['volatility_regime'] = 'unknown'
                
                all_results.append(result)
                
                # Group by week
                week_num = (scan_file['date'] - start_date).days // 7 + 1
                weekly_results[f'Week {week_num}'].append(result)
        
        # Generate comprehensive report
        report = self.generate_report(all_results, weekly_results, start_date, end_date)
        
        # Save report
        self.save_report(report)
        
        return report
    
    def generate_report(self, all_results, weekly_results, start_date, end_date):
        """Generate comprehensive analysis report"""
        report = {
            'analysis_period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'weeks': self.weeks_to_analyze
            },
            'summary': {},
            'weekly_breakdown': {},
            'regime_correlation': {},
            'detailed_trades': []
        }
        
        # Overall summary
        if all_results:
            total_trades = sum(r['total_trades'] for r in all_results)
            total_winners = sum(r['winners'] for r in all_results)
            total_pnl = sum(r['total_pnl'] for r in all_results)
            
            all_trades = []
            for r in all_results:
                all_trades.extend(r['trades'])
            
            report['summary'] = {
                'total_scans': len(all_results),
                'total_trades': total_trades,
                'total_winners': total_winners,
                'total_losers': total_trades - total_winners,
                'overall_win_rate': total_winners / total_trades * 100 if total_trades > 0 else 0,
                'total_pnl': total_pnl,
                'avg_pnl_per_scan': total_pnl / len(all_results) if all_results else 0,
                'avg_win_percentage': np.mean([t['pnl_percentage'] for t in all_trades if t['win']]) if any(t['win'] for t in all_trades) else 0,
                'avg_loss_percentage': np.mean([t['pnl_percentage'] for t in all_trades if not t['win']]) if any(not t['win'] for t in all_trades) else 0,
                'best_day': max(all_results, key=lambda x: x['total_pnl_pct'])['date'].strftime('%Y-%m-%d'),
                'worst_day': min(all_results, key=lambda x: x['total_pnl_pct'])['date'].strftime('%Y-%m-%d')
            }
        
        # Weekly breakdown
        for week, results in weekly_results.items():
            if results:
                week_trades = sum(r['total_trades'] for r in results)
                week_winners = sum(r['winners'] for r in results)
                week_pnl = sum(r['total_pnl'] for r in results)
                
                report['weekly_breakdown'][week] = {
                    'scans': len(results),
                    'trades': week_trades,
                    'winners': week_winners,
                    'win_rate': week_winners / week_trades * 100 if week_trades > 0 else 0,
                    'total_pnl': week_pnl,
                    'avg_pnl_per_scan': week_pnl / len(results),
                    'dates': [r['date'].strftime('%Y-%m-%d') for r in results]
                }
        
        # Regime correlation analysis
        regime_performance = defaultdict(lambda: {'trades': 0, 'winners': 0, 'pnl': 0, 'scans': 0})
        
        for result in all_results:
            regime = result['regime']
            regime_performance[regime]['scans'] += 1
            regime_performance[regime]['trades'] += result['total_trades']
            regime_performance[regime]['winners'] += result['winners']
            regime_performance[regime]['pnl'] += result['total_pnl']
        
        for regime, data in regime_performance.items():
            report['regime_correlation'][regime] = {
                'scans': data['scans'],
                'trades': data['trades'],
                'win_rate': data['winners'] / data['trades'] * 100 if data['trades'] > 0 else 0,
                'total_pnl': data['pnl'],
                'avg_pnl_per_scan': data['pnl'] / data['scans'] if data['scans'] > 0 else 0
            }
        
        # Add detailed trade data
        report['detailed_trades'] = all_results
        
        return report
    
    def save_report(self, report):
        """Save analysis report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON report
        json_file = os.path.join(self.output_dir, f'long_reversal_4week_analysis_{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save latest report
        latest_file = os.path.join(self.output_dir, 'latest_4week_analysis.json')
        with open(latest_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate Excel report
        self.generate_excel_report(report, timestamp)
        
        # Print summary
        self.print_summary(report)
        
        logger.info(f"Report saved to {json_file}")
    
    def generate_excel_report(self, report, timestamp):
        """Generate Excel report with multiple sheets"""
        excel_file = os.path.join(self.output_dir, f'long_reversal_4week_analysis_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame([report['summary']])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Weekly breakdown
            weekly_df = pd.DataFrame.from_dict(report['weekly_breakdown'], orient='index')
            weekly_df.to_excel(writer, sheet_name='Weekly_Breakdown')
            
            # Regime correlation
            regime_df = pd.DataFrame.from_dict(report['regime_correlation'], orient='index')
            regime_df.to_excel(writer, sheet_name='Regime_Correlation')
            
            # Daily results
            daily_data = []
            for result in report['detailed_trades']:
                daily_data.append({
                    'Date': result['date'],
                    'Regime': result['regime'],
                    'Regime_Confidence': result['regime_confidence'],
                    'Trades': result['total_trades'],
                    'Winners': result['winners'],
                    'Win_Rate': result['win_rate'],
                    'Total_PnL': result['total_pnl'],
                    'PnL_Pct': result['total_pnl_pct'],
                    'Avg_Win': result['avg_win'],
                    'Avg_Loss': result['avg_loss']
                })
            
            daily_df = pd.DataFrame(daily_data)
            daily_df.to_excel(writer, sheet_name='Daily_Results', index=False)
        
        # Also save latest Excel
        latest_excel = os.path.join(self.output_dir, 'latest_4week_analysis.xlsx')
        with pd.ExcelWriter(latest_excel, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            weekly_df.to_excel(writer, sheet_name='Weekly_Breakdown')
            regime_df.to_excel(writer, sheet_name='Regime_Correlation')
            daily_df.to_excel(writer, sheet_name='Daily_Results', index=False)
    
    def print_summary(self, report):
        """Print analysis summary to console"""
        print("\n" + "="*80)
        print("LONG REVERSAL 4-WEEK PERFORMANCE ANALYSIS")
        print("="*80)
        
        print(f"\nAnalysis Period: {report['analysis_period']['start']} to {report['analysis_period']['end']}")
        
        summary = report['summary']
        print(f"\nOVERALL SUMMARY:")
        print(f"  Total Scans: {summary.get('total_scans', 0)}")
        print(f"  Total Trades: {summary.get('total_trades', 0)}")
        print(f"  Win Rate: {summary.get('overall_win_rate', 0):.1f}%")
        print(f"  Total P&L: ₹{summary.get('total_pnl', 0):,.2f}")
        print(f"  Average Win: {summary.get('avg_win_percentage', 0):.2f}%")
        print(f"  Average Loss: {summary.get('avg_loss_percentage', 0):.2f}%")
        
        print(f"\nWEEKLY BREAKDOWN:")
        for week, data in sorted(report['weekly_breakdown'].items()):
            print(f"\n{week}:")
            print(f"  Scans: {data['scans']}")
            print(f"  Trades: {data['trades']}")
            print(f"  Win Rate: {data['win_rate']:.1f}%")
            print(f"  P&L: ₹{data['total_pnl']:,.2f}")
        
        print(f"\nREGIME CORRELATION:")
        for regime, data in sorted(report['regime_correlation'].items()):
            print(f"\n{regime}:")
            print(f"  Scans: {data['scans']}")
            print(f"  Win Rate: {data['win_rate']:.1f}%")
            print(f"  Avg P&L per Scan: ₹{data['avg_pnl_per_scan']:,.2f}")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    # You can specify a different user here if needed
    user = 'Sai'  # Change this to use different user credentials
    
    print(f"Using credentials for user: {user}")
    analyzer = LongReversalPerformanceAnalyzer(weeks_to_analyze=4, user=user)
    report = analyzer.run_analysis()
    
    print("\nAnalysis complete! Check the output directory for detailed reports.")
    print(f"Output directory: {analyzer.output_dir}")

if __name__ == "__main__":
    main()