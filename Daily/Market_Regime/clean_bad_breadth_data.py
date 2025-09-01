#!/usr/bin/env python3
"""
Clean bad breadth data from hourly breadth files.
Removes or corrects entries with 100% SMA breadth values that occurred 
during bad access token periods.
"""

import json
import os
from datetime import datetime
import glob
import shutil

def clean_breadth_data():
    """Clean bad breadth data from hourly files"""
    
    # Directory containing hourly breadth data
    breadth_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/hourly_breadth_data"
    
    # Define problematic periods (when access token was bad)
    problematic_periods = [
        # August 29, 12:15 PM to 3:15 PM
        ("2025-08-29 12:00:00", "2025-08-29 16:00:00"),
        # September 1, 9:15 AM (morning entry)
        ("2025-09-01 09:00:00", "2025-09-01 09:30:00")
    ]
    
    # Find all hourly breadth JSON files
    json_files = glob.glob(os.path.join(breadth_dir, "sma_breadth_hourly_*.json"))
    
    for json_file in json_files:
        print(f"\nProcessing: {os.path.basename(json_file)}")
        
        # Create backup
        backup_file = json_file + ".backup"
        if not os.path.exists(backup_file):
            shutil.copy2(json_file, backup_file)
            print(f"  Created backup: {os.path.basename(backup_file)}")
        
        # Load data
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Track changes
        original_count = len(data)
        cleaned_data = []
        removed_count = 0
        
        for entry in data:
            # Check if this entry falls within problematic periods
            entry_time = datetime.strptime(entry['datetime'], "%Y-%m-%d %H:%M:%S")
            
            is_problematic = False
            for start_str, end_str in problematic_periods:
                start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                
                if start_time <= entry_time <= end_time:
                    # Check if it has suspicious 100% values
                    if (entry.get('sma20_breadth') == 100.0 and 
                        entry.get('sma50_breadth') == 100.0):
                        is_problematic = True
                        break
            
            if is_problematic:
                print(f"  Removing bad entry: {entry['datetime']} - SMA20: {entry['sma20_breadth']}%, SMA50: {entry['sma50_breadth']}%")
                removed_count += 1
            else:
                # Keep good entries
                cleaned_data.append(entry)
        
        # Save cleaned data if changes were made
        if removed_count > 0:
            with open(json_file, 'w') as f:
                json.dump(cleaned_data, f, indent=2)
            print(f"  Cleaned {removed_count} bad entries (kept {len(cleaned_data)} of {original_count})")
        else:
            print(f"  No bad entries found")
    
    # Also clean the latest files
    latest_files = [
        os.path.join(breadth_dir, "sma_breadth_hourly_latest.json"),
        os.path.join(breadth_dir, "sma_breadth_hourly_latest.csv")
    ]
    
    for latest_file in latest_files:
        if os.path.exists(latest_file):
            print(f"\nProcessing latest file: {os.path.basename(latest_file)}")
            
            if latest_file.endswith('.json'):
                # Create backup
                backup_file = latest_file + ".backup"
                if not os.path.exists(backup_file):
                    shutil.copy2(latest_file, backup_file)
                
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                
                cleaned_data = []
                for entry in data:
                    entry_time = datetime.strptime(entry['datetime'], "%Y-%m-%d %H:%M:%S")
                    
                    is_problematic = False
                    for start_str, end_str in problematic_periods:
                        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                        end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                        
                        if start_time <= entry_time <= end_time:
                            if (entry.get('sma20_breadth') == 100.0 and 
                                entry.get('sma50_breadth') == 100.0):
                                is_problematic = True
                                break
                    
                    if not is_problematic:
                        cleaned_data.append(entry)
                
                with open(latest_file, 'w') as f:
                    json.dump(cleaned_data, f, indent=2)
                print(f"  Cleaned latest JSON file")

if __name__ == "__main__":
    print("Cleaning bad breadth data from hourly files...")
    print("This will remove entries with 100% SMA breadth values from problematic periods")
    clean_breadth_data()
    print("\nCleaning complete!")
    print("Dashboard should now display corrected historical data.")