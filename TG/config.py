"""
Grid Trading Bot Configuration

Handles XTS Interactive credentials (trading via Findoc) and
Zerodha user selection (market data from config.ini).

Credentials:
  - XTS Interactive: key + secret for order placement/cancellation
  - Zerodha: user name to look up in Daily/config.ini for LTP & instruments
"""

import os
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default XTS test credentials
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'


@dataclass
class SubsetConfig:
    """
    Configuration for a single grid level.

    Uniform spacing: all levels have the same grid_space and target.
    Level i (0-indexed):
      distance  = grid_space * (i + 1)
      target    = base_target (constant)

    Example with grid_space=0.01, base_target=0.03, levels_per_side=10:
      Level 0:  space=0.01, target=0.03, distance=0.01,  qty=100
      Level 1:  space=0.01, target=0.03, distance=0.02,  qty=100
      ...
      Level 9:  space=0.01, target=0.03, distance=0.10,  qty=100
    """
    index: int
    qty: int
    grid_space: float       # spacing for this subset (increases linearly)
    target: float           # target offset for this subset (increases linearly)
    distance_from_anchor: float  # cumulative distance from anchor price


@dataclass
class GridConfig:
    """
    Main grid trading configuration.

    Grid mechanics (epoch-based reanchor):
    - Anchor price P0 is the center of the grid
    - Buy levels are placed below P0, sell levels above
    - levels_per_side uniform levels on each side, qty_per_level shares each
    - When all levels on one side exhaust → reanchor to last filled price
    - Every reanchor_epoch reanchors, spacing increases by base_grid_space
    - Stop bot after max_grid_levels reanchors on one side
    """
    symbol: str
    anchor_price: float

    # Grid parameters
    base_grid_space: float = 0.01   # 1 paisa base spacing
    base_target: float = 0.02       # 2 paisa target
    levels_per_side: int = 10       # grid levels on each side before reanchor
    qty_per_level: int = 100        # shares per grid level order

    # Epoch-based reanchor parameters
    reanchor_epoch: int = 100       # reanchors before spacing increases
    max_grid_levels: int = 2000     # stop bot after N reanchors on one side

    # Broker parameters
    exchange: str = "NSE"
    product: str = "NRML"       # XTS: NRML for carry-forward, MIS for intraday

    # Pair trading parameters
    pair_symbol: str = ""           # e.g., "SPCENET" — opposite-direction hedge
    hedge_ratio: int = 0            # target pair ratio on COMPLETE (0 = disabled)
    partial_hedge_ratio: int = 0    # pair ratio on PARTIAL fills (0 = no partial hedging)

    # Holdings override (bypasses XTS holdings API which may return empty)
    holdings_override: int = -1     # -1 = use API, 0+ = override with this qty

    # Operational parameters
    auto_reenter: bool = True       # re-place entry after target fills
    auto_reanchor: bool = True      # re-anchor grid when all levels exhausted
    poll_interval: float = 2.0      # seconds between order status polls

    # XTS Interactive credentials (order placement)
    interactive_key: str = ""
    interactive_secret: str = ""

    # Zerodha user for market data (looked up in Daily/config.ini)
    zerodha_user: str = "Sai"

    # XTS API root URL
    xts_root: str = _DEFAULT_XTS_ROOT

    @property
    def has_pair(self) -> bool:
        """True if pair trading is configured."""
        return bool(self.pair_symbol and self.hedge_ratio > 0)

    def compute_subsets(self, grid_space: float = None) -> List[SubsetConfig]:
        """
        Compute grid subsets with uniform spacing.

        All levels have the same spacing and target.
        Level i (0-indexed): distance = grid_space * (i + 1)

        Args:
            grid_space: Override spacing (used during reanchor with increased spacing).
                        Defaults to base_grid_space.
        """
        space = grid_space or self.base_grid_space
        subsets = []
        for i in range(self.levels_per_side):
            distance = round(space * (i + 1), 10)
            subsets.append(SubsetConfig(
                index=i,
                qty=self.qty_per_level,
                grid_space=space,
                target=self.base_target,
                distance_from_anchor=distance,
            ))
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
        zerodha_user = overrides.pop('zerodha_user', 'Sai')
        xts_root = overrides.pop('xts_root', _DEFAULT_XTS_ROOT)

        if not interactive_key or not interactive_secret:
            raise ValueError("Missing XTS Interactive credentials "
                             "(--interactive-key, --interactive-secret)")

        return cls(
            symbol=symbol,
            anchor_price=anchor_price,
            interactive_key=interactive_key,
            interactive_secret=interactive_secret,
            zerodha_user=zerodha_user,
            xts_root=xts_root,
            **overrides,
        )

    def print_grid_layout(self, buy_spacing: float = None, sell_spacing: float = None):
        """Print the grid layout for visual verification before trading."""
        buy_space = buy_spacing or self.base_grid_space
        sell_space = sell_spacing or self.base_grid_space
        buy_subsets = self.compute_subsets(grid_space=buy_space)
        sell_subsets = self.compute_subsets(grid_space=sell_space)
        total_qty = self.levels_per_side * self.qty_per_level
        print(f"\n{'='*60}")
        print(f"  GRID CONFIGURATION — {self.symbol}")
        print(f"{'='*60}")
        print(f"  Anchor Price     : {self.anchor_price:.2f}")
        print(f"  Base Grid Space  : {self.base_grid_space} ({self.base_grid_space*100:.0f} paisa)")
        print(f"  Base Target      : {self.base_target} ({self.base_target*100:.0f} paisa)")
        print(f"  Levels Per Side  : {self.levels_per_side}")
        print(f"  Qty Per Level    : {self.qty_per_level}")
        print(f"  Reanchor Epoch   : {self.reanchor_epoch}")
        print(f"  Max Grid Levels  : {self.max_grid_levels}")
        print(f"  Buy Spacing      : {buy_space}")
        print(f"  Sell Spacing     : {sell_space}")
        print(f"  Product          : {self.product}")
        print(f"  Broker           : XTS + Zerodha (user={self.zerodha_user})")
        print(f"  Auto Re-enter    : {self.auto_reenter}")
        if self.has_pair:
            print(f"  Pair Symbol      : {self.pair_symbol}")
            print(f"  Hedge Ratio      : {self.hedge_ratio} (on COMPLETE)")
            print(f"  Partial Hedge    : {self.partial_hedge_ratio} (on PARTIAL, 0=disabled)")
            print(f"  Pair Mode        : OPPOSITE (entry→hedge, target→unwind)")
        print(f"{'='*60}")

        print(f"\n  BUY GRID (Bot A) — entries below anchor")
        print(f"  {'Level':<8} {'Entry':>10} {'Target':>10} {'Qty':>6} {'Space':>8} {'TgtOff':>8}")
        print(f"  {'-'*52}")
        for s in buy_subsets:
            entry = round(self.anchor_price - s.distance_from_anchor, 2)
            target = round(entry + s.target, 2)
            print(f"  {s.index:<8} {entry:>10.2f} {target:>10.2f} {s.qty:>6} {s.grid_space:>8.2f} {s.target:>8.2f}")

        print(f"\n  SELL GRID (Bot B) — entries above anchor")
        print(f"  {'Level':<8} {'Entry':>10} {'Target':>10} {'Qty':>6} {'Space':>8} {'TgtOff':>8}")
        print(f"  {'-'*52}")
        for s in sell_subsets:
            entry = round(self.anchor_price + s.distance_from_anchor, 2)
            target = round(entry - s.target, 2)
            print(f"  {s.index:<8} {entry:>10.2f} {target:>10.2f} {s.qty:>6} {s.grid_space:>8.2f} {s.target:>8.2f}")

        print(f"\n  Max buy exposure  : {total_qty} shares, "
              f"deepest at {self.anchor_price - buy_subsets[-1].distance_from_anchor:.2f}")
        print(f"  Max sell exposure : {total_qty} shares, "
              f"deepest at {self.anchor_price + sell_subsets[-1].distance_from_anchor:.2f}")
        print(f"  Effective spread  : {2 * self.base_grid_space:.2f} "
              f"({2 * self.base_grid_space * 100:.0f} paisa)")
        print(f"{'='*60}\n")


def generate_order_id(primary: str, secondary: str, subset_index: int,
                      role: str, bot: str, group_id: str, seq: int = 0) -> str:
    """
    Generate compact order identifier for XTS orderUniqueIdentifier (max 20 chars).

    Format: {ROLE}[{SEQ}]-{BOT}-L{LEVEL}-{GROUP_ID}

    Symbol names are omitted — XTS order record already has the symbol.
    The group_id (8-char UUID) ensures global uniqueness across all bots.

    For PH/PU roles, seq is appended (1-indexed).
    EN/TP roles don't need seq.

    Examples:
      EN-A-L0-abc12345     (16 chars)
      TP-B-L5-abc12345     (16 chars)
      PH1-A-L0-abc12345    (17 chars)
      PU1-B-L99-abc12345   (19 chars, extreme)
    """
    tag = role
    if seq > 0:
        tag += str(seq)
    return f"{tag}-{bot}-L{subset_index}-{group_id}"
