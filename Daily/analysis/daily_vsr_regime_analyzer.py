#!/usr/bin/env python3
"""
Daily VSR and Market Regime Correlation Analyzer
Analyzes Daily reversal signals over past month and correlates with market regimes
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import glob
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DailyVSRRegimeAnalyzer:
    def __init__(self, lookback_days=30):
        """Initialize analyzer for daily signals"""
        self.lookback_days = lookback_days
        self.base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"
        
        # Date range
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=lookback_days)
        
        # Data storage
        self.daily_signals = {
            'long': {},
            'short': {}
        }
        self.regime_data = []
        
    def load_market_regime_data(self):
        """Load historical market regime data"""
        regime_file = os.path.join(self.base_dir, "Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json")
        
        if os.path.exists(regime_file):
            with open(regime_file, 'r') as f:
                data = json.load(f)
                
            for item in data:
                date = datetime.strptime(item['date'], '%Y-%m-%d')
                if self.start_date <= date <= self.end_date:
                    self.regime_data.append({
                        'date': date,
                        'sma20': item['sma_breadth']['sma20_percent'],
                        'sma50': item['sma_breadth']['sma50_percent'],
                        'regime': item['market_regime'],
                        'score': item['market_score']
                    })
            
            logger.info(f"Loaded {len(self.regime_data)} days of regime data")
            return True
        return False
    
    def classify_regime(self, sma20):
        """Classify market regime based on SMA20 breadth"""
        if sma20 > 70:
            return 'Strong Bullish'
        elif sma20 > 60:
            return 'Bullish'
        elif sma20 > 50:
            return 'Neutral-Bullish'
        elif sma20 > 40:
            return 'Neutral'
        elif sma20 > 30:
            return 'Bearish'
        else:
            return 'Strong Bearish'
    
    def parse_daily_scanners(self):
        """Parse daily scanner files (Long/Short Reversal Daily)"""
        logger.info(f"Parsing daily scanner files from {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        
        # Directories to search
        scanner_dirs = [
            os.path.join(self.base_dir, "results"),
            os.path.join(self.base_dir, "results-s"),
        ]
        
        for scanner_dir in scanner_dirs:
            if not os.path.exists(scanner_dir):
                continue
            
            # Long Reversal Daily
            long_files = glob.glob(os.path.join(scanner_dir, "Long_Reversal_Daily_*.xlsx"))
            for filepath in long_files:
                self.parse_scanner_file(filepath, 'long')
            
            # Short Reversal Daily  
            short_files = glob.glob(os.path.join(scanner_dir, "Short_Reversal_Daily_*.xlsx"))
            for filepath in short_files:
                self.parse_scanner_file(filepath, 'short')
    
    def parse_scanner_file(self, filepath, signal_type):
        """Parse a scanner Excel file"""
        try:
            filename = os.path.basename(filepath)
            # Extract date from filename
            date_parts = filename.split('_')
            for part in date_parts:
                if len(part) == 8 and part.startswith('202'):
                    try:
                        file_date = datetime.strptime(part, '%Y%m%d')
                        if self.start_date <= file_date <= self.end_date:
                            df = pd.read_excel(filepath)
                            
                            if 'Ticker' in df.columns:
                                date_str = file_date.strftime('%Y-%m-%d')
                                if date_str not in self.daily_signals[signal_type]:
                                    self.daily_signals[signal_type][date_str] = []
                                
                                for _, row in df.iterrows():
                                    ticker_data = {
                                        'ticker': row.get('Ticker', ''),
                                        'score': row.get('Score', 0),
                                        'entry': row.get('Entry', row.get('Close', 0)),
                                        'stop_loss': row.get('Stop Loss', row.get('SL', 0)),
                                        'target': row.get('Target', row.get('TP', 0))
                                    }
                                    self.daily_signals[signal_type][date_str].append(ticker_data)
                        break
                    except:
                        continue
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
    
    def analyze_performance_by_regime(self):
        """Analyze signal performance across different market regimes"""
        results = []
        
        # Create regime lookup
        regime_lookup = {r['date'].strftime('%Y-%m-%d'): r for r in self.regime_data}
        
        # Analyze each day's signals
        for signal_type in ['long', 'short']:
            for date_str, signals in self.daily_signals[signal_type].items():
                if date_str in regime_lookup:
                    regime_info = regime_lookup[date_str]
                    
                    for signal in signals:
                        results.append({
                            'date': date_str,
                            'ticker': signal['ticker'],
                            'type': signal_type,
                            'score': signal['score'],
                            'sma20': regime_info['sma20'],
                            'sma50': regime_info['sma50'],
                            'regime': self.classify_regime(regime_info['sma20']),
                            'market_score': regime_info['score']
                        })
        
        return pd.DataFrame(results)
    
    def generate_analysis_report(self):
        """Generate comprehensive analysis report"""
        # Load data
        if not self.load_market_regime_data():
            logger.error("Failed to load regime data")
            return
        
        self.parse_daily_scanners()
        
        # Analyze
        df = self.analyze_performance_by_regime()
        
        if df.empty:
            logger.warning("No data to analyze")
            return
        
        print("\n" + "="*80)
        print("DAILY VSR SIGNALS - MARKET REGIME CORRELATION ANALYSIS")
        print("="*80)
        print(f"\nAnalysis Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Total Signals: {len(df)} ({len(df[df['type']=='long'])} long, {len(df[df['type']=='short'])} short)")
        
        # Signals by regime
        print("\n" + "-"*80)
        print("SIGNAL DISTRIBUTION BY MARKET REGIME:")
        print("-"*80)
        
        regime_stats = df.groupby(['regime', 'type']).size().unstack(fill_value=0)
        print(regime_stats)
        
        # Average scores by regime
        print("\n" + "-"*80)
        print("AVERAGE SIGNAL SCORES BY REGIME:")
        print("-"*80)
        
        avg_scores = df.groupby(['regime', 'type'])['score'].mean().unstack(fill_value=0)
        print(avg_scores.round(1))
        
        # Correlation analysis
        print("\n" + "-"*80)
        print("CORRELATION ANALYSIS:")
        print("-"*80)
        
        # Calculate correlations
        if 'score' in df.columns and 'sma20' in df.columns:
            corr_score_breadth = df['score'].corr(df['sma20'])
            print(f"Signal Score vs SMA20 Breadth: {corr_score_breadth:.3f}")
        
        # Regime transitions
        print("\n" + "-"*80)
        print("REGIME TRANSITIONS DURING PERIOD:")
        print("-"*80)
        
        regime_df = pd.DataFrame(self.regime_data)
        if not regime_df.empty:
            regime_df['regime_class'] = regime_df['sma20'].apply(self.classify_regime)
            regime_changes = regime_df[regime_df['regime_class'].ne(regime_df['regime_class'].shift())]
            
            for _, row in regime_changes.iterrows():
                print(f"{row['date'].strftime('%Y-%m-%d')}: {row['regime_class']} (SMA20: {row['sma20']:.1f}%)")
        
        # Signal persistence
        print("\n" + "-"*80)
        print("DAILY SIGNAL PERSISTENCE:")
        print("-"*80)
        
        # Count ticker occurrences
        ticker_counts = df.groupby(['ticker', 'type']).size().reset_index(name='occurrences')
        
        # Most persistent signals
        print("\nMost Persistent Daily Signals (Top 10):")
        top_persistent = ticker_counts.nlargest(10, 'occurrences')
        for _, row in top_persistent.iterrows():
            print(f"  {row['ticker']:<12} ({row['type']:<5}): {row['occurrences']} days")
        
        # Regime preference analysis
        print("\n" + "-"*80)
        print("SIGNAL TYPE PREFERENCE BY REGIME:")
        print("-"*80)
        
        regime_preference = df.groupby('regime')['type'].value_counts(normalize=True).unstack(fill_value=0)
        print((regime_preference * 100).round(1))
        
        return df

# Run the analysis
if __name__ == "__main__":
    analyzer = DailyVSRRegimeAnalyzer(lookback_days=30)
    df = analyzer.generate_analysis_report()
    
    # Save results
    if df is not None and not df.empty:
        output_file = f"Daily/analysis/daily_vsr_regime_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")