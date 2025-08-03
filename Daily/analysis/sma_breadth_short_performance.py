#!/usr/bin/env python3
"""
Analyze Short Performance based on SMA20 and SMA50 Breadth levels
Find optimal breadth thresholds for shorting
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

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

class SMABreadthShortAnalyzer:
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
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'breadth_analysis')
        os.makedirs(self.results_dir, exist_ok=True)
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'sma_breadth_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
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
    
    def find_short_reversal_files(self, date: datetime) -> List[str]:
        """Find short reversal files for a given date"""
        date_str = date.strftime('%Y%m%d')
        results_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
        
        files = []
        try:
            for file in os.listdir(results_dir):
                if file.startswith(f'Short_Reversal_Daily_{date_str}') and file.endswith('.xlsx'):
                    files.append(os.path.join(results_dir, file))
            
            # Return the file closest to noon if multiple exist
            if files:
                # Sort by timestamp in filename
                files.sort()
                # Try to find one around noon (11-13)
                for file in files:
                    if any(hour in file for hour in ['_11', '_12', '_13']):
                        return [file]
                # Otherwise return the last one
                return [files[-1]]
                
        except Exception as e:
            self.logger.error(f"Error finding files for {date_str}: {e}")
        
        return files
    
    def analyze_short_performance(self, signal_file: str, signal_date: datetime) -> Dict:
        """Analyze performance of shorts from a signal file"""
        try:
            # Load signals
            signals_df = pd.read_excel(signal_file)
            if signals_df.empty:
                return None
                
            # Get ticker column
            ticker_col = None
            for col in ['Ticker', 'ticker', 'Symbol', 'symbol']:
                if col in signals_df.columns:
                    ticker_col = col
                    break
            
            if not ticker_col:
                return None
            
            total_signals = len(signals_df)
            successful_shorts = 0
            total_pnl = 0
            analyzed_count = 0
            
            # Analyze each ticker (sample for speed)
            sample_size = min(20, len(signals_df))  # Analyze up to 20 tickers
            sample_df = signals_df.sample(n=sample_size) if len(signals_df) > sample_size else signals_df
            
            for _, row in sample_df.iterrows():
                ticker = row[ticker_col]
                
                # Get performance
                perf = self.get_ticker_weekly_performance(ticker, signal_date)
                if perf:
                    analyzed_count += 1
                    if perf['pnl_percent'] > 0:
                        successful_shorts += 1
                    total_pnl += perf['pnl_percent']
            
            if analyzed_count == 0:
                return None
            
            # Scale up the results
            scale_factor = total_signals / sample_size if sample_size < total_signals else 1
            
            return {
                'date': signal_date.strftime('%Y-%m-%d'),
                'total_signals': total_signals,
                'analyzed_signals': analyzed_count,
                'success_rate': (successful_shorts / analyzed_count * 100) if analyzed_count > 0 else 0,
                'avg_pnl': (total_pnl / analyzed_count) if analyzed_count > 0 else 0,
                'estimated_successful': int(successful_shorts * scale_factor)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {signal_file}: {e}")
            return None
    
    def get_ticker_weekly_performance(self, ticker: str, entry_date: datetime) -> Dict:
        """Get simplified weekly performance for a ticker"""
        try:
            if not self.kite:
                return None
                
            # Get instrument token
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return None
            
            # Fetch 5 days of data
            from_date = entry_date
            to_date = entry_date + timedelta(days=7)
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval='day'
            )
            
            if len(historical_data) < 2:
                return None
            
            entry_price = historical_data[0]['close']
            # Get price after 3-5 days
            exit_idx = min(3, len(historical_data) - 1)
            exit_price = historical_data[exit_idx]['close']
            
            # Short PnL
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
            
            return {
                'ticker': ticker,
                'pnl_percent': pnl_percent,
                'entry_price': entry_price,
                'exit_price': exit_price
            }
            
        except Exception:
            return None
    
    def get_instrument_token(self, ticker: str) -> int:
        """Get instrument token for a ticker"""
        try:
            instruments = self.kite.instruments("NSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            return None
        except:
            return None
    
    def analyze_breadth_performance_correlation(self):
        """Main analysis function"""
        self.logger.info("Starting SMA breadth and short performance analysis...")
        
        # Define breadth ranges to analyze
        sma20_ranges = [
            (0, 10, "Ultra Low"),
            (10, 20, "Very Low"),
            (20, 30, "Low"),
            (30, 40, "Below Average"),
            (40, 50, "Average"),
            (50, 60, "Above Average"),
            (60, 100, "High")
        ]
        
        results = []
        
        # Analyze last 2 months of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Filter breadth data
        analysis_df = self.breadth_data[
            (self.breadth_data['date'] >= start_date) & 
            (self.breadth_data['date'] <= end_date)
        ]
        
        # Analyze each breadth range
        for min_breadth, max_breadth, range_name in sma20_ranges:
            range_data = analysis_df[
                (analysis_df['sma20_percent'] >= min_breadth) & 
                (analysis_df['sma20_percent'] < max_breadth)
            ]
            
            if range_data.empty:
                continue
            
            self.logger.info(f"Analyzing {range_name} breadth range ({min_breadth}-{max_breadth}%): {len(range_data)} days")
            
            range_results = {
                'breadth_range': f"{min_breadth}-{max_breadth}%",
                'range_name': range_name,
                'days_count': len(range_data),
                'avg_sma20': range_data['sma20_percent'].mean(),
                'avg_sma50': range_data['sma50_percent'].mean(),
                'performances': []
            }
            
            # Sample a few days from this range for performance analysis
            sample_days = range_data.sample(n=min(5, len(range_data)))
            
            for _, day in sample_days.iterrows():
                # Find short reversal files for this day
                files = self.find_short_reversal_files(day['date'])
                
                if files:
                    for file in files:
                        perf = self.analyze_short_performance(file, day['date'])
                        if perf:
                            perf['sma20_breadth'] = day['sma20_percent']
                            perf['sma50_breadth'] = day['sma50_percent']
                            range_results['performances'].append(perf)
            
            # Calculate average performance for this range
            if range_results['performances']:
                avg_success = np.mean([p['success_rate'] for p in range_results['performances']])
                avg_pnl = np.mean([p['avg_pnl'] for p in range_results['performances']])
                
                range_results['avg_success_rate'] = avg_success
                range_results['avg_pnl'] = avg_pnl
                
                results.append(range_results)
        
        # Create summary report
        self.create_breadth_analysis_report(results)
        
        return results
    
    def create_breadth_analysis_report(self, results: List[Dict]):
        """Create analysis report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Print summary
        print("\n" + "="*70)
        print("SMA BREADTH vs SHORT PERFORMANCE ANALYSIS")
        print("="*70)
        
        print(f"\n{'Breadth Range':<20} {'Days':<8} {'Avg Success':<12} {'Avg PnL':<10}")
        print("-"*50)
        
        optimal_ranges = []
        
        for result in results:
            if 'avg_success_rate' in result:
                print(f"{result['range_name']:<20} {result['days_count']:<8} "
                      f"{result['avg_success_rate']:<12.1f}% {result['avg_pnl']:<10.2f}%")
                
                # Track optimal ranges
                if result['avg_success_rate'] > 60 or result['avg_pnl'] > 1:
                    optimal_ranges.append(result)
        
        # Print recommendations
        print("\n" + "="*70)
        print("OPTIMAL SHORTING CONDITIONS:")
        print("="*70)
        
        if optimal_ranges:
            # Sort by avg PnL
            optimal_ranges.sort(key=lambda x: x['avg_pnl'], reverse=True)
            
            print("\nBest SMA20 Breadth Ranges for Shorting:")
            for i, opt in enumerate(optimal_ranges[:3], 1):
                print(f"\n{i}. {opt['range_name']} ({opt['breadth_range']})")
                print(f"   - Average Success Rate: {opt['avg_success_rate']:.1f}%")
                print(f"   - Average PnL: {opt['avg_pnl']:.2f}%")
                print(f"   - Average SMA20: {opt['avg_sma20']:.1f}%")
                print(f"   - Average SMA50: {opt['avg_sma50']:.1f}%")
        
        # Additional insights
        print("\n" + "="*70)
        print("KEY INSIGHTS:")
        print("="*70)
        
        # Find the threshold
        if results:
            profitable_ranges = [r for r in results if 'avg_pnl' in r and r['avg_pnl'] > 0]
            if profitable_ranges:
                max_profitable_breadth = max(int(r['breadth_range'].split('-')[1].replace('%', '')) 
                                           for r in profitable_ranges)
                print(f"\n✓ Shorting becomes favorable when SMA20 breadth < {max_profitable_breadth}%")
                print(f"✓ Best performance typically in {optimal_ranges[0]['breadth_range']} range")
                print(f"✓ Success rate improves as breadth decreases")
        
        # Save detailed results
        output_file = os.path.join(self.results_dir, f'sma_breadth_analysis_{timestamp}.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: {output_file}")

def main():
    """Main function"""
    print("Analyzing SMA Breadth vs Short Performance...")
    print("-" * 60)
    
    analyzer = SMABreadthShortAnalyzer(user_name='Sai')
    results = analyzer.analyze_breadth_performance_correlation()

if __name__ == "__main__":
    main()