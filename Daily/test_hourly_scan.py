import pandas as pd
import os
import glob

# Find latest hourly scan file
results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results-h"
files = glob.glob(os.path.join(results_dir, "Long_Reversal_Hourly_*.xlsx"))

if files:
    latest_file = max(files, key=os.path.getctime)
    print(f"Latest file: {os.path.basename(latest_file)}")
    
    # Read the file
    df = pd.read_excel(latest_file)
    print(f"\nColumns: {list(df.columns)}")
    print(f"Number of tickers: {len(df)}")
    
    if 'Ticker' in df.columns:
        print(f"\nTickers: {df['Ticker'].tolist()}")
else:
    print("No hourly scan files found")