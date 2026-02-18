"""
TollGate State Persistence — TollGateGroup + TollGateState.

Custom group model with partial fill support: target_orders is a list
of individual target orders (one per partial fill increment) instead of
a single target_order_id.

State is persisted to JSON with atomic writes (tmp + os.replace).
"""

import json
import os
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TollGateStatus:
    ENTRY_PENDING = "ENTRY_PENDING"
    ENTRY_PARTIAL = "ENTRY_PARTIAL"
    TARGET_PENDING = "TARGET_PENDING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class TollGateGroup:
    """
    A single grid trade with partial fill support.

    Unlike TG.Group which has a single target_order_id, TollGateGroup
    maintains a list of target_orders — one per partial fill increment.
    """
    group_id: str
    bot: str                    # "A" (buy) or "B" (sell)
    subset_index: int           # Grid level 0-9
    entry_side: str             # "BUY" or "SELL"
    entry_price: float          # Grid level entry price
    target_price: float         # Target price (entry +/- round_trip_profit)
    qty: int                    # Total qty for this level
    status: str = TollGateStatus.ENTRY_PENDING
    cycle_number: int = 1       # Which cycle this level is on

    # Entry tracking
    entry_order_id: Optional[str] = None
    entry_fill_price: float = 0.0       # VWAP across partials
    entry_filled_so_far: int = 0        # Cumulative qty filled on entry

    # Target tracking — list of targets (one per partial fill increment)
    target_orders: List[dict] = field(default_factory=list)
    # Each: {order_id, qty, filled_qty, fill_price, placed_at}
    target_seq: int = 0                 # Counter for target naming (T1, T2, T3...)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    entry_filled_at: Optional[str] = None
    closed_at: Optional[str] = None

    # PnL
    realized_pnl: float = 0.0          # Accumulated from filled targets

    @staticmethod
    def create(bot: str, subset_index: int, entry_side: str,
               entry_price: float, target_price: float, qty: int,
               cycle_number: int = 1) -> 'TollGateGroup':
        """Factory method to create a new group."""
        return TollGateGroup(
            group_id=uuid.uuid4().hex[:8],
            bot=bot,
            subset_index=subset_index,
            entry_side=entry_side,
            entry_price=entry_price,
            target_price=target_price,
            qty=qty,
            cycle_number=cycle_number,
        )

    @property
    def target_side(self) -> str:
        """The opposite side of the entry."""
        return "SELL" if self.entry_side == "BUY" else "BUY"

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
            'cycle_number': self.cycle_number,
            'entry_order_id': self.entry_order_id,
            'entry_fill_price': self.entry_fill_price,
            'entry_filled_so_far': self.entry_filled_so_far,
            'target_orders': self.target_orders,
            'target_seq': self.target_seq,
            'created_at': self.created_at,
            'entry_filled_at': self.entry_filled_at,
            'closed_at': self.closed_at,
            'realized_pnl': self.realized_pnl,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'TollGateGroup':
        return cls(
            group_id=d['group_id'],
            bot=d['bot'],
            subset_index=d['subset_index'],
            entry_side=d['entry_side'],
            entry_price=d['entry_price'],
            target_price=d['target_price'],
            qty=d['qty'],
            status=d.get('status', TollGateStatus.ENTRY_PENDING),
            cycle_number=d.get('cycle_number', 1),
            entry_order_id=d.get('entry_order_id'),
            entry_fill_price=d.get('entry_fill_price', 0.0),
            entry_filled_so_far=d.get('entry_filled_so_far', 0),
            target_orders=d.get('target_orders', []),
            target_seq=d.get('target_seq', 0),
            created_at=d.get('created_at', ''),
            entry_filled_at=d.get('entry_filled_at'),
            closed_at=d.get('closed_at'),
            realized_pnl=d.get('realized_pnl', 0.0),
        )


