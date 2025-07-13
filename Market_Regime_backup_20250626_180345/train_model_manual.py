#!/usr/bin/env python3
"""
Manual Model Training Script for India-TS Market Regime Detection
This script allows manual retraining of the regime detection model
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Market_Regime.learning.adaptive_learner import AdaptiveLearner
from Market_Regime.core.market_indicators import MarketIndicators
from Market_Regime.core.regime_detector import RegimeDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelTrainer:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'data', 'regime_learning.db')
        self.learner = AdaptiveLearner()
        self.indicators = MarketIndicators()
        self.detector = RegimeDetector()
        
    def analyze_current_performance(self):
        """Analyze current model performance"""
        conn = sqlite3.connect(self.db_path)
        
        # Get performance metrics
        query = """
        SELECT 
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN actual_regime IS NOT NULL THEN 1 END) as resolved,
            AVG(CASE WHEN actual_regime IS NOT NULL THEN outcome_score END) as avg_accuracy,
            COUNT(CASE WHEN predicted_regime = actual_regime THEN 1 END) as exact_matches
        FROM regime_predictions
        WHERE timestamp >= datetime('now', '-7 days')
        """
        
        metrics = pd.read_sql_query(query, conn)
        
        # Get regime distribution
        regime_query = """
        SELECT 
            predicted_regime,
            COUNT(*) as count,
            AVG(confidence) as avg_confidence,
            AVG(CASE WHEN actual_regime IS NOT NULL THEN outcome_score END) as avg_accuracy
        FROM regime_predictions
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY predicted_regime
        ORDER BY count DESC
        """
        
        regime_dist = pd.read_sql_query(regime_query, conn)
        
        print("\n=== Current Model Performance (Last 7 Days) ===")
        print(f"Total Predictions: {metrics['total_predictions'].iloc[0]}")
        print(f"Resolved: {metrics['resolved'].iloc[0]} ({metrics['resolved'].iloc[0]/metrics['total_predictions'].iloc[0]*100:.1f}%)")
        print(f"Average Accuracy: {metrics['avg_accuracy'].iloc[0]:.1%}")
        print(f"Exact Match Rate: {metrics['exact_matches'].iloc[0]/metrics['resolved'].iloc[0]*100:.1f}%")
        
        print("\n=== Regime Distribution ===")
        print(regime_dist.to_string(index=False))
        
        conn.close()
        
    def prepare_training_data(self, days_back=30):
        """Prepare training data from resolved predictions"""
        conn = sqlite3.connect(self.db_path)
        
        # Get resolved predictions with all features
        query = """
        SELECT 
            predicted_regime,
            actual_regime,
            confidence,
            market_score,
            indicators,
            outcome_score,
            timestamp
        FROM regime_predictions
        WHERE actual_regime IS NOT NULL 
        AND actual_regime != ''
        AND timestamp >= datetime('now', '-{} days')
        ORDER BY timestamp DESC
        """.format(days_back)
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) < 20:
            logger.warning(f"Only {len(df)} training samples available. Need at least 20.")
            return None
            
        logger.info(f"Prepared {len(df)} training samples from last {days_back} days")
        
        # Parse indicators JSON
        df['indicators'] = df['indicators'].apply(json.loads)
        
        return df
        
    def train_model(self, force_retrain=False):
        """Train or retrain the model"""
        print("\n=== Starting Model Training ===")
        
        # Check if we should train
        if not force_retrain:
            if self.learner._check_learning_trigger():
                print("Learning trigger conditions met. Proceeding with training.")
            else:
                print("Learning trigger conditions not met. Use --force to override.")
                return
        
        # Prepare training data
        training_data = self.prepare_training_data(days_back=30)
        
        if training_data is None:
            print("Insufficient training data. Generating synthetic data for initial model...")
            training_data = self.generate_synthetic_training_data()
        
        # Train the model
        print(f"\nTraining with {len(training_data)} samples...")
        self.learner.learn_from_history()
        
        # Analyze feature importance
        if hasattr(self.learner, 'feature_importance'):
            print("\n=== Feature Importance ===")
            sorted_features = sorted(self.learner.feature_importance.items(), 
                                   key=lambda x: x[1], reverse=True)
            for feature, importance in sorted_features[:10]:
                print(f"{feature:.<30} {importance:.3f}")
        
        print("\nModel training completed!")
        
    def generate_synthetic_training_data(self):
        """Generate synthetic training data for initial model"""
        print("Generating synthetic training data...")
        
        # Create synthetic examples for each regime
        regimes = ['uptrend', 'downtrend', 'sideways', 'volatile', 'strong_uptrend']
        samples = []
        
        for regime in regimes:
            for i in range(20):  # 20 samples per regime
                # Create realistic feature values for each regime
                if regime == 'strong_uptrend':
                    features = {
                        'market_score': np.random.uniform(0.7, 1.0),
                        'trend_score': np.random.uniform(5, 10),
                        'momentum_composite': np.random.uniform(0.5, 1.0),
                        'volatility_score': np.random.uniform(0.2, 0.5),
                        'breadth_score': np.random.uniform(0.7, 1.0),
                        'rsi': np.random.uniform(60, 80),
                        'bullish_percent': np.random.uniform(0.7, 0.9)
                    }
                elif regime == 'uptrend':
                    features = {
                        'market_score': np.random.uniform(0.5, 0.8),
                        'trend_score': np.random.uniform(2, 5),
                        'momentum_composite': np.random.uniform(0.2, 0.6),
                        'volatility_score': np.random.uniform(0.3, 0.6),
                        'breadth_score': np.random.uniform(0.5, 0.8),
                        'rsi': np.random.uniform(50, 70),
                        'bullish_percent': np.random.uniform(0.6, 0.75)
                    }
                elif regime == 'volatile':
                    features = {
                        'market_score': np.random.uniform(0.3, 0.7),
                        'trend_score': np.random.uniform(-2, 2),
                        'momentum_composite': np.random.uniform(-0.3, 0.3),
                        'volatility_score': np.random.uniform(0.7, 1.0),
                        'breadth_score': np.random.uniform(0.3, 0.7),
                        'rsi': np.random.uniform(40, 60),
                        'bullish_percent': np.random.uniform(0.4, 0.6)
                    }
                elif regime == 'downtrend':
                    features = {
                        'market_score': np.random.uniform(0.1, 0.4),
                        'trend_score': np.random.uniform(-5, -2),
                        'momentum_composite': np.random.uniform(-0.6, -0.2),
                        'volatility_score': np.random.uniform(0.4, 0.7),
                        'breadth_score': np.random.uniform(0.2, 0.5),
                        'rsi': np.random.uniform(20, 40),
                        'bullish_percent': np.random.uniform(0.2, 0.4)
                    }
                else:  # sideways
                    features = {
                        'market_score': np.random.uniform(0.4, 0.6),
                        'trend_score': np.random.uniform(-1, 1),
                        'momentum_composite': np.random.uniform(-0.1, 0.1),
                        'volatility_score': np.random.uniform(0.2, 0.4),
                        'breadth_score': np.random.uniform(0.4, 0.6),
                        'rsi': np.random.uniform(45, 55),
                        'bullish_percent': np.random.uniform(0.45, 0.55)
                    }
                
                # Store in database
                self.store_synthetic_sample(regime, features)
                samples.append({
                    'predicted_regime': regime,
                    'actual_regime': regime,
                    'features': features,
                    'outcome_score': 1.0
                })
        
        print(f"Generated {len(samples)} synthetic training samples")
        return pd.DataFrame(samples)
    
    def store_synthetic_sample(self, regime, features):
        """Store synthetic sample in database for training"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add complete feature set
        full_features = {
            'market_score': features.get('market_score', 0.5),
            'trend_score': features.get('trend_score', 0),
            'momentum_composite': features.get('momentum_composite', 0),
            'volatility_score': features.get('volatility_score', 0.5),
            'breadth_score': features.get('breadth_score', 0.5),
            'rsi': features.get('rsi', 50),
            'macd': np.random.uniform(-1, 1),
            'atr_percent': np.random.uniform(1, 3),
            'volume_ratio': np.random.uniform(0.8, 1.2),
            'price_to_sma_50': np.random.uniform(-0.02, 0.02),
            'price_to_sma_200': np.random.uniform(-0.05, 0.05),
            'higher_highs': np.random.randint(0, 10),
            'lower_lows': np.random.randint(0, 10),
            'advance_decline_ratio': features.get('bullish_percent', 0.5) * 2,
            'bullish_percent': features.get('bullish_percent', 0.5)
        }
        
        # Insert synthetic prediction
        timestamp = datetime.now() - timedelta(days=np.random.randint(1, 30))
        
        cursor.execute("""
            INSERT INTO regime_predictions 
            (timestamp, predicted_regime, confidence, market_score, indicators, 
             actual_regime, outcome_score, feedback_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp.isoformat(),
            regime,
            0.8,  # confidence
            full_features['market_score'],
            json.dumps(full_features),
            regime,  # actual = predicted for synthetic data
            1.0,  # perfect score
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def validate_model(self):
        """Validate the trained model"""
        print("\n=== Model Validation ===")
        
        # Get recent predictions and check accuracy
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT 
            predicted_regime,
            actual_regime,
            outcome_score,
            confidence
        FROM regime_predictions
        WHERE actual_regime IS NOT NULL
        AND timestamp >= datetime('now', '-1 day')
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) > 0:
            accuracy = df['outcome_score'].mean()
            exact_match = (df['predicted_regime'] == df['actual_regime']).mean()
            
            print(f"Recent Accuracy (24h): {accuracy:.1%}")
            print(f"Exact Match Rate: {exact_match:.1%}")
            print(f"Average Confidence: {df['confidence'].mean():.1%}")
        else:
            print("No recent predictions to validate")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Train India-TS Market Regime Model')
    parser.add_argument('--analyze', action='store_true', help='Analyze current performance')
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--force', action='store_true', help='Force retrain even if conditions not met')
    parser.add_argument('--validate', action='store_true', help='Validate model performance')
    parser.add_argument('--synthetic', action='store_true', help='Generate synthetic training data')
    
    args = parser.parse_args()
    
    trainer = ModelTrainer()
    
    if args.analyze or not any(vars(args).values()):
        trainer.analyze_current_performance()
    
    if args.train:
        trainer.train_model(force_retrain=args.force)
    
    if args.synthetic:
        trainer.generate_synthetic_training_data()
        print("Synthetic data generated. Now run with --train to train the model.")
    
    if args.validate:
        trainer.validate_model()

if __name__ == "__main__":
    main()