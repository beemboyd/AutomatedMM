#!/usr/bin/env python3
"""
Fix the date issue in historical breadth data
- Remove the incorrect Aug 2 entry (Saturday)
- Update Aug 1 entry with the SMA breadth data
"""

import json
from datetime import datetime

# Load the data
with open('historical_breadth_data/sma_breadth_historical_latest.json', 'r') as f:
    data = json.load(f)

# Find and process the last entries
modified = False
aug1_entry = None
aug2_entry = None

# Find the entries
for i, entry in enumerate(data):
    if entry['date'] == '2025-08-01':
        aug1_entry = (i, entry)
    elif entry['date'] == '2025-08-02':
        aug2_entry = (i, entry)

if aug1_entry and aug2_entry:
    # Update Aug 1 entry with SMA breadth data from Aug 2
    aug1_idx, aug1_data = aug1_entry
    aug2_idx, aug2_data = aug2_entry
    
    # Merge the SMA breadth data into Aug 1
    aug1_data['sma_breadth'] = aug2_data['sma_breadth']
    aug1_data['market_regime'] = aug2_data['market_regime']
    aug1_data['market_score'] = aug2_data['market_score']
    aug1_data['index_momentum'] = aug2_data['index_momentum']
    aug1_data['method'] = aug2_data['method']
    
    # Update timestamp to end of day Aug 1
    aug1_data['timestamp'] = '2025-08-01T15:30:00'
    
    # Remove the Aug 2 entry
    data.pop(aug2_idx)
    
    print("Fixed date issue:")
    print(f"- Updated August 1 entry with SMA breadth data")
    print(f"- Removed incorrect August 2 (Saturday) entry")
    print(f"- SMA20: {aug1_data['sma_breadth']['sma20_percent']}%")
    print(f"- SMA50: {aug1_data['sma_breadth']['sma50_percent']}%")
    
    # Save the corrected data
    with open('historical_breadth_data/sma_breadth_historical_latest.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\nData saved successfully!")
else:
    print("Could not find the expected entries to fix")