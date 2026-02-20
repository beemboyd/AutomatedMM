"""
PnL Database Manager — PostgreSQL connection pool and CRUD operations.

Follows OrderFlow/core/db_manager.py pattern: ThreadedConnectionPool,
context manager, RealDictCursor. Uses the shared tick_data database
with tg_ table prefix.
"""

import os
import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

# Default DB config from Daily/config.ini [OrderFlow] section
_DEFAULT_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'name': 'tick_data',
    'user': 'maverick',
    'password': '',
}


class PnLDBManager:
    """PostgreSQL connection pool manager for PnL tracking tables."""

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.db_config = db_config or _DEFAULT_DB_CONFIG
        self.pool = None
        self._init_pool()

    def _init_pool(self):
        """Initialize threaded connection pool (min=2, max=5)."""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=2,
                maxconn=5,
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                dbname=self.db_config.get('name', 'tick_data'),
                user=self.db_config.get('user', 'maverick'),
                password=self.db_config.get('password', ''),
            )
            logger.info("PnL DB pool initialized (min=2, max=5)")
        except Exception as e:
            logger.error("Failed to initialize PnL DB pool: %s", e)
            raise

    @contextmanager
    def get_connection(self):
        """Thread-safe connection from pool with auto-commit/rollback."""
        conn = None
        try:
            conn = self.pool.getconn()
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("PnL DB error: %s", e)
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def ensure_schema(self):
        """Run schema.sql to create tables if they don't exist."""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path) as f:
            sql = f.read()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
        logger.info("PnL schema ensured")

    # ── Write Methods ──

    def create_session(self, bot_type: str, config_snapshot: Optional[dict] = None,
                       account_id: str = '') -> int:
        """Create a new session row. Returns session_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tg_sessions (bot_type, config_snapshot, account_id)
                VALUES (%s, %s, %s)
                RETURNING session_id
            """, (bot_type, json.dumps(config_snapshot) if config_snapshot else None,
                  account_id))
            session_id = cursor.fetchone()[0]
            logger.info("Created session %d for %s (account=%s)", session_id, bot_type, account_id)
            return session_id

    def end_session(self, session_id: int, total_pnl: float = 0,
                    total_cycles: int = 0, status: str = 'ended'):
        """Mark a session as ended."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tg_sessions
                SET ended_at = NOW(), status = %s,
                    total_pnl = %s, total_cycles = %s
                WHERE session_id = %s
            """, (status, total_pnl, total_cycles, session_id))
            logger.info("Ended session %d: status=%s, pnl=%.2f, cycles=%d",
                        session_id, status, total_pnl, total_cycles)

    def create_pair(self, session_id: int, primary_ticker: str,
                    secondary_ticker: Optional[str], pair_type: str,
                    anchor_price: float, grid_spacing: float,
                    levels_per_side: int, qty_per_level: int,
                    product: str = 'CNC') -> int:
        """Create a pair row. Returns pair_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tg_pairs (session_id, primary_ticker, secondary_ticker,
                    pair_type, anchor_price, grid_spacing, levels_per_side,
                    qty_per_level, product)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING pair_id
            """, (session_id, primary_ticker, secondary_ticker, pair_type,
                  anchor_price, grid_spacing, levels_per_side, qty_per_level,
                  product))
            pair_id = cursor.fetchone()[0]
            logger.info("Created pair %d: %s-%s (session=%d)",
                        pair_id, primary_ticker, secondary_ticker, session_id)
            return pair_id

    def open_cycle(self, pair_id: int, session_id: int, group_id: str,
                   bot_id: str, grid_level: int, cycle_number: int,
                   entry_side: str, entry_price: float, target_price: float,
                   qty: int) -> int:
        """Create a cycle row. Returns cycle_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tg_cycles (pair_id, session_id, group_id, bot_id,
                    grid_level, cycle_number, entry_side, entry_price,
                    target_price, qty)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING cycle_id
            """, (pair_id, session_id, group_id, bot_id, grid_level,
                  cycle_number, entry_side, entry_price, target_price, qty))
            return cursor.fetchone()[0]

    def close_cycle(self, cycle_id: int, entry_fill_price: float = 0,
                    target_fill_price: float = 0, primary_pnl: float = 0,
                    pair_pnl: float = 0):
        """Close a cycle with fill prices and PnL."""
        combined = primary_pnl + pair_pnl
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tg_cycles
                SET status = 'closed', closed_at = NOW(),
                    entry_fill_price = %s, target_fill_price = %s,
                    primary_pnl = %s, pair_pnl = %s, combined_pnl = %s
                WHERE cycle_id = %s
            """, (entry_fill_price, target_fill_price, primary_pnl,
                  pair_pnl, combined, cycle_id))

    def cancel_cycle(self, cycle_id: int):
        """Mark a cycle as cancelled."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tg_cycles
                SET status = 'cancelled', closed_at = NOW()
                WHERE cycle_id = %s
            """, (cycle_id,))

    def record_transaction(self, cycle_id: Optional[int], pair_id: int,
                           session_id: int, ticker: str, side: str,
                           qty: int, price: float, txn_type: str,
                           is_partial: bool = False,
                           order_id: Optional[str] = None,
                           group_id: Optional[str] = None,
                           pnl_increment: float = 0,
                           running_session_pnl: float = 0,
                           net_inventory: int = 0,
                           metadata: Optional[dict] = None) -> int:
        """Record a single fill transaction. Returns txn_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tg_transactions (cycle_id, pair_id, session_id,
                    ticker, side, qty, price, txn_type, is_partial,
                    order_id, group_id, pnl_increment, running_session_pnl,
                    net_inventory, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING txn_id
            """, (cycle_id, pair_id, session_id, ticker, side, qty, price,
                  txn_type, is_partial, order_id, group_id, pnl_increment,
                  running_session_pnl, net_inventory,
                  json.dumps(metadata) if metadata else '{}'))
            return cursor.fetchone()[0]

    def upsert_inventory(self, session_id: int, ticker: str,
                         qty_delta: int, price: float):
        """Update inventory position (upsert). Tracks net qty and running avg price."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tg_inventory (session_id, ticker, net_qty, avg_price, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (session_id, ticker) DO UPDATE SET
                    net_qty = tg_inventory.net_qty + EXCLUDED.net_qty,
                    avg_price = CASE
                        WHEN (tg_inventory.net_qty + EXCLUDED.net_qty) = 0 THEN 0
                        ELSE EXCLUDED.avg_price
                    END,
                    updated_at = NOW()
            """, (session_id, ticker, qty_delta, price))

    # ── Read Methods (Account-Based Daily Reports) ──

    def get_daily_summary_tollgate(self, days: int = 90) -> List[dict]:
        """Day-by-day summary for 01MU01 (TollGate): PnL, round trips, SOD/EOD inventory, VWAP."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                WITH daily_net AS (
                    SELECT
                        t.ts::date AS day,
                        SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) AS buy_qty,
                        SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) AS sell_qty,
                        CASE WHEN SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) > 0
                             THEN SUM(CASE WHEN t.side = 'BUY' THEN t.price * t.qty ELSE 0 END)
                                  / SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END)
                             ELSE 0 END AS buy_vwap,
                        CASE WHEN SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) > 0
                             THEN SUM(CASE WHEN t.side = 'SELL' THEN t.price * t.qty ELSE 0 END)
                                  / SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END)
                             ELSE 0 END AS sell_vwap,
                        SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END) AS day_net_qty
                    FROM tg_transactions t
                    JOIN tg_sessions s ON t.session_id = s.session_id
                    WHERE s.bot_type = 'tollgate'
                    GROUP BY t.ts::date
                ),
                daily_inventory AS (
                    SELECT
                        day, buy_qty, sell_qty, buy_vwap, sell_vwap, day_net_qty,
                        COALESCE(SUM(day_net_qty) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS sod_inventory,
                        SUM(day_net_qty) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS eod_inventory
                    FROM daily_net
                ),
                daily_cycles AS (
                    SELECT
                        c.closed_at::date AS day,
                        COUNT(*) AS round_trips,
                        COALESCE(SUM(c.combined_pnl), 0) AS pnl
                    FROM tg_cycles c
                    JOIN tg_sessions s ON c.session_id = s.session_id
                    WHERE c.status = 'closed' AND s.bot_type = 'tollgate'
                    GROUP BY c.closed_at::date
                ),
                daily_txn_pnl AS (
                    SELECT
                        t.ts::date AS day,
                        COALESCE(SUM(t.pnl_increment), 0) AS txn_pnl,
                        COUNT(DISTINCT CASE WHEN t.pnl_increment > 0 THEN t.group_id END) AS txn_round_trips
                    FROM tg_transactions t
                    JOIN tg_sessions s ON t.session_id = s.session_id
                    WHERE s.bot_type = 'tollgate'
                    GROUP BY t.ts::date
                )
                SELECT
                    di.day,
                    COALESCE(NULLIF(dc.pnl, 0), dtp.txn_pnl, 0) AS pnl,
                    GREATEST(COALESCE(dc.round_trips, 0), COALESCE(dtp.txn_round_trips, 0)) AS round_trips,
                    di.sod_inventory, di.eod_inventory,
                    ROUND(di.buy_vwap::numeric, 4) AS buy_vwap,
                    ROUND(di.sell_vwap::numeric, 4) AS sell_vwap,
                    di.buy_qty, di.sell_qty
                FROM daily_inventory di
                LEFT JOIN daily_cycles dc ON di.day = dc.day
                LEFT JOIN daily_txn_pnl dtp ON di.day = dtp.day
                WHERE di.day >= CURRENT_DATE - make_interval(days => %s)
                ORDER BY di.day DESC
            """, (days,))
            return [dict(r) for r in cursor.fetchall()]

    def get_daily_summary_grid(self, days: int = 90, account_id: Optional[str] = None) -> dict:
        """Day-by-day summary for TG Grid: primaries per ticker + hedge summary.
        Optionally filter by account_id (e.g. '01MU06', '01MU07')."""
        acct_filter = "AND s.account_id = %s" if account_id else ""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Primaries: per (day, ticker) with SOD/EOD inventory
            # account_id params appear in CTEs before the days param in final WHERE
            params_primary = []
            if account_id:
                params_primary.extend([account_id, account_id])  # daily_net + daily_cycles CTEs
            params_primary.append(days)
            cursor.execute(f"""
                WITH daily_net AS (
                    SELECT
                        t.ts::date AS day,
                        t.ticker,
                        SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) AS buy_qty,
                        SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) AS sell_qty,
                        CASE WHEN SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) > 0
                             THEN SUM(CASE WHEN t.side = 'BUY' THEN t.price * t.qty ELSE 0 END)
                                  / SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END)
                             ELSE 0 END AS buy_vwap,
                        CASE WHEN SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) > 0
                             THEN SUM(CASE WHEN t.side = 'SELL' THEN t.price * t.qty ELSE 0 END)
                                  / SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END)
                             ELSE 0 END AS sell_vwap,
                        SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END) AS day_net_qty
                    FROM tg_transactions t
                    JOIN tg_sessions s ON t.session_id = s.session_id
                    WHERE s.bot_type = 'tg_grid'
                      AND t.txn_type IN ('ENTRY', 'TARGET')
                      {acct_filter}
                    GROUP BY t.ts::date, t.ticker
                ),
                daily_inventory AS (
                    SELECT
                        day, ticker, buy_qty, sell_qty, buy_vwap, sell_vwap, day_net_qty,
                        COALESCE(SUM(day_net_qty) OVER (PARTITION BY ticker ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS sod_inventory,
                        SUM(day_net_qty) OVER (PARTITION BY ticker ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS eod_inventory
                    FROM daily_net
                ),
                daily_cycles AS (
                    SELECT
                        c.closed_at::date AS day,
                        p.primary_ticker AS ticker,
                        COUNT(*) AS round_trips,
                        COALESCE(SUM(c.primary_pnl), 0) AS primary_pnl,
                        COALESCE(SUM(c.pair_pnl), 0) AS pair_pnl,
                        COALESCE(SUM(c.combined_pnl), 0) AS combined_pnl
                    FROM tg_cycles c
                    JOIN tg_sessions s ON c.session_id = s.session_id
                    JOIN tg_pairs p ON c.pair_id = p.pair_id
                    WHERE c.status = 'closed' AND s.bot_type = 'tg_grid'
                      {acct_filter}
                    GROUP BY c.closed_at::date, p.primary_ticker
                )
                SELECT
                    di.day, di.ticker,
                    COALESCE(dc.primary_pnl, 0) AS primary_pnl,
                    COALESCE(dc.pair_pnl, 0) AS pair_pnl,
                    COALESCE(dc.combined_pnl, 0) AS combined_pnl,
                    COALESCE(dc.round_trips, 0) AS round_trips,
                    di.sod_inventory, di.eod_inventory,
                    ROUND(di.buy_vwap::numeric, 4) AS buy_vwap,
                    ROUND(di.sell_vwap::numeric, 4) AS sell_vwap,
                    di.buy_qty, di.sell_qty
                FROM daily_inventory di
                LEFT JOIN daily_cycles dc ON di.day = dc.day AND di.ticker = dc.ticker
                WHERE di.day >= CURRENT_DATE - make_interval(days => %s)
                ORDER BY di.day DESC, di.ticker
            """, params_primary)
            primaries = [dict(r) for r in cursor.fetchall()]

            # Hedges: per day from PAIR_HEDGE/PAIR_UNWIND transactions
            # account_id params appear in CTEs before the days param in final WHERE
            params_hedge = []
            if account_id:
                params_hedge.extend([account_id, account_id])  # hedge_txns + hedge_cost CTEs
            params_hedge.append(days)
            cursor.execute(f"""
                WITH hedge_txns AS (
                    SELECT
                        t.ts::date AS day,
                        SUM(CASE WHEN t.txn_type = 'PAIR_HEDGE' THEN 1 ELSE 0 END) AS hedges_placed,
                        SUM(CASE WHEN t.txn_type = 'PAIR_UNWIND' THEN 1 ELSE 0 END) AS hedges_unwound,
                        SUM(CASE WHEN t.txn_type = 'PAIR_HEDGE' THEN t.qty ELSE 0 END) AS hedge_qty,
                        SUM(CASE WHEN t.txn_type = 'PAIR_UNWIND' THEN t.qty ELSE 0 END) AS unwind_qty
                    FROM tg_transactions t
                    JOIN tg_sessions s ON t.session_id = s.session_id
                    WHERE s.bot_type = 'tg_grid'
                      AND t.txn_type IN ('PAIR_HEDGE', 'PAIR_UNWIND')
                      {acct_filter}
                    GROUP BY t.ts::date
                ),
                hedge_cost AS (
                    SELECT
                        c.closed_at::date AS day,
                        COALESCE(SUM(c.pair_pnl), 0) AS hedge_cost
                    FROM tg_cycles c
                    JOIN tg_sessions s ON c.session_id = s.session_id
                    WHERE c.status = 'closed' AND s.bot_type = 'tg_grid'
                      {acct_filter}
                    GROUP BY c.closed_at::date
                )
                SELECT
                    ht.day,
                    ht.hedges_placed, ht.hedges_unwound,
                    ht.hedge_qty, ht.unwind_qty,
                    COALESCE(hc.hedge_cost, 0) AS hedge_cost
                FROM hedge_txns ht
                LEFT JOIN hedge_cost hc ON ht.day = hc.day
                WHERE ht.day >= CURRENT_DATE - make_interval(days => %s)
                ORDER BY ht.day DESC
            """, params_hedge)
            hedges = [dict(r) for r in cursor.fetchall()]

            return {'primaries': primaries, 'hedges': hedges}

    def get_day_transactions(self, bot_type: str, day: str,
                             ticker: Optional[str] = None) -> List[dict]:
        """Drill-down: all transactions for a specific bot/day/ticker."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            conditions = ["s.bot_type = %s", "t.ts::date = %s::date"]
            params: list = [bot_type, day]
            if ticker:
                conditions.append("t.ticker = %s")
                params.append(ticker)
            where = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT t.ts, t.ticker, t.side, t.qty, t.price, t.txn_type,
                       t.pnl_increment, t.order_id, t.net_inventory
                FROM tg_transactions t
                JOIN tg_sessions s ON t.session_id = s.session_id
                WHERE {where}
                ORDER BY t.ts
            """, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_cumulative_pnl(self, bot_type: str, days: int = 90) -> List[dict]:
        """Cumulative PnL series per day for chart.

        Uses transaction pnl_increment as the primary source (always recorded),
        with closed cycle combined_pnl as an alternative when available.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT
                    day,
                    daily_pnl,
                    SUM(daily_pnl) OVER (ORDER BY day) AS cumulative_pnl
                FROM (
                    SELECT
                        t.ts::date AS day,
                        COALESCE(SUM(t.pnl_increment), 0) AS daily_pnl
                    FROM tg_transactions t
                    JOIN tg_sessions s ON t.session_id = s.session_id
                    WHERE s.bot_type = %s
                    GROUP BY t.ts::date
                ) daily
                WHERE day >= CURRENT_DATE - make_interval(days => %s)
                ORDER BY day
            """, (bot_type, days))
            return [dict(r) for r in cursor.fetchall()]

    def get_overall_vwap(self, bot_type: str) -> dict:
        """Overall Buy VWAP and Sell VWAP across all transactions for a bot type."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT
                    CASE WHEN SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) > 0
                         THEN SUM(CASE WHEN t.side = 'BUY' THEN t.price * t.qty ELSE 0 END)
                              / SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END)
                         ELSE 0 END AS buy_vwap,
                    SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE 0 END) AS buy_qty,
                    CASE WHEN SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) > 0
                         THEN SUM(CASE WHEN t.side = 'SELL' THEN t.price * t.qty ELSE 0 END)
                              / SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END)
                         ELSE 0 END AS sell_vwap,
                    SUM(CASE WHEN t.side = 'SELL' THEN t.qty ELSE 0 END) AS sell_qty
                FROM tg_transactions t
                JOIN tg_sessions s ON t.session_id = s.session_id
                WHERE s.bot_type = %s
            """, (bot_type,))
            row = cursor.fetchone()
            if not row:
                return {'buy_vwap': 0, 'buy_qty': 0, 'sell_vwap': 0, 'sell_qty': 0}
            return dict(row)

    # ── Legacy Read Methods (kept for /api/state) ──

    def get_overview(self) -> dict:
        """KPI overview: today/week/all-time PnL, active sessions, inventory."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Active sessions
            cursor.execute("""
                SELECT session_id, bot_type, started_at, total_pnl, total_cycles
                FROM tg_sessions WHERE status = 'active'
                ORDER BY started_at DESC
            """)
            active_sessions = [dict(r) for r in cursor.fetchall()]

            # Today's PnL from transactions
            cursor.execute("""
                SELECT COALESCE(SUM(pnl_increment), 0) AS today_pnl,
                       COUNT(*) AS today_txns
                FROM tg_transactions WHERE ts::date = CURRENT_DATE
            """)
            today = dict(cursor.fetchone())

            # Today's cycles
            cursor.execute("""
                SELECT COUNT(*) AS today_cycles
                FROM tg_cycles
                WHERE status = 'closed' AND closed_at::date = CURRENT_DATE
            """)
            today['today_cycles'] = dict(cursor.fetchone())['today_cycles']

            # This week PnL
            cursor.execute("""
                SELECT COALESCE(SUM(pnl_increment), 0) AS week_pnl
                FROM tg_transactions
                WHERE ts >= date_trunc('week', CURRENT_DATE)
            """)
            week_pnl = dict(cursor.fetchone())['week_pnl']

            # All-time PnL
            cursor.execute("""
                SELECT COALESCE(SUM(pnl_increment), 0) AS all_time_pnl,
                       COUNT(*) AS total_txns
                FROM tg_transactions
            """)
            all_time = dict(cursor.fetchone())

            # All-time cycles
            cursor.execute("""
                SELECT COUNT(*) AS total_cycles
                FROM tg_cycles WHERE status = 'closed'
            """)
            all_time['total_cycles'] = dict(cursor.fetchone())['total_cycles']

            # Bot breakdown (today)
            cursor.execute("""
                SELECT s.bot_type,
                       COALESCE(SUM(t.pnl_increment), 0) AS pnl,
                       COUNT(DISTINCT c.cycle_id) AS cycles
                FROM tg_transactions t
                JOIN tg_sessions s ON t.session_id = s.session_id
                LEFT JOIN tg_cycles c ON t.cycle_id = c.cycle_id AND c.status = 'closed'
                WHERE t.ts::date = CURRENT_DATE
                GROUP BY s.bot_type
            """)
            bot_breakdown = [dict(r) for r in cursor.fetchall()]

            return {
                'active_sessions': active_sessions,
                'today_pnl': today['today_pnl'],
                'today_txns': today['today_txns'],
                'today_cycles': today['today_cycles'],
                'week_pnl': week_pnl,
                'all_time_pnl': all_time['all_time_pnl'],
                'all_time_txns': all_time['total_txns'],
                'all_time_cycles': all_time['total_cycles'],
                'bot_breakdown': bot_breakdown,
            }

    def get_sessions(self, bot_type: Optional[str] = None, limit: int = 50) -> List[dict]:
        """Session list, optionally filtered by bot_type."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if bot_type:
                cursor.execute("""
                    SELECT * FROM tg_sessions
                    WHERE bot_type = %s
                    ORDER BY started_at DESC LIMIT %s
                """, (bot_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM tg_sessions
                    ORDER BY started_at DESC LIMIT %s
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_session_detail(self, session_id: int) -> Optional[dict]:
        """Session + its pairs."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM tg_sessions WHERE session_id = %s",
                           (session_id,))
            session = cursor.fetchone()
            if not session:
                return None
            session = dict(session)

            cursor.execute("""
                SELECT * FROM tg_pairs WHERE session_id = %s
                ORDER BY pair_id
            """, (session_id,))
            session['pairs'] = [dict(r) for r in cursor.fetchall()]
            return session

    def get_pair_cycles(self, pair_id: int, limit: int = 200) -> List[dict]:
        """Cycles for a pair, newest first."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM tg_cycles WHERE pair_id = %s
                ORDER BY opened_at DESC LIMIT %s
            """, (pair_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_cycle_transactions(self, cycle_id: int) -> List[dict]:
        """Transactions within a cycle."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM tg_transactions WHERE cycle_id = %s
                ORDER BY ts
            """, (cycle_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_transactions(self, session_id: Optional[int] = None,
                         bot_type: Optional[str] = None,
                         ticker: Optional[str] = None,
                         txn_type: Optional[str] = None,
                         from_date: Optional[str] = None,
                         to_date: Optional[str] = None,
                         limit: int = 200, offset: int = 0) -> List[dict]:
        """Filtered transaction log."""
        conditions = []
        params = []

        if session_id:
            conditions.append("t.session_id = %s")
            params.append(session_id)
        if bot_type:
            conditions.append("s.bot_type = %s")
            params.append(bot_type)
        if ticker:
            conditions.append("t.ticker = %s")
            params.append(ticker)
        if txn_type:
            conditions.append("t.txn_type = %s")
            params.append(txn_type)
        if from_date:
            conditions.append("t.ts::date >= %s::date")
            params.append(from_date)
        if to_date:
            conditions.append("t.ts::date <= %s::date")
            params.append(to_date)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(f"""
                SELECT t.*, s.bot_type
                FROM tg_transactions t
                JOIN tg_sessions s ON t.session_id = s.session_id
                {where}
                ORDER BY t.ts DESC
                LIMIT %s OFFSET %s
            """, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_inventory_current(self) -> List[dict]:
        """Current positions across active sessions."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT i.*, s.bot_type
                FROM tg_inventory i
                JOIN tg_sessions s ON i.session_id = s.session_id
                WHERE s.status = 'active' AND i.net_qty != 0
                ORDER BY i.ticker
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_pnl_by_ticker(self, days: Optional[int] = None) -> List[dict]:
        """PnL grouped by ticker."""
        date_filter = ""
        params = []
        if days:
            date_filter = "WHERE t.ts >= NOW() - make_interval(days => %s)"
            params.append(days)

        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(f"""
                SELECT t.ticker,
                       COALESCE(SUM(t.pnl_increment), 0) AS total_pnl,
                       COUNT(*) AS txn_count
                FROM tg_transactions t
                {date_filter}
                GROUP BY t.ticker
                ORDER BY total_pnl DESC
            """, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_pnl_by_day(self, days: int = 30) -> List[dict]:
        """PnL grouped by date."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT ts::date AS day,
                       COALESCE(SUM(pnl_increment), 0) AS daily_pnl,
                       COUNT(*) AS txn_count
                FROM tg_transactions
                WHERE ts >= NOW() - make_interval(days => %s)
                GROUP BY ts::date
                ORDER BY day
            """, (days,))
            return [dict(r) for r in cursor.fetchall()]

    def get_pnl_by_pair(self, days: Optional[int] = None) -> List[dict]:
        """PnL grouped by primary-secondary pair."""
        date_filter = ""
        params = []
        if days:
            date_filter = "AND t.ts >= NOW() - make_interval(days => %s)"
            params.append(days)

        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(f"""
                SELECT p.primary_ticker, p.secondary_ticker, p.pair_type,
                       COALESCE(SUM(t.pnl_increment), 0) AS total_pnl,
                       COUNT(*) AS txn_count
                FROM tg_transactions t
                JOIN tg_pairs p ON t.pair_id = p.pair_id
                WHERE 1=1 {date_filter}
                GROUP BY p.primary_ticker, p.secondary_ticker, p.pair_type
                ORDER BY total_pnl DESC
            """, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_pnl_timeline(self, days: int = 30) -> List[dict]:
        """Cumulative PnL time series (one point per transaction)."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT ts, pnl_increment, running_session_pnl, ticker, txn_type
                FROM tg_transactions
                WHERE ts >= NOW() - make_interval(days => %s)
                    AND pnl_increment != 0
                ORDER BY ts
            """, (days,))
            rows = [dict(r) for r in cursor.fetchall()]

            # Compute cumulative across all sessions
            cumulative = 0
            for row in rows:
                cumulative += row['pnl_increment']
                row['cumulative_pnl'] = round(cumulative, 2)
            return rows

    def get_stats(self) -> dict:
        """Win rate, avg PnL/cycle, best/worst day."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Cycle stats
            cursor.execute("""
                SELECT COUNT(*) AS total_cycles,
                       SUM(CASE WHEN combined_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                       SUM(CASE WHEN combined_pnl < 0 THEN 1 ELSE 0 END) AS losses,
                       COALESCE(AVG(combined_pnl), 0) AS avg_pnl,
                       COALESCE(MAX(combined_pnl), 0) AS best_cycle,
                       COALESCE(MIN(combined_pnl), 0) AS worst_cycle
                FROM tg_cycles WHERE status = 'closed'
            """)
            cycle_stats = dict(cursor.fetchone())

            # Win rate
            total = cycle_stats['total_cycles'] or 1
            cycle_stats['win_rate'] = round(
                (cycle_stats['wins'] or 0) / total * 100, 1)

            # Best/worst day
            cursor.execute("""
                SELECT ts::date AS day, SUM(pnl_increment) AS daily_pnl
                FROM tg_transactions
                GROUP BY ts::date
                ORDER BY daily_pnl DESC
                LIMIT 1
            """)
            best_day = cursor.fetchone()
            cycle_stats['best_day'] = dict(best_day) if best_day else None

            cursor.execute("""
                SELECT ts::date AS day, SUM(pnl_increment) AS daily_pnl
                FROM tg_transactions
                GROUP BY ts::date
                ORDER BY daily_pnl ASC
                LIMIT 1
            """)
            worst_day = cursor.fetchone()
            cycle_stats['worst_day'] = dict(worst_day) if worst_day else None

            return cycle_stats

    def get_active_session(self, bot_type: str,
                           primary_ticker: Optional[str] = None,
                           account_id: Optional[str] = None) -> Optional[dict]:
        """Find the last active session for a bot type (for restoration)."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if primary_ticker:
                acct_filter = "AND s.account_id = %s" if account_id else ""
                params = [primary_ticker, bot_type]
                if account_id:
                    params.append(account_id)
                cursor.execute(f"""
                    SELECT s.*, p.pair_id, p.primary_ticker
                    FROM tg_sessions s
                    LEFT JOIN tg_pairs p ON s.session_id = p.session_id
                        AND p.primary_ticker = %s
                    WHERE s.bot_type = %s AND s.status = 'active' {acct_filter}
                    ORDER BY s.started_at DESC LIMIT 1
                """, params)
            else:
                if account_id:
                    cursor.execute("""
                        SELECT * FROM tg_sessions
                        WHERE bot_type = %s AND status = 'active' AND account_id = %s
                        ORDER BY started_at DESC LIMIT 1
                    """, (bot_type, account_id))
                else:
                    cursor.execute("""
                        SELECT * FROM tg_sessions
                        WHERE bot_type = %s AND status = 'active'
                        ORDER BY started_at DESC LIMIT 1
                    """, (bot_type,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def health_check(self) -> bool:
        """Check if the database is reachable."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error("PnL DB health check failed: %s", e)
            return False

    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("PnL DB connection pool closed")
