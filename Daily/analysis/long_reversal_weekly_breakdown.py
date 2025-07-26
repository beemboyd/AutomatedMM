#!/usr/bin/env python
"""
Weekly Breakdown Analysis for Long Reversal Performance
Analyzes performance week by week for the past 4 weeks
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import glob
import json
from collections import defaultdict
from kiteconnect import KiteConnect
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_config

class WeeklyBreakdownAnalyzer:
    def __init__(self, weeks_to_analyze=4, user='Sai'):
        """Initialize the analyzer"""
        self.weeks_to_analyze = weeks_to_analyze
        self.user = user
        
        # Initialize Kite connection
        self.config = get_config()
        credential_section = f'API_CREDENTIALS_{user}'
        
        if not self.config.config.has_section(credential_section):
            raise ValueError(f"No credentials found for user {user}")
            
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Paths
        self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        os.makedirs(self.output_dir, exist_ok=True)
        
    def get_week_dates(self):
        """Get start and end dates for each of the past 4 weeks"""
        today = datetime.now()
        current_week_start = today - timedelta(days=today.weekday())  # Monday of current week
        
        weeks = []
        for i in range(self.weeks_to_analyze):
            week_end = current_week_start - timedelta(days=1) - timedelta(weeks=i)  # Sunday
            week_start = week_end - timedelta(days=6)  # Monday
            
            weeks.append({
                'week_num': self.weeks_to_analyze - i,
                'start': week_start,
                'end': week_end,
                'label': f"Week {self.weeks_to_analyze - i} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"
            })
        
        return list(reversed(weeks))
    
    def find_scan_files_by_week(self, week_start, week_end):
        """Find scan files for a specific week"""
        scan_files = []
        pattern = os.path.join(self.results_dir, 'Long_Reversal_Daily_*.xlsx')
        
        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            try:
                date_str = filename.split('_')[3]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if week_start <= file_date <= week_end:
                    scan_files.append({
                        'file': file_path,
                        'date': file_date,
                        'filename': filename
                    })
            except (IndexError, ValueError):
                continue
        
        return sorted(scan_files, key=lambda x: x['date'])
    
    def get_price_after_days(self, ticker, entry_date, days=5):
        """Get price after specified number of trading days"""
        try:
            end_date = entry_date + timedelta(days=days + 10)  # Extra days for weekends
            
            hist_data = self.kite.historical_data(
                self.get_instrument_token(ticker),
                entry_date,
                end_date,
                "day"
            )
            
            if not hist_data:
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(hist_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Remove timezone info for comparison
            if df['date'].dt.tz is not None:
                df['date'] = df['date'].dt.tz_localize(None)
            
            # Get data after entry date
            df = df[df['date'] > entry_date]
            
            if df.empty:
                return None
                
            # Get price after specified days
            if len(df) >= days:
                return df.iloc[days-1]['close']
            else:
                return df.iloc[-1]['close']  # Last available price
                
        except Exception as e:
            print(f"Error getting historical price for {ticker}: {e}")
            return None
    
    def get_instrument_token(self, ticker):
        """Get instrument token for a ticker"""
        try:
            instruments = self.kite.instruments("NSE")
            for inst in instruments:
                if inst['tradingsymbol'] == ticker:
                    return inst['instrument_token']
        except:
            pass
        return None
    
    def analyze_week(self, week_info):
        """Analyze performance for a specific week"""
        print(f"\nAnalyzing {week_info['label']}...")
        
        scan_files = self.find_scan_files_by_week(week_info['start'], week_info['end'])
        print(f"  Found {len(scan_files)} scan files")
        
        if not scan_files:
            return None
        
        # Collect all signals for this week
        week_signals = []
        
        for scan_file in scan_files:
            try:
                df = pd.read_excel(scan_file['file'])
                
                # Filter for 5/7 score and take top 10
                df_filtered = df[df['Score'] == '5/7'].head(10)
                
                if not df_filtered.empty:
                    for _, row in df_filtered.iterrows():
                        week_signals.append({
                            'ticker': row['Ticker'],
                            'signal_date': scan_file['date'],
                            'entry_price': row['Entry_Price'],
                            'stop_loss': row['Stop_Loss'],
                            'target1': row['Target1']
                        })
                        
            except Exception as e:
                print(f"  Error reading {scan_file['filename']}: {e}")
                continue
        
        if not week_signals:
            return None
        
        # Analyze each signal
        results = []
        unique_tickers = set()
        
        for signal in week_signals:
            ticker = signal['ticker']
            unique_tickers.add(ticker)
            
            # Get price after 5 trading days
            exit_price = self.get_price_after_days(ticker, signal['signal_date'], 5)
            
            if exit_price:
                price_change = exit_price - signal['entry_price']
                price_change_pct = (price_change / signal['entry_price']) * 100
                
                results.append({
                    'ticker': ticker,
                    'entry_price': signal['entry_price'],
                    'exit_price': exit_price,
                    'price_change': price_change,
                    'price_change_pct': price_change_pct,
                    'win': price_change > 0,
                    'hit_sl': exit_price <= signal['stop_loss'],
                    'hit_target': exit_price >= signal['target1']
                })
        
        if not results:
            return None
        
        # Calculate week statistics
        total_trades = len(results)
        winners = sum(1 for r in results if r['win'])
        win_rate = (winners / total_trades) * 100
        
        avg_gain = np.mean([r['price_change_pct'] for r in results if r['win']]) if winners > 0 else 0
        avg_loss = np.mean([r['price_change_pct'] for r in results if not r['win']]) if (total_trades - winners) > 0 else 0
        overall_avg = np.mean([r['price_change_pct'] for r in results])
        
        sl_hits = sum(1 for r in results if r['hit_sl'])
        target_hits = sum(1 for r in results if r['hit_target'])
        
        return {
            'week_info': week_info,
            'scan_files': len(scan_files),
            'total_signals': len(week_signals),
            'unique_tickers': len(unique_tickers),
            'total_trades': total_trades,
            'winners': winners,
            'losers': total_trades - winners,
            'win_rate': win_rate,
            'avg_gain': avg_gain,
            'avg_loss': avg_loss,
            'overall_avg': overall_avg,
            'sl_hits': sl_hits,
            'target_hits': target_hits,
            'best_trade': max(results, key=lambda x: x['price_change_pct']),
            'worst_trade': min(results, key=lambda x: x['price_change_pct']),
            'raw_results': results
        }
    
    def create_visualization(self, weekly_results):
        """Create visualization of weekly performance"""
        # Prepare data for plotting
        weeks = []
        win_rates = []
        avg_returns = []
        total_trades = []
        
        for result in weekly_results:
            if result:
                weeks.append(result['week_info']['label'].split(' (')[0])
                win_rates.append(result['win_rate'])
                avg_returns.append(result['overall_avg'])
                total_trades.append(result['total_trades'])
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Long Reversal Weekly Performance Analysis', fontsize=16)
        
        # 1. Win Rate by Week
        ax1 = axes[0, 0]
        bars1 = ax1.bar(weeks, win_rates, color=['green' if wr > 50 else 'red' for wr in win_rates])
        ax1.set_title('Win Rate by Week')
        ax1.set_ylabel('Win Rate (%)')
        ax1.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        for bar, rate in zip(bars1, win_rates):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                    f'{rate:.1f}%', ha='center', va='bottom')
        
        # 2. Average Return by Week
        ax2 = axes[0, 1]
        bars2 = ax2.bar(weeks, avg_returns, color=['green' if ar > 0 else 'red' for ar in avg_returns])
        ax2.set_title('Average Return by Week')
        ax2.set_ylabel('Average Return (%)')
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        for bar, ret in zip(bars2, avg_returns):
            ax2.text(bar.get_x() + bar.get_width()/2, 
                    bar.get_height() + 0.2 if ret > 0 else bar.get_height() - 0.5, 
                    f'{ret:.1f}%', ha='center', va='bottom' if ret > 0 else 'top')
        
        # 3. Number of Trades by Week
        ax3 = axes[1, 0]
        ax3.bar(weeks, total_trades, color='blue', alpha=0.7)
        ax3.set_title('Number of Trades by Week')
        ax3.set_ylabel('Number of Trades')
        for i, trades in enumerate(total_trades):
            ax3.text(i, trades + 2, str(trades), ha='center', va='bottom')
        
        # 4. Cumulative Performance
        ax4 = axes[1, 1]
        cumulative_returns = np.cumsum(avg_returns)
        ax4.plot(weeks, cumulative_returns, marker='o', linewidth=2, markersize=8)
        ax4.set_title('Cumulative Average Return')
        ax4.set_ylabel('Cumulative Return (%)')
        ax4.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax4.fill_between(range(len(weeks)), cumulative_returns, 0, 
                        where=(np.array(cumulative_returns) > 0), alpha=0.3, color='green')
        ax4.fill_between(range(len(weeks)), cumulative_returns, 0, 
                        where=(np.array(cumulative_returns) < 0), alpha=0.3, color='red')
        
        plt.tight_layout()
        
        # Save plot
        plot_file = os.path.join(self.output_dir, 'weekly_performance_chart.png')
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return plot_file
    
    def run_analysis(self):
        """Run the complete weekly breakdown analysis"""
        print("="*60)
        print("LONG REVERSAL WEEKLY BREAKDOWN ANALYSIS")
        print("="*60)
        
        # Get week dates
        weeks = self.get_week_dates()
        
        # Analyze each week
        weekly_results = []
        for week in weeks:
            result = self.analyze_week(week)
            if result:
                weekly_results.append(result)
                
                # Print week summary
                print(f"\n{week['label']} Summary:")
                print(f"  Total Trades: {result['total_trades']}")
                print(f"  Win Rate: {result['win_rate']:.1f}%")
                print(f"  Average Return: {result['overall_avg']:.2f}%")
                print(f"  Best: {result['best_trade']['ticker']} ({result['best_trade']['price_change_pct']:+.2f}%)")
                print(f"  Worst: {result['worst_trade']['ticker']} ({result['worst_trade']['price_change_pct']:+.2f}%)")
        
        # Overall summary
        if weekly_results:
            print("\n" + "="*60)
            print("OVERALL SUMMARY")
            print("="*60)
            
            total_trades = sum(r['total_trades'] for r in weekly_results)
            total_winners = sum(r['winners'] for r in weekly_results)
            overall_win_rate = (total_winners / total_trades) * 100 if total_trades > 0 else 0
            
            print(f"Total Trades: {total_trades}")
            print(f"Overall Win Rate: {overall_win_rate:.1f}%")
            print(f"Best Week: Week {max(weekly_results, key=lambda x: x['win_rate'])['week_info']['week_num']}")
            print(f"Worst Week: Week {min(weekly_results, key=lambda x: x['win_rate'])['week_info']['week_num']}")
            
            # Save detailed report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_file = os.path.join(self.output_dir, f'weekly_breakdown_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Summary sheet
                summary_data = []
                for result in weekly_results:
                    summary_data.append({
                        'Week': result['week_info']['label'],
                        'Scan_Files': result['scan_files'],
                        'Total_Signals': result['total_signals'],
                        'Unique_Tickers': result['unique_tickers'],
                        'Total_Trades': result['total_trades'],
                        'Winners': result['winners'],
                        'Losers': result['losers'],
                        'Win_Rate': result['win_rate'],
                        'Avg_Gain': result['avg_gain'],
                        'Avg_Loss': result['avg_loss'],
                        'Overall_Avg': result['overall_avg'],
                        'SL_Hits': result['sl_hits'],
                        'Target_Hits': result['target_hits']
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Weekly_Summary', index=False)
                
                # Detailed trades for each week
                for i, result in enumerate(weekly_results):
                    if result['raw_results']:
                        trades_df = pd.DataFrame(result['raw_results'])
                        sheet_name = f"Week_{result['week_info']['week_num']}_Trades"
                        trades_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Create visualization
            plot_file = self.create_visualization(weekly_results)
            
            print(f"\nResults saved to:")
            print(f"  - {excel_file}")
            print(f"  - {plot_file}")
            
            return weekly_results

def main():
    """Main function"""
    analyzer = WeeklyBreakdownAnalyzer(weeks_to_analyze=4, user='Sai')
    analyzer.run_analysis()

if __name__ == "__main__":
    main()