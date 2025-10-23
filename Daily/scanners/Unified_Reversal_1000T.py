#!/usr/bin/env python3
"""
Unified Reversal Scanner - 1000 Tick Timeframe Version
Uses tick-aggregated data instead of daily timeframe for faster signals
Modified to aggregate minute data into 1000-tick equivalent bars
Author: Claude (Modified)
Date: 2025-09-16
"""

import os
import sys
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import argparse
import json
import configparser

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
TICK_AGGREGATION = 1000  # Aggregate every 1000 ticks worth of volume
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DATA_DIR, '..', 'Detailed_Analysis', 'Tick')

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    return config, credential_section

class TickDataProcessor:
    """Process minute data into tick-aggregated bars"""

    def __init__(self, kite, ticker):
        self.kite = kite
        self.ticker = ticker
        self.instrument_token = self._get_instrument_token(ticker)

    def _get_instrument_token(self, ticker):
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
        except Exception as e:
            logger.error(f"Error getting instrument token for {ticker}: {e}")
        return None

    def fetch_minute_data(self, days_back=10):
        """Fetch minute-level data for aggregation"""
        if not self.instrument_token:
            return pd.DataFrame()

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)

        try:
            # Fetch minute data
            data = self.kite.historical_data(
                self.instrument_token,
                from_date,
                to_date,
                'minute'
            )

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df

        except Exception as e:
            logger.error(f"Error fetching minute data for {self.ticker}: {e}")
            return pd.DataFrame()

    def aggregate_to_tick_bars(self, minute_df, tick_size=1000):
        """Aggregate minute data into tick-equivalent bars based on volume"""
        if minute_df.empty:
            return pd.DataFrame()

        # Calculate average volume per minute
        avg_minute_volume = minute_df['volume'].mean()

        # Estimate ticks per minute (assuming 1 tick per trade, roughly)
        # This is a proxy - actual tick data would be more accurate
        ticks_per_minute = avg_minute_volume / 10  # Rough estimate

        # Calculate how many minutes to aggregate for tick_size ticks
        minutes_per_bar = max(1, int(tick_size / max(1, ticks_per_minute)))

        # Aggregate data
        aggregated_data = []
        for i in range(0, len(minute_df), minutes_per_bar):
            slice_df = minute_df.iloc[i:i+minutes_per_bar]

            if not slice_df.empty:
                bar = {
                    'Date': slice_df.index[-1],  # Use last timestamp
                    'Open': slice_df['open'].iloc[0],
                    'High': slice_df['high'].max(),
                    'Low': slice_df['low'].min(),
                    'Close': slice_df['close'].iloc[-1],
                    'Volume': slice_df['volume'].sum(),
                    'TickCount': minutes_per_bar * ticks_per_minute  # Estimated
                }
                aggregated_data.append(bar)

        return pd.DataFrame(aggregated_data)

