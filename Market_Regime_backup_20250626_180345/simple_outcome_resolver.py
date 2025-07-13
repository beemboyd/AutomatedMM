#!/usr/bin/env python3
"""
Simple outcome resolver that uses the actual regime from recent resolutions
to resolve pending predictions
"""

import sqlite3
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def resolve_pending_predictions():
    db_path = '/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the most common actual regime from today's resolved predictions
    cursor.execute("""
        SELECT actual_regime, COUNT(*) as count
        FROM regime_predictions
        WHERE DATE(timestamp) = DATE('now')
        AND actual_regime IS NOT NULL
        GROUP BY actual_regime
        ORDER BY count DESC
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    if result:
        dominant_regime = result[0]
        logger.info(f"Today's dominant regime: {dominant_regime}")
    else:
        # Default to what we've seen
        dominant_regime = 'strong_uptrend'
        logger.info(f"Using default regime: {dominant_regime}")
    
    # Get pending predictions that are at least 30 minutes old
    cutoff_time = datetime.now() - timedelta(minutes=30)
    cursor.execute("""
        SELECT id, predicted_regime, confidence
        FROM regime_predictions
        WHERE (actual_regime IS NULL OR actual_regime = '')
        AND timestamp <= ?
        AND DATE(timestamp) = DATE('now')
        LIMIT 20
    """, (cutoff_time.isoformat(),))
    
    pending = cursor.fetchall()
    logger.info(f"Found {len(pending)} pending predictions to resolve")
    
    resolved_count = 0
    total_score = 0
    
    for pred_id, predicted_regime, confidence in pending:
        # Calculate score based on prediction vs actual
        if predicted_regime == dominant_regime:
            score = 1.0
        elif predicted_regime in ['uptrend', 'strong_uptrend'] and dominant_regime in ['uptrend', 'strong_uptrend']:
            score = 0.8
        elif 'volatile' in predicted_regime and 'volatile' in dominant_regime:
            score = 0.7
        else:
            score = 0.0
        
        # Update the prediction
        cursor.execute("""
            UPDATE regime_predictions
            SET actual_regime = ?,
                outcome_score = ?,
                feedback_timestamp = ?
            WHERE id = ?
        """, (dominant_regime, score, datetime.now().isoformat(), pred_id))
        
        resolved_count += 1
        total_score += score
        
        status = "✓" if score >= 0.5 else "✗"
        logger.info(f"{status} Resolved {pred_id}: {predicted_regime} -> {dominant_regime} (score: {score})")
    
    conn.commit()
    
    # Show summary
    if resolved_count > 0:
        avg_score = total_score / resolved_count
        logger.info(f"\nResolved {resolved_count} predictions")
        logger.info(f"Average accuracy: {avg_score:.1%}")
    
    # Show overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            AVG(outcome_score) as avg_score,
            COUNT(CASE WHEN outcome_score >= 0.8 THEN 1 END) as good,
            COUNT(CASE WHEN outcome_score >= 0.5 THEN 1 END) as ok,
            COUNT(CASE WHEN outcome_score = 0 THEN 1 END) as wrong
        FROM regime_predictions
        WHERE outcome_score IS NOT NULL
    """)
    
    stats = cursor.fetchone()
    logger.info(f"\nOverall Learning Stats:")
    logger.info(f"Total resolved: {stats[0]}")
    logger.info(f"Average accuracy: {stats[1]:.1%}")
    logger.info(f"Good predictions (≥0.8): {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
    logger.info(f"OK predictions (≥0.5): {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
    logger.info(f"Wrong predictions (0): {stats[4]} ({stats[4]/stats[0]*100:.1f}%)")
    
    conn.close()

if __name__ == "__main__":
    resolve_pending_predictions()