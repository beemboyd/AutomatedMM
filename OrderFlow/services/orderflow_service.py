#!/usr/bin/env python3
"""
OrderFlow Service — main entry point.

Wires together all OrderFlow components:
- InstrumentResolver: symbol → token mapping
- DBManager: TimescaleDB connection pool
- TickBuffer: batched DB writes
- MetricsEngine: real-time order flow computations
- TickCollector: KiteTicker FULL mode WebSocket

Usage:
    python -m OrderFlow.services.orderflow_service --user Sai
    python -m OrderFlow.services.orderflow_service --user Sai --tickers RELIANCE,HDFCBANK,INFY
"""

import argparse
import configparser
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from kiteconnect import KiteConnect

from OrderFlow.core.db_manager import DBManager
from OrderFlow.core.instrument_resolver import InstrumentResolver
from OrderFlow.core.metrics_engine import MetricsEngine
from OrderFlow.core.tick_buffer import TickBuffer
from OrderFlow.core.tick_collector import TickCollector

# Paths
MODULE_DIR = Path(__file__).parent.parent
CONFIG_FILE = MODULE_DIR / "config" / "orderflow_config.json"
LOG_DIR = MODULE_DIR / "logs"
DAILY_DIR = PROJECT_ROOT / "Daily"
INI_FILE = DAILY_DIR / "config.ini"


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure logging to both file and console"""
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"orderflow_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    logger.addHandler(ch)

    return logger


def load_config() -> dict:
    """Load orderflow_config.json"""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_credentials(user: str) -> dict:
    """Load API credentials from Daily/config.ini for a given user"""
    config = configparser.ConfigParser()
    config.read(INI_FILE)

    section = f"API_CREDENTIALS_{user}"
    if not config.has_section(section):
        raise ValueError(f"No credentials section found for user '{user}' in {INI_FILE}")

    return {
        "api_key": config.get(section, "api_key"),
        "api_secret": config.get(section, "api_secret"),
        "access_token": config.get(section, "access_token"),
    }


def is_market_hours(config: dict) -> bool:
    """Check if current time is within configured market hours (IST)"""
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    market_hours = config.get("market_hours", {})
    start_str = market_hours.get("start", "09:10")
    end_str = market_hours.get("end", "15:35")

    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))

    start_time = now.replace(hour=start_h, minute=start_m, second=0)
    end_time = now.replace(hour=end_h, minute=end_m, second=0)

    return start_time <= now <= end_time


class OrderFlowService:
    """Main OrderFlow service that orchestrates all components"""

    def __init__(self, user: str, tickers: list = None):
        self.user = user
        self.logger = logging.getLogger("OrderFlowService")
        self.running = False

        # Load configs
        self.config = load_config()
        self.credentials = load_credentials(user)
        self.tickers = tickers or self.config.get("tickers", [])

        self.logger.info(f"OrderFlow service initializing for user={user}, "
                         f"tickers={self.tickers}")

        # Initialize KiteConnect
        self.kite = KiteConnect(api_key=self.credentials["api_key"])
        self.kite.set_access_token(self.credentials["access_token"])

        # Verify connection
        try:
            profile = self.kite.profile()
            self.logger.info(f"Authenticated as {profile['user_name']} ({profile['user_id']})")
        except Exception as e:
            self.logger.error(f"Failed to authenticate with Zerodha: {e}")
            raise

        # Initialize components
        db_config = self.config.get("db", {})
        self.db_manager = DBManager(db_config)
        self.instrument_resolver = InstrumentResolver(
            self.kite, self.config.get("exchange", "NSE")
        )
        self.tick_buffer = TickBuffer(
            self.db_manager,
            buffer_size=self.config.get("tick_buffer_size", 500),
            flush_interval=self.config.get("tick_flush_interval_seconds", 2.0),
        )
        self.metrics_engine = MetricsEngine(self.config)
        self.tick_collector = TickCollector(
            api_key=self.credentials["api_key"],
            access_token=self.credentials["access_token"],
            instrument_resolver=self.instrument_resolver,
            tick_buffer=self.tick_buffer,
            metrics_engine=self.metrics_engine,
        )

        # Metrics flush thread
        self._metrics_flush_thread = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def start(self):
        """Start the OrderFlow service"""
        self.logger.info("Starting OrderFlow service...")

        # Health check
        if not self.db_manager.health_check():
            self.logger.error("Database health check failed. Is TimescaleDB running?")
            raise RuntimeError("Database not reachable")

        self.running = True

        # Set tickers and start components
        self.tick_collector.set_tickers(self.tickers)
        self.tick_buffer.start()
        self.tick_collector.start()

        # Start metrics flush thread
        self._metrics_flush_thread = threading.Thread(
            target=self._metrics_flush_loop, daemon=True, name="MetricsFlush"
        )
        self._metrics_flush_thread.start()

        self.logger.info("OrderFlow service started successfully")
        self._run_loop()

    def _run_loop(self):
        """Main run loop — monitors health and logs stats periodically"""
        stats_interval = 60  # Log stats every 60 seconds
        last_stats = time.time()

        while self.running:
            time.sleep(5)

            # Periodic stats logging
            if time.time() - last_stats >= stats_interval:
                self._log_stats()
                last_stats = time.time()

            # Check if WebSocket is alive
            if not self.tick_collector.is_connected and self.running:
                self.logger.warning("WebSocket disconnected, collector will auto-reconnect")

    def _metrics_flush_loop(self):
        """Background thread that flushes computed metrics to DB"""
        interval = self.config.get("metrics_interval_seconds", 10)

        while self.running:
            time.sleep(interval)
            try:
                metrics = self.metrics_engine.drain_metrics()
                if metrics:
                    self.db_manager.insert_orderflow_metrics(metrics)
                    self.logger.debug(f"Flushed {len(metrics)} metric records to DB")
            except Exception as e:
                self.logger.error(f"Error flushing metrics: {e}")

    def _log_stats(self):
        """Log current service statistics"""
        collector_stats = self.tick_collector.stats
        buffer_stats = self.tick_buffer.stats
        engine_states = self.metrics_engine.get_all_states()

        self.logger.info(
            f"Stats: ticks={collector_stats['total_ticks']} "
            f"connected={collector_stats['connected']} "
            f"buf_pending={buffer_stats['pending_ticks']}t/{buffer_stats['pending_depths']}d "
            f"buf_flushed={buffer_stats['ticks_flushed']}t/{buffer_stats['depths_flushed']}d"
        )

        for symbol, state in engine_states.items():
            if state:
                self.logger.info(
                    f"  {symbol}: price={state['last_price']:.2f} "
                    f"cvd={state['cumulative_delta']:+.0f} "
                    f"phase={state['phase']}({state['phase_confidence']:.2f}) "
                    f"imb_l5={state['bid_ask_imbalance_l5']:.3f}"
                )

    def stop(self):
        """Graceful shutdown of all components"""
        self.logger.info("Stopping OrderFlow service...")
        self.running = False

        self.tick_collector.stop()
        self.tick_buffer.stop()

        # Final metrics flush
        try:
            metrics = self.metrics_engine.drain_metrics()
            if metrics:
                self.db_manager.insert_orderflow_metrics(metrics)
                self.logger.info(f"Final flush: {len(metrics)} metric records")
        except Exception as e:
            self.logger.error(f"Error in final metrics flush: {e}")

        self.db_manager.close()
        self.logger.info("OrderFlow service stopped")

    def _handle_shutdown(self, signum, frame):
        """Signal handler for graceful shutdown"""
        sig_name = signal.Signals(signum).name
        self.logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.stop()
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="OrderFlow Service")
    parser.add_argument("--user", type=str, default="Sai",
                        help="User name for API credentials (default: Sai)")
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated list of tickers (overrides config)")
    args = parser.parse_args()

    logger = setup_logging(LOG_DIR)

    tickers = args.tickers.split(",") if args.tickers else None

    service = OrderFlowService(user=args.user, tickers=tickers)
    service.start()


if __name__ == "__main__":
    main()
