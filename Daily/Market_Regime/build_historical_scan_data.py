#!/usr/bin/env python
"""
Build Historical Scan Data
Aggregates historical L/S counts from existing reversal pattern files
"""

import os
import json
import pandas as pd
from datetime import datetime
import glob
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_timestamp_from_filename(filename):
    """Extract timestamp from filename like Long_Reversal_Daily_20250725_151127.xlsx"""
    try:
        # Remove directory path and extension
        base_name = os.path.basename(filename)
        name_without_ext = os.path.splitext(base_name)[0]
        
        # Try to find date pattern YYYYMMDD_HHMMSS
        import re
        date_pattern = r'(\d{8})_(\d{6})'
        match = re.search(date_pattern, name_without_ext)
        
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            dt_str = f"{date_str}_{time_str}"
            dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
            return dt
        else:
            # Try alternate pattern for files without time
            date_pattern = r'(\d{8})'
            match = re.search(date_pattern, name_without_ext)
            if match:
                date_str = match.group(1)
                dt = datetime.strptime(date_str, "%Y%m%d")
                # Set time to 09:30 for files without time
                dt = dt.replace(hour=9, minute=30)
                return dt
                
        return None
    except Exception as e:
        logger.error(f"Error parsing filename {filename}: {e}")
        return None

def build_historical_data():
    """Build historical scan data from existing files"""
    
    # Directories
    results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
    results_s_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results-s"
    output_file = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/historical_scan_data.json"
    
    # Get all long and short reversal files - include all patterns
    long_patterns = ["Long_Reversal_Daily_*.xlsx", "Long_*.xlsx"]
    short_patterns = ["Short_Reversal_Daily_*.xlsx", "Short_*.xlsx"]
    
    long_files = []
    for pattern in long_patterns:
        long_files.extend(glob.glob(os.path.join(results_dir, pattern)))
    
    short_files = []
    for pattern in short_patterns:
        short_files.extend(glob.glob(os.path.join(results_s_dir, pattern)))
    
    # Remove duplicates
    long_files = list(set(long_files))
    short_files = list(set(short_files))
    
    logger.info(f"Found {len(long_files)} long reversal files")
    logger.info(f"Found {len(short_files)} short reversal files")
    
    # Build a mapping of timestamps to files
    timestamp_map = {}
    
    # Process long files
    for long_file in long_files:
        filename = os.path.basename(long_file)
        timestamp = extract_timestamp_from_filename(filename)
        if timestamp:
            # Round to nearest hour for matching
            timestamp_hour = timestamp.replace(minute=0, second=0, microsecond=0)
            if timestamp_hour not in timestamp_map:
                timestamp_map[timestamp_hour] = {'timestamps': []}
            timestamp_map[timestamp_hour]['long_file'] = long_file
            timestamp_map[timestamp_hour]['timestamps'].append(timestamp)
            
    # Process short files
    for short_file in short_files:
        filename = os.path.basename(short_file)
        timestamp = extract_timestamp_from_filename(filename)
        if timestamp:
            # Round to nearest hour for matching
            timestamp_hour = timestamp.replace(minute=0, second=0, microsecond=0)
            if timestamp_hour not in timestamp_map:
                timestamp_map[timestamp_hour] = {'timestamps': []}
            timestamp_map[timestamp_hour]['short_file'] = short_file
            timestamp_map[timestamp_hour]['timestamps'].append(timestamp)
    
    # Build historical data
    historical_data = []
    
    for timestamp_hour, files in sorted(timestamp_map.items()):
        # Only process if we have both long and short files
        if 'long_file' in files and 'short_file' in files:
            try:
                # Read the Excel files to get actual counts
                df_long = pd.read_excel(files['long_file'])
                df_short = pd.read_excel(files['short_file'])
                
                long_count = len(df_long)
                short_count = len(df_short)
                
                # Skip if both are zero
                if long_count == 0 and short_count == 0:
                    continue
                
                # Calculate ratio
                if short_count > 0:
                    ratio = long_count / short_count
                else:
                    ratio = float('inf') if long_count > 0 else 1.0
                
                # Use the average timestamp from all timestamps in this hour
                avg_timestamp = min(files['timestamps'])
                
                entry = {
                    'timestamp': avg_timestamp.isoformat(),
                    'long_count': long_count,
                    'short_count': short_count,
                    'ratio': ratio if ratio != float('inf') else 999.0  # Cap infinity at 999
                }
                
                historical_data.append(entry)
                logger.info(f"Processed {avg_timestamp}: L={long_count}, S={short_count}, R={ratio:.2f}")
                
            except Exception as e:
                logger.error(f"Error processing files for {timestamp_hour}: {e}")
                continue
    
    # Sort by timestamp
    historical_data.sort(key=lambda x: x['timestamp'])
    
    logger.info(f"Built historical data with {len(historical_data)} entries")
    
    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(historical_data, f, indent=2)
    
    logger.info(f"Saved historical data to {output_file}")
    
    # Also update the scan_history.json with this data
    scan_history_file = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/scan_history.json"
    
    try:
        # Load existing scan history
        if os.path.exists(scan_history_file):
            with open(scan_history_file, 'r') as f:
                existing_data = json.load(f)
        else:
            existing_data = []
        
        # Convert to dataframe for easier manipulation
        existing_df = pd.DataFrame(existing_data)
        new_df = pd.DataFrame(historical_data)
        
        # Combine and remove duplicates based on timestamp
        if not existing_df.empty:
            combined_df = pd.concat([new_df, existing_df], ignore_index=True)
            # Handle different timestamp formats
            combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'], format='mixed')
            combined_df = combined_df.drop_duplicates(subset=['timestamp'])
            combined_df = combined_df.sort_values('timestamp')
        else:
            combined_df = new_df
            combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'], format='mixed')
        
        # Convert back to list of dicts
        combined_data = combined_df.to_dict('records')
        
        # Convert timestamps back to strings
        for entry in combined_data:
            entry['timestamp'] = entry['timestamp'].isoformat()
        
        # Save updated scan history
        with open(scan_history_file, 'w') as f:
            json.dump(combined_data, f, indent=2)
        
        logger.info(f"Updated scan_history.json with {len(combined_data)} total entries")
        
    except Exception as e:
        logger.error(f"Error updating scan_history.json: {e}")
    
    return historical_data

