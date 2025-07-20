#!/usr/bin/env python
"""
StrategyKV_C_Filter.py - KC Upper Channel Break Filter for StrategyB results:
1. Read the most recent StrategyB report  
2. Apply KC upper channel break filter only
3. Save results as StrategyC_{date}_{time}.xlsx
"""

import os
import sys
import glob
import logging
import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from kiteconnect import KiteConnect
import configparser

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "strategykv_c_filter.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        logger.error(f"config.ini file not found at {config_path}")
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        logger.error(f"No credentials found for user {user_name}")
        raise ValueError(f"No credentials found for user {user_name}")
    
    return config


def find_strategyb_reports(num_reports):
    """Find the most recent N StrategyB report files"""
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    pattern = os.path.join(results_dir, "StrategyB_Report_*.xlsx")
    files = glob.glob(pattern)
    
    if not files:
        logger.error("No StrategyB report files found")
        return []
    
    # Sort by filename (which includes timestamp) to get the latest N files
    sorted_files = sorted(files)
    recent_files = sorted_files[-num_reports:] if len(sorted_files) >= num_reports else sorted_files
    
    logger.info(f"Found {len(recent_files)} StrategyB reports to analyze:")
    for i, file in enumerate(recent_files):
        logger.info(f"{i+1}. {os.path.basename(file)}")
    
    return recent_files


def extract_report_timestamp(filename):
    """Extract timestamp from StrategyB report filename"""
    try:
        # Extract timestamp from filename like "StrategyB_Report_20250617_160056.xlsx"
        basename = os.path.basename(filename)
        timestamp_part = basename.replace("StrategyB_Report_", "").replace(".xlsx", "")
        date_part, time_part = timestamp_part.split("_")
        
        # Parse datetime
        report_datetime = datetime.datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
        return report_datetime
    except Exception as e:
        logger.error(f"Error parsing timestamp from {filename}: {e}")
        return None


def get_current_price_data(kite, tickers):
    """Get current price data for tickers to calculate KC"""
    try:
        # Convert tickers to instrument tokens if needed
        ticker_list = [ticker.strip() for ticker in tickers]
        
        # Get current quotes
        quotes = kite.quote(ticker_list)
        
        price_data = {}
        for ticker in ticker_list:
            if ticker in quotes:
                price_data[ticker] = {
                    'close': quotes[ticker]['last_price'],
                    'high': quotes[ticker]['ohlc']['high'],
                    'low': quotes[ticker]['ohlc']['low'],
                    'open': quotes[ticker]['ohlc']['open']
                }
        
        return price_data
    except Exception as e:
        logger.error(f"Error fetching current price data: {e}")
        return {}


# Global cache for instruments
_instruments_cache = {}

def load_instruments_from_csv():
    """Load instruments from local CSV file"""
    global _instruments_cache
    
    if _instruments_cache:
        return _instruments_cache
    
    try:
        instruments_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "utils", "instruments_backup.csv")
        
        if not os.path.exists(instruments_file):
            logger.error(f"Instruments file not found: {instruments_file}")
            return {}
        
        logger.info("Loading instruments from local CSV file...")
        
        # Read CSV file
        instruments_df = pd.read_csv(instruments_file)
        
        # Create mapping from tradingsymbol to instrument_token
        for _, row in instruments_df.iterrows():
            symbol = row['tradingsymbol']
            token = row['instrument_token']
            _instruments_cache[symbol] = token
        
        logger.info(f"Loaded {len(_instruments_cache)} instruments from CSV file")
        return _instruments_cache
        
    except Exception as e:
        logger.error(f"Error loading instruments from CSV: {e}")
        return {}


def get_instrument_token(ticker_symbol):
    """Get instrument token for a ticker symbol"""
    try:
        # Load instruments cache if not already loaded
        instruments_cache = load_instruments_from_csv()
        
        if ticker_symbol in instruments_cache:
            return instruments_cache[ticker_symbol]
        
        logger.warning(f"Instrument token not found for {ticker_symbol}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting instrument token for {ticker_symbol}: {e}")
        return None


