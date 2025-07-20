#!/usr/bin/env python
"""
Reversal Trend Scanner
Runs both Long and Short reversal scans and calculates trend strength based on the ratio
"""

import os
import sys
import logging
import datetime
import pandas as pd
import subprocess
import json
from pathlib import Path

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                       "reversal_trend_scanner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ReversalTrendScanner:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.dirname(self.script_dir)
        self.scanners_dir = os.path.join(self.daily_dir, "scanners")
        # Output directories when running from Market_Regime
        self.results_long_dir = os.path.join(self.script_dir, "results")
        self.results_short_dir = os.path.join(self.script_dir, "results")
        self.output_dir = os.path.join(self.script_dir, "scan_results")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
    def run_long_reversal_scan(self):
        """Run the Long Reversal Daily scanner"""
        logger.info("Running Long Reversal Daily scanner...")
        
        # Use local copy in Market_Regime folder
        long_scanner_path = os.path.join(self.script_dir, "Long_Reversal_Daily.py")
        
        try:
            # Run the scanner
            result = subprocess.run(
                [sys.executable, long_scanner_path],
                capture_output=True,
                text=True,
                cwd=self.script_dir
            )
            
            if result.returncode != 0:
                logger.error(f"Long scanner failed: {result.stderr}")
                return None
                
            # Find the most recent output file
            latest_file = self._find_latest_file(self.results_long_dir, "Long_Reversal_Daily_*.xlsx")
            
            if latest_file:
                logger.info(f"Long scan completed. Output: {latest_file}")
                return latest_file
            else:
                logger.warning("Long scan completed but no output file found")
                return None
                
        except Exception as e:
            logger.error(f"Error running long reversal scan: {e}")
            return None
            
    def run_short_reversal_scan(self):
        """Run the Short Reversal Daily scanner"""
        logger.info("Running Short Reversal Daily scanner...")
        
        # Use local copy in Market_Regime folder
        short_scanner_path = os.path.join(self.script_dir, "Short_Reversal_Daily.py")
        
        try:
            # Run the scanner
            result = subprocess.run(
                [sys.executable, short_scanner_path],
                capture_output=True,
                text=True,
                cwd=self.script_dir
            )
            
            if result.returncode != 0:
                logger.error(f"Short scanner failed: {result.stderr}")
                return None
                
            # Find the most recent output file
            latest_file = self._find_latest_file(self.results_short_dir, "Short_Reversal_Daily_*.xlsx")
            
            if latest_file:
                logger.info(f"Short scan completed. Output: {latest_file}")
                return latest_file
            else:
                logger.warning("Short scan completed but no output file found")
                return None
                
        except Exception as e:
            logger.error(f"Error running short reversal scan: {e}")
            return None
            
    def _find_latest_file(self, directory, pattern):
        """Find the most recent file matching pattern in directory"""
        from glob import glob
        
        files = glob(os.path.join(directory, pattern))
        if not files:
            return None
            
        # Sort by modification time and return the most recent
        return max(files, key=os.path.getmtime)
        
    def analyze_scan_results(self, long_file, short_file):
        """Analyze the scan results and return counts"""
        long_count = 0
        short_count = 0
        
        # Read long scan results
        if long_file and os.path.exists(long_file):
            try:
                df_long = pd.read_excel(long_file)
                long_count = len(df_long)
                logger.info(f"Found {long_count} long reversal patterns")
            except Exception as e:
                logger.error(f"Error reading long scan file: {e}")
                
        # Read short scan results  
        if short_file and os.path.exists(short_file):
            try:
                df_short = pd.read_excel(short_file)
                short_count = len(df_short)
                logger.info(f"Found {short_count} short reversal patterns")
            except Exception as e:
                logger.error(f"Error reading short scan file: {e}")
                
        return long_count, short_count
        
    def run_complete_scan(self):
        """Run both scans and analyze results"""
        logger.info("Starting complete reversal trend scan...")
        
        # Run both scans
        long_file = self.run_long_reversal_scan()
        short_file = self.run_short_reversal_scan()
        
        # Analyze results
        long_count, short_count = self.analyze_scan_results(long_file, short_file)
        
        # Prepare scan data
        scan_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'long_count': long_count,
            'short_count': short_count,
            'long_file': long_file,
            'short_file': short_file
        }
        
        # Save scan results
        output_file = os.path.join(self.output_dir, 
                                 f"reversal_scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(output_file, 'w') as f:
            json.dump(scan_data, f, indent=2)
            
        logger.info(f"Scan results saved to {output_file}")
        
        return scan_data


def main():
    """Main function to run the reversal trend scanner"""
    scanner = ReversalTrendScanner()
    
    try:
        results = scanner.run_complete_scan()
        
        print("\n===== Reversal Trend Scan Results =====")
        print(f"Long Reversal Patterns: {results['long_count']}")
        print(f"Short Reversal Patterns: {results['short_count']}")
        print("=====================================\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())