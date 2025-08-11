#!/usr/bin/env python3
"""
VSR Daily Long Trading Script
Monitors VSR dashboard for high momentum tickers and places orders based on hourly breakouts
"""

# Standard library imports
import os
import sys
import logging
import datetime
import time
import json
import requests
import pandas as pd
import configparser
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_context_manager import (
    get_context_manager,
    get_user_data_handler,
    get_user_state_manager,
    get_user_order_manager,
    UserCredentials
)

# Configuration
VSR_DASHBOARD_URL = "http://localhost:3001/api/vsr-tickers"
MIN_VSR_SCORE = 60  # Minimum VSR score to consider
MIN_MOMENTUM = 2.0  # Minimum positive momentum %
POSITION_SIZE_PERCENT = 1.0  # 1% of portfolio per position
MAX_POSITIONS = 5  # Maximum positions to take

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
            logging.FileHandler(os.path.join(log_dir, f'place_orders_vsr_{user_credentials.name}.log'))
        ],
        force=True
    )

    logging.info(f"Context set for user: {user_credentials.name}")

def fetch_vsr_tickers() -> List[Dict]:
    """Fetch current VSR tickers from the dashboard API"""
    try:
        response = requests.get(VSR_DASHBOARD_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            tickers = data.get('tickers', {})
            
            # Filter for positive momentum and minimum score
            filtered_tickers = []
            for ticker, info in tickers.items():
                score = info.get('score', 0)
                momentum = info.get('latest_momentum', 0)
                
                if score >= MIN_VSR_SCORE and momentum >= MIN_MOMENTUM:
                    filtered_tickers.append({
                        'ticker': ticker,
                        'score': score,
                        'momentum': momentum,
                        'vsr_ratio': info.get('latest_vsr', 0),
                        'volume': info.get('latest_volume', 0),
                        'price': info.get('latest_price', 0),
                        'days_tracked': info.get('days_tracked', 0)
                    })
            
            # Sort by score and momentum
            filtered_tickers.sort(key=lambda x: (x['score'], x['momentum']), reverse=True)
            
            logging.info(f"Fetched {len(filtered_tickers)} VSR tickers with positive momentum")
            return filtered_tickers
            
    except Exception as e:
        logging.error(f"Error fetching VSR tickers: {e}")
        return []

def get_hourly_breakout_level(ticker: str, data_handler) -> Optional[float]:
    """
    Get the high of the previous hourly candle for breakout entry
    
    Args:
        ticker: Stock symbol
        data_handler: Data handler instance
        
    Returns:
        Previous hourly high price or None
    """
    try:
        # Get current time and 1 day ago for hourly data
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=1)
        
        # Fetch hourly data
        hourly_data = data_handler.fetch_historical_data(
            ticker,
            interval="60minute",
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )
        
        if hourly_data is None or hourly_data.empty or len(hourly_data) < 2:
            logging.warning(f"Insufficient hourly data for {ticker}")
            return None
            
        # Get the previous completed hour (second to last row)
        prev_hour = hourly_data.iloc[-2]
        prev_high = float(prev_hour.get('High', 0))
        
        logging.info(f"Previous hourly high for {ticker}: {prev_high}")
        return prev_high
        
    except Exception as e:
        logging.error(f"Error getting hourly breakout level for {ticker}: {e}")
        return None

def get_current_price(ticker: str, data_handler) -> Optional[float]:
    """Get current market price for a ticker"""
    try:
        quote = data_handler.get_quote(ticker)
        if quote and ticker in quote:
            return float(quote[ticker].get('last_price', 0))
    except Exception as e:
        logging.error(f"Error getting current price for {ticker}: {e}")
    return None

def calculate_position_size(portfolio_value: float, price: float) -> int:
    """Calculate position size as 1% of portfolio"""
    position_value = portfolio_value * (POSITION_SIZE_PERCENT / 100)
    quantity = int(position_value / price)
    return max(1, quantity)  # At least 1 share

