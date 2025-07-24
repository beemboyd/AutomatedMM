#!/usr/bin/env python3
"""
VSR Momentum Order Placement Script
Places orders for high-momentum tickers identified by VSR tracker
Designed to ride momentum with proper risk management
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
import pandas as pd
import requests
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from order_manager import OrderManager
from user_context_manager import UserContextManager
from state_manager import StateManager

class VSRMomentumTrader:
    """Places orders based on VSR momentum signals"""
    
    def __init__(self, user_name='Sai', mode='LIVE', max_positions=5):
        self.user_name = user_name
        self.mode = mode
        self.max_positions = max_positions
        
        # Initialize managers
        self.user_manager = UserContextManager()
        self.order_manager = OrderManager(user_name=user_name, mode=mode)
        self.state_manager = StateManager(user_name=user_name)
        
        # Setup logging
        self.setup_logging()
        
        # Configuration
        self.config = self.load_config()
        
        # Entry criteria
        self.min_score = 80  # Minimum VSR score
        self.min_vsr = 2.0   # Minimum VSR ratio
        self.min_momentum = 2.0  # Minimum momentum %
        self.max_momentum = 10.0  # Maximum momentum % (avoid extended moves)
        
        # Risk parameters
        self.position_size_pct = 2.0  # % of capital per position
        self.initial_stop_loss_pct = 3.0  # Initial stop loss %
        self.trailing_stop_activation = 2.0  # Activate trailing stop at 2% profit
        self.trailing_stop_distance = 1.5  # Trail by 1.5% from peak
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = f"../logs/{self.user_name}"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"vsr_momentum_orders_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """Load configuration from config.ini"""
        config_path = "../config.ini"
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        return config
        
    def fetch_vsr_tickers(self) -> List[Dict]:
        """Fetch current VSR tickers from dashboard API"""
        try:
            # Call VSR dashboard API
            response = requests.get('http://localhost:3001/api/trending-tickers', timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Get all tickers from categories
                all_tickers = []
                for category in ['perfect_scores', 'high_scores', 'high_vsr', 'high_momentum']:
                    if category in data['categories']:
                        all_tickers.extend(data['categories'][category])
                
                # Remove duplicates based on ticker symbol
                unique_tickers = {}
                for ticker in all_tickers:
                    symbol = ticker['ticker']
                    if symbol not in unique_tickers or ticker['score'] > unique_tickers[symbol]['score']:
                        unique_tickers[symbol] = ticker
                
                return list(unique_tickers.values())
            else:
                self.logger.error(f"Failed to fetch VSR data: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error fetching VSR tickers: {e}")
            return []
    
    def filter_momentum_candidates(self, tickers: List[Dict]) -> List[Dict]:
        """Filter tickers based on momentum criteria"""
        candidates = []
        
        for ticker in tickers:
            # Check basic criteria
            if (ticker.get('score', 0) >= self.min_score and
                ticker.get('vsr', 0) >= self.min_vsr and
                self.min_momentum <= ticker.get('momentum', 0) <= self.max_momentum):
                
                # Additional filters
                # 1. Must have momentum build (if available)
                if ticker.get('build', 0) > 0:
                    score_boost = 10
                else:
                    score_boost = 0
                
                # 2. Prefer tickers tracked for at least 1 day
                days_tracked = ticker.get('days_tracked', 0)
                
                # 3. Allow duplicate positions (as requested by user)
                # Calculate priority score
                priority = (
                    ticker['score'] + 
                    score_boost + 
                    (ticker['vsr'] * 10) + 
                    (ticker['momentum'] * 5) +
                    (days_tracked * 5)
                )
                
                ticker['priority'] = priority
                candidates.append(ticker)
                    
        # Sort by priority
        candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        return candidates
    
    def calculate_position_size(self, ticker_data: Dict) -> int:
        """Calculate position size based on risk parameters"""
        try:
            # Get account value
            account_value = self.order_manager.get_account_value()
            if not account_value:
                self.logger.error("Could not fetch account value")
                return 0
            
            # Calculate position value
            position_value = account_value * (self.position_size_pct / 100)
            
            # Get current price
            current_price = ticker_data.get('price', 0)
            if current_price <= 0:
                return 0
            
            # Calculate quantity
            quantity = int(position_value / current_price)
            
            # Apply minimum quantity
            min_quantity = 1
            quantity = max(quantity, min_quantity)
            
            # Check if we have enough margin
            required_margin = quantity * current_price
            available_margin = self.order_manager.get_available_margin()
            
            if available_margin and required_margin > available_margin:
                # Adjust quantity to fit available margin
                quantity = int(available_margin * 0.95 / current_price)  # Use 95% of available
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0
    
    def place_momentum_order(self, ticker_data: Dict) -> bool:
        """Place order for momentum ticker"""
        try:
            symbol = ticker_data['ticker']
            current_price = ticker_data['price']
            
            # Calculate position size
            quantity = self.calculate_position_size(ticker_data)
            if quantity <= 0:
                self.logger.warning(f"Invalid quantity for {symbol}")
                return False
            
            # Log entry signal
            self.logger.info(f"""
            ═══════════════════════════════════════
            VSR MOMENTUM ENTRY SIGNAL
            Symbol: {symbol}
            Score: {ticker_data['score']}
            VSR: {ticker_data['vsr']:.2f}
            Momentum: {ticker_data['momentum']:.2f}%
            Price: ₹{current_price}
            Quantity: {quantity}
            Days Tracked: {ticker_data.get('days_tracked', 0)}
            ═══════════════════════════════════════
            """)
            
            # Place LIMIT order at current price
            success = self.order_manager.place_order(
                tradingsymbol=symbol,
                transaction_type="BUY",
                order_type="LIMIT",
                quantity=quantity,
                price=current_price,
                product_type="MIS",  # Intraday for momentum trades
                tag="VSR_MOMENTUM"
            )
            
            if success:
                # Store entry metadata
                entry_data = {
                    'entry_time': datetime.now().isoformat(),
                    'entry_price': current_price,
                    'entry_score': ticker_data['score'],
                    'entry_vsr': ticker_data['vsr'],
                    'entry_momentum': ticker_data['momentum'],
                    'stop_loss': current_price * (1 - self.initial_stop_loss_pct / 100),
                    'peak_price': current_price,
                    'trailing_active': False,
                    'strategy': 'VSR_MOMENTUM'
                }
                
                # Save to state
                self.state_manager.update_position_metadata(symbol, entry_data)
                
                self.logger.info(f"✅ Successfully placed VSR momentum order for {symbol}")
                return True
            else:
                self.logger.error(f"❌ Failed to place order for {symbol}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing momentum order: {e}")
            return False
    
    def display_order_summary(self, candidates: List[Dict], current_positions: int):
        """Display order summary for user confirmation"""
        print("\n" + "="*80)
        print("VSR MOMENTUM ORDER SUMMARY")
        print("="*80)
        
        # Account info
        account_value = self.order_manager.get_account_value()
        available_margin = self.order_manager.get_available_margin()
        
        print(f"\nAccount Status:")
        print(f"- Account Value: ₹{account_value:,.2f}")
        print(f"- Available Margin: ₹{available_margin:,.2f}")
        print(f"- Current VSR Positions: {current_positions}/{self.max_positions}")
        print(f"- Position Size: {self.position_size_pct}% of capital")
        
        print(f"\nProposed Orders (MIS - Intraday):")
        print("-" * 80)
        print(f"{'Ticker':<10} {'Score':>6} {'VSR':>6} {'Mom%':>6} {'Price':>10} {'Qty':>6} {'Value':>12} {'Priority':>8}")
        print("-" * 80)
        
        total_value = 0
        for candidate in candidates:
            quantity = self.calculate_position_size(candidate)
            value = quantity * candidate['price']
            total_value += value
            
            print(f"{candidate['ticker']:<10} {candidate['score']:>6} {candidate['vsr']:>6.2f} "
                  f"{candidate['momentum']:>6.1f} ₹{candidate['price']:>9.2f} {quantity:>6} "
                  f"₹{value:>11,.2f} {candidate['priority']:>8.1f}")
        
        print("-" * 80)
        print(f"{'TOTAL':<36} {len(candidates)} orders {'₹':>18}{total_value:>11,.2f}")
        print("="*80)
        
        # Risk warning
        print("\n⚠️  Risk Disclosure:")
        print("- Maximum Loss per Trade: 3%")
        print("- All positions will be squared off by 3:20 PM (MIS)")
        print("- Momentum trading carries high risk")
    
    def check_existing_positions(self):
        """Check and update existing VSR momentum positions"""
        try:
            positions = self.state_manager.get_positions()
            vsr_positions = {
                k: v for k, v in positions.items() 
                if v.get('metadata', {}).get('strategy') == 'VSR_MOMENTUM'
            }
            
            if vsr_positions:
                self.logger.info(f"Monitoring {len(vsr_positions)} VSR momentum positions")
                
                # Note: Exit logic should be handled by SL_watchdog.py
                # This is just for monitoring
                for pos_id, position in vsr_positions.items():
                    symbol = position['tradingsymbol']
                    entry_price = position['metadata'].get('entry_price', position['average_price'])
                    current_price = self.order_manager.get_ltp(symbol)
                    
                    if current_price:
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        self.logger.info(f"{symbol}: Entry: ₹{entry_price:.2f}, Current: ₹{current_price:.2f}, PnL: {pnl_pct:.2f}%")
                        
        except Exception as e:
            self.logger.error(f"Error checking positions: {e}")
    
    def run(self):
        """Main execution"""
        try:
            self.logger.info("="*50)
            self.logger.info("Starting VSR Momentum Trading")
            self.logger.info(f"User: {self.user_name}, Mode: {self.mode}")
            self.logger.info("="*50)
            
            # Check market hours
            now = datetime.now()
            if now.weekday() >= 5:  # Weekend
                self.logger.info("Market closed (weekend)")
                return
                
            market_open = now.replace(hour=9, minute=15, second=0)
            market_close = now.replace(hour=15, minute=0, second=0)  # Close at 3 PM for momentum
            
            if not (market_open <= now <= market_close):
                self.logger.info("Outside market hours")
                return
            
            # Check existing positions
            self.check_existing_positions()
            
            # Get current positions count (including duplicates)
            current_positions = self.state_manager.get_positions()
            vsr_positions_count = sum(
                1 for p in current_positions.values() 
                if p.get('metadata', {}).get('strategy') == 'VSR_MOMENTUM'
            )
            
            if vsr_positions_count >= self.max_positions:
                self.logger.info(f"Maximum positions reached ({vsr_positions_count}/{self.max_positions})")
                return
            
            # Fetch VSR tickers
            vsr_tickers = self.fetch_vsr_tickers()
            if not vsr_tickers:
                self.logger.warning("No VSR tickers fetched")
                return
            
            self.logger.info(f"Fetched {len(vsr_tickers)} VSR tickers")
            
            # Filter candidates
            candidates = self.filter_momentum_candidates(vsr_tickers)
            self.logger.info(f"Found {len(candidates)} momentum candidates")
            
            # Calculate how many new orders we can place
            max_new_orders = self.max_positions - vsr_positions_count
            
            # Display candidates and get confirmation
            if candidates:
                self.display_order_summary(candidates[:max_new_orders], vsr_positions_count)
                
                # Get user confirmation
                confirm = input(f"\nProceed with placing MIS momentum orders? (y/n): ")
                if confirm.lower() != 'y':
                    self.logger.info("Order placement cancelled by user")
                    return
            
            # Place orders for top candidates
            orders_placed = 0
            
            for candidate in candidates[:max_new_orders]:
                if self.place_momentum_order(candidate):
                    orders_placed += 1
                    
                    # Add delay between orders
                    if orders_placed < max_new_orders and len(candidates) > orders_placed:
                        import time
                        time.sleep(2)
            
            self.logger.info(f"Placed {orders_placed} new momentum orders")
            
        except Exception as e:
            self.logger.error(f"Error in main execution: {e}")
            
        finally:
            self.logger.info("VSR Momentum Trading completed")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VSR Momentum Order Placement')
    parser.add_argument('--user', default='Sai', help='User name')
    parser.add_argument('--mode', default='LIVE', choices=['LIVE', 'PAPER'], help='Trading mode')
    parser.add_argument('--max-positions', type=int, default=5, help='Maximum positions')
    
    args = parser.parse_args()
    
    trader = VSRMomentumTrader(
        user_name=args.user,
        mode=args.mode,
        max_positions=args.max_positions
    )
    
    trader.run()

if __name__ == "__main__":
    main()