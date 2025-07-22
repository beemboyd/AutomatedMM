#!/usr/bin/env python3
"""
Analyze P&L data to find the most profitable trades
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Read the P&L Excel file
file_path = '/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07202025-PNL.xlsx'

# Try to read the file and understand its structure
try:
    # First, check all sheets
    excel_file = pd.ExcelFile(file_path)
    print("Available sheets:", excel_file.sheet_names)
    
    # Read each sheet to understand structure
    for sheet in excel_file.sheet_names:
        print(f"\n{'='*60}")
        print(f"Sheet: {sheet}")
        print('='*60)
        
        # Read with no header first to see the structure
        df = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=20)
        print("First 20 rows preview:")
        print(df)
        
        # Find where actual data starts
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            non_null_count = row.notna().sum()
            if non_null_count > 5:
                print(f"\nRow {idx} has {non_null_count} non-null values: {list(row.dropna())}")
        
except Exception as e:
    print(f"Error reading file: {e}")