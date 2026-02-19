"""
Group Model — tracks an entry + target order pair with depth cascading.

Each grid trade is a "group" consisting of:
  1. Entry order (BUY for Bot A, SELL for Bot B)
  2. One or more target orders (placed as entry fills, with sub-target cascading)

Lifecycle: ENTRY_PENDING → [ENTRY_PARTIAL →] TARGET_PENDING → CLOSED

Depth cascading (ported from TollGate):
  D1 target placed for each partial/full entry fill increment.
  When D1 fills, D2 re-entry placed, then D3 close, etc.
  Odd depths = closing (PnL), even depths = re-entry (no PnL).
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class GroupStatus:
    ENTRY_PENDING = "ENTRY_PENDING"    # entry order placed, awaiting fill
    ENTRY_PARTIAL = "ENTRY_PARTIAL"    # entry partially filled, D1 targets placed
    ENTRY_FILLED = "ENTRY_FILLED"      # entry filled, target not yet placed
    TARGET_PENDING = "TARGET_PENDING"  # target order placed, awaiting fill
    CLOSED = "CLOSED"                  # target filled, PnL realized
    CANCELLED = "CANCELLED"            # manually cancelled


@dataclass
class Group:
    """A single grid trade: entry order + target order(s) with depth cascading."""
    group_id: str
    bot: str                # "A" (buy bot) or "B" (sell bot)
    subset_index: int
    entry_side: str         # "BUY" or "SELL"
    entry_price: float      # theoretical entry price (grid level)
    target_price: float     # theoretical target price
    qty: int
    status: str = GroupStatus.ENTRY_PENDING

    # Order IDs from broker
    entry_order_id: Optional[str] = None

    # Target tracking — list of targets (one per partial fill increment, with depth cascading)
    # Each: {order_id, qty, filled_qty, fill_price, placed_at, depth, tag, ref_price}
    target_orders: List[Dict] = field(default_factory=list)
    target_seq: int = 0                 # Counter for target naming (D101, D102, ...)

    # Partial fill tracking
    entry_filled_so_far: int = 0           # cumulative entry fills (for increment calc)

    # Pair tracking (cumulative across all partial + final fills)
    pair_hedged_qty: int = 0               # total secondary shares hedged
    pair_hedge_total: float = 0.0          # sum(price * qty) for hedge PnL calc
    pair_hedge_seq: int = 0                # sequence counter for PH order naming
    pair_unwound_qty: int = 0              # total secondary shares unwound
    pair_unwind_total: float = 0.0         # sum(price * qty) for unwind PnL calc
    pair_unwind_seq: int = 0               # sequence counter for PU order naming
    pair_pnl: float = 0.0                  # realized pair PnL
    pair_orders: List[Dict] = field(default_factory=list)  # [{xts_id, custom_id, side, qty, price, ts, role}]

    # Fill info (actual prices from broker)
    entry_fill_price: Optional[float] = None
    entry_fill_qty: Optional[int] = None
    target_fill_price: Optional[float] = None
    target_fill_qty: Optional[int] = None

    # Legacy single target_order_id — kept for backward compat in cancel_all, reconciliation
    # Reads first target's order_id when accessed
    target_filled_so_far: int = 0          # cumulative target fills (legacy compat)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    entry_filled_at: Optional[str] = None
    target_filled_at: Optional[str] = None
    closed_at: Optional[str] = None

    # Realized PnL for this group
    realized_pnl: float = 0.0

    @staticmethod
    def create(bot: str, subset_index: int, entry_side: str,
               entry_price: float, target_price: float, qty: int) -> 'Group':
        """Factory method to create a new group."""
        return Group(
            group_id=uuid.uuid4().hex[:8],
            bot=bot,
            subset_index=subset_index,
            entry_side=entry_side,
            entry_price=entry_price,
            target_price=target_price,
            qty=qty,
        )

    @property
    def target_side(self) -> str:
        """The opposite side of the entry."""
        return "SELL" if self.entry_side == "BUY" else "BUY"

    @property
    def target_order_id(self) -> Optional[str]:
        """Backward compat: return first target's order_id (or None)."""
        if self.target_orders:
            return self.target_orders[0].get('order_id')
        return None

    @property
    def all_targets_filled(self) -> bool:
        """True if all placed targets have been fully filled."""
        if not self.target_orders:
            return False
        return all(t.get('filled_qty', 0) >= t.get('qty', 0) for t in self.target_orders)

    @property
    def total_target_filled_qty(self) -> int:
        """Sum of filled qty across all target orders."""
        return sum(t.get('filled_qty', 0) for t in self.target_orders)

    @property
    def max_target_depth(self) -> int:
        """Highest depth among target orders (0 if no targets)."""
        if not self.target_orders:
            return 0
        return max(t.get('depth', 1) for t in self.target_orders)

    def leaf_targets_filled(self, max_sub_depth: int) -> bool:
        """
        True when all sub-chains have completed to max depth.

        A leaf target is one at max_sub_depth. All leaf targets must be fully filled,
        and their total filled qty must cover the entry filled qty.
        """
        leaf_targets = [t for t in self.target_orders if t.get('depth', 1) == max_sub_depth]
        if not leaf_targets:
            return False
        all_filled = all(t.get('filled_qty', 0) >= t.get('qty', 0) for t in leaf_targets)
        total_leaf_filled = sum(t.get('filled_qty', 0) for t in leaf_targets)
        return all_filled and total_leaf_filled >= self.entry_filled_so_far

    def has_pending_sub_targets(self) -> bool:
        """True if any target at depth > 1 exists (sub-chain is active)."""
        return any(t.get('depth', 1) > 1 for t in self.target_orders)

    @property
    def pair_hedge_vwap(self) -> float:
        """Volume-weighted average price of all hedge fills."""
        return round(self.pair_hedge_total / self.pair_hedged_qty, 2) if self.pair_hedged_qty else 0.0

    @property
    def pair_unwind_vwap(self) -> float:
        """Volume-weighted average price of all unwind fills."""
        return round(self.pair_unwind_total / self.pair_unwound_qty, 2) if self.pair_unwound_qty else 0.0

    def to_dict(self) -> dict:
        return {
            'group_id': self.group_id,
            'bot': self.bot,
            'subset_index': self.subset_index,
            'entry_side': self.entry_side,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'qty': self.qty,
            'status': self.status,
            'entry_order_id': self.entry_order_id,
            'target_orders': self.target_orders,
            'target_seq': self.target_seq,
            'entry_filled_so_far': self.entry_filled_so_far,
            'target_filled_so_far': self.target_filled_so_far,
            'pair_hedged_qty': self.pair_hedged_qty,
            'pair_hedge_total': self.pair_hedge_total,
            'pair_hedge_seq': self.pair_hedge_seq,
            'pair_unwound_qty': self.pair_unwound_qty,
            'pair_unwind_total': self.pair_unwind_total,
            'pair_unwind_seq': self.pair_unwind_seq,
            'pair_pnl': self.pair_pnl,
            'pair_orders': self.pair_orders,
            'pair_hedge_vwap': self.pair_hedge_vwap,
            'pair_unwind_vwap': self.pair_unwind_vwap,
            'entry_fill_price': self.entry_fill_price,
            'entry_fill_qty': self.entry_fill_qty,
            'target_fill_price': self.target_fill_price,
            'target_fill_qty': self.target_fill_qty,
            'created_at': self.created_at,
            'entry_filled_at': self.entry_filled_at,
            'target_filled_at': self.target_filled_at,
            'closed_at': self.closed_at,
            'realized_pnl': self.realized_pnl,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Group':
        # Backward compat: migrate old target_order_id to target_orders list
        target_orders = d.get('target_orders', [])
        if not target_orders:
            old_tid = d.get('target_order_id')
            if old_tid:
                target_orders = [{
                    'order_id': old_tid,
                    'qty': d.get('target_fill_qty') or d.get('qty', 0),
                    'filled_qty': d.get('target_filled_so_far', 0),
                    'fill_price': d.get('target_fill_price'),
                    'depth': 1,
                    'tag': 'D101',
                    'ref_price': d.get('entry_fill_price'),
                }]

        return cls(
            group_id=d['group_id'],
            bot=d['bot'],
            subset_index=d['subset_index'],
            entry_side=d['entry_side'],
            entry_price=d['entry_price'],
            target_price=d['target_price'],
            qty=d['qty'],
            status=d.get('status', GroupStatus.ENTRY_PENDING),
            entry_order_id=d.get('entry_order_id'),
            target_orders=target_orders,
            target_seq=d.get('target_seq', 0),
            entry_filled_so_far=d.get('entry_filled_so_far', 0),
            target_filled_so_far=d.get('target_filled_so_far', 0),
            pair_hedged_qty=d.get('pair_hedged_qty', 0),
            pair_hedge_total=d.get('pair_hedge_total', 0.0),
            pair_hedge_seq=d.get('pair_hedge_seq', 0),
            pair_unwound_qty=d.get('pair_unwound_qty', 0),
            pair_unwind_total=d.get('pair_unwind_total', 0.0),
            pair_unwind_seq=d.get('pair_unwind_seq', 0),
            pair_pnl=d.get('pair_pnl', 0.0),
            pair_orders=d.get('pair_orders', []),
            entry_fill_price=d.get('entry_fill_price'),
            entry_fill_qty=d.get('entry_fill_qty'),
            target_fill_price=d.get('target_fill_price'),
            target_fill_qty=d.get('target_fill_qty'),
            created_at=d.get('created_at', ''),
            entry_filled_at=d.get('entry_filled_at'),
            target_filled_at=d.get('target_filled_at'),
            closed_at=d.get('closed_at'),
            realized_pnl=d.get('realized_pnl', 0.0),
        )
