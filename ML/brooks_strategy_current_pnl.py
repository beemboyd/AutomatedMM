#!/usr/bin/env python
"""
Brooks Higher Probability LONG Reversal Strategy - Current PnL Analysis
======================================================================
This script provides a simple PnL analysis of tickers from Brooks Higher Probability 
LONG Reversal strategy files by comparing entry prices to current prices from Zerodha.

Features:
- Analyzes all Brooks strategy files
- Calculates simple PnL: Current Price - Entry Price
- Gives equal weightage to all tickers
- Provides overall strategy effectiveness metrics
- Generates concise report with current PnL for all tickers
- Supports multiple Zerodha user accounts

Author: Claude Code Assistant
Created: 2025-05-30
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
import argparse
import logging
import glob
import re
import time
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns

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
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'brooks_current_pnl.log'))
    ]
)
logger = logging.getLogger(__name__)

class BrooksCurrentPnLAnalyzer:
    """Analyze current PnL of Brooks Higher Probability LONG Reversal strategy tickers"""
    
    def __init__(self, user_name="Sai"):
        """Initialize the analyzer with user credentials"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.join(os.path.dirname(self.script_dir), "Daily")
        self.results_dir_source = os.path.join(self.daily_dir, "results")
        self.results_dir = os.path.join(self.script_dir, "results")
        self.user_name = user_name
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize user context and Zerodha connection
        self.data_handler = self._initialize_data_handler()
        
        logger.info(f"Initialized Brooks Current PnL Analyzer for user: {user_name}")
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
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker from Zerodha"""
        try:
            # Try to use data_handler's fetch_current_price method
            if hasattr(self.data_handler, 'fetch_current_price'):
                price = self.data_handler.fetch_current_price(ticker)
                if price is not None:
                    logger.info(f"Current price for {ticker}: ₹{price:.2f}")
                    return price
            
            # Fallback to kite.ltp
            exchange = "NSE"  # Use NSE for Indian equities
            instrument = f"{exchange}:{ticker}"
            
            ltp_data = self.data_handler.kite.ltp(instrument)
            if ltp_data and instrument in ltp_data:
                price = ltp_data[instrument]['last_price']
                logger.info(f"Current price for {ticker}: ₹{price:.2f}")
                return price
            
            logger.warning(f"Could not get current price for {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return None
    
    def calculate_simple_pnl(self, ticker: str, entry_price: float) -> Dict:
        """Calculate simple PnL: Current Price - Entry Price"""
        try:
            current_price = self.get_current_price(ticker)
            
            if current_price is None or entry_price <= 0:
                return {
                    'ticker': ticker,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'absolute_pnl': None,
                    'percent_pnl': None,
                    'status': 'Error'
                }
            
            absolute_pnl = current_price - entry_price
            percent_pnl = (absolute_pnl / entry_price) * 100
            
            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'current_price': current_price,
                'absolute_pnl': absolute_pnl,
                'percent_pnl': percent_pnl,
                'status': 'Profit' if absolute_pnl > 0 else 'Loss'
            }
            
        except Exception as e:
            logger.error(f"Error calculating PnL for {ticker}: {e}")
            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'current_price': None,
                'absolute_pnl': None,
                'percent_pnl': None,
                'status': 'Error'
            }
    
    def analyze_current_pnl(self) -> Dict:
        """Analyze current PnL for all Brooks strategy tickers"""
        try:
            logger.info(f"Starting Brooks Strategy Current PnL Analysis for user: {self.user_name}")
            
            # Get all Brooks strategy files
            brooks_files = self.get_brooks_files()
            
            if not brooks_files:
                logger.error("No Brooks strategy files found")
                return {}
            
            all_tickers = {}  # Dict to track unique tickers with their earliest entry
            
            # Process all files
            for file_path, scan_date in brooks_files:
                logger.info(f"Processing file: {os.path.basename(file_path)} - {scan_date.strftime('%Y-%m-%d')}")
                
                strategy_data = self.read_brooks_file(file_path)
                for ticker_data in strategy_data:
                    ticker = ticker_data['ticker']
                    entry_price = ticker_data['entry_price']
                    
                    # Only keep the earliest entry for each ticker
                    if ticker not in all_tickers or scan_date < all_tickers[ticker]['scan_date']:
                        all_tickers[ticker] = {
                            'ticker': ticker,
                            'entry_price': entry_price,
                            'scan_date': scan_date,
                            'file': os.path.basename(file_path),
                            'stop_loss': ticker_data['stop_loss'],
                            'target1': ticker_data['target1'],
                            'risk_reward_ratio': ticker_data['risk_reward_ratio']
                        }
            
            logger.info(f"Found {len(all_tickers)} unique tickers across all strategy files")
            
            # Calculate current PnL for each ticker
            results = []
            successful_results = []
            
            for ticker, data in all_tickers.items():
                # Add a small delay to avoid API rate limits
                time.sleep(0.1)
                
                pnl_data = self.calculate_simple_pnl(ticker, data['entry_price'])
                result = {**data, **pnl_data}
                results.append(result)
                
                if pnl_data['status'] != 'Error':
                    successful_results.append(result)
            
            # Calculate overall statistics
            if successful_results:
                overall_stats = self.calculate_overall_stats(successful_results)
            else:
                overall_stats = {}
            
            # Generate Excel report
            excel_file = self.export_excel_report(results, overall_stats)
            
            # Generate summary chart
            chart_file = self.create_summary_chart(successful_results)
            
            # Print summary
            self.print_summary(results, overall_stats)
            
            return {
                'results': results,
                'stats': overall_stats,
                'excel_file': excel_file,
                'chart_file': chart_file
            }
            
        except Exception as e:
            logger.error(f"Error in current PnL analysis: {e}")
            return {}
    
    def calculate_overall_stats(self, results: List[Dict]) -> Dict:
        """Calculate overall statistics from PnL results"""
        try:
            total_tickers = len(results)
            
            if total_tickers == 0:
                return {}
            
            # Calculate basic statistics
            profitable_tickers = sum(1 for r in results if r['status'] == 'Profit')
            loss_making_tickers = sum(1 for r in results if r['status'] == 'Loss')
            
            win_rate = (profitable_tickers / total_tickers) * 100 if total_tickers > 0 else 0
            
            # Calculate PnL statistics
            pnl_values = [r['percent_pnl'] for r in results if r['percent_pnl'] is not None]
            
            if pnl_values:
                avg_pnl = sum(pnl_values) / len(pnl_values)
                median_pnl = sorted(pnl_values)[len(pnl_values) // 2]
                max_pnl = max(pnl_values)
                min_pnl = min(pnl_values)
                
                # Calculate average profit and loss
                profit_values = [r['percent_pnl'] for r in results if r['status'] == 'Profit']
                loss_values = [r['percent_pnl'] for r in results if r['status'] == 'Loss']
                
                avg_profit = sum(profit_values) / len(profit_values) if profit_values else 0
                avg_loss = sum(loss_values) / len(loss_values) if loss_values else 0
                
                # Calculate risk-reward and profit factor
                total_profit = sum(profit_values)
                total_loss = abs(sum(loss_values)) if loss_values else 0
                profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
                
                # Calculate equal-weighted portfolio return
                portfolio_return = avg_pnl
            else:
                avg_pnl = median_pnl = max_pnl = min_pnl = 0
                avg_profit = avg_loss = 0
                profit_factor = 0
                portfolio_return = 0
            
            return {
                'total_tickers': total_tickers,
                'profitable_tickers': profitable_tickers,
                'loss_making_tickers': loss_making_tickers,
                'win_rate': win_rate,
                'avg_percent_pnl': avg_pnl,
                'median_percent_pnl': median_pnl,
                'max_percent_pnl': max_pnl,
                'min_percent_pnl': min_pnl,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'equal_weighted_portfolio_return': portfolio_return
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall statistics: {e}")
            return {}
    
    def export_excel_report(self, results: List[Dict], stats: Dict) -> str:
        """Export PnL results to Excel file"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(self.results_dir, f"brooks_current_pnl_{timestamp}.xlsx")
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Create results DataFrame
                results_df = pd.DataFrame(results)
                
                # Format scan_date column
                if 'scan_date' in results_df.columns:
                    results_df['scan_date'] = results_df['scan_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
                
                # Sort by percent_pnl (descending)
                if 'percent_pnl' in results_df.columns:
                    results_df = results_df.sort_values('percent_pnl', ascending=False)
                
                # Write results to sheet
                results_df.to_excel(writer, sheet_name='PnL_Results', index=False)
                
                # Create summary DataFrame
                if stats:
                    summary_data = [
                        ['Total Tickers Analyzed', stats.get('total_tickers', 0)],
                        ['Profitable Tickers', stats.get('profitable_tickers', 0)],
                        ['Loss Making Tickers', stats.get('loss_making_tickers', 0)],
                        ['Win Rate (%)', round(stats.get('win_rate', 0), 2)],
                        ['Average Percent PnL (%)', round(stats.get('avg_percent_pnl', 0), 2)],
                        ['Median Percent PnL (%)', round(stats.get('median_percent_pnl', 0), 2)],
                        ['Maximum PnL (%)', round(stats.get('max_percent_pnl', 0), 2)],
                        ['Minimum PnL (%)', round(stats.get('min_percent_pnl', 0), 2)],
                        ['Average Profit (%)', round(stats.get('avg_profit', 0), 2)],
                        ['Average Loss (%)', round(stats.get('avg_loss', 0), 2)],
                        ['Profit Factor', round(stats.get('profit_factor', 0), 2)],
                        ['Equal-Weighted Portfolio Return (%)', round(stats.get('equal_weighted_portfolio_return', 0), 2)],
                        ['Analysis Date', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                        ['User Account', self.user_name]
                    ]
                    
                    summary_df = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            logger.info(f"Exported results to Excel: {excel_file}")
            return excel_file
            
        except Exception as e:
            logger.error(f"Error exporting Excel report: {e}")
            return ""
    
    def create_summary_chart(self, results: List[Dict]) -> str:
        """Create summary chart of PnL distribution"""
        try:
            if not results:
                return ""
            
            # Set style
            plt.style.use('seaborn-v0_8')
            
            # Create figure
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Extract PnL values
            pnl_values = [r['percent_pnl'] for r in results if r['percent_pnl'] is not None]
            
            if not pnl_values:
                return ""
            
            # 1. PnL Distribution
            ax1.hist(pnl_values, bins=20, alpha=0.7, color='steelblue', edgecolor='black')
            ax1.axvline(np.mean(pnl_values), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(pnl_values):.2f}%')
            ax1.axvline(0, color='black', linestyle='-', linewidth=1)
            ax1.set_title('Distribution of Percent PnL', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Percent PnL (%)')
            ax1.set_ylabel('Frequency')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. Win/Loss Pie Chart
            profitable = sum(1 for r in results if r['status'] == 'Profit')
            losses = sum(1 for r in results if r['status'] == 'Loss')
            
            labels = ['Profitable', 'Loss']
            sizes = [profitable, losses]
            colors = ['#27ae60', '#e74c3c']
            explode = (0.1, 0)
            
            ax2.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                   shadow=True, startangle=90)
            ax2.axis('equal')
            ax2.set_title('Win/Loss Ratio', fontsize=14, fontweight='bold')
            
            # Add text with key metrics
            win_rate = (profitable / (profitable + losses)) * 100 if (profitable + losses) > 0 else 0
            avg_pnl = np.mean(pnl_values)
            
            fig.text(0.5, 0.01, 
                    f"Brooks Strategy Current PnL Analysis | Win Rate: {win_rate:.1f}% | Avg PnL: {avg_pnl:.2f}%\nUser: {self.user_name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d')}",
                    ha='center', fontsize=12, fontstyle='italic')
            
            # Save figure
            plt.tight_layout(rect=[0, 0.05, 1, 0.95])
            chart_file = os.path.join(self.results_dir, f"brooks_current_pnl_chart_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created summary chart: {chart_file}")
            return chart_file
            
        except Exception as e:
            logger.error(f"Error creating summary chart: {e}")
            return ""
    
    def print_summary(self, results: List[Dict], stats: Dict):
        """Print summary of PnL analysis to console"""
        print("\n" + "="*80)
        print(f"BROOKS HIGHER PROBABILITY LONG REVERSAL STRATEGY - CURRENT PNL ANALYSIS")
        print(f"User: {self.user_name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        if not stats:
            print("No valid PnL results found.")
            return
        
        # Print overall statistics
        print(f"Total Tickers Analyzed: {stats.get('total_tickers', 0)}")
        print(f"Win Rate: {stats.get('win_rate', 0):.1f}% ({stats.get('profitable_tickers', 0)}/{stats.get('total_tickers', 0)} tickers)")
        print(f"Equal-Weighted Portfolio Return: {stats.get('equal_weighted_portfolio_return', 0):.2f}%")
        print(f"Average PnL: {stats.get('avg_percent_pnl', 0):.2f}%")
        print(f"Median PnL: {stats.get('median_percent_pnl', 0):.2f}%")
        print(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")
        print("-"*80)
        
        # Print top 5 winners
        profitable = [r for r in results if r.get('status') == 'Profit']
        profitable.sort(key=lambda x: x.get('percent_pnl', 0), reverse=True)
        
        print("TOP 5 WINNERS:")
        for i, ticker in enumerate(profitable[:5], 1):
            print(f"{i}. {ticker['ticker']}: {ticker.get('percent_pnl', 0):.2f}% (₹{ticker.get('entry_price', 0):.2f} → ₹{ticker.get('current_price', 0):.2f})")
        
        # Print top 5 losers
        losers = [r for r in results if r.get('status') == 'Loss']
        losers.sort(key=lambda x: x.get('percent_pnl', 0))
        
        print("\nTOP 5 LOSERS:")
        for i, ticker in enumerate(losers[:5], 1):
            print(f"{i}. {ticker['ticker']}: {ticker.get('percent_pnl', 0):.2f}% (₹{ticker.get('entry_price', 0):.2f} → ₹{ticker.get('current_price', 0):.2f})")
        
        print("-"*80)
        
        # Print report info
        print(f"Detailed results saved to: {self.results_dir}")
        
        print("="*80)


def main():
    """Main function"""
    try:
        # Create logs directory
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Brooks Strategy Current PnL Analysis")
        parser.add_argument("--user", "-u", type=str, default="Sai", help="User whose API credentials to use (default: Sai)")
        parser.add_argument("--results-dir", "-d", type=str, help="Custom directory to save results")
        args = parser.parse_args()
        
        # Initialize analyzer with user credentials
        analyzer = BrooksCurrentPnLAnalyzer(user_name=args.user)
        
        # Set custom results directory if provided
        if args.results_dir:
            analyzer.results_dir = os.path.abspath(args.results_dir)
            os.makedirs(analyzer.results_dir, exist_ok=True)
            logger.info(f"Custom results directory set: {analyzer.results_dir}")
        
        # Run analysis
        results = analyzer.analyze_current_pnl()
        
        if results:
            print(f"\nBrooks strategy current PnL analysis completed successfully!")
            print(f"Results saved to: {analyzer.results_dir}")
        else:
            print("Brooks strategy current PnL analysis failed. Check logs for details.")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())