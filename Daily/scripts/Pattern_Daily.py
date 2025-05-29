#!/usr/bin/env python
# Pattern_Daily.py - Detailed stock pattern analysis with stop loss calculations
#
# For PDF output support (optional):
#   1. pip install pdfkit
#   2. Install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html
#
# Standard library imports
import os
import sys
import logging
import datetime
import time
import glob
import configparser
from typing import Dict, List, Tuple, Optional, Union
import json
import argparse

# Third-party imports
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
import webbrowser
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False
    logging.warning("pdfkit not installed. PDF generation will be disabled. Install with 'pip install pdfkit'")

# Add parent directory to path so we can access required modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from project
# Replaced import from root config.py with local config.ini handling
from order_manager import get_order_manager
from state_manager import get_state_manager

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, 'pattern_daily.log'))
    ]
)
logger = logging.getLogger(__name__)

def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(daily_dir, 'config.ini')

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        logger.error(f"No credentials found for user {user_name} in {config_path}")
        raise ValueError(f"No credentials found for user {user_name}")

    return config

# Constants
SLOPE_BULL_THRESHOLD = 0.5  # Positive slope threshold for bullish trend
SLOPE_BEAR_THRESHOLD = -0.5  # Negative slope threshold for bearish trend
MAX_CANDLES = 500  # Maximum number of historical candles to analyze
KELTNER_MULTIPLIER = 2.0  # Multiplier for Keltner Channel width
SMA_PERIOD = 20  # Period for SMA calculation
ATR_PERIOD = 14  # Period for ATR calculation

