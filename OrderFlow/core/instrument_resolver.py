"""
Instrument resolver for OrderFlow module.

Resolves ticker symbols to Zerodha instrument tokens with 24-hour caching.
Pattern adapted from Daily/portfolio/SL_watchdog_PSAR.py.
"""

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_DURATION = 86400  # 24 hours


class InstrumentResolver:
    """Resolves ticker symbols to Zerodha instrument tokens"""

    def __init__(self, kite, exchange: str = "NSE"):
        """
        Args:
            kite: KiteConnect instance (authenticated)
            exchange: Exchange to fetch instruments for (NSE, BSE, NFO)
        """
        self.kite = kite
        self.exchange = exchange
        self._cache = None
        self._cache_time = 0
        self._token_map: Dict[str, int] = {}  # symbol -> token
        self._reverse_map: Dict[int, str] = {}  # token -> symbol

    def _refresh_cache(self):
        """Fetch instruments from Zerodha API and build lookup maps"""
        current_time = time.time()

        if self._cache and (current_time - self._cache_time) < CACHE_DURATION:
            return

        try:
            logger.info(f"Fetching instruments from {self.exchange}...")
            instruments = self.kite.instruments(self.exchange)
            self._cache = instruments
            self._cache_time = current_time

            # Build token maps
            self._token_map.clear()
            self._reverse_map.clear()
            for inst in instruments:
                symbol = inst.get("tradingsymbol", "").upper()
                token = inst.get("instrument_token")
                if symbol and token:
                    self._token_map[symbol] = token
                    self._reverse_map[token] = symbol

            logger.info(f"Cached {len(self._token_map)} instruments from {self.exchange}")
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            if self._cache:
                logger.warning("Using expired instruments cache")
            else:
                raise

    def get_token(self, symbol: str) -> Optional[int]:
        """Get instrument token for a ticker symbol.

        Args:
            symbol: Trading symbol (e.g. 'RELIANCE')

        Returns:
            Instrument token or None if not found
        """
        self._refresh_cache()
        token = self._token_map.get(symbol.upper())
        if token is None:
            logger.warning(f"Instrument token not found for {symbol}")
        return token

    def get_symbol(self, token: int) -> Optional[str]:
        """Reverse lookup: instrument token → symbol.

        Args:
            token: Instrument token

        Returns:
            Trading symbol or None if not found
        """
        self._refresh_cache()
        return self._reverse_map.get(token)

    def resolve_tickers(self, tickers: List[str]) -> Dict[str, int]:
        """Resolve a list of tickers to their instrument tokens.

        Args:
            tickers: List of trading symbols

        Returns:
            Dict of {symbol: instrument_token} for successfully resolved tickers
        """
        self._refresh_cache()
        resolved = {}
        failed = []

        for ticker in tickers:
            token = self._token_map.get(ticker.upper())
            if token:
                resolved[ticker.upper()] = token
            else:
                failed.append(ticker)

        if failed:
            logger.warning(f"Could not resolve {len(failed)} tickers: {failed}")

        logger.info(f"Resolved {len(resolved)}/{len(tickers)} tickers to instrument tokens")
        return resolved

    def get_reverse_map(self) -> Dict[int, str]:
        """Get the full token → symbol map (for use in on_ticks callback)"""
        self._refresh_cache()
        return dict(self._reverse_map)
