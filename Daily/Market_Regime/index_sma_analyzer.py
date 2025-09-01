#!/usr/bin/env python3
"""
Index SMA Analyzer

Analyzes major indices (NIFTY, CNXMIDCAP, CNXSMALLCAP) relative to their SMA20
to provide additional market regime confirmation.
"""

import os
import sys
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import configparser

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


class IndexSMAAnalyzer:
    """Analyzes index positions relative to SMA20 for market regime"""
    
    def __init__(self, kite=None):
        """
        Initialize the Index SMA Analyzer
        
        Args:
            kite: KiteConnect instance (optional, will create if not provided)
        """
        self.indices = {
            'NIFTY 50': 'NSE:NIFTY 50',
            'NIFTY MIDCAP 100': 'NSE:NIFTY MIDCAP 100',
            'NIFTY SMLCAP 100': 'NSE:NIFTY SMLCAP 100'
        }
        
        # Instrument tokens for indices (these need to be fetched)
        self.index_tokens = {
            'NIFTY 50': 256265,  # NIFTY 50
            'NIFTY MIDCAP 100': 288009,  # NIFTY MIDCAP 100
            'NIFTY SMLCAP 100': 288265   # NIFTY SMALLCAP 100
        }
        
        self.kite = kite
        if not self.kite:
            self.kite = self._initialize_kite()
            
        # Cache file for index data
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_file = os.path.join(self.cache_dir, 'index_sma_cache.json')
        
    def _initialize_kite(self):
        """Initialize KiteConnect with credentials from config"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                'config.ini'
            )
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Use default Sai credentials
            api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
            access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            return kite
        except Exception as e:
            logger.error(f"Error initializing KiteConnect: {e}")
            return None
    
    def fetch_index_data(self, days=40):
        """
        Fetch historical data for indices
        
        Args:
            days: Number of days of historical data to fetch (increased to 40 for proper SMA20)
            
        Returns:
            Dictionary with index data and SMA calculations
        """
        if not self.kite:
            logger.error("KiteConnect not initialized")
            return self._load_cached_data()
        
        try:
            # Need extra days for SMA calculation
            from_date = (datetime.now() - timedelta(days=days)).date()
            to_date = datetime.now().date()
            
            index_data = {}
            
            for index_name, instrument_token in self.index_tokens.items():
                try:
                    # Fetch historical data
                    historical_data = self.kite.historical_data(
                        instrument_token,
                        from_date,
                        to_date,
                        interval="day"
                    )
                    
                    if historical_data and len(historical_data) >= 20:
                        df = pd.DataFrame(historical_data)
                        
                        # Calculate SMA20
                        df['sma20'] = df['close'].rolling(window=20, min_periods=20).mean()
                        
                        # Get latest values (ensure SMA20 is not NaN)
                        latest = df.iloc[-1]
                        
                        # Check if SMA20 is valid
                        if pd.isna(latest['sma20']):
                            logger.warning(f"{index_name}: SMA20 is NaN, need more historical data")
                            # Try to get the last valid SMA20
                            valid_sma_df = df[df['sma20'].notna()]
                            if not valid_sma_df.empty:
                                latest = valid_sma_df.iloc[-1]
                            else:
                                logger.error(f"{index_name}: No valid SMA20 values found")
                                continue
                        
                        # Calculate position relative to SMA20
                        sma_position = (latest['close'] - latest['sma20']) / latest['sma20'] * 100 if latest['sma20'] > 0 else 0
                        
                        index_data[index_name] = {
                            'close': float(latest['close']),
                            'sma20': float(latest['sma20']) if not pd.isna(latest['sma20']) else None,
                            'above_sma20': bool(latest['close'] > latest['sma20']) if not pd.isna(latest['sma20']) else False,
                            'sma_position_pct': float(sma_position) if not pd.isna(latest['sma20']) else 0,
                            'timestamp': latest['date'].isoformat() if hasattr(latest['date'], 'isoformat') else str(latest['date'])
                        }
                        
                        logger.info(f"{index_name}: Close={latest['close']:.2f}, SMA20={latest['sma20']:.2f if not pd.isna(latest['sma20']) else 0:.2f}, Position={sma_position:.2f}%")
                    else:
                        logger.warning(f"{index_name}: Insufficient data for SMA20 calculation (got {len(historical_data)} days)")
                        
                except Exception as e:
                    logger.error(f"Error fetching data for {index_name}: {e}")
                    continue
            
            # Cache the data
            if index_data:
                self._save_cached_data(index_data)
                
            return index_data
            
        except Exception as e:
            logger.error(f"Error fetching index data: {e}")
            return self._load_cached_data()
    
    def analyze_index_trend(self, index_data=None):
        """
        Analyze overall market trend based on index positions
        
        Args:
            index_data: Dictionary with index data (will fetch if not provided)
            
        Returns:
            Dictionary with trend analysis
        """
        if index_data is None:
            index_data = self.fetch_index_data()
            
        if not index_data:
            logger.warning("No index data available")
            return {
                'trend': 'neutral',
                'strength': 0.5,
                'indices_above_sma20': 0,
                'total_indices': 0,
                'avg_position': 0,
                'weighted_position': 0,
                'analysis': 'Unable to analyze - no data',
                'index_details': {}
            }
        
        # Count indices above SMA20
        above_sma = sum(1 for data in index_data.values() if data.get('above_sma20', False))
        total_indices = len(index_data)
        
        # Calculate average position relative to SMA20
        positions = [data.get('sma_position_pct', 0) for data in index_data.values()]
        avg_position = np.mean(positions) if positions else 0
        
        # Weighted analysis (NIFTY gets more weight)
        weights = {
            'NIFTY 50': 0.5,
            'NIFTY MIDCAP 100': 0.25,
            'NIFTY SMLCAP 100': 0.25
        }
        
        weighted_position = sum(
            index_data.get(idx, {}).get('sma_position_pct', 0) * weight 
            for idx, weight in weights.items()
        )
        
        # Determine trend
        if above_sma == total_indices and avg_position > 2:
            trend = 'strong_bullish'
            strength = min(avg_position / 10, 1.0)  # Normalize to 0-1
            analysis = 'All indices above SMA20 - Strong bullish trend'
        elif above_sma >= 2 and avg_position > 0:
            trend = 'bullish'
            strength = 0.6 + (avg_position / 20)
            analysis = f'{above_sma}/{total_indices} indices above SMA20 - Bullish trend'
        elif above_sma == 0 and avg_position < -2:
            trend = 'strong_bearish'
            strength = min(abs(avg_position) / 10, 1.0)
            analysis = 'All indices below SMA20 - Strong bearish trend'
        elif above_sma <= 1 and avg_position < 0:
            trend = 'bearish'
            strength = 0.6 + (abs(avg_position) / 20)
            analysis = f'{above_sma}/{total_indices} indices above SMA20 - Bearish trend'
        else:
            trend = 'neutral'
            strength = 0.3 + (abs(avg_position) / 30)
            analysis = 'Mixed signals - Neutral trend'
        
        return {
            'trend': trend,
            'strength': float(strength),
            'indices_above_sma20': above_sma,
            'total_indices': total_indices,
            'avg_position': float(avg_position),
            'weighted_position': float(weighted_position),
            'analysis': analysis,
            'index_details': index_data
        }
    
    def get_regime_weight(self, index_trend):
        """
        Get weight for index trend in overall regime determination
        
        Args:
            index_trend: Dictionary from analyze_index_trend
            
        Returns:
            Weight between 0 and 1 for regime calculation
        """
        # Map index trend to regime weight
        trend_weights = {
            'strong_bullish': 1.0,
            'bullish': 0.7,
            'neutral': 0.5,
            'bearish': 0.3,
            'strong_bearish': 0.0
        }
        
        base_weight = trend_weights.get(index_trend['trend'], 0.5)
        
        # Adjust based on strength
        adjusted_weight = base_weight * index_trend.get('strength', 1.0)
        
        return float(adjusted_weight)
    
    def _save_cached_data(self, data):
        """Save data to cache file"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _load_cached_data(self):
        """Load data from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is recent (within 1 hour)
                cache_time = datetime.fromisoformat(cache_data['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=1):
                    logger.info("Using cached index data")
                    return cache_data['data']
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
        
        return {}


def test_analyzer():
    """Test the index SMA analyzer"""
    analyzer = IndexSMAAnalyzer()
    
    print("Testing Index SMA Analyzer")
    print("=" * 50)
    
    # Test with sample data
    test_data = {
        'NIFTY 50': {
            'close': 22500,
            'sma20': 22000,
            'above_sma20': True,
            'sma_position_pct': 2.27,
            'timestamp': datetime.now().isoformat()
        },
        'NIFTY MIDCAP 100': {
            'close': 48000,
            'sma20': 47500,
            'above_sma20': True,
            'sma_position_pct': 1.05,
            'timestamp': datetime.now().isoformat()
        },
        'NIFTY SMLCAP 100': {
            'close': 15500,
            'sma20': 16000,
            'above_sma20': False,
            'sma_position_pct': -3.12,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    # Analyze trend
    trend_analysis = analyzer.analyze_index_trend(test_data)
    
    print("\nIndex Analysis:")
    print(f"Trend: {trend_analysis['trend']}")
    print(f"Strength: {trend_analysis['strength']:.2f}")
    print(f"Indices above SMA20: {trend_analysis['indices_above_sma20']}/{trend_analysis['total_indices']}")
    print(f"Average position: {trend_analysis['avg_position']:.2f}%")
    print(f"Analysis: {trend_analysis['analysis']}")
    
    # Get regime weight
    weight = analyzer.get_regime_weight(trend_analysis)
    print(f"\nRegime weight: {weight:.2f}")
    
    # Try to fetch real data
    print("\nFetching real index data...")
    real_data = analyzer.fetch_index_data()
    if real_data:
        real_analysis = analyzer.analyze_index_trend(real_data)
        print("\nReal Market Analysis:")
        print(f"Trend: {real_analysis['trend']}")
        print(f"Analysis: {real_analysis['analysis']}")


if __name__ == "__main__":
    test_analyzer()