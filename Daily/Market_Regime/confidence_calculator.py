#!/usr/bin/env python3
"""
Confidence Calculator for Market Regime
Simplified version without ML dependencies
"""

import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ConfidenceCalculator:
    """Calculate confidence scores for regime predictions"""
    
    def __init__(self):
        # Confidence parameters
        self.ratio_thresholds = {
            'extreme_bullish': 3.0,    # Very high confidence
            'strong_bullish': 2.0,     # High confidence
            'bullish': 1.5,            # Moderate confidence
            'neutral_high': 1.2,       # Low confidence
            'neutral_low': 0.8,        # Low confidence
            'bearish': 0.67,           # Moderate confidence
            'strong_bearish': 0.5,     # High confidence
            'extreme_bearish': 0.33    # Very high confidence
        }
        
        self.history_window = 10  # Number of historical regimes to consider
        
    def calculate_confidence(self, regime_data: Dict) -> float:
        """
        Calculate overall confidence based on multiple factors
        
        Args:
            regime_data: Dictionary containing:
                - ratio: Long/Short ratio
                - history: List of recent regimes
                - volume_participation: Optional volume metric
                - trend_strength: Optional trend metric
                
        Returns:
            Confidence score between 0 and 1
        """
        try:
            # Base confidence from ratio extremity
            ratio = regime_data.get('ratio', 1.0)
            base_confidence = self._calculate_ratio_confidence(ratio)
            
            # Stability factor from historical consistency
            history = regime_data.get('history', [])
            stability_factor = self._calculate_stability_factor(history)
            
            # Volume participation factor
            volume_factor = regime_data.get('volume_participation', 0.5)
            volume_confidence = 0.5 + (volume_factor * 0.5)
            
            # Trend strength factor
            trend_strength = abs(regime_data.get('trend_strength', 0))
            trend_factor = min(trend_strength / 10, 1.0)  # Normalize to 0-1
            
            # Combine factors with weights
            weights = [0.4, 0.3, 0.2, 0.1]  # ratio, stability, volume, trend
            factors = [base_confidence, stability_factor, volume_confidence, trend_factor]
            
            # Weighted average
            confidence = sum(w * f for w, f in zip(weights, factors))
            
            # Apply bounds
            confidence = max(0.1, min(0.95, confidence))
            
            logger.debug(f"Confidence calculation: base={base_confidence:.2f}, "
                        f"stability={stability_factor:.2f}, volume={volume_confidence:.2f}, "
                        f"trend={trend_factor:.2f}, final={confidence:.2f}")
            
            return round(confidence, 3)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5  # Default moderate confidence
    
    def _calculate_ratio_confidence(self, ratio: float) -> float:
        """Calculate confidence based on Long/Short ratio extremity"""
        # The more extreme the ratio, the higher the confidence
        if ratio >= self.ratio_thresholds['extreme_bullish']:
            return 0.9
        elif ratio >= self.ratio_thresholds['strong_bullish']:
            return 0.8
        elif ratio >= self.ratio_thresholds['bullish']:
            return 0.7
        elif ratio <= self.ratio_thresholds['extreme_bearish']:
            return 0.9
        elif ratio <= self.ratio_thresholds['strong_bearish']:
            return 0.8
        elif ratio <= self.ratio_thresholds['bearish']:
            return 0.7
        else:
            # Neutral zone - lower confidence
            distance_from_neutral = min(
                abs(ratio - 1.0),
                abs(ratio - self.ratio_thresholds['neutral_high']),
                abs(ratio - self.ratio_thresholds['neutral_low'])
            )
            return 0.3 + (distance_from_neutral * 0.2)
    
    def _calculate_stability_factor(self, history: List[str]) -> float:
        """Calculate stability based on regime consistency"""
        if not history or len(history) < 2:
            return 0.5  # Default neutral stability
        
        # Take recent history
        recent_history = history[-self.history_window:]
        
        if len(recent_history) < 2:
            return 0.5
        
        # Count regime changes
        changes = 0
        for i in range(1, len(recent_history)):
            if recent_history[i] != recent_history[i-1]:
                changes += 1
        
        # Calculate stability (fewer changes = higher stability)
        change_rate = changes / (len(recent_history) - 1)
        stability = 1.0 - change_rate
        
        # Boost stability if current regime persists
        if len(recent_history) >= 3:
            current_regime = recent_history[-1]
            persistence = sum(1 for r in recent_history[-3:] if r == current_regime) / 3
            stability = (stability + persistence) / 2
        
        return stability
    
    def calculate_regime_strength(self, regime: str, ratio: float) -> float:
        """
        Calculate how strongly the current metrics support the regime
        
        Returns:
            Strength score between 0 and 1
        """
        regime_ranges = {
            'strong_uptrend': (2.0, float('inf')),
            'uptrend': (1.5, 2.0),
            'choppy_bullish': (1.2, 1.5),
            'choppy': (0.8, 1.2),
            'choppy_bearish': (0.67, 0.8),
            'downtrend': (0.5, 0.67),
            'strong_downtrend': (0, 0.5)
        }
        
        if regime not in regime_ranges:
            return 0.5
        
        min_ratio, max_ratio = regime_ranges[regime]
        
        # Check if ratio is within expected range
        if min_ratio <= ratio <= max_ratio:
            # Calculate position within range
            if max_ratio == float('inf'):
                # For strong_uptrend, use exponential decay
                strength = min(1.0, 0.7 + 0.3 * (1 - np.exp(-(ratio - min_ratio))))
            else:
                range_size = max_ratio - min_ratio
                position = (ratio - min_ratio) / range_size
                # Strength is highest in middle of range
                strength = 1.0 - abs(position - 0.5) * 0.4
            return strength
        else:
            # Outside expected range - lower strength
            if ratio < min_ratio:
                distance = min_ratio - ratio
            else:
                distance = ratio - max_ratio
            
            # Exponential decay for strength outside range
            strength = 0.5 * np.exp(-distance)
            return max(0.1, strength)


def test_confidence_calculator():
    """Test the confidence calculator with various scenarios"""
    calc = ConfidenceCalculator()
    
    test_cases = [
        {
            'name': 'Strong Bullish',
            'data': {
                'ratio': 3.5,
                'history': ['uptrend'] * 8 + ['strong_uptrend'] * 2,
                'volume_participation': 0.8,
                'trend_strength': 7.5
            }
        },
        {
            'name': 'Choppy Market',
            'data': {
                'ratio': 1.1,
                'history': ['choppy', 'choppy_bullish', 'choppy', 'choppy_bearish'] * 2,
                'volume_participation': 0.5,
                'trend_strength': 0.5
            }
        },
        {
            'name': 'Trend Reversal',
            'data': {
                'ratio': 0.6,
                'history': ['uptrend'] * 5 + ['choppy'] * 3 + ['downtrend'] * 2,
                'volume_participation': 0.6,
                'trend_strength': -3.5
            }
        }
    ]
    
    print("Confidence Calculator Test Results:")
    print("-" * 50)
    
    for test in test_cases:
        confidence = calc.calculate_confidence(test['data'])
        strength = calc.calculate_regime_strength('uptrend', test['data']['ratio'])
        
        print(f"\n{test['name']}:")
        print(f"  Ratio: {test['data']['ratio']}")
        print(f"  Confidence: {confidence:.1%}")
        print(f"  Regime Strength: {strength:.1%}")


if __name__ == "__main__":
    test_confidence_calculator()