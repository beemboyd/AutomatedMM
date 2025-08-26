#!/usr/bin/env python3
"""
VSR Order Watchdog
Continuously monitors VSR signal tickers for:
1. Breakouts above 4-candle resistance (BUY signal)
2. Breakdown below 2-candle support (SELL signal)
Places limit orders when signals are detected
No state files - all tracking is in-memory only
"""

import os
import sys
import logging
import datetime
import time
import json
import requests
import configparser
from typing import List, Dict, Optional, Set

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
VSR_DASHBOARD_URL = "http://localhost:3001/api/trending-tickers"
VSR_JSON_FILE = "/Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json"
MIN_VSR_SCORE = 60  # Minimum VSR score to consider
MIN_MOMENTUM = 2.0  # Minimum positive momentum %
POSITION_SIZE_PERCENT = 1.0  # 1% of portfolio per position
MAX_POSITIONS = 5  # Maximum positions to take
POLL_INTERVAL = 60  # Check every 60 seconds
BREAKOUT_BUFFER = 0.005  # 0.5% above resistance for limit order
LOOKBACK_CANDLES_BUY = 4  # Number of previous hourly candles to check for resistance
LOOKBACK_CANDLES_SELL = 2  # Number of previous hourly candles to check for support

# Trading hours
MARKET_OPEN = datetime.time(9, 15)
MARKET_CLOSE = datetime.time(15, 20)  # Stop monitoring at 3:20 PM

