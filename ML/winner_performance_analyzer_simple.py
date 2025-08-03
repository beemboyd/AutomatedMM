"""
Winner Performance Analyzer with Zerodha API

This script analyzes trading performance using actual OHLC data from Zerodha API.
Uses the same connection pattern as Al_Brooks_Higher_Probability_Reversal.py

Usage:
    python winner_performance_analyzer_simple.py [--days 30] [--top-n 20] [-u Sai]
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
        logging.FileHandler('ML/logs/winner_performance_analyzer.log'),
        logging.StreamHandler()
    ]
)

# Load credentials from Daily/config.ini (same as Al Brooks script)
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
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

# Data cache implementation (same as Al Brooks script)
class DataCache:
    def __init__(self):
        self.instruments_df = None
        self.instrument_tokens = {}
        self.data_cache = {}

cache = DataCache()

class SimpleWinnerAnalyzer:
    """Analyzer using the same pattern as Al Brooks script"""
    
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
        
        # Validate credentials
        if not self.api_key or not self.access_token:
            raise ValueError(f"API key or access token missing for user {user_name}")
        
        # Initialize Kite Connect (same as Al Brooks)
        self.kite = self._initialize_kite()
        
        # Data storage
        self.results_dir = "Daily/results"
        self.ticker_performance = {}
        
        self.logger.info(f"Successfully initialized for user {user_name}")
    
    def _initialize_kite(self):
        """Initialize Kite Connect client with error handling"""
        try:
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(self.access_token)
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite Connect: {e}")
            raise
    
    def get_instruments_data(self):
        """Fetch and cache instruments data from Zerodha (same as Al Brooks)"""
        if cache.instruments_df is None:
            try:
                instruments = self.kite.instruments("NSE")
                if instruments:
                    cache.instruments_df = pd.DataFrame(instruments)
                    self.logger.info("Fetched instruments data successfully.")
                else:
                    # Try backup file
                    backup_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                             "Daily", "data", "instruments_backup.csv")
                    if os.path.exists(backup_file):
                        cache.instruments_df = pd.read_csv(backup_file)
                        self.logger.info("Loaded instruments data from backup file.")
                    else:
                        cache.instruments_df = pd.DataFrame()
            except Exception as e:
                self.logger.error(f"Error fetching instruments data: {e}")
                # Try to load from backup file
                try:
                    backup_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                             "Daily", "data", "instruments_backup.csv")
                    if os.path.exists(backup_file):
                        cache.instruments_df = pd.read_csv(backup_file)
                        self.logger.info("Loaded instruments data from backup file after API error.")
                    else:
                        cache.instruments_df = pd.DataFrame()
                except Exception as backup_e:
                    self.logger.error(f"Error loading backup instruments data: {backup_e}")
                    cache.instruments_df = pd.DataFrame()
        return cache.instruments_df
    
    def get_instrument_token(self, ticker):
        """Get instrument token for a ticker with caching (same as Al Brooks)"""
        if ticker in cache.instrument_tokens:
            return cache.instrument_tokens[ticker]
        
        df = self.get_instruments_data()
        if df.empty:
            self.logger.warning("Instruments data is empty.")
            return None
        
        ticker_upper = ticker.upper()
        
        # Try exact match on trading symbol
        if 'tradingsymbol' in df.columns:
            df_filtered = df[df['tradingsymbol'].str.upper() == ticker_upper]
            if not df_filtered.empty:
                token = int(df_filtered.iloc[0]['instrument_token'])
                cache.instrument_tokens[ticker] = token
                return token
        
        return None
    
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
    
    def fetch_data_kite(self, ticker: str, from_date: datetime, to_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical data with caching and error handling (same as Al Brooks)"""
        cache_key = f"{ticker}_day_{from_date}_{to_date}"
        
        # Check cache first
        if cache_key in cache.data_cache:
            return cache.data_cache[cache_key]
        
        # Get instrument token
        token = self.get_instrument_token(ticker)
        if token is None:
            self.logger.warning(f"Instrument token for {ticker} not found.")
            return pd.DataFrame()
        
        # Try API with retries
        max_retries = 3
        retry_delay = 2
        backoff_factor = 1.5
        
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    self.logger.info(f"Fetching data for {ticker}...")
                else:
                    self.logger.debug(f"Retry {attempt+1} for {ticker}...")
                
                data = self.kite.historical_data(token, from_date, to_date, "day")
                
                if not data:
                    self.logger.warning(f"No data returned for {ticker}.")
                    break
                
                # Process the data
                df = pd.DataFrame(data)
                df.rename(columns={
                    "date": "Date",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                }, inplace=True)
                
                df['Date'] = pd.to_datetime(df['Date'])
                df['Ticker'] = ticker
                
                # Cache and return
                cache.data_cache[cache_key] = df
                return df
                
            except Exception as e:
                if "Too many requests" in str(e) and attempt < max_retries - 1:
                    wait_time = retry_delay * (backoff_factor ** attempt)
                    self.logger.warning(f"Rate limit hit for {ticker}. Waiting {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Error fetching data for {ticker}: {e}")
                    break
        
        return pd.DataFrame()
    
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
        df = self.fetch_data_kite(ticker, entry_date, end_date)
        
        if df.empty or len(df) < 2:
            return result
            
        # Set Date as index if not already
        if 'Date' in df.columns:
            df.set_index('Date', inplace=True)
            
        # Find entry date in data
        entry_found = False
        entry_idx = None
        for idx, (date, row) in enumerate(df.iterrows()):
            if date.date() >= entry_date.date():
                entry_found = True
                entry_idx = idx
                break
                
        if not entry_found:
            return result
            
        # Analyze subsequent days
        for i, (date, row) in enumerate(df.iloc[entry_idx:].iterrows()):
            days_held = i + 1
            
            # Track max gain/loss
            gain = ((row['High'] - entry_price) / entry_price) * 100
            loss = ((row['Low'] - entry_price) / entry_price) * 100
            
            result['max_gain'] = max(result['max_gain'], gain)
            result['max_loss'] = min(result['max_loss'], loss)
            
            # Check exit conditions
            if row['Low'] <= stop_loss:
                result['hit_stoploss'] = True
                result['outcome'] = 'stoploss'
                result['pnl_percent'] = ((stop_loss - entry_price) / entry_price) * 100
                result['holding_days'] = days_held
                break
                
            elif row['High'] >= target2:
                result['hit_target2'] = True
                result['hit_target1'] = True
                result['outcome'] = 'target2'
                result['pnl_percent'] = ((target2 - entry_price) / entry_price) * 100
                result['holding_days'] = days_held
                break
                
            elif row['High'] >= target1 and not result['hit_target1']:
                result['hit_target1'] = True
                # Continue to see if target2 is hit
                
        # If no exit, use last close
        if result['outcome'] == 'unknown' and len(df.iloc[entry_idx:]) > 0:
            last_close = df.iloc[-1]['Close']
            result['outcome'] = 'open'
            result['pnl_percent'] = ((last_close - entry_price) / entry_price) * 100
            result['holding_days'] = len(df.iloc[entry_idx:])
            
        return result
    
    def analyze_all_trades(self, df: pd.DataFrame):
        """Analyze all trades in the dataframe"""
        self.logger.info("Analyzing trade performance...")
        
        ticker_trades = defaultdict(list)
        total_trades = len(df)
        
        for idx, row in df.iterrows():
            if idx % 100 == 0:
                self.logger.info(f"Processing trade {idx + 1}/{total_trades}...")
                
            performance = self.calculate_trade_performance(
                ticker=row['Ticker'],
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
            
            ticker_trades[row['Ticker']].append(performance)
            
        # Aggregate by ticker
        for ticker, trades in ticker_trades.items():
            self._calculate_ticker_stats(ticker, trades)
            
        self.logger.info(f"Analyzed {len(ticker_trades)} tickers")
    
    def _calculate_ticker_stats(self, ticker: str, trades: List[Dict]):
        """Calculate aggregate statistics for a ticker"""
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl_percent'] > 0]
        
        stats = {
            'ticker': ticker,
            'total_trades': total_trades,
            'win_rate': len(winning_trades) / total_trades if total_trades > 0 else 0,
            'total_pnl': sum(t['pnl_percent'] for t in trades),
            'avg_pnl': np.mean([t['pnl_percent'] for t in trades]) if trades else 0,
            'avg_win': np.mean([t['pnl_percent'] for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t['pnl_percent'] for t in trades if t['pnl_percent'] < 0]) or 0,
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
        report_file = f"ML/results/winner_analysis_simple_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write("WINNER PERFORMANCE ANALYSIS (WITH LIVE DATA)\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now()}\n")
            f.write(f"Total Tickers: {len(self.ticker_performance)}\n")
            f.write(f"Total Trades: {sum(s['total_trades'] for s in self.ticker_performance.values())}\n\n")
            
            f.write(f"TOP {top_n} PERFORMERS\n")
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
            
            top_winners = sorted_tickers[:top_n]
            if top_winners:
                avg_win_rate = np.mean([s[1]['win_rate'] for s in top_winners])
                avg_holding = np.mean([s[1]['avg_holding_days'] for s in top_winners])
                
                f.write(f"1. Top performers average win rate: {avg_win_rate:.1%}\n")
                f.write(f"2. Average holding period for winners: {avg_holding:.1f} days\n")
                
                # Find repeat winners
                repeat_winners = [(t, s) for t, s in top_winners if s['total_trades'] >= 5]
                if repeat_winners:
                    f.write(f"3. Repeat winners (5+ trades): {', '.join([t[0] for t in repeat_winners[:5]])}\n")
                    
        # Excel report
        excel_file = f"ML/results/winner_analysis_simple_{timestamp}.xlsx"
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
    
    def run(self, days: int = 30, top_n: int = 20):
        """Run the complete analysis"""
        # Load data
        df = self.load_reports(days)
        if df.empty:
            self.logger.error("No data to analyze")
            return None, None
            
        # Analyze trades
        self.analyze_all_trades(df)
        
        # Generate report
        return self.generate_report(top_n)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze winner performance with live Zerodha data')
    parser.add_argument('--days', type=int, default=30, help='Days to analyze (default: 30)')
    parser.add_argument('--top-n', type=int, default=20, help='Top N winners to show (default: 20)')
    parser.add_argument('-u', '--user', type=str, default='Sai', help='User name for API credentials (default: Sai)')
    
    args = parser.parse_args()
    
    # Create directories
    os.makedirs('ML/results', exist_ok=True)
    os.makedirs('ML/logs', exist_ok=True)
    
    try:
        analyzer = SimpleWinnerAnalyzer(user_name=args.user)
        text_report, excel_report = analyzer.run(days=args.days, top_n=args.top_n)
        
        if text_report:
            print(f"\nAnalysis complete!")
            print(f"Text report: {text_report}")
            print(f"Excel report: {excel_report}")
            
            # Show summary
            with open(text_report, 'r') as f:
                print("\n" + "".join(f.readlines()[:30]))
                
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    main()