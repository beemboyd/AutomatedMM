"""
Hybrid Client — Zerodha for market data, XTS for trading.

Composes two brokers behind a single interface:
  - Zerodha KiteConnect: LTP quotes, instrument resolution (via config.ini)
  - XTS Interactive: order placement, cancellation, order book, holdings, positions

This eliminates the need for XTS market-data credentials. Zerodha is
already running for tick data and dashboards, so we reuse it for
instrument lookup and price queries.

Instrument mapping:
  Zerodha `exchange_token` == XTS `exchangeInstrumentID` for NSE EQ.
  On connect(), we fetch kite.instruments('NSE') once and build a
  symbol -> exchange_token cache for O(1) lookups.
"""

import sys
import os
import configparser
import logging
from typing import Optional, List, Dict, Any

from kiteconnect import KiteConnect

# Add SDK directory to path for XTS imports
_sdk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sdk')
if _sdk_dir not in sys.path:
    sys.path.insert(0, _sdk_dir)

from Connect import XTSConnect

logger = logging.getLogger(__name__)

# XTS order status -> normalized status for engine
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

# Exchange name -> XTS exchangeSegment string
_EXCHANGE_MAP = {
    'NSE': 'NSECM',
    'NSECM': 'NSECM',
    'BSE': 'BSECM',
    'BSECM': 'BSECM',
    'NFO': 'NSEFO',
    'NSEFO': 'NSEFO',
    'MCX': 'MCXFO',
    'MCXFO': 'MCXFO',
}

# Product type mapping
_PRODUCT_MAP = {
    'CNC': 'NRML',
    'NRML': 'NRML',
    'MIS': 'MIS',
}

# Path to Daily/config.ini
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Daily')


def _load_zerodha_credentials(user_name: str = "Sai") -> dict:
    """
    Load Zerodha API credentials from Daily/config.ini for a given user.

    Returns dict with api_key, api_secret, access_token.
    """
    config_path = os.path.join(_CONFIG_DIR, 'config.ini')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)

    section = f'API_CREDENTIALS_{user_name}'
    if section not in config.sections():
        raise ValueError(f"No credentials found for user '{user_name}' in {config_path}")

    api_key = config.get(section, 'api_key', fallback='')
    access_token = config.get(section, 'access_token', fallback='')

    if not api_key or not access_token:
        raise ValueError(f"Missing api_key or access_token for user '{user_name}'")

    return {'api_key': api_key, 'access_token': access_token}


