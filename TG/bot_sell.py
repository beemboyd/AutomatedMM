"""
Sell Bot B — Sell side of the grid.

Places SELL LIMIT entries at levels above anchor price.
On entry fill: places BUY LIMIT target.
On target fill: closes group, optionally re-enters.

Grid levels use geometric doubling:
  Subset 0: sell at anchor + 1p, target -2p
  Subset 1: sell at anchor + 3p, target -4p
  Subset 2: sell at anchor + 7p, target -8p
  ...
All buy targets converge to anchor - base_grid_space.

IMPORTANT: For CNC equity, sell orders require existing holdings.
This bot checks available holdings before placing sell entries.
"""

import logging
from typing import Dict, List
from datetime import datetime

from .grid import GridLevel
from .group import Group, GroupStatus
from .state import StateManager
from .hybrid_client import HybridClient
from .config import GridConfig

logger = logging.getLogger(__name__)


class SellBot:
    """
    Bot B: manages sell entries and their corresponding buy targets.

    CNC constraint: sell entries require holdings. The bot checks
    available quantity before placing sell orders. If insufficient
    holdings, the level is skipped with a warning.
    """

    def __init__(self, levels: List[GridLevel], client: HybridClient,
                 state: StateManager, config: GridConfig):
        self.levels = levels
        self.client = client
        self.state = state
        self.config = config
        # subset_index → group_id for active groups at each level
        self.level_groups: Dict[int, str] = {}

    def restore_level_groups(self):
        """Rebuild level_groups mapping from loaded state."""
        for group in self.state.get_open_groups_for_bot('B'):
            self.level_groups[group.subset_index] = group.group_id
        logger.info("SellBot restored %d active levels from state",
                     len(self.level_groups))

    def place_entries(self):
        """
        Place sell entry orders at all free grid levels.

        Checks available holdings before placing. Sells are placed
        from the nearest level outward, stopping when holdings run out.
        """
        available = self.client.get_available_qty(self.config.symbol)
        logger.info("SellBot: available holdings for %s = %d",
                     self.config.symbol, available)

        # Account for qty already committed in pending sell entries
        committed = sum(
            g.qty for g in self.state.get_open_groups_for_bot('B')
            if g.status == GroupStatus.ENTRY_PENDING
        )
        available -= committed

        placed = 0
        for level in self.levels:
            if level.subset_index in self.level_groups:
                logger.debug("SellBot level %d already active (group=%s)",
                             level.subset_index,
                             self.level_groups[level.subset_index])
                continue

            if available < level.qty:
                logger.warning("SellBot: insufficient holdings for subset=%d "
                               "(need %d, available %d). Skipping.",
                               level.subset_index, level.qty, available)
                continue

            if self._place_entry(level):
                available -= level.qty
                placed += 1

        logger.info("SellBot placed %d/%d entry orders", placed, len(self.levels))

    def _place_entry(self, level: GridLevel) -> bool:
        """Place a single sell entry order and register the group."""
        group = Group.create(
            bot="B",
            subset_index=level.subset_index,
            entry_side="SELL",
            entry_price=level.entry_price,
            target_price=level.target_price,
            qty=level.qty,
        )

        order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type="SELL",
            qty=level.qty,
            price=level.entry_price,
            exchange=self.config.exchange,
            product=self.config.product,
        )

        if order_id:
            group.entry_order_id = order_id
            self.state.add_group(group)
            self.level_groups[level.subset_index] = group.group_id
            logger.info("SellBot ENTRY: subset=%d, SELL %d @ %.2f, group=%s, order=%s",
                        level.subset_index, level.qty, level.entry_price,
                        group.group_id, order_id)
            return True
        else:
            logger.error("SellBot ENTRY FAILED: subset=%d, SELL %d @ %.2f",
                         level.subset_index, level.qty, level.entry_price)
            return False

    def on_entry_fill(self, group: Group, fill_price: float, fill_qty: int):
        """
        Handle sell entry fill → place buy target.

        Target price uses the theoretical grid level target.
        """
        group.status = GroupStatus.ENTRY_FILLED
        group.entry_fill_price = fill_price
        group.entry_fill_qty = fill_qty
        group.entry_filled_at = datetime.now().isoformat()

        logger.info("SellBot ENTRY FILLED: group=%s, SELL %d @ %.2f (level=%.2f)",
                     group.group_id, fill_qty, fill_price, group.entry_price)

        # Place buy target at the theoretical target price
        order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type="BUY",
            qty=fill_qty,
            price=group.target_price,
            exchange=self.config.exchange,
            product=self.config.product,
        )

        if order_id:
            group.target_order_id = order_id
            group.status = GroupStatus.TARGET_PENDING
            self.state.register_order(order_id, group.group_id)
            logger.info("SellBot TARGET: group=%s, BUY %d @ %.2f, order=%s",
                        group.group_id, fill_qty, group.target_price, order_id)
        else:
            logger.error("SellBot TARGET FAILED: group=%s, BUY %d @ %.2f",
                         group.group_id, fill_qty, group.target_price)

    def on_target_fill(self, group: Group, fill_price: float, fill_qty: int):
        """
        Handle buy target fill → close group, compute PnL.

        PnL = (sell_price - buy_price) * qty
        """
        group.target_fill_price = fill_price
        group.target_fill_qty = fill_qty
        group.target_filled_at = datetime.now().isoformat()

        # PnL: sold at entry, bought back at target (lower price)
        sell_price = group.entry_fill_price or group.entry_price
        group.realized_pnl = round((sell_price - fill_price) * fill_qty, 2)

        logger.info("SellBot TARGET FILLED: group=%s, BUY %d @ %.2f, PnL=%.2f",
                     group.group_id, fill_qty, fill_price, group.realized_pnl)

        # Free the level
        if group.subset_index in self.level_groups:
            del self.level_groups[group.subset_index]

        # Close the group
        self.state.close_group(group.group_id)

        # Re-enter if configured and holdings available
        if self.config.auto_reenter:
            for level in self.levels:
                if level.subset_index == group.subset_index:
                    available = self.client.get_available_qty(self.config.symbol)
                    if available >= level.qty:
                        logger.info("SellBot RE-ENTERING: subset=%d", level.subset_index)
                        self._place_entry(level)
                    else:
                        logger.warning("SellBot: cannot re-enter subset=%d, "
                                       "insufficient holdings (%d < %d)",
                                       level.subset_index, available, level.qty)
                    break

    def cancel_all(self):
        """Cancel all active entry and target orders for this bot."""
        cancelled = 0
        for group in list(self.state.get_open_groups_for_bot('B')):
            if group.status == GroupStatus.ENTRY_PENDING and group.entry_order_id:
                if self.client.cancel_order(group.entry_order_id):
                    cancelled += 1
            elif group.status == GroupStatus.TARGET_PENDING and group.target_order_id:
                if self.client.cancel_order(group.target_order_id):
                    cancelled += 1
        logger.info("SellBot cancelled %d orders", cancelled)
        return cancelled
