#\!/usr/bin/env python3
"""
ATR Calculator

Calculates Average True Range (ATR) for a given price series.
"""

import pandas as pd
import numpy as np

class ATRCalculator:
    """
    Calculates various volatility metrics including ATR.
    """
    
    def __init__(self, period=14):
        """
        Initialize the calculator.
        
        Args:
            period (int): Period for ATR calculation
        """
        self.period = period
    
    def calculate_atr(self, data):
        """
        Calculate ATR for the given data.
        
        Args:
            data (pd.DataFrame): DataFrame with OHLC price data
            
        Returns:
            pd.Series: ATR values
        """
        # Make sure we have the required columns
        required_columns = ['High', 'Low', 'Close']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"Data must have {required_columns} columns")
        
        # Calculate true range
        high = data['High']
        low = data['Low']
        close_prev = data['Close'].shift(1)
        
        # True range is max of (high-low, abs(high-prev_close), abs(low-prev_close))
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        
        # Calculate ATR using simple moving average of true range
        atr = tr.rolling(window=self.period).mean()
        
        return atr
    
    def calculate_adaptive_atr(self, data):
        """
        Calculate adaptive ATR that puts more weight on recent volatility.
        
        Args:
            data (pd.DataFrame): DataFrame with OHLC price data
            
        Returns:
            pd.Series: Adaptive ATR values
        """
        # First calculate standard ATR
        atr = self.calculate_atr(data)
        
        # Calculate short-term ATR (5 days)
        atr_short = self.calculate_atr_with_period(data, 5)
        
        # Calculate adaptive ATR with more weight on recent volatility
        adaptive_atr = (0.7 * atr_short) + (0.3 * atr)
        
        return adaptive_atr
    
    def calculate_atr_with_period(self, data, period):
        """
        Calculate ATR with a specific period.
        
        Args:
            data (pd.DataFrame): DataFrame with OHLC price data
            period (int): Period for ATR calculation
            
        Returns:
            pd.Series: ATR values
        """
        # Make sure we have the required columns
        required_columns = ['High', 'Low', 'Close']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"Data must have {required_columns} columns")
        
        # Calculate true range
        high = data['High']
        low = data['Low']
        close_prev = data['Close'].shift(1)
        
        # True range is max of (high-low, abs(high-prev_close), abs(low-prev_close))
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        
        # Calculate ATR using simple moving average of true range
        atr = tr.rolling(window=period).mean()
        
        return atr
