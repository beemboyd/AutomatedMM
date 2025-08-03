#!/usr/bin/env python
"""
Brooks Strategy Analysis - Available Data Range
===============================================
This script analyzes Brooks Higher Probability LONG Reversal strategy performance
using only the data that's available. It identifies which files can be analyzed
and provides performance statistics for those that have sufficient future data.

Author: Claude Code Assistant
Created: 2025-05-24
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
from pathlib import Path
import logging
import glob
import re
from typing import Dict, List, Tuple, Optional

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_brooks_data_availability():
    """Analyze what Brooks files can be processed with available data"""
    
    # Paths
    daily_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Daily")
    results_dir_source = os.path.join(daily_dir, "results")
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ohlc_data", "daily")
    
    print("="*80)
    print("BROOKS STRATEGY DATA AVAILABILITY ANALYSIS")
    print("="*80)
    
    # Get Brooks files
    files = glob.glob(os.path.join(results_dir_source, "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"))
    
    if not files:
        print("No Brooks strategy files found!")
        return
    
    # Get latest data date from OHLC files
    latest_data_date = None
    sample_files = [f for f in os.listdir(data_dir) if f.endswith('_day.csv')][:5]  # Check 5 files
    
    for csv_file in sample_files:
        try:
            df = pd.read_csv(os.path.join(data_dir, csv_file))
            if 'date' in df.columns or 'Date' in df.columns:
                date_col = 'Date' if 'Date' in df.columns else 'date'
                df[date_col] = pd.to_datetime(df[date_col])
                file_latest = df[date_col].max()
                if latest_data_date is None or file_latest > latest_data_date:
                    latest_data_date = file_latest
        except:
            continue
    
    print(f"Latest OHLC Data Available: {latest_data_date.date() if latest_data_date else 'Unknown'}")
    print(f"Total Brooks Files Found: {len(files)}")
    print("-"*80)
    
    analyzable_files = []
    future_files = []
    
    for file_path in sorted(files):
        filename = os.path.basename(file_path)
        
        # Extract date from filename
        date_match = re.search(r'Brooks_Higher_Probability_LONG_Reversal_(\\d{2})_(\\d{2})_(\\d{4})_(\\d{2})_(\\d{2})\\.xlsx', filename)
        if date_match:
            day, month, year, hour, minute = date_match.groups()
            scan_date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
            
            # Check if we have enough future data (need at least 10 days after scan)
            needed_date = scan_date + datetime.timedelta(days=10)
            
            try:
                df = pd.read_excel(file_path)
                ticker_count = len(df) if not df.empty else 0
            except:
                ticker_count = 0
            
            if latest_data_date and needed_date.date() <= latest_data_date.date():
                analyzable_files.append((file_path, scan_date, ticker_count))
                status = "✅ ANALYZABLE"
            else:
                future_files.append((file_path, scan_date, ticker_count))
                status = "❌ INSUFFICIENT DATA"
            
            print(f"{filename}")
            print(f"  Scan Date: {scan_date.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Tickers: {ticker_count}")
            print(f"  Status: {status}")
            if latest_data_date:
                days_diff = (latest_data_date.date() - scan_date.date()).days
                print(f"  Data Coverage: {days_diff} days after scan")
            print()
    
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Analyzable Files (with sufficient future data): {len(analyzable_files)}")
    print(f"Files with Insufficient Data: {len(future_files)}")
    
    if analyzable_files:
        print("\\nANALYZABLE FILES:")
        total_analyzable_tickers = 0
        for file_path, scan_date, ticker_count in analyzable_files:
            print(f"  • {os.path.basename(file_path)}: {ticker_count} tickers")
            total_analyzable_tickers += ticker_count
        print(f"\\nTotal Analyzable Tickers: {total_analyzable_tickers}")
    
    if future_files:
        print("\\nFILES NEEDING FUTURE DATA:")
        for file_path, scan_date, ticker_count in future_files:
            print(f"  • {os.path.basename(file_path)}: {ticker_count} tickers")
    
    print("\\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    if not analyzable_files:
        print("❌ NO FILES CAN BE ANALYZED with current data.")
        print("\\nTo analyze Brooks strategy performance:")
        print("1. Update OHLC data to include recent dates")
        print("2. Run: python ML/data/download_data.py")
        print("3. Then re-run the Brooks analysis")
    else:
        print(f"✅ {len(analyzable_files)} files can be analyzed.")
        print("\\nTo get more recent analysis:")
        print("1. Update OHLC data to include recent dates")
        print("2. This will allow analysis of the newer Brooks files")
    
    print("\\nTo update OHLC data:")
    print("  cd ML/data")
    print("  python download_data.py")
    print("="*80)
    
    return analyzable_files

if __name__ == "__main__":
    analyze_brooks_data_availability()