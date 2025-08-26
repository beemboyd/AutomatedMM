#!/usr/bin/env python3
"""
Load Historical Regime Data from Logs
This script extracts historical regime predictions from existing logs
without impacting any running dashboards or services.
"""

import os
import sys
import re
import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def extract_regimes_from_logs():
    """Extract regime predictions from market_regime_analyzer logs"""
    
    log_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/logs'
    predictions = []
    
    # Pattern to match regime predictions in logs
    regime_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Predicted regime:\s*(\w+(?:_\w+)?)\s*\(confidence:\s*([\d.]+)%\)'
    market_score_pattern = r'Market score normalized:\s*([-\d.]+)'
    
    # Look for market_regime_analyzer logs
    log_files = []
    for filename in os.listdir(log_dir):
        if filename.startswith('market_regime_analyzer') and filename.endswith('.log'):
            log_files.append(os.path.join(log_dir, filename))
    
    print(f"Found {len(log_files)} log files to process")
    
    for log_file in sorted(log_files):
        print(f"Processing: {log_file}")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Process lines to extract predictions
            for i, line in enumerate(lines):
                # Look for regime prediction
                regime_match = re.search(regime_pattern, line)
                if regime_match:
                    timestamp_str = regime_match.group(1)
                    regime = regime_match.group(2)
                    confidence = float(regime_match.group(3)) / 100.0
                    
                    # Look for market score in nearby lines
                    market_score = 0.0
                    for j in range(max(0, i-5), min(len(lines), i+5)):
                        score_match = re.search(market_score_pattern, lines[j])
                        if score_match:
                            market_score = float(score_match.group(1))
                            break
                    
                    # Parse timestamp
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Only include market hours predictions
                    if timestamp.hour >= 9 and timestamp.hour < 16:
                        predictions.append({
                            'timestamp': timestamp,
                            'regime': regime,
                            'confidence': confidence,
                            'market_score': market_score
                        })
        except Exception as e:
            print(f"Error processing {log_file}: {e}")
            continue
    
    return predictions

def calculate_actual_regimes(predictions_df):
    """Calculate what the actual regime should have been based on market movement"""
    
    actual_regimes = []
    
    # Group predictions by date
    predictions_df['date'] = predictions_df['timestamp'].dt.date
    
    for date, group in predictions_df.groupby('date'):
        # Get first and last prediction of the day
        first_pred = group.iloc[0]
        last_pred = group.iloc[-1]
        
        # Calculate time difference
        time_diff = (last_pred['timestamp'] - first_pred['timestamp']).total_seconds() / 3600.0
        
        if time_diff > 3:  # At least 3 hours of data
            # Use market score change to determine actual regime
            score_change = last_pred['market_score'] - first_pred['market_score']
            
            # Determine actual regime based on score change
            if score_change > 0.3:
                actual_regime = 'strongly_bullish'
            elif score_change > 0.1:
                actual_regime = 'bullish'
            elif score_change < -0.3:
                actual_regime = 'strongly_bearish'
            elif score_change < -0.1:
                actual_regime = 'bearish'
            else:
                # Check volatility
                scores = group['market_score'].values
                volatility = scores.std() if len(scores) > 1 else 0
                
                if volatility > 0.2:
                    if score_change > 0:
                        actual_regime = 'choppy_bullish'
                    else:
                        actual_regime = 'choppy_bearish'
                else:
                    actual_regime = 'neutral'
            
            # Add actual regime to predictions from that day
            for idx in group.index:
                actual_regimes.append({
                    'prediction_id': idx,
                    'actual_regime': actual_regime,
                    'score_change': score_change
                })
    
    return actual_regimes