def get_portfolio_value(order_manager) -> float:
    """Get total portfolio value including cash and holdings"""
    try:
        # Get margins
        margins = order_manager.kite.margins()
        equity_margin = margins.get('equity', {})
        available_cash = float(equity_margin.get('available', {}).get('cash', 0))
        
        # Get holdings value
        holdings = order_manager.kite.holdings()
        holdings_value = sum(
            float(h.get('quantity', 0)) * float(h.get('last_price', 0))
            for h in holdings
        )
        
        total_value = available_cash + holdings_value
        logging.info(f"Portfolio value - Cash: ₹{available_cash:,.2f}, Holdings: ₹{holdings_value:,.2f}, Total: ₹{total_value:,.2f}")
        return total_value
        
    except Exception as e:
        logging.error(f"Error getting portfolio value: {e}")
        return 0

def check_existing_positions(tickers: List[str], state_manager, order_manager) -> List[str]:
    """Check which tickers already have positions"""
    existing = []
    
    try:
        # Check state manager
        for ticker in tickers:
            position = state_manager.get_position(ticker)
            if position and position.get('quantity', 0) > 0:
                existing.append(ticker)
                
        # Check broker positions
        if order_manager and hasattr(order_manager, 'kite'):
            positions = order_manager.kite.positions()
            for pos in positions.get('net', []):
                symbol = pos.get('tradingsymbol', '')
                if symbol in tickers and symbol not in existing:
                    if int(pos.get('quantity', 0)) > 0:
                        existing.append(symbol)
                        
    except Exception as e:
        logging.error(f"Error checking existing positions: {e}")
        
    return existing

def display_candidates(candidates: List[Dict]) -> List[Dict]:
    """Display candidate tickers and allow user to exclude some"""
    print("\n" + "="*80)
    print("VSR BREAKOUT CANDIDATES")
    print("="*80)
    print(f"{'No.':<5} {'Ticker':<12} {'Score':<8} {'Momentum %':<12} {'VSR':<8} {'Price':<10} {'Days':<6}")
    print("-"*80)
    
    for i, candidate in enumerate(candidates, 1):
        print(f"{i:<5} {candidate['ticker']:<12} {candidate['score']:<8} "
              f"{candidate['momentum']:<12.2f} {candidate['vsr_ratio']:<8.2f} "
              f"₹{candidate['price']:<10.2f} {candidate['days_tracked']:<6}")
    
    print("-"*80)
    
    # Ask for exclusions
    exclude_input = input("\nEnter ticker numbers to EXCLUDE (comma-separated, or press Enter for none): ").strip()
    
    excluded_indices = []
    if exclude_input:
        try:
            excluded_indices = [int(x.strip()) - 1 for x in exclude_input.split(",")]
        except ValueError:
            print("Invalid input, proceeding with all tickers")
    
    # Filter out excluded tickers
    final_candidates = [
        c for i, c in enumerate(candidates) 
        if i not in excluded_indices
    ]
    
    if excluded_indices:
        print(f"\nExcluded {len(excluded_indices)} ticker(s)")
    
    return final_candidates

def place_vsr_orders(candidates: List[Dict], order_manager, data_handler, state_manager):
    """Place orders for VSR breakout candidates"""
    portfolio_value = get_portfolio_value(order_manager)
    if portfolio_value <= 0:
        logging.error("Could not determine portfolio value")
        return
    
    orders_placed = []
    
    for candidate in candidates[:MAX_POSITIONS]:  # Limit to max positions
        ticker = candidate['ticker']
        
        try:
            # Get breakout level (previous hourly high)
            breakout_level = get_hourly_breakout_level(ticker, data_handler)
            if not breakout_level:
                logging.warning(f"Could not get breakout level for {ticker}, skipping")
                continue
            
            # Get current price
            current_price = get_current_price(ticker, data_handler)
            if not current_price:
                logging.warning(f"Could not get current price for {ticker}, skipping")
                continue
            
            # Check if already broken out
            if current_price > breakout_level:
                logging.info(f"{ticker} already broke out (Current: {current_price}, Breakout: {breakout_level})")
                entry_price = current_price * 1.001  # Add 0.1% buffer
            else:
                entry_price = breakout_level * 1.001  # Add 0.1% buffer for breakout
                logging.info(f"{ticker} waiting for breakout (Current: {current_price}, Breakout: {breakout_level})")
            
            # Calculate position size
            quantity = calculate_position_size(portfolio_value, entry_price)
            
            # Calculate stop loss (2% below entry)
            stop_loss = round(entry_price * 0.98, 2)
            
            # Place order
            order_params = {
                'tradingsymbol': ticker,
                'quantity': quantity,
                'order_type': 'LIMIT',
                'price': round(entry_price, 2),
                'trigger_price': round(entry_price - 0.05, 2),  # Small buffer for limit order
                'product': 'CNC',
                'exchange': 'NSE',
                'transaction_type': 'BUY',
                'validity': 'DAY',
                'tag': 'VSR_BREAKOUT'
            }
            
            logging.info(f"Placing order for {ticker}: {quantity} shares @ ₹{entry_price:.2f}, SL: ₹{stop_loss:.2f}")
            
            order_id = order_manager.place_order(**order_params)
            
            if order_id:
                orders_placed.append({
                    'ticker': ticker,
                    'order_id': order_id,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'vsr_score': candidate['score'],
                    'momentum': candidate['momentum']
                })
                
                # Update state manager
                state_manager.add_position(
                    ticker=ticker,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    product_type='CNC',
                    order_id=order_id,
                    metadata={
                        'strategy': 'VSR_BREAKOUT',
                        'vsr_score': candidate['score'],
                        'momentum': candidate['momentum'],
                        'entry_time': datetime.datetime.now().isoformat()
                    }
                )
                
                logging.info(f"✅ Order placed successfully for {ticker}: {order_id}")
                
                # Small delay between orders
                time.sleep(0.5)
                
        except Exception as e:
            logging.error(f"Error placing order for {ticker}: {e}")
            continue
    
    return orders_placed

