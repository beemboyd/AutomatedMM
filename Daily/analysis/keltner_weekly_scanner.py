#!/usr/bin/env python3
"""
Keltner Channel Weekly Scanner
Identifies tickers that touched or crossed Keltner Channel limits in the current week
Outputs a simple Excel report with Long and Short tabs
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

class KeltnerWeeklyScanner:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the scanner"""
        self.user_name = user_name
        
        # Setup paths first
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Setup paths
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keltner_weekly_results')
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Load tickers
        self.ticker_file = os.path.join(self.base_dir, 'Daily', 'data', 'Ticker.xlsx')
        self.tickers = self.load_tickers()
        
        # Keltner Channel parameters (standard for weekly)
        self.kc_period = 20  # 20 weeks
        self.kc_multiplier = 2.0  # Standard multiplier
        
        self.logger.info(f"Keltner Weekly Scanner initialized with {len(self.tickers)} tickers")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'keltner_weekly_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
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
    
    def fetch_weekly_data(self, ticker: str, weeks: int = 104) -> pd.DataFrame:
        """Fetch weekly OHLC data for a ticker"""
        try:
            # Calculate date range (2 years of data to calculate KC properly)
            to_date = datetime.now()
            from_date = to_date - timedelta(weeks=weeks)
            
            # Get instrument token
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return pd.DataFrame()
            
            # Fetch daily data
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
            
            # Resample to weekly (week ending on Friday)
            weekly_df = pd.DataFrame()
            weekly_df['open'] = df['open'].resample('W-FRI').first()
            weekly_df['high'] = df['high'].resample('W-FRI').max()
            weekly_df['low'] = df['low'].resample('W-FRI').min()
            weekly_df['close'] = df['close'].resample('W-FRI').last()
            weekly_df['volume'] = df['volume'].resample('W-FRI').sum()
            
            weekly_df.dropna(inplace=True)
            weekly_df.reset_index(inplace=True)
            
            return weekly_df
            
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
    
    def analyze_current_week_touches(self, df: pd.DataFrame, ticker: str) -> Dict:
        """Check if ticker touched or crossed KC limits in current week"""
        if df.empty or 'KC_Upper' not in df.columns:
            return None
        
        # Get current week data (last row should be current/latest week)
        if len(df) == 0:
            return None
            
        latest = df.iloc[-1]
        
        # Check if the latest week is actually current week
        latest_date = pd.to_datetime(latest['date'])
        # Remove timezone info if present
        if latest_date.tz is not None:
            latest_date = latest_date.tz_localize(None)
        current_date = datetime.now()
        
        # If latest data is more than 7 days old, skip
        if (current_date - latest_date).days > 7:
            return None
        
        # Check if high touched or crossed upper KC
        touched_upper = latest['high'] >= latest['KC_Upper']
        crossed_upper = latest['close'] > latest['KC_Upper']
        
        # Check if low touched or crossed lower KC
        touched_lower = latest['low'] <= latest['KC_Lower']
        crossed_lower = latest['close'] < latest['KC_Lower']
        
        # Only return if there was a touch/cross
        if not (touched_upper or touched_lower):
            return None
        
        result = {
            'Ticker': ticker,
            'Week_Ending': latest['date'].strftime('%Y-%m-%d'),
            'Current_Price': float(latest['close']),
            'High': float(latest['high']),
            'Low': float(latest['low']),
            'KC_Upper': float(latest['KC_Upper']),
            'KC_Lower': float(latest['KC_Lower']),
            'EMA': float(latest['EMA']),
            'ATR': float(latest['ATR']),
            'Touched_Upper': touched_upper,
            'Crossed_Upper': crossed_upper,
            'Touched_Lower': touched_lower,
            'Crossed_Lower': crossed_lower,
            'Upper_Penetration%': ((latest['high'] - latest['KC_Upper']) / latest['KC_Upper'] * 100) if touched_upper else 0,
            'Lower_Penetration%': ((latest['KC_Lower'] - latest['low']) / latest['KC_Lower'] * 100) if touched_lower else 0
        }
        
        return result
    
    def run_scan(self):
        """Run the Keltner Channel weekly scan"""
        self.logger.info("Starting Keltner Channel weekly scan...")
        
        long_candidates = []  # Touched/crossed upper limit
        short_candidates = []  # Touched/crossed lower limit
        
        for i, ticker in enumerate(self.tickers, 1):
            if i % 50 == 0:
                self.logger.info(f"Processing {i}/{len(self.tickers)}: {ticker}")
            
            try:
                # Fetch weekly data
                df = self.fetch_weekly_data(ticker)
                if df.empty:
                    continue
                
                # Calculate Keltner Channels
                df = self.calculate_keltner_channels(df)
                
                # Analyze current week
                result = self.analyze_current_week_touches(df, ticker)
                if result:
                    if result['Touched_Upper']:
                        long_candidates.append(result)
                    if result['Touched_Lower']:
                        short_candidates.append(result)
                
            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                continue
        
        # Sort by penetration percentage
        long_candidates.sort(key=lambda x: x['Upper_Penetration%'], reverse=True)
        short_candidates.sort(key=lambda x: x['Lower_Penetration%'], reverse=True)
        
        # Save results
        self.save_results(long_candidates, short_candidates)
        
        return long_candidates, short_candidates
    
    def save_results(self, long_candidates: List[Dict], short_candidates: List[Dict]):
        """Save scan results to Excel with Long and Short tabs"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.results_dir, f'KC_Weekly_Current_{timestamp}.xlsx')
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Long tab - Upper limit touches
            if long_candidates:
                long_df = pd.DataFrame(long_candidates)
                # Select and reorder columns for clarity
                long_cols = ['Ticker', 'Week_Ending', 'Current_Price', 'High', 'KC_Upper', 
                           'Upper_Penetration%', 'Touched_Upper', 'Crossed_Upper', 'EMA', 'ATR']
                long_df = long_df[long_cols]
                long_df.to_excel(writer, sheet_name='Long', index=False)
                
                # Format the sheet
                worksheet = writer.sheets['Long']
                for column in worksheet.columns:
                    max_length = max(len(str(cell.value)) for cell in column)
                    worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 15)
            
            # Short tab - Lower limit touches
            if short_candidates:
                short_df = pd.DataFrame(short_candidates)
                # Select and reorder columns for clarity
                short_cols = ['Ticker', 'Week_Ending', 'Current_Price', 'Low', 'KC_Lower', 
                            'Lower_Penetration%', 'Touched_Lower', 'Crossed_Lower', 'EMA', 'ATR']
                short_df = short_df[short_cols]
                short_df.to_excel(writer, sheet_name='Short', index=False)
                
                # Format the sheet
                worksheet = writer.sheets['Short']
                for column in worksheet.columns:
                    max_length = max(len(str(cell.value)) for cell in column)
                    worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 15)
        
        self.logger.info(f"Results saved to {output_file}")
        self.logger.info(f"Long candidates: {len(long_candidates)}")
        self.logger.info(f"Short candidates: {len(short_candidates)}")
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"KELTNER CHANNEL WEEKLY ANALYSIS - Week ending {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"\nLONG CANDIDATES (Touched/Crossed Upper KC): {len(long_candidates)} tickers")
        if long_candidates:
            print(f"{'Ticker':<10} {'Price':<10} {'KC Upper':<10} {'Penetration%':<12} {'Status':<10}")
            print("-"*60)
            for candidate in long_candidates[:10]:  # Top 10
                status = "Crossed" if candidate['Crossed_Upper'] else "Touched"
                print(f"{candidate['Ticker']:<10} {candidate['Current_Price']:<10.2f} "
                      f"{candidate['KC_Upper']:<10.2f} {candidate['Upper_Penetration%']:<12.2f} {status:<10}")
        
        print(f"\nSHORT CANDIDATES (Touched/Crossed Lower KC): {len(short_candidates)} tickers")
        if short_candidates:
            print(f"{'Ticker':<10} {'Price':<10} {'KC Lower':<10} {'Penetration%':<12} {'Status':<10}")
            print("-"*60)
            for candidate in short_candidates[:10]:  # Top 10
                status = "Crossed" if candidate['Crossed_Lower'] else "Touched"
                print(f"{candidate['Ticker']:<10} {candidate['Current_Price']:<10.2f} "
                      f"{candidate['KC_Lower']:<10.2f} {candidate['Lower_Penetration%']:<12.2f} {status:<10}")
        
        print(f"\nFull results saved to: {output_file}")

def main():
    """Main function"""
    print("Starting Keltner Channel Weekly Scanner...")
    print("Analyzing weekly timeframe for current week touches/crosses")
    print("-" * 60)
    
    scanner = KeltnerWeeklyScanner(user_name='Sai')
    
    # Run scan
    long_candidates, short_candidates = scanner.run_scan()

if __name__ == "__main__":
    main()