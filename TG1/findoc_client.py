"""
Multi-Account Findoc XTS Client for TG1.

Manages 3 separate XTS Interactive sessions:
  - trade_client:        TokenA entries + targets (TradeAccount)
  - upside_oco_client:   OCO orders for SELL entries (UpsideocoAccount)
  - downside_oco_client: OCO orders for BUY entries (DownsideocoAccount)

Shares a single Zerodha KiteConnect instance for instrument resolution.
Zerodha exchange_token == XTS exchangeInstrumentID for NSE equity.
"""

import sys
import os
import configparser
import logging
from typing import Optional, Dict, Any, List

from kiteconnect import KiteConnect

# Add TG/sdk directory to path for XTS imports
_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'TG', 'sdk')
if _sdk_dir not in sys.path:
    sys.path.insert(0, _sdk_dir)

from Connect import XTSConnect

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    'New': 'OPEN',
    'PendingNew': 'OPEN',
    'Open': 'OPEN',
    'Replaced': 'OPEN',
    'PendingReplace': 'OPEN',
    'PartiallyFilled': 'PARTIAL',
    'Filled': 'COMPLETE',
    'Cancelled': 'CANCELLED',
    'PendingCancel': 'CANCELLED',
    'Rejected': 'REJECTED',
}

_EXCHANGE_MAP = {
    'NSE': 'NSECM',
    'NSECM': 'NSECM',
    'BSE': 'BSECM',
    'NFO': 'NSEFO',
    'MCX': 'MCXFO',
}

_PRODUCT_MAP = {
    'CNC': 'NRML',
    'NRML': 'NRML',
    'MIS': 'MIS',
}

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Daily')


def _load_zerodha_credentials(user_name: str = "Sai") -> dict:
    """Load Zerodha API credentials from Daily/config.ini."""
    config_path = os.path.join(_CONFIG_DIR, 'config.ini')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)

    section = f'API_CREDENTIALS_{user_name}'
    if section not in config.sections():
        raise ValueError(
            f"No credentials found for user '{user_name}' in {config_path}")

    api_key = config.get(section, 'api_key', fallback='')
    access_token = config.get(section, 'access_token', fallback='')

    if not api_key or not access_token:
        raise ValueError(
            f"Missing api_key or access_token for user '{user_name}'")

    return {'api_key': api_key, 'access_token': access_token}


