import os
import logging
import pandas as pd
import datetime
import glob
import concurrent.futures
import functools
import time

from config import get_config
from data_handler import get_data_handler
from indicators import calculate_indicators, get_trade_signals

logger = logging.getLogger(__name__)

class TradingLogic:
    """Core trading logic and signal generation"""
    
    def __init__(self):
        self.config = get_config()
        self.data_handler = get_data_handler()
        
        # Trading parameters
        self.exchange = self.config.get('Trading', 'exchange')
        self.max_workers = self.config.get_int('Scanner', 'max_workers', fallback=4)  # Reduced from 8 to avoid rate limiting
        self.account_value = self.config.get_float('Trading', 'account_value', fallback=100000.0)
        self.volume_spike_threshold = self.config.get_float('Trading', 'volume_spike_threshold', fallback=4.0)
        self.gap_down_threshold = self.config.get_float('Trading', 'gap_down_threshold', fallback=-1.0)
        self.gap_up_threshold = self.config.get_float('Trading', 'gap_up_threshold', fallback=1.0)
        
        # Get timeframe from config
        self.timeframe = self.config.get('Scanner', 'timeframe', fallback='day')
        self.interval = '1d' if self.timeframe == 'day' else '1h'
        
        # API rate limiting
        self.api_request_delay = 0.5  # Half-second delay between API calls
        
        # Interval mapping for API calls
        self.interval_mapping = {
            '1h': '60minute',
            '1d': 'day'
        }
        
        # Required columns for the summary output
        self.required_columns = [
            'Ticker', 'Date', 'Close', 'Slope', 'Alpha',
            'MaxGap', 'ATR', 'PosSize', 'SL1', 'SL2', 'TP1', 'Current_Close', 'C', 'Volume', 'GapPercent'
        ]
    
    def process_ticker(self, ticker, interval, period, key):
        """Process a single ticker for signal generation"""
        if not isinstance(ticker, str) or ticker.strip() == "":
            logger.warning(f"Skipping invalid ticker: {ticker}")
            return None, None

        # Add a small delay to avoid rate limiting
        time.sleep(self.api_request_delay)
        
        logger.info(f"Processing {ticker} for {key} data.")
        now = datetime.datetime.now()

        # Set lookback period based on timeframe
        if interval == '1d':
            # For daily timeframe, use ~3 months of data to get at least 60 bars
            from_date_obj = now - datetime.timedelta(days=90)
        else:
            # For hourly timeframe, use ~6 weeks of data
            from_date_obj = now - datetime.timedelta(weeks=6)
            
        from_date = from_date_obj.strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        interval_str = self.interval_mapping.get(interval, None)
        if not interval_str:
            logger.warning(f"No mapping found for interval {interval}. Skipping.")
            return ticker, None

        # Fetch historical data
        data = self.data_handler.fetch_historical_data(ticker, interval_str, from_date, to_date)
        if data.empty:
            logger.warning(f"No data found for {ticker}, skipping.")
            return ticker, None

        # Append a new bar for current time if needed
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        most_recent_data_date = data['Date'].iloc[-1]
        if most_recent_data_date.tzinfo is not None:
            most_recent_data_date = most_recent_data_date.tz_localize(None)
        
        if most_recent_data_date < current_hour:
            current_close = self.data_handler.fetch_current_price(ticker)
            if current_close is not None:
                # Create new data with non-NA values to avoid FutureWarning
                new_data = pd.DataFrame({
                    'Date': [current_hour],
                    'Open': [current_close],  # Use current_close as a placeholder
                    'High': [current_close],  # Use current_close as a placeholder
                    'Low': [current_close],   # Use current_close as a placeholder
                    'Close': [current_close],
                    'Volume': [0],            # Use 0 instead of None
                    'Ticker': [ticker]
                })
                data = pd.concat([data, new_data], ignore_index=True)

        # Make dates tz-naive and sort
        data['Date'] = data['Date'].apply(lambda d: d.tz_localize(None) if d.tzinfo is not None else d)
        data = data.sort_values(by='Date')

        # Calculate indicators
        data = calculate_indicators(data)
        if data.empty:
            logger.warning(f"Failed to calculate indicators for {ticker}")
            return ticker, None

        # Get trading signals
        long_signal, short_signal, advances, declines = get_trade_signals(data, ticker)

        results = []
        
        # Process long signal if available
        if long_signal is not None:
            df_summary = pd.DataFrame([long_signal])
            summary_key = "Hourly"
            
            try:
                current_close = self.data_handler.fetch_current_price(ticker)
                logger.debug(f"{ticker}: Fetched current price {current_close}")
                current_dt = datetime.datetime.now()
                
                df_summary['Date'] = current_dt
                df_summary['Close'] = current_close
                df_summary['Current_Close'] = current_close
            except Exception as e:
                logger.error(f"{ticker}: Error fetching or setting current price: {e}")
                # Use some fallback values
                df_summary['Date'] = datetime.datetime.now()
                df_summary['Close'] = df_summary.get('Close', 0) 
                df_summary['Current_Close'] = df_summary.get('Close', 0)

            # Ensure all required columns exist
            for col in self.required_columns:
                if col not in df_summary.columns:
                    df_summary[col] = None
            
            # Skip long signals for tickers with gap up above threshold
            try:
                if 'GapPercent' in df_summary.columns:
                    gap_percent = df_summary['GapPercent'].iloc[0] if len(df_summary) > 0 else 0
                else:
                    gap_percent = 0
                    logger.warning(f"{ticker}: No GapPercent column found in summary data")
            except Exception as e:
                logger.warning(f"{ticker}: Error extracting GapPercent: {e}, using 0 as default")
                gap_percent = 0
            if gap_percent is not None and gap_percent > self.gap_up_threshold:
                logger.info(f"{ticker}: Skipping LONG signal due to gap up of {gap_percent:.2f}% (> {self.gap_up_threshold:.2f}%)")
                # Return gap_up_skipped flag
                return ticker, (results, advances, declines, True, False)
            else:
                results.append((summary_key, df_summary[self.required_columns]))

        # Process short signal if available
        if short_signal is not None:
            df_summary = pd.DataFrame([short_signal])
            summary_key = "Hourly_Short"
            
            try:
                current_close = self.data_handler.fetch_current_price(ticker)
                logger.debug(f"{ticker}: Fetched current price {current_close}")
                current_dt = datetime.datetime.now()
                
                df_summary['Date'] = current_dt
                df_summary['Close'] = current_close
                df_summary['Current_Close'] = current_close
            except Exception as e:
                logger.error(f"{ticker}: Error fetching or setting current price: {e}")
                # Use some fallback values
                df_summary['Date'] = datetime.datetime.now()
                df_summary['Close'] = df_summary.get('Close', 0) 
                df_summary['Current_Close'] = df_summary.get('Close', 0)

            # Ensure all required columns exist
            for col in self.required_columns:
                if col not in df_summary.columns:
                    df_summary[col] = None
            
            # Skip short signals for tickers with gap down below threshold
            try:
                if 'GapPercent' in df_summary.columns:
                    gap_percent = df_summary['GapPercent'].iloc[0] if len(df_summary) > 0 else 0
                else:
                    gap_percent = 0
                    logger.warning(f"{ticker}: No GapPercent column found in summary data")
            except Exception as e:
                logger.warning(f"{ticker}: Error extracting GapPercent: {e}, using 0 as default")
                gap_percent = 0
            if gap_percent is not None and gap_percent < self.gap_down_threshold:
                logger.info(f"{ticker}: Skipping SHORT signal due to gap down of {gap_percent:.2f}% (< {self.gap_down_threshold:.2f}%)")
                # If already skipped a long signal, this will override, that's fine
                return ticker, (results, advances, declines, False, True)
            else:
                results.append((summary_key, df_summary[self.required_columns]))

        if not results:
            logger.info(f"{ticker}: Conditions not met for either side.")

        # Log what we're about to return
        logger.debug(f"{ticker}: Returning {len(results)} results, advances: {advances}, declines: {declines}")
        
        # Return the trading signals and the advances/declines counts along with gap flags
        # Format: ticker, (results, advances, declines, gap_up_skipped, gap_down_skipped)
        return ticker, (results, advances, declines, False, False)
    
    def process_tickers_parallel(self, tickers, interval, period, key):
        """Process multiple tickers in parallel for efficiency"""
        logger.info(f"\nProcessing {len(tickers)} tickers for {key} timeframe")

        results = []
        missing_tickers = []
        total_advances = 0
        total_declines = 0
        skipped_gap_up = 0
        skipped_gap_down = 0

        process_func = functools.partial(
            self.process_ticker,
            interval=interval,
            period=period,
            key=key
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(process_func, ticker): ticker for ticker in tickers}

            for future in concurrent.futures.as_completed(futures):
                ticker = futures[future]
                try:
                    ticker, result_data = future.result()
                    if result_data is None:
                        logger.debug(f"No result data for {ticker}, adding to missing tickers")
                        missing_tickers.append(ticker)
                    else:
                        try:
                            # Unpack the result data with gap flags
                            ticker_results, advances, declines, gap_up, gap_down = result_data
                            logger.debug(f"Processing result for {ticker}: {len(ticker_results)} results, advances: {advances}, declines: {declines}")
                            results.extend(ticker_results)
                            total_advances += advances
                            total_declines += declines
                            if gap_up:
                                skipped_gap_up += 1
                            if gap_down:
                                skipped_gap_down += 1
                        except Exception as e:
                            logger.error(f"Error unpacking result data for {ticker}: {e}")
                            logger.error(f"Result data: {result_data}")
                            missing_tickers.append(ticker)
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    logger.error(f"Exception details for {ticker}: {repr(e)}")
                    missing_tickers.append(ticker)

        # Log the number of tickers skipped due to gap conditions
        if skipped_gap_up > 0:
            logger.info(f"Skipped {skipped_gap_up} long signals due to gap up exceeding threshold of {self.gap_up_threshold}%")
        if skipped_gap_down > 0:
            logger.info(f"Skipped {skipped_gap_down} short signals due to gap down exceeding threshold of {self.gap_down_threshold}%")

        return results, missing_tickers, total_advances, total_declines
    
    def write_summary_to_excel(self, summaries, output_file_path, advances, declines):
        """Write summary data to Excel with market breadth information"""
        try:
            with pd.ExcelWriter(output_file_path, engine='openpyxl', mode='w') as writer:
                sheets_written = 0

                # Write Hourly Long Summary
                if 'Hourly' in summaries and summaries['Hourly']:
                    summary_df = pd.concat(summaries['Hourly'])
                    summary_df = summary_df.sort_values(by='Volume',
                                                        ascending=False) if 'Volume' in summary_df.columns else summary_df.sort_index()
                    summary_df.to_excel(writer, sheet_name="Hourly_Summary", index=False)
                    sheets_written += 1
                else:
                    pd.DataFrame(columns=self.required_columns).to_excel(writer, sheet_name="Hourly_Summary", index=False)
                    sheets_written += 1
                    logger.info("No long tickers found, creating empty Hourly_Summary sheet.")

                # Create a market summary sheet with Advances/Declines
                market_summary_df = pd.DataFrame({
                    'Metric': ['Advances', 'Declines', 'Advances/Declines Ratio'],
                    'Value': [
                        advances,
                        declines,
                        round(advances / declines, 2) if declines > 0 else "∞"
                    ]
                })
                market_summary_df.to_excel(writer, sheet_name="Summary", index=False)
                sheets_written += 1
                logger.info(f"Created market Summary sheet with Advances: {advances}, Declines: {declines}")

                if sheets_written == 0:
                    pd.DataFrame({"Message": ["No valid data available"]}).to_excel(writer, sheet_name="Summary",
                                                                                    index=False)

            logger.info(f"Successfully wrote output to {output_file_path}")
        except Exception as e:
            logger.error(f"Error writing output to Excel file: {e}")
    
    def analyze_market_breadth(self, advances, declines, trend_ratio_threshold=None):
        """Analyze market breadth using advances/declines ratio"""
        # Get trend ratio threshold from config or use default
        if trend_ratio_threshold is None:
            trend_ratio_threshold = self.config.get_float('Trading', 'trend_ratio_threshold', fallback=4.0)
            
        disable_long_trades = False
        disable_short_trades = False
        
        ad_ratio = 0.0
        if advances > 0 and declines > 0:
            ad_ratio = advances / declines
            logger.info(f"Advances/Declines Ratio: {ad_ratio:.2f}")

            if ad_ratio >= trend_ratio_threshold:
                # Strongly bullish - disable shorts
                disable_short_trades = True
                logger.info(f"STRONGLY BULLISH MARKET DETECTED: A/D Ratio = {ad_ratio:.2f} (>= {trend_ratio_threshold})")
                logger.info("DISABLING ALL SHORT TRADES due to strongly bullish market")
            elif ad_ratio <= (1.0 / trend_ratio_threshold):
                # Strongly bearish - disable longs
                disable_long_trades = True
                logger.info(
                    f"STRONGLY BEARISH MARKET DETECTED: A/D Ratio = {ad_ratio:.2f} (<= {1.0 / trend_ratio_threshold:.2f})")
                logger.info("DISABLING ALL LONG TRADES due to strongly bearish market")
            else:
                logger.info(
                    f"NEUTRAL MARKET DETECTED: A/D Ratio = {ad_ratio:.2f} (between {1.0 / trend_ratio_threshold:.2f} and {trend_ratio_threshold})")
                logger.info("Trading both long and short sides with top tickers")
        elif advances > 0:
            # All advances, no declines
            disable_short_trades = True
            logger.info("EXTREMELY BULLISH MARKET DETECTED: All advances, no declines")
            logger.info("DISABLING ALL SHORT TRADES due to extremely bullish market")
        elif declines > 0:
            # All declines, no advances
            disable_long_trades = True
            logger.info("EXTREMELY BEARISH MARKET DETECTED: All declines, no advances")
            logger.info("DISABLING ALL LONG TRADES due to extremely bearish market")
        else:
            # No advances, no declines - something might be wrong
            logger.warning("No advances or declines found. Using neutral market setting.")
            
        # Return the ratio and both flags (long and short disabling status)
        return ad_ratio, disable_long_trades, disable_short_trades
    
    def generate_trading_signals(self, input_file_path=None):
        """Generate trading signals from ticker list
        
        This method performs the following optimizations:
        1. Analyzes market breadth using advances/declines ratio to potentially disable
           long or short trades based on overall market direction
        2. Filters out tickers with gap up movements from long positions
           (gaps exceeding gap_up_threshold in config)
        3. Filters out tickers with gap down movements from short positions
           (gaps below gap_down_threshold in config)
        """
        start_time = time.time()
        data_dir = self.config.get('System', 'data_dir')
        
        # Default output file paths with formatted date and time
        today = datetime.datetime.now()
        formatted_date = today.strftime("%d_%m_%Y")
        formatted_time = today.strftime("%H_%M")
        
        # If input file not specified, use the default one
        if input_file_path is None:
            input_file_path = os.path.join(data_dir, "Ticker.xlsx")
        
        # Construct output file paths with timeframe indicator
        timeframe_str = "day" if self.timeframe == 'day' else "hour"
        output_file_path = os.path.join(data_dir, f'EMA_KV_F_Zerodha_{timeframe_str}_{formatted_date}_{formatted_time}.xlsx')
        output_file_path_short = os.path.join(data_dir, f'EMA_KV_F_Short_Zerodha_{timeframe_str}_{formatted_date}_{formatted_time}.xlsx')
        
        # Load tickers
        try:
            tickers = self.data_handler.get_tickers_from_file(input_file_path)
            if not tickers:
                logger.error(f"No tickers found in {input_file_path}")
                return None, None
        except Exception as e:
            logger.error(f"Error loading tickers from {input_file_path}: {e}")
            return None, None
        
        # Process data based on configured timeframe
        all_results = []
        missing_tickers = []
        total_advances = 0
        total_declines = 0
        
        timeframe_label = "Daily" if self.timeframe == 'day' else "Hourly"
        logger.info(f"Starting processing of ticker data using {timeframe_label} timeframe...")
        results, missing, advances, declines = self.process_tickers_parallel(tickers, self.interval, '1mo', timeframe_label)
        all_results.extend(results)
        missing_tickers.extend(missing)
        total_advances += advances
        total_declines += declines
        
        # Log the advances and declines
        logger.info(f"Total Advances: {total_advances}, Total Declines: {total_declines}")
        if total_declines > 0:
            ad_ratio = total_advances / total_declines
            logger.info(f"Advances/Declines Ratio: {ad_ratio:.2f}")
        else:
            logger.info("Advances/Declines Ratio: ∞ (no declines)")
        
        # Organize results
        timeframe_label = "Daily" if self.timeframe == 'day' else "Hourly"
        summaries = {
            f'{timeframe_label}': [],
            f'{timeframe_label}_Short': []
        }
        
        for key, df in all_results:
            if key in summaries:
                summaries[key].append(df)
        
        # Write results to Excel files
        timeframe_label = "Daily" if self.timeframe == 'day' else "Hourly"
        self.write_summary_to_excel({
            'Hourly': summaries.get(f'{timeframe_label}', [])
        }, output_file_path, total_advances, total_declines)
        
        self.write_summary_to_excel({
            'Hourly': summaries.get(f'{timeframe_label}_Short', [])
        }, output_file_path_short, total_advances, total_declines)
        
        # Report missing tickers
        if missing_tickers:
            logger.warning(f"Unable to process these tickers: {list(set(missing_tickers))}")
        
        end_time = time.time()
        logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")
        
        return output_file_path, output_file_path_short

# Create singleton instance
_trading_logic = None

def get_trading_logic():
    """Get or create the singleton trading logic instance"""
    global _trading_logic
    if _trading_logic is None:
        _trading_logic = TradingLogic()
    return _trading_logic
