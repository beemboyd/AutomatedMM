#!/usr/bin/env python
# update_cnc_stoploss.py - Places server-side GTT stop-loss orders for CNC positions on Zerodha
#
# Standard library imports
import os
import sys
import logging
import datetime
import time
import argparse
import json
import configparser
from decimal import Decimal, ROUND_DOWN

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

# Import required modules if available
try:
    from user_context_manager import (
        get_context_manager,
        get_user_state_manager,
        get_user_data_handler,
        UserCredentials
    )
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False
    # Define UserCredentials class if not imported
    from dataclasses import dataclass
    @dataclass
    class UserCredentials:
        """User API credentials container"""
        name: str
        api_key: str
        api_secret: str
        access_token: str

# Try to import zerodha_handler if available
try:
    from zerodha_handler import get_zerodha_handler
    ZERODHA_HANDLER_AVAILABLE = True
except ImportError:
    ZERODHA_HANDLER_AVAILABLE = False

def load_daily_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")

    config.read(config_path)
    return config

def get_available_users(config):
    """Extract available user credentials from config"""
    users = []
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user_name = section.replace('API_CREDENTIALS_', '')
            api_key = config.get(section, 'api_key', fallback='')
            api_secret = config.get(section, 'api_secret', fallback='')
            access_token = config.get(section, 'access_token', fallback='')

            if api_key and api_secret and access_token:
                users.append(UserCredentials(
                    name=user_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    access_token=access_token
                ))

    return users

def select_user(users):
    """Allow user to select which credentials to use"""
    if not users:
        print("No valid API credentials found in config.ini")
        return None

    print("\nAvailable accounts:")
    for i, user in enumerate(users, 1):
        print(f"{i}. {user.name}")

    while True:
        try:
            choice = int(input(f"\nSelect account (1-{len(users)}): "))
            if 1 <= choice <= len(users):
                return users[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("Please enter a valid number")

def setup_user_context(user_credentials: UserCredentials):
    """Set up user context and logging"""
    # Set user context if available
    if USER_CONTEXT_AVAILABLE:
        try:
            context_manager = get_context_manager()
            context_manager.set_current_user(user_credentials.name, user_credentials)
            print(f"Set current user in context manager to {user_credentials.name}")
        except Exception as e:
            print(f"Warning: Could not set user context: {e}")

    # Set up user-specific logging
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', user_credentials.name)
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, 'update_cnc_stoploss.log'))
        ],
        force=True
    )

    logger = logging.getLogger(__name__)
    logger.info(f"User context set up for: {user_credentials.name}")
    return logger

