"""
AMM Engine — ratio sampling, signal generation, and order management.

Single engine handles all pairs in one polling loop:
1. Ratio sampling (every sample_interval seconds): fetch LTPs, compute ratios,
   check entry signals after warmup.
2. Order polling (every poll_interval seconds): check fills, process status
   changes for entry/exit legs.
3. Exit checking: for each OPEN position, check if ratio reverted to mean.

No stop-loss — target-only exit when ratio reverts to mean.
Stacking allowed up to max_positions_per_pair per pair.
"""

import os
import time
import signal
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import AMMConfig, PairConfig
from .state import AMMState, AMMPosition, RatioSample

logger = logging.getLogger(__name__)


class AMMEngine:
    """
    Ratio mean-reversion stat-arb engine.

    Samples ratios at fixed intervals, generates entry signals when z-score
    exceeds threshold, exits when ratio reverts to mean.
    """

    def __init__(self, config: AMMConfig, pnl_tracker=None):
        self.config = config
        self.running = False

        self.pnl = pnl_tracker
        self._pnl_session_id = None

        # Client initialized in start()
        self.client = None
        self.state = AMMState(rolling_window=config.rolling_window)

        # Order status cache: order_id -> "status:filled_qty"
        self._order_status_cache: Dict[str, str] = {}

        # Timing
        self._last_sample_time: float = 0.0

        # Session refresh
        self._session_refresh_interval = timedelta(minutes=30)
        self._last_session_refresh: Optional[datetime] = None
        self._consecutive_poll_errors: int = 0
        self._max_poll_errors_before_refresh: int = 5

    def start(self):
        """
        Start the AMM engine.

        1. Build unique ticker list from all pairs
        2. Connect client with all tickers
        3. Load state or start fresh
        4. Reconcile open positions with broker
        5. Enter main polling loop
        """
        from .client import AMMClient

        symbols = self.config.get_all_symbols()
        logger.info("AMM starting with symbols: %s", ', '.join(symbols))

        self.client = AMMClient(
            interactive_key=self.config.interactive_key,
            interactive_secret=self.config.interactive_secret,
            marketdata_key=self.config.marketdata_key,
            marketdata_secret=self.config.marketdata_secret,
            root_url=self.config.xts_root,
        )
        if not self.client.connect(symbols):
            logger.error("Cannot start: connection failed")
            return

        self._last_session_refresh = datetime.now()

        # Load state
        if self.state.load():
            logger.info("Resuming from saved AMM state")
        else:
            logger.info("Starting fresh AMM state")

        # Reconcile open positions with broker order book
        self._reconcile_orders()

        # Print config and state
        self.config.print_summary()
        self.state.print_summary()

        # Initialize PnL tracking
        if self.pnl:
            try:
                config_snap = {
                    'pairs': [p.to_dict() for p in self.config.pairs],
                    'base_qty': self.config.base_qty,
                    'rolling_window': self.config.rolling_window,
                    'product': self.config.product,
                }
                self._pnl_session_id = self.pnl.start_session('amm_statarb', config_snap)
            except Exception as e:
                logger.warning("PnL tracker init failed (non-fatal): %s", e)

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Enter main loop
        self.running = True
        self._last_sample_time = 0.0  # Force immediate first sample
        logger.info("AMM engine started. Sample every %ds, poll every %.1fs",
                     self.config.sample_interval, self.config.poll_interval)
        self._run_loop()

    def _run_loop(self):
        """Main loop: sample ratios + poll orders + check exits."""
        poll_count = 0
        while self.running:
            try:
                now = time.time()

                # Proactive session refresh every 30 min
                if self._last_session_refresh:
                    elapsed = datetime.now() - self._last_session_refresh
                    if elapsed >= self._session_refresh_interval:
                        logger.info("Proactive session refresh (%.0f min since last)",
                                    elapsed.total_seconds() / 60)
                        self._refresh_xts_session()

                # Ratio sampling (every sample_interval)
                if now - self._last_sample_time >= self.config.sample_interval:
                    self._sample_ratios()
                    self._last_sample_time = now

                # Order polling (every poll_interval)
                fills_processed = self._poll_orders()
                if fills_processed is None:
                    self._consecutive_poll_errors += 1
                    if self._consecutive_poll_errors >= self._max_poll_errors_before_refresh:
                        logger.warning("Reactive session refresh after %d consecutive poll errors",
                                       self._consecutive_poll_errors)
                        self._refresh_xts_session()
                        self._consecutive_poll_errors = 0
                    time.sleep(self.config.poll_interval)
                    continue

                self._consecutive_poll_errors = 0

                # Check exit signals for OPEN positions
                self._check_exits()

                if fills_processed > 0:
                    self.state.save()
                    self.state.print_summary()

                poll_count += 1
                if poll_count % 100 == 0:
                    logger.info("Poll #%d | Open: %d | PnL: %.2f | Trades: %d",
                                poll_count, len(self.state.open_positions),
                                self.state.total_pnl, self.state.total_trades)
                    self.state.save()  # Periodic save

                time.sleep(self.config.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Poll loop error: %s", e, exc_info=True)
                time.sleep(self.config.poll_interval * 2)

        self._shutdown()

    # ----- Ratio Sampling -----

    def _sample_ratios(self):
        """Fetch LTPs, compute ratios, check entry signals for each pair."""
        now_iso = datetime.now().isoformat()

        for i, pair in enumerate(self.config.pairs):
            if not pair.enabled:
                continue

            num_ltp = self.client.get_ltp(pair.numerator_ticker)
            den_ltp = self.client.get_ltp(pair.denominator_ticker)

            if not num_ltp or not den_ltp or den_ltp == 0:
                logger.debug("Pair %d: LTP unavailable (num=%s, den=%s)",
                             i, num_ltp, den_ltp)
                continue

            ratio = num_ltp / den_ltp
            sample = RatioSample(
                timestamp=now_iso,
                num_price=num_ltp,
                den_price=den_ltp,
                ratio=ratio,
            )
            self.state.add_sample(i, sample)

            # Check if warmup complete
            stats = self.state.get_rolling_stats(i)
            if stats is None:
                series_len = len(self.state.ratio_series.get(i, []))
                logger.debug("Pair %d: warmup %d/%d (R=%.6f)",
                             i, series_len, self.config.warmup_samples, ratio)
                continue

            mean, sd = stats
            if sd == 0:
                logger.debug("Pair %d: SD=0, skipping signal check", i)
                continue

            z_score = (ratio - mean) / sd
            logger.info("Pair %d [%s/%s]: R=%.6f μ=%.6f σ=%.6f z=%.2f",
                        i, pair.numerator_ticker, pair.denominator_ticker,
                        ratio, mean, sd, z_score)

            self._check_entry_signal(i, pair, ratio, mean, sd, z_score,
                                     num_ltp, den_ltp)

    # ----- Entry Signal -----

    def _check_entry_signal(self, pair_index: int, pair: PairConfig,
                            ratio: float, mean: float, sd: float,
                            z_score: float, num_ltp: float, den_ltp: float):
        """Check if z-score exceeds threshold and enter a pair trade."""
        # Check position limit
        if self.state.active_count(pair_index) >= self.config.max_positions_per_pair:
            return

        if z_score > pair.entry_sd:
            # Ratio HIGH -> numerator overpriced -> SELL num, BUY den
            logger.info("ENTRY SIGNAL: Pair %d z=%.2f > %.2f -> SHORT_NUM",
                        pair_index, z_score, pair.entry_sd)
            self._enter_position(pair_index, pair, "SHORT_NUM",
                                 ratio, mean, sd, num_ltp, den_ltp)

        elif z_score < -pair.entry_sd:
            # Ratio LOW -> numerator underpriced -> BUY num, SELL den
            logger.info("ENTRY SIGNAL: Pair %d z=%.2f < -%.2f -> LONG_NUM",
                        pair_index, z_score, pair.entry_sd)
            self._enter_position(pair_index, pair, "LONG_NUM",
                                 ratio, mean, sd, num_ltp, den_ltp)

    def _enter_position(self, pair_index: int, pair: PairConfig,
                        direction: str, ratio: float, mean: float,
                        sd: float, num_ltp: float, den_ltp: float):
        """Place both legs of a pair trade."""
        num_qty = max(1, round(self.config.base_qty * pair.numerator_trade_pct / 100))
        den_qty = max(1, round(self.config.base_qty * pair.denominator_trade_pct / 100))

        pos = AMMPosition.create(
            pair_index=pair_index,
            direction=direction,
            entry_ratio=ratio,
            entry_mean=mean,
            entry_sd=sd,
            num_entry_price=num_ltp,
            den_entry_price=den_ltp,
            num_qty=num_qty,
            den_qty=den_qty,
        )

        if direction == "SHORT_NUM":
            # SELL numerator, BUY denominator
            num_side, den_side = "SELL", "BUY"
            num_price = round(num_ltp - self.config.slippage, 2)
            den_price = round(den_ltp + self.config.slippage, 2)
        else:
            # BUY numerator, SELL denominator
            num_side, den_side = "BUY", "SELL"
            num_price = round(num_ltp + self.config.slippage, 2)
            den_price = round(den_ltp - self.config.slippage, 2)

        # Ensure prices are positive
        num_price = max(0.01, num_price)
        den_price = max(0.01, den_price)

        logger.info("ENTERING %s: Pair %d [%s/%s] num=%s %d@%.2f den=%s %d@%.2f "
                     "R=%.6f μ=%.6f σ=%.6f",
                     direction, pair_index,
                     pair.numerator_ticker, pair.denominator_ticker,
                     num_side, num_qty, num_price,
                     den_side, den_qty, den_price,
                     ratio, mean, sd)

        # Place numerator leg
        num_oid = self.client.place_order(
            pair.numerator_ticker, num_side, num_qty, num_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=f"AMM-{pos.position_id}-NUM",
        )

        # Place denominator leg
        den_oid = self.client.place_order(
            pair.denominator_ticker, den_side, den_qty, den_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=f"AMM-{pos.position_id}-DEN",
        )

        if not num_oid and not den_oid:
            logger.error("Both entry legs failed for position %s", pos.position_id)
            return

        pos.num_entry_order_id = num_oid
        pos.den_entry_order_id = den_oid

        # Register in state
        self.state.register_position(pos)
        self.state.save()

        logger.info("Position %s created: numOID=%s denOID=%s",
                     pos.position_id, num_oid, den_oid)

    # ----- Exit Signal -----

    def _check_exits(self):
        """Check if any OPEN position's ratio has reverted to mean."""
        for pos in list(self.state.open_positions.values()):
            if pos.status != "OPEN":
                continue

            pair = self.config.pairs[pos.pair_index]
            stats = self.state.get_rolling_stats(pos.pair_index)
            if not stats:
                continue
            mean, sd = stats

            num_ltp = self.client.get_ltp(pair.numerator_ticker)
            den_ltp = self.client.get_ltp(pair.denominator_ticker)
            if not num_ltp or not den_ltp or den_ltp == 0:
                continue
            current_ratio = num_ltp / den_ltp

            # Check if ratio reverted to mean (within tolerance)
            tolerance = self.config.mean_reversion_tolerance * mean
            if abs(current_ratio - mean) <= tolerance:
                logger.info("EXIT SIGNAL: Position %s R=%.6f near μ=%.6f "
                            "(tol=%.6f)",
                            pos.position_id, current_ratio, mean, tolerance)
                self._exit_position(pos, pair, num_ltp, den_ltp, mean)

    def _exit_position(self, pos: AMMPosition, pair: PairConfig,
                       num_ltp: float, den_ltp: float, exit_mean: float):
        """Close both legs with aggressive limit orders."""
        pos.status = "EXITING"

        if pos.direction == "SHORT_NUM":
            # Was: SELL num, BUY den -> Now: BUY num back, SELL den back
            num_side, den_side = "BUY", "SELL"
        else:
            # Was: BUY num, SELL den -> Now: SELL num, BUY den back
            num_side, den_side = "SELL", "BUY"

        # Aggressive pricing
        if num_side == "BUY":
            num_price = round(num_ltp + self.config.slippage, 2)
        else:
            num_price = round(num_ltp - self.config.slippage, 2)

        if den_side == "BUY":
            den_price = round(den_ltp + self.config.slippage, 2)
        else:
            den_price = round(den_ltp - self.config.slippage, 2)

        num_price = max(0.01, num_price)
        den_price = max(0.01, den_price)

        logger.info("EXITING %s: Position %s num=%s %d@%.2f den=%s %d@%.2f",
                     pos.direction, pos.position_id,
                     num_side, pos.num_qty, num_price,
                     den_side, pos.den_qty, den_price)

        num_oid = self.client.place_order(
            pair.numerator_ticker, num_side, pos.num_qty, num_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=f"AMM-{pos.position_id}-XNUM",
        )

        den_oid = self.client.place_order(
            pair.denominator_ticker, den_side, pos.den_qty, den_price,
            exchange=self.config.exchange,
            product=self.config.product,
            order_unique_id=f"AMM-{pos.position_id}-XDEN",
        )

        pos.num_exit_order_id = num_oid
        pos.den_exit_order_id = den_oid

        if num_oid:
            self.state.register_order(num_oid, pos.position_id)
        if den_oid:
            self.state.register_order(den_oid, pos.position_id)

        self.state.save()

    # ----- Order Polling & Fill Handling -----

    def _poll_orders(self) -> Optional[int]:
        """
        Poll XTS order book, process fills for entry/exit legs.

        Returns number of fills processed, or None on fetch error.
        """
        orders = self.client.get_orders()
        if orders is None:
            return None

        fills_processed = 0

        for order in orders:
            order_id = str(order['order_id'])
            status = order['status']
            filled_qty = order['filled_quantity']
            avg_price = order['average_price']

            # Cache key to avoid re-processing
            cache_key = f"{status}:{filled_qty}"
            if self._order_status_cache.get(order_id) == cache_key:
                continue
            self._order_status_cache[order_id] = cache_key

            # Find the position this order belongs to
            pos = self.state.get_position_by_order(order_id)
            if pos is None:
                continue

            # Process based on status
            if status in ('COMPLETE', 'PARTIAL'):
                filled = self._process_fill(pos, order_id, filled_qty, avg_price)
                if filled:
                    fills_processed += 1

            elif status in ('CANCELLED', 'REJECTED'):
                logger.warning("Order %s for position %s: %s - %s",
                               order_id, pos.position_id, status,
                               order.get('status_message', ''))

        return fills_processed

    def _process_fill(self, pos: AMMPosition, order_id: str,
                      filled_qty: int, avg_price: float) -> bool:
        """Process a fill event for an entry or exit leg."""
        changed = False

        # Determine which leg this order is
        if order_id == pos.num_entry_order_id:
            if filled_qty > pos.num_entry_filled:
                pos.num_entry_filled = filled_qty
                pos.num_entry_fill_price = avg_price
                logger.info("Position %s: NUM entry fill %d @ %.2f",
                            pos.position_id, filled_qty, avg_price)
                changed = True

        elif order_id == pos.den_entry_order_id:
            if filled_qty > pos.den_entry_filled:
                pos.den_entry_filled = filled_qty
                pos.den_entry_fill_price = avg_price
                logger.info("Position %s: DEN entry fill %d @ %.2f",
                            pos.position_id, filled_qty, avg_price)
                changed = True

        elif order_id == pos.num_exit_order_id:
            if filled_qty > pos.num_exit_filled:
                pos.num_exit_filled = filled_qty
                pos.num_exit_fill_price = avg_price
                logger.info("Position %s: NUM exit fill %d @ %.2f",
                            pos.position_id, filled_qty, avg_price)
                changed = True

        elif order_id == pos.den_exit_order_id:
            if filled_qty > pos.den_exit_filled:
                pos.den_exit_filled = filled_qty
                pos.den_exit_fill_price = avg_price
                logger.info("Position %s: DEN exit fill %d @ %.2f",
                            pos.position_id, filled_qty, avg_price)
                changed = True

        if not changed:
            return False

        # Check state transitions
        if pos.status == "ENTERING":
            # Transition to OPEN when both entry legs are completely filled
            if (pos.num_entry_filled >= pos.num_qty and
                    pos.den_entry_filled >= pos.den_qty):
                pos.status = "OPEN"
                logger.info("Position %s -> OPEN (both entry legs filled)",
                            pos.position_id)

        elif pos.status == "EXITING":
            # Transition to CLOSED when both exit legs are completely filled
            if (pos.num_exit_filled >= pos.num_qty and
                    pos.den_exit_filled >= pos.den_qty):
                # Compute PnL
                pnl = self._compute_pnl(pos)
                pos.realized_pnl = pnl
                logger.info("Position %s -> CLOSED PnL=%.2f",
                            pos.position_id, pnl)

                # Track in PnL system
                if self.pnl and self._pnl_session_id:
                    try:
                        pair = self.config.pairs[pos.pair_index]
                        self.pnl.record_trade(
                            session_id=self._pnl_session_id,
                            symbol=f"{pair.numerator_ticker}/{pair.denominator_ticker}",
                            side=pos.direction,
                            qty=pos.num_qty,
                            entry_price=pos.entry_ratio,
                            exit_price=(pos.num_exit_fill_price / pos.den_exit_fill_price
                                        if pos.den_exit_fill_price > 0 else 0),
                            pnl=pnl,
                        )
                    except Exception as e:
                        logger.debug("PnL tracking error: %s", e)

                self.state.close_position(pos.position_id)

        return True

    def _compute_pnl(self, pos: AMMPosition) -> float:
        """
        Compute realized PnL for a closed position.

        SHORT_NUM (sold num, bought den):
          num_pnl = (entry - exit) * qty  (profit if price fell)
          den_pnl = (exit - entry) * qty  (profit if price rose)

        LONG_NUM (bought num, sold den):
          num_pnl = (exit - entry) * qty
          den_pnl = (entry - exit) * qty
        """
        if pos.direction == "SHORT_NUM":
            num_pnl = (pos.num_entry_fill_price - pos.num_exit_fill_price) * pos.num_qty
            den_pnl = (pos.den_exit_fill_price - pos.den_entry_fill_price) * pos.den_qty
        else:  # LONG_NUM
            num_pnl = (pos.num_exit_fill_price - pos.num_entry_fill_price) * pos.num_qty
            den_pnl = (pos.den_entry_fill_price - pos.den_exit_fill_price) * pos.den_qty

        total = round(num_pnl + den_pnl, 2)
        logger.info("PnL for %s: num_pnl=%.2f den_pnl=%.2f total=%.2f",
                     pos.position_id, num_pnl, den_pnl, total)
        return total

    # ----- Reconciliation -----

    def _reconcile_orders(self):
        """Reconcile open positions with broker order book on startup."""
        if not self.state.open_positions:
            return

        logger.info("Reconciling %d open positions with broker...",
                     len(self.state.open_positions))

        orders = self.client.get_orders()
        if orders is None:
            logger.warning("Cannot reconcile: order book fetch failed")
            return

        order_map = {str(o['order_id']): o for o in orders}

        for pos in list(self.state.open_positions.values()):
            # Check entry orders
            for oid_attr, filled_attr, price_attr in [
                ('num_entry_order_id', 'num_entry_filled', 'num_entry_fill_price'),
                ('den_entry_order_id', 'den_entry_filled', 'den_entry_fill_price'),
            ]:
                oid = getattr(pos, oid_attr)
                if oid and oid in order_map:
                    o = order_map[oid]
                    setattr(pos, filled_attr, o['filled_quantity'])
                    if o['average_price'] > 0:
                        setattr(pos, price_attr, o['average_price'])

            # Check exit orders
            for oid_attr, filled_attr, price_attr in [
                ('num_exit_order_id', 'num_exit_filled', 'num_exit_fill_price'),
                ('den_exit_order_id', 'den_exit_filled', 'den_exit_fill_price'),
            ]:
                oid = getattr(pos, oid_attr)
                if oid and oid in order_map:
                    o = order_map[oid]
                    setattr(pos, filled_attr, o['filled_quantity'])
                    if o['average_price'] > 0:
                        setattr(pos, price_attr, o['average_price'])

            # Update status based on fills
            if pos.status == "ENTERING":
                if (pos.num_entry_filled >= pos.num_qty and
                        pos.den_entry_filled >= pos.den_qty):
                    pos.status = "OPEN"
                    logger.info("Reconcile: position %s -> OPEN", pos.position_id)

            elif pos.status == "EXITING":
                if (pos.num_exit_filled >= pos.num_qty and
                        pos.den_exit_filled >= pos.den_qty):
                    pnl = self._compute_pnl(pos)
                    pos.realized_pnl = pnl
                    self.state.close_position(pos.position_id)
                    logger.info("Reconcile: position %s -> CLOSED PnL=%.2f",
                                pos.position_id, pnl)

        self.state.save()
        logger.info("Reconciliation complete")

    # ----- Session Management -----

    def _refresh_xts_session(self):
        """Force refresh the XTS Interactive session."""
        try:
            if self.client.refresh_session():
                self._last_session_refresh = datetime.now()
                logger.info("XTS session refreshed successfully")
            else:
                logger.error("XTS session refresh failed")
        except Exception as e:
            logger.error("XTS session refresh error: %s", e)

    # ----- Shutdown -----

    def _shutdown_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        sig_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        logger.info("Received %s, shutting down...", sig_name)
        self.running = False

    def _shutdown(self):
        """Save state and disconnect."""
        logger.info("AMM engine shutting down...")
        self.state.save()
        if self.client:
            self.client.stop()
        logger.info("AMM engine stopped. PnL=%.2f, Trades=%d",
                     self.state.total_pnl, self.state.total_trades)
