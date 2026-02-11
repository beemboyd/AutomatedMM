"""
XTS (Symphony Fintech) Client Wrapper for Grid Trading

Wraps the XTS Connect SDK to provide the same interface as the
original Zerodha client. Two XTSConnect instances are maintained:
  - xt_interactive: for order placement, cancellation, order book, positions
  - xt_marketdata:  for LTP quotes, instrument search, master data

Key differences from Zerodha:
  - Instruments are identified by exchangeInstrumentID (numeric), not symbol
  - Two separate logins: interactive + market data
  - Order IDs are AppOrderID (numeric)
  - No CNC product type — use NRML for carry-forward
  - Order statuses: New, Open, Filled, PartiallyFilled, Cancelled, Rejected
"""

import sys
import os
import json
import logging
from typing import Optional, List, Dict, Any

# Add SDK directory to path for XTS imports
_sdk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sdk')
if _sdk_dir not in sys.path:
    sys.path.insert(0, _sdk_dir)

from Connect import XTSConnect

logger = logging.getLogger(__name__)

# XTS order status → normalized status for engine
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

# Exchange name → XTS exchangeSegment string
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

# Exchange segment string → numeric ID (for market data instrument dicts)
_SEGMENT_ID = {
    'NSECM': 1,
    'NSEFO': 2,
    'NSECD': 3,
    'BSECM': 11,
    'BSEFO': 12,
    'MCXFO': 51,
}

# Product type mapping (Zerodha → XTS)
_PRODUCT_MAP = {
    'CNC': 'NRML',     # XTS uses NRML for carry-forward equity
    'NRML': 'NRML',
    'MIS': 'MIS',
}


