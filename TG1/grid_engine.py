"""
Grid OCO Trading Engine for TG1.

Implements the full Findoc GridOcoLogic lifecycle:
  1. Create grid levels (linear arithmetic spacing)
  2. Place one entry at a time per side (BUY DESC / SELL ASC)
  3. On entry fill: capture TokenB price, compute target + OCO prices,
     transform record to target state
  4. Place target order (TokenA), manage OCO orders (TokenB) dynamically
  5. On target fill: reset level to entry state (new uuid), clear OCO
  6. On OCO fill: mark level OcoFilled=True (permanently closed)
  7. Dynamic OCO bracketing: at most 2 active OCO orders per direction
     (nearest above + nearest below current TokenB price)
  8. Termination: OCO imbalance or untriggered OCO buildup

Trade types:
  gridocots  - BUY + SELL grid with OCO
  buyocots   - BUY-only grid with OCO
  sellocots  - SELL-only grid with OCO
  buyts      - BUY-only grid, no OCO
  sellts     - SELL-only grid, no OCO
"""

import time
import signal
import logging
from datetime import datetime
from typing import Optional

from .config import GridOcoConfig
from .models import OpenOrder, OrderHistoryRecord, new_uuid
from .state import StateManager
from .findoc_client import FindocMultiClient
from .zerodha_feed import ZerodhaFeed

logger = logging.getLogger(__name__)


