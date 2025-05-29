#!/usr/bin/env python
import os
import glob
import pandas as pd
import numpy as np
from collections import Counter
import sys
import datetime
from kiteconnect import KiteConnect

# Import configuration from Daily/config.ini
import configparser

def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(daily_dir, 'config.ini')
    
    if not os.path.exists(config_path):
        print(f"Error: config.ini not found at {config_path}")
        raise FileNotFoundError(f"config.ini not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        print(f"Error: No credentials found for user {user_name} in {config_path}")
        raise ValueError(f"No credentials found for user {user_name}")
    
    return config, credential_section

# Initialize with default user
user_name = "Sai"  # Default user
KITE_API_KEY = ""
ACCESS_TOKEN = ""

# Initialize KiteConnect client
def initialize_kite():
    """Initialize Kite Connect client with error handling"""
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        return kite
    except Exception as e:
        print(f"Failed to initialize Kite Connect: {e}")
        return None

# Function to detect H2 pattern
def detect_h2_pattern(df, body_percent_threshold=60):
    """
    Detect Al Brooks H2 pattern: strong bull trend bar closing above prior high
    
    Args:
        df (pd.DataFrame): Price data with OHLC columns
        body_percent_threshold (float): Threshold for body percentage (strong body)
        
    Returns:
        pd.Series: Boolean series indicating H2 pattern for each candle
    """
    # Calculate body and range
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = df['High'] - df['Low']
    df['BodyPercent'] = (df['Body'] / df['Range'] * 100).replace([np.inf, -np.inf], 0)
    
    # Check conditions for H2 pattern
    is_bull = df['Close'] > df['Open']  # Bull candle
    close_above_prev_high = df['Close'] > df['High'].shift(1)  # Close above prior high
    strong_body = df['BodyPercent'] >= body_percent_threshold  # Strong body
    
    # Return combined conditions
    return is_bull & close_above_prev_high & strong_body

# Function to analyze H2 patterns for ticker
def analyze_h2_patterns(ticker, timeframe='day', lookback_days=30):
    """
    Analyze H2 patterns for a given ticker and timeframe
    
    Args:
        ticker (str): Ticker symbol
        timeframe (str): Timeframe ('day' or 'hour')
        lookback_days (int): Days to look back for analysis
        
    Returns:
        dict: H2 pattern analysis results
    """
    kite = initialize_kite()
    if not kite:
        return None
    
    try:
        # Calculate date ranges
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=lookback_days)
        
        # Convert to strings
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
        
        # Get instrument token
        instruments = kite.instruments("NSE")
        df_instruments = pd.DataFrame(instruments)
        instrument_df = df_instruments[df_instruments['tradingsymbol'] == ticker]
        
        if instrument_df.empty:
            print(f"Could not find instrument token for {ticker}")
            return None
            
        instrument_token = int(instrument_df.iloc[0]['instrument_token'])
        
        # Fetch historical data
        interval = '60minute' if timeframe == 'hour' else 'day'
        data = kite.historical_data(instrument_token, from_date, to_date, interval)
        
        if not data:
            print(f"No data returned for {ticker} on {timeframe} timeframe")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Rename columns
        df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }, inplace=True)
        
        # Calculate SMA20
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        
        # Calculate weekly vWAP if daily timeframe
        weekly_vwap = None
        if timeframe == 'day':
            df['Date'] = pd.to_datetime(df['Date'])
            df['Year'] = df['Date'].dt.year
            df['Week'] = df['Date'].dt.isocalendar().week
            df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['TPV'] = df['TP'] * df['Volume']
            
            weekly_data = df.groupby(['Year', 'Week']).agg({
                'TPV': 'sum',
                'Volume': 'sum',
                'Date': 'last'
            }).reset_index()
            
            weekly_data['Weekly_VWAP'] = weekly_data['TPV'] / weekly_data['Volume']
            last_vwap = weekly_data.iloc[-1]['Weekly_VWAP'] if not weekly_data.empty else None
            weekly_vwap = last_vwap
        
        # Detect H2 patterns
        df['H2_Pattern'] = detect_h2_pattern(df)
        
        # Check latest candle conditions
        latest = df.iloc[-1]
        above_sma20 = latest['Close'] > latest['SMA20'] if not pd.isna(latest['SMA20']) else False
        latest_h2 = latest['H2_Pattern'] if 'H2_Pattern' in latest else False
        
        # Count H2 patterns in the lookback period
        h2_count = df['H2_Pattern'].sum()
        
        # Check for volume spike (3X threshold)
        df['Vol_Avg_3'] = df['Volume'].rolling(window=3).mean().shift(1)
        df['Volume_Ratio'] = df['Volume'] / df['Vol_Avg_3']
        volume_spike = latest['Volume_Ratio'] >= 3.0 if not pd.isna(latest.get('Volume_Ratio')) else False
        
        result = {
            'Ticker': ticker,
            'Timeframe': timeframe,
            'Current_Price': latest['Close'],
            'Above_SMA20': above_sma20,
            'Latest_H2': latest_h2,
            'H2_Count': h2_count,
            'Volume_Spike': volume_spike
        }
        
        if weekly_vwap is not None:
            result['Weekly_VWAP'] = weekly_vwap
            result['Above_Weekly_VWAP'] = latest['Close'] > weekly_vwap
        
        return result
    
    except Exception as e:
        print(f"Error analyzing H2 patterns for {ticker}: {e}")
        return None

