#!/usr/bin/env python3
"""
Enhanced Market Score Calculator with Breadth Integration
Combines reversal signals with market breadth for improved market direction assessment
"""

import json
import logging
import numpy as np
import os
from typing import Dict, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedMarketScoreCalculator:
    """Calculate enhanced market score with breadth weightage"""
    
    def __init__(self):
        # Load configuration
        self.config_file = os.path.join(os.path.dirname(__file__), 'market_score_config.json')
        self.load_config()
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                settings = config['enhanced_market_score']
                self.breadth_weight = settings['breadth_weight']
                self.momentum_weight = settings['momentum_weight']
                self.extreme_bullish_threshold = settings['extreme_bullish_threshold']
                self.extreme_bearish_threshold = settings['extreme_bearish_threshold']
                self.neutral_zone = tuple(settings['neutral_zone'])
                
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                # Default values
                self.breadth_weight = 0.4
                self.momentum_weight = 0.2
                self.extreme_bullish_threshold = 70
                self.extreme_bearish_threshold = 70
                self.neutral_zone = (40, 60)
                logger.warning("Config file not found, using default values")
                
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            # Default values
            self.breadth_weight = 0.4
            self.momentum_weight = 0.2
            self.extreme_bullish_threshold = 70
            self.extreme_bearish_threshold = 70
            self.neutral_zone = (40, 60)
        
    def calculate_enhanced_market_score(self, reversal_counts: Dict, breadth_data: Dict, 
                                      momentum_data: Dict = None) -> Dict:
        """
        Calculate enhanced market score incorporating breadth data
        
        Returns score between -1 (extreme bearish) to +1 (extreme bullish)
        """
        # 1. Calculate reversal-based score (original method)
        reversal_score = self._calculate_reversal_score(reversal_counts)
        
        # 2. Calculate breadth-based score
        breadth_score = self._calculate_breadth_score(breadth_data)
        
        # 3. Calculate momentum score if available
        momentum_score = 0
        if momentum_data:
            momentum_score = self._calculate_momentum_score(momentum_data)
        
        # 4. Combine scores with weights
        if momentum_data:
            # With momentum: 50% reversal, 30% breadth, 20% momentum
            combined_score = (
                reversal_score * 0.5 + 
                breadth_score * 0.3 + 
                momentum_score * 0.2
            )
        else:
            # Without momentum: 60% reversal, 40% breadth
            combined_score = (
                reversal_score * (1 - self.breadth_weight) + 
                breadth_score * self.breadth_weight
            )
        
        # 5. Calculate confidence based on agreement
        confidence = self._calculate_confidence(reversal_score, breadth_score, momentum_score)
        
        # 6. Determine market direction
        direction = self._determine_direction(combined_score)
        
        # 7. Calculate strategy recommendation
        strategy_recommendation = self._get_strategy_recommendation(
            combined_score, confidence, reversal_counts, breadth_data
        )
        
        return {
            'market_score': combined_score,
            'reversal_score': reversal_score,
            'breadth_score': breadth_score,
            'momentum_score': momentum_score,
            'confidence': confidence,
            'direction': direction,
            'components': {
                'reversal_contribution': reversal_score * (1 - self.breadth_weight),
                'breadth_contribution': breadth_score * self.breadth_weight,
                'momentum_contribution': momentum_score * self.momentum_weight if momentum_data else 0
            },
            'strategy_recommendation': strategy_recommendation,
            'weekly_bias': self._calculate_weekly_bias(combined_score, confidence)
        }
    
    def _calculate_reversal_score(self, counts: Dict) -> float:
        """Calculate score from reversal counts (-1 to +1)"""
        long_count = counts.get('long', 0)
        short_count = counts.get('short', 0)
        total = long_count + short_count
        
        if total == 0:
            return 0
        
        # Calculate ratio and normalize to -1 to +1
        long_ratio = long_count / total
        # Convert 0-1 ratio to -1 to +1 scale
        return (long_ratio * 2) - 1
    
    def _calculate_breadth_score(self, breadth_data: Dict) -> float:
        """Calculate score from market breadth (-1 to +1)"""
        bullish_pct = breadth_data.get('bullish_percent', 50)
        bearish_pct = breadth_data.get('bearish_percent', 50)
        
        # Normalize to -1 to +1
        # If 100% bullish: score = +1
        # If 100% bearish: score = -1
        # If 50/50: score = 0
        
        if bullish_pct + bearish_pct == 0:
            return 0
            
        net_bullish = bullish_pct - bearish_pct
        # net_bullish ranges from -100 to +100, normalize to -1 to +1
        return net_bullish / 100
    
    def _calculate_momentum_score(self, momentum_data: Dict) -> float:
        """Calculate momentum score (-1 to +1)"""
        momentum = momentum_data.get('momentum', 'neutral')
        
        momentum_scores = {
            'increasing_bullish': 0.5,
            'stable_bullish': 0.25,
            'neutral': 0,
            'stable_bearish': -0.25,
            'increasing_bearish': -0.5
        }
        
        return momentum_scores.get(momentum, 0)
    
    def _calculate_confidence(self, reversal_score: float, breadth_score: float, 
                            momentum_score: float) -> float:
        """Calculate confidence based on agreement between indicators"""
        scores = [reversal_score, breadth_score]
        if momentum_score != 0:
            scores.append(momentum_score)
        
        # Check if all indicators agree on direction
        all_positive = all(s > 0 for s in scores)
        all_negative = all(s < 0 for s in scores)
        
        if all_positive or all_negative:
            # High confidence when all agree
            avg_magnitude = np.mean([abs(s) for s in scores])
            confidence = 0.7 + (0.3 * avg_magnitude)  # 70-100%
        else:
            # Lower confidence when mixed signals
            avg_magnitude = np.mean([abs(s) for s in scores])
            confidence = 0.3 + (0.4 * avg_magnitude)  # 30-70%
        
        return min(confidence, 1.0)
    
    def _determine_direction(self, score: float) -> str:
        """Determine market direction from score"""
        if score >= 0.5:
            return 'strong_bullish'
        elif score >= 0.2:
            return 'bullish'
        elif score >= -0.2:
            return 'neutral'
        elif score >= -0.5:
            return 'bearish'
        else:
            return 'strong_bearish'
    
    def _get_strategy_recommendation(self, score: float, confidence: float, 
                                   reversal_counts: Dict, breadth_data: Dict) -> Dict:
        """Generate detailed strategy recommendation"""
        direction = self._determine_direction(score)
        
        # Base recommendations
        recommendations = {
            'strong_bullish': {
                'primary_strategy': 'Long Reversal',
                'secondary_strategy': 'Avoid Shorts',
                'position_sizing': 1.5 if confidence > 0.7 else 1.0,
                'risk_per_trade': 0.02 if confidence > 0.7 else 0.015
            },
            'bullish': {
                'primary_strategy': 'Long Reversal',
                'secondary_strategy': 'Selective Shorts',
                'position_sizing': 1.2 if confidence > 0.6 else 1.0,
                'risk_per_trade': 0.02 if confidence > 0.6 else 0.015
            },
            'neutral': {
                'primary_strategy': 'Both Strategies',
                'secondary_strategy': 'Equal Weight',
                'position_sizing': 0.8,
                'risk_per_trade': 0.015
            },
            'bearish': {
                'primary_strategy': 'Short Reversal',
                'secondary_strategy': 'Selective Longs',
                'position_sizing': 1.2 if confidence > 0.6 else 1.0,
                'risk_per_trade': 0.02 if confidence > 0.6 else 0.015
            },
            'strong_bearish': {
                'primary_strategy': 'Short Reversal',
                'secondary_strategy': 'Avoid Longs',
                'position_sizing': 1.5 if confidence > 0.7 else 1.0,
                'risk_per_trade': 0.02 if confidence > 0.7 else 0.015
            }
        }
        
        rec = recommendations[direction].copy()
        
        # Add specific insights
        bearish_pct = breadth_data.get('bearish_percent', 50)
        if bearish_pct > self.extreme_bearish_threshold:
            rec['special_note'] = f'Extreme bearish breadth ({bearish_pct:.1f}%) - Strong short bias'
        elif bearish_pct < 100 - self.extreme_bullish_threshold:
            rec['special_note'] = f'Extreme bullish breadth ({100-bearish_pct:.1f}%) - Strong long bias'
        
        # Add signal counts
        rec['available_signals'] = {
            'long': reversal_counts.get('long', 0),
            'short': reversal_counts.get('short', 0)
        }
        
        return rec
    
    def _calculate_weekly_bias(self, score: float, confidence: float) -> Dict:
        """Calculate weekly trading bias"""
        # Determine primary direction for the week
        if score > 0.3 and confidence > 0.6:
            return {
                'direction': 'LONG',
                'strength': 'Strong' if score > 0.5 else 'Moderate',
                'allocation': 70 if score > 0.5 else 60,  # % allocation to primary direction
                'rationale': 'Market breadth and reversals favor bullish setups'
            }
        elif score < -0.3 and confidence > 0.6:
            return {
                'direction': 'SHORT',
                'strength': 'Strong' if score < -0.5 else 'Moderate',
                'allocation': 70 if score < -0.5 else 60,
                'rationale': 'Market breadth and reversals favor bearish setups'
            }
        else:
            return {
                'direction': 'NEUTRAL',
                'strength': 'Balanced',
                'allocation': 50,  # Equal allocation
                'rationale': 'Mixed signals suggest balanced approach'
            }
    
    def get_tuning_parameters(self) -> Dict:
        """Get current tuning parameters"""
        return {
            'breadth_weight': self.breadth_weight,
            'momentum_weight': self.momentum_weight,
            'extreme_bullish_threshold': self.extreme_bullish_threshold,
            'extreme_bearish_threshold': self.extreme_bearish_threshold,
            'neutral_zone': self.neutral_zone
        }
    
    def update_parameters(self, **kwargs) -> None:
        """Update tuning parameters"""
        if 'breadth_weight' in kwargs:
            self.breadth_weight = max(0, min(1, kwargs['breadth_weight']))
        if 'momentum_weight' in kwargs:
            self.momentum_weight = max(0, min(1, kwargs['momentum_weight']))
        if 'extreme_bullish_threshold' in kwargs:
            self.extreme_bullish_threshold = kwargs['extreme_bullish_threshold']
        if 'extreme_bearish_threshold' in kwargs:
            self.extreme_bearish_threshold = kwargs['extreme_bearish_threshold']
        
        logger.info(f"Updated parameters: {self.get_tuning_parameters()}")


