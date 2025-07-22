#!/usr/bin/env python3
"""
VSR-Based Paper Trading System with Time-Based Order Slicing
Monitors VSR tracker output and simulates order entries with slicing
"""

import os
import sys
import json
import time
import logging
import sqlite3
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VSRPaperTrader:
    def __init__(self, config_path: str = "config/paper_trading_config.json"):
        """Initialize the VSR Paper Trading System"""
        self.config = self.load_config(config_path)
        self.db_path = "data/paper_trades.db"
        self.positions = {}
        self.pending_slices = {}
        self.setup_database()
        self.running = False
        
        # Trading parameters
        self.capital = self.config.get('capital', 1000000)
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)
        self.max_positions = self.config.get('max_positions', 5)
        self.slice_schedule = self.config.get('slice_schedule', {
            "0": 0.25,    # T+0 min: 25%
            "3": 0.25,    # T+3 min: 25%
            "7": 0.25,    # T+7 min: 25%
            "15": 0.25    # T+15 min: 25%
        })
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        full_path = os.path.join(os.path.dirname(__file__), config_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            default_config = {
                "capital": 1000000,
                "risk_per_trade": 0.02,
                "max_positions": 5,
                "vsr_threshold": 3.0,
                "momentum_threshold": 75,
                "slice_schedule": {
                    "0": 0.25,
                    "3": 0.25,
                    "7": 0.25,
                    "15": 0.25
                },
                "trading_hours": {
                    "start": "09:30",
                    "end": "14:30"
                }
            }
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
    
    def setup_database(self):
        """Initialize SQLite database for paper trades"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                slice_number INTEGER,
                total_slices INTEGER,
                vsr REAL,
                momentum_score INTEGER,
                order_id TEXT UNIQUE,
                status TEXT DEFAULT 'PENDING'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT PRIMARY KEY,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                pnl REAL,
                vsr REAL,
                momentum_score INTEGER,
                entry_time DATETIME,
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'OPEN'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT CURRENT_DATE,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                total_pnl REAL,
                win_rate REAL,
                avg_win REAL,
                avg_loss REAL,
                sharpe_ratio REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_vsr_signals(self) -> List[Dict]:
        """Read VSR tracker output and filter for high-momentum stocks"""
        try:
            # Read from VSR tracker log or API
            vsr_log_path = "/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_" + datetime.now().strftime("%Y%m%d") + ".log"
            
            signals = []
            if os.path.exists(vsr_log_path):
                with open(vsr_log_path, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines
                    
                for line in lines:
                    if "Score:" in line and "VSR:" in line:
                        # Parse the VSR tracker output
                        parts = line.split('|')
                        if len(parts) >= 8:
                            try:
                                ticker = parts[0].split(']')[1].strip()
                                score = int(parts[1].split(':')[1].strip())
                                vsr = float(parts[2].split(':')[1].strip())
                                price = float(parts[3].split('₹')[1].strip().replace(',', ''))
                                
                                # Apply filters
                                if (score >= self.config['momentum_threshold'] and 
                                    vsr >= self.config['vsr_threshold'] and
                                    ticker not in self.positions):
                                    
                                    signals.append({
                                        'ticker': ticker,
                                        'score': score,
                                        'vsr': vsr,
                                        'price': price,
                                        'timestamp': datetime.now()
                                    })
                            except Exception as e:
                                continue
                                
            return signals
            
        except Exception as e:
            logger.error(f"Error reading VSR signals: {e}")
            return []
    
    def calculate_position_size(self, price: float) -> int:
        """Calculate position size based on risk management rules"""
        risk_amount = self.capital * self.risk_per_trade
        # Assuming 3% stop loss
        stop_loss_pct = 0.03
        position_value = risk_amount / stop_loss_pct
        
        # Check if we have enough capital
        available_capital = self.capital - sum(pos['quantity'] * pos['avg_price'] 
                                             for pos in self.positions.values())
        position_value = min(position_value, available_capital * 0.9)  # Use max 90% of available
        
        quantity = int(position_value / price)
        return max(1, quantity)
    
    def place_paper_order(self, ticker: str, quantity: int, price: float, 
                         slice_num: int, total_slices: int, signal: Dict):
        """Simulate order placement"""
        order_id = f"PAPER_{ticker}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{slice_num}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (ticker, action, quantity, price, slice_number, 
                              total_slices, vsr, momentum_score, order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, 'BUY', quantity, price, slice_num, total_slices,
              signal['vsr'], signal['score'], order_id, 'EXECUTED'))
        
        conn.commit()
        conn.close()
        
        # Update position
        if ticker in self.positions:
            pos = self.positions[ticker]
            new_qty = pos['quantity'] + quantity
            new_avg = ((pos['quantity'] * pos['avg_price']) + (quantity * price)) / new_qty
            pos['quantity'] = new_qty
            pos['avg_price'] = new_avg
        else:
            self.positions[ticker] = {
                'quantity': quantity,
                'avg_price': price,
                'entry_time': datetime.now(),
                'vsr': signal['vsr'],
                'score': signal['score']
            }
        
        logger.info(f"📈 PAPER BUY: {ticker} - Qty: {quantity} @ ₹{price:.2f} "
                   f"(Slice {slice_num}/{total_slices}) VSR: {signal['vsr']:.2f}")
        
        return order_id
    
    def schedule_slices(self, ticker: str, total_quantity: int, signal: Dict):
        """Schedule time-based order slices"""
        slices = []
        remaining_qty = total_quantity
        
        for minute_offset, percentage in sorted(self.slice_schedule.items(), 
                                               key=lambda x: int(x[0])):
            slice_qty = int(total_quantity * percentage)
            if int(minute_offset) == max(int(k) for k in self.slice_schedule.keys()):
                # Last slice gets remaining quantity
                slice_qty = remaining_qty
            else:
                remaining_qty -= slice_qty
                
            execution_time = datetime.now() + timedelta(minutes=int(minute_offset))
            slices.append({
                'time': execution_time,
                'quantity': slice_qty,
                'executed': False
            })
        
        self.pending_slices[ticker] = {
            'signal': signal,
            'slices': slices,
            'total_quantity': total_quantity
        }
        
        # Execute first slice immediately
        if slices and slices[0]['quantity'] > 0:
            self.place_paper_order(ticker, slices[0]['quantity'], signal['price'],
                                 1, len(slices), signal)
            slices[0]['executed'] = True
    
    def execute_pending_slices(self):
        """Check and execute pending order slices"""
        current_time = datetime.now()
        
        for ticker, slice_data in list(self.pending_slices.items()):
            signal = slice_data['signal']
            slices = slice_data['slices']
            
            for i, slice_info in enumerate(slices):
                if not slice_info['executed'] and current_time >= slice_info['time']:
                    # Get current price (in real system, fetch from market)
                    current_price = self.get_current_price(ticker, signal['price'])
                    
                    # Execute slice
                    self.place_paper_order(ticker, slice_info['quantity'], 
                                         current_price, i + 1, len(slices), signal)
                    slice_info['executed'] = True
            
            # Remove completed slice schedules
            if all(s['executed'] for s in slices):
                del self.pending_slices[ticker]
    
    def get_current_price(self, ticker: str, last_price: float) -> float:
        """Get current price - in paper trading, simulate small movements"""
        import random
        # Simulate price movement within ±1%
        movement = random.uniform(-0.01, 0.01)
        return last_price * (1 + movement)
    
    def update_positions(self):
        """Update current prices and P&L for all positions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for ticker, pos in self.positions.items():
            current_price = self.get_current_price(ticker, pos['avg_price'])
            pnl = (current_price - pos['avg_price']) * pos['quantity']
            pnl_pct = ((current_price - pos['avg_price']) / pos['avg_price']) * 100
            
            cursor.execute('''
                INSERT OR REPLACE INTO positions 
                (ticker, quantity, avg_price, current_price, pnl, vsr, 
                 momentum_score, entry_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticker, pos['quantity'], pos['avg_price'], current_price, pnl,
                  pos['vsr'], pos['score'], pos['entry_time'], 'OPEN'))
            
            logger.info(f"📊 {ticker}: ₹{current_price:.2f} | P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
        
        conn.commit()
        conn.close()
    
    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        now = datetime.now().time()
        start = datetime.strptime(self.config['trading_hours']['start'], '%H:%M').time()
        end = datetime.strptime(self.config['trading_hours']['end'], '%H:%M').time()
        return start <= now <= end
    
    def run(self):
        """Main loop for the paper trading system"""
        logger.info("🚀 VSR Paper Trading System Started")
        logger.info(f"Capital: ₹{self.capital:,.0f} | Risk/Trade: {self.risk_per_trade*100}%")
        logger.info(f"VSR Threshold: {self.config['vsr_threshold']} | "
                   f"Momentum Threshold: {self.config['momentum_threshold']}")
        
        self.running = True
        last_signal_check = datetime.now() - timedelta(minutes=1)
        
        while self.running:
            try:
                if not self.is_trading_hours():
                    time.sleep(60)
                    continue
                
                # Check for new signals every minute
                if datetime.now() - last_signal_check >= timedelta(minutes=1):
                    signals = self.get_vsr_signals()
                    
                    for signal in signals:
                        if len(self.positions) < self.max_positions:
                            ticker = signal['ticker']
                            total_quantity = self.calculate_position_size(signal['price'])
                            
                            if total_quantity > 0:
                                logger.info(f"🎯 New Signal: {ticker} | VSR: {signal['vsr']:.2f} | "
                                          f"Score: {signal['score']} | Price: ₹{signal['price']:.2f}")
                                self.schedule_slices(ticker, total_quantity, signal)
                    
                    last_signal_check = datetime.now()
                
                # Execute pending slices
                self.execute_pending_slices()
                
                # Update positions every 30 seconds
                if int(datetime.now().timestamp()) % 30 == 0:
                    self.update_positions()
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)
    
    def generate_report(self):
        """Generate performance report"""
        conn = sqlite3.connect(self.db_path)
        
        # Get today's trades
        trades_df = pd.read_sql_query(
            "SELECT * FROM trades WHERE date(timestamp) = date('now')", conn)
        
        # Get positions
        positions_df = pd.read_sql_query("SELECT * FROM positions", conn)
        
        conn.close()
        
        if not trades_df.empty:
            logger.info("\n📈 === PAPER TRADING REPORT ===")
            logger.info(f"Total Trades: {len(trades_df)}")
            logger.info(f"Active Positions: {len(positions_df[positions_df['status'] == 'OPEN'])}")
            
            if not positions_df.empty:
                total_pnl = positions_df['pnl'].sum()
                logger.info(f"Total P&L: ₹{total_pnl:,.2f}")
                logger.info(f"Win Rate: {(positions_df['pnl'] > 0).sum() / len(positions_df) * 100:.1f}%")

if __name__ == "__main__":
    trader = VSRPaperTrader()
    
    try:
        trader.run()
    except KeyboardInterrupt:
        trader.generate_report()