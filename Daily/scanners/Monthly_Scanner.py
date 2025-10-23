#!/usr/bin/env python3
"""
Keltner Channel Upper Breakout and Monthly Long Reversal Scanner for NSE Stocks
Shows stocks at/above KC upper limit and monthly timeframe long reversals
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import warnings
import argparse
import configparser
import time
from kiteconnect import KiteConnect
from threading import Semaphore
warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Monthly KC Upper Breakout and Long Reversal Scanner for NSE Stocks")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

    if not os.path.exists(config_path):
        logger.error(f"config.ini file not found at {config_path}")
        raise FileNotFoundError(f"config.ini file not found at {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        logger.error(f"No credentials found for user {user_name} in {config_path}")
        raise ValueError(f"No credentials found for user {user_name}")

    return config

class KCMonthlyBreakoutScanner:
    """Scanner for detecting KC upper breakouts and monthly long reversals in NSE stocks"""

    def __init__(self, user_name="Sai"):
        """Initialize scanner with Kite API"""
        # Setup timezone for IST
        self.ist = pytz.timezone('Asia/Kolkata')
        self.current_time = datetime.now(self.ist)

        # Load configuration
        self.config = load_daily_config(user_name)
        self.credential_section = f'API_CREDENTIALS_{user_name}'

        # Initialize Kite Connect
        self.api_key = self.config.get(self.credential_section, 'api_key')
        self.access_token = self.config.get(self.credential_section, 'access_token')

        if not self.api_key or not self.access_token:
            logger.error(f"Missing API credentials for user {user_name}. Please check config.ini")
            raise ValueError(f"API key or access token missing for user {user_name}")

        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        logger.info(f"Successfully initialized Kite Connect for user {user_name}")

        # Results storage - separate sections
        self.kc_breakout_results = []
        self.monthly_reversal_results = []
        self.results_lock = threading.Lock()

        # Sector mapping
        self.sector_map = {}

        # Cache for instruments
        self.instruments_df = None

        # Rate limiting for API calls (3 requests per second)
        self.api_semaphore = Semaphore(1)  # Serialize API calls
        self.last_api_call = 0
        self.min_api_interval = 0.35  # ~3 requests per second

        # Threading configuration - reduce threads to avoid rate limit
        try:
            self.max_workers = int(self.config.get('SCANNER', 'max_threads', fallback=2))
        except:
            self.max_workers = 2  # Default to 2 threads to respect API limits

    def get_tradeable_universe(self) -> List[str]:
        """Get list of NSE stocks from Ticker_with_Sector.xlsx file"""
        try:
            # Read ticker file from Excel
            excel_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data', 'Ticker_with_Sector.xlsx'
            )

            if not os.path.exists(excel_path):
                logger.error(f"Ticker file not found: {excel_path}")
                return self.get_fallback_universe()

            # Read Excel file
            df = pd.read_excel(excel_path)

            # Get ticker and sector columns
            if 'Symbol' not in df.columns:
                logger.error("Symbol column not found in file")
                return self.get_fallback_universe()

            # Build sector mapping if Sector column exists
            if 'Sector' in df.columns:
                for _, row in df.iterrows():
                    if pd.notna(row['Symbol']) and pd.notna(row['Sector']):
                        symbol = str(row['Symbol']).strip().replace('\ufeff', '')
                        sector = str(row['Sector']).strip()
                        # Use the symbol as key for sector mapping
                        self.sector_map[symbol] = sector
                logger.info(f"Loaded sector information for {len(self.sector_map)} stocks")

            # Get symbol list
            symbols = df['Symbol'].tolist()

            # Clean symbols - remove any NaN, special characters, and strip whitespace
            universe = []
            for sym in symbols:
                if pd.notna(sym) and isinstance(sym, str):
                    # Strip BOM and whitespace
                    clean_sym = sym.strip().replace('\ufeff', '')
                    # Keep NSE symbols with format like TICKER.NSE
                    if clean_sym and '.NSE' in clean_sym:
                        universe.append(clean_sym)

            logger.info(f"Loaded {len(universe)} NSE stocks from Excel file")

            # Optionally limit to configured max stocks
            try:
                max_stocks = int(self.config.get('SCANNER', 'MAX_STOCKS', fallback=len(universe)))
            except:
                max_stocks = len(universe)  # Use all stocks
            return universe[:max_stocks]

        except Exception as e:
            logger.error(f"Error loading NSE stocks universe: {e}")
            return self.get_fallback_universe()

    def get_fallback_universe(self) -> List[str]:
        """Fallback list of liquid NSE stocks"""
        return ['RELIANCE.NSE', 'TCS.NSE', 'HDFCBANK.NSE', 'INFY.NSE', 'ICICIBANK.NSE',
                'HINDUNILVR.NSE', 'ITC.NSE', 'SBIN.NSE', 'BHARTIARTL.NSE', 'KOTAKBANK.NSE',
                'BAJFINANCE.NSE', 'LT.NSE', 'WIPRO.NSE', 'ASIANPAINT.NSE', 'AXISBANK.NSE']

    def calculate_keltner_channels(self, df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Keltner Channels matching TradingView Pine Script settings
        - EMA period: 20
        - ATR period: 10
        - Multiplier: 2.0
        """
        try:
            # Calculate EMA for middle band (20 period)
            middle_band = df['Close'].ewm(span=ema_period, adjust=False).mean()

            # Calculate ATR with 10 period (matching Pine Script)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())

            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=atr_period).mean()  # Using 10 period ATR

            # Calculate bands with 2x multiplier
            upper_band = middle_band + (multiplier * atr)
            lower_band = middle_band - (multiplier * atr)

            return upper_band, middle_band, lower_band
        except Exception as e:
            logger.error(f"Error calculating Keltner Channels: {e}")
            return None, None, None

    def check_kc_breakout(self, symbol: str, df_daily: pd.DataFrame) -> Dict:
        """Check if stock is at or above KC upper limit on MONTHLY timeframe"""
        try:
            if len(df_daily) < 400:  # Need enough data for monthly resampling
                return None

            # Ensure Date is the index for resampling
            if 'Date' in df_daily.columns:
                df_daily = df_daily.copy()
                df_daily['Date'] = pd.to_datetime(df_daily['Date'])
                df_daily.set_index('Date', inplace=True)

            # Resample daily data to monthly timeframe
            df_monthly = df_daily.resample('M').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

            if len(df_monthly) < 20:  # Need at least 20 months for EMA
                return None

            # Calculate Keltner Channels on monthly data
            upper_band, middle_band, lower_band = self.calculate_keltner_channels(df_monthly)
            if upper_band is None:
                return None

            # Get latest values (from monthly data)
            latest_monthly_close = df_monthly['Close'].iloc[-1]
            latest_upper = upper_band.iloc[-1]
            latest_middle = middle_band.iloc[-1]
            latest_monthly_volume = df_monthly['Volume'].iloc[-1]

            # Use the latest daily close for real-time price
            latest_daily_price = df_daily['Close'].iloc[-1]

            # Check if current daily price is at or above monthly KC upper band
            if latest_daily_price >= latest_upper:
                # Calculate additional metrics
                volume_avg = df_monthly['Volume'].rolling(20).mean().iloc[-1]

                # Price change over last month
                if len(df_monthly) >= 2:
                    price_change_1m = (latest_monthly_close - df_monthly['Close'].iloc[-2]) / df_monthly['Close'].iloc[-2] * 100
                else:
                    price_change_1m = 0

                return {
                    'symbol': symbol,
                    'sector': self.sector_map.get(symbol, 'Unknown'),
                    'price': latest_daily_price,
                    'monthly_close': latest_monthly_close,
                    'kc_upper': latest_upper,
                    'kc_middle': latest_middle,
                    'breakout_pct': (latest_daily_price - latest_upper) / latest_upper * 100,
                    'volume': latest_monthly_volume,
                    'volume_ratio': latest_monthly_volume / volume_avg if volume_avg > 0 else 0,
                    'price_change_1m': price_change_1m,
                    'scan_time': self.current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                }

            return None

        except Exception as e:
            logger.error(f"Error checking KC breakout for {symbol}: {e}")
            return None

    def fetch_data_kite(self, symbol: str, interval: str, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Fetch historical data using Kite API"""
        try:
            # Get instrument token for the symbol
            ticker = symbol.replace('.NSE', '')  # Remove .NSE suffix for token lookup
            ticker = ticker.strip()  # Remove any whitespace

            # Get instruments list (cached)
            if self.instruments_df is None:
                instruments = self.kite.instruments("NSE")
                self.instruments_df = pd.DataFrame(instruments)
                logger.info("Fetched and cached instruments list")

            instruments_df = self.instruments_df

            # Find the instrument token
            mask = instruments_df['tradingsymbol'] == ticker
            if not mask.any():
                # Skip logging for known problematic tickers
                if ticker not in ['AMBALALSA', 'ANDREWYU  B', 'CEINSYSTECH', 'DDEVPLASTIK  B']:
                    logger.error(f"Instrument token not found for {ticker}")
                return pd.DataFrame()

            token = instruments_df[mask]['instrument_token'].iloc[0]

            # Rate limiting for API calls
            with self.api_semaphore:
                # Ensure minimum interval between API calls
                current_time = time.time()
                time_since_last_call = current_time - self.last_api_call
                if time_since_last_call < self.min_api_interval:
                    time.sleep(self.min_api_interval - time_since_last_call)

                # Fetch historical data
                data = self.kite.historical_data(
                    instrument_token=token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval
                )
                self.last_api_call = time.time()

            if not data:
                logger.warning(f"No data returned for {ticker}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data)
            df.rename(columns={
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)

            # Ensure Date is datetime but keep as column for KC calculations
            df['Date'] = pd.to_datetime(df['Date'])

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def check_monthly_long_reversal(self, symbol: str) -> Dict:
        """Check if stock shows long reversal pattern on monthly timeframe

        Criteria includes:
        1. Price above 3-month SMA
        2. Bullish crossover (price crossing above SMA3)
        3. Oversold bounce (RSI < 40 and rising)
        4. MACD bullish (MACD > Signal)
        5. Price momentum (>5% gain over 3 months)
        6. Higher low formation
        7. Volume uptick (20% above 3-month average)

        Needs at least 3 conditions to qualify as reversal
        """
        try:
            # Get monthly data - fetch more days to ensure we have enough monthly bars
            end_date = self.current_time
            start_date = end_date - timedelta(days=365 * 3)  # 3 years of data for monthly analysis

            # Fetch daily data and resample to monthly
            df_daily = self.fetch_data_kite(
                symbol,
                'day',
                start_date,
                end_date
            )

            if df_daily is None or df_daily.empty:
                return None

            # Set Date column as index for resampling
            if 'Date' in df_daily.columns:
                df_daily['Date'] = pd.to_datetime(df_daily['Date'])
                df_daily.set_index('Date', inplace=True)
            else:
                logger.error(f"No date column found for {symbol}")
                return None

            # Resample to monthly timeframe
            df_monthly = df_daily.resample('M').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

            if len(df_monthly) < 12:  # Need at least 12 months of data
                return None

            # Calculate monthly indicators
            df_monthly['SMA3'] = df_monthly['Close'].rolling(window=3).mean()
            df_monthly['SMA6'] = df_monthly['Close'].rolling(window=6).mean()
            df_monthly['RSI'] = self.calculate_rsi(df_monthly['Close'], 14)
            df_monthly['MACD'], df_monthly['Signal'], df_monthly['Histogram'] = self.calculate_macd(df_monthly['Close'])

            # Calculate volume moving average for volume uptick detection
            df_monthly['VolumeMA3'] = df_monthly['Volume'].rolling(window=3).mean()
            df_monthly['VolumeMA6'] = df_monthly['Volume'].rolling(window=6).mean()

            # Get latest and previous month values
            latest = df_monthly.iloc[-1]
            prev = df_monthly.iloc[-2]

            # Monthly long reversal conditions with volume uptick
            conditions = {
                'price_above_sma3': latest['Close'] > latest['SMA3'],
                'bullish_crossover': (prev['Close'] <= prev['SMA3'] and
                                     latest['Close'] > latest['SMA3']),
                'oversold_bounce': (prev['RSI'] < 40 and latest['RSI'] > prev['RSI']),
                'macd_bullish': latest['MACD'] > latest['Signal'],
                'price_momentum': (latest['Close'] - df_monthly['Close'].iloc[-3]) / df_monthly['Close'].iloc[-3] > 0.05,
                'higher_low': latest['Low'] > df_monthly['Low'].iloc[-3],
                'volume_uptick': latest['Volume'] > latest['VolumeMA3'] * 1.2  # 20% above 3-month avg volume
            }

            # Calculate score
            score = sum(conditions.values())

            # Need at least 3 conditions for a valid monthly reversal signal (4 with volume for stronger signal)
            if score >= 3:
                # Calculate additional monthly metrics
                monthly_change = (latest['Close'] - prev['Close']) / prev['Close'] * 100
                quarterly_change = (latest['Close'] - df_monthly['Close'].iloc[-3]) / df_monthly['Close'].iloc[-3] * 100
                volume_ratio = latest['Volume'] / latest['VolumeMA3'] if latest['VolumeMA3'] > 0 else 0

                return {
                    'symbol': symbol,
                    'sector': self.sector_map.get(symbol, 'Unknown'),
                    'monthly_close': latest['Close'],
                    'monthly_rsi': latest['RSI'],
                    'monthly_score': score,
                    'conditions': conditions,
                    'sma3': latest['SMA3'],
                    'sma6': latest['SMA6'],
                    'monthly_change_pct': monthly_change,
                    'quarterly_change_pct': quarterly_change,
                    'volume_ratio': volume_ratio,
                    'volume_uptick': conditions['volume_uptick'],
                    'scan_time': self.current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                }

            return None

        except Exception as e:
            logger.error(f"Error checking monthly reversal for {symbol}: {e}")
            return None

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD indicator"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def scan_single_stock(self, symbol: str, index: int, total: int) -> Tuple[Dict, Dict]:
        """Scan a single stock for both KC breakout and monthly reversal"""
        try:
            # Get daily data for KC breakout check (need more data for monthly resampling)
            end_date = self.current_time
            start_date = end_date - timedelta(days=800)  # ~2.5 years for monthly KC calculation
            df_daily = self.fetch_data_kite(
                symbol,
                'day',
                start_date,
                end_date
            )

            kc_signal = None
            monthly_signal = None

            if df_daily is not None and not df_daily.empty:
                # Check for KC breakout
                kc_signal = self.check_kc_breakout(symbol, df_daily)

                if kc_signal:
                    with self.results_lock:
                        self.kc_breakout_results.append(kc_signal)
                    logger.info(f"KC Upper breakout found: {symbol} (+{kc_signal['breakout_pct']:.2f}% above upper band)")

            # Check for monthly reversal (independent of KC breakout)
            monthly_signal = self.check_monthly_long_reversal(symbol)

            if monthly_signal:
                with self.results_lock:
                    self.monthly_reversal_results.append(monthly_signal)
                logger.info(f"Monthly long reversal found: {symbol} (Score: {monthly_signal['monthly_score']})")

            # Progress update
            if (index + 1) % 10 == 0:
                logger.info(f"Progress: {index + 1}/{total} stocks scanned")

            return kc_signal, monthly_signal

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None, None

    def scan_market(self):
        """Scan market for KC breakouts and monthly reversals using multi-threading"""
        logger.info("Starting KC Upper Breakout and Monthly Long Reversal scan for NSE stocks...")
        logger.info(f"Using {self.max_workers} threads for parallel processing")

        # Check if market is open (NSE hours: 9:15 AM to 3:30 PM IST)
        now = self.current_time
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)

        if not (market_open <= now <= market_close):
            logger.warning("NSE market is closed. Running scan on latest available data.")

        # Get universe
        universe = self.get_tradeable_universe()
        logger.info(f"Scanning {len(universe)} stocks...")

        # Use ThreadPoolExecutor for parallel scanning
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_stock = {
                executor.submit(self.scan_single_stock, symbol, i, len(universe)): (symbol, i)
                for i, symbol in enumerate(universe)
            }

            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_stock):
                symbol, index = future_to_stock[future]
                try:
                    result = future.result()
                    completed += 1
                    if completed % 25 == 0:
                        logger.info(f"Completed: {completed}/{len(universe)} stocks")
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")

        logger.info(f"Scan complete. Found {len(self.kc_breakout_results)} KC breakouts and {len(self.monthly_reversal_results)} monthly reversals.")

    def save_results(self):
        """Save scan results to Excel in Monthly directory"""
        if not self.kc_breakout_results and not self.monthly_reversal_results:
            logger.warning("No results to save")
            return

        # Create output directories in Monthly folder
        base_output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'Monthly'
        )
        xlsx_dir = os.path.join(base_output_dir, 'XLSX')
        html_dir = os.path.join(base_output_dir, 'HTML')
        os.makedirs(xlsx_dir, exist_ok=True)
        os.makedirs(html_dir, exist_ok=True)

        # Generate filename with month name
        month_year = self.current_time.strftime('%B')  # Get month name like 'September'
        base_filename = f"Monthly_{month_year}"
        xlsx_filepath = os.path.join(xlsx_dir, f"{base_filename}.xlsx")
        html_filepath = os.path.join(html_dir, f"{base_filename}.html")

        # Create Excel writer
        with pd.ExcelWriter(xlsx_filepath, engine='openpyxl') as writer:
            # KC Breakout results
            if self.kc_breakout_results:
                df_kc = pd.DataFrame(self.kc_breakout_results)
                df_kc = df_kc.sort_values('breakout_pct', ascending=False)
                df_kc.to_excel(writer, sheet_name='KC Upper Breakouts', index=False)

            # Monthly Reversal results
            if self.monthly_reversal_results:
                df_monthly = pd.DataFrame(self.monthly_reversal_results)
                df_monthly = df_monthly.sort_values('monthly_score', ascending=False)
                df_monthly.to_excel(writer, sheet_name='Monthly Reversals', index=False)

            # Summary statistics
            summary_data = {
                'Metric': [
                    'Total KC Breakouts',
                    'Total Monthly Reversals',
                    'Avg KC Breakout %',
                    'Avg Monthly Score',
                    'Scan Time'
                ],
                'Value': [
                    len(self.kc_breakout_results),
                    len(self.monthly_reversal_results),
                    pd.DataFrame(self.kc_breakout_results)['breakout_pct'].mean() if self.kc_breakout_results else 0,
                    pd.DataFrame(self.monthly_reversal_results)['monthly_score'].mean() if self.monthly_reversal_results else 0,
                    self.current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        logger.info(f"Excel results saved to: {xlsx_filepath}")

        # Generate HTML report
        html_content = self.generate_html_report()
        with open(html_filepath, 'w') as f:
            f.write(html_content)
        logger.info(f"HTML report saved to: {html_filepath}")

        # Save as JSON for other systems
        json_filepath = xlsx_filepath.replace('.xlsx', '.json')
        try:
            json_data = {
                'scan_time': self.current_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'kc_breakouts': self._clean_for_json(self.kc_breakout_results),
                'monthly_reversals': self._clean_for_json(self.monthly_reversal_results)
            }

            with open(json_filepath, 'w') as f:
                json.dump(json_data, f, indent=2)
            logger.info(f"JSON results saved to: {json_filepath}")
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")

        return xlsx_filepath

    def _clean_for_json(self, results: List[Dict]) -> List[Dict]:
        """Clean results for JSON serialization"""
        json_results = []
        for result in results:
            json_result = {}
            for key, value in result.items():
                if isinstance(value, np.ndarray):
                    json_result[key] = value.tolist()
                elif isinstance(value, (np.integer, np.floating, np.float64, np.float32)):
                    json_result[key] = float(value)
                elif isinstance(value, (np.int64, np.int32)):
                    json_result[key] = int(value)
                elif isinstance(value, dict):
                    # Convert dict values recursively
                    clean_dict = {}
                    for k, v in value.items():
                        if isinstance(v, (np.integer, np.floating, np.float64, np.float32)):
                            clean_dict[k] = float(v)
                        elif isinstance(v, (np.int64, np.int32)):
                            clean_dict[k] = int(v)
                        elif isinstance(v, bool):
                            clean_dict[k] = v
                        else:
                            clean_dict[k] = str(v)
                    json_result[key] = clean_dict
                else:
                    json_result[key] = value
            json_results.append(json_result)
        return json_results

    def generate_html_report(self):
        """Generate HTML report with both KC breakouts and monthly reversals"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NSE KC Upper Breakout & Monthly Reversal Scanner - {self.current_time.strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .section {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th {{
            background-color: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .positive {{
            color: #2e7d32;
            font-weight: bold;
        }}
        .negative {{
            color: #d32f2f;
            font-weight: bold;
        }}
        .breakout {{
            background-color: #e8f5e9;
            font-weight: bold;
        }}
        .reversal-high {{
            background-color: #c8e6c9;
            font-weight: bold;
        }}
        .reversal-medium {{
            background-color: #fff9c4;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>NSE Monthly Timeframe KC Upper Breakout & Long Reversal Scanner</h1>
        <p>Scan Time: {self.current_time.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
        <p>Timeframe: Monthly | EMA Period: 20 | ATR Period: 10 | Multiplier: 2.0</p>
        <p>KC Breakouts Found: {len(self.kc_breakout_results)} | Monthly Reversals Found: {len(self.monthly_reversal_results)}</p>
    </div>
"""

        # KC Breakout Section
        if self.kc_breakout_results:
            df_kc = pd.DataFrame(self.kc_breakout_results).sort_values('breakout_pct', ascending=False)
            html += """
    <div class="section">
        <h2>1. Stocks at/above Monthly Keltner Channel Upper Limit</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Sector</th>
                    <th>Current Price</th>
                    <th>Monthly Close</th>
                    <th>KC Upper (Monthly)</th>
                    <th>Breakout %</th>
                    <th>Volume Ratio</th>
                    <th>1M Change %</th>
                </tr>
            </thead>
            <tbody>
"""
            for _, row in df_kc.iterrows():
                change_class = 'positive' if row.get('price_change_1m', 0) > 0 else 'negative'
                html += f"""                <tr>
                    <td><b>{row['symbol']}</b></td>
                    <td>{row['sector']}</td>
                    <td>${row['price']:.2f}</td>
                    <td>${row.get('monthly_close', row['price']):.2f}</td>
                    <td>${row['kc_upper']:.2f}</td>
                    <td class="breakout">+{row['breakout_pct']:.2f}%</td>
                    <td>{row['volume_ratio']:.2f}x</td>
                    <td class="{change_class}">{row.get('price_change_1m', 0):.2f}%</td>
                </tr>
"""
            html += """            </tbody>
        </table>
    </div>
"""

        # Monthly Reversal Section
        if self.monthly_reversal_results:
            df_monthly = pd.DataFrame(self.monthly_reversal_results).sort_values('monthly_score', ascending=False)
            html += """
    <div class="section">
        <h2>2. Monthly Timeframe Long Reversals</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Sector</th>
                    <th>Score</th>
                    <th>Monthly Close</th>
                    <th>Monthly RSI</th>
                    <th>Volume Ratio</th>
                    <th>Monthly Change %</th>
                    <th>Quarterly Change %</th>
                </tr>
            </thead>
            <tbody>
"""
            for _, row in df_monthly.iterrows():
                score_class = 'reversal-high' if row['monthly_score'] >= 4 else 'reversal-medium'
                monthly_class = 'positive' if row['monthly_change_pct'] > 0 else 'negative'
                quarterly_class = 'positive' if row['quarterly_change_pct'] > 0 else 'negative'

                volume_class = 'positive' if row.get('volume_uptick', False) else ''
                volume_ratio_display = f"{row.get('volume_ratio', 0):.2f}x"

                html += f"""                <tr>
                    <td><b>{row['symbol']}</b></td>
                    <td>{row['sector']}</td>
                    <td class="{score_class}">{row['monthly_score']}</td>
                    <td>${row['monthly_close']:.2f}</td>
                    <td>{row['monthly_rsi']:.2f}</td>
                    <td class="{volume_class}">{volume_ratio_display}</td>
                    <td class="{monthly_class}">{row['monthly_change_pct']:.2f}%</td>
                    <td class="{quarterly_class}">{row['quarterly_change_pct']:.2f}%</td>
                </tr>
"""
            html += """            </tbody>
        </table>
    </div>
"""

        html += """</body>
</html>
"""
        return html

def main():
    """Main execution function"""
    try:
        # Parse arguments
        args = parse_args()
        user_name = args.user
        logger.info(f"Using credentials for user: {user_name}")

        # Initialize and run scanner
        scanner = KCMonthlyBreakoutScanner(user_name=user_name)
        scanner.scan_market()
        scanner.save_results()

    except Exception as e:
        logger.error(f"Scanner failed: {e}")
        raise

if __name__ == "__main__":
    main()