class TollGateState:
    """
    Manages TollGate trading state with JSON persistence.

    Simplified from TG.StateManager — no pair tracking fields.
    Adds net_inventory tracking and level_cycle_counters for
    cycle numbering across group re-entries.
    """

    def __init__(self, symbol: str = "SPCENET", state_dir: str = None):
        if state_dir is None:
            state_dir = os.path.join(os.path.dirname(__file__), 'state')
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = os.path.join(state_dir, f'{symbol}_tollgate_state.json')
        self.symbol = symbol

        # In-memory state
        self.open_groups: Dict[str, TollGateGroup] = {}
        self.closed_groups: List[dict] = []
        self.order_to_group: Dict[str, str] = {}

        # Trading state
        self.anchor_price: float = 0.0
        self.total_pnl: float = 0.0
        self.total_cycles: int = 0

        # Spacing (shared for both sides)
        self.current_spacing: float = 0.0

        # Reanchor counters
        self.buy_reanchor_count: int = 0
        self.sell_reanchor_count: int = 0
        self.total_reanchors: int = 0

        # Inventory tracking
        self.net_inventory: int = 0     # positive = long, negative = short

        # Level cycle counters: "BUY:0" -> next cycle number
        self.level_cycle_counters: Dict[str, int] = {}

    def add_group(self, group: TollGateGroup):
        """Register a new group and its entry order."""
        self.open_groups[group.group_id] = group
        if group.entry_order_id:
            self.order_to_group[group.entry_order_id] = group.group_id

    def get_group_by_order(self, order_id: str) -> Optional[TollGateGroup]:
        """Look up which group an order belongs to."""
        gid = self.order_to_group.get(str(order_id))
        if gid:
            return self.open_groups.get(gid)
        return None

    def register_order(self, order_id: str, group_id: str):
        """Map an order ID to a group ID (used for target orders)."""
        self.order_to_group[str(order_id)] = group_id

    def close_group(self, group_id: str):
        """Move a group from open to closed, accumulate PnL."""
        if group_id not in self.open_groups:
            logger.warning("Attempted to close unknown group: %s", group_id)
            return

        group = self.open_groups.pop(group_id)
        group.status = TollGateStatus.CLOSED
        group.closed_at = datetime.now().isoformat()
        self.total_pnl += group.realized_pnl
        self.total_cycles += 1
        self.closed_groups.append(group.to_dict())

        # Trim closed groups to last 500
        if len(self.closed_groups) > 500:
            self.closed_groups = self.closed_groups[-500:]

        logger.info("Group %s closed. PnL=%.2f, Total PnL=%.2f, Cycles=%d",
                     group_id, group.realized_pnl, self.total_pnl, self.total_cycles)

    def get_open_groups_for_bot(self, bot: str) -> List[TollGateGroup]:
        """Get all open groups for a specific bot (A or B)."""
        return [g for g in self.open_groups.values() if g.bot == bot]

    def get_active_subset_indices(self, bot: str) -> set:
        """Get subset indices that have active (non-closed) groups for a bot."""
        return {g.subset_index for g in self.open_groups.values() if g.bot == bot}

    def next_cycle_for_level(self, side: str, index: int) -> int:
        """Get and increment the cycle counter for a level."""
        key = f"{side}:{index}"
        current = self.level_cycle_counters.get(key, 1)
        self.level_cycle_counters[key] = current + 1
        return current

    def save(self):
        """Persist state to JSON with atomic write."""
        state = {
            'symbol': self.symbol,
            'anchor_price': self.anchor_price,
            'total_pnl': self.total_pnl,
            'total_cycles': self.total_cycles,
            'current_spacing': self.current_spacing,
            'buy_reanchor_count': self.buy_reanchor_count,
            'sell_reanchor_count': self.sell_reanchor_count,
            'total_reanchors': self.total_reanchors,
            'net_inventory': self.net_inventory,
            'level_cycle_counters': self.level_cycle_counters,
            'last_updated': datetime.now().isoformat(),
            'open_groups': {gid: g.to_dict() for gid, g in self.open_groups.items()},
            'closed_groups': self.closed_groups[-500:],
            'order_to_group': self.order_to_group,
        }
        tmp = self.state_file + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_file)
        logger.debug("State saved: %d open, %d closed, PnL=%.2f, inv=%d",
                      len(self.open_groups), len(self.closed_groups),
                      self.total_pnl, self.net_inventory)

    def load(self) -> bool:
        """Load state from JSON. Returns True if state was loaded."""
        if not os.path.exists(self.state_file):
            logger.info("No existing state file for %s", self.symbol)
            return False
        try:
            with open(self.state_file) as f:
                state = json.load(f)

            self.symbol = state.get('symbol', self.symbol)
            self.anchor_price = state.get('anchor_price', 0.0)
            self.total_pnl = state.get('total_pnl', 0.0)
            self.total_cycles = state.get('total_cycles', 0)
            self.current_spacing = state.get('current_spacing', 0.0)
            self.buy_reanchor_count = state.get('buy_reanchor_count', 0)
            self.sell_reanchor_count = state.get('sell_reanchor_count', 0)
            self.total_reanchors = state.get('total_reanchors', 0)
            self.net_inventory = state.get('net_inventory', 0)
            self.level_cycle_counters = state.get('level_cycle_counters', {})

            self.open_groups = {
                gid: TollGateGroup.from_dict(d)
                for gid, d in state.get('open_groups', {}).items()
            }
            self.closed_groups = state.get('closed_groups', [])
            self.order_to_group = state.get('order_to_group', {})

            logger.info("State loaded for %s: %d open, PnL=%.2f, cycles=%d, inv=%d",
                         self.symbol, len(self.open_groups),
                         self.total_pnl, self.total_cycles, self.net_inventory)
            return True
        except Exception as e:
            logger.error("Failed to load state for %s: %s", self.symbol, e)
            return False

    def print_summary(self):
        """Print current state summary."""
        open_a = [g for g in self.open_groups.values() if g.bot == 'A']
        open_b = [g for g in self.open_groups.values() if g.bot == 'B']

        ep_a = sum(1 for g in open_a if g.status == TollGateStatus.ENTRY_PENDING)
        ep_b = sum(1 for g in open_b if g.status == TollGateStatus.ENTRY_PENDING)
        pa_a = sum(1 for g in open_a if g.status == TollGateStatus.ENTRY_PARTIAL)
        pa_b = sum(1 for g in open_b if g.status == TollGateStatus.ENTRY_PARTIAL)
        tp_a = sum(1 for g in open_a if g.status == TollGateStatus.TARGET_PENDING)
        tp_b = sum(1 for g in open_b if g.status == TollGateStatus.TARGET_PENDING)

        print(f"\n  TOLLGATE STATE — {self.symbol}")
        print(f"  Anchor: {self.anchor_price:.2f}  |  Spacing: {self.current_spacing}  |  "
              f"PnL: {self.total_pnl:.2f}  |  Cycles: {self.total_cycles}")
        print(f"  Net Inventory: {self.net_inventory}  |  "
              f"Reanchors: {self.total_reanchors} (buy={self.buy_reanchor_count}, "
              f"sell={self.sell_reanchor_count})")
        print(f"  Buy (A):  {ep_a} entry pending, {pa_a} partial, {tp_a} target pending")
        print(f"  Sell (B): {ep_b} entry pending, {pa_b} partial, {tp_b} target pending")
        print(f"  Total open groups: {len(self.open_groups)}")