def save_to_feedback_database(predictions, actual_regimes):
    """Save historical data to feedback database for training"""
    
    db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
    
    # Create database and tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regime_feedback (
            prediction_id INTEGER PRIMARY KEY,
            prediction_timestamp TIMESTAMP,
            predicted_regime TEXT,
            confidence REAL,
            market_score REAL,
            actual_regime TEXT,
            feedback_timestamp TIMESTAMP,
            accuracy INTEGER,
            UNIQUE(prediction_timestamp)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accuracy_metrics (
            date DATE PRIMARY KEY,
            total_predictions INTEGER,
            correct_predictions INTEGER,
            accuracy REAL,
            regime_distribution TEXT
        )
    ''')
    
    # Insert historical predictions with actual regimes
    inserted = 0
    for i, pred in enumerate(predictions):
        # Find corresponding actual regime
        actual = next((a for a in actual_regimes if a['prediction_id'] == i), None)
        
        if actual:
            try:
                accuracy = 1 if pred['regime'] == actual['actual_regime'] else 0
                
                cursor.execute('''
                    INSERT OR IGNORE INTO regime_feedback
                    (prediction_timestamp, predicted_regime, confidence, market_score,
                     actual_regime, feedback_timestamp, accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pred['timestamp'],
                    pred['regime'],
                    pred['confidence'],
                    pred['market_score'],
                    actual['actual_regime'],
                    datetime.now(),
                    accuracy
                ))
                
                if cursor.rowcount > 0:
                    inserted += 1
                    
            except Exception as e:
                print(f"Error inserting prediction: {e}")
                continue
    
    conn.commit()
    
    # Calculate daily accuracy metrics
    cursor.execute('''
        SELECT DATE(prediction_timestamp) as date,
               COUNT(*) as total,
               SUM(accuracy) as correct,
               predicted_regime
        FROM regime_feedback
        GROUP BY DATE(prediction_timestamp), predicted_regime
    ''')
    
    daily_stats = {}
    for row in cursor.fetchall():
        date = row[0]
        if date not in daily_stats:
            daily_stats[date] = {
                'total': 0,
                'correct': 0,
                'regimes': {}
            }
        daily_stats[date]['total'] += row[1]
        daily_stats[date]['correct'] += row[2]
        daily_stats[date]['regimes'][row[3]] = row[1]
    
    # Insert accuracy metrics
    for date, stats in daily_stats.items():
        accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        regime_dist = json.dumps(stats['regimes'])
        
        cursor.execute('''
            INSERT OR REPLACE INTO accuracy_metrics
            (date, total_predictions, correct_predictions, accuracy, regime_distribution)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, stats['total'], stats['correct'], accuracy, regime_dist))
    
    conn.commit()
    conn.close()
    
    return inserted

def main():
    """Main function to load historical regime data"""
    
    print("=" * 60)
    print("Loading Historical Regime Data from Logs")
    print("=" * 60)
    print()
    
    # Extract predictions from logs
    print("Step 1: Extracting regime predictions from logs...")
    predictions = extract_regimes_from_logs()
    print(f"Found {len(predictions)} predictions")
    
    if not predictions:
        print("No predictions found in logs!")
        return
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(predictions)
    
    # Calculate regime distribution
    print("\nRegime Distribution in Historical Data:")
    regime_counts = df['regime'].value_counts()
    for regime, count in regime_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {regime:20s}: {count:5d} ({pct:5.1f}%)")
    
    # Calculate actual regimes
    print("\nStep 2: Calculating actual regimes based on market movement...")
    actual_regimes = calculate_actual_regimes(df)
    print(f"Calculated actual regimes for {len(actual_regimes)} predictions")
    
    # Save to database
    print("\nStep 3: Saving to feedback database...")
    inserted = save_to_feedback_database(predictions, actual_regimes)
    print(f"Inserted {inserted} new records into feedback database")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total predictions processed: {len(predictions)}")
    print(f"  Predictions with actual regimes: {len(actual_regimes)}")
    print(f"  New records in database: {inserted}")
    print(f"  Database location: /Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db")
    
    # Check if regime diversity improved
    if len(regime_counts) > 1:
        max_regime_pct = (regime_counts.iloc[0] / len(df)) * 100
        if max_regime_pct > 70:
            print(f"\n⚠️  WARNING: Regime monoculture detected!")
            print(f"  {regime_counts.index[0]} represents {max_regime_pct:.1f}% of predictions")
            print("  This needs to be addressed before retraining")
        else:
            print(f"\n✅ Regime diversity looks reasonable")
            print(f"  Most common regime is {max_regime_pct:.1f}% of predictions")
    
    print("\n✅ Historical data loaded successfully!")
    print("This data can now be used for Phase 3 retraining without impacting existing services.")

if __name__ == "__main__":
    main()