#!/usr/bin/env python3
"""
Enhanced Market Regime Detection Model

This module combines traditional technical analysis with machine learning clustering
to provide robust market regime detection for position sizing and risk management.
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
import joblib

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import traditional detector from ML module
try:
    from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType
except ImportError:
    # If ML module not found, use path manipulation
    ml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'ML', 'utils')
    sys.path.append(ml_path)
    from market_regime import MarketRegimeDetector, MarketRegimeType

# Import from current ML-Framework
try:
    from .clustering.cluster_regime_detector import ClusteringRegimeDetector
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from clustering.cluster_regime_detector import ClusteringRegimeDetector

try:
    from ..features.feature_pipeline import FeaturePipeline
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from features.feature_pipeline import FeaturePipeline

logger = logging.getLogger(__name__)

class MarketRegimeML:
    """
    Enhanced market regime detection combining technical analysis and ML clustering.
    """
    
    def __init__(self, config_path=None):
        """
        Initialize the market regime detector.
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.traditional_detector = MarketRegimeDetector(
            lookback_short=self.config['lookback_short'],
            lookback_medium=self.config['lookback_medium'],
            lookback_long=self.config['lookback_long']
        )
        
        self.clustering_detector = ClusteringRegimeDetector(
            n_regimes=self.config['n_regimes'],
            lookback_periods=self.config['feature_lookback_periods']
        )
        
        self.feature_pipeline = FeaturePipeline()
        
        # Model storage
        self.models = {}
        self.regime_history = {}
        
    def _load_config(self, config_path) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            'lookback_short': 20,
            'lookback_medium': 50,
            'lookback_long': 100,
            'n_regimes': 5,
            'feature_lookback_periods': [20, 50, 100, 200],
            'ensemble_weights': {
                'traditional': 0.3,
                'clustering': 0.7
            },
            'min_regime_confidence': 0.6,
            'regime_persistence_threshold': 5,  # days
            'model_update_frequency': 7,  # days
            'position_adjustment_factors': {
                'STRONG_BULLISH': 1.2,
                'WEAK_BULLISH': 1.0,
                'NEUTRAL': 0.8,
                'WEAK_BEARISH': 0.6,
                'STRONG_BEARISH': 0.4,
                'HIGH_VOLATILITY': 0.5,
                'CRISIS': 0.2
            },
            'stop_loss_multipliers': {
                'STRONG_BULLISH': {'long': 2.0, 'short': 1.2},
                'WEAK_BULLISH': {'long': 1.8, 'short': 1.5},
                'NEUTRAL': {'long': 1.5, 'short': 1.5},
                'WEAK_BEARISH': {'long': 1.2, 'short': 1.8},
                'STRONG_BEARISH': {'long': 1.0, 'short': 2.0},
                'HIGH_VOLATILITY': {'long': 2.5, 'short': 2.5},
                'CRISIS': {'long': 3.0, 'short': 3.0}
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def detect_regime(self, ticker: str, data: pd.DataFrame, 
                     use_ensemble: bool = True) -> Tuple[str, Dict]:
        """
        Detect market regime for a given ticker.
        
        Args:
            ticker (str): Ticker symbol
            data (pd.DataFrame): OHLCV data
            use_ensemble (bool): Whether to use ensemble of methods
            
        Returns:
            Tuple[str, Dict]: (regime_name, regime_details)
        """
        # Traditional regime detection
        trad_regime, trad_metrics = self.traditional_detector.detect_consolidated_regime(data.copy())
        
        if not use_ensemble:
            # Map traditional regime to our regime labels
            regime_map = {
                MarketRegimeType.TRENDING_BULLISH.value: 'STRONG_BULLISH',
                MarketRegimeType.TRENDING_BEARISH.value: 'STRONG_BEARISH',
                MarketRegimeType.RANGING_LOW_VOL.value: 'NEUTRAL',
                MarketRegimeType.RANGING_HIGH_VOL.value: 'HIGH_VOLATILITY',
                MarketRegimeType.TRANSITIONING.value: 'NEUTRAL'
            }
            
            current_regime = trad_regime.iloc[-1] if len(trad_regime) > 0 else 'NEUTRAL'
            mapped_regime = regime_map.get(current_regime, 'NEUTRAL')
            
            return mapped_regime, {
                'confidence': 0.8,
                'method': 'traditional',
                'metrics': {k: v.iloc[-1] if hasattr(v, 'iloc') else v 
                          for k, v in trad_metrics.items()}
            }
        
        # ML-based regime detection
        features = self.feature_pipeline.create_features(data)
        
        # Handle NaN values
        features = features.fillna(method='ffill').fillna(0)
        
        if len(features) < 100:
            logger.warning(f"Insufficient data for ML regime detection ({len(features)} rows)")
            return self.detect_regime(ticker, data, use_ensemble=False)
        
        # Ensemble clustering
        ensemble_labels, clustering_results = self.clustering_detector.ensemble_clustering(
            features, 
            methods=['kmeans', 'gmm', 'hierarchical']
        )
        
        # Identify regime characteristics
        regime_chars = self.clustering_detector.identify_regime_characteristics(
            features, 
            ensemble_labels
        )
        
        # Get current regime from clustering
        current_cluster = ensemble_labels[-1]
        cluster_regime = regime_chars.get(current_cluster, {}).get('regime_name', 'NEUTRAL')
        
        # Combine traditional and clustering results
        final_regime = self._combine_regimes(
            trad_regime.iloc[-1] if len(trad_regime) > 0 else 'NEUTRAL',
            cluster_regime,
            trad_metrics,
            regime_chars.get(current_cluster, {})
        )
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            trad_regime,
            ensemble_labels,
            clustering_results
        )
        
        # Store regime history
        self._update_regime_history(ticker, final_regime, confidence)
        
        regime_details = {
            'regime': final_regime,
            'confidence': confidence,
            'traditional_regime': trad_regime.iloc[-1] if len(trad_regime) > 0 else 'NEUTRAL',
            'ml_regime': cluster_regime,
            'metrics': {
                'volatility': trad_metrics['volatility'].iloc[-1] if 'volatility' in trad_metrics else 0,
                'trend_strength': trad_metrics['trend_strength'].iloc[-1] if 'trend_strength' in trad_metrics else 0,
                'hurst': trad_metrics['hurst'].iloc[-1] if 'hurst' in trad_metrics else 0.5,
                'cluster_characteristics': regime_chars.get(current_cluster, {})
            },
            'position_adjustment': self.config['position_adjustment_factors'].get(final_regime, 1.0),
            'stop_loss_multipliers': self.config['stop_loss_multipliers'].get(final_regime, {'long': 1.5, 'short': 1.5})
        }
        
        return final_regime, regime_details
    
    def _combine_regimes(self, trad_regime: str, ml_regime: str, 
                        trad_metrics: Dict, ml_metrics: Dict) -> str:
        """Combine traditional and ML regime detections"""
        
        # Define regime mapping
        regime_priority = {
            'CRISIS': 7,
            'STRONG_BEARISH': 6,
            'HIGH_VOLATILITY': 5,
            'WEAK_BEARISH': 4,
            'NEUTRAL': 3,
            'WEAK_BULLISH': 2,
            'STRONG_BULLISH': 1
        }
        
        # Map traditional regimes
        trad_map = {
            MarketRegimeType.TRENDING_BULLISH.value: 'STRONG_BULLISH',
            MarketRegimeType.TRENDING_BEARISH.value: 'STRONG_BEARISH',
            MarketRegimeType.RANGING_LOW_VOL.value: 'NEUTRAL',
            MarketRegimeType.RANGING_HIGH_VOL.value: 'HIGH_VOLATILITY',
            MarketRegimeType.TRANSITIONING.value: 'NEUTRAL'
        }
        
        mapped_trad = trad_map.get(trad_regime, 'NEUTRAL')
        
        # Check for crisis conditions
        if self._check_crisis_conditions(trad_metrics, ml_metrics):
            return 'CRISIS'
        
        # Weighted combination based on config
        weights = self.config['ensemble_weights']
        
        # If regimes agree, use that regime
        if mapped_trad == ml_regime:
            return mapped_trad
        
        # If they disagree, use the more conservative regime
        trad_priority = regime_priority.get(mapped_trad, 3)
        ml_priority = regime_priority.get(ml_regime, 3)
        
        # Higher priority number means more conservative
        if weights['clustering'] > weights['traditional']:
            return ml_regime if ml_priority >= trad_priority else mapped_trad
        else:
            return mapped_trad if trad_priority >= ml_priority else ml_regime
    
    def _check_crisis_conditions(self, trad_metrics: Dict, ml_metrics: Dict) -> bool:
        """Check if market is in crisis conditions"""
        # Crisis indicators
        crisis_conditions = []
        
        # High volatility
        if 'volatility' in trad_metrics:
            vol = trad_metrics['volatility'].iloc[-1] if hasattr(trad_metrics['volatility'], 'iloc') else trad_metrics['volatility']
            crisis_conditions.append(vol > 0.5)  # 50% annualized volatility
        
        # Strong downtrend
        if 'trend_strength' in trad_metrics:
            trend = trad_metrics['trend_strength'].iloc[-1] if hasattr(trad_metrics['trend_strength'], 'iloc') else trad_metrics['trend_strength']
            crisis_conditions.append(trend < -10)  # Strong negative trend
        
        # Low returns with high volatility
        if 'avg_return' in ml_metrics and 'avg_volatility' in ml_metrics:
            crisis_conditions.append(
                ml_metrics['avg_return'] < -0.2 and ml_metrics['avg_volatility'] > 0.3
            )
        
        # Return true if multiple crisis conditions are met
        return sum(crisis_conditions) >= 2
    
    def _calculate_confidence(self, trad_regime: pd.Series, 
                            ml_labels: np.ndarray,
                            clustering_results: Dict) -> float:
        """Calculate confidence score for regime detection"""
        confidence_scores = []
        
        # Traditional regime stability
        if len(trad_regime) > 20:
            recent_regime = trad_regime.iloc[-20:]
            regime_stability = (recent_regime == recent_regime.iloc[-1]).sum() / len(recent_regime)
            confidence_scores.append(regime_stability)
        
        # ML clustering agreement
        if 'kmeans' in clustering_results and 'gmm' in clustering_results:
            kmeans_labels = clustering_results['kmeans']['labels']
            gmm_labels = clustering_results['gmm']['labels']
            
            # Check agreement in last 20 periods
            agreement = np.mean(kmeans_labels[-20:] == gmm_labels[-20:])
            confidence_scores.append(agreement)
        
        # Clustering quality metrics
        if 'kmeans' in clustering_results:
            silhouette = clustering_results['kmeans']['metrics'].get('silhouette_score', 0)
            # Normalize silhouette score (usually between -1 and 1)
            normalized_silhouette = (silhouette + 1) / 2
            confidence_scores.append(normalized_silhouette)
        
        # Return average confidence
        return np.mean(confidence_scores) if confidence_scores else 0.5
    
    def _update_regime_history(self, ticker: str, regime: str, confidence: float):
        """Update regime history for persistence analysis"""
        if ticker not in self.regime_history:
            self.regime_history[ticker] = []
        
        self.regime_history[ticker].append({
            'date': datetime.now(),
            'regime': regime,
            'confidence': confidence
        })
        
        # Keep only last 252 days (1 year)
        if len(self.regime_history[ticker]) > 252:
            self.regime_history[ticker] = self.regime_history[ticker][-252:]
    
    def get_position_recommendations(self, ticker: str, current_positions: Dict) -> Dict:
        """
        Get position sizing and risk management recommendations based on regime.
        
        Args:
            ticker (str): Ticker symbol
            current_positions (Dict): Current positions information
            
        Returns:
            Dict: Recommendations for position management
        """
        # Load latest data
        data = self._load_ticker_data(ticker)
        if data is None:
            return {'action': 'HOLD', 'reason': 'Insufficient data'}
        
        # Detect regime
        regime, details = self.detect_regime(ticker, data)
        
        recommendations = {
            'ticker': ticker,
            'regime': regime,
            'confidence': details['confidence'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Position sizing recommendations
        position_factor = details['position_adjustment']
        
        if regime in ['CRISIS', 'STRONG_BEARISH']:
            recommendations['action'] = 'REDUCE_EXPOSURE'
            recommendations['position_size_factor'] = position_factor
            recommendations['max_position_pct'] = 2.0  # Max 2% in any single position
            recommendations['reason'] = f"Market in {regime} regime - reduce risk exposure"
            
        elif regime == 'HIGH_VOLATILITY':
            recommendations['action'] = 'ADJUST_STOPS'
            recommendations['position_size_factor'] = position_factor
            recommendations['stop_loss_adjustment'] = details['stop_loss_multipliers']
            recommendations['reason'] = "High volatility - widen stops and reduce position size"
            
        elif regime in ['STRONG_BULLISH', 'WEAK_BULLISH']:
            recommendations['action'] = 'MAINTAIN_OR_INCREASE'
            recommendations['position_size_factor'] = position_factor
            recommendations['max_position_pct'] = 5.0  # Max 5% in favorable conditions
            recommendations['reason'] = f"Market in {regime} regime - favorable for long positions"
            
        else:  # NEUTRAL, WEAK_BEARISH
            recommendations['action'] = 'SELECTIVE_POSITIONING'
            recommendations['position_size_factor'] = position_factor
            recommendations['max_position_pct'] = 3.0
            recommendations['reason'] = f"Market in {regime} regime - be selective with positions"
        
        # Stop loss recommendations
        recommendations['stop_loss_multipliers'] = details['stop_loss_multipliers']
        
        # Add specific recommendations for current positions
        if ticker in current_positions:
            position = current_positions[ticker]
            recommendations['current_position'] = position
            
            # Check if position aligns with regime
            if position['type'] == 'LONG' and regime in ['STRONG_BEARISH', 'CRISIS']:
                recommendations['position_action'] = 'CONSIDER_EXIT'
                recommendations['urgency'] = 'HIGH'
            elif position['type'] == 'SHORT' and regime in ['STRONG_BULLISH']:
                recommendations['position_action'] = 'CONSIDER_EXIT'
                recommendations['urgency'] = 'HIGH'
            else:
                recommendations['position_action'] = 'MONITOR'
                recommendations['urgency'] = 'NORMAL'
        
        return recommendations
    
    def _load_ticker_data(self, ticker: str, lookback_days: int = 365):
        """Load historical data for a ticker"""
        try:
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'BT', 'data', f'{ticker}_day.csv'
            )
            
            if os.path.exists(file_path):
                data = pd.read_csv(file_path)
                data['date'] = pd.to_datetime(data['date'])
                data = data.set_index('date')
                data = data.sort_index()
                
                # Use last lookback_days of data
                if len(data) > lookback_days:
                    data = data.iloc[-lookback_days:]
                
                return data
            else:
                logger.error(f"No data file found for {ticker}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading data for {ticker}: {str(e)}")
            return None
    
    def save_models(self, path: str):
        """Save trained models to disk"""
        model_data = {
            'config': self.config,
            'regime_history': self.regime_history,
            'models': self.models,
            'last_updated': datetime.now().isoformat()
        }
        
        joblib.dump(model_data, path)
        logger.info(f"Models saved to {path}")
    
    def load_models(self, path: str):
        """Load trained models from disk"""
        if os.path.exists(path):
            model_data = joblib.load(path)
            
            self.config.update(model_data.get('config', {}))
            self.regime_history = model_data.get('regime_history', {})
            self.models = model_data.get('models', {})
            
            logger.info(f"Models loaded from {path}")
            return True
        
        return False