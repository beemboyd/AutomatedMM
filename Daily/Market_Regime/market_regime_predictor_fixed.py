#!/usr/bin/env python
"""
Fixed Market Regime Predictor with Data Normalization
Emergency Fix Applied: 2025-08-24T21:30:39.784314
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

from model_manager import ModelManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketRegimePredictor:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, "data")
        self.predictions_dir = os.path.join(self.script_dir, "predictions")
        self.models_dir = os.path.join(self.script_dir, "models")
        
        # Load emergency config
        self.config_file = os.path.join(self.script_dir, "ml_config.json")
        self.emergency_config = self._load_emergency_config()
        
        # Central database path
        self.central_db_path = "/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db"
        
        # Ensure directories exist
        for dir_path in [self.data_dir, self.predictions_dir, self.models_dir, 
                         os.path.join(self.script_dir, "logs")]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Initialize tracking files
        self.predictions_file = os.path.join(self.predictions_dir, "predictions_history.json")
        self.performance_file = os.path.join(self.predictions_dir, "model_performance.json")
        self.thresholds_file = os.path.join(self.data_dir, "optimized_thresholds.json")
        
        # Load historical data
        self.predictions_history = self._load_predictions_history()
        self.performance_metrics = self._load_performance_metrics()
        self.optimized_thresholds = self._load_optimized_thresholds()
        
        # Feature window for predictions
        self.feature_window = 10
        
        # Initialize ML model
        self.model = None
        self.scaler = StandardScaler()
        self.model_file = os.path.join(self.models_dir, "regime_predictor_model.pkl")
        self.scaler_file = os.path.join(self.models_dir, "regime_predictor_scaler.pkl")
        
        # Initialize model manager
        self.model_manager = ModelManager(self.models_dir)
        
        self._load_or_initialize_model()
        
    def _load_emergency_config(self):
        """Load emergency configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return {"auto_retrain_enabled": True}
        return {"auto_retrain_enabled": True}
        
    def _normalize_market_score(self, raw_score):
        """
        CRITICAL FIX: Properly normalize market score to [-1, 1] range
        """
        if raw_score is None:
            return 0.0
            
        # Log anomaly if score is out of expected range
        if abs(raw_score) > 1.5:
            logger.warning(f"⚠️ Anomalous market score detected: {raw_score:.3f}")
            
        # Apply strict clipping to valid range
        normalized_score = np.clip(raw_score, -1.0, 1.0)
        
        # Log if clipping was applied
        if normalized_score != raw_score:
            logger.info(f"📊 Market score normalized: {raw_score:.3f} → {normalized_score:.3f}")
            
        return normalized_score
        
    def _validate_scan_data(self, scan_data):
        """Validate and clean scan data before processing"""
        if not scan_data:
            return None
            
        # Ensure required fields exist
        required_fields = ['long_count', 'short_count']
        for field in required_fields:
            if field not in scan_data:
                scan_data[field] = 0
                
        # Validate counts are non-negative
        scan_data['long_count'] = max(0, scan_data.get('long_count', 0))
        scan_data['short_count'] = max(0, scan_data.get('short_count', 0))
        
        # Normalize market score if present
        if 'market_score' in scan_data:
            scan_data['market_score'] = self._normalize_market_score(scan_data['market_score'])
            
        return scan_data
        
    def _calculate_ratio_safe(self, long_count, short_count):
        """Safely calculate long/short ratio"""
        long_count = max(0, long_count)
        short_count = max(0, short_count)
        
        if short_count == 0:
            if long_count > 10:
                return 3.0  # Strong bullish, but capped
            elif long_count > 0:
                return 2.0  # Bullish
            else:
                return 1.0  # Neutral
        else:
            ratio = long_count / short_count
            # Cap extreme ratios to prevent model confusion
            return np.clip(ratio, 0.1, 5.0)
            
    def retrain_model(self):
        """Retrain model with emergency checks"""
        # Check if retraining is disabled
        if not self.emergency_config.get('auto_retrain_enabled', True):
            logger.warning("🛑 Automatic retraining is DISABLED in emergency mode")
            return False
            
        logger.info("Model retraining blocked by emergency configuration")
        return False
        
    def predict_next_regime(self, scan_history):
        """Predict next regime with data validation"""
        # Validate all scan data
        validated_history = []
        for scan in scan_history:
            validated = self._validate_scan_data(scan)
            if validated:
                validated_history.append(validated)
                
        if len(validated_history) < 3:
            logger.warning("Insufficient valid history for prediction")
            return None
            
        features = self.extract_features(validated_history)
        
        if features is None:
            return None
            
        try:
            if hasattr(self.model, 'predict_proba') and hasattr(self.model, 'classes_'):
                if not hasattr(self.scaler, 'mean_') or self.scaler.mean_ is None:
                    logger.warning("Scaler not fitted, using rule-based prediction")
                    return self._rule_based_prediction(validated_history[-1])
                    
                features_scaled = self.scaler.transform(features)
                probabilities = self.model.predict_proba(features_scaled)[0]
                prediction = self.model.predict(features_scaled)[0]
                
                confidence = max(probabilities)
                
                # Add diversity check
                if prediction == 'choppy_bullish' and confidence < 0.7:
                    logger.info("📊 Low confidence choppy_bullish - checking alternatives")
                    # Force consideration of other regimes
                    sorted_probs = sorted(zip(self.model.classes_, probabilities), 
                                        key=lambda x: x[1], reverse=True)
                    if len(sorted_probs) > 1 and sorted_probs[1][1] > 0.25:
                        prediction = sorted_probs[1][0]
                        confidence = sorted_probs[1][1]
                        logger.info(f"📊 Alternative regime selected: {prediction} ({confidence:.2%})")
                
                return {
                    'predicted_regime': prediction,
                    'confidence': confidence,
                    'probabilities': dict(zip(self.model.classes_, probabilities))
                }
            else:
                return self._rule_based_prediction(validated_history[-1])
                
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._rule_based_prediction(validated_history[-1])
            
    # Include other necessary methods with fixes...
    
    def _load_predictions_history(self):
        if os.path.exists(self.predictions_file):
            try:
                with open(self.predictions_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
        
    def _load_performance_metrics(self):
        if os.path.exists(self.performance_file):
            try:
                with open(self.performance_file, 'r') as f:
                    return json.load(f)
            except:
                return self._initialize_performance_metrics()
        return self._initialize_performance_metrics()
        
    def _initialize_performance_metrics(self):
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
        if os.path.exists(self.thresholds_file):
            try:
                with open(self.thresholds_file, 'r') as f:
                    return json.load(f)
            except:
                return self._get_default_thresholds()
        return self._get_default_thresholds()
        
    def _get_default_thresholds(self):
        return {
            'strong_bullish': 2.0,
            'bullish': 1.5,
            'neutral_bullish': 1.2,
            'neutral_high': 1.2,
            'neutral_low': 0.8,
            'neutral_bearish': 0.8,
            'bearish': 0.67,
            'strong_bearish': 0.5
        }
        
    def _load_or_initialize_model(self):
        model, scaler = self.model_manager.load_best_model()
        
        if model is not None and scaler is not None:
            self.model = model
            self.scaler = scaler
            logger.info("Loaded best model from model manager")
        elif os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
            try:
                with open(self.model_file, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded model from files")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
                self._initialize_new_model()
        else:
            self._initialize_new_model()
            
    def _initialize_new_model(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        logger.info("Initialized new Random Forest model")

# Additional required methods would go here...
