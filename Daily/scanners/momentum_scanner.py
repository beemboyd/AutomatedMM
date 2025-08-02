#!/usr/bin/env python3
"""
Momentum Scanner Module
Analyzes daily and weekly momentum for Indian stocks using EMA crossover strategy
Runs daily at 4 PM IST
"""

import os
import sys
import numpy as np
import pandas as pd
import datetime
from datetime import timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import required modules
from Daily.scanners.VSR_Momentum_Scanner import (
    load_daily_config,
    initialize_kite,
    fetch_data_kite
)
from kiteconnect import KiteConnect

# Global kite variable
kite = None

class MomentumScanner:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the momentum scanner"""
        self.user_name = user_name
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Set global kite for fetch_data_kite
        global kite
        kite = self.kite
        
        # Setup paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.momentum_dir = os.path.join(self.base_dir, 'Daily', 'Momentum')
        os.makedirs(self.momentum_dir, exist_ok=True)
        
        # Load tickers
        self.ticker_file = os.path.join(self.base_dir, 'Daily', 'data', 'Ticker.xlsx')
        self.tickers = self.load_tickers()
        
        self.logger.info(f"Momentum Scanner initialized with {len(self.tickers)} tickers")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'momentum_scanner')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'momentum_scanner_{datetime.datetime.now().strftime("%Y%m%d")}.log')
        
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
        """Initialize Kite connection using config"""
        try:
            # Load config
            config = load_daily_config(self.user_name)
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            
            # Get credentials
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
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators (EMAs, WM, ATR, Slope, etc.)"""
        # Normalize column names to lowercase
        data.columns = data.columns.str.lower()
        
        if 'close' not in data.columns or data.empty:
            return pd.DataFrame()
        
        # Calculate various EMAs
        data['EMA_5'] = data['close'].ewm(span=5, adjust=False).mean()
        data['EMA_8'] = data['close'].ewm(span=8, adjust=False).mean()
        data['EMA_13'] = data['close'].ewm(span=13, adjust=False).mean()
        data['EMA_21'] = data['close'].ewm(span=21, adjust=False).mean()
        data['EMA_50'] = data['close'].ewm(span=50, adjust=False).mean()
        data['EMA_100'] = data['close'].ewm(span=100, adjust=False).mean()
        
        # Calculate WM (Weighted Momentum) and its EMA
        data['WM'] = ((data['EMA_5'] - data['EMA_8']) +
                      (data['EMA_8'] - data['EMA_13']) +
                      (data['EMA_13'] - data['EMA_21']) +
                      (data['EMA_21'] - data['EMA_50'])) / 4
        
        # Only keep positive WM values
        data['WM'] = data['WM'].apply(lambda x: x if x > 0 else np.nan)
        data['EMA_WM'] = data['WM'].ewm(span=5, adjust=False).mean()
        data['WCross'] = np.where((data['WM'] > data['EMA_WM']) & (data['WM'] > 0), 'Yes', 'No')
        
        # Gap column: difference between WM and EMA_WM
        data['Gap'] = data['WM'] - data['EMA_WM']
        
        # Calculate price gap percentage from previous close to current open
        data['price_gap'] = (data['open'] - data['close'].shift(1)) / data['close'].shift(1) * 100
        data['MaxGap'] = data['price_gap'].rolling(window=100).max()
        
        # True Range (TR) and ATR (20-period rolling mean)
        prev_close = data['close'].shift(1)
        tr1 = data['high'] - data['low']
        tr2 = (data['high'] - prev_close).abs()
        tr3 = (data['low'] - prev_close).abs()
        data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['ATR'] = data['TR'].rolling(window=20).mean()
        
        # Slope: rolling linear regression of Close (over 8 periods) as a percentage
        data['Slope'] = data['close'].rolling(window=8).apply(
            lambda y: (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1] * 100) if len(y) > 0 and y[-1] != 0 else np.nan,
            raw=True
        )
        
        # R: Pearson correlation coefficient between time index and Close
        data['R'] = data['close'].rolling(window=8).apply(
            lambda y: np.corrcoef(np.arange(len(y)), y)[0, 1] if len(y) > 1 else np.nan,
            raw=True
        )
        
        # Additional calculations
        data['Beta'] = None  # Can be calculated if market index data is available
        data['PosSize'] = None
        data['SL1'] = None
        data['SL2'] = None
        
        return data
    
    def fetch_ticker_data(self, ticker: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch historical data for a ticker"""
        try:
            # Calculate date range
            to_date = datetime.datetime.now()
            from_date = to_date - timedelta(days=days)
            
            # Fetch data using existing function
            data = fetch_data_kite(
                ticker,
                interval,
                from_date.strftime('%Y-%m-%d %H:%M:%S'),
                to_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if data is not None and not data.empty:
                data['Ticker'] = ticker
                return data
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def analyze_timeframe(self, ticker: str, interval: str, days: int) -> Optional[Dict]:
        """Analyze a single timeframe for a ticker"""
        try:
            # Fetch data
            data = self.fetch_ticker_data(ticker, interval, days)
            if data is None or data.empty:
                return None
            
            # Calculate indicators
            data = self.calculate_indicators(data)
            if data.empty:
                return None
            
            # Get the latest data
            latest_data = data.iloc[-1]
            current_price = float(latest_data['close'])
            
            # Check EMA_100 condition - price must be above EMA_100
            if 'EMA_100' in latest_data and not pd.isna(latest_data['EMA_100']):
                if current_price < float(latest_data['EMA_100']):
                    return None
            
            # Check slope condition - must be positive
            if 'Slope' in latest_data:
                slope_val = latest_data['Slope']
                if pd.isna(slope_val) or float(slope_val) < 0:
                    return None
            
            # Get WCross information
            wcross_date = None
            wcross_value = None
            
            if 'WCross' in data.columns:
                # Find when the most recent crossover started
                wcross_changes = data.loc[(data['WCross'].shift(1) != data['WCross']) & 
                                         (data['WCross'] == 'Yes')]
                
                if not wcross_changes.empty:
                    wcross_date = wcross_changes.iloc[-1]['date']
                    wcross_value = float(wcross_changes.iloc[-1]['close'])
            
            # Return data for ALL tickers that meet the basic criteria (price > EMA_100, positive slope)
            return {
                'Ticker': ticker,
                'Date': latest_data['date'],
                'Close': current_price,
                'Slope': float(latest_data['Slope']) if not pd.isna(latest_data['Slope']) else None,
                'R': float(latest_data['R']) if not pd.isna(latest_data['R']) else None,
                'WCross': latest_data.get('WCross', 'No'),
                'Gap': float(latest_data['Gap']) if not pd.isna(latest_data['Gap']) else None,
                'Beta': latest_data.get('Beta'),
                'MaxGap': float(latest_data['MaxGap']) if not pd.isna(latest_data['MaxGap']) else None,
                'ATR': float(latest_data['ATR']) if not pd.isna(latest_data['ATR']) else None,
                'PosSize': latest_data.get('PosSize'),
                'SL1': latest_data.get('SL1'),
                'SL2': latest_data.get('SL2'),
                'Current_Close': current_price,
                'WCross_Date': wcross_date,
                'WCross_Value': wcross_value,
                'WM': float(latest_data['WM']) if not pd.isna(latest_data['WM']) else None,
                'EMA_5': float(latest_data['EMA_5']) if not pd.isna(latest_data['EMA_5']) else None,
                'EMA_100': float(latest_data['EMA_100']) if not pd.isna(latest_data['EMA_100']) else None
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {ticker} for {interval}: {e}")
            return None
    
    def run_scan(self, scan_date: Optional[datetime.datetime] = None) -> Dict[str, pd.DataFrame]:
        """Run the momentum scan for all tickers"""
        if scan_date is None:
            scan_date = datetime.datetime.now()
        
        self.logger.info(f"Starting momentum scan for {scan_date.strftime('%Y-%m-%d')}")
        
        # Results storage
        results = {
            'Daily': [],
            'Weekly': []
        }
        
        # Timeframe configurations
        timeframes = {
            'Daily': {'interval': 'day', 'days': 365},  # 1 year of daily data
            'Weekly': {'interval': 'week', 'days': 1825}  # 5 years of weekly data
        }
        
        # Process each ticker
        for i, ticker in enumerate(self.tickers, 1):
            if i % 10 == 0:
                self.logger.info(f"Processing ticker {i}/{len(self.tickers)}: {ticker}")
            
            for timeframe, config in timeframes.items():
                result = self.analyze_timeframe(ticker, config['interval'], config['days'])
                if result:
                    results[timeframe].append(result)
        
        # Convert to DataFrames and sort
        dataframes = {}
        for timeframe, data in results.items():
            if data:
                df = pd.DataFrame(data)
                # Sort by WM (Weighted Momentum) if available, else by Slope
                if 'WM' in df.columns and not df['WM'].isna().all():
                    df = df.sort_values('WM', ascending=False)
                elif 'Slope' in df.columns and not df['Slope'].isna().all():
                    df = df.sort_values('Slope', ascending=False)
                dataframes[timeframe] = df
                self.logger.info(f"{timeframe}: Found {len(df)} tickers with positive momentum")
            else:
                dataframes[timeframe] = pd.DataFrame()
                self.logger.info(f"{timeframe}: No tickers found with positive momentum")
        
        # Save results
        self.save_results(dataframes, scan_date)
        
        return dataframes
    
    def save_results(self, dataframes: Dict[str, pd.DataFrame], scan_date: datetime.datetime):
        """Save results to Excel file"""
        try:
            # Create filename
            filename = f"India-Momentum_Report_{scan_date.strftime('%Y%m%d')}_{scan_date.strftime('%H%M%S')}.xlsx"
            filepath = os.path.join(self.momentum_dir, filename)
            
            # Write to Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Write data sheets
                for timeframe, df in dataframes.items():
                    if not df.empty:
                        df.to_excel(writer, sheet_name=f"{timeframe}_Summary", index=False)
                
                # Add Count Summary sheet
                count_summary_data = {
                    'Metric': ['Total Tickers Analyzed', 'Daily Momentum Count', 'Weekly Momentum Count', 
                               'Both Daily & Weekly', 'Daily Only', 'Weekly Only'],
                    'Count': [
                        len(self.tickers),
                        len(dataframes.get('Daily', [])),
                        len(dataframes.get('Weekly', [])),
                        0,  # Will calculate below
                        0,  # Will calculate below
                        0   # Will calculate below
                    ]
                }
                
                # Calculate overlap
                if 'Daily' in dataframes and 'Weekly' in dataframes and not dataframes['Daily'].empty and not dataframes['Weekly'].empty:
                    daily_tickers = set(dataframes['Daily']['Ticker'].tolist())
                    weekly_tickers = set(dataframes['Weekly']['Ticker'].tolist())
                    both = daily_tickers.intersection(weekly_tickers)
                    daily_only = daily_tickers - weekly_tickers
                    weekly_only = weekly_tickers - daily_tickers
                    
                    count_summary_data['Count'][3] = len(both)
                    count_summary_data['Count'][4] = len(daily_only)
                    count_summary_data['Count'][5] = len(weekly_only)
                
                count_df = pd.DataFrame(count_summary_data)
                count_df.to_excel(writer, sheet_name="Count_Summary", index=False)
                
                # Add detailed summary sheet
                summary_data = {
                    'Timeframe': [],
                    'Count': [],
                    'Top_Ticker': [],
                    'Top_WM': [],
                    'Top_Slope': [],
                    'Avg_WM': [],
                    'Avg_Slope': []
                }
                
                for timeframe, df in dataframes.items():
                    summary_data['Timeframe'].append(timeframe)
                    summary_data['Count'].append(len(df))
                    if not df.empty:
                        summary_data['Top_Ticker'].append(df.iloc[0]['Ticker'])
                        summary_data['Top_WM'].append(df.iloc[0]['WM'] if 'WM' in df.columns else None)
                        summary_data['Top_Slope'].append(df.iloc[0]['Slope'] if 'Slope' in df.columns else None)
                        summary_data['Avg_WM'].append(df['WM'].mean() if 'WM' in df.columns else None)
                        summary_data['Avg_Slope'].append(df['Slope'].mean() if 'Slope' in df.columns else None)
                    else:
                        summary_data['Top_Ticker'].append(None)
                        summary_data['Top_WM'].append(None)
                        summary_data['Top_Slope'].append(None)
                        summary_data['Avg_WM'].append(None)
                        summary_data['Avg_Slope'].append(None)
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name="Summary", index=False)
            
            self.logger.info(f"Results saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
    
    def get_counts_for_date(self, target_date: datetime.datetime) -> Dict:
        """Get momentum counts for a specific date"""
        try:
            # Look for file from that date
            date_str = target_date.strftime('%Y%m%d')
            files = [f for f in os.listdir(self.momentum_dir) 
                    if f.startswith(f"India-Momentum_Report_{date_str}")]
            
            if not files:
                self.logger.warning(f"No momentum report found for {date_str}")
                return {'Daily': 0, 'Weekly': 0, 'tickers': {'Daily': [], 'Weekly': []}}
            
            # Use the latest file from that date
            latest_file = sorted(files)[-1]
            filepath = os.path.join(self.momentum_dir, latest_file)
            
            # Read the Excel file
            counts = {'Daily': 0, 'Weekly': 0}
            tickers = {'Daily': [], 'Weekly': []}
            
            xls = pd.ExcelFile(filepath)
            for sheet in xls.sheet_names:
                if 'Daily_Summary' in sheet:
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    counts['Daily'] = len(df)
                    tickers['Daily'] = df['Ticker'].tolist() if 'Ticker' in df.columns else []
                elif 'Weekly_Summary' in sheet:
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    counts['Weekly'] = len(df)
                    tickers['Weekly'] = df['Ticker'].tolist() if 'Ticker' in df.columns else []
            
            return {**counts, 'tickers': tickers}
            
        except Exception as e:
            self.logger.error(f"Error getting counts for date {target_date}: {e}")
            return {'Daily': 0, 'Weekly': 0, 'tickers': {'Daily': [], 'Weekly': []}}


def main():
    """Main function to run the scanner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Momentum Scanner for Indian Markets')
    parser.add_argument('--date', type=str, help='Date to scan (YYYY-MM-DD format)')
    parser.add_argument('--user', type=str, default='Sai', help='User name for API credentials')
    parser.add_argument('--test', action='store_true', help='Run in test mode with limited tickers')
    
    args = parser.parse_args()
    
    # Parse date if provided
    scan_date = None
    if args.date:
        try:
            scan_date = datetime.datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid date format: {args.date}. Using current date.")
    
    # Create and run scanner
    scanner = MomentumScanner(user_name=args.user)
    
    # Limit tickers in test mode
    if args.test:
        scanner.tickers = scanner.tickers[:10]  # Only process first 10 tickers
        scanner.logger.info("Running in TEST MODE with 10 tickers")
    
    results = scanner.run_scan(scan_date)
    
    # Print summary
    print("\n" + "="*50)
    print("MOMENTUM SCAN SUMMARY")
    print("="*50)
    for timeframe, df in results.items():
        print(f"\n{timeframe}: {len(df)} tickers with positive momentum")
        if not df.empty and len(df) > 0:
            print(f"Top 5 by momentum:")
            for i, row in df.head(5).iterrows():
                ticker = row['Ticker']
                wm = row['WM'] if 'WM' in row and not pd.isna(row['WM']) else 0
                slope = row['Slope'] if 'Slope' in row and not pd.isna(row['Slope']) else 0
                print(f"  {ticker}: WM={wm:.2f}, Slope={slope:.2f}%")


if __name__ == '__main__':
    main()