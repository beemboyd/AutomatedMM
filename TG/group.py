"""
Group Model — tracks an entry + target order pair.

Each grid trade is a "group" consisting of:
  1. Entry order (BUY for Bot A, SELL for Bot B)
  2. Target order (opposite side, placed after entry fills)

Lifecycle: ENTRY_PENDING → ENTRY_FILLED → TARGET_PENDING → CLOSED
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class GroupStatus:
    ENTRY_PENDING = "ENTRY_PENDING"    # entry order placed, awaiting fill
    ENTRY_FILLED = "ENTRY_FILLED"      # entry filled, target not yet placed
    TARGET_PENDING = "TARGET_PENDING"  # target order placed, awaiting fill
    CLOSED = "CLOSED"                  # target filled, PnL realized
    CANCELLED = "CANCELLED"            # manually cancelled


@dataclass
class Group:
    """A single grid trade: entry order + target order."""
    group_id: str
    bot: str                # "A" (buy bot) or "B" (sell bot)
    subset_index: int
    entry_side: str         # "BUY" or "SELL"
    entry_price: float      # theoretical entry price (grid level)
    target_price: float     # theoretical target price
    qty: int
    status: str = GroupStatus.ENTRY_PENDING

    # Order IDs from Zerodha
    entry_order_id: Optional[str] = None
    target_order_id: Optional[str] = None

    # Fill info (actual prices from broker)
    entry_fill_price: Optional[float] = None
    entry_fill_qty: Optional[int] = None
    target_fill_price: Optional[float] = None
    target_fill_qty: Optional[int] = None

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
            'target_order_id': self.target_order_id,
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
            target_order_id=d.get('target_order_id'),
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
