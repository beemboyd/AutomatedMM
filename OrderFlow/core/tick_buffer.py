"""
Thread-safe tick buffer for OrderFlow module.

Accumulates raw ticks and depth snapshots in memory, then flushes them
to TimescaleDB in batches on size or time thresholds.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from OrderFlow.core.db_manager import DBManager

logger = logging.getLogger(__name__)


class TickBuffer:
    """Thread-safe buffer that batches ticks and depth snapshots for DB insertion"""

    def __init__(self, db_manager: DBManager, buffer_size: int = 500,
                 flush_interval: float = 2.0):
        """
        Args:
            db_manager: DBManager instance for batch inserts
            buffer_size: Max ticks before auto-flush
            flush_interval: Max seconds between flushes
        """
        self.db = db_manager
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Separate buffers for ticks and depth
        self._tick_buffer: List[Tuple] = []
        self._depth_buffer: List[Tuple] = []
        self._lock = threading.Lock()

        # Background flush thread
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        self._last_flush = time.time()

        # Stats
        self._ticks_flushed = 0
        self._depths_flushed = 0
        self._flush_count = 0

    def start(self):
        """Start the background flush thread"""
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True,
                                              name="TickBuffer-Flush")
        self._flush_thread.start()
        logger.info(f"TickBuffer started (size={self.buffer_size}, "
                    f"interval={self.flush_interval}s)")

    def stop(self):
        """Stop the background flush thread and flush remaining data"""
        self._running = False
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=10)

        # Final flush
        self._flush()
        logger.info(f"TickBuffer stopped. Total flushed: {self._ticks_flushed} ticks, "
                    f"{self._depths_flushed} depth snapshots in {self._flush_count} flushes")

    def add_tick(self, tick: Dict, symbol: str):
        """Add a raw tick to the buffer.

        Args:
            tick: KiteTicker FULL mode tick dict
            symbol: Trading symbol for this tick
        """
        now = datetime.now(timezone.utc)
        last_trade_time = tick.get("last_trade_time")

        record = (
            now,
            tick.get("instrument_token"),
            symbol,
            tick.get("last_price", 0),
            tick.get("last_traded_quantity", 0),
            tick.get("average_traded_price"),
            tick.get("volume_traded"),
            tick.get("total_buy_quantity"),
            tick.get("total_sell_quantity"),
            tick.get("oi", 0),
            tick.get("ohlc", {}).get("open"),
            tick.get("ohlc", {}).get("high"),
            tick.get("ohlc", {}).get("low"),
            tick.get("ohlc", {}).get("close"),
            last_trade_time,
        )

        with self._lock:
            self._tick_buffer.append(record)

            if len(self._tick_buffer) >= self.buffer_size:
                self._flush_ticks()

    def add_depth(self, tick: Dict, symbol: str):
        """Add a depth snapshot to the buffer.

        Args:
            tick: KiteTicker FULL mode tick dict (contains 'depth' key)
            symbol: Trading symbol for this tick
        """
        depth = tick.get("depth", {})
        buy_depth = depth.get("buy", [])
        sell_depth = depth.get("sell", [])

        if not buy_depth and not sell_depth:
            return

        total_bid_qty = sum(level.get("quantity", 0) for level in buy_depth)
        total_ask_qty = sum(level.get("quantity", 0) for level in sell_depth)

        # Bid-ask spread from top of book
        best_bid = buy_depth[0].get("price", 0) if buy_depth else 0
        best_ask = sell_depth[0].get("price", 0) if sell_depth else 0
        spread = best_ask - best_bid if best_ask > 0 and best_bid > 0 else None

        # Simple imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)
        total_qty = total_bid_qty + total_ask_qty
        imbalance = (total_bid_qty - total_ask_qty) / total_qty if total_qty > 0 else 0

        record = (
            datetime.now(timezone.utc),
            tick.get("instrument_token"),
            symbol,
            json.dumps(buy_depth),
            json.dumps(sell_depth),
            spread,
            total_bid_qty,
            total_ask_qty,
            imbalance,
        )

        with self._lock:
            self._depth_buffer.append(record)

            if len(self._depth_buffer) >= self.buffer_size:
                self._flush_depth()

    def _flush_ticks(self):
        """Flush tick buffer to DB (must hold lock)"""
        if not self._tick_buffer:
            return

        batch = self._tick_buffer[:]
        self._tick_buffer.clear()

        try:
            self.db.insert_raw_ticks(batch)
            self._ticks_flushed += len(batch)
        except Exception as e:
            logger.error(f"Error flushing {len(batch)} ticks: {e}")
            # Put back on failure
            self._tick_buffer.extend(batch)

    def _flush_depth(self):
        """Flush depth buffer to DB (must hold lock)"""
        if not self._depth_buffer:
            return

        batch = self._depth_buffer[:]
        self._depth_buffer.clear()

        try:
            self.db.insert_depth_snapshots(batch)
            self._depths_flushed += len(batch)
        except Exception as e:
            logger.error(f"Error flushing {len(batch)} depth snapshots: {e}")
            self._depth_buffer.extend(batch)

    def _flush(self):
        """Flush both buffers"""
        with self._lock:
            self._flush_ticks()
            self._flush_depth()
            self._flush_count += 1
            self._last_flush = time.time()

    def _flush_loop(self):
        """Background thread that periodically flushes buffers"""
        while self._running:
            time.sleep(self.flush_interval)
            elapsed = time.time() - self._last_flush
            if elapsed >= self.flush_interval:
                self._flush()

    @property
    def pending_ticks(self) -> int:
        """Number of ticks waiting in buffer"""
        with self._lock:
            return len(self._tick_buffer)

    @property
    def pending_depths(self) -> int:
        """Number of depth snapshots waiting in buffer"""
        with self._lock:
            return len(self._depth_buffer)

    @property
    def stats(self) -> Dict:
        """Get buffer statistics"""
        return {
            "ticks_flushed": self._ticks_flushed,
            "depths_flushed": self._depths_flushed,
            "flush_count": self._flush_count,
            "pending_ticks": self.pending_ticks,
            "pending_depths": self.pending_depths,
        }