class PatternAnalyzer:
    """Analyzes stock patterns and trends based on technical indicators."""

    def __init__(self, user_name="Sai"):
        """Initialize the pattern analyzer with configuration and data handlers."""
        self.config = load_daily_config(user_name)
        self.user_name = user_name

        # We can't use the imported order_manager and data_handler directly since they
        # depend on the root config.py. Instead, we need to create new instances that
        # use our local config.ini.

        # Set up API credentials from config
        credential_section = f'API_CREDENTIALS_{user_name}'
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')

        # Initialize KiteConnect client
        from kiteconnect import KiteConnect
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)

        # For now, we'll try to use the existing order_manager and data_handler
        # This might not work perfectly and could be replaced with custom implementations later
        self.order_manager = get_order_manager()
        self.data_handler = self.order_manager.data_handler

        logger.info(f"PatternAnalyzer initialized for user: {user_name}")
        
    def fetch_historical_data(self, ticker: str, candles: int = MAX_CANDLES) -> pd.DataFrame:
        """
        Fetch historical daily data for a given ticker.
        
        Args:
            ticker: Stock ticker symbol
            candles: Number of candles to fetch (default: 500)
            
        Returns:
            DataFrame with historical price data
        """
        logger.info(f"Fetching historical data for {ticker}")
        
        # Calculate date range based on number of candles
        # Assume 252 trading days per year, but ensure we use integer years
        trading_days_needed = min(candles * 1.5, 1000)  # Add 50% buffer, cap at 1000 days

        end_date = datetime.datetime.now()
        # Use days instead of fractional years to avoid the ambiguity error
        start_date = end_date - datetime.timedelta(days=int(trading_days_needed))
        
        # Convert to strings
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
        
        try:
            # First try to fetch from API
            df = self.data_handler.fetch_historical_data(
                ticker, 
                interval="day",
                from_date=from_date, 
                to_date=to_date
            )
            
            if df is None or df.empty:
                logger.warning(f"No API data available for {ticker}, trying to load from CSV")
                # Try to load from CSV file in BT/data directory
                csv_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'BT', 'data', f"{ticker}_day.csv"
                )
                
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    # Ensure the date column is properly formatted
                    if 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'])
                    elif 'date' in df.columns:
                        df['Date'] = pd.to_datetime(df['date'])
                        df = df.drop('date', axis=1)
                    
                    # Standardize column names
                    column_mapping = {
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }
                    
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns and new_col not in df.columns:
                            df[new_col] = df[old_col]
                            df = df.drop(old_col, axis=1)
                else:
                    logger.error(f"Could not find CSV data for {ticker}")
                    return pd.DataFrame()
            
            # Sort by date and take the last 'candles' rows
            df = df.sort_values('Date')
            if len(df) > candles:
                df = df.tail(candles)
                
            # Add ticker column if not present
            if 'Ticker' not in df.columns:
                df['Ticker'] = ticker
                
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators needed for analysis.
        
        Args:
            df: DataFrame with price data
            
        Returns:
            DataFrame with added technical indicators
        """
        if df.empty:
            return df
            
        # Make a copy to avoid modifying the original
        data = df.copy()
        
        # Calculate SMA20
        data['SMA20'] = data['Close'].rolling(window=SMA_PERIOD).mean()
        
        # Calculate EMA21 and 50 for additional trend context
        data['EMA21'] = data['Close'].ewm(span=21, adjust=False).mean()
        data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
        
        # Calculate ATR for Keltner Channels
        data['TR'] = np.maximum(
            np.maximum(
                data['High'] - data['Low'],
                abs(data['High'] - data['Close'].shift(1))
            ),
            abs(data['Low'] - data['Close'].shift(1))
        )
        data['ATR'] = data['TR'].rolling(window=ATR_PERIOD).mean()
        
        # Calculate Keltner Channels
        data['KC_Middle'] = data['SMA20']
        data['KC_Upper'] = data['KC_Middle'] + (KELTNER_MULTIPLIER * data['ATR'])
        data['KC_Lower'] = data['KC_Middle'] - (KELTNER_MULTIPLIER * data['ATR'])
        
        # Calculate Slope of SMA20 over 8 periods
        def calculate_slope(y):
            if len(y) < 8 or y[-1] == 0:
                return np.nan
            return (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100

        data['SMA20_Slope'] = data['SMA20'].rolling(window=8).apply(
            calculate_slope, raw=True
        )
        
        # Flag days where price is above/below key indicators
        data['Above_SMA20'] = data['Close'] > data['SMA20']
        data['Above_EMA50'] = data['Close'] > data['EMA50']
        data['Above_KC_Upper'] = data['Close'] > data['KC_Upper']
        data['Below_KC_Lower'] = data['Close'] < data['KC_Lower']
        
        # Calculate distance from SMA20 as percentage
        data['SMA20_Distance'] = (data['Close'] - data['SMA20']) / data['SMA20'] * 100
        
        # Fill NaN values for initial periods
        data = data.fillna(method='bfill').fillna(method='ffill')
        
        return data
        
    def determine_trend(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Determine if the stock is in a bull, bear, or sideways trend.
        
        Args:
            df: DataFrame with calculated indicators
            
        Returns:
            Tuple of (trend_type, slope_value)
        """
        if df.empty:
            return "Unknown", 0
            
        # Get the latest slope
        latest_slope = df['SMA20_Slope'].iloc[-1]
        
        # Determine trend type
        if latest_slope > SLOPE_BULL_THRESHOLD:
            trend = "Bull"
        elif latest_slope < SLOPE_BEAR_THRESHOLD:
            trend = "Bear"
        else:
            trend = "Sideways"
            
        return trend, latest_slope
    
    def find_similar_patterns(self, df: pd.DataFrame, lookback: int = 200) -> List[Dict]:
        """
        Find historical instances of similar slope patterns.
        
        Args:
            df: DataFrame with calculated indicators
            lookback: How far back to look for patterns (excluding recent periods)
            
        Returns:
            List of dictionaries containing information about similar patterns
        """
        if df.empty or len(df) < lookback + 20:
            return []
        
        # Get the current slope
        current_slope = df['SMA20_Slope'].iloc[-1]
        
        # Define the range for similar slopes (±30%)
        slope_min = current_slope * 0.7
        slope_max = current_slope * 1.3
        
        # Find similar patterns in historical data
        # Skip the most recent 20 periods to avoid the current pattern
        historical_data = df.iloc[:-20]
        
        similar_patterns = []
        
        for i in range(len(historical_data) - 20):
            if i > lookback:
                break
                
            hist_slope = historical_data['SMA20_Slope'].iloc[i]
            
            # Check if this is a similar slope
            if slope_min <= hist_slope <= slope_max:
                # Analyze what happened in the next 20 periods
                future_window = df.iloc[i:i+20]
                
                # Calculate performance
                start_price = future_window['Close'].iloc[0]
                end_price = future_window['Close'].iloc[-1]
                performance = (end_price - start_price) / start_price * 100
                
                # Analyze pattern characteristics
                days_above_sma20 = future_window['Above_SMA20'].sum()
                days_above_kc_upper = future_window['Above_KC_Upper'].sum()
                
                pattern = {
                    'start_date': future_window['Date'].iloc[0].strftime('%Y-%m-%d'),
                    'end_date': future_window['Date'].iloc[-1].strftime('%Y-%m-%d'),
                    'slope': hist_slope,
                    'performance': performance,
                    'days_above_sma20': days_above_sma20,
                    'days_above_kc_upper': days_above_kc_upper,
                    'max_gain': future_window['Close'].max() / start_price * 100 - 100,
                    'max_loss': future_window['Close'].min() / start_price * 100 - 100
                }
                
                similar_patterns.append(pattern)
        
        # Sort by date (oldest first)
        similar_patterns.sort(key=lambda x: x['start_date'])
        
        return similar_patterns
        
    def identify_growth_pattern(self, df: pd.DataFrame) -> str:
        """
        Identify the type of growth pattern exhibited by the stock.

        Args:
            df: DataFrame with calculated indicators

        Returns:
            String describing the growth pattern
        """
        if df.empty:
            return "Unknown pattern"

        # Get recent data (last 40 periods)
        recent_data = df.tail(40)

        # Calculate metrics
        days_above_sma20 = recent_data['Above_SMA20'].sum()
        days_above_kc_upper = recent_data['Above_KC_Upper'].sum()
        days_below_kc_lower = recent_data['Below_KC_Lower'].sum()

        sma20_crosses = (recent_data['Above_SMA20'] != recent_data['Above_SMA20'].shift(1)).sum()

        # Determine pattern type
        if days_above_kc_upper >= 10:
            pattern = "Strong momentum growth with frequent Keltner Channel upper band breaks"
        elif days_above_sma20 >= 30 and sma20_crosses <= 4:
            pattern = "Consistent trend growth staying above SMA20"
        elif days_above_sma20 >= 25 and sma20_crosses >= 5:
            pattern = "Break and base cycle with SMA20 as support"
        elif days_below_kc_lower >= 8:
            pattern = "Oversold with potential for reversal"
        else:
            pattern = "Mixed pattern without clear trend characteristics"

        return pattern

    def find_previous_swing_low(self, df: pd.DataFrame, lookback: int = 60) -> float:
        """
        Find the previous significant swing low in price data.

        Args:
            df: DataFrame with price data
            lookback: Number of periods to look back for finding swing low

        Returns:
            Value of the previous swing low price
        """
        if df.empty or len(df) < 10:
            return df['Low'].min() if not df.empty else 0

        # Get recent data for analysis
        data = df.tail(lookback).copy()

        # Define window size for identifying local minima
        window = 5  # Consider a point a low if it's lower than 'window' points on either side

        # Initialize with a safe default (lowest price in the dataset)
        lowest_price = data['Low'].min()

        # Find local minima (swing lows)
        swing_lows = []

        for i in range(window, len(data) - window):
            # Current point's low price
            current_low = data['Low'].iloc[i]

            # Check if it's a local minimum
            left_window = data['Low'].iloc[i-window:i]
            right_window = data['Low'].iloc[i+1:i+window+1]

            if current_low <= left_window.min() and current_low <= right_window.min():
                # This is a swing low
                swing_lows.append((data.index[i], current_low))

        # If no swing lows found, return the default lowest price
        if not swing_lows:
            return lowest_price

        # Sort swing lows by date (most recent first) and return the most recent one
        # that isn't in the last 10 bars (to avoid using very recent, potentially unreliable swing lows)
        recent_threshold = 10
        filtered_swing_lows = [sl for sl in swing_lows if data.index.get_loc(sl[0]) < len(data) - recent_threshold]

        if filtered_swing_lows:
            # Return the most recent significant swing low
            return filtered_swing_lows[-1][1]
        else:
            # If no suitable swing low is found, return the default
            return lowest_price
        
    def analyze_ticker(self, ticker: str) -> Dict:
        """
        Perform comprehensive analysis of a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary containing analysis results
        """
        # Fetch historical data
        df = self.fetch_historical_data(ticker)

        if df.empty:
            return {
                'ticker': ticker,
                'success': False,
                'message': "Could not fetch data for this ticker"
            }

        # Calculate indicators
        df_with_indicators = self.calculate_indicators(df)

        # Determine trend
        trend, slope = self.determine_trend(df_with_indicators)

        # Identify growth pattern
        pattern = self.identify_growth_pattern(df_with_indicators)

        # Find similar historical patterns
        similar_patterns = self.find_similar_patterns(df_with_indicators)

        # Current price and indicators
        current_price = df_with_indicators['Close'].iloc[-1]
        current_sma20 = df_with_indicators['SMA20'].iloc[-1]
        current_kc_upper = df_with_indicators['KC_Upper'].iloc[-1]
        current_kc_lower = df_with_indicators['KC_Lower'].iloc[-1]

        # Calculate stop loss based on pattern type
        is_break_and_base = "Break and base cycle" in pattern

        if is_break_and_base:
            # For Break and Base patterns, use previous swing low as stop loss
            stop_loss = self.find_previous_swing_low(df_with_indicators)
            stop_loss_type = "Previous Swing Low"
        else:
            # For other patterns, use Keltner Channel Upper as stop loss
            stop_loss = current_kc_upper
            stop_loss_type = "KC Upper"

        # Calculate stop loss percentage
        stop_loss_pct = ((current_price - stop_loss) / current_price) * 100

        # Determine recommendation
        if trend == "Bull":
            recommendation = "Buy and hold"
        elif trend == "Bear":
            recommendation = "Avoid or wait for trend reversal"
        else:
            recommendation = "Wait for clear trend direction"

        # Compile averages from similar patterns if available
        avg_performance = None
        avg_days_above_sma20 = None
        avg_max_gain = None

        if similar_patterns:
            avg_performance = sum(p['performance'] for p in similar_patterns) / len(similar_patterns)
            avg_days_above_sma20 = sum(p['days_above_sma20'] for p in similar_patterns) / len(similar_patterns)
            avg_max_gain = sum(p['max_gain'] for p in similar_patterns) / len(similar_patterns)

        # Compile results
        results = {
            'ticker': ticker,
            'success': True,
            'current_price': current_price,
            'trend': trend,
            'slope': slope,
            'growth_pattern': pattern,
            'recommendation': recommendation,
            'stop_loss': {
                'value': stop_loss,
                'type': stop_loss_type,
                'percentage': stop_loss_pct
            },
            'indicators': {
                'sma20': current_sma20,
                'kc_upper': current_kc_upper,
                'kc_lower': current_kc_lower,
                'above_sma20': current_price > current_sma20,
                'above_kc_upper': current_price > current_kc_upper
            },
            'similar_patterns': {
                'count': len(similar_patterns),
                'avg_performance': avg_performance,
                'avg_days_above_sma20': avg_days_above_sma20,
                'avg_max_gain': avg_max_gain,
                'patterns': similar_patterns[:5]  # Include only the first 5 for brevity
            }
        }

        return results

