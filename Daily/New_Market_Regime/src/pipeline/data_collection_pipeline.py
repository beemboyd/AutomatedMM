#!/usr/bin/env python3
"""
Automated Data Collection Pipeline
Runs every 30 minutes during market hours to collect diverse market regime data
"""

import os
import sys
import json
import time
import logging
import schedule
import pandas as pd
from datetime import datetime, time as dt_time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.data_ingestor import MarketDataIngestor
from features.feature_builder import FeatureBuilder
from features.regime_labeler import RegimeLabeler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataCollectionPipeline:
    """
    Automated pipeline for collecting market regime data
    """
    
    def __init__(self, collection_interval_minutes=30):
        """
        Initialize the data collection pipeline
        
        Args:
            collection_interval_minutes: How often to collect data (default: 30)
        """
        self.collection_interval = collection_interval_minutes
        self.data_dir = Path(__file__).parent.parent.parent / 'data'
        self.collection_log_file = self.data_dir / 'collection_log.json'
        
        # Initialize components
        self.ingestor = MarketDataIngestor()
        self.feature_builder = FeatureBuilder()
        self.regime_labeler = RegimeLabeler()
        
        # Load collection history
        self.collection_history = self.load_collection_history()
        
    def load_collection_history(self):
        """Load collection history from log file"""
        if self.collection_log_file.exists():
            with open(self.collection_log_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_collection_history(self):
        """Save collection history to log file"""
        with open(self.collection_log_file, 'w') as f:
            json.dump(self.collection_history, f, indent=2, default=str)
    
    def is_market_hours(self):
        """Check if current time is within market hours"""
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)
        
        return market_open <= current_time <= market_close
    
    def run_collection_cycle(self):
        """Run a single data collection cycle"""
        try:
            timestamp = datetime.now()
            logger.info("="*50)
            logger.info(f"Starting collection cycle at {timestamp}")
            
            # Step 1: Ingest raw data
            logger.info("Step 1: Ingesting raw data...")
            raw_data = self.ingestor.run_ingestion_cycle()
            
            if not raw_data:
                logger.warning("No data ingested, skipping cycle")
                return None
            
            # Step 2: Build features
            logger.info("Step 2: Building features...")
            # Pass None to use the latest data file
            features = self.feature_builder.build_feature_vector(date=None)
            
            if features is None or features.empty:
                logger.warning("No features generated, skipping cycle")
                return None
            
            # Step 3: Label regimes
            logger.info("Step 3: Labeling regimes...")
            labeled_data = self.regime_labeler.label_features_dataframe(features)
            
            # Step 4: Log collection
            collection_entry = {
                'timestamp': timestamp,
                'raw_data_file': f"unified_data_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
                'features_file': f"features_v{timestamp.strftime('%Y%m%d_%H%M%S')}.parquet",
                'labeled_file': f"labeled_features_v{timestamp.strftime('%Y%m%d_%H%M%S')}.parquet",
                'market_metrics': {
                    'long_short_ratio': float(features['long_short_ratio'].iloc[-1]) if 'long_short_ratio' in features else None,
                    'bullish_percent': float(features['bullish_percent'].iloc[-1]) if 'bullish_percent' in features else None,
                    'regime': labeled_data['regime_label'].iloc[-1] if not labeled_data.empty else None,
                    'confidence': float(labeled_data['regime_confidence'].iloc[-1]) if not labeled_data.empty else None
                }
            }
            
            self.collection_history.append(collection_entry)
            self.save_collection_history()
            
            logger.info(f"✅ Collection cycle completed successfully")
            logger.info(f"   Regime: {collection_entry['market_metrics']['regime']}")
            logger.info(f"   L/S Ratio: {collection_entry['market_metrics']['long_short_ratio']:.2f}")
            logger.info(f"   Bullish %: {collection_entry['market_metrics']['bullish_percent']:.1f}%")
            
            return collection_entry
            
        except Exception as e:
            logger.error(f"Error in collection cycle: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def validate_collected_data(self):
        """Validate collected data for quality and diversity"""
        logger.info("="*50)
        logger.info("Validating collected data...")
        
        # Load all labeled data files
        labeled_files = list((self.data_dir / 'labels').glob('labeled_features_v*.parquet'))
        
        if not labeled_files:
            logger.warning("No labeled data files found")
            return
        
        # Combine all data
        all_data = []
        for file in labeled_files:
            try:
                df = pd.read_parquet(file)
                all_data.append(df)
            except Exception as e:
                logger.warning(f"Error reading {file}: {e}")
        
        if not all_data:
            logger.warning("No data could be loaded")
            return
        
        combined_data = pd.concat(all_data, ignore_index=True)
        
        # Validation metrics
        logger.info(f"Total data points collected: {len(combined_data)}")
        
        # Regime diversity
        regime_counts = combined_data['regime_label'].value_counts()
        logger.info("\nRegime distribution:")
        for regime, count in regime_counts.items():
            pct = (count / len(combined_data)) * 100
            logger.info(f"  {regime}: {count} ({pct:.1f}%)")
        
        # Check for regime diversity issues
        if len(regime_counts) == 1:
            logger.warning("⚠️ Only one regime detected - need more diverse market conditions")
        elif any((count / len(combined_data)) > 0.8 for count in regime_counts.values):
            logger.warning("⚠️ Severe regime imbalance detected (>80% single regime)")
        else:
            logger.info("✅ Good regime diversity")
        
        # Feature quality
        feature_cols = [col for col in combined_data.columns 
                       if col not in ['timestamp', 'regime_label', 'regime_confidence']]
        
        logger.info(f"\nFeature quality (non-null %):")
        for col in feature_cols[:10]:  # Show first 10 features
            non_null_pct = (combined_data[col].notna().sum() / len(combined_data)) * 100
            logger.info(f"  {col}: {non_null_pct:.1f}%")
        
        # Time coverage
        if 'timestamp' in combined_data.columns:
            combined_data['timestamp'] = pd.to_datetime(combined_data['timestamp'])
            date_range = combined_data['timestamp'].dt.date.unique()
            logger.info(f"\nData collected across {len(date_range)} days")
            logger.info(f"Date range: {min(date_range)} to {max(date_range)}")
        
        # Market breadth statistics
        if 'long_short_ratio' in combined_data.columns:
            logger.info(f"\nMarket breadth statistics:")
            logger.info(f"  L/S Ratio - Mean: {combined_data['long_short_ratio'].mean():.2f}")
            logger.info(f"  L/S Ratio - Min: {combined_data['long_short_ratio'].min():.2f}")
            logger.info(f"  L/S Ratio - Max: {combined_data['long_short_ratio'].max():.2f}")
        
        return combined_data
    
    def run_scheduled(self):
        """Run data collection on schedule during market hours"""
        logger.info(f"Starting scheduled data collection (every {self.collection_interval} minutes)")
        
        # Schedule collection
        schedule.every(self.collection_interval).minutes.do(self.run_if_market_open)
        
        # Also run immediately if market is open
        self.run_if_market_open()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def run_if_market_open(self):
        """Run collection only if market is open"""
        if self.is_market_hours():
            self.run_collection_cycle()
        else:
            logger.info("Market closed, skipping collection")
    
    def run_once(self):
        """Run a single collection cycle (for testing)"""
        return self.run_collection_cycle()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Data Collection Pipeline')
    parser.add_argument('--mode', choices=['once', 'scheduled', 'validate'], 
                       default='once',
                       help='Run mode: once, scheduled, or validate')
    parser.add_argument('--interval', type=int, default=30,
                       help='Collection interval in minutes (default: 30)')
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = DataCollectionPipeline(collection_interval_minutes=args.interval)
    
    if args.mode == 'once':
        # Run single collection
        result = pipeline.run_once()
        if result:
            print(f"\n✅ Data collected successfully")
            print(f"   Regime: {result['market_metrics']['regime']}")
            print(f"   Confidence: {result['market_metrics']['confidence']:.1%}")
    
    elif args.mode == 'scheduled':
        # Run on schedule
        try:
            pipeline.run_scheduled()
        except KeyboardInterrupt:
            print("\n⏹ Scheduled collection stopped by user")
    
    elif args.mode == 'validate':
        # Validate collected data
        data = pipeline.validate_collected_data()
        if data is not None:
            print(f"\n✅ Validation complete")
            print(f"   Total samples: {len(data)}")
            print(f"   Unique regimes: {data['regime_label'].nunique()}")

if __name__ == '__main__':
    main()