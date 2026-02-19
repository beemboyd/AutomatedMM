"""
AMM State Persistence — RatioSample, AMMPosition, AMMState.

Manages ratio timeseries per pair, open/closed positions, and
order-to-position mapping. State is persisted to JSON with atomic writes.
"""

import json
import os
import uuid
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
_STATE_FILE = os.path.join(_STATE_DIR, 'amm_state.json')


@dataclass
class RatioSample:
    """A single ratio data point for a pair."""
    timestamp: str
    num_price: float
    den_price: float
    ratio: float

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'num_price': self.num_price,
            'den_price': self.den_price,
            'ratio': self.ratio,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'RatioSample':
        return cls(
            timestamp=d['timestamp'],
            num_price=d['num_price'],
            den_price=d['den_price'],
            ratio=d['ratio'],
        )


@dataclass
class AMMPosition:
    """An active or closed pair trade position."""
    position_id: str
    pair_index: int
    direction: str              # "LONG_NUM" or "SHORT_NUM"

    # Entry context
    entry_time: str
    entry_ratio: float
    entry_mean: float
    entry_sd: float
    num_entry_price: float
    den_entry_price: float
    num_qty: int
    den_qty: int

    # Order tracking
    num_entry_order_id: Optional[str] = None
    den_entry_order_id: Optional[str] = None
    num_exit_order_id: Optional[str] = None
    den_exit_order_id: Optional[str] = None

    # Fill tracking
    num_entry_filled: int = 0
    den_entry_filled: int = 0
    num_exit_filled: int = 0
    den_exit_filled: int = 0
    num_entry_fill_price: float = 0.0
    den_entry_fill_price: float = 0.0
    num_exit_fill_price: float = 0.0
    den_exit_fill_price: float = 0.0

    # Status: ENTERING -> OPEN -> EXITING -> CLOSED
    status: str = "ENTERING"
    realized_pnl: float = 0.0
    closed_at: Optional[str] = None

    @staticmethod
    def create(pair_index: int, direction: str, entry_ratio: float,
               entry_mean: float, entry_sd: float,
               num_entry_price: float, den_entry_price: float,
               num_qty: int, den_qty: int) -> 'AMMPosition':
        return AMMPosition(
            position_id=uuid.uuid4().hex[:8],
            pair_index=pair_index,
            direction=direction,
            entry_time=datetime.now().isoformat(),
            entry_ratio=entry_ratio,
            entry_mean=entry_mean,
            entry_sd=entry_sd,
            num_entry_price=num_entry_price,
            den_entry_price=den_entry_price,
            num_qty=num_qty,
            den_qty=den_qty,
        )

    def to_dict(self) -> dict:
        return {
            'position_id': self.position_id,
            'pair_index': self.pair_index,
            'direction': self.direction,
            'entry_time': self.entry_time,
            'entry_ratio': self.entry_ratio,
            'entry_mean': self.entry_mean,
            'entry_sd': self.entry_sd,
            'num_entry_price': self.num_entry_price,
            'den_entry_price': self.den_entry_price,
            'num_qty': self.num_qty,
            'den_qty': self.den_qty,
            'num_entry_order_id': self.num_entry_order_id,
            'den_entry_order_id': self.den_entry_order_id,
            'num_exit_order_id': self.num_exit_order_id,
            'den_exit_order_id': self.den_exit_order_id,
            'num_entry_filled': self.num_entry_filled,
            'den_entry_filled': self.den_entry_filled,
            'num_exit_filled': self.num_exit_filled,
            'den_exit_filled': self.den_exit_filled,
            'num_entry_fill_price': self.num_entry_fill_price,
            'den_entry_fill_price': self.den_entry_fill_price,
            'num_exit_fill_price': self.num_exit_fill_price,
            'den_exit_fill_price': self.den_exit_fill_price,
            'status': self.status,
            'realized_pnl': self.realized_pnl,
            'closed_at': self.closed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'AMMPosition':
        return cls(
            position_id=d['position_id'],
            pair_index=d['pair_index'],
            direction=d['direction'],
            entry_time=d['entry_time'],
            entry_ratio=d['entry_ratio'],
            entry_mean=d['entry_mean'],
            entry_sd=d['entry_sd'],
            num_entry_price=d['num_entry_price'],
            den_entry_price=d['den_entry_price'],
            num_qty=d['num_qty'],
            den_qty=d['den_qty'],
            num_entry_order_id=d.get('num_entry_order_id'),
            den_entry_order_id=d.get('den_entry_order_id'),
            num_exit_order_id=d.get('num_exit_order_id'),
            den_exit_order_id=d.get('den_exit_order_id'),
            num_entry_filled=d.get('num_entry_filled', 0),
            den_entry_filled=d.get('den_entry_filled', 0),
            num_exit_filled=d.get('num_exit_filled', 0),
            den_exit_filled=d.get('den_exit_filled', 0),
            num_entry_fill_price=d.get('num_entry_fill_price', 0.0),
            den_entry_fill_price=d.get('den_entry_fill_price', 0.0),
            num_exit_fill_price=d.get('num_exit_fill_price', 0.0),
            den_exit_fill_price=d.get('den_exit_fill_price', 0.0),
            status=d.get('status', 'ENTERING'),
            realized_pnl=d.get('realized_pnl', 0.0),
            closed_at=d.get('closed_at'),
        )


class AMMState:
    """
    Manages AMM trading state with JSON persistence.

    Tracks ratio timeseries per pair, open/closed positions,
    and order-to-position mapping.
    """

    def __init__(self, rolling_window: int = 30, state_dir: str = None):
        if state_dir is None:
            state_dir = _STATE_DIR
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = os.path.join(state_dir, 'amm_state.json')
        self.rolling_window = rolling_window

        # Per-pair ratio timeseries: pair_index -> list of RatioSample
        self.ratio_series: Dict[int, List[RatioSample]] = {}

        # Active positions
        self.open_positions: Dict[str, AMMPosition] = {}

        # Closed positions (last 200)
        self.closed_positions: List[dict] = []

        # Order -> position mapping
        self.order_to_position: Dict[str, str] = {}

        # Stats
        self.total_pnl: float = 0.0
        self.total_trades: int = 0

    def add_sample(self, pair_index: int, sample: RatioSample):
        """Add a ratio sample, trimming to rolling window size."""
        if pair_index not in self.ratio_series:
            self.ratio_series[pair_index] = []
        series = self.ratio_series[pair_index]
        series.append(sample)
        # Keep 2x rolling window for chart display, trim older
        max_keep = self.rolling_window * 2
        if len(series) > max_keep:
            self.ratio_series[pair_index] = series[-max_keep:]

    def get_rolling_stats(self, pair_index: int) -> Optional[Tuple[float, float]]:
        """
        Compute rolling mean and SD for a pair's ratio series.
        Returns (mean, sd) or None if not enough samples.
        """
        series = self.ratio_series.get(pair_index, [])
        if len(series) < self.rolling_window:
            return None
        recent = [s.ratio for s in series[-self.rolling_window:]]
        mean = statistics.mean(recent)
        sd = statistics.stdev(recent) if len(recent) > 1 else 0.0
        return (mean, sd)

    def active_count(self, pair_index: int) -> int:
        """Count open (non-CLOSED) positions for a pair."""
        return sum(1 for p in self.open_positions.values()
                   if p.pair_index == pair_index and p.status != 'CLOSED')

    def register_position(self, pos: AMMPosition):
        """Register a new position and its entry orders."""
        self.open_positions[pos.position_id] = pos
        if pos.num_entry_order_id:
            self.order_to_position[pos.num_entry_order_id] = pos.position_id
        if pos.den_entry_order_id:
            self.order_to_position[pos.den_entry_order_id] = pos.position_id

    def register_order(self, order_id: str, position_id: str):
        """Map an order ID to a position ID (used for exit orders)."""
        self.order_to_position[str(order_id)] = position_id

    def get_position_by_order(self, order_id: str) -> Optional[AMMPosition]:
        """Look up which position an order belongs to."""
        pid = self.order_to_position.get(str(order_id))
        if pid:
            return self.open_positions.get(pid)
        return None

    def close_position(self, position_id: str):
        """Move a position from open to closed, accumulate PnL."""
        if position_id not in self.open_positions:
            logger.warning("Attempted to close unknown position: %s", position_id)
            return

        pos = self.open_positions.pop(position_id)
        pos.status = "CLOSED"
        pos.closed_at = datetime.now().isoformat()
        self.total_pnl += pos.realized_pnl
        self.total_trades += 1
        self.closed_positions.append(pos.to_dict())

        # Trim to last 200
        if len(self.closed_positions) > 200:
            self.closed_positions = self.closed_positions[-200:]

        logger.info("Position %s closed. PnL=%.2f, Total PnL=%.2f, Trades=%d",
                     position_id, pos.realized_pnl, self.total_pnl, self.total_trades)

    def save(self):
        """Persist state to JSON with atomic write."""
        state = {
            'rolling_window': self.rolling_window,
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'last_updated': datetime.now().isoformat(),
            'ratio_series': {
                str(k): [s.to_dict() for s in v]
                for k, v in self.ratio_series.items()
            },
            'open_positions': {
                pid: p.to_dict() for pid, p in self.open_positions.items()
            },
            'closed_positions': self.closed_positions[-200:],
            'order_to_position': self.order_to_position,
        }
        tmp = self.state_file + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_file)
        logger.debug("State saved: %d open, %d closed, PnL=%.2f",
                      len(self.open_positions), len(self.closed_positions),
                      self.total_pnl)

    def load(self) -> bool:
        """Load state from JSON. Returns True if state was loaded."""
        if not os.path.exists(self.state_file):
            logger.info("No existing AMM state file")
            return False
        try:
            with open(self.state_file) as f:
                state = json.load(f)

            self.rolling_window = state.get('rolling_window', self.rolling_window)
            self.total_pnl = state.get('total_pnl', 0.0)
            self.total_trades = state.get('total_trades', 0)

            self.ratio_series = {}
            for k, v in state.get('ratio_series', {}).items():
                self.ratio_series[int(k)] = [RatioSample.from_dict(s) for s in v]

            self.open_positions = {
                pid: AMMPosition.from_dict(d)
                for pid, d in state.get('open_positions', {}).items()
            }
            self.closed_positions = state.get('closed_positions', [])
            self.order_to_position = state.get('order_to_position', {})

            logger.info("AMM state loaded: %d open, PnL=%.2f, trades=%d, "
                         "ratio series for %d pairs",
                         len(self.open_positions), self.total_pnl,
                         self.total_trades, len(self.ratio_series))
            return True
        except Exception as e:
            logger.error("Failed to load AMM state: %s", e)
            return False

    def print_summary(self):
        """Print current state summary."""
        entering = sum(1 for p in self.open_positions.values() if p.status == 'ENTERING')
        open_ct = sum(1 for p in self.open_positions.values() if p.status == 'OPEN')
        exiting = sum(1 for p in self.open_positions.values() if p.status == 'EXITING')

        print(f"\n  AMM STATE")
        print(f"  PnL: {self.total_pnl:.2f}  |  Trades: {self.total_trades}")
        print(f"  Positions: {entering} entering, {open_ct} open, {exiting} exiting")
        for pi, series in sorted(self.ratio_series.items()):
            stats = self.get_rolling_stats(pi)
            if stats:
                mean, sd = stats
                last_ratio = series[-1].ratio if series else 0
                z = (last_ratio - mean) / sd if sd > 0 else 0
                print(f"  Pair {pi}: {len(series)} samples, "
                      f"μ={mean:.6f}, σ={sd:.6f}, R={last_ratio:.6f}, z={z:.2f}")
            else:
                print(f"  Pair {pi}: {len(series)} samples (warmup)")