class _XTSSession:
    """A single XTS Interactive session."""

    def __init__(self, name: str, api_key: str, secret_key: str,
                 root_url: str, source: str = 'WEBAPI'):
        self.name = name
        self.xt = XTSConnect(
            apiKey=api_key,
            secretKey=secret_key,
            source=source,
            root=root_url,
            disable_ssl=True,
        )
        self.client_id = None
        self.connected = False

    def login(self) -> bool:
        try:
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("[%s] XTS login failed: %s", self.name, resp)
                return False
            self.client_id = resp['result']['userID']
            self.connected = True
            logger.info("[%s] XTS login OK: userID=%s", self.name, self.client_id)
            return True
        except Exception as e:
            logger.error("[%s] XTS login exception: %s", self.name, e)
            return False

    def place_order(self, instrument_id: int, side: str, qty: int,
                    price: float, exchange: str = "NSE",
                    product: str = "MIS",
                    order_uid: str = "") -> Optional[str]:
        xts_segment = _EXCHANGE_MAP.get(exchange, 'NSECM')
        xts_product = _PRODUCT_MAP.get(product, 'MIS')
        try:
            resp = self.xt.place_order(
                exchangeSegment=xts_segment,
                exchangeInstrumentID=instrument_id,
                productType=xts_product,
                orderType=XTSConnect.ORDER_TYPE_LIMIT,
                orderSide=side,
                timeInForce=XTSConnect.VALIDITY_DAY,
                disclosedQuantity=0,
                orderQuantity=qty,
                limitPrice=price,
                stopPrice=0,
                orderUniqueIdentifier=order_uid or "",
                apiOrderSource="WebAPI",
            )
            if isinstance(resp, str):
                logger.error("[%s] ORDER FAILED: %s %d @ %.2f -> %s",
                             self.name, side, qty, price, resp)
                return None
            if resp.get('type') == 'error':
                logger.error("[%s] ORDER FAILED: %s %d @ %.2f -> %s",
                             self.name, side, qty, price,
                             resp.get('description', resp))
                return None
            order_id = str(resp['result']['AppOrderID'])
            logger.info("[%s] ORDER PLACED: %s %d @ %.2f -> ID=%s",
                        self.name, side, qty, price, order_id)
            return order_id
        except Exception as e:
            logger.error("[%s] ORDER EXCEPTION: %s %d @ %.2f -> %s",
                         self.name, side, qty, price, e)
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            resp = self.xt.cancel_order(
                appOrderID=int(order_id),
                orderUniqueIdentifier="",
            )
            if isinstance(resp, str) or (
                    isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.error("[%s] CANCEL FAILED: %s -> %s",
                             self.name, order_id, resp)
                return False
            logger.info("[%s] ORDER CANCELLED: %s", self.name, order_id)
            return True
        except Exception as e:
            logger.error("[%s] CANCEL EXCEPTION: %s -> %s",
                         self.name, order_id, e)
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get normalized status for a specific order by AppOrderID."""
        try:
            resp = self.xt.get_order_book()
            if isinstance(resp, str) or resp.get('type') == 'error':
                return None
            raw_orders = resp.get('result', [])
            if not isinstance(raw_orders, list):
                return None
            for o in raw_orders:
                if str(o.get('AppOrderID', '')) == str(order_id):
                    xts_status = o.get('OrderStatus', '')
                    return {
                        'order_id': str(o.get('AppOrderID', '')),
                        'status': _STATUS_MAP.get(xts_status, xts_status),
                        'price': float(
                            o.get('OrderAverageTradedPrice', 0)),
                        'filled_qty': int(
                            o.get('CumulativeQuantity', 0)),
                        'quantity': int(o.get('OrderQuantity', 0)),
                        'side': o.get('OrderSide', ''),
                    }
            return None
        except Exception as e:
            logger.error("[%s] get_order_status exception: %s", self.name, e)
            return None


class FindocMultiClient:
    """
    Multi-account Findoc client for grid OCO trading.

    3 XTS sessions + 1 Zerodha KiteConnect for instrument resolution.
    """

    def __init__(self, config):
        """
        Args:
            config: GridOcoConfig instance
        """
        self.config = config
        self.kite: Optional[KiteConnect] = None

        # Instrument caches: symbol -> exchange_token, symbol -> instrument_token
        self._exchange_token_cache: Dict[str, int] = {}
        self._instrument_token_cache: Dict[str, int] = {}
        self._tick_size_cache: Dict[str, float] = {}

        # XTS sessions
        self.trade_session = _XTSSession(
            'Trade', config.trade_key, config.trade_secret, config.xts_root)

        self.upside_oco_session: Optional[_XTSSession] = None
        self.downside_oco_session: Optional[_XTSSession] = None

        if config.has_oco:
            self.upside_oco_session = _XTSSession(
                'UpsideOCO', config.upside_oco_key,
                config.upside_oco_secret, config.xts_root)
            if config.same_oco_account:
                self.downside_oco_session = self.upside_oco_session
            else:
                self.downside_oco_session = _XTSSession(
                    'DownsideOCO', config.downside_oco_key,
                    config.downside_oco_secret, config.xts_root)

    def connect(self) -> bool:
        """Login to all XTS sessions and initialize Zerodha."""
        # XTS logins
        if not self.trade_session.login():
            return False

        if self.config.has_oco:
            if not self.upside_oco_session.login():
                return False
            if (self.downside_oco_session is not self.upside_oco_session
                    and not self.downside_oco_session.login()):
                return False

        # Zerodha init
        try:
            creds = _load_zerodha_credentials(self.config.zerodha_user)
            self.kite = KiteConnect(api_key=creds['api_key'])
            self.kite.set_access_token(creds['access_token'])
            logger.info("Zerodha KiteConnect initialized: user=%s",
                        self.config.zerodha_user)
        except Exception as e:
            logger.error("Zerodha init failed: %s", e)
            return False

        # Build instrument cache
        self._build_instrument_cache()
        return True

    def _build_instrument_cache(self):
        """Fetch NSE instruments from Zerodha and cache tokens + tick sizes."""
        try:
            instruments = self.kite.instruments('NSE')
            for inst in instruments:
                symbol = inst.get('tradingsymbol', '').upper()
                exchange_token = inst.get('exchange_token')
                instrument_token = inst.get('instrument_token')
                tick_size = inst.get('tick_size', 0.05)
                if symbol and exchange_token:
                    self._exchange_token_cache[symbol] = int(exchange_token)
                if symbol and instrument_token:
                    self._instrument_token_cache[symbol] = int(instrument_token)
                if symbol:
                    self._tick_size_cache[symbol] = float(tick_size)
            logger.info("Loaded %d NSE instruments from Zerodha",
                        len(self._exchange_token_cache))
        except Exception as e:
            logger.error("Failed to fetch instruments: %s", e)
            raise

    def resolve_exchange_token(self, symbol: str) -> Optional[int]:
        """Resolve symbol to exchangeInstrumentID (XTS order placement)."""
        return self._exchange_token_cache.get(symbol.upper())

    def resolve_instrument_token(self, symbol: str) -> Optional[int]:
        """Resolve symbol to instrument_token (KiteTicker subscription)."""
        return self._instrument_token_cache.get(symbol.upper())

    def get_tick_size(self, symbol: str) -> float:
        """Get tick size for a symbol (default 0.05 for NSE equity)."""
        return self._tick_size_cache.get(symbol.upper(), 0.05)

    def round_to_tick(self, price: float, symbol: str) -> float:
        """Round a price to the nearest valid tick size."""
        tick = self.get_tick_size(symbol)
        if tick <= 0:
            return round(price, 2)
        return round(round(price / tick) * tick, 2)

    # ----- Entry/Target order methods (Trade session) -----

    def place_entry_order(self, symbol: str, side: str, qty: int,
                          price: float, order_uid: str = "") -> Optional[str]:
        """Place entry or target order on TokenA via Trade account."""
        inst_id = self.resolve_exchange_token(symbol)
        if inst_id is None:
            logger.error("Cannot resolve instrument: %s", symbol)
            return None
        rounded_price = self.round_to_tick(price, symbol)
        return self.trade_session.place_order(
            inst_id, side, qty, rounded_price,
            self.config.exchange, self.config.product_type, order_uid)

    def cancel_entry_order(self, order_id: str) -> bool:
        """Cancel an entry/target order on Trade account."""
        return self.trade_session.cancel_order(order_id)

    def get_entry_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of an entry/target order from Trade account."""
        return self.trade_session.get_order_status(order_id)

    # ----- OCO order methods -----

    def _get_oco_session(self, trade_side: str) -> Optional[_XTSSession]:
        """Get the appropriate OCO session based on trade side."""
        if trade_side == 'upside':
            return self.upside_oco_session
        elif trade_side == 'downside':
            return self.downside_oco_session
        return None

    def place_oco_order(self, symbol: str, side: str, qty: int,
                        price: float, trade_side: str,
                        order_uid: str = "") -> Optional[str]:
        """Place OCO order on TokenB via appropriate OCO account."""
        session = self._get_oco_session(trade_side)
        if session is None:
            logger.error("No OCO session for trade_side=%s", trade_side)
            return None
        inst_id = self.resolve_exchange_token(symbol)
        if inst_id is None:
            logger.error("Cannot resolve OCO instrument: %s", symbol)
            return None
        rounded_price = self.round_to_tick(price, symbol)
        return session.place_order(
            inst_id, side, qty, rounded_price,
            self.config.exchange, self.config.product_type, order_uid)

    def cancel_oco_order(self, order_id: str, trade_side: str) -> bool:
        """Cancel an OCO order on the appropriate OCO account."""
        session = self._get_oco_session(trade_side)
        if session is None:
            return False
        return session.cancel_order(order_id)

    def get_oco_order_status(self, order_id: str,
                             trade_side: str) -> Optional[Dict]:
        """Get status of an OCO order from the appropriate OCO account."""
        session = self._get_oco_session(trade_side)
        if session is None:
            return None
        return session.get_order_status(order_id)

    # ----- Market data (Zerodha) -----

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get last traded price from Zerodha."""
        try:
            key = f"{exchange}:{symbol}"
            data = self.kite.ltp([key])
            return data[key]['last_price']
        except Exception as e:
            logger.error("LTP failed for %s: %s", symbol, e)
            return None

    def get_zerodha_credentials(self) -> dict:
        """Return Zerodha credentials for KiteTicker initialization."""
        return _load_zerodha_credentials(self.config.zerodha_user)
