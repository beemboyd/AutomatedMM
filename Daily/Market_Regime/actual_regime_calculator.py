#!/usr/bin/env python3
"""
Actual Regime Calculator
Calculates the actual market regime based on price action after predictions
Part of Phase 2: Restore Learning
"""

import os
import sys
import json
import sqlite3
import logging
import configparser
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ActualRegimeCalculator:
    """Calculate actual market regime from price action"""
    
    def __init__(self, user='Sai'):
        self.user = user
        
        # Load config from Daily/config.ini
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Get API credentials for user Sai
        credential_section = f'API_CREDENTIALS_{user}'
        KITE_API_KEY = config.get(credential_section, 'api_key')
        ACCESS_TOKEN = config.get(credential_section, 'access_token')
        
        # Initialize KiteConnect
        from kiteconnect import KiteConnect
        self.kite = KiteConnect(api_key=KITE_API_KEY)
        self.kite.set_access_token(ACCESS_TOKEN)
        
        # Database path
        self.db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
        self.feedback_db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
        
        # Initialize feedback database
        self._init_feedback_database()
        
        # Regime thresholds
        self.thresholds = {
            'strong_trend': 1.5,      # >1.5% move
            'moderate_trend': 0.75,   # 0.75-1.5% move
            'weak_trend': 0.3,        # 0.3-0.75% move
            'choppy': 0.3,            # <0.3% move with high volatility
            'volume_surge': 1.5,      # 50% above average volume
            'volatility_high': 2.0    # Volatility threshold
        }
        
    def _init_feedback_database(self):
        """Initialize the feedback database"""
        conn = sqlite3.connect(self.feedback_db_path)
        cursor = conn.cursor()
        
        # Create feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regime_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER,
                prediction_timestamp TEXT,
                predicted_regime TEXT,
                predicted_confidence REAL,
                actual_regime TEXT,
                price_change_pct REAL,
                volume_ratio REAL,
                volatility REAL,
                feedback_timestamp TEXT,
                calculation_delay_minutes INTEGER,
                UNIQUE(prediction_id)
            )
        ''')
        
        # Create accuracy tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accuracy_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_predictions INTEGER,
                validated_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy_pct REAL,
                regime_distribution TEXT,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Feedback database initialized")
        
    def calculate_actual_regime(self, prediction_id, prediction_time, delay_minutes=45):
        """
        Calculate actual regime after prediction
        
        Args:
            prediction_id: ID from predictions table
            prediction_time: When prediction was made
            delay_minutes: How long to wait before calculating actual (default 45 min)
        """
        try:
            # Get NIFTY data for regime calculation
            symbol = "NSE:NIFTY 50"
            
            # Calculate time windows
            prediction_dt = datetime.strptime(prediction_time, '%Y-%m-%d %H:%M:%S')
            actual_time = prediction_dt + timedelta(minutes=delay_minutes)
            
            # Skip if actual time is in future
            if actual_time > datetime.now():
                logger.debug(f"Skipping prediction {prediction_id} - too recent")
                return None
                
            # Get 5-minute candle data around prediction and actual time
            from_time = prediction_dt - timedelta(minutes=15)
            to_time = actual_time + timedelta(minutes=15)
            
            # Fetch historical data
            data = self.kite.historical_data(
                instrument_token=256265,  # NIFTY 50
                from_date=from_time,
                to_date=to_time,
                interval='5minute'
            )
            
            if not data:
                logger.warning(f"No data available for prediction {prediction_id}")
                return None
                
            df = pd.DataFrame(data)
            
            # Calculate metrics at prediction time
            pred_idx = df[df['date'] >= prediction_dt].index[0] if len(df[df['date'] >= prediction_dt]) > 0 else -1
            if pred_idx == -1:
                return None
                
            pred_price = df.iloc[pred_idx]['close']
            pred_volume = df.iloc[pred_idx]['volume']
            
            # Calculate metrics at actual time
            actual_idx = df[df['date'] >= actual_time].index[0] if len(df[df['date'] >= actual_time]) > 0 else -1
            if actual_idx == -1:
                return None
                
            actual_price = df.iloc[actual_idx]['close']
            actual_volume = df.iloc[actual_idx]['volume']
            
            # Calculate price change
            price_change_pct = ((actual_price - pred_price) / pred_price) * 100
            
            # Calculate volume ratio
            avg_volume = df['volume'].rolling(window=10).mean().iloc[actual_idx]
            volume_ratio = actual_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Calculate volatility (standard deviation of returns)
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].iloc[pred_idx:actual_idx].std() * 100
            
            # Determine actual regime
            actual_regime = self._determine_regime(
                price_change_pct, 
                volume_ratio, 
                volatility
            )
            
            # Get predicted regime from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT regime, confidence FROM predictions WHERE id = ?",
                (prediction_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.warning(f"Prediction {prediction_id} not found in database")
                return None
                
            predicted_regime, predicted_confidence = result
            
            # Save feedback to database
            self._save_feedback(
                prediction_id=prediction_id,
                prediction_timestamp=prediction_time,
                predicted_regime=predicted_regime,
                predicted_confidence=predicted_confidence,
                actual_regime=actual_regime,
                price_change_pct=price_change_pct,
                volume_ratio=volume_ratio,
                volatility=volatility,
                calculation_delay_minutes=delay_minutes
            )
            
            logger.info(f"Feedback saved - Predicted: {predicted_regime}, Actual: {actual_regime}, Change: {price_change_pct:.2f}%")
            
            return {
                'prediction_id': prediction_id,
                'predicted_regime': predicted_regime,
                'actual_regime': actual_regime,
                'price_change_pct': price_change_pct,
                'volume_ratio': volume_ratio,
                'volatility': volatility,
                'correct': predicted_regime == actual_regime
            }
            
        except Exception as e:
            logger.error(f"Error calculating actual regime: {str(e)}")
            return None
            
    def _determine_regime(self, price_change_pct, volume_ratio, volatility):
        """
        Determine regime based on price action metrics
        
        Returns one of:
        - strong_bullish
        - choppy_bullish  
        - sideways
        - choppy_bearish
        - strong_bearish
        - volatile_bullish
        - volatile_bearish
        """
        abs_change = abs(price_change_pct)
        
        # Check for strong trends
        if price_change_pct > self.thresholds['strong_trend']:
            if volatility > self.thresholds['volatility_high']:
                return 'volatile_bullish'
            else:
                return 'strong_bullish'
                
        elif price_change_pct < -self.thresholds['strong_trend']:
            if volatility > self.thresholds['volatility_high']:
                return 'volatile_bearish'
            else:
                return 'strong_bearish'
                
        # Check for moderate trends
        elif price_change_pct > self.thresholds['moderate_trend']:
            if volatility > self.thresholds['volatility_high']:
                return 'choppy_bullish'
            else:
                return 'strong_bullish'
                
        elif price_change_pct < -self.thresholds['moderate_trend']:
            if volatility > self.thresholds['volatility_high']:
                return 'choppy_bearish'
            else:
                return 'strong_bearish'
                
        # Check for weak trends with high volatility (choppy)
        elif abs_change < self.thresholds['choppy']:
            return 'sideways'
            
        # Weak trends
        elif price_change_pct > 0:
            if volatility > self.thresholds['volatility_high']:
                return 'choppy_bullish'
            else:
                return 'sideways'
                
        else:
            if volatility > self.thresholds['volatility_high']:
                return 'choppy_bearish'
            else:
                return 'sideways'
                
    def _save_feedback(self, **kwargs):
        """Save feedback to database"""
        conn = sqlite3.connect(self.feedback_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO regime_feedback 
            (prediction_id, prediction_timestamp, predicted_regime, predicted_confidence,
             actual_regime, price_change_pct, volume_ratio, volatility,
             feedback_timestamp, calculation_delay_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            kwargs['prediction_id'],
            kwargs['prediction_timestamp'],
            kwargs['predicted_regime'],
            kwargs['predicted_confidence'],
            kwargs['actual_regime'],
            kwargs['price_change_pct'],
            kwargs['volume_ratio'],
            kwargs['volatility'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            kwargs['calculation_delay_minutes']
        ))
        
        conn.commit()
        conn.close()
        
    def process_pending_predictions(self, lookback_hours=24, delay_minutes=45):
        """
        Process all predictions that don't have feedback yet
        
        Args:
            lookback_hours: How far back to look for predictions
            delay_minutes: Minimum delay before calculating actual regime
        """
        try:
            # Get predictions without feedback
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=lookback_hours)).strftime('%Y-%m-%d %H:%M:%S')
            max_time = (datetime.now() - timedelta(minutes=delay_minutes)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                SELECT id, timestamp FROM predictions 
                WHERE timestamp > ? AND timestamp < ?
                AND id NOT IN (SELECT prediction_id FROM regime_feedback)
                ORDER BY timestamp DESC
            ''', (cutoff_time, max_time))
            
            pending = cursor.fetchall()
            conn.close()
            
            logger.info(f"Found {len(pending)} predictions pending feedback")
            
            processed = 0
            correct = 0
            
            for pred_id, pred_time in pending:
                result = self.calculate_actual_regime(pred_id, pred_time, delay_minutes)
                if result:
                    processed += 1
                    if result['correct']:
                        correct += 1
                        
                # Rate limiting
                import time
                time.sleep(0.5)
                
            if processed > 0:
                accuracy = (correct / processed) * 100
                logger.info(f"Processed {processed} predictions, Accuracy: {accuracy:.2f}%")
                
                # Update accuracy metrics
                self._update_accuracy_metrics()
                
            return processed
            
        except Exception as e:
            logger.error(f"Error processing pending predictions: {str(e)}")
            return 0
            
    def _update_accuracy_metrics(self):
        """Update overall accuracy metrics"""
        try:
            conn = sqlite3.connect(self.feedback_db_path)
            cursor = conn.cursor()
            
            # Calculate today's metrics
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct,
                    GROUP_CONCAT(actual_regime) as regimes
                FROM regime_feedback
                WHERE DATE(feedback_timestamp) = ?
            ''', (today,))
            
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                total = result[0]
                correct = result[1] or 0
                accuracy = (correct / total) * 100
                
                # Calculate regime distribution
                regimes = result[2].split(',') if result[2] else []
                regime_dist = {}
                for regime in regimes:
                    regime_dist[regime] = regime_dist.get(regime, 0) + 1
                    
                # Save metrics
                cursor.execute('''
                    INSERT OR REPLACE INTO accuracy_metrics
                    (date, total_predictions, validated_predictions, correct_predictions,
                     accuracy_pct, regime_distribution, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    today,
                    total,
                    total,  # All are validated
                    correct,
                    accuracy,
                    json.dumps(regime_dist),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                conn.commit()
                logger.info(f"Updated accuracy metrics - {accuracy:.2f}% ({correct}/{total})")
                
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating accuracy metrics: {str(e)}")


def main():
    """Main function for testing"""
    calculator = ActualRegimeCalculator(user='Sai')
    
    # Process pending predictions
    processed = calculator.process_pending_predictions(lookback_hours=24, delay_minutes=45)
    
    print(f"\nProcessed {processed} predictions")
    
    # Show current accuracy
    conn = sqlite3.connect(calculator.feedback_db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct
        FROM regime_feedback
    ''')
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        accuracy = (result[1] / result[0]) * 100
        print(f"Overall Accuracy: {accuracy:.2f}% ({result[1]}/{result[0]})")
        
    conn.close()


if __name__ == "__main__":
    main()