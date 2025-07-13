#!/usr/bin/env python3
"""
Position Recommender for Market Regime
Provides position sizing and risk management recommendations
"""

import numpy as np
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class PositionRecommender:
    """Generate position sizing and risk management recommendations"""
    
    def __init__(self):
        # Base position multipliers by regime
        self.regime_multipliers = {
            'strong_uptrend': 1.5,    # Aggressive long positions
            'uptrend': 1.2,           # Moderate long positions
            'choppy_bullish': 1.0,    # Normal positions, long bias
            'choppy': 0.8,            # Reduced positions, both directions
            'choppy_bearish': 1.0,    # Normal positions, short bias
            'downtrend': 1.2,         # Moderate short positions
            'strong_downtrend': 1.5   # Aggressive short positions
        }
        
        # Risk multipliers by volatility
        self.volatility_ranges = {
            'low': (0, 0.3),
            'normal': (0.3, 0.6),
            'high': (0.6, 0.8),
            'extreme': (0.8, 1.0)
        }
        
        # Maximum position limits by regime
        self.max_positions = {
            'strong_uptrend': 10,
            'uptrend': 8,
            'choppy_bullish': 6,
            'choppy': 5,
            'choppy_bearish': 6,
            'downtrend': 8,
            'strong_downtrend': 10
        }
    
    def get_recommendations(self, regime: str, confidence: float, 
                          volatility: Optional[Dict] = None) -> Dict:
        """
        Generate comprehensive position recommendations
        
        Args:
            regime: Current market regime
            confidence: Confidence score (0-1)
            volatility: Optional volatility metrics
            
        Returns:
            Dictionary with position sizing and risk recommendations
        """
        try:
            # Get base multiplier for regime
            base_multiplier = self.regime_multipliers.get(regime, 1.0)
            
            # Adjust for confidence (0.5 to 1.0 range)
            confidence_factor = 0.5 + (confidence * 0.5)
            
            # Adjust for volatility
            vol_score = volatility.get('volatility_score', 0.5) if volatility else 0.5
            volatility_adjustment = self._calculate_volatility_adjustment(vol_score)
            
            # Calculate final position size multiplier
            position_multiplier = base_multiplier * confidence_factor * volatility_adjustment
            position_multiplier = round(max(0.5, min(2.0, position_multiplier)), 2)
            
            # Calculate stop loss multiplier
            stop_loss_multiplier = self._calculate_stop_loss_multiplier(vol_score)
            
            # Get maximum positions
            max_positions = self._calculate_max_positions(regime, volatility)
            
            # Determine preferred direction
            preferred_direction = self._get_preferred_direction(regime)
            
            # Calculate risk per trade
            risk_per_trade = self._calculate_risk_per_trade(confidence, vol_score)
            
            # Generate specific recommendations
            recommendations = {
                'position_size_multiplier': position_multiplier,
                'stop_loss_multiplier': stop_loss_multiplier,
                'max_positions': max_positions,
                'preferred_direction': preferred_direction,
                'risk_per_trade': risk_per_trade,
                'confidence_level': self._get_confidence_level(confidence),
                'volatility_regime': self._get_volatility_regime(vol_score),
                'specific_guidance': self._generate_specific_guidance(
                    regime, confidence, vol_score
                )
            }
            
            # Add regime-specific recommendations
            regime_specific = self._get_regime_specific_recommendations(regime, confidence)
            recommendations.update(regime_specific)
            
            logger.info(f"Generated recommendations for {regime} regime: "
                       f"size_mult={position_multiplier}, sl_mult={stop_loss_multiplier}")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return self._get_default_recommendations()
    
    def _calculate_volatility_adjustment(self, vol_score: float) -> float:
        """Calculate position size adjustment based on volatility"""
        # Lower positions in high volatility
        if vol_score >= 0.8:  # Extreme volatility
            return 0.6
        elif vol_score >= 0.6:  # High volatility
            return 0.8
        elif vol_score >= 0.3:  # Normal volatility
            return 1.0
        else:  # Low volatility
            return 1.2
    
    def _calculate_stop_loss_multiplier(self, vol_score: float) -> float:
        """Calculate stop loss multiplier based on volatility"""
        # Wider stops in high volatility
        if vol_score >= 0.8:  # Extreme volatility
            return 2.0
        elif vol_score >= 0.6:  # High volatility
            return 1.5
        elif vol_score >= 0.3:  # Normal volatility
            return 1.0
        else:  # Low volatility
            return 0.8
    
    def _calculate_max_positions(self, regime: str, volatility: Optional[Dict]) -> int:
        """Calculate maximum number of positions"""
        base_max = self.max_positions.get(regime, 6)
        
        if volatility:
            vol_score = volatility.get('volatility_score', 0.5)
            if vol_score >= 0.8:  # Extreme volatility
                base_max = int(base_max * 0.6)
            elif vol_score >= 0.6:  # High volatility
                base_max = int(base_max * 0.8)
        
        return max(3, base_max)  # Minimum 3 positions
    
    def _get_preferred_direction(self, regime: str) -> str:
        """Get preferred trading direction based on regime"""
        if regime in ['strong_uptrend', 'uptrend', 'choppy_bullish']:
            return 'long'
        elif regime in ['strong_downtrend', 'downtrend', 'choppy_bearish']:
            return 'short'
        else:
            return 'both'
    
    def _calculate_risk_per_trade(self, confidence: float, vol_score: float) -> float:
        """Calculate recommended risk per trade as percentage of capital"""
        # Base risk: 1-2% of capital
        base_risk = 0.01
        
        # Adjust for confidence
        confidence_adjustment = 0.5 + confidence
        
        # Adjust for volatility (inverse relationship)
        volatility_adjustment = 1.5 - vol_score
        
        risk_per_trade = base_risk * confidence_adjustment * volatility_adjustment
        
        # Cap between 0.5% and 2.5%
        return round(max(0.005, min(0.025, risk_per_trade)), 3)
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Convert confidence score to descriptive level"""
        if confidence >= 0.8:
            return 'Very High'
        elif confidence >= 0.6:
            return 'High'
        elif confidence >= 0.4:
            return 'Moderate'
        elif confidence >= 0.2:
            return 'Low'
        else:
            return 'Very Low'
    
    def _get_volatility_regime(self, vol_score: float) -> str:
        """Convert volatility score to regime description"""
        for regime, (low, high) in self.volatility_ranges.items():
            if low <= vol_score < high:
                return regime
        return 'extreme'
    
    def _generate_specific_guidance(self, regime: str, confidence: float, 
                                  vol_score: float) -> List[str]:
        """Generate specific trading guidance based on conditions"""
        guidance = []
        
        # Regime-based guidance
        if regime in ['strong_uptrend', 'strong_downtrend']:
            guidance.append(f"Strong trend detected - follow the trend with larger positions")
        elif regime in ['choppy', 'choppy_bullish', 'choppy_bearish']:
            guidance.append("Choppy market - reduce position sizes and use tight stops")
        
        # Confidence-based guidance
        if confidence >= 0.7:
            guidance.append("High confidence - can use full position sizing")
        elif confidence <= 0.3:
            guidance.append("Low confidence - consider reducing activity")
        
        # Volatility-based guidance
        if vol_score >= 0.7:
            guidance.append("High volatility - use wider stops and smaller positions")
        elif vol_score <= 0.3:
            guidance.append("Low volatility - can use tighter stops")
        
        # Combined conditions
        if regime in ['strong_uptrend', 'uptrend'] and confidence >= 0.6:
            guidance.append("Favorable conditions for long positions")
        elif regime in ['strong_downtrend', 'downtrend'] and confidence >= 0.6:
            guidance.append("Favorable conditions for short positions")
        
        return guidance
    
    def _get_regime_specific_recommendations(self, regime: str, 
                                           confidence: float) -> Dict:
        """Get regime-specific trading recommendations"""
        recommendations = {}
        
        if regime == 'strong_uptrend':
            recommendations['entry_strategy'] = 'Buy pullbacks to support'
            recommendations['exit_strategy'] = 'Trail stops below swing lows'
            recommendations['avoid'] = 'Short positions unless hedging'
        
        elif regime == 'uptrend':
            recommendations['entry_strategy'] = 'Buy breakouts and pullbacks'
            recommendations['exit_strategy'] = 'Use moving average as trailing stop'
            recommendations['avoid'] = 'Fighting the trend with shorts'
        
        elif regime == 'choppy':
            recommendations['entry_strategy'] = 'Buy support, sell resistance'
            recommendations['exit_strategy'] = 'Quick profits at range boundaries'
            recommendations['avoid'] = 'Trend-following strategies'
        
        elif regime == 'downtrend':
            recommendations['entry_strategy'] = 'Short rallies to resistance'
            recommendations['exit_strategy'] = 'Trail stops above swing highs'
            recommendations['avoid'] = 'Bottom fishing without confirmation'
        
        elif regime == 'strong_downtrend':
            recommendations['entry_strategy'] = 'Short breakdowns and rallies'
            recommendations['exit_strategy'] = 'Use moving average as trailing stop'
            recommendations['avoid'] = 'Long positions unless hedging'
        
        return recommendations
    
    def _get_default_recommendations(self) -> Dict:
        """Get default conservative recommendations"""
        return {
            'position_size_multiplier': 0.8,
            'stop_loss_multiplier': 1.0,
            'max_positions': 5,
            'preferred_direction': 'both',
            'risk_per_trade': 0.01,
            'confidence_level': 'Moderate',
            'volatility_regime': 'normal',
            'specific_guidance': ['Use standard position sizing', 
                                'Monitor market conditions closely']
        }


def test_position_recommender():
    """Test the position recommender with various scenarios"""
    recommender = PositionRecommender()
    
    test_scenarios = [
        {
            'name': 'Strong Bull Market',
            'regime': 'strong_uptrend',
            'confidence': 0.85,
            'volatility': {'volatility_score': 0.3}
        },
        {
            'name': 'Choppy High Vol',
            'regime': 'choppy',
            'confidence': 0.4,
            'volatility': {'volatility_score': 0.75}
        },
        {
            'name': 'Confident Bear',
            'regime': 'downtrend',
            'confidence': 0.7,
            'volatility': {'volatility_score': 0.5}
        }
    ]
    
    print("Position Recommender Test Results:")
    print("=" * 60)
    
    for scenario in test_scenarios:
        print(f"\n{scenario['name']}:")
        print(f"Regime: {scenario['regime']}, Confidence: {scenario['confidence']:.1%}")
        
        recommendations = recommender.get_recommendations(
            scenario['regime'],
            scenario['confidence'],
            scenario['volatility']
        )
        
        print(f"\nRecommendations:")
        print(f"  Position Size Multiplier: {recommendations['position_size_multiplier']}x")
        print(f"  Stop Loss Multiplier: {recommendations['stop_loss_multiplier']}x")
        print(f"  Max Positions: {recommendations['max_positions']}")
        print(f"  Preferred Direction: {recommendations['preferred_direction']}")
        print(f"  Risk per Trade: {recommendations['risk_per_trade']:.1%}")
        print(f"  Guidance: {', '.join(recommendations['specific_guidance'])}")


if __name__ == "__main__":
    test_position_recommender()