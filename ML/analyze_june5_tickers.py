#!/usr/bin/env python3
"""
Analyze ticker frequencies across Brooks Higher Probability LONG Reversal reports from June 5, 2025
"""

import pandas as pd
import os
from collections import Counter
from datetime import datetime

# Define the directory and files
results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results/"
files = [
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_08_58.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_09_31.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_10_31.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_11_30.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_12_30.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_13_30.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_14_31.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_15_31.xlsx",
    "Brooks_Higher_Probability_LONG_Reversal_05_06_2025_16_00.xlsx"
]

# Dictionary to store ticker occurrences by file
ticker_occurrences = {}
all_tickers = []

print("Analyzing Brooks Higher Probability LONG Reversal reports from June 5, 2025")
print("=" * 80)

for file in files:
    filepath = os.path.join(results_dir, file)
    time_str = file.split("_")[-2] + "_" + file.split("_")[-1].replace(".xlsx", "")
    
    try:
        # Read the Excel file
        df = pd.read_excel(filepath)
        
        # Print column names to identify ticker column
        print(f"\nFile: {file}")
        print(f"Columns: {list(df.columns)}")
        
        # Try to find ticker column (common names: 'Ticker', 'Symbol', 'ticker', 'symbol')
        ticker_col = None
        for col in df.columns:
            if col.lower() in ['ticker', 'symbol', 'stock', 'scrip']:
                ticker_col = col
                break
        
        if ticker_col is None and len(df.columns) > 0:
            # If no standard column name, assume first column is ticker
            ticker_col = df.columns[0]
        
        if ticker_col:
            tickers = df[ticker_col].tolist()
            # Clean tickers (remove NaN and convert to string)
            tickers = [str(t).strip() for t in tickers if pd.notna(t) and str(t).strip()]
            
            ticker_occurrences[time_str] = tickers
            all_tickers.extend(tickers)
            
            print(f"Found {len(tickers)} tickers in column '{ticker_col}'")
            print(f"Sample tickers: {tickers[:5] if len(tickers) > 5 else tickers}")
        else:
            print(f"Could not identify ticker column in {file}")
            
    except Exception as e:
        print(f"Error reading {file}: {str(e)}")

# Count ticker frequencies
ticker_counts = Counter(all_tickers)

print("\n" + "=" * 80)
print("TICKER FREQUENCY ANALYSIS")
print("=" * 80)
print(f"\nTotal unique tickers: {len(ticker_counts)}")
print(f"Total ticker occurrences: {len(all_tickers)}")

# Sort by frequency
sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)

# Display tickers by frequency
print("\nTickers appearing in multiple reports:")
print("-" * 40)
for ticker, count in sorted_tickers:
    if count > 1:
        print(f"{ticker}: {count} times")

print("\nTickers appearing only once:")
print("-" * 40)
single_tickers = [ticker for ticker, count in sorted_tickers if count == 1]
print(f"Total: {len(single_tickers)} tickers")
print(f"List: {', '.join(single_tickers[:20])}{'...' if len(single_tickers) > 20 else ''}")

# Show ticker presence across time slots
print("\n" + "=" * 80)
print("TICKER PRESENCE BY TIME SLOT")
print("=" * 80)

# Create a matrix showing which tickers appear at which times
time_slots = sorted(ticker_occurrences.keys())
unique_tickers = sorted(set(all_tickers))

# Show tickers that appear frequently
frequent_tickers = [ticker for ticker, count in ticker_counts.items() if count >= 3]
if frequent_tickers:
    print("\nFrequently appearing tickers (3+ times):")
    for ticker in sorted(frequent_tickers):
        appearances = []
        for time_slot in time_slots:
            if ticker in ticker_occurrences.get(time_slot, []):
                # Extract just the time part
                time_part = time_slot.split('_')[0]
                appearances.append(time_part)
        print(f"\n{ticker} (appeared {len(appearances)} times):")
        print(f"  Times: {', '.join(appearances)}")

# Summary statistics
print("\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)
print(f"Average tickers per report: {len(all_tickers) / len(files):.1f}")
print(f"Most common ticker: {sorted_tickers[0][0]} ({sorted_tickers[0][1]} times)")
print(f"Tickers appearing in all 9 reports: {sum(1 for _, count in ticker_counts.items() if count == 9)}")
print(f"Tickers appearing in 5+ reports: {sum(1 for _, count in ticker_counts.items() if count >= 5)}")