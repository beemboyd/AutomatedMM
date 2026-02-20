"""
PnL Tracker — fail-safe wrapper around PnLDBManager.

All methods catch exceptions to ensure DB issues never crash the engine.
Trading continues even if PostgreSQL is down.
"""

import logging
from typing import Any, Dict, Optional

from .db_manager import PnLDBManager

logger = logging.getLogger(__name__)


class PnLTracker:
    """
    Fail-safe PnL tracking wrapper.

    All public methods catch exceptions and log warnings.
    DB failures are non-fatal — trading continues without tracking.
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        try:
            self.db = PnLDBManager(db_config)
            self.db.ensure_schema()
            logger.info("PnLTracker initialized successfully")
        except Exception as e:
            logger.warning("PnLTracker init failed (non-fatal): %s", e)
            self.db = None

    @property
    def available(self) -> bool:
        """True if the DB connection is available."""
        return self.db is not None

    # ── Session Lifecycle ──

    def start_session(self, bot_type: str,
                      config_snapshot: Optional[dict] = None,
                      account_id: str = '') -> Optional[int]:
        """Create a new session. Returns session_id or None."""
        if not self.db:
            return None
        try:
            # Mark any previous active sessions for this bot as crashed
            prev = self.db.get_active_session(bot_type, account_id=account_id or None)
            if prev:
                self.db.end_session(
                    prev['session_id'],
                    total_pnl=prev.get('total_pnl', 0),
                    total_cycles=prev.get('total_cycles', 0),
                    status='crashed')
                logger.info("Marked previous session %d as crashed", prev['session_id'])

            return self.db.create_session(bot_type, config_snapshot, account_id=account_id)
        except Exception as e:
            logger.warning("PnL start_session error (non-fatal): %s", e)
            return None

    def end_session(self, session_id: Optional[int],
                    total_pnl: float = 0, total_cycles: int = 0):
        """End a session gracefully."""
        if not self.db or not session_id:
            return
        try:
            self.db.end_session(session_id, total_pnl, total_cycles, 'ended')
        except Exception as e:
            logger.warning("PnL end_session error (non-fatal): %s", e)

    # ── Pair Registration ──

    def register_pair(self, session_id: Optional[int], primary: str,
                      secondary: Optional[str], pair_type: str,
                      anchor: float = 0, spacing: float = 0,
                      levels: int = 0, qty: int = 0,
                      product: str = 'CNC') -> Optional[int]:
        """Register a trading pair. Returns pair_id or None."""
        if not self.db or not session_id:
            return None
        try:
            return self.db.create_pair(
                session_id, primary, secondary, pair_type,
                anchor, spacing, levels, qty, product)
        except Exception as e:
            logger.warning("PnL register_pair error (non-fatal): %s", e)
            return None

    # ── Cycle Lifecycle ──

    def open_cycle(self, pair_id: Optional[int], session_id: Optional[int],
                   group_id: str, bot_id: str, grid_level: int,
                   cycle_number: int, entry_side: str, entry_price: float,
                   target_price: float, qty: int) -> Optional[int]:
        """Open a new cycle. Returns cycle_id or None."""
        if not self.db or not pair_id or not session_id:
            return None
        try:
            return self.db.open_cycle(
                pair_id, session_id, group_id, bot_id, grid_level,
                cycle_number, entry_side, entry_price, target_price, qty)
        except Exception as e:
            logger.warning("PnL open_cycle error (non-fatal): %s", e)
            return None

    def close_cycle(self, cycle_id: Optional[int],
                    entry_fill_price: float = 0,
                    target_fill_price: float = 0,
                    primary_pnl: float = 0,
                    pair_pnl: float = 0):
        """Close a completed cycle."""
        if not self.db or not cycle_id:
            return
        try:
            self.db.close_cycle(
                cycle_id, entry_fill_price, target_fill_price,
                primary_pnl, pair_pnl)
        except Exception as e:
            logger.warning("PnL close_cycle error (non-fatal): %s", e)

    def cancel_cycle(self, cycle_id: Optional[int]):
        """Cancel a cycle."""
        if not self.db or not cycle_id:
            return
        try:
            self.db.cancel_cycle(cycle_id)
        except Exception as e:
            logger.warning("PnL cancel_cycle error (non-fatal): %s", e)

    # ── Transaction Recording ──

    def record_fill(self, cycle_id: Optional[int], pair_id: Optional[int],
                    session_id: Optional[int], ticker: str, side: str,
                    qty: int, price: float, txn_type: str,
                    is_partial: bool = False,
                    order_id: Optional[str] = None,
                    group_id: Optional[str] = None,
                    pnl_increment: float = 0,
                    running_pnl: float = 0,
                    net_inventory: int = 0,
                    metadata: Optional[dict] = None):
        """Record a single fill transaction and update inventory."""
        if not self.db or not pair_id or not session_id:
            return
        try:
            self.db.record_transaction(
                cycle_id, pair_id, session_id, ticker, side, qty, price,
                txn_type, is_partial, order_id, group_id, pnl_increment,
                running_pnl, net_inventory, metadata)

            # Update inventory: BUY adds, SELL subtracts
            inv_delta = qty if side == 'BUY' else -qty
            self.db.upsert_inventory(session_id, ticker, inv_delta, price)
        except Exception as e:
            logger.warning("PnL record_fill error (non-fatal): %s", e)

    # ── Session Restoration ──

    def get_last_active_session(self, bot_type: str,
                                primary_ticker: Optional[str] = None,
                                account_id: Optional[str] = None) -> Optional[dict]:
        """Get the last active session for restoration check."""
        if not self.db:
            return None
        try:
            return self.db.get_active_session(bot_type, primary_ticker, account_id=account_id)
        except Exception as e:
            logger.warning("PnL get_last_active_session error (non-fatal): %s", e)
            return None
