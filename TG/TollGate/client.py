"""
TollGateClient — Self-contained XTS-only client for TollGate market-making.

Replaces HybridClient (Zerodha + XTS) with a pure XTS implementation:
  - XTS Interactive (REST): orders, cancellations, order book
  - XTS Market Data (WebSocket): real-time LTP/bid/ask for SPCENET

WebSocket design:
  - Bypasses MDSocket_io SDK class (it reads config.ini from cwd which is unreliable).
  - Creates a lightweight socketio.Client directly and listens for 1501-json-full
    (touchline) events for real-time LTP/bid/ask.
  - Runs in a daemon thread started during connect().
  - Main thread reads from a threading.Lock-protected _market_data dict.
  - Fallback: if WebSocket data is stale (>30s), falls back to XTS REST get_quote().

Session file: TG/TollGate/state/.xts_session.json (no monkey-patching needed).
"""

import sys
import os
import json
import time
import threading
import logging
from typing import Optional, List, Dict, Any

import socketio

# Add SDK directory to path for XTS imports
_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sdk')
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

# Exchange name -> XTS exchangeSegment numeric code (for market data)
_EXCHANGE_SEGMENT_NUM = {
    'NSE': 1,
    'NSECM': 1,
    'BSE': 2,
    'BSECM': 2,
}

# Product type mapping
_PRODUCT_MAP = {
    'CNC': 'CNC',
    'NRML': 'NRML',
    'MIS': 'MIS',
}

# Session file for TollGate's separate XTS account
_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
_SESSION_FILE = os.path.join(_STATE_DIR, '.xts_session.json')
_SESSION_MAX_AGE = 8 * 3600  # 8 hours

# Market data staleness threshold
_MARKET_DATA_STALE_SECONDS = 30


