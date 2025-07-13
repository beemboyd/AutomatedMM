#!/usr/bin/env python
"""
Regime-Based Stop Loss Module
Provides intelligent stop loss multipliers based on market regime analysis
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class RegimeStopLoss:
    """Calculate intelligent stop loss multipliers based on market regime"""
    
    def __init__(self):
        # Load configuration
        self.load_config()
        
        # Stop Loss Multiplier Matrix
        self.REGIME_SL_MATRIX = {
            'strong_uptrend': {
                'low': 0.8,          # Tighter stops in strong trends
                'medium': 1.2,
                'high': 1.8,
                'extreme': 2.5
            },
            'uptrend': {
                'low': 1.0,
                'medium': 1.5,
                'high': 2.0,
                'extreme': 2.8
            },
            'choppy_bullish': {
                'low': 1.2,
                'medium': 1.8,
                'high': 2.5,
                'extreme': 3.0
            },
            'choppy': {  # Neutral choppy
                'low': 1.5,
                'medium': 2.0,
                'high': 2.8,
                'extreme': 3.5
            },
            'choppy_bearish': {
                'low': 0.7,          # Very tight stops in bear markets
                'medium': 1.0,
                'high': 1.5,
                'extreme': 2.0
            },
            'downtrend': {
                'low': 0.5,          # Exit quickly in downtrends
                'medium': 0.8,
                'high': 1.2,
                'extreme': 1.5
            },
            'strong_downtrend': {
                'low': 0.4,          # Very tight stops in strong downtrends
                'medium': 0.6,
                'high': 1.0,
                'extreme': 1.2
            }
        }
        
        # Default configuration parameters (overridden by config.ini if available)
        self.min_multiplier = 0.5
        self.max_multiplier = 3.0
        self.confidence_weight = 0.2
        self.momentum_weight = 0.15
        self.pattern_weight = 0.15
    
    def load_config(self):
        """Load configuration from config.ini if available"""
        try:
            import configparser
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config.ini'
            )
            
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                
                if 'REGIME_STOPS' in config:
                    self.enabled = config.getboolean('REGIME_STOPS', 'enable_regime_stops', fallback=True)
                    self.min_multiplier = config.getfloat('REGIME_STOPS', 'min_multiplier', fallback=0.5)
                    self.max_multiplier = config.getfloat('REGIME_STOPS', 'max_multiplier', fallback=3.0)
                    self.confidence_weight = config.getfloat('REGIME_STOPS', 'confidence_weight', fallback=0.2)
                    self.momentum_weight = config.getfloat('REGIME_STOPS', 'momentum_weight', fallback=0.15)
                    self.pattern_weight = config.getfloat('REGIME_STOPS', 'pattern_weight', fallback=0.15)
                    
                    logger.debug(f"Loaded regime stops config: enabled={self.enabled}, "
                               f"min={self.min_multiplier}, max={self.max_multiplier}")
        except Exception as e:
            logger.debug(f"Could not load config: {e}. Using defaults.")
        
    def load_regime_data(self) -> Optional[Dict]:
        """Load the latest market regime data"""
        try:
            # Try Daily folder first
            regime_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'Market_Regime', 'regime_analysis', 'latest_regime_summary.json'
            )
            
            # If not found, try parent directory
            if not os.path.exists(regime_file):
                regime_file = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'Market_Regime', 'regime_analysis', 'latest_regime_summary.json'
                )
            
            if not os.path.exists(regime_file):
                logger.warning(f"Regime file not found: {regime_file}")
                return None
                
            with open(regime_file, 'r') as f:
                data = json.load(f)
                
            # Check if data is recent (within 24 hours)
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            age_hours = (datetime.now() - timestamp.replace(tzinfo=None)).total_seconds() / 3600
            
            if age_hours > 24:
                logger.warning(f"Regime data is {age_hours:.1f} hours old, may be stale")
                
            return data
            
        except Exception as e:
            logger.error(f"Error loading regime data: {e}")
            return None
    
    def get_volatility_category(self, volatility_score: float) -> str:
        """Convert volatility score to category"""
        if volatility_score >= 0.75:
            return 'extreme'
        elif volatility_score >= 0.5:
            return 'high'
        elif volatility_score >= 0.25:
            return 'medium'
        else:
            return 'low'
    
    def get_confidence_adjustment(self, confidence: float) -> float:
        """
        High confidence = tighter stops (we trust the trend)
        Low confidence = wider stops (more uncertainty)
        """
        if confidence >= 0.8:
            return 0.9  # 10% tighter
        elif confidence >= 0.6:
            return 1.0  # Normal
        elif confidence >= 0.4:
            return 1.1  # 10% wider
        else:
            return 1.2  # 20% wider
    
    def get_momentum_adjustment(self, momentum_ratio: float, preferred_direction: str) -> float:
        """
        Strong momentum in trend direction = tighter stops
        Weakening momentum = wider stops
        """
        if preferred_direction == 'long':
            if momentum_ratio > 3.0:  # Very strong bullish momentum
                return 0.85
            elif momentum_ratio > 2.0:
                return 0.95
            elif momentum_ratio < 1.0:  # Bearish momentum
                return 1.3
        else:  # Short/bearish regime
            if momentum_ratio < 0.5:  # Very strong bearish momentum
                return 0.85
            elif momentum_ratio < 0.75:
                return 0.95
            elif momentum_ratio > 1.0:  # Bullish momentum in bear regime
                return 1.3
        return 1.0
    
    def get_pattern_adjustment(self, long_count: int, short_count: int) -> float:
        """
        Many opposing patterns = wider stops (conflicting signals)
        Few opposing patterns = tighter stops (clear direction)
        """
        total = long_count + short_count
        if total == 0:
            return 1.0
        
        opposition_ratio = min(long_count, short_count) / total
        
        if opposition_ratio < 0.2:  # Very few opposing patterns
            return 0.9
        elif opposition_ratio > 0.4:  # Many opposing patterns
            return 1.2
        return 1.0
    
    def get_regime_multiplier(self, ticker: str, atr_percent: float, position_age_days: int = 0) -> Tuple[float, str]:
        """
        Get intelligent stop loss multiplier based on market regime
        Returns: (multiplier, reason_string)
        """
        # Check if regime stops are enabled
        if not getattr(self, 'enabled', True):
            return None, "Regime stops disabled in config"
            
        # Load regime data
        regime_data = self.load_regime_data()
        
        # If no regime data available, return None to indicate fallback needed
        if regime_data is None:
            return None, "No regime data available"
        
        try:
            # Extract key metrics
            regime = regime_data['market_regime']['regime']
            confidence = regime_data['market_regime']['confidence']
            volatility_score = regime_data['volatility']['volatility_score']
            
            reversal_counts = regime_data['reversal_counts']
            long_count = reversal_counts['long']
            short_count = reversal_counts['short']
            
            momentum_ratio = regime_data['momentum_analysis']['momentum_ratio']
            preferred_direction = regime_data['position_recommendations']['preferred_direction']
            
            # Get volatility category
            vol_category = self.get_volatility_category(volatility_score)
            
            # Get base multiplier from matrix
            if regime not in self.REGIME_SL_MATRIX:
                logger.warning(f"Unknown regime: {regime}, using 'choppy'")
                regime = 'choppy'
                
            base_multiplier = self.REGIME_SL_MATRIX[regime][vol_category]
            
            # Get adjustments
            confidence_adj = self.get_confidence_adjustment(confidence)
            momentum_adj = self.get_momentum_adjustment(momentum_ratio, preferred_direction)
            pattern_adj = self.get_pattern_adjustment(long_count, short_count)
            
            # Time-based adjustment (tighten stops as position ages)
            time_adj = 1.0
            if position_age_days >= 14:
                time_adj = 0.85
            elif position_age_days >= 7:
                time_adj = 0.90
            elif position_age_days >= 3:
                time_adj = 0.95
            
            # Calculate final multiplier
            final_multiplier = base_multiplier * confidence_adj * momentum_adj * pattern_adj * time_adj
            
            # Apply min/max limits
            final_multiplier = max(self.min_multiplier, min(self.max_multiplier, final_multiplier))
            
            # Build reason string
            reason_parts = [
                f"Regime: {regime}",
                f"Vol: {vol_category}",
                f"Base: {base_multiplier:.2f}x",
                f"Conf({confidence:.1%}): {confidence_adj:.2f}x",
                f"Mom({momentum_ratio:.1f}): {momentum_adj:.2f}x",
                f"Pat({long_count}/{short_count}): {pattern_adj:.2f}x"
            ]
            
            if position_age_days > 0:
                reason_parts.append(f"Age({position_age_days}d): {time_adj:.2f}x")
                
            reason = " | ".join(reason_parts) + f" = {final_multiplier:.2f}x"
            
            return final_multiplier, reason
            
        except Exception as e:
            logger.error(f"Error calculating regime multiplier: {e}")
            return None, f"Error: {str(e)}"
    
    def get_default_multiplier(self, atr_percent: float) -> Tuple[float, str]:
        """
        Get default multiplier based on ATR (fallback logic)
        This should match the original SL_Watchdog logic
        """
        if atr_percent < 2.0:
            return 1.0, "Low volatility (<2%)"
        elif atr_percent < 4.0:
            return 1.5, "Medium volatility (2-4%)"
        else:
            return 2.0, "High volatility (>4%)"

# Example usage
if __name__ == "__main__":
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test the regime stop loss calculator
    rsl = RegimeStopLoss()
    
    # Test with current data
    multiplier, reason = rsl.get_regime_multiplier("TEST", 5.0, position_age_days=5)
    
    if multiplier is None:
        print("Using fallback logic")
        multiplier, reason = rsl.get_default_multiplier(5.0)
    
    print(f"Stop Loss Multiplier: {multiplier:.2f}x")
    print(f"Reason: {reason}")