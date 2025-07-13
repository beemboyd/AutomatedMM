#!/usr/bin/env python3
"""
Feature Engineering Pipeline for Market Regime Detection

This module creates a comprehensive feature pipeline that combines technical,
statistical, and market microstructure features for regime clustering.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

# Try to import talib, but provide fallback implementations
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    logging.warning("TA-Lib not installed. Using fallback implementations for technical indicators.")

logger = logging.getLogger(__name__)

class FeaturePipeline:
    """
    Comprehensive feature engineering pipeline for market regime detection.
    """
    
    def __init__(self, config=None):
        """
        Initialize the feature pipeline.
        
        Args:
            config (dict): Configuration parameters for feature calculation
        """
        self.config = config or self._get_default_config()
        
    def _get_default_config(self) -> Dict:
        """Get default configuration for feature calculation"""
        return {
            'returns_periods': [1, 5, 10, 20],
            'ma_periods': [10, 20, 50, 100, 200],
            'volatility_windows': [10, 20, 50],
            'rsi_periods': [14, 21, 28],
            'bb_periods': [20],
            'atr_periods': [14, 20],
            'volume_ma_periods': [10, 20, 50],
            'correlation_windows': [20, 50],
            'regime_lookback': 252  # One year for regime analysis
        }
    
    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create comprehensive feature set from OHLCV data.
        
        Args:
            data (pd.DataFrame): OHLCV data with columns [Open, High, Low, Close, Volume]
            
        Returns:
            pd.DataFrame: Feature matrix
        """
        features = pd.DataFrame(index=data.index)
        
        # 1. Price-based features
        price_features = self._create_price_features(data)
        features = pd.concat([features, price_features], axis=1)
        
        # 2. Return-based features
        return_features = self._create_return_features(data)
        features = pd.concat([features, return_features], axis=1)
        
        # 3. Volatility features
        volatility_features = self._create_volatility_features(data)
        features = pd.concat([features, volatility_features], axis=1)
        
        # 4. Technical indicators
        technical_features = self._create_technical_features(data)
        features = pd.concat([features, technical_features], axis=1)
        
        # 5. Volume features
        volume_features = self._create_volume_features(data)
        features = pd.concat([features, volume_features], axis=1)
        
        # 6. Market microstructure features
        microstructure_features = self._create_microstructure_features(data)
        features = pd.concat([features, microstructure_features], axis=1)
        
        # 7. Statistical features
        statistical_features = self._create_statistical_features(data, features)
        features = pd.concat([features, statistical_features], axis=1)
        
        # 8. Regime transition features
        regime_features = self._create_regime_transition_features(features)
        features = pd.concat([features, regime_features], axis=1)
        
        return features
    
    def _create_price_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create price-based features"""
        features = pd.DataFrame(index=data.index)
        
        # Moving averages
        for period in self.config['ma_periods']:
            features[f'sma_{period}'] = data['Close'].rolling(period).mean()
            features[f'ema_{period}'] = data['Close'].ewm(span=period, adjust=False).mean()
            features[f'price_to_sma_{period}'] = data['Close'] / features[f'sma_{period}']
            features[f'price_to_ema_{period}'] = data['Close'] / features[f'ema_{period}']
        
        # Moving average crossovers
        features['golden_cross'] = (features['sma_50'] > features['sma_200']).astype(int)
        features['death_cross'] = (features['sma_50'] < features['sma_200']).astype(int)
        
        # Price position relative to range
        for period in [20, 50, 100]:
            high_period = data['High'].rolling(period).max()
            low_period = data['Low'].rolling(period).min()
            features[f'price_position_{period}'] = (data['Close'] - low_period) / (high_period - low_period)
        
        # Trend strength using linear regression
        for period in self.config['ma_periods']:
            features[f'trend_slope_{period}'] = self._calculate_trend_slope(data['Close'], period)
        
        return features
    
    def _create_return_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create return-based features"""
        features = pd.DataFrame(index=data.index)
        
        # Simple returns
        for period in self.config['returns_periods']:
            features[f'return_{period}d'] = data['Close'].pct_change(periods=period)
            features[f'log_return_{period}d'] = np.log(data['Close'] / data['Close'].shift(period))
        
        # Cumulative returns
        features['cum_return_20d'] = (1 + features['return_1d']).rolling(20).apply(lambda x: x.prod() - 1)
        features['cum_return_50d'] = (1 + features['return_1d']).rolling(50).apply(lambda x: x.prod() - 1)
        
        # Return momentum
        features['return_momentum'] = features['return_5d'] - features['return_20d']
        
        return features
    
    def _create_volatility_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create volatility features"""
        features = pd.DataFrame(index=data.index)
        
        # Historical volatility
        returns = data['Close'].pct_change()
        for window in self.config['volatility_windows']:
            features[f'hist_vol_{window}d'] = returns.rolling(window).std() * np.sqrt(252)
        
        # Parkinson volatility (using high-low range)
        for window in self.config['volatility_windows']:
            hl_ratio = np.log(data['High'] / data['Low'])
            features[f'parkinson_vol_{window}d'] = np.sqrt(
                hl_ratio.rolling(window).apply(lambda x: np.sum(x**2) / (4 * len(x) * np.log(2)))
            ) * np.sqrt(252)
        
        # Garman-Klass volatility
        log_hl = np.log(data['High'] / data['Low'])
        log_co = np.log(data['Close'] / data['Open'])
        
        for window in self.config['volatility_windows']:
            rs = 0.5 * log_hl**2 - (2*np.log(2)-1) * log_co**2
            features[f'gk_vol_{window}d'] = np.sqrt(rs.rolling(window).mean() * 252)
        
        # Volatility of volatility
        features['vol_of_vol'] = features['hist_vol_20d'].rolling(20).std()
        
        # Volatility regime
        features['vol_percentile'] = features['hist_vol_20d'].rolling(252).rank(pct=True)
        
        return features
    
    def _create_technical_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicator features"""
        features = pd.DataFrame(index=data.index)
        
        # RSI
        for period in self.config['rsi_periods']:
            if HAS_TALIB:
                features[f'rsi_{period}'] = talib.RSI(data['Close'].values, timeperiod=period)
            else:
                features[f'rsi_{period}'] = self._calculate_rsi(data['Close'], period)
        
        # MACD
        if HAS_TALIB:
            macd, macd_signal, macd_hist = talib.MACD(data['Close'].values)
            features['macd'] = macd
            features['macd_signal'] = macd_signal
            features['macd_histogram'] = macd_hist
        else:
            # Simple MACD implementation
            ema12 = data['Close'].ewm(span=12, adjust=False).mean()
            ema26 = data['Close'].ewm(span=26, adjust=False).mean()
            features['macd'] = ema12 - ema26
            features['macd_signal'] = features['macd'].ewm(span=9, adjust=False).mean()
            features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # Bollinger Bands
        for period in self.config['bb_periods']:
            if HAS_TALIB:
                upper, middle, lower = talib.BBANDS(data['Close'].values, timeperiod=period)
            else:
                middle = data['Close'].rolling(period).mean()
                std = data['Close'].rolling(period).std()
                upper = middle + (2 * std)
                lower = middle - (2 * std)
            
            features[f'bb_upper_{period}'] = upper
            features[f'bb_middle_{period}'] = middle
            features[f'bb_lower_{period}'] = lower
            features[f'bb_width_{period}'] = (upper - lower) / middle
            features[f'bb_position_{period}'] = (data['Close'] - lower) / (upper - lower)
        
        # ATR
        for period in self.config['atr_periods']:
            if HAS_TALIB:
                features[f'atr_{period}'] = talib.ATR(data['High'].values, data['Low'].values, 
                                                      data['Close'].values, timeperiod=period)
            else:
                features[f'atr_{period}'] = self._calculate_atr(data, period)
            features[f'atr_ratio_{period}'] = features[f'atr_{period}'] / data['Close']
        
        # Stochastic
        if HAS_TALIB:
            slowk, slowd = talib.STOCH(data['High'].values, data['Low'].values, data['Close'].values)
            features['stoch_k'] = slowk
            features['stoch_d'] = slowd
        else:
            # Simple stochastic implementation
            low_min = data['Low'].rolling(14).min()
            high_max = data['High'].rolling(14).max()
            features['stoch_k'] = 100 * ((data['Close'] - low_min) / (high_max - low_min))
            features['stoch_d'] = features['stoch_k'].rolling(3).mean()
        
        # ADX - simplified version without talib
        features['adx'] = 50  # Placeholder - full implementation would be complex
        
        # CCI - simplified version
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        sma = typical_price.rolling(20).mean()
        mad = typical_price.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())))
        features['cci'] = (typical_price - sma) / (0.015 * mad)
        
        return features
    
    def _create_volume_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create volume-based features"""
        features = pd.DataFrame(index=data.index)
        
        # Volume moving averages
        for period in self.config['volume_ma_periods']:
            features[f'volume_sma_{period}'] = data['Volume'].rolling(period).mean()
            features[f'volume_ratio_{period}'] = data['Volume'] / features[f'volume_sma_{period}']
        
        # On-Balance Volume
        if HAS_TALIB:
            features['obv'] = talib.OBV(data['Close'].values, data['Volume'].values.astype(float))
        else:
            # Simple OBV implementation
            obv = [0]
            for i in range(1, len(data)):
                if data['Close'].iloc[i] > data['Close'].iloc[i-1]:
                    obv.append(obv[-1] + data['Volume'].iloc[i])
                elif data['Close'].iloc[i] < data['Close'].iloc[i-1]:
                    obv.append(obv[-1] - data['Volume'].iloc[i])
                else:
                    obv.append(obv[-1])
            features['obv'] = pd.Series(obv, index=data.index)
        
        # Volume-Price Trend
        features['vpt'] = (data['Close'].pct_change() * data['Volume']).cumsum()
        
        # Money Flow Index - simplified version
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        money_flow = typical_price * data['Volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(14).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(14).sum()
        money_ratio = positive_flow / negative_flow
        features['mfi'] = 100 - (100 / (1 + money_ratio))
        
        # Volume-weighted average price
        features['vwap'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close']) / 3).cumsum() / data['Volume'].cumsum()
        features['price_to_vwap'] = data['Close'] / features['vwap']
        
        # Volume volatility
        features['volume_volatility'] = data['Volume'].pct_change().rolling(20).std()
        
        return features
    
    def _create_microstructure_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create market microstructure features"""
        features = pd.DataFrame(index=data.index)
        
        # Spread metrics
        features['spread'] = (data['High'] - data['Low']) / data['Close']
        features['spread_ma'] = features['spread'].rolling(20).mean()
        features['relative_spread'] = features['spread'] / features['spread_ma']
        
        # Intraday volatility
        features['intraday_vol'] = (data['High'] - data['Low']) / data['Open']
        
        # Close position in daily range
        features['close_position'] = (data['Close'] - data['Low']) / (data['High'] - data['Low'])
        
        # Gap analysis
        features['gap'] = (data['Open'] - data['Close'].shift(1)) / data['Close'].shift(1)
        features['gap_ma'] = features['gap'].rolling(20).mean()
        
        # Efficiency ratio (trend efficiency)
        net_change = abs(data['Close'] - data['Close'].shift(20))
        sum_abs_changes = data['Close'].diff().abs().rolling(20).sum()
        features['efficiency_ratio'] = net_change / sum_abs_changes
        
        return features
    
    def _create_statistical_features(self, data: pd.DataFrame, existing_features: pd.DataFrame) -> pd.DataFrame:
        """Create statistical features"""
        features = pd.DataFrame(index=data.index)
        
        returns = data['Close'].pct_change()
        
        # Distribution moments
        for window in [20, 50]:
            features[f'skewness_{window}d'] = returns.rolling(window).skew()
            features[f'kurtosis_{window}d'] = returns.rolling(window).kurt()
        
        # Autocorrelation
        for lag in [1, 5, 10]:
            features[f'autocorr_lag_{lag}'] = returns.rolling(20).apply(
                lambda x: x.autocorr(lag=lag) if len(x) >= lag + 1 else np.nan
            )
        
        # Hurst exponent
        features['hurst_exponent'] = self._calculate_hurst_exponent(data['Close'])
        
        # Correlation between price and volume
        for window in self.config['correlation_windows']:
            features[f'price_volume_corr_{window}d'] = returns.rolling(window).corr(
                data['Volume'].pct_change()
            )
        
        # Feature correlations (regime stability indicator)
        if 'hist_vol_20d' in existing_features.columns and 'return_1d' in existing_features.columns:
            features['return_vol_corr'] = existing_features['return_1d'].rolling(50).corr(
                existing_features['hist_vol_20d']
            )
        
        return features
    
    def _create_regime_transition_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Create features that help identify regime transitions"""
        transition_features = pd.DataFrame(index=features.index)
        
        # Volatility regime changes
        if 'hist_vol_20d' in features.columns:
            transition_features['vol_regime_change'] = features['hist_vol_20d'].pct_change(periods=20)
            transition_features['vol_acceleration'] = transition_features['vol_regime_change'].diff()
        
        # Trend regime changes
        if 'trend_slope_50' in features.columns:
            transition_features['trend_change'] = features['trend_slope_50'].diff(periods=20)
            transition_features['trend_reversal'] = (
                features['trend_slope_50'] * features['trend_slope_50'].shift(20) < 0
            ).astype(int)
        
        # Moving average convergence/divergence
        if 'sma_20' in features.columns and 'sma_50' in features.columns:
            ma_diff = features['sma_20'] - features['sma_50']
            transition_features['ma_convergence'] = ma_diff.diff().abs()
        
        # Volatility vs return regime
        if 'return_5d' in features.columns and 'hist_vol_20d' in features.columns:
            transition_features['sharpe_20d'] = (
                features['return_5d'].rolling(20).mean() / 
                features['hist_vol_20d']
            )
            transition_features['sharpe_change'] = transition_features['sharpe_20d'].pct_change(periods=20)
        
        return transition_features
    
    def _calculate_trend_slope(self, prices: pd.Series, window: int) -> pd.Series:
        """Calculate trend slope using linear regression"""
        def slope(ts):
            if len(ts) < 2:
                return np.nan
            x = np.arange(len(ts))
            m, _ = np.polyfit(x, ts, 1)
            return m / ts.iloc[-1] * 100  # Percentage slope
        
        return prices.rolling(window).apply(slope)
    
    def _calculate_hurst_exponent(self, prices: pd.Series, window: int = 100) -> pd.Series:
        """Calculate rolling Hurst exponent"""
        def hurst(ts):
            if len(ts) < 20:
                return np.nan
            
            # Create range of lags
            lags = range(2, min(20, len(ts)//2))
            
            # Calculate the array of the variances of the lagged differences
            tau = []
            for lag in lags:
                diff = np.subtract(ts[lag:], ts[:-lag])
                tau.append(np.sqrt(np.std(diff)))
            
            # Use a linear fit to estimate the Hurst Exponent
            if len(tau) > 0:
                poly = np.polyfit(np.log(lags), np.log(tau), 1)
                return poly[0]
            return np.nan
        
        return prices.rolling(window).apply(lambda x: hurst(x.values))
    
    def select_features(self, features: pd.DataFrame, method: str = 'variance', 
                       n_features: int = 50) -> List[str]:
        """
        Select most important features using various methods.
        
        Args:
            features (pd.DataFrame): Feature matrix
            method (str): Feature selection method ('variance', 'correlation', 'mutual_info')
            n_features (int): Number of features to select
            
        Returns:
            List[str]: Selected feature names
        """
        try:
            from sklearn.feature_selection import VarianceThreshold, mutual_info_regression
        except ImportError:
            logger.warning("sklearn not available for feature selection")
            # Simple variance-based selection
            variances = features_clean.var()
            selected_features = variances.nlargest(n_features).index.tolist()
            return selected_features
        
        # Remove NaN values
        features_clean = features.dropna()
        
        if method == 'variance':
            # Select features with highest variance
            selector = VarianceThreshold()
            selector.fit(features_clean)
            variances = selector.variances_
            
            # Get indices of top n_features by variance
            top_indices = np.argsort(variances)[-n_features:]
            selected_features = features_clean.columns[top_indices].tolist()
            
        elif method == 'correlation':
            # Remove highly correlated features
            corr_matrix = features_clean.corr().abs()
            upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
            
            # Find features with correlation greater than 0.95
            to_drop = [column for column in upper.columns if any(upper[column] > 0.95)]
            selected_features = [f for f in features_clean.columns if f not in to_drop]
            
            # If still too many, select by variance
            if len(selected_features) > n_features:
                features_subset = features_clean[selected_features]
                variances = features_subset.var()
                selected_features = variances.nlargest(n_features).index.tolist()
        
        elif method == 'mutual_info':
            # Use mutual information with returns as target
            if 'return_1d' in features_clean.columns:
                X = features_clean.drop(['return_1d'], axis=1)
                y = features_clean['return_1d'].shift(-1).dropna()
                X = X[:-1]  # Align with shifted y
                
                mi_scores = mutual_info_regression(X, y)
                
                # Get indices of top n_features
                top_indices = np.argsort(mi_scores)[-n_features:]
                selected_features = X.columns[top_indices].tolist()
            else:
                # Fallback to variance method
                return self.select_features(features, method='variance', n_features=n_features)
        
        else:
            raise ValueError(f"Unknown feature selection method: {method}")
        
        logger.info(f"Selected {len(selected_features)} features using {method} method")
        
        return selected_features
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14):
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14):
        """Calculate Average True Range"""
        high = data['High']
        low = data['Low']
        close = data['Close']
        close_prev = close.shift(1)
        
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        true_range = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        
        # Calculate ATR
        atr = true_range.rolling(window=period).mean()
        
        return atr