class VSROrderWatchdog:
    def __init__(self, user_credentials: UserCredentials, config):
        """Initialize the watchdog"""
        self.user = user_credentials
        self.config = config
        self.setup_logging()
        
        # Set up user context
        context_manager = get_context_manager()
        context_manager.set_current_user(user_credentials.name, user_credentials)
        
        # Get managers
        self.data_handler = get_user_data_handler()
        self.state_manager = get_user_state_manager()
        self.order_manager = get_user_order_manager()
        
        # Track processed orders to avoid duplicates (in-memory only, no state files)
        self.processed_buy_orders = set()  # Set of tickers we've placed buy orders for today
        self.active_positions = {}  # Track active positions: {ticker: {'quantity': x, 'entry_price': y}}
        self.resistance_levels = {}  # Cache resistance levels for each ticker
        self.support_levels = {}  # Cache support levels for each ticker
        self.last_vsr_fetch = None  # Track when we last fetched VSR tickers
        self.vsr_tickers = []  # Current VSR ticker list
        
        # Initialize active positions from broker
        self.sync_active_positions()
        
        logging.info(f"VSR Order Watchdog initialized for user: {user_credentials.name}")
    
    def setup_logging(self):
        """Set up logging configuration"""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(script_dir, 'logs', self.user.name)
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'order_watchdog_vsr_{datetime.datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ],
            force=True
        )
    
    def sync_active_positions(self):
        """Sync active positions from broker (MIS positions only)"""
        try:
            positions = self.data_handler.kite.positions()
            self.active_positions.clear()
            
            for pos in positions.get('net', []):
                if (pos.get('product') == 'MIS' and 
                    int(pos.get('quantity', 0)) > 0):
                    
                    ticker = pos.get('tradingsymbol')
                    self.active_positions[ticker] = {
                        'quantity': int(pos.get('quantity')),
                        'entry_price': float(pos.get('average_price', 0))
                    }
                    logging.info(f"Found active MIS position: {ticker} - {pos.get('quantity')} @ ₹{pos.get('average_price')}")
            
            logging.info(f"Synced {len(self.active_positions)} active MIS positions")
            
        except Exception as e:
            logging.error(f"Error syncing positions: {e}")
    
    def is_market_hours(self) -> bool:
        """Check if market is open"""
        now = datetime.datetime.now()
        current_time = now.time()
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        return MARKET_OPEN <= current_time <= MARKET_CLOSE
    
    def fetch_vsr_tickers(self) -> List[Dict]:
        """Fetch current VSR tickers from dashboard or file"""
        try:
            # Try API first
            response = requests.get(VSR_DASHBOARD_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                all_tickers = []
                categories = data.get('categories', {})
                
                for ticker_data in categories.get('all_tickers', []):
                    ticker = ticker_data.get('ticker')
                    score = ticker_data.get('score', 0)
                    momentum = ticker_data.get('momentum', 0)
                    
                    if ticker and score >= MIN_VSR_SCORE and momentum >= MIN_MOMENTUM:
                        all_tickers.append({
                            'ticker': ticker,
                            'score': score,
                            'momentum': momentum
                        })
                
                logging.info(f"Fetched {len(all_tickers)} VSR tickers from API")
                return sorted(all_tickers, key=lambda x: (x['score'], x['momentum']), reverse=True)
                
        except Exception as e:
            logging.error(f"Error fetching from API: {e}")
        
        # Fallback to JSON file
        try:
            with open(VSR_JSON_FILE, 'r') as f:
                data = json.load(f)
            
            all_tickers = []
            tickers_data = data.get('tickers', {})
            
            for ticker, info in tickers_data.items():
                momentum_history = info.get('momentum_history', [])
                if momentum_history:
                    latest_momentum = momentum_history[-1].get('momentum', 0)
                    appearances = info.get('appearances', 0)
                    positive_days = info.get('positive_momentum_days', 0)
                    days_tracked = info.get('days_tracked', 0)
                    
                    if days_tracked > 0:
                        score = min(100, int((appearances / 10) * (positive_days / days_tracked + 1)))
                    else:
                        score = 0
                    
                    if score >= MIN_VSR_SCORE and latest_momentum >= MIN_MOMENTUM:
                        all_tickers.append({
                            'ticker': ticker,
                            'score': score,
                            'momentum': latest_momentum
                        })
            
            logging.info(f"Fetched {len(all_tickers)} VSR tickers from file")
            return sorted(all_tickers, key=lambda x: (x['score'], x['momentum']), reverse=True)
            
        except Exception as e:
            logging.error(f"Error fetching from file: {e}")
            return []
    
    def calculate_resistance_level(self, ticker: str) -> Optional[float]:
        """Calculate resistance level from previous 4 hourly candles"""
        try:
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=2)
            
            # Fetch hourly data
            hourly_data = self.data_handler.fetch_historical_data(
                ticker,
                interval="60minute",
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )
            
            if hourly_data is None or hourly_data.empty:
                return None
            
            # Remove current incomplete candle
            if len(hourly_data) > 1:
                completed_candles = hourly_data.iloc[:-1]
            else:
                return None
            
            # Get last 4 completed candles
            if len(completed_candles) < LOOKBACK_CANDLES_BUY:
                recent_candles = completed_candles
            else:
                recent_candles = completed_candles.iloc[-LOOKBACK_CANDLES_BUY:]
            
            # Find highest high (resistance level)
            resistance = float(recent_candles['High'].max())
            
            logging.debug(f"{ticker}: Resistance level ₹{resistance:.2f} from {len(recent_candles)} candles")
            return resistance
            
        except Exception as e:
            logging.error(f"Error calculating resistance for {ticker}: {e}")
            return None
    
    def calculate_support_level(self, ticker: str) -> Optional[float]:
        """Calculate support level from previous 2 hourly candles"""
        try:
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=2)
            
            # Fetch hourly data
            hourly_data = self.data_handler.fetch_historical_data(
                ticker,
                interval="60minute",
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )
            
            if hourly_data is None or hourly_data.empty:
                return None
            
            # Remove current incomplete candle
            if len(hourly_data) > 1:
                completed_candles = hourly_data.iloc[:-1]
            else:
                return None
            
            # Get last 2 completed candles for support
            if len(completed_candles) < LOOKBACK_CANDLES_SELL:
                recent_candles = completed_candles
            else:
                recent_candles = completed_candles.iloc[-LOOKBACK_CANDLES_SELL:]
            
            # Find lowest low (support level)
            support = float(recent_candles['Low'].min())
            
            logging.debug(f"{ticker}: Support level ₹{support:.2f} from {len(recent_candles)} candles")
            return support
            
        except Exception as e:
            logging.error(f"Error calculating support for {ticker}: {e}")
            return None
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current market price"""
        try:
            quote = self.data_handler.kite.quote([f"NSE:{ticker}"])
            if quote and f"NSE:{ticker}" in quote:
                return float(quote[f"NSE:{ticker}"].get('last_price', 0))
        except Exception as e:
            logging.error(f"Error getting price for {ticker}: {e}")
        return None
    
    def check_existing_buy_order(self, ticker: str) -> bool:
        """Check if we already have a pending BUY order for this ticker"""
        try:
            # Check open orders
            orders = self.data_handler.kite.orders()
            for order in orders:
                if (order.get('tradingsymbol') == ticker and 
                    order.get('status') in ['OPEN', 'PENDING', 'TRIGGER PENDING'] and
                    order.get('transaction_type') == 'BUY'):
                    return True
            
        except Exception as e:
            logging.error(f"Error checking buy order for {ticker}: {e}")
        
        return False
    
    def calculate_position_size(self, price: float) -> int:
        """Calculate position size as 1% of portfolio"""
        try:
            margins = self.data_handler.kite.margins()
            equity_margin = margins.get('equity', {})
            available_cash = float(equity_margin.get('available', {}).get('cash', 0))
            
            holdings = self.data_handler.kite.holdings()
            holdings_value = sum(
                float(h.get('quantity', 0)) * float(h.get('last_price', 0))
                for h in holdings
            )
            
            portfolio_value = available_cash + holdings_value
            position_value = portfolio_value * (POSITION_SIZE_PERCENT / 100)
            quantity = int(position_value / price)
            
            return max(1, quantity)
            
        except Exception as e:
            logging.error(f"Error calculating position size: {e}")
            return 1
    
    def place_breakout_order(self, ticker: str, resistance: float, current_price: float) -> bool:
        """Place limit buy order at 0.5% above resistance"""
        try:
            # Calculate limit price (0.5% above resistance)
            limit_price = round(resistance * (1 + BREAKOUT_BUFFER), 2)
            
            # Calculate position size
            quantity = self.calculate_position_size(limit_price)
            
            # Calculate stop loss (2% below entry)
            stop_loss = round(limit_price * 0.98, 2)
            
            logging.info(f"🎯 BREAKOUT DETECTED for {ticker}!")
            logging.info(f"  Current: ₹{current_price:.2f} > Resistance: ₹{resistance:.2f}")
            logging.info(f"  Placing LIMIT BUY: {quantity} @ ₹{limit_price:.2f}")
            logging.info(f"  Stop Loss: ₹{stop_loss:.2f}")
            
            # Place the order
            order_id = self.order_manager.place_order(
                tradingsymbol=ticker,
                transaction_type='BUY',
                order_type='LIMIT',
                quantity=quantity,
                price=limit_price,
                product_type='MIS'  # Intraday
            )
            
            if order_id:
                # Update state manager
                self.state_manager.add_position(
                    ticker=ticker,
                    quantity=quantity,
                    entry_price=limit_price,
                    stop_loss=stop_loss,
                    product_type='MIS',
                    order_id=order_id,
                    metadata={
                        'strategy': 'VSR_BREAKOUT_WATCHDOG',
                        'resistance_level': resistance,
                        'breakout_price': current_price,
                        'entry_time': datetime.datetime.now().isoformat(),
                        'order_type': 'LIMIT'
                    }
                )
                
                # Mark as processed and add to active positions
                self.processed_buy_orders.add(ticker)
                self.active_positions[ticker] = {
                    'quantity': quantity,
                    'entry_price': limit_price
                }
                
                logging.info(f"✅ Buy order placed successfully: {order_id}")
                return True
            else:
                logging.error(f"Failed to place buy order for {ticker}")
                return False
                
        except Exception as e:
            logging.error(f"Error placing buy order for {ticker}: {e}")
            return False
    
    def place_sell_order(self, ticker: str, support: float, current_price: float) -> bool:
        """Place limit sell order when price breaks below support"""
        try:
            # Get position details
            position = self.active_positions.get(ticker)
            if not position:
                logging.warning(f"No active position found for {ticker}")
                return False
            
            quantity = position['quantity']
            entry_price = position['entry_price']
            
            # Calculate sell price (market order for quick exit)
            logging.info(f"🔻 BREAKDOWN DETECTED for {ticker}!")
            logging.info(f"  Current: ₹{current_price:.2f} < Support: ₹{support:.2f}")
            logging.info(f"  Entry was at: ₹{entry_price:.2f}")
            
            # Calculate P&L
            pnl = (current_price - entry_price) * quantity
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            
            logging.info(f"  Expected P&L: ₹{pnl:.2f} ({pnl_pct:.2f}%)")
            logging.info(f"  Placing MARKET SELL: {quantity} shares")
            
            # Place market sell order for immediate exit
            order_id = self.order_manager.place_order(
                tradingsymbol=ticker,
                transaction_type='SELL',
                order_type='MARKET',
                quantity=quantity,
                product_type='MIS'  # Intraday
            )
            
            if order_id:
                # Remove from active positions
                del self.active_positions[ticker]
                
                # Update state manager (optional, since we're not using state files)
                self.state_manager.update_position(
                    ticker=ticker,
                    quantity=0,  # Position closed
                    metadata={
                        'exit_time': datetime.datetime.now().isoformat(),
                        'exit_reason': 'support_breakdown',
                        'support_level': support,
                        'exit_price': current_price
                    }
                )
                
                logging.info(f"✅ Sell order placed successfully: {order_id}")
                return True
            else:
                logging.error(f"Failed to place sell order for {ticker}")
                return False
                
        except Exception as e:
            logging.error(f"Error placing sell order for {ticker}: {e}")
            return False
    
    def monitor_ticker_for_buy(self, ticker_data: Dict) -> bool:
        """Monitor a ticker for buy signal (breakout above resistance)"""
        ticker = ticker_data['ticker']
        
        # Skip if already processed today or has active position
        if ticker in self.processed_buy_orders or ticker in self.active_positions:
            return False
        
        # Check if we already have a pending buy order
        if self.check_existing_buy_order(ticker):
            logging.debug(f"{ticker}: Already have pending buy order, skipping")
            return False
        
        # Get or update resistance level
        if ticker not in self.resistance_levels:
            resistance = self.calculate_resistance_level(ticker)
            if resistance:
                self.resistance_levels[ticker] = resistance
            else:
                return False
        else:
            resistance = self.resistance_levels[ticker]
        
        # Get current price
        current_price = self.get_current_price(ticker)
        if not current_price:
            return False
        
        # Check for breakout (current price > resistance)
        if current_price > resistance:
            # Clean breakout detected!
            breakout_pct = ((current_price - resistance) / resistance) * 100
            logging.info(f"📈 {ticker}: Breakout detected! Current ₹{current_price:.2f} > Resistance ₹{resistance:.2f} (+{breakout_pct:.2f}%)")
            
            # Place buy order
            return self.place_breakout_order(ticker, resistance, current_price)
        else:
            # Still in congestion
            gap_pct = ((resistance - current_price) / current_price) * 100
            logging.debug(f"{ticker}: In congestion. Current ₹{current_price:.2f} < Resistance ₹{resistance:.2f} (needs +{gap_pct:.2f}%)")
            return False
    
    def monitor_position_for_sell(self, ticker: str) -> bool:
        """Monitor an active position for sell signal (breakdown below support)"""
        # Only monitor if we have an active position
        if ticker not in self.active_positions:
            return False
        
        # Get or update support level
        if ticker not in self.support_levels:
            support = self.calculate_support_level(ticker)
            if support:
                self.support_levels[ticker] = support
            else:
                return False
        else:
            # Refresh support level periodically
            support = self.calculate_support_level(ticker)
            if support:
                self.support_levels[ticker] = support
            else:
                support = self.support_levels[ticker]
        
        # Get current price
        current_price = self.get_current_price(ticker)
        if not current_price:
            return False
        
        # Check for breakdown (current price < support)
        if current_price < support:
            # Breakdown detected!
            breakdown_pct = ((support - current_price) / support) * 100
            logging.info(f"📉 {ticker}: Breakdown detected! Current ₹{current_price:.2f} < Support ₹{support:.2f} (-{breakdown_pct:.2f}%)")
            
            # Place sell order
            return self.place_sell_order(ticker, support, current_price)
        else:
            # Still above support
            gap_pct = ((current_price - support) / support) * 100
            position = self.active_positions[ticker]
            pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
            logging.debug(f"{ticker}: Above support. Current ₹{current_price:.2f} > Support ₹{support:.2f} (+{gap_pct:.2f}%), P&L: {pnl_pct:.2f}%")
            return False
    
    def run_monitoring_cycle(self):
        """Run one monitoring cycle"""
        # Sync positions from broker at the start of each cycle
        self.sync_active_positions()
        
        # Refresh VSR tickers every 5 minutes
        now = datetime.datetime.now()
        if (self.last_vsr_fetch is None or 
            (now - self.last_vsr_fetch).seconds > 300):
            
            logging.info("Refreshing VSR ticker list...")
            self.vsr_tickers = self.fetch_vsr_tickers()
            self.last_vsr_fetch = now
            
            # Update resistance levels for new tickers
            for ticker_data in self.vsr_tickers[:10]:  # Monitor top 10
                ticker = ticker_data['ticker']
                if ticker not in self.resistance_levels:
                    resistance = self.calculate_resistance_level(ticker)
                    if resistance:
                        self.resistance_levels[ticker] = resistance
        
        # FIRST: Monitor existing positions for SELL signals
        logging.info(f"Monitoring {len(self.active_positions)} active positions for exit signals...")
        exits_triggered = 0
        
        for ticker in list(self.active_positions.keys()):  # Use list() to avoid dict change during iteration
            if self.monitor_position_for_sell(ticker):
                exits_triggered += 1
        
        if exits_triggered > 0:
            logging.info(f"🔻 Triggered {exits_triggered} exit orders")
        
        # SECOND: Monitor for new BUY signals if we have room
        active_count = len(self.active_positions)
        if active_count >= MAX_POSITIONS:
            logging.info(f"Max positions reached ({active_count}/{MAX_POSITIONS}), skipping buy monitoring")
            return
        
        # Monitor top tickers for breakouts
        available_slots = MAX_POSITIONS - active_count
        logging.info(f"Monitoring top {min(10, available_slots)} tickers for buy signals (slots available: {available_slots})...")
        
        buys_triggered = 0
        for ticker_data in self.vsr_tickers[:10]:  # Monitor top 10
            if self.monitor_ticker_for_buy(ticker_data):
                buys_triggered += 1
                
                # Check if we've reached max positions
                if len(self.active_positions) >= MAX_POSITIONS:
                    logging.info(f"Max positions reached, stopping buy monitoring")
                    break
        
        if buys_triggered > 0:
            logging.info(f"📈 Placed {buys_triggered} buy orders")
        
        # Summary
        logging.info(f"Cycle complete - Active positions: {len(self.active_positions)}, Buys: {buys_triggered}, Exits: {exits_triggered}")
    
    def run(self):
        """Main watchdog loop"""
        logging.info("="*80)
        logging.info("VSR ORDER WATCHDOG STARTED")
        logging.info(f"User: {self.user.name}")
        logging.info(f"Strategy: Buy on breakout above 4-candle resistance, Sell on breakdown below 2-candle support")
        logging.info(f"Min Score: {MIN_VSR_SCORE}, Min Momentum: {MIN_MOMENTUM}%")
        logging.info(f"Position Size: {POSITION_SIZE_PERCENT}%, Max Positions: {MAX_POSITIONS}")
        logging.info(f"Poll Interval: {POLL_INTERVAL} seconds")
        logging.info("="*80)
        
        try:
            while True:
                # Check market hours
                if not self.is_market_hours():
                    logging.info("Market closed, waiting...")
                    time.sleep(60)  # Check every minute
                    continue
                
                # Run monitoring cycle
                try:
                    self.run_monitoring_cycle()
                except Exception as e:
                    logging.error(f"Error in monitoring cycle: {e}")
                
                # Wait before next cycle
                logging.debug(f"Waiting {POLL_INTERVAL} seconds before next check...")
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            logging.info("\n" + "="*80)
            logging.info("VSR Order Watchdog stopped by user")
            logging.info(f"Total buy orders placed: {len(self.processed_buy_orders)}")
            if self.processed_buy_orders:
                logging.info(f"Buy tickers: {', '.join(self.processed_buy_orders)}")
            logging.info(f"Active positions remaining: {len(self.active_positions)}")
            if self.active_positions:
                logging.info(f"Open positions: {', '.join(self.active_positions.keys())}")
            logging.info("="*80)

def load_config():
    """Load configuration from config.ini"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found at {config_path}")
    
    config.read(config_path)
    return config

def get_user_credentials(config, user_name: str) -> Optional[UserCredentials]:
    """Get user credentials from config"""
    section = f'API_CREDENTIALS_{user_name}'
    
    if not config.has_section(section):
        return None
    
    return UserCredentials(
        name=user_name,
        api_key=config.get(section, 'api_key'),
        api_secret=config.get(section, 'api_secret'),
        access_token=config.get(section, 'access_token')
    )

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VSR Order Watchdog - Monitor and trade breakouts')
    parser.add_argument('-u', '--user', default='Sai', help='User account to use (default: Sai)')
    parser.add_argument('--test', action='store_true', help='Run in test mode (single cycle)')
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    
    # Get user credentials
    credentials = get_user_credentials(config, args.user)
    if not credentials:
        print(f"Error: No credentials found for user '{args.user}'")
        return
    
    # Create and run watchdog
    watchdog = VSROrderWatchdog(credentials, config)
    
    if args.test:
        # Test mode - run single cycle
        print("\nRunning in TEST MODE - Single cycle only\n")
        watchdog.run_monitoring_cycle()
        print("\nTest cycle completed")
    else:
        # Normal mode - continuous monitoring
        watchdog.run()

if __name__ == "__main__":
    main()