#!/usr/bin/env python3
"""
Append incremental market breadth data to historical file
This script should be run after market hours to update the historical data
"""

import json
import os
from datetime import datetime, timedelta
import logging
from pathlib import Path
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BREADTH_DATA_DIR = os.path.join(SCRIPT_DIR, 'breadth_data')
HISTORICAL_DATA_DIR = os.path.join(SCRIPT_DIR, 'historical_breadth_data')
HISTORICAL_FILE = os.path.join(HISTORICAL_DATA_DIR, 'sma_breadth_historical_latest.json')

def load_historical_data():
    """Load existing historical data"""
    if os.path.exists(HISTORICAL_FILE):
        with open(HISTORICAL_FILE, 'r') as f:
            return json.load(f)
    return []

def get_latest_daily_breadth():
    """Get the latest breadth data for today"""
    try:
        # Get today's date
        today = datetime.now().strftime('%Y%m%d')
        
        # Find all breadth files from today
        today_files = [f for f in os.listdir(BREADTH_DATA_DIR) 
                      if f.startswith(f'market_breadth_{today}') and f.endswith('.json')]
        
        if not today_files:
            logger.warning(f"No breadth data found for today ({today})")
            return None
        
        # Sort and get the latest file
        today_files.sort()
        latest_file = os.path.join(BREADTH_DATA_DIR, today_files[-1])
        
        with open(latest_file, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        logger.error(f"Error getting latest daily breadth: {e}")
        return None

def format_breadth_for_historical(breadth_data):
    """Format breadth data for historical storage"""
    try:
        # Extract date from timestamp
        timestamp_str = breadth_data.get('timestamp', '')
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            date_str = timestamp.strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Format the data with safe defaults for missing fields
        formatted_data = {
            "date": date_str,
            "timestamp": timestamp.strftime('%Y-%m-%dT%H:%M:%S') if timestamp_str else datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "total_stocks": breadth_data.get('total_stocks', 500),  # Default to 500
            "sma_breadth": breadth_data.get('sma_breadth', {}),
            "market_regime": breadth_data.get('market_regime', 'Unknown'),
            "market_score": breadth_data.get('market_score', 0.5)
        }
        
        # Add empty volume_breadth if not present
        if 'volume_breadth' not in breadth_data:
            formatted_data["volume_breadth"] = {
                "volume_breadth_percent": 0,
                "volume_participation": 0
            }
        else:
            formatted_data["volume_breadth"] = breadth_data.get('volume_breadth', {})
        
        return formatted_data
        
    except Exception as e:
        logger.error(f"Error formatting breadth data: {e}")
        return None

def append_to_historical(new_data):
    """Append new data to historical file"""
    try:
        # Load existing data
        historical_data = load_historical_data()
        
        # Check if data for this date already exists
        existing_dates = {d['date'] for d in historical_data}
        
        if new_data['date'] in existing_dates:
            logger.info(f"Data for {new_data['date']} already exists. Updating...")
            # Update existing entry
            for i, d in enumerate(historical_data):
                if d['date'] == new_data['date']:
                    historical_data[i] = new_data
                    break
        else:
            # Append new data
            historical_data.append(new_data)
            logger.info(f"Added new data for {new_data['date']}")
        
        # Sort by date
        historical_data.sort(key=lambda x: x['date'])
        
        # Keep only last 7 months of data (approximately 210 days)
        if len(historical_data) > 210:
            historical_data = historical_data[-210:]
            logger.info(f"Trimmed to last 210 days of data")
        
        # Save updated data
        Path(HISTORICAL_DATA_DIR).mkdir(parents=True, exist_ok=True)
        with open(HISTORICAL_FILE, 'w') as f:
            json.dump(historical_data, f, indent=2)
        
        logger.info(f"Successfully updated historical data. Total records: {len(historical_data)}")
        return True
        
    except Exception as e:
        logger.error(f"Error appending to historical data: {e}")
        return False

def main():
    """Main function to append daily breadth data to historical file"""
    logger.info("Starting historical breadth data update...")
    
    # Get latest breadth data
    latest_breadth = get_latest_daily_breadth()
    if not latest_breadth:
        logger.error("No breadth data available for today")
        return
    
    # Format for historical storage
    formatted_data = format_breadth_for_historical(latest_breadth)
    if not formatted_data:
        logger.error("Failed to format breadth data")
        return
    
    # Append to historical file
    if append_to_historical(formatted_data):
        logger.info("Historical breadth data updated successfully")
        
        # Also create a timestamped backup
        backup_file = os.path.join(HISTORICAL_DATA_DIR, 
                                  f"sma_breadth_historical_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(HISTORICAL_FILE, 'r') as f:
            data = json.load(f)
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Created backup: {backup_file}")
    else:
        logger.error("Failed to update historical breadth data")

def trigger_dashboard_refresh():
    """Trigger refresh on both dashboards after data update"""
    dashboards = [
        {"port": 8080, "name": "Market Regime Dashboard"},
        {"port": 5001, "name": "Market Breadth Dashboard"}
    ]
    
    for dashboard in dashboards:
        try:
            # Try to trigger refresh via API endpoint
            response = requests.get(f"http://localhost:{dashboard['port']}/api/refresh", timeout=5)
            if response.status_code == 200:
                logger.info(f"Successfully triggered refresh on {dashboard['name']} (port {dashboard['port']})")
            else:
                logger.warning(f"Failed to refresh {dashboard['name']}: Status {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"{dashboard['name']} (port {dashboard['port']}) is not running")
        except Exception as e:
            logger.error(f"Error refreshing {dashboard['name']}: {e}")
    
    # Also run the incremental collector to ensure latest data
    try:
        logger.info("Running incremental collector for latest data...")
        os.system(f"cd {SCRIPT_DIR} && python3 sma_breadth_incremental_collector.py")
        logger.info("Incremental collector completed")
    except Exception as e:
        logger.error(f"Error running incremental collector: {e}")

if __name__ == "__main__":
    main()
    
    # Trigger dashboard refresh after successful update
    logger.info("Triggering dashboard refresh...")
    trigger_dashboard_refresh()
    
    logger.info("Historical breadth update process completed")