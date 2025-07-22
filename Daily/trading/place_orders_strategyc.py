#!/usr/bin/env python
# Standard library imports
import os
import sys
import logging
import datetime
import time
import glob
import pandas as pd
import json
import configparser
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
# Add Daily to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from user_context_manager import (
    get_context_manager,
    get_user_state_manager,
    get_user_order_manager,
    get_user_data_handler,
    UserCredentials
)

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

            if api_key and api_secret and access_token:  # Only include users with all credentials
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
        print("Make sure you have api_key, api_secret, and access_token for at least one user")
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


def setup_user_context(user_credentials: UserCredentials, config):
    """Set up user context using UserContextManager (replaces singleton clearing)"""
    # Set user context - this handles all credential management
    context_manager = get_context_manager()
    context_manager.set_current_user(user_credentials.name, user_credentials)

    # Set up user-specific logging
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(script_dir, 'logs', user_credentials.name)
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, f'place_orders_daily_{user_credentials.name}.log'))
        ],
        force=True
    )

    logger = logging.getLogger(__name__)
    logger.info(f"User context set up for: {user_credentials.name}")

    # Get user-specific instances (guaranteed to be correct user)
    state_manager = get_user_state_manager()
    order_manager = get_user_order_manager()

    # Create temp config for compatibility
    temp_config_data = {
        'DEFAULT': {
            'max_cnc_positions': config.get('DEFAULT', 'max_cnc_positions', fallback='10'),
            'capital_deployment_percent': config.get('DEFAULT', 'capital_deployment_percent', fallback='50.0'),
            'exchange': config.get('DEFAULT', 'exchange', fallback='NSE'),
            'product_type': config.get('DEFAULT', 'product_type', fallback='CNC'),
            'log_level': config.get('DEFAULT', 'log_level', fallback='INFO')
        },
        'Daily': {
            'max_cnc_positions': config.get('DEFAULT', 'max_cnc_positions', fallback='10'),
            'capital_deployment_percent': config.get('DEFAULT', 'capital_deployment_percent', fallback='50.0'),
            'exchange': config.get('DEFAULT', 'exchange', fallback='NSE'),
            'product_type': config.get('DEFAULT', 'product_type', fallback='CNC'),
            'log_level': config.get('DEFAULT', 'log_level', fallback='INFO')
        }
    }

    logger.info(f"API Key in use: {order_manager.data_handler.api_key[:8]}...")

    return order_manager, state_manager, temp_config_data, logger