def main():
    """Main execution function"""
    print("\n" + "="*80)
    print("VSR DAILY LONG BREAKOUT TRADING SYSTEM")
    print("="*80)
    
    # Load configuration
    config = load_daily_config()
    
    # Get available users and let user select
    users = get_available_users(config)
    selected_user = select_user(users)
    
    if not selected_user:
        print("No user selected. Exiting.")
        return
    
    # Setup user context
    setup_user_context(selected_user, config)
    
    # Get managers
    data_handler = get_user_data_handler()
    state_manager = get_user_state_manager()
    order_manager = get_user_order_manager()
    
    # Initialize Kite connection
    order_manager.initialize_kite()
    
    print(f"\n✅ Connected to Zerodha for user: {selected_user.name}")
    
    # Fetch VSR tickers from dashboard
    print("\nFetching VSR tickers from dashboard...")
    vsr_tickers = fetch_vsr_tickers()
    
    if not vsr_tickers:
        print("❌ No suitable VSR tickers found")
        return
    
    print(f"✅ Found {len(vsr_tickers)} VSR tickers with positive momentum")
    
    # Check for existing positions
    ticker_symbols = [t['ticker'] for t in vsr_tickers]
    existing_positions = check_existing_positions(ticker_symbols, state_manager, order_manager)
    
    if existing_positions:
        print(f"\n⚠️ Already have positions in: {', '.join(existing_positions)}")
        # Filter out existing positions
        vsr_tickers = [t for t in vsr_tickers if t['ticker'] not in existing_positions]
    
    if not vsr_tickers:
        print("❌ No new positions to take")
        return
    
    # Display candidates and get user selection
    final_candidates = display_candidates(vsr_tickers[:10])  # Show top 10
    
    if not final_candidates:
        print("No tickers selected for trading")
        return
    
    # Confirmation
    print(f"\n📊 Ready to place orders for {len(final_candidates)} ticker(s)")
    print(f"Position size: {POSITION_SIZE_PERCENT}% of portfolio per ticker")
    
    confirm = input("\nProceed with order placement? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Order placement cancelled")
        return
    
    # Place orders
    print("\nPlacing orders...")
    orders = place_vsr_orders(final_candidates, order_manager, data_handler, state_manager)
    
    # Summary
    print("\n" + "="*80)
    print("ORDER SUMMARY")
    print("="*80)
    
    if orders:
        print(f"✅ Successfully placed {len(orders)} order(s):")
        for order in orders:
            print(f"  - {order['ticker']}: {order['quantity']} shares @ ₹{order['entry_price']:.2f}")
    else:
        print("❌ No orders were placed")
    
    print("\n" + "="*80)
    logging.info(f"VSR trading session completed - {len(orders)} orders placed")

if __name__ == "__main__":
    main()