def analyze_ticker_frequency(file_pattern, label="", top_n=20):
    """Analyze the frequency of tickers in signal files"""
    print(f"\n{label} - Analyzing files matching pattern: {file_pattern}")
    
    # Find matching files
    files = glob.glob(file_pattern)
    print(f"Found {len(files)} files")
    
    if not files:
        print("No files found matching the pattern.")
        return None
    
    # Dictionary to store ticker counts
    ticker_counter = Counter()
    
    # Process each file
    for file_path in files:
        try:
            print(f"Processing {os.path.basename(file_path)}")
            # Load the Excel file
            df = pd.read_excel(file_path)
            
            # Check if 'Ticker' column exists
            if 'Ticker' in df.columns:
                # Count occurrences per file to avoid biasing toward multiple entries in a single file
                file_tickers = df['Ticker'].tolist()
                ticker_counter.update(file_tickers)
            else:
                print(f"Warning: No 'Ticker' column found in {os.path.basename(file_path)}")
                
        except Exception as e:
            print(f"Error processing {os.path.basename(file_path)}: {e}")
    
    # Get the most common tickers
    most_common = ticker_counter.most_common(top_n)
    
    print(f"\nTop {top_n} Most Frequent {label} Tickers:")
    print("=" * (30 + len(label)))
    for ticker, count in most_common:
        print(f"{ticker}: {count} occurrences")
    
    if most_common:
        most_common_ticker, count = most_common[0]
        print(f"\nThe most frequently occurring {label} ticker is {most_common_ticker} with {count} occurrences.")
    else:
        print(f"\nNo {label} tickers found in the analyzed files.")
    
    return most_common

def analyze_top_tickers_for_h2_patterns(tickers, timeframes=['day', 'hour']):
    """
    Analyze H2 patterns for top tickers in both daily and hourly timeframes
    
    Args:
        tickers (list): List of (ticker, count) tuples to analyze
        timeframes (list): List of timeframes to analyze
        
    Returns:
        dict: Dictionary with analysis results for each timeframe
    """
    if not tickers:
        return {}
    
    print("\n\n=============================================")
    print("          H2 PATTERN ANALYSIS               ")
    print("=============================================")
    
    results = {}
    for timeframe in timeframes:
        print(f"\nAnalyzing {timeframe.upper()} timeframe for H2 patterns...")
        timeframe_results = []
        
        for ticker, _ in tickers:
            print(f"Analyzing {ticker} on {timeframe} timeframe...")
            result = analyze_h2_patterns(ticker, timeframe)
            if result:
                timeframe_results.append(result)
        
        results[f"H2_{timeframe.capitalize()}"] = timeframe_results
    
    return results

