import json
import logging
import datetime
import time
import os
import requests

from kiteconnect import KiteConnect

try:
    from .config import get_config
    from .data_handler import get_data_handler
    from .state_manager import get_state_manager
except ImportError:
    from config import get_config
    from data_handler import get_data_handler
    from state_manager import get_state_manager

logger = logging.getLogger(__name__)

class OrderManager:
    """Manages order placement and tracking"""
    
    def __init__(self):
        self.config = get_config()
        self.data_handler = get_data_handler()
        self.state_manager = get_state_manager()
        
        # API configuration
        self.api_key = self.config.get('API', 'api_key')
        self.access_token = self.config.get('API', 'access_token')
        self.exchange = self.config.get('Trading', 'exchange')
        self.product_type = self.config.get('Trading', 'product_type')
        
        # Zerodha API endpoints
        self.headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }
        self.order_url = "https://api.kite.trade/orders/regular"
        self.gtt_url = "https://api.kite.trade/gtt/triggers"
        
        # Initialize KiteConnect client
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # State file paths
        data_dir = self.config.get('System', 'data_dir', fallback='data')
        self.long_state_file = os.path.join(data_dir, 'long_positions.txt')
        self.short_state_file = os.path.join(data_dir, 'short_positions.txt')
        
    # These methods are no longer needed as the state manager handles this
    # They are kept as no-ops for compatibility
    def init_daily_ticker_tracker(self):
        """Initialize daily tracker of tickers that have been traded"""
        # No-op: handled by state_manager
        pass
        
    def save_daily_ticker_tracker(self, tracker_data):
        """Save the daily ticker tracker data to file"""
        # No-op: handled by state_manager
        pass
    
    def is_ticker_traded_today(self, ticker, position_type="LONG"):
        """Check if a ticker has already been traded today"""
        ticker = ticker.upper()
        try:
            return self.state_manager.is_ticker_traded_today(ticker, position_type.lower())
        except Exception as e:
            logger.exception(f"Error checking if {ticker} was traded today: {e}")
            return False
    
    def mark_ticker_as_traded(self, ticker, position_type="LONG"):
        """Mark a ticker as traded today"""
        ticker = ticker.upper()
        try:
            self.state_manager.add_daily_ticker(ticker, position_type.lower())
            logger.info(f"Marked {ticker} as traded today with position type {position_type}")
        except Exception as e:
            logger.exception(f"Error marking {ticker} as traded: {e}")
    
    def get_instrument_token(self, ticker):
        """Get the instrument token for a ticker"""
        return self.data_handler.get_instrument_token(ticker)
    
    def get_pending_orders(self):
        """Fetch pending orders from KiteConnect"""
        try:
            orders = self.kite.orders()  # returns list of orders
            pending_orders = set()
            # Assuming pending statuses include "OPEN" and "TRIGGER_PENDING"
            for order in orders:
                if order.get("status") in ("OPEN", "TRIGGER_PENDING"):
                    ticker = order.get("tradingsymbol", "").upper()
                    pending_orders.add(ticker)
            return pending_orders
        except Exception as e:
            logger.exception(f"Error fetching pending orders: {e}")
            return set()
    
    def check_existing_gtt_order(self, tradingsymbol, position_type=None):
        """Check if a GTT order already exists for a symbol
           If position_type is specified, also checks that it matches the expected type
        """
        tradingsymbol = tradingsymbol.upper()
        try:
            # First, check the local GTT tracker via state manager
            gtt_data = self.state_manager.get_gtt(tradingsymbol)
            if gtt_data is not None:
                # Check if we have position data to compare with
                position_data = self.state_manager.get_position(tradingsymbol)
                if position_data and position_type:
                    existing_pos_type = position_data.get("type")
                    # If position_type specified, check for conflict
                    if existing_pos_type and position_type != existing_pos_type:
                        logger.warning(f"GTT order exists for {tradingsymbol} but position types conflict: Existing={existing_pos_type}, Requested={position_type}")
                        # Don't allow placing a new order if there's a position type conflict
                        return True
                # If position_type not specified or matches, consider it a match
                return True
            
            # If no match in tracker or tracker doesn't exist, check API directly
            response = requests.get(self.gtt_url, headers=self.headers)
            if response.ok:
                data = response.json()
                triggers = data.get("data", [])
                for trigger in triggers:
                    condition = trigger.get("condition", {})
                    # In case condition is a JSON string, try parsing it
                    if isinstance(condition, str):
                        try:
                            condition = json.loads(condition)
                        except Exception:
                            condition = {}
                            
                    orders_data = trigger.get("orders", [])
                    if isinstance(orders_data, str):
                        try:
                            orders_data = json.loads(orders_data)
                        except Exception:
                            orders_data = []
                    
                    if condition.get("tradingsymbol", "").upper() == tradingsymbol and condition.get("exchange", "") == self.exchange:
                        # If position_type specified, check if it matches the transaction type
                        if position_type and orders_data:
                            transaction_type = orders_data[0].get("transaction_type", "")
                            existing_pos_type = "LONG" if transaction_type == "SELL" else "SHORT"
                            if position_type != existing_pos_type:
                                logger.warning(f"GTT order exists for {tradingsymbol} but position types conflict: Existing={existing_pos_type}, Requested={position_type}")
                                # Don't allow placing a new order if there's a position type conflict
                                return True
                        return True
                return False
            else:
                logger.error(f"Failed to fetch existing GTT orders: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.exception(f"Exception while checking existing GTT orders: {e}")
            return False
    
    def clean_position_trackers(self, ticker, all_types=False):
        """Clean up position tracking for a ticker in all tracking locations
        
        Args:
            ticker: The ticker to clean
            all_types: If True, remove from both LONG and SHORT trackers
        """
        ticker = ticker.upper()
        logger.info(f"Cleaning position trackers for {ticker}")
        
        try:
            # Remove GTT data if exists
            if self.state_manager.get_gtt(ticker) is not None:
                self.state_manager.remove_gtt(ticker)
                logger.info(f"Removed GTT data for {ticker}")
            
            # Remove position completely
            if self.state_manager.get_position(ticker) is not None:
                self.state_manager.remove_position(ticker)
                logger.info(f"Removed position data for {ticker}")
                
            # We don't remove from daily tickers as that's used for tracking which
            # tickers have been traded today, even if the position is closed
            
        except Exception as e:
            logger.error(f"Error cleaning position data for {ticker}: {e}")

    def _clean_position_state_file(self, state_file, ticker):
        """Clean a specific ticker from a position state file"""
        # No-op - handled by state_manager now
        pass
    
    def place_gtt_stoploss_order(self, tradingsymbol, quantity, stop_loss, position_type="LONG", max_retries=3, product_type=None):
        """Place a GTT stop-loss order
        
        Args:
            tradingsymbol: Stock symbol
            quantity: Number of shares
            stop_loss: Stop loss price
            position_type: LONG or SHORT
            max_retries: Number of retries for rate limits
            product_type: Override product type (CNC/MIS) - if not specified, uses position data or self.product_type
        """
        tradingsymbol = tradingsymbol.upper()
        
        # Check for existing GTT order first, before cleaning
        # Pass the position_type to ensure we don't place conflicting orders
        if self.check_existing_gtt_order(tradingsymbol, position_type):
            logger.info(f"Existing SL order found for {position_type} {tradingsymbol}; skipping SL placement.")
            return True  # Successfully skipped (not an error)
        
        # Determine product type to use
        # Priority: 1. Explicitly passed product_type, 2. Position data, 3. Instance default
        if product_type:
            # Use explicitly passed product type
            product_to_use = product_type
        else:
            # Check position data
            position_data = self.state_manager.get_position(tradingsymbol)
            if position_data and position_data.get("product_type"):
                product_to_use = position_data.get("product_type", "MIS").upper()
            else:
                product_to_use = self.product_type
        
        logger.info(f"Placing GTT order for {tradingsymbol} with product type: {product_to_use}")

        ltp = self.data_handler.fetch_current_price(tradingsymbol)
        if ltp is None:
            logger.error(f"Could not fetch real-time LTP for {tradingsymbol}; skipping GTT order.")
            return False  # Failed to place GTT
            
        # IMPORTANT: We should NOT clean position trackers here as that would remove position data
        # This is especially important for CNC positions which must be preserved
        
        # For long positions, the stop-loss is a SELL order when price drops below the trigger
        # For short positions, the stop-loss is a BUY order when price rises above the trigger
        transaction_type = "SELL" if position_type == "LONG" else "BUY"

        condition = {
            "exchange": self.exchange,
            "tradingsymbol": tradingsymbol,
            "trigger_values": [stop_loss],
            "last_price": ltp
        }
        orders = [{
            "exchange": self.exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": "LIMIT",
            "product": product_to_use,  # Use the determined product type
            "price": stop_loss
        }]
        # For CNC positions, make sure the position is created or updated
        if product_to_use == "CNC" and not self.state_manager.get_position(tradingsymbol):
            logger.warning(f"CNC position data for {tradingsymbol} not found. Creating it.")
            self.state_manager.add_position(
                ticker=tradingsymbol,
                position_type=position_type,
                quantity=quantity, 
                entry_price=ltp,  # Use current price as a placeholder
                product_type=product_to_use
            )
        
        payload = {
            "type": "single",  # for a single trigger GTT
            "condition": json.dumps(condition),
            "orders": json.dumps(orders)
        }
        logger.info(f"Placing GTT SL order for {position_type} {tradingsymbol} with payload: {payload}")
        
        for retry in range(max_retries):
            try:
                response = requests.post(self.gtt_url, headers=self.headers, data=payload)
                if response.ok:
                    # Parse the response to get the trigger_id
                    try:
                        response_data = response.json()
                        trigger_id = response_data.get("data", {}).get("trigger_id")
                        if trigger_id:
                            # Update the state manager with GTT info
                            self.state_manager.add_gtt(tradingsymbol, trigger_id, stop_loss)
                            logger.info(f"GTT SL order placed successfully for {tradingsymbol} with trigger_id {trigger_id}")
                        else:
                            logger.warning(f"GTT order placed but no trigger_id found in response: {response.text}")
                    except Exception as e:
                        logger.error(f"Error parsing GTT response: {e}")
                        
                    return True  # Successfully placed GTT
                else:
                    logger.error(f"Failed to place GTT SL order for {tradingsymbol}: {response.status_code} {response.text}")
                    if retry < max_retries - 1:
                        logger.info(f"Retrying GTT order placement in 2 seconds (attempt {retry+1}/{max_retries})")
                        time.sleep(2)  # Wait 2 seconds before retrying
                    else:
                        logger.error(f"Failed to place GTT SL order for {tradingsymbol} after {max_retries} attempts")
                        return False  # Failed to place GTT after max retries
            except Exception as e:
                logger.exception(f"Exception while placing GTT SL order for {tradingsymbol}: {e}")
                if retry < max_retries - 1:
                    logger.info(f"Retrying GTT order placement in 2 seconds after exception (attempt {retry+1}/{max_retries})")
                    time.sleep(2)  # Wait 2 seconds before retrying
                else:
                    logger.error(f"Failed to place GTT SL order for {tradingsymbol} after {max_retries} attempts due to exception")
                    return False  # Failed to place GTT after max retries
    
    def place_order(self, tradingsymbol, transaction_type, order_type, quantity, is_closing_position=False, exit_reason=None, product_type=None):
        """Place a market order
        
        Args:
            tradingsymbol: Stock symbol
            transaction_type: BUY or SELL
            order_type: MARKET or LIMIT
            quantity: Number of shares
            is_closing_position: Whether this is closing an existing position
            exit_reason: Reason for exit if closing
            product_type: Override product type (CNC/MIS) - if not specified, uses self.product_type
        """
        tradingsymbol_upper = tradingsymbol.upper()
        
        # Determine position type (still needed for tracking purposes)
        position_type = "LONG" if transaction_type == "BUY" else "SHORT"
        
        # Use provided product_type or fall back to instance default
        product = product_type if product_type else self.product_type
        
        # If closing a position, save exit details instead of cleaning trackers
        exit_details = {}
        if is_closing_position:
            logger.info(f"Closing position for {tradingsymbol_upper}")
            # Retrieve position data before closing
            position_data = self.state_manager.get_position(tradingsymbol_upper)
            if position_data:
                exit_details["position_data"] = position_data
        
        payload = {
            "tradingsymbol": tradingsymbol,
            "exchange": self.exchange,
            "transaction_type": transaction_type,
            "order_type": order_type,
            "quantity": quantity,
            "product": product,
            "validity": "DAY"
        }
        logger.info(f"Placing {transaction_type} order for {tradingsymbol} with payload: {payload}")
        try:
            response = requests.post(self.order_url, headers=self.headers, data=payload)
            if response.ok:
                # Try to extract order details and confirmation number
                response_data = response.json()
                order_id = response_data.get("data", {}).get("order_id", "unknown")
                logger.info(f"Order placed successfully for {tradingsymbol}: {response.text}")
                
                # Update state based on order type
                if is_closing_position:
                    # Get the current price for exit price
                    exit_price = self.data_handler.fetch_current_price(tradingsymbol_upper)
                    if exit_price is None:
                        logger.warning(f"Could not fetch exit price for {tradingsymbol_upper}, using 0")
                        exit_price = 0
                        
                    # Record exit details instead of just removing
                    self.state_manager.remove_position(
                        ticker=tradingsymbol_upper,
                        exit_price=exit_price,
                        exit_reason=exit_reason or "manual_exit",
                        exit_confirmation=order_id
                    )
                    logger.info(f"Position closed for {tradingsymbol_upper} at {exit_price}, confirmation: {order_id}")
                else:
                    # For new positions
                    # First check if there's a conflicting position
                    existing_position = self.state_manager.get_position(tradingsymbol_upper)
                    if existing_position and existing_position.get("type") != position_type:
                        logger.warning(f"Found conflicting position type for {tradingsymbol_upper}, cleaning up")
                        self.clean_position_trackers(tradingsymbol_upper, all_types=True)
                    
                    # Get the current price for entry
                    entry_price = self.data_handler.fetch_current_price(tradingsymbol_upper)
                    if entry_price is None:
                        logger.warning(f"Could not fetch entry price for {tradingsymbol_upper}, using 0")
                        entry_price = 0
                    
                    # Add to position tracking with confirmation number and product type
                    self.state_manager.add_position(
                        ticker=tradingsymbol_upper,
                        position_type=position_type,
                        quantity=quantity,
                        entry_price=entry_price,
                        timestamp=datetime.datetime.now().isoformat(),
                        confirmation=order_id,
                        product_type=product
                    )
                    
                    # Mark as traded with correct position type (adds to daily tickers)
                    self.mark_ticker_as_traded(tradingsymbol_upper, position_type)
                    
                    logger.info(f"New {position_type} position added for {tradingsymbol_upper} at {entry_price}, confirmation: {order_id}")
                
                return True
            else:
                logger.error(f"Failed to place {transaction_type} order for {tradingsymbol}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.exception(f"Exception while placing {transaction_type} order for {tradingsymbol}: {e}")
            return False
    
    def load_position_state(self, state_file):
        """Legacy method to load position data from state file"""
        # This is kept for backward compatibility but simply delegates to state_manager
        # for the actual implementation
        position_state = {}
        
        # Determine position type from file name
        if "long" in os.path.basename(state_file).lower():
            position_type = "LONG"
        elif "short" in os.path.basename(state_file).lower():
            position_type = "SHORT"
        else:
            return position_state
            
        # Get positions from state manager filtered by type
        positions = self.state_manager.get_positions_by_type(position_type)
        
        # Convert to old format for backward compatibility
        for ticker, data in positions.items():
            timestamp = datetime.datetime.fromisoformat(data.get("timestamp", datetime.datetime.now().isoformat()))
            position_state[ticker] = {
                "quantity": data.get("quantity", 0),
                "timestamp": timestamp
            }
            
        return position_state
    
    def save_position_state(self, state_file, position_state):
        """Legacy method to save position data to state file"""
        # This is kept for backward compatibility but uses state_manager
        # for the actual implementation
        
        # Determine position type from file name
        if "long" in os.path.basename(state_file).lower():
            position_type = "LONG"
        elif "short" in os.path.basename(state_file).lower():
            position_type = "SHORT"
        else:
            logger.warning(f"Unknown position type for file {state_file}, skipping save")
            return
            
        # Update positions in state manager
        for ticker, data in position_state.items():
            quantity = data.get("quantity", 0)
            timestamp = data.get("timestamp", datetime.datetime.now()).isoformat()
            
            # Check if position exists
            position_data = self.state_manager.get_position(ticker)
            if position_data is None:
                # Create new position with defaults
                self.state_manager.add_position(
                    ticker=ticker,
                    position_type=position_type,
                    quantity=quantity,
                    entry_price=0,  # Will be updated later with actual price
                    timestamp=timestamp
                )
            else:
                # Update quantity of existing position
                self.state_manager.update_position_quantity(ticker, quantity)
                
        logger.info(f"Updated {len(position_state)} {position_type.lower()} positions via state manager")
    
    def get_portfolio_positions(self):
        """Get current portfolio positions from Zerodha"""
        try:
            positions_data = self.kite.positions()
            net_positions = positions_data.get("net", [])
            
            long_positions = {}
            short_positions = {}
            
            for pos in net_positions:
                # Only process positions for the configured exchange and product type
                if pos.get("exchange", "") == self.exchange and pos.get("product", "") == self.product_type:
                    qty = pos.get("quantity", 0)
                    ticker = pos.get("tradingsymbol", "").strip().upper()
                    purchase_price = pos.get("average_price", 0)
                    
                    # Skip any problematic CNC positions that might appear in net positions
                    # This is a specific fix for RAYMOND, SANOFI, etc.
                    if ticker in ["RAYMOND", "SANOFI", "BIRLACORPN", "BIRLACORP"]:
                        logger.info(f"Skipping known problematic ticker {ticker} in portfolio positions")
                        continue
                    
                    if qty > 0:
                        long_positions[ticker] = {"quantity": qty, "purchase_price": purchase_price}
                    elif qty < 0:
                        short_positions[ticker] = {"quantity": abs(qty), "purchase_price": purchase_price}
            
            # Log detailed position information
            logger.info(f"Found {len(long_positions)} MIS long positions and {len(short_positions)} MIS short positions")
            
            return long_positions, short_positions
        except Exception as e:
            logger.exception(f"Error fetching portfolio positions: {e}")
            return {}, {}

# Create singleton instance
_order_manager = None

def get_order_manager():
    """Get or create the singleton order manager instance"""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
    return _order_manager