def get_cnc_positions(force_refresh=False):
    """
    Get all CNC positions directly from Zerodha

    Args:
        force_refresh (bool): Force refresh from API instead of using cache

    Returns:
        dict: Dictionary of CNC positions with ticker as key
    """
    cnc_positions = {}

    # Get user-specific instances
    state_manager = get_user_state_manager()

    # Always get the data from Zerodha first
    try:
        z_handler = get_zerodha_handler()

        # Get holdings (CNC positions)
        holdings = z_handler.get_holdings(force_refresh=force_refresh)

        if holdings:
            logger.info(f"Found {len(holdings)} holdings from Zerodha")
            for holding in holdings:
                ticker = holding.get('tradingsymbol')
                if ticker and holding.get('quantity', 0) > 0:
                    # Get instrument token from the holding if available
                    instrument_token = holding.get('instrument_token')

                    cnc_positions[ticker] = {
                        "type": "LONG",
                        "product_type": "CNC",
                        "entry_price": float(holding.get('average_price', 0)),
                        "quantity": int(holding.get('quantity', 0)),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "last_price": float(holding.get('last_price', 0)),
                        "pnl": float(holding.get('pnl', 0)),
                        "instrument_token": instrument_token,
                        "exchange": "NSE"  # Default to NSE for simplicity
                    }
            logger.info(f"Added {len(cnc_positions)} CNC positions from Zerodha holdings")

        # If still no positions, try getting net positions with CNC filter
        if not cnc_positions:
            positions = z_handler.get_positions(force_refresh=force_refresh)
            net_positions = positions.get('net', []) if positions else []

            if net_positions:
                cnc_net_positions = [p for p in net_positions if p.get('product') == 'CNC' and p.get('quantity', 0) > 0]
                logger.info(f"Found {len(cnc_net_positions)} CNC net positions from Zerodha")

                for position in cnc_net_positions:
                    ticker = position.get('tradingsymbol')
                    if ticker:
                        # Get instrument token from the position if available
                        instrument_token = position.get('instrument_token')

                        cnc_positions[ticker] = {
                            "type": "LONG",
                            "product_type": "CNC",
                            "entry_price": float(position.get('average_price', 0)),
                            "quantity": int(position.get('quantity', 0)),
                            "timestamp": datetime.datetime.now().isoformat(),
                            "last_price": float(position.get('last_price', 0)),
                            "instrument_token": instrument_token,
                            "exchange": "NSE"  # Default to NSE for simplicity
                        }
                logger.info(f"Added {len(cnc_positions)} CNC positions from Zerodha net positions")
    except Exception as e:
        logger.error(f"Error getting CNC positions from Zerodha: {e}")

    # If no positions from Zerodha and we're in test mode, create test data
    if not cnc_positions and (os.environ.get('TEST_MODE') == '1' or '--test' in sys.argv):
        logger.info("Creating test CNC positions")
        test_tickers = ["SBIN", "RELIANCE", "INFY", "TATASTEEL", "HDFCBANK"]
        for ticker in test_tickers:
            cnc_positions[ticker] = {
                "type": "LONG",
                "product_type": "CNC",
                "entry_price": 1000.0,  # Realistic price
                "quantity": 10,
                "timestamp": datetime.datetime.now().isoformat(),
                "last_price": 1050.0,
                "instrument_token": 12345,  # Dummy token
                "exchange": "NSE"
            }
        logger.info(f"Created {len(cnc_positions)} test CNC positions")

    # Update state manager with the positions
    if cnc_positions:
        state_manager = get_user_state_manager()
        for ticker, position in cnc_positions.items():
            # Store in state manager - use the correct method
            if ticker in state_manager.state["positions"]:
                # Update existing position
                state_manager.state["positions"][ticker] = position
            else:
                # Add new position with required parameters
                state_manager.add_position(
                    ticker=ticker,
                    position_type=position.get("type", "LONG"),
                    quantity=position.get("quantity", 0),
                    entry_price=position.get("entry_price", 0),
                    product_type=position.get("product_type", "CNC"),
                    timestamp=position.get("timestamp", None)
                )
        state_manager._save_state()
        logger.info(f"Updated state manager with {len(cnc_positions)} CNC positions")

    return cnc_positions


def get_existing_gtt_orders(ticker=None):
    """
    Get existing GTT orders from Zerodha with detailed information

    Args:
        ticker (str, optional): If provided, filter for this ticker only

    Returns:
        list: List of GTT orders with detailed information
    """
    try:
        z_handler = get_zerodha_handler()
        # Call the kite API directly since the handler may not have this method
        gtt_orders = z_handler.kite.get_gtts()

        # Get individual order details for each GTT to ensure we have complete information
        detailed_orders = []
        for order in gtt_orders:
            try:
                order_id = order.get('id')
                if order_id:
                    # Get the detailed information for this order
                    gtt_detail = z_handler.kite.get_gtt(order_id)
                    if gtt_detail:
                        detailed_orders.append(gtt_detail)
                    else:
                        detailed_orders.append(order)  # Use basic info if detailed fetch fails
                else:
                    detailed_orders.append(order)  # Use basic info if no order ID

                # Add a small delay to avoid API rate limits
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"Error getting details for GTT order {order.get('id')}: {e}")
                detailed_orders.append(order)  # Use basic info if detailed fetch fails

        # Filter by ticker if provided - look in condition.tradingsymbol
        if ticker:
            filtered_orders = []
            for order in detailed_orders:
                # Check if tradingsymbol is in the condition
                condition = order.get('condition', {})
                order_ticker = condition.get('tradingsymbol')
                if order_ticker == ticker:
                    filtered_orders.append(order)
            logger.info(f"Found {len(filtered_orders)} GTT orders for {ticker}")
            return filtered_orders
        else:
            logger.info(f"Found {len(detailed_orders)} GTT orders in total")
            return detailed_orders
    except Exception as e:
        logger.error(f"Error getting GTT orders: {e}")
        return []


