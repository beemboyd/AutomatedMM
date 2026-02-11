"""
Grid Trading Bot Configuration

Handles XTS (Symphony Fintech / Findoc) credentials and
grid-specific parameters from CLI args or defaults.

Two sets of XTS credentials required:
  - Interactive (trading): for order placement/cancellation
  - Market Data: for LTP quotes and instrument search
"""

import os
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default XTS test credentials
_DEFAULT_XTS_ROOT = 'https://developers.symphonyfintech.in'


@dataclass
class SubsetConfig:
    """
    Configuration for a single grid subset/band.

    Each successive subset doubles the grid spacing and target,
    creating a geometric grid that reduces adverse selection at deeper levels.

    Example with base_grid_space=0.01, base_target=0.02:
      Subset 0: space=0.01, target=0.02, distance=0.01, qty=300
      Subset 1: space=0.02, target=0.04, distance=0.03, qty=300
      Subset 2: space=0.04, target=0.08, distance=0.07, qty=300
      Subset 3: space=0.08, target=0.16, distance=0.15, qty=100
    """
    index: int
    qty: int
    grid_space: float       # spacing for this subset (doubles each level)
    target: float           # target offset for this subset (doubles each level)
    distance_from_anchor: float  # cumulative distance from anchor price


@dataclass
class GridConfig:
    """
    Main grid trading configuration.

    Grid mechanics:
    - Anchor price P0 is the center of the grid
    - Buy levels are placed below P0, sell levels above
    - Total position is split into subsets of subset_qty shares
    - Each successive subset doubles grid_space and target
    - All buy targets converge to P0 + base_grid_space
    - All sell targets converge to P0 - base_grid_space
    - Effective spread = 2 * base_grid_space
    """
    symbol: str
    anchor_price: float

    # Grid parameters
    base_grid_space: float = 0.01   # 1 paisa
    base_target: float = 0.02       # 2 paisa
    total_qty: int = 1000
    subset_qty: int = 300

    # Broker parameters
    exchange: str = "NSE"
    product: str = "NRML"       # XTS: NRML for carry-forward, MIS for intraday

    # Operational parameters
    auto_reenter: bool = True       # re-place entry after target fills
    poll_interval: float = 2.0      # seconds between order status polls

    # XTS Interactive credentials (order placement)
    interactive_key: str = ""
    interactive_secret: str = ""

    # XTS Market Data credentials (quotes, instrument search)
    marketdata_key: str = ""
    marketdata_secret: str = ""

    # XTS API root URL
    xts_root: str = _DEFAULT_XTS_ROOT

    def compute_subsets(self) -> List[SubsetConfig]:
        """
        Compute grid subsets with geometric doubling.

        Returns list of SubsetConfig, one per grid band.
        Qty allocation: subset_qty per band, remainder in final band.
        """
        subsets = []
        remaining = self.total_qty
        cumulative = 0.0
        i = 0
        while remaining > 0:
            qty = min(self.subset_qty, remaining)
            space = round(self.base_grid_space * (2 ** i), 10)
            target = round(self.base_target * (2 ** i), 10)
            cumulative = round(cumulative + space, 10)
            subsets.append(SubsetConfig(
                index=i,
                qty=qty,
                grid_space=space,
                target=target,
                distance_from_anchor=cumulative,
            ))
            remaining -= qty
            i += 1
        return subsets

    @classmethod
    def from_args(cls, symbol: str, anchor_price: float, **overrides):
        """
        Create config from CLI args.

        Args:
            symbol: NSE trading symbol
            anchor_price: Grid center price
            **overrides: Override any default grid parameter
        """
        interactive_key = overrides.pop('interactive_key', '')
        interactive_secret = overrides.pop('interactive_secret', '')
        marketdata_key = overrides.pop('marketdata_key', '')
        marketdata_secret = overrides.pop('marketdata_secret', '')
        xts_root = overrides.pop('xts_root', _DEFAULT_XTS_ROOT)

        if not interactive_key or not interactive_secret:
            raise ValueError("Missing XTS Interactive credentials "
                             "(--interactive-key, --interactive-secret)")
        if not marketdata_key or not marketdata_secret:
            raise ValueError("Missing XTS Market Data credentials "
                             "(--marketdata-key, --marketdata-secret)")

        return cls(
            symbol=symbol,
            anchor_price=anchor_price,
            interactive_key=interactive_key,
            interactive_secret=interactive_secret,
            marketdata_key=marketdata_key,
            marketdata_secret=marketdata_secret,
            xts_root=xts_root,
            **overrides,
        )

    def print_grid_layout(self):
        """Print the grid layout for visual verification before trading."""
        subsets = self.compute_subsets()
        print(f"\n{'='*60}")
        print(f"  GRID CONFIGURATION — {self.symbol}")
        print(f"{'='*60}")
        print(f"  Anchor Price     : {self.anchor_price:.2f}")
        print(f"  Base Grid Space  : {self.base_grid_space} ({self.base_grid_space*100:.0f} paisa)")
        print(f"  Base Target      : {self.base_target} ({self.base_target*100:.0f} paisa)")
        print(f"  Total Qty        : {self.total_qty}")
        print(f"  Subset Qty       : {self.subset_qty}")
        print(f"  Subsets          : {len(subsets)}")
        print(f"  Product          : {self.product}")
        print(f"  Broker           : XTS ({self.xts_root})")
        print(f"  Auto Re-enter    : {self.auto_reenter}")
        print(f"{'='*60}")

        print(f"\n  BUY GRID (Bot A) — entries below anchor")
        print(f"  {'Subset':<8} {'Entry':>10} {'Target':>10} {'Qty':>6} {'Space':>8} {'TgtOff':>8}")
        print(f"  {'-'*52}")
        for s in subsets:
            entry = round(self.anchor_price - s.distance_from_anchor, 2)
            target = round(entry + s.target, 2)
            print(f"  {s.index:<8} {entry:>10.2f} {target:>10.2f} {s.qty:>6} {s.grid_space:>8.2f} {s.target:>8.2f}")

        print(f"\n  SELL GRID (Bot B) — entries above anchor")
        print(f"  {'Subset':<8} {'Entry':>10} {'Target':>10} {'Qty':>6} {'Space':>8} {'TgtOff':>8}")
        print(f"  {'-'*52}")
        for s in subsets:
            entry = round(self.anchor_price + s.distance_from_anchor, 2)
            target = round(entry - s.target, 2)
            print(f"  {s.index:<8} {entry:>10.2f} {target:>10.2f} {s.qty:>6} {s.grid_space:>8.2f} {s.target:>8.2f}")

        print(f"\n  Max buy exposure  : {self.total_qty} shares, "
              f"deepest at {self.anchor_price - subsets[-1].distance_from_anchor:.2f}")
        print(f"  Max sell exposure : {self.total_qty} shares, "
              f"deepest at {self.anchor_price + subsets[-1].distance_from_anchor:.2f}")
        print(f"  Effective spread  : {2 * self.base_grid_space:.2f} "
              f"({2 * self.base_grid_space * 100:.0f} paisa)")
        print(f"{'='*60}\n")
