"""
Parabolic SAR Calculator for Dynamic Stop Losses
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from kiteconnect import KiteConnect
import configparser

logger = logging.getLogger(__name__)


class PSARCalculator:
    """
    Parabolic SAR Calculator for dynamic stop loss management

    PSAR Settings:
    - af_start: Initial acceleration factor (default 0.02)
    - af_increment: AF increment on new extreme (default 0.02)
    - af_max: Maximum acceleration factor (default 0.2)
    """

    def __init__(self, af_start: float = 0.02, af_increment: float = 0.02, af_max: float = 0.2):
        self.af_start = af_start
        self.af_increment = af_increment
        self.af_max = af_max
        self.kite = None
        self._cache = {}
        self._cache_timestamp = {}

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
            logger.info("Kite connection initialized for PSAR calculator")

    def _fetch_data(self, ticker: str, interval: str = 'day', days: int = 50, retry_on_token_error: bool = True) -> Optional[pd.DataFrame]:
        """Fetch OHLC data for a ticker"""
        self._init_kite()
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days + 10)

            data = self.kite.historical_data(
                instrument_token=f"NSE:{ticker}",
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d'),
                interval=interval
            )

            if not data:
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
                return self._fetch_data(ticker, interval, days, retry_on_token_error=False)
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    def calculate_psar(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Parabolic SAR

        Returns DataFrame with added columns:
        - psar: Parabolic SAR value
        - psar_trend: 1 for uptrend, -1 for downtrend
        - psar_af: Current acceleration factor
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        n = len(df)

        psar = np.zeros(n)
        trend = np.zeros(n)
        af = np.zeros(n)
        ep = np.zeros(n)  # Extreme point

        # Initialize first values
        psar[0] = close[0]
        trend[0] = 1  # Start with uptrend
        af[0] = self.af_start
        ep[0] = high[0]

        for i in range(1, n):
            # Calculate PSAR
            if trend[i-1] == 1:  # Uptrend
                psar[i] = psar[i-1] + af[i-1] * (ep[i-1] - psar[i-1])
                # PSAR should not be above prior two lows
                psar[i] = min(psar[i], low[i-1])
                if i > 1:
                    psar[i] = min(psar[i], low[i-2])

                # Check for trend reversal
                if low[i] < psar[i]:
                    trend[i] = -1  # Reverse to downtrend
                    psar[i] = ep[i-1]  # PSAR = previous extreme point
                    ep[i] = low[i]
                    af[i] = self.af_start
                else:
                    trend[i] = 1
                    # Update EP and AF
                    if high[i] > ep[i-1]:
                        ep[i] = high[i]
                        af[i] = min(af[i-1] + self.af_increment, self.af_max)
                    else:
                        ep[i] = ep[i-1]
                        af[i] = af[i-1]

            else:  # Downtrend
                psar[i] = psar[i-1] - af[i-1] * (psar[i-1] - ep[i-1])
                # PSAR should not be below prior two highs
                psar[i] = max(psar[i], high[i-1])
                if i > 1:
                    psar[i] = max(psar[i], high[i-2])

                # Check for trend reversal
                if high[i] > psar[i]:
                    trend[i] = 1  # Reverse to uptrend
                    psar[i] = ep[i-1]  # PSAR = previous extreme point
                    ep[i] = high[i]
                    af[i] = self.af_start
                else:
                    trend[i] = -1
                    # Update EP and AF
                    if low[i] < ep[i-1]:
                        ep[i] = low[i]
                        af[i] = min(af[i-1] + self.af_increment, self.af_max)
                    else:
                        ep[i] = ep[i-1]
                        af[i] = af[i-1]

        df = df.copy()
        df['psar'] = psar
        df['psar_trend'] = trend
        df['psar_af'] = af

        return df

    def get_psar_values(self, ticker: str, interval: str = 'day', use_cache: bool = True) -> Optional[Dict]:
        """
        Get current PSAR values for a ticker

        Returns dict with:
        - psar: Current PSAR value
        - trend: 1 (uptrend) or -1 (downtrend)
        - af: Current acceleration factor
        - close: Current close price
        """
        cache_key = f"{ticker}_{interval}"

        # Check cache (valid for 5 minutes)
        if use_cache and cache_key in self._cache:
            cache_time = self._cache_timestamp.get(cache_key)
            if cache_time and (datetime.now() - cache_time).seconds < 300:
                return self._cache[cache_key]

        # Fetch and calculate
        df = self._fetch_data(ticker, interval)
        if df is None or len(df) < 5:
            return None

        try:
            df = self.calculate_psar(df)

            values = {
                'psar': round(df['psar'].iloc[-1], 2),
                'trend': int(df['psar_trend'].iloc[-1]),
                'af': round(df['psar_af'].iloc[-1], 4),
                'close': round(df['close'].iloc[-1], 2),
                'timestamp': datetime.now().isoformat()
            }

            # Cache
            self._cache[cache_key] = values
            self._cache_timestamp[cache_key] = datetime.now()

            logger.debug(f"PSAR for {ticker}: {values['psar']} (Trend: {'UP' if values['trend']==1 else 'DOWN'})")

            return values

        except Exception as e:
            logger.error(f"Error calculating PSAR for {ticker}: {e}")
            return None

    def get_stop_loss(self, ticker: str, direction: str = 'long', interval: str = 'day') -> Optional[float]:
        """
        Get dynamic stop loss based on PSAR

        For long positions: PSAR acts as trailing stop (below price in uptrend)
        For short positions: PSAR acts as trailing stop (above price in downtrend)
        """
        psar_data = self.get_psar_values(ticker, interval)
        if psar_data is None:
            return None

        return psar_data['psar']

    def update_trailing_stop(self, ticker: str, current_stop: float,
                             direction: str = 'long', interval: str = 'day') -> Tuple[float, bool]:
        """
        Update trailing stop based on PSAR

        Returns (new_stop, should_exit)
        - new_stop: Updated stop loss price
        - should_exit: True if current price has breached stop
        """
        psar_data = self.get_psar_values(ticker, interval, use_cache=False)  # Always fresh for trailing
        if psar_data is None:
            return current_stop, False

        new_psar = psar_data['psar']
        current_price = psar_data['close']
        trend = psar_data['trend']

        if direction == 'long':
            # For long: only move stop UP, exit if price < PSAR
            new_stop = max(current_stop, new_psar) if trend == 1 else current_stop
            should_exit = current_price < new_psar
        else:
            # For short: only move stop DOWN, exit if price > PSAR
            new_stop = min(current_stop, new_psar) if trend == -1 else current_stop
            should_exit = current_price > new_psar

        return round(new_stop, 2), should_exit

    def clear_cache(self):
        """Clear the cache"""
        self._cache.clear()
        self._cache_timestamp.clear()


# Singleton
_psar_calculator = None


def get_psar_calculator(af_start: float = 0.02, af_increment: float = 0.02,
                        af_max: float = 0.2) -> PSARCalculator:
    """Get or create PSAR calculator singleton"""
    global _psar_calculator
    if _psar_calculator is None:
        _psar_calculator = PSARCalculator(af_start, af_increment, af_max)
    return _psar_calculator
