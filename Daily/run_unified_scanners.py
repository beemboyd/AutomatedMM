#!/usr/bin/env python
"""
Unified Scanner Runner - Runs all main scanners and opens HTML reports
"""

import os
import sys
import time
import subprocess
import webbrowser
import glob
from datetime import datetime
import argparse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "logs", "unified_scanner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Run unified scanners with HTML output")
    parser.add_argument("-u", "--user", default="Sai", help="User name for API credentials")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open HTML files")
    parser.add_argument("--scanners", nargs='+', 
                       choices=['long', 'short', 'vsr', 'all'],
                       default=['all'],
                       help="Which scanners to run")
    return parser.parse_args()

def run_scanner(script_path, user, scanner_name):
    """Run a scanner script and return the HTML output path"""
    logger.info(f"Running {scanner_name} scanner...")
    
    try:
        # Run the scanner
        result = subprocess.run(
            [sys.executable, script_path, "-u", user],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            logger.info(f"{scanner_name} scanner completed successfully")
            
            # Find the most recent HTML file for this scanner
            if scanner_name == "Long Reversal Daily":
                pattern = "Detailed_Analysis/Long_Reversal_Daily_*.html"
            elif scanner_name == "Short Reversal Daily":
                pattern = "Detailed_Analysis/Short_Reversal_Daily_*.html"
            elif scanner_name == "VSR Momentum":
                pattern = "Detailed_Analysis/Hourly/VSR_*.html"
            else:
                return None
                
            html_files = glob.glob(os.path.join(os.path.dirname(__file__), pattern))
            if html_files:
                # Get the most recent file
                latest_html = max(html_files, key=os.path.getctime)
                return latest_html
        else:
            logger.error(f"{scanner_name} scanner failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
                
    except subprocess.TimeoutExpired:
        logger.error(f"{scanner_name} scanner timed out")
    except Exception as e:
        logger.error(f"Error running {scanner_name} scanner: {e}")
    
    return None

def open_html_files(html_files):
    """Open multiple HTML files in browser tabs"""
    for html_file in html_files:
        if html_file and os.path.exists(html_file):
            try:
                webbrowser.open(f'file://{os.path.abspath(html_file)}')
                logger.info(f"Opened HTML report: {os.path.basename(html_file)}")
                time.sleep(1)  # Small delay between opening tabs
            except Exception as e:
                logger.warning(f"Could not open HTML file {html_file}: {e}")

def main():
    args = parse_args()
    
    logger.info("="*60)
    logger.info("Starting Unified Scanner Runner")
    logger.info(f"User: {args.user}")
    logger.info(f"Scanners to run: {args.scanners}")
    logger.info(f"Auto-open HTML: {not args.no_browser}")
    logger.info("="*60)
    
    # Define scanner paths
    scanners_dir = os.path.join(os.path.dirname(__file__), "scanners")
    
    scanners = {}
    if 'all' in args.scanners or 'long' in args.scanners:
        scanners['Long Reversal Daily'] = os.path.join(scanners_dir, "Long_Reversal_Daily.py")
    if 'all' in args.scanners or 'short' in args.scanners:
        scanners['Short Reversal Daily'] = os.path.join(scanners_dir, "Short_Reversal_Daily.py")
    if 'all' in args.scanners or 'vsr' in args.scanners:
        scanners['VSR Momentum'] = os.path.join(scanners_dir, "VSR_Momentum_Scanner.py")
    
    # Run scanners and collect HTML paths
    html_files = []
    results_summary = []
    
    for scanner_name, script_path in scanners.items():
        if os.path.exists(script_path):
            print(f"\n{'='*40}")
            print(f"Running {scanner_name}...")
            print(f"{'='*40}")
            
            start_time = time.time()
            html_file = run_scanner(script_path, args.user, scanner_name)
            execution_time = time.time() - start_time
            
            if html_file:
                html_files.append(html_file)
                results_summary.append(f"✓ {scanner_name}: Success ({execution_time:.1f}s)")
            else:
                results_summary.append(f"✗ {scanner_name}: Failed or no results")
        else:
            logger.warning(f"Scanner script not found: {script_path}")
            results_summary.append(f"✗ {scanner_name}: Script not found")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SCANNER EXECUTION SUMMARY")
    print(f"{'='*60}")
    for result in results_summary:
        print(result)
    
    # Open HTML files if requested
    if not args.no_browser and html_files:
        print(f"\nOpening {len(html_files)} HTML report(s) in browser...")
        open_html_files(html_files)
    
    # Print HTML file locations
    if html_files:
        print(f"\nHTML Reports Generated:")
        for html_file in html_files:
            print(f"  - {html_file}")
    
    logger.info("Unified Scanner Runner completed")
    print(f"\n{'='*60}")
    print("All scanners completed!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()