class TollGateClient:
    """
    Self-contained XTS client for TollGate.

    Uses XTS Interactive for trading and XTS Market Data WebSocket
    for real-time LTP/bid/ask — no Zerodha dependency.
    """

    def __init__(self, interactive_key: str, interactive_secret: str,
                 marketdata_key: str, marketdata_secret: str,
                 root_url: str = 'https://xts.myfindoc.com',
                 source: str = 'WEBAPI'):
        self.root_url = root_url
        self.source = source

        # XTS Interactive (trading)
        self.xt = XTSConnect(
            apiKey=interactive_key,
            secretKey=interactive_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        # XTS Market Data (quotes + WebSocket)
        self.xt_md = XTSConnect(
            apiKey=marketdata_key,
            secretKey=marketdata_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        self.connected = False
        self.client_id = None

        # Instrument cache: symbol -> exchangeInstrumentID
        self._instrument_cache: Dict[str, int] = {}

        # WebSocket market data
        self._sio: Optional[socketio.Client] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_connected = False
        self._market_data_lock = threading.Lock()
        self._market_data: Dict[str, dict] = {}
        # Each entry: {ltp, best_bid, best_ask, timestamp}

        self._md_token: Optional[str] = None
        self._md_user_id: Optional[str] = None

    def connect(self) -> bool:
        """
        Login to XTS Interactive + Market Data, start WebSocket, subscribe to SPCENET.

        Returns True on success.
        """
        try:
            # --- XTS Interactive: reuse or fresh login ---
            if self._try_reuse_session():
                logger.info("XTS Interactive session reused: userID=%s", self.client_id)
            else:
                resp = self.xt.interactive_login()
                if isinstance(resp, str) or resp.get('type') == 'error':
                    logger.error("XTS Interactive login failed: %s", resp)
                    return False
                self.client_id = resp['result']['userID']
                logger.info("XTS Interactive fresh login OK: userID=%s", self.client_id)
                self._save_session(resp['result']['token'], self.client_id)

            # --- XTS Market Data login ---
            md_resp = self.xt_md.marketdata_login()
            if isinstance(md_resp, str) or md_resp.get('type') == 'error':
                logger.error("XTS Market Data login failed: %s", md_resp)
                return False
            self._md_token = md_resp['result']['token']
            self._md_user_id = md_resp['result']['userID']
            logger.info("XTS Market Data login OK: userID=%s", self._md_user_id)

            # --- Resolve SPCENET instrument ---
            self._resolve_spcenet()

            # --- Start WebSocket for market data ---
            self._start_websocket()

            # --- Subscribe to SPCENET touchline ---
            self._subscribe_spcenet()

            self.connected = True
            return True

        except Exception as e:
            logger.error("TollGateClient connection failed: %s", e, exc_info=True)
            return False

    def _resolve_spcenet(self):
        """Resolve SPCENET instrument ID via search_by_scriptname, cache it."""
        resp = self.xt_md.search_by_scriptname('SPCENET')
        if isinstance(resp, str) or resp.get('type') == 'error':
            logger.error("SPCENET instrument search failed: %s", resp)
            raise RuntimeError(f"Cannot resolve SPCENET: {resp}")

        results = resp.get('result', [])
        if not results:
            raise RuntimeError("SPCENET not found in instrument search")

        # Find NSECM (NSE equity) result
        for inst in results:
            name = inst.get('Description', '') or inst.get('DisplayName', '')
            seg = inst.get('ExchangeSegment', '')
            inst_id = inst.get('ExchangeInstrumentID')
            symbol = inst.get('Name', '') or inst.get('TradingSymbol', '')

            if seg == 'NSECM' and inst_id:
                self._instrument_cache['SPCENET'] = int(inst_id)
                logger.info("Resolved SPCENET: exchangeInstrumentID=%d (segment=%s, name=%s)",
                            int(inst_id), seg, name or symbol)
                return

        # Fallback: take first result
        first = results[0]
        inst_id = first.get('ExchangeInstrumentID')
        if inst_id:
            self._instrument_cache['SPCENET'] = int(inst_id)
            logger.info("Resolved SPCENET (fallback): exchangeInstrumentID=%d", int(inst_id))
        else:
            raise RuntimeError(f"Cannot extract instrument ID from search results: {results[:2]}")

    def _start_websocket(self):
        """Start Socket.IO client for XTS market data in a daemon thread."""
        if self._sio is not None:
            try:
                self._sio.disconnect()
            except Exception:
                pass

        self._sio = socketio.Client(logger=False, engineio_logger=False)

        @self._sio.on('connect')
        def on_connect():
            self._ws_connected = True
            logger.info("Market Data WebSocket connected")

        @self._sio.on('1501-json-full')
        def on_touchline(data):
            self._handle_touchline(data)

        @self._sio.on('disconnect')
        def on_disconnect():
            self._ws_connected = False
            logger.warning("Market Data WebSocket disconnected")

        @self._sio.on('error')
        def on_error(data):
            logger.error("Market Data WebSocket error: %s", data)

        # Build connection URL
        url = (f"{self.root_url}/?token={self._md_token}"
               f"&userID={self._md_user_id}"
               f"&publishFormat=JSON&broadcastMode=Full")

        def ws_runner():
            try:
                self._sio.connect(
                    url,
                    transports=['websocket'],
                    socketio_path='/apimarketdata/socket.io',
                )
                self._sio.wait()
            except Exception as e:
                logger.error("WebSocket thread error: %s", e)
                self._ws_connected = False

        self._ws_thread = threading.Thread(target=ws_runner, daemon=True, name='TollGate-MD-WS')
        self._ws_thread.start()

        # Wait briefly for connection
        for _ in range(20):
            if self._ws_connected:
                break
            time.sleep(0.25)

        if self._ws_connected:
            logger.info("WebSocket connected in background thread")
        else:
            logger.warning("WebSocket did not connect within 5s — will use REST fallback")

    def _subscribe_spcenet(self):
        """Subscribe to SPCENET touchline (1501) via REST API."""
        inst_id = self._instrument_cache.get('SPCENET')
        if inst_id is None:
            logger.error("Cannot subscribe: SPCENET not resolved")
            return

        instruments = [{'exchangeSegment': 1, 'exchangeInstrumentID': inst_id}]
        resp = self.xt_md.send_subscription(instruments, 1501)
        if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
            logger.error("SPCENET subscription failed: %s", resp)
        else:
            logger.info("Subscribed to SPCENET touchline (1501): instrumentID=%d", inst_id)

    def _handle_touchline(self, data: str):
        """Parse 1501-json-full touchline event and update market data cache."""
        try:
            if isinstance(data, str):
                parsed = json.loads(data)
            else:
                parsed = data

            # The touchline data may be a dict or wrapped in a 'Touchline' key
            touchline = parsed.get('Touchline', parsed) if isinstance(parsed, dict) else parsed

            ltp = float(touchline.get('LastTradedPrice', 0) or 0)
            best_bid = float(touchline.get('BidInfo', {}).get('Price', 0) or 0) if isinstance(touchline.get('BidInfo'), dict) else 0.0
            best_ask = float(touchline.get('AskInfo', {}).get('Price', 0) or 0) if isinstance(touchline.get('AskInfo'), dict) else 0.0

            # Some XTS versions use different field names
            if best_bid == 0:
                best_bid = float(touchline.get('BestBidPrice', 0) or 0)
            if best_ask == 0:
                best_ask = float(touchline.get('BestAskPrice', 0) or 0)

            if ltp > 0:
                with self._market_data_lock:
                    self._market_data['SPCENET'] = {
                        'ltp': ltp,
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'timestamp': time.time(),
                    }
                logger.debug("Touchline: LTP=%.2f Bid=%.2f Ask=%.2f", ltp, best_bid, best_ask)
        except Exception as e:
            logger.warning("Touchline parse error: %s (data=%s)", e, str(data)[:200])

    def _get_cached_market_data(self, symbol: str) -> Optional[dict]:
        """Get cached market data if fresh (within staleness threshold)."""
        with self._market_data_lock:
            data = self._market_data.get(symbol)

        if data is None:
            return None

        age = time.time() - data.get('timestamp', 0)
        if age > _MARKET_DATA_STALE_SECONDS:
            logger.debug("Cached data for %s is stale (%.1fs old)", symbol, age)
            return None

        return data

    def _get_rest_quote(self, symbol: str, exchange: str = 'NSE') -> Optional[dict]:
        """Fallback: get quote via XTS REST API."""
        inst_id = self._instrument_cache.get(symbol.upper())
        if inst_id is None:
            logger.error("Cannot get REST quote: %s not resolved", symbol)
            return None

        try:
            seg_num = _EXCHANGE_SEGMENT_NUM.get(exchange, 1)
            instruments = [{'exchangeSegment': seg_num, 'exchangeInstrumentID': inst_id}]
            resp = self.xt_md.get_quote(instruments, xtsMessageCode=1501, publishFormat='JSON')

            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("REST quote failed for %s: %s", symbol, resp)
                return None

            result = resp.get('result', {})
            # Result may contain 'listQuotes' with JSON strings
            quotes = result.get('listQuotes', [])
            if quotes:
                q = json.loads(quotes[0]) if isinstance(quotes[0], str) else quotes[0]
                touchline = q.get('Touchline', q)
                ltp = float(touchline.get('LastTradedPrice', 0) or 0)
                best_bid = float(touchline.get('BidInfo', {}).get('Price', 0) or 0) if isinstance(touchline.get('BidInfo'), dict) else 0.0
                best_ask = float(touchline.get('AskInfo', {}).get('Price', 0) or 0) if isinstance(touchline.get('AskInfo'), dict) else 0.0

                if best_bid == 0:
                    best_bid = float(touchline.get('BestBidPrice', 0) or 0)
                if best_ask == 0:
                    best_ask = float(touchline.get('BestAskPrice', 0) or 0)

                data = {
                    'ltp': ltp,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'timestamp': time.time(),
                }

                # Also update the cache
                with self._market_data_lock:
                    self._market_data[symbol.upper()] = data

                return data

            return None
        except Exception as e:
            logger.error("REST quote exception for %s: %s", symbol, e)
            return None

    # ----- Public market data methods -----

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get last traded price — WebSocket cache first, REST fallback."""
        data = self._get_cached_market_data(symbol.upper())
        if data and data['ltp'] > 0:
            return data['ltp']

        # Fallback to REST
        data = self._get_rest_quote(symbol, exchange)
        if data and data['ltp'] > 0:
            return data['ltp']

        return None

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """
        Get full quote (LTP, bid, ask) — WebSocket cache first, REST fallback.

        Returns dict with keys: ltp, best_bid, best_ask.
        """
        data = self._get_cached_market_data(symbol.upper())
        if data and data['ltp'] > 0:
            return {'ltp': data['ltp'], 'best_bid': data['best_bid'], 'best_ask': data['best_ask']}

        # Fallback to REST
        data = self._get_rest_quote(symbol, exchange)
        if data and data['ltp'] > 0:
            return {'ltp': data['ltp'], 'best_bid': data['best_bid'], 'best_ask': data['best_ask']}

        return None

    def resolve_instrument(self, symbol: str, exchange: str = 'NSE') -> Optional[int]:
        """Resolve a trading symbol to its exchangeInstrumentID."""
        inst_id = self._instrument_cache.get(symbol.upper())
        if inst_id is None:
            logger.error("Could not resolve instrument: %s (not in cache)", symbol)
        return inst_id

    # ----- Trading methods (XTS Interactive) -----

    def place_order(self, symbol: str, transaction_type: str, qty: int,
                    price: float, exchange: str = "NSE",
                    product: str = "NRML",
                    order_unique_id: str = "") -> Optional[str]:
        """Place a LIMIT order via XTS Interactive."""
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
        """Place a market-like order using aggressive LIMIT at LTP +/- slippage."""
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
        Returns None on fetch error (vs [] for empty order book).
        """
        try:
            resp = self.xt.get_order_book()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("Order book fetch failed: %s", resp)
                return None

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

    # ----- Session management -----

    def _try_reuse_session(self) -> bool:
        """Try to reuse an existing XTS Interactive session from file."""
        try:
            if not os.path.exists(_SESSION_FILE):
                return False

            with open(_SESSION_FILE) as f:
                session = json.load(f)

            saved_time = session.get('timestamp', 0)
            if time.time() - saved_time > _SESSION_MAX_AGE:
                logger.info("XTS session file expired (age=%.0f hours)",
                            (time.time() - saved_time) / 3600)
                return False

            token = session.get('token', '')
            user_id = session.get('userID', '')
            if not token or not user_id:
                return False

            is_investor = session.get('isInvestorClient', True)
            self.xt._set_common_variables(token, user_id, is_investor)
            self.client_id = user_id

            # Validate with a lightweight API call
            resp = self.xt.get_order_book()
            if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.info("XTS session file invalid, will re-login")
                return False

            return True

        except Exception as e:
            logger.debug("Session reuse failed: %s", e)
            return False

    def _save_session(self, token: str, user_id: str):
        """Save XTS Interactive session token to file."""
        try:
            os.makedirs(_STATE_DIR, exist_ok=True)
            session = {
                'token': token,
                'userID': user_id,
                'isInvestorClient': getattr(self.xt, 'isInvestorClient', True),
                'timestamp': time.time(),
            }
            tmp = _SESSION_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(session, f)
            os.replace(tmp, _SESSION_FILE)
            logger.info("XTS session saved to %s", _SESSION_FILE)
        except Exception as e:
            logger.warning("Failed to save XTS session: %s", e)

    def refresh_session(self) -> bool:
        """Force a fresh XTS Interactive login and save the new session token."""
        try:
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("XTS session refresh failed: %s", resp)
                return False
            self.client_id = resp['result']['userID']
            self._save_session(resp['result']['token'], self.client_id)
            logger.info("XTS session refreshed: userID=%s", self.client_id)
            return True
        except Exception as e:
            logger.error("XTS session refresh error: %s", e)
            return False

    def stop(self):
        """Disconnect WebSocket and clean up."""
        logger.info("Stopping TollGateClient...")
        if self._sio is not None:
            try:
                self._sio.disconnect()
            except Exception as e:
                logger.debug("WebSocket disconnect error: %s", e)
        self._ws_connected = False
        self.connected = False
        logger.info("TollGateClient stopped")
