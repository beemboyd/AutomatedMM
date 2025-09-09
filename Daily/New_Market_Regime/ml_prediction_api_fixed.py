#!/usr/bin/env python3
"""
Fixed ML Market Regime Prediction API Service
Provides real-time market regime predictions via REST API
"""

import os
import json
import sqlite3
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
from typing import Dict, List, Optional
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Paths
BASE_DIR = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime'
ML_DB_PATH = os.path.join(BASE_DIR, 'ml_market_regime.db')
ANALYSIS_DB_PATH = '/Users/maverick/PycharmProjects/Analysis/data/warehouse/market_data.db'
MODELS_DIR = os.path.join(BASE_DIR, 'models')


class MarketRegimePredictor:
    """Handles ML predictions for market regime"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.metadata = None
        self.features = []
        self.load_model()
    
    def load_model(self):
        """Load the latest trained model"""
        try:
            # Hardcode the known working model path
            model_path = os.path.join(MODELS_DIR, 'market_regime_gradient_boosting_20250909_133414.pkl')
            scaler_path = os.path.join(MODELS_DIR, 'scaler_20250909_133414.pkl')
            metadata_path = os.path.join(MODELS_DIR, 'metadata_20250909_133414.json')
            
            # Load model
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
                self.features = self.metadata.get('features', [])
            
            logger.info(f"Loaded model with {len(self.features)} features")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
    
    def get_latest_features(self) -> Optional[Dict]:
        """Get latest feature data from databases"""
        try:
            # Get breadth data
            conn = sqlite3.connect(ANALYSIS_DB_PATH)
            
            query = """
                SELECT * FROM india_breadth
                WHERE date >= date('now', '-7 days')
                ORDER BY date DESC
                LIMIT 1
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                logger.warning("No recent data in Analysis DB")
                return None
            
            row = df.iloc[0]
            logger.info(f"Found data for {row['date']}")
            
            # Create feature dict with all required features
            feature_values = {}
            
            # Direct mappings
            feature_values['binary_breadth_pct'] = float(row.get('binary_breadth_pct', 50))
            feature_values['weighted_breadth_index'] = float(row.get('weighted_breadth_index', 0.5))
            feature_values['breadth_momentum'] = float(row.get('breadth_momentum', 0))
            feature_values['market_momentum_index'] = float(row.get('market_momentum_index', 0))
            feature_values['fast_wm_pct'] = float(row.get('fast_wm_pct', 50))
            feature_values['slow_wm_pct'] = float(row.get('slow_wm_pct', 50))
            
            # Calculated features
            feature_values['breadth_strength'] = feature_values['binary_breadth_pct'] / 100.0
            feature_values['breadth_momentum_ma5'] = feature_values['breadth_momentum']
            feature_values['ad_ratio'] = float(row.get('active_positive', 100)) / max(float(row.get('active_negative', 100)), 1)
            feature_values['ad_diff'] = float(row.get('active_positive', 100)) - float(row.get('active_negative', 100))
            feature_values['ad_ratio_ma5'] = feature_values['ad_ratio']
            feature_values['sma_breadth_avg'] = (feature_values['fast_wm_pct'] + feature_values['slow_wm_pct']) / 2
            feature_values['sma_breadth_diff'] = feature_values['fast_wm_pct'] - feature_values['slow_wm_pct']
            feature_values['trend_strength'] = abs(feature_values['breadth_momentum'])
            feature_values['trend_change'] = 0
            feature_values['breadth_volatility'] = 10.0
            
            # L/S ratio features - check ML database
            try:
                ml_conn = sqlite3.connect(ML_DB_PATH)
                ls_query = """
                    SELECT ls_ratio_combined FROM market_metrics
                    ORDER BY timestamp DESC LIMIT 1
                """
                ls_result = pd.read_sql_query(ls_query, ml_conn)
                ml_conn.close()
                
                if not ls_result.empty:
                    feature_values['ls_ratio_combined'] = float(ls_result.iloc[0]['ls_ratio_combined'])
                else:
                    feature_values['ls_ratio_combined'] = 1.0
            except:
                feature_values['ls_ratio_combined'] = 1.0
            
            feature_values['ls_ratio_ma5'] = feature_values['ls_ratio_combined']
            feature_values['ls_ratio_ma10'] = feature_values['ls_ratio_combined']
            feature_values['ls_momentum'] = 0
            
            # Volume features
            feature_values['avg_volume_ratio'] = 1.0
            feature_values['volume_strength'] = 50.0
            
            return feature_values
            
        except Exception as e:
            logger.error(f"Error getting features: {e}")
            return None
    
    def predict(self, features: Optional[Dict] = None) -> Dict:
        """Make prediction for current market regime"""
        
        if self.model is None:
            return {
                'error': 'No model loaded',
                'regime': 'Unknown',
                'confidence': 0
            }
        
        try:
            # Get features if not provided
            if features is None:
                features = self.get_latest_features()
            
            if features is None:
                return {
                    'error': 'No data available',
                    'regime': 'Unknown',
                    'confidence': 0
                }
            
            # Prepare feature vector in correct order
            X = []
            for feature_name in self.features:
                value = features.get(feature_name, 0)
                X.append(value)
            
            X = np.array([X])
            logger.info(f"Feature array shape: {X.shape}")
            
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Make prediction
            prediction = self.model.predict(X_scaled)[0]
            proba = self.model.predict_proba(X_scaled)[0]
            confidence = float(np.max(proba))
            
            # Map prediction to regime
            regime_map = {0: 'Bearish', 1: 'Neutral', 2: 'Bullish'}
            regime = regime_map.get(int(prediction), 'Unknown')
            
            result = {
                'regime': regime,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'features_used': len(self.features),
                'model_version': self.metadata.get('timestamp', 'unknown') if self.metadata else 'unknown',
                'probabilities': {
                    'Bearish': float(proba[0]) if len(proba) > 0 else 0,
                    'Neutral': float(proba[1]) if len(proba) > 1 else 0,
                    'Bullish': float(proba[2]) if len(proba) > 2 else 0
                }
            }
            
            logger.info(f"Prediction: {regime} with {confidence:.1%} confidence")
            return result
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'error': str(e),
                'regime': 'Unknown',
                'confidence': 0
            }