class HybridClient:
    """
    Hybrid broker client: Zerodha (data) + XTS (trading).

    Provides the same method signatures as XTSClient so bots
    and engine code require no changes beyond the import.
    """

    def __init__(self, interactive_key: str, interactive_secret: str,
                 zerodha_user: str = "Sai",
                 root_url: str = 'https://xts.myfindoc.com',
                 source: str = 'WEBAPI'):
        self.root_url = root_url
        self.source = source
        self.zerodha_user = zerodha_user

        # XTS Interactive instance (trading only)
        self.xt = XTSConnect(
            apiKey=interactive_key,
            secretKey=interactive_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        # Zerodha KiteConnect (market data only) — initialized on connect()
        self.kite: Optional[KiteConnect] = None

        self.connected = False
        self.client_id = None
        # symbol -> exchange_token (== XTS exchangeInstrumentID for NSE EQ)
        self._instrument_cache: Dict[str, int] = {}

    def connect(self) -> bool:
        """
        Login to XTS interactive + initialize Zerodha instrument cache.

        1. XTS interactive login (for trading)
        2. Zerodha KiteConnect init (for market data)
        3. Fetch kite.instruments('NSE') and build symbol -> exchange_token map
        """
        try:
            # --- XTS Interactive login ---
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("XTS Interactive login failed: %s", resp)
                return False
            self.client_id = resp['result']['userID']
            logger.info("XTS Interactive login OK: userID=%s", self.client_id)

            # --- Zerodha init ---
            creds = _load_zerodha_credentials(self.zerodha_user)
            self.kite = KiteConnect(api_key=creds['api_key'])
            self.kite.set_access_token(creds['access_token'])
            logger.info("Zerodha KiteConnect initialized for user=%s", self.zerodha_user)

            # --- Build instrument cache ---
            self._build_instrument_cache()

            self.connected = True
            return True

        except Exception as e:
            logger.error("Hybrid client connection failed: %s", e)
            return False

    def _build_instrument_cache(self):
        """
        Fetch all NSE instruments from Zerodha and cache symbol -> exchange_token.

        exchange_token is the same numeric ID that XTS uses as exchangeInstrumentID
        for NSE equity, so we can use it directly for order placement.
        """
        try:
            instruments = self.kite.instruments('NSE')
            for inst in instruments:
                symbol = inst.get('tradingsymbol', '')
                exchange_token = inst.get('exchange_token')
                if symbol and exchange_token:
                    self._instrument_cache[symbol.upper()] = int(exchange_token)
            logger.info("Loaded %d NSE instruments from Zerodha", len(self._instrument_cache))
        except Exception as e:
            logger.error("Failed to fetch instruments from Zerodha: %s", e)
            raise

    def resolve_instrument(self, symbol: str, exchange: str = 'NSE') -> Optional[int]:
        """
        Resolve a trading symbol to its exchangeInstrumentID (exchange_token).

        Pure dict lookup — zero network calls after connect().
        """
        inst_id = self._instrument_cache.get(symbol.upper())
        if inst_id is None:
            logger.error("Could not resolve instrument: %s (not in cache)", symbol)
        return inst_id

    # ----- Trading methods (XTS Interactive) -----

    def place_order(self, symbol: str, transaction_type: str, qty: int,
                    price: float, exchange: str = "NSE",
                    product: str = "NRML",
                    order_unique_id: str = "") -> Optional[str]:
        """
        Place a LIMIT order via XTS Interactive.

        Args:
            symbol: Trading symbol (e.g., "IRFC")
            transaction_type: "BUY" or "SELL"
            qty: Number of shares
            price: Limit price
            exchange: Exchange (default NSE)
            product: Product type (CNC->NRML, MIS, NRML)
            order_unique_id: Custom identifier for tracking

        Returns:
            AppOrderID as string, or None on failure.
        """
        instrument_id = self.resolve_instrument(symbol, exchange)
        if instrument_id is None:
            logger.error("ORDER FAILED: cannot resolve %s", symbol)
            return None

        xts_segment = _EXCHANGE_MAP.get(exchange, 'NSECM')
        xts_product = _PRODUCT_MAP.get(product, 'NRML')

        try:
            resp = self.xt.place_order(
                exchangeSegment=xts_segment,
                exchangeInstrumentID=instrument_id,
                productType=xts_product,
                orderType=XTSConnect.ORDER_TYPE_LIMIT,
                orderSide=transaction_type,
                timeInForce=XTSConnect.VALIDITY_DAY,
                disclosedQuantity=0,
                orderQuantity=qty,
                limitPrice=price,
                stopPrice=0,
                orderUniqueIdentifier=order_unique_id or "",
                apiOrderSource="WebAPI",
            )

            if isinstance(resp, str):
                logger.error("ORDER FAILED: %s %s %d @ %.2f -> %s",
                             transaction_type, symbol, qty, price, resp)
                return None

            if resp.get('type') == 'error':
                logger.error("ORDER FAILED: %s %s %d @ %.2f -> %s",
                             transaction_type, symbol, qty, price,
                             resp.get('description', resp))
                return None

            order_id = str(resp['result']['AppOrderID'])
            logger.info("ORDER PLACED: %s %s %d @ %.2f -> AppOrderID=%s",
                        transaction_type, symbol, qty, price, order_id)
            return order_id

        except Exception as e:
            logger.error("ORDER EXCEPTION: %s %s %d @ %.2f -> %s",
                         transaction_type, symbol, qty, price, e)
            return None

    def place_market_order(self, symbol: str, transaction_type: str, qty: int,
                           exchange: str = "NSE",
                           product: str = "NRML",
                           order_unique_id: str = "",
                           slippage: float = 0.02) -> tuple:
        """
        Place a market-like order by using aggressive LIMIT at LTP ± slippage.

        For illiquid instruments, LTP alone won't fill a SELL (need to hit bid).
        We add slippage: SELL at LTP - slippage, BUY at LTP + slippage.

        Returns (AppOrderID, price) tuple, or (None, 0.0) on failure.
        """
        ltp = self.get_ltp(symbol, exchange)
        if ltp is None:
            logger.error("MARKET ORDER FAILED: cannot get LTP for %s", symbol)
            return None, 0.0

        if transaction_type == "SELL":
            price = round(ltp - slippage, 2)
        else:
            price = round(ltp + slippage, 2)

        logger.info("MARKET ORDER: %s %s %d @ LTP=%.2f -> LIMIT=%.2f (slip=%.2f)",
                     transaction_type, symbol, qty, ltp, price, slippage)
        order_id = self.place_order(symbol, transaction_type, qty, price, exchange, product,
                                    order_unique_id=order_unique_id)
        return order_id, price

    def cancel_order(self, order_id: str, order_unique_id: str = "") -> bool:
        """Cancel a pending order by AppOrderID via XTS."""
        try:
            resp = self.xt.cancel_order(
                appOrderID=int(order_id),
                orderUniqueIdentifier=order_unique_id or f"CANCEL_{order_id}",
            )
            if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.error("CANCEL FAILED: %s -> %s", order_id, resp)
                return False
            logger.info("ORDER CANCELLED: %s", order_id)
            return True
        except Exception as e:
            logger.error("CANCEL EXCEPTION: %s -> %s", order_id, e)
            return False

    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all orders for the day from XTS, normalized to engine-expected format.

        Returns list of dicts with keys:
            order_id, status, average_price, filled_quantity,
            quantity, status_message, transaction_type
        """
        try:
            resp = self.xt.get_order_book()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Order book fetch failed: %s", resp)
                return []

            raw_orders = resp.get('result', [])
            if not isinstance(raw_orders, list):
                return []

            normalized = []
            for o in raw_orders:
                xts_status = o.get('OrderStatus', '')
                normalized.append({
                    'order_id': str(o.get('AppOrderID', '')),
                    'status': _STATUS_MAP.get(xts_status, xts_status),
                    'average_price': float(o.get('OrderAverageTradedPrice', 0) or 0),
                    'filled_quantity': int(o.get('CumulativeQuantity', 0) or 0),
                    'quantity': int(o.get('OrderQuantity', 0) or 0),
                    'status_message': o.get('CancelRejectReason', ''),
                    'transaction_type': o.get('OrderSide', ''),
                    'order_unique_id': o.get('OrderUniqueIdentifier', ''),
                })
            return normalized

        except Exception as e:
            logger.error("Order book exception: %s", e)
            return []

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get normalized status dict for a specific order."""
        orders = self.get_orders()
        for o in orders:
            if o['order_id'] == str(order_id):
                return o
        return None

    # ----- Market data methods (Zerodha) -----

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get last traded price from Zerodha."""
        try:
            key = f"{exchange}:{symbol}"
            data = self.kite.ltp([key])
            return data[key]['last_price']
        except Exception as e:
            logger.error("LTP failed for %s: %s", symbol, e)
            return None

    # ----- Holdings/positions (XTS Interactive) -----

    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings from XTS (Findoc account)."""
        try:
            resp = self.xt.get_holding()
            logger.info("Holdings raw response type=%s, keys=%s",
                        type(resp).__name__,
                        list(resp.keys()) if isinstance(resp, dict) else 'N/A')
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Holdings fetch failed: %s", resp)
                return []
            result = resp.get('result', [])
            logger.info("Holdings result type=%s, len=%s, sample=%s",
                        type(result).__name__,
                        len(result) if isinstance(result, (list, dict)) else 'N/A',
                        str(result)[:500] if result else 'empty')
            # XTS may nest holdings under 'RMSHoldings' or 'ClientHoldings'
            if isinstance(result, dict):
                result = (result.get('RMSHoldings') or
                          result.get('ClientHoldings') or
                          result.get('holdings') or [])
                logger.info("Holdings unwrapped: type=%s, len=%s",
                            type(result).__name__,
                            len(result) if isinstance(result, list) else 'N/A')
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Holdings exception: %s", e)
            return []

    def get_available_qty(self, symbol: str) -> int:
        """Get available quantity of a symbol in XTS holdings."""
        holdings = self.get_holdings()
        if not isinstance(holdings, list):
            logger.warning("Holdings not a list: %s", type(holdings))
            return 0
        for h in holdings:
            if isinstance(h, dict):
                # XTS uses various field names across versions
                holding_symbol = (h.get('TradingSymbol') or
                                  h.get('tradingSymbol') or
                                  h.get('ScripName') or
                                  h.get('Symbol') or '')
                if holding_symbol.upper() == symbol.upper():
                    qty = (h.get('HoldingQuantity') or
                           h.get('Quantity') or
                           h.get('quantity') or
                           h.get('FreeQuantity') or
                           h.get('holdingQuantity') or 0)
                    total = int(qty)
                    logger.info("Holdings for %s: qty=%d (raw keys: %s)",
                                symbol, total, list(h.keys()))
                    return total
        logger.warning("Symbol %s not found in %d holdings", symbol, len(holdings))
        if holdings:
            logger.info("Sample holding keys: %s", list(holdings[0].keys()) if isinstance(holdings[0], dict) else type(holdings[0]))
        return 0

    def get_positions(self) -> Dict[str, Any]:
        """Get current positions from XTS (net-wise)."""
        try:
            resp = self.xt.get_position_netwise()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Positions fetch failed: %s", resp)
                return {}
            return resp.get('result', {})
        except Exception as e:
            logger.error("Positions exception: %s", e)
            return {}
