#!/usr/bin/env python3
"""
Simple Historical Data Backfill
Directly processes scanner Excel files to build training dataset
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import glob
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_date_from_filename(filename):
    """Extract date from scanner filename format"""
    try:
        # Format: Scanner_Name_YYYYMMDD_HHMMSS.xlsx
        parts = os.path.basename(filename).replace('.xlsx', '').split('_')
        for i, part in enumerate(parts):
            if len(part) == 8 and part.isdigit():
                return datetime.strptime(part, '%Y%m%d')
    except:
        pass
    return None

def process_scanner_files(days_back=60):
    """Process scanner files from the past N days"""
    
    base_path = '/Users/maverick/PycharmProjects/India-TS/Daily'
    output_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data/historical'
    os.makedirs(output_path, exist_ok=True)
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    # Find all scanner files
    patterns = {
        'long_reversal': f'{base_path}/results/Long_Reversal_Daily_*.xlsx',
        'short_reversal': f'{base_path}/results-s/Short_Reversal_Daily_*.xlsx',
    }
    
    # Collect data by date
    data_by_date = {}
    
    for scanner_type, pattern in patterns.items():
        files = glob.glob(pattern)
        logger.info(f"Found {len(files)} {scanner_type} files")
        
        for filepath in files:
            date = extract_date_from_filename(filepath)
            
            if date and date >= cutoff_date:
                if date not in data_by_date:
                    data_by_date[date] = {'long': [], 'short': [], 'files': []}
                
                try:
                    df = pd.read_excel(filepath)
                    if not df.empty:
                        ticker_col = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
                        if ticker_col in df.columns:
                            tickers = df[ticker_col].tolist()
                            
                            if 'long' in scanner_type:
                                data_by_date[date]['long'].extend(tickers)
                            else:
                                data_by_date[date]['short'].extend(tickers)
                            
                            data_by_date[date]['files'].append(os.path.basename(filepath))
                except Exception as e:
                    logger.debug(f"Error reading {filepath}: {e}")
    
    # Build feature dataset
    all_features = []
    
    for date in sorted(data_by_date.keys()):
        data = data_by_date[date]
        
        # Remove duplicates
        long_stocks = list(set(data['long']))
        short_stocks = list(set(data['short']))
        
        long_count = len(long_stocks)
        short_count = len(short_stocks)
        total = long_count + short_count
        
        if total > 0:
            # Calculate features
            features = {
                'timestamp': date,
                'date': date.strftime('%Y-%m-%d'),
                'long_count': long_count,
                'short_count': short_count,
                'total_stocks': total,
                'long_short_ratio': long_count / (short_count if short_count > 0 else 1),
                'bullish_percent': (long_count / total) * 100,
                'bearish_percent': (short_count / total) * 100,
                'market_breadth': long_count - short_count,
                'normalized_breadth': (long_count - short_count) / total,
                'volatility_proxy': abs(long_count - short_count) / total,
                'momentum_score': (long_count - short_count) / (long_count + short_count + 1),
            }
            
            # Add regime label based on simple rules
            if features['bullish_percent'] > 60:
                features['regime'] = 'bullish'
            elif features['bullish_percent'] < 40:
                features['regime'] = 'bearish'
            else:
                features['regime'] = 'neutral'
            
            # Add trend based on ratio
            if features['long_short_ratio'] > 2:
                features['trend'] = 'strong_up'
            elif features['long_short_ratio'] > 1.2:
                features['trend'] = 'up'
            elif features['long_short_ratio'] < 0.5:
                features['trend'] = 'strong_down'
            elif features['long_short_ratio'] < 0.8:
                features['trend'] = 'down'
            else:
                features['trend'] = 'sideways'
            
            all_features.append(features)
    
    if all_features:
        # Create DataFrame
        df = pd.DataFrame(all_features)
        df = df.sort_values('timestamp')
        
        # Add rolling features
        df['ma_5_bullish'] = df['bullish_percent'].rolling(5, min_periods=1).mean()
        df['ma_10_bullish'] = df['bullish_percent'].rolling(10, min_periods=1).mean()
        df['ma_20_bullish'] = df['bullish_percent'].rolling(20, min_periods=1).mean()
        
        df['breadth_change'] = df['market_breadth'].diff()
        df['breadth_acceleration'] = df['breadth_change'].diff()
        
        # Save to parquet
        output_file = f"{output_path}/backfilled_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        df.to_parquet(output_file, index=False)
        
        # Save to CSV for easy viewing
        csv_file = output_file.replace('.parquet', '.csv')
        df.to_csv(csv_file, index=False)
        
        # Print summary
        print("\n" + "="*60)
        print("BACKFILL COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Total days: {len(df)}")
        print(f"Total data points: {len(df)}")
        
        print("\nRegime Distribution:")
        for regime, count in df['regime'].value_counts().items():
            print(f"  {regime}: {count} ({count/len(df)*100:.1f}%)")
        
        print("\nTrend Distribution:")
        for trend, count in df['trend'].value_counts().items():
            print(f"  {trend}: {count} ({count/len(df)*100:.1f}%)")
        
        print(f"\nFiles saved:")
        print(f"  - Parquet: {output_file}")
        print(f"  - CSV: {csv_file}")
        
        # Check if sufficient for training
        if len(df) >= 30:
            print(f"\n✅ Sufficient data for initial model training ({len(df)} days)")
        else:
            print(f"\n⚠️  Need more data for robust training (have {len(df)} days, recommend 30+)")
        
        return df
    else:
        print("\n❌ No data found in the specified date range")
        return None

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Historical Backfill')
    parser.add_argument('--days', type=int, default=60, help='Days to look back')
    args = parser.parse_args()
    
    print(f"Starting backfill for past {args.days} days...")
    result = process_scanner_files(args.days)
    
    if result is not None:
        print(f"\n✅ Backfill successful!")
    else:
        print(f"\n❌ Backfill failed")