def get_latest_brooks_file() -> Optional[str]:
    """
    Find the latest StrategyB Report file in the Daily/results directory,
    excluding Weekly analysis files which are handled separately.

    Returns:
        str: Path to the latest StrategyB Report file or None if not found
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(os.path.dirname(script_dir), "results")

        # Get all StrategyB Report files with new naming format
        strategy_b_files = glob.glob(os.path.join(results_dir, "StrategyB_Report_*.xlsx"))
        # Also check for previous format files for backward compatibility
        report_files = glob.glob(os.path.join(results_dir, "Report_*.xlsx"))
        # And old format files for backward compatibility
        old_format_files = glob.glob(os.path.join(results_dir, "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"))
        old_format_files = [f for f in old_format_files if "Weekly" not in os.path.basename(f)]
        
        # Combine all formats
        all_files = strategy_b_files + report_files + old_format_files

        if not all_files:
            logging.error("No StrategyB Report files found in the Daily/results directory")
            return None

        # Sort files by timestamp in filename (newest first)
        # New filename format: Report_YYYYMMDD_HHMMSS.xlsx
        # Old filename format: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
        def extract_timestamp(filename):
            try:
                basename = os.path.basename(filename)
                
                # Check if it's the new StrategyB format or previous Report format
                if basename.startswith("StrategyB_Report_") or basename.startswith("Report_"):
                    # Remove prefix and suffix
                    if basename.startswith("StrategyB_Report_"):
                        timestamp_part = basename.replace("StrategyB_Report_", "").replace(".xlsx", "")
                    else:
                        timestamp_part = basename.replace("Report_", "").replace(".xlsx", "")
                    # Parse timestamp: YYYYMMDD_HHMMSS
                    parts = timestamp_part.split("_")
                    if len(parts) == 2:
                        date_part, time_part = parts
                        # Parse YYYYMMDD
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        # Parse HHMMSS
                        hour = int(time_part[:2])
                        minute = int(time_part[2:4])
                        second = int(time_part[4:6])
                        # Create datetime object for sorting
                        dt = datetime.datetime(year, month, day, hour, minute, second)
                        return dt
                else:
                    # Old format: Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx
                    timestamp_part = basename.replace("Brooks_Higher_Probability_LONG_Reversal_", "").replace(".xlsx", "")
                    # Parse timestamp: DD_MM_YYYY_HH_MM
                    parts = timestamp_part.split("_")
                    if len(parts) == 5:
                        day, month, year, hour, minute = parts
                        # Create datetime object for sorting
                        dt = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                        return dt
            except Exception:
                # If parsing fails, use modification time as fallback
                return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            
            # Default to modification time if parsing fails
            return datetime.datetime.fromtimestamp(os.path.getmtime(filename))

        # Sort by extracted timestamp (newest first)
        all_files.sort(key=extract_timestamp, reverse=True)
        latest_file = all_files[0]

        logging.info(f"Found latest StrategyB Report file: {os.path.basename(latest_file)}")
        return latest_file
    except Exception as e:
        logging.error(f"Error finding latest Brooks file: {e}")
        return None

def get_latest_brooks_weekly_file() -> Optional[str]:
    """
    Find the latest Brooks_Higher_Probability_LONG_Reversal_Weekly file in the Daily/results directory.
    This function specifically searches for weekly analysis files.

    Returns:
        str: Path to the latest Brooks Weekly file or None if not found
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(os.path.dirname(script_dir), "results")

        # Get all Brooks Weekly files
        brooks_weekly_files = glob.glob(os.path.join(results_dir, "Brooks_Higher_Probability_LONG_Reversal_Weekly_*.xlsx"))

        if not brooks_weekly_files:
            logging.error("No Brooks Higher Probability LONG Reversal Weekly files found in the Daily/results directory")
            return None

        # Sort files by timestamp in filename (newest first)
        # Filename format: Brooks_Higher_Probability_LONG_Reversal_Weekly_DD_MM_YYYY_HH_MM.xlsx
        def extract_timestamp(filename):
            try:
                basename = os.path.basename(filename)
                # Remove prefix and suffix
                timestamp_part = basename.replace("Brooks_Higher_Probability_LONG_Reversal_Weekly_", "").replace(".xlsx", "")
                # Parse timestamp: DD_MM_YYYY_HH_MM
                parts = timestamp_part.split("_")
                if len(parts) == 5:
                    day, month, year, hour, minute = parts
                    # Create datetime object for sorting
                    dt = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                    return dt
            except Exception:
                # If parsing fails, use modification time as fallback
                return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            
            # Default to modification time if parsing fails
            return datetime.datetime.fromtimestamp(os.path.getmtime(filename))

        # Sort by extracted timestamp (newest first)
        brooks_weekly_files.sort(key=extract_timestamp, reverse=True)
        latest_weekly_file = brooks_weekly_files[0]

        logging.info(f"Found latest Brooks Weekly file: {os.path.basename(latest_weekly_file)}")
        return latest_weekly_file
    except Exception as e:
        logging.error(f"Error finding latest Brooks Weekly file: {e}")
        return None

