#!/usr/bin/env python
"""
FNO Options Wheel Strategy Script
Implements the wheel strategy for FNO stocks based on KC Upper Limit Trending signals
Shows both put and call options for wheel strategy implementation
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
from tabulate import tabulate

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
            logging.FileHandler(os.path.join(log_dir, f'place_orders_FNO_wheel_{user_credentials.name}.log'))
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
    """Get standard FNO lot sizes"""
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
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    
    while last_day.weekday() != 3:  # Thursday
        last_day -= datetime.timedelta(days=1)
    
    # If it's already passed, get next month's
    if last_day <= today:
        month = month + 1 if month < 12 else 1
        year = year if month > 1 else year + 1
        if month == 12:
            last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        while last_day.weekday() != 3:
            last_day -= datetime.timedelta(days=1)
    
    return last_day

def get_strike_interval(price):
    """Get strike interval based on price"""
    if price < 100:
        return 2.5
    elif price < 500:
        return 5
    elif price < 1000:
        return 10
    elif price < 5000:
        return 25
    else:
        return 50

def calculate_option_greeks(spot, strike, days_to_expiry, volatility=0.25, risk_free_rate=0.06):
    """Calculate simplified option Greeks"""
    # Simplified calculations - in production use proper Black-Scholes
    moneyness = (spot - strike) / spot
    time_value = days_to_expiry / 365
    
    # Simplified delta calculation
    if moneyness > 0:  # ITM
        delta_put = -0.3 - (0.4 * min(moneyness / 0.1, 1))
        delta_call = 0.7 + (0.3 * min(moneyness / 0.1, 1))
    else:  # OTM
        delta_put = -0.3 + (0.2 * max(moneyness / -0.1, -1))
        delta_call = 0.3 - (0.2 * max(moneyness / -0.1, -1))
    
    # Simplified theta (time decay per day)
    theta = -0.05 * (1 / max(time_value, 0.01))
    
    return {
        'delta_put': round(delta_put, 3),
        'delta_call': round(delta_call, 3),
        'theta': round(theta, 3)
    }

def estimate_option_premium(spot, strike, days_to_expiry, option_type='PE', volatility=0.25):
    """Estimate option premium using simplified model"""
    moneyness = abs(spot - strike) / spot
    time_value_factor = math.sqrt(days_to_expiry / 365)
    
    # Base premium calculation
    if option_type == 'PE':
        if strike >= spot:  # OTM Put
            base_premium = spot * volatility * time_value_factor * 0.4
            otm_adjustment = math.exp(-moneyness * 10)
            premium = base_premium * otm_adjustment
        else:  # ITM Put
            intrinsic = strike - spot
            time_premium = spot * volatility * time_value_factor * 0.2
            premium = intrinsic + time_premium
    else:  # CE
        if strike <= spot:  # ITM Call
            intrinsic = spot - strike
            time_premium = spot * volatility * time_value_factor * 0.2
            premium = intrinsic + time_premium
        else:  # OTM Call
            base_premium = spot * volatility * time_value_factor * 0.4
            otm_adjustment = math.exp(-moneyness * 10)
            premium = base_premium * otm_adjustment
    
    return max(premium, spot * 0.002)  # Minimum 0.2% of spot

def calculate_margin_requirement(spot, strike, lot_size, option_type='PE'):
    """Calculate SPAN margin for option selling"""
    # Simplified margin calculation
    if option_type == 'PE':
        # Put margin
        exposure_margin = spot * lot_size * 0.05
        span_margin = max(
            spot * lot_size * 0.12,  # 12% of spot value
            strike * lot_size * 0.10  # 10% of strike value
        )
    else:
        # Call margin
        exposure_margin = spot * lot_size * 0.05
        span_margin = spot * lot_size * 0.12
    
    total_margin = exposure_margin + span_margin
    return total_margin

def analyze_wheel_opportunities(ticker, spot_price, lot_size, capital_available, expiry_date):
    """Analyze wheel strategy opportunities for a ticker"""
    strike_interval = get_strike_interval(spot_price)
    days_to_expiry = (expiry_date - datetime.date.today()).days
    
    wheel_options = []
    
    # Analyze PUT options (for initial wheel entry)
    put_strikes = []
    current_strike = spot_price
    while current_strike >= spot_price * 0.85:  # Up to 15% OTM
        current_strike = math.floor(current_strike / strike_interval) * strike_interval
        if current_strike < spot_price:
            put_strikes.append(current_strike)
        current_strike -= strike_interval
    
    for strike in put_strikes[:5]:  # Top 5 strikes
        premium = estimate_option_premium(spot_price, strike, days_to_expiry, 'PE')
        margin = calculate_margin_requirement(spot_price, strike, lot_size, 'PE')
        greeks = calculate_option_greeks(spot_price, strike, days_to_expiry)
        
        # Calculate return metrics
        premium_collected = premium * lot_size
        return_on_margin = (premium_collected / margin) * 100
        annualized_return = return_on_margin * (365 / days_to_expiry)
        
        # Calculate breakeven and profit at expiry
        breakeven = strike - premium
        max_profit = premium_collected
        max_loss = (strike - premium) * lot_size  # If stock goes to zero
        
        wheel_options.append({
            'type': 'PUT',
            'strike': strike,
            'premium': round(premium, 2),
            'margin': round(margin, 2),
            'lots_possible': int(capital_available / margin),
            'otm_percent': round((spot_price - strike) / spot_price * 100, 2),
            'delta': greeks['delta_put'],
            'theta': greeks['theta'],
            'return_on_margin': round(return_on_margin, 2),
            'annualized_return': round(annualized_return, 2),
            'breakeven': round(breakeven, 2),
            'max_profit': round(max_profit, 2),
            'wheel_entry': 'Initial Position - Sell Put to Enter'
        })
    
    # Analyze CALL options (for covered calls if assigned)
    call_strikes = []
    current_strike = spot_price
    while current_strike <= spot_price * 1.15:  # Up to 15% OTM
        current_strike = math.ceil(current_strike / strike_interval) * strike_interval
        if current_strike > spot_price:
            call_strikes.append(current_strike)
        current_strike += strike_interval
    
    for strike in call_strikes[:5]:  # Top 5 strikes
        premium = estimate_option_premium(spot_price, strike, days_to_expiry, 'CE')
        # For covered calls, margin is just the stock value
        stock_value = spot_price * lot_size
        greeks = calculate_option_greeks(spot_price, strike, days_to_expiry)
        
        # Calculate returns
        premium_collected = premium * lot_size
        return_on_stock = (premium_collected / stock_value) * 100
        annualized_return = return_on_stock * (365 / days_to_expiry)
        
        # Total return if called away
        capital_gain = (strike - spot_price) * lot_size
        total_return = premium_collected + capital_gain
        total_return_percent = (total_return / stock_value) * 100
        
        wheel_options.append({
            'type': 'CALL',
            'strike': strike,
            'premium': round(premium, 2),
            'margin': round(stock_value, 2),
            'lots_possible': 'N/A - Requires Stock',
            'otm_percent': round((strike - spot_price) / spot_price * 100, 2),
            'delta': greeks['delta_call'],
            'theta': greeks['theta'],
            'return_on_margin': round(return_on_stock, 2),
            'annualized_return': round(annualized_return, 2),
            'if_called_return': round(total_return_percent, 2),
            'max_profit': round(total_return, 2),
            'wheel_entry': 'After Assignment - Sell Call on Stock'
        })
    
    return wheel_options

def display_wheel_analysis(ticker, spot_price, lot_size, wheel_options):
    """Display wheel strategy analysis in a formatted way"""
    print(f"\n{'='*100}")
    print(f"WHEEL STRATEGY ANALYSIS: {ticker}")
    print(f"{'='*100}")
    print(f"Spot Price: ₹{spot_price:,.2f}")
    print(f"Lot Size: {lot_size}")
    print(f"Contract Value: ₹{spot_price * lot_size:,.2f}")
    
    # Separate puts and calls
    puts = [opt for opt in wheel_options if opt['type'] == 'PUT']
    calls = [opt for opt in wheel_options if opt['type'] == 'CALL']
    
    # Display PUT options
    print(f"\n{'='*100}")
    print("STEP 1: SELL CASH-SECURED PUTS (Entry Strategy)")
    print(f"{'='*100}")
    
    put_headers = ['Strike', 'Premium', 'OTM%', 'Margin Req', 'Lots', 'RoM%', 'Annual%', 'Delta', 'Breakeven']
    put_data = []
    
    for put in puts:
        put_data.append([
            f"₹{put['strike']}",
            f"₹{put['premium']}",
            f"{put['otm_percent']}%",
            f"₹{put['margin']:,.0f}",
            put['lots_possible'],
            f"{put['return_on_margin']}%",
            f"{put['annualized_return']}%",
            put['delta'],
            f"₹{put['breakeven']}"
        ])
    
    print(tabulate(put_data, headers=put_headers, tablefmt='grid'))
    
    # Display CALL options
    print(f"\n{'='*100}")
    print("STEP 2: SELL COVERED CALLS (If Assigned Stock)")
    print(f"{'='*100}")
    
    call_headers = ['Strike', 'Premium', 'OTM%', 'Stock Value', 'RoS%', 'Annual%', 'Delta', 'If Called%']
    call_data = []
    
    for call in calls:
        call_data.append([
            f"₹{call['strike']}",
            f"₹{call['premium']}",
            f"{call['otm_percent']}%",
            f"₹{call['margin']:,.0f}",
            f"{call['return_on_margin']}%",
            f"{call['annualized_return']}%",
            call['delta'],
            f"{call['if_called_return']}%"
        ])
    
    print(tabulate(call_data, headers=call_headers, tablefmt='grid'))
    
    # Display strategy explanation
    print(f"\n{'='*100}")
    print("WHEEL STRATEGY EXECUTION:")
    print(f"{'='*100}")
    print("1. SELL PUT: Choose a strike below current price where you're comfortable owning the stock")
    print("2. IF NOT ASSIGNED: Keep the premium and repeat")
    print("3. IF ASSIGNED: You now own the stock at a discount (strike - premium received)")
    print("4. SELL CALL: Choose a strike above your cost basis")
    print("5. IF NOT CALLED: Keep the premium and repeat covered calls")
    print("6. IF CALLED AWAY: Profit from stock appreciation + all premiums collected")
    print("\nKEY METRICS:")
    print("- RoM% = Return on Margin (Premium/Margin Required)")
    print("- RoS% = Return on Stock (Premium/Stock Value)")
    print("- Annual% = Annualized return based on days to expiry")
    print("- Delta = Rate of change in option price with stock price")

def execute_wheel_trade(kite, ticker, option_details, lot_size, quantity_lots):
    """Execute a wheel strategy trade"""
    try:
        order_params = {
            'exchange': 'NFO',
            'tradingsymbol': option_details['symbol'],
            'transaction_type': 'SELL',
            'quantity': quantity_lots * lot_size,
            'product': 'MIS',  # Can be changed to NRML for overnight
            'order_type': 'LIMIT',
            'price': option_details['premium'],
            'validity': 'DAY',
            'tag': 'WHEEL_STRATEGY'
        }
        
        order_id = kite.place_order(variety=kite.VARIETY_REGULAR, **order_params)
        return order_id
    except Exception as e:
        raise Exception(f"Order placement failed: {str(e)}")

def check_existing_positions(kite, ticker):
    """Check if user already has positions in the ticker"""
    try:
        positions = kite.positions()
        holdings = kite.holdings()
        
        # Check for existing stock positions
        stock_qty = 0
        for pos in positions['net']:
            if pos['tradingsymbol'] == ticker and pos['quantity'] != 0:
                stock_qty += pos['quantity']
        
        for holding in holdings:
            if holding['tradingsymbol'] == ticker:
                stock_qty += holding['quantity']
        
        # Check for existing option positions
        option_positions = []
        for pos in positions['net']:
            if ticker in pos['tradingsymbol'] and pos['exchange'] == 'NFO':
                option_positions.append({
                    'symbol': pos['tradingsymbol'],
                    'quantity': pos['quantity'],
                    'type': 'PUT' if 'PE' in pos['tradingsymbol'] else 'CALL'
                })
        
        return {
            'stock_quantity': stock_qty,
            'option_positions': option_positions,
            'has_stock': stock_qty > 0,
            'has_options': len(option_positions) > 0
        }
    except Exception as e:
        logger.error(f"Error checking positions: {str(e)}")
        return {
            'stock_quantity': 0,
            'option_positions': [],
            'has_stock': False,
            'has_options': False
        }

def main():
    """Main execution function"""
    print("=== FNO Options Wheel Strategy Script ===")
    print("This script analyzes wheel strategy opportunities based on KC Upper Limit Trending signals")
    print("The wheel strategy combines selling puts and covered calls for income generation\n")
    
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
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=selected_user.api_key)
        kite.set_access_token(selected_user.access_token)
        
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
        
        if len(df_fno) == 0:
            logger.error("No FNO-enabled tickers found in scanner results")
            return
        
        # Display top FNO tickers
        print("\nTop FNO Tickers from Scanner:")
        print("="*60)
        for idx, row in df_fno.head(10).iterrows():
            lot_size = lot_sizes.get(row['ticker'], 'N/A')
            print(f"{idx+1}. {row['ticker']}: Rank {row['rank']}, Score {row['score']:.2f}, "
                  f"Price ₹{row['close']:.2f}, Lot Size {lot_size}")
        
        # Get available capital
        try:
            funds = kite.margins()
            available_capital = funds['equity']['available']['live_balance']
            logger.info(f"\nAvailable capital: ₹{available_capital:,.2f}")
        except Exception as e:
            logger.error(f"Error fetching margin: {str(e)}")
            available_capital = float(input("Enter available capital manually: ₹"))
        
        # Select ticker for analysis
        print("\nSelect a ticker for wheel strategy analysis:")
        ticker_choice = input("Enter ticker number (1-10) or ticker symbol: ").strip().upper()
        
        if ticker_choice.isdigit():
            idx = int(ticker_choice) - 1
            if 0 <= idx < len(df_fno):
                selected_ticker = df_fno.iloc[idx]['ticker']
                spot_price = df_fno.iloc[idx]['close']
            else:
                print("Invalid selection")
                return
        else:
            # Direct ticker entry
            if ticker_choice in lot_sizes:
                selected_ticker = ticker_choice
                # Try to get price from dataframe or fetch current price
                ticker_data = df_fno[df_fno['ticker'] == ticker_choice]
                if not ticker_data.empty:
                    spot_price = ticker_data.iloc[0]['close']
                else:
                    # Fetch current price
                    try:
                        quote = kite.quote(f"NSE:{ticker_choice}")
                        spot_price = quote[f"NSE:{ticker_choice}"]['last_price']
                    except:
                        spot_price = float(input(f"Enter current price for {ticker_choice}: ₹"))
            else:
                print(f"{ticker_choice} is not an FNO stock")
                return
        
        lot_size = lot_sizes[selected_ticker]
        
        # Check existing positions
        logger.info(f"Checking existing positions for {selected_ticker}...")
        existing_positions = check_existing_positions(kite, selected_ticker)
        
        if existing_positions['has_stock']:
            print(f"\n⚠️  You already own {existing_positions['stock_quantity']} shares of {selected_ticker}")
            print("Recommendation: Consider SELLING COVERED CALLS")
        
        if existing_positions['has_options']:
            print(f"\n⚠️  You have existing option positions in {selected_ticker}:")
            for pos in existing_positions['option_positions']:
                print(f"   - {pos['symbol']}: {pos['quantity']} qty")
        
        # Get expiry options
        print(f"\nSelect expiry for {selected_ticker} options:")
        weekly_expiry = get_next_weekly_expiry()
        monthly_expiry = get_next_monthly_expiry()
        
        print(f"1. Weekly: {weekly_expiry} ({(weekly_expiry - datetime.date.today()).days} days)")
        print(f"2. Monthly: {monthly_expiry} ({(monthly_expiry - datetime.date.today()).days} days)")
        
        expiry_choice = input("Select expiry (1/2): ").strip()
        selected_expiry = weekly_expiry if expiry_choice == '1' else monthly_expiry
        
        # Analyze wheel opportunities
        logger.info(f"Analyzing wheel opportunities for {selected_ticker}...")
        wheel_options = analyze_wheel_opportunities(
            selected_ticker, spot_price, lot_size, available_capital, selected_expiry
        )
        
        # Display analysis
        display_wheel_analysis(selected_ticker, spot_price, lot_size, wheel_options)
        
        # Risk warnings
        print(f"\n{'='*100}")
        print("⚠️  RISK WARNINGS")
        print(f"{'='*100}")
        print("PUT SELLING RISKS:")
        print("- You may be assigned stock at the strike price")
        print("- Stock can fall below your breakeven causing losses")
        print("- Requires full cash to secure the put (strike × lot size)")
        print("\nCOVERED CALL RISKS:")
        print("- Limits upside if stock rallies above strike")
        print("- Stock can still fall causing losses")
        print("- You need to own the stock first")
        
        # Trade execution
        print(f"\n{'='*100}")
        proceed = input("\nDo you want to execute a wheel strategy trade? (yes/no): ").lower().strip()
        
        if proceed != 'yes':
            logger.info("Trade execution cancelled by user")
            return
        
        # Select specific option
        print("\nSelect option type:")
        print("1. SELL PUT (Start wheel strategy)")
        print("2. SELL CALL (If you own stock)")
        
        option_type_choice = input("Select (1/2): ").strip()
        
        if option_type_choice == '1':
            # Put selection
            puts = [opt for opt in wheel_options if opt['type'] == 'PUT']
            print("\nSelect PUT strike:")
            for i, put in enumerate(puts, 1):
                print(f"{i}. Strike ₹{put['strike']} - Premium ₹{put['premium']} - "
                      f"RoM {put['return_on_margin']}% - Delta {put['delta']}")
            
            strike_choice = int(input("Select strike (number): ")) - 1
            selected_option = puts[strike_choice]
            
        else:
            # Call selection
            if not existing_positions['has_stock']:
                print("\n⚠️  WARNING: You don't own the stock. Naked call selling is very risky!")
                confirm = input("Continue anyway? (yes/no): ").lower()
                if confirm != 'yes':
                    return
            
            calls = [opt for opt in wheel_options if opt['type'] == 'CALL']
            print("\nSelect CALL strike:")
            for i, call in enumerate(calls, 1):
                print(f"{i}. Strike ₹{call['strike']} - Premium ₹{call['premium']} - "
                      f"RoS {call['return_on_margin']}% - Delta {call['delta']}")
            
            strike_choice = int(input("Select strike (number): ")) - 1
            selected_option = calls[strike_choice]
        
        # Determine quantity
        if selected_option['type'] == 'PUT':
            max_lots = min(selected_option['lots_possible'], 5)  # Cap at 5 lots for safety
            print(f"\nMaximum lots possible: {max_lots}")
            quantity_lots = int(input(f"Enter number of lots to trade (1-{max_lots}): "))
        else:
            # For calls, need to check stock ownership
            if existing_positions['has_stock']:
                max_lots = existing_positions['stock_quantity'] // lot_size
                print(f"\nYou can sell covered calls on {max_lots} lots")
                quantity_lots = int(input(f"Enter number of lots (1-{max_lots}): "))
            else:
                quantity_lots = int(input("Enter number of lots: "))
        
        # Construct option symbol
        expiry_str = selected_expiry.strftime('%y%b').upper()
        option_symbol = f"{selected_ticker}{expiry_str}{int(selected_option['strike'])}{selected_option['type']}"
        
        # Final confirmation
        print(f"\n{'='*100}")
        print("ORDER CONFIRMATION")
        print(f"{'='*100}")
        print(f"Symbol: {option_symbol}")
        print(f"Action: SELL {quantity_lots} lot(s) ({quantity_lots * lot_size} qty)")
        print(f"Strike: ₹{selected_option['strike']}")
        print(f"Premium: ₹{selected_option['premium']}")
        print(f"Total Premium: ₹{selected_option['premium'] * quantity_lots * lot_size:,.2f}")
        if selected_option['type'] == 'PUT':
            print(f"Margin Required: ₹{selected_option['margin'] * quantity_lots:,.2f}")
            print(f"Breakeven: ₹{selected_option['breakeven']}")
        print(f"{'='*100}")
        
        final_confirm = input("\nConfirm order placement? (yes/no): ").lower().strip()
        
        if final_confirm == 'yes':
            try:
                # Prepare order details
                option_details = {
                    'symbol': option_symbol,
                    'premium': selected_option['premium']
                }
                
                order_id = execute_wheel_trade(kite, selected_ticker, option_details, lot_size, quantity_lots)
                
                print(f"\n✅ Order placed successfully!")
                print(f"Order ID: {order_id}")
                logger.info(f"Wheel strategy order placed: {option_symbol} - Order ID: {order_id}")
                
            except Exception as e:
                print(f"\n❌ Order failed: {str(e)}")
                logger.error(f"Order placement failed: {str(e)}")
        else:
            print("\nOrder cancelled")
            logger.info("Order cancelled by user")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        logging.error(f"Script error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()