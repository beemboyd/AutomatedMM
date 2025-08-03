#!/usr/bin/env python3
"""
Analyze weekly performance of Short Reversal signals
Track how much yield would have been generated if we went short
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import json
import configparser
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

class ShortReversalPerformanceAnalyzer:
    def __init__(self, signal_file: str, user_name: str = 'Sai'):
        """Initialize the analyzer"""
        self.signal_file = signal_file
        self.user_name = user_name
        
        # Extract date from filename
        self.signal_date = self.extract_date_from_filename(signal_file)
        
        # Setup paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Results directory
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'performance_analysis')
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.logger.info(f"Analyzing short reversal signals from {signal_file}")
        self.logger.info(f"Signal date: {self.signal_date}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'short_performance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def extract_date_from_filename(self, filename: str) -> datetime:
        """Extract date from filename like Short_Reversal_Daily_20250728_121336.xlsx"""
        import re
        match = re.search(r'(\d{8})_\d{6}', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')
        else:
            raise ValueError("Could not extract date from filename")
    
    def initialize_kite_connection(self) -> KiteConnect:
        """Initialize Kite connection"""
        try:
            config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def load_signal_data(self) -> pd.DataFrame:
        """Load short reversal signals from Excel file"""
        try:
            df = pd.read_excel(self.signal_file)
            self.logger.info(f"Loaded {len(df)} short signals from {self.signal_file}")
            return df
        except Exception as e:
            self.logger.error(f"Error loading signal file: {e}")
            return pd.DataFrame()
    
    def get_instrument_token(self, ticker: str) -> int:
        """Get instrument token for a ticker"""
        try:
            instruments = self.kite.instruments("NSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            # Try BSE if not found in NSE
            instruments = self.kite.instruments("BSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            return None
        except:
            return None
    
    def fetch_ticker_performance(self, ticker: str, entry_date: datetime, days: int = 5) -> Dict:
        """Fetch ticker performance from entry date"""
        try:
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                self.logger.warning(f"Instrument token not found for {ticker}")
                return None
            
            # Fetch data from entry date to end of week (5 trading days)
            from_date = entry_date
            to_date = entry_date + timedelta(days=days + 2)  # Add buffer for weekends
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval='day'
            )
            
            if not historical_data:
                return None
            
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get entry day data
            entry_day = df.iloc[0] if len(df) > 0 else None
            if entry_day is None:
                return None
            
            # Calculate performance for each day
            performance = {
                'ticker': ticker,
                'entry_date': entry_day['date'].strftime('%Y-%m-%d'),
                'entry_price': float(entry_day['close']),
                'entry_high': float(entry_day['high']),
                'entry_low': float(entry_day['low']),
                'daily_performance': []
            }
            
            # Track performance for each subsequent day
            for i in range(1, min(len(df), 6)):  # Max 5 days after entry
                day_data = df.iloc[i]
                
                # For short position: profit when price goes down
                pnl_percent = ((entry_day['close'] - day_data['close']) / entry_day['close']) * 100
                max_profit = ((entry_day['close'] - day_data['low']) / entry_day['close']) * 100
                max_loss = ((entry_day['close'] - day_data['high']) / entry_day['close']) * 100
                
                performance['daily_performance'].append({
                    'day': i,
                    'date': day_data['date'].strftime('%Y-%m-%d'),
                    'close': float(day_data['close']),
                    'high': float(day_data['high']),
                    'low': float(day_data['low']),
                    'pnl_percent': float(pnl_percent),
                    'max_profit_percent': float(max_profit),
                    'max_loss_percent': float(max_loss),
                    'volume': int(day_data['volume'])
                })
            
            # Calculate week-end performance
            if len(df) >= 5:
                last_day = df.iloc[4] if len(df) > 4 else df.iloc[-1]
                performance['week_end_price'] = float(last_day['close'])
                performance['week_end_pnl_percent'] = float(
                    ((entry_day['close'] - last_day['close']) / entry_day['close']) * 100
                )
                performance['week_end_date'] = last_day['date'].strftime('%Y-%m-%d')
            
            return performance
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def analyze_performance(self):
        """Analyze performance of all short signals"""
        # Load signals
        signals_df = self.load_signal_data()
        if signals_df.empty:
            self.logger.error("No signals found")
            return
        
        # Get ticker column - try different possible names
        ticker_col = None
        for col in ['Ticker', 'ticker', 'Symbol', 'symbol']:
            if col in signals_df.columns:
                ticker_col = col
                break
        
        if not ticker_col:
            self.logger.error("No ticker column found in signal file")
            return
        
        # Analyze each ticker
        performance_results = []
        successful_shorts = 0
        total_pnl = 0
        
        for idx, row in signals_df.iterrows():
            ticker = row[ticker_col]
            self.logger.info(f"Analyzing {ticker} ({idx+1}/{len(signals_df)})")
            
            performance = self.fetch_ticker_performance(ticker, self.signal_date)
            if performance:
                performance_results.append(performance)
                
                # Check if profitable
                if 'week_end_pnl_percent' in performance:
                    if performance['week_end_pnl_percent'] > 0:
                        successful_shorts += 1
                    total_pnl += performance['week_end_pnl_percent']
        
        # Create summary report
        self.create_performance_report(performance_results, signals_df, successful_shorts, total_pnl)
    
    def create_performance_report(self, performance_results: List[Dict], signals_df: pd.DataFrame, 
                                 successful_shorts: int, total_pnl: float):
        """Create detailed performance report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create Excel report
        output_file = os.path.join(self.results_dir, 
                                  f'Short_Performance_{self.signal_date.strftime("%Y%m%d")}_{timestamp}.xlsx')
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Signal Date', 'Total Signals', 'Analyzed Signals', 'Successful Shorts', 
                          'Success Rate %', 'Average PnL %', 'Total PnL %', 'Best Performer', 
                          'Worst Performer', 'Analysis Date'],
                'Value': [
                    self.signal_date.strftime('%Y-%m-%d'),
                    len(signals_df),
                    len(performance_results),
                    successful_shorts,
                    (successful_shorts / len(performance_results) * 100) if performance_results else 0,
                    total_pnl / len(performance_results) if performance_results else 0,
                    total_pnl,
                    max(performance_results, key=lambda x: x.get('week_end_pnl_percent', -999))['ticker'] if performance_results else 'N/A',
                    min(performance_results, key=lambda x: x.get('week_end_pnl_percent', 999))['ticker'] if performance_results else 'N/A',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Detailed performance sheet
            if performance_results:
                perf_data = []
                for perf in performance_results:
                    row = {
                        'Ticker': perf['ticker'],
                        'Entry Date': perf['entry_date'],
                        'Entry Price': perf['entry_price'],
                        'Week End Price': perf.get('week_end_price', 'N/A'),
                        'Week PnL %': perf.get('week_end_pnl_percent', 'N/A'),
                        'Day 1 PnL %': perf['daily_performance'][0]['pnl_percent'] if perf['daily_performance'] else 'N/A',
                        'Day 2 PnL %': perf['daily_performance'][1]['pnl_percent'] if len(perf['daily_performance']) > 1 else 'N/A',
                        'Day 3 PnL %': perf['daily_performance'][2]['pnl_percent'] if len(perf['daily_performance']) > 2 else 'N/A',
                        'Day 4 PnL %': perf['daily_performance'][3]['pnl_percent'] if len(perf['daily_performance']) > 3 else 'N/A',
                        'Day 5 PnL %': perf['daily_performance'][4]['pnl_percent'] if len(perf['daily_performance']) > 4 else 'N/A',
                        'Status': 'Profit' if perf.get('week_end_pnl_percent', 0) > 0 else 'Loss'
                    }
                    perf_data.append(row)
                
                perf_df = pd.DataFrame(perf_data)
                perf_df = perf_df.sort_values('Week PnL %', ascending=False)
                perf_df.to_excel(writer, sheet_name='Performance Details', index=False)
            
            # Original signals
            signals_df.to_excel(writer, sheet_name='Original Signals', index=False)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"SHORT REVERSAL PERFORMANCE ANALYSIS")
        print(f"Signal Date: {self.signal_date.strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"\nSUMMARY:")
        print(f"Total Signals: {len(signals_df)}")
        print(f"Analyzed: {len(performance_results)}")
        print(f"Successful Shorts: {successful_shorts}")
        print(f"Success Rate: {(successful_shorts / len(performance_results) * 100) if performance_results else 0:.2f}%")
        print(f"Average PnL: {total_pnl / len(performance_results) if performance_results else 0:.2f}%")
        print(f"Total PnL: {total_pnl:.2f}%")
        
        if performance_results:
            # Top performers
            sorted_results = sorted(performance_results, 
                                  key=lambda x: x.get('week_end_pnl_percent', -999), 
                                  reverse=True)
            
            print(f"\nTOP 5 PERFORMERS:")
            print(f"{'Ticker':<10} {'Entry':<10} {'Exit':<10} {'PnL %':<10}")
            print("-"*40)
            for perf in sorted_results[:5]:
                if 'week_end_pnl_percent' in perf:
                    print(f"{perf['ticker']:<10} {perf['entry_price']:<10.2f} "
                          f"{perf['week_end_price']:<10.2f} {perf['week_end_pnl_percent']:<10.2f}")
            
            print(f"\nBOTTOM 5 PERFORMERS:")
            print(f"{'Ticker':<10} {'Entry':<10} {'Exit':<10} {'PnL %':<10}")
            print("-"*40)
            for perf in sorted_results[-5:]:
                if 'week_end_pnl_percent' in perf:
                    print(f"{perf['ticker']:<10} {perf['entry_price']:<10.2f} "
                          f"{perf['week_end_price']:<10.2f} {perf['week_end_pnl_percent']:<10.2f}")
        
        print(f"\nFull report saved to: {output_file}")
        self.logger.info(f"Performance report created: {output_file}")

def main():
    """Main function"""
    # Use the file from July 22 when market breadth was 26.4%
    signal_file = "/Users/maverick/PycharmProjects/India-TS/Daily/results-s/Short_Reversal_Daily_20250722_110652.xlsx"
    
    print(f"Analyzing short reversal performance for: {signal_file}")
    print("Market Breadth: 26.4% bullish (73.6% bearish)")
    print("Signal Count: 14 long vs 39 short reversals")
    print("-" * 60)
    
    analyzer = ShortReversalPerformanceAnalyzer(signal_file, user_name='Sai')
    analyzer.analyze_performance()

if __name__ == "__main__":
    main()