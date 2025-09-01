#!/usr/bin/env python3
"""
Breadth Data Validator and Cleaner
Automatically detects and fixes bad breadth data caused by access token issues
"""

import json
import os
import glob
from datetime import datetime, timedelta
import shutil
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BreadthDataValidator:
    """Validates and cleans breadth data"""
    
    def __init__(self):
        self.breadth_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/hourly_breadth_data"
        self.historical_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data"
        
        # Suspicious patterns that indicate bad data
        self.suspicious_patterns = {
            'all_100': lambda e: (
                e.get('sma20_breadth') == 100.0 and 
                e.get('sma50_breadth') == 100.0 and 
                e.get('volume_breadth') == 100.0
            ),
            'both_sma_100': lambda e: (
                e.get('sma20_breadth') == 100.0 and 
                e.get('sma50_breadth') == 100.0
            ),
            'low_stock_count': lambda e: e.get('total_stocks', 0) < 10,
            'impossible_values': lambda e: (
                e.get('sma20_breadth', 0) > 100 or 
                e.get('sma50_breadth', 0) > 100 or
                e.get('sma20_breadth', 0) < 0 or
                e.get('sma50_breadth', 0) < 0
            ),
            'weekend_data': lambda e: self._is_weekend(e.get('datetime', '')),
            'outside_market_hours': lambda e: self._outside_market_hours(e.get('datetime', ''))
        }
    
    def _is_weekend(self, datetime_str: str) -> bool:
        """Check if date is weekend"""
        try:
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            return dt.weekday() in [5, 6]  # Saturday, Sunday
        except:
            return False
    
    def _outside_market_hours(self, datetime_str: str) -> bool:
        """Check if time is outside market hours (9:15 AM - 3:30 PM IST)"""
        try:
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            hour = dt.hour
            minute = dt.minute
            
            # Before 9:15 AM
            if hour < 9 or (hour == 9 and minute < 15):
                return True
            # After 3:30 PM  
            if hour > 15 or (hour == 15 and minute > 30):
                return True
            return False
        except:
            return False
    
    def validate_entry(self, entry: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single breadth entry
        Returns: (is_valid, list_of_issues)
        """
        issues = []
        
        for pattern_name, check_func in self.suspicious_patterns.items():
            if check_func(entry):
                issues.append(pattern_name)
        
        # Additional context-aware checks
        if entry.get('total_stocks', 0) < 30 and entry.get('sma20_breadth') == 100:
            issues.append('low_stocks_perfect_breadth')
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def analyze_data_quality(self, data: List[Dict]) -> Dict:
        """Analyze overall data quality"""
        total_entries = len(data)
        bad_entries = []
        issues_summary = {}
        
        for entry in data:
            is_valid, issues = self.validate_entry(entry)
            if not is_valid:
                bad_entries.append({
                    'entry': entry,
                    'issues': issues
                })
                for issue in issues:
                    issues_summary[issue] = issues_summary.get(issue, 0) + 1
        
        return {
            'total_entries': total_entries,
            'bad_entries_count': len(bad_entries),
            'bad_entries': bad_entries,
            'issues_summary': issues_summary,
            'quality_score': (total_entries - len(bad_entries)) / total_entries * 100 if total_entries > 0 else 0
        }
    
    def clean_file(self, filepath: str, backup: bool = True, dry_run: bool = False) -> Dict:
        """
        Clean a single breadth data file
        """
        logger.info(f"Processing: {os.path.basename(filepath)}")
        
        # Load data
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return {'error': str(e)}
        
        if not isinstance(data, list):
            logger.info(f"Skipping non-list file: {filepath}")
            return {'skipped': True}
        
        # Analyze before cleaning
        analysis_before = self.analyze_data_quality(data)
        
        # Filter out bad entries
        cleaned_data = []
        removed_entries = []
        
        for entry in data:
            is_valid, issues = self.validate_entry(entry)
            if is_valid:
                cleaned_data.append(entry)
            else:
                removed_entries.append({
                    'datetime': entry.get('datetime'),
                    'issues': issues
                })
                logger.warning(f"  Removing: {entry.get('datetime')} - Issues: {issues}")
        
        # Results
        result = {
            'file': os.path.basename(filepath),
            'original_count': len(data),
            'cleaned_count': len(cleaned_data),
            'removed_count': len(removed_entries),
            'removed_entries': removed_entries,
            'quality_before': analysis_before['quality_score'],
            'dry_run': dry_run
        }
        
        if not dry_run and len(removed_entries) > 0:
            # Create backup
            if backup:
                backup_file = filepath + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(filepath, backup_file)
                logger.info(f"  Created backup: {os.path.basename(backup_file)}")
            
            # Save cleaned data
            with open(filepath, 'w') as f:
                json.dump(cleaned_data, f, indent=2)
            logger.info(f"  Cleaned {len(removed_entries)} bad entries")
        
        return result
    
    def clean_all_files(self, dry_run: bool = False) -> List[Dict]:
        """Clean all breadth data files"""
        results = []
        
        for directory in [self.breadth_dir, self.historical_dir]:
            logger.info(f"\nScanning directory: {directory}")
            
            json_files = glob.glob(os.path.join(directory, "*.json"))
            for json_file in json_files:
                if '.backup' in json_file:
                    continue
                
                result = self.clean_file(json_file, dry_run=dry_run)
                if not result.get('skipped'):
                    results.append(result)
        
        return results
    
    def validate_recent_data(self, hours: int = 24) -> Dict:
        """
        Validate data from the last N hours
        Useful for checking after access token refresh
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_bad_entries = []
        
        # Check latest file
        latest_file = os.path.join(self.breadth_dir, "sma_breadth_hourly_latest.json")
        if os.path.exists(latest_file):
            with open(latest_file, 'r') as f:
                data = json.load(f)
            
            for entry in data:
                try:
                    entry_time = datetime.strptime(entry['datetime'], "%Y-%m-%d %H:%M:%S")
                    if entry_time >= cutoff_time:
                        is_valid, issues = self.validate_entry(entry)
                        if not is_valid:
                            recent_bad_entries.append({
                                'datetime': entry['datetime'],
                                'issues': issues
                            })
                except:
                    pass
        
        return {
            'hours_checked': hours,
            'bad_entries_found': len(recent_bad_entries),
            'bad_entries': recent_bad_entries
        }


def main():
    """Main function with CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate and clean breadth data')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be cleaned without making changes')
    parser.add_argument('--recent', type=int, metavar='HOURS',
                       help='Check data from last N hours')
    parser.add_argument('--file', type=str,
                       help='Clean specific file')
    
    args = parser.parse_args()
    
    validator = BreadthDataValidator()
    
    if args.recent:
        print(f"\nValidating data from last {args.recent} hours...")
        result = validator.validate_recent_data(args.recent)
        print(f"Found {result['bad_entries_found']} bad entries")
        if result['bad_entries']:
            print("\nBad entries:")
            for entry in result['bad_entries']:
                print(f"  {entry['datetime']}: {', '.join(entry['issues'])}")
    
    elif args.file:
        print(f"\nCleaning file: {args.file}")
        result = validator.clean_file(args.file, dry_run=args.dry_run)
        print(f"Original: {result.get('original_count', 0)} entries")
        print(f"Cleaned: {result.get('cleaned_count', 0)} entries")
        print(f"Removed: {result.get('removed_count', 0)} entries")
    
    else:
        print("\nCleaning all breadth data files...")
        if args.dry_run:
            print("DRY RUN - No changes will be made")
        
        results = validator.clean_all_files(dry_run=args.dry_run)
        
        total_removed = sum(r['removed_count'] for r in results)
        print(f"\n{'='*50}")
        print(f"Summary:")
        print(f"  Files processed: {len(results)}")
        print(f"  Total bad entries removed: {total_removed}")
        
        if not args.dry_run and total_removed > 0:
            print("\nData cleaned successfully!")
            print("Dashboard should now display corrected data.")


if __name__ == "__main__":
    main()