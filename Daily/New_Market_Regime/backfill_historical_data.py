#!/usr/bin/env python3
"""
Historical Data Backfill Script
Processes existing scanner results from the past 30-60 days to build training dataset
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
from tqdm import tqdm

# Add parent directory to path
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, '/Users/maverick/PycharmProjects/India-TS')

# Import pipeline components
from src.ingestion.data_ingestor import MarketDataIngestor
from src.features.feature_builder import FeatureBuilder
from src.features.feature_store import FeatureStore
from src.features.regime_labeler import RegimeLabeler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HistoricalDataBackfill:
    """Backfills historical data from existing scanner results"""
    
    def __init__(self, days_back=60):
        self.days_back = days_back
        self.base_path = '/Users/maverick/PycharmProjects/India-TS/Daily'
        self.output_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data'
        
        # Initialize components
        self.ingestor = MarketDataIngestor()
        self.feature_builder = FeatureBuilder()
        self.feature_store = FeatureStore()
        self.regime_labeler = RegimeLabeler()
        
    def find_historical_files(self):
        """Find all historical scanner result files"""
        cutoff_date = datetime.now() - timedelta(days=self.days_back)
        
        # Define scanner paths
        scanner_patterns = {
            'long_reversal': f'{self.base_path}/results/Long_Reversal_Daily_*.xlsx',
            'short_reversal': f'{self.base_path}/results-s/Short_Reversal_Daily_*.xlsx',
            'kc_upper': f'{self.base_path}/results/KC_Upper_Limit_Trending_*.xlsx',
            'kc_lower': f'{self.base_path}/results/KC_Lower_Limit_Trending_*.xlsx',
        }
        
        historical_files = {}
        
        for scanner_name, pattern in scanner_patterns.items():
            files = glob.glob(pattern)
            valid_files = []
            
            for file_path in files:
                try:
                    # Extract date from filename
                    filename = os.path.basename(file_path)
                    # Parse date from filename format: Scanner_Name_YYYYMMDD_HHMMSS.xlsx
                    date_parts = filename.split('_')
                    if len(date_parts) >= 4:
                        date_str = date_parts[-2]  # YYYYMMDD
                        file_date = datetime.strptime(date_str, '%Y%m%d')
                        
                        if file_date >= cutoff_date:
                            valid_files.append({
                                'path': file_path,
                                'date': file_date,
                                'filename': filename
                            })
                except Exception as e:
                    logger.debug(f"Could not parse date from {filename}: {e}")
                    continue
            
            # Sort by date
            valid_files.sort(key=lambda x: x['date'])
            historical_files[scanner_name] = valid_files
            
        return historical_files
    
    def process_historical_day(self, date, scanner_files):
        """Process scanner data for a specific historical date"""
        try:
            logger.info(f"Processing data for {date.strftime('%Y-%m-%d')}")
            
            # Aggregate scanner data
            aggregated_data = {
                'timestamp': date.isoformat(),
                'long_stocks': [],
                'short_stocks': [],
                'scanner_metrics': {}
            }
            
            for scanner_name, file_info in scanner_files.items():
                if file_info:
                    try:
                        df = pd.read_excel(file_info['path'])
                        
                        # Extract tickers
                        if 'Ticker' in df.columns:
                            tickers = df['Ticker'].tolist()
                        elif 'Symbol' in df.columns:
                            tickers = df['Symbol'].tolist()
                        else:
                            continue
                        
                        # Categorize by scanner type
                        if 'long' in scanner_name.lower():
                            aggregated_data['long_stocks'].extend(tickers)
                        elif 'short' in scanner_name.lower():
                            aggregated_data['short_stocks'].extend(tickers)
                        
                        aggregated_data['scanner_metrics'][scanner_name] = {
                            'count': len(tickers),
                            'tickers': tickers[:10]  # Store sample
                        }
                        
                    except Exception as e:
                        logger.error(f"Error processing {scanner_name} file: {e}")
                        continue
            
            # Remove duplicates
            aggregated_data['long_stocks'] = list(set(aggregated_data['long_stocks']))
            aggregated_data['short_stocks'] = list(set(aggregated_data['short_stocks']))
            
            # Calculate market breadth
            long_count = len(aggregated_data['long_stocks'])
            short_count = len(aggregated_data['short_stocks'])
            total_stocks = long_count + short_count
            
            if total_stocks > 0:
                market_breadth = {
                    'long_count': long_count,
                    'short_count': short_count,
                    'total_stocks': total_stocks,
                    'long_short_ratio': long_count / (short_count if short_count > 0 else 1),
                    'bullish_percent': (long_count / total_stocks) * 100
                }
                aggregated_data['market_breadth'] = market_breadth
                
                # Build features
                # Save the data temporarily for feature builder to pick up
                temp_file = f"{self.output_path}/raw/temp_backfill_{date.strftime('%Y%m%d')}.json"
                os.makedirs(os.path.dirname(temp_file), exist_ok=True)
                with open(temp_file, 'w') as f:
                    json.dump(aggregated_data, f, default=str)
                
                # Build features using the date
                features_df = self.feature_builder.build_feature_vector(date=date.strftime('%Y-%m-%d'))
                
                if features_df is not None and not features_df.empty:
                    # Add timestamp
                    features_df['timestamp'] = date
                    
                    # Label the data
                    labeled_df = self.regime_labeler.label_data(features_df)
                    
                    return labeled_df
            
        except Exception as e:
            logger.error(f"Error processing date {date}: {e}")
        
        return None
    
    def run_backfill(self):
        """Execute the historical data backfill"""
        logger.info(f"Starting historical data backfill for past {self.days_back} days")
        
        # Find historical files
        historical_files = self.find_historical_files()
        
        # Group files by date
        files_by_date = {}
        
        for scanner_name, files in historical_files.items():
            for file_info in files:
                date = file_info['date']
                if date not in files_by_date:
                    files_by_date[date] = {}
                files_by_date[date][scanner_name] = file_info
        
        # Sort dates
        sorted_dates = sorted(files_by_date.keys())
        
        logger.info(f"Found data for {len(sorted_dates)} trading days")
        
        if len(sorted_dates) == 0:
            logger.warning("No historical data found!")
            return None
        
        # Process each date
        all_data = []
        
        for date in tqdm(sorted_dates, desc="Processing historical data"):
            labeled_data = self.process_historical_day(date, files_by_date[date])
            
            if labeled_data is not None:
                all_data.append(labeled_data)
        
        if all_data:
            # Combine all data
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Save to feature store
            feature_version = self.feature_store.save_features(
                combined_df.drop(['regime', 'regime_label', 'confidence'], axis=1, errors='ignore'),
                metadata={'source': 'historical_backfill', 'days': self.days_back}
            )
            
            # Save labeled data
            output_file = f"{self.output_path}/historical/backfilled_data_{datetime.now().strftime('%Y%m%d')}.parquet"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            combined_df.to_parquet(output_file)
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("BACKFILL SUMMARY")
            logger.info("="*50)
            logger.info(f"Total days processed: {len(sorted_dates)}")
            logger.info(f"Total data points: {len(combined_df)}")
            logger.info(f"Date range: {combined_df['timestamp'].min()} to {combined_df['timestamp'].max()}")
            
            if 'regime_label' in combined_df.columns:
                logger.info("\nRegime Distribution:")
                for regime, count in combined_df['regime_label'].value_counts().items():
                    logger.info(f"  {regime}: {count} ({count/len(combined_df)*100:.1f}%)")
            
            logger.info(f"\nData saved to: {output_file}")
            logger.info(f"Feature version: {feature_version}")
            
            return combined_df
        else:
            logger.warning("No valid data could be processed from historical files")
            return None

def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Historical Data Backfill')
    parser.add_argument('--days', type=int, default=60,
                       help='Number of days to backfill (default: 60)')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode (process only 5 days)')
    
    args = parser.parse_args()
    
    # Adjust days for test mode
    days_to_process = 5 if args.test else args.days
    
    # Create backfill instance
    backfill = HistoricalDataBackfill(days_back=days_to_process)
    
    # Run backfill
    result = backfill.run_backfill()
    
    if result is not None:
        print(f"\n✅ Successfully backfilled {len(result)} data points")
        print(f"📊 Data spans {result['timestamp'].nunique()} unique days")
        
        # Check if we have enough data for training
        if len(result) >= 100:
            print(f"✅ Sufficient data for Phase 3 model training!")
        else:
            print(f"⚠️  Need more data: Have {len(result)}, need at least 100 points")
    else:
        print("\n❌ Backfill failed - check logs for details")
        sys.exit(1)

if __name__ == '__main__':
    main()