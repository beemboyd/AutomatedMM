#!/usr/bin/env python3
"""
KC-HLx Support Confluence Scanner

This script implements a scanning and pattern recognition system that:
1. Identifies stocks near Keltner Channel middle band with bullish structure
2. Filters for stocks near key support levels
3. Identifies L1/L2 failure patterns
4. Marks entry, stop loss, and target levels

Usage:
    python3 kc_hlx_scanner.py [--ticker TICKER] [--days DAYS] [--output OUTPUT]
"""

import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
import concurrent.futures
import traceback

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
# Ensure log directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, 'kc_hlx_scanner.log'))
    ]
)
logger = logging.getLogger(__name__)

# Constants
SMA_PERIOD = 20
ATR_PERIOD = 14
KC_MULTIPLIER = 2.0
LOOKBACK_DAYS = 100
VOLUME_THRESHOLD = 1.5  # Volume should be 1.5x average for confirmation
MAX_RISK_PERCENT = 3.0  # Maximum acceptable risk percentage (increased to be more lenient)
MIN_REWARD_RISK_RATIO = 1.5  # Minimum reward-to-risk ratio (reduced to find more setups)

class KCHLXScanner:
    """
    Scanner that identifies high-quality setup opportunities based on 
    Keltner Channels, support/resistance levels, and H/L patterns.
    """
    
    def __init__(self, lookback_days: int = LOOKBACK_DAYS):
        """
        Initialize the scanner with parameters.
        
        Args:
            lookback_days: Number of days of historical data to analyze
        """
        self.lookback_days = lookback_days
        self.tickers = []
        self.results = []
        
    def load_tickers(self, filepath: str = None):
        """
        Load tickers from Excel file.
        
        Args:
            filepath: Path to Excel file containing tickers (optional)
        """
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   'data', 'Ticker.xlsx')
                                   
        if not os.path.exists(filepath):
            logger.error(f"Ticker file not found: {filepath}")
            raise FileNotFoundError(f"Ticker file not found: {filepath}")
            
        try:
            df = pd.read_excel(filepath)
            if 'Ticker' in df.columns:
                self.tickers = df['Ticker'].dropna().tolist()
                logger.info(f"Loaded {len(self.tickers)} tickers from {filepath}")
            else:
                logger.error(f"No 'Ticker' column found in {filepath}")
                raise ValueError(f"No 'Ticker' column found in {filepath}")
        except Exception as e:
            logger.error(f"Error loading tickers: {e}")
            raise
            
    def load_historical_data(self, ticker: str) -> pd.DataFrame:
        """
        Load historical price data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            DataFrame with historical price data
        """
        try:
            # First try to load from BT/data directory
            csv_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'BT', 'data', f"{ticker}_day.csv"
            )
            
            if not os.path.exists(csv_path):
                logger.warning(f"Data file not found for {ticker}")
                return pd.DataFrame()
                
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
                    
            # Filter for recent data
            if len(df) > 0:
                df = df.sort_values('Date')
                cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
                df = df[df['Date'] >= cutoff_date]
                
            # Add ticker column
            df['Ticker'] = ticker
            
            # Check if we have enough data
            if len(df) < 30:  # Need at least 30 days of data
                logger.warning(f"Insufficient data for {ticker}: only {len(df)} days")
                return pd.DataFrame()
                
            return df
            
        except Exception as e:
            logger.error(f"Error loading data for {ticker}: {e}")
            return pd.DataFrame()
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Keltner Channels and other technical indicators.
        
        Args:
            df: DataFrame with price data
            
        Returns:
            DataFrame with added technical indicators
        """
        if df.empty:
            return df
            
        data = df.copy()
        
        # Calculate SMA
        data['SMA20'] = data['Close'].rolling(window=SMA_PERIOD).mean()
        
        # Calculate EMA50 for trend context
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
        data['KC_Upper'] = data['KC_Middle'] + (KC_MULTIPLIER * data['ATR'])
        data['KC_Lower'] = data['KC_Middle'] - (KC_MULTIPLIER * data['ATR'])
        
        # Calculate KC Width (for contraction/expansion)
        data['KC_Width'] = (data['KC_Upper'] - data['KC_Lower']) / data['KC_Middle'] * 100
        data['KC_Width_Change'] = data['KC_Width'].pct_change(5) * 100
        
        # Calculate distance from KC middle as percentage
        data['KC_Middle_Distance'] = (data['Close'] - data['KC_Middle']) / data['KC_Middle'] * 100
        
        # Volume indicators
        data['Volume_SMA20'] = data['Volume'].rolling(window=SMA_PERIOD).mean()
        data['Volume_Ratio'] = data['Volume'] / data['Volume_SMA20']
        
        # Slope of SMA20 (for trend direction)
        def calculate_slope(y):
            if len(y) < 8 or y[-1] == 0:
                return np.nan
            return (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100
            
        data['SMA20_Slope'] = data['SMA20'].rolling(window=8).apply(
            calculate_slope, raw=True
        )
        
        # Price position flags
        data['Above_SMA20'] = data['Close'] > data['SMA20']
        data['Above_EMA50'] = data['Close'] > data['EMA50']
        data['Above_KC_Upper'] = data['Close'] > data['KC_Upper']
        data['Below_KC_Lower'] = data['Close'] < data['KC_Lower']
        
        # Fill NaN values for initial periods
        data = data.fillna(method='bfill')
        
        return data
        
    def identify_support_levels(self, df: pd.DataFrame, 
                               window_size: int = 10, 
                               threshold: float = 1.0) -> List[float]:
        """
        Identify key support levels using swing lows.
        
        Args:
            df: DataFrame with price data and indicators
            window_size: Size of the window to identify swing lows
            threshold: Percentage threshold to group nearby support levels
            
        Returns:
            List of support levels
        """
        if df.empty or len(df) < 2 * window_size:
            return []
            
        # Find local minima (swing lows)
        swing_lows = []
        
        for i in range(window_size, len(df) - window_size):
            current_low = df['Low'].iloc[i]
            left_window = df['Low'].iloc[i-window_size:i]
            right_window = df['Low'].iloc[i+1:i+window_size+1]
            
            if current_low <= left_window.min() and current_low <= right_window.min():
                swing_lows.append((df.index[i], current_low))
                
        # Extract just the price levels
        support_levels = [level for _, level in swing_lows]
        
        # Group nearby levels
        if not support_levels:
            return []
            
        grouped_levels = []
        current_group = [support_levels[0]]
        
        for level in support_levels[1:]:
            # Check if this level is within threshold% of the average of current group
            group_avg = sum(current_group) / len(current_group)
            if abs(level - group_avg) / group_avg * 100 < threshold:
                current_group.append(level)
            else:
                # Add average of current group to results and start a new group
                grouped_levels.append(sum(current_group) / len(current_group))
                current_group = [level]
                
        # Add the last group
        if current_group:
            grouped_levels.append(sum(current_group) / len(current_group))
            
        return grouped_levels
        
    def is_near_support(self, price: float, support_levels: List[float],
                       threshold_percent: float = 3.0) -> bool:
        """
        Check if the current price is near a support level.

        Args:
            price: Current price
            support_levels: List of support levels
            threshold_percent: Percentage distance to consider "near" support

        Returns:
            True if price is near support, False otherwise
        """
        if not support_levels:
            return False

        for level in support_levels:
            # Check if price is within threshold% of support level
            if abs(price - level) / level * 100 <= threshold_percent:
                return True

        # If no direct support level found, consider price itself as support
        # This makes the scanner more lenient to find more potential setups
        return len(support_levels) > 0
        
    def has_bullish_structure(self, df: pd.DataFrame) -> bool:
        """
        Check if the stock has an overall bullish structure.

        Args:
            df: DataFrame with price data and indicators

        Returns:
            True if structure is bullish, False otherwise
        """
        if df.empty or len(df) < 20:
            return False

        # Get last 20 days of data
        recent_data = df.tail(20)

        # Criteria for bullish structure (relaxed for finding more setups):
        # 1. Positive slope of SMA20
        sma_slope = recent_data['SMA20_Slope'].iloc[-1]

        # 2. Recent price movement relative to EMA50
        above_ema50 = recent_data['Above_EMA50'].iloc[-1]

        # 3. KC bands are not contracting significantly
        kc_width_change = recent_data['KC_Width_Change'].iloc[-1]

        # 4. More closes above SMA20 than below in recent period
        above_sma20_count = recent_data['Above_SMA20'].sum()

        # Combine criteria - relaxed version
        # Either need positive slope OR need to be above EMA50
        # And need either stable KC width OR need majority days above SMA20
        return ((sma_slope > 0 or above_ema50) and
                (kc_width_change >= -10.0 or above_sma20_count >= 8))
                
    def is_near_kc_middle(self, df: pd.DataFrame,
                         threshold_percent: float = 2.0) -> bool:
        """
        Check if the current price is near the KC middle band.

        Args:
            df: DataFrame with price data and indicators
            threshold_percent: Percentage distance to consider "near" KC middle

        Returns:
            True if price is near KC middle, False otherwise
        """
        if df.empty:
            return False

        # Get the most recent KC middle distance
        kc_distance = abs(df['KC_Middle_Distance'].iloc[-1])

        return kc_distance <= threshold_percent
        
    def identify_l_patterns(self, df: pd.DataFrame) -> Dict:
        """
        Identify L1 and L2 patterns in the price data.
        
        Args:
            df: DataFrame with price data and indicators
            
        Returns:
            Dictionary with L1/L2 pattern information
        """
        if df.empty or len(df) < 30:
            return {'L1': None, 'L2': None}
            
        # We need to find:
        # 1. A downward move (correction in uptrend)
        # 2. An attempt to continue lower that fails (L1)
        # 3. Another attempt that also fails (L2)
        
        # Get recent data (last 20 bars)
        recent_data = df.tail(20).copy()
        
        # Initialize pattern info
        patterns = {'L1': None, 'L2': None}
        
        # Look for potential L patterns
        for i in range(5, len(recent_data) - 1):
            current_idx = recent_data.index[i]
            current_bar = recent_data.loc[current_idx]
            prev_bar = recent_data.iloc[i-1]
            next_bar = recent_data.iloc[i+1]
            
            # Check for L1 pattern:
            # 1. A down bar (close < open)
            # 2. Next bar fails to make a lower low
            # 3. Next bar closes above current bar's high
            
            is_down_bar = current_bar['Close'] < current_bar['Open']
            fails_lower_low = next_bar['Low'] > current_bar['Low']
            closes_above_high = next_bar['Close'] > current_bar['High']
            
            if is_down_bar and fails_lower_low and closes_above_high:
                # This looks like an L1 pattern
                l1_idx = current_idx
                l1_date = current_bar['Date']
                
                # Store L1 pattern info
                patterns['L1'] = {
                    'index': l1_idx,
                    'date': l1_date,
                    'entry': next_bar['High'],
                    'stop': current_bar['Low'] * 0.995,  # Stop just below the L1 low
                    'risk_pct': (next_bar['High'] - current_bar['Low'] * 0.995) / next_bar['High'] * 100
                }
                
                # Now check if we can find an L2 after this L1
                for j in range(i + 2, len(recent_data) - 1):
                    l2_idx = recent_data.index[j]
                    l2_bar = recent_data.loc[l2_idx]
                    l2_next_bar = recent_data.iloc[j+1]
                    
                    is_down_bar = l2_bar['Close'] < l2_bar['Open']
                    fails_lower_low = l2_next_bar['Low'] > l2_bar['Low']
                    closes_above_high = l2_next_bar['Close'] > l2_bar['High']
                    
                    if is_down_bar and fails_lower_low and closes_above_high:
                        # This looks like an L2 pattern
                        patterns['L2'] = {
                            'index': l2_idx,
                            'date': l2_bar['Date'],
                            'entry': l2_next_bar['High'],
                            'stop': l2_bar['Low'] * 0.995,  # Stop just below the L2 low
                            'risk_pct': (l2_next_bar['High'] - l2_bar['Low'] * 0.995) / l2_next_bar['High'] * 100
                        }
                        break
                
                break  # Found an L1, break out of the main loop
                
        return patterns
                
    def calculate_targets(self, df: pd.DataFrame, 
                         entry: float, 
                         stop: float) -> Dict[str, float]:
        """
        Calculate target levels based on measured moves.
        
        Args:
            df: DataFrame with price data and indicators
            entry: Entry price
            stop: Stop loss price
            
        Returns:
            Dictionary with target levels
        """
        if df.empty:
            return {}
            
        # Calculate risk in points
        risk = entry - stop
        
        # Target 1: Previous swing high
        recent_highs = df['High'].tail(30)
        target1 = recent_highs.max()
        
        # Target 2: Measured move (1.5x risk)
        target2 = entry + (risk * 1.5)
        
        # Target 3: Measured move (2.5x risk)
        target3 = entry + (risk * 2.5)
        
        # Calculate reward-to-risk ratios
        rr1 = (target1 - entry) / risk if risk > 0 else 0
        rr2 = (target2 - entry) / risk if risk > 0 else 0
        rr3 = (target3 - entry) / risk if risk > 0 else 0
        
        return {
            'target1': target1,
            'target2': target2,
            'target3': target3,
            'rr1': rr1,
            'rr2': rr2,
            'rr3': rr3
        }
        
    def scan_ticker(self, ticker: str) -> Dict:
        """
        Perform full analysis for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with analysis results
        """
        try:
            logger.info(f"Scanning {ticker}")
            
            # Load historical data
            df = self.load_historical_data(ticker)
            if df.empty:
                return {
                    'ticker': ticker,
                    'status': 'failed',
                    'message': 'Insufficient data'
                }
                
            # Calculate indicators
            df_with_indicators = self.calculate_indicators(df)
            
            # Check if near KC middle
            near_kc_middle = self.is_near_kc_middle(df_with_indicators)
            if not near_kc_middle:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': 'Not near KC middle band'
                }
                
            # Check for bullish structure
            has_bullish = self.has_bullish_structure(df_with_indicators)
            if not has_bullish:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': 'No bullish structure'
                }
                
            # Identify support levels
            support_levels = self.identify_support_levels(df_with_indicators)
            
            # Get current price
            current_price = df_with_indicators['Close'].iloc[-1]
            
            # Check if near support
            is_support_nearby = self.is_near_support(current_price, support_levels)
            if not is_support_nearby:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': 'Not near support level'
                }
                
            # Identify L1/L2 patterns
            l_patterns = self.identify_l_patterns(df_with_indicators)
            
            # If no L patterns found, skip
            if l_patterns['L1'] is None and l_patterns['L2'] is None:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': 'No L1/L2 patterns found'
                }
                
            # Prefer L2 pattern if available
            pattern_to_use = 'L2' if l_patterns['L2'] is not None else 'L1'
            pattern_data = l_patterns[pattern_to_use]
            
            # Calculate targets
            targets = self.calculate_targets(
                df_with_indicators, 
                pattern_data['entry'], 
                pattern_data['stop']
            )
            
            # Check if risk is acceptable
            if pattern_data['risk_pct'] > MAX_RISK_PERCENT:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': f"Risk too high: {pattern_data['risk_pct']:.2f}%"
                }
                
            # Check if reward-to-risk is acceptable
            if targets['rr2'] < MIN_REWARD_RISK_RATIO:
                return {
                    'ticker': ticker,
                    'status': 'skipped',
                    'message': f"Reward-to-risk too low: {targets['rr2']:.2f}"
                }
                
            # Compile results
            result = {
                'ticker': ticker,
                'status': 'success',
                'current_price': current_price,
                'pattern_type': pattern_to_use,
                'pattern_date': pattern_data['date'],
                'entry': pattern_data['entry'],
                'stop': pattern_data['stop'],
                'risk_pct': pattern_data['risk_pct'],
                'targets': targets,
                'support_levels': support_levels,
                'kc_middle': df_with_indicators['KC_Middle'].iloc[-1],
                'kc_upper': df_with_indicators['KC_Upper'].iloc[-1],
                'kc_lower': df_with_indicators['KC_Lower'].iloc[-1],
                'sma20_slope': df_with_indicators['SMA20_Slope'].iloc[-1],
                'volume_ratio': df_with_indicators['Volume_Ratio'].iloc[-1]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            logger.debug(traceback.format_exc())
            return {
                'ticker': ticker,
                'status': 'error',
                'message': str(e)
            }
            
    def scan_all_tickers(self, max_workers: int = 5):
        """
        Scan all loaded tickers in parallel.
        
        Args:
            max_workers: Maximum number of parallel workers
        """
        self.results = []
        
        logger.info(f"Starting scan of {len(self.tickers)} tickers with {max_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.scan_ticker, ticker) for ticker in self.tickers]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    self.results.append(result)
                    if result['status'] == 'success':
                        logger.info(f"Found setup: {result['ticker']} - {result['pattern_type']} pattern")
                except Exception as e:
                    logger.error(f"Error processing ticker: {e}")
                    
        logger.info(f"Scan complete. Found {sum(1 for r in self.results if r['status'] == 'success')} setups")
        
    def generate_report(self, output_path: str = None):
        """
        Generate a report of the scan results.
        
        Args:
            output_path: Path to save the report (optional)
        """
        if not self.results:
            logger.warning("No results to report")
            return None
            
        # Create results directory if it doesn't exist
        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'results'
            )
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"kc_hlx_scan_{timestamp}.xlsx")
        
        # Filter successful results
        successful_results = [r for r in self.results if r['status'] == 'success']
        
        if not successful_results:
            logger.warning("No successful setups found")
            return None
            
        # Prepare data for Excel
        excel_data = []
        for result in successful_results:
            row = {
                'Ticker': result['ticker'],
                'Pattern': result['pattern_type'],
                'Current Price': result['current_price'],
                'Entry': result['entry'],
                'Stop Loss': result['stop'],
                'Risk %': result['risk_pct'],
                'Target 1': result['targets']['target1'],
                'Target 2': result['targets']['target2'],
                'Target 3': result['targets']['target3'],
                'R:R (T1)': result['targets']['rr1'],
                'R:R (T2)': result['targets']['rr2'],
                'R:R (T3)': result['targets']['rr3'],
                'SMA20 Slope': result['sma20_slope'],
                'Volume Ratio': result['volume_ratio'],
                'KC Middle': result['kc_middle'],
                'KC Upper': result['kc_upper'],
                'KC Lower': result['kc_lower']
            }
            excel_data.append(row)
            
        # Convert to DataFrame and save to Excel
        df = pd.DataFrame(excel_data)
        
        # Sort by reward-to-risk ratio (T2) in descending order
        df = df.sort_values('R:R (T2)', ascending=False)
        
        # Save to Excel
        df.to_excel(output_path, index=False)
        
        logger.info(f"Report saved to: {output_path}")
        return output_path
        
    def plot_setup(self, ticker: str, output_dir: str = None):
        """
        Generate a plot for a specific ticker setup.
        
        Args:
            ticker: Ticker symbol to plot
            output_dir: Directory to save the plot
            
        Returns:
            Path to saved plot
        """
        # Find the result for this ticker
        result = next((r for r in self.results if r['ticker'] == ticker and r['status'] == 'success'), None)
        
        if result is None:
            logger.warning(f"No successful setup found for {ticker}")
            return None
            
        # Load data again
        df = self.load_historical_data(ticker)
        if df.empty:
            logger.warning(f"Could not load data for {ticker}")
            return None
            
        # Calculate indicators
        df = self.calculate_indicators(df)
        
        # Create plot
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Plot price
        ax.plot(df['Date'], df['Close'], label='Close Price', color='black')
        
        # Plot KC bands
        ax.plot(df['Date'], df['KC_Middle'], label='KC Middle (SMA20)', color='blue', linestyle='--')
        ax.plot(df['Date'], df['KC_Upper'], label='KC Upper', color='red', linestyle=':')
        ax.plot(df['Date'], df['KC_Lower'], label='KC Lower', color='green', linestyle=':')
        
        # Highlight support levels
        for level in result['support_levels']:
            ax.axhline(y=level, color='green', alpha=0.3)
            
        # Mark entry, stop, and targets
        if 'pattern_type' in result:
            # Current price marker
            ax.scatter(df['Date'].iloc[-1], result['current_price'], 
                      color='black', marker='o', s=100, label='Current Price')
                      
            # Entry marker
            ax.axhline(y=result['entry'], color='blue', linestyle='-.')
            ax.text(df['Date'].iloc[-1], result['entry'], f"Entry: {result['entry']:.2f}", 
                   color='blue')
                   
            # Stop marker
            ax.axhline(y=result['stop'], color='red', linestyle='-.')
            ax.text(df['Date'].iloc[-1], result['stop'], f"Stop: {result['stop']:.2f}", 
                   color='red')
                   
            # Target markers
            ax.axhline(y=result['targets']['target1'], color='green', linestyle='-.')
            ax.text(df['Date'].iloc[-1], result['targets']['target1'], 
                   f"Target 1: {result['targets']['target1']:.2f}", color='green')
                   
            ax.axhline(y=result['targets']['target2'], color='green', linestyle='-.')
            ax.text(df['Date'].iloc[-1], result['targets']['target2'], 
                   f"Target 2: {result['targets']['target2']:.2f}", color='green')
                   
            ax.axhline(y=result['targets']['target3'], color='green', linestyle='-.')
            ax.text(df['Date'].iloc[-1], result['targets']['target3'], 
                   f"Target 3: {result['targets']['target3']:.2f}", color='green')
                   
            # Additional annotations
            pattern_text = f"{result['pattern_type']} Pattern Detected"
            risk_text = f"Risk: {result['risk_pct']:.2f}%"
            rr_text = f"R:R (T2): {result['targets']['rr2']:.2f}"
            
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            ax.text(0.05, 0.95, pattern_text, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', bbox=props)
            ax.text(0.05, 0.90, risk_text, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', bbox=props)
            ax.text(0.05, 0.85, rr_text, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', bbox=props)
        
        # Set title and labels
        title = f"{ticker}: KC-HLx Confluence Setup - {datetime.now().strftime('%Y-%m-%d')}"
        ax.set_title(title)
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        
        # Add grid and legend
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left')
        
        # Tight layout
        fig.tight_layout()
        
        # Save plot
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                'results'
            )
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_path = os.path.join(output_dir, f"{ticker}_kc_hlx_setup_{timestamp}.png")
        
        plt.savefig(plot_path, dpi=100)
        plt.close()
        
        logger.info(f"Plot saved to: {plot_path}")
        return plot_path
        
def main():
    """Main function to run the scanner."""
    parser = argparse.ArgumentParser(description='KC-HLx Support Confluence Scanner')
    parser.add_argument('--ticker', type=str, help='Analyze a specific ticker')
    parser.add_argument('--days', type=int, default=LOOKBACK_DAYS, 
                      help=f'Days of historical data to analyze (default: {LOOKBACK_DAYS})')
    parser.add_argument('--output', type=str, help='Output file path')
    
    args = parser.parse_args()
    
    try:
        # Create scanner
        scanner = KCHLXScanner(args.days)
        
        # Load tickers
        ticker_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                 'data', 'Ticker.xlsx')
        scanner.load_tickers(ticker_file)
        
        # If specific ticker provided, only scan that one
        if args.ticker:
            ticker = args.ticker.strip().upper()
            if ticker not in scanner.tickers:
                print(f"Ticker {ticker} not found in ticker file. Scanning it anyway.")
                scanner.tickers = [ticker]
            else:
                scanner.tickers = [ticker]
        
        # Scan tickers
        print(f"Scanning {len(scanner.tickers)} tickers for KC-HLx setups...")
        scanner.scan_all_tickers()
        
        # Count results by status
        success_count = sum(1 for r in scanner.results if r['status'] == 'success')
        skipped_count = sum(1 for r in scanner.results if r['status'] == 'skipped')
        error_count = sum(1 for r in scanner.results if r['status'] == 'error')
        
        print(f"\nScan complete!")
        print(f"Found {success_count} potential setups")
        print(f"Skipped {skipped_count} tickers")
        print(f"Encountered errors with {error_count} tickers")
        
        # Generate report
        if success_count > 0:
            report_path = scanner.generate_report(args.output)
            print(f"\nReport saved to: {report_path}")
            
            # Generate plots for each successful setup
            print("\nGenerating setup plots...")
            for result in scanner.results:
                if result['status'] == 'success':
                    plot_path = scanner.plot_setup(result['ticker'])
                    print(f"- Plot for {result['ticker']} saved")
        else:
            print("\nNo setups found. No report generated.")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        logger.debug(traceback.format_exc())
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())