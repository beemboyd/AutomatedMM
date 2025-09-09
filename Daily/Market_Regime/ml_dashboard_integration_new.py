#!/usr/bin/env python3
"""
Enhanced ML Dashboard Integration for Market Regime Predictions
Connects to the new ML prediction API service on port 8083
"""

import requests
import json
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ML Prediction API endpoint
ML_API_BASE = "http://localhost:8083/api/v1"

def get_ml_regime_prediction():
    """Get current ML market regime prediction from the API"""
    try:
        response = requests.get(f"{ML_API_BASE}/predict", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return {
                'regime': data.get('regime', 'Unknown'),
                'confidence': data.get('confidence', 0),
                'timestamp': data.get('timestamp', ''),
                'model_version': data.get('model_version', 'unknown')
            }
    except Exception as e:
        logger.error(f"Error getting ML prediction: {e}")
    
    return {
        'regime': 'Unavailable',
        'confidence': 0,
        'timestamp': datetime.now().isoformat(),
        'model_version': 'offline'
    }

def get_ml_insights():
    """Get comprehensive ML insights including predictions and features"""
    insights = {
        'prediction': get_ml_regime_prediction(),
        'features': {},
        'metrics': {},
        'model_info': {}
    }
    
    try:
        # Get current features
        response = requests.get(f"{ML_API_BASE}/features/current", timeout=2)
        if response.status_code == 200:
            data = response.json()
            features = data.get('features', {})
            
            # Extract key features for display
            insights['features'] = {
                'breadth_volatility': round(features.get('breadth_volatility', 0), 2),
                'ls_ratio': round(features.get('ls_ratio_combined', 1), 2),
                'trend_strength': round(features.get('trend_strength', 0), 2),
                'market_breadth': round(features.get('binary_breadth_pct', 50), 1),
                'sma_breadth': round(features.get('sma_breadth_avg', 50), 1),
                'momentum': round(features.get('breadth_momentum', 0), 2)
            }
    except Exception as e:
        logger.error(f"Error getting ML features: {e}")
    
    try:
        # Get market metrics
        response = requests.get(f"{ML_API_BASE}/metrics", timeout=2)
        if response.status_code == 200:
            data = response.json()
            insights['metrics'] = {
                'total_patterns': data.get('total_patterns', 0),
                'long_count': data.get('long_count_daily', 0),
                'short_count': data.get('short_count_daily', 0),
                'market_phase': data.get('market_phase', 'Unknown')
            }
    except Exception as e:
        logger.error(f"Error getting ML metrics: {e}")
    
    try:
        # Get model info
        response = requests.get(f"{ML_API_BASE}/model/info", timeout=2)
        if response.status_code == 200:
            data = response.json()
            insights['model_info'] = {
                'version': data.get('version', 'unknown'),
                'model_type': data.get('model_type', 'unknown'),
                'accuracy': round(data.get('accuracy', 0) * 100, 1),
                'feature_count': data.get('feature_count', 0)
            }
    except Exception as e:
        logger.error(f"Error getting ML model info: {e}")
    
    return insights

def get_ml_alerts():
    """Get ML-based alerts for significant market changes"""
    alerts = []
    
    try:
        # Get current prediction
        prediction = get_ml_regime_prediction()
        
        # Get historical predictions for comparison
        response = requests.get(f"{ML_API_BASE}/history?days=1", timeout=2)
        if response.status_code == 200:
            data = response.json()
            predictions = data.get('predictions', [])
            
            if len(predictions) >= 2:
                # Check for regime change
                current_regime = prediction['regime']
                prev_regime = predictions[1].get('regime', 'Unknown')
                
                if current_regime != prev_regime and current_regime != 'Unavailable':
                    alerts.append({
                        'type': 'regime_change',
                        'severity': 'high',
                        'message': f'Market regime changed from {prev_regime} to {current_regime}',
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Check for confidence drop
                current_conf = prediction['confidence']
                prev_conf = predictions[1].get('confidence', 0)
                
                if current_conf < 0.6 and prev_conf >= 0.6:
                    alerts.append({
                        'type': 'confidence_drop',
                        'severity': 'medium',
                        'message': f'Model confidence dropped below 60% ({current_conf:.1%})',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Check for extreme predictions
            if prediction['confidence'] > 0.85:
                alerts.append({
                    'type': 'high_confidence',
                    'severity': 'info',
                    'message': f'High confidence {prediction["regime"]} prediction ({prediction["confidence"]:.1%})',
                    'timestamp': datetime.now().isoformat()
                })
                
    except Exception as e:
        logger.error(f"Error generating ML alerts: {e}")
    
    return alerts

def get_ml_performance():
    """Get ML model performance metrics"""
    performance = {
        'health': 'unknown',
        'latency': 0,
        'predictions_24h': 0,
        'accuracy': 0,
        'last_retrain': 'unknown'
    }
    
    try:
        # Check health
        response = requests.get(f"{ML_API_BASE}/health", timeout=1)
        if response.status_code == 200:
            data = response.json()
            performance['health'] = data.get('status', 'unknown')
            
        # Get model info for accuracy
        response = requests.get(f"{ML_API_BASE}/model/info", timeout=2)
        if response.status_code == 200:
            data = response.json()
            performance['accuracy'] = round(data.get('accuracy', 0) * 100, 1)
            
            # Calculate model age for last retrain estimate
            version = data.get('version', '')
            if version:
                try:
                    # Parse version timestamp (format: YYYYMMDD_HHMMSS)
                    model_date = datetime.strptime(version, '%Y%m%d_%H%M%S')
                    days_old = (datetime.now() - model_date).days
                    performance['last_retrain'] = f"{days_old} days ago"
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Error getting ML performance: {e}")
    
    return performance

def format_ml_display_data():
    """Format ML data for dashboard display"""
    insights = get_ml_insights()
    prediction = insights['prediction']
    
    # Determine regime color and icon
    regime_colors = {
        'Bullish': '#28a745',
        'Bearish': '#dc3545',
        'Neutral': '#ffc107',
        'Unknown': '#6c757d',
        'Unavailable': '#6c757d'
    }
    
    regime_icons = {
        'Bullish': '📈',
        'Bearish': '📉',
        'Neutral': '➡️',
        'Unknown': '❓',
        'Unavailable': '⚠️'
    }
    
    display_data = {
        'regime': {
            'label': prediction['regime'],
            'confidence': round(prediction['confidence'] * 100, 1),
            'color': regime_colors.get(prediction['regime'], '#6c757d'),
            'icon': regime_icons.get(prediction['regime'], '❓'),
            'model_version': prediction.get('model_version', 'unknown')
        },
        'features': insights['features'],
        'metrics': insights['metrics'],
        'model': insights['model_info'],
        'timestamp': datetime.now().isoformat()
    }
    
    return display_data

# Export functions for dashboard integration
__all__ = [
    'get_ml_regime_prediction',
    'get_ml_insights', 
    'get_ml_alerts',
    'get_ml_performance',
    'format_ml_display_data'
]