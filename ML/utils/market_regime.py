#\!/usr/bin/env python3
"""
Market Regime Detector

Detects market regimes based on various technical analysis methods.
"""

import pandas as pd
import numpy as np
from enum import Enum

class MarketRegimeType(Enum):
    """Market regime type enumeration"""
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING_LOW_VOL = "ranging_low_volatility"
    RANGING_HIGH_VOL = "ranging_high_volatility"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"

class MarketRegimeDetector:
    """
    Detects market regimes based on price action, moving averages, and volatility.
    """
    
    def __init__(self, lookback_short=20, lookback_medium=50, lookback_long=100):
        """
        Initialize the detector.
        
        Args:
            lookback_short (int): Period for short-term lookback
            lookback_medium (int): Period for medium-term lookback
            lookback_long (int): Period for long-term lookback
        """
        self.lookback_short = lookback_short
        self.lookback_medium = lookback_medium
        self.lookback_long = lookback_long
        
        # Thresholds for regime classification
        self.volatility_threshold = 0.4  # Threshold for high/low volatility
        self.trend_strength_threshold = 5.0  # Threshold for strong/weak trend
    
    def detect_using_ma(self, data):
        """
        Detect market regime using moving average method.
        
        Args:
            data (pd.DataFrame): DataFrame with price data
            
        Returns:
            pd.Series: Market regime for each date
        """
        # Calculate moving averages
        data['ma_short'] = data['Close'].rolling(window=self.lookback_short).mean()
        data['ma_medium'] = data['Close'].rolling(window=self.lookback_medium).mean()
        data['ma_long'] = data['Close'].rolling(window=self.lookback_long).mean()
        
        # Calculate moving average slopes (rate of change)
        data['ma_short_slope'] = data['ma_short'].pct_change(periods=5) * 100
        data['ma_medium_slope'] = data['ma_medium'].pct_change(periods=10) * 100
        data['ma_long_slope'] = data['ma_long'].pct_change(periods=20) * 100
        
        # Initialize regime series
        regime = pd.Series(index=data.index, dtype='object')
        
        # Detect regime for each date
        for date in data.index:
            if pd.isna(data.loc[date, 'ma_long']):
                regime[date] = MarketRegimeType.UNKNOWN.value
                continue
            
            # Get moving average values
            ma_short = data.loc[date, 'ma_short']
            ma_medium = data.loc[date, 'ma_medium']
            ma_long = data.loc[date, 'ma_long']
            
            # Get moving average slopes
            ma_short_slope = data.loc[date, 'ma_short_slope']
            ma_medium_slope = data.loc[date, 'ma_medium_slope']
            ma_long_slope = data.loc[date, 'ma_long_slope']
            
            # Define trending bullish: Short > Medium > Long, with positive slopes
            if (ma_short > ma_medium > ma_long and 
                ma_short_slope > 0 and ma_medium_slope > 0):
                regime[date] = MarketRegimeType.TRENDING_BULLISH.value
                
            # Define trending bearish: Short < Medium < Long, with negative slopes
            elif (ma_short < ma_medium < ma_long and 
                 ma_short_slope < 0 and ma_medium_slope < 0):
                regime[date] = MarketRegimeType.TRENDING_BEARISH.value
                
            # Define ranging: MAs are close together with flat slopes
            elif (abs(ma_short - ma_long) / ma_long < 0.05 and 
                 abs(ma_short_slope) < 1.0 and abs(ma_medium_slope) < 1.0):
                
                # Calculate volatility
                volatility = data.loc[date, 'Volatility'] if 'Volatility' in data else 0
                
                if volatility > self.volatility_threshold:
                    regime[date] = MarketRegimeType.RANGING_HIGH_VOL.value
                else:
                    regime[date] = MarketRegimeType.RANGING_LOW_VOL.value
                    
            # Default to transitioning for everything else
            else:
                regime[date] = MarketRegimeType.TRANSITIONING.value
        
        return regime
    
    def calculate_hurst_exponent(self, prices, lag_range=20):
        """
        Calculate Hurst exponent to determine if a time series is trending or mean-reverting.

        Args:
            prices (pd.Series): Price series
            lag_range (int): Maximum lag for calculation

        Returns:
            pd.Series: Hurst exponent for each date
        """
        # Initialize Hurst series
        hurst_series = pd.Series(index=prices.index)

        # Calculate Hurst exponent for each point using a rolling window
        window_size = 100  # Minimum window size

        for i in range(window_size, len(prices)):
            price_window = prices.iloc[i-window_size:i]

            # Skip if there are NaN values
            if price_window.isna().any():
                hurst_series.iloc[i] = np.nan
                continue

            # Calculate returns
            returns = np.log(price_window / price_window.shift(1)).dropna()

            # Skip if not enough data
            if len(returns) < lag_range:
                hurst_series.iloc[i] = np.nan
                continue

            # Create a range of lag values
            lags = range(2, lag_range)

            try:
                # Calculate the variance of the log return differences with zero protection
                tau = []
                valid_lags = []

                for lag in lags:
                    diff = np.subtract(returns[lag:], returns[:-lag])
                    if len(diff) > 0:
                        std_val = np.std(diff)
                        if std_val > 0:  # Only use positive standard deviations
                            tau.append(np.sqrt(std_val))
                            valid_lags.append(lag)

                # Check if we have enough valid data points
                if len(tau) > 5 and len(valid_lags) > 5:  # Need at least 5 points for a meaningful regression
                    # Fit a line to the log-log plot
                    log_lags = np.log10(valid_lags)
                    log_tau = np.log10(tau)

                    m = np.polyfit(log_lags, log_tau, 1)
                    hurst = m[0] / 2.0  # Hurst exponent is half the slope

                    # Validating the Hurst exponent is in a reasonable range
                    if 0 <= hurst <= 1:
                        hurst_series.iloc[i] = hurst
                    else:
                        hurst_series.iloc[i] = np.nan
                else:
                    hurst_series.iloc[i] = np.nan
            except Exception as e:
                # More detailed error handling
                hurst_series.iloc[i] = np.nan

        # Fill NaN values with forward fill (using ffill method instead of method parameter)
        hurst_series = hurst_series.ffill()

        return hurst_series
    
    def detect_consolidated_regime(self, data):
        """
        Detect market regime using multiple methods and consolidate results.
        
        Args:
            data (pd.DataFrame): DataFrame with price data
            
        Returns:
            tuple: (pd.Series, dict) - Consolidated regime and metrics
        """
        # Calculate volatility (ATR as % of price)
        high = data['High']
        low = data['Low']
        close = data['Close']
        close_prev = close.shift(1)
        
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        
        # Calculate ATR (20-day)
        atr = tr.rolling(window=20).mean()
        
        # ATR as percentage of price
        data['Volatility'] = atr / close
        
        # Calculate trend strength: slope of linear regression on prices
        window = 20
        data['TrendStrength'] = 0.0
        
        for i in range(window, len(data)):
            price_window = data['Close'].iloc[i-window:i]
            time_index = np.arange(1, window+1)
            
            try:
                slope, _ = np.polyfit(time_index, price_window, 1)
                data.iloc[i, data.columns.get_loc('TrendStrength')] = abs(slope * window / price_window.iloc[-1]) * 100
            except:
                pass
        
        # Detect regime using MA method
        regime = self.detect_using_ma(data)
        
        # Calculate Hurst exponent
        data['Hurst'] = self.calculate_hurst_exponent(data['Close'])
        
        # Adjust regime based on Hurst exponent
        for date in data.index:
            if pd.isna(data.loc[date, 'Hurst']):
                continue
            
            hurst = data.loc[date, 'Hurst']
            volatility = data.loc[date, 'Volatility']
            trend_strength = data.loc[date, 'TrendStrength']
            
            # Strong trending (Hurst > 0.6) or strong trend strength
            if (hurst > 0.6 or trend_strength > self.trend_strength_threshold):
                if volatility > self.volatility_threshold:
                    # Determine direction based on short-term slope
                    if data.loc[date, 'ma_short_slope'] > 0:
                        regime[date] = MarketRegimeType.TRENDING_BULLISH.value
                    else:
                        regime[date] = MarketRegimeType.TRENDING_BEARISH.value
                else:
                    # Confirm existing trend or change to transitioning
                    if regime[date] not in [MarketRegimeType.TRENDING_BULLISH.value, 
                                          MarketRegimeType.TRENDING_BEARISH.value]:
                        regime[date] = MarketRegimeType.TRANSITIONING.value
            
            # Mean-reverting (Hurst < 0.4) and not strong trend
            elif (hurst < 0.4 and trend_strength < self.trend_strength_threshold):
                if volatility > self.volatility_threshold:
                    regime[date] = MarketRegimeType.RANGING_HIGH_VOL.value
                else:
                    regime[date] = MarketRegimeType.RANGING_LOW_VOL.value
        
        # Create metrics dictionary
        metrics = {
            'hurst': data['Hurst'],
            'volatility': data['Volatility'],
            'trend_strength': data['TrendStrength']
        }
        
        return regime, metrics
