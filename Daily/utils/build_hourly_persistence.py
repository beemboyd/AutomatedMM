#!/usr/bin/env python3
"""
Build VSR persistence files from hourly scan results
Matches the data structure of existing vsr_ticker_persistence.json
"""

import os
import sys
import json
import pandas as pd
import datetime
from pathlib import Path
from collections import defaultdict
import glob

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class HourlyPersistenceBuilder:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.short_momentum_dir = os.path.join(self.base_dir, 'data', 'short_momentum')
        self.results_h_dir = os.path.join(self.base_dir, 'results-h')
        self.results_s_h_dir = os.path.join(self.base_dir, 'results-s-h')
        
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.short_momentum_dir, exist_ok=True)
        
        # Output files - matching existing architecture
        # Long hourly persistence stays in data/ directory (same as VSR)
        self.long_persistence_file = os.path.join(self.data_dir, 'vsr_ticker_persistence_hourly_long.json')
        # Short hourly persistence goes to short_momentum/ directory (same as short momentum tracker)
        self.short_persistence_file = os.path.join(self.short_momentum_dir, 'vsr_ticker_persistence_hourly_short.json')
        
    def get_hourly_files(self, directory, pattern, days=3):
        """Get hourly scan files from the last N days"""
        files = []
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        # Get all matching files
        file_pattern = os.path.join(directory, pattern)
        all_files = glob.glob(file_pattern)
        
        # Filter by date
        for file_path in all_files:
            try:
                # Extract date from filename (format: *_YYYYMMDD_HHMMSS.xlsx)
                filename = os.path.basename(file_path)
                date_part = filename.split('_')[-2]  # Get YYYYMMDD part
                file_date = datetime.datetime.strptime(date_part, '%Y%m%d')
                
                if file_date >= cutoff_date:
                    files.append({
                        'path': file_path,
                        'date': file_date,
                        'filename': filename
                    })
            except Exception as e:
                print(f"Error parsing file {file_path}: {e}")
                continue
        
        # Sort by date
        files.sort(key=lambda x: x['date'])
        return files
    
    def read_hourly_scan(self, file_path):
        """Read tickers from hourly scan Excel file"""
        try:
            df = pd.read_excel(file_path)
            
            # Extract ticker list
            if 'Ticker' in df.columns:
                ticker_data = {}
                for _, row in df.iterrows():
                    ticker = row['Ticker']
                    ticker_data[ticker] = {
                        'score': row.get('Score', 'N/A'),
                        'momentum': row.get('Momentum_5D', 0),
                        'sector': row.get('Sector', 'Unknown'),
                        'entry_price': row.get('Entry_Price', 0),
                        'stop_loss': row.get('Stop_Loss', 0),
                        'risk_reward': row.get('Risk_Reward_Ratio', 0)
                    }
                
                return ticker_data
            else:
                print(f"No 'Ticker' column found in {file_path}")
                return {}
                
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
    
    def build_persistence_data(self, files, direction='LONG'):
        """Build persistence data matching existing VSR structure"""
        # Initialize with exact structure from existing vsr_ticker_persistence.json
        persistence_data = {
            'tickers': {},
            'last_updated': datetime.datetime.now().isoformat()
        }
        
        # Track all scan times for each ticker
        ticker_scans = defaultdict(list)
        
        # Process each file
        for file_info in files:
            print(f"Processing {file_info['filename']}...")
            ticker_data = self.read_hourly_scan(file_info['path'])
            
            # Extract datetime from filename
            try:
                parts = file_info['filename'].split('_')
                date_str = parts[-2]  # YYYYMMDD
                time_str = parts[-1].replace('.xlsx', '')  # HHMMSS
                scan_datetime = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
            except:
                scan_datetime = file_info['date']
            
            # Record scan time and data for each ticker
            for ticker, data in ticker_data.items():
                ticker_scans[ticker].append({
                    'datetime': scan_datetime,
                    'momentum': data['momentum'],
                    'data': data
                })
        
        # Build persistence structure for each ticker
        for ticker, scans in ticker_scans.items():
            # Sort scans by datetime
            scans.sort(key=lambda x: x['datetime'])
            
            first_scan = scans[0]
            last_scan = scans[-1]
            
            # Calculate days tracked
            days_tracked = (last_scan['datetime'] - first_scan['datetime']).days + 1
            days_tracked = min(days_tracked, 3)  # Cap at 3 days
            
            # Build momentum history
            momentum_history = []
            positive_momentum_dates = set()
            last_positive_momentum = None
            
            for scan in scans:
                momentum_entry = {
                    'date': scan['datetime'].isoformat(),
                    'momentum': scan['momentum']
                }
                momentum_history.append(momentum_entry)
                
                # Track positive momentum days
                if scan['momentum'] > 0:
                    positive_momentum_dates.add(scan['datetime'].date())
                    last_positive_momentum = scan['datetime']
            
            # Create ticker entry matching existing structure
            persistence_data['tickers'][ticker] = {
                'first_seen': first_scan['datetime'].isoformat(),
                'last_seen': last_scan['datetime'].isoformat(),
                'days_tracked': days_tracked,
                'appearances': len(scans),
                'positive_momentum_days': len(positive_momentum_dates),
                'last_positive_momentum': last_positive_momentum.isoformat() if last_positive_momentum else None,
                'momentum_history': momentum_history
            }
        
        return persistence_data
    
    def save_persistence_file(self, data, output_file):
        """Save persistence data to JSON file"""
        try:
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved persistence data to {output_file}")
            return True
        except Exception as e:
            print(f"Error saving persistence file: {e}")
            return False
    
    def build_all_persistence_files(self, days=3):
        """Build persistence files for both Long and Short hourly scans"""
        print(f"\nBuilding persistence files from last {days} days of hourly scans...")
        print("Using data structure matching existing vsr_ticker_persistence.json")
        
        # Process Long hourly scans
        print("\n=== Processing LONG hourly scans ===")
        long_files = self.get_hourly_files(self.results_h_dir, "Long_Reversal_Hourly_*.xlsx", days)
        print(f"Found {len(long_files)} Long hourly scan files")
        
        if long_files:
            long_data = self.build_persistence_data(long_files, 'LONG')
            self.save_persistence_file(long_data, self.long_persistence_file)
            
            # Print summary
            print(f"\nLONG Summary:")
            print(f"- Total unique tickers: {len(long_data['tickers'])}")
            print(f"- Last updated: {long_data['last_updated']}")
            
            # Top tickers by appearances
            top_tickers = sorted(long_data['tickers'].items(), 
                               key=lambda x: x[1]['appearances'], 
                               reverse=True)[:10]
            print("\nTop 10 LONG tickers by appearances:")
            for ticker, info in top_tickers:
                print(f"  {ticker}: {info['appearances']} times, "
                      f"{info['days_tracked']} days, "
                      f"{info['positive_momentum_days']} positive days")
        
        # Process Short hourly scans
        print("\n=== Processing SHORT hourly scans ===")
        short_files = self.get_hourly_files(self.results_s_h_dir, "Short_Reversal_Hourly_*.xlsx", days)
        print(f"Found {len(short_files)} Short hourly scan files")
        
        if short_files:
            short_data = self.build_persistence_data(short_files, 'SHORT')
            self.save_persistence_file(short_data, self.short_persistence_file)
            
            # Print summary
            print(f"\nSHORT Summary:")
            print(f"- Total unique tickers: {len(short_data['tickers'])}")
            print(f"- Last updated: {short_data['last_updated']}")
            
            # Top tickers by appearances
            top_tickers = sorted(short_data['tickers'].items(), 
                               key=lambda x: x[1]['appearances'], 
                               reverse=True)[:10]
            print("\nTop 10 SHORT tickers by appearances:")
            for ticker, info in top_tickers:
                print(f"  {ticker}: {info['appearances']} times, "
                      f"{info['days_tracked']} days, "
                      f"{info['positive_momentum_days']} positive days")
    
    def get_active_tickers_from_persistence(self, persistence_file, recent_hours=24):
        """Get active tickers using same logic as VSRTickerPersistence class"""
        try:
            with open(persistence_file, 'r') as f:
                data = json.load(f)
            
            active_tickers = []
            now = datetime.datetime.now()
            cutoff_date = now - datetime.timedelta(hours=recent_hours)
            
            for ticker, info in data['tickers'].items():
                last_seen = datetime.datetime.fromisoformat(info['last_seen'])
                
                # Include if seen recently AND has positive momentum criteria
                if last_seen >= cutoff_date:
                    # Check momentum criteria (same as VSRTickerPersistence)
                    first_seen = datetime.datetime.fromisoformat(info['first_seen'])
                    if info['positive_momentum_days'] > 0 or (now - first_seen).days < 1:
                        active_tickers.append({
                            'ticker': ticker,
                            'appearances': info['appearances'],
                            'last_seen': info['last_seen'],
                            'days_tracked': info['days_tracked'],
                            'positive_momentum_days': info['positive_momentum_days'],
                            'last_positive_momentum': info.get('last_positive_momentum')
                        })
            
            # Sort by appearances
            active_tickers.sort(key=lambda x: x['appearances'], reverse=True)
            return active_tickers
            
        except Exception as e:
            print(f"Error reading persistence file: {e}")
            return []
    
    def merge_with_existing(self, new_file, existing_file):
        """Merge new persistence data with existing file"""
        existing_data = {'tickers': {}, 'last_updated': datetime.datetime.now().isoformat()}
        
        # Load existing data if file exists
        if os.path.exists(existing_file):
            try:
                with open(existing_file, 'r') as f:
                    existing_data = json.load(f)
                print(f"Loaded existing data from {existing_file}")
            except Exception as e:
                print(f"Error loading existing file: {e}")
        
        # Load new data
        try:
            with open(new_file, 'r') as f:
                new_data = json.load(f)
        except Exception as e:
            print(f"Error loading new file: {e}")
            return
        
        # Merge tickers
        for ticker, new_info in new_data['tickers'].items():
            if ticker in existing_data['tickers']:
                # Merge with existing ticker
                existing_info = existing_data['tickers'][ticker]
                
                # Update timestamps
                existing_info['last_seen'] = new_info['last_seen']
                existing_info['appearances'] += new_info['appearances']
                
                # Merge momentum history
                existing_history = {h['date']: h for h in existing_info.get('momentum_history', [])}
                for h in new_info['momentum_history']:
                    existing_history[h['date']] = h
                
                # Sort and keep only last 3 days
                cutoff = datetime.datetime.now() - datetime.timedelta(days=3)
                merged_history = []
                for date_str, entry in sorted(existing_history.items()):
                    if datetime.datetime.fromisoformat(date_str) > cutoff:
                        merged_history.append(entry)
                
                existing_info['momentum_history'] = merged_history
                
                # Recalculate positive momentum days
                positive_dates = set()
                last_positive = None
                for h in merged_history:
                    if h['momentum'] > 0:
                        date = datetime.datetime.fromisoformat(h['date'])
                        positive_dates.add(date.date())
                        last_positive = date
                
                existing_info['positive_momentum_days'] = len(positive_dates)
                existing_info['last_positive_momentum'] = last_positive.isoformat() if last_positive else None
                
                # Update days tracked
                first_seen = datetime.datetime.fromisoformat(existing_info['first_seen'])
                last_seen = datetime.datetime.fromisoformat(existing_info['last_seen'])
                existing_info['days_tracked'] = min((last_seen - first_seen).days + 1, 3)
            else:
                # Add new ticker
                existing_data['tickers'][ticker] = new_info
        
        existing_data['last_updated'] = datetime.datetime.now().isoformat()
        
        # Save merged data back to existing file
        with open(existing_file, 'w') as f:
            json.dump(existing_data, f, indent=2)
        print(f"Merged data saved to {existing_file}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build hourly persistence files from scan results")
    parser.add_argument("--days", type=int, default=3, help="Number of days to look back (default: 3)")
    parser.add_argument("--show-active", action="store_true", help="Show currently active tickers")
    parser.add_argument("--merge", action="store_true", help="Merge with existing persistence files")
    
    args = parser.parse_args()
    
    builder = HourlyPersistenceBuilder()
    
    # Build persistence files
    builder.build_all_persistence_files(days=args.days)
    
    # Merge with existing if requested
    if args.merge:
        print("\n=== Merging with existing persistence files ===")
        # Define existing files (if you want to merge with main VSR persistence)
        main_persistence = os.path.join(builder.data_dir, 'vsr_ticker_persistence.json')
        
        if os.path.exists(builder.long_persistence_file):
            print("\nMerging LONG hourly data...")
            builder.merge_with_existing(builder.long_persistence_file, main_persistence)
    
    # Show active tickers if requested
    if args.show_active:
        print("\n=== Currently Active Tickers ===")
        
        # Long tickers
        if os.path.exists(builder.long_persistence_file):
            print("\nActive LONG tickers (last 24 hours):")
            long_active = builder.get_active_tickers_from_persistence(builder.long_persistence_file)
            for ticker_info in long_active[:20]:
                pos_days = ticker_info['positive_momentum_days']
                print(f"  {ticker_info['ticker']}: {ticker_info['appearances']} scans, "
                      f"{ticker_info['days_tracked']} days tracked, "
                      f"{pos_days} positive momentum days")
        
        # Short tickers
        if os.path.exists(builder.short_persistence_file):
            print("\nActive SHORT tickers (last 24 hours):")
            short_active = builder.get_active_tickers_from_persistence(builder.short_persistence_file)
            for ticker_info in short_active[:20]:
                pos_days = ticker_info['positive_momentum_days']
                print(f"  {ticker_info['ticker']}: {ticker_info['appearances']} scans, "
                      f"{ticker_info['days_tracked']} days tracked, "
                      f"{pos_days} positive momentum days")