"""
TollGate Configuration — grid parameters, credentials, and order ID generation.

Handles XTS Interactive credentials for the separate "Interactive Order Data"
account and XTS Market Data credentials for real-time quotes.
"""

import os
import logging
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'


@dataclass
class GridLevel:
    """A single grid level on one side of the anchor."""
    index: int
    side: str               # "BUY" or "SELL"
    entry_price: float      # Where the entry order is placed
    target_price: float     # Where the target is placed after fill
    qty: int


@dataclass
class TollGateConfig:
    """
    TollGate market-maker configuration.

    Grid mechanics:
    - Anchor price P0 is the center of the grid
    - Buy levels are placed below P0, sell levels above
    - Round-trip profit = 0.01 per cycle (entry + target)
    - When all levels on one side exhaust -> reanchor to last filled price
    - Each reanchor increases spacing by base_spacing
    """
    symbol: str = "SPCENET"
    anchor_price: float = 0.0

    # Grid parameters
    base_spacing: float = 0.01          # 1 paisa base spacing
    round_trip_profit: float = 0.01     # 1 paisa round-trip target
    levels_per_side: int = 10
    qty_per_level: int = 4000

    # Reanchor limits
    max_reanchors: int = 100            # Stop bot after N total reanchors

    # Broker parameters
    exchange: str = "NSE"
    product: str = "CNC"

    # XTS Interactive credentials (separate account)
    interactive_key: str = "1d17edd135146be7572510"
    interactive_secret: str = "Htvy720#4K"

    # XTS Market Data credentials (shared read-only from main TG)
    marketdata_key: str = "202e06ba0b421bf9e1e515"
    marketdata_secret: str = "Payr544@nk"

    # XTS API root URL
    xts_root: str = _DEFAULT_XTS_ROOT

    # Operational
    poll_interval: float = 2.0

    def compute_levels(self, spacing: float = None) -> Tuple[List[GridLevel], List[GridLevel]]:
        """
        Generate buy and sell grid levels around anchor_price.

        Buy level i: entry = anchor - spacing*(i+1), target = entry + round_trip_profit
        Sell level i: entry = anchor + spacing*(i+1), target = entry - round_trip_profit

        Returns (buy_levels, sell_levels).
        """
        space = spacing or self.base_spacing
        buy_levels = []
        sell_levels = []

        for i in range(self.levels_per_side):
            distance = round(space * (i + 1), 10)

            buy_entry = round(self.anchor_price - distance, 2)
            buy_target = round(buy_entry + self.round_trip_profit, 2)
            buy_levels.append(GridLevel(
                index=i, side="BUY",
                entry_price=buy_entry, target_price=buy_target,
                qty=self.qty_per_level,
            ))

            sell_entry = round(self.anchor_price + distance, 2)
            sell_target = round(sell_entry - self.round_trip_profit, 2)
            sell_levels.append(GridLevel(
                index=i, side="SELL",
                entry_price=sell_entry, target_price=sell_target,
                qty=self.qty_per_level,
            ))

        return buy_levels, sell_levels

    def print_grid_layout(self, spacing: float = None):
        """Print the grid layout for visual verification before trading."""
        space = spacing or self.base_spacing
        buy_levels, sell_levels = self.compute_levels(space)
        total_qty = self.levels_per_side * self.qty_per_level

        print(f"\n{'='*60}")
        print(f"  TOLLGATE GRID — {self.symbol}")
        print(f"{'='*60}")
        print(f"  Anchor Price     : {self.anchor_price:.2f}")
        print(f"  Base Spacing     : {self.base_spacing} ({self.base_spacing*100:.0f} paisa)")
        print(f"  Round-Trip Profit: {self.round_trip_profit} ({self.round_trip_profit*100:.0f} paisa)")
        print(f"  Current Spacing  : {space} ({space*100:.0f} paisa)")
        print(f"  Levels Per Side  : {self.levels_per_side}")
        print(f"  Qty Per Level    : {self.qty_per_level}")
        print(f"  Max Reanchors    : {self.max_reanchors}")
        print(f"  Product          : {self.product}")
        print(f"  Poll Interval    : {self.poll_interval}s")
        print(f"  Broker           : XTS Interactive + XTS Market Data")
        print(f"{'='*60}")

        print(f"\n  BUY GRID (Bot A) — entries below anchor")
        print(f"  {'Level':<8} {'Entry':>10} {'Target':>10} {'Qty':>8}")
        print(f"  {'-'*40}")
        for lv in buy_levels:
            print(f"  {lv.index:<8} {lv.entry_price:>10.2f} {lv.target_price:>10.2f} {lv.qty:>8}")

        print(f"\n  SELL GRID (Bot B) — entries above anchor")
        print(f"  {'Level':<8} {'Entry':>10} {'Target':>10} {'Qty':>8}")
        print(f"  {'-'*40}")
        for lv in sell_levels:
            print(f"  {lv.index:<8} {lv.entry_price:>10.2f} {lv.target_price:>10.2f} {lv.qty:>8}")

        print(f"\n  Max buy exposure  : {total_qty} shares, "
              f"deepest at {buy_levels[-1].entry_price:.2f}")
        print(f"  Max sell exposure : {total_qty} shares, "
              f"deepest at {sell_levels[-1].entry_price:.2f}")
        print(f"  Effective spread  : {2 * space:.2f} "
              f"({2 * space * 100:.0f} paisa)")
        print(f"{'='*60}\n")


def generate_order_id(role: str, side: str, level: int, cycle: int,
                      group_id: str, seq: int = 0) -> str:
    """
    Generate compact order identifier for XTS orderUniqueIdentifier (max 20 chars).

    Format: {ROLE}-{SIDE}L{LEVEL}C{CYCLE}-{GROUP_ID}

    Examples:
      EN-BL0C1-abc12345    Entry BUY level 0 cycle 1       (18 chars)
      EN-SL3C5-def67890    Entry SELL level 3 cycle 5       (18 chars)
      T1-BL0C1-abc12345    Target #1 level 0 cycle 1       (18 chars)
      T2-BL0C1-abc12345    Target #2 (2nd partial) cycle 1  (18 chars)
    """
    tag = role
    if seq > 0:
        tag = f"T{seq}"
    side_code = side[0]  # B or S
    return f"{tag}-{side_code}L{level}C{cycle}-{group_id}"
