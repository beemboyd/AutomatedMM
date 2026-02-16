"""
Buy Bot A — Buy side of the grid.

Places BUY LIMIT entries at levels below anchor price.
On entry fill: places SELL LIMIT target.
On target fill: closes group, optionally re-enters.

Grid levels use geometric doubling:
  Subset 0: buy at anchor - 1p, target +2p
  Subset 1: buy at anchor - 3p, target +4p
  Subset 2: buy at anchor - 7p, target +8p
  ...
All sell targets converge to anchor + base_grid_space.
"""

import logging
from typing import Dict, List
from datetime import datetime

from .grid import GridLevel
from .group import Group, GroupStatus
from .state import StateManager
from .hybrid_client import HybridClient
from .config import GridConfig, generate_order_id

logger = logging.getLogger(__name__)


class BuyBot:
    """
    Bot A: manages buy entries and their corresponding sell targets.

    Each grid level can have at most one active group.
    When a group completes (target fills), the level is freed
    and a new entry can be placed if auto_reenter is enabled.
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
        for group in self.state.get_open_groups_for_bot('A'):
            self.level_groups[group.subset_index] = group.group_id
        logger.info("BuyBot restored %d active levels from state",
                     len(self.level_groups))

    def place_entries(self):
        """Place buy entry orders at all free grid levels."""
        placed = 0
        for level in self.levels:
            if level.subset_index in self.level_groups:
                logger.debug("BuyBot level %d already active (group=%s)",
                             level.subset_index,
                             self.level_groups[level.subset_index])
                continue
            if self._place_entry(level):
                placed += 1
        logger.info("BuyBot placed %d/%d entry orders", placed, len(self.levels))

    def _place_entry(self, level: GridLevel) -> bool:
        """Place a single buy entry order and register the group."""
        group = Group.create(
            bot="A",
            subset_index=level.subset_index,
            entry_side="BUY",
            entry_price=level.entry_price,
            target_price=level.target_price,
            qty=level.qty,
        )

        entry_oid = generate_order_id("EN", level.subset_index, "A", group.group_id)
        order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type="BUY",
            qty=level.qty,
            price=level.entry_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=entry_oid,
        )

        if order_id:
            group.entry_order_id = order_id
            self.state.add_group(group)
            self.level_groups[level.subset_index] = group.group_id
            logger.info("BuyBot ENTRY: subset=%d, BUY %d @ %.2f, group=%s, order=%s [%s]",
                        level.subset_index, level.qty, level.entry_price,
                        group.group_id, order_id, entry_oid)
            return True
        else:
            logger.error("BuyBot ENTRY FAILED: subset=%d, BUY %d @ %.2f",
                         level.subset_index, level.qty, level.entry_price)
            return False

    def on_entry_fill(self, group: Group, fill_price: float, fill_qty: int):
        """
        Handle buy entry fill → place sell target.

        Target price uses the theoretical grid level target,
        not computed from fill price. This preserves grid convergence.
        """
        group.status = GroupStatus.ENTRY_FILLED
        group.entry_fill_price = fill_price
        group.entry_fill_qty = fill_qty
        group.entry_filled_at = datetime.now().isoformat()

        logger.info("BuyBot ENTRY FILLED: group=%s, BUY %d @ %.2f (level=%.2f)",
                     group.group_id, fill_qty, fill_price, group.entry_price)

        # Place sell target at the theoretical target price
        target_oid = generate_order_id("TP", group.subset_index, "A", group.group_id)
        order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type="SELL",
            qty=fill_qty,
            price=group.target_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=target_oid,
        )

        if order_id:
            group.target_order_id = order_id
            group.status = GroupStatus.TARGET_PENDING
            self.state.register_order(order_id, group.group_id)
            logger.info("BuyBot TARGET: group=%s, SELL %d @ %.2f, order=%s [%s]",
                        group.group_id, fill_qty, group.target_price, order_id, target_oid)
        else:
            logger.error("BuyBot TARGET FAILED: group=%s, SELL %d @ %.2f",
                         group.group_id, fill_qty, group.target_price)

        # Pair trade: BUY TATSILV entry → SELL pair symbol
        if self.config.has_pair:
            pair_oid = generate_order_id("PR", group.subset_index, "A", group.group_id)
            pair_id = self.client.place_market_order(
                self.config.pair_symbol, "SELL", self.config.pair_qty,
                self.config.exchange, self.config.product,
                order_unique_id=pair_oid)
            if pair_id:
                group.pair_order_id = pair_id
                logger.info("BuyBot PAIR: group=%s, SELL %s %d, order=%s [%s]",
                            group.group_id, self.config.pair_symbol,
                            self.config.pair_qty, pair_id, pair_oid)
            else:
                logger.error("BuyBot PAIR FAILED: group=%s, SELL %s %d",
                             group.group_id, self.config.pair_symbol,
                             self.config.pair_qty)

    def on_target_fill(self, group: Group, fill_price: float, fill_qty: int):
        """
        Handle sell target fill → close group, compute PnL.

        PnL = (sell_price - buy_price) * qty
        """
        group.target_fill_price = fill_price
        group.target_fill_qty = fill_qty
        group.target_filled_at = datetime.now().isoformat()

        # PnL from the actual fill prices
        buy_price = group.entry_fill_price or group.entry_price
        group.realized_pnl = round((fill_price - buy_price) * fill_qty, 2)

        logger.info("BuyBot TARGET FILLED: group=%s, SELL %d @ %.2f, PnL=%.2f",
                     group.group_id, fill_qty, fill_price, group.realized_pnl)

        # Reverse pair: SELL target filled → BUY pair symbol back
        if self.config.has_pair:
            pair_oid = generate_order_id("PR", group.subset_index, "A", group.group_id)
            pair_id = self.client.place_market_order(
                self.config.pair_symbol, "BUY", self.config.pair_qty,
                self.config.exchange, self.config.product,
                order_unique_id=pair_oid)
            if pair_id:
                logger.info("BuyBot PAIR UNWIND: group=%s, BUY %s %d, order=%s [%s]",
                            group.group_id, self.config.pair_symbol,
                            self.config.pair_qty, pair_id, pair_oid)
            else:
                logger.error("BuyBot PAIR UNWIND FAILED: group=%s, BUY %s %d",
                             group.group_id, self.config.pair_symbol,
                             self.config.pair_qty)

        # Free the level
        if group.subset_index in self.level_groups:
            del self.level_groups[group.subset_index]

        # Close the group
        self.state.close_group(group.group_id)

        # Re-enter if configured
        if self.config.auto_reenter:
            for level in self.levels:
                if level.subset_index == group.subset_index:
                    logger.info("BuyBot RE-ENTERING: subset=%d", level.subset_index)
                    self._place_entry(level)
                    break

    def cancel_all(self):
        """Cancel all active entry and target orders for this bot."""
        cancelled = 0
        for group in list(self.state.get_open_groups_for_bot('A')):
            if group.status == GroupStatus.ENTRY_PENDING and group.entry_order_id:
                if self.client.cancel_order(group.entry_order_id):
                    cancelled += 1
            elif group.status == GroupStatus.TARGET_PENDING and group.target_order_id:
                if self.client.cancel_order(group.target_order_id):
                    cancelled += 1
        logger.info("BuyBot cancelled %d orders", cancelled)
        return cancelled
