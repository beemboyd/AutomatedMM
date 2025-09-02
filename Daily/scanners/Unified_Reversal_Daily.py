#!/usr/bin/env python3
"""
Unified Reversal Scanner - Combines Long and Short Reversal Daily Scanners
Uses exact same logic from both scanners, just combines data fetching
Author: Claude
Date: 2025-09-01
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the ACTUAL scanners
import Daily.scanners.Long_Reversal_Daily as LongScanner
import Daily.scanners.Short_Reversal_Daily as ShortScanner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Main function - run both scanners with shared data cache"""
    print("\n" + "="*60)
    print("UNIFIED REVERSAL SCANNER")
    print("Running Long and Short Reversal Daily Scanners Together")
    print("="*60 + "\n")
    
    start_time = time.time()
    
    try:
        # The scanners will automatically initialize with default user when imported
        # They parse args at module level
        
        # Initialize shared components ONCE
        print("Initializing shared components...")
        
        # Both scanners already have kite initialized at module level
        # Just need to ensure they share the same cache
        
        # Get tickers ONCE
        tickers = LongScanner.read_ticker_file()
        
        # Share the data cache between both scanners - THIS IS THE KEY OPTIMIZATION
        shared_cache = LongScanner.DataCache()
        LongScanner.data_cache = shared_cache
        ShortScanner.data_cache = shared_cache
        
        # Both scanners now share the same cache, so when Long fetches data,
        # Short will use the cached version instead of making another API call
        
        print(f"Starting scan for {len(tickers)} tickers...")
        print("="*60)
        
        # Process tickers using EXACT logic from each scanner
        long_results = []
        short_results = []
        
        for i, ticker in enumerate(tickers):
            try:
                # Use the ACTUAL process_ticker functions from each scanner
                long_result = LongScanner.process_ticker(ticker)
                if long_result:
                    long_results.append(long_result)
                
                # Short scanner uses same cached data
                short_result = ShortScanner.process_ticker(ticker)
                if short_result:
                    short_results.append(short_result)
                
                # Progress update
                if (i + 1) % 50 == 0:
                    print(f"Processed {i+1}/{len(tickers)} tickers...")
                    
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                continue
        
        print("="*60)
        print(f"Scan complete. Found {len(long_results)} long and {len(short_results)} short patterns")
        
        # Generate outputs using EXACT functions from each scanner
        if long_results:
            print("\nGenerating Long Reversal outputs...")
            # Create timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create DataFrame and sort by score (descending)
            long_df = LongScanner.pd.DataFrame(long_results)
            long_df = long_df.sort_values('Score', ascending=False)
            
            # Save Excel
            excel_file = os.path.join(LongScanner.RESULTS_DIR, f"Long_Reversal_Daily_{timestamp}.xlsx")
            long_df.to_excel(excel_file, index=False)
            print(f"Saved Long results to: {excel_file}")
            
            # Generate HTML using Long scanner's function
            html_file = os.path.join(LongScanner.HTML_DIR, f"Long_Reversal_Daily_{timestamp}.html")
            LongScanner.generate_html_report(long_df, html_file, LongScanner.__file__)
            print(f"Created Long HTML report: {html_file}")
            
            # Send Telegram notification if enabled
            try:
                telegram_notifier = LongScanner.TelegramNotifier()
                if telegram_notifier.enabled:
                    telegram_notifier.send_reversal_notification(
                        long_df, 
                        'long',
                        LongScanner.GITHUB_HTML_BASE_URL + os.path.basename(html_file)
                    )
            except:
                pass
        
        if short_results:
            print("\nGenerating Short Reversal outputs...")
            # Create timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create DataFrame and sort by score (descending)
            short_df = ShortScanner.pd.DataFrame(short_results)
            short_df = short_df.sort_values('Score', ascending=False)
            
            # Save Excel
            excel_file = os.path.join(ShortScanner.RESULTS_DIR, f"Short_Reversal_Daily_{timestamp}.xlsx")
            short_df.to_excel(excel_file, index=False)
            print(f"Saved Short results to: {excel_file}")
            
            # Generate HTML using Short scanner's function
            html_file = os.path.join(ShortScanner.HTML_DIR, f"Short_Reversal_Daily_{timestamp}.html")
            ShortScanner.generate_html_report(short_df, html_file, ShortScanner.__file__)
            print(f"Created Short HTML report: {html_file}")
            
            # Send Telegram notification if enabled
            try:
                telegram_notifier = ShortScanner.TelegramNotifier()
                if telegram_notifier.enabled:
                    telegram_notifier.send_reversal_notification(
                        short_df,
                        'short', 
                        ShortScanner.GITHUB_HTML_BASE_URL + os.path.basename(html_file)
                    )
            except:
                pass
        
        # Print summary
        elapsed_time = time.time() - start_time
        print("\n" + "="*60)
        print("UNIFIED SCAN COMPLETE")
        print(f"Time taken: {elapsed_time:.2f} seconds")
        print(f"Long patterns found: {len(long_results)}")
        print(f"Short patterns found: {len(short_results)}")
        print(f"API calls saved: ~{len(tickers)} (by sharing data cache)")
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"Fatal error in unified scanner: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()