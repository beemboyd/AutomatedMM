#!/usr/bin/env python
"""
Regime Detector Module
=====================
Core regime detection engine that combines indicators and signals
to determine current market regime.
"""

import os
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import pickle

from .market_indicators import MarketIndicators
from .regime_signals import RegimeSignals

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Main regime detection engine"""
    
    def __init__(self, base_dir: str = None, config_path: str = None):
        """
        Initialize regime detector
        
        Args:
            base_dir: Base directory for India-TS Daily
            config_path: Path to configuration file
        """
        if base_dir is None:
            base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"
            
        self.base_dir = base_dir
        self.results_dir = os.path.join(base_dir, "results")
        self.reports_dir = os.path.join(base_dir, "reports")
        
        # Initialize components
        self.indicators = MarketIndicators(base_dir)
        self.signals = RegimeSignals(config_path)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize state
        self.current_regime = None
        self.regime_history = []
        self.indicator_history = []
        
        # Load historical data if exists
        self._load_state()
        
    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration"""
        if config_path is None:
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(config_dir, 'config', 'regime_config.json')
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}, using defaults")
            return self._default_config()
            
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'regime_detection': {
                'lookback_days': 20,
                'momentum_threshold': 5.0,
                'volatility_threshold': 30.0,
                'breadth_threshold': 0.6,
                'regime_persistence_days': 3,
                'confidence_threshold': 0.7
            },
            'regime_definitions': {
                'STRONG_BULL': {
                    'momentum_min': 10.0,
                    'breadth_min': 0.7,
                    'volatility_max': 25.0
                },
                'BULL': {
                    'momentum_min': 5.0,
                    'breadth_min': 0.55,
                    'volatility_max': 30.0
                },
                'NEUTRAL': {
                    'momentum_range': [-5.0, 5.0],
                    'breadth_range': [0.45, 0.55],
                    'volatility_max': 35.0
                },
                'BEAR': {
                    'momentum_max': -5.0,
                    'breadth_max': 0.45,
                    'volatility_max': 40.0
                },
                'STRONG_BEAR': {
                    'momentum_max': -10.0,
                    'breadth_max': 0.3,
                    'volatility_max': 50.0
                },
                'VOLATILE': {
                    'volatility_min': 40.0
                }
            }
        }
        
    def detect_current_regime(self) -> Tuple[str, float]:
        """
        Detect current market regime
        
        Returns:
            Tuple of (regime_name, confidence_score)
        """
        # Load recent scan results
        scan_data = self._load_recent_scans()
        
        if scan_data.empty:
            logger.warning("No recent scan data available")
            return "UNKNOWN", 0.0
            
        # Calculate current indicators
        current_indicators = self.indicators.get_all_indicators(scan_data)
        
        # Detect regime based on indicators
        regime, confidence = self._classify_regime(current_indicators)
        
        # Check for regime persistence
        if self._check_regime_persistence(regime):
            confidence = min(1.0, confidence * 1.2)  # Boost confidence for persistent regime
            
        # Update state
        self._update_state(regime, confidence, current_indicators)
        
        return regime, confidence
        
    def _load_recent_scans(self, days: int = 1) -> pd.DataFrame:
        """Load recent scan results"""
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        # Pattern for StrategyB reports
        pattern = os.path.join(self.results_dir, "StrategyB_Report_*.xlsx")
        files = sorted(glob.glob(pattern))
        
        # Get most recent files
        for file in files[-10:]:  # Last 10 files
            try:
                # Extract date from filename
                date_str = os.path.basename(file).replace("StrategyB_Report_", "").replace(".xlsx", "")
                file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                
                if file_date >= cutoff_date:
                    df = pd.read_excel(file)
                    df['scan_time'] = file_date
                    all_data.append(df)
                    
            except Exception as e:
                logger.warning(f"Error loading {file}: {e}")
                continue
                
        if all_data:
            # Combine and return most recent data
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Get the most recent scan
            if len(all_data) > 1:
                latest_time = combined_df['scan_time'].max()
                return combined_df[combined_df['scan_time'] == latest_time]
            else:
                return combined_df
        else:
            return pd.DataFrame()
            
    def _classify_regime(self, indicators: Dict) -> Tuple[str, float]:
        """
        Classify market regime based on indicators
        
        Args:
            indicators: Market indicators dictionary
            
        Returns:
            Tuple of (regime_name, confidence_score)
        """
        regime_scores = {}
        
        # Extract key metrics
        momentum = indicators.get('momentum', {}).get('average_momentum', 0)
        breadth = indicators.get('breadth', {}).get('bullish_percent', 0.5)
        volatility = indicators.get('volatility', {}).get('average_range', 20)
        market_strength = indicators.get('composite', {}).get('market_strength_index', 50)
        
        # Score each regime
        for regime_name, criteria in self.config['regime_definitions'].items():
            score = 0
            matches = 0
            total_criteria = 0
            
            # Check momentum criteria
            if 'momentum_min' in criteria:
                total_criteria += 1
                if momentum >= criteria['momentum_min']:
                    score += 1
                    matches += 1
                    
            if 'momentum_max' in criteria:
                total_criteria += 1
                if momentum <= criteria['momentum_max']:
                    score += 1
                    matches += 1
                    
            if 'momentum_range' in criteria:
                total_criteria += 1
                if criteria['momentum_range'][0] <= momentum <= criteria['momentum_range'][1]:
                    score += 1
                    matches += 1
                    
            # Check breadth criteria
            if 'breadth_min' in criteria:
                total_criteria += 1
                if breadth >= criteria['breadth_min']:
                    score += 1
                    matches += 1
                    
            if 'breadth_max' in criteria:
                total_criteria += 1
                if breadth <= criteria['breadth_max']:
                    score += 1
                    matches += 1
                    
            if 'breadth_range' in criteria:
                total_criteria += 1
                if criteria['breadth_range'][0] <= breadth <= criteria['breadth_range'][1]:
                    score += 1
                    matches += 1
                    
            # Check volatility criteria
            if 'volatility_min' in criteria:
                total_criteria += 1
                if volatility >= criteria['volatility_min']:
                    score += 1
                    matches += 1
                    
            if 'volatility_max' in criteria:
                total_criteria += 1
                if volatility <= criteria['volatility_max']:
                    score += 1
                    matches += 1
                    
            # Calculate regime score
            if total_criteria > 0:
                regime_scores[regime_name] = matches / total_criteria
                
        # Find best matching regime
        if regime_scores:
            best_regime = max(regime_scores.items(), key=lambda x: x[1])
            regime_name = best_regime[0]
            base_confidence = best_regime[1]
            
            # Adjust confidence based on market strength consistency
            if regime_name in ['STRONG_BULL', 'BULL'] and market_strength > 60:
                confidence = min(1.0, base_confidence * 1.1)
            elif regime_name in ['STRONG_BEAR', 'BEAR'] and market_strength < 40:
                confidence = min(1.0, base_confidence * 1.1)
            else:
                confidence = base_confidence
                
            # Check for volatile override
            if volatility > self.config['regime_detection']['volatility_threshold'] * 1.5:
                if confidence < 0.8:  # Only override if not strongly another regime
                    regime_name = 'VOLATILE'
                    confidence = 0.7
                    
            return regime_name, confidence
        else:
            return 'NEUTRAL', 0.5
            
    def _check_regime_persistence(self, regime: str) -> bool:
        """Check if regime has persisted for minimum days"""
        if not self.regime_history:
            return False
            
        persistence_days = self.config['regime_detection']['regime_persistence_days']
        
        if len(self.regime_history) >= persistence_days:
            recent_regimes = [r['regime'] for r in self.regime_history[-persistence_days:]]
            return all(r == regime for r in recent_regimes)
            
        return False
        
    def _update_state(self, regime: str, confidence: float, indicators: Dict):
        """Update detector state"""
        # Update current regime
        self.current_regime = {
            'regime': regime,
            'confidence': confidence,
            'timestamp': datetime.now(),
            'indicators': indicators
        }
        
        # Add to history
        self.regime_history.append({
            'regime': regime,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only recent history
        max_history = 252  # 1 year of trading days
        if len(self.regime_history) > max_history:
            self.regime_history = self.regime_history[-max_history:]
            
        # Add to indicator history
        self.indicator_history.append(indicators)
        if len(self.indicator_history) > 30:  # Keep 30 days
            self.indicator_history = self.indicator_history[-30:]
            
        # Save state
        self._save_state()
        
    def get_regime_recommendations(self) -> Dict:
        """
        Get recommendations based on current regime
        
        Returns:
            Dict with regime-based recommendations
        """
        if not self.current_regime:
            regime, confidence = self.detect_current_regime()
        else:
            regime = self.current_regime['regime']
            confidence = self.current_regime['confidence']
            
        # Get position adjustments from config
        adjustments = self.config.get('position_adjustments', {}).get(regime, {})
        
        recommendations = {
            'regime': regime,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'position_sizing': {
                'size_multiplier': adjustments.get('size_multiplier', 1.0),
                'max_portfolio_exposure': adjustments.get('max_portfolio_exposure', 0.8),
                'stop_loss_multiplier': adjustments.get('stop_loss_multiplier', 1.5)
            },
            'preferred_sectors': adjustments.get('preferred_sectors', []),
            'risk_level': self._get_risk_level(regime),
            'action_items': self._get_action_items(regime, confidence)
        }
        
        # Check for regime changes
        if len(self.indicator_history) > 1:
            change_signals = self.signals.detect_regime_changes(
                self.current_regime['indicators'],
                self.indicator_history[:-1]
            )
            
            if change_signals.get('regime_change_detected'):
                recommendations['regime_change_alert'] = change_signals
                recommendations['alerts'] = self.signals.get_regime_alerts(change_signals)
                
        return recommendations
        
    def _get_risk_level(self, regime: str) -> str:
        """Determine risk level for regime"""
        risk_levels = {
            'STRONG_BULL': 'LOW',
            'BULL': 'MEDIUM_LOW',
            'NEUTRAL': 'MEDIUM',
            'BEAR': 'MEDIUM_HIGH',
            'STRONG_BEAR': 'HIGH',
            'VOLATILE': 'HIGH'
        }
        return risk_levels.get(regime, 'MEDIUM')
        
    def _get_action_items(self, regime: str, confidence: float) -> List[str]:
        """Get specific action items for regime"""
        actions = []
        
        if regime == 'STRONG_BULL':
            actions.append("Consider increasing position sizes on high-probability setups")
            actions.append("Focus on momentum and growth stocks")
            actions.append("Use wider stops to capture trends")
            
        elif regime == 'BULL':
            actions.append("Maintain normal position sizing")
            actions.append("Balance between growth and quality stocks")
            actions.append("Monitor for signs of market exhaustion")
            
        elif regime == 'NEUTRAL':
            actions.append("Reduce position sizes slightly")
            actions.append("Focus on high-quality setups only")
            actions.append("Consider more selective entry criteria")
            
        elif regime == 'BEAR':
            actions.append("Reduce overall market exposure")
            actions.append("Focus on defensive sectors")
            actions.append("Use tighter stops and smaller positions")
            
        elif regime == 'STRONG_BEAR':
            actions.append("Minimize market exposure")
            actions.append("Consider cash as a position")
            actions.append("Only take highest conviction trades")
            
        elif regime == 'VOLATILE':
            actions.append("Reduce position sizes significantly")
            actions.append("Widen stops to account for volatility")
            actions.append("Focus on risk management over returns")
            
        # Add confidence-based actions
        if confidence < 0.6:
            actions.append("Low regime confidence - be extra cautious")
            
        return actions
        
    def _save_state(self):
        """Save detector state to disk"""
        state_file = os.path.join(self.reports_dir, 'regime_detector_state.pkl')
        
        state = {
            'current_regime': self.current_regime,
            'regime_history': self.regime_history,
            'indicator_history': self.indicator_history,
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, 'wb') as f:
                pickle.dump(state, f)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            
    def _load_state(self):
        """Load detector state from disk"""
        state_file = os.path.join(self.reports_dir, 'regime_detector_state.pkl')
        
        try:
            if os.path.exists(state_file):
                with open(state_file, 'rb') as f:
                    state = pickle.load(f)
                    
                self.current_regime = state.get('current_regime')
                self.regime_history = state.get('regime_history', [])
                self.indicator_history = state.get('indicator_history', [])
                
                logger.info(f"Loaded state from {state.get('last_updated')}")
        except Exception as e:
            logger.warning(f"Could not load state: {e}")
            
    def get_historical_analysis(self, days: int = 30) -> pd.DataFrame:
        """Get historical regime analysis"""
        if not self.regime_history:
            return pd.DataFrame()
            
        # Convert to DataFrame
        df = pd.DataFrame(self.regime_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter by days
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df['timestamp'] >= cutoff]
        
        return df