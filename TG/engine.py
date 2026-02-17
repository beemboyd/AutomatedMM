"""
Grid Engine — main orchestrator for the grid trading bot.

Responsibilities:
1. Initialize bots with computed grid levels
2. Poll Zerodha order status at regular intervals
3. Route fills to the correct bot (A or B, entry or target)
4. Persist state after every significant event
5. Handle startup with state recovery and order reconciliation

The engine is feed-agnostic: it reacts to order fills via polling,
not price ticks. A tick-based interface (on_tick) is provided for
future integration with real-time feeds.
"""

import time
import signal
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import GridConfig
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
    Polls Zerodha for order status changes and routes fills
    to the appropriate bot for target placement or group closure.
    """

    def __init__(self, config: GridConfig):
        self.config = config
        self.running = False

        # Initialize components
        self.client = HybridClient(
            interactive_key=config.interactive_key,
            interactive_secret=config.interactive_secret,
            zerodha_user=config.zerodha_user,
            root_url=config.xts_root,
        )
        self.state = StateManager(config.symbol)
        self.grid = GridCalculator(config)

        # Current spacing for each side (may increase over epochs)
        self.current_buy_spacing = config.base_grid_space
        self.current_sell_spacing = config.base_grid_space

        # Compute grid levels with separate spacings
        self.buy_levels = self.grid.compute_buy_levels(grid_space=self.current_buy_spacing)
        self.sell_levels = self.grid.compute_sell_levels(grid_space=self.current_sell_spacing)

        # Initialize bots
        self.buy_bot = BuyBot(self.buy_levels, self.client, self.state, config)
        self.sell_bot = SellBot(self.sell_levels, self.client, self.state, config)

        # Order status cache: order_id → "status:filled_qty"
        # Detects incremental partial fills and prevents reprocessing
        self._order_status_cache: Dict[str, str] = {}

        # Re-anchor cooldown tracking
        self._last_reanchor_time: Optional[datetime] = None
        self._reanchor_cooldown = timedelta(seconds=60)

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

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Enter main loop
        self.running = True
        if self.config.has_pair:
            logger.info("Pair trading ENABLED: %s hedge_ratio=%d partial_ratio=%d (opposite direction)",
                        self.config.pair_symbol, self.config.hedge_ratio,
                        self.config.partial_hedge_ratio)
        logger.info("Grid engine started. Polling every %.1fs", self.config.poll_interval)
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

        On each fill event:
        1. Compute increment = current_filled_qty - previously_filled_qty
        2. If PARTIAL: pair_qty = increment * partial_hedge_ratio
        3. If COMPLETE: target_total = filled_qty * hedge_ratio, remaining = target - already_hedged
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
            if group.status != GroupStatus.ENTRY_PENDING:
                logger.debug("Skipping entry fill for group=%s (status=%s, already processed)",
                             group.group_id, group.status)
                return False

            increment = filled_qty - group.entry_filled_so_far
            if increment > 0 and self.config.has_pair:
                if is_complete:
                    # Final fill: hedge to target ratio, accounting for partials already hedged
                    target_hedge = filled_qty * self.config.hedge_ratio
                    remaining = target_hedge - group.pair_hedged_qty
                    if remaining > 0:
                        bot.place_pair_hedge(group, remaining)
                else:
                    # Partial: hedge at partial ratio
                    if self.config.partial_hedge_ratio > 0:
                        pair_qty = increment * self.config.partial_hedge_ratio
                        bot.place_pair_hedge(group, pair_qty)

            group.entry_filled_so_far = filled_qty
            group.entry_fill_price = fill_price

            if is_complete:
                bot.on_entry_fill(group, fill_price, filled_qty)
            return True

        # --- Target order ---
        elif order_id == group.target_order_id:
            if group.status != GroupStatus.TARGET_PENDING:
                logger.debug("Skipping target fill for group=%s (status=%s, already processed)",
                             group.group_id, group.status)
                return False

            increment = filled_qty - group.target_filled_so_far
            if increment > 0 and self.config.has_pair:
                if is_complete:
                    # Final fill: unwind to target ratio
                    target_unwind = filled_qty * self.config.hedge_ratio
                    remaining = target_unwind - group.pair_unwound_qty
                    if remaining > 0:
                        bot.place_pair_unwind(group, remaining)
                else:
                    # Partial: unwind at partial ratio
                    if self.config.partial_hedge_ratio > 0:
                        pair_qty = increment * self.config.partial_hedge_ratio
                        bot.place_pair_unwind(group, pair_qty)

            group.target_filled_so_far = filled_qty

            if is_complete:
                bot.on_target_fill(group, fill_price, filled_qty)
            return True

        return False

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
            if (group.status == GroupStatus.ENTRY_PENDING and
                    group.entry_order_id):
                broker_order = broker_orders.get(group.entry_order_id)
                if broker_order:
                    status = broker_order.get('status', '')
                    if status == 'COMPLETE':
                        fill_price = float(broker_order.get('average_price', 0))
                        fill_qty = int(broker_order.get('filled_quantity', 0))
                        logger.info("Reconcile: entry fill detected for group=%s",
                                     group.group_id)
                        self._handle_fill_event(broker_order)
                    elif status in ('CANCELLED', 'REJECTED'):
                        logger.info("Reconcile: entry %s for group=%s",
                                     status, group.group_id)
                        bot = self.buy_bot if group.bot == 'A' else self.sell_bot
                        if group.subset_index in bot.level_groups:
                            del bot.level_groups[group.subset_index]
                        if group.group_id in self.state.open_groups:
                            del self.state.open_groups[group.group_id]

            # Check target order
            elif (group.status == GroupStatus.TARGET_PENDING and
                  group.target_order_id):
                broker_order = broker_orders.get(group.target_order_id)
                if broker_order:
                    status = broker_order.get('status', '')
                    if status == 'COMPLETE':
                        logger.info("Reconcile: target fill detected for group=%s",
                                     group.group_id)
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
                    if g.bot == 'A':
                        g.pair_pnl = round(g.pair_hedge_total - g.pair_unwind_total, 2)
                    else:
                        g.pair_pnl = round(g.pair_unwind_total - g.pair_hedge_total, 2)
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
