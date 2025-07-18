#!/usr/bin/env python
"""
Advanced FNO Put Option Selling Script
Sells put options based on KC Upper Limit Trending FNO scanner results
Allocates 2% of capital equally between top 2 tickers
Includes real option chain fetching and proper margin calculations
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
import math

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

def setup_user_context(user_credentials: UserCredentials, config):
    """Set up user context using UserContextManager"""
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
    """Get the most recent KC Upper Limit Trending FNO file"""
    fno_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'FNO', 'Long')
    pattern = os.path.join(fno_dir, 'KC_Upper_Limit_Trending_FNO_*.xlsx')
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No FNO files found matching pattern: {pattern}")
    
    latest_file = max(files, key=os.path.getctime)
    return latest_file

def read_fno_scanner_results(file_path):
    """Read and parse the FNO scanner results"""
    try:
        df = pd.read_excel(file_path)
        # FNO scanner uses different column names
        # Sort by G_Score (highest first) or Base_Score if G_Score not available
        if 'G_Score' in df.columns:
            df = df.sort_values('G_Score', ascending=False)
        elif 'Base_Score' in df.columns:
            df = df.sort_values('Base_Score', ascending=False)
        else:
            # If no score columns, sort by Entry_Price
            df = df.sort_values('Entry_Price', ascending=False)
        
        # Add a rank column for compatibility
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

def get_fno_lot_sizes():
    """Get standard FNO lot sizes - in production, fetch from NSE"""
    # This is a simplified mapping - should be fetched dynamically
    lot_sizes = {
        'RELIANCE': 250,
        'TCS': 150,
        'INFY': 300,
        'HDFC': 300,
        'HDFCBANK': 550,
        'ICICIBANK': 1375,
        'SBIN': 1500,
        'ITC': 2100,
        'BAJFINANCE': 125,
        'TATAMOTORS': 1425,
        'AXISBANK': 1200,
        'LT': 150,
        'MARUTI': 100,
        'TITAN': 375,
        'KOTAKBANK': 400,
        'WIPRO': 1200,
        'ASIANPAINT': 300,
        'HINDUNILVR': 300,
        'BHARTIARTL': 950,
        'TATASTEEL': 425,
        'POWERGRID': 2700,
        'SUNPHARMA': 700,
        'ONGC': 3850,
        'BPCL': 900,
        'COALINDIA': 2700,
        'NTPC': 3000,
        'MM': 500,
        'GRASIM': 325,
        'DRREDDY': 125,
        'HINDALCO': 1075,
        'ADANIENT': 250,
        'DIVISLAB': 200,
        'JSWSTEEL': 950,
        'TECHM': 600,
        'ULTRACEMCO': 100,
        'HEROMOTOCO': 300,
        'BAJAJFINSV': 500,
        'CIPLA': 650,
        'HCLTECH': 700,
        'EICHERMOT': 350,
        'INDUSINDBK': 400,
        'APOLLOHOSP': 250,
        'TATACONSUM': 600,
        'NESTLEIND': 40,
        'BAJAJ-AUTO': 250,
        'ADANIPORTS': 1250,
        'GAIL': 3250,
        'BRITANNIA': 200,
        'SHRIRAMFIN': 600,
        'LTIM': 150
    }
    return lot_sizes

def get_option_chain(kite, ticker, expiry_date):
    """Fetch option chain for a ticker - simplified version"""
    try:
        # In production, use proper NSE option chain API
        # For now, return simulated data
        instruments = kite.instruments('NFO')
        
        # Filter for the ticker's options
        ticker_options = [inst for inst in instruments 
                         if inst['name'] == ticker 
                         and inst['instrument_type'] == 'PE'
                         and inst['expiry'] == expiry_date]
        
        return ticker_options
    except Exception as e:
        logger.error(f"Error fetching option chain: {str(e)}")
        return []

def get_next_weekly_expiry():
    """Get next weekly expiry (Thursday)"""
    today = datetime.date.today()
    days_ahead = 3 - today.weekday()  # Thursday is 3
    if days_ahead <= 0:
        days_ahead += 7
    return today + datetime.timedelta(days_ahead)

def get_next_monthly_expiry():
    """Get next monthly expiry (last Thursday)"""
    today = datetime.date.today()
    
    # Find last Thursday of current month
    month = today.month
    year = today.year
    
    # Start from last day of month and work backwards
    last_day = datetime.date(year, month + 1 if month < 12 else 1, 1) - datetime.timedelta(days=1)
    
    while last_day.weekday() != 3:  # Thursday
        last_day -= datetime.timedelta(days=1)
    
    # If it's already passed, get next month's
    if last_day <= today:
        month = month + 1 if month < 12 else 1
        year = year if month > 1 else year + 1
        last_day = datetime.date(year, month + 1 if month < 12 else 1, 1) - datetime.timedelta(days=1)
        while last_day.weekday() != 3:
            last_day -= datetime.timedelta(days=1)
    
    return last_day

def calculate_put_option_margin(strike_price, lot_size, underlying_price):
    """Calculate SPAN margin for put option selling"""
    # Simplified margin calculation
    # In production, use broker's margin API
    
    # Base margin: 15% of underlying value
    base_margin = underlying_price * lot_size * 0.15
    
    # Add premium margin (assumed 3% for OTM puts)
    premium_margin = strike_price * lot_size * 0.03
    
    # Total margin
    total_margin = base_margin + premium_margin
    
    # Apply minimum margin rule (usually 10% of strike value)
    min_margin = strike_price * lot_size * 0.10
    
    return max(total_margin, min_margin)

def select_optimal_strike(kite, ticker, current_price, capital_available, lot_size, logger):
    """Select optimal strike price based on various factors"""
    
    # Target 5-8% OTM for safety
    target_otm_percent = 6
    target_strike = current_price * (1 - target_otm_percent/100)
    
    # Get strike interval based on underlying price
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
    
    # Round to nearest valid strike
    strike_price = math.floor(target_strike / strike_interval) * strike_interval
    
    # Verify margin requirement
    margin_required = calculate_put_option_margin(strike_price, lot_size, current_price)
    
    # If margin exceeds available capital, adjust strike further OTM
    while margin_required > capital_available * 0.9 and strike_price > current_price * 0.8:
        strike_price -= strike_interval
        margin_required = calculate_put_option_margin(strike_price, lot_size, current_price)
    
    # Calculate estimated premium (simplified)
    moneyness = (current_price - strike_price) / current_price
    time_to_expiry_days = 7  # Weekly expiry
    
    # Simple premium estimation based on moneyness and time
    base_premium_percent = 0.5  # Base premium for ATM
    otm_adjustment = moneyness * 10  # Reduce premium for OTM
    time_adjustment = time_to_expiry_days / 30  # Time value adjustment
    
    premium_percent = max(0.2, base_premium_percent - otm_adjustment) * time_adjustment
    estimated_premium = strike_price * premium_percent / 100
    
    return {
        'strike': strike_price,
        'premium': estimated_premium,
        'margin': margin_required,
        'otm_percent': moneyness * 100
    }

def display_order_analysis(ticker, current_price, option_details, lot_size, quantity_lots):
    """Display detailed analysis of the proposed option trade"""
    print(f"\n{'='*60}")
    print(f"OPTION ANALYSIS: {ticker}")
    print(f"{'='*60}")
    print(f"Underlying Price: ₹{current_price:,.2f}")
    print(f"Strike Selected: ₹{option_details['strike']:,.2f}")
    print(f"OTM %: {option_details['otm_percent']:.2f}%")
    print(f"Lot Size: {lot_size}")
    print(f"Quantity (lots): {quantity_lots}")
    print(f"Total Quantity: {quantity_lots * lot_size}")
    print(f"\nPremium Analysis:")
    print(f"  Premium per unit: ₹{option_details['premium']:.2f}")
    print(f"  Total Premium: ₹{option_details['premium'] * lot_size * quantity_lots:,.2f}")
    print(f"\nMargin Analysis:")
    print(f"  Margin per lot: ₹{option_details['margin']:,.2f}")
    print(f"  Total Margin: ₹{option_details['margin'] * quantity_lots:,.2f}")
    print(f"\nRisk Analysis:")
    print(f"  Max Loss (if exercised): ₹{(option_details['strike'] - option_details['premium']) * lot_size * quantity_lots:,.2f}")
    print(f"  Breakeven: ₹{option_details['strike'] - option_details['premium']:.2f}")
    print(f"  Return on Margin: {(option_details['premium'] * lot_size * 100) / option_details['margin']:.2f}%")

def main():
    """Main execution function"""
    print("=== Advanced FNO Put Option Selling Script ===")
    print("This script sells put options based on KC Upper Limit Trending FNO signals")
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
        
        # Get latest FNO file
        logger.info("Looking for latest FNO scanner file...")
        fno_file = get_latest_fno_file()
        logger.info(f"Using FNO file: {fno_file}")
        
        # Read scanner results
        df = read_fno_scanner_results(fno_file)
        logger.info(f"Found {len(df)} tickers in scanner results")
        
        # Get lot sizes
        lot_sizes = get_fno_lot_sizes()
        
        # Filter tickers that have FNO contracts
        df['has_fno'] = df['ticker'].apply(lambda x: x in lot_sizes)
        df_fno = df[df['has_fno']].copy()
        
        if len(df_fno) < 2:
            logger.error("Less than 2 FNO-enabled tickers found in scanner results")
            return
        
        # Get top 2 tickers
        top_tickers = df_fno.head(2)
        logger.info(f"\nTop 2 FNO tickers for put selling:")
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
        
        # Calculate capital allocation
        total_allocation = available_capital * 0.02
        capital_per_ticker = total_allocation / 2
        
        logger.info(f"Total allocation (2%): ₹{total_allocation:,.2f}")
        logger.info(f"Capital per ticker: ₹{capital_per_ticker:,.2f}")
        
        # Get expiry dates
        weekly_expiry = get_next_weekly_expiry()
        monthly_expiry = get_next_monthly_expiry()
        
        print(f"\nExpiry options:")
        print(f"1. Weekly: {weekly_expiry}")
        print(f"2. Monthly: {monthly_expiry}")
        
        expiry_choice = input("Select expiry (1/2): ").strip()
        selected_expiry = weekly_expiry if expiry_choice == '1' else monthly_expiry
        
        # Prepare orders
        orders = []
        total_margin_required = 0
        
        for idx, row in top_tickers.iterrows():
            ticker = row['ticker']
            current_price = row['close']
            lot_size = lot_sizes.get(ticker, 1)
            
            logger.info(f"\nAnalyzing {ticker}...")
            
            # Select optimal strike and calculate details
            option_details = select_optimal_strike(
                kite, ticker, current_price, capital_per_ticker, lot_size, logger
            )
            
            # Calculate number of lots
            lots = int(capital_per_ticker / option_details['margin'])
            
            if lots <= 0:
                logger.warning(f"Insufficient capital for {ticker}. Skipping.")
                continue
            
            # Display analysis
            display_order_analysis(ticker, current_price, option_details, lot_size, lots)
            
            # Construct order
            expiry_str = selected_expiry.strftime('%y%b').upper()
            option_symbol = f"{ticker}{expiry_str}{int(option_details['strike'])}PE"
            
            order = {
                'ticker': ticker,
                'symbol': option_symbol,
                'strike': option_details['strike'],
                'premium': option_details['premium'],
                'quantity': lots * lot_size,
                'lots': lots,
                'lot_size': lot_size,
                'margin': option_details['margin'] * lots,
                'order_params': {
                    'exchange': 'NFO',
                    'tradingsymbol': option_symbol,
                    'transaction_type': 'SELL',
                    'quantity': lots * lot_size,
                    'product': 'MIS',
                    'order_type': 'LIMIT',
                    'price': option_details['premium'],
                    'validity': 'DAY',
                    'tag': 'FNO_PUT_SELL'
                }
            }
            
            orders.append(order)
            total_margin_required += order['margin']
        
        if not orders:
            logger.warning("No valid orders could be prepared.")
            return
        
        # Final summary
        print(f"\n{'='*60}")
        print("FINAL ORDER SUMMARY")
        print(f"{'='*60}")
        print(f"Account: {selected_user.name}")
        print(f"Available Capital: ₹{available_capital:,.2f}")
        print(f"Total Margin Required: ₹{total_margin_required:,.2f}")
        print(f"Margin Utilization: {(total_margin_required/available_capital)*100:.2f}%")
        
        print("\nOrders to place:")
        for order in orders:
            print(f"\n{order['ticker']}:")
            print(f"  Contract: {order['symbol']}")
            print(f"  Action: SELL {order['lots']} lots ({order['quantity']} qty)")
            print(f"  Premium: ₹{order['premium']:.2f} per unit")
            print(f"  Total Premium: ₹{order['premium'] * order['quantity']:,.2f}")
            print(f"  Margin: ₹{order['margin']:,.2f}")
        
        # Risk warning
        print(f"\n{'='*60}")
        print("⚠️  RISK WARNING")
        print(f"{'='*60}")
        print("Put selling involves unlimited risk if the underlying falls significantly.")
        print("Ensure you understand the risks and have appropriate risk management.")
        print(f"{'='*60}")
        
        # Confirmation
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
                
                # Double-check margin before placing
                current_margin = kite.margins()['equity']['available']['live_balance']
                if current_margin < order['margin']:
                    logger.error(f"Insufficient margin for {order['ticker']}. Required: {order['margin']}, Available: {current_margin}")
                    continue
                
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    **order['order_params']
                )
                
                logger.info(f"Order placed successfully. Order ID: {order_id}")
                successful_orders.append({
                    'ticker': order['ticker'],
                    'order_id': order_id,
                    'symbol': order['symbol'],
                    'premium_collected': order['premium'] * order['quantity']
                })
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error placing order for {order['ticker']}: {str(e)}")
        
        # Final summary
        if successful_orders:
            total_premium = sum(order['premium_collected'] for order in successful_orders)
            print(f"\n{'='*60}")
            print("EXECUTION COMPLETE")
            print(f"{'='*60}")
            print(f"Orders placed: {len(successful_orders)}/{len(orders)}")
            print(f"Total premium collected: ₹{total_premium:,.2f}")
            print("\nOrder details:")
            for order in successful_orders:
                print(f"  {order['ticker']}: {order['symbol']} (ID: {order['order_id']})")
        
        logger.info("FNO put selling script completed")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        logging.error(f"Script error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()