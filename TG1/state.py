"""
State persistence for TG1 Grid OCO Trading Bot.

JSON-based state with atomic writes (tmp + os.replace).
Tracks: open orders, order history, position counters, bot status.
"""

import json
import os
import logging
from datetime import datetime
from typing import List, Optional

from .models import OpenOrder, OrderHistoryRecord

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')


class StateManager:
    """Manages bot state persistence via JSON files."""

    def __init__(self, bot_name: str, state_dir: str = None):
        self.bot_name = bot_name
        self.state_dir = state_dir or _STATE_DIR
        safe_name = bot_name.replace(' ', '_').replace('/', '_')
        self.state_file = os.path.join(self.state_dir, f'{safe_name}_state.json')

        # Open orders (grid levels)
        self.open_orders: List[OpenOrder] = []

        # Completed trade history (last 500)
        self.order_history: List[OrderHistoryRecord] = []

        # Position counters
        self.upside_net_quantity: float = 0.0
        self.downside_net_quantity: float = 0.0
        self.upside_oco_net_count: int = 0
        self.downside_oco_net_count: int = 0

        # Bot metadata
        self.bot_status: str = "Active"
        self.trade_type: str = ""
        self.token_a_symbol: str = ""
        self.token_b_symbol: str = ""
        self.entry_price: float = 0.0
        self.max_quantity: float = 0.0
        self.total_pnl: float = 0.0
        self.last_updated: str = ""

    def save(self):
        """Atomic write: create .tmp, then os.replace()."""
        os.makedirs(self.state_dir, exist_ok=True)
        self.last_updated = datetime.now().isoformat()

        state = {
            'bot_name': self.bot_name,
            'bot_status': self.bot_status,
            'trade_type': self.trade_type,
            'token_a_symbol': self.token_a_symbol,
            'token_b_symbol': self.token_b_symbol,
            'entry_price': self.entry_price,
            'max_quantity': self.max_quantity,
            'upside_net_quantity': self.upside_net_quantity,
            'downside_net_quantity': self.downside_net_quantity,
            'upside_oco_net_count': self.upside_oco_net_count,
            'downside_oco_net_count': self.downside_oco_net_count,
            'total_pnl': self.total_pnl,
            'last_updated': self.last_updated,
            'open_orders': [o.to_dict() for o in self.open_orders],
            'order_history': [h.to_dict() for h in self.order_history[-500:]],
        }

        tmp = self.state_file + '.tmp'
        try:
            with open(tmp, 'w') as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, self.state_file)
            logger.debug("State saved: %d open, %d history",
                         len(self.open_orders), len(self.order_history))
        except Exception as e:
            logger.error("Failed to save state: %s", e)
            if os.path.exists(tmp):
                os.remove(tmp)

    def load(self) -> bool:
        """Load state from JSON file. Returns True if state was found."""
        if not os.path.exists(self.state_file):
            logger.info("No existing state file found: %s", self.state_file)
            return False

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            self.bot_status = state.get('bot_status', 'Active')
            self.trade_type = state.get('trade_type', '')
            self.token_a_symbol = state.get('token_a_symbol', '')
            self.token_b_symbol = state.get('token_b_symbol', '')
            self.entry_price = state.get('entry_price', 0.0)
            self.max_quantity = state.get('max_quantity', 0.0)
            self.upside_net_quantity = state.get('upside_net_quantity', 0.0)
            self.downside_net_quantity = state.get('downside_net_quantity', 0.0)
            self.upside_oco_net_count = state.get('upside_oco_net_count', 0)
            self.downside_oco_net_count = state.get('downside_oco_net_count', 0)
            self.total_pnl = state.get('total_pnl', 0.0)
            self.last_updated = state.get('last_updated', '')

            self.open_orders = [
                OpenOrder.from_dict(o)
                for o in state.get('open_orders', [])
            ]
            self.order_history = [
                OrderHistoryRecord.from_dict(h)
                for h in state.get('order_history', [])
            ]

            logger.info("State loaded: %d open orders, %d history, "
                        "upside_qty=%.1f, downside_qty=%.1f, "
                        "upside_oco=%d, downside_oco=%d",
                        len(self.open_orders), len(self.order_history),
                        self.upside_net_quantity, self.downside_net_quantity,
                        self.upside_oco_net_count, self.downside_oco_net_count)
            return True

        except Exception as e:
            logger.error("Failed to load state from %s: %s", self.state_file, e)
            return False

    def update_quantity(self, order_type: str, side: str, quantity: float):
        """
        Update position counters after a fill.

        order_type: 'entry', 'target', or 'oco'
        side: original entry direction ('BUY' or 'SELL')
        quantity: token_a_quantity
        """
        if order_type == 'entry':
            if side == 'BUY':
                self.downside_net_quantity += quantity
            elif side == 'SELL':
                self.upside_net_quantity += quantity
        elif order_type == 'target':
            if side == 'SELL':
                self.downside_net_quantity -= quantity
            elif side == 'BUY':
                self.upside_net_quantity -= quantity
        elif order_type == 'oco':
            if side == 'SELL':
                self.downside_oco_net_count += 1
            elif side == 'BUY':
                self.upside_oco_net_count += 1

    def find_order_by_uuid(self, order_uuid: str) -> Optional[OpenOrder]:
        for order in self.open_orders:
            if order.uuid == order_uuid:
                return order
        return None

    def find_order_by_entry_id(self, entry_order_id: str) -> Optional[OpenOrder]:
        for order in self.open_orders:
            if order.entry_order_id == entry_order_id:
                return order
        return None

    def find_order_by_oco_id(self, oco_order_id: str) -> Optional[OpenOrder]:
        for order in self.open_orders:
            if order.oco_order_id == oco_order_id:
                return order
        return None
