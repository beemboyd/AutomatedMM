"""
PostgreSQL connection pool and batch operations for OrderFlow module.

Uses the existing tick_data database (shared with Simplified_India_TS).
Provides thread-safe connection pooling via psycopg2.pool.ThreadedConnectionPool
and high-performance batch inserts via psycopg2.extras.execute_values.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


class DBManager:
    """PostgreSQL connection pool manager with batch insert and query helpers"""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.pool = None
        self._init_pool()

    def _init_pool(self):
        """Initialize the threaded connection pool"""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=self.db_config.get("min_connections", 2),
                maxconn=self.db_config.get("max_connections", 10),
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 5432),
                dbname=self.db_config.get("name", "tick_data"),
                user=self.db_config.get("user", "maverick"),
                password=self.db_config.get("password", ""),
            )
            logger.info("PostgreSQL connection pool initialized "
                        f"(min={self.db_config.get('min_connections', 2)}, "
                        f"max={self.db_config.get('max_connections', 10)})")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for getting a connection from the pool"""
        conn = None
        try:
            conn = self.pool.getconn()
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    # ── Batch Insert Methods ──

    def insert_raw_ticks(self, ticks: List[Tuple]):
        """Batch insert raw tick records.

        Args:
            ticks: List of tuples matching of_raw_ticks columns:
                (ts, instrument_token, symbol, last_price, last_traded_quantity,
                 average_traded_price, volume_traded, total_buy_quantity,
                 total_sell_quantity, oi, ohlc_open, ohlc_high, ohlc_low,
                 ohlc_close, last_trade_time)
        """
        if not ticks:
            return

        query = """
            INSERT INTO of_raw_ticks (
                ts, instrument_token, symbol, last_price, last_traded_quantity,
                average_traded_price, volume_traded, total_buy_quantity,
                total_sell_quantity, oi, ohlc_open, ohlc_high, ohlc_low,
                ohlc_close, last_trade_time
            ) VALUES %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            psycopg2.extras.execute_values(cursor, query, ticks, page_size=500)
            logger.debug(f"Inserted {len(ticks)} raw ticks")

    def insert_depth_snapshots(self, snapshots: List[Tuple]):
        """Batch insert depth snapshot records.

        Args:
            snapshots: List of tuples matching of_depth_snapshots columns:
                (ts, instrument_token, symbol, buy_depth_json, sell_depth_json,
                 bid_ask_spread, total_bid_qty, total_ask_qty, bid_ask_imbalance)
        """
        if not snapshots:
            return

        query = """
            INSERT INTO of_depth_snapshots (
                ts, instrument_token, symbol, buy_depth, sell_depth,
                bid_ask_spread, total_bid_qty, total_ask_qty, bid_ask_imbalance
            ) VALUES %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            psycopg2.extras.execute_values(cursor, query, snapshots, page_size=500)
            logger.debug(f"Inserted {len(snapshots)} depth snapshots")

    def insert_orderflow_metrics(self, metrics: List[Tuple]):
        """Batch insert computed orderflow metric records.

        Args:
            metrics: List of tuples matching of_metrics columns
        """
        if not metrics:
            return

        query = """
            INSERT INTO of_metrics (
                ts, symbol, interval_seconds,
                trade_delta, cumulative_delta, delta_divergence,
                phase, phase_confidence,
                bid_ask_imbalance_l1, bid_ask_imbalance_l5,
                stacked_imbalance_buy, stacked_imbalance_sell,
                interval_volume, interval_buy_volume, interval_sell_volume, vwap,
                large_trade_count, large_trade_volume,
                absorption_buy, absorption_sell,
                price_open, price_high, price_low, price_close
            ) VALUES %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            psycopg2.extras.execute_values(cursor, query, metrics, page_size=100)
            logger.debug(f"Inserted {len(metrics)} orderflow metrics")

    # ── Query Methods ──

    def get_latest_metrics(self, symbol: str, limit: int = 1) -> List[Dict]:
        """Get the most recent orderflow metrics for a symbol"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM of_metrics
                WHERE symbol = %s
                ORDER BY ts DESC
                LIMIT %s
            """, (symbol, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_cvd_series(self, symbol: str, since_minutes: int = 60) -> List[Dict]:
        """Get CVD time series for a symbol over the last N minutes"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT ts, cumulative_delta, price_close, trade_delta, phase
                FROM of_metrics
                WHERE symbol = %s AND ts > NOW() - make_interval(mins => %s)
                ORDER BY ts ASC
            """, (symbol, since_minutes))
            return [dict(row) for row in cursor.fetchall()]

    def get_volume_profile(self, symbol: str, date: str = None) -> List[Dict]:
        """Get volume profile (price vs volume) for a symbol on a given date"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT
                    ROUND(last_price::numeric, 1) AS price_level,
                    SUM(last_traded_quantity) AS total_volume,
                    COUNT(*) AS tick_count
                FROM of_raw_ticks
                WHERE symbol = %s AND ts::date = %s::date
                GROUP BY price_level
                ORDER BY price_level
            """, (symbol, date))
            return [dict(row) for row in cursor.fetchall()]

    def get_phase_transitions(self, symbol: str, since_minutes: int = 120) -> List[Dict]:
        """Get phase change events for a symbol"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                WITH phase_changes AS (
                    SELECT ts, symbol, phase, phase_confidence, price_close,
                           cumulative_delta,
                           LAG(phase) OVER (ORDER BY ts) AS prev_phase
                    FROM of_metrics
                    WHERE symbol = %s AND ts > NOW() - make_interval(mins => %s)
                )
                SELECT * FROM phase_changes
                WHERE phase != prev_phase OR prev_phase IS NULL
                ORDER BY ts ASC
            """, (symbol, since_minutes))
            return [dict(row) for row in cursor.fetchall()]

    def get_1min_bars(self, symbol: str, since_minutes: int = 60) -> List[Dict]:
        """Get 1-minute aggregated bars from the materialized view"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM of_metrics_1min
                WHERE symbol = %s AND bucket > NOW() - make_interval(mins => %s)
                ORDER BY bucket ASC
            """, (symbol, since_minutes))
            return [dict(row) for row in cursor.fetchall()]

    def get_tick_count(self, symbol: str = None) -> int:
        """Get total tick count, optionally filtered by symbol"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if symbol:
                cursor.execute("SELECT COUNT(*) FROM of_raw_ticks WHERE symbol = %s", (symbol,))
            else:
                cursor.execute("SELECT COUNT(*) FROM of_raw_ticks")
            return cursor.fetchone()[0]

    def purge_old_data(self, raw_ticks_days: int = 7, depth_days: int = 7,
                       metrics_days: int = 90):
        """Delete data older than the specified retention periods"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM of_raw_ticks WHERE ts < NOW() - make_interval(days => %s)",
                (raw_ticks_days,))
            raw_deleted = cursor.rowcount

            cursor.execute(
                "DELETE FROM of_depth_snapshots WHERE ts < NOW() - make_interval(days => %s)",
                (depth_days,))
            depth_deleted = cursor.rowcount

            cursor.execute(
                "DELETE FROM of_metrics WHERE ts < NOW() - make_interval(days => %s)",
                (metrics_days,))
            metrics_deleted = cursor.rowcount

            logger.info(f"Purged old data: {raw_deleted} ticks, "
                        f"{depth_deleted} depth, {metrics_deleted} metrics")

    # ── Lifecycle ──

    def close(self):
        """Close all connections in the pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")

    def health_check(self) -> bool:
        """Check if the database is reachable"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
