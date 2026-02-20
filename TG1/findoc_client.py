"""
Multi-Account Findoc XTS Client for TG1.

Manages 3 separate XTS Interactive sessions:
  - trade_client:        TokenA entries + targets (TradeAccount)
  - upside_oco_client:   OCO orders for SELL entries (UpsideocoAccount)
  - downside_oco_client: OCO orders for BUY entries (DownsideocoAccount)

Shares a single Zerodha KiteConnect instance for instrument resolution.
Zerodha exchange_token == XTS exchangeInstrumentID for NSE equity.

Session sharing: sessions using the same XTS API key share a session file
(under TG/state/) so multiple bots on the same account don't invalidate
each other's tokens by calling interactive_login() independently.
"""

import sys
import os
import json
import time
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

# Shared XTS session directory (TG/state/) for cross-bot session sharing
_SHARED_SESSION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'TG', 'state')
_SESSION_MAX_AGE = 8 * 3600  # 8 hours

# Map known XTS API keys to account IDs for session file naming
_API_KEY_TO_ACCOUNT = {
    '8971817fbc4b2ee3607278': '01MU07',
    '59ec1c9e69270e5cd97108': '01MU06',
}


def _session_file_for_key(api_key: str) -> Optional[str]:
    """Return shared session file path for a known XTS API key."""
    account_id = _API_KEY_TO_ACCOUNT.get(api_key)
    if account_id:
        return os.path.join(_SHARED_SESSION_DIR, f'.xts_session_{account_id}.json')
    return None


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
    """A single XTS Interactive session with optional shared session file."""

    def __init__(self, name: str, api_key: str, secret_key: str,
                 root_url: str, source: str = 'WEBAPI',
                 session_file: Optional[str] = None):
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
        self._session_file = session_file

    def _try_reuse_session(self) -> bool:
        """Try to reuse an existing XTS session from shared file."""
        if not self._session_file:
            return False
        try:
            if not os.path.exists(self._session_file):
                return False
            with open(self._session_file) as f:
                session = json.load(f)
            saved_time = session.get('timestamp', 0)
            if time.time() - saved_time > _SESSION_MAX_AGE:
                logger.info("[%s] Session file expired (age=%.0f hours)",
                            self.name, (time.time() - saved_time) / 3600)
                return False
            token = session.get('token', '')
            user_id = session.get('userID', '')
            if not token or not user_id:
                return False
            is_investor = session.get('isInvestorClient', True)
            self.xt._set_common_variables(token, user_id, is_investor)
            self.client_id = user_id
            resp = self.xt.get_order_book()
            if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.info("[%s] Session file token invalid, will re-login", self.name)
                return False
            return True
        except Exception as e:
            logger.debug("[%s] Session reuse failed: %s", self.name, e)
            return False

    def _save_session(self, token: str, user_id: str):
        """Save XTS session token to shared file for other bots."""
        if not self._session_file:
            return
        try:
            os.makedirs(os.path.dirname(self._session_file), exist_ok=True)
            session = {
                'token': token,
                'userID': user_id,
                'isInvestorClient': getattr(self.xt, 'isInvestorClient', True),
                'timestamp': time.time(),
            }
            tmp = self._session_file + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(session, f)
            os.replace(tmp, self._session_file)
            logger.info("[%s] Session saved to %s", self.name, self._session_file)
        except Exception as e:
            logger.warning("[%s] Failed to save session: %s", self.name, e)

    def login(self) -> bool:
        """Login to XTS — reuse shared session file first, fresh login if needed."""
        try:
            if self._try_reuse_session():
                self.connected = True
                logger.info("[%s] XTS session reused from file: userID=%s",
                            self.name, self.client_id)
                return True
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("[%s] XTS login failed: %s", self.name, resp)
                return False
            self.client_id = resp['result']['userID']
            self.connected = True
            logger.info("[%s] XTS fresh login OK: userID=%s", self.name, self.client_id)
            self._save_session(resp['result']['token'], self.client_id)
            return True
        except Exception as e:
            logger.error("[%s] XTS login exception: %s", self.name, e)
            return False

    def refresh_session(self) -> bool:
        """Refresh session, checking shared file first to avoid ping-pong."""
        try:
            if self._try_reuse_session():
                logger.info("[%s] Picked up refreshed session from shared file",
                            self.name)
                return True
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("[%s] XTS session refresh failed: %s", self.name, resp)
                return False
            self.client_id = resp['result']['userID']
            self._save_session(resp['result']['token'], self.client_id)
            logger.info("[%s] XTS session refreshed (fresh login): userID=%s",
                        self.name, self.client_id)
            return True
        except Exception as e:
            logger.error("[%s] XTS session refresh error: %s", self.name, e)
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

        # XTS sessions (with shared session files for known accounts)
        trade_sf = _session_file_for_key(config.trade_key)
        self.trade_session = _XTSSession(
            'Trade', config.trade_key, config.trade_secret, config.xts_root,
            session_file=trade_sf)

        self.upside_oco_session: Optional[_XTSSession] = None
        self.downside_oco_session: Optional[_XTSSession] = None

        if config.has_oco:
            upside_sf = _session_file_for_key(config.upside_oco_key)
            self.upside_oco_session = _XTSSession(
                'UpsideOCO', config.upside_oco_key,
                config.upside_oco_secret, config.xts_root,
                session_file=upside_sf)
            if config.same_oco_account:
                self.downside_oco_session = self.upside_oco_session
            else:
                downside_sf = _session_file_for_key(config.downside_oco_key)
                self.downside_oco_session = _XTSSession(
                    'DownsideOCO', config.downside_oco_key,
                    config.downside_oco_secret, config.xts_root,
                    session_file=downside_sf)

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
