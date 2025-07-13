"""
Market Indicators Module

Calculates various market indicators used for regime detection.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
import json
import os
import sqlite3
from .volatility_scorer import calculate_volatility_score_from_scanner

class MarketIndicators:
    """Calculate market indicators for regime detection"""
    
    def __init__(self, config_path: str = None):
        """Initialize with configuration"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'config', 'regime_config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.indicators_config = self.config['indicators']
        self.lookback = self.config['lookback_periods']
        self.logger = logging.getLogger(__name__)
        
    def calculate_all_indicators(self, market_data: pd.DataFrame, scanner_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        Calculate all market indicators
        
        Args:
            market_data: DataFrame with OHLCV data
            scanner_data: Optional DataFrame with scanner results for enhanced volatility
            
        Returns:
            Dictionary of indicator values
        """
        indicators = {}
        
        # Price Action Indicators
        price_indicators = self.calculate_price_action_indicators(market_data)
        indicators.update(price_indicators)
        
        # Volatility Indicators (now with scanner data support)
        volatility_indicators = self.calculate_volatility_indicators(market_data, scanner_data)
        indicators.update(volatility_indicators)
        
        # Market Breadth Indicators
        breadth_indicators = self.calculate_breadth_indicators(market_data)
        indicators.update(breadth_indicators)
        
        # Momentum Indicators
        momentum_indicators = self.calculate_momentum_indicators(market_data)
        indicators.update(momentum_indicators)
        
        # Composite Scores
        composite_scores = self.calculate_composite_scores(indicators)
        indicators.update(composite_scores)
        
        # Add trend score from database/files as a separate field
        db_trend_score = self.get_trend_score_from_db()
        if db_trend_score is not None:
            indicators['reversal_trend_score'] = db_trend_score
            # If we don't have a calculated trend_score, use normalized db value
            if 'trend_score' not in indicators:
                indicators['trend_score'] = np.clip(db_trend_score / 10, -1, 1)
        
        return indicators
    
    def calculate_price_action_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate price action based indicators"""
        indicators = {}
        
        try:
            close_prices = data['close'].values
            
            # Moving Averages
            for period in self.indicators_config['price_action']['sma_periods']:
                if len(close_prices) >= period:
                    sma = np.mean(close_prices[-period:])
                    indicators[f'sma_{period}'] = sma
                    indicators[f'price_to_sma_{period}'] = close_prices[-1] / sma - 1
            
            # Trend Strength
            if len(close_prices) >= 20:
                indicators['trend_strength'] = self._calculate_trend_strength(close_prices)
            
            # Support/Resistance levels
            if len(data) >= 20:
                indicators['distance_to_resistance'] = self._calculate_sr_distance(data, 'resistance')
                indicators['distance_to_support'] = self._calculate_sr_distance(data, 'support')
            
            # Price patterns
            if len(data) >= 10:
                indicators['higher_highs'] = self._count_higher_highs(data)
                indicators['lower_lows'] = self._count_lower_lows(data)
            
        except Exception as e:
            self.logger.error(f"Error calculating price indicators: {e}")
            
        return indicators
    
    def calculate_volatility_indicators(self, data: pd.DataFrame, scanner_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """Calculate volatility indicators, using scanner data when available"""
        indicators = {}
        
        try:
            # First calculate NIFTY-based volatility indicators
            # ATR
            atr_period = self.indicators_config['volatility']['atr_period']
            if len(data) >= atr_period:
                indicators['atr'] = self._calculate_atr(data, atr_period)
                indicators['atr_percent'] = indicators['atr'] / data['close'].iloc[-1] * 100
            
            # Bollinger Bands
            bb_period = self.indicators_config['volatility']['bollinger_period']
            bb_std = self.indicators_config['volatility']['bollinger_std']
            if len(data) >= bb_period:
                bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
                    data['close'].values, bb_period, bb_std
                )
                indicators['bb_width'] = (bb_upper - bb_lower) / bb_middle
                indicators['bb_position'] = (data['close'].iloc[-1] - bb_lower) / (bb_upper - bb_lower)
            
            # Historical Volatility
            if len(data) >= 20:
                indicators['hist_volatility'] = self._calculate_historical_volatility(data['close'].values)
            
            # If scanner data is available, use it for enhanced volatility scoring
            if scanner_data is not None and not scanner_data.empty:
                scanner_vol_analysis = calculate_volatility_score_from_scanner(scanner_data)
                
                # Override volatility score with scanner-based calculation
                if 'market_volatility' in scanner_vol_analysis:
                    market_vol = scanner_vol_analysis['market_volatility']
                    
                    # Use scanner-based volatility score
                    indicators['scanner_volatility_score'] = market_vol.get('volatility_score', 50.0) / 100.0
                    indicators['scanner_volatility_regime'] = market_vol.get('volatility_regime', 'normal')
                    
                    # Add additional scanner volatility metrics
                    if 'avg_atr_percent' in market_vol:
                        indicators['scanner_avg_atr_percent'] = market_vol['avg_atr_percent']
                    if 'high_volatility_percent' in market_vol:
                        indicators['scanner_high_vol_prevalence'] = market_vol['high_volatility_percent']
                    if 'avg_volume_ratio' in market_vol:
                        indicators['scanner_volume_expansion'] = market_vol['avg_volume_ratio']
                    
                    # Store sector volatility for reference
                    if 'sector_volatility' in scanner_vol_analysis:
                        indicators['sector_volatility'] = scanner_vol_analysis['sector_volatility']
            
            # Determine final volatility regime (prefer scanner-based if available)
            if 'scanner_volatility_regime' in indicators:
                indicators['volatility_regime'] = indicators['scanner_volatility_regime']
            else:
                indicators['volatility_regime'] = self._classify_volatility_regime(indicators)
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility indicators: {e}")
            
        return indicators
    
    def calculate_breadth_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate market breadth indicators"""
        indicators = {}
        
        try:
            # If we have market breadth data
            if 'advances' in data.columns and 'declines' in data.columns:
                indicators['advance_decline_ratio'] = data['advances'].iloc[-1] / max(data['declines'].iloc[-1], 1)
                indicators['advance_decline_line'] = (data['advances'] - data['declines']).cumsum().iloc[-1]
            
            # If we have high/low data
            if 'new_highs' in data.columns and 'new_lows' in data.columns:
                indicators['high_low_ratio'] = data['new_highs'].iloc[-1] / max(data['new_lows'].iloc[-1], 1)
                indicators['high_low_index'] = (data['new_highs'] - data['new_lows']).rolling(10).mean().iloc[-1]
            
            # Volume indicators
            if 'volume' in data.columns:
                vol_ma = data['volume'].rolling(20).mean().iloc[-1]
                indicators['volume_ratio'] = data['volume'].iloc[-1] / vol_ma
                indicators['volume_trend'] = self._calculate_volume_trend(data)
            
            # Breadth thrust
            if 'advances' in data.columns:
                indicators['breadth_thrust'] = self._calculate_breadth_thrust(data)
            
        except Exception as e:
            self.logger.error(f"Error calculating breadth indicators: {e}")
            
        return indicators
    
    def calculate_momentum_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate momentum indicators"""
        indicators = {}
        
        try:
            close_prices = data['close'].values
            
            # RSI
            rsi_period = self.indicators_config['price_action']['rsi_period']
            if len(close_prices) >= rsi_period + 1:
                indicators['rsi'] = self._calculate_rsi(close_prices, rsi_period)
            
            # Rate of Change
            roc_period = self.indicators_config['momentum']['roc_period']
            if len(close_prices) >= roc_period + 1:
                indicators['roc'] = (close_prices[-1] / close_prices[-roc_period-1] - 1) * 100
            
            # MACD
            if len(close_prices) >= 26:
                macd, signal, histogram = self._calculate_macd(close_prices)
                indicators['macd'] = macd
                indicators['macd_signal'] = signal
                indicators['macd_histogram'] = histogram
            
            # Money Flow Index
            if 'high' in data.columns and 'low' in data.columns and 'volume' in data.columns:
                mfi_period = self.indicators_config['momentum']['mfi_period']
                if len(data) >= mfi_period + 1:
                    indicators['mfi'] = self._calculate_mfi(data, mfi_period)
            
            # Momentum Score
            indicators['momentum_score'] = self._calculate_momentum_score(indicators)
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum indicators: {e}")
            
        return indicators
    
    def calculate_composite_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate composite scores from individual indicators"""
        scores = {}
        
        try:
            # Trend Score (-1 to 1)
            trend_components = []
            if 'trend_strength' in indicators:
                trend_components.append(indicators['trend_strength'])
            if 'price_to_sma_50' in indicators:
                trend_components.append(np.clip(indicators['price_to_sma_50'] * 10, -1, 1))
            if 'higher_highs' in indicators and 'lower_lows' in indicators:
                pattern_score = (indicators['higher_highs'] - indicators['lower_lows']) / 10
                trend_components.append(np.clip(pattern_score, -1, 1))
            
            if trend_components:
                scores['trend_score'] = np.mean(trend_components)
            
            # Momentum Score (-1 to 1)
            momentum_components = []
            if 'rsi' in indicators:
                momentum_components.append((indicators['rsi'] - 50) / 50)
            if 'roc' in indicators:
                momentum_components.append(np.clip(indicators['roc'] / 20, -1, 1))
            if 'momentum_score' in indicators:
                momentum_components.append(indicators['momentum_score'])
            
            if momentum_components:
                scores['momentum_composite'] = np.mean(momentum_components)
            
            # Volatility Score (0 to 1, higher = more volatile)
            # Prefer scanner-based volatility if available
            if 'scanner_volatility_score' in indicators:
                scores['volatility_score'] = indicators['scanner_volatility_score']
            else:
                # Fallback to NIFTY-based volatility
                vol_components = []
                if 'atr_percent' in indicators:
                    vol_components.append(min(indicators['atr_percent'] / 5, 1))
                if 'bb_width' in indicators:
                    vol_components.append(min(indicators['bb_width'] / 0.2, 1))
                if 'hist_volatility' in indicators:
                    vol_components.append(min(indicators['hist_volatility'] / 30, 1))
                
                if vol_components:
                    scores['volatility_score'] = np.mean(vol_components)
            
            # Breadth Score (-1 to 1)
            breadth_components = []
            if 'advance_decline_ratio' in indicators:
                ad_score = np.clip((indicators['advance_decline_ratio'] - 1) / 2, -1, 1)
                breadth_components.append(ad_score)
            if 'breadth_thrust' in indicators:
                breadth_components.append(indicators['breadth_thrust'])
            
            if breadth_components:
                scores['breadth_score'] = np.mean(breadth_components)
            
            # Overall Market Score (-1 to 1)
            all_scores = []
            weights = []
            
            if 'trend_score' in scores:
                all_scores.append(scores['trend_score'])
                weights.append(0.3)
            if 'momentum_composite' in scores:
                all_scores.append(scores['momentum_composite'])
                weights.append(0.3)
            if 'breadth_score' in scores:
                all_scores.append(scores['breadth_score'])
                weights.append(0.2)
            if 'volatility_score' in scores:
                # Inverse volatility contribution (high vol = negative)
                all_scores.append(0.5 - scores['volatility_score'])
                weights.append(0.2)
            
            if all_scores:
                scores['market_score'] = np.average(all_scores, weights=weights[:len(all_scores)])
            
        except Exception as e:
            self.logger.error(f"Error calculating composite scores: {e}")
            
        return scores
    
    # Helper methods
    def _calculate_trend_strength(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate trend strength using linear regression"""
        if len(prices) < period:
            return 0.0
        
        recent_prices = prices[-period:]
        x = np.arange(period)
        
        # Linear regression
        slope, intercept = np.polyfit(x, recent_prices, 1)
        
        # R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((recent_prices - y_pred) ** 2)
        ss_tot = np.sum((recent_prices - np.mean(recent_prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Normalize slope
        normalized_slope = slope / np.mean(recent_prices) * 100
        
        # Trend strength combines slope and R-squared
        trend_strength = np.sign(normalized_slope) * r_squared * min(abs(normalized_slope) / 2, 1)
        
        return np.clip(trend_strength, -1, 1)
    
    def _calculate_sr_distance(self, data: pd.DataFrame, level_type: str) -> float:
        """Calculate distance to support/resistance"""
        current_price = data['close'].iloc[-1]
        
        if level_type == 'resistance':
            # Find recent highs
            highs = data['high'].rolling(window=5).max()
            resistance_levels = highs[highs > current_price * 1.01].dropna()
            if len(resistance_levels) > 0:
                nearest_resistance = resistance_levels.iloc[-1]
                return (nearest_resistance - current_price) / current_price
        else:
            # Find recent lows
            lows = data['low'].rolling(window=5).min()
            support_levels = lows[lows < current_price * 0.99].dropna()
            if len(support_levels) > 0:
                nearest_support = support_levels.iloc[-1]
                return (current_price - nearest_support) / current_price
        
        return 0.0
    
    def _count_higher_highs(self, data: pd.DataFrame, period: int = 10) -> int:
        """Count number of higher highs in recent period"""
        if len(data) < period:
            return 0
        
        recent_data = data.tail(period)
        highs = recent_data['high'].values
        count = 0
        
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                count += 1
                
        return count
    
    def _count_lower_lows(self, data: pd.DataFrame, period: int = 10) -> int:
        """Count number of lower lows in recent period"""
        if len(data) < period:
            return 0
        
        recent_data = data.tail(period)
        lows = recent_data['low'].values
        count = 0
        
        for i in range(1, len(lows)):
            if lows[i] < lows[i-1]:
                count += 1
                
        return count
    
    def _calculate_atr(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Average True Range"""
        high = data['high'].values
        low = data['low'].values
        close = data['close'].values
        
        tr = np.maximum(high[1:] - low[1:], 
                       np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        
        if len(tr) >= period:
            return np.mean(tr[-period:])
        return 0.0
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int, std_dev: float) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        return upper, sma, lower
    
    def _calculate_historical_volatility(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate historical volatility (annualized)"""
        if len(prices) < period + 1:
            return 0.0
        
        returns = np.diff(np.log(prices[-period-1:]))
        return np.std(returns) * np.sqrt(252) * 100
    
    def _classify_volatility_regime(self, indicators: Dict[str, float]) -> str:
        """Classify volatility regime"""
        if 'hist_volatility' not in indicators:
            return 'normal'
        
        vol = indicators['hist_volatility']
        
        if vol < 10:
            return 'low'
        elif vol < 15:
            return 'normal'
        elif vol < 25:
            return 'elevated'
        elif vol < 35:
            return 'high'
        else:
            return 'extreme'
    
    def _calculate_volume_trend(self, data: pd.DataFrame) -> float:
        """Calculate volume trend"""
        if len(data) < 20:
            return 0.0
        
        volume = data['volume'].values[-20:]
        x = np.arange(20)
        
        slope, _ = np.polyfit(x, volume, 1)
        avg_volume = np.mean(volume)
        
        return slope / avg_volume if avg_volume > 0 else 0.0
    
    def _calculate_breadth_thrust(self, data: pd.DataFrame) -> float:
        """Calculate breadth thrust indicator"""
        if 'advances' not in data.columns or len(data) < 10:
            return 0.0
        
        advances = data['advances'].values[-10:]
        declines = data['declines'].values[-10:]
        
        ratios = advances / (advances + declines + 1)
        thrust = np.mean(ratios[-5:]) - np.mean(ratios[-10:-5])
        
        return np.clip(thrust * 2, -1, 1)
    
    def _calculate_rsi(self, prices: np.ndarray, period: int) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return 100.0
        
        rs = up / down
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD"""
        exp1 = pd.Series(prices).ewm(span=12, adjust=False).mean()
        exp2 = pd.Series(prices).ewm(span=26, adjust=False).mean()
        
        macd = exp1.iloc[-1] - exp2.iloc[-1]
        signal = pd.Series(exp1 - exp2).ewm(span=9, adjust=False).mean().iloc[-1]
        histogram = macd - signal
        
        return macd, signal, histogram
    
    def _calculate_mfi(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Money Flow Index"""
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        money_flow = typical_price * data['volume']
        
        positive_flow = money_flow[typical_price.diff() > 0].tail(period).sum()
        negative_flow = money_flow[typical_price.diff() < 0].tail(period).sum()
        
        if negative_flow == 0:
            return 100.0
        
        mfi = 100 - (100 / (1 + positive_flow / negative_flow))
        return mfi
    
    def _calculate_momentum_score(self, indicators: Dict[str, float]) -> float:
        """Calculate composite momentum score"""
        components = []
        
        if 'rsi' in indicators:
            components.append((indicators['rsi'] - 50) / 50)
        if 'macd_histogram' in indicators and 'close' in indicators:
            # Normalize MACD histogram
            norm_macd = indicators['macd_histogram'] / indicators.get('close', 1) * 100
            components.append(np.clip(norm_macd, -1, 1))
        if 'mfi' in indicators:
            components.append((indicators['mfi'] - 50) / 50)
        
        return np.mean(components) if components else 0.0
    
    def calculate_scanner_breadth(self, scanner_data: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate market breadth indicators from scanner data
        
        Args:
            scanner_data: DataFrame with scanner results
            
        Returns:
            Dict with breadth indicators
        """
        breadth = {}
        
        try:
            if scanner_data is None or scanner_data.empty:
                return breadth
            
            # Basic advance/decline from Direction
            if 'Direction' in scanner_data.columns:
                total_tickers = len(scanner_data)
                longs = (scanner_data['Direction'] == 'LONG').sum()
                shorts = (scanner_data['Direction'] == 'SHORT').sum()
                
                breadth['advance_decline_ratio'] = longs / max(shorts, 1)
                breadth['bullish_percent'] = longs / max(total_tickers, 1)
                breadth['bearish_percent'] = shorts / max(total_tickers, 1)
                breadth['net_breadth'] = (longs - shorts) / max(total_tickers, 1)
            
            # Momentum breadth
            if 'Momentum_5D' in scanner_data.columns:
                scanner_data['Momentum_5D'] = pd.to_numeric(scanner_data['Momentum_5D'], errors='coerce').fillna(0)
                
                positive_momentum = (scanner_data['Momentum_5D'] > 0).sum()
                negative_momentum = (scanner_data['Momentum_5D'] < 0).sum()
                strong_positive = (scanner_data['Momentum_5D'] > 10).sum()
                strong_negative = (scanner_data['Momentum_5D'] < -10).sum()
                
                breadth['positive_momentum_percent'] = positive_momentum / len(scanner_data)
                breadth['strong_momentum_percent'] = strong_positive / len(scanner_data)
                breadth['weak_momentum_percent'] = strong_negative / len(scanner_data)
                breadth['momentum_ratio'] = positive_momentum / max(negative_momentum, 1)
                breadth['momentum_spread'] = breadth['positive_momentum_percent'] - (negative_momentum / len(scanner_data))
            
            # Volume breadth
            if 'Volume_Ratio' in scanner_data.columns:
                scanner_data['Volume_Ratio'] = pd.to_numeric(scanner_data['Volume_Ratio'], errors='coerce').fillna(1)
                
                high_volume = (scanner_data['Volume_Ratio'] > 1.5).sum()
                low_volume = (scanner_data['Volume_Ratio'] < 0.7).sum()
                
                breadth['high_volume_percent'] = high_volume / len(scanner_data)
                breadth['low_volume_percent'] = low_volume / len(scanner_data)
                breadth['volume_participation'] = (len(scanner_data) - low_volume) / len(scanner_data)
            
            # Score distribution
            if 'Score' in scanner_data.columns:
                scanner_data['Score'] = pd.to_numeric(scanner_data['Score'], errors='coerce').fillna(0)
                
                top_scores = (scanner_data['Score'] > scanner_data['Score'].quantile(0.8)).sum()
                bottom_scores = (scanner_data['Score'] < scanner_data['Score'].quantile(0.2)).sum()
                
                breadth['high_score_percent'] = top_scores / len(scanner_data)
                breadth['low_score_percent'] = bottom_scores / len(scanner_data)
                breadth['score_spread'] = breadth['high_score_percent'] - breadth['low_score_percent']
            
            # Calculate composite breadth score
            breadth_components = []
            if 'advance_decline_ratio' in breadth:
                # Normalize A/D ratio (1.0 is neutral)
                breadth_components.append((breadth['advance_decline_ratio'] - 1.0) / 2.0)
            if 'momentum_spread' in breadth:
                breadth_components.append(breadth['momentum_spread'])
            if 'volume_participation' in breadth:
                breadth_components.append(breadth['volume_participation'] - 0.5)
            
            if breadth_components:
                breadth['composite_breadth_score'] = np.clip(np.mean(breadth_components), -1, 1)
            
        except Exception as e:
            self.logger.error(f"Error calculating scanner breadth: {e}")
        
        return breadth
    
    def get_trend_score_from_db(self) -> float:
        """Get the latest trend_score from regime analysis database"""
        try:
            # Point to the correct database in Daily/Market_Regime
            db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get the most recent trend_score
            cursor.execute("""
                SELECT trend_score, timestamp 
                FROM predictions 
                WHERE trend_score IS NOT NULL 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                trend_score, timestamp = result
                # Check if it's recent (within last hour)
                ts = datetime.fromisoformat(timestamp.replace(' ', 'T'))
                if datetime.now() - ts < timedelta(hours=1):
                    return float(trend_score)
            
            # Fallback: calculate from latest scanner results
            return self._calculate_trend_score_from_files()
            
        except Exception as e:
            self.logger.error(f"Error getting trend_score from database: {e}")
            return 0.0
    
    def _calculate_trend_score_from_files(self) -> float:
        """Calculate trend score from latest scanner result files"""
        try:
            # Find latest regime summary
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            summary_file = os.path.join(base_path, '..', 'Daily', 'Market_Regime', 
                                      'regime_analysis', 'latest_regime_summary.json')
            
            if os.path.exists(summary_file):
                with open(summary_file, 'r') as f:
                    data = json.load(f)
                    if 'trend_analysis' in data and 'ratio' in data['trend_analysis']:
                        ratio = data['trend_analysis']['ratio']
                        if ratio != 'inf':
                            return float(ratio)
            
            return 1.0  # Default neutral
            
        except Exception as e:
            self.logger.error(f"Error calculating trend_score from files: {e}")
            return 1.0