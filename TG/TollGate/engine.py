"""
TollGate Engine — unified polling loop for SPCENET market-making.

Single engine handles both buy and sell sides (no separate BuyBot/SellBot).
Uses HybridClient from TG.hybrid_client with session isolation so the
separate XTS account doesn't collide with the main TG bots' session.

Key features:
- Immediate partial fill handling (place target for each partial increment)
- VWAP-based entry price tracking
- Reanchor with increasing spacing when one side exhausts
- Net inventory tracking
"""

import os
import time
import signal
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from .config import TollGateConfig, GridLevel, generate_order_id
from .state import TollGateState, TollGateGroup, TollGateStatus

logger = logging.getLogger(__name__)


class TollGateEngine:
    """
    Unified grid market-making engine for SPCENET.

    Handles both buy and sell sides in a single class.
    Polls XTS order book for fills and routes to appropriate handlers.
    """

    def __init__(self, config: TollGateConfig):
        self.config = config
        self.running = False

        # Client initialized in start() to allow session isolation
        self.client = None
        self.state = TollGateState(config.symbol)

        # Grid levels (recomputed on reanchor)
        self.buy_levels: List[GridLevel] = []
        self.sell_levels: List[GridLevel] = []

        # Level -> group_id mapping (quick lookup for free levels)
        self.level_groups: Dict[str, str] = {}  # "A:0" -> group_id, "B:3" -> group_id

        # Order status cache: order_id -> "status:filled_qty"
        self._order_status_cache: Dict[str, str] = {}

        # Re-anchor cooldown
        self._last_reanchor_time: Optional[datetime] = None
        self._reanchor_cooldown = timedelta(seconds=60)

    def start(self):
        """
        Start the TollGate engine.

        1. Connect to XTS (with TollGate credentials) + Zerodha
        2. Load existing state or initialize fresh
        3. Compute grid levels
        4. Reconcile with broker
        5. Place entry orders for free levels
        6. Enter main polling loop
        """
        # Session isolation: override session file before connecting
        import TG.hybrid_client as hc_module
        original_session_file = hc_module._SESSION_FILE
        tollgate_session = os.path.join(os.path.dirname(__file__), 'state', '.xts_session.json')
        hc_module._SESSION_FILE = tollgate_session

        try:
            from TG.hybrid_client import HybridClient
            self.client = HybridClient(
                interactive_key=self.config.interactive_key,
                interactive_secret=self.config.interactive_secret,
                zerodha_user=self.config.zerodha_user,
                root_url=self.config.xts_root,
            )
            if not self.client.connect():
                logger.error("Cannot start: connection failed")
                return
        finally:
            # Restore original session file path
            hc_module._SESSION_FILE = original_session_file

        # Load state or start fresh
        if self.state.load():
            logger.info("Resuming from saved state")
            if self.state.current_spacing > 0:
                current_spacing = self.state.current_spacing
            else:
                current_spacing = self.config.base_spacing
                self.state.current_spacing = current_spacing
        else:
            logger.info("Starting fresh grid at anchor=%.2f", self.config.anchor_price)
            self.state.anchor_price = self.config.anchor_price
            self.state.current_spacing = self.config.base_spacing

        # Compute grid levels
        self.buy_levels, self.sell_levels = self.config.compute_levels(self.state.current_spacing)

        # Rebuild level_groups from state
        self._rebuild_level_groups()

        # Reconcile with broker
        self._reconcile_orders()

        # Print layout
        self.config.print_grid_layout(self.state.current_spacing)

        # Place entries for free levels
        self._place_entries()
        self.state.save()
        self.state.print_summary()

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Enter main loop
        self.running = True
        logger.info("TollGate engine started. Polling every %.1fs", self.config.poll_interval)
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

                # Check for grid exhaustion -> re-anchor
                exhausted_side = self._check_grid_exhausted()
                if exhausted_side:
                    self._reanchor_grid(exhausted_side)

                poll_count += 1
                if poll_count % 100 == 0:
                    logger.info("Poll #%d | Open: %d | PnL: %.2f | Cycles: %d | Inv: %d",
                                poll_count, len(self.state.open_groups),
                                self.state.total_pnl, self.state.total_cycles,
                                self.state.net_inventory)

                time.sleep(self.config.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Poll loop error: %s", e, exc_info=True)
                time.sleep(self.config.poll_interval * 2)

        self._shutdown()

    def _place_entries(self):
        """Place entry orders for all free levels on both sides."""
        for level in self.buy_levels:
            key = f"A:{level.index}"
            if key not in self.level_groups:
                self._place_entry(level, bot="A")

        for level in self.sell_levels:
            key = f"B:{level.index}"
            if key not in self.level_groups:
                self._place_entry(level, bot="B")

    def _place_entry(self, level: GridLevel, bot: str):
        """Place a single entry order and create a TollGateGroup."""
        cycle = self.state.next_cycle_for_level(level.side, level.index)
        group = TollGateGroup.create(
            bot=bot,
            subset_index=level.index,
            entry_side=level.side,
            entry_price=level.entry_price,
            target_price=level.target_price,
            qty=level.qty,
            cycle_number=cycle,
        )

        order_uid = generate_order_id("EN", level.side, level.index, cycle, group.group_id)
        order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type=level.side,
            qty=level.qty,
            price=level.entry_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=order_uid,
        )

        if order_id:
            group.entry_order_id = order_id
            self.state.add_group(group)
            self.level_groups[f"{bot}:{level.index}"] = group.group_id
            logger.info("Entry placed: %s L%d C%d @ %.2f -> order=%s (group=%s)",
                        level.side, level.index, cycle, level.entry_price,
                        order_id, group.group_id)
        else:
            logger.error("Entry FAILED: %s L%d @ %.2f",
                         level.side, level.index, level.entry_price)

    def _poll_orders(self) -> int:
        """
        Poll all orders from XTS and process status changes.

        Cache key includes filled_qty to detect incremental partial fills.
        """
        orders = self.client.get_orders()
        if not orders:
            return 0

        fills_processed = 0
        for order in orders:
            order_id = str(order.get('order_id', ''))
            status = order.get('status', '')
            filled_qty = int(order.get('filled_quantity', 0))

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
        Handle PARTIAL or COMPLETE fill events.

        Routes to entry or target handler based on order_id lookup.
        """
        order_id = str(order['order_id'])
        group = self.state.get_group_by_order(order_id)
        if not group:
            return False

        fill_price = float(order.get('average_price', 0))
        filled_qty = int(order.get('filled_quantity', 0))

        if fill_price == 0 or filled_qty == 0:
            logger.warning("Fill with zero price/qty: order=%s", order_id)
            return False

        is_complete = (order.get('status') == 'COMPLETE')

        # Entry order
        if order_id == group.entry_order_id:
            return self._on_entry_fill(group, order_id, fill_price, filled_qty, is_complete)

        # Target order
        for target in group.target_orders:
            if target.get('order_id') == order_id:
                return self._on_target_fill(group, target, order_id, fill_price, filled_qty, is_complete)

        return False

    def _on_entry_fill(self, group: TollGateGroup, order_id: str,
                       fill_price: float, filled_qty: int, is_complete: bool) -> bool:
        """
        Handle entry fill (partial or complete).

        For each increment, immediately place a target order for that qty.
        Updates VWAP entry price and net inventory.
        """
        increment = filled_qty - group.entry_filled_so_far
        if increment <= 0:
            return False

        # Update VWAP: weighted average of previous fills + new fill
        # XTS average_price is the VWAP of all fills for this order, so use it directly
        group.entry_fill_price = fill_price
        group.entry_filled_so_far = filled_qty

        # Update net inventory
        if group.entry_side == "BUY":
            self.state.net_inventory += increment
        else:
            self.state.net_inventory -= increment

        # Place target for this increment
        group.target_seq += 1
        target_uid = generate_order_id(
            "TP", group.entry_side, group.subset_index,
            group.cycle_number, group.group_id, seq=group.target_seq,
        )
        target_order_id = self.client.place_order(
            symbol=self.config.symbol,
            transaction_type=group.target_side,
            qty=increment,
            price=group.target_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=target_uid,
        )

        if target_order_id:
            target_record = {
                'order_id': target_order_id,
                'qty': increment,
                'filled_qty': 0,
                'fill_price': None,
                'placed_at': datetime.now().isoformat(),
            }
            group.target_orders.append(target_record)
            self.state.register_order(target_order_id, group.group_id)
            logger.info("Target T%d placed: %s %d @ %.2f -> order=%s (group=%s, entry fill %d/%d)",
                        group.target_seq, group.target_side, increment,
                        group.target_price, target_order_id, group.group_id,
                        filled_qty, group.qty)
        else:
            logger.error("Target FAILED: %s %d @ %.2f for group=%s",
                         group.target_side, increment, group.target_price,
                         group.group_id)

        # Update status
        if is_complete:
            group.status = TollGateStatus.TARGET_PENDING
            group.entry_filled_at = datetime.now().isoformat()
            logger.info("Entry COMPLETE: %s L%d C%d, %d @ %.2f (group=%s)",
                        group.entry_side, group.subset_index, group.cycle_number,
                        filled_qty, fill_price, group.group_id)
        else:
            group.status = TollGateStatus.ENTRY_PARTIAL
            logger.info("Entry PARTIAL: %s L%d C%d, %d/%d @ %.2f (group=%s)",
                        group.entry_side, group.subset_index, group.cycle_number,
                        filled_qty, group.qty, fill_price, group.group_id)

        return True

    def _on_target_fill(self, group: TollGateGroup, target: dict,
                        order_id: str, fill_price: float, filled_qty: int,
                        is_complete: bool) -> bool:
        """
        Handle target fill (partial or complete).

        Computes PnL increment and checks if all targets are filled.
        """
        prev_filled = target.get('filled_qty', 0)
        increment = filled_qty - prev_filled
        if increment <= 0:
            return False

        target['filled_qty'] = filled_qty
        target['fill_price'] = fill_price

        # Update net inventory (target is opposite side of entry)
        if group.entry_side == "BUY":
            # Entry was BUY, target is SELL -> reduce long
            self.state.net_inventory -= increment
            pnl_increment = round((fill_price - group.entry_fill_price) * increment, 2)
        else:
            # Entry was SELL, target is BUY -> reduce short
            self.state.net_inventory += increment
            pnl_increment = round((group.entry_fill_price - fill_price) * increment, 2)

        group.realized_pnl = round(group.realized_pnl + pnl_increment, 2)

        logger.info("Target fill: %s L%d C%d.T%s, %d @ %.2f, PnL incr=%.2f (group=%s)",
                    group.target_side, group.subset_index, group.cycle_number,
                    order_id[-8:], increment, fill_price, pnl_increment, group.group_id)

        # Check if all targets filled AND entry is complete
        entry_complete = (group.status == TollGateStatus.TARGET_PENDING)
        all_filled = group.all_targets_filled and group.total_target_filled_qty >= group.entry_filled_so_far

        if entry_complete and all_filled:
            logger.info("CYCLE COMPLETE: %s L%d C%d, PnL=%.2f (group=%s)",
                        group.entry_side, group.subset_index, group.cycle_number,
                        group.realized_pnl, group.group_id)

            # Free the level
            level_key = f"{group.bot}:{group.subset_index}"
            self.level_groups.pop(level_key, None)

            # Close group
            self.state.close_group(group.group_id)

            # Re-enter at same grid level
            if group.bot == 'A' and group.subset_index < len(self.buy_levels):
                self._place_entry(self.buy_levels[group.subset_index], bot="A")
            elif group.bot == 'B' and group.subset_index < len(self.sell_levels):
                self._place_entry(self.sell_levels[group.subset_index], bot="B")

        return True

    def _handle_rejection(self, order: dict):
        """Log rejected orders and free the level."""
        order_id = str(order.get('order_id', ''))
        reason = order.get('status_message', 'unknown')
        group = self.state.get_group_by_order(order_id)

        if group:
            logger.error("ORDER REJECTED: order=%s, group=%s, bot=%s, reason=%s",
                         order_id, group.group_id, group.bot, reason)
            if order_id == group.entry_order_id:
                level_key = f"{group.bot}:{group.subset_index}"
                self.level_groups.pop(level_key, None)
                self.state.open_groups.pop(group.group_id, None)
        else:
            logger.warning("REJECTED (untracked): order=%s, reason=%s", order_id, reason)

    def _handle_cancellation(self, order: dict):
        """Log cancelled orders."""
        order_id = str(order.get('order_id', ''))
        group = self.state.get_group_by_order(order_id)
        if group:
            logger.info("ORDER CANCELLED: order=%s, group=%s, bot=%s",
                        order_id, group.group_id, group.bot)

    def _check_grid_exhausted(self) -> Optional[str]:
        """
        Check if all grid levels on one side have status TARGET_PENDING.

        ENTRY_PARTIAL levels do NOT count toward exhaustion.
        Returns 'buy' or 'sell' if exhausted, None otherwise.
        """
        if self._last_reanchor_time:
            elapsed = datetime.now() - self._last_reanchor_time
            if elapsed < self._reanchor_cooldown:
                return None

        num_levels = self.config.levels_per_side
        if num_levels == 0:
            return None

        buy_tp = sum(1 for g in self.state.open_groups.values()
                     if g.bot == 'A' and g.status == TollGateStatus.TARGET_PENDING)
        sell_tp = sum(1 for g in self.state.open_groups.values()
                      if g.bot == 'B' and g.status == TollGateStatus.TARGET_PENDING)

        if buy_tp >= num_levels:
            logger.info("GRID EXHAUSTED: all %d buy levels are TARGET_PENDING", buy_tp)
            return 'buy'
        if sell_tp >= num_levels:
            logger.info("GRID EXHAUSTED: all %d sell levels are TARGET_PENDING", sell_tp)
            return 'sell'
        return None

    def _reanchor_grid(self, exhausted_side: str):
        """
        Reanchor algorithm (10 steps).

        1. Find last fill price on exhausted side -> new anchor
        2. Increment counters
        3. Increase spacing
        4. Check safety (max reanchors)
        5. Cancel ALL open orders (both sides)
        6. Close all open groups as CANCELLED
        7. Clear state
        8. Set new anchor, recompute grid
        9. Place fresh entries
        10. Save state, set cooldown
        """
        old_anchor = self.state.anchor_price

        # Step 1: Find last fill price on exhausted side
        new_anchor = self._get_last_filled_price(exhausted_side)

        logger.info("=" * 60)
        logger.info("REANCHORING (%s exhausted): %.2f -> %.2f",
                     exhausted_side.upper(), old_anchor, new_anchor)
        logger.info("=" * 60)

        # Step 2: Increment counters
        if exhausted_side == 'buy':
            self.state.buy_reanchor_count += 1
        else:
            self.state.sell_reanchor_count += 1
        self.state.total_reanchors += 1

        # Step 3: Increase spacing
        self.state.current_spacing = round(
            self.state.current_spacing + self.config.base_spacing, 10)
        logger.info("Spacing increased to %.4f (reanchor #%d)",
                     self.state.current_spacing, self.state.total_reanchors)

        # Step 4: Check safety
        if self.state.total_reanchors >= self.config.max_reanchors:
            logger.warning("MAX REANCHORS REACHED: %d (limit=%d). STOPPING BOT.",
                           self.state.total_reanchors, self.config.max_reanchors)
            self.state.save()
            self.running = False
            return

        # Step 5: Cancel all open orders
        logger.info("Step 5: Cancelling all orders...")
        self.cancel_all()

        # Step 6: Close all open groups as CANCELLED
        logger.info("Step 6: Closing %d open groups as CANCELLED...",
                     len(self.state.open_groups))
        for group in list(self.state.open_groups.values()):
            group.status = TollGateStatus.CANCELLED
            group.realized_pnl = 0.0
            group.closed_at = datetime.now().isoformat()
            self.state.closed_groups.append(group.to_dict())

        # Step 7: Clear state
        logger.info("Step 7: Clearing state...")
        self.state.open_groups = {}
        self.state.order_to_group = {}
        self.level_groups = {}
        self._order_status_cache = {}

        # Step 8: Set new anchor, recompute grid
        logger.info("Step 8: Recomputing grid at anchor=%.2f, spacing=%.4f...",
                     new_anchor, self.state.current_spacing)
        self.config.anchor_price = new_anchor
        self.state.anchor_price = new_anchor
        self.buy_levels, self.sell_levels = self.config.compute_levels(self.state.current_spacing)

        # Step 9: Place fresh entries
        logger.info("Step 9: Placing fresh entries...")
        self._place_entries()

        # Step 10: Save and cooldown
        self.state.save()
        self._last_reanchor_time = datetime.now()
        self.state.print_summary()

        logger.info("=" * 60)
        logger.info("REANCHOR COMPLETE: %.2f -> %.2f | Side: %s | Open: %d",
                     old_anchor, new_anchor, exhausted_side.upper(),
                     len(self.state.open_groups))
        logger.info("=" * 60)

    def _get_last_filled_price(self, side: str) -> float:
        """Get the deepest fill price on the given side."""
        bot_id = 'A' if side == 'buy' else 'B'
        candidates = [
            g for g in self.state.open_groups.values()
            if g.bot == bot_id and g.status == TollGateStatus.TARGET_PENDING
               and g.entry_fill_price > 0
        ]
        if not candidates:
            return self.state.anchor_price
        if side == 'buy':
            return round(min(g.entry_fill_price for g in candidates), 2)
        else:
            return round(max(g.entry_fill_price for g in candidates), 2)

    def cancel_all(self):
        """Cancel all open/partial orders (entries + targets)."""
        cancelled = 0
        for group in list(self.state.open_groups.values()):
            # Cancel entry if still open/partial
            if group.status in (TollGateStatus.ENTRY_PENDING, TollGateStatus.ENTRY_PARTIAL):
                if group.entry_order_id:
                    if self.client.cancel_order(group.entry_order_id):
                        cancelled += 1

            # Cancel unfilled targets
            for target in group.target_orders:
                if target.get('filled_qty', 0) < target.get('qty', 0):
                    tid = target.get('order_id')
                    if tid:
                        if self.client.cancel_order(tid):
                            cancelled += 1

        logger.info("Cancelled %d orders total", cancelled)
        self.state.save()

    def _reconcile_orders(self):
        """
        On startup with existing state, reconcile with broker.

        Check actual order statuses and process any fills that occurred while offline.
        """
        if not self.state.open_groups:
            return

        logger.info("Reconciling state with broker orders...")
        orders = self.client.get_orders()
        if not orders:
            logger.warning("No orders returned from broker during reconciliation")
            return

        broker_orders = {str(o['order_id']): o for o in orders}

        for group in list(self.state.open_groups.values()):
            # Check entry order
            if group.status in (TollGateStatus.ENTRY_PENDING, TollGateStatus.ENTRY_PARTIAL):
                if group.entry_order_id:
                    broker_order = broker_orders.get(group.entry_order_id)
                    if broker_order:
                        status = broker_order.get('status', '')
                        if status in ('COMPLETE', 'PARTIAL'):
                            logger.info("Reconcile: entry fill for group=%s", group.group_id)
                            self._handle_fill_event(broker_order)
                        elif status in ('CANCELLED', 'REJECTED'):
                            logger.info("Reconcile: entry %s for group=%s", status, group.group_id)
                            level_key = f"{group.bot}:{group.subset_index}"
                            self.level_groups.pop(level_key, None)
                            self.state.open_groups.pop(group.group_id, None)

            # Check target orders
            for target in group.target_orders:
                tid = target.get('order_id')
                if tid and target.get('filled_qty', 0) < target.get('qty', 0):
                    broker_order = broker_orders.get(tid)
                    if broker_order:
                        status = broker_order.get('status', '')
                        if status in ('COMPLETE', 'PARTIAL'):
                            logger.info("Reconcile: target fill for group=%s", group.group_id)
                            self._handle_fill_event(broker_order)

        self.state.save()
        logger.info("Reconciliation complete")

    def _rebuild_level_groups(self):
        """Rebuild level_groups mapping from loaded state."""
        self.level_groups = {}
        for gid, group in self.state.open_groups.items():
            key = f"{group.bot}:{group.subset_index}"
            self.level_groups[key] = gid

    def _shutdown_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM gracefully."""
        logger.info("Shutdown signal received (sig=%d)", signum)
        self.running = False

    def _shutdown(self):
        """Graceful shutdown: save state, do NOT cancel orders."""
        logger.info("Shutting down TollGate engine...")
        self.state.save()
        self.state.print_summary()
        logger.info("State saved. Orders remain active (NRML). "
                     "Run with --cancel-all to cancel open orders.")
        logger.info("Total PnL: %.2f | Cycles: %d | Inventory: %d",
                     self.state.total_pnl, self.state.total_cycles,
                     self.state.net_inventory)
