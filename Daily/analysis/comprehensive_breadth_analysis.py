#!/usr/bin/env python3
"""
Comprehensive Breadth Analysis for Long and Short Strategies
Analyzes ALL available data points for accurate rule formation
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Tuple
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

class ComprehensiveBreadthAnalyzer:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the analyzer"""
        self.user_name = user_name
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.setup_logging()
        
        # Load historical breadth data
        self.breadth_data = self.load_historical_breadth()
        
        # Initialize Kite for performance checking
        self.kite = self.initialize_kite_connection()
        
        # Results directory
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comprehensive_analysis')
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Cache for ticker data
        self.ticker_cache = {}
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'comprehensive_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def initialize_kite_connection(self) -> KiteConnect:
        """Initialize Kite connection"""
        try:
            config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            return None
    
    def load_historical_breadth(self) -> pd.DataFrame:
        """Load historical breadth data"""
        try:
            breadth_file = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                       'historical_breadth_data', 'sma_breadth_historical_latest.json')
            
            with open(breadth_file, 'r') as f:
                data = json.load(f)
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Extract breadth values
            df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
            df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
            
            self.logger.info(f"Loaded {len(df)} days of breadth data")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading breadth data: {e}")
            return pd.DataFrame()
    
    def find_signal_files(self, date: datetime, signal_type: str = 'Long') -> List[str]:
        """Find reversal signal files for a given date"""
        date_str = date.strftime('%Y%m%d')
        
        if signal_type == 'Long':
            results_dir = os.path.join(self.base_dir, 'Daily', 'results')
            pattern = f'Long_Reversal_Daily_{date_str}'
        else:
            results_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
            pattern = f'Short_Reversal_Daily_{date_str}'
        
        files = []
        try:
            if os.path.exists(results_dir):
                for file in os.listdir(results_dir):
                    if file.startswith(pattern) and file.endswith('.xlsx'):
                        files.append(os.path.join(results_dir, file))
            
            # Return files around market hours (10-15)
            if files:
                market_hour_files = []
                for file in files:
                    for hour in ['_10', '_11', '_12', '_13', '_14']:
                        if hour in file:
                            market_hour_files.append(file)
                            break
                
                if market_hour_files:
                    return market_hour_files
                else:
                    return files[:1]  # Return first file if no market hour files
                
        except Exception as e:
            self.logger.error(f"Error finding files for {date_str}: {e}")
        
        return files
    
    def get_ticker_performance(self, ticker: str, entry_date: datetime, holding_days: int = 4) -> Dict:
        """Get ticker performance with caching"""
        cache_key = f"{ticker}_{entry_date.strftime('%Y%m%d')}_{holding_days}"
        
        if cache_key in self.ticker_cache:
            return self.ticker_cache[cache_key]
        
        try:
            if not self.kite:
                return None
            
            # Get instrument token
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return None
            
            # Fetch data
            from_date = entry_date
            to_date = entry_date + timedelta(days=holding_days + 4)  # Extra buffer
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval='day'
            )
            
            if len(historical_data) < 2:
                return None
            
            # Calculate performance
            entry_price = historical_data[0]['close']
            
            # Get exit price (after holding_days trading days)
            exit_idx = min(holding_days, len(historical_data) - 1)
            exit_price = historical_data[exit_idx]['close']
            
            # Calculate PnL
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            
            result = {
                'ticker': ticker,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_percent': pnl_percent,
                'holding_days': exit_idx
            }
            
            # Cache the result
            self.ticker_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            return None
    
    def get_instrument_token(self, ticker: str) -> int:
        """Get instrument token for a ticker"""
        try:
            instruments = self.kite.instruments("NSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            # Try BSE
            instruments = self.kite.instruments("BSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            return None
        except:
            return None
    
    def analyze_signals_for_date(self, date: datetime, signal_type: str = 'Long') -> Dict:
        """Analyze all signals for a specific date"""
        signal_files = self.find_signal_files(date, signal_type)
        
        if not signal_files:
            return None
        
        all_results = []
        total_signals = 0
        
        for signal_file in signal_files:
            try:
                # Load signals
                signals_df = pd.read_excel(signal_file)
                if signals_df.empty:
                    continue
                
                # Get ticker column
                ticker_col = None
                for col in ['Ticker', 'ticker', 'Symbol', 'symbol']:
                    if col in signals_df.columns:
                        ticker_col = col
                        break
                
                if not ticker_col:
                    continue
                
                total_signals += len(signals_df)
                
                # Analyze each ticker
                for _, row in signals_df.iterrows():
                    ticker = row[ticker_col]
                    perf = self.get_ticker_performance(ticker, date)
                    
                    if perf:
                        all_results.append(perf)
                
            except Exception as e:
                self.logger.error(f"Error analyzing {signal_file}: {e}")
                continue
        
        if not all_results:
            return None
        
        # Calculate statistics
        pnl_values = [r['pnl_percent'] for r in all_results]
        successful = sum(1 for pnl in pnl_values if pnl > 0)
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'signal_type': signal_type,
            'total_signals': total_signals,
            'analyzed_signals': len(all_results),
            'successful_trades': successful,
            'success_rate': (successful / len(all_results) * 100) if all_results else 0,
            'avg_pnl': np.mean(pnl_values),
            'median_pnl': np.median(pnl_values),
            'std_pnl': np.std(pnl_values),
            'max_pnl': max(pnl_values),
            'min_pnl': min(pnl_values),
            'sharpe_ratio': (np.mean(pnl_values) / np.std(pnl_values)) if np.std(pnl_values) > 0 else 0
        }
    
    def run_comprehensive_analysis(self, lookback_days: int = 60):
        """Run comprehensive analysis for both long and short strategies"""
        self.logger.info(f"Starting comprehensive analysis for past {lookback_days} days...")
        
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Filter breadth data
        analysis_df = self.breadth_data[
            (self.breadth_data['date'] >= start_date) & 
            (self.breadth_data['date'] <= end_date)
        ]
        
        # Results storage
        long_results = []
        short_results = []
        
        # Process each date
        total_dates = len(analysis_df)
        
        for idx, (_, row) in enumerate(analysis_df.iterrows(), 1):
            date = row['date']
            sma20 = row['sma20_percent']
            sma50 = row['sma50_percent']
            
            self.logger.info(f"Processing {idx}/{total_dates}: {date.strftime('%Y-%m-%d')} (SMA20: {sma20:.1f}%)")
            
            # Analyze long signals
            long_perf = self.analyze_signals_for_date(date, 'Long')
            if long_perf:
                long_perf['sma20_breadth'] = sma20
                long_perf['sma50_breadth'] = sma50
                long_results.append(long_perf)
            
            # Analyze short signals
            short_perf = self.analyze_signals_for_date(date, 'Short')
            if short_perf:
                short_perf['sma20_breadth'] = sma20
                short_perf['sma50_breadth'] = sma50
                short_results.append(short_perf)
        
        # Create comprehensive report
        self.create_comprehensive_report(long_results, short_results)
        
        return long_results, short_results
    
    def create_comprehensive_report(self, long_results: List[Dict], short_results: List[Dict]):
        """Create detailed analysis report with optimal breadth ranges"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Convert to DataFrames
        long_df = pd.DataFrame(long_results) if long_results else pd.DataFrame()
        short_df = pd.DataFrame(short_results) if short_results else pd.DataFrame()
        
        # Define breadth ranges for analysis
        breadth_ranges = [
            (0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
            (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)
        ]
        
        # Analyze long strategy by breadth ranges
        print("\n" + "="*80)
        print("COMPREHENSIVE LONG REVERSAL STRATEGY ANALYSIS")
        print("="*80)
        
        if not long_df.empty:
            print(f"\nTotal data points analyzed: {len(long_df)}")
            print(f"Total signals processed: {long_df['total_signals'].sum()}")
            print(f"\n{'SMA20 Range':<15} {'Days':<8} {'Signals':<10} {'Success%':<10} {'Avg PnL%':<10} {'Sharpe':<10}")
            print("-"*70)
            
            long_summary = []
            for min_b, max_b in breadth_ranges:
                range_data = long_df[(long_df['sma20_breadth'] >= min_b) & (long_df['sma20_breadth'] < max_b)]
                
                if not range_data.empty:
                    summary = {
                        'range': f"{min_b}-{max_b}%",
                        'days': len(range_data),
                        'total_signals': range_data['total_signals'].sum(),
                        'avg_success_rate': range_data['success_rate'].mean(),
                        'avg_pnl': range_data['avg_pnl'].mean(),
                        'avg_sharpe': range_data['sharpe_ratio'].mean()
                    }
                    long_summary.append(summary)
                    
                    print(f"{summary['range']:<15} {summary['days']:<8} {summary['total_signals']:<10} "
                          f"{summary['avg_success_rate']:<10.1f} {summary['avg_pnl']:<10.2f} {summary['avg_sharpe']:<10.2f}")
        
        # Analyze short strategy by breadth ranges
        print("\n" + "="*80)
        print("COMPREHENSIVE SHORT REVERSAL STRATEGY ANALYSIS")
        print("="*80)
        
        if not short_df.empty:
            print(f"\nTotal data points analyzed: {len(short_df)}")
            print(f"Total signals processed: {short_df['total_signals'].sum()}")
            print(f"\n{'SMA20 Range':<15} {'Days':<8} {'Signals':<10} {'Success%':<10} {'Avg PnL%':<10} {'Sharpe':<10}")
            print("-"*70)
            
            short_summary = []
            for min_b, max_b in breadth_ranges:
                range_data = short_df[(short_df['sma20_breadth'] >= min_b) & (short_df['sma20_breadth'] < max_b)]
                
                if not range_data.empty:
                    summary = {
                        'range': f"{min_b}-{max_b}%",
                        'days': len(range_data),
                        'total_signals': range_data['total_signals'].sum(),
                        'avg_success_rate': range_data['success_rate'].mean(),
                        'avg_pnl': range_data['avg_pnl'].mean(),
                        'avg_sharpe': range_data['sharpe_ratio'].mean()
                    }
                    short_summary.append(summary)
                    
                    print(f"{summary['range']:<15} {summary['days']:<8} {summary['total_signals']:<10} "
                          f"{summary['avg_success_rate']:<10.1f} {summary['avg_pnl']:<10.2f} {summary['avg_sharpe']:<10.2f}")
        
        # Find optimal ranges
        self.determine_optimal_ranges(long_summary, short_summary)
        
        # Save detailed results
        output_file = os.path.join(self.results_dir, f'comprehensive_analysis_{timestamp}.json')
        results = {
            'analysis_date': datetime.now().isoformat(),
            'long_results': long_results,
            'short_results': short_results,
            'long_summary': long_summary,
            'short_summary': short_summary
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Comprehensive analysis saved to: {output_file}")
    
    def determine_optimal_ranges(self, long_summary: List[Dict], short_summary: List[Dict]):
        """Determine optimal breadth ranges based on comprehensive data"""
        print("\n" + "="*80)
        print("OPTIMAL TRADING RANGES - DATA-DRIVEN RECOMMENDATIONS")
        print("="*80)
        
        # Long strategy optimal ranges
        if long_summary:
            # Sort by average PnL
            long_sorted = sorted(long_summary, key=lambda x: x['avg_pnl'], reverse=True)
            
            print("\n📈 LONG REVERSAL STRATEGY:")
            print("-" * 40)
            
            # Find ranges with positive PnL and good success rate
            best_ranges = [r for r in long_sorted if r['avg_pnl'] > 0 and r['avg_success_rate'] > 40]
            good_ranges = [r for r in long_sorted if r['avg_pnl'] > -1 and r['avg_success_rate'] > 35]
            
            if best_ranges:
                print(f"✅ BEST: SMA20 breadth {best_ranges[0]['range']}")
                print(f"   - Success Rate: {best_ranges[0]['avg_success_rate']:.1f}%")
                print(f"   - Average PnL: {best_ranges[0]['avg_pnl']:.2f}%")
                print(f"   - Sample Size: {best_ranges[0]['total_signals']} signals")
            
            avoid_ranges = [r for r in long_sorted if r['avg_pnl'] < -2]
            if avoid_ranges:
                print(f"\n❌ AVOID: SMA20 breadth {', '.join([r['range'] for r in avoid_ranges])}")
        
        # Short strategy optimal ranges
        if short_summary:
            # Sort by average PnL
            short_sorted = sorted(short_summary, key=lambda x: x['avg_pnl'], reverse=True)
            
            print("\n📉 SHORT REVERSAL STRATEGY:")
            print("-" * 40)
            
            # Find ranges with positive PnL
            best_ranges = [r for r in short_sorted if r['avg_pnl'] > 0.5 and r['avg_success_rate'] > 50]
            
            if best_ranges:
                print(f"✅ BEST: SMA20 breadth {best_ranges[0]['range']}")
                print(f"   - Success Rate: {best_ranges[0]['avg_success_rate']:.1f}%")
                print(f"   - Average PnL: {best_ranges[0]['avg_pnl']:.2f}%")
                print(f"   - Sample Size: {best_ranges[0]['total_signals']} signals")

def main():
    """Main function"""
    print("Starting Comprehensive Breadth Analysis...")
    print("This will analyze all available data for accurate rule formation")
    print("-" * 60)
    
    analyzer = ComprehensiveBreadthAnalyzer(user_name='Sai')
    
    # Run analysis for past 60 days
    long_results, short_results = analyzer.run_comprehensive_analysis(lookback_days=60)

if __name__ == "__main__":
    main()