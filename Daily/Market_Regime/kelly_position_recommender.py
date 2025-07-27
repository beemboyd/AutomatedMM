#!/usr/bin/env python3
"""
Kelly Criterion Position Recommender
Uses Kelly formula to calculate optimal position sizes based on market score and confidence
"""

from typing import Dict, Optional, List
import logging
import math

logger = logging.getLogger(__name__)

class KellyPositionRecommender:
    """
    Position sizing using Kelly Criterion:
    f* = (p*b - q) / b
    where:
    - f* = fraction of capital to wager
    - p = probability of winning (derived from market score + confidence)
    - q = probability of losing (1 - p)
    - b = odds (expected win/loss ratio)
    """
    
    def __init__(self):
        # Kelly parameters by regime
        self.regime_parameters = {
            'strong_uptrend': {
                'base_win_rate': 0.65,
                'win_loss_ratio': 1.8,
                'max_kelly_fraction': 0.25,  # Max 25% per position
                'confidence_weight': 0.3
            },
            'uptrend': {
                'base_win_rate': 0.60,
                'win_loss_ratio': 1.5,
                'max_kelly_fraction': 0.20,
                'confidence_weight': 0.35
            },
            'choppy_bullish': {
                'base_win_rate': 0.55,
                'win_loss_ratio': 1.3,
                'max_kelly_fraction': 0.15,
                'confidence_weight': 0.40
            },
            'choppy': {
                'base_win_rate': 0.50,
                'win_loss_ratio': 1.0,
                'max_kelly_fraction': 0.10,
                'confidence_weight': 0.45
            },
            'choppy_bearish': {
                'base_win_rate': 0.55,
                'win_loss_ratio': 1.3,
                'max_kelly_fraction': 0.15,
                'confidence_weight': 0.40
            },
            'downtrend': {
                'base_win_rate': 0.60,
                'win_loss_ratio': 1.5,
                'max_kelly_fraction': 0.20,
                'confidence_weight': 0.35
            },
            'strong_downtrend': {
                'base_win_rate': 0.65,
                'win_loss_ratio': 1.8,
                'max_kelly_fraction': 0.25,
                'confidence_weight': 0.3
            }
        }
        
        # Risk management parameters
        self.max_total_exposure = 1.0  # Maximum 100% exposure
        self.min_position_size = 0.01  # Minimum 1% position
        self.kelly_safety_factor = 0.25  # Use 25% of full Kelly for safety
        
    def calculate_kelly_fraction(self, win_probability: float, win_loss_ratio: float) -> float:
        """
        Calculate raw Kelly fraction
        """
        if win_loss_ratio <= 0:
            return 0.0
            
        p = win_probability
        q = 1 - p
        b = win_loss_ratio
        
        # Kelly formula: f* = (p*b - q) / b
        kelly = (p * b - q) / b
        
        # Return 0 if negative (don't bet)
        return max(0, kelly)
    
    def adjust_for_market_score(self, base_probability: float, market_score: float, 
                               confidence: float, confidence_weight: float) -> float:
        """
        Adjust win probability based on market score and confidence
        
        Market score range: -1 to 1
        Confidence range: 0 to 1
        """
        # Convert market score to probability adjustment (-0.1 to +0.1)
        market_adjustment = market_score * 0.1
        
        # Weight confidence impact
        confidence_adjustment = (confidence - 0.5) * confidence_weight
        
        # Adjusted probability
        adjusted_prob = base_probability + market_adjustment + confidence_adjustment
        
        # Ensure within valid range
        return max(0.1, min(0.9, adjusted_prob))
    
    def get_recommendations(self, regime: str, confidence: float, 
                          volatility: Optional[Dict] = None,
                          market_score: float = 0.0,
                          breadth_score: float = 0.5) -> Dict:
        """
        Generate Kelly-based position recommendations
        
        Args:
            regime: Current market regime
            confidence: Confidence score (0-1)
            volatility: Volatility metrics
            market_score: Enhanced market score (-1 to 1)
            breadth_score: Market breadth score (0-1)
        """
        try:
            # Get regime parameters
            params = self.regime_parameters.get(regime, self.regime_parameters['choppy'])
            
            # Adjust win probability based on market conditions
            win_probability = self.adjust_for_market_score(
                params['base_win_rate'],
                market_score,
                confidence,
                params['confidence_weight']
            )
            
            # Adjust win/loss ratio based on volatility
            vol_score = volatility.get('volatility_score', 0.5) if volatility else 0.5
            volatility_factor = 1.5 - vol_score  # Higher volatility = lower ratio
            adjusted_ratio = params['win_loss_ratio'] * volatility_factor
            
            # Calculate raw Kelly fraction
            raw_kelly = self.calculate_kelly_fraction(win_probability, adjusted_ratio)
            
            # Apply safety factor
            safe_kelly = raw_kelly * self.kelly_safety_factor
            
            # Apply maximum limit
            final_kelly = min(safe_kelly, params['max_kelly_fraction'])
            
            # Adjust for breadth divergence
            if breadth_score < 0.3:  # Poor breadth
                final_kelly *= 0.5
            elif breadth_score > 0.7:  # Strong breadth
                final_kelly *= 1.2
            
            # Ensure minimum position size if Kelly > 0
            if final_kelly > 0 and final_kelly < self.min_position_size:
                final_kelly = self.min_position_size
            
            # Calculate number of positions based on Kelly fraction
            if final_kelly > 0:
                max_positions = int(self.max_total_exposure / final_kelly)
                max_positions = max(1, min(20, max_positions))  # Between 1 and 20
            else:
                max_positions = 0
            
            # Calculate stop loss based on volatility
            base_stop = 0.02  # 2% base stop loss
            vol_stop_multiplier = 1 + (vol_score * 2)  # 1x to 3x
            stop_loss = base_stop * vol_stop_multiplier
            
            # Determine preferred direction
            preferred_direction = self._get_preferred_direction(regime)
            
            # Build recommendations
            recommendations = {
                # Core Kelly metrics
                'kelly_fraction': float(round(final_kelly, 4)),
                'position_size_percent': float(round(final_kelly * 100, 2)),
                'win_probability': float(round(win_probability, 3)),
                'win_loss_ratio': float(round(adjusted_ratio, 2)),
                'expected_value': float(round((win_probability * adjusted_ratio - (1 - win_probability)), 3)),
                
                # Position sizing
                'position_size_multiplier': float(round(final_kelly / 0.05, 2)),  # Relative to 5% base
                'max_positions': int(max_positions),
                'total_exposure_limit': float(round(min(self.max_total_exposure, max_positions * final_kelly), 2)),
                
                # Risk management
                'stop_loss_percent': float(round(stop_loss * 100, 2)),
                'stop_loss_multiplier': float(round(vol_stop_multiplier, 2)),
                'risk_per_trade': float(round(final_kelly * stop_loss, 4)),
                
                # Directional bias
                'preferred_direction': preferred_direction,
                'confidence_level': self._get_confidence_level(confidence),
                'volatility_regime': self._get_volatility_regime(vol_score),
                
                # Kelly components (for transparency)
                'kelly_components': {
                    'raw_kelly': float(round(raw_kelly, 4)),
                    'safety_factor': float(self.kelly_safety_factor),
                    'regime_limit': float(params['max_kelly_fraction']),
                    'breadth_adjustment': float(round(final_kelly / safe_kelly if safe_kelly > 0 else 1.0, 2))
                },
                
                # Guidance
                'specific_guidance': self._generate_kelly_guidance(
                    regime, final_kelly, win_probability, adjusted_ratio, confidence
                )
            }
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error calculating Kelly recommendations: {e}")
            return self._get_default_recommendations()
    
    def _get_preferred_direction(self, regime: str) -> str:
        """Get preferred trading direction based on regime"""
        long_regimes = ['strong_uptrend', 'uptrend', 'choppy_bullish']
        short_regimes = ['strong_downtrend', 'downtrend', 'choppy_bearish']
        
        if regime in long_regimes:
            return 'long'
        elif regime in short_regimes:
            return 'short'
        else:
            return 'both'
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Categorize confidence level"""
        if confidence >= 0.8:
            return 'very_high'
        elif confidence >= 0.6:
            return 'high'
        elif confidence >= 0.4:
            return 'moderate'
        elif confidence >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _get_volatility_regime(self, vol_score: float) -> str:
        """Categorize volatility regime"""
        if vol_score < 0.3:
            return 'low'
        elif vol_score < 0.6:
            return 'normal'
        elif vol_score < 0.8:
            return 'high'
        else:
            return 'extreme'
    
    def _generate_kelly_guidance(self, regime: str, kelly_fraction: float,
                                win_prob: float, win_loss_ratio: float,
                                confidence: float) -> List[str]:
        """Generate specific guidance based on Kelly calculations"""
        guidance = []
        
        # Kelly fraction interpretation
        if kelly_fraction >= 0.20:
            guidance.append("⚡ Strong Kelly signal - Market conditions highly favorable")
        elif kelly_fraction >= 0.10:
            guidance.append("✅ Positive Kelly signal - Good risk/reward setup")
        elif kelly_fraction >= 0.05:
            guidance.append("⚠️ Modest Kelly signal - Proceed with caution")
        elif kelly_fraction > 0:
            guidance.append("🔸 Minimal Kelly signal - Consider waiting for better setup")
        else:
            guidance.append("🛑 Negative Kelly - Avoid trading in current conditions")
        
        # Win probability guidance
        if win_prob >= 0.65:
            guidance.append(f"📊 High win probability ({win_prob:.1%}) supports aggressive sizing")
        elif win_prob >= 0.55:
            guidance.append(f"📊 Moderate win probability ({win_prob:.1%}) - Standard position sizing")
        else:
            guidance.append(f"📊 Low win probability ({win_prob:.1%}) - Reduce position size")
        
        # Risk/reward guidance
        if win_loss_ratio >= 1.5:
            guidance.append(f"💰 Favorable risk/reward ratio ({win_loss_ratio:.1f}:1)")
        elif win_loss_ratio >= 1.0:
            guidance.append(f"💰 Neutral risk/reward ratio ({win_loss_ratio:.1f}:1)")
        else:
            guidance.append(f"💰 Poor risk/reward ratio ({win_loss_ratio:.1f}:1) - Avoid")
        
        # Confidence-based guidance
        if confidence < 0.4:
            guidance.append("🟡 Low regime confidence - Consider reducing exposure")
        
        # Expected value
        ev = win_prob * win_loss_ratio - (1 - win_prob)
        if ev > 0:
            guidance.append(f"📈 Positive expected value: {ev:.1%} per trade")
        else:
            guidance.append(f"📉 Negative expected value: {ev:.1%} per trade")
        
        return guidance
    
    def _get_default_recommendations(self) -> Dict:
        """Return conservative default recommendations"""
        return {
            'kelly_fraction': 0.0,
            'position_size_percent': 0.0,
            'win_probability': 0.5,
            'win_loss_ratio': 1.0,
            'expected_value': 0.0,
            'position_size_multiplier': 0.0,
            'max_positions': 0,
            'total_exposure_limit': 0.0,
            'stop_loss_percent': 2.0,
            'stop_loss_multiplier': 1.0,
            'risk_per_trade': 0.0,
            'preferred_direction': 'none',
            'confidence_level': 'very_low',
            'volatility_regime': 'normal',
            'kelly_components': {
                'raw_kelly': 0.0,
                'safety_factor': self.kelly_safety_factor,
                'regime_limit': 0.0,
                'breadth_adjustment': 1.0
            },
            'specific_guidance': [
                "🛑 No trading recommended - Waiting for better market conditions",
                "📊 Kelly Criterion suggests zero allocation",
                "⏸️ Preserve capital until positive expected value emerges"
            ]
        }