def test_calculator():
    """Test the enhanced calculator with sample data"""
    calculator = EnhancedMarketScoreCalculator()
    
    # Test scenarios
    test_cases = [
        {
            'name': 'Bearish Alignment',
            'reversal_counts': {'long': 20, 'short': 80},
            'breadth_data': {'bullish_percent': 25, 'bearish_percent': 75},
            'momentum_data': {'momentum': 'increasing_bearish'}
        },
        {
            'name': 'Mixed Signals',
            'reversal_counts': {'long': 60, 'short': 40},
            'breadth_data': {'bullish_percent': 30, 'bearish_percent': 70},
            'momentum_data': None
        },
        {
            'name': 'Neutral Market',
            'reversal_counts': {'long': 50, 'short': 50},
            'breadth_data': {'bullish_percent': 48, 'bearish_percent': 52},
            'momentum_data': {'momentum': 'neutral'}
        }
    ]
    
    for test in test_cases:
        print(f"\n=== {test['name']} ===")
        result = calculator.calculate_enhanced_market_score(
            test['reversal_counts'],
            test['breadth_data'],
            test['momentum_data']
        )
        
        print(f"Market Score: {result['market_score']:.3f}")
        print(f"Direction: {result['direction']}")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Weekly Bias: {result['weekly_bias']['direction']} "
              f"({result['weekly_bias']['strength']}, {result['weekly_bias']['allocation']}% allocation)")
        print(f"Strategy: {result['strategy_recommendation']['primary_strategy']}")
        

if __name__ == "__main__":
    test_calculator()