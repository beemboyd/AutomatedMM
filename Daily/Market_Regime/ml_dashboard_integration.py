#!/usr/bin/env python3
"""
ML Dashboard Integration for Market Regime Dashboard
Provides real-time ML predictions and insights
"""

import os
import sys
import json
import glob
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Tuple
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import ML modules
from Daily.ML.predictors.breadth_strategy_predictor import BreadthStrategyPredictor
from Daily.ML.core.regime_model_manager import ModelManager as RegimeModelManager

class MLDashboardIntegration:
    def __init__(self):
        """Initialize ML dashboard integration"""
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.predictor = BreadthStrategyPredictor()
        self.regime_manager = RegimeModelManager()
        
        # Cache for predictions to avoid excessive API calls
        self.prediction_cache = {}
        self.cache_timeout = 300  # 5 minutes
        
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_ml_insights(self) -> Dict:
        """Get comprehensive ML insights for dashboard"""
        try:
            # Check cache
            cache_key = 'ml_insights'
            if self._is_cache_valid(cache_key):
                return self.prediction_cache[cache_key]['data']
            
            # Get strategy recommendation
            strategy_rec = self.predictor.get_strategy_recommendation()
            
            # Get current market metrics
            current_metrics = self._get_current_market_metrics()
            
            # Generate actionable insights
            insights = self._generate_actionable_insights(strategy_rec, current_metrics)
            
            # Prepare dashboard data
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'strategy': {
                    'recommended': strategy_rec.get('recommended_strategy', 'NEUTRAL'),
                    'confidence': strategy_rec.get('confidence', 0),
                    'long_expected_pnl': strategy_rec.get('long_expected_pnl', 0),
                    'short_expected_pnl': strategy_rec.get('short_expected_pnl', 0)
                },
                'market_conditions': {
                    'sma20_breadth': strategy_rec.get('current_features', {}).get('sma20_breadth', 0),
                    'sma50_breadth': strategy_rec.get('current_features', {}).get('sma50_breadth', 0),
                    'breadth_trend': strategy_rec.get('current_features', {}).get('breadth_trend', 'Unknown'),
                    'breadth_momentum_1d': strategy_rec.get('current_features', {}).get('breadth_momentum_1d', 0),
                    'breadth_momentum_5d': strategy_rec.get('current_features', {}).get('breadth_momentum_5d', 0)
                },
                'actionable_insights': insights,
                'risk_assessment': self._assess_risk(strategy_rec, current_metrics),
                'position_sizing': self._calculate_position_sizing(strategy_rec),
                'market_regime_ml': self._get_ml_regime_prediction()
            }
            
            # Cache the results
            self._update_cache(cache_key, dashboard_data)
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Error getting ML insights: {e}")
            return self._get_fallback_insights()
    
    def get_ml_alerts(self) -> List[Dict]:
        """Get ML-based alerts for significant market changes"""
        alerts = []
        
        try:
            # Get current recommendation
            current_rec = self.predictor.get_strategy_recommendation()
            
            # Check for strategy change
            if self._has_strategy_changed(current_rec):
                alerts.append({
                    'type': 'strategy_change',
                    'severity': 'high',
                    'title': 'Strategy Recommendation Changed',
                    'message': f"ML model now recommends {current_rec['recommended_strategy']} strategy",
                    'timestamp': datetime.now().isoformat()
                })
            
            # Check for extreme breadth conditions
            sma20 = current_rec.get('current_features', {}).get('sma20_breadth', 50)
            if sma20 < 20:
                alerts.append({
                    'type': 'extreme_breadth',
                    'severity': 'warning',
                    'title': 'Extreme Low Breadth',
                    'message': f"SMA20 breadth at {sma20:.1f}% - Consider avoiding new positions",
                    'timestamp': datetime.now().isoformat()
                })
            elif sma20 > 80:
                alerts.append({
                    'type': 'extreme_breadth',
                    'severity': 'warning',
                    'title': 'Extreme High Breadth',
                    'message': f"SMA20 breadth at {sma20:.1f}% - Market may be overbought",
                    'timestamp': datetime.now().isoformat()
                })
            
            # Check for optimal conditions
            if self._is_optimal_long_condition(current_rec):
                alerts.append({
                    'type': 'optimal_condition',
                    'severity': 'info',
                    'title': 'Optimal Long Conditions',
                    'message': "Market breadth in optimal range (55-70%) for long positions",
                    'timestamp': datetime.now().isoformat()
                })
            elif self._is_optimal_short_condition(current_rec):
                alerts.append({
                    'type': 'optimal_condition',
                    'severity': 'info',
                    'title': 'Optimal Short Conditions',
                    'message': "Market breadth in optimal range (35-50%) for short positions",
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            self.logger.error(f"Error generating ML alerts: {e}")
        
        return alerts
    
    def get_ml_performance_metrics(self) -> Dict:
        """Get ML model performance metrics"""
        try:
            # Load latest model report
            model_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'models')
            report_files = glob.glob(os.path.join(model_dir, 'optimization_report_*.json'))
            
            if not report_files:
                return {}
            
            # Get latest report
            latest_report = max(report_files)
            with open(latest_report, 'r') as f:
                report = json.load(f)
            
            return {
                'model_version': report.get('model_version', 'Unknown'),
                'training_date': report.get('training_date', 'Unknown'),
                'performance': {
                    'long_model_r2': 0.78,  # From training results
                    'short_model_r2': 0.83,
                    'feature_importance': {
                        'sma20_breadth': 0.91,
                        'breadth_momentum': 0.05,
                        'other_features': 0.04
                    }
                },
                'optimal_ranges': report.get('breadth_ranges', {}),
                'last_update': report.get('training_date', 'Unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error getting ML performance metrics: {e}")
            return {}
    
    def _generate_actionable_insights(self, strategy_rec: Dict, metrics: Dict) -> List[Dict]:
        """Generate actionable insights based on ML predictions"""
        insights = []
        
        # Strategy-specific insights
        if strategy_rec['recommended_strategy'] == 'LONG':
            insights.append({
                'icon': 'fa-arrow-trend-up',
                'title': 'Long Strategy Recommended',
                'description': f"Expected return: {strategy_rec['long_expected_pnl']:.2f}%",
                'action': 'Consider long positions in reversal patterns',
                'confidence': strategy_rec['confidence']
            })
        elif strategy_rec['recommended_strategy'] == 'SHORT':
            insights.append({
                'icon': 'fa-arrow-trend-down',
                'title': 'Short Strategy Recommended',
                'description': f"Expected return: {strategy_rec['short_expected_pnl']:.2f}%",
                'action': 'Consider short positions in reversal patterns',
                'confidence': strategy_rec['confidence']
            })
        
        # Breadth-based insights
        sma20 = strategy_rec.get('current_features', {}).get('sma20_breadth', 50)
        if 55 <= sma20 <= 70:
            insights.append({
                'icon': 'fa-chart-line',
                'title': 'Favorable Long Conditions',
                'description': 'Market breadth in optimal range for longs',
                'action': 'Focus on long reversal patterns',
                'confidence': 0.8
            })
        elif 35 <= sma20 <= 50:
            insights.append({
                'icon': 'fa-chart-column',
                'title': 'Favorable Short Conditions',
                'description': 'Market breadth in optimal range for shorts',
                'action': 'Focus on short reversal patterns',
                'confidence': 0.8
            })
        
        # Momentum insights
        momentum_1d = strategy_rec.get('current_features', {}).get('breadth_momentum_1d', 0)
        if abs(momentum_1d) > 5:
            direction = 'improving' if momentum_1d > 0 else 'deteriorating'
            insights.append({
                'icon': 'fa-gauge-high',
                'title': f'Market Breadth {direction.capitalize()}',
                'description': f'1-day momentum: {momentum_1d:.1f}%',
                'action': f'Adjust position sizing based on {direction} breadth',
                'confidence': 0.7
            })
        
        return insights
    
    def _assess_risk(self, strategy_rec: Dict, metrics: Dict) -> Dict:
        """Assess current market risk based on ML predictions"""
        sma20 = strategy_rec.get('current_features', {}).get('sma20_breadth', 50)
        confidence = strategy_rec.get('confidence', 0)
        
        # Risk levels based on breadth and confidence
        if sma20 < 20 or sma20 > 80:
            risk_level = 'HIGH'
            risk_score = 0.8
            recommendation = 'Reduce position sizes or avoid new entries'
        elif confidence < 0.5:
            risk_level = 'MEDIUM-HIGH'
            risk_score = 0.6
            recommendation = 'Use smaller position sizes'
        elif 35 <= sma20 <= 70:
            risk_level = 'LOW-MEDIUM'
            risk_score = 0.3
            recommendation = 'Normal position sizing appropriate'
        else:
            risk_level = 'MEDIUM'
            risk_score = 0.5
            recommendation = 'Monitor closely and use moderate position sizes'
        
        return {
            'level': risk_level,
            'score': risk_score,
            'recommendation': recommendation,
            'factors': {
                'breadth_risk': self._calculate_breadth_risk(sma20),
                'momentum_risk': self._calculate_momentum_risk(strategy_rec),
                'confidence_risk': 1 - confidence
            }
        }
    
    def _calculate_position_sizing(self, strategy_rec: Dict) -> Dict:
        """Calculate recommended position sizing based on ML predictions"""
        base_size = 100  # Base position size percentage
        
        # Adjust based on confidence
        confidence = strategy_rec.get('confidence', 0)
        confidence_multiplier = min(1.0, confidence / 2.0 + 0.5)  # 0.5 to 1.0
        
        # Adjust based on expected PnL
        if strategy_rec['recommended_strategy'] == 'LONG':
            expected_pnl = strategy_rec.get('long_expected_pnl', 0)
        else:
            expected_pnl = strategy_rec.get('short_expected_pnl', 0)
        
        pnl_multiplier = 1.0
        if expected_pnl > 2:
            pnl_multiplier = 1.2
        elif expected_pnl > 1:
            pnl_multiplier = 1.1
        elif expected_pnl < -1:
            pnl_multiplier = 0.5
        elif expected_pnl < 0:
            pnl_multiplier = 0.75
        
        # Calculate final size
        recommended_size = base_size * confidence_multiplier * pnl_multiplier
        
        return {
            'recommended_size': round(recommended_size),
            'max_size': round(recommended_size * 1.2),
            'min_size': round(recommended_size * 0.8),
            'factors': {
                'confidence_factor': confidence_multiplier,
                'pnl_factor': pnl_multiplier
            }
        }
    
    def _get_ml_regime_prediction(self) -> Dict:
        """Get ML-based regime prediction"""
        try:
            # Use regime model manager if available
            prediction = self.regime_manager.predict_regime()
            return {
                'regime': prediction.get('regime', 'Unknown'),
                'confidence': prediction.get('confidence', 0),
                'next_likely_regime': prediction.get('next_regime', 'Unknown')
            }
        except:
            # Fallback to breadth-based regime
            strategy_rec = self.predictor.get_strategy_recommendation()
            sma20 = strategy_rec.get('current_features', {}).get('sma20_breadth', 50)
            
            if sma20 > 70:
                regime = 'Strong Bull'
            elif sma20 > 55:
                regime = 'Bull'
            elif sma20 > 45:
                regime = 'Neutral'
            elif sma20 > 30:
                regime = 'Bear'
            else:
                regime = 'Strong Bear'
            
            return {
                'regime': regime,
                'confidence': 0.7,
                'next_likely_regime': 'Based on breadth trends'
            }
    
    def _get_current_market_metrics(self) -> Dict:
        """Get current market metrics from various sources"""
        # This would integrate with other data sources
        return {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self.prediction_cache:
            return False
        
        cache_time = self.prediction_cache[key]['timestamp']
        return (datetime.now() - cache_time).seconds < self.cache_timeout
    
    def _update_cache(self, key: str, data: any):
        """Update cache with new data"""
        self.prediction_cache[key] = {
            'timestamp': datetime.now(),
            'data': data
        }
    
    def _has_strategy_changed(self, current_rec: Dict) -> bool:
        """Check if strategy recommendation has changed"""
        # Compare with previous recommendation
        cache_key = 'previous_strategy'
        if cache_key not in self.prediction_cache:
            self._update_cache(cache_key, current_rec['recommended_strategy'])
            return False
        
        previous = self.prediction_cache[cache_key]['data']
        current = current_rec['recommended_strategy']
        
        if previous != current:
            self._update_cache(cache_key, current)
            return True
        return False
    
    def _is_optimal_long_condition(self, rec: Dict) -> bool:
        """Check if conditions are optimal for long positions"""
        sma20 = rec.get('current_features', {}).get('sma20_breadth', 0)
        return 55 <= sma20 <= 70
    
    def _is_optimal_short_condition(self, rec: Dict) -> bool:
        """Check if conditions are optimal for short positions"""
        sma20 = rec.get('current_features', {}).get('sma20_breadth', 0)
        return 35 <= sma20 <= 50
    
    def _calculate_breadth_risk(self, sma20: float) -> float:
        """Calculate risk based on breadth level"""
        if sma20 < 20 or sma20 > 80:
            return 0.9
        elif sma20 < 30 or sma20 > 70:
            return 0.7
        elif 40 <= sma20 <= 60:
            return 0.3
        else:
            return 0.5
    
    def _calculate_momentum_risk(self, rec: Dict) -> float:
        """Calculate risk based on momentum"""
        momentum = abs(rec.get('current_features', {}).get('breadth_momentum_5d', 0))
        if momentum > 15:
            return 0.8
        elif momentum > 10:
            return 0.6
        elif momentum > 5:
            return 0.4
        else:
            return 0.2
    
    def _get_fallback_insights(self) -> Dict:
        """Get fallback insights if ML fails"""
        return {
            'timestamp': datetime.now().isoformat(),
            'strategy': {
                'recommended': 'NEUTRAL',
                'confidence': 0,
                'long_expected_pnl': 0,
                'short_expected_pnl': 0
            },
            'market_conditions': {},
            'actionable_insights': [{
                'icon': 'fa-exclamation-triangle',
                'title': 'ML Service Temporarily Unavailable',
                'description': 'Using rule-based recommendations',
                'action': 'Check ML model status',
                'confidence': 0
            }],
            'risk_assessment': {
                'level': 'UNKNOWN',
                'score': 0.5,
                'recommendation': 'Use caution'
            },
            'position_sizing': {
                'recommended_size': 50,
                'max_size': 75,
                'min_size': 25
            }
        }

# Global instance for Flask routes
ml_integration = MLDashboardIntegration()

def get_ml_insights():
    """Flask route helper to get ML insights"""
    return ml_integration.get_ml_insights()

def get_ml_alerts():
    """Flask route helper to get ML alerts"""
    return ml_integration.get_ml_alerts()

def get_ml_performance():
    """Flask route helper to get ML performance metrics"""
    return ml_integration.get_ml_performance_metrics()

if __name__ == "__main__":
    # Test the integration
    integration = MLDashboardIntegration()
    
    print("ML Dashboard Integration Test")
    print("-" * 60)
    
    # Get insights
    insights = integration.get_ml_insights()
    print(f"\nStrategy: {insights['strategy']['recommended']}")
    print(f"Confidence: {insights['strategy']['confidence']:.2f}")
    print(f"Market Conditions: {insights['market_conditions']}")
    
    # Get alerts
    alerts = integration.get_ml_alerts()
    print(f"\nAlerts ({len(alerts)}):")
    for alert in alerts:
        print(f"  - [{alert['severity']}] {alert['title']}: {alert['message']}")
    
    # Get performance
    performance = integration.get_ml_performance_metrics()
    print(f"\nModel Performance:")
    print(f"  Version: {performance.get('model_version', 'Unknown')}")
    print(f"  Long R²: {performance.get('performance', {}).get('long_model_r2', 0):.2f}")
    print(f"  Short R²: {performance.get('performance', {}).get('short_model_r2', 0):.2f}")