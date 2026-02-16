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
from datetime import datetime
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

        # Compute grid levels
        self.buy_levels = self.grid.compute_buy_levels()
        self.sell_levels = self.grid.compute_sell_levels()

        # Initialize bots
        self.buy_bot = BuyBot(self.buy_levels, self.client, self.state, config)
        self.sell_bot = SellBot(self.sell_levels, self.client, self.state, config)

        # Order status cache: order_id → "status:filled_qty"
        # Detects incremental partial fills and prevents reprocessing
        self._order_status_cache: Dict[str, str] = {}

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

        # Print grid layout
        self.config.print_grid_layout()

        # Load state or start fresh
        if self.state.load():
            logger.info("Resuming from saved state")
            self.state.anchor_price = self.config.anchor_price
            self.buy_bot.restore_level_groups()
            self.sell_bot.restore_level_groups()
            self._reconcile_orders()
        else:
            logger.info("Starting fresh grid at anchor=%.2f", self.config.anchor_price)
            self.state.anchor_price = self.config.anchor_price

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
