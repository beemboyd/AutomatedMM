#!/usr/bin/env python3
"""
Test ML Integration
"""

import requests
import json
from datetime import datetime

print("\n" + "="*60)
print("ML MARKET REGIME INTEGRATION TEST")
print("="*60)

# Test ML Prediction API
print("\n1. Testing ML Prediction API (port 8083)...")
try:
    response = requests.get("http://localhost:8083/api/v1/predict", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("✅ ML API Working!")
        print(f"   - Regime: {data.get('regime', 'Unknown')}")
        print(f"   - Confidence: {data.get('confidence', 0):.1%}")
        print(f"   - Model Version: {data.get('model_version', 'Unknown')}")
    else:
        print(f"❌ ML API Error: Status {response.status_code}")
except Exception as e:
    print(f"❌ ML API Error: {e}")

# Test ML Monitoring Dashboard API
print("\n2. Testing ML Monitoring Dashboard (port 8082)...")
try:
    response = requests.get("http://localhost:8082/api/status", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("✅ Monitoring Dashboard Working!")
        print(f"   - Market Breadth: {data.get('market_breadth', 0):.1f}%")
        print(f"   - Current Regime: {data.get('current_regime', 'Unknown')}")
        print(f"   - L/S Ratio: {data.get('ls_ratio', 0):.2f}")
    else:
        print(f"❌ Monitoring Dashboard Error: Status {response.status_code}")
except Exception as e:
    print(f"❌ Monitoring Dashboard Error: {e}")

# Test integration module directly
print("\n3. Testing Integration Module...")
try:
    import sys
    sys.path.insert(0, '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime')
    from ml_dashboard_integration_new import get_ml_regime_prediction
    
    ml_data = get_ml_regime_prediction()
    print("✅ Integration Module Working!")
    print(f"   - Data: {json.dumps(ml_data, indent=2)}")
except Exception as e:
    print(f"❌ Integration Module Error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)

# Display current values for dashboard
print("\n📊 VALUES TO DISPLAY ON DASHBOARD:")
print("-"*40)
try:
    response = requests.get("http://localhost:8083/api/v1/predict", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"ML Market Regime Prediction: {data.get('regime', 'Unknown')}")
        print(f"Confidence: {data.get('confidence', 0):.1%}")
        print(f"Timestamp: {data.get('timestamp', datetime.now().isoformat())}")
        
        probs = data.get('probabilities', {})
        print(f"\nProbabilities:")
        print(f"  Bullish: {probs.get('Bullish', 0):.1%}")
        print(f"  Neutral: {probs.get('Neutral', 0):.1%}")
        print(f"  Bearish: {probs.get('Bearish', 0):.1%}")
except:
    pass

print("\nURLs to access:")
print("  ML Monitoring Dashboard: http://localhost:8082")
print("  Main Dashboard: http://localhost:8080")
print("  ML Prediction API: http://localhost:8083/api/v1/predict")