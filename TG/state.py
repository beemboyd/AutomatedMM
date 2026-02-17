"""
State Persistence for Grid Trading Bot

Maintains all open/closed groups, order-to-group mappings,
and cumulative PnL. Persists to JSON with atomic writes.

State is keyed by symbol — one state file per symbol.
"""

import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

from .group import Group, GroupStatus

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages grid trading state with JSON persistence.

    State includes:
    - Open groups (entry pending or target pending)
    - Closed groups (last N for audit trail)
    - Order ID → Group ID mapping for fill routing
    - Cumulative PnL
    """

    def __init__(self, symbol: str, state_dir: str = None):
        if state_dir is None:
            state_dir = os.path.join(os.path.dirname(__file__), 'state')
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = os.path.join(state_dir, f'{symbol}_grid_state.json')
        self.symbol = symbol

        # In-memory state
        self.open_groups: Dict[str, Group] = {}      # group_id → Group
        self.closed_groups: List[Group] = []
        self.order_to_group: Dict[str, str] = {}     # order_id → group_id
        self.anchor_price: float = 0.0
        self.total_pnl: float = 0.0
        self.total_cycles: int = 0                    # completed round-trips

        # Epoch-based reanchor state
        self.main_anchor: float = 0.0                # original anchor (set once)
        self.buy_grid_levels: int = 0                # cumulative buy-side reanchors
        self.sell_grid_levels: int = 0               # cumulative sell-side reanchors
        self.current_buy_spacing: float = 0.0        # current buy grid spacing
        self.current_sell_spacing: float = 0.0       # current sell grid spacing

    def add_group(self, group: Group):
        """Register a new group and its entry order."""
        self.open_groups[group.group_id] = group
        if group.entry_order_id:
            self.order_to_group[group.entry_order_id] = group.group_id

    def get_group_by_order(self, order_id: str) -> Optional[Group]:
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
        group.status = GroupStatus.CLOSED
        group.closed_at = datetime.now().isoformat()
        self.total_pnl += group.realized_pnl
        self.total_cycles += 1
        self.closed_groups.append(group)

        # Trim closed groups to last 500
        if len(self.closed_groups) > 500:
            self.closed_groups = self.closed_groups[-500:]

        logger.info("Group %s closed. PnL=%.2f, Total PnL=%.2f, Cycles=%d",
                     group_id, group.realized_pnl, self.total_pnl, self.total_cycles)

    def get_open_groups_for_bot(self, bot: str) -> List[Group]:
        """Get all open groups for a specific bot (A or B)."""
        return [g for g in self.open_groups.values() if g.bot == bot]

    def get_active_subset_indices(self, bot: str) -> set:
        """Get subset indices that have active (non-closed) groups for a bot."""
        return {g.subset_index for g in self.open_groups.values() if g.bot == bot}

    def save(self):
        """Persist state to JSON with atomic write."""
        state = {
            'symbol': self.symbol,
            'anchor_price': self.anchor_price,
            'total_pnl': self.total_pnl,
            'total_cycles': self.total_cycles,
            'main_anchor': self.main_anchor,
            'buy_grid_levels': self.buy_grid_levels,
            'sell_grid_levels': self.sell_grid_levels,
            'current_buy_spacing': self.current_buy_spacing,
            'current_sell_spacing': self.current_sell_spacing,
            'last_updated': datetime.now().isoformat(),
            'open_groups': {gid: g.to_dict() for gid, g in self.open_groups.items()},
            'closed_groups': [g.to_dict() for g in self.closed_groups[-200:]],
            'order_to_group': self.order_to_group,
        }
        tmp = self.state_file + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_file)
        logger.debug("State saved: %d open, %d closed, PnL=%.2f",
                      len(self.open_groups), len(self.closed_groups), self.total_pnl)

    def load(self) -> bool:
        """Load state from JSON. Returns True if state was loaded."""
        if not os.path.exists(self.state_file):
            logger.info("No existing state file for %s", self.symbol)
            return False
        try:
            with open(self.state_file) as f:
                state = json.load(f)

            self.symbol = state['symbol']
            self.anchor_price = state['anchor_price']
            self.total_pnl = state.get('total_pnl', 0.0)
            self.total_cycles = state.get('total_cycles', 0)

            # Epoch-based reanchor state
            self.main_anchor = state.get('main_anchor', 0.0)
            self.buy_grid_levels = state.get('buy_grid_levels', 0)
            self.sell_grid_levels = state.get('sell_grid_levels', 0)
            self.current_buy_spacing = state.get('current_buy_spacing', 0.0)
            self.current_sell_spacing = state.get('current_sell_spacing', 0.0)

            self.open_groups = {
                gid: Group.from_dict(d)
                for gid, d in state.get('open_groups', {}).items()
            }
            self.closed_groups = [
                Group.from_dict(d)
                for d in state.get('closed_groups', [])
            ]
            self.order_to_group = state.get('order_to_group', {})

            logger.info("State loaded for %s: %d open groups, PnL=%.2f, cycles=%d",
                         self.symbol, len(self.open_groups),
                         self.total_pnl, self.total_cycles)
            return True
        except Exception as e:
            logger.error("Failed to load state for %s: %s", self.symbol, e)
            return False

    def print_summary(self):
        """Print current state summary."""
        open_a = [g for g in self.open_groups.values() if g.bot == 'A']
        open_b = [g for g in self.open_groups.values() if g.bot == 'B']
        entry_pending_a = sum(1 for g in open_a if g.status == GroupStatus.ENTRY_PENDING)
        target_pending_a = sum(1 for g in open_a if g.status == GroupStatus.TARGET_PENDING)
        entry_pending_b = sum(1 for g in open_b if g.status == GroupStatus.ENTRY_PENDING)
        target_pending_b = sum(1 for g in open_b if g.status == GroupStatus.TARGET_PENDING)

        print(f"\n  STATE SUMMARY — {self.symbol}")
        print(f"  Anchor: {self.anchor_price:.2f}  |  Main Anchor: {self.main_anchor:.2f}  |  PnL: {self.total_pnl:.2f}  |  Cycles: {self.total_cycles}")
        print(f"  Buy Grid Levels: {self.buy_grid_levels}  |  Buy Spacing: {self.current_buy_spacing}")
        print(f"  Sell Grid Levels: {self.sell_grid_levels}  |  Sell Spacing: {self.current_sell_spacing}")
        print(f"  Bot A (Buy):  {entry_pending_a} entry pending, {target_pending_a} target pending")
        print(f"  Bot B (Sell): {entry_pending_b} entry pending, {target_pending_b} target pending")
        print(f"  Total open groups: {len(self.open_groups)}")
