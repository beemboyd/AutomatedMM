"""
Regime Detector Module

Core engine for detecting market regimes based on multiple indicators.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
import json
import os
from enum import Enum

from .market_indicators import MarketIndicators


class MarketRegime(Enum):
    """Market regime types"""
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    NEUTRAL = "neutral"
    BEAR = "bear"
    STRONG_BEAR = "strong_bear"
    VOLATILE = "volatile"
    CRISIS = "crisis"


class RegimeDetector:
    """Main regime detection engine"""
    
    def __init__(self, config_path: str = None):
        """Initialize regime detector"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'config', 'regime_config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.market_indicators = MarketIndicators(config_path)
        self.regime_thresholds = self.config['regime_thresholds']
        self.logger = logging.getLogger(__name__)
        
        # State tracking
        self.current_regime = None
        self.regime_confidence = 0.0
        self.regime_start_time = None
        self.regime_history = []
        
    def detect_regime(self, market_data: pd.DataFrame, 
                     scanner_data: Optional[pd.DataFrame] = None) -> Dict[str, any]:
        """
        Detect current market regime
        
        Args:
            market_data: DataFrame with market OHLCV data
            scanner_data: Optional DataFrame with scanner results
            
        Returns:
            Dict with regime, confidence, indicators, and recommendations
        """
        try:
            # Calculate all indicators (now with scanner data for volatility)
            indicators = self.market_indicators.calculate_all_indicators(market_data, scanner_data)
            
            # Store NIFTY breadth separately for display
            nifty_breadth = {
                'nifty_advance_decline_ratio': indicators.get('advance_decline_ratio', 1.0),
                'nifty_bullish_percent': indicators.get('bullish_percent', 0.5),
                'nifty_bearish_percent': indicators.get('bearish_percent', 0.5),
                'nifty_breadth_score': indicators.get('breadth_score', 0.0)
            }
            
            # Add scanner-based indicators if available
            if scanner_data is not None:
                scanner_indicators = self._analyze_scanner_data(scanner_data)
                
                # Override market breadth with scanner breadth for regime detection
                if 'breadth_score' in scanner_indicators:
                    indicators['breadth_score'] = scanner_indicators['breadth_score']
                if 'advance_decline_ratio' in scanner_indicators:
                    indicators['advance_decline_ratio'] = scanner_indicators['advance_decline_ratio']
                if 'bullish_percent' in scanner_indicators:
                    indicators['bullish_percent'] = scanner_indicators['bullish_percent']
                if 'bearish_percent' in scanner_indicators:
                    indicators['bearish_percent'] = scanner_indicators['bearish_percent']
                
                # Update all scanner-based indicators
                indicators.update(scanner_indicators)
                
                # Recalculate market score with scanner breadth
                indicators['market_score'] = self._recalculate_market_score(indicators)
            
            # Add NIFTY breadth data for display purposes
            indicators.update(nifty_breadth)
            
            # Determine regime
            regime, confidence, reasoning = self._classify_regime(indicators)
            
            # Check for regime change
            regime_changed = self._check_regime_change(regime, confidence)
            
            # Generate analysis
            analysis = {
                'regime': regime.value,
                'confidence': confidence,
                'previous_regime': self.current_regime.value if self.current_regime else None,
                'regime_changed': regime_changed,
                'regime_duration': self._get_regime_duration(),
                'indicators': indicators,
                'reasoning': reasoning,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update state
            self._update_regime_state(regime, confidence)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error detecting regime: {e}")
            return {
                'regime': 'neutral',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _classify_regime(self, indicators: Dict[str, float]) -> Tuple[MarketRegime, float, List[str]]:
        """
        Classify market regime based on indicators
        
        Returns:
            Tuple of (regime, confidence, reasoning)
        """
        regime_scores = {}
        reasoning = []
        
        # Check each regime type
        for regime in MarketRegime:
            score, reasons = self._calculate_regime_score(regime, indicators)
            regime_scores[regime] = score
            
        # Special handling for volatile and crisis regimes
        if self._is_crisis_regime(indicators):
            reasoning.append("Crisis conditions detected")
            return MarketRegime.CRISIS, 0.9, reasoning
        
        if self._is_volatile_regime(indicators):
            reasoning.append("High volatility regime detected")
            return MarketRegime.VOLATILE, 0.8, reasoning
        
        # Find best matching regime
        best_regime = max(regime_scores, key=regime_scores.get)
        confidence = regime_scores[best_regime]
        
        # Get reasoning for best regime
        _, reasons = self._calculate_regime_score(best_regime, indicators)
        reasoning.extend(reasons)
        
        # Adjust confidence based on indicator agreement
        confidence = self._adjust_confidence(confidence, indicators)
        
        return best_regime, confidence, reasoning
    
    def _calculate_regime_score(self, regime: MarketRegime, 
                               indicators: Dict[str, float]) -> Tuple[float, List[str]]:
        """Calculate score for a specific regime"""
        if regime.value not in self.regime_thresholds:
            return 0.0, []
        
        thresholds = self.regime_thresholds[regime.value]
        score = 0.0
        max_score = 0.0
        reasons = []
        
        # Check market score
        if 'market_score' in indicators:
            market_score = indicators['market_score']
            
            if 'min_score' in thresholds:
                if market_score >= thresholds['min_score']:
                    score += 1.0
                    reasons.append(f"Market score {market_score:.2f} >= {thresholds['min_score']}")
                max_score += 1.0
                
            if 'max_score' in thresholds:
                if market_score <= thresholds['max_score']:
                    score += 1.0
                    reasons.append(f"Market score {market_score:.2f} <= {thresholds['max_score']}")
                max_score += 1.0
        
        # Check individual indicators
        if 'indicators' in thresholds:
            for indicator, expected in thresholds['indicators'].items():
                if indicator == 'trend_strength' and 'trend_score' in indicators:
                    if self._check_indicator_threshold(indicators['trend_score'], expected):
                        score += 0.5
                        reasons.append(f"Trend score matches {regime.value} criteria")
                    max_score += 0.5
                    
                elif indicator == 'momentum' and 'momentum_composite' in indicators:
                    if self._check_indicator_threshold(indicators['momentum_composite'], expected):
                        score += 0.5
                        reasons.append(f"Momentum matches {regime.value} criteria")
                    max_score += 0.5
                    
                elif indicator == 'breadth' and 'breadth_score' in indicators:
                    if self._check_indicator_threshold(indicators['breadth_score'], expected):
                        score += 0.3
                        reasons.append(f"Breadth matches {regime.value} criteria")
                    max_score += 0.3
                    
                elif indicator == 'volatility' and 'volatility_regime' in indicators:
                    if indicators['volatility_regime'] == expected:
                        score += 0.4
                        reasons.append(f"Volatility regime is {expected}")
                    max_score += 0.4
        
        # Calculate final score
        final_score = score / max_score if max_score > 0 else 0.0
        
        # Apply minimum confidence threshold
        if 'min_confidence' in thresholds:
            if final_score < thresholds['min_confidence']:
                final_score *= 0.5  # Penalize low confidence matches
                
        return final_score, reasons
    
    def _check_indicator_threshold(self, value: float, threshold: float) -> bool:
        """Check if indicator meets threshold criteria"""
        if isinstance(threshold, (int, float)):
            if threshold >= 0:
                return value >= threshold
            else:
                return value <= threshold
        return False
    
    def _is_crisis_regime(self, indicators: Dict[str, float]) -> bool:
        """Check for crisis conditions"""
        crisis_signals = 0
        
        # Check extreme negative trend
        if indicators.get('trend_score', 0) < -0.7:
            crisis_signals += 1
        
        # Check extreme volatility
        if indicators.get('volatility_regime') in ['extreme', 'very_high']:
            crisis_signals += 1
        
        # Check extreme negative momentum
        if indicators.get('momentum_composite', 0) < -0.7:
            crisis_signals += 1
        
        # Check market score
        if indicators.get('market_score', 0) < -0.8:
            crisis_signals += 1
        
        # Check breadth collapse
        if indicators.get('breadth_score', 0) < 0.2:
            crisis_signals += 1
        
        return crisis_signals >= 3
    
    def _is_volatile_regime(self, indicators: Dict[str, float]) -> bool:
        """Check for volatile regime conditions"""
        vol_signals = 0
        
        # Check volatility indicators
        if indicators.get('volatility_regime') in ['high', 'very_high', 'extreme']:
            vol_signals += 2
        
        # Check volatility score
        if indicators.get('volatility_score', 0) > 0.7:
            vol_signals += 1
        
        # Check for whipsaws (conflicting signals)
        trend = indicators.get('trend_score', 0)
        momentum = indicators.get('momentum_composite', 0)
        if abs(trend - momentum) > 0.5:
            vol_signals += 1
        
        # Check ATR expansion
        if indicators.get('atr_percent', 0) > 3:
            vol_signals += 1
        
        return vol_signals >= 3
    
    def _adjust_confidence(self, base_confidence: float, indicators: Dict[str, float]) -> float:
        """Adjust confidence based on indicator agreement"""
        adjustments = []
        
        # Check trend and momentum alignment
        trend = indicators.get('trend_score', 0)
        momentum = indicators.get('momentum_composite', 0)
        if np.sign(trend) == np.sign(momentum):
            adjustments.append(0.1)
        else:
            adjustments.append(-0.1)
        
        # Check breadth confirmation
        breadth = indicators.get('breadth_score', 0)
        if np.sign(breadth) == np.sign(trend):
            adjustments.append(0.05)
        else:
            adjustments.append(-0.05)
        
        # Volatility penalty
        vol_score = indicators.get('volatility_score', 0)
        if vol_score > 0.7:
            adjustments.append(-0.1)
        elif vol_score < 0.3:
            adjustments.append(0.05)
        
        # Apply adjustments
        adjusted_confidence = base_confidence + sum(adjustments)
        
        return np.clip(adjusted_confidence, 0.1, 0.95)
    
    def _recalculate_market_score(self, indicators: Dict[str, float]) -> float:
        """Recalculate market score using scanner breadth data"""
        all_scores = []
        weights = []
        
        # Trend component
        if 'trend_score' in indicators:
            all_scores.append(indicators['trend_score'])
            weights.append(0.3)
        
        # Momentum component
        if 'momentum_composite' in indicators:
            all_scores.append(indicators['momentum_composite'])
            weights.append(0.3)
        
        # Breadth component (using scanner breadth)
        if 'breadth_score' in indicators:
            all_scores.append(indicators['breadth_score'])
            weights.append(0.2)
        
        # Volatility component (inverse contribution)
        if 'volatility_score' in indicators:
            all_scores.append(0.5 - indicators['volatility_score'])
            weights.append(0.2)
        
        if all_scores:
            return np.average(all_scores, weights=weights[:len(all_scores)])
        
        return 0.0
    
    def _analyze_scanner_data(self, scanner_data: pd.DataFrame) -> Dict[str, float]:
        """Analyze scanner data for additional indicators"""
        indicators = {}
        
        try:
            if len(scanner_data) == 0:
                return indicators
            
            # Calculate breadth indicators using the new method
            breadth_indicators = self.market_indicators.calculate_scanner_breadth(scanner_data)
            indicators.update(breadth_indicators)
            
            # Add composite breadth score for regime detection
            if 'composite_breadth_score' in breadth_indicators:
                indicators['breadth_score'] = breadth_indicators['composite_breadth_score']
            
            # Bullish/Bearish percentage (fallback for compatibility)
            if 'bullish_percent' not in indicators:
                total_stocks = len(scanner_data)
                bullish_patterns = scanner_data[scanner_data['signal'] == 'BUY'].shape[0]
                bearish_patterns = scanner_data[scanner_data['signal'] == 'SELL'].shape[0]
                
                indicators['bullish_percent'] = bullish_patterns / total_stocks if total_stocks > 0 else 0.5
                indicators['bearish_percent'] = bearish_patterns / total_stocks if total_stocks > 0 else 0.5
            
            # Sector distribution
            if 'sector' in scanner_data.columns:
                sector_momentum = self._calculate_sector_momentum(scanner_data)
                indicators.update(sector_momentum)
            
            # Average signal strength
            if 'strength' in scanner_data.columns:
                indicators['avg_signal_strength'] = scanner_data['strength'].mean()
            
            # New highs/lows from scanner
            if 'price_position' in scanner_data.columns:
                new_highs = (scanner_data['price_position'] > 0.9).sum()
                new_lows = (scanner_data['price_position'] < 0.1).sum()
                indicators['scanner_new_highs'] = new_highs
                indicators['scanner_new_lows'] = new_lows
                indicators['scanner_high_low_ratio'] = new_highs / max(new_lows, 1)
            
        except Exception as e:
            self.logger.error(f"Error analyzing scanner data: {e}")
            
        return indicators
    
    def _calculate_sector_momentum(self, scanner_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate sector-wise momentum"""
        sector_indicators = {}
        
        try:
            sector_groups = scanner_data.groupby('sector')
            
            for sector, group in sector_groups:
                bullish = (group['signal'] == 'BUY').sum()
                total = len(group)
                
                sector_indicators[f'sector_{sector.lower()}_bullish'] = bullish / total if total > 0 else 0.5
                
                if 'strength' in group.columns:
                    sector_indicators[f'sector_{sector.lower()}_strength'] = group['strength'].mean()
                    
        except Exception as e:
            self.logger.error(f"Error calculating sector momentum: {e}")
            
        return sector_indicators
    
    def _check_regime_change(self, new_regime: MarketRegime, confidence: float) -> bool:
        """Check if regime has changed"""
        if self.current_regime is None:
            return True
        
        if new_regime != self.current_regime:
            # Require higher confidence for regime change
            if confidence > 0.6:
                return True
                
        return False
    
    def _update_regime_state(self, regime: MarketRegime, confidence: float):
        """Update internal regime state"""
        if self.current_regime != regime:
            # Save to history
            if self.current_regime is not None:
                self.regime_history.append({
                    'regime': self.current_regime.value,
                    'start_time': self.regime_start_time,
                    'end_time': datetime.now(),
                    'duration': self._get_regime_duration()
                })
            
            # Update current state
            self.current_regime = regime
            self.regime_start_time = datetime.now()
            
        self.regime_confidence = confidence
    
    def _get_regime_duration(self) -> Optional[float]:
        """Get current regime duration in hours"""
        if self.regime_start_time is None:
            return None
        
        duration = datetime.now() - self.regime_start_time
        return duration.total_seconds() / 3600
    
    def get_regime_history(self) -> List[Dict]:
        """Get regime history"""
        return self.regime_history
    
    def get_current_regime_info(self) -> Dict[str, any]:
        """Get current regime information"""
        return {
            'regime': self.current_regime.value if self.current_regime else None,
            'confidence': self.regime_confidence,
            'start_time': self.regime_start_time.isoformat() if self.regime_start_time else None,
            'duration_hours': self._get_regime_duration()
        }