class XTSClient:
    """
    XTS API client for grid trading.

    Provides the same method signatures as the original Zerodha client
    so bots and engine code require no changes.
    """

    def __init__(self, interactive_key: str, interactive_secret: str,
                 marketdata_key: str, marketdata_secret: str,
                 root_url: str = 'https://developers.symphonyfintech.in',
                 source: str = 'WEBAPI'):
        self.root_url = root_url
        self.source = source

        # Interactive instance (trading)
        self.xt = XTSConnect(
            apiKey=interactive_key,
            secretKey=interactive_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        # Market data instance (quotes, instrument search)
        self.xt_md = XTSConnect(
            apiKey=marketdata_key,
            secretKey=marketdata_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        self.connected = False
        self.client_id = None
        self._instrument_cache: Dict[str, int] = {}  # symbol → exchangeInstrumentID

    def connect(self) -> bool:
        """Login to both interactive and market data sessions."""
        try:
            # Interactive login
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Interactive login failed: %s", resp)
                return False
            self.client_id = resp['result']['userID']
            logger.info("XTS Interactive login OK: userID=%s", self.client_id)

            # Market data login
            resp_md = self.xt_md.marketdata_login()
            if isinstance(resp_md, str) or resp_md.get('type') == 'error':
                logger.error("Market data login failed: %s", resp_md)
                return False
            logger.info("XTS Market data login OK")

            self.connected = True
            return True

        except Exception as e:
            logger.error("XTS connection failed: %s", e)
            return False

    def resolve_instrument(self, symbol: str, exchange: str = 'NSE') -> Optional[int]:
        """
        Resolve a trading symbol to its exchangeInstrumentID.

        Uses search_by_scriptname and caches the result.
        Returns numeric instrument ID or None.
        """
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._instrument_cache:
            return self._instrument_cache[cache_key]

        try:
            resp = self.xt_md.search_by_scriptname(searchString=symbol)
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Instrument search failed for %s: %s", symbol, resp)
                return None

            results = resp.get('result', [])
            segment = _EXCHANGE_MAP.get(exchange, 'NSECM')
            seg_id = _SEGMENT_ID.get(segment, 1)

            # Find exact match for the symbol in the correct exchange
            for item in results:
                # Results can be dicts or strings depending on XTS version
                if isinstance(item, dict):
                    if (item.get('ExchangeSegment') == seg_id and
                            item.get('Name', '').upper() == symbol.upper()):
                        inst_id = int(item['ExchangeInstrumentID'])
                        self._instrument_cache[cache_key] = inst_id
                        logger.info("Resolved %s → exchangeInstrumentID=%d", symbol, inst_id)
                        return inst_id

            # Fallback: try get_equity_symbol
            resp2 = self.xt_md.get_equity_symbol(
                exchangeSegment=seg_id, series='EQ', symbol=symbol)
            if resp2 and resp2.get('type') != 'error' and resp2.get('result'):
                result = resp2['result']
                if isinstance(result, list) and len(result) > 0:
                    inst_id = int(result[0].get('ExchangeInstrumentID',
                                                result[0].get('exchangeInstrumentID', 0)))
                elif isinstance(result, dict):
                    inst_id = int(result.get('ExchangeInstrumentID',
                                            result.get('exchangeInstrumentID', 0)))
                else:
                    inst_id = 0

                if inst_id:
                    self._instrument_cache[cache_key] = inst_id
                    logger.info("Resolved %s via equity_symbol → ID=%d", symbol, inst_id)
                    return inst_id

            logger.error("Could not resolve instrument: %s on %s", symbol, exchange)
            return None

        except Exception as e:
            logger.error("Instrument resolution error for %s: %s", symbol, e)
            return None

    def place_order(self, symbol: str, transaction_type: str, qty: int,
                    price: float, exchange: str = "NSE",
                    product: str = "NRML",
                    order_unique_id: str = "") -> Optional[str]:
        """
        Place a LIMIT order.

        Args:
            symbol: Trading symbol (e.g., "IRFC")
            transaction_type: "BUY" or "SELL"
            qty: Number of shares
            price: Limit price
            exchange: Exchange (default NSE)
            product: Product type (CNC→NRML, MIS, NRML)
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
                apiOrderSource="",
            )

            if isinstance(resp, str):
                logger.error("ORDER FAILED: %s %s %d @ %.2f → %s",
                             transaction_type, symbol, qty, price, resp)
                return None

            if resp.get('type') == 'error':
                logger.error("ORDER FAILED: %s %s %d @ %.2f → %s",
                             transaction_type, symbol, qty, price,
                             resp.get('description', resp))
                return None

            order_id = str(resp['result']['AppOrderID'])
            logger.info("ORDER PLACED: %s %s %d @ %.2f → AppOrderID=%s",
                        transaction_type, symbol, qty, price, order_id)
            return order_id

        except Exception as e:
            logger.error("ORDER EXCEPTION: %s %s %d @ %.2f → %s",
                         transaction_type, symbol, qty, price, e)
            return None

    def cancel_order(self, order_id: str, order_unique_id: str = "") -> bool:
        """Cancel a pending order by AppOrderID."""
        try:
            resp = self.xt.cancel_order(
                appOrderID=int(order_id),
                orderUniqueIdentifier=order_unique_id,
            )
            if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.error("CANCEL FAILED: %s → %s", order_id, resp)
                return False
            logger.info("ORDER CANCELLED: %s", order_id)
            return True
        except Exception as e:
            logger.error("CANCEL EXCEPTION: %s → %s", order_id, e)
            return False

    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all orders for the day, normalized to engine-expected format.

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
                    'average_price': float(o.get('OrderAverageTradedPrice', 0)),
                    'filled_quantity': int(o.get('CumulativeQuantity', 0)),
                    'quantity': int(o.get('OrderQuantity', 0)),
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

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get last traded price via touchline quote."""
        instrument_id = self.resolve_instrument(symbol, exchange)
        if instrument_id is None:
            return None

        seg_id = _SEGMENT_ID.get(_EXCHANGE_MAP.get(exchange, 'NSECM'), 1)

        try:
            resp = self.xt_md.get_quote(
                Instruments=[{
                    'exchangeSegment': seg_id,
                    'exchangeInstrumentID': instrument_id,
                }],
                xtsMessageCode=1501,  # Touchline
                publishFormat='JSON',
            )

            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("LTP fetch failed for %s: %s", symbol, resp)
                return None

            result = resp.get('result', {})
            # Parse touchline data
            if isinstance(result, dict):
                quotes = result.get('listQuotes', [])
            elif isinstance(result, list):
                quotes = result
            else:
                quotes = []

            for q in quotes:
                # Quote data may be a JSON string
                if isinstance(q, str):
                    q = json.loads(q)
                ltp = q.get('LastTradedPrice', q.get('ltp', 0))
                if ltp:
                    return float(ltp)

            return None

        except Exception as e:
            logger.error("LTP exception for %s: %s", symbol, e)
            return None

    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get CNC/delivery holdings."""
        try:
            resp = self.xt.get_holding()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Holdings fetch failed: %s", resp)
                return []
            return resp.get('result', [])
        except Exception as e:
            logger.error("Holdings exception: %s", e)
            return []

    def get_available_qty(self, symbol: str) -> int:
        """Get available quantity of a symbol in holdings."""
        holdings = self.get_holdings()
        if not isinstance(holdings, list):
            return 0
        for h in holdings:
            if isinstance(h, dict):
                holding_symbol = h.get('TradingSymbol', h.get('tradingSymbol', ''))
                if holding_symbol.upper() == symbol.upper():
                    total = int(h.get('Quantity', h.get('quantity', 0)))
                    return total
        return 0

    def get_positions(self) -> Dict[str, Any]:
        """Get current positions (net-wise)."""
        try:
            resp = self.xt.get_position_netwise()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Positions fetch failed: %s", resp)
                return {}
            return resp.get('result', {})
        except Exception as e:
            logger.error("Positions exception: %s", e)
            return {}
