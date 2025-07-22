#!/usr/bin/env python
"""
G Pattern Auto Trader - Multi-User Version
Places orders for stocks in G PATTERN CONFIRMED category from G_Pattern_Master_List.xlsx
Position size calculated as: (capital available * config %) / number of confirmed tickers
Supports multiple trading accounts with user selection
"""

import os
import sys
import pandas as pd
import datetime
import logging
import configparser
import glob
from kiteconnect import KiteConnect
import time
import json

# Add parent directories to path
# Add Daily to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import user context manager
from user_context_manager import (
    get_context_manager,
    get_user_state_manager,
    get_user_order_manager,
    get_user_data_handler,
    UserCredentials
)

# Initial logging setup - will be reconfigured per user
logger = logging.getLogger(__name__)

# Define paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = os.path.dirname(SCRIPT_DIR)
RESULTS_DIR = os.path.join(DAILY_DIR, "results")
MASTER_DIR = os.path.join(DAILY_DIR, "G_Pattern_Master")
CONFIG_PATH = os.path.join(DAILY_DIR, "config.ini")

class GPatternAutoTrader:
    def __init__(self, user_credentials: UserCredentials):
        self.user_credentials = user_credentials
        self.user_name = user_credentials.name
        self.config = self.load_config()
        self.setup_user_logging()
        self.kite = self.initialize_kite()
        self.positions = []
        self.orders = []
        
    def setup_user_logging(self):
        """Set up user-specific logging"""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(script_dir, 'logs', self.user_name)
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure user-specific logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f'g_pattern_auto_trader_{self.user_name}.log')),
                logging.StreamHandler()
            ],
            force=True
        )
        
    def load_config(self):
        """Load configuration from config.ini"""
        if not os.path.exists(CONFIG_PATH):
            logger.error(f"config.ini not found at {CONFIG_PATH}")
            raise FileNotFoundError(f"config.ini not found at {CONFIG_PATH}")
        
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        
        return config
    
    def initialize_kite(self):
        """Initialize Kite Connect client"""
        try:
            # Use credentials from UserCredentials object
            kite = KiteConnect(api_key=self.user_credentials.api_key)
            kite.set_access_token(self.user_credentials.access_token)
            
            # Test connection
            profile = kite.profile()
            logger.info(f"Connected to Kite as {profile['user_name']}")
            
            return kite
        except Exception as e:
            logger.error(f"Failed to initialize Kite Connect: {e}")
            raise
    
    def get_position_sizing_params(self):
        """Get position sizing parameters from config"""
        params = {
            'base_capital': float(self.config.get('RISK_MANAGEMENT', 'base_capital', fallback=100000)),
            'position_size_percentage': float(self.config.get('RISK_MANAGEMENT', 'position_size_percentage', fallback=5.0)),
            'max_positions': int(self.config.get('RISK_MANAGEMENT', 'max_positions', fallback=5)),
            'max_risk_per_trade': float(self.config.get('RISK_MANAGEMENT', 'max_risk_per_trade', fallback=2.0)),
            'g_pattern_multiplier': float(self.config.get('RISK_MANAGEMENT', 'g_pattern_multiplier', fallback=1.5))
        }
        
        # Add G Pattern specific settings if available
        if 'G_PATTERN_TRADING' in self.config.sections():
            params['min_probability_score'] = float(self.config.get('G_PATTERN_TRADING', 'min_probability_score', fallback=65.0))
            params['initial_position_percent'] = float(self.config.get('G_PATTERN_TRADING', 'initial_position_percent', fallback=25.0))
            params['double_position_percent'] = float(self.config.get('G_PATTERN_TRADING', 'double_position_percent', fallback=50.0))
            params['full_position_percent'] = float(self.config.get('G_PATTERN_TRADING', 'full_position_percent', fallback=100.0))
            params['g_pattern_confirmed_allocation_percent'] = float(self.config.get('G_PATTERN_TRADING', 'g_pattern_confirmed_allocation_percent', fallback=15.0))
        else:
            params['min_probability_score'] = 65.0
            params['initial_position_percent'] = 25.0
            params['double_position_percent'] = 50.0
            params['full_position_percent'] = 100.0
            params['g_pattern_confirmed_allocation_percent'] = 15.0
        
        return params
    
    def get_latest_report(self):
        """Get the latest KC Upper Limit Trending report file path"""
        pattern = os.path.join(RESULTS_DIR, "KC_Upper_Limit_Trending_*.xlsx")
        files = glob.glob(pattern)
        
        if not files:
            logger.warning("No KC Upper Limit Trending reports found")
            return None
        
        latest_file = max(files, key=os.path.getctime)
        logger.info(f"Found latest report: {latest_file}")
        
        return latest_file
    
    def get_master_recommendations(self):
        """Get recommendations from master tracker if available"""
        master_file = os.path.join(MASTER_DIR, "G_Pattern_Master_List.xlsx")
        
        if os.path.exists(master_file):
            logger.info(f"Loading master recommendations from: {master_file}")
            return pd.read_excel(master_file)
        
        return None
    
    def get_confirmed_tickers_from_master(self):
        """Get only G PATTERN CONFIRMED tickers from master list"""
        master_df = self.get_master_recommendations()
        
        if master_df is None or master_df.empty:
            logger.warning("No master recommendations found")
            return pd.DataFrame()
        
        # Parse summary to get confirmed tickers
        summary_categories = self.parse_summary_file()
        confirmed_tickers = summary_categories.get('G_PATTERN_CONFIRMED', [])
        
        if not confirmed_tickers:
            logger.warning("No G PATTERN CONFIRMED tickers found in summary")
            return pd.DataFrame()
        
        # Filter master df for confirmed tickers only
        confirmed_df = master_df[master_df['Ticker'].isin(confirmed_tickers)]
        
        logger.info(f"Found {len(confirmed_df)} G PATTERN CONFIRMED tickers")
        for _, row in confirmed_df.iterrows():
            logger.info(f"  {row['Ticker']} ({row.get('Sector', 'Unknown')}): "
                       f"Score {row.get('Current_Score', 0)}, "
                       f"Price ₹{row.get('Current_Price', 0):.2f}")
        
        return confirmed_df
    
    def parse_summary_file(self):
        """Parse G_Pattern_Summary.txt to get recommendations by category"""
        summary_file = os.path.join(MASTER_DIR, "G_Pattern_Summary.txt")
        
        if not os.path.exists(summary_file):
            logger.warning(f"Summary file not found: {summary_file}")
            return {}
        
        categories = {}
        current_category = None
        
        with open(summary_file, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            
            # Check for category headers
            if "G PATTERN CONFIRMED - FULL POSITION (100%)" in line:
                current_category = "G_PATTERN_CONFIRMED"
                categories[current_category] = []
            elif "G PATTERN DEVELOPING - DOUBLE POSITION (50%)" in line:
                current_category = "G_PATTERN_DEVELOPING"
                categories[current_category] = []
            elif "PATTERN EMERGING - INITIAL POSITION (25%)" in line:
                current_category = "PATTERN_EMERGING"
                categories[current_category] = []
            elif "HOLD AND MONITOR - PATTERN MATURE" in line:
                current_category = "HOLD_AND_MONITOR"
                categories[current_category] = []
            elif "WATCH CLOSELY - PRE-ENTRY" in line:
                current_category = "WATCH_CLOSELY"
                categories[current_category] = []
            elif "WATCH ONLY" in line:
                current_category = "WATCH_ONLY"
                categories[current_category] = []
            elif current_category and line and not line.startswith("-") and not line.startswith("="):
                # Parse stock entry (e.g., "MEDANTA (Healthcare): Score 100, Days 6, Entry ₹1311.90")
                if ":" in line and "Score" in line and "Entry" in line:
                    # Extract ticker name (everything before the first parenthesis)
                    if "(" in line:
                        ticker = line.split("(")[0].strip()
                        if ticker:  # Only add if ticker is not empty
                            categories[current_category].append(ticker)
                            logger.debug(f"Added {ticker} to {current_category}")
        
        # Log detailed parsing results
        for category, tickers in categories.items():
            if tickers:
                logger.info(f"{category}: {len(tickers)} stocks - {', '.join(tickers)}")
        
        return categories
    
    def filter_tradeable_stocks_by_strategy(self, report_df, summary_categories):
        """Filter stocks based on G Pattern Summary strategy"""
        # Get both G_PATTERN_CONFIRMED and PATTERN_EMERGING categories
        g_pattern_confirmed = summary_categories.get('G_PATTERN_CONFIRMED', [])
        pattern_emerging = summary_categories.get('PATTERN_EMERGING', [])
        
        # Combine both categories
        all_tradeable_tickers = g_pattern_confirmed + pattern_emerging
        
        if not all_tradeable_tickers:
            logger.warning("No stocks in G_PATTERN_CONFIRMED or PATTERN_EMERGING categories")
            return pd.DataFrame(), pd.DataFrame()
        
        # Filter report_df for each category
        confirmed_df = report_df[report_df['Ticker'].isin(g_pattern_confirmed)] if g_pattern_confirmed else pd.DataFrame()
        emerging_df = report_df[report_df['Ticker'].isin(pattern_emerging)] if pattern_emerging else pd.DataFrame()
        
        # Log findings
        if not confirmed_df.empty:
            logger.info(f"Found {len(confirmed_df)} stocks in G_PATTERN_CONFIRMED category")
            for _, row in confirmed_df.iterrows():
                logger.info(f"  {row['Ticker']}: Score {row['Probability_Score']:.1f}%, Pattern: {row['Pattern']}")
        
        if not emerging_df.empty:
            logger.info(f"Found {len(emerging_df)} stocks in PATTERN_EMERGING category")
            for _, row in emerging_df.iterrows():
                logger.info(f"  {row['Ticker']}: Score {row['Probability_Score']:.1f}%, Pattern: {row['Pattern']}")
        
        return confirmed_df, emerging_df
    
    def calculate_position_size_from_capital(self, available_capital, current_price, num_positions, allocation_percent):
        """
        Calculate position size based on strategy:
        Position size = (allocation_percent × available_capital) ÷ num_positions
        
        For G_PATTERN_CONFIRMED: Uses g_pattern_confirmed_allocation_percent from config
        """
        if available_capital <= 0 or current_price <= 0:
            logger.warning(f"Invalid capital ({available_capital}) or price ({current_price})")
            return 0

        # Convert percentage to decimal
        deployment_percent = allocation_percent / 100.0

        # Calculate total usable capital: deployment% × available
        total_usable_capital = deployment_percent * available_capital

        # Calculate capital per position
        capital_per_position = total_usable_capital / num_positions

        # Calculate position size: capital_per_position / current_price
        position_size = capital_per_position / current_price

        # Round down to nearest integer
        position_size = int(position_size)

        logger.info(f"Position sizing: {allocation_percent:.0f}% × ₹{available_capital:,.2f} ÷ {num_positions} positions")
        logger.info(f"Capital per position: ₹{capital_per_position:,.2f}, Price: ₹{current_price:.2f}, Shares: {position_size}")

        return position_size
    
    def get_existing_positions(self):
        """Get existing positions from Kite"""
        try:
            positions = self.kite.positions()
            return positions['net']
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def check_if_already_positioned(self, ticker):
        """Check if already have position in ticker"""
        positions = self.get_existing_positions()
        
        for pos in positions:
            if pos['tradingsymbol'] == ticker and pos['quantity'] != 0:
                return True
        
        return False
    
    def prepare_orders_for_confirmed_only(self, confirmed_df, available_capital, params):
        """Prepare orders for G PATTERN CONFIRMED stocks only"""
        orders = []
        
        if confirmed_df.empty:
            logger.warning("No confirmed tickers to process")
            return orders
        
        # For G PATTERN CONFIRMED, we allow buying even if already positioned
        # This is part of the scaling strategy
        confirmed_stocks = []
        for idx, row in confirmed_df.iterrows():
            ticker = row['Ticker']
            if self.check_if_already_positioned(ticker):
                logger.info(f"Already positioned in {ticker}, but allowing additional purchase for G PATTERN CONFIRMED")
            confirmed_stocks.append(row)
        
        if not confirmed_stocks:
            logger.warning("No confirmed tickers to process")
            return orders
        
        num_confirmed = len(confirmed_stocks)
        allocation_percent = params['g_pattern_confirmed_allocation_percent']
        
        logger.info(f"Preparing orders for {num_confirmed} G PATTERN CONFIRMED stocks (including existing positions)")
        logger.info(f"Using allocation: {allocation_percent}% of available capital")
        
        for row in confirmed_stocks:
            ticker = row['Ticker']
            current_price = row.get('Current_Price', 0)
            stop_loss = row.get('Stop_Loss', 0)
            target1 = row.get('Target1', 0)
            
            if current_price <= 0:
                logger.warning(f"Invalid price for {ticker}: {current_price}")
                continue
            
            # Calculate position size using config allocation
            position_size = self.calculate_position_size_from_capital(
                available_capital, current_price, num_confirmed, allocation_percent
            )
            
            if position_size > 0:
                investment_amount = position_size * current_price
                risk_per_share = current_price - stop_loss if stop_loss > 0 else current_price * 0.02
                total_risk = position_size * risk_per_share
                risk_percentage = (total_risk / available_capital) * 100
                risk_reward = row.get('Risk_Reward', 2.0)
                
                order = {
                    'ticker': ticker,
                    'pattern': row.get('Current_Pattern', 'G_Pattern'),
                    'score': row.get('Current_Score', 0),
                    'days_tracked': row.get('Days_Tracked', 0),
                    'sector': row.get('Sector', 'Unknown'),
                    'recommendation': f"G PATTERN CONFIRMED - {allocation_percent}% ALLOCATION",
                    'category': "G_PATTERN_CONFIRMED",
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'target1': target1,
                    'quantity': position_size,
                    'position_value': investment_amount,
                    'risk_amount': total_risk,
                    'risk_percentage': risk_percentage,
                    'risk_reward_ratio': risk_reward
                }
                orders.append(order)
        
        return orders
    
    def prepare_orders(self, confirmed_df, emerging_df, available_capital, params, master_df=None):
        """Prepare order list for confirmation based on G Pattern strategy"""
        orders = []
        
        # Process G_PATTERN_CONFIRMED stocks (10% allocation)
        if not confirmed_df.empty:
            confirmed_stocks = []
            for idx, row in confirmed_df.iterrows():
                ticker = row['Ticker']
                if not self.check_if_already_positioned(ticker):
                    confirmed_stocks.append(row)
                else:
                    logger.info(f"Already positioned in {ticker}, skipping")
            
            if confirmed_stocks:
                num_confirmed = len(confirmed_stocks)
                for row in confirmed_stocks:
                    ticker = row['Ticker']
                    current_price = row['Entry_Price']
                    
                    # Calculate position size with 10% allocation
                    position_size = self.calculate_position_size_from_capital(
                        available_capital, current_price, num_confirmed, category="G_PATTERN_CONFIRMED"
                    )
                    
                    if position_size > 0:
                        investment_amount = position_size * current_price
                        risk_per_share = current_price - row['Stop_Loss']
                        total_risk = position_size * risk_per_share
                        risk_percentage = (total_risk / available_capital) * 100
                        
                        order = {
                            'ticker': ticker,
                            'pattern': row['Pattern'],
                            'probability_score': row['Probability_Score'],
                            'recommendation': "G PATTERN CONFIRMED - 10% POSITION",
                            'category': "G_PATTERN_CONFIRMED",
                            'entry_price': current_price,
                            'stop_loss': row['Stop_Loss'],
                            'target1': row['Target1'],
                            'quantity': position_size,
                            'position_value': investment_amount,
                            'risk_amount': total_risk,
                            'risk_percentage': risk_percentage,
                            'risk_reward_ratio': row.get('Risk_Reward', 0)
                        }
                        orders.append(order)
        
        # Process PATTERN_EMERGING stocks (5% allocation)
        if not emerging_df.empty:
            emerging_stocks = []
            for idx, row in emerging_df.iterrows():
                ticker = row['Ticker']
                if not self.check_if_already_positioned(ticker):
                    emerging_stocks.append(row)
                else:
                    logger.info(f"Already positioned in {ticker}, skipping")
            
            if emerging_stocks:
                num_emerging = len(emerging_stocks)
                for row in emerging_stocks:
                    ticker = row['Ticker']
                    current_price = row['Entry_Price']
                    
                    # Calculate position size with 5% allocation
                    position_size = self.calculate_position_size_from_capital(
                        available_capital, current_price, num_emerging, category="PATTERN_EMERGING"
                    )
                    
                    if position_size > 0:
                        investment_amount = position_size * current_price
                        risk_per_share = current_price - row['Stop_Loss']
                        total_risk = position_size * risk_per_share
                        risk_percentage = (total_risk / available_capital) * 100
                        
                        order = {
                            'ticker': ticker,
                            'pattern': row['Pattern'],
                            'probability_score': row['Probability_Score'],
                            'recommendation': "PATTERN EMERGING - 5% POSITION",
                            'category': "PATTERN_EMERGING",
                            'entry_price': current_price,
                            'stop_loss': row['Stop_Loss'],
                            'target1': row['Target1'],
                            'quantity': position_size,
                            'position_value': investment_amount,
                            'risk_amount': total_risk,
                            'risk_percentage': risk_percentage,
                            'risk_reward_ratio': row.get('Risk_Reward', 0)
                        }
                        orders.append(order)
        
        return orders
    
    def display_orders_for_confirmed_only(self, orders, available_capital, allocation_percent):
        """Display orders for G PATTERN CONFIRMED stocks only"""
        if not orders:
            print("\n❌ No orders to place. All stocks may already be in portfolio.")
            return False
        
        # Calculate totals
        total_capital_used = sum(order['position_value'] for order in orders)
        total_allocation_percent = (total_capital_used / available_capital) * 100
        
        print("\n" + "="*80)
        print("📊 G PATTERN AUTO TRADER - CONFIRMED POSITIONS ONLY")
        print("="*80)
        print(f"\nAccount: {self.user_name}")
        print(f"Source: G_Pattern_Master_List.xlsx - G PATTERN CONFIRMED category")
        print(f"\nAvailable Capital: ₹{available_capital:,.2f}")
        print(f"Allocation Per Category: {allocation_percent}% of capital")
        print(f"Number of Stocks: {len(orders)}")
        print(f"Total Allocation: ₹{total_capital_used:,.2f} ({total_allocation_percent:.1f}% of available capital)")
        
        print("\n" + "-"*80)
        print(f"🟢 G PATTERN CONFIRMED POSITIONS")
        print("-"*80)
        
        for i, order in enumerate(orders, 1):
            ticker = order['ticker']
            entry = order['entry_price']
            sl = order['stop_loss']
            tp = order['target1']
            score = order.get('score', 0)
            days = order.get('days_tracked', 0)
            sector = order.get('sector', 'Unknown')
            shares = order['quantity']
            value = order['position_value']
            
            # Check if already positioned
            existing_position = " [ADDING TO EXISTING POSITION]" if self.check_if_already_positioned(ticker) else ""
            
            print(f"\n{i}. {ticker} ({sector}){existing_position}")
            print(f"   Score: {score} | Days Tracked: {days}")
            print(f"   Entry: ₹{entry:.2f} | Stop Loss: ₹{sl:.2f} | Target: ₹{tp:.2f}")
            print(f"   Quantity: {shares} shares | Investment: ₹{value:,.2f}")
        
        print("\n" + "-"*80)
        print(f"SUMMARY:")
        print(f"Total Positions: {len(orders)}")
        print(f"Total Investment: ₹{total_capital_used:,.2f}")
        print(f"Remaining Capital: ₹{available_capital - total_capital_used:,.2f}")
        print("-"*80)
        
        print("\n⚠️  POSITION SIZING STRATEGY:")
        print(f"  - Each position gets equal share of {allocation_percent}% allocation")
        print(f"  - Per position allocation: {allocation_percent}% ÷ {len(orders)} = {allocation_percent/len(orders):.2f}%")
        
        # Count existing positions
        existing_positions = sum(1 for order in orders if self.check_if_already_positioned(order['ticker']))
        if existing_positions > 0:
            print(f"\n📌 NOTE: {existing_positions} of these are ADDITIONS to existing positions (scaling up)")
        
        # Get user confirmation
        confirmation = input(f"\nPlace buy orders for these {len(orders)} G PATTERN CONFIRMED stocks? (y/n): ")
        
        return confirmation.lower() == 'y'
    
    def display_orders_for_confirmation(self, orders, available_capital):
        """Display orders and get user confirmation for G Pattern strategy"""
        if not orders:
            print("\n❌ No orders to place. All stocks may already be in portfolio or none match criteria.")
            return False
        
        # Separate orders by category
        confirmed_orders = [o for o in orders if o.get('category') == 'G_PATTERN_CONFIRMED']
        emerging_orders = [o for o in orders if o.get('category') == 'PATTERN_EMERGING']
        
        # Calculate totals
        total_capital_used = sum(order['position_value'] for order in orders)
        total_allocation_percent = (total_capital_used / available_capital) * 100
        
        print("\n" + "="*80)
        print("📊 G PATTERN AUTO TRADER - CATEGORY-BASED ORDER CONFIRMATION")
        print("="*80)
        print(f"\nAccount: {self.user_name}")
        print(f"Source: G_Pattern_Summary.txt recommendations")
        print(f"\nAvailable Capital: ₹{available_capital:,.2f}")
        print(f"Total Allocation: ₹{total_capital_used:,.2f} ({total_allocation_percent:.1f}% of available capital)")
        
        # Display G_PATTERN_CONFIRMED orders if any
        if confirmed_orders:
            confirmed_total = sum(o['position_value'] for o in confirmed_orders)
            confirmed_percent = (confirmed_total / available_capital) * 100
            print("\n" + "-"*80)
            print(f"🟢 G PATTERN CONFIRMED (10% allocation per position)")
            print(f"   Total: ₹{confirmed_total:,.2f} ({confirmed_percent:.1f}% of capital)")
            print("-"*80)
            
            for i, order in enumerate(confirmed_orders, 1):
                ticker = order['ticker']
                entry = order['entry_price']
                sl = order['stop_loss']
                tp = order['target1']
                score = order['probability_score']
                pattern = order['pattern']
                shares = order['quantity']
                value = order['position_value']
                
                print(f"\n{i}. {ticker}")
                print(f"   Score: {score:.1f}% | Pattern: {pattern}")
                print(f"   Entry: ₹{entry:.2f} | Stop Loss: ₹{sl:.2f} | Target: ₹{tp:.2f}")
                print(f"   Quantity: {shares} shares | Investment: ₹{value:,.2f}")
        
        # Display PATTERN_EMERGING orders if any
        if emerging_orders:
            emerging_total = sum(o['position_value'] for o in emerging_orders)
            emerging_percent = (emerging_total / available_capital) * 100
            print("\n" + "-"*80)
            print(f"🟡 PATTERN EMERGING/DEVELOPING (5% allocation per position)")
            print(f"   Total: ₹{emerging_total:,.2f} ({emerging_percent:.1f}% of capital)")
            print("-"*80)
            
            start_num = len(confirmed_orders) + 1
            for i, order in enumerate(emerging_orders, start_num):
                ticker = order['ticker']
                entry = order['entry_price']
                sl = order['stop_loss']
                tp = order['target1']
                score = order['probability_score']
                pattern = order['pattern']
                shares = order['quantity']
                value = order['position_value']
                
                print(f"\n{i}. {ticker}")
                print(f"   Score: {score:.1f}% | Pattern: {pattern}")
                print(f"   Entry: ₹{entry:.2f} | Stop Loss: ₹{sl:.2f} | Target: ₹{tp:.2f}")
                print(f"   Quantity: {shares} shares | Investment: ₹{value:,.2f}")
        
        print("\n" + "-"*80)
        print(f"SUMMARY:")
        print(f"Total Positions: {len(orders)}")
        if confirmed_orders:
            print(f"  - G Pattern Confirmed: {len(confirmed_orders)} positions")
        if emerging_orders:
            print(f"  - Pattern Emerging: {len(emerging_orders)} positions")
        print(f"Total Investment: ₹{total_capital_used:,.2f}")
        print(f"Remaining Capital: ₹{available_capital - total_capital_used:,.2f}")
        print("-"*80)
        
        print("\n⚠️  ALLOCATION STRATEGY:")
        print("  - G PATTERN CONFIRMED: 10% of available funds per position")
        print("  - PATTERN EMERGING/DEVELOPING: 5% of available funds per position")
        
        # Get user confirmation
        confirmation = input(f"\nPlace positions in these {len(orders)} stocks? (y/n): ")
        
        return confirmation.lower() == 'y'
    
    
    def execute_orders(self, orders, available_capital):
        """Execute confirmed orders following place_orders_daily.py pattern"""
        successful_orders = []
        order_details = []
        
        logger.info(f"Placing orders for {len(orders)} stocks...")
        
        for order in orders:
            ticker = order['ticker']
            stop_loss = order['stop_loss']
            target_price = order['target1']
            risk_reward = order.get('risk_reward_ratio', 0)
            entry_price = order['entry_price']
            position_size = order['quantity']
            
            # Initialize order detail record
            order_detail = {
                'ticker': ticker,
                'g_pattern_entry_price': entry_price,
                'stop_loss': stop_loss,
                'target_price': target_price,
                'risk_reward_ratio': risk_reward,
                'order_timestamp': datetime.datetime.now().isoformat(),
                'order_success': False,
                'gtt_success': False,
                'error_message': None,
                'pattern': order.get('pattern', 'G_Pattern'),
                'score': order.get('score', 0),
                'days_tracked': order.get('days_tracked', 0),
                'sector': order.get('sector', 'Unknown'),
                'position_size': position_size,
                'current_price': entry_price,
                'investment_amount': order['position_value'],
                'category': order.get('category', 'G_PATTERN_CONFIRMED'),
                'allocation_percent': self.config.getfloat('G_PATTERN_TRADING', 'g_pattern_confirmed_allocation_percent', fallback=15.0)
            }
            
            try:
                category = order.get('category', 'G_PATTERN_CONFIRMED')
                allocation = order_detail['allocation_percent']
                logger.info(f"Placing order for {ticker}: {position_size} shares at ₹{entry_price:.2f}")
                logger.info(f"  Category: {category} ({allocation}% allocation)")
                logger.info(f"  Score: {order.get('score', 0)}, Days: {order.get('days_tracked', 0)}")
                logger.info(f"  SL: ₹{stop_loss:.2f}, Target: ₹{target_price:.2f}")
                
                # Place the order - use MARKET order type
                order_id = self.kite.place_order(
                    variety="regular",
                    exchange="NSE",
                    tradingsymbol=ticker,
                    transaction_type="BUY",
                    quantity=position_size,
                    order_type="MARKET",
                    product=self.config.get('DEFAULT', 'product_type', fallback='CNC'),
                    validity="DAY"
                )
                logger.info(f"Order placed successfully for {ticker}: Order ID {order_id}")
                
                order_detail['order_success'] = True
                order_detail['order_id'] = order_id
                successful_orders.append(ticker)
                
                # Small delay between orders
                time.sleep(1)
                
            except Exception as e:
                order_detail['error_message'] = str(e)
                logger.error(f"Error placing order for {ticker}: {e}")
            
            order_details.append(order_detail)
        
        return successful_orders, order_details
    
    def run(self):
        """Main execution flow for G Pattern Confirmed stocks only"""
        try:
            logger.info("Starting G Pattern Auto Trader - G PATTERN CONFIRMED Only")
            print("\n🔍 G Pattern Auto Trader - Trading G PATTERN CONFIRMED stocks only...")
            
            # Get G Pattern Confirmed stocks from master list
            confirmed_df = self.get_confirmed_tickers_from_master()
            
            if confirmed_df.empty:
                print("\n❌ No G PATTERN CONFIRMED stocks found in master list")
                return
            
            # Display summary
            print("\n📊 G Pattern Master Analysis:")
            print(f"  - G PATTERN CONFIRMED: {len(confirmed_df)} stocks")
            
            # Get available capital
            available_capital = self.get_available_capital()
            if available_capital is None or available_capital <= 0:
                logger.error("Could not get available capital or capital is zero")
                print("❌ Could not get available capital or capital is zero")
                return
            
            # Load parameters
            params = self.get_position_sizing_params()
            allocation_percent = params['g_pattern_confirmed_allocation_percent']
            
            print(f"\n💰 Capital Analysis:")
            print(f"  - Available Capital: ₹{available_capital:,.2f}")
            print(f"  - G Pattern Allocation: {allocation_percent}% of capital")
            print(f"  - Total Allocation: ₹{available_capital * allocation_percent / 100:,.2f}")
            
            # Prepare orders for confirmed stocks only
            orders = self.prepare_orders_for_confirmed_only(confirmed_df, available_capital, params)
            
            if not orders:
                print("❌ No valid orders to place after filtering existing positions")
                return
            
            # Get user confirmation
            if self.display_orders_for_confirmed_only(orders, available_capital, allocation_percent):
                # Execute orders
                successful_orders, order_details = self.execute_orders(orders, available_capital)
                
                # Save order information - use master file path instead of report file
                master_file = os.path.join(MASTER_DIR, "G_Pattern_Master_List.xlsx")
                saved_file = self.save_order_information(order_details, master_file, available_capital, successful_orders)
                
                # Show summary
                total_invested = sum([detail.get('investment_amount', 0) for detail in order_details if detail.get('order_success', False)])

                print(f"\nOrder placement complete for {self.user_name}!")
                print(f"Successfully placed {len(successful_orders)} out of {len(orders)} orders.")
                print(f"Total investment: ₹{total_invested:,.2f} ({(total_invested/available_capital)*100:.1f}% of capital)")
                print(f"Remaining capital: ₹{available_capital - total_invested:,.2f}")

                if successful_orders:
                    print(f"\nSuccessful orders:")
                    for ticker in successful_orders:
                        detail = next((d for d in order_details if d['ticker'] == ticker), {})
                        investment = detail.get('investment_amount', 0)
                        shares = detail.get('position_size', 0)
                        price = detail.get('current_price', 0)
                        sector = detail.get('sector', 'Unknown')
                        print(f"  ✓ {ticker} ({sector}): {shares} shares @ ₹{price:.2f} = ₹{investment:,.2f}")

                failed_orders = [detail for detail in order_details if not detail.get('order_success', False)]
                if failed_orders:
                    print(f"\nFailed orders:")
                    for detail in failed_orders:
                        ticker = detail['ticker']
                        error = detail.get('error_message', 'Unknown error')
                        print(f"  ✗ {ticker}: {error}")

                # Show next steps
                print("\n📅 Next Steps:")
                print(f"  - Monitor G Pattern Confirmed positions")
                print(f"  - Each position allocated {allocation_percent}% ÷ {len(orders)} = {allocation_percent/len(orders):.2f}% of capital")
                print(f"  - Run this tool daily to check for new G Pattern Confirmed stocks")

                if saved_file:
                    print(f"\nOrder information saved to: {os.path.basename(saved_file)}")
            else:
                print("\nOrder placement cancelled by user.")
        
        except Exception as e:
            logger.error(f"Error in auto trader: {e}")
            print(f"\n❌ Error: {e}")
    
    def get_available_capital(self):
        """Get available capital from Zerodha account"""
        try:
            # Get margin information
            margins = self.kite.margins()

            # Extract available cash from equity segment
            equity_margin = margins.get('equity', {})
            available_cash = equity_margin.get('available', {}).get('cash', 0)

            logger.info(f"Available capital: ₹{available_cash}")
            return float(available_cash)
        except Exception as e:
            logger.error(f"Error getting available capital: {e}")
            return None
    
    def save_order_information(self, order_details, report_file, available_capital, successful_orders):
        """Save order information to user-specific Current_Orders folder"""
        try:
            # Get deployment percentage from config
            deployment_percent = float(self.config.get('DEFAULT', 'capital_deployment_percent', fallback=50.0))
            usable_capital = available_capital * (deployment_percent / 100.0)

            # Create user-specific Current_Orders directory
            current_orders_dir = os.path.join(DAILY_DIR, "Current_Orders", self.user_name)
            os.makedirs(current_orders_dir, exist_ok=True)

            # Create timestamp for filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Prepare summary information
            summary_info = {
                "user_profile": self.user_name,
                "timestamp": datetime.datetime.now().isoformat(),
                "report_file_used": os.path.basename(report_file),
                "available_capital": available_capital,
                "usable_capital": usable_capital,
                "capital_utilization_percent": deployment_percent,
                "min_probability_score": 65.0,
                "total_orders_attempted": len(order_details),
                "successful_orders": len(successful_orders),
                "total_investment": sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]),
                "orders": order_details
            }

            # Save as JSON
            json_filename = f"g_pattern_orders_{self.user_name}_{timestamp}.json"
            json_filepath = os.path.join(current_orders_dir, json_filename)

            with open(json_filepath, 'w') as f:
                json.dump(summary_info, f, indent=2, default=str)

            # Save as Excel for easy viewing
            excel_filename = f"g_pattern_orders_{self.user_name}_{timestamp}.xlsx"
            excel_filepath = os.path.join(current_orders_dir, excel_filename)

            # Create DataFrame for Excel
            df_orders = pd.DataFrame(order_details)

            # Create summary sheet data
            summary_data = {
                'Metric': [
                    'User Profile',
                    'Timestamp',
                    'Report File Used',
                    'Available Capital',
                    f'Usable Capital ({deployment_percent:.0f}%)',
                    'Min Probability Score',
                    'Total Orders Attempted',
                    'Successful Orders',
                    'Total Investment',
                    'Remaining Capital'
                ],
                'Value': [
                    self.user_name,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    os.path.basename(report_file),
                    f"₹{available_capital:,.2f}",
                    f"₹{usable_capital:,.2f}",
                    "65%",
                    len(order_details),
                    len(successful_orders),
                    f"₹{sum([o.get('investment_amount', 0) for o in order_details if o.get('order_success', False)]):,.2f}",
                    f"₹{available_capital - usable_capital:,.2f}"
                ]
            }
            df_summary = pd.DataFrame(summary_data)

            # Write to Excel with multiple sheets
            with pd.ExcelWriter(excel_filepath, engine='openpyxl') as writer:
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
                df_orders.to_excel(writer, sheet_name='Order_Details', index=False)

            logger.info(f"Order information saved to: {json_filepath} and {excel_filepath}")
            return excel_filepath

        except Exception as e:
            logger.error(f"Error saving order information: {e}")
            return ""

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

