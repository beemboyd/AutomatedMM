#!/usr/bin/env python3
"""
Integration module for Market Regime Detection with Risk Management

This module bridges the ML-based regime detection with the existing
position sizing and risk management systems.
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime
from typing import Dict, Tuple, Optional, List

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ML_Framework.models.market_regime_ml import MarketRegimeML
from risk_management import RiskManager
from state_manager import StateManager

logger = logging.getLogger(__name__)

class RegimeRiskIntegration:
    """
    Integrates market regime detection with position sizing and risk management.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the integration module"""
        self.regime_detector = MarketRegimeML(config_path)
        self.risk_manager = RiskManager()
        self.state_manager = StateManager()
        
        # Load integration config
        self.config = self._load_integration_config(config_path)
        
    def _load_integration_config(self, config_path: Optional[str]) -> Dict:
        """Load integration configuration"""
        default_config = {
            'regime_override_enabled': True,
            'min_confidence_for_override': 0.7,
            'position_size_limits': {
                'absolute_max': 0.10,  # 10% max position
                'regime_adjusted_max': {
                    'CRISIS': 0.02,
                    'STRONG_BEARISH': 0.03,
                    'HIGH_VOLATILITY': 0.03,
                    'WEAK_BEARISH': 0.05,
                    'NEUTRAL': 0.07,
                    'WEAK_BULLISH': 0.08,
                    'STRONG_BULLISH': 0.10
                }
            },
            'stop_loss_regime_adjustments': {
                'use_dynamic_stops': True,
                'min_stop_distance': 0.01,  # 1% minimum
                'max_stop_distance': 0.10   # 10% maximum
            },
            'portfolio_exposure_limits': {
                'CRISIS': 0.20,
                'STRONG_BEARISH': 0.40,
                'HIGH_VOLATILITY': 0.50,
                'WEAK_BEARISH': 0.60,
                'NEUTRAL': 0.80,
                'WEAK_BULLISH': 0.90,
                'STRONG_BULLISH': 1.00
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config.get('integration', {}))
        
        return default_config
    
    def calculate_regime_adjusted_position_size(self, 
                                              ticker: str,
                                              base_position_size: float,
                                              entry_price: float,
                                              account_value: float) -> Dict:
        """
        Calculate position size adjusted for market regime.
        
        Args:
            ticker (str): Stock ticker
            base_position_size (float): Base position size (in rupees)
            entry_price (float): Entry price per share
            account_value (float): Total account value
            
        Returns:
            Dict: Adjusted position sizing details
        """
        try:
            # Get market regime
            data = self._load_ticker_data(ticker)
            if data is None:
                return self._default_position_size(base_position_size, entry_price, account_value)
            
            regime, details = self.regime_detector.detect_regime(ticker, data)
            
            # Check confidence threshold
            if details['confidence'] < self.config['min_confidence_for_override']:
                logger.warning(f"Low confidence ({details['confidence']:.2f}) for {ticker}, using base position size")
                return self._default_position_size(base_position_size, entry_price, account_value)
            
            # Calculate regime-adjusted position size
            position_adjustment = details['position_adjustment']
            regime_max_pct = self.config['position_size_limits']['regime_adjusted_max'].get(
                regime, 0.07
            )
            
            # Apply adjustments
            adjusted_size = base_position_size * position_adjustment
            
            # Apply regime-based maximum
            max_position_value = account_value * regime_max_pct
            adjusted_size = min(adjusted_size, max_position_value)
            
            # Apply absolute maximum
            absolute_max = account_value * self.config['position_size_limits']['absolute_max']
            adjusted_size = min(adjusted_size, absolute_max)
            
            # Calculate shares
            shares = int(adjusted_size / entry_price)
            actual_value = shares * entry_price
            
            return {
                'shares': shares,
                'position_value': actual_value,
                'position_pct': actual_value / account_value,
                'regime': regime,
                'regime_confidence': details['confidence'],
                'adjustment_factor': position_adjustment,
                'max_allowed_pct': regime_max_pct,
                'reasoning': f"Position sized for {regime} regime (conf: {details['confidence']:.2%})"
            }
            
        except Exception as e:
            logger.error(f"Error in regime-adjusted position sizing: {str(e)}")
            return self._default_position_size(base_position_size, entry_price, account_value)
    
    def calculate_regime_adjusted_stop_loss(self,
                                          ticker: str,
                                          entry_price: float,
                                          position_type: str,
                                          atr: float) -> Dict:
        """
        Calculate stop loss adjusted for market regime.
        
        Args:
            ticker (str): Stock ticker
            entry_price (float): Entry price
            position_type (str): 'LONG' or 'SHORT'
            atr (float): Average True Range
            
        Returns:
            Dict: Stop loss details
        """
        try:
            # Get market regime
            data = self._load_ticker_data(ticker)
            if data is None:
                return self._default_stop_loss(entry_price, position_type, atr)
            
            regime, details = self.regime_detector.detect_regime(ticker, data)
            
            # Get stop loss multiplier
            sl_multipliers = details['stop_loss_multipliers']
            multiplier = sl_multipliers.get(position_type.lower(), 1.5)
            
            # Calculate stop distance
            stop_distance = atr * multiplier
            
            # Apply min/max constraints
            min_distance = entry_price * self.config['stop_loss_regime_adjustments']['min_stop_distance']
            max_distance = entry_price * self.config['stop_loss_regime_adjustments']['max_stop_distance']
            
            stop_distance = max(min_distance, min(stop_distance, max_distance))
            
            # Calculate stop price
            if position_type == 'LONG':
                stop_price = entry_price - stop_distance
            else:
                stop_price = entry_price + stop_distance
            
            return {
                'stop_price': round(stop_price, 2),
                'stop_distance': stop_distance,
                'stop_pct': stop_distance / entry_price,
                'atr_multiplier': multiplier,
                'regime': regime,
                'reasoning': f"Stop loss set for {regime} regime using {multiplier:.1f}x ATR"
            }
            
        except Exception as e:
            logger.error(f"Error in regime-adjusted stop loss: {str(e)}")
            return self._default_stop_loss(entry_price, position_type, atr)
    
    def check_portfolio_exposure_limits(self, current_exposure: float) -> Dict:
        """
        Check if current portfolio exposure is within regime-based limits.
        
        Args:
            current_exposure (float): Current portfolio exposure as percentage
            
        Returns:
            Dict: Exposure check results and recommendations
        """
        try:
            # Analyze market indices to get overall regime
            indices = ['SMALLCAP', 'MIDCAP', 'TOP100CASE']
            index_regimes = {}
            
            for index in indices:
                data = self._load_ticker_data(index)
                if data is not None:
                    regime, details = self.regime_detector.detect_regime(index, data)
                    index_regimes[index] = {
                        'regime': regime,
                        'confidence': details['confidence']
                    }
            
            # Determine overall market regime (weighted by confidence)
            market_regime = self._determine_market_regime(index_regimes)
            
            # Get exposure limit for regime
            max_exposure = self.config['portfolio_exposure_limits'].get(
                market_regime, 0.80
            )
            
            # Check if within limits
            within_limits = current_exposure <= max_exposure
            
            recommendations = {
                'within_limits': within_limits,
                'current_exposure': current_exposure,
                'max_allowed_exposure': max_exposure,
                'market_regime': market_regime,
                'action_required': None
            }
            
            if not within_limits:
                excess_exposure = current_exposure - max_exposure
                recommendations['action_required'] = 'REDUCE_EXPOSURE'
                recommendations['excess_exposure'] = excess_exposure
                recommendations['reasoning'] = (
                    f"Portfolio exposure ({current_exposure:.1%}) exceeds "
                    f"limit for {market_regime} regime ({max_exposure:.1%})"
                )
            else:
                available_exposure = max_exposure - current_exposure
                recommendations['available_exposure'] = available_exposure
                recommendations['reasoning'] = (
                    f"Portfolio exposure ({current_exposure:.1%}) is within "
                    f"limit for {market_regime} regime ({max_exposure:.1%})"
                )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error checking portfolio exposure: {str(e)}")
            return {
                'within_limits': True,
                'error': str(e),
                'reasoning': 'Error in regime detection, using default limits'
            }
    
    def get_entry_signals_filter(self, candidates: List[Dict]) -> List[Dict]:
        """
        Filter entry signals based on regime analysis.
        
        Args:
            candidates (List[Dict]): List of potential entry candidates
            
        Returns:
            List[Dict]: Filtered and ranked candidates
        """
        filtered_candidates = []
        
        for candidate in candidates:
            ticker = candidate['ticker']
            
            try:
                # Get regime for this ticker
                data = self._load_ticker_data(ticker)
                if data is None:
                    continue
                
                regime, details = self.regime_detector.detect_regime(ticker, data)
                
                # Add regime information
                candidate['regime'] = regime
                candidate['regime_confidence'] = details['confidence']
                candidate['position_adjustment'] = details['position_adjustment']
                
                # Filter based on regime
                if self._should_enter_position(regime, candidate.get('signal_type', 'LONG')):
                    # Calculate regime score
                    regime_score = self._calculate_regime_score(regime, details)
                    candidate['regime_score'] = regime_score
                    
                    filtered_candidates.append(candidate)
                
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {str(e)}")
                continue
        
        # Sort by regime score (higher is better)
        filtered_candidates.sort(key=lambda x: x.get('regime_score', 0), reverse=True)
        
        return filtered_candidates
    
    def _should_enter_position(self, regime: str, signal_type: str) -> bool:
        """Determine if position should be entered based on regime"""
        if signal_type == 'LONG':
            # Allow long positions in bullish and neutral regimes
            return regime in ['STRONG_BULLISH', 'WEAK_BULLISH', 'NEUTRAL']
        else:  # SHORT
            # Allow short positions in bearish regimes
            return regime in ['STRONG_BEARISH', 'WEAK_BEARISH', 'HIGH_VOLATILITY']
    
    def _calculate_regime_score(self, regime: str, details: Dict) -> float:
        """Calculate score for ranking opportunities"""
        # Base scores by regime
        regime_scores = {
            'STRONG_BULLISH': 1.0,
            'WEAK_BULLISH': 0.7,
            'NEUTRAL': 0.5,
            'WEAK_BEARISH': 0.3,
            'STRONG_BEARISH': 0.2,
            'HIGH_VOLATILITY': 0.4,
            'CRISIS': 0.0
        }
        
        base_score = regime_scores.get(regime, 0.5)
        
        # Adjust by confidence
        confidence_adjusted = base_score * details['confidence']
        
        # Adjust by trend strength
        trend_strength = details['metrics'].get('trend_strength', 0)
        if trend_strength > 0:
            trend_bonus = min(trend_strength / 20, 0.2)  # Max 0.2 bonus
        else:
            trend_bonus = max(trend_strength / 20, -0.2)  # Max 0.2 penalty
        
        final_score = confidence_adjusted + trend_bonus
        
        return max(0, min(1, final_score))  # Clamp between 0 and 1
    
    def _determine_market_regime(self, index_regimes: Dict) -> str:
        """Determine overall market regime from index regimes"""
        if not index_regimes:
            return 'NEUTRAL'
        
        # Weight regimes by confidence
        regime_weights = {}
        total_confidence = 0
        
        for index, data in index_regimes.items():
            regime = data['regime']
            confidence = data['confidence']
            
            regime_weights[regime] = regime_weights.get(regime, 0) + confidence
            total_confidence += confidence
        
        if total_confidence == 0:
            return 'NEUTRAL'
        
        # Find dominant regime
        dominant_regime = max(regime_weights.items(), key=lambda x: x[1])[0]
        
        # Check if it's a crisis (multiple bearish signals)
        bearish_weight = (
            regime_weights.get('STRONG_BEARISH', 0) + 
            regime_weights.get('WEAK_BEARISH', 0) +
            regime_weights.get('HIGH_VOLATILITY', 0)
        )
        
        if bearish_weight / total_confidence > 0.7:
            return 'CRISIS'
        
        return dominant_regime
    
    def _load_ticker_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """Load ticker data for analysis"""
        try:
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'BT', 'data', f'{ticker}_day.csv'
            )
            
            if os.path.exists(file_path):
                data = pd.read_csv(file_path)
                data['date'] = pd.to_datetime(data['date'])
                data = data.set_index('date')
                return data
                
        except Exception as e:
            logger.error(f"Error loading data for {ticker}: {str(e)}")
        
        return None
    
    def _default_position_size(self, base_size: float, entry_price: float, 
                             account_value: float) -> Dict:
        """Default position sizing when regime detection fails"""
        shares = int(base_size / entry_price)
        actual_value = shares * entry_price
        
        return {
            'shares': shares,
            'position_value': actual_value,
            'position_pct': actual_value / account_value,
            'regime': 'UNKNOWN',
            'regime_confidence': 0,
            'adjustment_factor': 1.0,
            'reasoning': 'Using default position sizing'
        }
    
    def _default_stop_loss(self, entry_price: float, position_type: str, 
                          atr: float) -> Dict:
        """Default stop loss when regime detection fails"""
        multiplier = 1.5
        stop_distance = atr * multiplier
        
        if position_type == 'LONG':
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance
        
        return {
            'stop_price': round(stop_price, 2),
            'stop_distance': stop_distance,
            'stop_pct': stop_distance / entry_price,
            'atr_multiplier': multiplier,
            'regime': 'UNKNOWN',
            'reasoning': 'Using default stop loss (1.5x ATR)'
        }