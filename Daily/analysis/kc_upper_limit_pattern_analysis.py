#!/usr/bin/env python3
"""
KC Upper Limit Trending Pattern Analysis
Analyzes historical performance of KC Upper Limit Trending signals
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
import json
from kiteconnect import KiteConnect
import logging
import sys
from collections import defaultdict
import configparser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KCUpperLimitAnalyzer:
    def __init__(self):
        self.config = self.load_config()
        self.kite = None
        self.signals_data = []
        self.performance_data = []
        
    def load_config(self):
        """Load configuration from Daily/config.ini file"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        if not os.path.exists(config_path):
            logger.error(f"config.ini file not found at {config_path}")
            raise FileNotFoundError(f"config.ini file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        return config
        
    def setup_kite_connection(self):
        """Setup Zerodha KiteConnect API connection"""
        try:
            # Use Sai's credentials which have access token
            api_key = self.config.get('API_CREDENTIALS_Sai', 'api_key')
            api_secret = self.config.get('API_CREDENTIALS_Sai', 'api_secret')
            access_token = self.config.get('API_CREDENTIALS_Sai', 'access_token')
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
            profile = self.kite.profile()
            logger.info(f"Connected to Zerodha API. User: {profile['user_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Kite connection: {str(e)}")
            return False
    
    def load_all_signals(self):
        """Load all KC Upper Limit Trending signal files"""
        pattern_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   'results', 'KC_Upper_Limit_Trending_*.xlsx')
        files = glob.glob(pattern_path)
        
        logger.info(f"Found {len(files)} KC Upper Limit Trending files")
        
        for file_path in sorted(files):
            try:
                # Extract date from filename
                filename = os.path.basename(file_path)
                date_str = filename.replace('KC_Upper_Limit_Trending_', '').replace('.xlsx', '')
                signal_date = datetime.strptime(date_str[:8], '%Y%m%d')
                
                # Fix year if it's 2025 (likely a typo, should be 2024)
                if signal_date.year == 2025:
                    signal_date = signal_date.replace(year=2024)
                
                # Load Excel file
                df = pd.read_excel(file_path)
                
                # Add signal date to each row
                df['Signal_Date'] = signal_date
                df['Signal_Time'] = date_str[9:15] if len(date_str) > 8 else '090000'
                df['File_Path'] = file_path
                
                self.signals_data.append(df)
                
            except Exception as e:
                logger.error(f"Error loading file {file_path}: {str(e)}")
        
        # Combine all signals
        if self.signals_data:
            self.all_signals = pd.concat(self.signals_data, ignore_index=True)
            logger.info(f"Total signals loaded: {len(self.all_signals)}")
            
            # Parse date properly
            self.all_signals['Signal_Date'] = pd.to_datetime(self.all_signals['Signal_Date'])
            
            return True
        else:
            logger.error("No signals data loaded")
            return False
    
    def get_historical_data(self, ticker, from_date, to_date):
        """Get historical data from Zerodha API"""
        try:
            # Get instrument token - first try to get the instrument
            try:
                instruments = self.kite.ltp([f"NSE:{ticker}"])
                if not instruments or f"NSE:{ticker}" not in instruments:
                    logger.warning(f"Could not find instrument token for {ticker}")
                    return None
                
                instrument_token = list(instruments.values())[0]['instrument_token']
            except Exception as e:
                logger.warning(f"Could not get instrument token for {ticker}: {str(e)}")
                return None
            
            # Fetch historical data
            try:
                historical_data = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval="day"
                )
                
                if historical_data:
                    df = pd.DataFrame(historical_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    return df
            except Exception as e:
                logger.warning(f"Could not fetch historical data for {ticker}: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            
        return None
    
    def analyze_signal_performance(self, signal_row, holding_periods=[1, 3, 5, 10, 20]):
        """Analyze performance of a single signal"""
        ticker = signal_row['Ticker']
        signal_date = signal_row['Signal_Date']
        entry_price = signal_row['Entry_Price']
        stop_loss = signal_row['Stop_Loss']
        target1 = signal_row['Target1']
        target2 = signal_row['Target2']
        
        logger.debug(f"Analyzing {ticker} from {signal_date} - Entry: {entry_price}, SL: {stop_loss}")
        
        # Get historical data from signal date onwards
        from_date = signal_date
        to_date = min(signal_date + timedelta(days=max(holding_periods) + 10), datetime.now())
        
        hist_data = self.get_historical_data(ticker, from_date, to_date)
        
        if hist_data is None:
            logger.warning(f"No historical data for {ticker}")
            return None
            
        if len(hist_data) < 2:
            logger.warning(f"Insufficient historical data for {ticker}: only {len(hist_data)} points")
            return None
        
        performance = {
            'Ticker': ticker,
            'Signal_Date': signal_date,
            'Entry_Price': entry_price,
            'Stop_Loss': stop_loss,
            'Target1': target1,
            'Target2': target2,
            'Pattern': signal_row.get('Pattern', 'Unknown'),
            'Probability_Score': signal_row.get('Probability_Score', 0),
            'Has_H2': signal_row.get('Has_H2', False),
            'H2_Count': signal_row.get('H2_Count', 0),
            'Trend_Strength': signal_row.get('Trend_Strength', 0),
            'KC_Distance_%': signal_row.get('KC_Distance_%', 0),
            'ADX': signal_row.get('ADX', 0),
            'Volume_Ratio': signal_row.get('Volume_Ratio', 0)
        }
        
        # Get actual entry (next day open)
        if len(hist_data) > 0:
            actual_entry = hist_data.iloc[0]['open']
            performance['Actual_Entry'] = actual_entry
            
            # Check if stopped out
            stopped_out = False
            stop_day = None
            
            for i, (idx, row) in enumerate(hist_data.iterrows()):
                if row['low'] <= stop_loss:
                    stopped_out = True
                    stop_day = i
                    performance['Stopped_Out'] = True
                    performance['Stop_Day'] = stop_day
                    performance['Exit_Price'] = stop_loss
                    break
            
            # Calculate returns for different holding periods
            for period in holding_periods:
                if period < len(hist_data):
                    if stopped_out and stop_day < period:
                        # If stopped out before this period
                        performance[f'Return_{period}D'] = ((stop_loss - actual_entry) / actual_entry) * 100
                        performance[f'Exit_{period}D'] = stop_loss
                    else:
                        # Normal exit
                        exit_price = hist_data.iloc[period]['close']
                        performance[f'Return_{period}D'] = ((exit_price - actual_entry) / actual_entry) * 100
                        performance[f'Exit_{period}D'] = exit_price
                        
                        # Check if targets hit
                        high_till_period = hist_data.iloc[:period+1]['high'].max()
                        performance[f'Target1_Hit_{period}D'] = high_till_period >= target1
                        performance[f'Target2_Hit_{period}D'] = high_till_period >= target2
                        
                        # Maximum favorable excursion
                        performance[f'Max_Gain_{period}D'] = ((high_till_period - actual_entry) / actual_entry) * 100
                        
                        # Maximum adverse excursion
                        low_till_period = hist_data.iloc[:period+1]['low'].min()
                        performance[f'Max_Loss_{period}D'] = ((low_till_period - actual_entry) / actual_entry) * 100
        
        return performance
    
    def analyze_all_signals(self, sample_size=None, days_ago_min=14):
        """Analyze all signals or a sample"""
        if not self.all_signals.empty:
            # Filter signals to be at least days_ago_min days old to ensure enough data
            cutoff_date = datetime.now() - timedelta(days=days_ago_min)
            old_enough_signals = self.all_signals[self.all_signals['Signal_Date'] <= cutoff_date]
            
            if old_enough_signals.empty:
                logger.error(f"No signals older than {days_ago_min} days found")
                return False
                
            # Sort by date to analyze most recent first
            signals_to_analyze = old_enough_signals.sort_values('Signal_Date', ascending=False)
            
            if sample_size:
                signals_to_analyze = signals_to_analyze.head(sample_size)
            
            logger.info(f"Analyzing {len(signals_to_analyze)} signals...")
            
            for i, (idx, signal) in enumerate(signals_to_analyze.iterrows()):
                try:
                    performance = self.analyze_signal_performance(signal)
                    if performance:
                        self.performance_data.append(performance)
                        
                    # Log progress
                    if (i + 1) % 10 == 0:
                        logger.info(f"Analyzed {i + 1}/{len(signals_to_analyze)} signals")
                        
                except Exception as e:
                    logger.error(f"Error analyzing signal for {signal['Ticker']} on {signal['Signal_Date']}: {str(e)}")
            
            # Convert to DataFrame
            if self.performance_data:
                self.performance_df = pd.DataFrame(self.performance_data)
                logger.info(f"Successfully analyzed {len(self.performance_df)} signals with performance data")
                return True
            else:
                logger.warning("No performance data collected")
            
        return False
    
    def generate_statistics(self):
        """Generate comprehensive statistics from performance data"""
        if not hasattr(self, 'performance_df') or self.performance_df.empty:
            logger.error("No performance data to analyze")
            return None
        
        stats = {}
        
        # Overall statistics
        holding_periods = [1, 3, 5, 10, 20]
        
        for period in holding_periods:
            col_name = f'Return_{period}D'
            if col_name in self.performance_df.columns:
                returns = self.performance_df[col_name].dropna()
                
                stats[f'{period}D_Stats'] = {
                    'Count': len(returns),
                    'Win_Rate': (returns > 0).sum() / len(returns) * 100,
                    'Avg_Return': returns.mean(),
                    'Median_Return': returns.median(),
                    'Std_Dev': returns.std(),
                    'Max_Return': returns.max(),
                    'Min_Return': returns.min(),
                    'Sharpe_Ratio': returns.mean() / returns.std() if returns.std() > 0 else 0
                }
                
                # Target achievement rates
                if f'Target1_Hit_{period}D' in self.performance_df.columns:
                    stats[f'{period}D_Stats']['Target1_Hit_Rate'] = \
                        self.performance_df[f'Target1_Hit_{period}D'].sum() / len(returns) * 100
                
                if f'Target2_Hit_{period}D' in self.performance_df.columns:
                    stats[f'{period}D_Stats']['Target2_Hit_Rate'] = \
                        self.performance_df[f'Target2_Hit_{period}D'].sum() / len(returns) * 100
        
        # Pattern-wise statistics
        if 'Pattern' in self.performance_df.columns:
            pattern_stats = {}
            for pattern in self.performance_df['Pattern'].unique():
                pattern_data = self.performance_df[self.performance_df['Pattern'] == pattern]
                if len(pattern_data) >= 5:  # Only analyze patterns with enough samples
                    pattern_stats[pattern] = {
                        'Count': len(pattern_data),
                        'Avg_3D_Return': pattern_data['Return_3D'].mean() if 'Return_3D' in pattern_data else None,
                        'Win_Rate_3D': (pattern_data['Return_3D'] > 0).sum() / len(pattern_data) * 100 
                                       if 'Return_3D' in pattern_data else None,
                        'Avg_5D_Return': pattern_data['Return_5D'].mean() if 'Return_5D' in pattern_data else None,
                        'Win_Rate_5D': (pattern_data['Return_5D'] > 0).sum() / len(pattern_data) * 100 
                                       if 'Return_5D' in pattern_data else None
                    }
            stats['Pattern_Stats'] = pattern_stats
        
        # H2 analysis
        if 'Has_H2' in self.performance_df.columns and 'Return_3D' in self.performance_df.columns:
            h2_signals = self.performance_df[self.performance_df['Has_H2'] == True]
            non_h2_signals = self.performance_df[self.performance_df['Has_H2'] == False]
            
            stats['H2_Analysis'] = {
                'H2_Count': len(h2_signals),
                'Non_H2_Count': len(non_h2_signals),
                'H2_Avg_Return_3D': h2_signals['Return_3D'].mean() if len(h2_signals) > 0 else None,
                'Non_H2_Avg_Return_3D': non_h2_signals['Return_3D'].mean() if len(non_h2_signals) > 0 else None,
                'H2_Win_Rate_3D': (h2_signals['Return_3D'] > 0).sum() / len(h2_signals) * 100 if len(h2_signals) > 0 else None,
                'Non_H2_Win_Rate_3D': (non_h2_signals['Return_3D'] > 0).sum() / len(non_h2_signals) * 100 if len(non_h2_signals) > 0 else None
            }
        
        # Trend strength analysis
        if 'Trend_Strength' in self.performance_df.columns and 'Return_3D' in self.performance_df.columns:
            # Categorize trend strength
            self.performance_df['Trend_Category'] = pd.cut(self.performance_df['Trend_Strength'], 
                                                          bins=[0, 50, 70, 100], 
                                                          labels=['Weak', 'Medium', 'Strong'])
            trend_stats = self.performance_df.groupby('Trend_Category')['Return_3D'].agg(['mean', 'count'])
            trend_stats['win_rate'] = self.performance_df.groupby('Trend_Category')['Return_3D'].apply(lambda x: (x > 0).sum() / len(x) * 100)
            stats['Trend_Strength_Stats'] = trend_stats.to_dict()
        
        # Stop loss statistics
        if 'Stopped_Out' in self.performance_df.columns:
            stop_rate = self.performance_df['Stopped_Out'].sum() / len(self.performance_df) * 100
            stats['Stop_Loss_Rate'] = stop_rate
            
            if 'Stop_Day' in self.performance_df.columns:
                avg_stop_day = self.performance_df[self.performance_df['Stopped_Out'] == True]['Stop_Day'].mean()
                stats['Avg_Stop_Day'] = avg_stop_day
        
        return stats
    
    def save_results(self):
        """Save analysis results to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save performance data
        if hasattr(self, 'performance_df'):
            output_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/kc_upper_limit_performance_{timestamp}.xlsx'
            self.performance_df.to_excel(output_file, index=False)
            logger.info(f"Performance data saved to {output_file}")
        
        # Save statistics
        stats = self.generate_statistics()
        if stats:
            stats_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/kc_upper_limit_stats_{timestamp}.json'
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=4, default=str)
            logger.info(f"Statistics saved to {stats_file}")
            
            # Print summary
            print("\n=== KC UPPER LIMIT TRENDING PATTERN ANALYSIS SUMMARY ===")
            print(f"\nTotal Signals Analyzed: {len(self.performance_df)}")
            
            print("\n--- Returns by Holding Period ---")
            for period in [1, 3, 5, 10, 20]:
                if f'{period}D_Stats' in stats:
                    period_stats = stats[f'{period}D_Stats']
                    print(f"\n{period}-Day Holding Period:")
                    print(f"  Win Rate: {period_stats['Win_Rate']:.2f}%")
                    print(f"  Avg Return: {period_stats['Avg_Return']:.2f}%")
                    print(f"  Sharpe Ratio: {period_stats['Sharpe_Ratio']:.2f}")
                    if 'Target1_Hit_Rate' in period_stats:
                        print(f"  Target1 Hit Rate: {period_stats['Target1_Hit_Rate']:.2f}%")
            
            # Print pattern performance
            if 'Pattern_Stats' in stats:
                print("\n--- Pattern Performance (3-Day Returns) ---")
                pattern_stats = stats['Pattern_Stats']
                for pattern, data in sorted(pattern_stats.items(), key=lambda x: x[1].get('Avg_3D_Return', 0), reverse=True):
                    print(f"\n{pattern}:")
                    print(f"  Count: {data['Count']}")
                    print(f"  Avg Return: {data.get('Avg_3D_Return', 0):.2f}%")
                    print(f"  Win Rate: {data.get('Win_Rate_3D', 0):.2f}%")
            
            # Print H2 analysis
            if 'H2_Analysis' in stats:
                h2_stats = stats['H2_Analysis']
                print("\n--- H2 Pattern Analysis ---")
                print(f"H2 Signals: {h2_stats['H2_Count']} | Non-H2 Signals: {h2_stats['Non_H2_Count']}")
                if h2_stats.get('H2_Avg_Return_3D') is not None:
                    print(f"H2 Avg Return (3D): {h2_stats['H2_Avg_Return_3D']:.2f}% | Win Rate: {h2_stats.get('H2_Win_Rate_3D', 0):.2f}%")
                if h2_stats.get('Non_H2_Avg_Return_3D') is not None:
                    print(f"Non-H2 Avg Return (3D): {h2_stats['Non_H2_Avg_Return_3D']:.2f}% | Win Rate: {h2_stats.get('Non_H2_Win_Rate_3D', 0):.2f}%")
            
            if 'Stop_Loss_Rate' in stats:
                print(f"\nStop Loss Hit Rate: {stats['Stop_Loss_Rate']:.2f}%")
    
    def run_analysis(self, sample_size=None):
        """Run complete analysis"""
        # Load signals
        if not self.load_all_signals():
            logger.error("Failed to load signals")
            return False
        
        # Setup Kite connection
        if not self.setup_kite_connection():
            logger.error("Failed to setup Kite connection")
            return False
        
        # Analyze signals
        if not self.analyze_all_signals(sample_size):
            logger.error("Failed to analyze signals")
            return False
        
        # Save results
        self.save_results()
        
        return True


def main():
    analyzer = KCUpperLimitAnalyzer()
    
    # Run analysis on recent signals (last 100)
    analyzer.run_analysis(sample_size=100)


if __name__ == "__main__":
    main()