def detect_tick_reversal_patterns(tick_data, ticker, pattern_type='long'):
    """Detect reversal patterns on tick data"""
    if tick_data.empty or len(tick_data) < 20:
        return None

    df = tick_data.copy()

    # Calculate indicators on tick data
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA10'] = df['Close'].rolling(window=10).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()

    # ATR for volatility
    high_low = df['High'] - df['Low']
    df['ATR'] = high_low.rolling(window=14).mean()

    # Volume analysis
    df['AvgVolume'] = df['Volume'].rolling(window=10).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume']

    # Get latest bar
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    score = 0
    pattern_found = False

    if pattern_type == 'long':
        # Long reversal pattern detection on tick data

        # 1. Price below short-term SMA (oversold on tick timeframe)
        if latest['Close'] < latest['SMA5']:
            score += 10

        # 2. Volume spike (institutional interest)
        if latest['VolumeRatio'] > 1.5:
            score += 20

        # 3. Bullish bar formation
        if latest['Close'] > latest['Open']:
            score += 10

        # 4. Higher low than previous bar
        if latest['Low'] > prev['Low']:
            score += 10

        # 5. Break above previous high (micro breakout)
        if latest['Close'] > prev['High']:
            score += 20

        # 6. SMA alignment starting (5 > 10)
        if latest['SMA5'] > latest['SMA10']:
            score += 15

        # 7. Large range bar (volatility expansion)
        if (latest['High'] - latest['Low']) > latest['ATR'] * 1.5:
            score += 15

        pattern_found = score >= 50

    else:  # short pattern
        # Short reversal pattern detection on tick data

        # 1. Price above short-term SMA (overbought on tick timeframe)
        if latest['Close'] > latest['SMA5']:
            score += 10

        # 2. Volume spike (distribution)
        if latest['VolumeRatio'] > 1.5:
            score += 20

        # 3. Bearish bar formation
        if latest['Close'] < latest['Open']:
            score += 10

        # 4. Lower high than previous bar
        if latest['High'] < prev['High']:
            score += 10

        # 5. Break below previous low (micro breakdown)
        if latest['Close'] < prev['Low']:
            score += 20

        # 6. SMA alignment starting (5 < 10)
        if latest['SMA5'] < latest['SMA10']:
            score += 15

        # 7. Large range bar (volatility expansion)
        if (latest['High'] - latest['Low']) > latest['ATR'] * 1.5:
            score += 15

        pattern_found = score >= 50

    if pattern_found:
        return {
            'Ticker': ticker,
            'Pattern': f"{'Long' if pattern_type == 'long' else 'Short'} Reversal (Tick)",
            'Score': score,
            'Price': latest['Close'],
            'Volume': latest['Volume'],
            'VolumeRatio': round(latest['VolumeRatio'], 2),
            'TickBars': len(df),
            'TimeFrame': '1000T',
            'Entry': latest['Close'],
            'StopLoss': latest['Low'] - latest['ATR'] if pattern_type == 'long' else latest['High'] + latest['ATR'],
            'Target': latest['Close'] + (2 * latest['ATR']) if pattern_type == 'long' else latest['Close'] - (2 * latest['ATR']),
            'Timestamp': latest['Date'].strftime('%Y-%m-%d %H:%M:%S')
        }

    return None

def read_ticker_file():
    """Read tickers from Ticker.xlsx"""
    ticker_file = os.path.join(DATA_DIR, '..', 'data', 'Ticker.xlsx')

    try:
        if os.path.exists(ticker_file):
            df = pd.read_excel(ticker_file)

            # Check for 'Symbol' or 'Ticker' column
            if 'Symbol' in df.columns:
                tickers = df['Symbol'].dropna().tolist()
            elif 'Ticker' in df.columns:
                tickers = df['Ticker'].dropna().tolist()
            else:
                logger.warning("Ticker file doesn't have 'Symbol' or 'Ticker' column")
                return []

            # Clean tickers
            tickers = [str(t).strip() for t in tickers if pd.notna(t) and str(t).strip()]
            logger.info(f"Loaded {len(tickers)} tickers from {ticker_file}")
            return tickers
        else:
            logger.error(f"Ticker file not found: {ticker_file}")
            return []
    except Exception as e:
        logger.error(f"Error reading ticker file: {e}")
        return []

def save_results(results, pattern_type):
    """Save results to Excel and generate HTML report"""
    if not results:
        logger.info(f"No {pattern_type} patterns found")
        return

    # Create DataFrame
    df = pd.DataFrame(results)
    df = df.sort_values('Score', ascending=False)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save to Excel
    excel_file = os.path.join(OUTPUT_DIR, f"{pattern_type}_Reversal_1000T_{timestamp}.xlsx")
    df.to_excel(excel_file, index=False)
    logger.info(f"Saved {len(results)} {pattern_type} patterns to {excel_file}")

    # Generate HTML report
    html_content = f"""
    <html>
    <head>
        <title>{pattern_type} Reversal Patterns - 1000 Tick</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .high-score {{ background-color: #d4edda; }}
            .medium-score {{ background-color: #fff3cd; }}
        </style>
    </head>
    <body>
        <h1>{pattern_type} Reversal Patterns - 1000 Tick Timeframe</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Total Patterns Found: {len(results)}</p>

        <table>
            <tr>
                <th>Ticker</th>
                <th>Score</th>
                <th>Price</th>
                <th>Volume Ratio</th>
                <th>Entry</th>
                <th>Stop Loss</th>
                <th>Target</th>
                <th>Time</th>
            </tr>
    """

    for _, row in df.iterrows():
        score_class = 'high-score' if row['Score'] >= 70 else 'medium-score' if row['Score'] >= 50 else ''
        html_content += f"""
            <tr class="{score_class}">
                <td><b>{row['Ticker']}</b></td>
                <td>{row['Score']}</td>
                <td>₹{row['Price']:.2f}</td>
                <td>{row['VolumeRatio']:.2f}x</td>
                <td>₹{row['Entry']:.2f}</td>
                <td>₹{row['StopLoss']:.2f}</td>
                <td>₹{row['Target']:.2f}</td>
                <td>{row['Timestamp']}</td>
            </tr>
        """

    html_content += """
        </table>
    </body>
    </html>
    """

    html_file = os.path.join(OUTPUT_DIR, f"{pattern_type}_Reversal_1000T_{timestamp}.html")
    with open(html_file, 'w') as f:
        f.write(html_content)
    logger.info(f"Generated HTML report: {html_file}")

