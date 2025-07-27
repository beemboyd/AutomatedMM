#!/usr/bin/env python3
"""Update scan history with current data"""

import json
import os
from datetime import datetime, timedelta

# Create data directory if it doesn't exist
data_dir = "data"
os.makedirs(data_dir, exist_ok=True)

# Load existing scan history
history_file = os.path.join(data_dir, "scan_history.json")
if os.path.exists(history_file):
    with open(history_file, 'r') as f:
        scan_history = json.load(f)
else:
    scan_history = []

# Add current data point
current_data = {
    "timestamp": datetime.now().isoformat(),
    "long_count": 11,
    "short_count": 46,
    "ratio": 0.239,
    "regime": "strong_downtrend",
    "confidence": 0.85
}

# Add to history
scan_history.append(current_data)

# Keep only last 30 days of data
cutoff_date = datetime.now() - timedelta(days=30)
scan_history = [
    entry for entry in scan_history 
    if datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')) > cutoff_date
]

# Save updated history
with open(history_file, 'w') as f:
    json.dump(scan_history, f, indent=2)

print(f"Updated scan history with current data: L={current_data['long_count']}, S={current_data['short_count']}, Ratio={current_data['ratio']:.3f}")
print(f"Total history entries: {len(scan_history)}")