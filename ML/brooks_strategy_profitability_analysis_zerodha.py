#!/usr/bin/env python
"""
Brooks Higher Probability LONG Reversal Strategy Profitability Analysis using Zerodha API
======================================================================================
This script analyzes the profitability of tickers from Brooks Higher Probability LONG Reversal 
strategy files by date, using real-time Zerodha API data instead of local files. It tracks 
performance over different holding periods and provides comprehensive statistics.

Features:
- Analyzes all Brooks strategy files chronologically
- Uses Zerodha API for real market data and PnL calculations
- Tracks 1-day, 3-day, 5-day, and 10-day performance
- Calculates win/loss ratios and average returns
- Analyzes stop loss effectiveness
- Multi-user support for different Zerodha accounts
- Generates detailed reports and visualizations
- Exports results to Excel and HTML

Author: Claude Code Assistant
Created: 2025-05-30
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
import argparse
from pathlib import Path
import logging
import glob
import re
import time
import json
import configparser
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import timedelta

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from parent directory
try:
    from user_context_manager import get_context_manager, get_user_data_handler, UserCredentials
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False
    
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'brooks_strategy_zerodha_analysis.log'))
    ]
)
logger = logging.getLogger(__name__)

class BrooksStrategyZerodhaAnalyzer:
    """Analyze profitability of Brooks Higher Probability LONG Reversal strategy using Zerodha API"""
    
    def __init__(self, user_name="Sai"):
        """Initialize the analyzer with user credentials"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.join(os.path.dirname(self.script_dir), "Daily")
        self.results_dir_source = os.path.join(self.daily_dir, "results")
        self.results_dir = os.path.join(self.script_dir, "results")
        self.user_name = user_name
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Performance tracking periods
        self.holding_periods = [1, 3, 5, 10]  # days
        
        # Initialize user context and Zerodha connection
        self.data_handler = self._initialize_data_handler()
        
        logger.info(f"Initialized Brooks Strategy Zerodha Analyzer for user: {user_name}")
        logger.info(f"Brooks results directory: {self.results_dir_source}")
    
    def _initialize_data_handler(self):
        """Initialize data handler with user credentials"""
        try:
            if USER_CONTEXT_AVAILABLE:
                # Set up user context
                context_manager = get_context_manager()
                
                # Load credentials from config.ini
                user_credentials = self._load_user_credentials()
                
                if user_credentials:
                    # Set current user context
                    context_manager.set_current_user(self.user_name, user_credentials)
                    
                    # Get data handler for current user
                    data_handler = get_user_data_handler()
                    
                    if data_handler and hasattr(data_handler, 'kite'):
                        logger.info(f"Successfully initialized Zerodha data handler for user: {self.user_name}")
                        logger.info(f"Using API Key: {data_handler.api_key[:8]}...")
                        return data_handler
            
            # Fallback to direct ZerodhaHandler if user context is not available
            logger.warning("User context not available, falling back to direct ZerodhaHandler")
            from zerodha_handler import get_zerodha_handler
            return get_zerodha_handler()
            
        except Exception as e:
            logger.error(f"Failed to initialize data handler: {e}")
            raise
    
    def _load_user_credentials(self) -> Optional[UserCredentials]:
        """Load user credentials from config.ini"""
        try:
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.error(f"Config file not found: {config_path}")
                return None
            
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            if credential_section not in config.sections():
                logger.error(f"No credentials found for user {self.user_name}")
                return None
            
            api_key = config.get(credential_section, 'api_key')
            api_secret = config.get(credential_section, 'api_secret')
            access_token = config.get(credential_section, 'access_token')
            
            if not all([api_key, api_secret, access_token]):
                logger.error(f"Incomplete credentials for user {self.user_name}")
                return None
            
            return UserCredentials(
                name=self.user_name,
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token
            )
            
        except Exception as e:
            logger.error(f"Error loading user credentials: {e}")
            return None
    
    def get_brooks_files(self) -> List[Tuple[str, datetime.datetime]]:
        """Get all Brooks Higher Probability LONG Reversal files sorted by date"""
        try:
            files = glob.glob(os.path.join(self.results_dir_source, "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"))
            
            file_dates = []
            for file_path in files:
                filename = os.path.basename(file_path)
                # Extract date from filename: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
                date_match = re.search(r'Brooks_Higher_Probability_LONG_Reversal_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx', filename)
                if date_match:
                    day, month, year, hour, minute = date_match.groups()
                    scan_date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                    file_dates.append((file_path, scan_date))
            
            # Sort by date
            file_dates.sort(key=lambda x: x[1])
            
            logger.info(f"Found {len(file_dates)} Brooks strategy files")
            return file_dates
            
        except Exception as e:
            logger.error(f"Error getting Brooks files: {e}")
            return []
    
    def read_brooks_file(self, file_path: str) -> List[Dict]:
        """Read ticker data from a Brooks strategy file"""
        try:
            # Read the Excel file
            df = pd.read_excel(file_path)
            
            if df.empty:
                logger.warning(f"Empty file: {os.path.basename(file_path)}")
                return []
            
            # Extract relevant columns
            required_cols = ['Ticker', 'Entry_Price', 'Stop_Loss', 'Target1', 'Risk_Reward_Ratio']
            
            # Check if required columns exist
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"Missing columns in {os.path.basename(file_path)}: {missing_cols}")
                # Try alternative column names
                col_mapping = {
                    'Entry_Price': ['Entry Price', 'EntryPrice', 'entry_price'],
                    'Stop_Loss': ['Stop Loss', 'StopLoss', 'stop_loss', 'SL'],
                    'Target1': ['Target', 'Target 1', 'target1', 'Target_1'],
                    'Risk_Reward_Ratio': ['Risk Reward Ratio', 'RiskRewardRatio', 'R:R', 'RR']
                }
                
                for std_col, alt_cols in col_mapping.items():
                    if std_col not in df.columns:
                        for alt_col in alt_cols:
                            if alt_col in df.columns:
                                df = df.rename(columns={alt_col: std_col})
                                break
            
            # Extract tickers and their strategy data
            strategy_data = []
            for _, row in df.iterrows():
                if pd.notna(row.get('Ticker')):
                    ticker_data = {
                        'ticker': str(row['Ticker']).strip().upper(),
                        'entry_price': float(row.get('Entry_Price', 0)) if pd.notna(row.get('Entry_Price')) else 0,
                        'stop_loss': float(row.get('Stop_Loss', 0)) if pd.notna(row.get('Stop_Loss')) else 0,
                        'target1': float(row.get('Target1', 0)) if pd.notna(row.get('Target1')) else 0,
                        'risk_reward_ratio': float(row.get('Risk_Reward_Ratio', 0)) if pd.notna(row.get('Risk_Reward_Ratio')) else 0
                    }
                    strategy_data.append(ticker_data)
            
            logger.info(f"Read {len(strategy_data)} tickers from {os.path.basename(file_path)}")
            return strategy_data
            
        except Exception as e:
            logger.error(f"Error reading Brooks file {file_path}: {e}")
            return []
    
    def get_ticker_zerodha_data(self, ticker: str, from_date: datetime.datetime, to_date: datetime.datetime) -> Optional[pd.DataFrame]:
        """Get OHLC data for a ticker from Zerodha API"""
        try:
            # Ensure to_date is not in the future
            current_date = datetime.datetime.now()
            if to_date > current_date:
                to_date = current_date
            
            # Convert datetime objects to date strings for Zerodha API
            from_date_str = from_date.strftime('%Y-%m-%d')
            to_date_str = to_date.strftime('%Y-%m-%d')
            
            # Fetch daily historical data
            historical_data = self.data_handler.fetch_historical_data(
                ticker,
                interval="day",
                from_date=from_date_str,
                to_date=to_date_str
            )
            
            if not historical_data or len(historical_data) < 2:
                logger.warning(f"Insufficient daily data for {ticker}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            
            # Standardize column names
            columns_map = {
                'date': 'Date',
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
            
            df = df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns})
            
            # Ensure Date is datetime
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            df = df.reset_index(drop=True)
            
            logger.info(f"Retrieved {len(df)} days of data for {ticker} from Zerodha")
            return df
            
        except Exception as e:
            logger.error(f"Error getting Zerodha data for {ticker}: {e}")
            return None
    
    def calculate_brooks_performance(self, ticker_data: pd.DataFrame, entry_date: datetime.datetime, 
                                   strategy_data: Dict, holding_periods: List[int]) -> Dict:
        """Calculate performance for Brooks strategy including stop loss analysis"""
        try:
            # Find the entry date or the next available trading day
            entry_date_only = entry_date.date()
            
            # Find the closest trading day on or after entry date
            entry_row = None
            for idx, row in ticker_data.iterrows():
                if row['Date'].date() >= entry_date_only:
                    entry_row = idx
                    break
            
            if entry_row is None:
                return {}
            
            # Use strategy entry price if available, otherwise use actual close price
            entry_price = strategy_data.get('entry_price', 0)
            if entry_price == 0:
                entry_price = ticker_data.iloc[entry_row]['Close']
            
            stop_loss_price = strategy_data.get('stop_loss', 0)
            target_price = strategy_data.get('target1', 0)
            
            performances = {
                'entry_price_used': entry_price,
                'stop_loss_price': stop_loss_price,
                'target_price': target_price,
                'stop_loss_hit': False,
                'target_hit': False,
                'exit_reason': 'time_based'
            }
            
            # Track price action for stop loss and target analysis
            for period in holding_periods:
                exit_row = entry_row + period
                
                if exit_row < len(ticker_data):
                    # Check if stop loss or target was hit during the period
                    period_data = ticker_data.iloc[entry_row+1:exit_row+1]
                    
                    stop_hit = False
                    target_hit = False
                    exit_price = ticker_data.iloc[exit_row]['Close']
                    exit_reason = 'time_based'
                    
                    # Check for stop loss hit (assuming LONG position)
                    if stop_loss_price > 0:
                        for _, day_data in period_data.iterrows():
                            if day_data['Low'] <= stop_loss_price:
                                stop_hit = True
                                exit_price = stop_loss_price
                                exit_reason = 'stop_loss'
                                break
                    
                    # Check for target hit (only if stop loss wasn't hit)
                    if not stop_hit and target_price > 0:
                        for _, day_data in period_data.iterrows():
                            if day_data['High'] >= target_price:
                                target_hit = True
                                exit_price = target_price
                                exit_reason = 'target'
                                break
                    
                    # Calculate performance
                    performance = ((exit_price - entry_price) / entry_price) * 100
                    
                    performances[f'performance_{period}d'] = performance
                    performances[f'exit_price_{period}d'] = exit_price
                    performances[f'exit_reason_{period}d'] = exit_reason
                    performances[f'stop_hit_{period}d'] = stop_hit
                    performances[f'target_hit_{period}d'] = target_hit
                else:
                    # If we don't have enough future data, skip this period
                    performances[f'performance_{period}d'] = None
            
            return performances
            
        except Exception as e:
            logger.error(f"Error calculating Brooks performance: {e}")
            return {}
    
    def analyze_brooks_file(self, file_path: str, scan_date: datetime.datetime) -> Dict:
        """Analyze a single Brooks strategy file"""
        try:
            strategy_data = self.read_brooks_file(file_path)
            
            if not strategy_data:
                return {
                    'file': os.path.basename(file_path),
                    'scan_date': scan_date,
                    'total_tickers': 0,
                    'analyzed_tickers': 0,
                    'results': []
                }
            
            results = []
            analyzed_count = 0
            
            # Calculate the date range for Zerodha data
            # Get data from 1 day before scan date to 15 days after (to cover all holding periods)
            from_date = scan_date - datetime.timedelta(days=1)
            to_date = scan_date + datetime.timedelta(days=max(self.holding_periods) + 5)
            
            for ticker_strategy in strategy_data:
                ticker = ticker_strategy['ticker']
                ticker_data = self.get_ticker_zerodha_data(ticker, from_date, to_date)
                
                if ticker_data is not None and not ticker_data.empty:
                    performances = self.calculate_brooks_performance(
                        ticker_data, scan_date, ticker_strategy, self.holding_periods
                    )
                    
                    if performances:
                        result = {
                            'ticker': ticker,
                            'scan_date': scan_date,
                            **ticker_strategy,
                            **performances
                        }
                        results.append(result)
                        analyzed_count += 1
                
                # Throttle API requests to avoid rate limits
                time.sleep(0.1)
            
            analysis = {
                'file': os.path.basename(file_path),
                'scan_date': scan_date,
                'total_tickers': len(strategy_data),
                'analyzed_tickers': analyzed_count,
                'results': results
            }
            
            logger.info(f"Analyzed {analyzed_count}/{len(strategy_data)} tickers from {os.path.basename(file_path)}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing Brooks file {file_path}: {e}")
            return {}
    
    def calculate_brooks_statistics(self, all_results: List[Dict]) -> Dict:
        """Calculate comprehensive statistics for Brooks strategy"""
        try:
            if not all_results:
                return {}
            
            # Flatten all results
            all_performances = []
            for file_result in all_results:
                all_performances.extend(file_result.get('results', []))
            
            if not all_performances:
                return {}
            
            df = pd.DataFrame(all_performances)
            
            stats = {
                'overall': {
                    'total_scans': len(all_results),
                    'total_tickers_scanned': sum([r.get('total_tickers', 0) for r in all_results]),
                    'total_tickers_analyzed': sum([r.get('analyzed_tickers', 0) for r in all_results]),
                    'date_range': {
                        'start': min([r.get('scan_date') for r in all_results if r.get('scan_date')]),
                        'end': max([r.get('scan_date') for r in all_results if r.get('scan_date')])
                    },
                    'average_risk_reward_ratio': df['risk_reward_ratio'].mean() if 'risk_reward_ratio' in df.columns else 0
                }
            }
            
            # Calculate statistics for each holding period
            for period in self.holding_periods:
                col = f'performance_{period}d'
                stop_col = f'stop_hit_{period}d'
                target_col = f'target_hit_{period}d'
                
                if col in df.columns:
                    valid_data = df[col].dropna()
                    
                    if len(valid_data) > 0:
                        positive_returns = valid_data[valid_data > 0]
                        negative_returns = valid_data[valid_data <= 0]
                        
                        # Calculate stop loss and target statistics
                        stop_loss_hits = df[stop_col].sum() if stop_col in df.columns else 0
                        target_hits = df[target_col].sum() if target_col in df.columns else 0
                        total_trades = len(valid_data)
                        
                        period_stats = {
                            'total_trades': total_trades,
                            'profitable_trades': len(positive_returns),
                            'unprofitable_trades': len(negative_returns),
                            'win_rate': (len(positive_returns) / total_trades) * 100 if total_trades > 0 else 0,
                            'average_return': valid_data.mean(),
                            'median_return': valid_data.median(),
                            'std_return': valid_data.std(),
                            'max_return': valid_data.max(),
                            'min_return': valid_data.min(),
                            'average_winning_return': positive_returns.mean() if len(positive_returns) > 0 else 0,
                            'average_losing_return': negative_returns.mean() if len(negative_returns) > 0 else 0,
                            'profit_factor': abs(positive_returns.sum() / negative_returns.sum()) if negative_returns.sum() != 0 else float('inf') if positive_returns.sum() > 0 else 0,
                            'stop_loss_hits': stop_loss_hits,
                            'target_hits': target_hits,
                            'stop_loss_rate': (stop_loss_hits / total_trades) * 100 if total_trades > 0 else 0,
                            'target_hit_rate': (target_hits / total_trades) * 100 if total_trades > 0 else 0
                        }
                        
                        stats[f'{period}_day'] = period_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating Brooks statistics: {e}")
            return {}
    
    def create_brooks_visualizations(self, all_results: List[Dict], stats: Dict) -> List[str]:
        """Create visualization plots for Brooks strategy"""
        try:
            plot_files = []
            
            # Flatten all results
            all_performances = []
            for file_result in all_results:
                all_performances.extend(file_result.get('results', []))
            
            if not all_performances:
                return plot_files
            
            df = pd.DataFrame(all_performances)
            
            # Set style
            plt.style.use('seaborn-v0_8')
            fig_size = (15, 10)
            
            # 1. Performance Distribution by Holding Period
            fig, axes = plt.subplots(2, 2, figsize=fig_size)
            fig.suptitle('Brooks Strategy Performance Distribution by Holding Period (Zerodha Data)', fontsize=16, fontweight='bold')
            
            for i, period in enumerate(self.holding_periods):
                row, col = i // 2, i % 2
                col_name = f'performance_{period}d'
                
                if col_name in df.columns:
                    valid_data = df[col_name].dropna()
                    
                    if len(valid_data) > 0:
                        axes[row, col].hist(valid_data, bins=30, alpha=0.7, color='steelblue', edgecolor='black')
                        axes[row, col].axvline(valid_data.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {valid_data.mean():.2f}%')
                        axes[row, col].axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
                        axes[row, col].set_title(f'{period}-Day Performance')
                        axes[row, col].set_xlabel('Return (%)')
                        axes[row, col].set_ylabel('Frequency')
                        axes[row, col].legend()
                        axes[row, col].grid(True, alpha=0.3)
            
            plt.tight_layout()
            plot_file = os.path.join(self.results_dir, 'brooks_zerodha_performance_distribution.png')
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(plot_file)
            
            # 2. Win Rate vs Stop Loss/Target Hit Rate
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            periods = []
            win_rates = []
            stop_rates = []
            target_rates = []
            
            for period in self.holding_periods:
                if f'{period}_day' in stats:
                    periods.append(f'{period}D')
                    win_rates.append(stats[f'{period}_day']['win_rate'])
                    stop_rates.append(stats[f'{period}_day']['stop_loss_rate'])
                    target_rates.append(stats[f'{period}_day']['target_hit_rate'])
            
            # Win Rate Chart
            bars1 = ax1.bar(periods, win_rates, color=['green' if rate >= 50 else 'red' for rate in win_rates], alpha=0.7)
            ax1.set_title('Win Rate by Holding Period', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Win Rate (%)')
            ax1.set_ylim(0, 100)
            ax1.axhline(50, color='black', linestyle='--', alpha=0.5, label='Break-even (50%)')
            
            for bar, rate in zip(bars1, win_rates):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Stop Loss vs Target Hit Rate
            x = np.arange(len(periods))
            width = 0.35
            
            bars2 = ax2.bar(x - width/2, stop_rates, width, label='Stop Loss Hit', color='red', alpha=0.7)
            bars3 = ax2.bar(x + width/2, target_rates, width, label='Target Hit', color='green', alpha=0.7)
            
            ax2.set_title('Stop Loss vs Target Hit Rates', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Hit Rate (%)')
            ax2.set_xlabel('Holding Period')
            ax2.set_xticks(x)
            ax2.set_xticklabels(periods)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Add value labels
            for bars in [bars2, bars3]:
                for bar in bars:
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                            f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            plot_file = os.path.join(self.results_dir, 'brooks_zerodha_win_rates_analysis.png')
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(plot_file)
            
            # 3. Risk-Reward Analysis
            if 'risk_reward_ratio' in df.columns:
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
                
                # Risk-Reward Distribution
                rr_data = df['risk_reward_ratio'].dropna()
                ax1.hist(rr_data, bins=20, alpha=0.7, color='purple', edgecolor='black')
                ax1.axvline(rr_data.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {rr_data.mean():.2f}')
                ax1.set_title('Risk-Reward Ratio Distribution', fontsize=14, fontweight='bold')
                ax1.set_xlabel('Risk-Reward Ratio')
                ax1.set_ylabel('Frequency')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
                
                # Performance vs Risk-Reward
                if 'performance_5d' in df.columns:
                    perf_data = df['performance_5d'].dropna()
                    rr_aligned = df.loc[perf_data.index, 'risk_reward_ratio']
                    
                    ax2.scatter(rr_aligned, perf_data, alpha=0.6, color='blue')
                    ax2.set_title('5-Day Performance vs Risk-Reward Ratio', fontsize=14, fontweight='bold')
                    ax2.set_xlabel('Risk-Reward Ratio')
                    ax2.set_ylabel('5-Day Return (%)')
                    ax2.axhline(0, color='black', linestyle='-', alpha=0.5)
                    ax2.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plot_file = os.path.join(self.results_dir, 'brooks_zerodha_risk_reward_analysis.png')
                plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                plt.close()
                plot_files.append(plot_file)
            
            logger.info(f"Created {len(plot_files)} Brooks strategy visualization plots")
            return plot_files
            
        except Exception as e:
            logger.error(f"Error creating Brooks visualizations: {e}")
            return []
    
    def export_brooks_excel(self, all_results: List[Dict], stats: Dict) -> str:
        """Export Brooks strategy results to Excel"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(self.results_dir, f"brooks_zerodha_strategy_analysis_{timestamp}.xlsx")
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Summary statistics
                summary_data = []
                for period in self.holding_periods:
                    if f'{period}_day' in stats:
                        period_stats = stats[f'{period}_day']
                        summary_data.append({
                            'Holding_Period': f'{period} Days',
                            'Total_Trades': period_stats['total_trades'],
                            'Profitable_Trades': period_stats['profitable_trades'],
                            'Win_Rate_%': round(period_stats['win_rate'], 2),
                            'Average_Return_%': round(period_stats['average_return'], 2),
                            'Median_Return_%': round(period_stats['median_return'], 2),
                            'Max_Return_%': round(period_stats['max_return'], 2),
                            'Min_Return_%': round(period_stats['min_return'], 2),
                            'Avg_Winning_Return_%': round(period_stats['average_winning_return'], 2),
                            'Avg_Losing_Return_%': round(period_stats['average_losing_return'], 2),
                            'Profit_Factor': round(period_stats['profit_factor'], 2),
                            'Stop_Loss_Hits': period_stats['stop_loss_hits'],
                            'Target_Hits': period_stats['target_hits'],
                            'Stop_Loss_Rate_%': round(period_stats['stop_loss_rate'], 2),
                            'Target_Hit_Rate_%': round(period_stats['target_hit_rate'], 2)
                        })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Brooks_Summary_Statistics', index=False)
                
                # Individual file results
                file_summary = []
                for file_result in all_results:
                    file_summary.append({
                        'File': file_result['file'],
                        'Scan_Date': file_result['scan_date'].strftime('%Y-%m-%d %H:%M'),
                        'Total_Tickers': file_result['total_tickers'],
                        'Analyzed_Tickers': file_result['analyzed_tickers'],
                        'Analysis_Rate_%': round((file_result['analyzed_tickers'] / file_result['total_tickers'] * 100) if file_result['total_tickers'] > 0 else 0, 2)
                    })
                
                if file_summary:
                    file_df = pd.DataFrame(file_summary)
                    file_df.to_excel(writer, sheet_name='File_Summary', index=False)
                
                # All individual ticker results
                all_ticker_results = []
                for file_result in all_results:
                    for result in file_result.get('results', []):
                        ticker_result = {
                            'File': file_result['file'],
                            'Scan_Date': file_result['scan_date'].strftime('%Y-%m-%d %H:%M'),
                            'Ticker': result['ticker'],
                            'Entry_Price': result.get('entry_price', 0),
                            'Stop_Loss': result.get('stop_loss', 0),
                            'Target1': result.get('target1', 0),
                            'Risk_Reward_Ratio': result.get('risk_reward_ratio', 0)
                        }
                        
                        for period in self.holding_periods:
                            perf_col = f'performance_{period}d'
                            exit_col = f'exit_reason_{period}d'
                            if perf_col in result:
                                ticker_result[f'{period}D_Return_%'] = round(result[perf_col], 2) if result[perf_col] is not None else None
                                ticker_result[f'{period}D_Exit_Reason'] = result.get(exit_col, '')
                        
                        all_ticker_results.append(ticker_result)
                
                if all_ticker_results:
                    ticker_df = pd.DataFrame(all_ticker_results)
                    ticker_df.to_excel(writer, sheet_name='All_Ticker_Results', index=False)
            
            logger.info(f"Exported Brooks strategy results to Excel: {excel_file}")
            return excel_file
            
        except Exception as e:
            logger.error(f"Error exporting Brooks results to Excel: {e}")
            return ""
    
    def generate_brooks_html_report(self, all_results: List[Dict], stats: Dict, plot_files: List[str], excel_file: str) -> str:
        """Generate HTML report for Brooks strategy"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = os.path.join(self.results_dir, f"brooks_zerodha_strategy_report_{timestamp}.html")
            
            # Calculate overall statistics
            overall = stats.get('overall', {})
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Brooks Higher Probability LONG Reversal Strategy Analysis (Zerodha Data)</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f9f9f9;
                    }}
                    h1, h2, h3 {{
                        color: #2c3e50;
                    }}
                    h1 {{
                        border-bottom: 2px solid #27ae60;
                        padding-bottom: 10px;
                    }}
                    .summary-stats {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin: 20px 0;
                    }}
                    .stat-card {{
                        background-color: white;
                        border-radius: 8px;
                        padding: 20px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        border-left: 5px solid #27ae60;
                    }}
                    .stat-value {{
                        font-size: 2em;
                        font-weight: bold;
                        color: #27ae60;
                    }}
                    .stat-label {{
                        color: #7f8c8d;
                        font-size: 0.9em;
                        margin-top: 5px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin: 20px 0;
                        background-color: white;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }}
                    th, td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #27ae60;
                        color: white;
                        font-weight: bold;
                    }}
                    .positive {{
                        color: #27ae60;
                        font-weight: bold;
                    }}
                    .negative {{
                        color: #e74c3c;
                        font-weight: bold;
                    }}
                    .chart-container {{
                        text-align: center;
                        margin: 30px 0;
                        background-color: white;
                        border-radius: 8px;
                        padding: 20px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }}
                    .chart-container img {{
                        max-width: 100%;
                        height: auto;
                        border-radius: 4px;
                    }}
                    .strategy-note {{
                        background-color: #d4edda;
                        border: 1px solid #c3e6cb;
                        border-radius: 8px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .zerodha-badge {{
                        background-color: #387ed1;
                        color: white;
                        padding: 5px 10px;
                        border-radius: 4px;
                        font-weight: bold;
                        display: inline-block;
                        margin-left: 10px;
                    }}
                </style>
            </head>
            <body>
                <h1>📈 Brooks Higher Probability LONG Reversal Strategy Analysis <span class="zerodha-badge">Zerodha Data</span></h1>
                <p><strong>Generated:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>User Account:</strong> {self.user_name}</p>
                
                <div class="strategy-note">
                    <h3>🎯 About This Strategy</h3>
                    <p>The Al Brooks Higher Probability LONG Reversal strategy identifies bullish reversal patterns with 60%+ probability based on:</p>
                    <ul>
                        <li>Strong breakout above resistance levels</li>
                        <li>Multiple confirmation bars (at least 2 of last 3 bullish)</li>
                        <li>Volume expansion on breakout (1.5x+ average)</li>
                        <li>Price action confirmation (close in upper 70% of range)</li>
                        <li>Wider stop losses (2.5x ATR) for higher probability trades</li>
                    </ul>
                    <p><strong>Note:</strong> This analysis uses real-time data from Zerodha's API instead of local data files.</p>
                </div>
                
                <h2>📈 Overall Summary</h2>
                <div class="summary-stats">
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('total_scans', 0)}</div>
                        <div class="stat-label">Total Strategy Files Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('total_tickers_analyzed', 0):,}</div>
                        <div class="stat-label">Total LONG Setups Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('average_risk_reward_ratio', 0):.2f}</div>
                        <div class="stat-label">Average Risk-Reward Ratio</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{overall.get('date_range', {}).get('start', 'N/A')}</div>
                        <div class="stat-label">Analysis Start Date</div>
                    </div>
                </div>
            """
            
            # Performance statistics table
            html_content += """
                <h2>🎯 Strategy Performance by Holding Period</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Holding Period</th>
                            <th>Total Trades</th>
                            <th>Win Rate (%)</th>
                            <th>Avg Return (%)</th>
                            <th>Stop Loss Rate (%)</th>
                            <th>Target Hit Rate (%)</th>
                            <th>Max Return (%)</th>
                            <th>Min Return (%)</th>
                            <th>Profit Factor</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for period in self.holding_periods:
                if f'{period}_day' in stats:
                    period_stats = stats[f'{period}_day']
                    win_rate = period_stats['win_rate']
                    avg_return = period_stats['average_return']
                    
                    html_content += f"""
                        <tr>
                            <td>{period} Day{'s' if period > 1 else ''}</td>
                            <td>{period_stats['total_trades']:,}</td>
                            <td class="{'positive' if win_rate >= 50 else 'negative'}">{win_rate:.1f}%</td>
                            <td class="{'positive' if avg_return >= 0 else 'negative'}">{avg_return:.2f}%</td>
                            <td class="negative">{period_stats['stop_loss_rate']:.1f}%</td>
                            <td class="positive">{period_stats['target_hit_rate']:.1f}%</td>
                            <td class="positive">{period_stats['max_return']:.2f}%</td>
                            <td class="negative">{period_stats['min_return']:.2f}%</td>
                            <td>{period_stats['profit_factor']:.2f}</td>
                        </tr>
                    """
            
            html_content += """
                    </tbody>
                </table>
            """
            
            # Add charts
            if plot_files:
                html_content += "<h2>📊 Strategy Performance Visualizations</h2>"
                for plot_file in plot_files:
                    if os.path.exists(plot_file):
                        plot_name = os.path.basename(plot_file).replace('brooks_zerodha_', '').replace('_', ' ').replace('.png', '').title()
                        html_content += f"""
                        <div class="chart-container">
                            <h3>{plot_name}</h3>
                            <img src="{os.path.basename(plot_file)}" alt="{plot_name}">
                        </div>
                        """
            
            # Add download links
            html_content += f"""
                <h2>📁 Download Results</h2>
                <p><a href="{os.path.basename(excel_file)}" target="_blank">Download Excel Report</a></p>
                
                <div style="margin-top: 50px; text-align: center; color: #7f8c8d; font-size: 0.9em;">
                    <p>Report generated by Brooks Strategy Zerodha Analyzer for user: {self.user_name}</p>
                    <p>Analysis covers {overall.get('total_scans', 0)} strategy files from {overall.get('date_range', {}).get('start', 'N/A')} to {overall.get('date_range', {}).get('end', 'N/A')}</p>
                    <p>Using Zerodha API data instead of local files</p>
                </div>
            </body>
            </html>
            """
            
            with open(html_file, 'w') as f:
                f.write(html_content)
            
            logger.info(f"Generated Brooks strategy HTML report: {html_file}")
            return html_file
            
        except Exception as e:
            logger.error(f"Error generating Brooks HTML report: {e}")
            return ""
    
    def run_brooks_analysis(self) -> Dict:
        """Run the complete Brooks strategy profitability analysis"""
        try:
            logger.info(f"Starting Brooks Higher Probability LONG Reversal Strategy Analysis using Zerodha data for user: {self.user_name}")
            
            # Get all Brooks strategy files
            brooks_files = self.get_brooks_files()
            
            if not brooks_files:
                logger.error("No Brooks strategy files found")
                return {}
            
            # Analyze each file
            all_results = []
            for file_path, scan_date in brooks_files:
                logger.info(f"Analyzing {os.path.basename(file_path)} - {scan_date.strftime('%Y-%m-%d %H:%M')}")
                result = self.analyze_brooks_file(file_path, scan_date)
                if result:
                    all_results.append(result)
            
            if not all_results:
                logger.error("No successful analyses")
                return {}
            
            # Calculate statistics
            logger.info("Calculating comprehensive Brooks strategy statistics")
            stats = self.calculate_brooks_statistics(all_results)
            
            # Create visualizations
            logger.info("Creating Brooks strategy visualizations")
            plot_files = self.create_brooks_visualizations(all_results, stats)
            
            # Export to Excel
            logger.info("Exporting Brooks strategy results to Excel")
            excel_file = self.export_brooks_excel(all_results, stats)
            
            # Generate HTML report
            logger.info("Generating Brooks strategy HTML report")
            html_file = self.generate_brooks_html_report(all_results, stats, plot_files, excel_file)
            
            # Print summary
            self.print_brooks_summary(stats, excel_file, html_file)
            
            logger.info("Brooks strategy analysis completed successfully")
            
            return {
                'stats': stats,
                'excel_file': excel_file,
                'html_file': html_file,
                'plot_files': plot_files,
                'total_files_analyzed': len(all_results)
            }
            
        except Exception as e:
            logger.error(f"Error in Brooks analysis: {e}")
            return {}
    
    def print_brooks_summary(self, stats: Dict, excel_file: str, html_file: str):
        """Print Brooks strategy analysis summary to console"""
        print("\n" + "="*80)
        print(f"BROOKS HIGHER PROBABILITY LONG REVERSAL STRATEGY ANALYSIS (ZERODHA DATA) - USER: {self.user_name}")
        print("="*80)
        
        overall = stats.get('overall', {})
        print(f"Analysis Period: {overall.get('date_range', {}).get('start', 'N/A')} to {overall.get('date_range', {}).get('end', 'N/A')}")
        print(f"Total Strategy Files: {overall.get('total_scans', 0)}")
        print(f"Total LONG Setups Analyzed: {overall.get('total_tickers_analyzed', 0):,}")
        print(f"Average Risk-Reward Ratio: {overall.get('average_risk_reward_ratio', 0):.2f}")
        print("-"*80)
        
        print("PERFORMANCE BY HOLDING PERIOD:")
        for period in self.holding_periods:
            if f'{period}_day' in stats:
                period_stats = stats[f'{period}_day']
                print(f"\n{period} Day{'s' if period > 1 else ''} Holding:")
                print(f"  Win Rate: {period_stats['win_rate']:.1f}% ({period_stats['profitable_trades']}/{period_stats['total_trades']} trades)")
                print(f"  Average Return: {period_stats['average_return']:.2f}%")
                print(f"  Stop Loss Hit Rate: {period_stats['stop_loss_rate']:.1f}% ({period_stats['stop_loss_hits']} hits)")
                print(f"  Target Hit Rate: {period_stats['target_hit_rate']:.1f}% ({period_stats['target_hits']} hits)")
                print(f"  Max Return: {period_stats['max_return']:.2f}%")
                print(f"  Min Return: {period_stats['min_return']:.2f}%")
                print(f"  Profit Factor: {period_stats['profit_factor']:.2f}")
        
        print("\n" + "-"*80)
        print("OUTPUT FILES:")
        print(f"Excel Report: {os.path.basename(excel_file)}")
        print(f"HTML Report: {os.path.basename(html_file)}")
        print(f"Results Directory: {self.results_dir}")
        print("="*80)


def main():
    """Main function"""
    try:
        # Create logs directory
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Brooks Higher Probability LONG Reversal Strategy Analysis using Zerodha API")
        parser.add_argument("--user", "-u", type=str, default="Sai", help="User whose API credentials to use (default: Sai)")
        parser.add_argument("--results-dir", "-d", type=str, help="Custom directory to save results")
        args = parser.parse_args()
        
        # Initialize analyzer with user credentials
        analyzer = BrooksStrategyZerodhaAnalyzer(user_name=args.user)
        
        # Set custom results directory if provided
        if args.results_dir:
            analyzer.results_dir = os.path.abspath(args.results_dir)
            os.makedirs(analyzer.results_dir, exist_ok=True)
            logger.info(f"Custom results directory set: {analyzer.results_dir}")
        
        # Run analysis
        results = analyzer.run_brooks_analysis()
        
        if results:
            print(f"\nBrooks strategy analysis using Zerodha data completed successfully!")
            print(f"Results saved to: {analyzer.results_dir}")
        else:
            print("Brooks strategy analysis failed. Check logs for details.")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())