def get_previous_day_low(ticker: str, order_manager) -> Optional[float]:
    """
    Get the low of the previous day's candle
    
    Args:
        ticker (str): The stock ticker symbol
        order_manager: Order manager instance
        
    Returns:
        Optional[float]: The low price of the previous day or None if not available
    """
    try:
        data_handler = order_manager.data_handler
        
        # Get current date and date for 5 days ago (to ensure we have enough data)
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=5)
        
        # Fetch daily data
        daily_data = data_handler.fetch_historical_data(
            ticker,
            interval="day",
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )
        
        if daily_data is None or daily_data.empty or len(daily_data) < 2:
            logging.warning(f"Insufficient daily data for {ticker}, need at least 2 days")
            return None
            
        # Get the previous completed day (second to last row)
        prev_day = daily_data.iloc[-2]
        prev_low = float(prev_day.get('Low', 0))
        
        logging.info(f"Previous day's low for {ticker}: {prev_low}")
        return prev_low
        
    except Exception as e:
        logging.error(f"Error getting previous day's low for {ticker}: {e}")
        return None

def check_existing_positions(tickers: List[str], state_manager, order_manager=None) -> List[str]:
    """
    Check which tickers already exist in the portfolio (including T1 holdings)

    Args:
        tickers (List[str]): List of tickers to check
        state_manager: State manager instance
        order_manager: Order manager instance (optional, for broker position check)

    Returns:
        List[str]: List of tickers that already exist in portfolio
    """
    try:
        existing_tickers = []
        
        # First check state manager positions
        for ticker in tickers:
            position = state_manager.get_position(ticker)
            if position and position.get('quantity', 0) > 0:
                existing_tickers.append(ticker)
                logging.info(f"{ticker} already exists in portfolio with quantity: {position.get('quantity', 0)}")
        
        # If order_manager provided, also check broker positions including T1 holdings
        if order_manager and hasattr(order_manager, 'kite'):
            try:
                # Get positions from broker
                positions = order_manager.kite.positions()
                holdings = order_manager.kite.holdings()
                
                # Check net positions
                for pos in positions.get('net', []):
                    symbol = pos.get('tradingsymbol', '')
                    if (symbol in tickers and 
                        pos.get('product') == 'CNC' and 
                        int(pos.get('quantity', 0)) > 0 and 
                        symbol not in existing_tickers):
                        existing_tickers.append(symbol)
                        logging.info(f"{symbol} found in broker positions with quantity: {pos.get('quantity', 0)}")
                
                # Check holdings including T1
                for holding in holdings:
                    symbol = holding.get('tradingsymbol', '')
                    if symbol in tickers and symbol not in existing_tickers:
                        quantity = int(holding.get('quantity', 0))
                        t1_quantity = int(holding.get('t1_quantity', 0))
                        total_quantity = quantity + t1_quantity
                        
                        if total_quantity > 0:
                            existing_tickers.append(symbol)
                            if t1_quantity > 0:
                                logging.info(f"{symbol} found in broker holdings - Settled: {quantity}, T1: {t1_quantity}, Total: {total_quantity}")
                            else:
                                logging.info(f"{symbol} found in broker holdings with quantity: {total_quantity}")
                
            except Exception as e:
                logging.warning(f"Could not check broker positions: {e}")
                # Continue with just state_manager data

        return existing_tickers
    except Exception as e:
        logging.error(f"Error checking existing positions: {e}")
        return []

