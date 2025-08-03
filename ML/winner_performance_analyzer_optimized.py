"""
Optimized Winner Performance Analyzer with Zerodha API

This script analyzes trading performance using actual OHLC data from Zerodha API.
Optimized to fetch data only when needed and avoid timeouts.

Usage:
    python winner_performance_analyzer_optimized.py [--days 7] [--top-n 20] [-u Sai] [--limit 50]
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List, Optional
import configparser
from collections import defaultdict
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/winner_performance_analyzer.log'),
        logging.StreamHandler()
    ]
)

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Daily', 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        raise ValueError(f"No credentials found for user {user_name}")
    
    return config

class OptimizedWinnerAnalyzer:
    """Optimized analyzer that fetches data only when needed"""
    
    def __init__(self, user_name: str = "Sai"):
        """Initialize with Zerodha credentials"""
        self.user_name = user_name
        self.logger = logging.getLogger(__name__)
        
        # Load config
        self.config = load_daily_config(user_name)
        credential_section = f'API_CREDENTIALS_{user_name}'
        
        # Get credentials
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        # Initialize Kite Connect
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Data storage
        self.results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       "Daily", "results")
        self.ticker_performance = {}
        self.data_cache = {}  # Cache for historical data
        self.instrument_cache = {}  # Cache for instrument tokens
        self.instruments_loaded = False
        
        self.logger.info(f"Successfully initialized for user {user_name}")
    
    def get_instrument_token(self, ticker: str) -> Optional[int]:
        """Get instrument token for a ticker with lazy loading"""
        # Check cache first
        if ticker in self.instrument_cache:
            return self.instrument_cache[ticker]
        
        # Load instruments if not already loaded
        if not self.instruments_loaded:
            try:
                self.logger.info("Loading instruments list from Kite...")
                instruments = self.kite.instruments("NSE")
                
                # Build cache
                for inst in instruments:
                    self.instrument_cache[inst['tradingsymbol']] = inst['instrument_token']
                
                self.instruments_loaded = True
                self.logger.info(f"Loaded {len(self.instrument_cache)} instruments")
                
            except Exception as e:
                self.logger.error(f"Error loading instruments: {e}")
                # Try backup file
                backup_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                         "Daily", "data", "instruments_backup.csv")
                if os.path.exists(backup_file):
                    try:
                        df = pd.read_csv(backup_file)
                        for _, row in df.iterrows():
                            if 'tradingsymbol' in row and 'instrument_token' in row:
                                self.instrument_cache[row['tradingsymbol']] = int(row['instrument_token'])
                        self.instruments_loaded = True
                        self.logger.info(f"Loaded {len(self.instrument_cache)} instruments from backup")
                    except Exception as be:
                        self.logger.error(f"Error loading backup: {be}")
        
        # Return from cache
        return self.instrument_cache.get(ticker)
    
    def load_reports(self, days: int) -> pd.DataFrame:
        """Load Excel reports from the last N days"""
        self.logger.info(f"Loading reports from last {days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        files = [f for f in os.listdir(self.results_dir) if f.endswith('.xlsx')]
        files.sort()
        
        for file in files:
            try:
                # Extract date from filename
                date_str = file.split('_')[2]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if file_date < cutoff_date:
                    continue
                    
                df = pd.read_excel(os.path.join(self.results_dir, file))
                df['scan_date'] = file_date
                all_data.append(df)
                
            except Exception as e:
                self.logger.debug(f"Skipping {file}: {e}")
                
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Loaded {len(combined)} entries from {len(all_data)} files")
            return combined
        
        return pd.DataFrame()
    
    def fetch_historical_data(self, ticker: str, from_date: datetime, to_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical data with caching"""
        cache_key = f"{ticker}_{from_date.date()}_{to_date.date()}"
        
        # Check cache
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        # Get instrument token
        token = self.get_instrument_token(ticker)
        if not token:
            self.logger.debug(f"No instrument token for {ticker}")
            return None
        
        try:
            # Fetch data
            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if data:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                # Cache the data
                self.data_cache[cache_key] = df
                return df
            
        except Exception as e:
            self.logger.debug(f"Error fetching data for {ticker}: {e}")
            
        return None
    
    def calculate_trade_performance(self, ticker: str, entry_date: datetime, 
                                  entry_price: float, stop_loss: float,
                                  target1: float, target2: float) -> Dict:
        """Calculate actual performance for a trade"""
        result = {
            'ticker': ticker,
            'entry_date': entry_date,
            'outcome': 'unknown',
            'pnl_percent': 0,
            'holding_days': 0,
            'hit_target1': False,
            'hit_target2': False,
            'hit_stoploss': False,
            'max_gain': 0,
            'max_loss': 0
        }
        
        # Get data from entry date + 30 days
        end_date = min(entry_date + timedelta(days=30), datetime.now())
        df = self.fetch_historical_data(ticker, entry_date, end_date)
        
        if df is None or len(df) < 2:
            return result
            
        # Find entry date in data
        entry_found = False
        entry_idx = None
        for idx, (date, row) in enumerate(df.iterrows()):
            if date.date() >= entry_date.date():
                entry_found = True
                entry_idx = idx
                break
                
        if not entry_found or entry_idx is None:
            return result
            
        # Analyze subsequent days
        for i, (date, row) in enumerate(df.iloc[entry_idx:].iterrows()):
            days_held = i + 1
            
            # Track max gain/loss
            gain = ((row['high'] - entry_price) / entry_price) * 100
            loss = ((row['low'] - entry_price) / entry_price) * 100
            
            result['max_gain'] = max(result['max_gain'], gain)
            result['max_loss'] = min(result['max_loss'], loss)
            
            # Check exit conditions
            if row['low'] <= stop_loss:
                result['hit_stoploss'] = True
                result['outcome'] = 'stoploss'
                result['pnl_percent'] = ((stop_loss - entry_price) / entry_price) * 100
                result['holding_days'] = days_held
                break
                
            elif row['high'] >= target2:
                result['hit_target2'] = True
                result['hit_target1'] = True
                result['outcome'] = 'target2'
                result['pnl_percent'] = ((target2 - entry_price) / entry_price) * 100
                result['holding_days'] = days_held
                break
                
            elif row['high'] >= target1 and not result['hit_target1']:
                result['hit_target1'] = True
                # Continue to see if target2 is hit
                
        # If no exit, use last close
        if result['outcome'] == 'unknown' and len(df.iloc[entry_idx:]) > 0:
            last_close = df.iloc[-1]['close']
            result['outcome'] = 'open'
            result['pnl_percent'] = ((last_close - entry_price) / entry_price) * 100
            result['holding_days'] = len(df.iloc[entry_idx:])
            
        return result
    
    def analyze_trades(self, df: pd.DataFrame, limit: Optional[int] = None):
        """Analyze trades with optional limit"""
        self.logger.info(f"Analyzing trade performance...")
        
        # Group by ticker first to reduce redundant API calls
        ticker_groups = df.groupby('Ticker')
        
        total_tickers = len(ticker_groups)
        if limit:
            self.logger.info(f"Limiting analysis to {limit} tickers")
            ticker_groups = list(ticker_groups)[:limit]
        
        ticker_trades = defaultdict(list)
        
        for ticker_idx, (ticker, group) in enumerate(ticker_groups):
            self.logger.info(f"Processing ticker {ticker_idx + 1}/{len(ticker_groups)}: {ticker} ({len(group)} trades)")
            
            for idx, row in group.iterrows():
                performance = self.calculate_trade_performance(
                    ticker=ticker,
                    entry_date=row['scan_date'],
                    entry_price=row['Entry_Price'],
                    stop_loss=row['Stop_Loss'],
                    target1=row['Target1'],
                    target2=row['Target2']
                )
                
                # Add scan info
                performance['score'] = row['Score']
                performance['momentum_scan'] = row.get('Momentum_5D', 0)
                performance['volume_ratio'] = row.get('Volume_Ratio', 0)
                
                ticker_trades[ticker].append(performance)
                
            # Small delay to avoid rate limiting
            time.sleep(0.1)
            
        # Aggregate by ticker
        for ticker, trades in ticker_trades.items():
            self._calculate_ticker_stats(ticker, trades)
            
        self.logger.info(f"Analyzed {len(ticker_trades)} tickers")
    
    def _calculate_ticker_stats(self, ticker: str, trades: List[Dict]):
        """Calculate aggregate statistics for a ticker"""
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl_percent'] > 0]
        losing_trades = [t for t in trades if t['pnl_percent'] < 0]
        
        stats = {
            'ticker': ticker,
            'total_trades': total_trades,
            'win_rate': len(winning_trades) / total_trades if total_trades > 0 else 0,
            'total_pnl': sum(t['pnl_percent'] for t in trades),
            'avg_pnl': np.mean([t['pnl_percent'] for t in trades]) if trades else 0,
            'avg_win': np.mean([t['pnl_percent'] for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t['pnl_percent'] for t in losing_trades]) if losing_trades else 0,
            'target1_rate': sum(1 for t in trades if t['hit_target1']) / total_trades if total_trades > 0 else 0,
            'target2_rate': sum(1 for t in trades if t['hit_target2']) / total_trades if total_trades > 0 else 0,
            'stoploss_rate': sum(1 for t in trades if t['hit_stoploss']) / total_trades if total_trades > 0 else 0,
            'avg_holding_days': np.mean([t['holding_days'] for t in trades]) if trades else 0,
            'trades': trades
        }
        
        # Calculate expectancy
        stats['expectancy'] = (stats['win_rate'] * stats['avg_win']) + ((1 - stats['win_rate']) * stats['avg_loss'])
        
        self.ticker_performance[ticker] = stats
    
    def generate_report(self, top_n: int = 20):
        """Generate analysis report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Sort by total PnL
        sorted_tickers = sorted(
            self.ticker_performance.items(),
            key=lambda x: x[1]['total_pnl'],
            reverse=True
        )
        
        # Text report
        report_file = f"ML/results/winner_analysis_optimized_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write("WINNER PERFORMANCE ANALYSIS (OPTIMIZED)\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now()}\n")
            f.write(f"Total Tickers Analyzed: {len(self.ticker_performance)}\n")
            f.write(f"Total Trades Analyzed: {sum(s['total_trades'] for s in self.ticker_performance.values())}\n\n")
            
            # Winners summary
            winners = [t for t in sorted_tickers if t[1]['total_pnl'] > 0]
            losers = [t for t in sorted_tickers if t[1]['total_pnl'] < 0]
            
            f.write(f"Winners: {len(winners)} ({len(winners)/len(sorted_tickers)*100:.1f}%)\n")
            f.write(f"Losers: {len(losers)} ({len(losers)/len(sorted_tickers)*100:.1f}%)\n\n")
            
            f.write(f"TOP {min(top_n, len(sorted_tickers))} PERFORMERS\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<5}{'Ticker':<10}{'Trades':<8}{'Win%':<8}{'Total PnL':<12}{'Expectancy':<12}{'Avg Days':<10}\n")
            f.write("-" * 80 + "\n")
            
            for i, (ticker, stats) in enumerate(sorted_tickers[:top_n], 1):
                f.write(f"{i:<5}{ticker:<10}{stats['total_trades']:<8}"
                       f"{stats['win_rate']*100:<8.1f}{stats['total_pnl']:<12.2f}"
                       f"{stats['expectancy']:<12.2f}{stats['avg_holding_days']:<10.1f}\n")
                       
            # Key insights
            f.write("\n\nKEY INSIGHTS\n")
            f.write("-" * 40 + "\n")
            
            if winners:
                # Average stats for winners
                avg_win_rate = np.mean([s[1]['win_rate'] for s in winners])
                avg_expectancy = np.mean([s[1]['expectancy'] for s in winners])
                avg_holding = np.mean([s[1]['avg_holding_days'] for s in winners])
                
                f.write(f"1. Winners average win rate: {avg_win_rate:.1%}\n")
                f.write(f"2. Winners average expectancy: {avg_expectancy:.2f}%\n")
                f.write(f"3. Winners average holding period: {avg_holding:.1f} days\n")
                
                # Find consistent winners
                consistent_winners = [(t, s) for t, s in winners if s['total_trades'] >= 5 and s['win_rate'] > 0.5]
                if consistent_winners:
                    f.write(f"4. Consistent winners (5+ trades, 50%+ win rate): ")
                    f.write(", ".join([t[0] for t in consistent_winners[:5]]) + "\n")
                
                # Score analysis
                all_trades = []
                for _, stats in winners:
                    all_trades.extend(stats['trades'])
                
                if all_trades:
                    score_performance = defaultdict(list)
                    for trade in all_trades:
                        score_performance[trade['score']].append(trade['pnl_percent'])
                    
                    f.write("\n5. Performance by Score:\n")
                    for score in sorted(score_performance.keys(), reverse=True):
                        avg_pnl = np.mean(score_performance[score])
                        win_rate = sum(1 for p in score_performance[score] if p > 0) / len(score_performance[score])
                        f.write(f"   {score}: Avg PnL {avg_pnl:.2f}%, Win Rate {win_rate:.1%}\n")
                
        # Excel report
        excel_file = f"ML/results/winner_analysis_optimized_{timestamp}.xlsx"
        self._save_excel_report(excel_file, sorted_tickers)
        
        self.logger.info(f"Reports saved: {report_file} and {excel_file}")
        return report_file, excel_file
    
    def _save_excel_report(self, filename: str, sorted_tickers: List):
        """Save detailed Excel report"""
        # Summary sheet
        summary_data = []
        for ticker, stats in sorted_tickers:
            summary_data.append({
                'Ticker': ticker,
                'Total_Trades': stats['total_trades'],
                'Win_Rate_%': stats['win_rate'] * 100,
                'Total_PnL_%': stats['total_pnl'],
                'Avg_PnL_%': stats['avg_pnl'],
                'Expectancy_%': stats['expectancy'],
                'Target1_Hit_%': stats['target1_rate'] * 100,
                'Target2_Hit_%': stats['target2_rate'] * 100,
                'StopLoss_Hit_%': stats['stoploss_rate'] * 100,
                'Avg_Holding_Days': stats['avg_holding_days']
            })
            
        summary_df = pd.DataFrame(summary_data)
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Top 20 trades detail
            detail_data = []
            for ticker, stats in sorted_tickers[:20]:
                for trade in stats['trades']:
                    detail_data.append({
                        'Ticker': ticker,
                        'Entry_Date': trade['entry_date'],
                        'Outcome': trade['outcome'],
                        'PnL_%': trade['pnl_percent'],
                        'Holding_Days': trade['holding_days'],
                        'Max_Gain_%': trade['max_gain'],
                        'Max_Loss_%': trade['max_loss'],
                        'Score': trade['score']
                    })
                    
            if detail_data:
                detail_df = pd.DataFrame(detail_data)
                detail_df.to_excel(writer, sheet_name='Trade_Details', index=False)
    
    def run(self, days: int = 30, top_n: int = 20, limit: Optional[int] = None):
        """Run the complete analysis"""
        # Load data
        df = self.load_reports(days)
        if df.empty:
            self.logger.error("No data to analyze")
            return None, None
            
        # Analyze trades
        self.analyze_trades(df, limit=limit)
        
        # Generate report
        return self.generate_report(top_n)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze winner performance with live Zerodha data')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    parser.add_argument('--top-n', type=int, default=20, help='Top N winners to show (default: 20)')
    parser.add_argument('-u', '--user', type=str, default='Sai', help='User name for API credentials')
    parser.add_argument('--limit', type=int, help='Limit number of tickers to analyze (for testing)')
    
    args = parser.parse_args()
    
    # Create directories
    os.makedirs('ML/results', exist_ok=True)
    os.makedirs('ML/logs', exist_ok=True)
    
    try:
        analyzer = OptimizedWinnerAnalyzer(user_name=args.user)
        text_report, excel_report = analyzer.run(days=args.days, top_n=args.top_n, limit=args.limit)
        
        if text_report:
            print(f"\nAnalysis complete!")
            print(f"Text report: {text_report}")
            print(f"Excel report: {excel_report}")
            
            # Show summary
            with open(text_report, 'r') as f:
                lines = f.readlines()
                print("\n" + "".join(lines[:40]))
                if len(lines) > 40:
                    print("... (see full report for details)")
                
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    main()