def display_analysis_results(results: Dict):
    """
    Display analysis results in a user-friendly format.

    Args:
        results: Dictionary with analysis results
    """
    if not results['success']:
        print(f"[!] {results['message']}")
        return

    # Print header
    print("\n" + "="*60)
    print(f"Pattern Analysis for {results['ticker']}")
    print("="*60)

    # Basic trend information
    print(f"\nCurrent Price: Rs.{results['current_price']:.2f}")

    # Print trend with symbols
    trend_symbol = "^" if results['trend'] == "Bull" else "v" if results['trend'] == "Bear" else "<>"
    print(f"Trend: {trend_symbol} {results['trend']} (SMA20 Slope: {results['slope']:.2f})")

    # Print recommendation
    rec_symbol = "[+]" if "Buy" in results['recommendation'] else "[-]" if "Avoid" in results['recommendation'] else "[?]"
    print(f"Recommendation: {rec_symbol} {results['recommendation']}")

    # Print pattern
    print(f"\nGrowth Pattern: {results['growth_pattern']}")

    # Print stop loss information
    sl = results['stop_loss']
    print(f"\nStop Loss:")
    print(f"- Value: Rs.{sl['value']:.2f} ({sl['type']})")
    print(f"- Risk: {sl['percentage']:.2f}%")

    # Print key indicators
    ind = results['indicators']
    print("\nKey Indicators:")
    print(f"- SMA20: Rs.{ind['sma20']:.2f} {'(Price Above +)' if ind['above_sma20'] else '(Price Below -)'}")
    print(f"- Keltner Upper: Rs.{ind['kc_upper']:.2f} {'(Price Above +)' if ind['above_kc_upper'] else '(Price Below -)'}")
    print(f"- Keltner Lower: Rs.{ind['kc_lower']:.2f}")

    # Historical patterns
    similar = results['similar_patterns']
    if similar['count'] > 0:
        print(f"\nFound {similar['count']} similar historical patterns")
        print(f"- Average 20-day performance: {similar['avg_performance']:.2f}%")
        print(f"- Average days above SMA20: {similar['avg_days_above_sma20']:.1f}/20")
        print(f"- Average maximum gain: {similar['avg_max_gain']:.2f}%")

        # Print some examples
        if similar['patterns']:
            print("\nExamples of similar historical patterns:")
            for i, pattern in enumerate(similar['patterns'], 1):
                print(f"{i}. {pattern['start_date']} to {pattern['end_date']}: {pattern['performance']:.2f}% return, " +
                     f"{pattern['days_above_sma20']}/20 days above SMA20, max gain {pattern['max_gain']:.2f}%")
    else:
        print("\nNo similar historical patterns found")

    print("\n" + "="*60)