def get_top_stocks(brooks_file: str, target_positions: int, state_manager, order_manager=None) -> Tuple[List[Dict], List[str]]:
    """
    Extract stocks from the Brooks file in Excel order, taking the first N positions
    
    Note: Stocks are selected based on their order in the Excel file (top to bottom), 
    NOT sorted by Risk_Reward_Ratio. No existing position check is performed.

    Args:
        brooks_file (str): Path to the Brooks file
        target_positions (int): Target number of positions to select
        state_manager: State manager instance (not used, kept for compatibility)
        order_manager: Order manager instance (not used, kept for compatibility)

    Returns:
        Tuple[List[Dict], List[str]]: (List of stock details, Empty list for compatibility)
    """
    try:
        df = pd.read_excel(brooks_file)

        # Ensure required columns exist for Brooks file
        required_columns = ['Ticker', 'Stop_Loss', 'Target1', 'Risk_Reward_Ratio']
        for col in required_columns:
            if col not in df.columns:
                logging.error(f"Required column '{col}' not found in Brooks file. Columns found: {df.columns.tolist()}")
                return [], []

        # Keep the original Excel order - do not sort by Risk_Reward_Ratio
        # This ensures stocks are selected based on their position in the Excel file
        logging.info("Using Excel file order for stock selection (not sorting by Risk_Reward_Ratio)")
        logging.info("No existing position check - will select first N stocks from Excel")

        # Convert to list of dictionaries, taking first N positions
        result = []

        for idx, (_, row) in enumerate(df.iterrows()):
            # Stop if we have enough positions
            if len(result) >= target_positions:
                break

            ticker = row['Ticker']
            stop_loss = float(row['Stop_Loss'])
            target1 = float(row['Target1'])
            risk_reward = float(row['Risk_Reward_Ratio'])

            # Create stock data dictionary
            stock_data = {
                'ticker': ticker,
                'stop_loss': stop_loss,
                'target_price': target1,
                'risk_reward_ratio': risk_reward,
                'entry_price': float(row.get('Entry_Price', 0))
            }

            logging.info(f"Position {idx+1}: {ticker} - SL: {stop_loss}, Target: {target1}, R:R: {risk_reward}")
            result.append(stock_data)

        logging.info(f"Extracted {len(result)} stocks from Brooks file (first {target_positions} positions)")

        return result, []  # Return empty list for skipped_existing for compatibility
    except Exception as e:
        logging.error(f"Error extracting top stocks from Brooks file: {e}")
        return [], []

def get_available_capital(order_manager) -> Optional[float]:
    """
    Get available capital from Zerodha account

    Args:
        order_manager: Order manager instance

    Returns:
        Optional[float]: Available capital or None if not available
    """
    try:
        # Get margin information
        margins = order_manager.kite.margins()

        # Extract available cash from equity segment
        equity_margin = margins.get('equity', {})
        available_cash = equity_margin.get('available', {}).get('cash', 0)

        logging.info(f"Available capital: ₹{available_cash}")
        return float(available_cash)
    except Exception as e:
        logging.error(f"Error getting available capital: {e}")
        return None

def calculate_position_size_from_capital(available_capital: float, current_price: float, num_positions: int, config) -> int:
    """
    Calculate position size based on available capital divided equally among positions

    Args:
        available_capital (float): Total available capital
        current_price (float): Current price of the stock
        num_positions (int): Number of positions to divide capital among
        config: Configuration instance

    Returns:
        int: Number of shares to buy (rounded down to nearest integer)
    """
    if available_capital <= 0 or current_price <= 0:
        logging.warning(f"Invalid capital ({available_capital}) or price ({current_price})")
        return 0

    # Get deployment percentage from config
    deployment_percent = float(config['Daily']['capital_deployment_percent']) / 100.0

    # Use configured percentage of available capital
    usable_capital = available_capital * deployment_percent

    # Calculate capital per position
    capital_per_position = usable_capital / num_positions

    # Calculate position size: capital_per_position / current_price
    position_size = capital_per_position / current_price

    # Round down to nearest integer
    position_size = int(position_size)

    logging.info(f"Usable capital ({deployment_percent*100:.0f}%): ₹{usable_capital:.2f}, Capital per position: ₹{capital_per_position:.2f}, Price: ₹{current_price:.2f}, Shares: {position_size}")

    return position_size

