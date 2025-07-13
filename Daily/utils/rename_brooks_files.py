#!/usr/bin/env python3
"""
Script to rename existing Brooks files to new StrategyB_Report format
Old format: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
New format: StrategyB_Report_YYYYMMDD_HHMMSS.xlsx
"""

import os
import glob
import shutil
from datetime import datetime

def rename_brooks_files(results_dir):
    """Rename all Brooks files to new StrategyB_Report format"""
    
    # Pattern for old format files
    old_pattern = os.path.join(results_dir, "Brooks_Higher_Probability_LONG_Reversal_*.xlsx")
    files = glob.glob(old_pattern)
    
    if not files:
        print("No files to rename")
        return
    
    print(f"Found {len(files)} files to rename")
    
    renamed_count = 0
    skipped_count = 0
    
    for old_path in files:
        filename = os.path.basename(old_path)
        
        try:
            # Extract date and time from old format: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
            parts = filename.split('_')
            
            if len(parts) >= 10:  # Ensure we have all required parts
                day = parts[5]
                month = parts[6]
                year = parts[7]
                hour = parts[8]
                minute = parts[9].replace('.xlsx', '')
                
                # Convert to new format: YYYYMMDD_HHMMSS
                new_date = f"{year}{month.zfill(2)}{day.zfill(2)}"
                new_time = f"{hour.zfill(2)}{minute.zfill(2)}00"  # Add seconds as 00
                
                # Create new filename
                new_filename = f"StrategyB_Report_{new_date}_{new_time}.xlsx"
                new_path = os.path.join(results_dir, new_filename)
                
                # Check if target file already exists
                if os.path.exists(new_path):
                    print(f"  Skipping {filename} - target already exists: {new_filename}")
                    skipped_count += 1
                    continue
                
                # Rename the file
                os.rename(old_path, new_path)
                print(f"  Renamed: {filename}")
                print(f"       to: {new_filename}")
                renamed_count += 1
                
            else:
                print(f"  Skipping {filename} - unexpected format")
                skipped_count += 1
                
        except Exception as e:
            print(f"  Error renaming {filename}: {e}")
            skipped_count += 1
    
    print(f"\nSummary:")
    print(f"  Total files found: {len(files)}")
    print(f"  Successfully renamed: {renamed_count}")
    print(f"  Skipped: {skipped_count}")

def main():
    """Main function"""
    results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
    
    print(f"Renaming Brooks files in: {results_dir}")
    print("Converting from: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx")
    print("            to: StrategyB_Report_YYYYMMDD_HHMMSS.xlsx")
    print("-" * 80)
    
    # Auto-confirm for script execution
    print("\nProceeding with renaming...")
    print()
    rename_brooks_files(results_dir)

if __name__ == "__main__":
    main()