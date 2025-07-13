#!/usr/bin/env python
"""
Self-Improving Market Regime Predictor
Tracks predictions vs actual results and optimizes thresholds over time
"""

import os
import sys
import logging
import datetime
import json
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import sqlite3
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from collections import deque

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import model manager
from model_manager import ModelManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                       "logs", "market_regime_predictor.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketRegimePredictor:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, "data")
        self.predictions_dir = os.path.join(self.script_dir, "predictions")
        self.models_dir = os.path.join(self.script_dir, "models")
        
        # Central database path
        self.central_db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
        
        # Ensure directories exist
        for dir_path in [self.data_dir, self.predictions_dir, self.models_dir, 
                         os.path.join(self.script_dir, "logs")]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Initialize prediction tracking
        self.predictions_file = os.path.join(self.predictions_dir, "predictions_history.json")
        self.performance_file = os.path.join(self.predictions_dir, "model_performance.json")
        self.thresholds_file = os.path.join(self.data_dir, "optimized_thresholds.json")
        
        # Load historical data
        self.predictions_history = self._load_predictions_history()
        self.performance_metrics = self._load_performance_metrics()
        self.optimized_thresholds = self._load_optimized_thresholds()
        
        # Feature window for predictions
        self.feature_window = 10  # Look at past 10 scans for features
        
        # Initialize ML model
        self.model = None
        self.scaler = StandardScaler()
        self.model_file = os.path.join(self.models_dir, "regime_predictor_model.pkl")
        self.scaler_file = os.path.join(self.models_dir, "regime_predictor_scaler.pkl")
        
        # Initialize model manager
        self.model_manager = ModelManager(self.models_dir)
        
        self._load_or_initialize_model()
        
    def _load_predictions_history(self):
        """Load historical predictions"""
        if os.path.exists(self.predictions_file):
            try:
                with open(self.predictions_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
        
    def _load_performance_metrics(self):
        """Load model performance metrics"""
        if os.path.exists(self.performance_file):
            try:
                with open(self.performance_file, 'r') as f:
                    return json.load(f)
            except:
                return self._initialize_performance_metrics()
        return self._initialize_performance_metrics()
        
    def _initialize_performance_metrics(self):
        """Initialize performance tracking"""
        return {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy': 0.0,
            'regime_accuracy': {},
            'feature_importance': {},
            'last_training': None,
            'optimization_history': []
        }
        
    def _load_optimized_thresholds(self):
        """Load optimized thresholds"""
        if os.path.exists(self.thresholds_file):
            try:
                with open(self.thresholds_file, 'r') as f:
                    return json.load(f)
            except:
                return self._get_default_thresholds()
        return self._get_default_thresholds()
        
    def _get_default_thresholds(self):
        """Get default thresholds for regime classification"""
        return {
            'strong_bullish': 2.0,      # Long/Short ratio > 2.0
            'bullish': 1.5,             # Long/Short ratio > 1.5
            'neutral_bullish': 1.2,     # Long/Short ratio > 1.2
            'neutral_high': 1.2,        # Upper neutral boundary
            'neutral_low': 0.8,         # Lower neutral boundary
            'neutral_bearish': 0.8,     # Long/Short ratio < 0.8
            'bearish': 0.67,            # Long/Short ratio < 0.67
            'strong_bearish': 0.5       # Long/Short ratio < 0.5
        }
        
    def _load_or_initialize_model(self):
        """Load existing model or create new one"""
        # Try to load from model manager first
        model, scaler = self.model_manager.load_best_model()
        
        if model is not None and scaler is not None:
            self.model = model
            self.scaler = scaler
            model_info = self.model_manager.get_model_info()
            if model_info:
                logger.info(f"Loaded best model with {model_info['performance']:.2%} accuracy")
            else:
                logger.info("Loaded existing prediction model")
        elif os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
            try:
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded existing prediction model from legacy files")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}, initializing new one")
                self._initialize_new_model()
        else:
            self._initialize_new_model()
            
    def _initialize_new_model(self):
        """Initialize a new Random Forest model"""
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        logger.info("Initialized new Random Forest model")
        
    def extract_features(self, scan_history):
        """Extract features from scan history for prediction"""
        features = []
        
        if len(scan_history) < 3:
            return None
            
        # Recent scans
        recent_scans = scan_history[-self.feature_window:]
        
        # Basic count features
        long_counts = [s['long_count'] for s in recent_scans]
        short_counts = [s['short_count'] for s in recent_scans]
        ratios = []
        
        for l, s in zip(long_counts, short_counts):
            if s > 0:
                ratios.append(l / s)
            else:
                ratios.append(5.0 if l > 0 else 1.0)
                
        # Statistical features
        features.extend([
            np.mean(long_counts),           # Average long count
            np.std(long_counts),            # Long count volatility
            np.mean(short_counts),          # Average short count
            np.std(short_counts),           # Short count volatility
            np.mean(ratios),                # Average ratio
            np.std(ratios),                 # Ratio volatility
            ratios[-1],                     # Current ratio
            ratios[-1] - ratios[-2] if len(ratios) > 1 else 0,  # Ratio change
        ])
        
        # Trend features
        if len(long_counts) >= 3:
            # Moving averages
            ma3_long = np.mean(long_counts[-3:])
            ma3_short = np.mean(short_counts[-3:])
            
            # Trend direction
            long_trend = 1 if long_counts[-1] > ma3_long else -1
            short_trend = 1 if short_counts[-1] > ma3_short else -1
            
            features.extend([
                ma3_long,
                ma3_short,
                long_trend,
                short_trend,
                long_counts[-1] - long_counts[-3],   # 3-period change
                short_counts[-1] - short_counts[-3]  # 3-period change
            ])
        else:
            features.extend([0] * 6)
            
        # Momentum features
        if len(ratios) >= 5:
            momentum = np.mean(ratios[-3:]) - np.mean(ratios[-5:-2])
            acceleration = (ratios[-1] - ratios[-2]) - (ratios[-2] - ratios[-3]) if len(ratios) >= 3 else 0
            features.extend([momentum, acceleration])
        else:
            features.extend([0, 0])
            
        return np.array(features).reshape(1, -1)
        
    def predict_next_regime(self, scan_history):
        """Predict the next market regime"""
        features = self.extract_features(scan_history)
        
        if features is None:
            logger.warning("Insufficient history for prediction")
            return None
            
        # Make prediction
        try:
            if hasattr(self.model, 'predict_proba') and hasattr(self.model, 'classes_'):
                # Check if scaler is fitted
                if not hasattr(self.scaler, 'mean_') or self.scaler.mean_ is None:
                    logger.warning("Scaler not fitted, using rule-based prediction")
                    return self._rule_based_prediction(scan_history[-1])
                    
                # Get probability predictions
                features_scaled = self.scaler.transform(features)
                probabilities = self.model.predict_proba(features_scaled)[0]
                prediction = self.model.predict(features_scaled)[0]
                
                # Get confidence
                confidence = max(probabilities)
                
                return {
                    'predicted_regime': prediction,
                    'confidence': confidence,
                    'probabilities': dict(zip(self.model.classes_, probabilities))
                }
            else:
                # Model not trained yet, use rule-based prediction
                return self._rule_based_prediction(scan_history[-1])
                
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._rule_based_prediction(scan_history[-1])
            
    def _rule_based_prediction(self, latest_scan):
        """Fallback rule-based prediction using optimized thresholds"""
        long_count = latest_scan['long_count']
        short_count = latest_scan['short_count']
        
        if short_count == 0:
            ratio = 5.0 if long_count > 0 else 1.0
        else:
            ratio = long_count / short_count
            
        # Use optimized thresholds
        thresholds = self.optimized_thresholds
        
        if ratio > thresholds['strong_bullish']:
            regime = 'strong_uptrend'
        elif ratio > thresholds['bullish']:
            regime = 'uptrend'
        elif ratio > thresholds['neutral_bullish']:
            regime = 'choppy_bullish'
        elif ratio < thresholds['strong_bearish']:
            regime = 'strong_downtrend'
        elif ratio < thresholds['bearish']:
            regime = 'downtrend'
        elif ratio < thresholds['neutral_bearish']:
            regime = 'choppy_bearish'
        else:
            regime = 'choppy'
            
        # Calculate confidence based on ratio extremity
        if ratio > 3.0 or ratio < 0.33:
            confidence = 0.8
        elif ratio > 2.0 or ratio < 0.5:
            confidence = 0.6
        else:
            confidence = 0.4
            
        return {
            'predicted_regime': regime,
            'confidence': confidence,
            'probabilities': {regime: confidence}
        }
        
    def record_prediction(self, prediction_data):
        """Record a prediction for future tracking"""
        prediction_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'predicted_regime': prediction_data['predicted_regime'],
            'confidence': prediction_data['confidence'],
            'actual_regime': None,  # To be filled later
            'correct': None,  # To be determined later
            'scan_data': prediction_data.get('scan_data', {})
        }
        
        self.predictions_history.append(prediction_entry)
        
        # Keep only last 1000 predictions
        if len(self.predictions_history) > 1000:
            self.predictions_history = self.predictions_history[-1000:]
            
        # Save predictions to JSON file
        with open(self.predictions_file, 'w') as f:
            json.dump(self.predictions_history, f, indent=2)
            
        # Also save to central database
        self._save_prediction_to_db(prediction_data)
            
        return prediction_entry
    
    def _save_prediction_to_db(self, prediction_data):
        """Save prediction to central database"""
        try:
            conn = sqlite3.connect(self.central_db_path)
            cursor = conn.cursor()
            
            # Extract market indicators if available
            scan_data = prediction_data.get('scan_data', {})
            
            # Get market_score from indicators if available, otherwise calculate ratio
            market_score = scan_data.get('market_score')
            if market_score is None:
                # Calculate long/short ratio as fallback
                long_count = scan_data.get('long_count', 0)
                short_count = scan_data.get('short_count', 0)
                if short_count > 0:
                    ratio = long_count / short_count
                elif long_count > 0:
                    ratio = 5.0
                else:
                    ratio = 1.0
                # Normalize ratio to -1 to 1 range
                # ratio > 2 = bullish (0.5 to 1.0)
                # ratio 0.5-2 = neutral (-0.5 to 0.5)
                # ratio < 0.5 = bearish (-1.0 to -0.5)
                if ratio > 2:
                    market_score = 0.5 + min((ratio - 2) / 4, 0.5)
                elif ratio < 0.5:
                    market_score = -0.5 - min((0.5 - ratio) / 0.5, 0.5)
                else:
                    market_score = (ratio - 1.25) / 0.75  # Maps 0.5-2 to -0.5 to 0.5
            
            # Ensure market_score is within valid range
            market_score = np.clip(market_score, -1.0, 1.0)
            
            # Insert prediction
            cursor.execute("""
                INSERT INTO regime_predictions 
                (timestamp, predicted_regime, confidence, market_score, indicators)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.datetime.now(),
                prediction_data['predicted_regime'],
                prediction_data['confidence'],
                market_score,
                json.dumps(scan_data)
            ))
            
            # Also insert into predictions table for compatibility
            cursor.execute("""
                INSERT INTO predictions 
                (timestamp, regime, confidence, market_score, indicators)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.datetime.now(),
                prediction_data['predicted_regime'],
                prediction_data['confidence'],
                market_score,
                json.dumps(scan_data)
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved prediction to database: {prediction_data['predicted_regime']} (confidence: {prediction_data['confidence']:.2%})")
            
        except Exception as e:
            logger.error(f"Error saving prediction to database: {e}")
        
    def update_actual_regime(self, timestamp, actual_regime):
        """Update the actual regime for a past prediction"""
        updated = False
        
        for prediction in self.predictions_history:
            pred_time = datetime.datetime.fromisoformat(prediction['timestamp'])
            check_time = datetime.datetime.fromisoformat(timestamp)
            
            # Find predictions within 30 minutes of the actual regime
            if abs((pred_time - check_time).total_seconds()) < 1800:
                prediction['actual_regime'] = actual_regime
                prediction['correct'] = prediction['predicted_regime'] == actual_regime
                updated = True
                
        if updated:
            # Update performance metrics
            self._update_performance_metrics()
            
            # Save updated predictions
            with open(self.predictions_file, 'w') as f:
                json.dump(self.predictions_history, f, indent=2)
                
            # Update database with actual regime
            self._update_db_actual_regime(timestamp, actual_regime)
                
            # Retrain model if enough new data
            if self.performance_metrics['total_predictions'] % 50 == 0:
                self.retrain_model()
                
            # Optimize thresholds periodically
            if self.performance_metrics['total_predictions'] % 100 == 0:
                self.optimize_thresholds()
                
    def _update_db_actual_regime(self, timestamp, actual_regime):
        """Update actual regime in database"""
        try:
            conn = sqlite3.connect(self.central_db_path)
            cursor = conn.cursor()
            
            check_time = datetime.datetime.fromisoformat(timestamp)
            
            # Update regime_predictions table
            cursor.execute("""
                UPDATE regime_predictions
                SET actual_regime = ?,
                    feedback_timestamp = ?
                WHERE datetime(timestamp) BETWEEN datetime(?, '-30 minutes') AND datetime(?, '+30 minutes')
                  AND actual_regime IS NULL
            """, (actual_regime, datetime.datetime.now(), check_time, check_time))
            
            # Calculate outcome score based on accuracy (0-1 scale)
            cursor.execute("""
                UPDATE regime_predictions
                SET outcome_score = CASE
                    WHEN predicted_regime = actual_regime THEN 1.0
                    WHEN predicted_regime IN ('uptrend', 'strong_uptrend') AND actual_regime IN ('uptrend', 'strong_uptrend') THEN 0.8
                    WHEN predicted_regime IN ('downtrend', 'strong_downtrend') AND actual_regime IN ('downtrend', 'strong_downtrend') THEN 0.8
                    WHEN predicted_regime = 'volatile' AND actual_regime IN ('volatile_bullish', 'volatile_bearish') THEN 0.7
                    WHEN predicted_regime IN ('bullish', 'bearish') AND actual_regime = 'volatile' THEN 0.5
                    ELSE 0.0
                END
                WHERE actual_regime = ?
                  AND outcome_score IS NULL
            """, (actual_regime,))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated database with actual regime: {actual_regime}")
            
        except Exception as e:
            logger.error(f"Error updating actual regime in database: {e}")
                
    def _update_performance_metrics(self):
        """Update model performance metrics"""
        predictions_with_actuals = [p for p in self.predictions_history if p['actual_regime'] is not None]
        
        if not predictions_with_actuals:
            return
            
        total = len(predictions_with_actuals)
        correct = sum(1 for p in predictions_with_actuals if p['correct'])
        
        self.performance_metrics['total_predictions'] = total
        self.performance_metrics['correct_predictions'] = correct
        self.performance_metrics['accuracy'] = correct / total if total > 0 else 0
        
        # Calculate per-regime accuracy
        regime_accuracy = {}
        regimes = set(p['actual_regime'] for p in predictions_with_actuals)
        
        for regime in regimes:
            regime_preds = [p for p in predictions_with_actuals if p['actual_regime'] == regime]
            regime_correct = sum(1 for p in regime_preds if p['correct'])
            regime_accuracy[regime] = regime_correct / len(regime_preds) if regime_preds else 0
            
        self.performance_metrics['regime_accuracy'] = regime_accuracy
        
        # Save metrics
        with open(self.performance_file, 'w') as f:
            json.dump(self.performance_metrics, f, indent=2)
            
        logger.info(f"Updated performance: Accuracy={self.performance_metrics['accuracy']:.2%}")
        
    def retrain_model(self):
        """Retrain the ML model with accumulated data"""
        logger.info("Retraining prediction model...")
        
        # Prepare training data
        valid_predictions = [p for p in self.predictions_history if p['actual_regime'] is not None]
        
        if len(valid_predictions) < 50:
            logger.warning("Not enough data for retraining")
            return
            
        # Extract features and labels
        X = []
        y = []
        
        for i, pred in enumerate(valid_predictions):
            if 'scan_data' in pred and pred['scan_data']:
                # Reconstruct feature from scan data
                scan_history = []
                
                # Get historical context
                for j in range(max(0, i - self.feature_window), i + 1):
                    if j < len(valid_predictions) and 'scan_data' in valid_predictions[j]:
                        scan_history.append(valid_predictions[j]['scan_data'])
                        
                if len(scan_history) >= 3:
                    features = self.extract_features(scan_history)
                    if features is not None:
                        X.append(features[0])
                        y.append(pred['actual_regime'])
                        
        if len(X) < 30:
            logger.warning("Not enough valid features for retraining")
            return
            
        # Train model
        X = np.array(X)
        
        # Fit scaler
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        
        # Update performance metrics
        self.performance_metrics['last_training'] = datetime.datetime.now().isoformat()
        
        # Calculate feature importance
        if hasattr(self.model, 'feature_importances_'):
            feature_names = [
                'avg_long', 'std_long', 'avg_short', 'std_short',
                'avg_ratio', 'std_ratio', 'current_ratio', 'ratio_change',
                'ma3_long', 'ma3_short', 'long_trend', 'short_trend',
                'long_3p_change', 'short_3p_change', 'momentum', 'acceleration'
            ]
            importance_dict = dict(zip(feature_names, self.model.feature_importances_))
            self.performance_metrics['feature_importance'] = importance_dict
            
        with open(self.performance_file, 'w') as f:
            json.dump(self.performance_metrics, f, indent=2)
            
        # Save model using model manager
        version_name = self.model_manager.save_model(
            self.model,
            self.scaler,
            self.performance_metrics
        )
        
        if version_name:
            logger.info(f"Model retrained and saved as version {version_name}")
        else:
            # Fallback to legacy saving
            with open(self.model_file, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info("Model retrained successfully (legacy save)")
            
        # Archive old models
        self.model_manager.archive_old_models(keep_last_n=5)
        
    def optimize_thresholds(self):
        """Optimize regime thresholds based on historical performance"""
        logger.info("Optimizing regime thresholds...")
        
        # Get predictions with actuals
        valid_data = [p for p in self.predictions_history if p['actual_regime'] is not None and 'scan_data' in p]
        
        if len(valid_data) < 100:
            logger.warning("Not enough data for threshold optimization")
            return
            
        # Extract ratios and actual regimes
        data_points = []
        for pred in valid_data:
            scan_data = pred['scan_data']
            if scan_data.get('short_count', 0) > 0:
                ratio = scan_data['long_count'] / scan_data['short_count']
            else:
                ratio = 5.0 if scan_data.get('long_count', 0) > 0 else 1.0
                
            data_points.append({
                'ratio': ratio,
                'regime': pred['actual_regime']
            })
            
        df = pd.DataFrame(data_points)
        
        # Calculate optimal thresholds for each regime transition
        new_thresholds = self.optimized_thresholds.copy()
        
        # Find optimal boundaries between regimes
        regime_pairs = [
            ('strong_uptrend', 'uptrend', 'strong_bullish'),
            ('uptrend', 'choppy_bullish', 'bullish'),
            ('choppy_bullish', 'choppy', 'neutral_bullish'),
            ('choppy', 'choppy_bearish', 'neutral_bearish'),
            ('choppy_bearish', 'downtrend', 'bearish'),
            ('downtrend', 'strong_downtrend', 'strong_bearish')
        ]
        
        for regime1, regime2, threshold_key in regime_pairs:
            # Get data for both regimes
            regime1_ratios = df[df['regime'] == regime1]['ratio'].values
            regime2_ratios = df[df['regime'] == regime2]['ratio'].values
            
            if len(regime1_ratios) > 5 and len(regime2_ratios) > 5:
                # Find optimal threshold that maximizes separation
                all_ratios = np.concatenate([regime1_ratios, regime2_ratios])
                best_threshold = None
                best_score = -1
                
                for threshold in np.percentile(all_ratios, range(10, 91, 5)):
                    # Calculate separation score
                    correct1 = np.sum(regime1_ratios > threshold) if regime1 == 'strong_uptrend' or regime1 == 'uptrend' else np.sum(regime1_ratios < threshold)
                    correct2 = np.sum(regime2_ratios < threshold) if regime1 == 'strong_uptrend' or regime1 == 'uptrend' else np.sum(regime2_ratios > threshold)
                    
                    score = (correct1 + correct2) / (len(regime1_ratios) + len(regime2_ratios))
                    
                    if score > best_score:
                        best_score = score
                        best_threshold = threshold
                        
                if best_threshold is not None:
                    # Apply smoothing to avoid drastic changes
                    old_threshold = new_thresholds[threshold_key]
                    new_thresholds[threshold_key] = 0.7 * old_threshold + 0.3 * best_threshold
                    
        # Save optimized thresholds
        self.optimized_thresholds = new_thresholds
        with open(self.thresholds_file, 'w') as f:
            json.dump(self.optimized_thresholds, f, indent=2)
            
        # Record optimization
        self.performance_metrics['optimization_history'].append({
            'timestamp': datetime.datetime.now().isoformat(),
            'thresholds': new_thresholds,
            'data_points': len(data_points)
        })
        
        with open(self.performance_file, 'w') as f:
            json.dump(self.performance_metrics, f, indent=2)
            
        logger.info("Thresholds optimized successfully")
        
    def get_model_insights(self):
        """Get insights about model performance and important features"""
        insights = {
            'performance': {
                'accuracy': self.performance_metrics['accuracy'],
                'total_predictions': self.performance_metrics['total_predictions'],
                'regime_accuracy': self.performance_metrics['regime_accuracy']
            },
            'important_features': [],
            'optimization_status': {
                'last_training': self.performance_metrics.get('last_training'),
                'current_thresholds': self.optimized_thresholds
            }
        }
        
        # Get top features
        if self.performance_metrics.get('feature_importance'):
            importance = self.performance_metrics['feature_importance']
            sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
            insights['important_features'] = sorted_features[:5]
            
        return insights
    
    def save_model(self):
        """Save the current model and scaler to disk"""
        try:
            # Check if model and scaler are ready to save
            model_ready = hasattr(self.model, 'classes_') and len(self.model.classes_) > 0
            scaler_ready = hasattr(self.scaler, 'mean_') and self.scaler.mean_ is not None
            
            if model_ready and scaler_ready:
                # Save using model manager
                version_name = self.model_manager.save_model(
                    self.model,
                    self.scaler,
                    self.performance_metrics
                )
                
                if version_name:
                    logger.info(f"Model saved as version {version_name}")
                else:
                    # Fallback to legacy saving
                    with open(self.model_file, 'wb') as f:
                        pickle.dump(self.model, f)
                    with open(self.scaler_file, 'wb') as f:
                        pickle.dump(self.scaler, f)
                    logger.info("Model saved (legacy method)")
            else:
                logger.warning("Model or scaler not ready to save")
                
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def track_outcome(self, prediction_id, outcome_data):
        """Track outcome of a prediction for learning"""
        try:
            conn = sqlite3.connect(self.central_db_path)
            cursor = conn.cursor()
            
            # Get prediction details
            cursor.execute("""
                SELECT predicted_regime, actual_regime, confidence
                FROM regime_predictions
                WHERE id = ?
            """, (prediction_id,))
            
            result = cursor.fetchone()
            if result:
                predicted_regime, actual_regime, confidence = result
                
                # Calculate performance score
                if predicted_regime == actual_regime:
                    performance_score = confidence * outcome_data.get('market_performance', 1.0)
                else:
                    performance_score = -confidence * outcome_data.get('market_performance', 1.0)
                
                # Update outcome
                cursor.execute("""
                    UPDATE regime_predictions
                    SET outcome_score = ?,
                        feedback_timestamp = ?
                    WHERE id = ?
                """, (performance_score, datetime.datetime.now(), prediction_id))
                
                # Track feature performance
                feature_importance = outcome_data.get('important_features', {})
                for feature, importance in feature_importance.items():
                    cursor.execute("""
                        INSERT INTO feature_performance
                        (timestamp, feature_name, regime, importance_score, prediction_accuracy)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        datetime.datetime.now(),
                        feature,
                        actual_regime,
                        importance,
                        1.0 if predicted_regime == actual_regime else 0.0
                    ))
                
                conn.commit()
                logger.info(f"Tracked outcome for prediction {prediction_id}: score={performance_score:.2f}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error tracking outcome: {e}")


def main():
    """Test the predictor"""
    predictor = MarketRegimePredictor()
    
    # Example scan history
    scan_history = [
        {'long_count': 15, 'short_count': 5, 'timestamp': '2024-01-01T10:00:00'},
        {'long_count': 18, 'short_count': 4, 'timestamp': '2024-01-01T10:30:00'},
        {'long_count': 20, 'short_count': 3, 'timestamp': '2024-01-01T11:00:00'},
    ]
    
    # Make prediction
    prediction = predictor.predict_next_regime(scan_history)
    
    if prediction:
        print(f"Predicted Regime: {prediction['predicted_regime']}")
        print(f"Confidence: {prediction['confidence']:.2%}")
        print("\nModel Insights:")
        insights = predictor.get_model_insights()
        print(f"Overall Accuracy: {insights['performance']['accuracy']:.2%}")
        
        
if __name__ == "__main__":
    main()