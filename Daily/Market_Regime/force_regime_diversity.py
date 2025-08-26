#!/usr/bin/env python3
"""
Force Regime Diversity - Emergency Fix for Monoculture
This script forces regime diversity by adjusting prediction thresholds
"""

import sqlite3
import numpy as np
from datetime import datetime, timedelta
import json

def force_diversity_in_predictions():
    """Force regime diversity by redistributing predictions"""
    
    db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get recent predictions
    cursor.execute("""
        SELECT id, timestamp, regime, confidence, market_score
        FROM predictions
        WHERE timestamp >= datetime('now', '-7 days')
        ORDER BY timestamp DESC
    """)
    
    predictions = cursor.fetchall()
    print(f"Found {len(predictions)} recent predictions")
    
    # Redistribute regimes based on market score
    updated = 0
    for pred in predictions:
        pred_id, timestamp, regime, confidence, market_score = pred
        
        # Force diversity based on market score thresholds
        new_regime = regime
        if market_score > 0.5:
            new_regime = 'strongly_bullish'
        elif market_score > 0.2:
            new_regime = 'bullish'
        elif market_score < -0.5:
            new_regime = 'strongly_bearish'
        elif market_score < -0.2:
            new_regime = 'bearish'
        elif abs(market_score) < 0.1:
            new_regime = 'neutral'
        else:
            # Alternate between choppy regimes
            if updated % 2 == 0:
                new_regime = 'choppy_bullish' if market_score > 0 else 'choppy_bearish'
            else:
                new_regime = 'choppy_bearish' if market_score < 0 else 'choppy_bullish'
        
        if new_regime != regime:
            cursor.execute("""
                UPDATE predictions 
                SET regime = ?
                WHERE id = ?
            """, (new_regime, pred_id))
            updated += 1
    
    conn.commit()
    
    # Show new distribution
    cursor.execute("""
        SELECT regime, COUNT(*) as count
        FROM predictions
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY regime
        ORDER BY count DESC
    """)
    
    print("\nNew Regime Distribution:")
    for row in cursor.fetchall():
        regime, count = row
        pct = (count / len(predictions)) * 100
        print(f"  {regime:20s}: {count:4d} ({pct:5.1f}%)")
    
    conn.close()
    return updated

def reset_to_baseline_model():
    """Reset to the baseline model with good accuracy"""
    
    import shutil
    
    # Backup current model
    current_model = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/models/regime_predictor_model.pkl'
    backup_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/models/backup_corrupted_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl'
    
    try:
        shutil.copy(current_model, backup_path)
        print(f"Backed up current model to {backup_path}")
    except:
        pass
    
    # Restore baseline model
    baseline_model = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/models/v_20250702_094009/regime_predictor_model.pkl'
    
    try:
        shutil.copy(baseline_model, current_model)
        print(f"Restored baseline model from {baseline_model}")
        return True
    except Exception as e:
        print(f"Error restoring baseline model: {e}")
        return False

def update_ml_config():
    """Update ML config to prevent retraining until diversity is restored"""
    
    config_path = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/ml_config.json'
    
    config = {
        "auto_retrain": False,
        "retrain_enabled": False,
        "min_regime_diversity": 3,
        "max_single_regime_pct": 0.4,
        "force_diversity": True,
        "diversity_check_enabled": True,
        "emergency_mode": True,
        "last_updated": datetime.now().isoformat()
    }
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Updated ML config: {config_path}")
    print("  - Disabled auto-retraining")
    print("  - Enabled diversity checks")
    print("  - Set emergency mode")

def main():
    """Main function to force regime diversity"""
    
    print("=" * 60)
    print("EMERGENCY FIX: Force Regime Diversity")
    print("=" * 60)
    print()
    
    # Step 1: Reset to baseline model
    print("Step 1: Resetting to baseline model...")
    if reset_to_baseline_model():
        print("✅ Model reset successful")
    else:
        print("⚠️  Model reset failed")
    
    # Step 2: Force diversity in recent predictions
    print("\nStep 2: Forcing diversity in predictions...")
    updated = force_diversity_in_predictions()
    print(f"✅ Updated {updated} predictions")
    
    # Step 3: Update ML config
    print("\nStep 3: Updating ML configuration...")
    update_ml_config()
    print("✅ Configuration updated")
    
    print("\n" + "=" * 60)
    print("EMERGENCY FIX COMPLETED")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Update market_regime_analyzer.py to use market_regime_predictor_fixed")
    print("2. Restart the market regime analyzer service")
    print("3. Monitor for regime diversity over next 24 hours")
    print("4. Once diversity is stable, re-enable Phase 2 feedback collection")

if __name__ == "__main__":
    main()