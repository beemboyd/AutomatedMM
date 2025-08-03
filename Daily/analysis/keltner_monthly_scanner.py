#!/usr/bin/env python3
"""
Keltner Channel Monthly Scanner
Identifies tickers that have touched or crossed Keltner Channel upper/lower limits on monthly timeframe
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect
import configparser

class KeltnerMonthlyScanner:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the scanner"""
        self.user_name = user_name
        
        # Setup paths first
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keltner_monthly_results')
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Load tickers
        self.ticker_file = os.path.join(self.base_dir, 'Daily', 'data', 'Ticker.xlsx')
        self.tickers = self.load_tickers()
        
        # Keltner Channel parameters
        self.kc_period = 20  # Standard period for monthly
        self.kc_multiplier = 2.0  # Standard multiplier
        
        self.logger.info(f"Keltner Monthly Scanner initialized with {len(self.tickers)} tickers")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'keltner_monthly_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def initialize_kite_connection(self) -> KiteConnect:
        """Initialize Kite connection using config.ini"""
        try:
            # Load config
            config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"config.ini not found at {config_path}")
            
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Get user-specific API credentials
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            
            if not config.has_section(credential_section):
                raise ValueError(f"No credentials found for user {self.user_name}")
            
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            # Initialize Kite
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def load_tickers(self) -> List[str]:
        """Load tickers from Excel file"""
        try:
            df = pd.read_excel(self.ticker_file)
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].str.strip().dropna().tolist()
                self.logger.info(f"Loaded {len(tickers)} tickers from {self.ticker_file}")
                return tickers
            else:
                self.logger.error("No 'Ticker' column found in Excel file")
                return []
        except Exception as e:
            self.logger.error(f"Error loading tickers: {e}")
            return []
    
    def fetch_monthly_data(self, ticker: str, months: int = 36) -> pd.DataFrame:
        """Fetch monthly OHLC data for a ticker"""
        try:
            # Calculate date range (3 years of monthly data)
            to_date = datetime.now()
            from_date = to_date - timedelta(days=months * 30)
            
            # Fetch daily data first
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return pd.DataFrame()
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval='day'
            )
            
            if not historical_data:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Resample to monthly
            monthly_df = pd.DataFrame()
            monthly_df['open'] = df['open'].resample('M').first()
            monthly_df['high'] = df['high'].resample('M').max()
            monthly_df['low'] = df['low'].resample('M').min()
            monthly_df['close'] = df['close'].resample('M').last()
            monthly_df['volume'] = df['volume'].resample('M').sum()
            
            monthly_df.dropna(inplace=True)
            monthly_df.reset_index(inplace=True)
            
            return monthly_df
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
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
    
    def calculate_keltner_channels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Keltner Channels"""
        if df.empty or len(df) < self.kc_period:
            return df
        
        # Calculate True Range
        df['TR'] = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        
        # Calculate ATR
        df['ATR'] = df['TR'].rolling(window=self.kc_period).mean()
        
        # Calculate EMA of close
        df['EMA'] = df['close'].ewm(span=self.kc_period, adjust=False).mean()
        
        # Calculate Keltner Channels
        df['KC_Upper'] = df['EMA'] + (self.kc_multiplier * df['ATR'])
        df['KC_Lower'] = df['EMA'] - (self.kc_multiplier * df['ATR'])
        
        return df
    
    def analyze_keltner_touches(self, df: pd.DataFrame, ticker: str) -> Dict:
        """Analyze if price has touched or crossed Keltner limits"""
        if df.empty or 'KC_Upper' not in df.columns:
            return None
        
        # Check for upper limit touches/crosses
        df['touched_upper'] = (df['high'] >= df['KC_Upper']) | (df['close'] >= df['KC_Upper'])
        df['crossed_upper'] = df['close'] > df['KC_Upper']
        
        # Check for lower limit touches/crosses
        df['touched_lower'] = (df['low'] <= df['KC_Lower']) | (df['close'] <= df['KC_Lower'])
        df['crossed_lower'] = df['close'] < df['KC_Lower']
        
        # Get recent touches (last 12 months)
        recent_df = df.tail(12)
        
        # Find last touch dates
        upper_touches = df[df['touched_upper']]
        lower_touches = df[df['touched_lower']]
        
        result = {
            'ticker': ticker,
            'current_price': float(df.iloc[-1]['close']),
            'current_ema': float(df.iloc[-1]['EMA']),
            'current_kc_upper': float(df.iloc[-1]['KC_Upper']),
            'current_kc_lower': float(df.iloc[-1]['KC_Lower']),
            'distance_to_upper_pct': ((df.iloc[-1]['KC_Upper'] - df.iloc[-1]['close']) / df.iloc[-1]['close'] * 100),
            'distance_to_lower_pct': ((df.iloc[-1]['close'] - df.iloc[-1]['KC_Lower']) / df.iloc[-1]['close'] * 100),
            'upper_touches_total': len(upper_touches),
            'lower_touches_total': len(lower_touches),
            'upper_touches_recent': len(recent_df[recent_df['touched_upper']]),
            'lower_touches_recent': len(recent_df[recent_df['touched_lower']]),
            'last_upper_touch': upper_touches.iloc[-1]['date'].strftime('%Y-%m-%d') if len(upper_touches) > 0 else None,
            'last_lower_touch': lower_touches.iloc[-1]['date'].strftime('%Y-%m-%d') if len(lower_touches) > 0 else None,
            'currently_above_upper': bool(df.iloc[-1]['crossed_upper']),
            'currently_below_lower': bool(df.iloc[-1]['crossed_lower'])
        }
        
        return result
    
    def run_scan(self):
        """Run the Keltner Channel monthly scan"""
        self.logger.info("Starting Keltner Channel monthly scan...")
        
        upper_limit_touches = []
        lower_limit_touches = []
        all_results = []
        
        for i, ticker in enumerate(self.tickers, 1):
            if i % 10 == 0:
                self.logger.info(f"Processing {i}/{len(self.tickers)}: {ticker}")
            
            try:
                # Fetch monthly data
                df = self.fetch_monthly_data(ticker)
                if df.empty:
                    continue
                
                # Calculate Keltner Channels
                df = self.calculate_keltner_channels(df)
                
                # Analyze touches
                result = self.analyze_keltner_touches(df, ticker)
                if result:
                    all_results.append(result)
                    
                    # Categorize based on recent activity
                    if result['upper_touches_recent'] > 0 or result['currently_above_upper']:
                        upper_limit_touches.append(result)
                    
                    if result['lower_touches_recent'] > 0 or result['currently_below_lower']:
                        lower_limit_touches.append(result)
                
            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                continue
        
        # Sort results
        upper_limit_touches.sort(key=lambda x: x['distance_to_upper_pct'])
        lower_limit_touches.sort(key=lambda x: x['distance_to_lower_pct'])
        
        # Save results
        self.save_results(upper_limit_touches, lower_limit_touches, all_results)
        
        return upper_limit_touches, lower_limit_touches
    
    def save_results(self, upper_touches: List[Dict], lower_touches: List[Dict], all_results: List[Dict]):
        """Save scan results to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save upper limit touches
        if upper_touches:
            upper_df = pd.DataFrame(upper_touches)
            upper_file = os.path.join(self.results_dir, f'keltner_upper_touches_{timestamp}.xlsx')
            upper_df.to_excel(upper_file, index=False)
            self.logger.info(f"Saved {len(upper_touches)} upper limit touches to {upper_file}")
        
        # Save lower limit touches
        if lower_touches:
            lower_df = pd.DataFrame(lower_touches)
            lower_file = os.path.join(self.results_dir, f'keltner_lower_touches_{timestamp}.xlsx')
            lower_df.to_excel(lower_file, index=False)
            self.logger.info(f"Saved {len(lower_touches)} lower limit touches to {lower_file}")
        
        # Save all results
        if all_results:
            all_df = pd.DataFrame(all_results)
            all_file = os.path.join(self.results_dir, f'keltner_all_results_{timestamp}.xlsx')
            all_df.to_excel(all_file, index=False)
            
            # Also save as JSON for easy reading
            json_file = os.path.join(self.results_dir, f'keltner_summary_{timestamp}.json')
            summary = {
                'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_tickers_scanned': len(self.tickers),
                'total_analyzed': len(all_results),
                'upper_limit_touches': len(upper_touches),
                'lower_limit_touches': len(lower_touches),
                'upper_limit_tickers': [t['ticker'] for t in upper_touches[:20]],  # Top 20
                'lower_limit_tickers': [t['ticker'] for t in lower_touches[:20]]   # Top 20
            }
            
            with open(json_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            self.logger.info(f"Saved summary to {json_file}")
    
    def generate_report(self, upper_touches: List[Dict], lower_touches: List[Dict]):
        """Generate a summary report"""
        print("\n" + "="*60)
        print("KELTNER CHANNEL MONTHLY ANALYSIS REPORT")
        print("="*60)
        print(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tickers Scanned: {len(self.tickers)}")
        print("\n")
        
        print("UPPER LIMIT TOUCHES (Recent 12 months)")
        print("-"*60)
        if upper_touches:
            print(f"Total: {len(upper_touches)} tickers")
            print("\nTop 10 - Closest to Upper Limit:")
            print(f"{'Ticker':<10} {'Price':<10} {'Upper KC':<10} {'Distance':<10} {'Last Touch':<12}")
            print("-"*60)
            for t in upper_touches[:10]:
                print(f"{t['ticker']:<10} {t['current_price']:<10.2f} {t['current_kc_upper']:<10.2f} "
                      f"{t['distance_to_upper_pct']:<10.2f}% {t['last_upper_touch'] or 'Never':<12}")
        else:
            print("No tickers touched upper limit recently")
        
        print("\n")
        print("LOWER LIMIT TOUCHES (Recent 12 months)")
        print("-"*60)
        if lower_touches:
            print(f"Total: {len(lower_touches)} tickers")
            print("\nTop 10 - Closest to Lower Limit:")
            print(f"{'Ticker':<10} {'Price':<10} {'Lower KC':<10} {'Distance':<10} {'Last Touch':<12}")
            print("-"*60)
            for t in lower_touches[:10]:
                print(f"{t['ticker']:<10} {t['current_price']:<10.2f} {t['current_kc_lower']:<10.2f} "
                      f"{t['distance_to_lower_pct']:<10.2f}% {t['last_lower_touch'] or 'Never':<12}")
        else:
            print("No tickers touched lower limit recently")
        
        print("\n" + "="*60)

def main():
    """Main function"""
    print("Starting Keltner Channel Monthly Scanner...")
    print("This will analyze monthly Keltner Channel touches for all tickers")
    print("-" * 60)
    
    scanner = KeltnerMonthlyScanner(user_name='Sai')
    
    # Run scan
    upper_touches, lower_touches = scanner.run_scan()
    
    # Generate report
    scanner.generate_report(upper_touches, lower_touches)
    
    print(f"\nResults saved in: {scanner.results_dir}")

if __name__ == "__main__":
    main()