"""
Order flow metrics computation engine for OrderFlow module.

Computes per-symbol real-time metrics:
- Trade delta (tick rule: price up = buy, price down = sell)
- Cumulative Volume Delta (CVD)
- Bid-ask imbalance (weighted across 5 depth levels)
- Stacked imbalance detection
- Absorption detection (large resting orders absorbing aggression)
- Large trade detection
- Delta divergence (price vs CVD divergence)
- Wyckoff phase detection (accumulation/markup/distribution/markdown)

No database dependency — operates on in-memory state and produces tuples
for batch insertion by the TickBuffer/DBManager.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SymbolState:
    """Per-symbol tracking state for metrics computation"""
    # Price
    last_price: float = 0.0
    prev_price: float = 0.0
    interval_prices: list = field(default_factory=list)

    # Delta tracking
    interval_delta: float = 0.0
    cumulative_delta: float = 0.0
    interval_buy_volume: int = 0
    interval_sell_volume: int = 0
    interval_volume: int = 0

    # VWAP
    vwap_cumulative_pv: float = 0.0  # price * volume
    vwap_cumulative_volume: int = 0

    # Large trade detection
    trade_quantities: deque = field(default_factory=lambda: deque(maxlen=200))
    large_trade_count: int = 0
    large_trade_volume: int = 0

    # Depth tracking (latest snapshot)
    latest_depth: dict = field(default_factory=dict)
    bid_ask_imbalance_l1: float = 0.0
    bid_ask_imbalance_l5: float = 0.0
    stacked_imbalance_buy: int = 0
    stacked_imbalance_sell: int = 0

    # Absorption tracking
    prev_total_bid_qty: int = 0
    prev_total_ask_qty: int = 0
    absorption_buy: bool = False
    absorption_sell: bool = False

    # Phase detection history
    delta_history: deque = field(default_factory=lambda: deque(maxlen=60))
    cvd_history: deque = field(default_factory=lambda: deque(maxlen=60))
    price_history: deque = field(default_factory=lambda: deque(maxlen=60))
    imbalance_history: deque = field(default_factory=lambda: deque(maxlen=60))

    # Current phase
    phase: str = "unknown"
    phase_confidence: float = 0.0

    # Interval timing
    interval_start_time: float = 0.0
    tick_count: int = 0


class MetricsEngine:
    """Computes real-time order flow metrics per symbol"""

    def __init__(self, config: Dict):
        """
        Args:
            config: orderflow_config.json loaded as dict
        """
        self.interval_seconds = config.get("metrics_interval_seconds", 10)
        self.large_trade_multiplier = config.get("large_trade_multiplier", 5.0)
        self.imbalance_ratio_threshold = config.get("imbalance_ratio_threshold", 3.0)
        self.depth_weights = config.get("depth_weights", [1.0, 0.8, 0.6, 0.4, 0.2])

        phase_config = config.get("phase_detection", {})
        self.cvd_lookback = phase_config.get("cvd_lookback_periods", 30)
        self.price_lookback = phase_config.get("price_lookback_periods", 30)
        self.absorption_volume_threshold = phase_config.get("absorption_volume_threshold", 2.0)
        self.divergence_threshold = phase_config.get("delta_divergence_threshold", 0.3)
        self.min_confidence = phase_config.get("min_confidence", 0.4)

        # Per-symbol state
        self._states: Dict[str, SymbolState] = {}

        # Pending metrics ready for DB flush
        self._pending_metrics: List[Tuple] = []

    def _get_state(self, symbol: str) -> SymbolState:
        """Get or create per-symbol state"""
        if symbol not in self._states:
            self._states[symbol] = SymbolState(interval_start_time=time.time())
        return self._states[symbol]

    def process_tick(self, tick: Dict, symbol: str):
        """Process a single FULL-mode tick and update symbol state.

        Args:
            tick: KiteTicker FULL mode tick dict
            symbol: Trading symbol
        """
        state = self._get_state(symbol)
        price = tick.get("last_price", 0)
        qty = tick.get("last_traded_quantity", 0)

        if price <= 0:
            return

        # ── Tick Rule: classify as buy or sell ──
        if state.prev_price > 0:
            if price > state.prev_price:
                # Uptick → buyer-initiated
                state.interval_buy_volume += qty
                state.interval_delta += qty
            elif price < state.prev_price:
                # Downtick → seller-initiated
                state.interval_sell_volume += qty
                state.interval_delta -= qty
            else:
                # No change → use previous classification (split 50/50)
                half = qty // 2
                state.interval_buy_volume += half
                state.interval_sell_volume += (qty - half)

        state.prev_price = state.last_price
        state.last_price = price
        state.interval_prices.append(price)
        state.interval_volume += qty
        state.tick_count += 1

        # VWAP accumulation
        state.vwap_cumulative_pv += price * qty
        state.vwap_cumulative_volume += qty

        # Large trade detection
        state.trade_quantities.append(qty)
        if len(state.trade_quantities) > 20:
            avg_qty = sum(state.trade_quantities) / len(state.trade_quantities)
            if avg_qty > 0 and qty > avg_qty * self.large_trade_multiplier:
                state.large_trade_count += 1
                state.large_trade_volume += qty

        # ── Process depth data ──
        depth = tick.get("depth", {})
        if depth:
            self._process_depth(state, depth, tick)

        # ── Check interval boundary ──
        elapsed = time.time() - state.interval_start_time
        if elapsed >= self.interval_seconds:
            self._compute_and_emit(symbol, state)

    def _process_depth(self, state: SymbolState, depth: Dict, tick: Dict):
        """Process depth data for imbalance and absorption metrics"""
        buy_levels = depth.get("buy", [])
        sell_levels = depth.get("sell", [])

        if not buy_levels or not sell_levels:
            return

        state.latest_depth = depth

        # ── L1 imbalance (top of book) ──
        bid_qty_l1 = buy_levels[0].get("quantity", 0)
        ask_qty_l1 = sell_levels[0].get("quantity", 0)
        total_l1 = bid_qty_l1 + ask_qty_l1
        state.bid_ask_imbalance_l1 = (
            (bid_qty_l1 - ask_qty_l1) / total_l1 if total_l1 > 0 else 0
        )

        # ── L5 weighted imbalance ──
        weighted_bid = 0.0
        weighted_ask = 0.0
        for i, weight in enumerate(self.depth_weights):
            if i < len(buy_levels):
                weighted_bid += buy_levels[i].get("quantity", 0) * weight
            if i < len(sell_levels):
                weighted_ask += sell_levels[i].get("quantity", 0) * weight

        total_weighted = weighted_bid + weighted_ask
        state.bid_ask_imbalance_l5 = (
            (weighted_bid - weighted_ask) / total_weighted if total_weighted > 0 else 0
        )

        # ── Stacked imbalance: consecutive levels where ratio > threshold ──
        stacked_buy = 0
        stacked_sell = 0
        for i in range(min(len(buy_levels), len(sell_levels))):
            bid_q = buy_levels[i].get("quantity", 0)
            ask_q = sell_levels[i].get("quantity", 0)
            if ask_q > 0 and bid_q / ask_q >= self.imbalance_ratio_threshold:
                stacked_buy += 1
            elif bid_q > 0 and ask_q / bid_q >= self.imbalance_ratio_threshold:
                stacked_sell += 1
            else:
                break  # Must be consecutive
        state.stacked_imbalance_buy = stacked_buy
        state.stacked_imbalance_sell = stacked_sell

        # ── Absorption detection ──
        total_bid_qty = tick.get("total_buy_quantity", 0)
        total_ask_qty = tick.get("total_sell_quantity", 0)

        # Buy absorption: strong selling (negative delta) but bid qty holds/increases
        if (state.interval_delta < 0 and state.prev_total_bid_qty > 0 and
                total_bid_qty >= state.prev_total_bid_qty * 0.95):
            state.absorption_buy = True

        # Sell absorption: strong buying (positive delta) but ask qty holds/increases
        if (state.interval_delta > 0 and state.prev_total_ask_qty > 0 and
                total_ask_qty >= state.prev_total_ask_qty * 0.95):
            state.absorption_sell = True

        state.prev_total_bid_qty = total_bid_qty
        state.prev_total_ask_qty = total_ask_qty

    def _compute_and_emit(self, symbol: str, state: SymbolState):
        """Compute final metrics for the interval and create a DB record"""
        if state.tick_count == 0:
            state.interval_start_time = time.time()
            return

        # Finalize CVD
        state.cumulative_delta += state.interval_delta

        # VWAP
        vwap = (state.vwap_cumulative_pv / state.vwap_cumulative_volume
                if state.vwap_cumulative_volume > 0 else state.last_price)

        # OHLC for interval
        prices = state.interval_prices
        price_open = prices[0] if prices else state.last_price
        price_high = max(prices) if prices else state.last_price
        price_low = min(prices) if prices else state.last_price
        price_close = prices[-1] if prices else state.last_price

        # Delta divergence check
        delta_divergence = self._check_divergence(state)

        # Update history for phase detection
        state.delta_history.append(state.interval_delta)
        state.cvd_history.append(state.cumulative_delta)
        state.price_history.append(price_close)
        state.imbalance_history.append(state.bid_ask_imbalance_l5)

        # Detect phase
        phase, confidence = self._detect_phase(state)
        state.phase = phase
        state.phase_confidence = confidence

        # Build the metrics tuple
        metrics_record = (
            datetime.now(timezone.utc),          # ts
            symbol,                               # symbol
            self.interval_seconds,                # interval_seconds
            state.interval_delta,                 # trade_delta
            state.cumulative_delta,               # cumulative_delta
            delta_divergence,                     # delta_divergence
            phase,                                # phase
            confidence,                           # phase_confidence
            state.bid_ask_imbalance_l1,           # bid_ask_imbalance_l1
            state.bid_ask_imbalance_l5,           # bid_ask_imbalance_l5
            state.stacked_imbalance_buy,          # stacked_imbalance_buy
            state.stacked_imbalance_sell,         # stacked_imbalance_sell
            state.interval_volume,                # interval_volume
            state.interval_buy_volume,            # interval_buy_volume
            state.interval_sell_volume,           # interval_sell_volume
            round(vwap, 2),                       # vwap
            state.large_trade_count,              # large_trade_count
            state.large_trade_volume,             # large_trade_volume
            state.absorption_buy,                 # absorption_buy
            state.absorption_sell,                # absorption_sell
            round(price_open, 2),                 # price_open
            round(price_high, 2),                 # price_high
            round(price_low, 2),                  # price_low
            round(price_close, 2),                # price_close
        )

        self._pending_metrics.append(metrics_record)

        logger.debug(f"{symbol}: delta={state.interval_delta:+.0f} "
                     f"cvd={state.cumulative_delta:+.0f} phase={phase}({confidence:.2f}) "
                     f"vol={state.interval_volume} large={state.large_trade_count}")

        # Reset interval state (preserve cumulative values)
        state.interval_delta = 0.0
        state.interval_buy_volume = 0
        state.interval_sell_volume = 0
        state.interval_volume = 0
        state.interval_prices.clear()
        state.large_trade_count = 0
        state.large_trade_volume = 0
        state.absorption_buy = False
        state.absorption_sell = False
        state.tick_count = 0
        state.interval_start_time = time.time()

    def _check_divergence(self, state: SymbolState) -> bool:
        """Check for delta-price divergence.

        Returns True if price direction and CVD direction disagree.
        """
        if len(state.price_history) < 5 or len(state.cvd_history) < 5:
            return False

        recent_prices = list(state.price_history)[-5:]
        recent_cvd = list(state.cvd_history)[-5:]

        price_change = recent_prices[-1] - recent_prices[0]
        cvd_change = recent_cvd[-1] - recent_cvd[0]

        # Normalize
        price_range = max(recent_prices) - min(recent_prices)
        if price_range == 0:
            return False

        norm_price = price_change / price_range
        cvd_range = max(recent_cvd) - min(recent_cvd) if max(recent_cvd) != min(recent_cvd) else 1
        norm_cvd = cvd_change / cvd_range

        # Divergence: price up but CVD down (or vice versa)
        if abs(norm_price) > self.divergence_threshold and abs(norm_cvd) > self.divergence_threshold:
            if (norm_price > 0 and norm_cvd < 0) or (norm_price < 0 and norm_cvd > 0):
                return True

        return False

    def _detect_phase(self, state: SymbolState) -> Tuple[str, float]:
        """Detect current Wyckoff-style market phase.

        Combines multiple signals to determine:
        - accumulation: price flat + positive CVD trend + buy absorption
        - markup: price rising + strong positive delta + CVD rising
        - distribution: price at highs + CVD diverging + sell absorption
        - markdown: price falling + strong negative delta + CVD falling

        Returns:
            (phase_name, confidence) where confidence is 0.0 to 1.0
        """
        if len(state.price_history) < 10 or len(state.cvd_history) < 10:
            return "unknown", 0.0

        prices = list(state.price_history)
        cvds = list(state.cvd_history)
        deltas = list(state.delta_history)
        imbalances = list(state.imbalance_history)

        # Compute trends (simple linear: end - start over lookback)
        lookback = min(self.cvd_lookback, len(prices))
        price_trend = (prices[-1] - prices[-lookback]) / prices[-lookback] if prices[-lookback] != 0 else 0
        cvd_trend = cvds[-1] - cvds[-lookback]

        # Price volatility (range relative to price)
        recent_prices = prices[-lookback:]
        price_range = (max(recent_prices) - min(recent_prices)) / prices[-1] if prices[-1] > 0 else 0

        # Average recent delta
        recent_deltas = deltas[-lookback:] if len(deltas) >= lookback else deltas
        avg_delta = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0

        # Average recent imbalance
        recent_imbalances = imbalances[-lookback:] if len(imbalances) >= lookback else imbalances
        avg_imbalance = sum(recent_imbalances) / len(recent_imbalances) if recent_imbalances else 0

        scores = {
            "accumulation": 0.0,
            "markup": 0.0,
            "distribution": 0.0,
            "markdown": 0.0,
        }

        # ── Accumulation signals ──
        # Price relatively flat (low range)
        if price_range < 0.005:  # < 0.5% range
            scores["accumulation"] += 0.25
        # Positive CVD trend (hidden buying)
        if cvd_trend > 0:
            scores["accumulation"] += 0.25
        # Buy absorption detected
        if state.absorption_buy:
            scores["accumulation"] += 0.25
        # Bid imbalance growing
        if avg_imbalance > 0.1:
            scores["accumulation"] += 0.25

        # ── Markup signals ──
        # Price rising
        if price_trend > 0.002:
            scores["markup"] += 0.25
        # Strong positive delta
        if avg_delta > 0:
            scores["markup"] += 0.25
        # CVD rising in sync with price
        if cvd_trend > 0 and price_trend > 0:
            scores["markup"] += 0.25
        # Stacked buy imbalance
        if state.stacked_imbalance_buy >= 2:
            scores["markup"] += 0.25

        # ── Distribution signals ──
        # Price at highs (near top of range)
        if len(recent_prices) > 1:
            price_position = (prices[-1] - min(recent_prices)) / (max(recent_prices) - min(recent_prices)) if max(recent_prices) != min(recent_prices) else 0.5
            if price_position > 0.8:
                scores["distribution"] += 0.2
        # CVD diverging (price up, CVD flattening/down)
        if price_trend > 0 and cvd_trend <= 0:
            scores["distribution"] += 0.3
        # Sell absorption
        if state.absorption_sell:
            scores["distribution"] += 0.25
        # Ask imbalance growing
        if avg_imbalance < -0.1:
            scores["distribution"] += 0.25

        # ── Markdown signals ──
        # Price falling
        if price_trend < -0.002:
            scores["markdown"] += 0.25
        # Strong negative delta
        if avg_delta < 0:
            scores["markdown"] += 0.25
        # CVD falling
        if cvd_trend < 0 and price_trend < 0:
            scores["markdown"] += 0.25
        # Stacked sell imbalance
        if state.stacked_imbalance_sell >= 2:
            scores["markdown"] += 0.25

        # Select highest scoring phase
        best_phase = max(scores, key=scores.get)
        best_score = scores[best_phase]

        if best_score < self.min_confidence:
            return "unknown", best_score

        return best_phase, round(best_score, 3)

    def drain_metrics(self) -> List[Tuple]:
        """Drain pending metrics records for DB insertion.

        Returns:
            List of metric tuples ready for batch insert
        """
        metrics = self._pending_metrics[:]
        self._pending_metrics.clear()
        return metrics

    def get_symbol_state(self, symbol: str) -> Optional[Dict]:
        """Get current state snapshot for a symbol (for dashboards/debugging)"""
        state = self._states.get(symbol)
        if not state:
            return None

        return {
            "symbol": symbol,
            "last_price": state.last_price,
            "cumulative_delta": state.cumulative_delta,
            "phase": state.phase,
            "phase_confidence": state.phase_confidence,
            "bid_ask_imbalance_l1": state.bid_ask_imbalance_l1,
            "bid_ask_imbalance_l5": state.bid_ask_imbalance_l5,
            "stacked_buy": state.stacked_imbalance_buy,
            "stacked_sell": state.stacked_imbalance_sell,
            "absorption_buy": state.absorption_buy,
            "absorption_sell": state.absorption_sell,
            "interval_delta": state.interval_delta,
            "interval_volume": state.interval_volume,
            "tick_count": state.tick_count,
        }

    def get_all_states(self) -> Dict[str, Dict]:
        """Get state snapshots for all tracked symbols"""
        return {
            symbol: self.get_symbol_state(symbol)
            for symbol in self._states
        }

    def reset_daily(self):
        """Reset all cumulative state for a new trading day"""
        for symbol, state in self._states.items():
            state.cumulative_delta = 0.0
            state.vwap_cumulative_pv = 0.0
            state.vwap_cumulative_volume = 0
            state.delta_history.clear()
            state.cvd_history.clear()
            state.price_history.clear()
            state.imbalance_history.clear()
            state.phase = "unknown"
            state.phase_confidence = 0.0
            logger.info(f"Reset daily state for {symbol}")
