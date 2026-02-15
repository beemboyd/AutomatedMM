"""
Grid OCO Trading Bot Configuration

Two-token grid trading with OCO hedging:
  - TokenA: grid-traded instrument (entries + targets via TradeAccount)
  - TokenB: hedge instrument (OCO orders via Upside/Downside OCO accounts)

Trade types:
  gridocots  - Bidirectional grid (BUY below + SELL above) with OCO
  buyocots   - Buy-only grid with OCO protection
  sellocots  - Sell-only grid with OCO protection
  buyts      - Buy-only grid, targets only (no OCO)
  sellts     - Sell-only grid, targets only (no OCO)

Credentials:
  - 3 XTS accounts for OCO types (trade, upside_oco, downside_oco)
  - 1 XTS account for non-OCO types (trade only)
  - Zerodha user for KiteTicker WebSocket prices + instrument resolution
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'

VALID_TRADE_TYPES = ('gridocots', 'buyocots', 'sellocots', 'buyts', 'sellts')
OCO_TRADE_TYPES = ('gridocots', 'buyocots', 'sellocots')


@dataclass
class GridOcoConfig:
    """Configuration for a grid OCO trading bot."""

    # Bot identity
    bot_name: str = ""
    trade_type: str = "gridocots"

    # Instruments (Zerodha tradingsymbols)
    token_a_symbol: str = ""
    token_b_symbol: str = ""

    # Grid parameters
    entry_price: float = 0.0
    steps: int = 5
    spread: float = 1.0
    target_spread: float = 1.0
    oco_spread: float = 0.0
    token_a_quantity: int = 0
    token_b_quantity: int = 0

    # Broker parameters
    product_type: str = "MIS"
    exchange: str = "NSE"

    # Termination
    oco_stop_count: int = 3

    # XTS credentials - Trade Account (TokenA entries + targets)
    trade_key: str = ""
    trade_secret: str = ""

    # XTS credentials - Upside OCO Account (OCO for SELL entries)
    upside_oco_key: str = ""
    upside_oco_secret: str = ""

    # XTS credentials - Downside OCO Account (OCO for BUY entries)
    downside_oco_key: str = ""
    downside_oco_secret: str = ""

    # Zerodha user for market data
    zerodha_user: str = "Sai"

    # XTS API root
    xts_root: str = _DEFAULT_XTS_ROOT

    # Operational
    poll_interval: float = 1.0
    auto_reenter: bool = True

    @property
    def has_oco(self) -> bool:
        return self.trade_type in OCO_TRADE_TYPES

    @property
    def max_quantity(self) -> float:
        return self.token_a_quantity * self.steps

    @property
    def same_oco_account(self) -> bool:
        return (self.upside_oco_key == self.downside_oco_key and
                self.upside_oco_secret == self.downside_oco_secret)

    def validate(self):
        """Validate configuration. Raises ValueError on invalid config."""
        if not self.bot_name:
            raise ValueError("--bot-name is required")
        if self.trade_type not in VALID_TRADE_TYPES:
            raise ValueError(f"--trade-type must be one of {VALID_TRADE_TYPES}")
        if not self.token_a_symbol:
            raise ValueError("--token-a is required")
        if self.has_oco and not self.token_b_symbol:
            raise ValueError("--token-b is required for OCO trade types")
        if self.steps < 1:
            raise ValueError("--steps must be >= 1")
        if self.spread <= 0:
            raise ValueError("--spread must be > 0")
        if self.target_spread <= 0:
            raise ValueError("--target-spread must be > 0")
        if self.token_a_quantity <= 0:
            raise ValueError("--qty-a must be > 0")
        if self.has_oco and self.oco_spread <= 0:
            raise ValueError("--oco-spread must be > 0 for OCO trade types")
        if not self.trade_key or not self.trade_secret:
            raise ValueError("--trade-key and --trade-secret are required")
        if self.has_oco:
            if not self.upside_oco_key or not self.upside_oco_secret:
                raise ValueError("--upside-oco-key/secret required for OCO types")
            if not self.downside_oco_key or not self.downside_oco_secret:
                raise ValueError("--downside-oco-key/secret required for OCO types")

    def print_grid_layout(self):
        """Print the grid layout for visual verification."""
        print(f"\n{'='*65}")
        print(f"  GRID OCO CONFIGURATION — {self.bot_name}")
        print(f"{'='*65}")
        print(f"  Trade Type       : {self.trade_type}")
        print(f"  Token A          : {self.token_a_symbol} (grid-traded)")
        if self.has_oco:
            print(f"  Token B          : {self.token_b_symbol} (OCO hedge)")
        print(f"  Entry Price      : {self.entry_price:.2f}")
        print(f"  Steps            : {self.steps}")
        print(f"  Spread           : {self.spread}")
        print(f"  Target Spread    : {self.target_spread}")
        if self.has_oco:
            print(f"  OCO Spread       : {self.oco_spread}")
            print(f"  OCO Stop Count   : {self.oco_stop_count}")
        print(f"  Qty A per step   : {self.token_a_quantity}")
        print(f"  Max Quantity     : {self.max_quantity}")
        print(f"  Product          : {self.product_type}")
        print(f"  Poll Interval    : {self.poll_interval}s")
        print(f"  Auto Re-enter    : {self.auto_reenter}")
        if self.has_oco:
            same = "YES (shared)" if self.same_oco_account else "NO (separate)"
            print(f"  Same OCO Account : {same}")
        print(f"{'='*65}")

        if self.trade_type in ('gridocots', 'sellocots', 'sellts'):
            print(f"\n  SELL GRID (upside) — entries above {self.entry_price:.2f}")
            print(f"  {'Level':<8} {'Entry':>10} {'Target':>10}")
            print(f"  {'-'*30}")
            for i in range(1, self.steps + 1):
                entry = self.entry_price + (i * self.spread)
                target = entry - self.target_spread
                print(f"  {i:<8} {entry:>10.2f} {target:>10.2f}")

        if self.trade_type in ('gridocots',):
            print(f"\n  {'─'*30} ENTRY PRICE ({self.entry_price:.2f}) {'─'*10}")

        if self.trade_type in ('gridocots', 'buyocots', 'buyts'):
            print(f"\n  BUY GRID (downside) — entries below {self.entry_price:.2f}")
            print(f"  {'Level':<8} {'Entry':>10} {'Target':>10}")
            print(f"  {'-'*30}")
            for i in range(1, self.steps + 1):
                entry = self.entry_price - (i * self.spread)
                target = entry + self.target_spread
                print(f"  {i:<8} {entry:>10.2f} {target:>10.2f}")

        print(f"{'='*65}\n")
