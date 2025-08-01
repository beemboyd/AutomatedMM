#!/usr/bin/env python3
"""
Append momentum scanner data to historical breadth file
Integrates momentum counts with existing market breadth data
"""

import json
import os
from datetime import datetime, timedelta
import logging
from pathlib import Path
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOMENTUM_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Momentum')
HISTORICAL_DATA_DIR = os.path.join(SCRIPT_DIR, 'historical_breadth_data')
HISTORICAL_FILE = os.path.join(HISTORICAL_DATA_DIR, 'sma_breadth_historical_latest.json')

def load_historical_data():
    """Load existing historical data"""
    if os.path.exists(HISTORICAL_FILE):
        with open(HISTORICAL_FILE, 'r') as f:
            return json.load(f)
    return []

def get_momentum_data_for_date(date_str):
    """Get momentum scanner results for a specific date"""
    try:
        # Look for momentum report files
        momentum_files = [f for f in os.listdir(MOMENTUM_DIR) 
                         if f.startswith(f'India-Momentum_Report_{date_str}') and f.endswith('.xlsx')]
        
        if not momentum_files:
            logger.warning(f"No momentum data found for {date_str}")
            return None
        
        # Get the latest file for that date
        momentum_files.sort()
        latest_file = os.path.join(MOMENTUM_DIR, momentum_files[-1])
        
        # Read Excel file
        try:
            # Read Count Summary sheet
            count_df = pd.read_excel(latest_file, sheet_name='Count_Summary')
            daily_count = count_df[count_df['Metric'] == 'Daily Momentum Count']['Count'].iloc[0]
            weekly_count = count_df[count_df['Metric'] == 'Weekly Momentum Count']['Count'].iloc[0]
            
            # Read Daily Summary sheet for top movers
            daily_df = pd.read_excel(latest_file, sheet_name='Daily_Summary')
            if not daily_df.empty:
                # Get top 10 tickers
                top_tickers = daily_df.head(10)['Ticker'].tolist()
                # Get top WM values
                top_wm = daily_df.head(5)[['Ticker', 'WM', 'Slope']].to_dict('records')
            else:
                top_tickers = []
                top_wm = []
            
            return {
                'daily_count': int(daily_count),
                'weekly_count': int(weekly_count),
                'daily_tickers': top_tickers,
                'top_wm': top_wm
            }
            
        except Exception as e:
            logger.error(f"Error reading Excel file {latest_file}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting momentum data for {date_str}: {e}")
        return None

def update_historical_with_momentum(date_str, momentum_data):
    """Update historical data with momentum information"""
    try:
        # Load existing data
        historical_data = load_historical_data()
        
        # Convert date_str to date format
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        date_formatted = date_obj.strftime('%Y-%m-%d')
        
        # Find the entry for this date
        entry_updated = False
        for entry in historical_data:
            if entry['date'] == date_formatted:
                # Add momentum data to existing entry
                entry['momentum_breadth'] = {
                    'daily_count': momentum_data['daily_count'],
                    'weekly_count': momentum_data['weekly_count'],
                    'daily_percent': round(momentum_data['daily_count'] / 603 * 100, 2),  # 603 total tickers
                    'weekly_percent': round(momentum_data['weekly_count'] / 603 * 100, 2),
                    'top_movers': momentum_data['top_wm'][:5] if momentum_data['top_wm'] else []
                }
                entry_updated = True
                logger.info(f"Updated momentum data for {date_formatted}")
                break
        
        if not entry_updated:
            # Create new entry if date doesn't exist
            new_entry = {
                'date': date_formatted,
                'timestamp': date_obj.strftime('%Y-%m-%dT%H:%M:%S'),
                'momentum_breadth': {
                    'daily_count': momentum_data['daily_count'],
                    'weekly_count': momentum_data['weekly_count'],
                    'daily_percent': round(momentum_data['daily_count'] / 603 * 100, 2),
                    'weekly_percent': round(momentum_data['weekly_count'] / 603 * 100, 2),
                    'top_movers': momentum_data['top_wm'][:5] if momentum_data['top_wm'] else []
                }
            }
            historical_data.append(new_entry)
            logger.info(f"Added new momentum entry for {date_formatted}")
        
        # Sort by date
        historical_data.sort(key=lambda x: x['date'])
        
        # Save updated data
        with open(HISTORICAL_FILE, 'w') as f:
            json.dump(historical_data, f, indent=2)
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating historical data: {e}")
        return False

def backfill_momentum_data(days=210):
    """Backfill momentum data for past days"""
    logger.info(f"Starting backfill for past {days} days...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    current_date = start_date
    success_count = 0
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        
        date_str = current_date.strftime('%Y%m%d')
        
        # Get momentum data for this date
        momentum_data = get_momentum_data_for_date(date_str)
        
        if momentum_data:
            # Update historical file
            if update_historical_with_momentum(date_str, momentum_data):
                success_count += 1
                logger.info(f"Successfully processed {date_str}")
        
        current_date += timedelta(days=1)
    
    logger.info(f"Backfill complete. Processed {success_count} days.")

def main():
    """Main function to append today's momentum data"""
    logger.info("Starting momentum breadth data update...")
    
    # Get today's date
    today_str = datetime.now().strftime('%Y%m%d')
    
    # Get momentum data for today
    momentum_data = get_momentum_data_for_date(today_str)
    
    if not momentum_data:
        logger.error("No momentum data available for today")
        return
    
    # Update historical file
    if update_historical_with_momentum(today_str, momentum_data):
        logger.info("Momentum breadth data updated successfully")
        
        # Log summary
        logger.info(f"Today's momentum: {momentum_data['daily_count']} stocks ({momentum_data['daily_count']/603*100:.1f}%)")
        if momentum_data['top_wm']:
            logger.info("Top movers:")
            for i, mover in enumerate(momentum_data['top_wm'][:5], 1):
                logger.info(f"  {i}. {mover['Ticker']}: WM={mover['WM']:.2f}")
    else:
        logger.error("Failed to update momentum breadth data")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Append momentum data to historical breadth')
    parser.add_argument('--backfill', type=int, help='Backfill data for past N days')
    
    args = parser.parse_args()
    
    if args.backfill:
        backfill_momentum_data(args.backfill)
    else:
        main()