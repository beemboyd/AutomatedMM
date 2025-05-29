import json
import logging
import os
import datetime
import time
import threading
import requests

from kiteconnect import KiteConnect, KiteTicker

from config import get_config
from data_handler import get_data_handler
from state_manager import get_state_manager

logger = logging.getLogger(__name__)

class RiskManager:
    """Manages risk assessment and trailing stops"""
    
    def __init__(self):
        self.config = get_config()
        self.data_handler = get_data_handler()
        self.state_manager = get_state_manager()
        
        # API configuration
        self.api_key = self.config.get('API', 'api_key')
        self.access_token = self.config.get('API', 'access_token')
        self.exchange = self.config.get('Trading', 'exchange')
        self.product_type = self.config.get('Trading', 'product_type')
        self.profit_target = self.config.get_float('Trading', 'profit_target', fallback=10.0)
        
        # Initialize KiteConnect client
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Zerodha API endpoints
        self.headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }
        self.gtt_url = "https://api.kite.trade/gtt/triggers"
        
        # Initialize ticker manager for real-time data
        self.ticker_manager = None
    
    def load_gtt_tracker(self):
        """Load the GTT tracker data from the state manager"""
        try:
            gtt_data = self.state_manager.get_all_gtts()
            # Format for this class's internal use
            result = {"tickers": {}}
            
            for ticker, gtt_info in gtt_data.items():
                # Get the position type
                position = self.state_manager.get_position(ticker)
                position_type = position.get("type", "UNKNOWN") if position else "UNKNOWN"
                
                result["tickers"][ticker] = {
                    "position_type": position_type,
                    "timestamp": gtt_info.get("timestamp", datetime.datetime.now().isoformat()),
                    "trigger_id": gtt_info.get("trigger_id"),
                    "trigger_price": gtt_info.get("trigger_price")
                }
            
            logger.info(f"Loaded GTT tracker with {len(result['tickers'])} tickers from state manager")
            return result
        except Exception as e:
            logger.exception(f"Error loading GTT tracker: {e}")
            return {"tickers": {}}
    
    def save_gtt_tracker(self, tracker_data):
        """Save the GTT tracker data to state manager"""
        try:
            for ticker, data in tracker_data.get("tickers", {}).items():
                self.state_manager.add_gtt(
                    ticker=ticker,
                    trigger_id=data.get("trigger_id"),
                    trigger_price=data.get("trigger_price")
                )
            logger.info(f"Updated GTT tracker with {len(tracker_data.get('tickers', {}))} tickers in state manager")
        except Exception as e:
            logger.exception(f"Error saving GTT tracker: {e}")
    
    def has_active_gtt(self, ticker, position_type):
        """Check if ticker already has an active GTT for the given position type"""
        ticker = ticker.upper()
        
        # Get GTT data from state manager
        gtt_data = self.state_manager.get_gtt(ticker)
        if gtt_data is None:
            return False
            
        # Get position data to check type
        position = self.state_manager.get_position(ticker)
        if position is None:
            return False
            
        # Check if it was created in the last hour (prevents stale GTTs)
        timestamp = gtt_data.get("timestamp")
        if timestamp:
            try:
                creation_time = datetime.datetime.fromisoformat(timestamp)
                if (datetime.datetime.now() - creation_time).total_seconds() < 3600:
                    saved_type = position.get("type")
                    return saved_type == position_type
            except Exception as e:
                logger.error(f"Error parsing timestamp for {ticker}: {e}")
                
        return False
    
    def register_gtt(self, ticker, position_type, trigger_id=None, trigger_price=None):
        """Register a GTT as created for a ticker"""
        ticker = ticker.upper()
        
        # First ensure position exists with correct type
        position = self.state_manager.get_position(ticker)
        if position is None:
            # Create a basic position entry
            self.state_manager.add_position(
                ticker=ticker,
                position_type=position_type,
                quantity=0,  # Will be updated when actual position data is known
                entry_price=0,  # Will be updated when actual position data is known
                timestamp=datetime.datetime.now().isoformat()
            )
        elif position.get("type") != position_type:
            # Position exists but with wrong type, update it
            logger.warning(f"Position type mismatch for {ticker}: Expected {position_type}, found {position.get('type')}")
            # Need to remove and re-add with correct type
            self.state_manager.remove_position(ticker)
            self.state_manager.add_position(
                ticker=ticker,
                position_type=position_type,
                quantity=position.get("quantity", 0),
                entry_price=position.get("entry_price", 0),
                timestamp=datetime.datetime.now().isoformat()
            )
            
        # Now add the GTT data
        self.state_manager.add_gtt(
            ticker=ticker,
            trigger_id=trigger_id,
            trigger_price=trigger_price
        )
        
        logger.info(f"Registered GTT for {ticker} ({position_type}) with ID: {trigger_id}, price: {trigger_price}")
    
    def clear_gtt_registration(self, ticker):
        """Clear the GTT registration for a ticker"""
        ticker = ticker.upper()
        
        # Remove GTT data through state manager
        if self.state_manager.get_gtt(ticker) is not None:
            self.state_manager.remove_gtt(ticker)
            logger.info(f"Cleared GTT registration for {ticker}")
    
    def get_all_gtt_orders(self):
        """Fetch all existing GTT orders from Zerodha's API"""
        try:
            response = requests.get(self.gtt_url, headers=self.headers)
            if response.ok:
                data = response.json()
                orders = data.get("data", [])
                logger.info(f"Fetched {len(orders)} existing GTT orders.")
                return orders
            else:
                logger.error(f"Failed to fetch GTT orders: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.exception(f"Exception while fetching GTT orders: {e}")
            return []
    
    def delete_gtt_order(self, order_id, ticker=None):
        """Delete a specific GTT order by its order ID"""
        try:
            del_url = f"{self.gtt_url}/{order_id}"
            response = requests.delete(del_url, headers=self.headers)
            if response.ok:
                logger.info(f"GTT order {order_id} deleted successfully.")
                # If ticker is provided, clear the GTT registration
                if ticker:
                    self.clear_gtt_registration(ticker)
                return True
            else:
                logger.error(f"Failed to delete GTT order {order_id}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.exception(f"Exception while deleting GTT order {order_id}: {e}")
            return False
    
    def get_existing_gtt_orders_by_symbol(self):
        """Fetch all existing GTT orders and organize them by symbol"""
        logger.info("Fetching existing GTT orders...")
        orders_by_symbol = {}
        
        all_orders = self.get_all_gtt_orders()
        for order in all_orders:
            order_status = order.get("status", "").lower()
            if order_status == "triggered":
                continue
                
            # Extract order details
            try:
                condition = order.get("condition", {})
                if isinstance(condition, str):
                    condition = json.loads(condition)
                    
                symbol = condition.get("tradingsymbol", "").upper()
                if not symbol:
                    continue
                    
                trigger_id = order.get("trigger_id") or order.get("triggerId") or order.get("id")
                if not trigger_id:
                    logger.warning(f"No valid trigger id found in order: {order}")
                    continue
                    
                # Get transaction type (BUY/SELL) to know if it's for a long or short position
                orders_data = order.get("orders", [])
                if isinstance(orders_data, str):
                    orders_data = json.loads(orders_data)
                    
                if len(orders_data) == 0:
                    continue
                    
                transaction_type = orders_data[0].get("transaction_type", "")
                trigger_price = condition.get("trigger_values", [None])[0]
                quantity = orders_data[0].get("quantity", 0)
                
                # Store order details
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                    
                orders_by_symbol[symbol].append({
                    "trigger_id": trigger_id,
                    "transaction_type": transaction_type,
                    "trigger_price": trigger_price,
                    "quantity": quantity
                })
                
                # Update GTT tracker for this order
                # For stop losses: SELL orders are for LONG positions, BUY orders are for SHORT positions
                # This correctly records the actual position type being protected, not the transaction type of the GTT
                position_type = "LONG" if transaction_type == "SELL" else "SHORT"
                
                # Cross-check with daily tickers from state manager to ensure position type is consistent
                # and we don't register a short stop when the position is actually long 
                try:
                    daily_tickers = self.state_manager.get_daily_tickers()
                    
                    symbol_upper = symbol.upper()
                    # If this symbol is in the long tickers but position_type is SHORT, correct it
                    if position_type == "SHORT" and symbol_upper in daily_tickers.get('long', []):
                        logger.warning(f"GTT position type mismatch for {symbol}: Daily tracker says LONG but GTT is for SHORT - correcting")
                        position_type = "LONG"
                    # If this symbol is in the short tickers but position_type is LONG, correct it
                    elif position_type == "LONG" and symbol_upper in daily_tickers.get('short', []):
                        logger.warning(f"GTT position type mismatch for {symbol}: Daily tracker says SHORT but GTT is for LONG - correcting")
                        position_type = "SHORT"
                except Exception as e:
                    logger.error(f"Error cross-checking GTT position type with state manager: {e}")
                
                self.register_gtt(symbol, position_type, trigger_id, trigger_price)
                
            except Exception as e:
                logger.error(f"Error parsing GTT order: {e}")
                continue
        
        logger.info(f"Found GTT orders for {len(orders_by_symbol)} symbols")
        return orders_by_symbol
    
    def calculate_atr(self, ticker, count=None, interval=None, max_retries=3):
        """Calculate Average True Range (ATR) for volatility-based stop-loss placement
        
        Uses timeframe from config.ini to reduce sensitivity and prevent excessive trading
        """
        # Get ATR parameters from config
        if count is None:
            count = self.config.get_int('Trading', 'risk_atr_periods', fallback=20)
        
        if interval is None:
            interval = self.config.get('Trading', 'risk_atr_timeframe', fallback="15minute")
        
        # Get multiplier from interval for timeframe calculation
        if interval == "5minute":
            minute_multiplier = 5
        elif interval == "15minute":
            minute_multiplier = 15
        elif interval == "30minute":
            minute_multiplier = 30
        elif interval == "60minute" or interval == "1hour":
            minute_multiplier = 60
        else:
            minute_multiplier = 15  # Default to 15 minutes if unknown interval
            
        logger.info(f"Calculating ATR for {ticker} using {interval} candles with {count} periods")
        
        token = self.data_handler.get_instrument_token(ticker)
        if token is None:
            logger.error(f"Token not found for {ticker}. Cannot calculate ATR.")
            return None

        # Default to a simple fixed ATR if all else fails
        default_atr = 0.5  # 0.5% as generic fallback

        # Try current day data
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(minutes=(count + 1) * minute_multiplier)

        retry = 0
        while retry < max_retries:
            try:
                candles = self.kite.historical_data(token, start_date, end_date, interval)
                if len(candles) >= count + 1:
                    tr_values = []
                    for i in range(1, len(candles)):
                        high = candles[i]["high"]
                        low = candles[i]["low"]
                        prev_close = candles[i - 1]["close"]
                        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                        tr_values.append(tr)
                    atr = sum(tr_values[-count:]) / count
                    logger.info(f"Calculated ATR for {ticker}: {atr}")
                    return atr
                else:
                    logger.warning(
                        f"Not enough current day candle data for {ticker} to calculate ATR at interval '{interval}'")
                    break
            except Exception as e:
                retry += 1
                wait_time = 2 ** retry  # Exponential backoff: 2, 4, 8 seconds
                logger.error(f"Error calculating ATR for {ticker}: {e}")
                if retry < max_retries:
                    logger.info(f"Retrying {retry}/{max_retries} after {wait_time} seconds.")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Max retries reached for {ticker}. Using default ATR value: {default_atr}")
                    return default_atr

        # If we reach here, both attempts failed after retries
        logger.warning(f"Could not calculate ATR for {ticker} after all attempts. Using default value: {default_atr}")
        return default_atr
    
    def load_position_data(self):
        """Load position tracking data for trailing stop management"""
        try:
            # Get position data directly from state manager
            data = {}
            positions = self.state_manager.get_all_positions()
            
            # Format for internal use
            for ticker, position in positions.items():
                data[ticker] = {
                    "type": position.get("type", ""),
                    "entry_price": position.get("entry_price", 0),
                    "best_price": position.get("best_price", 0)
                }
                
            logger.info(f"Loaded position tracking data for {len(data)} positions from state manager")
            return data
        except Exception as e:
            logger.error(f"Error loading position data: {e}")
            return {}
    
    def save_position_data(self, position_data):
        """Save position tracking data to state manager"""
        try:
            # Update positions in state manager
            for ticker, data in position_data.items():
                position = self.state_manager.get_position(ticker)
                
                if position is None:
                    # Create new position if it doesn't exist
                    self.state_manager.add_position(
                        ticker=ticker,
                        position_type=data.get("type", "UNKNOWN"),
                        quantity=0,  # Will be updated when actual position data is known
                        entry_price=data.get("entry_price", 0),
                        product_type="MIS",  # Default to MIS for new positions
                        timestamp=datetime.datetime.now().isoformat()
                    )
                
                # Always update best price for trailing stops
                if "best_price" in data:
                    current_best = position.get("best_price", 0) if position else 0
                    new_best = data.get("best_price", current_best)
                    
                    if current_best != new_best:
                        self.state_manager.update_best_price(ticker, new_best)
                        
            logger.info(f"Saved position tracking data for {len(position_data)} positions to state manager")
        except Exception as e:
            logger.error(f"Error saving position data: {e}")
    
    def update_trailing_stop_data(self, position_data, ticker, position_type, current_price, purchase_price):
        """Update trailing stop tracking data based on current price movement"""
        ticker = ticker.upper()
        
        # First update the in-memory position_data for compatibility
        # Initialize if this is a new position
        if ticker not in position_data:
            position_data[ticker] = {
                "type": position_type,
                "entry_price": purchase_price,
                "best_price": current_price
            }
            logger.info(f"Initialized tracking for {position_type} {ticker} at {current_price}")
        else:
            # Update existing position data
            existing_data = position_data[ticker]

            # Check if position type changed (rare, but possible)
            if existing_data["type"] != position_type:
                logger.info(f"Position type changed for {ticker} from {existing_data['type']} to {position_type}. Resetting tracking.")
                position_data[ticker] = {
                    "type": position_type,
                    "entry_price": purchase_price,
                    "best_price": current_price
                }
            else:
                # Update best price if current price is better
                if position_type == "LONG" and current_price > existing_data["best_price"]:
                    old_best = existing_data["best_price"]
                    position_data[ticker]["best_price"] = current_price
                    logger.info(f"Updated best price for LONG {ticker}: {old_best} -> {current_price}")
                elif position_type == "SHORT" and current_price < existing_data["best_price"]:
                    old_best = existing_data["best_price"]
                    position_data[ticker]["best_price"] = current_price
                    logger.info(f"Updated best price for SHORT {ticker}: {old_best} -> {current_price}")
        
        # Now update the state manager version
        position = self.state_manager.get_position(ticker)
        if position is None:
            # Create position if it doesn't exist
            self.state_manager.add_position(
                ticker=ticker,
                position_type=position_type,
                quantity=0,  # Will be updated when position data is available
                entry_price=purchase_price,
                timestamp=datetime.datetime.now().isoformat()
            )
            # Set best price
            self.state_manager.update_best_price(ticker, current_price)
        else:
            # Check if position type in state manager differs
            if position.get("type") != position_type:
                logger.info(f"Position type in state manager differs for {ticker}: {position.get('type')} vs {position_type}")
                # Remove and recreate with correct type
                self.state_manager.remove_position(ticker)
                self.state_manager.add_position(
                    ticker=ticker,
                    position_type=position_type,
                    quantity=position.get("quantity", 0),
                    entry_price=purchase_price,
                    timestamp=datetime.datetime.now().isoformat()
                )
                # Set best price
                self.state_manager.update_best_price(ticker, current_price)
            else:
                # Update best price if needed
                best_price = position.get("best_price", 0)
                if (position_type == "LONG" and current_price > best_price) or \
                   (position_type == "SHORT" and current_price < best_price):
                    self.state_manager.update_best_price(ticker, current_price)
        
        return position_data
    
    def get_previous_candle(self, ticker, interval="60minute", max_retries=3):
        """Get the previous completed candle for a given ticker"""
        token = self.data_handler.get_instrument_token(ticker)
        if token is None:
            logger.error(f"Token not found for {ticker}. Cannot get previous candle.")
            return None
            
        # Calculate start and end times to get the last 2 candles
        end_date = datetime.datetime.now()
        
        # Determine time offset based on interval
        if interval == "5minute":
            start_date = end_date - datetime.timedelta(minutes=15)  # Get last 3 candles
        elif interval == "15minute":
            start_date = end_date - datetime.timedelta(minutes=45)  # Get last 3 candles
        elif interval == "30minute":
            start_date = end_date - datetime.timedelta(minutes=90)  # Get last 3 candles
        elif interval == "60minute" or interval == "1hour":
            start_date = end_date - datetime.timedelta(minutes=180)  # Get last 3 candles
        else:
            start_date = end_date - datetime.timedelta(minutes=180)  # Default to 3x60min
        
        retry = 0
        while retry < max_retries:
            try:
                candles = self.kite.historical_data(token, start_date, end_date, interval)
                if len(candles) >= 2:
                    # Return the previous (second to last) candle
                    return candles[-2]
                elif len(candles) == 1:
                    # Only one candle available, use it
                    logger.warning(f"Only one candle available for {ticker}, using it as previous candle")
                    return candles[0]
                else:
                    logger.warning(f"No candles found for {ticker}")
                    return None
            except Exception as e:
                retry += 1
                wait_time = 2 ** retry  # Exponential backoff
                logger.error(f"Error getting previous candle for {ticker}: {e}")
                if retry < max_retries:
                    logger.info(f"Retrying {retry}/{max_retries} after {wait_time} seconds.")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Max retries reached for {ticker}. Cannot get previous candle.")
                    return None
        
        return None
        
    def calculate_trailing_stop(self, ticker, position_type, current_price, atr, position_data):
        """Calculate trailing stop using previous candle's low/high"""
        # Get the previous candle data
        interval = self.config.get('Trading', 'risk_atr_timeframe', fallback="60minute")
        prev_candle = self.get_previous_candle(ticker, interval=interval)
        
        if prev_candle is None:
            # Fall back to ATR-based stop if we can't get candle data
            logger.warning(f"Could not get previous candle for {ticker}. Falling back to ATR-based stop.")
            if position_type == "LONG":
                return current_price - 1.2 * atr
            else:
                return current_price + 1.2 * atr
        
        best_price = position_data.get(ticker, {}).get("best_price", current_price)
        
        if position_type == "LONG":
            # For longs, use the previous candle's low as stop-loss
            candle_stop = prev_candle["low"]
            
            # If the best price is higher than current price, also consider a trailing stop
            # based on best price to prevent giving back too much profit
            if best_price > current_price:
                best_price_stop = best_price * 0.98  # 2% below best price as safety
                # Use the higher of the two stops (more conservative)
                return max(candle_stop, best_price_stop)
            else:
                return candle_stop
        else:
            # For shorts, use the previous candle's high as stop-loss
            candle_stop = prev_candle["high"]
            
            # If the best price is lower than current price, also consider a trailing stop
            # based on best price to prevent giving back too much profit
            if best_price < current_price:
                best_price_stop = best_price * 1.02  # 2% above best price as safety
                # Use the lower of the two stops (more conservative)
                return min(candle_stop, best_price_stop)
            else:
                return candle_stop
    
    def place_market_order(self, ticker, quantity, transaction_type, max_retries=3):
        """Place an immediate market order when profit target is hit or GTT fails"""
        # First, get access to the order manager to use its cleanup method
        import importlib
        order_manager_module = importlib.import_module('order_manager')
        order_manager = order_manager_module.get_order_manager()
        
        # Clean up ALL trackers for this ticker to prevent position type conflicts
        if order_manager:
            logger.info(f"Cleaning all position trackers for {ticker} before placing market order")
            order_manager.clean_position_trackers(ticker, all_types=True)
        else:
            # Fallback to just clearing GTT registration if order_manager not available
            logger.warning(f"Order manager not available. Only clearing GTT for {ticker}")
            self.clear_gtt_registration(ticker)
        
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                order_id = self.kite.place_order(
                    variety="regular",
                    exchange=self.exchange,
                    tradingsymbol=ticker,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    order_type="MARKET",
                    product=self.product_type,
                    validity="DAY"
                )
                logger.info(f"Market order placed for {ticker} with order id {order_id}.")
                
                # Make extra sure we've cleaned up all trackers after successful order placement
                if order_manager:
                    order_manager.clean_position_trackers(ticker, all_types=True)
                
                return order_id
            except Exception as e:
                retry_count += 1
                logger.error(f"Exception while placing market order for {ticker}: {e}")
                
                if retry_count < max_retries:
                    logger.info(f"Retrying market order for {ticker} (attempt {retry_count}/{max_retries})")
                    time.sleep(1)  # Wait before retrying
                else:
                    logger.error(f"Failed to place market order for {ticker} after {max_retries} attempts")
                    return None
    
    def place_new_gtt_order(self, ticker, quantity, stop_loss, transaction_type, max_adjustments=3, max_retries=3):
        """Place a new GTT (Good-Till-Triggered) stop-loss order"""
        # GTT orders should only be placed on MIS product type
        if self.product_type != "MIS":
            logger.warning(f"GTT orders are only supported for MIS product type. Current product type: {self.product_type}")
            return False
            
        # Register this order creation attempt to avoid duplicates
        position_type = "LONG" if transaction_type == "SELL" else "SHORT"
        
        # Check if we already have a registered GTT for this ticker/position type
        if self.has_active_gtt(ticker, position_type):
            logger.info(f"GTT already registered for {ticker} ({position_type}). Skipping duplicate order placement.")
            return True
        
        ltp = self.data_handler.fetch_current_price(ticker)
        if ltp is None:
            logger.error(f"Could not fetch LTP for {ticker}. Skipping order placement.")
            return False

        # Pre-check if price has already moved past the stop-loss
        if (position_type == "LONG" and ltp <= stop_loss) or (position_type == "SHORT" and ltp >= stop_loss):
            logger.warning(f"Current price ({ltp}) has already crossed stop-loss ({stop_loss}) for {position_type} {ticker}")
            logger.info(f"Placing immediate market order instead of GTT for {ticker}")
            return self.place_market_order(ticker, quantity, transaction_type)

        # Pre-calculate a stop loss that's at least 0.25% away from current price to avoid "too close" errors
        min_required_diff = 0.0025 * ltp  # 0.25% of LTP
        additional_buffer = 0.0005 * ltp  # Extra buffer to be safe (0.05%)

        # Initial adjustment if the calculated stop-loss is too close
        current_diff = abs(ltp - stop_loss)
        if current_diff < min_required_diff:
            # Adjust according to order type
            adjustment_needed = (min_required_diff - current_diff) + additional_buffer

            if transaction_type.upper() == "SELL":  # For long positions
                stop_loss -= adjustment_needed  # Move further down
            else:  # For short positions (BUY)
                stop_loss += adjustment_needed  # Move further up

            logger.info(
                f"Pre-adjusted SL for {ticker} from {current_diff:.4f}% to required 0.25%+. New SL: {stop_loss:.4f}")

        adjustments = 0
        current_stop_loss = stop_loss

        # Round to ensure price is a multiple of tick size (0.05 for most equities)
        tick_size = 0.05
        current_stop_loss = round(current_stop_loss / tick_size) * tick_size
        logger.info(f"Adjusted SL for {ticker} to {current_stop_loss} to match tick size")
        
        # Ensure trigger price is not the same as last price
        if abs(current_stop_loss - ltp) < 0.0001:  # If they're virtually the same
            if transaction_type.upper() == "SELL":  # For long positions
                current_stop_loss -= tick_size  # Move one tick down
            else:  # For short positions (BUY)
                current_stop_loss += tick_size  # Move one tick up
            logger.info(f"Adjusted SL for {ticker} to {current_stop_loss} to avoid equal to last price error")

        while adjustments <= max_adjustments:
            retry_count = 0
            error_msg = ""
            
            while retry_count < max_retries:
                condition = {
                    "exchange": self.exchange,
                    "tradingsymbol": ticker,
                    "trigger_values": [current_stop_loss],
                    "last_price": ltp
                }
                orders = [{
                    "exchange": self.exchange,
                    "tradingsymbol": ticker,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "order_type": "LIMIT",
                    "product": "MIS",  # Ensure product type is always MIS for GTT orders
                    "price": current_stop_loss
                }]
                payload = {
                    "type": "single",  # for a single trigger GTT
                    "condition": json.dumps(condition),
                    "orders": json.dumps(orders)
                }
                logger.info(
                    f"Placing new GTT order for {ticker}: Qty {quantity}, SL: {current_stop_loss}, Transaction: {transaction_type}")
                try:
                    response = requests.post(self.gtt_url, headers=self.headers, data=payload)
                    if response.ok:
                        response_data = response.json()
                        trigger_id = response_data.get("data", {}).get("trigger_id")
                        logger.info(f"GTT order placed for {ticker}: {response.text}")
                        self.register_gtt(ticker, position_type, trigger_id, current_stop_loss)
                        return True
                    else:
                        error_json = response.json()
                        error_msg = error_json.get("message", "")
                        logger.error(f"Failed to place GTT order for {ticker}: {response.status_code} {response.text}")
                        
                        # Handle specific errors
                        if "Trigger cannot be created with trigger price equal to the last price" in error_msg:
                            if transaction_type.upper() == "SELL":  # For long positions
                                current_stop_loss -= tick_size  # Move one tick down
                            else:  # For short positions (BUY)
                                current_stop_loss += tick_size  # Move one tick up
                            logger.info(f"Adjusted SL for {ticker} to {current_stop_loss} to handle equal price error")
                            continue  # Try again immediately with adjusted price
                        
                        if "Trigger price was too close" in error_msg:
                            # Break retry loop and go to adjustment loop
                            break
                        
                        # For other errors, retry up to max_retries times
                        retry_count += 1
                        logger.info(f"Retrying order placement for {ticker} (attempt {retry_count}/{max_retries})")
                        time.sleep(1)  # Wait before retrying
                        
                        if retry_count >= max_retries:
                            logger.error(f"Max retries reached for {ticker}. Moving to next adjustment.")
                            break
                except Exception as e:
                    logger.exception(f"Exception while placing GTT order for {ticker}: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.info(f"Retrying after exception for {ticker} (attempt {retry_count}/{max_retries})")
                        time.sleep(1)
                    else:
                        logger.error(f"Max retries reached after exception for {ticker}")
                        return False
            
            # If we're here either because of "too close" error or max retries reached
            if "Trigger price was too close" in error_msg:
                # If we still get "too close" error, adjust with a larger buffer
                extra_margin = 0.001 * ltp  # 0.1% additional buffer on each retry

                if transaction_type.upper() == "SELL":
                    current_stop_loss -= extra_margin
                else:
                    current_stop_loss += extra_margin

                # Round to ensure price is a multiple of tick size after adjustment
                current_stop_loss = round(current_stop_loss / tick_size) * tick_size
                
                logger.info(
                    f"Adjusted SL for {ticker} to {current_stop_loss} (adjustment {adjustments + 1}) due to trigger price too close.")
                adjustments += 1
                time.sleep(0.5)
            else:
                # If we failed due to other errors after max retries, exit adjustment loop
                logger.error(f"Unknown error for {ticker} after max retries: {error_msg}")
                return False

        logger.error(
            f"Failed to place GTT order for {ticker} after {max_adjustments} adjustments. Falling back to market order.")
        return self.place_market_order(ticker, quantity, transaction_type)

# Create singleton instance
_risk_manager = None

def get_risk_manager():
    """Get or create the singleton risk manager instance"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