class GridOcoEngine:
    """
    Main grid OCO trading engine.

    Orchestrates entry/target orders on TokenA (Trade session) and
    OCO hedge orders on TokenB (Upside/Downside OCO sessions).
    Uses KiteTicker for real-time prices and XTS for order placement.
    """

    def __init__(self, config: GridOcoConfig):
        self.config = config
        self.running = False
        self.terminated = False
        self.max_quantity_reached = False

        # Components
        self.client = FindocMultiClient(config)
        self.state = StateManager(config.bot_name)
        self.feed: Optional[ZerodhaFeed] = None

        # Instrument token mapping (for KiteTicker)
        self._token_a_inst: Optional[int] = None
        self._token_b_inst: Optional[int] = None

    # ================================================================
    #  STARTUP
    # ================================================================

    def start(self):
        """
        Start the grid OCO engine.

        1. Connect to XTS + Zerodha
        2. Start KiteTicker for real-time prices
        3. Load state or create fresh grid
        4. Enter main polling loop
        """
        # Connect to all sessions
        if not self.client.connect():
            logger.error("Cannot start: connection failed")
            return

        # Resolve instrument tokens for KiteTicker
        self._token_a_inst = self.client.resolve_instrument_token(
            self.config.token_a_symbol)
        if self._token_a_inst is None:
            logger.error("Cannot resolve instrument_token for %s",
                         self.config.token_a_symbol)
            return

        subscribe_tokens = [self._token_a_inst]
        if self.config.has_oco and self.config.token_b_symbol:
            self._token_b_inst = self.client.resolve_instrument_token(
                self.config.token_b_symbol)
            if self._token_b_inst is None:
                logger.error("Cannot resolve instrument_token for %s",
                             self.config.token_b_symbol)
                return
            subscribe_tokens.append(self._token_b_inst)

        # Start KiteTicker feed
        creds = self.client.get_zerodha_credentials()
        self.feed = ZerodhaFeed(creds['api_key'], creds['access_token'])
        self.feed.subscribe(subscribe_tokens)
        self.feed.start()

        # Wait for initial prices
        logger.info("Waiting for initial tick data...")
        for _ in range(30):
            if self.feed.get_ltp(self._token_a_inst) is not None:
                break
            time.sleep(1)
        else:
            logger.error("Timeout waiting for TokenA price from KiteTicker")
            self.feed.stop()
            return

        # Print config
        self.config.print_grid_layout()

        # Load state or create fresh grid
        if self.state.load():
            logger.info("Resuming from saved state: %d open orders",
                         len(self.state.open_orders))
            self._reconcile_orders()
        else:
            logger.info("Starting fresh grid")
            self._create_grid_levels()
            self.state.trade_type = self.config.trade_type
            self.state.token_a_symbol = self.config.token_a_symbol
            self.state.token_b_symbol = self.config.token_b_symbol
            self.state.entry_price = self.config.entry_price
            self.state.max_quantity = self.config.max_quantity
            self.state.save()

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Enter main loop
        self.running = True
        logger.info("Grid OCO engine started. Polling every %.1fs",
                     self.config.poll_interval)
        self._run_loop()

    # ================================================================
    #  GRID CREATION
    # ================================================================

    def _create_grid_levels(self):
        """Create initial grid level records based on trade type."""
        orders = []
        trade_type = self.config.trade_type

        # SELL levels (upside) — entries above entry_price
        if trade_type in ('gridocots', 'sellocots', 'sellts'):
            for i in range(1, self.config.steps + 1):
                entry_price = self.config.entry_price + (i * self.config.spread)
                orders.append(OpenOrder(
                    bot_name=self.config.bot_name,
                    entry_trade_direction='SELL',
                    entry_trade_price=self.client.round_to_tick(
                        entry_price, self.config.token_a_symbol),
                    trade_side='upside',
                    order_side='entry',
                    token_a_quantity=self.config.token_a_quantity,
                    token_b_quantity=self.config.token_b_quantity,
                ))

        # BUY levels (downside) — entries below entry_price
        if trade_type in ('gridocots', 'buyocots', 'buyts'):
            for i in range(1, self.config.steps + 1):
                entry_price = self.config.entry_price - (i * self.config.spread)
                orders.append(OpenOrder(
                    bot_name=self.config.bot_name,
                    entry_trade_direction='BUY',
                    entry_trade_price=self.client.round_to_tick(
                        entry_price, self.config.token_a_symbol),
                    trade_side='downside',
                    order_side='entry',
                    token_a_quantity=self.config.token_a_quantity,
                    token_b_quantity=self.config.token_b_quantity,
                ))

        self.state.open_orders = orders
        logger.info("Created %d grid levels", len(orders))

    # ================================================================
    #  MAIN POLLING LOOP
    # ================================================================

    def _run_loop(self):
        """Main 1-second polling loop."""
        poll_count = 0
        while self.running:
            try:
                if self.terminated:
                    break

                changes = self._poll_cycle()
                if changes:
                    self.state.save()

                poll_count += 1
                if poll_count % 60 == 0:
                    token_b_price = self._get_token_b_price()
                    logger.info(
                        "Poll #%d | Open: %d | Up_qty=%.0f Down_qty=%.0f | "
                        "Up_oco=%d Down_oco=%d | PnL=%.2f | TokenB=%.2f",
                        poll_count, len(self.state.open_orders),
                        self.state.upside_net_quantity,
                        self.state.downside_net_quantity,
                        self.state.upside_oco_net_count,
                        self.state.downside_oco_net_count,
                        self.state.total_pnl,
                        token_b_price or 0)

                time.sleep(self.config.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Poll loop error: %s", e, exc_info=True)
                time.sleep(self.config.poll_interval * 2)

        self._shutdown()

    def _poll_cycle(self) -> bool:
        """
        One complete poll cycle:
        1. Check max quantity
        2. Check OCO termination conditions
        3. Check untriggered OCO buildup
        4. Place entry orders (one per side)
        5. Poll entry order statuses
        6. Poll target order statuses
        7. Poll OCO order statuses
        8. Manage dynamic OCO bracketing

        Returns True if any state changes occurred.
        """
        changes = False

        # Check termination conditions
        if self._check_termination():
            return True

        # Check max quantity
        self._check_max_quantity()

        # Place entry orders (one at a time per side)
        if self._place_entry_orders():
            changes = True

        # Poll entry orders for fills
        if self._poll_entry_orders():
            changes = True

        # Poll target orders for fills
        if self._poll_target_orders():
            changes = True

        # OCO management (only for OCO trade types)
        if self.config.has_oco:
            # Poll OCO orders for fills
            if self._poll_oco_orders():
                changes = True

            # Dynamic OCO bracketing
            if self._manage_oco_orders():
                changes = True

        return changes

    # ================================================================
    #  ENTRY ORDER PLACEMENT
    # ================================================================

    def _place_entry_orders(self) -> bool:
        """
        Place at most one entry order per side.

        BUY entries: sorted DESC by price (nearest to market first), limit 1.
        SELL entries: sorted ASC by price (nearest to market first), limit 1.

        MaxQuantity check: BUY entries on downside are blocked when
        maxQuantityReached=True. SELL entries on upside are blocked when
        maxQuantityReached=True.
        """
        changes = False
        trade_type = self.config.trade_type

        # BUY entries
        if trade_type in ('gridocots', 'buyocots', 'buyts'):
            buy_candidates = [
                o for o in self.state.open_orders
                if (o.entry_trade_direction == 'BUY'
                    and o.order_side == 'entry'
                    and o.entry_order_id is None
                    and not o.oco_filled)
            ]
            # Sort DESC (highest price = nearest to market for BUY)
            buy_candidates.sort(key=lambda o: o.entry_trade_price, reverse=True)

            if buy_candidates:
                candidate = buy_candidates[0]
                # MaxQuantity gate: BUY on upside (target) is always OK,
                # BUY on downside (new entry) is blocked by maxQuantityReached
                can_place = True
                if candidate.trade_side == 'downside' and self.max_quantity_reached:
                    can_place = False

                if can_place:
                    if self._place_single_entry(candidate):
                        changes = True

        # SELL entries
        if trade_type in ('gridocots', 'sellocots', 'sellts'):
            sell_candidates = [
                o for o in self.state.open_orders
                if (o.entry_trade_direction == 'SELL'
                    and o.order_side == 'entry'
                    and o.entry_order_id is None
                    and not o.oco_filled)
            ]
            # Sort ASC (lowest price = nearest to market for SELL)
            sell_candidates.sort(key=lambda o: o.entry_trade_price)

            if sell_candidates:
                candidate = sell_candidates[0]
                # MaxQuantity gate: SELL on downside (target) is always OK,
                # SELL on upside (new entry) is blocked by maxQuantityReached
                can_place = True
                if candidate.trade_side == 'upside' and self.max_quantity_reached:
                    can_place = False

                if can_place:
                    if self._place_single_entry(candidate):
                        changes = True

        return changes

    def _place_single_entry(self, order: OpenOrder) -> bool:
        """Place a single entry or target order on TokenA via Trade session."""
        order_uid = f"{self.config.bot_name}_{order.uuid}_{order.order_side}"
        order_id = self.client.place_entry_order(
            symbol=self.config.token_a_symbol,
            side=order.entry_trade_direction,
            qty=int(order.token_a_quantity),
            price=order.entry_trade_price,
            order_uid=order_uid,
        )
        if order_id:
            order.entry_order_id = order_id
            # Capture TokenB price at the time entry is placed
            # (will be refreshed at fill time for accuracy)
            if self.config.has_oco and order.order_side == 'entry':
                token_b_price = self._get_token_b_price()
                if token_b_price:
                    order.token_b_price = token_b_price
            logger.info("[%s] %s %s placed: %s %d @ %.2f -> ID=%s",
                        order.trade_side, order.order_side.upper(),
                        order.entry_trade_direction,
                        self.config.token_a_symbol,
                        int(order.token_a_quantity),
                        order.entry_trade_price, order_id)
            return True
        return False

    # ================================================================
    #  ENTRY FILL HANDLING
    # ================================================================

    def _poll_entry_orders(self) -> bool:
        """Poll all placed entry orders for fills."""
        changes = False
        for order in self.state.open_orders:
            if order.order_side == 'entry' and order.entry_order_id:
                status = self.client.get_entry_order_status(
                    order.entry_order_id)
                if status is None:
                    continue
                if status['status'] == 'COMPLETE':
                    self._handle_entry_fill(order, status)
                    changes = True
                elif status['status'] == 'REJECTED':
                    logger.error("Entry REJECTED: %s -> clearing order_id",
                                 order.entry_order_id)
                    order.entry_order_id = None
                    changes = True
                elif status['status'] == 'CANCELLED':
                    logger.warning("Entry CANCELLED: %s -> clearing order_id",
                                   order.entry_order_id)
                    order.entry_order_id = None
                    changes = True
        return changes

    def _handle_entry_fill(self, order: OpenOrder, status: dict):
        """
        Handle entry order fill.

        1. Capture TokenB price at fill time
        2. Compute target price (entry +/- target_spread)
        3. Compute OCO price (tokenB -/+ oco_spread)
        4. Transform record to target state
        5. Update position counters
        6. Record in history
        """
        filled_price = status.get('price', order.entry_trade_price)
        original_direction = order.entry_trade_direction

        # Capture TokenB price at fill time
        token_b_price = self._get_token_b_price()
        if self.config.has_oco and token_b_price is None:
            logger.warning("Cannot get TokenB price at entry fill time, "
                           "using last known price")
            token_b_price = order.token_b_price

        # Compute target price
        if original_direction == 'BUY':
            target_price = order.entry_trade_price + self.config.target_spread
        else:
            target_price = order.entry_trade_price - self.config.target_spread
        target_price = self.client.round_to_tick(
            target_price, self.config.token_a_symbol)

        # Compute OCO price
        oco_trade_price = None
        oco_direction = None
        if self.config.has_oco and token_b_price:
            if original_direction == 'BUY':
                oco_trade_price = token_b_price - self.config.oco_spread
                oco_direction = 'SELL'
            else:
                oco_trade_price = token_b_price + self.config.oco_spread
                oco_direction = 'BUY'
            oco_trade_price = self.client.round_to_tick(
                oco_trade_price, self.config.token_b_symbol)

        # New direction for target order (opposite of entry)
        new_direction = 'SELL' if original_direction == 'BUY' else 'BUY'

        logger.info("[%s] ENTRY FILLED: %s %s @ %.2f (filled %.2f) | "
                    "Target: %s @ %.2f | OCO: %s @ %s | TokenB: %s",
                    order.trade_side, original_direction,
                    self.config.token_a_symbol, order.entry_trade_price,
                    filled_price, new_direction, target_price,
                    oco_direction or 'N/A',
                    f"{oco_trade_price:.2f}" if oco_trade_price else 'N/A',
                    f"{token_b_price:.2f}" if token_b_price else 'N/A')

        # Record entry in history
        history = OrderHistoryRecord(
            uuid=order.uuid,
            bot_name=self.config.bot_name,
            trade_side=order.trade_side,
            token_a_symbol=self.config.token_a_symbol,
            token_a_quantity=order.token_a_quantity,
            token_b_symbol=self.config.token_b_symbol,
            token_b_quantity=order.token_b_quantity,
            token_b_price=token_b_price,
            entry_order_id=order.entry_order_id,
            entry_trade_direction=original_direction,
            entry_trade_price=order.entry_trade_price,
            filled_entry_price=filled_price,
            entry_order_status='COMPLETE',
            created_at=datetime.now().isoformat(),
        )
        self.state.order_history.append(history)

        # Update position counters
        self.state.update_quantity('entry', original_direction,
                                  order.token_a_quantity)

        # Transform to target state
        order.entry_order_id = None
        order.entry_trade_direction = new_direction
        order.entry_trade_price = target_price
        order.oco_trade_direction = oco_direction
        order.oco_trade_price = oco_trade_price
        order.token_b_price = None  # Clear after use
        order.order_side = 'target'

    # ================================================================
    #  TARGET FILL HANDLING
    # ================================================================

    def _poll_target_orders(self) -> bool:
        """Poll all placed target orders for fills."""
        changes = False
        for order in self.state.open_orders:
            if order.order_side == 'target' and order.entry_order_id:
                status = self.client.get_entry_order_status(
                    order.entry_order_id)
                if status is None:
                    continue
                if status['status'] == 'COMPLETE':
                    self._handle_target_fill(order, status)
                    changes = True
                elif status['status'] == 'REJECTED':
                    logger.error("Target REJECTED: %s", order.entry_order_id)
                    order.entry_order_id = None
                    changes = True
                elif status['status'] == 'CANCELLED':
                    logger.warning("Target CANCELLED: %s",
                                   order.entry_order_id)
                    order.entry_order_id = None
                    changes = True
        return changes

    def _handle_target_fill(self, order: OpenOrder, status: dict):
        """
        Handle target order fill.

        1. Cancel any active OCO order for this level
        2. Update position counters
        3. Update history record
        4. Reset level back to entry state (new uuid, ready for re-entry)
        5. Clear maxQuantityReached flag
        """
        filled_price = status.get('price', order.entry_trade_price)
        # entry_trade_direction is now the TARGET direction (opposite of original)
        target_direction = order.entry_trade_direction
        # original entry direction
        original_direction = 'SELL' if target_direction == 'BUY' else 'BUY'

        logger.info("[%s] TARGET FILLED: %s @ %.2f (filled %.2f)",
                    order.trade_side, target_direction,
                    order.entry_trade_price, filled_price)

        # Cancel any active OCO for this level
        if order.oco_order_id and self.config.has_oco:
            self.client.cancel_oco_order(order.oco_order_id, order.trade_side)
            order.oco_order_id = None

        # Update position counters
        self.state.update_quantity('target', original_direction,
                                  order.token_a_quantity)

        # Update history record
        for h in reversed(self.state.order_history):
            if h.uuid == order.uuid:
                h.target_order_id = order.entry_order_id
                h.target_trade_direction = target_direction
                h.target_trade_price = order.entry_trade_price
                h.filled_target_price = filled_price
                h.target_order_status = 'COMPLETE'
                h.completed_at = datetime.now().isoformat()
                break

        # Compute re-entry price (back to original entry level)
        if original_direction == 'BUY':
            re_entry_price = order.entry_trade_price - self.config.target_spread
        else:
            re_entry_price = order.entry_trade_price + self.config.target_spread
        re_entry_price = self.client.round_to_tick(
            re_entry_price, self.config.token_a_symbol)

        # Reset level to entry state with new uuid
        order.uuid = new_uuid()
        order.entry_order_id = None
        order.oco_order_id = None
        order.entry_trade_direction = original_direction
        order.entry_trade_price = re_entry_price
        order.oco_trade_direction = None
        order.oco_trade_price = None
        order.token_b_price = None
        order.order_side = 'entry'
        order.oco_filled = False

        # Reset maxQuantityReached
        self.max_quantity_reached = False
        logger.info("[%s] Level reset for re-entry: %s @ %.2f",
                    order.trade_side, original_direction, re_entry_price)

    # ================================================================
    #  OCO ORDER MANAGEMENT
    # ================================================================

    def _poll_oco_orders(self) -> bool:
        """Poll all placed OCO orders for fills."""
        changes = False
        for order in self.state.open_orders:
            if order.oco_order_id and not order.oco_filled:
                status = self.client.get_oco_order_status(
                    order.oco_order_id, order.trade_side)
                if status is None:
                    continue
                if status['status'] == 'COMPLETE':
                    self._handle_oco_fill(order, status)
                    changes = True
                elif status['status'] == 'CANCELLED':
                    # OCO was cancelled (by our dynamic bracketing or manually)
                    order.oco_order_id = None
                    changes = True
                elif status['status'] == 'REJECTED':
                    logger.error("OCO REJECTED: %s", order.oco_order_id)
                    order.oco_order_id = None
                    changes = True
        return changes

    def _handle_oco_fill(self, order: OpenOrder, status: dict):
        """
        Handle OCO order fill.

        1. Cancel target order for this level
        2. Mark level as OcoFilled (permanently closed)
        3. Update position counters
        4. Update history record
        """
        filled_price = status.get('price', 0)
        target_direction = order.entry_trade_direction
        original_direction = 'SELL' if target_direction == 'BUY' else 'BUY'

        logger.info("[%s] OCO FILLED: %s @ %.2f (filled %.2f)",
                    order.trade_side, order.oco_trade_direction,
                    order.oco_trade_price or 0, filled_price)

        # Cancel the target order for this level
        if order.entry_order_id:
            self.client.cancel_entry_order(order.entry_order_id)

        # Update position counters
        self.state.update_quantity('oco', original_direction,
                                  order.token_a_quantity)

        # Update history
        for h in reversed(self.state.order_history):
            if h.uuid == order.uuid:
                h.oco_order_id = order.oco_order_id
                h.oco_trade_direction = order.oco_trade_direction
                h.oco_trade_price = order.oco_trade_price
                h.completed_at = datetime.now().isoformat()
                break

        # Mark level permanently closed
        # Compute re-entry price (same as target fill logic)
        if original_direction == 'BUY':
            re_entry_price = order.entry_trade_price - self.config.target_spread
        else:
            re_entry_price = order.entry_trade_price + self.config.target_spread

        order.entry_order_id = None
        order.oco_order_id = None
        order.entry_trade_direction = original_direction
        order.entry_trade_price = re_entry_price
        order.oco_trade_direction = None
        order.oco_trade_price = None
        order.token_b_price = None
        order.oco_filled = True
        order.order_side = 'entry'

    def _manage_oco_orders(self) -> bool:
        """
        Dynamic OCO bracketing — maintain at most 2 active OCO orders
        per direction (nearest above + nearest below current TokenB price).

        For each OCO direction (BUY, SELL):
          1. Find all orders with oco_trade_price set (target state, not filled)
          2. Find nearest below and nearest above current TokenB price
          3. Place those two if not already placed
          4. Cancel any other active OCO orders for that direction
        """
        token_b_price = self._get_token_b_price()
        if token_b_price is None or token_b_price <= 0:
            return False

        changes = False

        # Process BUY OCO orders (from SELL entries → upside)
        if self._manage_oco_direction('BUY', token_b_price):
            changes = True

        # Process SELL OCO orders (from BUY entries → downside)
        if self._manage_oco_direction('SELL', token_b_price):
            changes = True

        return changes

    def _manage_oco_direction(self, oco_direction: str,
                               current_price: float) -> bool:
        """
        Manage OCO orders for a single direction (BUY or SELL).

        1. Find all target-state orders with matching oco_trade_direction
        2. Determine nearest below and nearest above current price
        3. Ensure those two are placed, cancel all others
        """
        changes = False

        # All orders that have an OCO price set for this direction
        oco_candidates = [
            o for o in self.state.open_orders
            if (o.oco_trade_direction == oco_direction
                and o.oco_trade_price is not None
                and not o.oco_filled)
        ]

        if not oco_candidates:
            return False

        # Find nearest below (or equal) current price
        below_candidates = [
            o for o in oco_candidates
            if o.oco_trade_price <= current_price
        ]
        below_candidates.sort(key=lambda o: o.oco_trade_price, reverse=True)
        nearest_below = below_candidates[0] if below_candidates else None

        # Find nearest above current price
        above_candidates = [
            o for o in oco_candidates
            if o.oco_trade_price > current_price
        ]
        above_candidates.sort(key=lambda o: o.oco_trade_price)
        nearest_above = above_candidates[0] if above_candidates else None

        # Set of orders that SHOULD have active OCO orders
        should_be_active = set()
        if nearest_below:
            should_be_active.add(nearest_below.uuid)
        if nearest_above:
            should_be_active.add(nearest_above.uuid)

        # Get all currently placed OCO orders for this direction
        existing_oco = [
            o for o in oco_candidates
            if o.oco_order_id is not None
        ]

        # Cancel OCO orders that are NOT in should_be_active
        for o in existing_oco:
            if o.uuid not in should_be_active:
                logger.info("[%s] Cancelling stale OCO: %s %s @ %.2f",
                            o.trade_side, oco_direction,
                            self.config.token_b_symbol,
                            o.oco_trade_price)
                if self.client.cancel_oco_order(o.oco_order_id, o.trade_side):
                    o.oco_order_id = None
                    changes = True

        # Place OCO orders that SHOULD be active but are not
        for target_order in [nearest_below, nearest_above]:
            if target_order is None:
                continue
            if target_order.oco_order_id is not None:
                continue
            # Check if an existing OCO order already covers this price
            already_covered = any(
                o.oco_order_id is not None
                and o.oco_trade_price == target_order.oco_trade_price
                for o in existing_oco
            )
            if already_covered:
                continue

            order_uid = (f"{self.config.bot_name}_{target_order.uuid}_oco")
            oco_id = self.client.place_oco_order(
                symbol=self.config.token_b_symbol,
                side=oco_direction,
                qty=int(target_order.token_b_quantity),
                price=target_order.oco_trade_price,
                trade_side=target_order.trade_side,
                order_uid=order_uid,
            )
            if oco_id:
                target_order.oco_order_id = oco_id
                logger.info("[%s] OCO PLACED: %s %s %d @ %.2f -> ID=%s",
                            target_order.trade_side, oco_direction,
                            self.config.token_b_symbol,
                            int(target_order.token_b_quantity),
                            target_order.oco_trade_price, oco_id)
                changes = True

        return changes

    # ================================================================
    #  TERMINATION CONDITIONS
    # ================================================================

    def _check_max_quantity(self):
        """
        Check if max quantity has been reached.
        Only PAUSES new entries — does NOT terminate.
        """
        max_qty = self.config.max_quantity
        if (abs(self.state.upside_net_quantity) >= max_qty or
                abs(self.state.downside_net_quantity) >= max_qty):
            if not self.max_quantity_reached:
                self.max_quantity_reached = True
                logger.warning("MAX QUANTITY REACHED: upside=%.0f "
                               "downside=%.0f max=%.0f — pausing new entries",
                               self.state.upside_net_quantity,
                               self.state.downside_net_quantity, max_qty)

    def _check_termination(self) -> bool:
        """
        Check termination conditions:

        1. OCO imbalance:
           - Same OCO account: |upside_oco - downside_oco| >= steps
           - Different accounts: upside_oco >= steps OR downside_oco >= steps

        2. Untriggered OCO buildup:
           If BUY or SELL untriggered OCO orders >= oco_stop_count, terminate.
           "Untriggered" means BUY OCO at/below current price (should have
           filled but didn't) or SELL OCO at/above current price.
        """
        if self.terminated or not self.config.has_oco:
            return False

        # 1. OCO imbalance check
        if self.config.same_oco_account:
            oco_condition = (abs(self.state.upside_oco_net_count -
                                self.state.downside_oco_net_count) >=
                            self.config.steps)
        else:
            oco_condition = (abs(self.state.upside_oco_net_count) >=
                            self.config.steps or
                            abs(self.state.downside_oco_net_count) >=
                            self.config.steps)

        if oco_condition:
            logger.error("TERMINATING: OCO imbalance — upside_oco=%d "
                         "downside_oco=%d steps=%d",
                         self.state.upside_oco_net_count,
                         self.state.downside_oco_net_count,
                         self.config.steps)
            self._terminate("OCO imbalance")
            return True

        # 2. Untriggered OCO buildup check
        token_b_price = self._get_token_b_price()
        if token_b_price and token_b_price > 0:
            oco_orders = [
                o for o in self.state.open_orders
                if o.oco_trade_price is not None and not o.oco_filled
            ]

            buy_oco = [o for o in oco_orders
                       if o.oco_trade_direction == 'BUY']
            sell_oco = [o for o in oco_orders
                        if o.oco_trade_direction == 'SELL']

            # BUY OCO at or below current price should have triggered
            untriggered_buy = len([
                o for o in buy_oco
                if o.oco_trade_price <= token_b_price
            ])
            # SELL OCO at or above current price should have triggered
            untriggered_sell = len([
                o for o in sell_oco
                if o.oco_trade_price >= token_b_price
            ])

            if (untriggered_buy >= self.config.oco_stop_count or
                    untriggered_sell >= self.config.oco_stop_count):
                logger.error("TERMINATING: Untriggered OCO buildup — "
                             "buy_untriggered=%d sell_untriggered=%d "
                             "threshold=%d",
                             untriggered_buy, untriggered_sell,
                             self.config.oco_stop_count)
                self._terminate("untriggered OCO buildup")
                return True

        return False

    def _terminate(self, reason: str):
        """Cancel all orders and terminate the bot."""
        self.terminated = True
        self.state.bot_status = f"Terminated: {reason}"
        logger.error("BOT TERMINATED: %s", reason)
        self.cancel_all()
        self.state.save()

    # ================================================================
    #  RECONCILIATION
    # ================================================================

    def _reconcile_orders(self):
        """
        On startup with existing state, check actual order statuses
        and process any fills that occurred while we were down.
        """
        logger.info("Reconciling state with broker orders...")

        for order in self.state.open_orders:
            # Check entry/target orders
            if order.entry_order_id:
                status = self.client.get_entry_order_status(
                    order.entry_order_id)
                if status:
                    if status['status'] == 'COMPLETE':
                        if order.order_side == 'entry':
                            logger.info("Reconcile: entry fill for %s",
                                         order.uuid)
                            self._handle_entry_fill(order, status)
                        elif order.order_side == 'target':
                            logger.info("Reconcile: target fill for %s",
                                         order.uuid)
                            self._handle_target_fill(order, status)
                    elif status['status'] in ('CANCELLED', 'REJECTED'):
                        order.entry_order_id = None

            # Check OCO orders
            if order.oco_order_id and not order.oco_filled:
                status = self.client.get_oco_order_status(
                    order.oco_order_id, order.trade_side)
                if status:
                    if status['status'] == 'COMPLETE':
                        logger.info("Reconcile: OCO fill for %s", order.uuid)
                        self._handle_oco_fill(order, status)
                    elif status['status'] in ('CANCELLED', 'REJECTED'):
                        order.oco_order_id = None

        self.state.save()
        logger.info("Reconciliation complete")

    # ================================================================
    #  CANCEL ALL
    # ================================================================

    def cancel_all(self):
        """Cancel all active orders across all sessions."""
        cancelled = 0
        for order in self.state.open_orders:
            if order.entry_order_id:
                if self.client.cancel_entry_order(order.entry_order_id):
                    cancelled += 1
                order.entry_order_id = None
            if order.oco_order_id:
                if self.client.cancel_oco_order(
                        order.oco_order_id, order.trade_side):
                    cancelled += 1
                order.oco_order_id = None
        logger.info("Cancelled %d orders", cancelled)
        self.state.save()

    # ================================================================
    #  HELPERS
    # ================================================================

    def _get_token_b_price(self) -> Optional[float]:
        """Get current TokenB price from KiteTicker feed."""
        if self._token_b_inst and self.feed:
            return self.feed.get_ltp(self._token_b_inst)
        return None

    def _shutdown_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM gracefully."""
        logger.info("Shutdown signal received (sig=%d)", signum)
        self.running = False

    def _shutdown(self):
        """Graceful shutdown: save state, stop feed."""
        logger.info("Shutting down grid OCO engine...")
        self.state.save()
        if self.feed:
            self.feed.stop()

        active = len([o for o in self.state.open_orders
                      if o.entry_order_id or o.oco_order_id])
        logger.info("State saved. %d orders remain active on exchange.", active)
        logger.info("Position: upside_qty=%.0f downside_qty=%.0f | "
                     "OCO: up=%d down=%d | PnL=%.2f",
                     self.state.upside_net_quantity,
                     self.state.downside_net_quantity,
                     self.state.upside_oco_net_count,
                     self.state.downside_oco_net_count,
                     self.state.total_pnl)
        logger.info("Run with --cancel-all to cancel open orders.")