def save_order_information(order_details: List[Dict], brooks_file: str, available_capital: float, usable_capital: float, skipped_existing: List[str], user_name: str, config) -> str:
    """
    Save order information to user-specific Current_Orders folder

    Args:
        order_details (List[Dict]): List of order details
        brooks_file (str): Path to the Brooks file used
        available_capital (float): Total available capital
        usable_capital (float): Capital used for orders
        skipped_existing (List[str]): List of skipped existing tickers
        user_name (str): Name of the user profile
        config: Configuration instance

    Returns:
        str: Path to the saved file
    """
    try:
        # Get deployment percentage from config
        deployment_percent = float(config['Daily']['capital_deployment_percent'])

        # Create user-specific Current_Orders directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        daily_dir = os.path.dirname(script_dir)
        current_orders_dir = os.path.join(daily_dir, "Current_Orders", user_name)
        os.makedirs(current_orders_dir, exist_ok=True)

        # Create timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Prepare summary information
        summary_info = {
            "user_profile": user_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "strategyc_file_used": os.path.basename(brooks_file),
            "available_capital": available_capital,
            "usable_capital": usable_capital,
            "capital_utilization_percent": deployment_percent,
            "total_orders_attempted": len(order_details),
            "successful_orders": len([o for o in order_details if o.get('order_success', False)]),
            "total_investment": sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]),
            "skipped_existing_positions": skipped_existing or [],
            "orders": order_details
        }

        # Save as JSON
        json_filename = f"orders_{user_name}_{timestamp}.json"
        json_filepath = os.path.join(current_orders_dir, json_filename)

        with open(json_filepath, 'w') as f:
            json.dump(summary_info, f, indent=2, default=str)

        # Save as Excel for easy viewing
        excel_filename = f"orders_{user_name}_{timestamp}.xlsx"
        excel_filepath = os.path.join(current_orders_dir, excel_filename)

        # Create DataFrame for Excel
        df_orders = pd.DataFrame(order_details)

        # Create summary sheet data
        skipped_count = len(skipped_existing) if skipped_existing else 0
        summary_data = {
            'Metric': [
                'User Profile',
                'Timestamp',
                'StrategyC File Used',
                'Available Capital',
                f'Usable Capital ({deployment_percent:.0f}%)',
                'Skipped Existing Positions',
                'Total Orders Attempted',
                'Successful Orders',
                'Total Investment',
                'Remaining Capital'
            ],
            'Value': [
                user_name,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                os.path.basename(brooks_file),
                f"₹{available_capital:,.2f}",
                f"₹{usable_capital:,.2f}",
                f"{skipped_count} ({', '.join(skipped_existing) if skipped_existing else 'None'})",
                len(order_details),
                len([o for o in order_details if o.get('order_success', False)]),
                f"₹{sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]):,.2f}",
                f"₹{available_capital - usable_capital:,.2f}"
            ]
        }
        df_summary = pd.DataFrame(summary_data)

        # Write to Excel with multiple sheets
        with pd.ExcelWriter(excel_filepath, engine='openpyxl') as writer:
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            df_orders.to_excel(writer, sheet_name='Order_Details', index=False)

        logging.info(f"Order information saved to: {json_filepath} and {excel_filepath}")
        return excel_filepath

    except Exception as e:
        logging.error(f"Error saving order information: {e}")
        return ""