def analyze_historical_trends(data):
    """Analyze historical trends from the data"""
    if not data:
        return
    
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    
    print("\n=== Historical Trend Analysis ===")
    print(f"Total days of data: {len(df['date'].unique())}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Daily averages
    daily_avg = df.groupby('date').agg({
        'long_count': 'mean',
        'short_count': 'mean',
        'ratio': 'mean'
    })
    
    print("\nDaily Averages:")
    print(f"Long counts: {daily_avg['long_count'].mean():.1f}")
    print(f"Short counts: {daily_avg['short_count'].mean():.1f}")
    print(f"L/S Ratio: {daily_avg['ratio'].mean():.2f}")
    
    # Weekly aggregation
    df['week'] = df['timestamp'].dt.to_period('W')
    weekly_data = df.groupby('week').agg({
        'long_count': 'sum',
        'short_count': 'sum'
    })
    weekly_data['ratio'] = weekly_data['long_count'] / weekly_data['short_count']
    
    print("\nWeekly Summary:")
    for week, row in weekly_data.iterrows():
        print(f"Week {week}: L={row['long_count']}, S={row['short_count']}, Ratio={row['ratio']:.2f}")

if __name__ == "__main__":
    print("Building historical scan data from reversal pattern files...")
    historical_data = build_historical_data()
    
    if historical_data:
        analyze_historical_trends(historical_data)
        print(f"\nSuccessfully built historical data with {len(historical_data)} entries")
    else:
        print("No historical data could be built")