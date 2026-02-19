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

        entry_oid = generate_order_id(
            self.config.symbol, self.config.pair_symbol or "NONE",
            level.subset_index, "EN", "A", group.group_id)
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

            # PnL: open cycle
            pnl = getattr(self.config, '_pnl', None)
            if pnl and getattr(self.config, '_pnl_pair_id', None):
                cid = pnl.open_cycle(
                    self.config._pnl_pair_id, self.config._pnl_session_id,
                    group.group_id, 'A', level.subset_index, 1,
                    'BUY', level.entry_price, level.target_price, level.qty)
                if cid:
                    self.config._pnl_cycle_ids[group.group_id] = cid

            return True
        else:
            logger.error("BuyBot ENTRY FAILED: subset=%d, BUY %d @ %.2f",
                         level.subset_index, level.qty, level.entry_price)
            return False

    def place_pair_hedge(self, group: Group, pair_qty: int):
        """
        Place pair HEDGE: BUY primary entry → SELL secondary.

        Updates group cumulative tracking fields.
        """
        group.pair_hedge_seq += 1
        pair_oid = generate_order_id(
            self.config.symbol, self.config.pair_symbol,
            group.subset_index, "PH", "A", group.group_id,
            seq=group.pair_hedge_seq)
        pair_id, pair_price = self.client.place_market_order(
            self.config.pair_symbol, "SELL", pair_qty,
            self.config.exchange, self.config.product,
            order_unique_id=pair_oid)
        if pair_id:
            group.pair_hedged_qty += pair_qty
            group.pair_hedge_total += pair_price * pair_qty
            group.pair_orders.append({
                'xts_id': pair_id, 'custom_id': pair_oid,
                'side': 'SELL', 'qty': pair_qty, 'price': pair_price,
                'role': 'HEDGE', 'ts': datetime.now().isoformat(),
            })
            logger.info("BuyBot PAIR HEDGE: group=%s, SELL %s %d @ %.2f (total_hedged=%d, vwap=%.2f), order=%s [%s]",
                        group.group_id, self.config.pair_symbol,
                        pair_qty, pair_price, group.pair_hedged_qty,
                        group.pair_hedge_vwap, pair_id, pair_oid)

            # PnL: record pair hedge
            pnl = getattr(self.config, '_pnl', None)
            if pnl and getattr(self.config, '_pnl_pair_id', None):
                pnl.record_fill(
                    cycle_id=self.config._pnl_cycle_ids.get(group.group_id),
                    pair_id=self.config._pnl_pair_id,
                    session_id=self.config._pnl_session_id,
                    ticker=self.config.pair_symbol,
                    side='SELL', qty=pair_qty, price=pair_price,
                    txn_type='PAIR_HEDGE', order_id=pair_id,
                    group_id=group.group_id)
        else:
            logger.error("BuyBot PAIR HEDGE FAILED: group=%s, SELL %s %d",
                         group.group_id, self.config.pair_symbol, pair_qty)

    def place_pair_unwind(self, group: Group, pair_qty: int):
        """
        Place pair UNWIND: SELL primary target → BUY secondary back.

        Updates group cumulative tracking and computes pair PnL.
        BuyBot PnL = hedge_total - unwind_total (sold high, bought back low).
        """
        group.pair_unwind_seq += 1
        pair_oid = generate_order_id(
            self.config.symbol, self.config.pair_symbol,
            group.subset_index, "PU", "A", group.group_id,
            seq=group.pair_unwind_seq)
        pair_id, pair_price = self.client.place_market_order(
            self.config.pair_symbol, "BUY", pair_qty,
            self.config.exchange, self.config.product,
            order_unique_id=pair_oid)
        if pair_id:
            group.pair_unwound_qty += pair_qty
            group.pair_unwind_total += pair_price * pair_qty
            # Pair PnL: sold at hedge, bought back at unwind
            group.pair_pnl = round(group.pair_hedge_total - group.pair_unwind_total, 2)
            group.pair_orders.append({
                'xts_id': pair_id, 'custom_id': pair_oid,
                'side': 'BUY', 'qty': pair_qty, 'price': pair_price,
                'role': 'UNWIND', 'ts': datetime.now().isoformat(),
            })
            logger.info("BuyBot PAIR UNWIND: group=%s, BUY %s %d @ %.2f (total_unwound=%d, pair_pnl=%.2f), order=%s [%s]",
                        group.group_id, self.config.pair_symbol,
                        pair_qty, pair_price, group.pair_unwound_qty,
                        group.pair_pnl, pair_id, pair_oid)

            # PnL: record pair unwind
            pnl = getattr(self.config, '_pnl', None)
            if pnl and getattr(self.config, '_pnl_pair_id', None):
                pnl.record_fill(
                    cycle_id=self.config._pnl_cycle_ids.get(group.group_id),
                    pair_id=self.config._pnl_pair_id,
                    session_id=self.config._pnl_session_id,
                    ticker=self.config.pair_symbol,
                    side='BUY', qty=pair_qty, price=pair_price,
                    txn_type='PAIR_UNWIND', order_id=pair_id,
                    group_id=group.group_id,
                    pnl_increment=group.pair_pnl)
        else:
            logger.error("BuyBot PAIR UNWIND FAILED: group=%s, BUY %s %d",
                         group.group_id, self.config.pair_symbol, pair_qty)

    def cancel_all(self):
        """Cancel all active entry and target orders for this bot."""
        cancelled = 0
        for group in list(self.state.get_open_groups_for_bot('A')):
            if group.status in (GroupStatus.ENTRY_PENDING, GroupStatus.ENTRY_PARTIAL) and group.entry_order_id:
                if self.client.cancel_order(group.entry_order_id):
                    cancelled += 1
            if group.status in (GroupStatus.TARGET_PENDING, GroupStatus.ENTRY_PARTIAL):
                for target in group.target_orders:
                    tid = target.get('order_id')
                    if tid and target.get('filled_qty', 0) < target.get('qty', 0):
                        if self.client.cancel_order(tid):
                            cancelled += 1
        logger.info("BuyBot cancelled %d orders", cancelled)
        return cancelled
