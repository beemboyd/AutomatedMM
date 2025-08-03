"""
Keltner Channel Filter Analyzer for Daily StrategyB Tickers

This script tests the theory that applying a Keltner Channel upward crossing filter
to Daily timeframe tickers (from StrategyB reports) can improve entry success rates.

The script:
1. Loads tickers from Daily/results/StrategyB_Report_*.xlsx files
2. For each ticker, fetches hourly data
3. Applies Keltner Channel filter - looks for second upward crossing
4. Backtests entries with and without the filter
5. Compares performance metrics

Usage:
    python keltner_channel_filter_analyzer.py [--days 7] [--user Sai] [--limit 20]
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List, Optional, Tuple
import configparser
from collections import defaultdict
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/keltner_filter_analyzer.log'),
        logging.StreamHandler()
    ]
)

def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        raise ValueError(f"No credentials found for user {user_name}")
    
    return config

class KeltnerChannelAnalyzer:
    """Analyzer for Keltner Channel filtering on Daily strategy tickers"""
    
    def __init__(self, user_name: str = "Sai"):
        """Initialize with Zerodha credentials"""
        self.user_name = user_name
        self.logger = logging.getLogger(__name__)
        
        # Load config
        self.config = load_daily_config(user_name)
        credential_section = f'API_CREDENTIALS_{user_name}'
        
        # Get credentials
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        # Initialize Kite Connect
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Data storage
        self.results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       "results")
        self.data_cache = {}  # Cache for historical data
        self.instrument_cache = {}  # Cache for instrument tokens
        self.instruments_loaded = False
        
        # Analysis results
        self.original_trades = []
        self.filtered_trades = []
        
        self.logger.info(f"Successfully initialized for user {user_name}")
    
    def get_instrument_token(self, ticker: str) -> Optional[int]:
        """Get instrument token for a ticker with lazy loading"""
        if ticker in self.instrument_cache:
            return self.instrument_cache[ticker]
        
        if not self.instruments_loaded:
            try:
                self.logger.info("Loading instruments list from Kite...")
                instruments = self.kite.instruments("NSE")
                
                for inst in instruments:
                    self.instrument_cache[inst['tradingsymbol']] = inst['instrument_token']
                
                self.instruments_loaded = True
                self.logger.info(f"Loaded {len(self.instrument_cache)} instruments")
                
            except Exception as e:
                self.logger.error(f"Error loading instruments: {e}")
                return None
        
        return self.instrument_cache.get(ticker)
    
    def calculate_keltner_channels(self, df: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
        """
        Calculate Keltner Channels
        
        Args:
            df: DataFrame with OHLC data
            period: EMA period (default 20)
            multiplier: ATR multiplier (default 2.0)
        
        Returns:
            DataFrame with Keltner Channel bands
        """
        df = df.copy()
        
        # Calculate EMA
        df['EMA'] = df['close'].ewm(span=period).mean()
        
        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
        # Calculate ATR
        df['ATR'] = df['TR'].rolling(window=period).mean()
        
        # Calculate Keltner Channels
        df['KC_Upper'] = df['EMA'] + (multiplier * df['ATR'])
        df['KC_Lower'] = df['EMA'] - (multiplier * df['ATR'])
        df['KC_Middle'] = df['EMA']
        
        # Clean up intermediate columns
        df.drop(['high_low', 'high_close', 'low_close', 'TR'], axis=1, inplace=True)
        
        return df
    
    def detect_keltner_crossings_with_highs(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect upward crossings of Keltner Channel upper band with subsequent high tracking
        
        Args:
            df: DataFrame with Keltner Channel data
            
        Returns:
            List of crossing events with first high after crossing and second crossing details
        """
        crossings = []
        
        if len(df) < 2:
            return crossings
        
        for i in range(1, len(df)):
            prev_row = df.iloc[i-1]
            curr_row = df.iloc[i]
            
            # Check for upward crossing of upper band
            if (prev_row['close'] <= prev_row['KC_Upper'] and 
                curr_row['close'] > curr_row['KC_Upper']):
                
                crossing_event = {
                    'datetime': curr_row.name,
                    'price': curr_row['close'],
                    'upper_band': curr_row['KC_Upper'],
                    'middle_band': curr_row['KC_Middle'],
                    'volume': curr_row['volume'],
                    'first_high': curr_row['high'],  # High of crossing candle
                    'first_high_datetime': curr_row.name,
                    'second_crossing': None,
                    'second_crossing_valid': False
                }
                
                # Look for the highest high after this crossing
                max_high = curr_row['high']
                max_high_datetime = curr_row.name
                
                # Search forward for the peak high after crossing
                for j in range(i+1, min(i+50, len(df))):  # Look ahead max 50 bars
                    future_row = df.iloc[j]
                    if future_row['high'] > max_high:
                        max_high = future_row['high']
                        max_high_datetime = future_row.name
                    
                    # Check for another KC upper crossing that breaks above the first high
                    if (j > i and 
                        df.iloc[j-1]['close'] <= df.iloc[j-1]['KC_Upper'] and 
                        future_row['close'] > future_row['KC_Upper'] and
                        future_row['close'] > max_high):
                        
                        crossing_event['second_crossing'] = {
                            'datetime': future_row.name,
                            'price': future_row['close'],
                            'upper_band': future_row['KC_Upper'],
                            'breaks_first_high': True
                        }
                        crossing_event['second_crossing_valid'] = True
                        break
                
                crossing_event['first_high'] = max_high
                crossing_event['first_high_datetime'] = max_high_datetime
                crossings.append(crossing_event)
        
        return crossings
    
    def load_strategy_reports(self, days: int) -> pd.DataFrame:
        """Load StrategyB reports from the last N days"""
        self.logger.info(f"Loading StrategyB reports from last {days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        files = [f for f in os.listdir(self.results_dir) 
                if f.startswith('StrategyB_Report_') and f.endswith('.xlsx')]
        files.sort()
        
        for file in files:
            try:
                # Extract date from filename
                date_str = file.split('_')[2]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if file_date < cutoff_date:
                    continue
                    
                df = pd.read_excel(os.path.join(self.results_dir, file))
                df['scan_date'] = file_date
                df['scan_file'] = file
                all_data.append(df)
                
            except Exception as e:
                self.logger.debug(f"Skipping {file}: {e}")
                
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Loaded {len(combined)} entries from {len(all_data)} files")
            return combined
        
        return pd.DataFrame()
    
    def fetch_hourly_data(self, ticker: str, from_date: datetime, to_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch hourly historical data with caching"""
        cache_key = f"{ticker}_hourly_{from_date.date()}_{to_date.date()}"
        
        # Check cache
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        # Get instrument token
        token = self.get_instrument_token(ticker)
        if not token:
            self.logger.debug(f"No instrument token for {ticker}")
            return None
        
        try:
            # Fetch hourly data
            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="60minute"
            )
            
            if data:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)  # Remove timezone info
                df.set_index('date', inplace=True)
                
                # Cache the data
                self.data_cache[cache_key] = df
                return df
            
        except Exception as e:
            self.logger.debug(f"Error fetching hourly data for {ticker}: {e}")
            
        return None
    
    def analyze_ticker_with_keltner_filter(self, ticker: str, entry_date: datetime, 
                                         entry_price: float, stop_loss: float,
                                         target1: float, target2: float) -> Tuple[Dict, Dict]:
        """
        Analyze a ticker with and without Keltner Channel filter
        
        Returns:
            Tuple of (original_trade_result, filtered_trade_result)
        """
        # Get hourly data from 10 days before entry to 30 days after  
        start_date = entry_date - timedelta(days=10)
        end_date = min(entry_date + timedelta(days=30), datetime.now())
        
        hourly_df = self.fetch_hourly_data(ticker, start_date, end_date)
        
        # Original trade result (without filter)
        original_result = self.calculate_trade_performance(
            ticker, entry_date, entry_price, stop_loss, target1, target2, hourly_df
        )
        original_result['filter_applied'] = False
        
        # Filtered trade result
        filtered_result = None
        filter_signal = False
        
        if hourly_df is not None and len(hourly_df) > 25:  # Need enough data for Keltner calculation
            # Calculate Keltner Channels on hourly data
            kc_df = self.calculate_keltner_channels(hourly_df)
            
            # Find crossings before entry date with sophisticated logic
            pre_entry_df = kc_df[kc_df.index < entry_date]
            crossings = self.detect_keltner_crossings_with_highs(pre_entry_df)
            
            self.logger.debug(f"{ticker}: Found {len(crossings)} Keltner crossings before {entry_date}")
            
            # Apply sophisticated filter: second crossing that breaks first high
            valid_second_crossings = [c for c in crossings 
                                    if c['second_crossing_valid'] and
                                    c['second_crossing']['datetime'] >= entry_date - timedelta(days=5)]
            
            self.logger.debug(f"{ticker}: Found {len(valid_second_crossings)} valid second crossings within 5 days")
            
            if len(valid_second_crossings) >= 1:  # At least one valid second crossing
                filter_signal = True
                latest_crossing = max(valid_second_crossings, key=lambda x: x['second_crossing']['datetime'])
                self.logger.info(f"{ticker}: PASSED sophisticated Keltner filter - second crossing breaks first high")
                
                # Calculate performance for filtered entry
                filtered_result = self.calculate_trade_performance(
                    ticker, entry_date, entry_price, stop_loss, target1, target2, hourly_df
                )
                filtered_result['filter_applied'] = True
                filtered_result['keltner_crossings'] = len(crossings)
                filtered_result['valid_second_crossings'] = len(valid_second_crossings)
                filtered_result['second_crossing_price'] = latest_crossing['second_crossing']['price']
                filtered_result['first_high'] = latest_crossing['first_high']
            else:
                self.logger.debug(f"{ticker}: No valid second crossings found that break first high")
        else:
            self.logger.debug(f"{ticker}: Insufficient hourly data ({len(hourly_df) if hourly_df is not None else 0} bars)")
        
        # If no filter signal, create empty filtered result
        if not filter_signal:
            filtered_result = {
                'ticker': ticker,
                'entry_date': entry_date,
                'outcome': 'filtered_out',
                'filter_applied': True,
                'pnl_percent': 0,
                'holding_days': 0,
                'keltner_crossings': len(crossings) if 'crossings' in locals() else 0,
                'valid_second_crossings': 0
            }
        
        return original_result, filtered_result
    
    def calculate_trade_performance(self, ticker: str, entry_date: datetime, 
                                  entry_price: float, stop_loss: float,
                                  target1: float, target2: float, 
                                  hourly_df: Optional[pd.DataFrame] = None) -> Dict:
        """Calculate trade performance using hourly data for more precision"""
        result = {
            'ticker': ticker,
            'entry_date': entry_date,
            'outcome': 'unknown',
            'pnl_percent': 0,
            'holding_days': 0,
            'hit_target1': False,
            'hit_target2': False,
            'hit_stoploss': False,
            'max_gain': 0,
            'max_loss': 0
        }
        
        if hourly_df is None or len(hourly_df) < 2:
            return result
        
        # Find entry point in hourly data
        entry_found = False
        entry_idx = None
        for idx, (date, row) in enumerate(hourly_df.iterrows()):
            if date >= entry_date:
                entry_found = True
                entry_idx = idx
                break
                
        if not entry_found or entry_idx is None:
            return result
        
        # Analyze subsequent hours/days
        hours_analyzed = 0
        for i, (date, row) in enumerate(hourly_df.iloc[entry_idx:].iterrows()):
            hours_held = i + 1
            hours_analyzed = hours_held
            
            # Track max gain/loss
            gain = ((row['high'] - entry_price) / entry_price) * 100
            loss = ((row['low'] - entry_price) / entry_price) * 100
            
            result['max_gain'] = max(result['max_gain'], gain)
            result['max_loss'] = min(result['max_loss'], loss)
            
            # Check exit conditions (intrabar)
            if row['low'] <= stop_loss:
                result['hit_stoploss'] = True
                result['outcome'] = 'stoploss'
                result['pnl_percent'] = ((stop_loss - entry_price) / entry_price) * 100
                result['holding_days'] = hours_held / 24  # Convert to days
                break
                
            elif row['high'] >= target2:
                result['hit_target2'] = True
                result['hit_target1'] = True
                result['outcome'] = 'target2'
                result['pnl_percent'] = ((target2 - entry_price) / entry_price) * 100
                result['holding_days'] = hours_held / 24
                break
                
            elif row['high'] >= target1 and not result['hit_target1']:
                result['hit_target1'] = True
                # Continue to see if target2 is hit
                
        # If no exit after analyzing available data
        if result['outcome'] == 'unknown' and hours_analyzed > 0:
            last_close = hourly_df.iloc[entry_idx + hours_analyzed - 1]['close']
            result['outcome'] = 'open'
            result['pnl_percent'] = ((last_close - entry_price) / entry_price) * 100
            result['holding_days'] = hours_analyzed / 24
            
        return result
    
    def run_analysis(self, days: int = 7, limit: Optional[int] = None):
        """Run the complete Keltner Channel filter analysis"""
        # Load StrategyB reports
        strategy_df = self.load_strategy_reports(days)
        if strategy_df.empty:
            self.logger.error("No StrategyB data to analyze")
            return
        
        # Limit analysis if specified
        if limit:
            strategy_df = strategy_df.head(limit)
            self.logger.info(f"Limiting analysis to first {limit} entries")
        
        self.logger.info(f"Analyzing {len(strategy_df)} strategy entries...")
        
        for idx, row in strategy_df.iterrows():
            self.logger.info(f"Processing {idx+1}/{len(strategy_df)}: {row['Ticker']}")
            
            try:
                original_result, filtered_result = self.analyze_ticker_with_keltner_filter(
                    ticker=row['Ticker'],
                    entry_date=row['scan_date'],
                    entry_price=row['Entry_Price'],
                    stop_loss=row['Stop_Loss'],
                    target1=row['Target1'],
                    target2=row['Target2']
                )
                
                # Add original strategy info
                for result in [original_result, filtered_result]:
                    if result:
                        result['score'] = row['Score']
                        result['pattern'] = row['Pattern']
                        result['direction'] = row['Direction']
                        result['volume_ratio'] = row.get('Volume_Ratio', 0)
                        result['momentum_5d'] = row.get('Momentum_5D', 0)
                
                self.original_trades.append(original_result)
                self.filtered_trades.append(filtered_result)
                
            except Exception as e:
                self.logger.error(f"Error analyzing {row['Ticker']}: {e}")
                continue
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        self.logger.info(f"Analysis complete. Original trades: {len(self.original_trades)}, "
                        f"Filtered trades: {len([t for t in self.filtered_trades if t['outcome'] != 'filtered_out'])}")
    
    def generate_comparison_report(self):
        """Generate comparison report between original and filtered strategies"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Calculate statistics
        original_stats = self._calculate_strategy_stats(self.original_trades, "Original Strategy")
        
        # Filter out trades that were filtered out
        executed_filtered_trades = [t for t in self.filtered_trades if t['outcome'] != 'filtered_out']
        filtered_stats = self._calculate_strategy_stats(executed_filtered_trades, "Sophisticated Keltner Filtered Strategy")
        
        # Generate text report
        report_file = f"results/keltner_filter_comparison_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write("SOPHISTICATED KELTNER CHANNEL FILTER ANALYSIS\n")
            f.write("=" * 60 + "\n")
            f.write("Filter Criteria: Second KC crossing that breaks first high\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Analysis Date: {datetime.now()}\n")
            f.write(f"Analysis Period: Last {(datetime.now() - min(t['entry_date'] for t in self.original_trades)).days} days\n\n")
            
            # Strategy comparison
            f.write("STRATEGY COMPARISON\n")
            f.write("-" * 40 + "\n")
            f.write(f"Original Strategy Trades: {len(self.original_trades)}\n")
            f.write(f"Filtered Strategy Trades: {len(executed_filtered_trades)}\n")
            f.write(f"Filter Efficiency: {(1 - len(executed_filtered_trades)/len(self.original_trades))*100:.1f}% trades filtered out\n\n")
            
            # Performance metrics
            f.write("PERFORMANCE METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Metric':<25}{'Original':<15}{'Filtered':<15}{'Improvement':<15}\n")
            f.write("-" * 60 + "\n")
            
            metrics = [
                ('Win Rate %', 'win_rate'),
                ('Avg PnL %', 'avg_pnl'),
                ('Total PnL %', 'total_pnl'),
                ('Expectancy %', 'expectancy'),
                ('Target1 Hit %', 'target1_rate'),
                ('Target2 Hit %', 'target2_rate'),
                ('StopLoss Hit %', 'stoploss_rate'),
                ('Avg Holding Days', 'avg_holding_days')
            ]
            
            for metric_name, metric_key in metrics:
                orig_val = original_stats[metric_key]
                filt_val = filtered_stats[metric_key]
                
                if metric_key in ['win_rate', 'target1_rate', 'target2_rate', 'stoploss_rate']:
                    orig_display = f"{orig_val*100:.1f}%"
                    filt_display = f"{filt_val*100:.1f}%"
                    improvement = f"{(filt_val - orig_val)*100:+.1f}pp"
                else:
                    orig_display = f"{orig_val:.2f}"
                    filt_display = f"{filt_val:.2f}"
                    if orig_val != 0:
                        improvement = f"{((filt_val - orig_val)/abs(orig_val))*100:+.1f}%"
                    else:
                        improvement = "N/A"
                
                f.write(f"{metric_name:<25}{orig_display:<15}{filt_display:<15}{improvement:<15}\n")
            
            # Key insights
            f.write("\n\nKEY INSIGHTS\n")
            f.write("-" * 40 + "\n")
            
            if len(executed_filtered_trades) > 0:
                win_improvement = (filtered_stats['win_rate'] - original_stats['win_rate']) * 100
                pnl_improvement = filtered_stats['avg_pnl'] - original_stats['avg_pnl']
                
                f.write(f"1. Filter Impact: {win_improvement:+.1f}pp win rate change\n")
                f.write(f"2. PnL Impact: {pnl_improvement:+.2f}% average PnL change\n")
                f.write(f"3. Trade Reduction: {len(self.original_trades) - len(executed_filtered_trades)} trades filtered out\n")
                
                if filtered_stats['expectancy'] > original_stats['expectancy']:
                    f.write("4. CONCLUSION: Sophisticated Keltner Channel filter SIGNIFICANTLY IMPROVES strategy performance\n")
                    f.write("5. The filter successfully identifies high-probability entries with second KC crossing above first high\n")
                else:
                    f.write("4. CONCLUSION: Sophisticated Keltner Channel filter does NOT improve strategy performance\n")
            else:
                f.write("No trades passed the sophisticated Keltner Channel filter\n")
                f.write("(This is expected - the sophisticated filter is highly selective)\n")
        
        # Generate Excel report
        excel_file = f"results/keltner_filter_comparison_{timestamp}.xlsx"
        self._save_excel_comparison(excel_file)
        
        self.logger.info(f"Reports saved: {report_file} and {excel_file}")
        return report_file, excel_file
    
    def _calculate_strategy_stats(self, trades: List[Dict], strategy_name: str) -> Dict:
        """Calculate strategy statistics"""
        if not trades:
            return {
                'strategy_name': strategy_name,
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'total_pnl': 0,
                'expectancy': 0,
                'target1_rate': 0,
                'target2_rate': 0,
                'stoploss_rate': 0,
                'avg_holding_days': 0
            }
        
        winning_trades = [t for t in trades if t['pnl_percent'] > 0]
        losing_trades = [t for t in trades if t['pnl_percent'] < 0]
        
        stats = {
            'strategy_name': strategy_name,
            'total_trades': len(trades),
            'win_rate': len(winning_trades) / len(trades),
            'avg_pnl': np.mean([t['pnl_percent'] for t in trades]),
            'total_pnl': sum(t['pnl_percent'] for t in trades),
            'target1_rate': sum(1 for t in trades if t.get('hit_target1', False)) / len(trades),
            'target2_rate': sum(1 for t in trades if t.get('hit_target2', False)) / len(trades),
            'stoploss_rate': sum(1 for t in trades if t.get('hit_stoploss', False)) / len(trades),
            'avg_holding_days': np.mean([t.get('holding_days', 0) for t in trades])
        }
        
        # Calculate expectancy
        avg_win = np.mean([t['pnl_percent'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl_percent'] for t in losing_trades]) if losing_trades else 0
        stats['expectancy'] = (stats['win_rate'] * avg_win) + ((1 - stats['win_rate']) * avg_loss)
        
        return stats
    
    def _save_excel_comparison(self, filename: str):
        """Save detailed Excel comparison report with proper date formatting"""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Original trades
            original_df = pd.DataFrame(self.original_trades)
            if 'entry_date' in original_df.columns:
                original_df['entry_date'] = pd.to_datetime(original_df['entry_date']).dt.strftime('%Y-%m-%d')
            original_df.to_excel(writer, sheet_name='Original_Trades', index=False)
            
            # Filtered trades
            filtered_df = pd.DataFrame(self.filtered_trades)
            if 'entry_date' in filtered_df.columns:
                filtered_df['entry_date'] = pd.to_datetime(filtered_df['entry_date']).dt.strftime('%Y-%m-%d')
            filtered_df.to_excel(writer, sheet_name='Filtered_Trades', index=False)
            
            # Summary comparison
            original_stats = self._calculate_strategy_stats(self.original_trades, "Original")
            executed_filtered = [t for t in self.filtered_trades if t['outcome'] != 'filtered_out']
            filtered_stats = self._calculate_strategy_stats(executed_filtered, "Filtered")
            
            comparison_data = []
            for key in ['total_trades', 'win_rate', 'avg_pnl', 'total_pnl', 'expectancy']:
                comparison_data.append({
                    'Metric': key,
                    'Original': original_stats[key],
                    'Filtered': filtered_stats[key],
                    'Difference': filtered_stats[key] - original_stats[key]
                })
            
            comparison_df = pd.DataFrame(comparison_data)
            comparison_df.to_excel(writer, sheet_name='Summary_Comparison', index=False)
            
            # Format the date columns properly in the Excel file
            workbook = writer.book
            for sheet_name in ['Original_Trades', 'Filtered_Trades']:
                if sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    # Find the entry_date column and format it
                    for col_num, col_name in enumerate(filtered_df.columns if sheet_name == 'Filtered_Trades' else original_df.columns, 1):
                        if 'date' in col_name.lower():
                            col_letter = chr(64 + col_num)  # Convert to Excel column letter
                            for row in range(2, len(filtered_df) + 2 if sheet_name == 'Filtered_Trades' else len(original_df) + 2):
                                cell = worksheet[f'{col_letter}{row}']
                                if cell.value and isinstance(cell.value, str):
                                    try:
                                        # Parse the date string and set as date
                                        date_obj = pd.to_datetime(cell.value)
                                        cell.value = date_obj.date()
                                        cell.number_format = 'YYYY-MM-DD'
                                    except:
                                        pass


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze Keltner Channel filter effectiveness on Daily strategy')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    parser.add_argument('-u', '--user', type=str, default='Sai', help='User name for API credentials')
    parser.add_argument('--limit', type=int, help='Limit number of entries to analyze (for testing)')
    
    args = parser.parse_args()
    
    # Create directories
    os.makedirs('results', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    try:
        analyzer = KeltnerChannelAnalyzer(user_name=args.user)
        analyzer.run_analysis(days=args.days, limit=args.limit)
        
        if analyzer.original_trades:
            text_report, excel_report = analyzer.generate_comparison_report()
            
            print(f"\nKeltner Channel Filter Analysis Complete!")
            print(f"Text report: {text_report}")
            print(f"Excel report: {excel_report}")
            
            # Show summary
            with open(text_report, 'r') as f:
                lines = f.readlines()
                print("\n" + "".join(lines[:50]))
                if len(lines) > 50:
                    print("... (see full report for details)")
        else:
            print("No trades to analyze")
                
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    main()