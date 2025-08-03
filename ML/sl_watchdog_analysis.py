#!/usr/bin/env python
"""
SL Watchdog Transaction Analysis
================================
This script analyzes actual stop loss transactions from SL watchdog logs 
to evaluate the effectiveness of the ATR-based stop loss strategy.

Features:
- Parses SL watchdog logs for actual stop loss triggers
- Analyzes stop loss effectiveness (false stops vs saved losses)
- Calculates optimal ATR multipliers based on historical data
- Identifies patterns in stopped positions that later recovered
- Generates comprehensive report with actionable insights

Author: Claude Code Assistant
Created: 2025-05-31
"""

import os
import sys
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import logging
from typing import Dict, List, Tuple, Optional
import json
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from parent directory
try:
    from user_context_manager import get_context_manager, get_user_data_handler, UserCredentials
    from zerodha_handler import get_zerodha_handler
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SLWatchdogAnalyzer:
    """Analyze SL watchdog stop loss transactions"""
    
    def __init__(self, user_name="Sai", start_date="2025-05-22", end_date="2025-05-30"):
        """Initialize the analyzer"""
        self.user_name = user_name
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Paths
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.join(os.path.dirname(self.script_dir), "Daily")
        self.logs_dir = os.path.join(self.daily_dir, "logs", user_name)
        self.results_dir = os.path.join(self.script_dir, "results")
        
        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize data handler
        self.data_handler = self._initialize_data_handler()
        
        # ATR multiplier categories
        self.atr_categories = {
            'Low': {'threshold': 2.0, 'multiplier': 1.0},
            'Medium': {'threshold': 4.0, 'multiplier': 1.5},
            'High': {'threshold': float('inf'), 'multiplier': 2.0}
        }
        
        logger.info(f"Initialized SL Watchdog Analyzer for user: {user_name}")
        logger.info(f"Analysis period: {start_date} to {end_date}")
    
    def _initialize_data_handler(self):
        """Initialize Zerodha data handler"""
        try:
            if USER_CONTEXT_AVAILABLE:
                context_manager = get_context_manager()
                user_credentials = self._load_user_credentials()
                
                if user_credentials:
                    context_manager.set_current_user(self.user_name, user_credentials)
                    data_handler = get_user_data_handler()
                    
                    if data_handler and hasattr(data_handler, 'kite'):
                        logger.info(f"Successfully initialized Zerodha data handler for user: {self.user_name}")
                        return data_handler
            
            # Fallback
            logger.warning("User context not available, falling back to direct handler")
            from zerodha_handler import ZerodhaHandler
            return ZerodhaHandler()
            
        except Exception as e:
            logger.error(f"Failed to initialize data handler: {e}")
            return None
    
    def _load_user_credentials(self) -> Optional[UserCredentials]:
        """Load user credentials from config.ini"""
        try:
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.error(f"Config file not found: {config_path}")
                return None
            
            import configparser
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
            
            from collections import namedtuple
            UserCredentials = namedtuple('UserCredentials', ['name', 'api_key', 'api_secret', 'access_token'])
            
            return UserCredentials(
                name=self.user_name,
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token
            )
            
        except Exception as e:
            logger.error(f"Error loading user credentials: {e}")
            return None
    
    def parse_sl_logs(self) -> List[Dict]:
        """Parse stop loss transactions from log files"""
        sl_transactions = []
        
        try:
            # Find all SL watchdog log files
            log_pattern = os.path.join(self.logs_dir, f"SL_watchdog_{self.user_name}*.log")
            import glob
            log_files = glob.glob(log_pattern)
            
            if not log_files:
                logger.warning(f"No SL watchdog logs found for user {self.user_name}")
                return sl_transactions
            
            # Pattern to match stop loss triggers
            sl_pattern = re.compile(
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*ATR STOP LOSS TRIGGERED - (\w+): '
                r'Current Price ₹([\d.]+) fell below ATR Stop Loss ₹([\d.]+) '
                r'\((\w+) volatility, ([\d.]+)x ATR\)\. '
                r'(?:Queuing SELL order for ([\d]+) shares \((\d+)% of position\) )?'
                r'at ₹([\d.]+)'
            )
            
            for log_file in log_files:
                logger.info(f"Parsing log file: {log_file}")
                
                with open(log_file, 'r') as f:
                    for line in f:
                        if 'ATR STOP LOSS TRIGGERED' in line:
                            match = sl_pattern.search(line)
                            if match:
                                timestamp_str = match.group(1)
                                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                                
                                # Check if within date range
                                if self.start_date <= timestamp <= self.end_date + timedelta(days=1):
                                    transaction = {
                                        'timestamp': timestamp,
                                        'ticker': match.group(2),
                                        'trigger_price': float(match.group(3)),
                                        'stop_loss': float(match.group(4)),
                                        'volatility_category': match.group(5),
                                        'atr_multiplier': float(match.group(6)),
                                        'shares': int(match.group(7)) if match.group(7) else None,
                                        'position_percent': int(match.group(8)) if match.group(8) else 100,
                                        'sell_price': float(match.group(9))
                                    }
                                    sl_transactions.append(transaction)
            
            logger.info(f"Found {len(sl_transactions)} stop loss transactions")
            return sl_transactions
            
        except Exception as e:
            logger.error(f"Error parsing SL logs: {e}")
            return sl_transactions
    
    def get_price_after_sl(self, ticker: str, sl_date: datetime, days_after: int = 5) -> Dict:
        """Get price movement after stop loss was triggered"""
        try:
            if not self.data_handler:
                return {'data_available': False, 'error': 'No data handler'}
            
            # Fetch historical data
            from_date = sl_date
            to_date = sl_date + timedelta(days=days_after + 5)  # Extra buffer for weekends
            
            historical_data = self.data_handler.fetch_historical_data(
                ticker,
                interval="day",
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d')
            )
            
            if not historical_data or len(historical_data) < 2:
                return {'data_available': False, 'error': 'Insufficient data'}
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Get data after SL date
            post_sl_data = df[df['date'] > sl_date].head(days_after)
            
            if post_sl_data.empty:
                return {'data_available': False, 'error': 'No data after SL date'}
            
            # Get SL day data
            sl_day_data = df[df['date'].dt.date == sl_date.date()]
            if sl_day_data.empty:
                # Use the last available price before SL date
                sl_day_data = df[df['date'] < sl_date].tail(1)
            
            if sl_day_data.empty:
                return {'data_available': False, 'error': 'No SL day data'}
            
            sl_price = sl_day_data.iloc[0]['close']
            
            result = {
                'data_available': True,
                'sl_price': sl_price,
                'prices_after': [],
                'max_price_after': post_sl_data['high'].max(),
                'min_price_after': post_sl_data['low'].min(),
                'close_after_days': {}
            }
            
            # Daily prices after SL
            for i, (_, row) in enumerate(post_sl_data.iterrows(), 1):
                result['prices_after'].append({
                    'day': i,
                    'date': row['date'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'return_pct': ((row['close'] - sl_price) / sl_price) * 100
                })
                result[f'close_after_days'][i] = row['close']
            
            # Calculate recovery metrics
            result['max_recovery_pct'] = ((result['max_price_after'] - sl_price) / sl_price) * 100
            result['max_drawdown_pct'] = ((result['min_price_after'] - sl_price) / sl_price) * 100
            
            # Check if stop loss saved money
            final_close = post_sl_data.iloc[-1]['close'] if len(post_sl_data) > 0 else sl_price
            result['final_return_pct'] = ((final_close - sl_price) / sl_price) * 100
            result['sl_effective'] = result['final_return_pct'] < 0  # SL saved money if price went lower
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting price data for {ticker}: {e}")
            return {'data_available': False, 'error': str(e)}
    
    def analyze_sl_effectiveness(self, sl_transactions: List[Dict]) -> Dict:
        """Analyze effectiveness of stop losses"""
        analysis = {
            'total_sl_hits': len(sl_transactions),
            'unique_tickers': len(set(t['ticker'] for t in sl_transactions)),
            'by_volatility': {},
            'by_ticker': {},
            'effectiveness_stats': {
                'total_analyzed': 0,
                'effective_stops': 0,
                'false_stops': 0,
                'saved_losses': [],
                'unnecessary_exits': []
            },
            'recovery_analysis': {
                'recovered_in_1_day': 0,
                'recovered_in_3_days': 0,
                'recovered_in_5_days': 0,
                'never_recovered': 0
            }
        }
        
        # Group by volatility category
        for category in ['Low', 'Medium', 'High']:
            category_txns = [t for t in sl_transactions if t['volatility_category'] == category]
            analysis['by_volatility'][category] = {
                'count': len(category_txns),
                'percentage': (len(category_txns) / len(sl_transactions) * 100) if sl_transactions else 0,
                'tickers': list(set(t['ticker'] for t in category_txns))
            }
        
        # Analyze each transaction
        for txn in sl_transactions:
            ticker = txn['ticker']
            
            # Get price movement after SL
            price_after = self.get_price_after_sl(ticker, txn['timestamp'])
            
            if price_after.get('data_available'):
                analysis['effectiveness_stats']['total_analyzed'] += 1
                
                # Store detailed analysis
                txn_analysis = {
                    'ticker': ticker,
                    'sl_date': txn['timestamp'],
                    'sl_price': txn['trigger_price'],
                    'volatility': txn['volatility_category'],
                    'atr_multiplier': txn['atr_multiplier'],
                    'price_after': price_after
                }
                
                # Check effectiveness
                if price_after['sl_effective']:
                    analysis['effectiveness_stats']['effective_stops'] += 1
                    saved_amount = abs(price_after['final_return_pct'])
                    analysis['effectiveness_stats']['saved_losses'].append({
                        'ticker': ticker,
                        'saved_pct': saved_amount,
                        'sl_date': txn['timestamp'],
                        'final_price': price_after['close_after_days'].get(5, txn['trigger_price'])
                    })
                else:
                    analysis['effectiveness_stats']['false_stops'] += 1
                    analysis['effectiveness_stats']['unnecessary_exits'].append({
                        'ticker': ticker,
                        'recovery_pct': price_after['max_recovery_pct'],
                        'sl_date': txn['timestamp'],
                        'days_to_recover': self._days_to_recover(price_after, txn['trigger_price'])
                    })
                
                # Recovery analysis
                recovered = False
                for day in [1, 3, 5]:
                    if day in price_after['close_after_days']:
                        if price_after['close_after_days'][day] > txn['trigger_price'] and not recovered:
                            analysis['recovery_analysis'][f'recovered_in_{day}_day{"s" if day > 1 else ""}'] += 1
                            recovered = True
                
                if not recovered and price_after.get('final_return_pct', 0) < 0:
                    analysis['recovery_analysis']['never_recovered'] += 1
                
                # By ticker analysis
                if ticker not in analysis['by_ticker']:
                    analysis['by_ticker'][ticker] = {
                        'sl_count': 0,
                        'effective': 0,
                        'false_stops': 0,
                        'avg_recovery': 0,
                        'transactions': []
                    }
                
                analysis['by_ticker'][ticker]['sl_count'] += 1
                analysis['by_ticker'][ticker]['transactions'].append({
                    'date': txn['timestamp'],
                    'effective': price_after['sl_effective'],
                    'recovery_pct': price_after.get('max_recovery_pct', 0)
                })
                
                if price_after['sl_effective']:
                    analysis['by_ticker'][ticker]['effective'] += 1
                else:
                    analysis['by_ticker'][ticker]['false_stops'] += 1
        
        # Calculate summary statistics
        if analysis['effectiveness_stats']['total_analyzed'] > 0:
            analysis['effectiveness_stats']['effectiveness_rate'] = (
                analysis['effectiveness_stats']['effective_stops'] / 
                analysis['effectiveness_stats']['total_analyzed'] * 100
            )
            
            if analysis['effectiveness_stats']['saved_losses']:
                analysis['effectiveness_stats']['avg_saved_loss'] = np.mean(
                    [s['saved_pct'] for s in analysis['effectiveness_stats']['saved_losses']]
                )
            
            if analysis['effectiveness_stats']['unnecessary_exits']:
                analysis['effectiveness_stats']['avg_recovery_missed'] = np.mean(
                    [u['recovery_pct'] for u in analysis['effectiveness_stats']['unnecessary_exits']]
                )
        
        return analysis
    
    def _days_to_recover(self, price_after: Dict, trigger_price: float) -> Optional[int]:
        """Calculate days to recover to trigger price"""
        for price_data in price_after.get('prices_after', []):
            if price_data['high'] >= trigger_price:
                return price_data['day']
        return None
    
    def generate_report(self, sl_transactions: List[Dict], analysis: Dict) -> str:
        """Generate comprehensive report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.results_dir, f"sl_watchdog_analysis_{self.user_name}_{timestamp}.txt")
        
        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"SL WATCHDOG TRANSACTION ANALYSIS REPORT\n")
            f.write(f"User: {self.user_name}\n")
            f.write(f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Summary Statistics
            f.write("SUMMARY STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Stop Losses Triggered: {analysis['total_sl_hits']}\n")
            f.write(f"Unique Tickers: {analysis['unique_tickers']}\n")
            f.write(f"Total Analyzed: {analysis['effectiveness_stats']['total_analyzed']}\n")
            f.write(f"Effective Stops: {analysis['effectiveness_stats']['effective_stops']}\n")
            f.write(f"False Stops: {analysis['effectiveness_stats']['false_stops']}\n")
            
            if 'effectiveness_rate' in analysis['effectiveness_stats']:
                f.write(f"Effectiveness Rate: {analysis['effectiveness_stats']['effectiveness_rate']:.1f}%\n")
            
            if 'avg_saved_loss' in analysis['effectiveness_stats']:
                f.write(f"Average Saved Loss: {analysis['effectiveness_stats']['avg_saved_loss']:.2f}%\n")
            
            if 'avg_recovery_missed' in analysis['effectiveness_stats']:
                f.write(f"Average Recovery Missed: {analysis['effectiveness_stats']['avg_recovery_missed']:.2f}%\n")
            
            f.write("\n")
            
            # Transaction Details
            f.write("STOP LOSS TRANSACTIONS\n")
            f.write("-" * 40 + "\n")
            for txn in sl_transactions:
                f.write(f"{txn['timestamp'].strftime('%Y-%m-%d %H:%M')} - {txn['ticker']}: ")
                f.write(f"₹{txn['trigger_price']:.2f} (SL: ₹{txn['stop_loss']:.2f}) ")
                f.write(f"[{txn['volatility_category']} {txn['atr_multiplier']}x]\n")
            
            f.write("\n")
            
            # By Volatility Category
            f.write("STOP LOSSES BY VOLATILITY CATEGORY\n")
            f.write("-" * 40 + "\n")
            for category, stats in analysis['by_volatility'].items():
                f.write(f"{category}: {stats['count']} ({stats['percentage']:.1f}%)\n")
                if stats['tickers']:
                    f.write(f"  Tickers: {', '.join(stats['tickers'][:5])}")
                    if len(stats['tickers']) > 5:
                        f.write(f" ... and {len(stats['tickers']) - 5} more")
                    f.write("\n")
            
            f.write("\n")
            
            # Recovery Analysis
            f.write("RECOVERY ANALYSIS\n")
            f.write("-" * 40 + "\n")
            for period, count in analysis['recovery_analysis'].items():
                f.write(f"{period.replace('_', ' ').title()}: {count}\n")
            
            f.write("\n")
            
            # Top False Stops
            if analysis['effectiveness_stats']['unnecessary_exits']:
                f.write("TOP FALSE STOPS (Recovered Quickly)\n")
                f.write("-" * 40 + "\n")
                false_stops = sorted(
                    analysis['effectiveness_stats']['unnecessary_exits'], 
                    key=lambda x: x['recovery_pct'], 
                    reverse=True
                )[:5]
                
                for stop in false_stops:
                    f.write(f"{stop['ticker']} ({stop['sl_date'].strftime('%m/%d')}): ")
                    f.write(f"Recovered {stop['recovery_pct']:.2f}% ")
                    if stop['days_to_recover']:
                        f.write(f"in {stop['days_to_recover']} day(s)\n")
                    else:
                        f.write("(no full recovery in 5 days)\n")
                
                f.write("\n")
            
            # Top Effective Stops
            if analysis['effectiveness_stats']['saved_losses']:
                f.write("TOP EFFECTIVE STOPS (Saved Losses)\n")
                f.write("-" * 40 + "\n")
                effective_stops = sorted(
                    analysis['effectiveness_stats']['saved_losses'], 
                    key=lambda x: x['saved_pct'], 
                    reverse=True
                )[:5]
                
                for stop in effective_stops:
                    f.write(f"{stop['ticker']} ({stop['sl_date'].strftime('%m/%d')}): ")
                    f.write(f"Saved {stop['saved_pct']:.2f}% loss\n")
                
                f.write("\n")
            
            # By Ticker Analysis
            if analysis['by_ticker']:
                f.write("ANALYSIS BY TICKER\n")
                f.write("-" * 40 + "\n")
                
                # Sort by number of SL hits
                sorted_tickers = sorted(
                    analysis['by_ticker'].items(), 
                    key=lambda x: x[1]['sl_count'], 
                    reverse=True
                )[:10]
                
                for ticker, stats in sorted_tickers:
                    eff_rate = (stats['effective'] / stats['sl_count'] * 100) if stats['sl_count'] > 0 else 0
                    f.write(f"{ticker}: {stats['sl_count']} SL hits, ")
                    f.write(f"{eff_rate:.0f}% effective ")
                    f.write(f"({stats['effective']} saved, {stats['false_stops']} false)\n")
            
            f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 40 + "\n")
            
            effectiveness_rate = analysis['effectiveness_stats'].get('effectiveness_rate', 0)
            
            if effectiveness_rate < 40:
                f.write("• CRITICAL: Stop losses are too tight - only {:.0f}% effective\n".format(effectiveness_rate))
                f.write("• Consider increasing ATR multipliers by 0.5x across all categories\n")
            elif effectiveness_rate < 60:
                f.write("• Stop loss effectiveness is moderate ({:.0f}%)\n".format(effectiveness_rate))
                f.write("• Review individual volatility categories for optimization\n")
            else:
                f.write("• Stop loss strategy is working well ({:.0f}% effective)\n".format(effectiveness_rate))
            
            # Volatility-specific recommendations
            for category, stats in analysis['by_volatility'].items():
                if stats['count'] > 0:
                    f.write(f"\n{category} Volatility ({stats['count']} stops):\n")
                    current_mult = self.atr_categories[category]['multiplier']
                    
                    # Get effectiveness for this category
                    cat_effective = sum(1 for t in sl_transactions 
                                      if t['volatility_category'] == category 
                                      and any(s['ticker'] == t['ticker'] and 
                                            s['sl_date'] == t['timestamp'] 
                                            for s in analysis['effectiveness_stats']['saved_losses']))
                    
                    cat_rate = (cat_effective / stats['count'] * 100) if stats['count'] > 0 else 0
                    
                    if cat_rate < 40:
                        f.write(f"  • Current {current_mult}x too tight ({cat_rate:.0f}% effective)\n")
                        f.write(f"  • Recommend: {current_mult + 0.5}x ATR\n")
                    else:
                        f.write(f"  • Current {current_mult}x is appropriate ({cat_rate:.0f}% effective)\n")
            
            # Recovery-based recommendations
            recovery = analysis['recovery_analysis']
            quick_recovery = recovery.get('recovered_in_1_day', 0) + recovery.get('recovered_in_3_days', 0)
            total_analyzed = analysis['effectiveness_stats']['total_analyzed']
            
            if total_analyzed > 0 and quick_recovery / total_analyzed > 0.5:
                f.write("\n• HIGH QUICK RECOVERY RATE: {:.0f}% recover within 3 days\n".format(
                    quick_recovery / total_analyzed * 100))
                f.write("• Consider implementing time-based stops or trailing stops\n")
                f.write("• Avoid selling on minor dips - use wider initial stops\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        logger.info(f"Report generated: {report_file}")
        return report_file
    
    def create_visualizations(self, sl_transactions: List[Dict], analysis: Dict) -> List[str]:
        """Create visualization charts"""
        chart_files = []
        
        try:
            # Set style
            plt.style.use('seaborn-v0_8')
            
            # Create figure with subplots
            fig = plt.figure(figsize=(15, 10))
            
            # 1. Stop Losses by Date
            ax1 = plt.subplot(2, 3, 1)
            dates = [t['timestamp'].date() for t in sl_transactions]
            date_counts = pd.Series(dates).value_counts().sort_index()
            ax1.bar(date_counts.index, date_counts.values, color='skyblue', edgecolor='black')
            ax1.set_title('Stop Losses by Date')
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Number of SL Hits')
            plt.xticks(rotation=45)
            
            # 2. Effectiveness by Volatility Category
            ax2 = plt.subplot(2, 3, 2)
            categories = list(analysis['by_volatility'].keys())
            counts = [analysis['by_volatility'][cat]['count'] for cat in categories]
            colors = ['green', 'yellow', 'red']
            ax2.pie(counts, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
            ax2.set_title('Stop Losses by Volatility Category')
            
            # 3. Recovery Timeline
            ax3 = plt.subplot(2, 3, 3)
            recovery_data = analysis['recovery_analysis']
            recovery_labels = ['1 Day', '3 Days', '5 Days', 'Never']
            recovery_values = [
                recovery_data.get('recovered_in_1_day', 0),
                recovery_data.get('recovered_in_3_days', 0) - recovery_data.get('recovered_in_1_day', 0),
                recovery_data.get('recovered_in_5_days', 0) - recovery_data.get('recovered_in_3_days', 0),
                recovery_data.get('never_recovered', 0)
            ]
            ax3.bar(recovery_labels, recovery_values, color=['darkgreen', 'green', 'orange', 'red'])
            ax3.set_title('Price Recovery After Stop Loss')
            ax3.set_ylabel('Number of Stocks')
            
            # 4. Effectiveness Rate
            ax4 = plt.subplot(2, 3, 4)
            effectiveness = analysis['effectiveness_stats']
            if effectiveness['total_analyzed'] > 0:
                sizes = [effectiveness['effective_stops'], effectiveness['false_stops']]
                labels = [f"Effective\n({effectiveness['effective_stops']})", 
                         f"False Stops\n({effectiveness['false_stops']})"]
                colors = ['green', 'red']
                ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax4.set_title(f"Stop Loss Effectiveness (n={effectiveness['total_analyzed']})")
            
            # 5. Top Tickers by SL Count
            ax5 = plt.subplot(2, 3, 5)
            if analysis['by_ticker']:
                sorted_tickers = sorted(
                    analysis['by_ticker'].items(), 
                    key=lambda x: x[1]['sl_count'], 
                    reverse=True
                )[:10]
                
                tickers = [t[0] for t in sorted_tickers]
                counts = [t[1]['sl_count'] for t in sorted_tickers]
                
                ax5.barh(tickers, counts, color='coral')
                ax5.set_title('Top 10 Tickers by Stop Loss Count')
                ax5.set_xlabel('Number of Stop Losses')
            
            # 6. Average Saved vs Missed
            ax6 = plt.subplot(2, 3, 6)
            if 'avg_saved_loss' in effectiveness or 'avg_recovery_missed' in effectiveness:
                metrics = ['Avg Saved Loss', 'Avg Recovery Missed']
                values = [
                    effectiveness.get('avg_saved_loss', 0),
                    effectiveness.get('avg_recovery_missed', 0)
                ]
                colors = ['green', 'orange']
                bars = ax6.bar(metrics, values, color=colors)
                ax6.set_title('Impact Analysis')
                ax6.set_ylabel('Percentage (%)')
                
                # Add value labels
                for bar, value in zip(bars, values):
                    ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                           f'{value:.1f}%', ha='center', va='bottom')
            
            plt.tight_layout()
            chart_file = os.path.join(self.results_dir, f"sl_watchdog_analysis_{self.user_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            chart_files.append(chart_file)
            
            logger.info(f"Created {len(chart_files)} visualization charts")
            
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")
        
        return chart_files
    
    def export_to_excel(self, sl_transactions: List[Dict], analysis: Dict) -> str:
        """Export detailed analysis to Excel"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file = os.path.join(self.results_dir, f"sl_watchdog_analysis_{self.user_name}_{timestamp}.xlsx")
        
        try:
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 1. Transaction Details
                if sl_transactions:
                    txn_df = pd.DataFrame(sl_transactions)
                    txn_df['timestamp'] = txn_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    txn_df.to_excel(writer, sheet_name='SL_Transactions', index=False)
                
                # 2. Effectiveness Summary
                summary_data = {
                    'Metric': [
                        'Total Stop Losses',
                        'Unique Tickers',
                        'Effective Stops',
                        'False Stops',
                        'Effectiveness Rate (%)',
                        'Avg Saved Loss (%)',
                        'Avg Recovery Missed (%)'
                    ],
                    'Value': [
                        analysis['total_sl_hits'],
                        analysis['unique_tickers'],
                        analysis['effectiveness_stats']['effective_stops'],
                        analysis['effectiveness_stats']['false_stops'],
                        analysis['effectiveness_stats'].get('effectiveness_rate', 0),
                        analysis['effectiveness_stats'].get('avg_saved_loss', 0),
                        analysis['effectiveness_stats'].get('avg_recovery_missed', 0)
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # 3. By Ticker Analysis
                if analysis['by_ticker']:
                    ticker_data = []
                    for ticker, stats in analysis['by_ticker'].items():
                        ticker_data.append({
                            'Ticker': ticker,
                            'SL Count': stats['sl_count'],
                            'Effective': stats['effective'],
                            'False Stops': stats['false_stops'],
                            'Effectiveness (%)': (stats['effective'] / stats['sl_count'] * 100) if stats['sl_count'] > 0 else 0
                        })
                    
                    ticker_df = pd.DataFrame(ticker_data)
                    ticker_df.sort_values('SL Count', ascending=False, inplace=True)
                    ticker_df.to_excel(writer, sheet_name='By_Ticker', index=False)
                
                # 4. Detailed Analysis
                if analysis['effectiveness_stats']['saved_losses']:
                    saved_df = pd.DataFrame(analysis['effectiveness_stats']['saved_losses'])
                    saved_df['sl_date'] = saved_df['sl_date'].dt.strftime('%Y-%m-%d')
                    saved_df.to_excel(writer, sheet_name='Effective_Stops', index=False)
                
                if analysis['effectiveness_stats']['unnecessary_exits']:
                    false_df = pd.DataFrame(analysis['effectiveness_stats']['unnecessary_exits'])
                    false_df['sl_date'] = false_df['sl_date'].dt.strftime('%Y-%m-%d')
                    false_df.to_excel(writer, sheet_name='False_Stops', index=False)
            
            logger.info(f"Excel report exported: {excel_file}")
            return excel_file
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return ""
    
    def run_analysis(self):
        """Run complete stop loss analysis"""
        logger.info("Starting SL watchdog analysis...")
        
        # 1. Parse stop loss transactions
        sl_transactions = self.parse_sl_logs()
        
        if not sl_transactions:
            logger.warning("No stop loss transactions found in the specified period")
            print("\nNo stop loss transactions found in the logs.")
            print("Please check:")
            print(f"1. Log directory: {self.logs_dir}")
            print(f"2. Date range: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
            return
        
        # 2. Analyze effectiveness
        analysis = self.analyze_sl_effectiveness(sl_transactions)
        
        # 3. Generate reports
        text_report = self.generate_report(sl_transactions, analysis)
        excel_report = self.export_to_excel(sl_transactions, analysis)
        
        # 4. Create visualizations
        charts = self.create_visualizations(sl_transactions, analysis)
        
        # Print summary
        print("\n" + "="*60)
        print(f"SL WATCHDOG ANALYSIS COMPLETE")
        print(f"User: {self.user_name}")
        print(f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print("="*60)
        print(f"Total Stop Losses: {analysis['total_sl_hits']}")
        print(f"Unique Tickers: {analysis['unique_tickers']}")
        print(f"Effectiveness Rate: {analysis['effectiveness_stats'].get('effectiveness_rate', 0):.1f}%")
        print(f"Average Saved Loss: {analysis['effectiveness_stats'].get('avg_saved_loss', 0):.2f}%")
        print(f"Average Recovery Missed: {analysis['effectiveness_stats'].get('avg_recovery_missed', 0):.2f}%")
        print("-"*60)
        
        # Print stop loss transactions
        print("\nSTOP LOSS TRANSACTIONS:")
        for txn in sl_transactions[:10]:  # Show first 10
            print(f"{txn['timestamp'].strftime('%m/%d %H:%M')} - {txn['ticker']}: ₹{txn['trigger_price']:.2f} [{txn['volatility_category']}]")
        
        if len(sl_transactions) > 10:
            print(f"... and {len(sl_transactions) - 10} more")
        
        print("-"*60)
        print(f"Reports generated in: {self.results_dir}")
        print("="*60)
        
        return {
            'transactions': sl_transactions,
            'analysis': analysis,
            'reports': {
                'text': text_report,
                'excel': excel_report,
                'charts': charts
            }
        }


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Analyze SL watchdog stop loss effectiveness")
    parser.add_argument("--user", "-u", type=str, default="Sai", help="User name (default: Sai)")
    parser.add_argument("--start-date", "-s", type=str, default="2025-05-22", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", "-e", type=str, default="2025-05-30", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    try:
        analyzer = SLWatchdogAnalyzer(
            user_name=args.user,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        results = analyzer.run_analysis()
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())