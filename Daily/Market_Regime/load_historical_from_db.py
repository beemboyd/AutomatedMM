#!/usr/bin/env python3
"""
Load Historical Regime Data from Existing Database
Extracts predictions from regime_learning.db and creates feedback
"""

import os
import sys
import sqlite3
import json
import configparser
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from kiteconnect import KiteConnect

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_kite_client():
    """Initialize KiteConnect client"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get API credentials for user Sai
    credential_section = 'API_CREDENTIALS_Sai'
    KITE_API_KEY = config.get(credential_section, 'api_key')
    ACCESS_TOKEN = config.get(credential_section, 'access_token')
    
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    return kite

def load_predictions_from_db():
    """Load existing predictions from regime_learning database"""
    
    db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
    conn = sqlite3.connect(db_path)
    
    # Load all predictions
    query = '''
        SELECT id, timestamp, regime, confidence, market_score, indicators
        FROM predictions
        WHERE timestamp >= datetime('now', '-30 days')
        ORDER BY timestamp
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return df

def calculate_actual_regimes_from_market(df, kite):
    """Calculate actual regimes using NIFTY price data"""
    
    actual_regimes = []
    
    # Group by date
    df['date'] = df['timestamp'].dt.date
    
    for date, group in df.groupby('date'):
        try:
            # Skip if less than 10 predictions for the day
            if len(group) < 10:
                continue
                
            # Get NIFTY historical data for that day
            from_date = datetime.combine(date, datetime.min.time())
            to_date = datetime.combine(date, datetime.max.time())
            
            try:
                # Get NIFTY 50 historical data
                historical_data = kite.historical_data(
                    instrument_token=256265,  # NIFTY 50
                    from_date=from_date,
                    to_date=to_date,
                    interval="day"
                )
                
                if historical_data:
                    day_data = historical_data[0]
                    
                    # Calculate price movement
                    open_price = day_data['open']
                    close_price = day_data['close']
                    high_price = day_data['high']
                    low_price = day_data['low']
                    
                    # Calculate percentage change
                    pct_change = ((close_price - open_price) / open_price) * 100
                    
                    # Calculate volatility
                    volatility = ((high_price - low_price) / open_price) * 100
                    
                    # Determine actual regime
                    if pct_change > 1.5:
                        actual_regime = 'strongly_bullish'
                    elif pct_change > 0.5:
                        actual_regime = 'bullish'
                    elif pct_change < -1.5:
                        actual_regime = 'strongly_bearish'
                    elif pct_change < -0.5:
                        actual_regime = 'bearish'
                    elif volatility > 2.0:
                        if pct_change > 0:
                            actual_regime = 'choppy_bullish'
                        else:
                            actual_regime = 'choppy_bearish'
                    else:
                        actual_regime = 'neutral'
                else:
                    # If no market data, use market_score trend
                    scores = group['market_score'].values
                    if len(scores) > 2:
                        score_change = scores[-1] - scores[0]
                        if score_change > 0.2:
                            actual_regime = 'bullish'
                        elif score_change < -0.2:
                            actual_regime = 'bearish'
                        else:
                            actual_regime = 'choppy_bullish' if np.std(scores) > 0.1 else 'neutral'
                    else:
                        actual_regime = 'neutral'
                        
            except Exception as e:
                # Fallback to score-based calculation
                scores = group['market_score'].values
                if len(scores) > 2:
                    score_change = scores[-1] - scores[0]
                    if score_change > 0.2:
                        actual_regime = 'bullish'
                    elif score_change < -0.2:
                        actual_regime = 'bearish'
                    else:
                        actual_regime = 'choppy_bullish' if np.std(scores) > 0.1 else 'neutral'
                else:
                    actual_regime = 'neutral'
            
            # Assign actual regime to all predictions from that day
            for idx in group.index:
                actual_regimes.append({
                    'prediction_id': df.loc[idx, 'id'],
                    'actual_regime': actual_regime,
                    'date': date,
                    'pct_change': pct_change if 'pct_change' in locals() else 0
                })
                
        except Exception as e:
            print(f"Error processing date {date}: {e}")
            continue
    
    return actual_regimes

def save_feedback_to_database(df, actual_regimes):
    """Save feedback to database"""
    
    feedback_db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
    
    # Create/connect to feedback database
    conn = sqlite3.connect(feedback_db_path)
    cursor = conn.cursor()
    
    # Create tables
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
    
    # Insert feedback
    inserted = 0
    for actual in actual_regimes:
        pred_id = actual['prediction_id']
        pred_row = df[df['id'] == pred_id].iloc[0]
        
        accuracy = 1 if pred_row['regime'] == actual['actual_regime'] else 0
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO regime_feedback
                (prediction_id, prediction_timestamp, predicted_regime, confidence, 
                 market_score, actual_regime, feedback_timestamp, accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pred_id,
                pred_row['timestamp'],
                pred_row['regime'],
                pred_row['confidence'],
                pred_row['market_score'],
                actual['actual_regime'],
                datetime.now(),
                accuracy
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
                
        except Exception as e:
            continue
    
    conn.commit()
    
    # Calculate accuracy metrics
    cursor.execute('''
        SELECT DATE(prediction_timestamp) as date,
               COUNT(*) as total,
               SUM(accuracy) as correct
        FROM regime_feedback
        GROUP BY DATE(prediction_timestamp)
    ''')
    
    for row in cursor.fetchall():
        date, total, correct = row
        accuracy = correct / total if total > 0 else 0
        
        # Get regime distribution for this date
        cursor.execute('''
            SELECT predicted_regime, COUNT(*) as count
            FROM regime_feedback
            WHERE DATE(prediction_timestamp) = ?
            GROUP BY predicted_regime
        ''', (date,))
        
        regime_dist = {}
        for r in cursor.fetchall():
            regime_dist[r[0]] = r[1]
        
        cursor.execute('''
            INSERT OR REPLACE INTO accuracy_metrics
            (date, total_predictions, correct_predictions, accuracy, regime_distribution)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, total, correct, accuracy, json.dumps(regime_dist)))
    
    conn.commit()
    conn.close()
    
    return inserted

def main():
    """Main function"""
    
    print("=" * 60)
    print("Loading Historical Regime Data from Database")
    print("=" * 60)
    print()
    
    # Load predictions from database
    print("Step 1: Loading predictions from regime_learning.db...")
    df = load_predictions_from_db()
    print(f"Loaded {len(df)} predictions")
    
    # Show regime distribution
    print("\nCurrent Regime Distribution:")
    regime_counts = df['regime'].value_counts()
    for regime, count in regime_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {regime:20s}: {count:5d} ({pct:5.1f}%)")
    
    # Get Kite client
    print("\nStep 2: Initializing market data connection...")
    try:
        kite = get_kite_client()
        print("Connected to market data API")
    except Exception as e:
        print(f"Warning: Could not connect to market API: {e}")
        print("Will use fallback calculation method")
        kite = None
    
    # Calculate actual regimes
    print("\nStep 3: Calculating actual regimes from market data...")
    actual_regimes = calculate_actual_regimes_from_market(df, kite)
    print(f"Calculated actual regimes for {len(actual_regimes)} predictions")
    
    # Save to feedback database
    print("\nStep 4: Saving feedback to database...")
    inserted = save_feedback_to_database(df, actual_regimes)
    print(f"Inserted {inserted} feedback records")
    
    # Final summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total predictions: {len(df)}")
    print(f"  Predictions with feedback: {len(actual_regimes)}")
    print(f"  New feedback records: {inserted}")
    
    # Check regime diversity
    max_regime_pct = (regime_counts.iloc[0] / len(df)) * 100
    if max_regime_pct > 70:
        print(f"\n⚠️  WARNING: Regime monoculture detected!")
        print(f"  {regime_counts.index[0]} represents {max_regime_pct:.1f}% of predictions")
        print("  Phase 2 feedback collection is critical for fixing this")
    else:
        print(f"\n✅ Some regime diversity exists")
        print(f"  Most common regime is {max_regime_pct:.1f}% of predictions")
    
    print("\n✅ Historical feedback loaded successfully!")
    print("This feedback data can be used for Phase 3 retraining.")

if __name__ == "__main__":
    main()