def main():
    """Main entry point with multi-user support"""
    # Check if market is open
    now = datetime.datetime.now()
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    
    if not (market_open <= now.time() <= market_close) and not any(arg in sys.argv for arg in ['--force', '-f']):
        print("\n⚠️  Market is closed. Use --force to run anyway.")
        return
    
    # Load config
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    # Get available users
    available_users = get_available_users(config)
    if not available_users:
        print("\n❌ No valid user credentials found in config.ini")
        return
    
    # Check if user specified via command line
    user_credentials = None
    for i, arg in enumerate(sys.argv):
        if arg in ['--user', '-u'] and i + 1 < len(sys.argv):
            user_name = sys.argv[i + 1]
            # Find matching user
            for user in available_users:
                if user.name == user_name:
                    user_credentials = user
                    break
            if not user_credentials:
                print(f"\n❌ User '{user_name}' not found in config.ini")
                return
            break
    
    # If no user specified, prompt for selection
    if not user_credentials:
        user_credentials = select_user(available_users)
        if not user_credentials:
            return
    
    # Set up user context
    context_manager = get_context_manager()
    context_manager.set_current_user(user_credentials.name, user_credentials)
    
    print(f"\n🔐 Selected account: {user_credentials.name}")
    
    # Run auto trader
    trader = GPatternAutoTrader(user_credentials=user_credentials)
    trader.run()

if __name__ == "__main__":
    main()