def get_latest_scanner_file() -> Optional[str]:
    """
    Find the latest Custom_Scanner file in the scanner_files directory.

    Returns:
        Path to the latest scanner file or None if not found
    """
    try:
        daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scanner_dir = os.path.join(daily_dir, "scanner_files")
        scanner_files = glob.glob(os.path.join(scanner_dir, "Custom_Scanner_*.xlsx"))

        if not scanner_files:
            logger.error("No scanner files found in the scanner_files directory")
            return None

        # Sort files by modification time (newest first)
        scanner_files.sort(key=os.path.getmtime, reverse=True)
        latest_file = scanner_files[0]

        logger.info(f"Found latest scanner file: {os.path.basename(latest_file)}")
        return latest_file
    except Exception as e:
        logger.error(f"Error finding latest scanner file: {e}")
        return None

def read_tickers_from_scanner(file_path: str) -> List[str]:
    """
    Read tickers from a scanner Excel file.

    Args:
        file_path: Path to the scanner Excel file

    Returns:
        List of ticker symbols
    """
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)

        # Ensure 'Ticker' column exists
        if 'Ticker' not in df.columns:
            logger.error(f"No 'Ticker' column found in {file_path}")
            return []

        # Extract tickers
        tickers = df['Ticker'].dropna().tolist()

        logger.info(f"Extracted {len(tickers)} tickers from {os.path.basename(file_path)}")
        return tickers
    except Exception as e:
        logger.error(f"Error reading scanner file: {e}")
        return []