def check_kc_breakout_since_report(kite, ticker, report_timestamp, direction):
    """Check if ticker had KC breakout since the report timestamp"""
    try:
        import time
        from datetime import datetime, timedelta
        
        # Get instrument token for the ticker
        instrument_token = get_instrument_token(ticker)
        if instrument_token is None:
            logger.error(f"Could not find instrument token for {ticker}")
            return None
        
        logger.info(f"   Getting data for {ticker} (token: {instrument_token})")
        
        # Get historical data from report timestamp to now (hourly data)
        start_date = report_timestamp - timedelta(days=10)  # 10 days should give us enough hourly data for KC calculation
        end_date = datetime.now()
        
        # Add rate limiting to avoid overwhelming the API
        time.sleep(0.2)  # 200ms delay between calls
        
        try:
            # Get hourly data for KC breakout detection
            historical_data = kite.historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval="hour"
            )
        except Exception as api_error:
            logger.error(f"API error for {ticker}: {api_error}")
            return None
        
        if not historical_data:
            logger.warning(f"No historical data returned for {ticker} - API returned empty data")
            return None
            
        logger.info(f"   Retrieved {len(historical_data)} hourly data points for {ticker}")
            
        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate hourly KC parameters (using 20-period for hourly data)
        kc_period = 20  # 20 hours for hourly KC
        
        # Calculate 20-period SMA on hourly data
        df['SMA20'] = df['close'].rolling(window=kc_period).mean()
        
        # Calculate ATR (Average True Range) on hourly data
        df['TR'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['ATR'] = df['TR'].rolling(window=kc_period).mean()
        
        # Calculate Keltner Channels (using 2 * ATR multiplier)
        df['KC_Upper'] = df['SMA20'] + (2 * df['ATR'])
        df['KC_Lower'] = df['SMA20'] - (2 * df['ATR'])
        
        # Remove rows with NaN values (first 19 rows won't have SMA/ATR)
        df = df.dropna().copy()
        
        if df.empty:
            logger.warning(f"No valid data after hourly KC calculation for {ticker}")
            return None
        
        logger.info(f"   Calculated hourly KC for {ticker}: Latest Close={df.iloc[-1]['close']:.2f}, KC_Upper={df.iloc[-1]['KC_Upper']:.2f}, KC_Lower={df.iloc[-1]['KC_Lower']:.2f}")
        
        # Debug: Show sample of data timestamps
        logger.info(f"   API data timestamp range: {df['date'].min()} to {df['date'].max()}")
        logger.info(f"   Report timestamp: {report_timestamp}")
        
        # Filter data from report timestamp onwards
        # Robust approach: handle timezone and format issues
        try:
            # Convert report timestamp to naive datetime
            if hasattr(report_timestamp, 'tz_localize'):
                # It's already a pandas timestamp
                report_date = report_timestamp.tz_localize(None) if report_timestamp.tz is None else report_timestamp.tz_convert(None)
            elif hasattr(report_timestamp, 'replace') and hasattr(report_timestamp, 'tzinfo'):
                # It's a Python datetime with timezone
                report_date = report_timestamp.replace(tzinfo=None)
            else:
                # Convert to pandas timestamp and make naive
                report_date = pd.to_datetime(report_timestamp)
                if hasattr(report_date, 'tz') and report_date.tz is not None:
                    report_date = report_date.tz_localize(None)
            
            # Convert DataFrame dates to naive
            if df['date'].dt.tz is not None:
                df['date'] = df['date'].dt.tz_convert(None)
            
            logger.info(f"   Normalized report timestamp: {report_date}")
            logger.info(f"   Normalized API data range: {df['date'].min()} to {df['date'].max()}")
            
            # Filter hourly data from report timestamp onwards
            df_since_report = df[df['date'] >= report_date].copy()
            
            logger.info(f"   Records after timestamp filter: {len(df_since_report)}")
            
        except Exception as tz_error:
            logger.warning(f"Timezone conversion issue for {ticker}: {tz_error}. Using relaxed filtering.")
            # Relaxed fallback: if report is today, just get today's data
            today_str = str(report_timestamp)[:10]  # Get YYYY-MM-DD part
            df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
            df_since_report = df[df['date_str'] >= today_str].copy()
            df_since_report = df_since_report.drop('date_str', axis=1)
            logger.info(f"   Using fallback filter: {len(df_since_report)} records")
        
        if df_since_report.empty:
            logger.warning(f"No data found for {ticker} since report timestamp {report_timestamp}")
            # Last resort: check if current price is above KC at any point today
            logger.info(f"   Trying fallback: checking if current price shows KC breakout")
            current_close = df.iloc[-1]['close']
            current_kc_upper = df.iloc[-1]['KC_Upper']
            current_kc_lower = df.iloc[-1]['KC_Lower']
            
            # Check current price against KC levels
            if direction == 'LONG' and current_close >= current_kc_upper:
                logger.info(f"   💡 FALLBACK: Current price {current_close} >= KC_Upper {current_kc_upper} - treating as breakout")
                return {
                    'breakout_occurred': True,
                    'breakout_date': df.iloc[-1]['date'],
                    'breakout_price': current_close,
                    'kc_level': current_kc_upper,
                    'current_close': current_close,
                    'current_kc_upper': current_kc_upper,
                    'current_kc_lower': current_kc_lower
                }
            elif direction == 'SHORT' and current_close <= current_kc_lower:
                logger.info(f"   💡 FALLBACK: Current price {current_close} <= KC_Lower {current_kc_lower} - treating as breakout")
                return {
                    'breakout_occurred': True,
                    'breakout_date': df.iloc[-1]['date'],
                    'breakout_price': current_close,
                    'kc_level': current_kc_lower,
                    'current_close': current_close,
                    'current_kc_upper': current_kc_upper,
                    'current_kc_lower': current_kc_lower
                }
            
            return None
        
        logger.info(f"   Found {len(df_since_report)} hourly records for {ticker} since report timestamp")
        
        # Check for breakouts since report
        breakout_info = {
            'breakout_occurred': False,
            'breakout_date': None,
            'breakout_price': None,
            'kc_level': None,
            'current_close': df.iloc[-1]['close'],
            'current_kc_upper': df.iloc[-1]['KC_Upper'],
            'current_kc_lower': df.iloc[-1]['KC_Lower']
        }
        
        # Check for hourly KC breakouts since report
        for _, row in df_since_report.iterrows():
            if direction == 'LONG' and row['close'] >= row['KC_Upper']:
                breakout_info['breakout_occurred'] = True
                breakout_info['breakout_date'] = row['date']
                breakout_info['breakout_price'] = row['close']
                breakout_info['kc_level'] = row['KC_Upper']
                logger.info(f"   📈 Hourly KC breakout found for {ticker} at {row['date']}")
                break
            elif direction == 'SHORT' and row['close'] <= row['KC_Lower']:
                breakout_info['breakout_occurred'] = True
                breakout_info['breakout_date'] = row['date']
                breakout_info['breakout_price'] = row['close']
                breakout_info['kc_level'] = row['KC_Lower']
                logger.info(f"   📉 Hourly KC breakdown found for {ticker} at {row['date']}")
                break
        
        # Log the result
        if breakout_info['breakout_occurred']:
            logger.info(f"   ✅ KC breakout detected for {ticker}")
        else:
            logger.info(f"   ❌ No KC breakout found for {ticker} since report")
        
        return breakout_info
        
    except Exception as e:
        logger.error(f"Error checking KC breakout for {ticker}: {e}")
        return None


def process_multiple_reports(report_files, user_name="Sai"):
    """Process multiple StrategyB reports and check for KC breakouts since each report"""
    
    # Load config and connect to Kite
    try:
        config = load_daily_config(user_name)
        credential_section = f'API_CREDENTIALS_{user_name}'
        
        KITE_API_KEY = config.get(credential_section, 'api_key')
        ACCESS_TOKEN = config.get(credential_section, 'access_token')
        
        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        
        logger.info("Connected to Kite API successfully")
        
        # Load instruments cache from CSV file
        logger.info("Loading instruments for symbol-to-token mapping...")
        load_instruments_from_csv()
        
    except Exception as e:
        logger.error(f"Failed to connect to Kite API: {e}")
        logger.warning("Cannot proceed without Kite API connection for real-time data")
        return pd.DataFrame()
    
    all_breakout_results = []
    
    for report_file in report_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing report: {os.path.basename(report_file)}")
        logger.info(f"{'='*60}")
        
        # Extract report timestamp
        report_timestamp = extract_report_timestamp(report_file)
        if report_timestamp is None:
            logger.warning(f"Skipping {report_file} - could not parse timestamp")
            continue
        
        logger.info(f"Report timestamp: {report_timestamp}")
        
        try:
            # Load the report data
            df = pd.read_excel(report_file)
            logger.info(f"Loaded {len(df)} tickers from report")
            
            # Process each ticker in the report
            for _, row in df.iterrows():
                ticker = row['Ticker']
                direction = row['Direction']
                
                logger.info(f"Checking {ticker} ({direction}) for KC breakout since report...")
                
                try:
                    # Check for KC breakout since report timestamp
                    breakout_info = check_kc_breakout_since_report(kite, ticker, report_timestamp, direction)
                    
                    if breakout_info is None:
                        logger.warning(f"Could not get breakout data for {ticker}")
                        continue
                    
                    if breakout_info['breakout_occurred']:
                        logger.info(f"✅ {ticker}: KC BREAKOUT DETECTED!")
                        logger.info(f"   Report Date: {report_timestamp}")
                        logger.info(f"   Breakout Date: {breakout_info['breakout_date']}")
                        logger.info(f"   Breakout Price: {breakout_info['breakout_price']:.2f}")
                        logger.info(f"   KC Level: {breakout_info['kc_level']:.2f}")
                        logger.info(f"   Current Price: {breakout_info['current_close']:.2f}")
                        
                        # Create result record
                        result_record = row.to_dict()
                        result_record['Report_File'] = os.path.basename(report_file)
                        result_record['Report_Timestamp'] = report_timestamp
                        result_record['Breakout_Date'] = breakout_info['breakout_date']
                        result_record['Breakout_Price'] = breakout_info['breakout_price']
                        result_record['KC_Level_at_Breakout'] = breakout_info['kc_level']
                        result_record['Current_Close'] = breakout_info['current_close']
                        result_record['Current_KC_Upper'] = breakout_info['current_kc_upper']
                        result_record['Current_KC_Lower'] = breakout_info['current_kc_lower']
                        result_record['Days_Since_Report'] = (datetime.datetime.now() - report_timestamp).days
                        
                        # Calculate gain/loss since breakout
                        if breakout_info['breakout_price'] > 0:
                            result_record['Gain_Since_Breakout_Pct'] = ((breakout_info['current_close'] - breakout_info['breakout_price']) / breakout_info['breakout_price']) * 100
                        else:
                            result_record['Gain_Since_Breakout_Pct'] = 0
                        
                        all_breakout_results.append(result_record)
                    else:
                        logger.info(f"   No KC breakout detected for {ticker} since report")
                        
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing report {report_file}: {e}")
            continue
    
    # Create final results DataFrame
    if all_breakout_results:
        results_df = pd.DataFrame(all_breakout_results)
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY: Found {len(results_df)} KC breakouts across all reports")
        logger.info(f"{'='*60}")
        return results_df
    else:
        logger.warning("No KC breakouts found across all reports")
        return pd.DataFrame()


def save_results(df):
    """Save the filtered results to StrategyC_{date}_{time}.xlsx"""
    if df.empty:
        logger.warning("No KC breakouts found to save")
        return
    
    # Generate output filename with StrategyC format
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    output_file = os.path.join(results_dir, f"StrategyC_{date_str}_{time_str}.xlsx")
    
    # Ensure output directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Sort by breakout date (most recent first)
    df_sorted = df.sort_values('Breakout_Date', ascending=False)
    
    # Save to Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Main filtered results
        df_sorted.to_excel(writer, sheet_name='KC_Breakouts', index=False)
        
        # Helper function to safely calculate mean for potentially non-numeric columns
        def safe_mean(series):
            try:
                # Convert to numeric, errors='coerce' will turn non-numeric to NaN
                numeric_series = pd.to_numeric(series, errors='coerce')
                return numeric_series.mean()
            except:
                return 0
        
        # Summary statistics
        summary_data = {
            'Metric': [
                'Total KC Breakouts Found',
                'Long Position Breakouts', 
                'Short Position Breakouts',
                'Average Score',
                'Average Risk-Reward Ratio',
                'Average Gain Since Breakout (%)',
                'Reports Analyzed',
                'Unique Tickers with Breakouts'
            ],
            'Value': [
                len(df),
                len(df[df['Direction'] == 'LONG']),
                len(df[df['Direction'] == 'SHORT']),
                safe_mean(df['Score']) if 'Score' in df.columns else 0,
                safe_mean(df['Risk_Reward_Ratio']) if 'Risk_Reward_Ratio' in df.columns else 0,
                safe_mean(df['Gain_Since_Breakout_Pct']) if 'Gain_Since_Breakout_Pct' in df.columns else 0,
                len(df['Report_File'].unique()) if 'Report_File' in df.columns else 0,
                len(df['Ticker'].unique()) if 'Ticker' in df.columns else 0
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Top performers by gain
        if 'Gain_Since_Breakout_Pct' in df.columns:
            try:
                # Convert gain column to numeric for sorting
                df_sorted['Gain_Since_Breakout_Pct_Numeric'] = pd.to_numeric(df_sorted['Gain_Since_Breakout_Pct'], errors='coerce')
                top_performers = df_sorted.nlargest(10, 'Gain_Since_Breakout_Pct_Numeric')[
                    ['Ticker', 'Direction', 'Breakout_Date', 'Breakout_Price', 'Current_Close', 'Gain_Since_Breakout_Pct']
                ]
                top_performers.to_excel(writer, sheet_name='Top_Performers', index=False)
            except Exception as e:
                logger.warning(f"Could not create top performers sheet: {e}")
                # Create a simple top performers sheet without sorting
                top_performers = df_sorted.head(10)[
                    ['Ticker', 'Direction', 'Breakout_Date', 'Breakout_Price', 'Current_Close', 'Gain_Since_Breakout_Pct']
                ]
                top_performers.to_excel(writer, sheet_name='Top_Performers', index=False)
    
    logger.info(f"Results saved to: {output_file}")
    logger.info(f"\nTop KC Breakout Results:")
    for i, (_, row) in enumerate(df_sorted.head(10).iterrows()):
        gain_pct = row.get('Gain_Since_Breakout_Pct', 0)
        logger.info(f"{i+1}. {row['Ticker']} ({row['Direction']}) - Breakout: {row['Breakout_Date'].strftime('%Y-%m-%d')}, Gain: {gain_pct:.2f}%")


def get_user_input():
    """Get number of reports to analyze from user"""
    try:
        test_mode = input("\nTest mode with single ticker? (y/N): ").lower().strip()
        if test_mode == 'y':
            return -1  # Special flag for test mode
            
        num_reports = input("\nHow many previous StrategyB reports would you like to analyze? (default: 5): ")
        if not num_reports.strip():
            return 5
        return int(num_reports)
    except ValueError:
        logger.warning("Invalid input, using default of 5 reports")
        return 5


def test_single_ticker(kite):
    """Test KC calculation with a single known ticker"""
    logger.info("=== TEST MODE: Testing with INFY ===")
    
    # Test with INFY 
    test_ticker = "INFY"
    test_timestamp = datetime.datetime(2025, 6, 17, 13, 0, 0)  # Earlier today
    
    logger.info(f"Testing KC breakout for {test_ticker} since {test_timestamp}")
    
    result = check_kc_breakout_since_report(kite, test_ticker, test_timestamp, "LONG")
    
    if result:
        logger.info("✅ Test successful! KC calculation working.")
        logger.info(f"Breakout occurred: {result['breakout_occurred']}")
        logger.info(f"Current close: {result['current_close']}")
        logger.info(f"KC Upper: {result['current_kc_upper']}")
    else:
        logger.error("❌ Test failed - no result returned")
    
    return result is not None


def main():
    """Main execution function"""
    logger.info("Starting StrategyKV-C KC Breakout Analysis")
    logger.info("This script analyzes StrategyB reports and identifies tickers that had KC breakouts since the report timestamp")
    
    # Get user input for number of reports
    num_reports = get_user_input()
    
    # Handle test mode
    if num_reports == -1:
        logger.info("Running in TEST MODE...")
        
        try:
            # Connect to API for test
            config = load_daily_config("Sai")
            credential_section = f'API_CREDENTIALS_Sai'
            
            KITE_API_KEY = config.get(credential_section, 'api_key')
            ACCESS_TOKEN = config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=KITE_API_KEY)
            kite.set_access_token(ACCESS_TOKEN)
            
            logger.info("Connected to Kite API successfully")
            
            # Load instruments
            load_instruments_from_csv()
            
            # Run test
            if test_single_ticker(kite):
                logger.info("✅ Test passed! You can now run the full analysis.")
            else:
                logger.error("❌ Test failed! Check API connection and credentials.")
                
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
        
        return
    
    # Find the reports to analyze
    report_files = find_strategyb_reports(num_reports)
    if not report_files:
        logger.error("No StrategyB reports found. Exiting.")
        return
    
    logger.info(f"\nAnalyzing {len(report_files)} reports for KC breakouts...")
    
    try:
        # Process all reports and find KC breakouts
        breakout_results = process_multiple_reports(report_files)
        
        # Save results
        save_results(breakout_results)
            
    except Exception as e:
        logger.error(f"Error processing reports: {e}")
        raise
    
    logger.info("\nStrategyKV-C KC Breakout Analysis completed!")


if __name__ == "__main__":
    main()