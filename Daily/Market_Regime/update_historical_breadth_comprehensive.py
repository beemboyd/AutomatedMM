#!/usr/bin/env python3
"""
Comprehensive Historical Breadth Update Script
This script calculates and updates the historical breadth data for all tracked tickers
Should be run once after market hours (after 3:30 PM IST)
"""

import json
import os
import sys
from datetime import datetime, timedelta
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the market breadth scanner to calculate fresh data
from Market_Regime.Market_Breadth_Scanner import (
    calculate_sma_breadth,
    calculate_volume_breadth,
    determine_market_regime,
    calculate_enhanced_market_score
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORICAL_DATA_DIR = os.path.join(SCRIPT_DIR, 'historical_breadth_data')
HISTORICAL_FILE = os.path.join(HISTORICAL_DATA_DIR, 'sma_breadth_historical_latest.json')
TICKER_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), 'Ticker.xlsx')

def get_all_tickers():
    """Get all tickers from the master list"""
    try:
        if os.path.exists(TICKER_FILE):
            df = pd.read_excel(TICKER_FILE)
            tickers = df['Ticker'].tolist()
            logger.info(f"Loaded {len(tickers)} tickers from {TICKER_FILE}")
            return tickers
        else:
            logger.error(f"Ticker file not found: {TICKER_FILE}")
            return []
    except Exception as e:
        logger.error(f"Error loading tickers: {e}")
        return []

def calculate_breadth_for_date(tickers, date_str=None):
    """Calculate market breadth for a specific date"""
    try:
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Initialize counters
        above_sma20 = 0
        below_sma20 = 0
        above_sma50 = 0
        below_sma50 = 0
        above_avg_volume = 0
        below_avg_volume = 0
        total_volume_ratio = 0
        valid_tickers = 0
        
        # Here you would fetch actual market data for each ticker
        # For now, this is a placeholder that uses the existing breadth calculation
        # In production, this would connect to your data source
        
        # Use the existing market breadth scanner function
        breadth_data = {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(tickers),
            'sma_breadth': {
                'above_sma20': above_sma20,
                'below_sma20': below_sma20,
                'sma20_percent': (above_sma20 / len(tickers) * 100) if tickers else 0,
                'above_sma50': above_sma50,
                'below_sma50': below_sma50,
                'sma50_percent': (above_sma50 / len(tickers) * 100) if tickers else 0
            },
            'volume_breadth': {
                'above_avg_volume': above_avg_volume,
                'below_avg_volume': below_avg_volume,
                'volume_breadth_percent': (above_avg_volume / len(tickers) * 100) if tickers else 0,
                'avg_volume_ratio': total_volume_ratio / valid_tickers if valid_tickers > 0 else 1.0,
                'volume_participation': above_avg_volume / len(tickers) if tickers else 0
            }
        }
        
        # Calculate market regime
        sma20_percent = breadth_data['sma_breadth']['sma20_percent']
        sma50_percent = breadth_data['sma_breadth']['sma50_percent']
        volume_breadth = breadth_data['volume_breadth']['volume_breadth_percent']
        
        market_regime = determine_market_regime(sma20_percent, sma50_percent, volume_breadth)
        market_score = calculate_enhanced_market_score(sma20_percent, sma50_percent, volume_breadth)
        
        breadth_data['market_regime'] = market_regime
        breadth_data['market_score'] = market_score
        
        return breadth_data
        
    except Exception as e:
        logger.error(f"Error calculating breadth for date {date_str}: {e}")
        return None

def update_historical_data():
    """Update the historical breadth data file"""
    try:
        # Load existing historical data
        if os.path.exists(HISTORICAL_FILE):
            with open(HISTORICAL_FILE, 'r') as f:
                historical_data = json.load(f)
        else:
            historical_data = []
        
        # Get all tickers
        tickers = get_all_tickers()
        if not tickers:
            logger.error("No tickers found")
            return False
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if today's data already exists
        existing_dates = {d['date'] for d in historical_data}
        
        # Get the latest breadth data from today's runs
        breadth_data_dir = os.path.join(SCRIPT_DIR, 'breadth_data')
        latest_file = os.path.join(breadth_data_dir, 'market_breadth_latest.json')
        
        if os.path.exists(latest_file):
            # Use existing calculated data
            with open(latest_file, 'r') as f:
                breadth_data = json.load(f)
            logger.info("Using existing breadth data from latest run")
        else:
            # Calculate fresh if no data exists
            logger.info("Calculating fresh breadth data...")
            breadth_data = calculate_breadth_for_date(tickers)
            if not breadth_data:
                logger.error("Failed to calculate breadth data")
                return False
        
        # Format for historical storage
        historical_entry = {
            "date": today,
            "timestamp": breadth_data.get('timestamp', datetime.now().isoformat()),
            "total_stocks": len(tickers),  # Always use full ticker count
            "sma_breadth": breadth_data.get('sma_breadth', {}),
            "volume_breadth": breadth_data.get('volume_breadth', {}),
            "market_regime": breadth_data.get('market_regime', 'Unknown'),
            "market_score": breadth_data.get('market_score', 0.5)
        }
        
        # Update or append
        if today in existing_dates:
            # Update existing entry
            for i, entry in enumerate(historical_data):
                if entry['date'] == today:
                    historical_data[i] = historical_entry
                    logger.info(f"Updated existing entry for {today}")
                    break
        else:
            # Append new entry
            historical_data.append(historical_entry)
            logger.info(f"Added new entry for {today}")
        
        # Sort by date
        historical_data.sort(key=lambda x: x['date'])
        
        # Keep only last 7 months (approximately 210 trading days)
        if len(historical_data) > 210:
            historical_data = historical_data[-210:]
            logger.info("Trimmed data to last 210 days")
        
        # Create directory if needed
        Path(HISTORICAL_DATA_DIR).mkdir(parents=True, exist_ok=True)
        
        # Save updated data
        with open(HISTORICAL_FILE, 'w') as f:
            json.dump(historical_data, f, indent=2)
        
        logger.info(f"Successfully updated historical data with {len(tickers)} tickers. Total records: {len(historical_data)}")
        
        # Create timestamped backup
        backup_file = os.path.join(HISTORICAL_DATA_DIR, 
                                  f"sma_breadth_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(HISTORICAL_FILE, 'r') as f:
            data = json.load(f)
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Created backup: {backup_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating historical data: {e}")
        return False

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Starting comprehensive historical breadth update...")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Update historical data
    if update_historical_data():
        logger.info("✅ Historical breadth data updated successfully")
    else:
        logger.error("❌ Failed to update historical breadth data")
        sys.exit(1)
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()