def place_cnc_orders(stocks: List[Dict], available_capital: float, order_manager, state_manager, config) -> Tuple[List[str], List[Dict]]:
    """
    Place CNC orders for the given stocks using equal capital allocation

    Args:
        stocks (List[Dict]): List of stocks to place orders for
        available_capital (float): Total available capital to divide among positions
        order_manager: Order manager instance
        state_manager: State manager instance
        config: Configuration instance

    Returns:
        Tuple[List[str], List[Dict]]: (List of successful tickers, List of detailed order information)
    """
    data_handler = order_manager.data_handler

    successful_orders = []
    order_details = []
    num_positions = len(stocks)

    for stock in stocks:
        ticker = stock['ticker']
        stop_loss = stock['stop_loss']
        target_price = stock['target_price']
        risk_reward = stock.get('risk_reward_ratio', 0)
        entry_price = stock.get('entry_price', 0)

        # Initialize order detail record
        order_detail = {
            'ticker': ticker,
            'brooks_entry_price': entry_price,
            'stop_loss': stop_loss,
            'target_price': target_price,
            'risk_reward_ratio': risk_reward,
            'order_timestamp': datetime.datetime.now().isoformat(),
            'order_success': False,
            'gtt_success': False,
            'error_message': None
        }

        try:
            # Get current price
            current_price = data_handler.fetch_current_price(ticker)
            if current_price is None:
                order_detail['error_message'] = "Could not fetch current price"
                order_detail['current_price'] = 0
                order_detail['position_size'] = 0
                order_detail['investment_amount'] = 0
                logging.error(f"Could not fetch price for {ticker}, skipping")
                order_details.append(order_detail)
                continue

            order_detail['current_price'] = current_price

            # Calculate position size based on equal capital allocation
            position_size = calculate_position_size_from_capital(available_capital, current_price, num_positions, config)
            if position_size <= 0:
                order_detail['error_message'] = "Position size is 0 or negative"
                order_detail['position_size'] = position_size
                order_detail['investment_amount'] = 0
                logging.warning(f"Calculated position size for {ticker} is 0 or negative, skipping")
                order_details.append(order_detail)
                continue

            # Calculate investment amount
            investment_amount = position_size * current_price
            order_detail['position_size'] = position_size
            order_detail['investment_amount'] = investment_amount

            logging.info(f"Placing CNC order for {ticker}: {position_size} shares at ₹{current_price:.2f} (₹{investment_amount:.2f})")
            logging.info(f"  SL: ₹{stop_loss:.2f}, Target: ₹{target_price:.2f}, R:R: {risk_reward:.1f}")
            logging.info(f"  Product Type: {config['DEFAULT']['product_type']}")

            # Place the order with CNC product type explicitly passed
            success = order_manager.place_order(
                tradingsymbol=ticker,
                transaction_type="BUY",
                order_type="MARKET",
                quantity=position_size,
                is_closing_position=False,
                product_type=config['DEFAULT']['product_type']
            )

            order_detail['order_success'] = success

            if success:
                # Update product type to CNC in the state manager
                position = state_manager.get_position(ticker)
                if position:
                    position["product_type"] = "CNC"
                    # Also add stop loss and target to position data
                    position["stop_loss"] = stop_loss
                    position["target_price"] = target_price
                    position["risk_reward_ratio"] = risk_reward
                    state_manager._save_state()

                logging.info(f"Successfully placed CNC order for {ticker}")
                successful_orders.append(ticker)

                # GTT stop loss orders are no longer created automatically
                # Stop losses are managed by SL_watchdog.py instead
                order_detail['gtt_success'] = False

                # Add a small delay between orders to avoid API rate limits
                time.sleep(1)
            else:
                order_detail['error_message'] = "Failed to place CNC order"
                logging.error(f"Failed to place CNC order for {ticker}")

        except Exception as e:
            order_detail['error_message'] = str(e)
            logging.error(f"Error placing order for {ticker}: {e}")

        order_details.append(order_detail)

    return successful_orders, order_details

