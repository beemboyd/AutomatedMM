#!/usr/bin/env python
# Standard library imports
import os
import sys
import logging
import datetime
import time
import pandas as pd
import json
import configparser
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import required modules
from user_context_manager import (
    get_context_manager,
    get_user_state_manager,
    get_user_order_manager,
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
    """Set up user context using UserContextManager"""
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
            logging.FileHandler(os.path.join(log_dir, f'place_orders_consolidated_{user_credentials.name}.log'))
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

def load_consolidated_plan() -> pd.DataFrame:
    """
    Load the Consolidated Plan from Excel file
    
    Returns:
        pd.DataFrame: Dataframe with consolidated plan data
    """
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        plan_file = os.path.join(os.path.dirname(script_dir), "Plan", "Consolidated_Score_Latest.xlsx")
        
        if not os.path.exists(plan_file):
            raise FileNotFoundError(f"Consolidated plan file not found: {plan_file}")
        
        # Read the Excel file
        df = pd.read_excel(plan_file)
        logging.info(f"Loaded consolidated plan with {len(df)} stocks")
        
        return df
    except Exception as e:
        logging.error(f"Error loading consolidated plan: {e}")
        raise

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

def calculate_position_size_by_percentage(available_capital: float, current_price: float, position_percent: float) -> int:
    """
    Calculate position size based on percentage allocation
    
    Args:
        available_capital (float): Total available capital
        current_price (float): Current price of the stock
        position_percent (float): Percentage of capital to allocate (e.g., 5.0 for 5%)
        
    Returns:
        int: Number of shares to buy (rounded down to nearest integer)
    """
    if available_capital <= 0 or current_price <= 0 or position_percent <= 0:
        logging.warning(f"Invalid parameters: capital={available_capital}, price={current_price}, percent={position_percent}")
        return 0
    
    # Calculate capital for this position
    capital_for_position = available_capital * (position_percent / 100.0)
    
    # Calculate position size
    position_size = capital_for_position / current_price
    
    # Round down to nearest integer
    position_size = int(position_size)
    
    logging.info(f"Position allocation: {position_percent}% of ₹{available_capital:.2f} = ₹{capital_for_position:.2f}, Price: ₹{current_price:.2f}, Shares: {position_size}")
    
    return position_size

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

def save_order_information(order_details: List[Dict], plan_file: str, available_capital: float, 
                          deployment_percent: float, skipped_existing: List[str], 
                          user_name: str, config) -> str:
    """
    Save order information to user-specific Current_Orders folder
    
    Args:
        order_details (List[Dict]): List of order details
        plan_file (str): Path to the consolidated plan file used
        available_capital (float): Total available capital
        deployment_percent (float): Percentage of capital to deploy
        skipped_existing (List[str]): List of skipped existing tickers
        user_name (str): Name of the user profile
        config: Configuration instance
        
    Returns:
        str: Path to the saved file
    """
    try:
        # Calculate usable capital
        usable_capital = available_capital * (deployment_percent / 100.0)
        
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
            "plan_file_used": os.path.basename(plan_file),
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
        json_filename = f"orders_consolidated_{user_name}_{timestamp}.json"
        json_filepath = os.path.join(current_orders_dir, json_filename)
        
        with open(json_filepath, 'w') as f:
            json.dump(summary_info, f, indent=2, default=str)
        
        # Save as Excel for easy viewing
        excel_filename = f"orders_consolidated_{user_name}_{timestamp}.xlsx"
        excel_filepath = os.path.join(current_orders_dir, excel_filename)
        
        # Create DataFrame for Excel
        df_orders = pd.DataFrame(order_details)
        
        # Create summary sheet data
        skipped_count = len(skipped_existing) if skipped_existing else 0
        summary_data = {
            'Metric': [
                'User Profile',
                'Timestamp', 
                'Plan File Used',
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
                os.path.basename(plan_file),
                f"₹{available_capital:,.2f}",
                f"₹{usable_capital:,.2f}",
                f"{skipped_count} ({', '.join(skipped_existing) if skipped_existing else 'None'})",
                len(order_details),
                len([o for o in order_details if o.get('order_success', False)]),
                f"₹{sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]):,.2f}",
                f"₹{available_capital - sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]):,.2f}"
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

def place_consolidated_orders(plan_df: pd.DataFrame, available_capital: float, deployment_percent: float,
                            order_manager, state_manager, config) -> Tuple[List[str], List[Dict]]:
    """
    Place CNC orders based on consolidated plan with percentage allocation
    
    Args:
        plan_df (pd.DataFrame): Dataframe with consolidated plan
        available_capital (float): Total available capital
        deployment_percent (float): Percentage of capital to deploy
        order_manager: Order manager instance
        state_manager: State manager instance
        config: Configuration instance
        
    Returns:
        Tuple[List[str], List[Dict]]: (List of successful tickers, List of detailed order information)
    """
    data_handler = order_manager.data_handler
    
    successful_orders = []
    order_details = []
    skipped_existing = []
    
    # Calculate usable capital
    usable_capital = available_capital * (deployment_percent / 100.0)
    
    # Check existing positions first
    all_tickers = plan_df['Ticker'].tolist()
    existing_positions = check_existing_positions(all_tickers, state_manager, order_manager)
    
    for _, row in plan_df.iterrows():
        ticker = row['Ticker']
        position_percent = float(row['Position%'])
        
        # Skip if position already exists
        if ticker in existing_positions:
            logging.info(f"Skipping {ticker} - already exists in portfolio")
            skipped_existing.append(ticker)
            continue
        
        # Initialize order detail record
        order_detail = {
            'ticker': ticker,
            'position_percent': position_percent,
            'order_timestamp': datetime.datetime.now().isoformat(),
            'order_success': False,
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
            
            # Calculate position size based on percentage allocation of USABLE capital
            position_size = calculate_position_size_by_percentage(usable_capital, current_price, position_percent)
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
            
            logging.info(f"Placing CNC order for {ticker}: {position_size} shares at ₹{current_price:.2f} (₹{investment_amount:.2f}) - {position_percent}% allocation")
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
                    state_manager._save_state()
                
                logging.info(f"Successfully placed CNC order for {ticker}")
                successful_orders.append(ticker)
                
                # Add a small delay between orders to avoid API rate limits
                time.sleep(1)
            else:
                order_detail['error_message'] = "Failed to place CNC order"
                logging.error(f"Failed to place CNC order for {ticker}")
                
        except Exception as e:
            order_detail['error_message'] = str(e)
            logging.error(f"Error placing order for {ticker}: {e}")
        
        order_details.append(order_detail)
    
    return successful_orders, order_details, skipped_existing

def main():
    """Main function to place CNC orders based on the Consolidated Plan"""
    try:
        print("=== Consolidated Plan Order Placement Tool ===")
        
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
        
        logger.info("Starting order placement from Consolidated Plan")
        
        # Load the consolidated plan
        try:
            plan_df = load_consolidated_plan()
        except Exception as e:
            logger.error(f"Failed to load consolidated plan: {e}")
            print(f"Error: Could not load Consolidated_Plan_Latest.xlsx")
            return 1
        
        # Get available capital
        available_capital = get_available_capital(order_manager)
        if available_capital is None or available_capital <= 0:
            logger.error("Could not get available capital or capital is zero, exiting")
            return 1
        
        # Get deployment percentage from config
        deployment_percent = float(temp_config['DEFAULT']['capital_deployment_percent'])
        usable_capital = available_capital * (deployment_percent / 100.0)
        
        # Check for existing positions
        all_tickers = plan_df['Ticker'].tolist()
        existing_positions = check_existing_positions(all_tickers, state_manager, order_manager)
        
        # Filter out existing positions from the plan
        filtered_plan_df = plan_df[~plan_df['Ticker'].isin(existing_positions)]
        
        # Display the stocks and capital allocation
        print(f"\nAccount: {user_name}")
        print(f"Stocks from Consolidated Plan:")
        print(f"Available Capital: ₹{available_capital:,.2f}")
        print(f"Usable Capital ({deployment_percent:.0f}%): ₹{usable_capital:,.2f}")
        print(f"Positions to create: {len(filtered_plan_df)} (Skipping {len(existing_positions)} existing positions)")
        print("=" * 80)
        
        # Show existing positions if any
        if existing_positions:
            print(f"\nSkipping existing positions: {', '.join(existing_positions)}")
            print("=" * 80)
        
        print(f"\n{'Rank':>4} {'Ticker':>12} {'Position%':>10} {'Est. Shares':>12} {'Est. Investment':>15}")
        print("-" * 65)
        
        total_est_investment = 0
        for idx, row in filtered_plan_df.iterrows():
            ticker = row['Ticker']
            position_percent = float(row['Position%'])
            
            # Get current price for estimation
            try:
                current_price = order_manager.data_handler.fetch_current_price(ticker)
                if current_price:
                    est_shares = calculate_position_size_by_percentage(usable_capital, current_price, position_percent)
                    est_investment = est_shares * current_price
                    total_est_investment += est_investment
                    print(f"{idx+1:4d} {ticker:>12} {position_percent:>9.2f}% {est_shares:>12d} ₹{est_investment:>14,.2f}")
                else:
                    print(f"{idx+1:4d} {ticker:>12} {position_percent:>9.2f}% {'N/A':>12} {'N/A':>15}")
            except:
                print(f"{idx+1:4d} {ticker:>12} {position_percent:>9.2f}% {'Error':>12} {'Error':>15}")
        
        print("-" * 65)
        print(f"{'Total Estimated Investment:':>39} ₹{total_est_investment:>14,.2f}")
        print("=" * 80)
        
        # Confirm before placing orders
        confirm = input(f"\nPlace CNC orders for these {len(filtered_plan_df)} stocks based on Position% allocation? (y/n): ")
        if confirm.lower() != 'y':
            print("Order placement cancelled by user.")
            return 0
        
        # Place orders
        logger.info(f"Placing orders for {len(filtered_plan_df)} stocks...")
        successful_orders, order_details, skipped_existing = place_consolidated_orders(
            filtered_plan_df, available_capital, deployment_percent, 
            order_manager, state_manager, temp_config
        )
        
        # Save order information to user-specific Current_Orders folder
        logger.info("Saving order information...")
        plan_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                      "Plan", "Consolidated_Plan_Latest.xlsx")
        saved_file = save_order_information(
            order_details, plan_file_path, available_capital, 
            deployment_percent, existing_positions, user_name, temp_config
        )
        
        # Show summary
        total_invested = sum([detail.get('investment_amount', 0) for detail in order_details if detail.get('order_success', False)])
        
        print(f"\nOrder placement complete for {user_name}!")
        print(f"Successfully placed {len(successful_orders)} out of {len(order_details)} orders.")
        print(f"Skipped {len(existing_positions)} existing positions.")
        print(f"Total investment: ₹{total_invested:,.2f}")
        print(f"Remaining capital: ₹{available_capital - total_invested:,.2f}")
        
        if successful_orders:
            print(f"\nSuccessful orders:")
            for ticker in successful_orders:
                # Find the order detail for this ticker
                detail = next((d for d in order_details if d['ticker'] == ticker), {})
                investment = detail.get('investment_amount', 0)
                shares = detail.get('position_size', 0)
                price = detail.get('current_price', 0)
                percent = detail.get('position_percent', 0)
                print(f"  ✓ {ticker}: {shares} shares @ ₹{price:.2f} = ₹{investment:,.2f} ({percent:.2f}%)")
        
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
        
        logger.info("Consolidated plan order placement completed")
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