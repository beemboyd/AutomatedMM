"""
AMMClient — Multi-instrument XTS client for AMM stat-arb bot.

Generalized from TollGateClient to handle multiple instruments:
  - XTS Interactive (REST): orders, cancellations, order book
  - XTS Market Data (WebSocket): real-time LTP/bid/ask for all pair tickers

WebSocket design:
  - Creates a lightweight socketio.Client directly and listens for 1501-json-full
    (touchline) events for real-time LTP/bid/ask.
  - Runs in a daemon thread started during connect().
  - Main thread reads from a threading.Lock-protected _market_data dict.
  - Fallback: if WebSocket data is stale (>30s), falls back to XTS REST get_quote().
  - Uses _instrument_id_to_symbol dict for reverse mapping in touchline events.

Session file: TG/state/.xts_session_01MU07.json (shared with TG Grid and TG1)
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

# XTS order status -> normalized status
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
    'NSE': 'NSECM', 'NSECM': 'NSECM',
    'BSE': 'BSECM', 'BSECM': 'BSECM',
    'NFO': 'NSEFO', 'NSEFO': 'NSEFO',
    'MCX': 'MCXFO', 'MCXFO': 'MCXFO',
}

_EXCHANGE_SEGMENT_NUM = {
    'NSE': 1, 'NSECM': 1,
    'BSE': 2, 'BSECM': 2,
}

_PRODUCT_MAP = {'CNC': 'CNC', 'NRML': 'NRML', 'MIS': 'MIS'}

_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
_SESSION_FILE = os.path.join(_STATE_DIR, '.xts_session_01MU07.json')
_SESSION_MAX_AGE = 8 * 3600

_MARKET_DATA_STALE_SECONDS = 30


class AMMClient:
    """
    Multi-instrument XTS client for AMM stat-arb.

    Resolves and subscribes to multiple instruments, provides LTP/quote
    for any resolved symbol, and handles order placement/cancellation.
    """

    def __init__(self, interactive_key: str, interactive_secret: str,
                 marketdata_key: str, marketdata_secret: str,
                 root_url: str = 'https://xts.myfindoc.com',
                 source: str = 'WEBAPI'):
        self.root_url = root_url
        self.source = source

        self.xt = XTSConnect(
            apiKey=interactive_key,
            secretKey=interactive_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        self.xt_md = XTSConnect(
            apiKey=marketdata_key,
            secretKey=marketdata_secret,
            source=source,
            root=root_url,
            disable_ssl=True,
        )

        self.connected = False
        self.client_id = None

        # Instrument caches
        self._instrument_cache: Dict[str, int] = {}          # symbol -> instrumentID
        self._instrument_id_to_symbol: Dict[int, str] = {}   # instrumentID -> symbol

        # WebSocket
        self._sio: Optional[socketio.Client] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_connected = False
        self._market_data_lock = threading.Lock()
        self._market_data: Dict[str, dict] = {}

        self._md_token: Optional[str] = None
        self._md_user_id: Optional[str] = None

    def connect(self, symbols: List[str]) -> bool:
        """
        Login to XTS Interactive + Market Data, resolve instruments,
        start WebSocket, subscribe to all symbols.

        Returns True on success.
        """
        try:
            # XTS Interactive: reuse or fresh login
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

            # XTS Market Data login
            md_resp = self.xt_md.marketdata_login()
            if isinstance(md_resp, str) or md_resp.get('type') == 'error':
                logger.error("XTS Market Data login failed: %s", md_resp)
                return False
            self._md_token = md_resp['result']['token']
            self._md_user_id = md_resp['result']['userID']
            logger.info("XTS Market Data login OK: userID=%s", self._md_user_id)

            # Resolve all instruments
            self._resolve_instruments(symbols)

            # Start WebSocket
            self._start_websocket()

            # Subscribe all
            self._subscribe_all(symbols)

            self.connected = True
            return True

        except Exception as e:
            logger.error("AMMClient connection failed: %s", e, exc_info=True)
            return False

    def _resolve_instruments(self, symbols: List[str]):
        """Resolve multiple symbols via search_by_scriptname, cache IDs."""
        for symbol in symbols:
            sym = symbol.upper()
            if sym in self._instrument_cache:
                continue

            resp = self.xt_md.search_by_scriptname(sym)
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("%s instrument search failed: %s", sym, resp)
                raise RuntimeError(f"Cannot resolve {sym}: {resp}")

            results = resp.get('result', [])
            if not results:
                raise RuntimeError(f"{sym} not found in instrument search")

            # Find NSECM result
            resolved = False
            for inst in results:
                seg = inst.get('ExchangeSegment', '')
                inst_id = inst.get('ExchangeInstrumentID')
                name = inst.get('Description', '') or inst.get('DisplayName', '')

                if seg == 'NSECM' and inst_id:
                    iid = int(inst_id)
                    self._instrument_cache[sym] = iid
                    self._instrument_id_to_symbol[iid] = sym
                    logger.info("Resolved %s: instrumentID=%d (segment=%s, desc=%s)",
                                sym, iid, seg, name)
                    resolved = True
                    break

            if not resolved:
                # Fallback: first result
                first = results[0]
                inst_id = first.get('ExchangeInstrumentID')
                if inst_id:
                    iid = int(inst_id)
                    self._instrument_cache[sym] = iid
                    self._instrument_id_to_symbol[iid] = sym
                    logger.info("Resolved %s (fallback): instrumentID=%d", sym, iid)
                else:
                    raise RuntimeError(f"Cannot extract instrument ID for {sym}: {results[:2]}")

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
            logger.info("AMM Market Data WebSocket connected")

        @self._sio.on('1501-json-full')
        def on_touchline(data):
            self._handle_touchline(data)

        @self._sio.on('disconnect')
        def on_disconnect():
            self._ws_connected = False
            logger.warning("AMM Market Data WebSocket disconnected")

        @self._sio.on('error')
        def on_error(data):
            logger.error("AMM Market Data WebSocket error: %s", data)

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
                logger.error("AMM WebSocket thread error: %s", e)
                self._ws_connected = False

        self._ws_thread = threading.Thread(target=ws_runner, daemon=True, name='AMM-MD-WS')
        self._ws_thread.start()

        for _ in range(20):
            if self._ws_connected:
                break
            time.sleep(0.25)

        if self._ws_connected:
            logger.info("AMM WebSocket connected in background thread")
        else:
            logger.warning("AMM WebSocket did not connect within 5s — will use REST fallback")

    def _subscribe_all(self, symbols: List[str]):
        """Subscribe to touchline (1501) for all resolved instruments."""
        instruments = []
        for sym in symbols:
            sym = sym.upper()
            inst_id = self._instrument_cache.get(sym)
            if inst_id is None:
                logger.error("Cannot subscribe %s: not resolved", sym)
                continue
            instruments.append({'exchangeSegment': 1, 'exchangeInstrumentID': inst_id})

        if not instruments:
            logger.error("No instruments to subscribe")
            return

        resp = self.xt_md.send_subscription(instruments, 1501)
        if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
            logger.error("Subscription failed: %s", resp)
        else:
            syms = ', '.join(symbols)
            logger.info("Subscribed to touchline (1501) for: %s", syms)

    def _handle_touchline(self, data):
        """Parse 1501-json-full touchline event, reverse-lookup instrumentID -> symbol."""
        try:
            if isinstance(data, str):
                parsed = json.loads(data)
            else:
                parsed = data

            touchline = parsed.get('Touchline', parsed) if isinstance(parsed, dict) else parsed

            # Reverse-lookup symbol from instrument ID
            inst_id = parsed.get('ExchangeInstrumentID') or touchline.get('ExchangeInstrumentID')
            if inst_id is not None:
                inst_id = int(inst_id)
            symbol = self._instrument_id_to_symbol.get(inst_id)
            if symbol is None:
                # Try to identify from data fields
                logger.debug("Touchline for unknown instrumentID=%s", inst_id)
                return

            ltp = float(touchline.get('LastTradedPrice', 0) or 0)
            best_bid = 0.0
            best_ask = 0.0

            bid_info = touchline.get('BidInfo')
            ask_info = touchline.get('AskInfo')
            if isinstance(bid_info, dict):
                best_bid = float(bid_info.get('Price', 0) or 0)
            if isinstance(ask_info, dict):
                best_ask = float(ask_info.get('Price', 0) or 0)

            if best_bid == 0:
                best_bid = float(touchline.get('BestBidPrice', 0) or 0)
            if best_ask == 0:
                best_ask = float(touchline.get('BestAskPrice', 0) or 0)

            if ltp > 0:
                with self._market_data_lock:
                    self._market_data[symbol] = {
                        'ltp': ltp,
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'timestamp': time.time(),
                    }
                logger.debug("Touchline %s: LTP=%.2f Bid=%.2f Ask=%.2f",
                             symbol, ltp, best_bid, best_ask)
        except Exception as e:
            logger.warning("Touchline parse error: %s (data=%s)", e, str(data)[:200])

    def _get_cached_market_data(self, symbol: str) -> Optional[dict]:
        """Get cached market data if fresh (within staleness threshold)."""
        with self._market_data_lock:
            data = self._market_data.get(symbol.upper())
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
        data = self._get_rest_quote(symbol, exchange)
        if data and data['ltp'] > 0:
            return data['ltp']
        return None

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, Any]]:
        """Get full quote (LTP, bid, ask) — WebSocket first, REST fallback."""
        data = self._get_cached_market_data(symbol.upper())
        if data and data['ltp'] > 0:
            return {'ltp': data['ltp'], 'best_bid': data['best_bid'], 'best_ask': data['best_ask']}
        data = self._get_rest_quote(symbol, exchange)
        if data and data['ltp'] > 0:
            return {'ltp': data['ltp'], 'best_bid': data['best_bid'], 'best_ask': data['best_ask']}
        return None

    def resolve_instrument(self, symbol: str) -> Optional[int]:
        """Resolve a trading symbol to its exchangeInstrumentID."""
        return self._instrument_cache.get(symbol.upper())

    # ----- Trading methods -----

    def place_order(self, symbol: str, transaction_type: str, qty: int,
                    price: float, exchange: str = "NSE",
                    product: str = "CNC",
                    order_unique_id: str = "") -> Optional[str]:
        """Place a LIMIT order via XTS Interactive."""
        instrument_id = self.resolve_instrument(symbol)
        if instrument_id is None:
            logger.error("ORDER FAILED: cannot resolve %s", symbol)
            return None

        xts_segment = _EXCHANGE_MAP.get(exchange, 'NSECM')
        xts_product = _PRODUCT_MAP.get(product, 'CNC')

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

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order by AppOrderID."""
        try:
            resp = self.xt.cancel_order(
                appOrderID=int(order_id),
                orderUniqueIdentifier=f"CANCEL_{order_id}",
            )
            if isinstance(resp, str) or (isinstance(resp, dict) and resp.get('type') == 'error'):
                logger.error("CANCEL FAILED: %s -> %s", order_id, resp)
                return False
            logger.info("ORDER CANCELLED: %s", order_id)
            return True
        except Exception as e:
            logger.error("CANCEL EXCEPTION: %s -> %s", order_id, e)
            return False

    def get_orders(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all orders for the day from XTS, normalized.

        Returns list of dicts with keys:
            order_id, status, average_price, filled_quantity,
            quantity, status_message, transaction_type, order_unique_id
        Returns None on fetch error.
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
        """Refresh XTS Interactive session, checking shared file first.

        Another bot sharing the same account may have already refreshed.
        Re-read the shared session file before doing a fresh login to
        avoid invalidating another bot's active token (ping-pong).
        """
        try:
            # Step 1: Re-read shared file — another bot may have refreshed
            if self._try_reuse_session():
                logger.info("Picked up refreshed session from shared file")
                return True
            # Step 2: Shared file also invalid — we do the login
            resp = self.xt.interactive_login()
            if isinstance(resp, str) or resp.get('type') == 'error':
                logger.error("XTS session refresh failed: %s", resp)
                return False
            self.client_id = resp['result']['userID']
            self._save_session(resp['result']['token'], self.client_id)
            logger.info("XTS session refreshed (fresh login): userID=%s", self.client_id)
            return True
        except Exception as e:
            logger.error("XTS session refresh error: %s", e)
            return False

    def stop(self):
        """Disconnect WebSocket and clean up."""
        logger.info("Stopping AMMClient...")
        if self._sio is not None:
            try:
                self._sio.disconnect()
            except Exception as e:
                logger.debug("WebSocket disconnect error: %s", e)
        self._ws_connected = False
        self.connected = False
        logger.info("AMMClient stopped")
