#!/usr/bin/env python3
"""
Remove ALL September 1st breadth data entries as they're all invalid
due to access token issues.
"""

import json
import os
import glob

def clean_sept1_data():
    """Remove all September 1st entries from breadth data files"""
    
    # Directories to clean
    dirs_to_clean = [
        "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/hourly_breadth_data",
        "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data"
    ]
    
    for directory in dirs_to_clean:
        print(f"\nCleaning directory: {directory}")
        
        # Find all JSON files
        json_files = glob.glob(os.path.join(directory, "*.json"))
        
        for json_file in json_files:
            if '.backup' in json_file:
                continue
                
            try:
                # Load data
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Handle both list and dict formats
                if isinstance(data, list):
                    original_count = len(data)
                    # Filter out ALL September 1st entries
                    cleaned_data = [
                        entry for entry in data 
                        if not (entry.get('date') == '2025-09-01' or 
                               entry.get('datetime', '').startswith('2025-09-01'))
                    ]
                    
                    removed_count = original_count - len(cleaned_data)
                    
                    if removed_count > 0:
                        print(f"  {os.path.basename(json_file)}: Removing {removed_count} Sept 1st entries")
                        with open(json_file, 'w') as f:
                            json.dump(cleaned_data, f, indent=2)
                            
                elif isinstance(data, dict):
                    # Skip non-breadth data files
                    continue
                    
            except Exception as e:
                print(f"  Skipping {os.path.basename(json_file)}: {e}")

if __name__ == "__main__":
    print("Removing ALL September 1st breadth data (invalid due to access token issues)")
    clean_sept1_data()
    print("\nDone! All September 1st entries have been removed.")