#!/usr/bin/env python3
"""
Fix negative outcome scores in the database
Convert them to proper 0-1 scale
"""

import sqlite3

def fix_negative_scores():
    db_path = '/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, check how many negative scores we have
    cursor.execute("SELECT COUNT(*) FROM regime_predictions WHERE outcome_score < 0")
    negative_count = cursor.fetchone()[0]
    print(f"Found {negative_count} predictions with negative scores")
    
    # Fix negative scores by converting them to 0 (wrong prediction)
    cursor.execute("""
        UPDATE regime_predictions
        SET outcome_score = 0.0
        WHERE outcome_score < 0
    """)
    
    rows_updated = cursor.rowcount
    print(f"Fixed {rows_updated} negative scores to 0.0")
    
    # Also fix any scores > 1 (should be capped at 1)
    cursor.execute("""
        UPDATE regime_predictions
        SET outcome_score = 1.0
        WHERE outcome_score > 1.0
    """)
    
    rows_capped = cursor.rowcount
    print(f"Capped {rows_capped} scores that were > 1.0")
    
    # Show current score distribution
    cursor.execute("""
        SELECT 
            CASE 
                WHEN outcome_score = 1.0 THEN 'Perfect (1.0)'
                WHEN outcome_score >= 0.8 THEN 'Good (0.8-0.99)'
                WHEN outcome_score >= 0.5 THEN 'Partial (0.5-0.79)'
                WHEN outcome_score > 0 THEN 'Low (0.01-0.49)'
                ELSE 'Wrong (0.0)'
            END as score_range,
            COUNT(*) as count
        FROM regime_predictions
        WHERE outcome_score IS NOT NULL
        GROUP BY score_range
        ORDER BY outcome_score DESC
    """)
    
    print("\nScore distribution after fix:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    # Calculate new accuracy
    cursor.execute("""
        SELECT AVG(outcome_score), COUNT(*)
        FROM regime_predictions
        WHERE outcome_score IS NOT NULL
    """)
    
    avg_score, total = cursor.fetchone()
    print(f"\nOverall accuracy: {avg_score:.1%} ({total} resolved predictions)")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_negative_scores()