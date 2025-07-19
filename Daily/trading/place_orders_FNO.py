#!/usr/bin/env python
"""
FNO Put Option Selling Script
Sells put options based on KC Upper Limit Trending scanner results from Daily/results
Allocates 2% of capital equally between top 2 tickers
"""

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import required modules
from kiteconnect import KiteConnect
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
            logging.FileHandler(os.path.join(log_dir, f'place_orders_FNO_{user_credentials.name}.log'))
        ],
        force=True
    )

    logger = logging.getLogger(__name__)
    logger.info(f"User context set up for: {user_credentials.name}")
    return logger

def get_latest_fno_file():
    """Get the most recent KC Upper Limit Trending file"""
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    pattern = os.path.join(results_dir, 'KC_Upper_Limit_Trending_*.xlsx')
    files = glob.glob(pattern)
    
    if not files:
        print(f"No KC Upper Limit Trending files found in {results_dir}")
        print("Exiting...")
        sys.exit(0)
    
    # Get the most recent file
    latest_file = max(files, key=os.path.getctime)
    return latest_file

def read_fno_scanner_results(file_path):
    """Read and parse the FNO scanner results"""
    try:
        df = pd.read_excel(file_path)
        
        # The KC_Upper_Limit_Trending file already has the tickers in rank order
        # Preserve the original order instead of re-sorting
        
        # Check if rank column already exists
        if 'rank' not in df.columns:
            # Add a rank column based on current order
            df['rank'] = range(1, len(df) + 1)
        
        # Map column names for compatibility
        df['ticker'] = df['Ticker']
        df['close'] = df['Entry_Price']
        
        # Get score - handle if columns contain string values like "6/6"
        if 'G_Score' in df.columns:
            # Extract numerator from "6/6" format
            df['score'] = df['G_Score'].apply(lambda x: float(str(x).split('/')[0]) if '/' in str(x) else 0)
        elif 'Base_Score' in df.columns:
            df['score'] = pd.to_numeric(df['Base_Score'], errors='coerce').fillna(0)
        else:
            df['score'] = 0
        
        return df
    except Exception as e:
        raise Exception(f"Error reading FNO file: {str(e)}")

def get_strike_price_for_put(kite, ticker, current_price, otm_percent=5):
    """Calculate appropriate strike price for put option selling"""
    # Get OTM strike price (5% below current price by default)
    target_strike = current_price * (1 - otm_percent/100)
    
    # Round to nearest valid strike price based on the stock
    # This is a simplified version - in production, you'd want to fetch actual option chain
    if current_price < 100:
        strike_interval = 2.5
    elif current_price < 500:
        strike_interval = 5
    elif current_price < 1000:
        strike_interval = 10
    elif current_price < 5000:
        strike_interval = 25
    else:
        strike_interval = 50
    
    strike_price = round(target_strike / strike_interval) * strike_interval
    return strike_price

def get_option_symbol(ticker, expiry_date, strike_price, option_type='PE'):
    """Construct option symbol for NFO segment"""
    # Format: SYMBOL YYMMDD STRIKE PE/CE
    # Example: RELIANCE 250731 2800 PE
    expiry_str = expiry_date.strftime('%y%m%d')
    return f"{ticker} {expiry_str} {int(strike_price)} {option_type}"

def get_next_expiry():
    """Get next weekly/monthly expiry date"""
    # This is simplified - in production, you'd fetch actual expiry dates from NSE
    today = datetime.date.today()
    
    # Find next Thursday (weekly expiry)
    days_ahead = 3 - today.weekday()  # Thursday is 3
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    
    next_expiry = today + datetime.timedelta(days_ahead)
    return next_expiry

def place_put_sell_orders(kite, order_manager, tickers_data, capital_per_ticker, logger):
    """Place put option sell orders for selected tickers"""
    orders_placed = []
    
    for _, ticker_data in tickers_data.iterrows():
        ticker = ticker_data['ticker']
        current_price = ticker_data['close']
        
        try:
            # Get strike price and expiry
            strike_price = get_strike_price_for_put(kite, ticker, current_price)
            expiry_date = get_next_expiry()
            option_symbol = get_option_symbol(ticker, expiry_date, strike_price)
            
            # Fetch option price (simplified - in production, fetch actual LTP)
            # For now, estimate premium as 2% of strike price
            estimated_premium = strike_price * 0.02
            
            # Calculate quantity based on capital allocation
            # For put selling, margin requirement is typically 15-20% of contract value
            margin_per_lot = strike_price * ticker_data.get('lot_size', 1) * 0.20
            quantity = int(capital_per_ticker / margin_per_lot) * ticker_data.get('lot_size', 1)
            
            if quantity <= 0:
                logger.warning(f"Insufficient capital for {ticker} put option. Skipping.")
                continue
            
            # Prepare order details
            order_details = {
                'exchange': 'NFO',
                'tradingsymbol': option_symbol,
                'transaction_type': 'SELL',
                'quantity': quantity,
                'product': 'MIS',  # Intraday for options
                'order_type': 'LIMIT',
                'price': estimated_premium,
                'validity': 'DAY',
                'tag': 'FNO_PUT_SELL'
            }
            
            logger.info(f"\nPreparing to sell put option:")
            logger.info(f"  Underlying: {ticker} @ ₹{current_price:.2f}")
            logger.info(f"  Strike: ₹{strike_price}")
            logger.info(f"  Expiry: {expiry_date}")
            logger.info(f"  Quantity: {quantity}")
            logger.info(f"  Premium: ₹{estimated_premium:.2f}")
            logger.info(f"  Total Premium: ₹{estimated_premium * quantity:.2f}")
            logger.info(f"  Margin Required: ₹{margin_per_lot * (quantity / ticker_data.get('lot_size', 1)):.2f}")
            
            orders_placed.append({
                'ticker': ticker,
                'option_symbol': option_symbol,
                'order_details': order_details,
                'margin_required': margin_per_lot * (quantity / ticker_data.get('lot_size', 1))
            })
            
        except Exception as e:
            logger.error(f"Error preparing order for {ticker}: {str(e)}")
            continue
    
    return orders_placed

