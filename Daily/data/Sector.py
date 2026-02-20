import requests
import pandas as pd
import time
from datetime import datetime
import os

API_KEY = "YOUR_EODHD_API_KEY"  # Replace with your real EODHD API key

def get_sector(ticker, retry_count=3):
    """Fetch sector information for a ticker with retry logic"""
    url = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={API_KEY}&fmt=json"
    
    for attempt in range(retry_count):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 429:  # Rate limit hit
                print(f"[{ticker}] Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                continue
            elif response.status_code != 200:
                print(f"[{ticker}] HTTP {response.status_code}: {response.text[:100]}")
                return None
            
            data = response.json()
            sector = data.get("General", {}).get("Sector", None)
            if not sector:
                print(f"[{ticker}] No sector info in response.")
            else:
                print(f"[{ticker}] Found sector: {sector}")
            return sector
            
        except requests.exceptions.Timeout:
            print(f"[{ticker}] Timeout on attempt {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(5)
        except Exception as e:
            print(f"[{ticker}] Error on attempt {attempt + 1}: {e}")
            if attempt < retry_count - 1:
                time.sleep(5)
    
    return None

# Load your Excel file
print(f"Loading Ticker.xlsx at {datetime.now()}")
df = pd.read_excel("Ticker.xlsx")
print(f"Loaded {len(df)} tickers")

# Add NSE suffix
df["Symbol"] = df["Ticker"].astype(str) + ".NSE"

# Check if we have a partial result file (for resuming)
output_file = "Ticker_with_Sector.xlsx"
temp_file = "Ticker_with_Sector_temp.xlsx"

start_index = 0
if os.path.exists(temp_file):
    print(f"Found temporary file, loading progress...")
    df_temp = pd.read_excel(temp_file)
    # Find where we left off
    if "Sector" in df_temp.columns:
        last_processed = df_temp[df_temp["Sector"].notna()].index
        if len(last_processed) > 0:
            start_index = last_processed[-1] + 1
            print(f"Resuming from index {start_index}")
            # Copy existing sector data
            df["Sector"] = None
            df.loc[:start_index-1, "Sector"] = df_temp.loc[:start_index-1, "Sector"]

# Initialize Sector column if not exists
if "Sector" not in df.columns:
    df["Sector"] = None

# Fetch sector info from EODHD with rate limiting
print(f"\nStarting to fetch sector information from index {start_index}...")
batch_size = 10
delay_between_batches = 2  # seconds

for i in range(start_index, len(df)):
    ticker = df.iloc[i]["Symbol"]
    print(f"\n[{i+1}/{len(df)}] Processing {ticker}")
    
    sector = get_sector(ticker)
    df.at[i, "Sector"] = sector
    
    # Save progress every batch_size tickers
    if (i + 1) % batch_size == 0:
        print(f"\nSaving progress at ticker {i+1}...")
        # Reorder columns to place Sector next to Ticker
        cols = df.columns.tolist()
        if "Sector" in cols:
            cols.remove("Sector")
        cols.insert(cols.index("Ticker")+1, "Sector")
        df_save = df[cols]
        df_save.to_excel(temp_file, index=False)
        print(f"Progress saved. Waiting {delay_between_batches} seconds before next batch...")
        time.sleep(delay_between_batches)
    
    # Small delay between each request to avoid rate limiting
    time.sleep(0.5)

# Final save
print(f"\nSaving final results...")
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
