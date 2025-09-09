#!/usr/bin/env python3
"""
Test ML prediction with sample data
"""

import sqlite3
import pandas as pd
import numpy as np
import joblib
import json
from datetime import datetime

# Load model and metadata
model_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/models/market_regime_gradient_boosting_20250909_133414.pkl'
metadata_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/models/metadata_20250909_133414.json'
scaler_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/models/scaler_20250909_133414.pkl'

print("Loading model...")
model = joblib.load(model_path)
scaler = joblib.load(scaler_path)

with open(metadata_path, 'r') as f:
    metadata = json.load(f)

features = metadata['features']
print(f"Model expects {len(features)} features")

# Get data from Analysis DB
print("\nGetting data from Analysis DB...")
conn = sqlite3.connect('/Users/maverick/PycharmProjects/Analysis/data/warehouse/market_data.db')

query = """
    SELECT * FROM india_breadth 
    WHERE date >= date('now', '-5 days')
    ORDER BY date DESC
    LIMIT 1
"""

df = pd.read_sql_query(query, conn)
conn.close()

if df.empty:
    print("No data found!")
    exit()

print(f"Found data for: {df['date'].iloc[0]}")

# Engineer features
row = df.iloc[0]
print("\nEngineering features...")

# Create feature dict with defaults
feature_values = {}

# Direct mappings
feature_values['binary_breadth_pct'] = row.get('binary_breadth_pct', 50)
feature_values['weighted_breadth_index'] = row.get('weighted_breadth_index', 0.5)
feature_values['breadth_momentum'] = row.get('breadth_momentum', 0)
feature_values['market_momentum_index'] = row.get('market_momentum_index', 0)
feature_values['fast_wm_pct'] = row.get('fast_wm_pct', 50)
feature_values['slow_wm_pct'] = row.get('slow_wm_pct', 50)

# Calculated features
feature_values['breadth_strength'] = feature_values['binary_breadth_pct'] / 100.0
feature_values['breadth_momentum_ma5'] = feature_values['breadth_momentum']  # Simplified
feature_values['ad_ratio'] = row.get('active_positive', 100) / max(row.get('active_negative', 100), 1)
feature_values['ad_diff'] = row.get('active_positive', 100) - row.get('active_negative', 100)
feature_values['ad_ratio_ma5'] = feature_values['ad_ratio']  # Simplified
feature_values['sma_breadth_avg'] = (feature_values['fast_wm_pct'] + feature_values['slow_wm_pct']) / 2
feature_values['sma_breadth_diff'] = feature_values['fast_wm_pct'] - feature_values['slow_wm_pct']
feature_values['trend_strength'] = abs(feature_values['breadth_momentum'])
feature_values['trend_change'] = 0  # Simplified - would need historical data
feature_values['breadth_volatility'] = 10  # Default value

# L/S ratio features - use defaults for now
feature_values['ls_ratio_combined'] = 1.0
feature_values['ls_ratio_ma5'] = 1.0
feature_values['ls_ratio_ma10'] = 1.0
feature_values['ls_momentum'] = 0

# Volume features - use defaults
feature_values['avg_volume_ratio'] = 1.0
feature_values['volume_strength'] = 50.0

# Create feature array in correct order
X = []
for feature in features:
    value = feature_values.get(feature, 0)
    X.append(value)
    print(f"  {feature}: {value:.2f}")

X = np.array([X])
print(f"\nFeature array shape: {X.shape}")

# Scale features
print("\nScaling features...")
X_scaled = scaler.transform(X)

# Make prediction
print("\nMaking prediction...")
prediction = model.predict(X_scaled)[0]
proba = model.predict_proba(X_scaled)[0]
confidence = float(np.max(proba))

# Map to regime
regime_map = {0: 'Bearish', 1: 'Neutral', 2: 'Bullish'}
regime = regime_map.get(int(prediction), 'Unknown')

print("\n" + "="*50)
print(f"PREDICTION RESULT:")
print(f"  Regime: {regime}")
print(f"  Confidence: {confidence:.1%}")
print(f"  Probabilities: Bearish={proba[0]:.1%}, Neutral={proba[1] if len(proba) > 1 else 0:.1%}, Bullish={proba[2] if len(proba) > 2 else 0:.1%}")
print("="*50)