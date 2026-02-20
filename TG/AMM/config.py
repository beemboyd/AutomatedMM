"""
AMM Configuration — pair parameters, credentials, and rolling stats settings.

Handles XTS Interactive credentials for the separate 01MU07 account
and XTS Market Data credentials for real-time quotes.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
CONFIG_FILE = os.path.join(STATE_DIR, 'amm_config.json')


@dataclass
class PairConfig:
    """Per-pair configuration for ratio mean-reversion."""
    numerator_ticker: str
    denominator_ticker: str
    entry_sd: float = 1.0
    numerator_trade_pct: float = 100.0
    denominator_trade_pct: float = 100.0
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            'numerator_ticker': self.numerator_ticker,
            'denominator_ticker': self.denominator_ticker,
            'entry_sd': self.entry_sd,
            'numerator_trade_pct': self.numerator_trade_pct,
            'denominator_trade_pct': self.denominator_trade_pct,
            'enabled': self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'PairConfig':
        return cls(
            numerator_ticker=d['numerator_ticker'],
            denominator_ticker=d['denominator_ticker'],
            entry_sd=d.get('entry_sd', 1.0),
            numerator_trade_pct=d.get('numerator_trade_pct', 100.0),
            denominator_trade_pct=d.get('denominator_trade_pct', 100.0),
            enabled=d.get('enabled', True),
        )


DEFAULT_PAIRS = [
    PairConfig(numerator_ticker="TATAGOLD", denominator_ticker="SPCENET",
               entry_sd=1.0, numerator_trade_pct=100, denominator_trade_pct=100),
    PairConfig(numerator_ticker="YESBANK", denominator_ticker="SPCENET",
               entry_sd=1.0, numerator_trade_pct=100, denominator_trade_pct=100),
]


@dataclass
class AMMConfig:
    """
    AMM stat-arb bot configuration.

    Ratio mechanics:
    - For each pair, compute R = numerator_LTP / denominator_LTP every sample_interval
    - After warmup_samples collected, compute rolling mean and SD
    - Enter pair trade when |z-score| > entry_sd
    - Exit when ratio reverts to mean (within tolerance)
    - Stacking up to max_positions_per_pair
    """
    pairs: List[PairConfig] = field(default_factory=lambda: [p for p in DEFAULT_PAIRS])

    # Sizing
    base_qty: int = 10000

    # Rolling stats
    rolling_window: int = 30
    sample_interval: int = 60
    warmup_samples: int = 30

    # Position limits
    max_positions_per_pair: int = 3

    # Exit
    mean_reversion_tolerance: float = 0.002

    # Broker
    exchange: str = "NSE"
    product: str = "CNC"
    poll_interval: float = 2.0
    slippage: float = 0.05

    # XTS credentials (01MU07)
    interactive_key: str = "YOUR_XTS_INTERACTIVE_KEY"
    interactive_secret: str = "YOUR_XTS_INTERACTIVE_SECRET"
    marketdata_key: str = "YOUR_XTS_MARKETDATA_KEY"
    marketdata_secret: str = "YOUR_XTS_MARKETDATA_SECRET"
    xts_root: str = _DEFAULT_XTS_ROOT

    def get_all_symbols(self) -> List[str]:
        """Return unique list of all ticker symbols across all pairs."""
        symbols = set()
        for pair in self.pairs:
            symbols.add(pair.numerator_ticker)
            symbols.add(pair.denominator_ticker)
        return sorted(symbols)

    def to_dict(self) -> dict:
        return {
            'pairs': [p.to_dict() for p in self.pairs],
            'base_qty': self.base_qty,
            'rolling_window': self.rolling_window,
            'sample_interval': self.sample_interval,
            'warmup_samples': self.warmup_samples,
            'max_positions_per_pair': self.max_positions_per_pair,
            'mean_reversion_tolerance': self.mean_reversion_tolerance,
            'exchange': self.exchange,
            'product': self.product,
            'poll_interval': self.poll_interval,
            'slippage': self.slippage,
            'interactive_key': self.interactive_key,
            'interactive_secret': self.interactive_secret,
            'marketdata_key': self.marketdata_key,
            'marketdata_secret': self.marketdata_secret,
            'xts_root': self.xts_root,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'AMMConfig':
        pairs = [PairConfig.from_dict(p) for p in d.get('pairs', [])]
        if not pairs:
            pairs = [p for p in DEFAULT_PAIRS]
        return cls(
            pairs=pairs,
            base_qty=d.get('base_qty', 10000),
            rolling_window=d.get('rolling_window', 30),
            sample_interval=d.get('sample_interval', 60),
            warmup_samples=d.get('warmup_samples', 30),
            max_positions_per_pair=d.get('max_positions_per_pair', 3),
            mean_reversion_tolerance=d.get('mean_reversion_tolerance', 0.002),
            exchange=d.get('exchange', 'NSE'),
            product=d.get('product', 'CNC'),
            poll_interval=d.get('poll_interval', 2.0),
            slippage=d.get('slippage', 0.05),
            interactive_key=d.get('interactive_key', 'YOUR_XTS_INTERACTIVE_KEY'),
            interactive_secret=d.get('interactive_secret', 'YOUR_XTS_INTERACTIVE_SECRET'),
            marketdata_key=d.get('marketdata_key', 'YOUR_XTS_MARKETDATA_KEY'),
            marketdata_secret=d.get('marketdata_secret', 'YOUR_XTS_MARKETDATA_SECRET'),
            xts_root=d.get('xts_root', _DEFAULT_XTS_ROOT),
        )

    @classmethod
    def load_from_file(cls, path: str = None) -> 'AMMConfig':
        """Load config from JSON file, falling back to defaults."""
        path = path or CONFIG_FILE
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return cls.from_dict(json.load(f))
            except Exception as e:
                logger.error("Failed to load config from %s: %s", path, e)
        return cls()

    def save_to_file(self, path: str = None):
        """Save config to JSON with atomic write."""
        path = path or CONFIG_FILE
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)

    def print_summary(self):
        """Print config summary for verification."""
        print(f"\n{'='*60}")
        print(f"  AMM STAT-ARB BOT CONFIGURATION")
        print(f"{'='*60}")
        print(f"  Base Qty         : {self.base_qty}")
        print(f"  Rolling Window   : {self.rolling_window}")
        print(f"  Sample Interval  : {self.sample_interval}s")
        print(f"  Warmup Samples   : {self.warmup_samples}")
        print(f"  Max Positions    : {self.max_positions_per_pair} per pair")
        print(f"  Mean Rev Tol     : {self.mean_reversion_tolerance}")
        print(f"  Product          : {self.product}")
        print(f"  Poll Interval    : {self.poll_interval}s")
        print(f"  Slippage         : {self.slippage}")
        print(f"  Broker           : XTS Interactive + XTS Market Data (01MU07)")
        print(f"{'='*60}")
        for i, pair in enumerate(self.pairs):
            status = "ENABLED" if pair.enabled else "DISABLED"
            print(f"\n  Pair {i}: {pair.numerator_ticker} / {pair.denominator_ticker} [{status}]")
            print(f"    Entry SD           : {pair.entry_sd}")
            print(f"    Numerator Trade %  : {pair.numerator_trade_pct}")
            print(f"    Denominator Trade %: {pair.denominator_trade_pct}")
            num_qty = max(1, round(self.base_qty * pair.numerator_trade_pct / 100))
            den_qty = max(1, round(self.base_qty * pair.denominator_trade_pct / 100))
            print(f"    Effective Num Qty  : {num_qty}")
            print(f"    Effective Den Qty  : {den_qty}")
        print(f"{'='*60}\n")
