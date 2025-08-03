#!/usr/bin/env python3
"""
Simple utility to read and display Excel file contents
"""

import pandas as pd
import sys

def read_excel(file_path):
    """Read and display Excel file contents"""
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Display basic information
        print(f"\nFile: {file_path}")
        print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        print(f"Columns: {', '.join(df.columns)}")
        
        # Display the content
        print("\nContent:")
        print(df.to_string())
        
        return True
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_excel.py <excel_file_path>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    read_excel(file_path)