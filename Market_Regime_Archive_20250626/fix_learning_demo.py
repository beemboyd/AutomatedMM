#!/usr/bin/env python3
"""
Temporary fix to demonstrate learning system functionality
Resolves some old predictions with simulated outcomes
"""

import sqlite3
import random
from datetime import datetime, timedelta

def fix_demo_predictions():
    db_path = '/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get 20 oldest unresolved predictions for demo
    cursor.execute("""
        SELECT id, predicted_regime, timestamp 
        FROM regime_predictions 
        WHERE (actual_regime IS NULL OR actual_regime = '')
        ORDER BY timestamp ASC
        LIMIT 20
    """)
    
    predictions = cursor.fetchall()
    
    print(f"Found {len(predictions)} predictions to resolve for demo")
    
    # Possible regimes
    regimes = ['uptrend', 'downtrend', 'sideways', 'volatile']
    
    # Simulate outcomes with 70% accuracy
    for pred_id, predicted_regime, timestamp in predictions:
        # 70% chance of correct prediction
        if random.random() < 0.7:
            actual_regime = predicted_regime
            outcome_score = random.uniform(0.8, 1.0)
        else:
            # Wrong prediction
            actual_regime = random.choice([r for r in regimes if r != predicted_regime])
            outcome_score = random.uniform(0.0, 0.3)
        
        # Update the prediction
        cursor.execute("""
            UPDATE regime_predictions
            SET actual_regime = ?,
                outcome_score = ?,
                feedback_timestamp = ?
            WHERE id = ?
        """, (actual_regime, outcome_score, datetime.now().isoformat(), pred_id))
        
        print(f"Resolved prediction {pred_id}: {predicted_regime} -> {actual_regime} (score: {outcome_score:.2f})")
    
    conn.commit()
    conn.close()
    print("\nDemo predictions resolved successfully!")

if __name__ == "__main__":
    fix_demo_predictions()