# Initialize predictor
predictor = MarketRegimePredictor()


@app.route('/api/v1/predict', methods=['GET'])
def predict_current():
    """Get current market regime prediction"""
    result = predictor.predict()
    
    if 'error' in result and result['error'] != 'No data available':
        return jsonify(result), 500
    
    return jsonify(result)


@app.route('/api/v1/features/current', methods=['GET'])
def get_current_features():
    """Get current feature values"""
    try:
        features = predictor.get_latest_features()
        
        if features is None:
            return jsonify({'error': 'No data available'}), 400
        
        return jsonify({
            'features': features,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/model/info', methods=['GET'])
def model_info():
    """Get model information"""
    
    if predictor.metadata:
        return jsonify({
            'version': predictor.metadata.get('timestamp'),
            'model_type': predictor.metadata.get('model_type'),
            'accuracy': predictor.metadata.get('accuracy'),
            'features': predictor.features,
            'feature_count': len(predictor.features)
        })
    
    return jsonify({'error': 'No model loaded'}), 500


@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy' if predictor.model else 'no_model',
        'model_loaded': predictor.model is not None,
        'timestamp': datetime.now().isoformat()
    })


def run_api_server(port: int = 8083):
    """Run the API server"""
    print("\n" + "="*60)
    print("ML MARKET REGIME PREDICTION API (FIXED)")
    print("="*60)
    print(f"Starting API server on http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /api/v1/predict       - Current prediction")
    print("  GET  /api/v1/features/current - Current features")
    print("  GET  /api/v1/model/info    - Model information")
    print("  GET  /api/v1/health        - Health check")
    print("\nPress Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    run_api_server()