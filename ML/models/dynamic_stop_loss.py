#\!/usr/bin/env python3
"""
Dynamic Stop Loss Model

This module calculates dynamic stop loss levels based on market regimes and volatility.
It's a simplified version for demonstration purposes.
"""

import numpy as np
from enum import Enum

class PositionType(Enum):
    """Position type enumeration"""
    LONG = "LONG"
    SHORT = "SHORT"

class MarketRegimeType(Enum):
    """Market regime type enumeration"""
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING_LOW_VOL = "ranging_low_volatility"
    RANGING_HIGH_VOL = "ranging_high_volatility"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"

class DynamicStopLossModel:
    """
    Dynamic Stop Loss Model that adjusts ATR multipliers based on market regime.
    This is a simplified version that doesn't require scikit-learn.
    """
    
    def __init__(self):
        """Initialize the model with default parameters"""
        self.base_multipliers = {
            MarketRegimeType.TRENDING_BULLISH.value: {
                PositionType.LONG.value: 2.0, 
                PositionType.SHORT.value: 1.5
            },
            MarketRegimeType.TRENDING_BEARISH.value: {
                PositionType.LONG.value: 1.5, 
                PositionType.SHORT.value: 2.0
            },
            MarketRegimeType.RANGING_LOW_VOL.value: {
                PositionType.LONG.value: 1.5, 
                PositionType.SHORT.value: 1.5
            },
            MarketRegimeType.RANGING_HIGH_VOL.value: {
                PositionType.LONG.value: 2.5, 
                PositionType.SHORT.value: 2.5
            },
            MarketRegimeType.TRANSITIONING.value: {
                PositionType.LONG.value: 2.0, 
                PositionType.SHORT.value: 2.0
            },
            MarketRegimeType.UNKNOWN.value: {
                PositionType.LONG.value: 2.0, 
                PositionType.SHORT.value: 2.0
            }
        }
    
    def _get_base_atr_multiplier(self, regime, position_type):
        """
        Get the base ATR multiplier for the given market regime and position type.
        
        Args:
            regime (str): Market regime type
            position_type (PositionType): Position type (LONG or SHORT)
            
        Returns:
            float: Base ATR multiplier
        """
        # Default to transitioning if regime not found
        if regime not in self.base_multipliers:
            regime = MarketRegimeType.TRANSITIONING.value
            
        # Get multiplier based on position type
        return self.base_multipliers[regime][position_type.value]
    
    def calculate_stop_loss(self, current_price, atr, regime, position_type, 
                           volatility=None, trend_strength=None):
        """
        Calculate the stop loss price based on current price, ATR, market regime, and position type.
        
        Args:
            current_price (float): Current price
            atr (float): Average True Range
            regime (str): Market regime type
            position_type (PositionType): Position type (LONG or SHORT)
            volatility (float, optional): Market volatility
            trend_strength (float, optional): Trend strength
            
        Returns:
            float: Stop loss price
        """
        # Get base multiplier
        multiplier = self._get_base_atr_multiplier(regime, position_type)
        
        # Apply adjustments based on volatility and trend strength if provided
        if volatility is not None and trend_strength is not None:
            # Increase multiplier for high volatility
            if volatility > 0.5:
                multiplier += 0.2
            
            # Decrease multiplier for strong trends
            if trend_strength > 10:
                multiplier += 0.2
        
        # Calculate stop loss based on position type
        if position_type == PositionType.LONG:
            return current_price - (multiplier * atr)
        else:
            return current_price + (multiplier * atr)