def main():
    """Main execution function"""
    print("=== FNO Put Option Selling Script ===")
    print("This script sells put options based on KC Upper Limit Trending signals from Daily/results")
    print("Capital allocation: 2% of available capital, split equally between top 2 tickers\n")
    
    try:
        # Load configuration
        config = load_daily_config()
        
        # Get available users
        users = get_available_users(config)
        if not users:
            print("No valid users found in configuration")
            return
        
        # Select user
        selected_user = select_user(users)
        if not selected_user:
            return
        
        # Setup user context
        logger = setup_user_context(selected_user, config)
        
        # Get managers
        context_manager = get_context_manager()
        # Initialize KiteConnect directly
        kite = KiteConnect(api_key=selected_user.api_key)
        kite.set_access_token(selected_user.access_token)
        order_manager = get_user_order_manager()
        state_manager = get_user_state_manager()
        
        # Get latest FNO file
        logger.info("Looking for latest KC Upper Limit Trending scanner file...")
        fno_file = get_latest_fno_file()
        logger.info(f"Using FNO file: {fno_file}")
        
        # Read scanner results
        df = read_fno_scanner_results(fno_file)
        logger.info(f"Found {len(df)} tickers in scanner results")
        
        # Exit if no tickers found
        if len(df) == 0:
            logger.info("No tickers found in scanner results. Exiting...")
            print("No tickers found in scanner results. Exiting...")
            return
        
        # Get top 2 tickers
        top_tickers = df.head(2)
        logger.info(f"\nTop 2 tickers for put selling:")
        for idx, row in top_tickers.iterrows():
            logger.info(f"  {row['ticker']}: Rank {row['rank']}, Score {row['score']}, Close ₹{row['close']:.2f}")
        
        # Get available capital
        try:
            funds = kite.margins()
            available_capital = funds['equity']['available']['live_balance']
            logger.info(f"\nAvailable capital: ₹{available_capital:,.2f}")
        except Exception as e:
            logger.error(f"Error fetching margin: {str(e)}")
            available_capital = float(input("Enter available capital manually: ₹"))
        
        # Calculate capital allocation (2% of total, split between 2 tickers)
        total_allocation = available_capital * 0.02
        capital_per_ticker = total_allocation / 2
        
        logger.info(f"Total allocation (2%): ₹{total_allocation:,.2f}")
        logger.info(f"Capital per ticker: ₹{capital_per_ticker:,.2f}")
        
        # Prepare orders
        orders = place_put_sell_orders(kite, order_manager, top_tickers, capital_per_ticker, logger)
        
        if not orders:
            logger.warning("No orders could be prepared. Exiting.")
            return
        
        # Display order summary
        print("\n" + "="*60)
        print("ORDER SUMMARY - PUT OPTION SELLING")
        print("="*60)
        print(f"\nAccount: {selected_user.name}")
        print(f"Available Capital: ₹{available_capital:,.2f}")
        print(f"Total Allocation (2%): ₹{total_allocation:,.2f}")
        print(f"\nOrders to be placed:")
        
        total_margin = 0
        for order in orders:
            print(f"\n{order['ticker']}:")
            print(f"  Option: {order['option_symbol']}")
            print(f"  Type: SELL {order['order_details']['quantity']} PUT")
            print(f"  Strike: {order['option_symbol'].split()[-2]}")
            print(f"  Premium: ₹{order['order_details']['price']:.2f}")
            print(f"  Margin Required: ₹{order['margin_required']:,.2f}")
            total_margin += order['margin_required']
        
        print(f"\nTotal Margin Required: ₹{total_margin:,.2f}")
        print("="*60)
        
        # Get user confirmation
        confirm = input("\nDo you want to place these orders? (yes/no): ").lower().strip()
        
        if confirm != 'yes':
            logger.info("Order placement cancelled by user")
            return
        
        # Place orders
        logger.info("\nPlacing orders...")
        successful_orders = []
        
        for order in orders:
            try:
                logger.info(f"\nPlacing order for {order['ticker']}...")
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    **order['order_details']
                )
                
                logger.info(f"Order placed successfully. Order ID: {order_id}")
                successful_orders.append({
                    'ticker': order['ticker'],
                    'order_id': order_id,
                    'option_symbol': order['option_symbol']
                })
                
                # Small delay between orders
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error placing order for {order['ticker']}: {str(e)}")
        
        # Summary
        print("\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"Orders attempted: {len(orders)}")
        print(f"Orders successful: {len(successful_orders)}")
        
        if successful_orders:
            print("\nSuccessful orders:")
            for order in successful_orders:
                print(f"  - {order['ticker']}: {order['option_symbol']} (ID: {order['order_id']})")
        
        logger.info("FNO put selling script completed")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        logger.error(f"Script error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()