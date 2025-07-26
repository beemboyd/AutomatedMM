#!/usr/bin/env python
import pandas as pd
import json
from datetime import datetime, timedelta

# Load scan history
with open('/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/scan_history.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
df['date'] = df['timestamp'].dt.date

print(f'Total records: {len(df)}')
print(f'Date range: {df["date"].min()} to {df["date"].max()}')
print(f'Unique dates: {df["date"].nunique()}')
print('\nDaily counts:')
print(df.groupby('date').size().tail(10))

# Check what data we have for different timeframes
now = datetime.now()
for days in [1, 5, 10, 20]:
    cutoff = now - timedelta(days=days)
    tf_data = df[df['timestamp'] >= cutoff]
    daily_data = tf_data.groupby('date').last()
    print(f'\nTimeframe {days}d: {len(daily_data)} days, L/S totals: {daily_data["long_count"].sum()}/{daily_data["short_count"].sum()}')