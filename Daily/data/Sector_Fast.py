import requests
import pandas as pd
import time
from datetime import datetime
import os
import sys
import json

API_KEY = "YOUR_EODHD_API_KEY"  # Replace with your real EODHD API key

# Cache file to store already fetched sectors
CACHE_FILE = "sector_cache.json"

def load_cache():
    """Load sector cache from file"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Save sector cache to file"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def get_sector(ticker, cache, retry_count=2):
    """Fetch sector information for a ticker with retry logic and caching"""
    
    # Check cache first
    if ticker in cache:
        print(f"[{ticker}] Using cached sector: {cache[ticker]}")
        return cache[ticker]
    
    url = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={API_KEY}&fmt=json"
    
    for attempt in range(retry_count):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 429:  # Rate limit hit
                print(f"[{ticker}] Rate limit hit, waiting 30 seconds...")
                time.sleep(30)
                continue
            elif response.status_code == 404:
                print(f"[{ticker}] Symbol not found")
                cache[ticker] = None
                return None
            elif response.status_code == 422:
                print(f"[{ticker}] Invalid symbol format")
                cache[ticker] = None
                return None
            elif response.status_code != 200:
                print(f"[{ticker}] HTTP {response.status_code}")
                return None
            
            data = response.json()
            sector = data.get("General", {}).get("Sector", None)
            if not sector:
                print(f"[{ticker}] No sector info in response.")
            else:
                print(f"[{ticker}] Found sector: {sector}")
            
            # Cache the result
            cache[ticker] = sector
            return sector
            
        except requests.exceptions.Timeout:
            print(f"[{ticker}] Timeout on attempt {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(2)
        except Exception as e:
            print(f"[{ticker}] Error: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
    
    return None

def main():
    # Load cache
    cache = load_cache()
    print(f"Loaded cache with {len(cache)} entries")
    
    # Load your Excel file
    print(f"\nLoading Ticker.xlsx at {datetime.now()}")
    df = pd.read_excel("Ticker.xlsx")
    print(f"Loaded {len(df)} tickers")
    
    # Add NSE suffix
    df["Symbol"] = df["Ticker"].astype(str) + ".NSE"
    
    # Check if we have a partial result file (for resuming)
    output_file = "Ticker_with_Sector.xlsx"
    temp_file = "Ticker_with_Sector_temp.xlsx"
    
    # Load existing progress if available
    if os.path.exists(temp_file):
        print(f"\nFound temporary file, loading existing data...")
        df_existing = pd.read_excel(temp_file)
        # Merge sector data if available
        if "Sector" in df_existing.columns:
            df = df_existing
            print(f"Loaded existing data with {df['Sector'].notna().sum()} sectors already found")
    
    # Initialize Sector column if not exists
    if "Sector" not in df.columns:
        df["Sector"] = None
    
    # Find tickers that still need sectors
    missing_sectors = df[df["Sector"].isna()].index.tolist()
    print(f"\nNeed to fetch sectors for {len(missing_sectors)} tickers")
    
    if len(missing_sectors) == 0:
        print("All sectors already fetched!")
    else:
        # Process in smaller batches
        batch_size = 5
        save_interval = 20  # Save every 20 tickers
        delay_between_requests = 0.2  # 200ms between requests
        
        print(f"\nStarting to fetch sector information...")
        processed = 0
        
        for idx in missing_sectors:
            ticker = df.iloc[idx]["Symbol"]
            print(f"\n[{processed+1}/{len(missing_sectors)}] Processing {ticker}")
            
            sector = get_sector(ticker, cache)
            df.at[idx, "Sector"] = sector
            processed += 1
            
            # Save cache periodically
            if processed % save_interval == 0:
                save_cache(cache)
                print(f"Cache saved with {len(cache)} entries")
                
                # Also save Excel progress
                print(f"Saving Excel progress...")
                cols = df.columns.tolist()
                if "Sector" in cols:
                    cols.remove("Sector")
                cols.insert(cols.index("Ticker")+1, "Sector")
                df_save = df[cols]
                df_save.to_excel(temp_file, index=False)
                print(f"Progress saved to {temp_file}")
            
            # Small delay between requests
            time.sleep(delay_between_requests)
            
            # Allow interruption with Ctrl+C
            if processed % 10 == 0:
                print(f"\nProcessed {processed}/{len(missing_sectors)} tickers. Press Ctrl+C to stop and save progress.")
    
    # Final save
    print(f"\nSaving final results...")
    save_cache(cache)
    
    # Reorder columns to place Sector next to Ticker
    cols = df.columns.tolist()
    if "Sector" in cols:
        cols.remove("Sector")
    cols.insert(cols.index("Ticker")+1, "Sector")
    df = df[cols]
    
    # Save the final result
    df.to_excel(output_file, index=False)
    
    # Remove temporary file if exists
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # Print summary
    sectors_found = df["Sector"].notna().sum()
    print(f"\n✅ Finished at {datetime.now()}")
    print(f"Total tickers: {len(df)}")
    print(f"Sectors found: {sectors_found}")
    print(f"Missing sectors: {len(df) - sectors_found}")
    print(f"File saved as {output_file}")
    
    # Show sector distribution
    print("\nSector distribution:")
    sector_counts = df["Sector"].value_counts()
    for sector, count in sector_counts.items():
        print(f"  {sector}: {count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress has been saved.")
        print("Run the script again to continue from where you left off.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        print("Progress has been saved. You can run the script again to continue.")
        sys.exit(1)