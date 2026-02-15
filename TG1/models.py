"""
Data models for TG1 Grid OCO Trading Bot.

OpenOrder: A single grid level record that cycles between entry and target states.
OrderHistoryRecord: A completed trade record (entry fill + target/OCO fill).

State machine for each OpenOrder:

  FRESH: order_side='entry', entry_order_id=None, oco_trade_price=None
    -> place_entry_orders picks it up, places LIMIT on exchange
  ENTRY_PLACED: order_side='entry', entry_order_id='123'
    -> polls for fill
  ENTRY_FILLED -> TARGET_READY: order_side='target', entry_order_id=None,
                                oco_trade_price set
    -> place_entry_orders picks it up as target order
  TARGET_PLACED: order_side='target', entry_order_id='456'
    -> polls for target fill or OCO fill
  TARGET_FILLED: resets back to FRESH state (new uuid, ready for re-entry)
  OCO_FILLED: oco_filled=True, level permanently closed
"""

import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


def new_uuid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class OpenOrder:
    """A single grid level that cycles between entry and target states."""

    uuid: str = field(default_factory=new_uuid)
    bot_name: str = ""

    # Exchange order IDs (null when not placed)
    entry_order_id: Optional[str] = None
    oco_order_id: Optional[str] = None

    # Direction and prices
    entry_trade_direction: str = ""       # BUY or SELL
    oco_trade_direction: Optional[str] = None
    entry_trade_price: Optional[float] = None
    oco_trade_price: Optional[float] = None

    # TokenB reference price (captured at entry fill time)
    token_b_price: Optional[float] = None

    # Grid position
    trade_side: str = ""                  # "upside" or "downside"
    oco_filled: bool = False
    order_side: str = "entry"             # "entry" or "target"

    # Quantities (copied from config at creation time)
    token_a_quantity: float = 0
    token_b_quantity: float = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'OpenOrder':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OrderHistoryRecord:
    """A completed trade record stored in order history."""

    uuid: str = ""
    bot_name: str = ""
    trade_side: str = ""

    # Token A details
    token_a_symbol: str = ""
    token_a_quantity: float = 0

    # Token B details
    token_b_symbol: str = ""
    token_b_quantity: float = 0
    token_b_price: Optional[float] = None

    # Entry order
    entry_order_id: Optional[str] = None
    entry_trade_direction: str = ""
    entry_trade_price: float = 0.0
    filled_entry_price: float = 0.0
    entry_order_status: str = ""

    # Target order
    target_order_id: Optional[str] = None
    target_trade_direction: Optional[str] = None
    target_trade_price: Optional[float] = None
    filled_target_price: Optional[float] = None
    target_order_status: Optional[str] = None

    # OCO order
    oco_order_id: Optional[str] = None
    oco_trade_direction: Optional[str] = None
    oco_trade_price: Optional[float] = None

    # Timestamps
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'OrderHistoryRecord':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
