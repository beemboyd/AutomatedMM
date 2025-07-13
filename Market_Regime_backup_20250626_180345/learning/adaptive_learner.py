"""
Adaptive Learning Module

Continuously learns and improves regime detection accuracy based on outcomes.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json
import os
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import sqlite3


class AdaptiveLearner:
    """Adaptive learning system for regime detection"""
    
    def __init__(self, config_path: str = None, db_path: str = None):
        """Initialize adaptive learner"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'config', 'regime_config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.learning_params = self.config['learning_parameters']
        self.logger = logging.getLogger(__name__)
        
        # Database for storing learning data
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  'data', 'regime_learning.db')
        
        self.db_path = db_path
        self._init_database()
        
        # Feature importance tracking
        self.feature_importance = {}
        self.feature_performance = {}
        
        # Model components
        self.scaler = StandardScaler()
        self.regime_model = None
        self.confidence_model = None
        
        # Performance tracking
        self.prediction_history = []
        self.regime_accuracy = {}
        
        # Load existing models if available
        self._load_models()
    
    def _init_database(self):
        """Initialize learning database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Regime predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regime_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                predicted_regime TEXT,
                confidence REAL,
                actual_regime TEXT,
                market_score REAL,
                indicators TEXT,
                outcome_score REAL,
                feedback_timestamp DATETIME
            )
        ''')
        
        # Feature performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                feature_name TEXT,
                regime TEXT,
                importance_score REAL,
                prediction_accuracy REAL,
                update_count INTEGER
            )
        ''')
        
        # Regime transitions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regime_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                from_regime TEXT,
                to_regime TEXT,
                transition_indicators TEXT,
                transition_successful BOOLEAN,
                market_impact REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_prediction(self, regime: str, confidence: float, 
                         indicators: Dict[str, float], market_score: float):
        """Record a regime prediction for later learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO regime_predictions 
            (timestamp, predicted_regime, confidence, market_score, indicators)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.now(),
            regime,
            confidence,
            market_score,
            json.dumps(indicators)
        ))
        
        prediction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Store in memory for quick access
        self.prediction_history.append({
            'id': prediction_id,
            'timestamp': datetime.now(),
            'regime': regime,
            'confidence': confidence,
            'indicators': indicators
        })
        
        # Limit memory storage
        if len(self.prediction_history) > 1000:
            self.prediction_history = self.prediction_history[-1000:]
        
        return prediction_id
    
    def update_prediction_outcome(self, prediction_id: int, actual_outcome: Dict[str, any]):
        """Update a prediction with its actual outcome"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate outcome score
        outcome_score = self._calculate_outcome_score(actual_outcome)
        
        cursor.execute('''
            UPDATE regime_predictions
            SET actual_regime = ?, outcome_score = ?, feedback_timestamp = ?
            WHERE id = ?
        ''', (
            actual_outcome.get('actual_regime'),
            outcome_score,
            datetime.now(),
            prediction_id
        ))
        
        conn.commit()
        conn.close()
        
        # Trigger learning if enough feedback
        self._check_learning_trigger()
    
    def learn_from_history(self, min_samples: Optional[int] = None):
        """Learn from historical predictions and outcomes"""
        if min_samples is None:
            min_samples = self.learning_params['min_samples']
        
        # Get historical data
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT * FROM regime_predictions
            WHERE outcome_score IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(min_samples * 2,))
        conn.close()
        
        if len(df) < min_samples:
            self.logger.info(f"Not enough samples for learning: {len(df)} < {min_samples}")
            return
        
        # Prepare training data
        X, y_regime, y_confidence = self._prepare_training_data(df)
        
        if X is None:
            return
        
        # Update models
        self._update_regime_model(X, y_regime)
        self._update_confidence_model(X, y_confidence)
        
        # Update feature importance
        self._update_feature_importance(X, y_regime)
        
        # Update regime accuracy tracking
        self._update_regime_accuracy(df)
        
        # Save updated models
        self._save_models()
        
        self.logger.info("Learning cycle completed successfully")
    
    def get_enhanced_prediction(self, indicators: Dict[str, float], 
                               base_regime: str, base_confidence: float) -> Tuple[str, float]:
        """Enhance prediction using learned models"""
        if not self.learning_params['enabled']:
            return base_regime, base_confidence
        
        if self.regime_model is None:
            return base_regime, base_confidence
        
        try:
            # Prepare features
            features = self._extract_features(indicators)
            if features is None:
                return base_regime, base_confidence
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Get model predictions
            regime_proba = self.regime_model.predict_proba(features_scaled)[0]
            regime_classes = self.regime_model.classes_
            
            # Find best regime
            best_regime_idx = np.argmax(regime_proba)
            model_regime = regime_classes[best_regime_idx]
            model_confidence = regime_proba[best_regime_idx]
            
            # Blend with base prediction
            if model_regime == base_regime:
                # Boost confidence if models agree
                enhanced_confidence = min(0.95, (base_confidence + model_confidence) / 2 * 1.1)
                return base_regime, enhanced_confidence
            else:
                # Models disagree - use weighted average
                if model_confidence > base_confidence * 1.2:
                    # Model is much more confident
                    return model_regime, model_confidence * 0.9
                else:
                    # Keep base prediction but reduce confidence
                    return base_regime, base_confidence * 0.8
                    
        except Exception as e:
            self.logger.error(f"Error in enhanced prediction: {e}")
            return base_regime, base_confidence
    
    def get_feature_importance_ranking(self) -> List[Tuple[str, float]]:
        """Get current feature importance ranking"""
        if not self.feature_importance:
            return []
        
        # Sort by importance
        sorted_features = sorted(self.feature_importance.items(), 
                               key=lambda x: x[1], reverse=True)
        
        return sorted_features
    
    def get_regime_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for each regime"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                predicted_regime,
                COUNT(*) as total_predictions,
                AVG(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as accuracy,
                AVG(confidence) as avg_confidence,
                AVG(outcome_score) as avg_outcome_score
            FROM regime_predictions
            WHERE actual_regime IS NOT NULL
            GROUP BY predicted_regime
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        stats = {}
        for _, row in df.iterrows():
            stats[row['predicted_regime']] = {
                'total_predictions': int(row['total_predictions']),
                'accuracy': float(row['accuracy']),
                'avg_confidence': float(row['avg_confidence']),
                'avg_outcome_score': float(row['avg_outcome_score'])
            }
        
        return stats
    
    def suggest_parameter_adjustments(self) -> Dict[str, any]:
        """Suggest parameter adjustments based on learning"""
        suggestions = {}
        
        # Get regime performance
        regime_stats = self.get_regime_performance_stats()
        
        # Check for consistently poor performing regimes
        for regime, stats in regime_stats.items():
            if stats['accuracy'] < 0.5 and stats['total_predictions'] > 20:
                suggestions[f'regime_{regime}'] = {
                    'issue': 'Low accuracy',
                    'current_accuracy': stats['accuracy'],
                    'suggestion': 'Adjust thresholds or add indicators'
                }
        
        # Check feature importance
        feature_ranking = self.get_feature_importance_ranking()
        
        # Identify underutilized features
        if feature_ranking:
            top_features = [f[0] for f in feature_ranking[:5]]
            suggestions['top_features'] = {
                'most_important': top_features,
                'suggestion': 'Focus on these indicators for regime detection'
            }
        
        # Check confidence calibration
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                ROUND(confidence, 1) as conf_bucket,
                AVG(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as actual_accuracy
            FROM regime_predictions
            WHERE actual_regime IS NOT NULL
            GROUP BY conf_bucket
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) > 0:
            # Check if confidence is well calibrated
            calibration_error = np.mean(np.abs(df['conf_bucket'] - df['actual_accuracy']))
            
            if calibration_error > 0.15:
                suggestions['confidence_calibration'] = {
                    'issue': 'Poor confidence calibration',
                    'calibration_error': calibration_error,
                    'suggestion': 'Adjust confidence calculation method'
                }
        
        return suggestions
    
    # Private helper methods
    def _calculate_outcome_score(self, outcome: Dict[str, any]) -> float:
        """Calculate outcome score for a prediction (0-1 scale)"""
        predicted = outcome.get('predicted_regime', '')
        actual = outcome.get('actual_regime', '')
        
        # Exact match = 1.0
        if predicted == actual:
            return 1.0
        
        # Partial credit for similar regimes
        partial_credit = {
            # Trend similarity
            ('uptrend', 'strong_uptrend'): 0.8,
            ('strong_uptrend', 'uptrend'): 0.8,
            ('downtrend', 'strong_downtrend'): 0.8,
            ('strong_downtrend', 'downtrend'): 0.8,
            
            # Volatile variations
            ('volatile', 'volatile_bullish'): 0.7,
            ('volatile', 'volatile_bearish'): 0.7,
            ('volatile_bullish', 'volatile'): 0.7,
            ('volatile_bearish', 'volatile'): 0.7,
            
            # Direction partially correct
            ('bullish', 'uptrend'): 0.6,
            ('bearish', 'downtrend'): 0.6,
            ('uptrend', 'bullish'): 0.6,
            ('downtrend', 'bearish'): 0.6,
            
            # Neutral/sideways
            ('neutral', 'sideways'): 0.8,
            ('sideways', 'neutral'): 0.8,
        }
        
        # Check for partial credit
        key = (predicted, actual)
        if key in partial_credit:
            return partial_credit[key]
        
        # No credit for wrong predictions
        return 0.0
    
    def _check_learning_trigger(self):
        """Check if learning should be triggered"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count recent predictions with feedback
        cursor.execute('''
            SELECT COUNT(*) FROM regime_predictions
            WHERE feedback_timestamp > datetime('now', '-7 days')
            AND outcome_score IS NOT NULL
        ''')
        
        recent_feedback_count = cursor.fetchone()[0]
        conn.close()
        
        # Trigger learning if enough recent feedback
        if recent_feedback_count >= self.learning_params['min_samples']:
            self.learn_from_history()
    
    def _prepare_training_data(self, df: pd.DataFrame) -> Tuple[Optional[np.ndarray], 
                                                               Optional[np.ndarray], 
                                                               Optional[np.ndarray]]:
        """Prepare training data from historical predictions"""
        try:
            # Parse indicators
            feature_data = []
            regime_labels = []
            confidence_labels = []
            
            for _, row in df.iterrows():
                indicators = json.loads(row['indicators'])
                features = self._extract_features(indicators)
                
                if features is not None:
                    feature_data.append(features)
                    regime_labels.append(row['actual_regime'])
                    
                    # Confidence label based on prediction accuracy
                    was_correct = row['predicted_regime'] == row['actual_regime']
                    confidence_labels.append(1.0 if was_correct else 0.0)
            
            if not feature_data:
                return None, None, None
            
            X = np.array(feature_data)
            y_regime = np.array(regime_labels)
            y_confidence = np.array(confidence_labels)
            
            # Scale features
            X = self.scaler.fit_transform(X)
            
            return X, y_regime, y_confidence
            
        except Exception as e:
            self.logger.error(f"Error preparing training data: {e}")
            return None, None, None
    
    def _extract_features(self, indicators: Dict[str, float]) -> Optional[np.ndarray]:
        """Extract feature vector from indicators"""
        try:
            # Define feature order for consistency
            feature_names = [
                'market_score', 'trend_score', 'momentum_composite', 
                'volatility_score', 'breadth_score',
                'rsi', 'macd', 'atr_percent', 'volume_ratio',
                'price_to_sma_50', 'price_to_sma_200',
                'higher_highs', 'lower_lows',
                'advance_decline_ratio', 'bullish_percent'
            ]
            
            features = []
            for name in feature_names:
                if name in indicators:
                    features.append(float(indicators[name]))
                else:
                    features.append(0.0)  # Default value
            
            return np.array(features)
            
        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
            return None
    
    def _update_regime_model(self, X: np.ndarray, y: np.ndarray):
        """Update regime classification model"""
        try:
            # Initialize or update model
            if self.regime_model is None:
                self.regime_model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
                )
            
            # Train model
            self.regime_model.fit(X, y)
            
            # Log performance
            train_score = self.regime_model.score(X, y)
            self.logger.info(f"Regime model updated. Training accuracy: {train_score:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error updating regime model: {e}")
    
    def _update_confidence_model(self, X: np.ndarray, y: np.ndarray):
        """Update confidence prediction model"""
        try:
            # For now, we'll skip the confidence model
            # Could implement a regression model here
            pass
            
        except Exception as e:
            self.logger.error(f"Error updating confidence model: {e}")
    
    def _update_feature_importance(self, X: np.ndarray, y: np.ndarray):
        """Update feature importance scores"""
        if self.regime_model is None:
            return
        
        try:
            # Get feature importances from random forest
            importances = self.regime_model.feature_importances_
            
            feature_names = [
                'market_score', 'trend_score', 'momentum_composite', 
                'volatility_score', 'breadth_score',
                'rsi', 'macd', 'atr_percent', 'volume_ratio',
                'price_to_sma_50', 'price_to_sma_200',
                'higher_highs', 'lower_lows',
                'advance_decline_ratio', 'bullish_percent'
            ]
            
            # Update importance tracking
            decay = self.learning_params.get('confidence_decay_rate', 0.95)
            
            for i, name in enumerate(feature_names):
                if i < len(importances):
                    # Exponential moving average of importance
                    if name in self.feature_importance:
                        self.feature_importance[name] = (
                            decay * self.feature_importance[name] + 
                            (1 - decay) * importances[i]
                        )
                    else:
                        self.feature_importance[name] = importances[i]
            
            # Save to database
            self._save_feature_importance()
            
        except Exception as e:
            self.logger.error(f"Error updating feature importance: {e}")
    
    def _update_regime_accuracy(self, df: pd.DataFrame):
        """Update regime-specific accuracy tracking"""
        for regime in self.config['regime_types']:
            regime_df = df[df['predicted_regime'] == regime]
            
            if len(regime_df) > 0:
                accuracy = (regime_df['predicted_regime'] == regime_df['actual_regime']).mean()
                
                if regime in self.regime_accuracy:
                    # Moving average
                    self.regime_accuracy[regime] = (
                        0.9 * self.regime_accuracy[regime] + 0.1 * accuracy
                    )
                else:
                    self.regime_accuracy[regime] = accuracy
    
    def _save_feature_importance(self):
        """Save feature importance to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for feature, importance in self.feature_importance.items():
            cursor.execute('''
                INSERT INTO feature_performance
                (timestamp, feature_name, regime, importance_score, update_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(feature_name, regime) DO UPDATE SET
                    importance_score = ?,
                    update_count = update_count + 1,
                    timestamp = ?
            ''', (
                datetime.now(), feature, 'all', importance,
                importance, datetime.now()
            ))
        
        conn.commit()
        conn.close()
    
    def _save_models(self):
        """Save trained models to disk"""
        try:
            model_dir = os.path.join(os.path.dirname(self.db_path), 'models')
            os.makedirs(model_dir, exist_ok=True)
            
            # Save regime model
            if self.regime_model is not None:
                model_path = os.path.join(model_dir, 'regime_model.pkl')
                with open(model_path, 'wb') as f:
                    pickle.dump(self.regime_model, f)
            
            # Save scaler
            scaler_path = os.path.join(model_dir, 'scaler.pkl')
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            # Save feature importance
            importance_path = os.path.join(model_dir, 'feature_importance.json')
            with open(importance_path, 'w') as f:
                json.dump(self.feature_importance, f)
            
            self.logger.info("Models saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving models: {e}")
    
    def _load_models(self):
        """Load trained models from disk"""
        try:
            model_dir = os.path.join(os.path.dirname(self.db_path), 'models')
            
            # Load regime model
            model_path = os.path.join(model_dir, 'regime_model.pkl')
            if os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    self.regime_model = pickle.load(f)
                self.logger.info("Loaded existing regime model")
            
            # Load scaler
            scaler_path = os.path.join(model_dir, 'scaler.pkl')
            if os.path.exists(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
            
            # Load feature importance
            importance_path = os.path.join(model_dir, 'feature_importance.json')
            if os.path.exists(importance_path):
                with open(importance_path, 'r') as f:
                    self.feature_importance = json.load(f)
            
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")