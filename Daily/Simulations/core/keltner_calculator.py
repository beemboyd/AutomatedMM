"""
Keltner Channel Calculator for Daily Timeframe
Fetches daily OHLC data and calculates KC bands for stop loss placement
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from kiteconnect import KiteConnect
import configparser

logger = logging.getLogger(__name__)


class KeltnerChannelCalculator:
    """Calculate Keltner Channel bands for stop loss placement"""

    def __init__(self, ema_period: int = 20, atr_period: int = 10, atr_multiplier: float = 2.0):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.kite = None
        self._cache = {}  # Cache KC values by ticker
        self._cache_timestamp = {}  # Track when cache was updated

    def _init_kite(self, force_refresh: bool = False):
        """Initialize Kite connection. Set force_refresh=True to reload credentials."""
        if self.kite is None or force_refresh:
            config = configparser.ConfigParser()
            config_path = Path(__file__).parent.parent.parent / 'config.ini'
            config.read(config_path)

            # Use first available user credentials (Sai)
            credential_section = 'API_CREDENTIALS_Sai'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')

            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            logger.info("Kite connection initialized for KC calculator")

    def _get_instrument_token(self, ticker: str) -> Optional[int]:
        """Get numeric instrument token for a ticker"""
        self._init_kite()
        try:
            # Check cache first
            cache_key = f"token_{ticker}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Get instruments and find the ticker
            instruments = self.kite.instruments('NSE')
            for inst in instruments:
                if inst['tradingsymbol'] == ticker:
                    self._cache[cache_key] = inst['instrument_token']
                    return inst['instrument_token']

            logger.warning(f"Could not find instrument token for {ticker}")
        except Exception as e:
            logger.warning(f"Could not get instrument token for {ticker}: {e}")
        return None

    def _fetch_daily_data(self, ticker: str, days: int = 50, retry_on_token_error: bool = True) -> Optional[pd.DataFrame]:
        """Fetch daily OHLC data for a ticker"""
        self._init_kite()
        try:
            # Get numeric instrument token first
            instrument_token = self._get_instrument_token(ticker)
            if not instrument_token:
                logger.warning(f"No instrument token for {ticker}")
                return None

            to_date = datetime.now()
            from_date = to_date - timedelta(days=days + 10)  # Extra days for buffer

            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d'),
                interval='day'
            )

            if not data:
                logger.warning(f"No daily data returned for {ticker}")
                return None

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            return df

        except Exception as e:
            error_str = str(e).lower()
            # Retry with fresh credentials if token error
            if retry_on_token_error and ('invalid token' in error_str or 'access_token' in error_str):
                logger.warning(f"Token error for {ticker}, refreshing credentials...")
                self._init_kite(force_refresh=True)
                return self._fetch_daily_data(ticker, days, retry_on_token_error=False)
            logger.error(f"Error fetching daily data for {ticker}: {e}")
            return None

    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        """Calculate Average True Range"""
        if period is None:
            period = self.atr_period

        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    def calculate_keltner_channel(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Keltner Channel bands
        Returns (middle, upper, lower) bands
        """
        # Middle band is EMA of close
        middle = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # ATR for band width
        atr = self.calculate_atr(df)

        # Upper and lower bands
        upper = middle + (self.atr_multiplier * atr)
        lower = middle - (self.atr_multiplier * atr)

        return middle, upper, lower

    def get_kc_values(self, ticker: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get current Keltner Channel values for a ticker
        Returns dict with 'middle', 'upper', 'lower', 'atr' keys
        """
        # Check cache (valid for 1 hour during market hours)
        cache_key = ticker
        if use_cache and cache_key in self._cache:
            cache_time = self._cache_timestamp.get(cache_key)
            if cache_time and (datetime.now() - cache_time).seconds < 3600:
                return self._cache[cache_key]

        # Fetch fresh data
        df = self._fetch_daily_data(ticker)
        if df is None or len(df) < self.ema_period + 5:
            logger.warning(f"Insufficient data for KC calculation: {ticker}")
            return None

        try:
            middle, upper, lower = self.calculate_keltner_channel(df)
            atr = self.calculate_atr(df)

            # Get latest values
            kc_values = {
                'middle': round(middle.iloc[-1], 2),
                'upper': round(upper.iloc[-1], 2),
                'lower': round(lower.iloc[-1], 2),
                'atr': round(atr.iloc[-1], 2),
                'close': round(df['close'].iloc[-1], 2),
                'timestamp': datetime.now().isoformat()
            }

            # Cache the values
            self._cache[cache_key] = kc_values
            self._cache_timestamp[cache_key] = datetime.now()

            logger.debug(f"KC for {ticker}: Middle={kc_values['middle']}, Upper={kc_values['upper']}, Lower={kc_values['lower']}")

            return kc_values

        except Exception as e:
            logger.error(f"Error calculating KC for {ticker}: {e}")
            return None

    def get_stop_loss(self, ticker: str, direction: str = 'long') -> Optional[float]:
        """
        Get stop loss price based on KC
        direction: 'long' uses KC lower, 'short' uses KC upper
        """
        kc = self.get_kc_values(ticker)
        if kc is None:
            return None

        if direction == 'long':
            return kc['lower']
        else:
            return kc['upper']

    def get_batch_kc_values(self, tickers: list) -> Dict[str, Dict]:
        """Get KC values for multiple tickers"""
        results = {}
        for ticker in tickers:
            kc = self.get_kc_values(ticker)
            if kc:
                results[ticker] = kc
        return results

    def clear_cache(self):
        """Clear the KC cache"""
        self._cache.clear()
        self._cache_timestamp.clear()
        logger.info("KC cache cleared")


class MockKeltnerCalculator(KeltnerChannelCalculator):
    """Mock KC calculator for testing without API access"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mock_data = {}

    def set_mock_data(self, ticker: str, middle: float, upper: float, lower: float, atr: float):
        """Set mock KC data for a ticker"""
        self._mock_data[ticker] = {
            'middle': middle,
            'upper': upper,
            'lower': lower,
            'atr': atr,
            'close': middle,
            'timestamp': datetime.now().isoformat()
        }

    def get_kc_values(self, ticker: str, use_cache: bool = True) -> Optional[Dict]:
        """Return mock data or generate from current price"""
        if ticker in self._mock_data:
            return self._mock_data[ticker]

        # Generate mock KC values based on typical percentage ranges
        # Assuming a base price of 500 for testing
        base_price = 500
        atr = base_price * 0.02  # 2% ATR
        return {
            'middle': base_price,
            'upper': base_price + (2 * atr),
            'lower': base_price - (2 * atr),
            'atr': atr,
            'close': base_price,
            'timestamp': datetime.now().isoformat()
        }


# Singleton instance
_kc_calculator = None


def get_kc_calculator(ema_period: int = 20, atr_period: int = 10,
                      atr_multiplier: float = 2.0, mock: bool = False) -> KeltnerChannelCalculator:
    """Get or create KC calculator singleton"""
    global _kc_calculator
    if _kc_calculator is None:
        if mock:
            _kc_calculator = MockKeltnerCalculator(ema_period, atr_period, atr_multiplier)
        else:
            _kc_calculator = KeltnerChannelCalculator(ema_period, atr_period, atr_multiplier)
    return _kc_calculator
