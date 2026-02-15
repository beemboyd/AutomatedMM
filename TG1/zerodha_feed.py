"""
Zerodha KiteTicker WebSocket feed for TG1.

Provides real-time LTP for TokenA and TokenB via KiteTicker WebSocket.
Thread-safe price dict updated on every tick. Auto-reconnects on disconnect.

Usage:
    feed = ZerodhaFeed(api_key, access_token)
    feed.subscribe([token_a_inst, token_b_inst])
    feed.start()       # starts in background thread
    ltp = feed.get_ltp(token_a_inst)
    feed.stop()
"""

import logging
import threading
from typing import Dict, Optional, List

from kiteconnect import KiteTicker

logger = logging.getLogger(__name__)


class ZerodhaFeed:
    """Real-time price feed via KiteTicker WebSocket."""

    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token

        # Thread-safe price store: instrument_token -> last_price
        self._prices: Dict[int, float] = {}
        self._lock = threading.Lock()

        self._tokens: List[int] = []
        self._ticker: Optional[KiteTicker] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def subscribe(self, instrument_tokens: List[int]):
        """Set the list of instrument_tokens to subscribe to."""
        self._tokens = [t for t in instrument_tokens if t is not None]

    def start(self):
        """Start KiteTicker in a background daemon thread."""
        if self._running:
            logger.warning("Feed already running")
            return

        if not self._tokens:
            logger.warning("No instrument tokens to subscribe")
            return

        self._ticker = KiteTicker(self.api_key, self.access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._ticker.on_error = self._on_error
        self._ticker.on_reconnect = self._on_reconnect
        self._ticker.on_noreconnect = self._on_noreconnect

        self._running = True
        self._thread = threading.Thread(
            target=self._ticker.connect, kwargs={'threaded': False},
            name='KiteTicker', daemon=True)
        self._thread.start()
        logger.info("KiteTicker started for %d tokens: %s",
                     len(self._tokens), self._tokens)

    def stop(self):
        """Stop the KiteTicker WebSocket."""
        self._running = False
        if self._ticker:
            try:
                self._ticker.close()
            except Exception:
                pass
        logger.info("KiteTicker stopped")

    def get_ltp(self, instrument_token: int) -> Optional[float]:
        """Get last traded price for an instrument_token (thread-safe)."""
        with self._lock:
            return self._prices.get(instrument_token)

    def get_all_prices(self) -> Dict[int, float]:
        """Get copy of all current prices."""
        with self._lock:
            return dict(self._prices)

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ---- KiteTicker callbacks ----

    def _on_ticks(self, ws, ticks):
        with self._lock:
            for tick in ticks:
                token = tick.get('instrument_token')
                ltp = tick.get('last_price')
                if token is not None and ltp is not None:
                    self._prices[token] = float(ltp)

    def _on_connect(self, ws, response):
        logger.info("KiteTicker connected. Subscribing to %d tokens", len(self._tokens))
        ws.subscribe(self._tokens)
        ws.set_mode(ws.MODE_LTP, self._tokens)

    def _on_close(self, ws, code, reason):
        logger.warning("KiteTicker closed: code=%s reason=%s", code, reason)

    def _on_error(self, ws, code, reason):
        logger.error("KiteTicker error: code=%s reason=%s", code, reason)

    def _on_reconnect(self, ws, attempts_count):
        logger.info("KiteTicker reconnecting (attempt %d)...", attempts_count)

    def _on_noreconnect(self, ws):
        logger.error("KiteTicker: max reconnect attempts exhausted")
        self._running = False
