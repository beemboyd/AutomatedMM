#!/usr/bin/env python
"""
Regime Signals Module
====================
Detects regime change signals and transition patterns.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class RegimeSignals:
    """Detect regime change signals and transitions"""
    
    def __init__(self, config_path: str = None):
        """Initialize regime signals detector"""
        self.config = self._load_config(config_path)
        self.signal_history = []
        
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
                'momentum_threshold': 5.0,
                'volatility_threshold': 30.0,
                'breadth_threshold': 0.6,
                'confidence_threshold': 0.7
            }
        }
        
    def detect_regime_changes(self, 
                            current_indicators: Dict,
                            historical_indicators: List[Dict]) -> Dict:
        """
        Detect regime change signals
        
        Args:
            current_indicators: Current market indicators
            historical_indicators: List of historical indicators
            
        Returns:
            Dict with regime change signals
        """
        signals = {
            'regime_change_detected': False,
            'signals': [],
            'transition_type': None,
            'confidence': 0.0
        }
        
        if not historical_indicators:
            return signals
            
        # Analyze momentum shifts
        momentum_signal = self._analyze_momentum_shift(
            current_indicators.get('momentum', {}),
            historical_indicators
        )
        if momentum_signal:
            signals['signals'].append(momentum_signal)
            
        # Analyze breadth deterioration/improvement
        breadth_signal = self._analyze_breadth_change(
            current_indicators.get('breadth', {}),
            historical_indicators
        )
        if breadth_signal:
            signals['signals'].append(breadth_signal)
            
        # Analyze volatility regime changes
        volatility_signal = self._analyze_volatility_change(
            current_indicators.get('volatility', {}),
            historical_indicators
        )
        if volatility_signal:
            signals['signals'].append(volatility_signal)
            
        # Analyze sector rotation
        sector_signal = self._analyze_sector_rotation(
            current_indicators.get('sectors', {}),
            historical_indicators
        )
        if sector_signal:
            signals['signals'].append(sector_signal)
            
        # Analyze pattern shifts
        pattern_signal = self._analyze_pattern_shift(
            current_indicators.get('patterns', {}),
            historical_indicators
        )
        if pattern_signal:
            signals['signals'].append(pattern_signal)
            
        # Determine if regime change occurred
        if len(signals['signals']) >= 2:
            signals['regime_change_detected'] = True
            signals['transition_type'] = self._determine_transition_type(signals['signals'])
            signals['confidence'] = self._calculate_signal_confidence(signals['signals'])
            
        return signals
        
    def _analyze_momentum_shift(self, 
                              current_momentum: Dict,
                              historical: List[Dict]) -> Optional[Dict]:
        """Analyze momentum regime shifts"""
        if not current_momentum or not historical:
            return None
            
        # Get historical momentum
        hist_momentum = [h.get('momentum', {}).get('average_momentum', 0) 
                        for h in historical[-10:] if 'momentum' in h]
        
        if not hist_momentum:
            return None
            
        current_avg = current_momentum.get('average_momentum', 0)
        hist_avg = np.mean(hist_momentum)
        hist_std = np.std(hist_momentum)
        
        # Check for significant shifts
        if abs(current_avg - hist_avg) > 2 * hist_std:
            direction = 'bullish' if current_avg > hist_avg else 'bearish'
            
            return {
                'type': 'momentum_shift',
                'direction': direction,
                'current': current_avg,
                'historical_avg': hist_avg,
                'significance': abs(current_avg - hist_avg) / (hist_std + 1),
                'description': f"Significant momentum shift to {direction} territory"
            }
            
        # Check for momentum divergence
        if len(hist_momentum) >= 5:
            recent_trend = np.polyfit(range(5), hist_momentum[-5:], 1)[0]
            
            if recent_trend > 0 and current_avg < hist_momentum[-1] - hist_std:
                return {
                    'type': 'momentum_divergence',
                    'direction': 'bearish',
                    'description': "Bearish momentum divergence detected"
                }
            elif recent_trend < 0 and current_avg > hist_momentum[-1] + hist_std:
                return {
                    'type': 'momentum_divergence', 
                    'direction': 'bullish',
                    'description': "Bullish momentum divergence detected"
                }
                
        return None
        
    def _analyze_breadth_change(self,
                              current_breadth: Dict,
                              historical: List[Dict]) -> Optional[Dict]:
        """Analyze market breadth changes"""
        if not current_breadth or not historical:
            return None
            
        # Get historical breadth
        hist_bullish = [h.get('breadth', {}).get('bullish_percent', 0.5) 
                       for h in historical[-10:] if 'breadth' in h]
        
        if not hist_bullish:
            return None
            
        current_bullish = current_breadth.get('bullish_percent', 0.5)
        hist_avg = np.mean(hist_bullish)
        
        # Check for breadth thrust
        if current_bullish > 0.7 and hist_avg < 0.5:
            return {
                'type': 'breadth_thrust',
                'direction': 'bullish',
                'current': current_bullish,
                'historical_avg': hist_avg,
                'description': "Bullish breadth thrust - strong buying pressure"
            }
            
        # Check for breadth deterioration
        if current_bullish < 0.3 and hist_avg > 0.5:
            return {
                'type': 'breadth_deterioration',
                'direction': 'bearish',
                'current': current_bullish,
                'historical_avg': hist_avg,
                'description': "Breadth deterioration - widespread selling"
            }
            
        # Check for narrowing breadth
        if current_bullish > 0.5 and current_breadth.get('high_score_percent', 0) < 0.1:
            return {
                'type': 'narrow_breadth',
                'direction': 'warning',
                'description': "Market advance on narrow breadth - potential weakness"
            }
            
        return None
        
    def _analyze_volatility_change(self,
                                 current_volatility: Dict,
                                 historical: List[Dict]) -> Optional[Dict]:
        """Analyze volatility regime changes"""
        if not current_volatility or not historical:
            return None
            
        # Get historical volatility
        hist_vol = [h.get('volatility', {}).get('average_range', 0) 
                   for h in historical[-10:] if 'volatility' in h]
        
        if not hist_vol:
            return None
            
        current_vol = current_volatility.get('average_range', 0)
        hist_avg = np.mean(hist_vol)
        threshold = self.config['regime_detection']['volatility_threshold']
        
        # Check for volatility expansion
        if current_vol > hist_avg * 1.5 and current_vol > threshold:
            return {
                'type': 'volatility_expansion',
                'direction': 'risk',
                'current': current_vol,
                'historical_avg': hist_avg,
                'description': "Volatility expansion - increased market risk"
            }
            
        # Check for volatility compression
        if current_vol < hist_avg * 0.7 and hist_avg > threshold:
            return {
                'type': 'volatility_compression',
                'direction': 'calm',
                'current': current_vol,
                'historical_avg': hist_avg,
                'description': "Volatility compression - market calming"
            }
            
        return None
        
    def _analyze_sector_rotation(self,
                               current_sectors: Dict,
                               historical: List[Dict]) -> Optional[Dict]:
        """Analyze sector rotation patterns"""
        if not current_sectors or not historical:
            return None
            
        # Get current top sectors
        current_top = current_sectors.get('top_sectors', {})
        if not current_top:
            return None
            
        # Compare with historical top sectors
        historical_tops = []
        for h in historical[-5:]:
            if 'sectors' in h and 'top_sectors' in h['sectors']:
                historical_tops.extend(list(h['sectors']['top_sectors'].keys()))
                
        if not historical_tops:
            return None
            
        # Check for defensive rotation
        defensive_sectors = ['Consumer Staples', 'Utilities', 'Healthcare']
        current_defensive = sum(1 for s in list(current_top.keys())[:3] 
                              if s in defensive_sectors)
        
        if current_defensive >= 2:
            return {
                'type': 'defensive_rotation',
                'direction': 'bearish',
                'top_sectors': list(current_top.keys())[:3],
                'description': "Rotation to defensive sectors - risk-off sentiment"
            }
            
        # Check for growth rotation
        growth_sectors = ['Technology', 'Consumer Discretionary', 'Communication']
        current_growth = sum(1 for s in list(current_top.keys())[:3] 
                           if s in growth_sectors)
        
        if current_growth >= 2:
            return {
                'type': 'growth_rotation',
                'direction': 'bullish',
                'top_sectors': list(current_top.keys())[:3],
                'description': "Rotation to growth sectors - risk-on sentiment"
            }
            
        return None
        
    def _analyze_pattern_shift(self,
                             current_patterns: Dict,
                             historical: List[Dict]) -> Optional[Dict]:
        """Analyze pattern distribution shifts"""
        if not current_patterns or not historical:
            return None
            
        # Get pattern bias history
        hist_bias = [h.get('patterns', {}).get('pattern_bias', 0) 
                    for h in historical[-10:] if 'patterns' in h]
        
        if not hist_bias:
            return None
            
        current_bias = current_patterns.get('pattern_bias', 0)
        hist_avg = np.mean(hist_bias)
        
        # Check for pattern regime shift
        if current_bias > 0.2 and hist_avg < 0:
            return {
                'type': 'pattern_shift',
                'direction': 'bullish',
                'current_bias': current_bias,
                'historical_avg': hist_avg,
                'description': "Shift to bullish pattern dominance"
            }
        elif current_bias < -0.2 and hist_avg > 0:
            return {
                'type': 'pattern_shift',
                'direction': 'bearish',
                'current_bias': current_bias,
                'historical_avg': hist_avg,
                'description': "Shift to bearish pattern dominance"
            }
            
        return None
        
    def _determine_transition_type(self, signals: List[Dict]) -> str:
        """Determine the type of regime transition"""
        bullish_signals = sum(1 for s in signals if s.get('direction') == 'bullish')
        bearish_signals = sum(1 for s in signals if s.get('direction') == 'bearish')
        risk_signals = sum(1 for s in signals if s.get('direction') in ['risk', 'warning'])
        
        if bullish_signals >= 2:
            return 'BULLISH_TRANSITION'
        elif bearish_signals >= 2:
            return 'BEARISH_TRANSITION'
        elif risk_signals >= 2:
            return 'RISK_INCREASE'
        else:
            return 'MIXED_SIGNALS'
            
    def _calculate_signal_confidence(self, signals: List[Dict]) -> float:
        """Calculate confidence score for regime change signals"""
        if not signals:
            return 0.0
            
        # Base confidence on number and strength of signals
        base_confidence = min(len(signals) * 0.2, 0.8)
        
        # Adjust for signal agreement
        directions = [s.get('direction') for s in signals if 'direction' in s]
        if directions:
            direction_agreement = max(directions.count(d) for d in set(directions)) / len(directions)
            base_confidence *= (0.5 + 0.5 * direction_agreement)
            
        # Adjust for signal significance
        significances = [s.get('significance', 1.0) for s in signals if 'significance' in s]
        if significances:
            avg_significance = np.mean(significances)
            base_confidence *= min(1.0, 0.5 + 0.5 * avg_significance / 3.0)
            
        return min(1.0, base_confidence)
        
    def get_regime_alerts(self, regime_change_signals: Dict) -> List[Dict]:
        """Generate alerts for significant regime changes"""
        alerts = []
        
        if not regime_change_signals.get('regime_change_detected'):
            return alerts
            
        # High confidence regime change
        if regime_change_signals.get('confidence', 0) > 0.7:
            alerts.append({
                'level': 'HIGH',
                'type': 'REGIME_CHANGE',
                'message': f"High confidence {regime_change_signals['transition_type']} detected",
                'signals': regime_change_signals['signals'],
                'timestamp': datetime.now().isoformat()
            })
            
        # Specific signal alerts
        for signal in regime_change_signals.get('signals', []):
            if signal.get('type') == 'breadth_thrust':
                alerts.append({
                    'level': 'MEDIUM',
                    'type': 'BREADTH_THRUST',
                    'message': "Bullish breadth thrust detected - consider increasing exposure",
                    'timestamp': datetime.now().isoformat()
                })
            elif signal.get('type') == 'breadth_deterioration':
                alerts.append({
                    'level': 'HIGH',
                    'type': 'BREADTH_DETERIORATION',
                    'message': "Market breadth deteriorating - consider reducing exposure",
                    'timestamp': datetime.now().isoformat()
                })
            elif signal.get('type') == 'volatility_expansion':
                alerts.append({
                    'level': 'MEDIUM',
                    'type': 'VOLATILITY_SPIKE',
                    'message': "Volatility expanding - tighten risk controls",
                    'timestamp': datetime.now().isoformat()
                })
                
        return alerts