def main():
    """Main function - run tick-based reversal scanner"""
    print("\n" + "="*60)
    print("UNIFIED REVERSAL SCANNER - 1000 TICK VERSION")
    print("Using tick-aggregated data for faster signal detection")
    print("="*60 + "\n")

    start_time = time.time()

    # Parse arguments
    parser = argparse.ArgumentParser(description='Unified Reversal Scanner - 1000 Tick Version')
    parser.add_argument('--user', type=str, default='Sai', help='User context for credentials')
    args = parser.parse_args()

    user_name = args.user
    logger.info(f"Using credentials for user: {user_name}")
    print(f"Using credentials for user: {user_name}")

    # Initialize Kite Connect
    try:
        # Load config and credentials
        config, credential_section = load_daily_config(user_name)

        # Get API credentials
        api_key = config.get(credential_section, 'api_key')
        access_token = config.get(credential_section, 'access_token')

        # Validate credentials
        if not api_key or not access_token:
            logger.error(f"Missing API credentials for user {user_name}. Please check config.ini")
            raise ValueError(f"API key or access token missing for user {user_name}")

        logger.info(f"Successfully loaded API credentials for user {user_name}")

        # Initialize Kite Connect
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        # Test connection
        profile = kite.profile()
        print(f"Connected as: {profile['user_name']}")
        logger.info(f"Connected to Kite as: {profile['user_name']}")

    except Exception as e:
        logger.error(f"Failed to initialize Kite Connect: {e}")
        return

    # Read tickers
    tickers = read_ticker_file()
    if not tickers:
        logger.error("No tickers loaded")
        return

    print(f"Processing {len(tickers)} tickers for tick patterns...")
    print("="*60)

    long_results = []
    short_results = []

    for i, ticker in enumerate(tickers):
        try:
            # Create tick data processor
            processor = TickDataProcessor(kite, ticker)

            # Fetch minute data
            minute_data = processor.fetch_minute_data(days_back=10)

            if minute_data.empty:
                continue

            # Aggregate to tick bars
            tick_data = processor.aggregate_to_tick_bars(minute_data, TICK_AGGREGATION)

            if tick_data.empty:
                continue

            # Detect patterns
            long_pattern = detect_tick_reversal_patterns(tick_data, ticker, 'long')
            if long_pattern:
                long_results.append(long_pattern)
                print(f"✓ {ticker}: Long pattern (Score: {long_pattern['Score']})")

            short_pattern = detect_tick_reversal_patterns(tick_data, ticker, 'short')
            if short_pattern:
                short_results.append(short_pattern)
                print(f"✓ {ticker}: Short pattern (Score: {short_pattern['Score']})")

            # Progress update
            if (i + 1) % 50 == 0:
                print(f"Processed {i+1}/{len(tickers)} tickers...")

            # Rate limiting
            time.sleep(0.1)  # Avoid hitting API rate limits

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            continue

    print("="*60)
    print(f"Scan complete. Found {len(long_results)} long and {len(short_results)} short patterns")

    # Save results
    save_results(long_results, 'Long')
    save_results(short_results, 'Short')

    # Print summary
    elapsed_time = time.time() - start_time
    print(f"\nExecution time: {elapsed_time:.2f} seconds")

    # Print top patterns
    if long_results:
        print("\nTop 5 Long Patterns:")
        top_long = sorted(long_results, key=lambda x: x['Score'], reverse=True)[:5]
        for pattern in top_long:
            print(f"  {pattern['Ticker']}: Score={pattern['Score']}, Price=₹{pattern['Price']:.2f}")

    if short_results:
        print("\nTop 5 Short Patterns:")
        top_short = sorted(short_results, key=lambda x: x['Score'], reverse=True)[:5]
        for pattern in top_short:
            print(f"  {pattern['Ticker']}: Score={pattern['Score']}, Price=₹{pattern['Price']:.2f}")

if __name__ == "__main__":
    main()