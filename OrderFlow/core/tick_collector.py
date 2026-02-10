"""
KiteTicker WebSocket handler for OrderFlow module.

Connects to Zerodha's KiteTicker in MODE_FULL to receive L1/L2 tick data,
then feeds each tick to both TickBuffer (storage) and MetricsEngine (computation).

Pattern adapted from Daily/portfolio/SL_watchdog_PSAR.py.
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from kiteconnect import KiteTicker

from OrderFlow.core.instrument_resolver import InstrumentResolver
from OrderFlow.core.metrics_engine import MetricsEngine
from OrderFlow.core.tick_buffer import TickBuffer

logger = logging.getLogger(__name__)


class TickCollector:
    """KiteTicker FULL mode WebSocket handler"""

    def __init__(self, api_key: str, access_token: str,
                 instrument_resolver: InstrumentResolver,
                 tick_buffer: TickBuffer,
                 metrics_engine: MetricsEngine):
        """
        Args:
            api_key: Zerodha API key
            access_token: Zerodha access token
            instrument_resolver: Resolver for token ↔ symbol mapping
            tick_buffer: Buffer for batch DB writes
            metrics_engine: Real-time metrics computation engine
        """
        self.api_key = api_key
        self.access_token = access_token
        self.resolver = instrument_resolver
        self.tick_buffer = tick_buffer
        self.metrics_engine = metrics_engine

        self.kws: Optional[KiteTicker] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False

        # Token → symbol mapping for fast lookup in on_ticks
        self._token_to_symbol: Dict[int, str] = {}
        self._subscribed_tokens: List[int] = []

        # Stats
        self._tick_count = 0
        self._last_tick_time = 0.0
        self._connect_count = 0

        # Callback for external consumers (e.g., dashboard)
        self._on_phase_change: Optional[Callable] = None

    def set_tickers(self, tickers: List[str]):
        """Set the list of tickers to subscribe to.

        Args:
            tickers: List of trading symbols
        """
        resolved = self.resolver.resolve_tickers(tickers)
        self._token_to_symbol = {token: symbol for symbol, token in resolved.items()}
        self._subscribed_tokens = list(resolved.values())
        logger.info(f"Prepared {len(self._subscribed_tokens)} tokens for subscription: "
                    f"{list(resolved.keys())}")

    def start(self):
        """Initialize and start the WebSocket connection"""
        if self._running:
            logger.warning("TickCollector already running")
            return

        if not self._subscribed_tokens:
            logger.error("No tokens to subscribe to. Call set_tickers() first")
            return

        self._running = True
        self._start_websocket()

    def stop(self):
        """Stop the WebSocket connection"""
        self._running = False

        if self.kws:
            try:
                self.kws.close()
            except Exception as e:
                logger.error(f"Error closing KiteTicker: {e}")
            self.kws = None

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5)

        logger.info(f"TickCollector stopped. Total ticks received: {self._tick_count}")

    def _start_websocket(self):
        """Initialize KiteTicker and start connection in a daemon thread"""
        try:
            logger.info("Initializing KiteTicker for FULL mode...")

            self.kws = KiteTicker(self.api_key, self.access_token)
            self.kws.on_ticks = self._on_ticks
            self.kws.on_connect = self._on_connect
            self.kws.on_close = self._on_close
            self.kws.on_error = self._on_error

            self._ws_thread = threading.Thread(
                target=self.kws.connect, daemon=True, name="KiteTicker-WS"
            )
            self._ws_thread.start()
            self._connect_count += 1

            logger.info("KiteTicker WebSocket thread started")
        except Exception as e:
            logger.error(f"Error starting KiteTicker: {e}")

    # ── WebSocket Callbacks ──

    def _on_ticks(self, ws, ticks):
        """Process incoming ticks: feed to buffer and metrics engine"""
        try:
            for tick in ticks:
                token = tick.get("instrument_token")
                symbol = self._token_to_symbol.get(token)

                if not symbol:
                    continue

                price = tick.get("last_price")
                if not price or price <= 0:
                    continue

                self._tick_count += 1
                self._last_tick_time = time.time()

                # Feed to tick buffer for DB storage
                self.tick_buffer.add_tick(tick, symbol)

                # Feed depth data to buffer
                if tick.get("depth"):
                    self.tick_buffer.add_depth(tick, symbol)

                # Feed to metrics engine for real-time computation
                self.metrics_engine.process_tick(tick, symbol)

        except Exception as e:
            logger.error(f"Error processing ticks: {e}")

    def _on_connect(self, ws, response):
        """Subscribe to tokens in FULL mode on connection"""
        logger.info(f"KiteTicker connected (attempt #{self._connect_count}): {response}")

        if self._subscribed_tokens:
            ws.subscribe(self._subscribed_tokens)
            ws.set_mode(ws.MODE_FULL, self._subscribed_tokens)
            logger.info(f"Subscribed {len(self._subscribed_tokens)} tokens in MODE_FULL")

    def _on_close(self, ws, code, reason):
        """Handle WebSocket close with auto-reconnect"""
        logger.warning(f"KiteTicker closed: code={code}, reason={reason}")

        if self._running:
            logger.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
            if self._running:
                self._start_websocket()

    def _on_error(self, ws, code, reason):
        """Log WebSocket errors"""
        logger.error(f"KiteTicker error: code={code}, reason={reason}")

    # ── Public Accessors ──

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected"""
        return (self.kws is not None and
                self._ws_thread is not None and
                self._ws_thread.is_alive())

    @property
    def stats(self) -> Dict:
        """Get collector statistics"""
        return {
            "total_ticks": self._tick_count,
            "last_tick_age_seconds": (
                round(time.time() - self._last_tick_time, 1)
                if self._last_tick_time > 0 else None
            ),
            "connected": self.is_connected,
            "connect_count": self._connect_count,
            "subscribed_tokens": len(self._subscribed_tokens),
            "symbols": list(self._token_to_symbol.values()),
        }
