#!/usr/bin/env python3
"""
Test the 30-minute prediction and verification cycle
"""

import sqlite3
from datetime import datetime, timedelta
import pandas as pd

def check_prediction_cycle():
    """Check the status of predictions and resolutions"""
    db_path = '/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    
    print("="*60)
    print("MARKET REGIME PREDICTION CYCLE STATUS")
    print("="*60)
    print(f"Current Time: {datetime.now()}")
    print()
    
    # 1. Check total predictions
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM regime_predictions")
    total = cursor.fetchone()[0]
    print(f"Total Predictions: {total}")
    
    # 2. Check resolved vs pending
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN actual_regime IS NOT NULL AND actual_regime != '' THEN 1 END) as resolved,
            COUNT(CASE WHEN actual_regime IS NULL OR actual_regime = '' THEN 1 END) as pending
        FROM regime_predictions
    """)
    resolved, pending = cursor.fetchone()
    print(f"Resolved: {resolved}")
    print(f"Pending: {pending}")
    print()
    
    # 3. Check recent predictions
    print("Recent Predictions (last 10):")
    print("-"*60)
    recent_df = pd.read_sql_query("""
        SELECT 
            datetime(timestamp, 'localtime') as time,
            predicted_regime,
            confidence,
            actual_regime,
            outcome_score,
            CASE 
                WHEN actual_regime IS NOT NULL AND actual_regime != '' THEN 'Resolved'
                ELSE 'Pending'
            END as status
        FROM regime_predictions
        ORDER BY timestamp DESC
        LIMIT 10
    """, conn)
    
    print(recent_df.to_string(index=False))
    print()
    
    # 4. Check predictions ready for resolution
    cutoff = datetime.now() - timedelta(minutes=30)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM regime_predictions
        WHERE (actual_regime IS NULL OR actual_regime = '')
        AND timestamp <= ?
    """, (cutoff.isoformat(),))
    ready = cursor.fetchone()[0]
    print(f"Predictions ready for resolution (>30 min old): {ready}")
    print()
    
    # 5. Check resolution performance
    cursor.execute("""
        SELECT 
            predicted_regime,
            actual_regime,
            COUNT(*) as count,
            AVG(outcome_score) as avg_score
        FROM regime_predictions
        WHERE actual_regime IS NOT NULL AND actual_regime != ''
        GROUP BY predicted_regime, actual_regime
        ORDER BY count DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    if results:
        print("Resolution Performance (Predicted → Actual):")
        print("-"*60)
        print(f"{'Predicted':<20} {'Actual':<20} {'Count':<10} {'Avg Score':<10}")
        print("-"*60)
        for row in results:
            print(f"{row[0]:<20} {row[1]:<20} {row[2]:<10} {row[3]:<10.2f}")
    else:
        print("No resolved predictions yet")
    
    print()
    
    # 6. Check prediction frequency
    print("Prediction Frequency (last 24 hours):")
    print("-"*60)
    freq_df = pd.read_sql_query("""
        SELECT 
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as predictions
        FROM regime_predictions
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY hour
        ORDER BY hour DESC
        LIMIT 10
    """, conn)
    
    if not freq_df.empty:
        print(freq_df.to_string(index=False))
    else:
        print("No predictions in last 24 hours")
    
    conn.close()
    print("\n" + "="*60)


def simulate_prediction():
    """Simulate a new prediction for testing"""
    from Daily.Market_Regime.market_regime_predictor import MarketRegimePredictor
    
    print("\nSimulating new prediction...")
    predictor = MarketRegimePredictor()
    
    # Make a prediction
    result = predictor.predict_regime({
        'long_count': 45,
        'short_count': 20,
        'timestamp': datetime.now().isoformat()
    })
    
    print(f"New prediction: {result['predicted_regime']} (confidence: {result['confidence']:.2%})")
    print("This prediction will be ready for resolution in 30 minutes")


if __name__ == "__main__":
    # Check current status
    check_prediction_cycle()
    
    # Ask if user wants to simulate a prediction
    response = input("\nSimulate a new prediction? (y/n): ")
    if response.lower() == 'y':
        simulate_prediction()
        print("\nWait 30 minutes and run the outcome resolver to see it resolved!")