#!/usr/bin/env python3
"""
Feature Builder Module
Engineers features from raw market data for regime prediction
Implements 30+ technical and market structure features
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import glob
import sqlite3
from typing import Dict, List, Optional, Tuple

# Setup logging
log_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/feature_builder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FeatureBuilder:
    """
    Builds features for market regime prediction
    Categories:
    1. Price-based features (returns, volatility)
    2. Technical indicators (RSI, MACD, Bollinger Bands)
    3. Market breadth features
    4. Volume features
    5. Regime transition features
    """
    
    def __init__(self):
        self.base_path = '/Users/maverick/PycharmProjects/India-TS/Daily'
        self.data_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data'
        
        # Feature configuration
        self.feature_config = {
            'price_features': {
                'returns': [1, 5, 10, 20],  # periods for returns
                'volatility': [5, 10, 20],   # periods for volatility
                'price_position': [20, 50]    # MA periods for price position
            },
            'technical_features': {
                'rsi_periods': [14, 21],
                'macd': {'fast': 12, 'slow': 26, 'signal': 9},
                'bb_period': 20,
                'sma_periods': [20, 50, 200],
                'ema_periods': [12, 26]
            },
            'breadth_features': {
                'advance_decline': True,
                'high_low': True,
                'sector_rotation': True
            }
        }
        
        # Track feature names for consistency
        self.feature_names = []
        
    def load_raw_data(self, date: Optional[str] = None) -> Dict:
        """
        Load raw data from ingested files
        """
        logger.info(f"Loading raw data for {date or 'latest'}")
        
        try:
            # Find latest unified data file
            if date:
                pattern = f"{self.data_path}/raw/unified_data_{date}*.json"
            else:
                pattern = f"{self.data_path}/raw/unified_data_*.json"
            
            files = glob.glob(pattern)
            if not files:
                logger.error(f"No data files found matching {pattern}")
                return None
            
            latest_file = max(files, key=os.path.getmtime)
            
            with open(latest_file, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded data from {latest_file}")
            return data
            
        except Exception as e:
            logger.error(f"Error loading raw data: {e}")
            return None
    
    def load_price_data(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        Load historical price data for a ticker
        """
        try:
            # Try to load from existing scanner results with price data
            # For now, we'll create sample data - in production, this would
            # connect to your data source
            
            # Check if we have cached price data
            cache_file = f"{self.data_path}/price_cache/{ticker}_{days}d.parquet"
            if os.path.exists(cache_file):
                df = pd.read_parquet(cache_file)
                logger.info(f"Loaded cached price data for {ticker}")
                return df
            
            # If not cached, we would fetch from API/database
            # For now, return empty DataFrame
            logger.warning(f"No price data available for {ticker}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error loading price data for {ticker}: {e}")
            return pd.DataFrame()
    
    def calculate_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate price-based features
        """
        features = pd.DataFrame(index=df.index)
        
        try:
            # Returns
            for period in self.feature_config['price_features']['returns']:
                features[f'return_{period}d'] = df['close'].pct_change(period)
                features[f'log_return_{period}d'] = np.log(df['close'] / df['close'].shift(period))
            
            # Volatility (rolling std of returns)
            returns = df['close'].pct_change()
            for period in self.feature_config['price_features']['volatility']:
                features[f'volatility_{period}d'] = returns.rolling(window=period).std()
                features[f'volatility_ratio_{period}d'] = (
                    features[f'volatility_{period}d'] / features[f'volatility_{period}d'].rolling(window=period).mean()
                )
            
            # Price position relative to moving averages
            for period in self.feature_config['price_features']['price_position']:
                ma = df['close'].rolling(window=period).mean()
                features[f'price_to_ma{period}'] = df['close'] / ma - 1
                features[f'above_ma{period}'] = (df['close'] > ma).astype(int)
            
            # Price momentum
            features['momentum_5d'] = df['close'] / df['close'].shift(5) - 1
            features['momentum_20d'] = df['close'] / df['close'].shift(20) - 1
            
            # High-Low spread
            if 'high' in df.columns and 'low' in df.columns:
                features['hl_spread'] = (df['high'] - df['low']) / df['close']
                features['hl_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
            
            logger.info(f"Calculated {len(features.columns)} price features")
            
        except Exception as e:
            logger.error(f"Error calculating price features: {e}")
        
        return features
    
    def calculate_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicator features
        """
        features = pd.DataFrame(index=df.index)
        
        try:
            # RSI (Relative Strength Index)
            for period in self.feature_config['technical_features']['rsi_periods']:
                features[f'rsi_{period}'] = self._calculate_rsi(df['close'], period)
                features[f'rsi_{period}_oversold'] = (features[f'rsi_{period}'] < 30).astype(int)
                features[f'rsi_{period}_overbought'] = (features[f'rsi_{period}'] > 70).astype(int)
            
            # MACD
            macd_config = self.feature_config['technical_features']['macd']
            exp1 = df['close'].ewm(span=macd_config['fast'], adjust=False).mean()
            exp2 = df['close'].ewm(span=macd_config['slow'], adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=macd_config['signal'], adjust=False).mean()
            
            features['macd'] = macd
            features['macd_signal'] = signal
            features['macd_histogram'] = macd - signal
            features['macd_crossover'] = ((macd > signal) & (macd.shift(1) <= signal.shift(1))).astype(int)
            
            # Bollinger Bands
            bb_period = self.feature_config['technical_features']['bb_period']
            bb_ma = df['close'].rolling(window=bb_period).mean()
            bb_std = df['close'].rolling(window=bb_period).std()
            
            features['bb_upper'] = bb_ma + (2 * bb_std)
            features['bb_lower'] = bb_ma - (2 * bb_std)
            features['bb_position'] = (df['close'] - bb_lower) / (features['bb_upper'] - bb_lower)
            features['bb_squeeze'] = (features['bb_upper'] - bb_lower) / bb_ma
            
            # Moving Averages
            for period in self.feature_config['technical_features']['sma_periods']:
                sma = df['close'].rolling(window=period).mean()
                features[f'sma_{period}'] = sma
                features[f'sma_{period}_slope'] = sma.diff(5) / sma.shift(5)
            
            # EMA
            for period in self.feature_config['technical_features']['ema_periods']:
                ema = df['close'].ewm(span=period, adjust=False).mean()
                features[f'ema_{period}'] = ema
                features[f'ema_{period}_slope'] = ema.diff(5) / ema.shift(5)
            
            # Volume features (if available)
            if 'volume' in df.columns:
                features['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
                features['volume_trend'] = df['volume'].rolling(window=5).mean().diff()
                features['price_volume_corr'] = (
                    df['close'].pct_change().rolling(window=20)
                    .corr(df['volume'].pct_change())
                )
            
            logger.info(f"Calculated {len(features.columns)} technical features")
            
        except Exception as e:
            logger.error(f"Error calculating technical features: {e}")
        
        return features
    
    def calculate_breadth_features(self, market_data: Dict) -> Dict:
        """
        Calculate market breadth features from scanner data
        """
        features = {}
        
        try:
            if 'market_breadth' in market_data:
                breadth = market_data['market_breadth']
                
                # Direct breadth metrics
                features['long_short_ratio'] = breadth.get('long_short_ratio', 0)
                features['bullish_percent'] = breadth.get('bullish_percent', 0)
                features['long_stocks_count'] = breadth.get('long_stocks', 0)
                features['short_stocks_count'] = breadth.get('short_stocks', 0)
                
                # Derived metrics
                total_stocks = features['long_stocks_count'] + features['short_stocks_count']
                features['breadth_thrust'] = features['long_stocks_count'] / max(total_stocks, 1)
                
                # Market sentiment encoding
                sentiment_map = {'bullish': 1, 'bearish': -1, 'neutral': 0}
                features['market_sentiment_score'] = sentiment_map.get(
                    breadth.get('market_sentiment', 'neutral'), 0
                )
                
                # Breadth momentum (would need historical data)
                features['breadth_momentum'] = 0  # Placeholder for breadth change
                
            # Scanner diversity
            if 'scanner_summary' in market_data:
                features['active_scanners'] = market_data['scanner_summary'].get('total_scanners', 0)
            
            # Calculate regime-like features from scanner data instead of old predictor
            # This makes the system independent of the old ML model
            # First check the actual scanner data from ingestion
            scanner_data = None
            if 'scanner_summary' in market_data:
                # Extract scanner counts from summary
                summary = market_data['scanner_summary']
                scanner_data = {
                    'long_count': summary.get('long_stocks', 0),
                    'short_count': summary.get('short_stocks', 0)
                }
            
            if scanner_data:
                
                # Calculate regime features from scanner signals
                long_count = scanner_data.get('long_count', 0)
                short_count = scanner_data.get('short_count', 0)
                total_signals = long_count + short_count
                
                # Estimate regime concentration from signal distribution
                if total_signals > 0:
                    long_ratio = long_count / total_signals
                    short_ratio = short_count / total_signals
                    
                    # Use signal ratio to estimate regime entropy
                    if long_ratio > 0 and short_ratio > 0:
                        features['regime_entropy'] = -(long_ratio * np.log(long_ratio + 1e-10) + 
                                                      short_ratio * np.log(short_ratio + 1e-10))
                    else:
                        features['regime_entropy'] = 0
                    
                    features['regime_concentration'] = max(long_ratio, short_ratio)
                    
                    # Estimate regime counts based on signal strength
                    if long_ratio > 0.7:
                        features['bullish_regime_count'] = 3
                        features['bearish_regime_count'] = 0
                    elif long_ratio > 0.5:
                        features['bullish_regime_count'] = 2
                        features['bearish_regime_count'] = 1
                    elif long_ratio > 0.3:
                        features['bullish_regime_count'] = 1
                        features['bearish_regime_count'] = 1
                    elif long_ratio > 0.1:
                        features['bullish_regime_count'] = 1
                        features['bearish_regime_count'] = 2
                    else:
                        features['bullish_regime_count'] = 0
                        features['bearish_regime_count'] = 3
                    
                    features['neutral_regime_count'] = 1 if 0.4 <= long_ratio <= 0.6 else 0
                else:
                    # No signals - neutral market
                    features['regime_entropy'] = 0
                    features['regime_concentration'] = 0
                    features['bullish_regime_count'] = 0
                    features['bearish_regime_count'] = 0
                    features['neutral_regime_count'] = 1
                
                # Calculate market score from breadth
                if 'market_breadth' in market_data:
                    breadth = market_data['market_breadth']
                    # Market score: -1 (bearish) to +1 (bullish)
                    features['market_score_mean'] = (breadth.get('bullish_percent', 50) - 50) / 50
                    features['market_score_std'] = 0.2  # Default std
                    features['market_score_range'] = abs(features['market_score_mean'])
                else:
                    features['market_score_mean'] = 0
                    features['market_score_std'] = 0
                    features['market_score_range'] = 0
            
            logger.info(f"Calculated {len(features)} breadth features")
            
        except Exception as e:
            logger.error(f"Error calculating breadth features: {e}")
        
        return features
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def build_feature_vector(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        Build complete feature vector for a given date
        """
        logger.info("Building complete feature vector")
        
        try:
            # Load raw data
            raw_data = self.load_raw_data(date)
            if not raw_data:
                logger.error("No raw data available")
                return None
            
            # Initialize feature dictionary
            all_features = {}
            
            # Add breadth features
            breadth_features = self.calculate_breadth_features(raw_data)
            all_features.update(breadth_features)
            
            # Add timestamp features
            timestamp = pd.to_datetime(raw_data['timestamp'])
            all_features['hour'] = timestamp.hour
            all_features['day_of_week'] = timestamp.dayofweek
            all_features['day_of_month'] = timestamp.day
            all_features['month'] = timestamp.month
            
            # Time since market open (in minutes)
            market_open = timestamp.replace(hour=9, minute=15)
            if timestamp >= market_open:
                all_features['minutes_since_open'] = (timestamp - market_open).total_seconds() / 60
            else:
                all_features['minutes_since_open'] = 0
            
            # Create DataFrame
            features_df = pd.DataFrame([all_features])
            
            # Store feature names for consistency
            self.feature_names = list(features_df.columns)
            
            # Add metadata
            features_df['timestamp'] = timestamp
            features_df['data_quality'] = self._assess_data_quality(all_features)
            
            logger.info(f"Built feature vector with {len(self.feature_names)} features")
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error building feature vector: {e}")
            return None
    
    def _assess_data_quality(self, features: Dict) -> float:
        """
        Assess quality of feature data (0-1 score)
        """
        try:
            # Count non-null features
            non_null = sum(1 for v in features.values() if v is not None and not pd.isna(v))
            total = len(features)
            
            # Check for extreme values
            numeric_features = [v for v in features.values() if isinstance(v, (int, float))]
            if numeric_features:
                has_extreme = any(abs(v) > 1000 for v in numeric_features if not pd.isna(v))
                if has_extreme:
                    return 0.5  # Penalize extreme values
            
            return non_null / total if total > 0 else 0
            
        except:
            return 0.5
    
    def save_features(self, features_df: pd.DataFrame, version: str = None):
        """
        Save features to feature store
        """
        try:
            # Create feature store directory
            feature_store_path = f"{self.data_path}/features"
            os.makedirs(feature_store_path, exist_ok=True)
            
            # Generate version if not provided
            if version is None:
                version = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save as parquet for efficiency
            output_file = f"{feature_store_path}/features_v{version}.parquet"
            features_df.to_parquet(output_file)
            
            # Save feature metadata
            metadata = {
                'version': version,
                'timestamp': datetime.now().isoformat(),
                'feature_count': len(self.feature_names),
                'feature_names': self.feature_names,
                'data_quality': features_df['data_quality'].mean() if 'data_quality' in features_df else None
            }
            
            metadata_file = f"{feature_store_path}/features_v{version}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved features to {output_file}")
            
            # Update latest symlink
            latest_link = f"{feature_store_path}/features_latest.parquet"
            if os.path.exists(latest_link):
                os.remove(latest_link)
            os.symlink(output_file, latest_link)
            
            return output_file
            
        except Exception as e:
            logger.error(f"Error saving features: {e}")
            return None


def main():
    """
    Test feature builder
    """
    builder = FeatureBuilder()
    
    # Build features from latest data
    features = builder.build_feature_vector()
    
    if features is not None:
        print("\n" + "=" * 50)
        print("Feature Engineering Summary:")
        print("=" * 50)
        
        print(f"Total features: {len(builder.feature_names)}")
        print(f"Timestamp: {features['timestamp'].iloc[0]}")
        print(f"Data quality: {features['data_quality'].iloc[0]:.2%}")
        
        print("\nSample features:")
        for col in features.columns[:10]:
            if col not in ['timestamp', 'data_quality']:
                value = features[col].iloc[0]
                if isinstance(value, float):
                    print(f"  {col}: {value:.4f}")
                else:
                    print(f"  {col}: {value}")
        
        # Save features
        saved_file = builder.save_features(features)
        if saved_file:
            print(f"\n✅ Features saved to: {saved_file}")
    else:
        print("❌ Failed to build features")


if __name__ == "__main__":
    main()