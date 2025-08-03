"""
Winner Performance Analyzer

This script analyzes trading performance data from Daily/results Excel files to:
1. Aggregate ticker data across all reports
2. Rank tickers by profitability using Zerodha OHLC data
3. Analyze winner characteristics (rate of change, pullbacks, patterns)
4. Generate insights for better future winner identification

Usage:
    python winner_performance_analyzer.py [--days 30] [--top-n 20]
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
import json
from collections import defaultdict
import configparser
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ML/logs/winner_performance_analyzer.log'),
        logging.StreamHandler()
    ]
)

def load_config(user_name="Sai"):
    """Load configuration from config.ini file"""
    config_path = 'Daily/config.ini'
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

class WinnerPerformanceAnalyzer:
    """Analyzes historical trading performance to identify winner characteristics"""
    
    def __init__(self, user_name: str = "Sai", use_offline: bool = False):
        """Initialize analyzer with configuration"""
        self.user_name = user_name
        self.use_offline = use_offline
        self.logger = logging.getLogger(__name__)
        
        if not use_offline:
            self.config = load_config(user_name)
            
            # Initialize Kite Connect
            credential_section = f'API_CREDENTIALS_{user_name}'
            try:
                self.api_key = self.config.get(credential_section, 'api_key')
                self.access_token = self.config.get(credential_section, 'access_token')
                
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.access_token)
                
                # Get instrument list with timeout
                self.logger.info("Fetching instrument list from Kite...")
                self.instruments = self.kite.instruments("NSE")
                self.instrument_lookup = {inst['tradingsymbol']: inst['instrument_token'] 
                                        for inst in self.instruments}
                self.logger.info(f"Loaded {len(self.instruments)} instruments")
            except Exception as e:
                self.logger.error(f"Error initializing Kite Connect: {e}")
                self.logger.info("Switching to offline mode...")
                self.use_offline = True
        
        if self.use_offline:
            self.logger.info("Running in offline mode - will use local CSV data")
        
        # Results directory
        self.results_dir = "Daily/results"
        
        # Analysis parameters
        self.lookback_days = 30
        self.top_n_winners = 20
        
        # Data storage
        self.ticker_data = defaultdict(list)
        self.ticker_performance = {}
        self.winner_characteristics = {}
        
    def load_excel_reports(self) -> pd.DataFrame:
        """Load all Excel reports from the results directory"""
        self.logger.info(f"Loading Excel reports from {self.results_dir}")
        
        all_data = []
        
        # Get all Excel files
        excel_files = [f for f in os.listdir(self.results_dir) if f.endswith('.xlsx')]
        excel_files.sort()  # Sort by date
        
        for file in excel_files:
            try:
                # Extract date from filename
                date_str = file.split('_')[2]  # StrategyB_Report_YYYYMMDD_HHMMSS.xlsx
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                # Load Excel file
                df = pd.read_excel(os.path.join(self.results_dir, file))
                df['scan_date'] = file_date
                df['scan_file'] = file
                
                all_data.append(df)
                
            except Exception as e:
                self.logger.warning(f"Error loading {file}: {e}")
                continue
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Loaded {len(all_data)} files with {len(combined_df)} total entries")
            return combined_df
        else:
            self.logger.error("No data loaded from Excel files")
            return pd.DataFrame()
    
    def get_price_data(self, ticker: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Get historical price data for a ticker"""
        if self.use_offline:
            # Try to load from local CSV files
            csv_path = f"ML/data/ohlc_data/daily/{ticker}_day.csv"
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # Remove timezone info to avoid comparison issues
                    df['date'] = df['date'].dt.tz_localize(None)
                    df.set_index('date', inplace=True)
                    
                    # Ensure start_date and end_date are timezone-naive
                    start_date = pd.to_datetime(start_date).tz_localize(None)
                    end_date = pd.to_datetime(end_date).tz_localize(None)
                    
                    # Filter by date range
                    mask = (df.index >= start_date) & (df.index <= end_date)
                    df = df.loc[mask]
                    
                    if len(df) > 0:
                        return df
                except Exception as e:
                    self.logger.warning(f"Error reading CSV for {ticker}: {e}")
            else:
                self.logger.debug(f"No local data found for {ticker}")
            return None
        
        try:
            # Get instrument token
            instrument_token = self.instrument_lookup.get(ticker)
            
            if not instrument_token:
                self.logger.warning(f"Instrument token not found for {ticker}")
                return None
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval="day"
            )
            
            if historical_data:
                df = pd.DataFrame(historical_data)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                return df
            
        except Exception as e:
            self.logger.warning(f"Error fetching data for {ticker}: {e}")
            
        return None
    
    def calculate_performance_metrics(self, ticker: str, entry_date: datetime, 
                                    entry_price: float, stop_loss: float,
                                    target1: float, target2: float) -> Dict:
        """Calculate actual performance metrics for a ticker"""
        metrics = {
            'ticker': ticker,
            'entry_date': entry_date,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'outcome': 'unknown',
            'exit_price': None,
            'exit_date': None,
            'pnl_percent': 0,
            'holding_days': 0,
            'max_favorable': 0,
            'max_adverse': 0,
            'hit_target1': False,
            'hit_target2': False,
            'hit_stoploss': False,
            'avg_pullback': 0,
            'volatility': 0,
            'momentum_score': 0,
            'volume_surge': 0
        }
        
        try:
            # Get price data from entry date
            end_date = min(entry_date + timedelta(days=30), datetime.now())
            price_data = self.get_price_data(ticker, entry_date, end_date)
            
            if price_data is None or len(price_data) < 2:
                return metrics
            
            # Find entry date data
            entry_idx = None
            for i, (date, row) in enumerate(price_data.iterrows()):
                if date.date() >= entry_date.date():
                    entry_idx = i
                    break
            
            if entry_idx is None:
                return metrics
            
            # Analyze price movement after entry
            post_entry_data = price_data.iloc[entry_idx:]
            
            if len(post_entry_data) == 0:
                return metrics
            
            # Track price movement
            for i, (date, row) in enumerate(post_entry_data.iterrows()):
                current_price = row['close']
                
                # Update max favorable/adverse excursion
                price_move = ((current_price - entry_price) / entry_price) * 100
                metrics['max_favorable'] = max(metrics['max_favorable'], price_move)
                metrics['max_adverse'] = min(metrics['max_adverse'], price_move)
                
                # Check exit conditions
                if row['low'] <= stop_loss:
                    metrics['hit_stoploss'] = True
                    metrics['outcome'] = 'stoploss'
                    metrics['exit_price'] = stop_loss
                    metrics['exit_date'] = date
                    metrics['pnl_percent'] = ((stop_loss - entry_price) / entry_price) * 100
                    metrics['holding_days'] = i + 1
                    break
                    
                elif row['high'] >= target2:
                    metrics['hit_target2'] = True
                    metrics['hit_target1'] = True
                    metrics['outcome'] = 'target2'
                    metrics['exit_price'] = target2
                    metrics['exit_date'] = date
                    metrics['pnl_percent'] = ((target2 - entry_price) / entry_price) * 100
                    metrics['holding_days'] = i + 1
                    break
                    
                elif row['high'] >= target1 and not metrics['hit_target1']:
                    metrics['hit_target1'] = True
                    if i == len(post_entry_data) - 1:  # Last day
                        metrics['outcome'] = 'target1'
                        metrics['exit_price'] = target1
                        metrics['exit_date'] = date
                        metrics['pnl_percent'] = ((target1 - entry_price) / entry_price) * 100
                        metrics['holding_days'] = i + 1
            
            # If no exit, use last available price
            if metrics['outcome'] == 'unknown':
                last_row = post_entry_data.iloc[-1]
                metrics['outcome'] = 'open'
                metrics['exit_price'] = last_row['close']
                metrics['exit_date'] = post_entry_data.index[-1]
                metrics['pnl_percent'] = ((last_row['close'] - entry_price) / entry_price) * 100
                metrics['holding_days'] = len(post_entry_data)
            
            # Calculate additional metrics
            if len(price_data) > 5:
                # Pre-entry momentum (5 days before entry)
                pre_entry_start = max(0, entry_idx - 5)
                pre_entry_data = price_data.iloc[pre_entry_start:entry_idx]
                if len(pre_entry_data) > 1:
                    pre_entry_return = ((pre_entry_data.iloc[-1]['close'] - pre_entry_data.iloc[0]['close']) / 
                                      pre_entry_data.iloc[0]['close']) * 100
                    metrics['momentum_score'] = pre_entry_return
                
                # Volatility (ATR as percentage of price)
                price_data['tr'] = pd.DataFrame({
                    'hl': price_data['high'] - price_data['low'],
                    'hc': abs(price_data['high'] - price_data['close'].shift(1)),
                    'lc': abs(price_data['low'] - price_data['close'].shift(1))
                }).max(axis=1)
                
                atr = price_data['tr'].rolling(window=14).mean().iloc[-1]
                metrics['volatility'] = (atr / entry_price) * 100
                
                # Volume surge (current vs 20-day average)
                if 'volume' in price_data.columns:
                    avg_volume = price_data['volume'].rolling(window=20).mean()
                    if entry_idx < len(avg_volume) and avg_volume.iloc[entry_idx] > 0:
                        metrics['volume_surge'] = price_data['volume'].iloc[entry_idx] / avg_volume.iloc[entry_idx]
                
                # Average pullback calculation
                if metrics['outcome'] in ['target1', 'target2', 'open'] and metrics['pnl_percent'] > 0:
                    # Calculate pullbacks during winning trade
                    pullbacks = []
                    peak = entry_price
                    
                    for _, row in post_entry_data.iterrows():
                        if row['high'] > peak:
                            peak = row['high']
                        pullback = ((peak - row['low']) / peak) * 100
                        if pullback > 0.5:  # Meaningful pullback
                            pullbacks.append(pullback)
                    
                    if pullbacks:
                        metrics['avg_pullback'] = np.mean(pullbacks)
            
        except Exception as e:
            self.logger.warning(f"Error calculating metrics for {ticker}: {e}")
        
        return metrics
    
    def analyze_ticker_performance(self, df: pd.DataFrame):
        """Analyze performance for all tickers in the dataset"""
        self.logger.info("Analyzing ticker performance...")
        
        # Group by ticker
        for _, row in df.iterrows():
            ticker = row['Ticker']
            entry_date = row['scan_date']
            
            # Calculate performance
            metrics = self.calculate_performance_metrics(
                ticker=ticker,
                entry_date=entry_date,
                entry_price=row['Entry_Price'],
                stop_loss=row['Stop_Loss'],
                target1=row['Target1'],
                target2=row['Target2']
            )
            
            # Add scan metadata
            metrics['score'] = row['Score']
            metrics['pattern'] = row['Pattern']
            metrics['volume_ratio_scan'] = row['Volume_Ratio']
            metrics['momentum_5d_scan'] = row['Momentum_5D']
            metrics['atr_scan'] = row['ATR']
            metrics['conditions_met'] = row['Conditions_Met']
            
            # Store in ticker data
            self.ticker_data[ticker].append(metrics)
        
        self.logger.info(f"Analyzed {len(self.ticker_data)} unique tickers")
    
    def aggregate_ticker_statistics(self):
        """Aggregate statistics for each ticker"""
        self.logger.info("Aggregating ticker statistics...")
        
        for ticker, trades in self.ticker_data.items():
            if not trades:
                continue
            
            # Calculate aggregate metrics
            total_trades = len(trades)
            winning_trades = [t for t in trades if t['pnl_percent'] > 0]
            losing_trades = [t for t in trades if t['pnl_percent'] < 0]
            
            # Performance metrics
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            avg_win = np.mean([t['pnl_percent'] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t['pnl_percent'] for t in losing_trades]) if losing_trades else 0
            
            # Calculate expectancy
            expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
            
            # Target achievement rates
            target1_rate = sum(1 for t in trades if t['hit_target1']) / total_trades
            target2_rate = sum(1 for t in trades if t['hit_target2']) / total_trades
            stoploss_rate = sum(1 for t in trades if t['hit_stoploss']) / total_trades
            
            # Average characteristics of winning trades
            if winning_trades:
                avg_win_momentum = np.mean([t['momentum_score'] for t in winning_trades])
                avg_win_volume = np.mean([t['volume_surge'] for t in winning_trades if t['volume_surge'] > 0])
                avg_win_pullback = np.mean([t['avg_pullback'] for t in winning_trades if t['avg_pullback'] > 0])
                avg_win_holding = np.mean([t['holding_days'] for t in winning_trades])
                avg_win_volatility = np.mean([t['volatility'] for t in winning_trades])
            else:
                avg_win_momentum = avg_win_volume = avg_win_pullback = avg_win_holding = avg_win_volatility = 0
            
            # Score distribution
            score_dist = defaultdict(int)
            for t in trades:
                score_dist[t['score']] += 1
            
            # Store aggregated data
            self.ticker_performance[ticker] = {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_win_percent': avg_win,
                'avg_loss_percent': avg_loss,
                'expectancy': expectancy,
                'total_pnl': sum(t['pnl_percent'] for t in trades),
                'target1_rate': target1_rate,
                'target2_rate': target2_rate,
                'stoploss_rate': stoploss_rate,
                'avg_holding_days': np.mean([t['holding_days'] for t in trades]),
                'avg_win_momentum': avg_win_momentum,
                'avg_win_volume_surge': avg_win_volume,
                'avg_win_pullback': avg_win_pullback,
                'avg_win_holding_days': avg_win_holding,
                'avg_win_volatility': avg_win_volatility,
                'score_distribution': dict(score_dist),
                'trades': trades
            }
    
    def identify_winner_characteristics(self):
        """Identify common characteristics of top-performing tickers"""
        self.logger.info("Identifying winner characteristics...")
        
        # Sort tickers by total PnL
        sorted_tickers = sorted(
            self.ticker_performance.items(),
            key=lambda x: x[1]['total_pnl'],
            reverse=True
        )
        
        # Get top performers
        top_winners = sorted_tickers[:self.top_n_winners]
        
        # Analyze winning patterns
        winner_stats = {
            'avg_win_rate': np.mean([t[1]['win_rate'] for t in top_winners]),
            'avg_expectancy': np.mean([t[1]['expectancy'] for t in top_winners]),
            'avg_momentum': np.mean([t[1]['avg_win_momentum'] for t in top_winners]),
            'avg_volume_surge': np.mean([t[1]['avg_win_volume_surge'] for t in top_winners if t[1]['avg_win_volume_surge'] > 0]),
            'avg_pullback_tolerance': np.mean([t[1]['avg_win_pullback'] for t in top_winners if t[1]['avg_win_pullback'] > 0]),
            'avg_holding_period': np.mean([t[1]['avg_win_holding_days'] for t in top_winners]),
            'avg_volatility': np.mean([t[1]['avg_win_volatility'] for t in top_winners]),
            'common_scores': self._get_common_scores(top_winners),
            'sector_distribution': self._get_sector_distribution([t[0] for t in top_winners])
        }
        
        self.winner_characteristics = winner_stats
        
        return top_winners, winner_stats
    
    def _get_common_scores(self, top_winners: List[Tuple]) -> Dict:
        """Get distribution of scores among top winners"""
        score_counts = defaultdict(int)
        total_trades = 0
        
        for ticker, stats in top_winners:
            for score, count in stats['score_distribution'].items():
                score_counts[score] += count
                total_trades += count
        
        # Convert to percentages
        score_dist = {}
        for score, count in score_counts.items():
            score_dist[score] = (count / total_trades) * 100 if total_trades > 0 else 0
        
        return score_dist
    
    def _get_sector_distribution(self, tickers: List[str]) -> Dict:
        """Get sector distribution for tickers (placeholder - would need sector mapping)"""
        # This is a simplified version - in production, you'd map tickers to sectors
        sector_keywords = {
            'BANK': 'Banking',
            'TECH': 'Technology',
            'PHARMA': 'Pharma',
            'AUTO': 'Auto',
            'FMCG': 'FMCG',
            'METAL': 'Metals',
            'REALTY': 'Realty',
            'POWER': 'Power',
            'OIL': 'Oil & Gas',
            'TELE': 'Telecom'
        }
        
        sector_counts = defaultdict(int)
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            sector_found = False
            
            for keyword, sector in sector_keywords.items():
                if keyword in ticker_upper:
                    sector_counts[sector] += 1
                    sector_found = True
                    break
            
            if not sector_found:
                sector_counts['Others'] += 1
        
        return dict(sector_counts)
    
    def generate_report(self, top_winners: List[Tuple], winner_stats: Dict):
        """Generate comprehensive analysis report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"ML/results/winner_performance_analysis_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("WINNER PERFORMANCE ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Analysis Period: Last {self.lookback_days} days\n")
            f.write(f"Total Tickers Analyzed: {len(self.ticker_performance)}\n")
            f.write(f"Total Trades Analyzed: {sum(p['total_trades'] for p in self.ticker_performance.values())}\n\n")
            
            # Winner Characteristics
            f.write("WINNER CHARACTERISTICS (Top {} Performers)\n".format(self.top_n_winners))
            f.write("-" * 50 + "\n")
            f.write(f"Average Win Rate: {winner_stats['avg_win_rate']:.1%}\n")
            f.write(f"Average Expectancy: {winner_stats['avg_expectancy']:.2f}%\n")
            f.write(f"Average Pre-Entry Momentum: {winner_stats['avg_momentum']:.2f}%\n")
            f.write(f"Average Volume Surge: {winner_stats['avg_volume_surge']:.2f}x\n")
            f.write(f"Average Pullback Tolerance: {winner_stats['avg_pullback_tolerance']:.2f}%\n")
            f.write(f"Average Holding Period: {winner_stats['avg_holding_period']:.1f} days\n")
            f.write(f"Average Volatility (ATR%): {winner_stats['avg_volatility']:.2f}%\n\n")
            
            # Score Distribution
            f.write("Score Distribution Among Winners:\n")
            for score, pct in sorted(winner_stats['common_scores'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {score}: {pct:.1f}%\n")
            f.write("\n")
            
            # Top Winners List
            f.write("TOP {} WINNING TICKERS\n".format(self.top_n_winners))
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<6}{'Ticker':<12}{'Trades':<8}{'Win%':<8}{'Total PnL%':<12}{'Expectancy%':<12}{'Avg Hold':<10}\n")
            f.write("-" * 80 + "\n")
            
            for i, (ticker, stats) in enumerate(top_winners, 1):
                f.write(f"{i:<6}{ticker:<12}{stats['total_trades']:<8}"
                       f"{stats['win_rate']*100:<8.1f}{stats['total_pnl']:<12.2f}"
                       f"{stats['expectancy']:<12.2f}{stats['avg_holding_days']:<10.1f}\n")
            
            f.write("\n")
            
            # Key Insights
            f.write("KEY INSIGHTS FOR SPOTTING FUTURE WINNERS\n")
            f.write("-" * 50 + "\n")
            
            insights = self._generate_insights(winner_stats, top_winners)
            for i, insight in enumerate(insights, 1):
                f.write(f"{i}. {insight}\n")
            
            # Bottom Performers Analysis
            f.write("\n\nBOTTOM PERFORMERS (AVOID CHARACTERISTICS)\n")
            f.write("-" * 50 + "\n")
            
            bottom_performers = sorted(
                self.ticker_performance.items(),
                key=lambda x: x[1]['total_pnl']
            )[:10]
            
            if bottom_performers:
                avg_loss_rate = np.mean([t[1]['win_rate'] for t in bottom_performers])
                avg_loss_exp = np.mean([t[1]['expectancy'] for t in bottom_performers])
                
                f.write(f"Average Win Rate: {avg_loss_rate:.1%}\n")
                f.write(f"Average Expectancy: {avg_loss_exp:.2f}%\n")
                
                f.write("\nBottom 10 Tickers:\n")
                for ticker, stats in bottom_performers:
                    f.write(f"  {ticker}: {stats['total_pnl']:.2f}% (Win Rate: {stats['win_rate']:.1%})\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Report generated: {datetime.now()}\n")
        
        # Generate Excel report with detailed data
        excel_file = f"ML/results/winner_performance_analysis_{timestamp}.xlsx"
        self._generate_excel_report(excel_file, top_winners)
        
        self.logger.info(f"Reports generated: {report_file} and {excel_file}")
        
        return report_file, excel_file
    
    def _generate_insights(self, winner_stats: Dict, top_winners: List[Tuple]) -> List[str]:
        """Generate actionable insights from the analysis"""
        insights = []
        
        # Momentum insight
        if winner_stats['avg_momentum'] > 5:
            insights.append(f"Winners show strong pre-entry momentum (avg {winner_stats['avg_momentum']:.1f}%). "
                          "Focus on stocks with 5-day momentum > 5%")
        
        # Volume insight
        if winner_stats['avg_volume_surge'] > 1.5:
            insights.append(f"Winners typically have volume surge of {winner_stats['avg_volume_surge']:.1f}x. "
                          "Prioritize setups with volume > 1.5x 20-day average")
        
        # Score insight
        score_dist = winner_stats['common_scores']
        if '7/7' in score_dist and score_dist['7/7'] > 20:
            insights.append(f"High-score setups (7/7) represent {score_dist['7/7']:.0f}% of winner trades. "
                          "These should be prioritized with larger position sizes")
        
        # Holding period insight
        if winner_stats['avg_holding_period'] < 5:
            insights.append(f"Winners reach targets quickly (avg {winner_stats['avg_holding_period']:.1f} days). "
                          "Consider tightening stops after 5 days if no progress")
        elif winner_stats['avg_holding_period'] > 10:
            insights.append(f"Winners need time to develop (avg {winner_stats['avg_holding_period']:.1f} days). "
                          "Be patient with positions showing positive momentum")
        
        # Pullback insight
        if winner_stats['avg_pullback_tolerance'] > 0:
            insights.append(f"Winners typically pullback {winner_stats['avg_pullback_tolerance']:.1f}% during trends. "
                          "Don't exit on normal retracements under this level")
        
        # Win rate insight
        if winner_stats['avg_win_rate'] > 0.6:
            insights.append(f"Top performers have high win rates ({winner_stats['avg_win_rate']:.0%}). "
                          "Focus on quality over quantity in trade selection")
        
        # Volatility insight
        if winner_stats['avg_volatility'] > 3:
            insights.append(f"Winners tend to be volatile stocks (ATR {winner_stats['avg_volatility']:.1f}%). "
                          "Adjust position sizes based on volatility")
        
        # Repeat winners
        repeat_winners = [t for t, s in top_winners if s['total_trades'] >= 3]
        if repeat_winners:
            insights.append(f"Tickers like {', '.join(repeat_winners[:3])} appear multiple times in scans. "
                          "Track these 'repeat winners' for future opportunities")
        
        return insights
    
    def _generate_excel_report(self, filename: str, top_winners: List[Tuple]):
        """Generate detailed Excel report"""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for ticker, stats in self.ticker_performance.items():
                summary_data.append({
                    'Ticker': ticker,
                    'Total_Trades': stats['total_trades'],
                    'Win_Rate_%': stats['win_rate'] * 100,
                    'Total_PnL_%': stats['total_pnl'],
                    'Avg_Win_%': stats['avg_win_percent'],
                    'Avg_Loss_%': stats['avg_loss_percent'],
                    'Expectancy_%': stats['expectancy'],
                    'Target1_Hit_%': stats['target1_rate'] * 100,
                    'Target2_Hit_%': stats['target2_rate'] * 100,
                    'StopLoss_Hit_%': stats['stoploss_rate'] * 100,
                    'Avg_Holding_Days': stats['avg_holding_days'],
                    'Avg_Win_Momentum_%': stats['avg_win_momentum'],
                    'Avg_Win_Volume_Surge': stats['avg_win_volume_surge'],
                    'Avg_Win_Volatility_%': stats['avg_win_volatility']
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.sort_values('Total_PnL_%', ascending=False, inplace=True)
            summary_df.to_excel(writer, sheet_name='Ticker_Summary', index=False)
            
            # Top winners detail sheet
            top_winner_details = []
            for ticker, stats in top_winners:
                for trade in stats['trades']:
                    trade_detail = {
                        'Ticker': ticker,
                        'Entry_Date': trade['entry_date'],
                        'Entry_Price': trade['entry_price'],
                        'Exit_Date': trade['exit_date'],
                        'Exit_Price': trade['exit_price'],
                        'Outcome': trade['outcome'],
                        'PnL_%': trade['pnl_percent'],
                        'Holding_Days': trade['holding_days'],
                        'Score': trade['score'],
                        'Max_Favorable_%': trade['max_favorable'],
                        'Max_Adverse_%': trade['max_adverse'],
                        'Pre_Momentum_%': trade['momentum_score'],
                        'Volume_Surge': trade['volume_surge'],
                        'Volatility_%': trade['volatility']
                    }
                    top_winner_details.append(trade_detail)
            
            if top_winner_details:
                detail_df = pd.DataFrame(top_winner_details)
                detail_df.to_excel(writer, sheet_name='Top_Winner_Trades', index=False)
            
            # Winner characteristics sheet
            char_data = {
                'Metric': [
                    'Average Win Rate',
                    'Average Expectancy',
                    'Average Pre-Entry Momentum',
                    'Average Volume Surge',
                    'Average Pullback Tolerance',
                    'Average Holding Period',
                    'Average Volatility (ATR%)'
                ],
                'Value': [
                    f"{self.winner_characteristics['avg_win_rate']:.1%}",
                    f"{self.winner_characteristics['avg_expectancy']:.2f}%",
                    f"{self.winner_characteristics['avg_momentum']:.2f}%",
                    f"{self.winner_characteristics['avg_volume_surge']:.2f}x",
                    f"{self.winner_characteristics['avg_pullback_tolerance']:.2f}%",
                    f"{self.winner_characteristics['avg_holding_period']:.1f} days",
                    f"{self.winner_characteristics['avg_volatility']:.2f}%"
                ]
            }
            
            char_df = pd.DataFrame(char_data)
            char_df.to_excel(writer, sheet_name='Winner_Characteristics', index=False)
    
    def run_analysis(self, days: int = 30, top_n: int = 20):
        """Run the complete analysis"""
        self.lookback_days = days
        self.top_n_winners = top_n
        
        self.logger.info(f"Starting winner performance analysis for last {days} days")
        
        # Load Excel reports
        df = self.load_excel_reports()
        if df.empty:
            self.logger.error("No data to analyze")
            return None, None
        
        # Filter by date range
        cutoff_date = datetime.now() - timedelta(days=days)
        df = df[df['scan_date'] >= cutoff_date]
        
        if df.empty:
            self.logger.error(f"No data in the last {days} days")
            return None, None
        
        # Analyze performance
        self.analyze_ticker_performance(df)
        
        # Aggregate statistics
        self.aggregate_ticker_statistics()
        
        # Identify winner characteristics
        top_winners, winner_stats = self.identify_winner_characteristics()
        
        # Generate reports
        text_report, excel_report = self.generate_report(top_winners, winner_stats)
        
        return text_report, excel_report


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze winner performance from trading results')
    parser.add_argument('--days', type=int, default=30, help='Number of days to analyze (default: 30)')
    parser.add_argument('--top-n', type=int, default=20, help='Number of top winners to analyze (default: 20)')
    parser.add_argument('-u', '--user', type=str, default='Sai', help='User name for credentials (default: Sai)')
    parser.add_argument('--offline', action='store_true', help='Use offline mode with local CSV data')
    
    args = parser.parse_args()
    
    # Create results directory if it doesn't exist
    os.makedirs('ML/results', exist_ok=True)
    os.makedirs('ML/logs', exist_ok=True)
    
    # Run analysis
    analyzer = WinnerPerformanceAnalyzer(user_name=args.user, use_offline=args.offline)
    text_report, excel_report = analyzer.run_analysis(days=args.days, top_n=args.top_n)
    
    if text_report and excel_report:
        print(f"\nAnalysis complete!")
        print(f"Text report: {text_report}")
        print(f"Excel report: {excel_report}")
        
        # Display summary
        with open(text_report, 'r') as f:
            lines = f.readlines()
            # Print first 50 lines as summary
            print("\n" + "".join(lines[:50]))
            if len(lines) > 50:
                print("\n... (see full report for more details)")
    else:
        print("Analysis failed. Check logs for details.")


if __name__ == "__main__":
    main()