"""
Grid Engine — main orchestrator for the grid trading bot.

Responsibilities:
1. Initialize bots with computed grid levels
2. Poll Zerodha order status at regular intervals
3. Handle all entry/target fills (with depth cascading for partials)
4. Route pair hedge/unwind to appropriate bot
5. Persist state after every significant event
6. Handle startup with state recovery and order reconciliation

The engine is feed-agnostic: it reacts to order fills via polling,
not price ticks. A tick-based interface (on_tick) is provided for
future integration with real-time feeds.

Fill handling architecture (ported from TollGate):
- Entry fills (partial or complete) → engine._on_entry_fill()
  Places D1 target for each fill increment
- Target fills (partial or complete) → engine._on_target_fill()
  Computes PnL on odd depths, spawns sub-targets, checks cycle completion
- Pair hedge/unwind still delegated to bots
"""

import time
import signal
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import GridConfig, generate_order_id, depth_tag
from .grid import GridCalculator
from .group import Group, GroupStatus
from .state import StateManager
from .hybrid_client import HybridClient
from .bot_buy import BuyBot
from .bot_sell import SellBot

logger = logging.getLogger(__name__)


class GridEngine:
    """
    Main grid trading engine.

    Orchestrates Buy Bot A and Sell Bot B around an anchor price.
    Polls Zerodha for order status changes and handles all fill
    logic (entry + target + depth cascading) centrally.
    """

    def __init__(self, config: GridConfig, pnl_tracker=None):
        self.config = config
        self.running = False

        # PnL tracking (fail-safe — None if DB unavailable)
        self.pnl = pnl_tracker
        self._pnl_session_id = None
        self._pnl_pair_id = None

        # Initialize components
        self.client = HybridClient(
            interactive_key=config.interactive_key,
            interactive_secret=config.interactive_secret,
            zerodha_user=config.zerodha_user,
            root_url=config.xts_root,
            account_id=config.account_id,
        )
        self.state = StateManager(config.symbol, account_id=config.account_id)
        self.grid = GridCalculator(config)

        # Current spacing for each side (may increase over epochs)
        self.current_buy_spacing = config.base_grid_space
        self.current_sell_spacing = config.base_grid_space

        # Compute grid levels with separate spacings
        self.buy_levels = self.grid.compute_buy_levels(grid_space=self.current_buy_spacing)
        self.sell_levels = self.grid.compute_sell_levels(grid_space=self.current_sell_spacing)

        # Initialize bots (pnl refs attached via config to avoid changing signatures)
        config._pnl = pnl_tracker
        config._pnl_session_id = None
        config._pnl_pair_id = None
        config._pnl_cycle_ids = {}  # group_id -> cycle_id

        self.buy_bot = BuyBot(self.buy_levels, self.client, self.state, config)
        self.sell_bot = SellBot(self.sell_levels, self.client, self.state, config)

        # Order status cache: order_id → "status:filled_qty"
        # Detects incremental partial fills and prevents reprocessing
        self._order_status_cache: Dict[str, str] = {}

        # Re-anchor cooldown tracking
        self._last_reanchor_time: Optional[datetime] = None
        self._reanchor_cooldown = timedelta(seconds=60)

    def _disclosed_qty(self, qty: int) -> int:
        """Compute disclosed quantity for iceberg orders."""
        if self.config.disclosed_pct <= 0:
            return 0
        return max(1, round(qty * self.config.disclosed_pct / 100))

    def start(self):
        """
        Start the grid engine.

        1. Connect to Zerodha
        2. Load existing state or initialize fresh
        3. Place entry orders
        4. Enter main polling loop
        """
        # Connect
        if not self.client.connect():
            logger.error("Cannot start: XTS connection failed")
            return

        # Load state or start fresh
        if self.state.load():
            logger.info("Resuming from saved state")
            self.state.anchor_price = self.config.anchor_price
            # Restore spacing from persisted state
            if self.state.current_buy_spacing > 0:
                self.current_buy_spacing = self.state.current_buy_spacing
            if self.state.current_sell_spacing > 0:
                self.current_sell_spacing = self.state.current_sell_spacing
            # Recompute levels with restored spacings
            self.buy_levels = self.grid.compute_buy_levels(grid_space=self.current_buy_spacing)
            self.sell_levels = self.grid.compute_sell_levels(grid_space=self.current_sell_spacing)
            self.buy_bot.levels = self.buy_levels
            self.sell_bot.levels = self.sell_levels
            self.buy_bot.restore_level_groups()
            self.sell_bot.restore_level_groups()
            self._reconcile_orders()
        else:
            logger.info("Starting fresh grid at anchor=%.2f", self.config.anchor_price)
            self.state.anchor_price = self.config.anchor_price

        # Ensure main_anchor and spacings are always initialized
        if self.state.main_anchor == 0.0:
            self.state.main_anchor = self.config.anchor_price
            logger.info("Set main_anchor=%.2f", self.state.main_anchor)
        if self.state.current_buy_spacing == 0.0:
            self.state.current_buy_spacing = self.current_buy_spacing
        if self.state.current_sell_spacing == 0.0:
            self.state.current_sell_spacing = self.current_sell_spacing

        # Print grid layout with current spacings
        self.config.print_grid_layout(
            buy_spacing=self.current_buy_spacing,
            sell_spacing=self.current_sell_spacing,
        )

        # Place entry orders for any free levels
        self.buy_bot.place_entries()
        self.sell_bot.place_entries()
        self.state.save()

        # Print initial state
        self.state.print_summary()

        # Initialize PnL tracking session
        if self.pnl:
            config_snap = {
                'symbol': self.config.symbol, 'pair': self.config.pair_symbol,
                'anchor': self.config.anchor_price,
                'grid_space': self.current_buy_spacing,
                'levels': self.config.levels_per_side,
                'qty': self.config.qty_per_level, 'product': self.config.product,
                'account_id': self.config.account_id,
            }
            self._pnl_session_id = self.pnl.start_session(
                'tg_grid', config_snap, account_id=self.config.account_id)
            if self._pnl_session_id:
                self._pnl_pair_id = self.pnl.register_pair(
                    self._pnl_session_id,
                    primary=self.config.symbol,
                    secondary=self.config.pair_symbol or None,
                    pair_type='hedged' if self.config.has_pair else 'direct',
                    anchor=self.config.anchor_price,
                    spacing=self.current_buy_spacing,
                    levels=self.config.levels_per_side,
                    qty=self.config.qty_per_level,
                    product=self.config.product)
                # Share IDs with bots via config
                self.config._pnl_session_id = self._pnl_session_id
                self.config._pnl_pair_id = self._pnl_pair_id

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Enter main loop
        self.running = True
        if self.config.has_pair:
            logger.info("Pair trading ENABLED: %s hedge_ratio=%.1f%% partial_ratio=%.1f%% (opposite direction)",
                        self.config.pair_symbol, self.config.hedge_ratio,
                        self.config.partial_hedge_ratio)
        logger.info("Grid engine started. Polling every %.1fs | max_sub_depth=%d",
                     self.config.poll_interval, self.config.max_sub_depth)
        self._run_loop()

    def _run_loop(self):
        """Main polling loop."""
        poll_count = 0
        while self.running:
            try:
                fills_processed = self._poll_orders()
                if fills_processed > 0:
                    self.state.save()
                    self.state.print_summary()

                # Check for grid exhaustion → re-anchor
                if self.config.auto_reanchor:
                    exhausted_side = self._check_grid_exhausted()
                    if exhausted_side:
                        self._reanchor_grid(exhausted_side)

                poll_count += 1
                if poll_count % 100 == 0:
                    logger.info("Poll #%d | Open groups: %d | PnL: %.2f | Cycles: %d",
                                poll_count, len(self.state.open_groups),
                                self.state.total_pnl, self.state.total_cycles)

                time.sleep(self.config.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Poll loop error: %s", e, exc_info=True)
                time.sleep(self.config.poll_interval * 2)

        self._shutdown()

    def _poll_orders(self) -> int:
        """
        Poll all orders from XTS and process status changes.

        Returns number of fills processed. Cache key includes filled_qty
        to detect incremental partial fills.
        """
        orders = self.client.get_orders()
        if not orders:
            return 0

        fills_processed = 0
        for order in orders:
            order_id = str(order.get('order_id', ''))
            status = order.get('status', '')
            filled_qty = int(order.get('filled_quantity', 0))

            # Cache key includes filled_qty so partial increments are detected
            cache_key = f"{status}:{filled_qty}"
            if self._order_status_cache.get(order_id) == cache_key:
                continue
            self._order_status_cache[order_id] = cache_key

            if status in ('COMPLETE', 'PARTIAL'):
                if self._handle_fill_event(order):
                    fills_processed += 1
            elif status == 'REJECTED':
                self._handle_rejection(order)
            elif status == 'CANCELLED':
                self._handle_cancellation(order)

        return fills_processed

    def _handle_fill_event(self, order: dict) -> bool:
        """
        Handle PARTIAL or COMPLETE fill events with dual hedge ratio logic.

        Routes to entry or target handler. Pair hedging/unwinding happens
        inline before delegating to _on_entry_fill / _on_target_fill.
        """
        order_id = str(order['order_id'])
        status = order.get('status', '')
        group = self.state.get_group_by_order(order_id)
        if not group:
            return False

        fill_price = float(order.get('average_price', 0))
        filled_qty = int(order.get('filled_quantity', 0))

        if fill_price == 0 or filled_qty == 0:
            logger.warning("Fill with zero price/qty: order=%s", order_id)
            return False

        bot = self.buy_bot if group.bot == 'A' else self.sell_bot
        is_complete = (status == 'COMPLETE')

        # --- Entry order ---
        if order_id == group.entry_order_id:
            if group.status not in (GroupStatus.ENTRY_PENDING, GroupStatus.ENTRY_PARTIAL):
                logger.debug("Skipping entry fill for group=%s (status=%s, already processed)",
                             group.group_id, group.status)
                return False

            increment = filled_qty - group.entry_filled_so_far
            if increment > 0 and self.config.has_pair:
                if is_complete:
                    # Final fill: hedge to target ratio (%), accounting for partials already hedged
                    target_hedge = round(filled_qty * self.config.hedge_ratio / 100)
                    remaining = target_hedge - group.pair_hedged_qty
                    if remaining > 0:
                        bot.place_pair_hedge(group, remaining)
                else:
                    # Partial: hedge at partial ratio (%)
                    if self.config.partial_hedge_ratio > 0:
                        pair_qty = round(increment * self.config.partial_hedge_ratio / 100)
                        if pair_qty > 0:
                            bot.place_pair_hedge(group, pair_qty)

            # Delegate to engine fill handler (places D1 target, updates VWAP, etc.)
            return self._on_entry_fill(group, order_id, fill_price, filled_qty, is_complete)

        # --- Target order ---
        for target in group.target_orders:
            if target.get('order_id') == order_id:
                if group.status not in (GroupStatus.TARGET_PENDING, GroupStatus.ENTRY_PARTIAL):
                    logger.debug("Skipping target fill for group=%s (status=%s, already processed)",
                                 group.group_id, group.status)
                    return False

                increment = filled_qty - target.get('filled_qty', 0)
                depth = target.get('depth', 1)
                is_closing = (depth % 2 == 1)

                if increment > 0 and self.config.has_pair and is_closing:
                    if is_complete:
                        # Final fill: unwind to target ratio (%)
                        target_unwind = round(filled_qty * self.config.hedge_ratio / 100)
                        remaining = target_unwind - group.pair_unwound_qty
                        if remaining > 0:
                            bot.place_pair_unwind(group, remaining)
                    else:
                        # Partial: unwind at partial ratio (%)
                        if self.config.partial_hedge_ratio > 0:
                            pair_qty = round(increment * self.config.partial_hedge_ratio / 100)
                            if pair_qty > 0:
                                bot.place_pair_unwind(group, pair_qty)

                # Delegate to engine fill handler
                return self._on_target_fill(group, target, order_id, fill_price, filled_qty, is_complete)

        return False

    # ── Entry fill handler (ported from TollGate) ────────────────────────

    def _on_entry_fill(self, group: Group, order_id: str,
                       fill_price: float, filled_qty: int, is_complete: bool) -> bool:
        """
        Handle entry fill (partial or complete).

        For each increment, immediately place a D1 target for that qty.
        Updates VWAP entry price.
        """
        increment = filled_qty - group.entry_filled_so_far
        if increment <= 0:
            return False

        # Update VWAP: XTS average_price is the VWAP of all fills for this order
        group.entry_fill_price = fill_price
        group.entry_filled_so_far = filled_qty

        # PnL: record entry fill
        pnl = self.pnl
        if pnl and self._pnl_pair_id:
            pnl.record_fill(
                cycle_id=self.config._pnl_cycle_ids.get(group.group_id),
                pair_id=self._pnl_pair_id,
                session_id=self._pnl_session_id,
                ticker=self.config.symbol,
                side=group.entry_side,
                qty=increment,
                price=fill_price,
                txn_type='ENTRY',
                is_partial=not is_complete,
                order_id=order_id,
                group_id=group.group_id,
                running_pnl=self.state.total_pnl)

        # Place D1 target for this increment (closing position)
        group.target_seq += 1
        tag = f"{depth_tag(1)}{group.target_seq:02d}"
        target_uid = generate_order_id(
            self.config.symbol, self.config.pair_symbol or "NONE",
            group.subset_index, "TP", group.bot, group.group_id, tag=tag,
        )
        target_order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type=group.target_side,
            qty=increment,
            price=group.target_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=target_uid,
            disclosed_qty=self._disclosed_qty(increment),
        )

        if target_order_id:
            target_record = {
                'order_id': target_order_id,
                'qty': increment,
                'filled_qty': 0,
                'fill_price': None,
                'placed_at': datetime.now().isoformat(),
                'depth': 1,
                'tag': tag,
                'ref_price': fill_price,   # cost basis = entry fill VWAP
            }
            group.target_orders.append(target_record)
            self.state.register_order(target_order_id, group.group_id)
            logger.info("Target %s placed: %s %d @ %.2f -> order=%s (group=%s, depth=1, entry fill %d/%d)",
                        tag, group.target_side, increment,
                        group.target_price, target_order_id, group.group_id,
                        filled_qty, group.qty)
        else:
            logger.error("Target FAILED: %s %d @ %.2f for group=%s",
                         group.target_side, increment, group.target_price,
                         group.group_id)

        # Update status
        if is_complete:
            group.status = GroupStatus.TARGET_PENDING
            group.entry_fill_qty = filled_qty
            group.entry_filled_at = datetime.now().isoformat()
            logger.info("Entry COMPLETE: %s L%d, %d @ %.2f (group=%s)",
                        group.entry_side, group.subset_index,
                        filled_qty, fill_price, group.group_id)
        else:
            group.status = GroupStatus.ENTRY_PARTIAL
            logger.info("Entry PARTIAL: %s L%d, %d/%d @ %.2f (group=%s)",
                        group.entry_side, group.subset_index,
                        filled_qty, group.qty, fill_price, group.group_id)

        return True

    # ── Target fill handler (ported from TollGate) ───────────────────────

    def _on_target_fill(self, group: Group, target: dict,
                        order_id: str, fill_price: float, filled_qty: int,
                        is_complete: bool) -> bool:
        """
        Handle target fill (partial or complete).

        Computes PnL increment, spawns sub-target cascading for partial-fill
        groups, and checks if all targets/sub-chains are filled.

        Depth rules:
        - Odd depths (1,3,5): closing fills (target_side @ target_price) -> generate PnL
        - Even depths (2,4): re-entry fills (entry_side @ entry_price) -> no PnL
        """
        prev_filled = target.get('filled_qty', 0)
        increment = filled_qty - prev_filled
        if increment <= 0:
            return False

        target['filled_qty'] = filled_qty
        target['fill_price'] = fill_price

        # Update legacy compat field
        group.target_filled_so_far = group.total_target_filled_qty

        depth = target.get('depth', 1)
        tag = target.get('tag', f"D1{order_id[-2:]}")
        is_closing = (depth % 2 == 1)  # odd depths are closing fills

        # Compute PnL
        if is_closing:
            ref_price = target.get('ref_price', group.entry_fill_price)
            if group.entry_side == "BUY":
                pnl_increment = round((fill_price - ref_price) * increment, 2)
            else:
                pnl_increment = round((ref_price - fill_price) * increment, 2)
            group.realized_pnl = round(group.realized_pnl + pnl_increment, 2)
        else:
            pnl_increment = 0.0

        # PnL tracker: record fill
        pnl = self.pnl
        if pnl and self._pnl_pair_id:
            fill_side = group.target_side if is_closing else group.entry_side
            pnl.record_fill(
                cycle_id=self.config._pnl_cycle_ids.get(group.group_id),
                pair_id=self._pnl_pair_id,
                session_id=self._pnl_session_id,
                ticker=self.config.symbol,
                side=fill_side,
                qty=increment,
                price=fill_price,
                txn_type='TARGET' if is_closing else 'SUB_ENTRY',
                is_partial=not is_complete,
                order_id=order_id,
                group_id=group.group_id,
                pnl_increment=pnl_increment,
                running_pnl=self.state.total_pnl + group.realized_pnl)

        logger.info("Target fill: %s depth=%d L%d, %d @ %.2f, PnL incr=%.2f (group=%s)",
                    tag, depth, group.subset_index,
                    increment, fill_price, pnl_increment, group.group_id)

        # --- Sub-target cascading ---
        max_depth = self.config.max_sub_depth
        target_fully_filled = (filled_qty >= target.get('qty', 0))

        # Cascade when:
        # 1. Already in a sub-chain (depth > 1), OR
        # 2. Entry is still partial (ENTRY_PARTIAL), OR
        # 3. Entry completed but had partial fills (multiple D1 targets exist)
        # Case 3 catches the scenario where entry fills in chunks, status transitions
        # to TARGET_PENDING, but the D1 targets from those chunks should still cascade.
        # Single D1 target = complete entry fill → closes normally without cascading.
        d1_count = sum(1 for t in group.target_orders if t.get('depth', 1) == 1)
        should_cascade = (depth > 1) or (group.status == GroupStatus.ENTRY_PARTIAL) or (d1_count > 1)

        if target_fully_filled and depth < max_depth and should_cascade:
            # Spawn next depth order
            next_depth = depth + 1
            next_is_closing = (next_depth % 2 == 1)

            if next_is_closing:
                # Closing: target_side @ target_price
                next_side = group.target_side
                next_price = group.target_price
                next_ref_price = fill_price  # cost basis = re-entry fill price
            else:
                # Re-entry: entry_side @ entry_price
                next_side = group.entry_side
                next_price = group.entry_price
                next_ref_price = None  # will be set on fill

            # Build tag: e.g. "D201", "D301"
            seq_str = tag[-2:] if len(tag) >= 2 and tag[-2:].isdigit() else f"{group.target_seq:02d}"
            next_tag = f"{depth_tag(next_depth)}{seq_str}"

            next_uid = generate_order_id(
                self.config.symbol, self.config.pair_symbol or "NONE",
                group.subset_index, "TP", group.bot, group.group_id, tag=next_tag,
            )
            next_order_id = self.client.place_order(
                symbol=self.config.symbol,
                transaction_type=next_side,
                qty=target.get('qty', increment),
                price=next_price,
                exchange=self.config.exchange,
                product=self.config.product,
                order_unique_id=next_uid,
                disclosed_qty=self._disclosed_qty(target.get('qty', increment)),
            )

            if next_order_id:
                next_record = {
                    'order_id': next_order_id,
                    'qty': target.get('qty', increment),
                    'filled_qty': 0,
                    'fill_price': None,
                    'placed_at': datetime.now().isoformat(),
                    'depth': next_depth,
                    'tag': next_tag,
                    'ref_price': next_ref_price,
                }
                group.target_orders.append(next_record)
                self.state.register_order(next_order_id, group.group_id)
                logger.info("Sub-target %s placed: %s %d @ %.2f (depth=%d, group=%s)",
                            next_tag, next_side, target.get('qty', increment),
                            next_price, next_depth, group.group_id)
            else:
                logger.error("Sub-target FAILED: %s %d @ %.2f (depth=%d, group=%s)",
                             next_side, target.get('qty', increment),
                             next_price, next_depth, group.group_id)

        # --- Cycle completion check ---
        entry_complete = (group.status == GroupStatus.TARGET_PENDING)

        if group.has_pending_sub_targets() or depth > 1:
            # Sub-chains are active — check if ALL leaf targets at max_depth are filled
            if entry_complete and group.leaf_targets_filled(max_depth):
                self._complete_cycle(group, fill_price, "CYCLE COMPLETE (full entry + all sub-chains)")
            elif group.status == GroupStatus.ENTRY_PARTIAL and group.leaf_targets_filled(max_depth):
                self._complete_partial_cycle(group, fill_price)
        else:
            # No sub-chains — original behavior
            all_filled = group.all_targets_filled and group.total_target_filled_qty >= group.entry_filled_so_far
            if entry_complete and all_filled:
                self._complete_cycle(group, fill_price, "CYCLE COMPLETE")

        return True

    # ── Cycle completion ─────────────────────────────────────────────────

    def _complete_cycle(self, group: Group, fill_price: float, label: str):
        """Close a completed cycle and re-enter at the same grid level."""
        logger.info("%s: %s L%d, PnL=%.2f (group=%s)",
                    label, group.entry_side, group.subset_index,
                    group.realized_pnl, group.group_id)

        # Update legacy fields for backward compat
        group.target_fill_price = fill_price
        group.target_fill_qty = group.total_target_filled_qty
        group.target_filled_at = datetime.now().isoformat()

        # PnL: close cycle
        pnl = self.pnl
        if pnl:
            cid = self.config._pnl_cycle_ids.pop(group.group_id, None)
            pnl.close_cycle(
                cid,
                entry_fill_price=group.entry_fill_price,
                target_fill_price=fill_price,
                primary_pnl=group.realized_pnl,
                pair_pnl=group.pair_pnl)

        # Free the level
        bot = self.buy_bot if group.bot == 'A' else self.sell_bot
        if group.subset_index in bot.level_groups:
            del bot.level_groups[group.subset_index]

        # Close the group
        self.state.close_group(group.group_id)

        # Re-enter if configured
        if self.config.auto_reenter:
            levels = self.buy_levels if group.bot == 'A' else self.sell_levels
            for level in levels:
                if level.subset_index == group.subset_index:
                    if group.bot == 'A':
                        logger.info("BuyBot RE-ENTERING: subset=%d", level.subset_index)
                        self.buy_bot._place_entry(level)
                    else:
                        available = self.client.get_available_qty(self.config.symbol)
                        if available >= level.qty:
                            logger.info("SellBot RE-ENTERING: subset=%d", level.subset_index)
                            self.sell_bot._place_entry(level)
                        else:
                            logger.warning("SellBot: cannot re-enter subset=%d, "
                                           "insufficient holdings (%d < %d)",
                                           level.subset_index, available, level.qty)
                    break

    def _complete_partial_cycle(self, group: Group, fill_price: float):
        """
        Handle partial-fill cycle completion after all sub-chains reach max depth.

        Cancels the remaining entry order, closes the group, and re-enters fresh.
        """
        logger.info("PARTIAL CYCLE CLOSE: %s L%d, filled=%d/%d, PnL=%.2f, "
                    "sub-chains exhausted -> recycling level (group=%s)",
                    group.entry_side, group.subset_index,
                    group.entry_filled_so_far, group.qty, group.realized_pnl,
                    group.group_id)

        # Cancel remaining entry order
        if group.entry_order_id:
            if self.client.cancel_order(group.entry_order_id):
                logger.info("Cancelled remaining entry order %s (group=%s)",
                            group.entry_order_id, group.group_id)
            else:
                logger.warning("Failed to cancel remaining entry %s (group=%s, may already be done)",
                               group.entry_order_id, group.group_id)

        # Update legacy fields
        group.target_fill_price = fill_price
        group.target_fill_qty = group.total_target_filled_qty
        group.target_filled_at = datetime.now().isoformat()

        # PnL: close cycle
        pnl = self.pnl
        if pnl:
            cid = self.config._pnl_cycle_ids.pop(group.group_id, None)
            pnl.close_cycle(
                cid,
                entry_fill_price=group.entry_fill_price,
                target_fill_price=fill_price,
                primary_pnl=group.realized_pnl,
                pair_pnl=group.pair_pnl)

        # Free the level
        bot = self.buy_bot if group.bot == 'A' else self.sell_bot
        if group.subset_index in bot.level_groups:
            del bot.level_groups[group.subset_index]

        # Close group
        self.state.close_group(group.group_id)

        # Re-enter at same grid level with full qty
        if self.config.auto_reenter:
            levels = self.buy_levels if group.bot == 'A' else self.sell_levels
            for level in levels:
                if level.subset_index == group.subset_index:
                    if group.bot == 'A':
                        logger.info("BuyBot RE-ENTERING (after partial): subset=%d", level.subset_index)
                        self.buy_bot._place_entry(level)
                    else:
                        available = self.client.get_available_qty(self.config.symbol)
                        if available >= level.qty:
                            logger.info("SellBot RE-ENTERING (after partial): subset=%d", level.subset_index)
                            self.sell_bot._place_entry(level)
                        else:
                            logger.warning("SellBot: cannot re-enter subset=%d after partial, "
                                           "insufficient holdings (%d < %d)",
                                           level.subset_index, available, level.qty)
                    break

    # ── Order event handlers ─────────────────────────────────────────────

    def _handle_rejection(self, order: dict):
        """Log rejected orders. Do not auto-retry — let operator decide."""
        order_id = str(order.get('order_id', ''))
        reason = order.get('status_message', 'unknown')
        group = self.state.get_group_by_order(order_id)

        if group:
            logger.error("ORDER REJECTED: order=%s, group=%s, bot=%s, reason=%s",
                         order_id, group.group_id, group.bot, reason)
            # Free the level if entry was rejected
            if order_id == group.entry_order_id:
                bot = self.buy_bot if group.bot == 'A' else self.sell_bot
                if group.subset_index in bot.level_groups:
                    del bot.level_groups[group.subset_index]
                # Remove from open groups
                if group.group_id in self.state.open_groups:
                    del self.state.open_groups[group.group_id]
        else:
            logger.warning("REJECTED (untracked): order=%s, reason=%s",
                           order_id, reason)

    def _handle_cancellation(self, order: dict):
        """Log cancelled orders."""
        order_id = str(order.get('order_id', ''))
        group = self.state.get_group_by_order(order_id)
        if group:
            logger.info("ORDER CANCELLED: order=%s, group=%s, bot=%s",
                        order_id, group.group_id, group.bot)

    def _reconcile_orders(self):
        """
        On startup with existing state, reconcile with broker.

        Check actual order statuses for all tracked orders.
        Process any fills that occurred while we were down.
        """
        logger.info("Reconciling state with broker orders...")
        orders = self.client.get_orders()
        if not orders:
            logger.warning("No orders returned from broker during reconciliation")
            return

        # Build lookup
        broker_orders = {str(o['order_id']): o for o in orders}

        for group in list(self.state.open_groups.values()):
            # Check entry order
            if (group.status in (GroupStatus.ENTRY_PENDING, GroupStatus.ENTRY_PARTIAL) and
                    group.entry_order_id):
                broker_order = broker_orders.get(group.entry_order_id)
                if broker_order:
                    status = broker_order.get('status', '')
                    if status in ('COMPLETE', 'PARTIAL'):
                        logger.info("Reconcile: entry fill detected for group=%s (status=%s)",
                                     group.group_id, status)
                        self._handle_fill_event(broker_order)
                    elif status in ('CANCELLED', 'REJECTED'):
                        logger.info("Reconcile: entry %s for group=%s",
                                     status, group.group_id)
                        bot = self.buy_bot if group.bot == 'A' else self.sell_bot
                        if group.subset_index in bot.level_groups:
                            del bot.level_groups[group.subset_index]
                        if group.group_id in self.state.open_groups:
                            del self.state.open_groups[group.group_id]

            # Check target orders
            elif group.status in (GroupStatus.TARGET_PENDING, GroupStatus.ENTRY_PARTIAL):
                for target in group.target_orders:
                    tid = target.get('order_id')
                    if tid:
                        broker_order = broker_orders.get(tid)
                        if broker_order:
                            status = broker_order.get('status', '')
                            if status in ('COMPLETE', 'PARTIAL'):
                                logger.info("Reconcile: target fill detected for group=%s order=%s",
                                             group.group_id, tid)
                                self._handle_fill_event(broker_order)

        self.state.save()
        logger.info("Reconciliation complete")

    def _check_grid_exhausted(self) -> Optional[str]:
        """
        Check if all grid levels on one side are TARGET_PENDING.

        Returns 'buy' or 'sell' if that side is exhausted, None otherwise.
        Respects cooldown to prevent rapid re-anchoring.
        """
        # Cooldown check
        if self._last_reanchor_time:
            elapsed = datetime.now() - self._last_reanchor_time
            if elapsed < self._reanchor_cooldown:
                return None

        num_levels = len(self.buy_levels)
        if num_levels == 0:
            return None

        buy_tp = sum(1 for g in self.state.open_groups.values()
                     if g.bot == 'A' and g.status == GroupStatus.TARGET_PENDING)
        sell_tp = sum(1 for g in self.state.open_groups.values()
                      if g.bot == 'B' and g.status == GroupStatus.TARGET_PENDING)

        if buy_tp >= num_levels:
            logger.info("GRID EXHAUSTED: all %d buy levels are TARGET_PENDING", buy_tp)
            return 'buy'
        if sell_tp >= num_levels:
            logger.info("GRID EXHAUSTED: all %d sell levels are TARGET_PENDING", sell_tp)
            return 'sell'
        return None

    def _get_last_filled_price(self, side: str) -> float:
        """Get the fill price of the most recently filled entry on given side."""
        bot_id = 'A' if side == 'buy' else 'B'
        candidates = [
            g for g in self.state.open_groups.values()
            if g.bot == bot_id and g.status == GroupStatus.TARGET_PENDING
               and g.entry_fill_price is not None
        ]
        if not candidates:
            return self.config.anchor_price
        # Deepest filled = lowest price for buy, highest for sell
        if side == 'buy':
            return min(g.entry_fill_price for g in candidates)
        else:
            return max(g.entry_fill_price for g in candidates)

    def _reanchor_grid(self, exhausted_side: str):
        """
        Epoch-based re-anchor when all levels on one side are exhausted.

        Sequence:
        1. Find last filled price on exhausted side → new sub_anchor
        2. Increment grid level counter for exhausted side
        3. Check epoch: increase spacing every reanchor_epoch reanchors
        4. Check stop: halt if max_grid_levels reached
        5. Cancel all open orders (both sides)
        6. Flatten SPCENET pair position
        7. Close all open groups as CANCELLED
        8. Recompute grid at new sub_anchor with current spacings
        9. Place fresh entries on both sides
        """
        old_anchor = self.config.anchor_price

        # Step 1: Find last filled price on exhausted side
        new_anchor = round(self._get_last_filled_price(exhausted_side), 2)

        logger.info("=" * 60)
        logger.info("REANCHORING GRID (%s exhausted): %.2f -> %.2f",
                     exhausted_side.upper(), old_anchor, new_anchor)
        logger.info("=" * 60)

        # Step 2: Increment grid level counter
        if exhausted_side == 'buy':
            self.state.buy_grid_levels += 1
            grid_count = self.state.buy_grid_levels
        else:
            self.state.sell_grid_levels += 1
            grid_count = self.state.sell_grid_levels

        logger.info("Grid level count: buy=%d, sell=%d",
                     self.state.buy_grid_levels, self.state.sell_grid_levels)

        # Step 3: Check epoch — increase spacing every reanchor_epoch
        if grid_count > 0 and grid_count % self.config.reanchor_epoch == 0:
            if exhausted_side == 'buy':
                self.current_buy_spacing = round(
                    self.current_buy_spacing + self.config.base_grid_space, 10)
                logger.info("BUY SPACING EPOCH: increased to %.4f (after %d grid levels)",
                            self.current_buy_spacing, grid_count)
            else:
                self.current_sell_spacing = round(
                    self.current_sell_spacing + self.config.base_grid_space, 10)
                logger.info("SELL SPACING EPOCH: increased to %.4f (after %d grid levels)",
                            self.current_sell_spacing, grid_count)

        # Step 4: Check stop condition
        if grid_count >= self.config.max_grid_levels:
            logger.warning("MAX GRID LEVELS REACHED: %s side at %d (limit=%d). STOPPING BOT.",
                           exhausted_side.upper(), grid_count, self.config.max_grid_levels)
            self.state.save()
            self.running = False
            return

        # Step 5: Cancel all open orders
        logger.info("Step 5: Cancelling all orders...")
        self.cancel_all()

        # Step 6: Flatten SPCENET pair position
        if self.config.has_pair:
            self._flatten_pair_position()

        # Step 7: Close all open groups as CANCELLED
        logger.info("Step 7: Closing %d open groups as CANCELLED...",
                     len(self.state.open_groups))
        for group in list(self.state.open_groups.values()):
            group.status = GroupStatus.CANCELLED
            group.realized_pnl = 0.0  # primary PnL not realized (shares still held)
            group.closed_at = datetime.now().isoformat()
            self.state.closed_groups.append(group)

        # Step 8: Clear state and recompute grid
        logger.info("Step 8: Clearing bot state, recomputing grid at anchor=%.2f...", new_anchor)
        self.state.open_groups = {}
        self.state.order_to_group = {}
        self.buy_bot.level_groups = {}
        self.sell_bot.level_groups = {}
        self._order_status_cache = {}

        self.config.anchor_price = new_anchor
        self.state.anchor_price = new_anchor
        self.state.current_buy_spacing = self.current_buy_spacing
        self.state.current_sell_spacing = self.current_sell_spacing
        self.grid = GridCalculator(self.config)
        self.buy_levels = self.grid.compute_buy_levels(grid_space=self.current_buy_spacing)
        self.sell_levels = self.grid.compute_sell_levels(grid_space=self.current_sell_spacing)
        self.buy_bot.levels = self.buy_levels
        self.sell_bot.levels = self.sell_levels

        # Step 9: Place fresh entries
        logger.info("Step 9: Placing fresh entries (buy_space=%.4f, sell_space=%.4f)...",
                     self.current_buy_spacing, self.current_sell_spacing)
        self.buy_bot.place_entries()
        self.sell_bot.place_entries()

        # Save state and update cooldown
        self.state.save()
        self._last_reanchor_time = datetime.now()
        self.state.print_summary()

        logger.info("=" * 60)
        logger.info("REANCHOR COMPLETE: %.2f -> %.2f | Side: %s | Open groups: %d",
                     old_anchor, new_anchor, exhausted_side.upper(),
                     len(self.state.open_groups))
        logger.info("=" * 60)

    def _flatten_pair_position(self):
        """
        Flatten net SPCENET position from open groups before re-anchor.

        Computes net pair qty from all open groups:
        - BuyBot (A) hedges = SELL secondary → net negative
        - SellBot (B) hedges = BUY secondary → net positive
        Net = sum(hedged - unwound) per group, signed by direction.
        """
        net_pair_qty = 0
        for g in self.state.open_groups.values():
            remaining = g.pair_hedged_qty - g.pair_unwound_qty
            if remaining <= 0:
                continue
            if g.bot == 'A':
                # BuyBot hedged by SELLING secondary → we are short
                net_pair_qty -= remaining
            else:
                # SellBot hedged by BUYING secondary → we are long
                net_pair_qty += remaining

        if net_pair_qty == 0:
            logger.info("No net %s position to flatten", self.config.pair_symbol)
            return

        # Flatten: positive = long → SELL, negative = short → BUY
        if net_pair_qty > 0:
            side = "SELL"
            qty = net_pair_qty
        else:
            side = "BUY"
            qty = abs(net_pair_qty)

        logger.info("Flattening %s: %s %d (net=%d)",
                     self.config.pair_symbol, side, qty, net_pair_qty)
        order_id, price = self.client.place_market_order(
            self.config.pair_symbol, side, qty,
            self.config.exchange, self.config.product,
            order_unique_id=f"RA_{self.config.symbol}",
            slippage=0.05,
        )
        if order_id:
            logger.info("Pair flatten order placed: %s %s %d @ %.2f, order=%s",
                         side, self.config.pair_symbol, qty, price, order_id)
            # Record pair PnL on each group being closed
            for g in self.state.open_groups.values():
                remaining = g.pair_hedged_qty - g.pair_unwound_qty
                if remaining > 0:
                    g.pair_unwound_qty = g.pair_hedged_qty
                    g.pair_unwind_total += price * remaining
                    # PnL on fully matched qty (all unwound now)
                    if g.bot == 'A':
                        g.pair_pnl = round(g.pair_hedged_qty * (g.pair_hedge_vwap - g.pair_unwind_vwap), 2)
                    else:
                        g.pair_pnl = round(g.pair_hedged_qty * (g.pair_unwind_vwap - g.pair_hedge_vwap), 2)
                    g.pair_orders.append({
                        'xts_id': order_id, 'custom_id': f"RA_{self.config.symbol}",
                        'side': side, 'qty': remaining, 'price': price,
                        'role': 'REANCHOR_FLATTEN',
                        'ts': datetime.now().isoformat(),
                    })
        else:
            logger.error("Pair flatten FAILED: %s %s %d",
                         side, self.config.pair_symbol, qty)

    def cancel_all(self):
        """Cancel all open orders for both bots."""
        logger.info("Cancelling all orders...")
        a = self.buy_bot.cancel_all()
        b = self.sell_bot.cancel_all()
        logger.info("Cancelled %d orders total (BuyBot=%d, SellBot=%d)", a + b, a, b)
        self.state.save()

    def _shutdown_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM gracefully."""
        logger.info("Shutdown signal received (sig=%d)", signum)
        self.running = False

    def _shutdown(self):
        """Graceful shutdown: save state, do NOT cancel orders (CNC persists)."""
        logger.info("Shutting down grid engine...")
        self.state.save()
        self.state.print_summary()

        # PnL: end session
        if self.pnl and self._pnl_session_id:
            self.pnl.end_session(
                self._pnl_session_id,
                total_pnl=self.state.total_pnl,
                total_cycles=self.state.total_cycles)

        logger.info("State saved. Orders remain active (CNC). "
                     "Run with --cancel-all to cancel open orders.")
        logger.info("Total PnL: %.2f | Cycles: %d",
                     self.state.total_pnl, self.state.total_cycles)

    def on_tick(self, price: float, timestamp: Optional[datetime] = None):
        """
        Process a price tick from an external feed.

        Currently unused — the engine reacts to order fills via polling.
        Reserved for future enhancements:
        - Dynamic grid re-anchoring
        - Price-based entry logic
        - Spread monitoring
        """
        pass