def generate_summary_report(long_tickers, short_tickers):
    """Generate a summary report comparing long and short tickers"""
    if not long_tickers and not short_tickers:
        return None
    
    print("\n\n=============================================")
    print("            SUMMARY COMPARISON              ")
    print("=============================================")
    
    # Initialize dictionaries
    long_dict = {}
    short_dict = {}
    
    # Convert to dictionaries for easier lookup
    if long_tickers:
        long_dict = dict(long_tickers)
    if short_tickers:
        short_dict = dict(short_tickers)
    
    # Initialize lists to store report data
    common_tickers_data = []
    long_to_short_ratios = []
    short_to_long_ratios = []
    
    # Find tickers appearing in both lists
    common_tickers = set(long_dict.keys()) & set(short_dict.keys())
    
    if common_tickers:
        print("\nTickers appearing in both LONG and SHORT signals:")
        print("=================================================")
        for ticker in common_tickers:
            print(f"{ticker}: {long_dict[ticker]} long occurrences, {short_dict[ticker]} short occurrences")
            common_tickers_data.append({
                'Ticker': ticker,
                'Long_Count': long_dict[ticker],
                'Short_Count': short_dict[ticker]
            })
    
    # Calculate frequency ratios
    ratios = []
    if common_tickers:
        for ticker in common_tickers:
            long_count = long_dict[ticker]
            short_count = short_dict[ticker]
            if short_count > 0:  # Avoid division by zero
                ratio = long_count / short_count
                ratios.append((ticker, ratio, long_count, short_count))
            elif long_count > 0:  # All long, no short
                ratios.append((ticker, float('inf'), long_count, short_count))
        
        if ratios:
            # Sort by ratio (descending)
            ratios.sort(key=lambda x: x[1], reverse=True)
            
            print("\nTickers with highest long-to-short ratio:")
            print("==========================================")
            for ticker, ratio, long_count, short_count in ratios[:5]:
                if ratio == float('inf'):
                    ratio_str = "∞"
                    ratio_val = 999.99  # For Excel
                else:
                    ratio_str = f"{ratio:.2f}"
                    ratio_val = ratio
                print(f"{ticker}: {ratio_str} ratio ({long_count} long / {short_count} short)")
                long_to_short_ratios.append({
                    'Ticker': ticker,
                    'Ratio': ratio_val,
                    'Long_Count': long_count,
                    'Short_Count': short_count
                })
            
            # Sort by reverse ratio (short/long)
            ratios.sort(key=lambda x: 1/x[1] if x[1] > 0 else 0, reverse=True)
            
            print("\nTickers with highest short-to-long ratio:")
            print("==========================================")
            for ticker, ratio, long_count, short_count in ratios[:5]:
                if ratio > 0:
                    inv_ratio = 1 / ratio
                    ratio_str = f"{inv_ratio:.2f}"
                    print(f"{ticker}: {ratio_str} ratio ({short_count} short / {long_count} long)")
                    short_to_long_ratios.append({
                        'Ticker': ticker,
                        'Ratio': inv_ratio,
                        'Long_Count': long_count,
                        'Short_Count': short_count
                    })
    
    # Create a dictionary of DataFrames for Excel sheets
    report_data = {
        'Long_Tickers': pd.DataFrame([{'Ticker': t, 'Count': c} for t, c in long_dict.items()]) if long_dict else pd.DataFrame(),
        'Short_Tickers': pd.DataFrame([{'Ticker': t, 'Count': c} for t, c in short_dict.items()]) if short_dict else pd.DataFrame(),
        'Common_Tickers': pd.DataFrame(common_tickers_data),
        'Long_To_Short_Ratio': pd.DataFrame(long_to_short_ratios),
        'Short_To_Long_Ratio': pd.DataFrame(short_to_long_ratios)
    }
    
    return report_data

