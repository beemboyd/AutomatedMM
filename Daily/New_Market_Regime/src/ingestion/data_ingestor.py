#!/usr/bin/env python3
"""
Data Ingestor Module
Collects and organizes existing scanner results and market data
Reuses data from existing system without duplication
"""

import os
import sys
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import glob
import configparser

# Setup logging
log_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/data_ingestor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketDataIngestor:
    """
    Ingests data from existing sources:
    1. Scanner results (Long/Short Reversal, KC scanners)
    2. Market regime predictions
    3. Index data
    """
    
    def __init__(self):
        # Paths to existing data sources
        self.base_path = '/Users/maverick/PycharmProjects/India-TS/Daily'
        
        # Scanner result paths - Updated with correct paths
        # KC files are optional - they provide additional trend signals but not essential
        self.scanner_paths = {
            # Daily scanners (REQUIRED)
            'long_reversal_daily': f'{self.base_path}/results/Long_Reversal_Daily_*.xlsx',
            'short_reversal_daily': f'{self.base_path}/results-s/Short_Reversal_Daily_*.xlsx',
            
            # Hourly scanners (REQUIRED)
            'long_reversal_hourly': f'{self.base_path}/results-h/Long_Reversal_Hourly_*.xlsx',
            'short_reversal_hourly': f'{self.base_path}/results-s-h/Short_Reversal_Hourly_*.xlsx',
            
            # Optional scanners - will be used if available
            # 'kc_upper': f'{self.base_path}/FNO/Long/KC_Upper_Limit_Trending_FNO_*.xlsx',
            # 'kc_lower': f'{self.base_path}/FNO/Short/KC_Lower_Limit_Trending_FNO_*.xlsx',
            # 'vsr_hourly': f'{self.base_path}/scanners/Hourly/VSR_*.xlsx'
        }
        
        # Database paths
        self.regime_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
        
        # Output paths for organized data
        self.output_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data/raw'
        os.makedirs(self.output_path, exist_ok=True)
        
        # Track ingestion state
        self.last_ingestion_file = f'{self.output_path}/last_ingestion.json'
        self.last_ingestion = self.load_last_ingestion()
        
    def load_last_ingestion(self):
        """Load timestamp of last successful ingestion"""
        if os.path.exists(self.last_ingestion_file):
            with open(self.last_ingestion_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_last_ingestion(self):
        """Save timestamp of successful ingestion"""
        with open(self.last_ingestion_file, 'w') as f:
            json.dump(self.last_ingestion, f, default=str)
    
    def ingest_scanner_results(self):
        """
        Collect latest scanner results from existing system
        """
        logger.info("Ingesting scanner results...")
        
        all_scanner_data = {}
        
        for scanner_name, pattern in self.scanner_paths.items():
            try:
                # Find latest file
                files = glob.glob(pattern)
                if not files:
                    logger.warning(f"No files found for {scanner_name}")
                    continue
                
                latest_file = max(files, key=os.path.getmtime)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(latest_file))
                
                # Check if already processed
                last_processed = self.last_ingestion.get(scanner_name)
                if last_processed and datetime.fromisoformat(last_processed) >= file_mtime:
                    logger.info(f"Skipping {scanner_name} - already processed")
                    continue
                
                # Read the file
                df = pd.read_excel(latest_file)
                
                # Extract key metrics
                scanner_data = {
                    'timestamp': file_mtime,
                    'scanner': scanner_name,
                    'total_stocks': len(df),
                    'file_path': latest_file
                }
                
                # Scanner-specific metrics
                if 'long' in scanner_name.lower():
                    scanner_data['type'] = 'bullish'
                elif 'short' in scanner_name.lower():
                    scanner_data['type'] = 'bearish'
                else:
                    scanner_data['type'] = 'neutral'
                
                # Store ticker list
                if 'Ticker' in df.columns:
                    scanner_data['tickers'] = df['Ticker'].tolist()
                elif 'Symbol' in df.columns:
                    scanner_data['tickers'] = df['Symbol'].tolist()
                
                all_scanner_data[scanner_name] = scanner_data
                
                # Update last processed
                self.last_ingestion[scanner_name] = file_mtime.isoformat()
                
                logger.info(f"Ingested {scanner_name}: {scanner_data['total_stocks']} stocks")
                
            except Exception as e:
                logger.error(f"Error ingesting {scanner_name}: {e}")
                continue
        
        # Save aggregated scanner data
        if all_scanner_data:
            output_file = f"{self.output_path}/scanner_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(all_scanner_data, f, default=str, indent=2)
            logger.info(f"Saved scanner data to {output_file}")
        
        return all_scanner_data
    
    def ingest_regime_predictions(self):
        """
        Collect regime predictions from existing database
        """
        logger.info("Ingesting regime predictions...")
        
        try:
            conn = sqlite3.connect(self.regime_db)
            
            # Get recent predictions (last 24 hours)
            query = """
                SELECT timestamp, regime, confidence, market_score
                FROM predictions
                WHERE timestamp >= datetime('now', '-1 day')
                ORDER BY timestamp DESC
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) == 0:
                logger.warning("No recent regime predictions found")
                return None
            
            # Aggregate regime data
            regime_data = {
                'timestamp': datetime.now(),
                'total_predictions': len(df),
                'regime_distribution': df['regime'].value_counts().to_dict(),
                'avg_confidence': df['confidence'].mean(),
                'market_scores': {
                    'mean': df['market_score'].mean(),
                    'std': df['market_score'].std(),
                    'min': df['market_score'].min(),
                    'max': df['market_score'].max()
                }
            }
            
            # Check for monoculture
            top_regime_pct = df['regime'].value_counts().iloc[0] / len(df) * 100
            if top_regime_pct > 70:
                regime_data['warning'] = f"Regime monoculture detected: {top_regime_pct:.1f}% single regime"
                logger.warning(regime_data['warning'])
            
            # Save regime data
            output_file = f"{self.output_path}/regime_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(regime_data, f, default=str, indent=2)
            
            logger.info(f"Ingested {len(df)} regime predictions")
            
            return regime_data
            
        except Exception as e:
            logger.error(f"Error ingesting regime predictions: {e}")
            return None
    
    def ingest_market_breadth(self, scanner_data=None):
        """
        Calculate market breadth from scanner results
        """
        logger.info("Calculating market breadth...")
        
        try:
            # Use provided scanner data or get latest
            if scanner_data is None:
                scanner_data = self.ingest_scanner_results()
            
            if not scanner_data:
                logger.warning("No scanner data available for breadth calculation")
                return None
            
            # Calculate breadth metrics
            long_stocks = 0
            short_stocks = 0
            
            for scanner_name, data in scanner_data.items():
                if data['type'] == 'bullish':
                    long_stocks += data['total_stocks']
                elif data['type'] == 'bearish':
                    short_stocks += data['total_stocks']
            
            breadth_data = {
                'timestamp': datetime.now(),
                'long_stocks': long_stocks,
                'short_stocks': short_stocks,
                'long_short_ratio': long_stocks / max(short_stocks, 1),
                'bullish_percent': long_stocks / max(long_stocks + short_stocks, 1) * 100,
                'market_sentiment': 'bullish' if long_stocks > short_stocks else 'bearish'
            }
            
            # Save breadth data
            output_file = f"{self.output_path}/breadth_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(breadth_data, f, default=str, indent=2)
            
            logger.info(f"Market breadth: L/S Ratio = {breadth_data['long_short_ratio']:.2f}")
            
            return breadth_data
            
        except Exception as e:
            logger.error(f"Error calculating market breadth: {e}")
            return None
    
    def create_unified_dataset(self):
        """
        Create a unified dataset combining all ingested data
        """
        logger.info("Creating unified dataset...")
        
        try:
            # Collect all components
            scanner_data = self.ingest_scanner_results()
            regime_data = self.ingest_regime_predictions()
            breadth_data = self.ingest_market_breadth(scanner_data)  # Pass scanner_data to avoid re-ingestion
            
            # Create unified record
            unified_data = {
                'timestamp': datetime.now(),
                'market_breadth': breadth_data,
                'regime_predictions': regime_data,
                'scanner_summary': {
                    'total_scanners': len(scanner_data) if scanner_data else 0,
                    'scanners': list(scanner_data.keys()) if scanner_data else [],
                    'last_update': max([d['timestamp'] for d in scanner_data.values()]) if scanner_data else datetime.now()
                }
            }
            
            # Save unified dataset
            output_file = f"{self.output_path}/unified_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(unified_data, f, default=str, indent=2)
            
            # Also save as parquet for efficient processing
            df = pd.DataFrame([unified_data])
            parquet_file = f"{self.output_path}/unified_data_{datetime.now().strftime('%Y%m%d')}.parquet"
            df.to_parquet(parquet_file)
            
            logger.info(f"Created unified dataset: {output_file}")
            
            # Save ingestion state
            self.save_last_ingestion()
            
            return unified_data
            
        except Exception as e:
            logger.error(f"Error creating unified dataset: {e}")
            return None
    
    def is_market_open(self):
        """
        Check if market is open (weekdays 9:15 AM - 3:30 PM IST)
        """
        now = datetime.now()
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False, "Weekend - Market closed"
        
        # Check market hours
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if now < market_open:
            return False, f"Too early - Market opens at 9:15 AM"
        elif now > market_close:
            return False, f"Market closed - Trading ended at 3:30 PM"
        
        return True, "Market is open"
    
    def run_ingestion_cycle(self):
        """
        Run complete ingestion cycle
        To be called every 5 minutes during market hours (weekdays only)
        """
        logger.info("=" * 50)
        logger.info("Starting data ingestion cycle")
        logger.info("=" * 50)
        
        # Check if market is open
        is_open, reason = self.is_market_open()
        
        if not is_open:
            logger.info(f"Skipping ingestion: {reason}")
            return None
        
        logger.info("Market is open - proceeding with ingestion")
        
        # Run ingestion
        result = self.create_unified_dataset()
        
        if result:
            logger.info("✅ Ingestion cycle completed successfully")
        else:
            logger.error("❌ Ingestion cycle failed")
        
        return result


def main():
    """
    Main function for testing
    """
    ingestor = MarketDataIngestor()
    
    # Run single ingestion cycle
    result = ingestor.run_ingestion_cycle()
    
    if result:
        print("\n" + "=" * 50)
        print("Ingestion Summary:")
        print("=" * 50)
        
        if result.get('market_breadth'):
            breadth = result['market_breadth']
            print(f"Market Breadth: L/S Ratio = {breadth['long_short_ratio']:.2f}")
            print(f"Bullish Percent: {breadth['bullish_percent']:.1f}%")
        
        if result.get('regime_predictions'):
            regime = result['regime_predictions']
            print(f"Regime Predictions: {regime['total_predictions']} total")
            print(f"Average Confidence: {regime['avg_confidence']:.1%}")
            
            if 'warning' in regime:
                print(f"⚠️  WARNING: {regime['warning']}")
        
        print("\n✅ Data ingestion successful!")
    else:
        print("❌ Data ingestion failed!")


if __name__ == "__main__":
    main()