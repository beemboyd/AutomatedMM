"""
Database Manager for VSR Simulations
Handles all database operations for trades, positions, and portfolio state
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SimulationDatabase:
    """Database manager for a single simulation instance"""

    def __init__(self, sim_id: str, db_path: Optional[str] = None):
        self.sim_id = sim_id
        if db_path is None:
            base_path = Path(__file__).parent.parent / "data"
            base_path.mkdir(exist_ok=True)
            db_path = base_path / f"simulation_{sim_id}.db"
        self.db_path = str(db_path)
        self._init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Portfolio state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_state (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    cash REAL NOT NULL,
                    invested REAL NOT NULL,
                    total_value REAL NOT NULL,
                    open_positions INTEGER NOT NULL,
                    daily_pnl REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    total_pnl_pct REAL DEFAULT 0,
                    metadata TEXT
                )
            """)

            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    signal_timestamp TEXT NOT NULL,
                    entry_timestamp TEXT,
                    exit_timestamp TEXT,
                    signal_price REAL NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    quantity INTEGER,
                    position_value REAL,
                    stop_loss REAL,
                    target REAL,
                    kc_lower REAL,
                    kc_upper REAL,
                    kc_middle REAL,
                    status TEXT DEFAULT 'PENDING',
                    exit_reason TEXT,
                    pnl REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    vsr_score REAL,
                    vsr_momentum REAL,
                    signal_pattern TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    opening_capital REAL NOT NULL,
                    closing_capital REAL NOT NULL,
                    cash REAL NOT NULL,
                    invested REAL NOT NULL,
                    trades_opened INTEGER DEFAULT 0,
                    trades_closed INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    daily_pnl REAL DEFAULT 0,
                    daily_pnl_pct REAL DEFAULT 0,
                    cumulative_pnl REAL DEFAULT 0,
                    cumulative_pnl_pct REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    open_positions INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Signals log table (all received signals)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    signal_type TEXT,
                    price REAL,
                    vsr_score REAL,
                    vsr_momentum REAL,
                    pattern TEXT,
                    action_taken TEXT,
                    rejection_reason TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_entry_ts ON trades(entry_timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals_log(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals_log(timestamp)")

    def get_current_portfolio_state(self) -> Optional[Dict]:
        """Get the most recent portfolio state"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM portfolio_state
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def update_portfolio_state(self, cash: float, invested: float, total_value: float,
                               open_positions: int, daily_pnl: float = 0,
                               total_pnl: float = 0, metadata: Dict = None):
        """Update portfolio state"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            initial_capital = 10000000  # 1 Crore
            total_pnl_pct = ((total_value - initial_capital) / initial_capital) * 100

            cursor.execute("""
                INSERT INTO portfolio_state
                (timestamp, cash, invested, total_value, open_positions,
                 daily_pnl, total_pnl, total_pnl_pct, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                cash, invested, total_value, open_positions,
                daily_pnl, total_pnl, total_pnl_pct,
                json.dumps(metadata) if metadata else None
            ))

    def create_trade(self, ticker: str, signal_price: float, signal_timestamp: str,
                     vsr_score: float = None, vsr_momentum: float = None,
                     signal_pattern: str = None, metadata: Dict = None) -> int:
        """Create a new trade entry (PENDING status)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades
                (ticker, signal_timestamp, signal_price, status,
                 vsr_score, vsr_momentum, signal_pattern, metadata)
                VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?)
            """, (
                ticker, signal_timestamp, signal_price,
                vsr_score, vsr_momentum, signal_pattern,
                json.dumps(metadata) if metadata else None
            ))
            return cursor.lastrowid

    def execute_trade(self, trade_id: int, entry_price: float, quantity: int,
                      stop_loss: float, target: float = None,
                      kc_lower: float = None, kc_upper: float = None,
                      kc_middle: float = None):
        """Execute a pending trade (move to OPEN status)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            position_value = entry_price * quantity
            cursor.execute("""
                UPDATE trades SET
                    entry_timestamp = ?,
                    entry_price = ?,
                    quantity = ?,
                    position_value = ?,
                    stop_loss = ?,
                    target = ?,
                    kc_lower = ?,
                    kc_upper = ?,
                    kc_middle = ?,
                    status = 'OPEN',
                    updated_at = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                entry_price, quantity, position_value,
                stop_loss, target, kc_lower, kc_upper, kc_middle,
                datetime.now().isoformat(), trade_id
            ))

    def close_trade(self, trade_id: int, exit_price: float, exit_reason: str):
        """Close an open trade"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get trade details
            cursor.execute("SELECT entry_price, quantity FROM trades WHERE id = ?", (trade_id,))
            trade = cursor.fetchone()
            if not trade:
                return

            entry_price, quantity = trade['entry_price'], trade['quantity']
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            cursor.execute("""
                UPDATE trades SET
                    exit_timestamp = ?,
                    exit_price = ?,
                    exit_reason = ?,
                    pnl = ?,
                    pnl_pct = ?,
                    status = 'CLOSED',
                    updated_at = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                exit_price, exit_reason, pnl, pnl_pct,
                datetime.now().isoformat(), trade_id
            ))

    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE status = 'OPEN'
                ORDER BY entry_timestamp DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_trades(self) -> List[Dict]:
        """Get all pending trades"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE status = 'PENDING'
                ORDER BY signal_timestamp DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_closed_trades(self, limit: int = 100) -> List[Dict]:
        """Get closed trades"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE status = 'CLOSED'
                ORDER BY exit_timestamp DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_trades(self) -> List[Dict]:
        """Get all trades"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_trade_by_ticker(self, ticker: str, status: str = None) -> Optional[Dict]:
        """Get trade by ticker and optionally status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM trades WHERE ticker = ? AND status = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (ticker, status))
            else:
                cursor.execute("""
                    SELECT * FROM trades WHERE ticker = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (ticker,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def log_signal(self, ticker: str, timestamp: str, signal_type: str = None,
                   price: float = None, vsr_score: float = None,
                   vsr_momentum: float = None, pattern: str = None,
                   action_taken: str = None, rejection_reason: str = None,
                   metadata: Dict = None):
        """Log a received signal"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals_log
                (timestamp, ticker, signal_type, price, vsr_score,
                 vsr_momentum, pattern, action_taken, rejection_reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, ticker, signal_type, price, vsr_score,
                vsr_momentum, pattern, action_taken, rejection_reason,
                json.dumps(metadata) if metadata else None
            ))

    def save_daily_snapshot(self, date: str, opening_capital: float,
                           closing_capital: float, cash: float, invested: float,
                           trades_opened: int, trades_closed: int,
                           winning_trades: int, losing_trades: int,
                           daily_pnl: float, cumulative_pnl: float,
                           max_drawdown: float, open_positions: int,
                           metadata: Dict = None):
        """Save end of day snapshot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            daily_pnl_pct = (daily_pnl / opening_capital) * 100 if opening_capital > 0 else 0
            cumulative_pnl_pct = (cumulative_pnl / 10000000) * 100  # vs initial capital

            cursor.execute("""
                INSERT OR REPLACE INTO daily_snapshots
                (date, opening_capital, closing_capital, cash, invested,
                 trades_opened, trades_closed, winning_trades, losing_trades,
                 daily_pnl, daily_pnl_pct, cumulative_pnl, cumulative_pnl_pct,
                 max_drawdown, open_positions, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, opening_capital, closing_capital, cash, invested,
                trades_opened, trades_closed, winning_trades, losing_trades,
                daily_pnl, daily_pnl_pct, cumulative_pnl, cumulative_pnl_pct,
                max_drawdown, open_positions,
                json.dumps(metadata) if metadata else None
            ))

    def get_daily_snapshots(self, limit: int = 30) -> List[Dict]:
        """Get daily snapshots"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daily_snapshots
                ORDER BY date DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """Get overall simulation statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total trades
            cursor.execute("SELECT COUNT(*) as total FROM trades")
            total_trades = cursor.fetchone()['total']

            # Closed trades stats
            cursor.execute("""
                SELECT
                    COUNT(*) as closed_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) as breakeven_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    AVG(pnl_pct) as avg_pnl_pct,
                    MAX(pnl) as max_win,
                    MIN(pnl) as max_loss
                FROM trades WHERE status = 'CLOSED'
            """)
            closed_stats = dict(cursor.fetchone())

            # Open trades
            cursor.execute("SELECT COUNT(*) as open FROM trades WHERE status = 'OPEN'")
            open_trades = cursor.fetchone()['open']

            # Win rate
            win_rate = 0
            if closed_stats['closed_trades'] and closed_stats['closed_trades'] > 0:
                win_rate = (closed_stats['winning_trades'] or 0) / closed_stats['closed_trades'] * 100

            return {
                'total_trades': total_trades,
                'open_trades': open_trades,
                'closed_trades': closed_stats['closed_trades'] or 0,
                'winning_trades': closed_stats['winning_trades'] or 0,
                'losing_trades': closed_stats['losing_trades'] or 0,
                'breakeven_trades': closed_stats['breakeven_trades'] or 0,
                'win_rate': round(win_rate, 2),
                'total_pnl': closed_stats['total_pnl'] or 0,
                'avg_pnl': closed_stats['avg_pnl'] or 0,
                'avg_pnl_pct': closed_stats['avg_pnl_pct'] or 0,
                'max_win': closed_stats['max_win'] or 0,
                'max_loss': closed_stats['max_loss'] or 0
            }

    def reset_simulation(self):
        """Reset simulation - clear all data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM portfolio_state")
            cursor.execute("DELETE FROM daily_snapshots")
            cursor.execute("DELETE FROM signals_log")
            logger.info(f"Simulation {self.sim_id} reset complete")