def delete_gtt_order(order_id):
    """
    Delete a GTT order by ID

    Args:
        order_id (int): GTT order ID

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        z_handler = get_zerodha_handler()
        # Call the kite API directly
        result = z_handler.kite.delete_gtt(order_id)

        if result:
            logger.info(f"Successfully deleted GTT order {order_id}")
            return True
        else:
            logger.warning(f"Failed to delete GTT order {order_id}")
            return False
    except Exception as e:
        logger.error(f"Error deleting GTT order {order_id}: {e}")
        return False


def place_gtt_order(ticker, trigger_price, quantity, exchange="NSE", order_type="MARKET", current_price=None, force_place=False):
    """
    Place a GTT sell order for a CNC position

    Args:
        ticker (str): Trading symbol
        trigger_price (float): Trigger price for the GTT order
        quantity (int): Quantity to sell
        exchange (str): Exchange (NSE, BSE)
        order_type (str): Order type (MARKET or LIMIT)
        current_price (float): Current price of the stock (for outside market hours)
        force_place (bool): Force placement regardless of market hours

    Returns:
        dict: Order response or None if failed
    """
    try:
        z_handler = get_zerodha_handler()

        # We need to round down the trigger price to the nearest tick
        # For NSE stocks, the tick size is typically 0.05
        # We'll use Decimal for precise rounding
        tick_size = 0.05
        decimal_trigger = Decimal(str(trigger_price))
        decimal_tick = Decimal(str(tick_size))
        rounded_trigger = float((decimal_trigger // decimal_tick) * decimal_tick)

        # If no current price is provided and we have a position with last_price, use that
        if current_price is None and force_place:
            # Try to get the current price from quote API
            try:
                quote = z_handler.kite.quote(f"{exchange}:{ticker}")
                if quote and f"{exchange}:{ticker}" in quote:
                    current_price = quote[f"{exchange}:{ticker}"].get("last_price")
                    logger.info(f"Using current price from quotes API: {current_price} for {ticker}")
            except Exception as e:
                logger.warning(f"Could not get quote for {ticker}: {e}")
        
        # Last resort - use the trigger price as a base and add 20% as a conservative estimate
        if current_price is None and force_place:
            current_price = rounded_trigger * 1.2
            logger.warning(f"Using estimated current price: {current_price} for {ticker} (trigger price +20%)")

        # Set the order price based on order type
        # For LIMIT orders, use 95% of trigger price for a more likely sell
        # For MARKET orders, set price to 0 (required by API)
        order_price = rounded_trigger * 0.95 if order_type == "LIMIT" else 0
        
        # Round the order price to nearest tick
        if order_type == "LIMIT":
            decimal_price = Decimal(str(order_price))
            order_price = float((decimal_price // decimal_tick) * decimal_tick)

        # Create the sell order
        orders = [{
            "exchange": exchange,
            "tradingsymbol": ticker,
            "transaction_type": "SELL",
            "quantity": quantity,
            "order_type": order_type,
            "product": "CNC",
            "price": order_price  # Required by API for both MARKET and LIMIT orders
        }]

        # Place the GTT order using the kite object directly
        # Always attempt to fetch the current price for GTT orders
        last_price_to_use = 0

        # Try to get current price from holdings data
        if force_place:
            # First check if we have a valid current price from arguments
            if current_price and current_price > 0:
                last_price_to_use = current_price
            else:
                # If not, try to get it from quote API
                try:
                    quote = z_handler.kite.quote(f"{exchange}:{ticker}")
                    if quote and f"{exchange}:{ticker}" in quote:
                        last_price = quote[f"{exchange}:{ticker}"].get("last_price")
                        if last_price and last_price > 0:
                            last_price_to_use = last_price
                            logger.info(f"Using current price from quotes API: {last_price_to_use} for {ticker}")
                except Exception as e:
                    logger.warning(f"Could not get quote for {ticker}: {e}")

                # If we still don't have a valid price, try to get historical data
                if last_price_to_use == 0:
                    try:
                        # Get the latest closing price from historical data
                        end_date = datetime.datetime.now()
                        start_date = end_date - datetime.timedelta(days=5)

                        daily_data = z_handler.get_historical_data(
                            ticker,
                            interval="day",
                            from_date=start_date,
                            to_date=end_date
                        )

                        if daily_data and len(daily_data) > 0:
                            # Get the latest day's close price
                            latest_close = daily_data[-1].get('close')
                            if latest_close and latest_close > 0:
                                last_price_to_use = latest_close
                                logger.info(f"Using latest closing price: {last_price_to_use} for {ticker}")
                    except Exception as e:
                        logger.warning(f"Could not get historical data for {ticker}: {e}")

            # Last resort - use 1.5x the trigger price as an estimate
            if last_price_to_use == 0:
                last_price_to_use = rounded_trigger * 1.5
                logger.warning(f"Using estimated current price: {last_price_to_use} for {ticker} (trigger price x1.5)")

        logger.info(f"Using last_price={last_price_to_use} for GTT order on {ticker}")

        # Ensure last_price is at least 5% higher than trigger price
        if last_price_to_use <= rounded_trigger:
            last_price_to_use = rounded_trigger * 1.05
            logger.warning(f"Adjusted last_price to {last_price_to_use} to be above trigger price")

        # Ensure the last_price is a multiple of tick size (0.05 for NSE)
        tick_size = 0.05
        decimal_last_price = Decimal(str(last_price_to_use))
        decimal_tick = Decimal(str(tick_size))
        last_price_to_use = float((decimal_last_price // decimal_tick) * decimal_tick)

        result = z_handler.kite.place_gtt(
            trigger_type="single",  # single trigger
            tradingsymbol=ticker,
            exchange=exchange,
            trigger_values=[rounded_trigger],
            last_price=last_price_to_use,
            orders=orders
        )

        if result and 'trigger_id' in result:
            logger.info(f"Successfully placed GTT order for {ticker}: trigger_id {result['trigger_id']}, "
                      f"trigger price {rounded_trigger}")
            return result
        else:
            logger.warning(f"Failed to place GTT order for {ticker}")
            return None

    except Exception as e:
        logger.error(f"Error placing GTT order for {ticker}: {e}")
        return None

def get_previous_day_low(ticker, max_retries=3):
    """
    Get the previous day's low price for a ticker
    
    Args:
        ticker (str): The trading symbol
        max_retries (int): Number of retries on failure
        
    Returns:
        float: Previous day's low price or None if not available
    """
    # Try using zerodha_handler first if available
    try:
        from zerodha_handler import get_zerodha_handler
        z_handler = get_zerodha_handler()
        
        # Get historical data for the last week to ensure we have previous day
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=7)
        
        daily_data = z_handler.get_historical_data(
            ticker,
            interval="day",
            from_date=start_date,
            to_date=end_date
        )
        
        if daily_data and len(daily_data) > 1:
            # Get the previous day's data (second to last)
            prev_day = daily_data[-2]
            prev_low = prev_day.get('low')
            
            if prev_low is not None:
                logger.info(f"Retrieved previous day's low for {ticker} from Zerodha: {prev_low}")
                return prev_low
    except ImportError:
        logger.debug("Zerodha handler not available, using data_handler instead")
    except Exception as e:
        logger.warning(f"Error getting data from Zerodha: {e}")
    
    # If Zerodha handler wasn't available or failed, use data_handler
    data_handler = get_user_data_handler()
    
    # Try using data_handler's get_previous_candle method first
    prev_candle = data_handler.get_previous_candle(ticker, interval="day", max_retries=max_retries)
    
    if prev_candle:
        logger.info(f"Retrieved previous day's data for {ticker}: Low = {prev_candle['low']}")
        return prev_candle['low']
    
    # If that fails, try fetching historical data directly
    logger.warning(f"Could not get previous candle for {ticker}, trying historical data")
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=5)  # Get 5 days of data
    
    try:
        daily_data = data_handler.fetch_historical_data(
            ticker, 
            interval="day", 
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )
        
        if not daily_data.empty and len(daily_data) > 1:
            # Get the second last row (previous completed day)
            prev_day = daily_data.iloc[-2]
            prev_low = prev_day.get('Low', None)
            if prev_low is not None:
                logger.info(f"Retrieved previous day's low for {ticker} from historical data: Low = {prev_low}")
                return prev_low
    except Exception as e:
        logger.error(f"Error fetching historical data for {ticker}: {e}")
    
    logger.warning(f"Could not retrieve previous day's data for {ticker}")
    return None

def update_stoploss_for_cnc_positions(dry_run=False, test_mode=False, force_refresh=False, force_place=False, cleanup_only=False, symbol=None, force=False, verbose=False):
    """
    Update stoploss GTT orders for all CNC positions using the previous day's low

    IMPORTANT: This function ALWAYS deletes ALL existing GTT orders for a ticker before
    placing a new one to prevent duplicate orders. This ensures each stock has exactly
    one GTT order.

    Args:
        dry_run (bool): If True, don't actually place GTT orders, just log what would be done
        test_mode (bool): If True, use test data
        force_refresh (bool): Force refresh data from API
        force_place (bool): Force placement of GTT orders even outside market hours
                           (may need to provide last_price manually)
        cleanup_only (bool): If True, only clean up duplicate GTT orders without placing new ones

    Returns:
        int: Number of positions updated with GTT orders
    """
    if test_mode:
        os.environ['TEST_MODE'] = '1'

    # 1. Get all CNC positions from Zerodha
    cnc_positions = get_cnc_positions(force_refresh=force_refresh)

    if not cnc_positions:
        logger.info("No CNC positions found. Nothing to update.")
        return 0

    # 2. Get all existing GTT orders and organize by ticker
    existing_gtt_orders = get_existing_gtt_orders()

    # Group GTT orders by ticker
    gtt_orders_by_ticker = {}
    for order in existing_gtt_orders:
        # Check if tradingsymbol is in the condition
        condition = order.get('condition', {})
        ticker = condition.get('tradingsymbol')
        if ticker:
            if ticker not in gtt_orders_by_ticker:
                gtt_orders_by_ticker[ticker] = []
            gtt_orders_by_ticker[ticker].append(order)

    # Statistics for reporting
    updated_count = 0
    failed_count = 0
    unchanged_count = 0
    canceled_count = 0

    # Process each position
    for ticker, position in cnc_positions.items():
        try:
            logger.info(f"Processing CNC position for {ticker}")

            # Skip if not a long position
            if position.get("type", "").upper() != "LONG":
                logger.info(f"Skipping {ticker}: Not a long position ({position.get('type')})")
                continue

            # Get quantity
            quantity = position.get("quantity", 0)
            if quantity <= 0:
                logger.info(f"Skipping {ticker}: Zero or negative quantity ({quantity})")
                continue

            # Get previous day's low price for stoploss
            prev_day_low = get_previous_day_low(ticker)

            if prev_day_low is None:
                logger.warning(f"Skipping {ticker}: Could not retrieve previous day's low")
                failed_count += 1
                continue

            # Round down to nearest 0.05 to ensure valid price point
            prev_day_low_rounded = float(Decimal(str(prev_day_low)).quantize(Decimal('0.05'), rounding=ROUND_DOWN))

            # Get current price
            current_price = position.get("last_price", 0)

            # Sanity check: Make sure the stoploss price is not too close to current price
            # (must be at least 1% lower than current price)
            if current_price > 0 and prev_day_low_rounded > current_price * 0.99:
                adjusted_sl = current_price * 0.95  # Use 5% below current price as fallback
                logger.warning(f"Stoploss for {ticker} ({prev_day_low_rounded}) is too close to current price "
                              f"({current_price}). Adjusting to {adjusted_sl}")
                prev_day_low_rounded = float(Decimal(str(adjusted_sl)).quantize(Decimal('0.05'), rounding=ROUND_DOWN))

            # 3. ALWAYS delete ALL existing GTT orders for this ticker before placing a new one
            if ticker in gtt_orders_by_ticker:
                ticker_gtt_orders = gtt_orders_by_ticker[ticker]
                num_orders = len(ticker_gtt_orders)

                if num_orders > 0:
                    logger.info(f"Found {num_orders} existing GTT orders for {ticker}. Deleting all.")

                    # Delete all existing GTT orders for this ticker
                    if not dry_run:
                        for order in ticker_gtt_orders:
                            order_id = order.get('id')
                            if order_id:
                                if delete_gtt_order(order_id):
                                    canceled_count += 1
                                # Add a small delay to avoid API rate limits
                                time.sleep(0.2)
                    else:
                        logger.info(f"[DRY RUN] Would delete {num_orders} existing GTT orders for {ticker}")
                        canceled_count += num_orders

            # 4. Place new GTT order with the previous day's low as trigger price (skip if cleanup_only is True)
            if cleanup_only:
                logger.info(f"Cleanup-only mode: Skipping placing new GTT order for {ticker}")
                continue

            if not dry_run:
                logger.info(f"Placing GTT order for {ticker} at trigger price {prev_day_low_rounded} for {quantity} shares")
                # Use LIMIT orders for more reliable execution
                order_result = place_gtt_order(
                    ticker=ticker,
                    trigger_price=prev_day_low_rounded,
                    quantity=quantity,
                    exchange=position.get("exchange", "NSE"),
                    order_type="LIMIT",  # LIMIT orders are more reliable for GTT
                    current_price=current_price,
                    force_place=force_place
                )

                if order_result:
                    # Store the GTT order ID in the position data
                    position["gtt_order_id"] = order_result.get("trigger_id")
                    position["stop_loss"] = prev_day_low_rounded
                    position["stop_loss_updated"] = datetime.datetime.now().isoformat()
                    position["stop_loss_source"] = "previous_day_low_gtt"

                    # Update state manager
                    state_manager = get_user_state_manager()
                    if ticker in state_manager.state["positions"]:
                        # Update existing position
                        state_manager.state["positions"][ticker] = position
                    else:
                        # Add new position with required parameters
                        state_manager.add_position(
                            ticker=ticker,
                            position_type=position.get("type", "LONG"),
                            quantity=position.get("quantity", 0),
                            entry_price=position.get("entry_price", 0),
                            product_type=position.get("product_type", "CNC"),
                            timestamp=position.get("timestamp", None)
                        )
                    state_manager._save_state()

                    updated_count += 1
                else:
                    logger.warning(f"Failed to place GTT order for {ticker}")
                    failed_count += 1
            else:
                logger.info(f"[DRY RUN] Would place GTT LIMIT order for {ticker} with trigger price {prev_day_low_rounded} and sell price {prev_day_low_rounded * 0.95:.2f}")
                updated_count += 1

            # Add a small delay to avoid API rate limits
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            failed_count += 1

    logger.info(f"Summary: {updated_count} GTT orders placed, {canceled_count} old orders canceled, "
               f"{unchanged_count} unchanged, {failed_count} failed")

    # Return both updated_count and canceled_count as a tuple
    return (updated_count, canceled_count)

def main():
    """Main function to run the CNC stoploss updater with GTT orders"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update stop-loss orders for CNC positions')
    parser.add_argument('--user', '-u', type=str, help='User to use (default: interactive selection)')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--force', '-f', action='store_true', help='Force update even for existing stop-loss orders')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information for each position')
    parser.add_argument('--symbol', '-s', type=str, help='Update stop-loss for a specific symbol only')
    parser.add_argument('--refresh', '-r', action='store_true', help='Force refresh data from API')
    parser.add_argument('--test', '-t', action='store_true', help='Use test data if no positions are found')
    parser.add_argument('--force-place', action='store_true', help='Try to place orders even outside market hours')
    parser.add_argument('--cleanup-only', action='store_true', help='Only delete duplicate GTT orders')

    args = parser.parse_args()

    print("=== CNC Stop Loss Updater (Multi-User) ===")

    # Load config and get users
    try:
        config = load_daily_config()
        users = get_available_users(config)

        if not users:
            print("No valid API credentials found in config.ini")
            return 1

        # Select user either from command line or interactively
        selected_user = None
        if args.user:
            # Find user by name
            for user in users:
                if user.name.lower() == args.user.lower():
                    selected_user = user
                    break
            if not selected_user:
                print(f"User '{args.user}' not found in config.ini")
                print("Available users:", ", ".join([u.name for u in users]))
                return 1
        else:
            # Interactive selection
            selected_user = select_user(users)
            if not selected_user:
                return 1

        print(f"\nSelected account: {selected_user.name}")

        # Set up user context and logging
        logger = setup_user_context(selected_user)

    except Exception as e:
        print(f"Error setting up user context: {e}")
        return 1

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Update stoploss for CNC positions using server-side GTT orders on Zerodha',
        epilog='This script downloads CNC positions, cancels existing GTT orders, calculates new stop-loss values '
               'based on previous day\'s low, and places new GTT orders on the Zerodha server.'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without making actual changes (simulation mode)')
    parser.add_argument('--test', action='store_true',
                       help='Use test data if no positions found')
    parser.add_argument('--force', action='store_true',
                       help='Force update even if a similar stop-loss order already exists')
    parser.add_argument('--refresh', action='store_true',
                       help='Force refresh data from API instead of using cached data')
    parser.add_argument('--force-place', action='store_true',
                       help='Force placement of GTT orders even outside market hours (recommended to use outside trading hours)')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only clean up duplicate GTT orders without placing new ones (useful for fixing duplicates)')
    parser.add_argument('--loop', action='store_true',
                       help='Run continuously with the specified interval')
    parser.add_argument('--interval', type=int, default=60,
                       help='Interval in minutes between runs when using --loop (default: 60)')
    parser.add_argument('--use-last-price', type=float, default=0,
                       help='Force use of this value as last price for all GTT orders')
    args = parser.parse_args()

    try:
        logger.info(f"Starting CNC stoploss updater for user: {selected_user.name}")
        logger.info(f"API Key in use: {selected_user.api_key[:8]}...")
        logger.info("IMPORTANT: This will delete ALL existing GTT orders for each ticker and create new ones")

        # Display mode information
        if args.dry_run:
            logger.info("Running in dry-run mode - no actual GTT orders will be placed")
        if args.test:
            logger.info("Test mode enabled - will use test data if no positions are found")
        if args.force:
            logger.info("Force mode enabled - will update stoploss even if already set")
        if args.refresh:
            logger.info("Refresh mode enabled - will force refresh data from API")
        if args.force_place:
            logger.info("Force-place mode enabled - will try to place GTT orders even outside market hours")
        if args.cleanup_only:
            logger.info("Cleanup-only mode enabled - will only delete duplicate GTT orders without placing new ones")
        if args.loop:
            logger.info(f"Loop mode enabled - will run every {args.interval} minutes")

        # Function to run a single update cycle
        def run_update_cycle():
            try:
                # Get the result tuple (updated_count, canceled_count)
                # If a specific last price is provided, pass it to all positions
                custom_last_price = args.use_last_price if args.use_last_price > 0 else None

                # Store the original last_price for each position if we're using a custom value
                if custom_last_price:
                    logger.info(f"Using custom last_price={custom_last_price} for all positions")
                    # Get all positions
                    cnc_positions = get_cnc_positions(force_refresh=args.refresh)
                    # Update each position with the custom last_price
                    for ticker, position in cnc_positions.items():
                        position["last_price"] = custom_last_price

                result = update_stoploss_for_cnc_positions(
                    dry_run=args.dry_run,
                    test_mode=args.test if hasattr(args, 'test') else False,
                    force_refresh=args.refresh if hasattr(args, 'refresh') else False,
                    force_place=args.force_place if hasattr(args, 'force_place') else False or custom_last_price is not None,
                    cleanup_only=args.cleanup_only if hasattr(args, 'cleanup_only') else False,
                    symbol=args.symbol if hasattr(args, 'symbol') else None,
                    force=args.force if hasattr(args, 'force') else False,
                    verbose=args.verbose if hasattr(args, 'verbose') else False
                )

                # Unpack the result tuple
                updated_count, canceled_count = result

                if args.cleanup_only:
                    logger.info(f"Successfully cleaned up GTT orders for {canceled_count} positions")
                elif updated_count > 0:
                    logger.info(f"Successfully placed/updated GTT orders for {updated_count} CNC positions")
                else:
                    logger.info("No GTT orders were updated")

                return True
            except Exception as e:
                logger.error(f"Error in update cycle: {e}", exc_info=True)
                return False

        # Run once or in a loop based on arguments
        if args.loop:
            logger.info(f"Starting continuous mode, will run every {args.interval} minutes")

            while True:
                cycle_start = time.time()
                success = run_update_cycle()

                # Calculate time to sleep until next run
                elapsed = time.time() - cycle_start
                sleep_time = max(0, args.interval * 60 - elapsed)

                if sleep_time > 0:
                    next_run = datetime.datetime.now() + datetime.timedelta(seconds=sleep_time)
                    logger.info(f"Next update cycle scheduled at {next_run.strftime('%H:%M:%S')}")
                    time.sleep(sleep_time)
        else:
            # Run once
            run_update_cycle()
            logger.info("CNC stoploss updater completed")

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error in CNC stoploss updater: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    # Print banner
    print("\n" + "="*100)
    print("CNC POSITIONS STOP LOSS UPDATER (MULTI-USER)")
    print("="*100)
    print("This script sets GTT stop-loss orders for all CNC positions from Zerodha broker")
    print("")
    print("Key Features:")
    print("• Sets stop-loss orders for all CNC (delivery) positions")
    print("• Uses previous day's low as a sensible stop-loss level")
    print("• Handles multiple user accounts from config.ini")
    print("• Can be automated or run manually")
    print("• Cleans up duplicate GTT orders automatically")
    print("")
    print("Command-line Options:")
    print("• --user, -u NAME      : Use specific user credentials instead of selecting interactively")
    print("• --dry-run, -d        : Show what would be done without making changes")
    print("• --force, -f          : Force update even for existing stop-loss orders")
    print("• --symbol, -s SYMBOL  : Update stop-loss for a specific symbol only")
    print("• --verbose, -v        : Show detailed information for each position")
    print("• --refresh, -r        : Force refresh data from API")
    print("• --test, -t           : Use test data if no positions are found")
    print("• --force-place        : Try to place orders even outside market hours")
    print("• --cleanup-only       : Only delete duplicate GTT orders")
    print("="*100)

    sys.exit(main())