#!/usr/bin/env python

import os
import sys
import logging
import argparse
import concurrent.futures
import time
from datetime import datetime
import pandas as pd
import numpy as np

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create scan_market_BTPB.log in the log directory
    log_file = os.path.join(log_dir, 'scan_market_BTPB.log')
    
    # Configure logging
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized at level {log_level}")
    
    return logger

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Scan market for Bull Trend Pullback opportunities")
    parser.add_argument(
        "-i", "--input", 
        help="Path to input Excel file with ticker list"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    return parser.parse_args()

class BullTrendPullbackScanner:
    """Scans for Bull Trend Pullback trading opportunities"""
    
    def __init__(self):
        self.config = get_config()
        self.data_handler = get_data_handler()
        
        # Trading parameters
        self.exchange = self.config.get('Trading', 'exchange')
        self.max_workers = min(self.config.get_int('Scanner', 'max_workers', fallback=8), 4)  # Limit to max 4 for rate limiting
        self.account_value = self.config.get_float('Trading', 'account_value', fallback=100000.0)
        
        # Timeframe settings - configurable via config.ini
        self.interval = 'day'  # Default to daily, will be updated from config
        
        # Strategy parameters
        self.swing_lookback = 10        # Bars to look back for swing points
        self.pullback_length = 3        # Max number of bars in pullback
        self.min_pullback_length = 2    # Min number of bars in pullback
        self.num_swing_lows = 3         # Number of consecutive swing lows to check for higher lows
        self.ema_period = 20            # EMA period
        self.rsi_period = 14            # RSI calculation period
        self.rsi_oversold = 40          # RSI oversold level in bull trend
        self.volume_factor = 1.2        # Volume confirmation factor (1.2 = 20% above average)
        self.atr_period = 14            # ATR for stop loss and volatility assessment
        
        # Required columns for the summary output
        self.required_columns = [
            'Ticker', 'Date', 'Close', 'Signal_Strength', 'Reversal_Type',
            'ATR', 'PosSize', 'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Target3', 'Current_Close'
        ]
    
    def calculate_atr(self, data, period=None):
        """
        Compute the ATR (Average True Range) from historical data.
        Expects data with 'high', 'low', and 'close' columns.
        """
        if period is None:
            period = self.atr_period
            
        data_copy = data.copy()
        data_copy['prev_close'] = data_copy['Close'].shift(1)
        data_copy['tr'] = data_copy.apply(
            lambda row: max(
                row['High'] - row['Low'],
                abs(row['High'] - row['prev_close']) if pd.notnull(row['prev_close']) else 0,
                abs(row['Low'] - row['prev_close']) if pd.notnull(row['prev_close']) else 0
            ),
            axis=1
        )
        atr = data_copy['tr'].rolling(window=period).mean()
        return atr

    def calculate_rsi(self, data, period=None):
        """Calculate RSI indicator on the dataframe"""
        if period is None:
            period = self.rsi_period
            
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Avoid division by zero
        rs = gain / loss.replace(0, 0.001)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_ema(self, data, period=None):
        """Calculate EMA indicator on the dataframe"""
        if period is None:
            period = self.ema_period
            
        return data['Close'].ewm(span=period, adjust=False).mean()
    
    def identify_swing_points(self, df, lookback=None):
        """Identify swing highs and lows for trend analysis"""
        if lookback is None:
            lookback = self.swing_lookback
            
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
        
        # Initialize columns
        df_copy['swing_high'] = False
        df_copy['swing_low'] = False
        
        for i in range(lookback, len(df_copy) - lookback):
            # Current price window
            window = df_copy.iloc[i-lookback:i+lookback+1]
            
            # Check if this is a swing high
            if df_copy.iloc[i]['High'] == window['High'].max():
                df_copy.loc[df_copy.index[i], 'swing_high'] = True
                
            # Check if this is a swing low
            if df_copy.iloc[i]['Low'] == window['Low'].min():
                df_copy.loc[df_copy.index[i], 'swing_low'] = True
        
        return df_copy
    
    def identify_bull_trend(self, df):
        """
        Identify if price is in a bull trend based on:
        1. Higher lows
        2. Price above 20 EMA
        3. Upward sloping 20 EMA
        """
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
        
        # Get swing points
        df_copy = self.identify_swing_points(df_copy)
        
        # Calculate 20 EMA
        if 'ema20' not in df_copy.columns:
            df_copy['ema20'] = self.calculate_ema(df_copy, 20)
            
        # Find swing low points
        swing_lows = df_copy[df_copy['swing_low']].sort_index()
        
        # Number of consecutive swing lows to check (default is 3)
        num_lows_to_check = min(self.num_swing_lows, len(swing_lows))
        
        # Need at least 2 swing low points and enough data for EMA
        if len(swing_lows) < num_lows_to_check or len(df_copy) < 30:
            return False, df_copy
        
        # Get the last N swing lows
        recent_lows = swing_lows.iloc[-num_lows_to_check:]['Low'].values
        
        # Check if lows are consistently rising (higher lows)
        # This is true if each low is higher than the previous one
        higher_lows = True
        for i in range(1, len(recent_lows)):
            if recent_lows[i] <= recent_lows[i-1]:
                higher_lows = False
                break
        
        # Check if price is above 20 EMA
        last_close = df_copy.iloc[-1]['Close']
        last_ema = df_copy.iloc[-1]['ema20']
        price_above_ema = last_close > last_ema
        
        # Check if EMA is sloping upward (current EMA > EMA 5 bars ago)
        ema_5_bars_ago = df_copy.iloc[-6]['ema20'] if len(df_copy) >= 6 else df_copy.iloc[0]['ema20']
        ema_upward_slope = last_ema > ema_5_bars_ago
        
        # Bull trend requires at least 2 out of 3 conditions
        conditions_met = sum([higher_lows, price_above_ema, ema_upward_slope])
        bull_trend = conditions_met >= 2
        
        # Initialize bull_trend column if it doesn't exist
        if 'bull_trend' not in df_copy.columns:
            df_copy['bull_trend'] = False
            
        # Mark bull trend in dataframe for last N bars
        if bull_trend:
            df_copy.loc[df_copy.index[-15:], 'bull_trend'] = True
        
        return bull_trend, df_copy
    
    def identify_pullback(self, df, min_bars=None, max_bars=None):
        """
        Identify pullbacks in a bull trend (2-3 consecutive bearish bars)
        """
        if min_bars is None:
            min_bars = self.min_pullback_length
        if max_bars is None:
            max_bars = self.pullback_length
            
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
            
        # Initialize pullback columns
        df_copy['pullback'] = False
        df_copy['pullback_bars'] = 0
        
        # Only check recent bars for pullbacks
        for i in range(max(max_bars, 10), len(df_copy)):
            # Only look for pullbacks in bull trends
            if not df_copy.iloc[i-1].get('bull_trend', False):
                continue
            
            # Count consecutive bearish bars
            bearish_count = 0
            for j in range(i, max(0, i-max_bars), -1):
                # Bearish bar: close < open
                if df_copy.iloc[j]['Close'] < df_copy.iloc[j]['Open']:
                    bearish_count += 1
                else:
                    break
            
            # If we have the right number of bearish bars
            if min_bars <= bearish_count <= max_bars:
                df_copy.loc[df_copy.index[i], 'pullback'] = True
                df_copy.loc[df_copy.index[i], 'pullback_bars'] = bearish_count
                
                # Find the lowest point of the pullback
                pullback_start = max(0, i - bearish_count)
                pullback_bars = df_copy.iloc[pullback_start:i+1]
                df_copy.loc[df_copy.index[i], 'pullback_low'] = pullback_bars['Low'].min()
        
        return df_copy
    
    def identify_reversal_bar(self, df):
        """
        Identify bullish reversal bars: higher low or inside bar after pullback
        """
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
        
        # Initialize reversal columns
        df_copy['reversal_bar'] = False
        df_copy['reversal_type'] = None
        
        # Only check the most recent bars
        for i in range(5, len(df_copy)):
            # Look for pullback completion
            if df_copy.iloc[i-1].get('pullback', False):
                current_bar = df_copy.iloc[i]
                prev_bar = df_copy.iloc[i-1]
                
                # Higher low pattern (low > previous low)
                higher_low = current_bar['Low'] > prev_bar['Low']
                
                # Bullish bar (close > open)
                bullish_bar = current_bar['Close'] > current_bar['Open']
                
                # Inside bar pattern
                inside_bar = (current_bar['High'] <= prev_bar['High'] and 
                              current_bar['Low'] >= prev_bar['Low'])
                
                # Volume confirmation if available
                volume_confirmed = True
                if 'Volume' in df_copy.columns:
                    avg_volume = df_copy['Volume'].rolling(5).mean().iloc[i-1]
                    volume_confirmed = current_bar['Volume'] >= avg_volume * self.volume_factor
                
                # Bullish engulfing pattern
                bullish_engulfing = (current_bar['Close'] > prev_bar['Open'] and
                                     current_bar['Open'] < prev_bar['Close'] and
                                     bullish_bar)
                
                # RSI confirmation if in oversold territory during bull trend
                rsi_confirmed = True
                if 'rsi' in df_copy.columns:
                    rsi_confirmed = df_copy['rsi'].iloc[i-1] <= self.rsi_oversold
                
                # Check reversal conditions and set entry and stop levels
                if bullish_bar and higher_low:
                    df_copy.loc[df_copy.index[i], 'reversal_bar'] = True
                    df_copy.loc[df_copy.index[i], 'reversal_type'] = 'higher_low'
                    df_copy.loc[df_copy.index[i], 'entry_price'] = current_bar['High']  # Entry above high
                    df_copy.loc[df_copy.index[i], 'stop_loss'] = current_bar['Low'] - (0.1 * self.calculate_atr(df_copy).iloc[i])
                    df_copy.loc[df_copy.index[i], 'volume_confirmed'] = volume_confirmed
                    df_copy.loc[df_copy.index[i], 'rsi_confirmed'] = rsi_confirmed
                    
                elif inside_bar:
                    df_copy.loc[df_copy.index[i], 'reversal_bar'] = True
                    df_copy.loc[df_copy.index[i], 'reversal_type'] = 'inside_bar'
                    df_copy.loc[df_copy.index[i], 'entry_price'] = current_bar['High']  # Entry above high
                    df_copy.loc[df_copy.index[i], 'stop_loss'] = current_bar['Low'] - (0.1 * self.calculate_atr(df_copy).iloc[i])
                    df_copy.loc[df_copy.index[i], 'volume_confirmed'] = volume_confirmed
                    df_copy.loc[df_copy.index[i], 'rsi_confirmed'] = rsi_confirmed
                    
                elif bullish_engulfing:
                    df_copy.loc[df_copy.index[i], 'reversal_bar'] = True
                    df_copy.loc[df_copy.index[i], 'reversal_type'] = 'engulfing'
                    df_copy.loc[df_copy.index[i], 'entry_price'] = current_bar['High']  # Entry above high
                    df_copy.loc[df_copy.index[i], 'stop_loss'] = current_bar['Low'] - (0.1 * self.calculate_atr(df_copy).iloc[i])
                    df_copy.loc[df_copy.index[i], 'volume_confirmed'] = volume_confirmed
                    df_copy.loc[df_copy.index[i], 'rsi_confirmed'] = rsi_confirmed
        
        return df_copy
    
    def calculate_targets(self, df):
        """
        Calculate take profit targets for bull trend pullback trades
        """
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
        
        for i in range(len(df_copy)):
            if df_copy.iloc[i].get('reversal_bar', False):
                # Entry and stop loss prices
                entry_price = df_copy.iloc[i]['entry_price']
                stop_loss = df_copy.iloc[i]['stop_loss']
                risk = entry_price - stop_loss
                
                # Find the last swing high (target 1)
                lookback = min(i, 50)  # Look back up to 50 bars
                prev_bars = df_copy.iloc[max(0, i-lookback):i]
                prev_swing_highs = prev_bars[prev_bars['swing_high']]
                
                # Target 1: Previous swing high
                if not prev_swing_highs.empty:
                    target1 = prev_swing_highs.iloc[-1]['High']
                else:
                    # If no swing high found, use a 1:1 risk-reward
                    target1 = entry_price + risk
                
                # Target 2: 1:2 risk-reward ratio
                target2 = entry_price + (2 * risk)
                
                # Target 3: 1:3 risk-reward ratio
                target3 = entry_price + (3 * risk)
                
                # Store targets
                df_copy.loc[df_copy.index[i], 'target1'] = target1
                df_copy.loc[df_copy.index[i], 'target2'] = target2
                df_copy.loc[df_copy.index[i], 'target3'] = target3
        
        return df_copy
    
    def check_for_entry_signals(self, df, ticker):
        """
        Check for entry signals based on the bull trend pullback strategy
        """
        # Initialize results dictionary for signal data
        signal_data = {
            'Ticker': ticker,
            'Date': None,
            'Close': None,
            'Signal_Strength': 0,
            'Reversal_Type': None,
            'ATR': None,
            'PosSize': None,
            'Entry_Price': None,
            'Stop_Loss': None,
            'Target1': None,
            'Target2': None,
            'Target3': None,
            'Current_Close': None,
            'Volume_Confirmed': False,
            'RSI_Confirmed': False
        }
        
        # Need a minimum of data
        if len(df) < 30:
            return None
        
        # Create a copy to avoid SettingWithCopyWarning
        df_copy = df.copy()
        
        # Calculate RSI
        df_copy['rsi'] = self.calculate_rsi(df_copy)
        
        # Run analysis pipeline
        # 1. Identify bull trend
        bull_trend, df_copy = self.identify_bull_trend(df_copy)
        if not bull_trend:
            return None
        
        # 2. Identify pullbacks
        df_copy = self.identify_pullback(df_copy)
        
        # 3. Identify reversal bars
        df_copy = self.identify_reversal_bar(df_copy)
        
        # 4. Calculate profit targets
        df_copy = self.calculate_targets(df_copy)
        
        # Check for entry signal in the last bar
        last_bar = df_copy.iloc[-1]
        
        if last_bar.get('reversal_bar', False):
            # Determine signal strength
            strength = 1
            if last_bar.get('volume_confirmed', False):
                strength += 1
            if last_bar.get('rsi_confirmed', False):
                strength += 1
            if last_bar.get('reversal_type') == 'engulfing':
                strength += 1
            
            # Update signal data
            signal_data['Date'] = last_bar.name if isinstance(last_bar.name, pd.Timestamp) else pd.Timestamp.now()
            signal_data['Close'] = last_bar['Close']
            signal_data['Signal_Strength'] = strength
            signal_data['Reversal_Type'] = last_bar.get('reversal_type', 'Unknown')
            signal_data['ATR'] = self.calculate_atr(df_copy).iloc[-1]
            signal_data['PosSize'] = int(self.account_value * 0.01 / (last_bar['entry_price'] - last_bar['stop_loss']))
            signal_data['Entry_Price'] = last_bar['entry_price']
            signal_data['Stop_Loss'] = last_bar['stop_loss']
            signal_data['Target1'] = last_bar.get('target1', last_bar['entry_price'] + (last_bar['entry_price'] - last_bar['stop_loss']))
            signal_data['Target2'] = last_bar.get('target2', last_bar['entry_price'] + 2 * (last_bar['entry_price'] - last_bar['stop_loss']))
            signal_data['Target3'] = last_bar.get('target3', last_bar['entry_price'] + 3 * (last_bar['entry_price'] - last_bar['stop_loss']))
            signal_data['Current_Close'] = last_bar['Close']
            signal_data['Volume_Confirmed'] = last_bar.get('volume_confirmed', False)
            signal_data['RSI_Confirmed'] = last_bar.get('rsi_confirmed', False)
            
            return signal_data
        
        return None
    
    def process_ticker(self, ticker):
        """Process a single ticker for signal generation"""
        if not isinstance(ticker, str) or ticker.strip() == "":
            logging.warning(f"Skipping invalid ticker: {ticker}")
            return ticker, None
        
        logging.info(f"Processing {ticker} for Bull Trend Pullback strategy using {self.interval} timeframe.")
        now = datetime.now()
        
        # Set lookback period based on timeframe
        if self.interval == '1h':
            # For hourly timeframe, get 30 days of data
            from_date_obj = now - pd.DateOffset(days=30)
            lookback_desc = "30 days"
        else:
            # For daily timeframe, get 12 weeks of data for accurate swing point identification
            from_date_obj = now - pd.DateOffset(weeks=12)
            lookback_desc = "12 weeks"
            
        from_date = from_date_obj.strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        logging.info(f"Fetching {lookback_desc} of {self.interval} data for {ticker}")
        
        # Fetch historical data based on configured timeframe
        data = self.data_handler.fetch_historical_data(ticker, self.interval, from_date, to_date)
        if data.empty:
            logging.warning(f"No data found for {ticker}, skipping.")
            return ticker, None
        
        # Make dates tz-naive and sort
        data['Date'] = data['Date'].apply(lambda d: d.tz_localize(None) if hasattr(d, 'tzinfo') and d.tzinfo is not None else d)
        data = data.sort_values(by='Date')
        
        # Check for entry signals based on the Bull Trend Pullback strategy
        signal = self.check_for_entry_signals(data, ticker)
        
        if signal:
            logging.info(f"{ticker} qualifies as Bull Trend Pullback candidate with {signal['Reversal_Type']} pattern")
            return ticker, signal
        else:
            logging.info(f"{ticker}: Conditions not met for Bull Trend Pullback strategy.")
            return ticker, None
    
    def generate_trading_signals(self, input_file_path=None):
        """Generate trading signals from ticker list"""
        data_dir = self.config.get('System', 'data_dir')
        
        # Default output file paths with formatted date and time
        today = datetime.now()
        formatted_date = today.strftime("%d_%m_%Y")
        formatted_time = today.strftime("%H_%M")
        
        # If input file not specified, use the default one
        if input_file_path is None:
            input_file_path = os.path.join(data_dir, "Ticker.xlsx")
        
        # Construct output file path for BTPB signals with timeframe
        timeframe_label = "hourly" if self.interval == "60minute" else "daily"
        output_file_path = os.path.join(data_dir, f'BTPB_Signals_{timeframe_label}_{formatted_date}_{formatted_time}.xlsx')
        
        # Load tickers
        try:
            tickers = self.data_handler.get_tickers_from_file(input_file_path)
            if not tickers:
                logging.error(f"No tickers found in {input_file_path}")
                return None
        except Exception as e:
            logging.error(f"Error loading tickers from {input_file_path}: {e}")
            return None
        
        logging.info(f"Starting processing of {len(tickers)} tickers for Bull Trend Pullback strategy...")
        
        # Process each ticker with rate limiting
        all_signals = []
        missing_tickers = []
        
        # Process tickers in smaller batches to avoid rate limits
        batch_size = 20  # Process 20 tickers at a time
        total_batches = (len(tickers) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min((batch_num + 1) * batch_size, len(tickers))
            batch_tickers = tickers[start_idx:end_idx]
            
            logging.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_tickers)} tickers)")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.process_ticker, ticker): ticker for ticker in batch_tickers}
                
                for future in concurrent.futures.as_completed(futures):
                    ticker = futures[future]
                    try:
                        _, signal = future.result()
                        if signal:
                            all_signals.append(signal)
                        else:
                            missing_tickers.append(ticker)
                    except Exception as e:
                        logging.error(f"Error processing {ticker}: {e}")
                        missing_tickers.append(ticker)
            
            # Add a delay between batches to avoid rate limiting
            if batch_num < total_batches - 1:
                wait_time = 5  # seconds
                logging.info(f"Pausing for {wait_time} seconds before next batch to avoid rate limiting...")
                time.sleep(wait_time)
        
        # If no signals were found
        if not all_signals:
            logging.info("No Bull Trend Pullback signals found.")
            # Create empty dataframe with required columns
            empty_df = pd.DataFrame(columns=self.required_columns)
            empty_df.to_excel(output_file_path, index=False)
            return output_file_path
        
        # Convert signals to DataFrame and sort by signal strength
        signals_df = pd.DataFrame(all_signals)
        signals_df = signals_df.sort_values(by=['Signal_Strength', 'Target1'], ascending=[False, False])
        
        # Write to Excel
        try:
            signals_df.to_excel(output_file_path, index=False)
            logging.info(f"Successfully wrote output to {output_file_path}")
            
            # Also create a text file with tickers and entry prices
            txt_file_path = output_file_path.replace('.xlsx', '.txt')
            with open(txt_file_path, 'w') as f:
                for _, row in signals_df.iterrows():
                    f.write(f"{row['Ticker']}, Entry: {row['Entry_Price']:.2f}, "
                            f"SL: {row['Stop_Loss']:.2f}, T1: {row['Target1']:.2f}, "
                            f"T2: {row['Target2']:.2f}, T3: {row['Target3']:.2f}\n")
            
            logging.info(f"Also wrote signals to text file: {txt_file_path}")
            
        except Exception as e:
            logging.error(f"Error writing output to Excel file: {e}")
            return None
        
        return output_file_path

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Bull Trend Pullback Market Scan Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Get scanner timeframe from config
    timeframe = config.get('Scanner', 'timeframe', fallback='day')
    scanner_type = config.get('Scanner', 'scanner_type', fallback='default')
    
    logger.info(f"Using scanner type: bull_trend_pullback, timeframe: {timeframe}")
    
    # Create scanner
    scanner = BullTrendPullbackScanner()
    
    # Set the timeframe
    if timeframe.lower() == 'hour':
        scanner.interval = '60minute'  # Zerodha uses 60minute format instead of 1h
        logger.info("Using hourly timeframe for scanning")
    else:
        scanner.interval = 'day'  # Zerodha uses 'day' format
        logger.info("Using daily timeframe for scanning")
    
    # Generate trading signals
    input_file = args.input
    logger.info(f"Generating Bull Trend Pullback signals from {input_file if input_file else 'default ticker list'}")
    
    try:
        signal_file = scanner.generate_trading_signals(input_file)
        
        if signal_file:
            logger.info(f"Successfully generated Bull Trend Pullback signal file: {os.path.basename(signal_file)}")
        else:
            logger.error("Failed to generate signal file")
        
    except Exception as e:
        logger.exception(f"Error during Bull Trend Pullback market scan: {e}")
    
    # Log end of execution
    logger.info(f"===== Bull Trend Pullback Market Scan Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()