def save_to_excel(report_data, output_file):
    """Save report data to Excel file with multiple sheets"""
    if not report_data:
        print("No data to save to Excel.")
        return
    
    try:
        # Create a Pandas Excel writer using openpyxl as the engine
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Write each dataframe or list to a different worksheet
            for sheet_name, data in report_data.items():
                if isinstance(data, pd.DataFrame) and not data.empty:
                    # Sort dataframes by count/ratio in descending order
                    if 'Count' in data.columns:
                        data = data.sort_values(by='Count', ascending=False)
                    elif 'Ratio' in data.columns:
                        data = data.sort_values(by='Ratio', ascending=False)
                    
                    data.to_excel(writer, sheet_name=sheet_name, index=False)
                elif isinstance(data, list) and data:
                    # Convert list of dictionaries to DataFrame
                    df = pd.DataFrame(data)
                    if not df.empty:
                        if 'Above_SMA20' in df.columns and 'Latest_H2' in df.columns:
                            # Calculate score for H2 analysis based on criteria met
                            score_cols = ['Above_SMA20', 'Latest_H2', 'Volume_Spike']
                            if 'Above_Weekly_VWAP' in df.columns:
                                score_cols.append('Above_Weekly_VWAP')
                            
                            # Create Score column
                            df['Score'] = 0
                            for col in score_cols:
                                if col in df.columns:
                                    df['Score'] += df[col].astype(int)
                            
                            # Sort by score (descending)
                            df = df.sort_values(by='Score', ascending=False)
                        
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"\nAnalysis saved to Excel file: {output_file}")
    except Exception as e:
        print(f"Error saving to Excel: {e}")

if __name__ == "__main__":
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Analyze ticker frequency in signal files')
    parser.add_argument('--user', '-u', type=str, default='Sai',
                        help='User whose API credentials to use (default: Sai)')
    parser.add_argument('--long', '-l', type=str, 
                        help='File pattern for long signals')
    parser.add_argument('--short', '-s', type=str,
                        help='File pattern for short signals')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file path')
    
    args = parser.parse_args()
    
    # Try to load user credentials
    try:
        config, credential_section = load_daily_config(args.user)
        KITE_API_KEY = config.get(credential_section, 'api_key')
        ACCESS_TOKEN = config.get(credential_section, 'access_token')
        print(f"Using credentials for user: {args.user}")
    except Exception as e:
        print(f"Error: Could not load credentials for {args.user}: {e}")
        sys.exit(1)
    
    # Define file patterns
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), "data")
    
    # Create data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
    # Set file patterns
    if args.long:
        long_pattern = args.long
    else:
        long_pattern = os.path.join(data_dir, "EMA_KV_F_Zerodha_hour*.xlsx")
    
    if args.short:
        short_pattern = args.short
    else:
        short_pattern = os.path.join(data_dir, "EMA_KV_F_Short_Zerodha_hour*.xlsx")
    
    # Get current date for output filename
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    if args.output:
        output_file = args.output
    else:
        output_file = os.path.join(data_dir, f"Hourly_summary_{args.user}_{current_date}.xlsx")
    
    # Analyze long tickers
    long_tickers = analyze_ticker_frequency(long_pattern, "LONG", 20)
    
    # Analyze short tickers
    short_tickers = analyze_ticker_frequency(short_pattern, "SHORT", 10)
    
    # Generate summary report
    report_data = generate_summary_report(long_tickers, short_tickers)
    
    # Run H2 pattern analysis on top tickers
    top_tickers_for_h2 = []
    if long_tickers:
        # Get top 10 long tickers
        top_tickers_for_h2.extend(long_tickers[:min(10, len(long_tickers))])
    
    print("\nRunning H2 pattern analysis on top tickers...")
    h2_results = analyze_top_tickers_for_h2_patterns(top_tickers_for_h2)
    
    # Add H2 pattern analysis to report
    if h2_results and report_data:
        for key, value in h2_results.items():
            report_data[key] = value
    
    # Save to Excel
    if report_data:
        save_to_excel(report_data, output_file)