def main():
    """Main function to place CNC orders for stocks from the latest Brooks Higher Probability LONG Reversal file"""
    try:
        print("=== CNC Order Placement Tool ===")
        
        # Load Daily config
        config = load_daily_config()
        
        # Get available users
        users = get_available_users(config)
        if not users:
            print("No valid API credentials found in config.ini")
            print("Make sure you have api_key, api_secret, and access_token for at least one user")
            return 1
        
        # Let user select account
        selected_user = select_user(users)
        if not selected_user:
            return 1
        
        user_name = selected_user.name
        print(f"\nSelected account: {user_name}")

        # Set up user context and services
        order_manager, state_manager, temp_config, logger = setup_user_context(selected_user, config)
        
        logger.info("Starting CNC order placement from Brooks Higher Probability LONG Reversal file")

        # Find the latest Brooks file
        brooks_file = get_latest_brooks_file()
        if not brooks_file:
            logger.error("No Brooks Higher Probability LONG Reversal file found, exiting")
            return 1

        # Get available capital
        available_capital = get_available_capital(order_manager)
        if available_capital is None or available_capital <= 0:
            logger.error("Could not get available capital or capital is zero, exiting")
            return 1

        # Get max positions from config
        max_positions = int(temp_config['DEFAULT']['max_cnc_positions'])

        # Get stocks from the Brooks file in Excel order (first N positions)
        stocks_to_buy, _ = get_top_stocks(brooks_file, max_positions, state_manager, order_manager)
        if not stocks_to_buy:
            logger.error("No stocks found in Brooks file, exiting")
            return 1

        num_positions = len(stocks_to_buy)

        # Get deployment percentage from config and calculate usable capital
        deployment_percent = float(temp_config['DEFAULT']['capital_deployment_percent']) / 100.0
        usable_capital = available_capital * deployment_percent
        capital_per_position = usable_capital / num_positions

        # Display the stocks and capital allocation
        print(f"\nAccount: {user_name}")
        print(f"Stocks from {os.path.basename(brooks_file)} (first {max_positions} in Excel order):")
        print(f"Available Capital: ₹{available_capital:,.2f}")
        print(f"Usable Capital ({deployment_percent*100:.0f}%): ₹{usable_capital:,.2f}")
        print(f"Positions to create: {num_positions}")
        print(f"Capital per position: ₹{capital_per_position:,.2f}")
        print("=" * 80)

        for i, stock in enumerate(stocks_to_buy, 1):
            ticker = stock['ticker']
            sl = stock['stop_loss']
            tp = stock['target_price']
            rr = stock['risk_reward_ratio']
            entry = stock.get('entry_price', 0)
            print(f"{i:2d}. {ticker:12s} | Entry: ₹{entry:7.2f} | SL: ₹{sl:7.2f} | Target: ₹{tp:7.2f} | R:R: {rr:4.1f}")

        print("=" * 80)

        # Confirm before placing orders
        confirm = input(f"\nPlace CNC orders for these {num_positions} stocks using {deployment_percent*100:.0f}% of available capital (₹{capital_per_position:,.2f} each)? (y/n): ")
        if confirm.lower() != 'y':
            print("Order placement cancelled by user.")
            return 0

        # Place orders
        logger.info(f"Placing orders for {num_positions} stocks...")
        successful_orders, order_details = place_cnc_orders(stocks_to_buy, available_capital, order_manager, state_manager, temp_config)

        # Save order information to user-specific Current_Orders folder
        logger.info("Saving order information...")
        saved_file = save_order_information(order_details, brooks_file, available_capital, usable_capital, [], user_name, temp_config)

        # Show summary
        total_invested = sum([detail.get('investment_amount', 0) for detail in order_details if detail.get('order_success', False)])

        print(f"\nOrder placement complete for {user_name}!")
        print(f"Successfully placed {len(successful_orders)} out of {num_positions} orders.")
        print(f"Total investment: ₹{total_invested:,.2f} ({deployment_percent*100:.0f}% of available capital)")
        print(f"Remaining capital available: ₹{available_capital - usable_capital:,.2f}")

        if successful_orders:
            print(f"\nSuccessful orders:")
            for ticker in successful_orders:
                # Find the order detail for this ticker
                detail = next((d for d in order_details if d['ticker'] == ticker), {})
                investment = detail.get('investment_amount', 0)
                shares = detail.get('position_size', 0)
                price = detail.get('current_price', 0)
                print(f"  ✓ {ticker}: {shares} shares @ ₹{price:.2f} = ₹{investment:,.2f}")

        failed_orders = [detail for detail in order_details if not detail.get('order_success', False)]
        if failed_orders:
            print(f"\nFailed orders:")
            for detail in failed_orders:
                ticker = detail['ticker']
                error = detail.get('error_message', 'Unknown error')
                print(f"  ✗ {ticker}: {error}")

        # Show order information file location
        if saved_file:
            print(f"\nOrder information saved to: {os.path.basename(saved_file)}")
            print(f"Full path: {saved_file}")

        logger.info("CNC order placement completed")
        return 0

    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
        print("\nProcess interrupted by user.")
        return 0
    except Exception as e:
        logging.exception(f"Error in main function: {e}")
        print(f"An error occurred: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())