def generate_report(results: List[Dict], output_file: str, open_browser: bool = True, include_sideways: bool = False, user_name: str = "Sai"):
    """
    Generate a detailed analysis report for multiple tickers.

    Args:
        results: List of analysis results for each ticker
        output_file: Path to the output file
        open_browser: Whether to automatically open the report in the browser (default: True)
        include_sideways: Whether to include sideways trending tickers in the report (default: False)
    """
    try:
        # Create HTML content
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Detailed Stock Analysis Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333366; text-align: center; }
                .report-date { text-align: center; margin-bottom: 30px; color: #666; }
                .ticker-card {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .ticker-header {
                    display: flex;
                    justify-content: space-between;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 15px;
                }
                .ticker-name { font-size: 24px; font-weight: bold; }
                .ticker-price { font-size: 20px; }
                .bull { color: green; }
                .bear { color: red; }
                .sideways { color: orange; }
                .indicators { margin: 15px 0; }
                .indicators table { width: 100%; border-collapse: collapse; }
                .indicators th, .indicators td {
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                .patterns { margin-top: 15px; }
                .pattern-examples {
                    font-size: 14px;
                    background-color: #f9f9f9;
                    padding: 10px;
                    border-radius: 4px;
                }
                .recommendation {
                    margin-top: 15px;
                    padding: 10px;
                    background-color: #f0f7ff;
                    border-radius: 4px;
                    font-weight: bold;
                }
                .buy { background-color: #e6ffe6; }
                .avoid { background-color: #ffe6e6; }
                .wait { background-color: #fff9e6; }
                /* Highlight the stop loss row */
                .indicators tr:last-child {
                    background-color: #fff0f0;
                    font-weight: bold;
                }
                @media print {
                    .ticker-card {
                        page-break-inside: avoid;
                        margin-bottom: 20px;
                    }
                    body { font-size: 12px; }
                    .ticker-name { font-size: 18px; }
                    .ticker-price { font-size: 16px; }
                }
            </style>
        </head>
        <body>
            <h1>Detailed Stock Analysis Report</h1>
            <div class="report-date">Generated on: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</div>
        """

        # Add ticker sections
        successful_results = [r for r in results if r['success']]

        # Group by trend
        bull_tickers = [r for r in successful_results if r['trend'] == 'Bull']
        bear_tickers = [r for r in successful_results if r['trend'] == 'Bear']
        sideways_tickers = [r for r in successful_results if r['trend'] == 'Sideways']

        # Sort within groups by slope (descending)
        bull_tickers.sort(key=lambda x: x['slope'], reverse=True)
        bear_tickers.sort(key=lambda x: x['slope'])  # Bear tickers have negative slopes, so we don't reverse

        if include_sideways:
            # If including sideways tickers, sort them by absolute slope value
            sideways_tickers.sort(key=lambda x: abs(x['slope']))
            # Combine all tickers
            sorted_results = bull_tickers + sideways_tickers + bear_tickers
        else:
            # Exclude sideways trending tickers
            sorted_results = bull_tickers + bear_tickers

        for result in sorted_results:
            trend_class = result['trend'].lower()
            rec_class = "buy" if "Buy" in result['recommendation'] else "avoid" if "Avoid" in result['recommendation'] else "wait"

            html_content += f"""
            <div class="ticker-card">
                <div class="ticker-header">
                    <div class="ticker-name">{result['ticker']}</div>
                    <div class="ticker-price">&#8377;{result['current_price']:.2f}</div>
                </div>

                <div class="trend {trend_class}">
                    Trend: {result['trend']} (SMA20 Slope: {result['slope']:.2f})
                </div>

                <div class="growth-pattern">
                    <strong>Growth Pattern:</strong> {result['growth_pattern']}
                </div>

                <div class="indicators">
                    <table>
                        <tr>
                            <th>Indicator</th>
                            <th>Value</th>
                            <th>Status</th>
                        </tr>
                        <tr>
                            <td>SMA20</td>
                            <td>&#8377;{result['indicators']['sma20']:.2f}</td>
                            <td>{("Above ✓" if result['indicators']['above_sma20'] else "Below ✗")}</td>
                        </tr>
                        <tr>
                            <td>Keltner Upper</td>
                            <td>&#8377;{result['indicators']['kc_upper']:.2f}</td>
                            <td>{("Above ✓" if result['indicators']['above_kc_upper'] else "Below ✗")}</td>
                        </tr>
                        <tr>
                            <td>Keltner Lower</td>
                            <td>&#8377;{result['indicators']['kc_lower']:.2f}</td>
                            <td>-</td>
                        </tr>
                        <tr>
                            <td>Stop Loss ({result['stop_loss']['type']})</td>
                            <td>&#8377;{result['stop_loss']['value']:.2f}</td>
                            <td>Risk: {result['stop_loss']['percentage']:.2f}%</td>
                        </tr>
                    </table>
                </div>
            """

            # Add historical patterns if available
            similar = result['similar_patterns']
            if similar['count'] > 0:
                html_content += f"""
                <div class="patterns">
                    <strong>Similar Historical Patterns:</strong> {similar['count']} instances found<br>
                    Average 20-day performance: {similar['avg_performance']:.2f}%<br>
                    Average days above SMA20: {similar['avg_days_above_sma20']:.1f}/20<br>
                    Average maximum gain: {similar['avg_max_gain']:.2f}%

                    <div class="pattern-examples">
                        <strong>Examples:</strong><br>
                """

                for i, pattern in enumerate(similar['patterns'][:3], 1):  # Show top 3 examples
                    html_content += f"""
                    {i}. {pattern['start_date']} to {pattern['end_date']}: {pattern['performance']:.2f}% return,
                    {pattern['days_above_sma20']}/20 days above SMA20, max gain {pattern['max_gain']:.2f}%<br>
                    """

                html_content += """
                    </div>
                </div>
                """
            else:
                html_content += "<div class='patterns'>No similar historical patterns found</div>"

            # Add recommendation
            html_content += f"""
                <div class="recommendation {rec_class}">
                    {result['recommendation']}
                </div>
            </div>
            """

        # Add summary section
        html_content += f"""
            <div style="margin-top: 30px; text-align: center;">
                <h2>Summary</h2>
                <p>Total stocks analyzed: {len(successful_results)}</p>
                <p>Bull trend: {len(bull_tickers)} stocks</p>
                <p>Bear trend: {len(bear_tickers)} stocks</p>
                {'<p>Sideways trend: ' + str(len(sideways_tickers)) + ' stocks</p>' if include_sideways
                 else '<p><i>Note: ' + str(len(sideways_tickers)) + ' stocks with sideways trend were excluded from this report</i></p>'}
            </div>
        """

        # Close HTML
        html_content += """
        </body>
        </html>
        """

        # Write to HTML file with UTF-8 encoding
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML report generated successfully: {output_file}")
        print(f"\nHTML report generated: {output_file}")

        # Open the HTML report in the browser if requested
        if open_browser:
            try:
                print("Opening HTML report in browser...")
                webbrowser.open_new_tab(f"file://{os.path.abspath(output_file)}")
            except Exception as e:
                logger.warning(f"Could not open HTML report automatically: {e}")

        # Generate PDF version if pdfkit is available
        if PDFKIT_AVAILABLE:
            pdf_file = output_file.replace('.html', '.pdf')
            try:
                # Configure pdfkit options
                options = {
                    'page-size': 'A4',
                    'margin-top': '15mm',
                    'margin-right': '15mm',
                    'margin-bottom': '15mm',
                    'margin-left': '15mm',
                    'encoding': 'UTF-8',
                    'quiet': '',
                }

                # Create PDF
                pdfkit.from_file(output_file, pdf_file, options=options)
                logger.info(f"PDF report generated successfully: {pdf_file}")
                print(f"PDF report generated: {pdf_file}")

                # Attempt to open the PDF
                try:
                    webbrowser.open_new_tab(f"file://{pdf_file}")
                except Exception as e:
                    logger.warning(f"Could not open PDF automatically: {e}")
            except Exception as e:
                logger.error(f"Error generating PDF report: {e}")
                print(f"Error generating PDF report: {e}")
                print("Make sure wkhtmltopdf is installed. Visit https://wkhtmltopdf.org/downloads.html")
        else:
            print("\nPDF generation is disabled because pdfkit is not installed.")
            print("To enable PDF generation, install pdfkit and wkhtmltopdf:")
            print("1. pip install pdfkit")
            print("2. Install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html")

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        print(f"\nError generating report: {e}")

def main():
    """Main function to run the pattern analyzer on multiple tickers."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Pattern Daily Analyzer')
        parser.add_argument('--ticker', '-t', type=str, help='Analyze a specific ticker')
        parser.add_argument('--scan-file', '-f', type=str, help='Path to a specific scanner file')
        parser.add_argument('--output', '-o', type=str, help='Output filename')
        parser.add_argument('--format', choices=['html', 'pdf', 'both'], default='both',
                            help='Output format (html, pdf, or both)')
        parser.add_argument('--no-browser', action='store_true', help='Do not open the report in browser')
        parser.add_argument('--include-sideways', action='store_true',
                            help='Include sideways trending tickers in the report')
        parser.add_argument('--user', '-u', type=str, default='Sai',
                            help='User whose API credentials to use (default: Sai)')

        args = parser.parse_args()

        # Create pattern analyzer with user argument
        analyzer = PatternAnalyzer(user_name=args.user)
        logger.info(f"Running Pattern Daily Analyzer with credentials for user: {args.user}")

        # Set up report parameters
        today = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Detailed_Analysis")
        # Ensure the directory exists
        os.makedirs(report_dir, exist_ok=True)

        # Single ticker analysis mode
        if args.ticker:
            ticker = args.ticker.strip().upper()
            print(f"\nAnalyzing {ticker}... Please wait.")
            results = analyzer.analyze_ticker(ticker)

            # Display results
            display_analysis_results(results)

            # Generate report for single ticker if successful
            if results['success']:
                output_file = args.output or os.path.join(report_dir, f"Detailed_Analysis_{ticker}_{args.user}_{today}.html")
                generate_report([results], output_file, not args.no_browser, args.include_sideways, args.user)
            return 0

        # Find scanner file to use
        scanner_file = None
        if args.scan_file:
            if os.path.exists(args.scan_file):
                scanner_file = args.scan_file
            else:
                print(f"Specified scanner file not found: {args.scan_file}")
                return 1
        else:
            scanner_file = get_latest_scanner_file()

        if not scanner_file:
            print("No scanner file found. Would you like to analyze a specific ticker instead? (y/n)")
            response = input().strip().lower()
            if response == 'y':
                ticker = input("Enter ticker symbol to analyze: ").strip().upper()
                if not ticker:
                    print("No ticker provided. Exiting.")
                    return 1

                print(f"\nAnalyzing {ticker}... Please wait.")
                results = analyzer.analyze_ticker(ticker)
                display_analysis_results(results)

                # Generate report for single ticker if successful
                if results['success']:
                    output_file = os.path.join(report_dir, f"Detailed_Analysis_{ticker}_{args.user}_{today}.html")
                    generate_report([results], output_file, not args.no_browser, args.include_sideways, args.user)
                return 0
            else:
                print("Exiting.")
                return 1

        # Read tickers from scanner
        tickers = read_tickers_from_scanner(scanner_file)
        if not tickers:
            print("No tickers found in the scanner file. Exiting.")
            return 1

        print(f"\nFound {len(tickers)} tickers in {os.path.basename(scanner_file)}")
        print("Analyzing all tickers... This may take a few minutes.")

        # Analyze each ticker
        all_results = []
        for i, ticker in enumerate(tickers, 1):
            print(f"Analyzing {ticker} ({i}/{len(tickers)})...")
            try:
                results = analyzer.analyze_ticker(ticker)
                all_results.append(results)
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                all_results.append({
                    'ticker': ticker,
                    'success': False,
                    'message': str(e)
                })

        # Generate report
        output_file = args.output or os.path.join(report_dir, f"Detailed_Analysis_{args.user}_{today}.html")

        # Handle format choice
        if args.format == 'html':
            # Only generate HTML report
            global PDFKIT_AVAILABLE
            PDFKIT_AVAILABLE = False  # Temporarily disable PDF

        # Generate report
        generate_report(all_results, output_file, not args.no_browser, args.include_sideways)

        # Provide a summary of results to the console
        successful = sum(1 for r in all_results if r['success'])
        bull = sum(1 for r in all_results if r.get('success') and r.get('trend') == 'Bull')
        bear = sum(1 for r in all_results if r.get('success') and r.get('trend') == 'Bear')
        sideways = sum(1 for r in all_results if r.get('success') and r.get('trend') == 'Sideways')

        print("\nAnalysis complete!")
        print(f"Successfully analyzed: {successful}/{len(tickers)} tickers")
        print(f"Bull trend: {bull} stocks")
        print(f"Bear trend: {bear} stocks")
        print(f"Sideways trend: {sideways} stocks {'' if args.include_sideways else '(excluded from report)'}")
        print(f"\nDetailed report saved to: {output_file}")

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 1
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        print(f"\nAn error occurred: {str(e)}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())