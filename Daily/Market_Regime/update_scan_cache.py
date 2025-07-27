#!/usr/bin/env python3
"""Update scan cache with correct data"""

import json
import os
from datetime import datetime

# Create scan results directory if it doesn't exist
scan_dir = "scan_results"
os.makedirs(scan_dir, exist_ok=True)

# Create cache file with correct counts
scan_data = {
    "timestamp": datetime.now().isoformat(),
    "long_count": 11,
    "short_count": 46,
    "ratio": 0.239,
    "long_file": "/Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_20250725_153916.xlsx",
    "short_file": "/Users/maverick/PycharmProjects/India-TS/Daily/results-s/Short_Reversal_Daily_20250725_153951.xlsx"
}

# Save to cache file
cache_file = os.path.join(scan_dir, f"reversal_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
with open(cache_file, 'w') as f:
    json.dump(scan_data, f, indent=2)

print(f"Scan cache updated: {cache_file}")
print(f"Long: {scan_data['long_count']}, Short: {scan_data['short_count']}, Ratio: {scan_data['ratio']:.3f}")