#!/usr/bin/env python
"""
VSR Anomaly Detection Service
Monitors all portfolio positions (CNC, MIS, T1) for VSR anomalies
Logs all anomalies to a detailed running log file
"""

import os
import sys
import time
import logging
import datetime
import json
import pandas as pd
import numpy as np
from pathlib import Path
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Tuple
import configparser

# Add parent directories to path
# Add Daily to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from kiteconnect import KiteConnect
from user_context_manager import get_context_manager, UserCredentials

# Import VSR calculation functions
from scanners.VSR_Momentum_Scanner import (
    calculate_vsr_indicators,
    fetch_data_kite,
    DataCache
)

class VSRAnomalyDetector:
    """VSR Anomaly Detection Service for Portfolio Positions"""
    
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.data_cache = DataCache()
        
        # Setup logging
        self.setup_logging()
        
        # Load config
        self.config = self.load_config()
        
        # Initialize Kite Connect
        self.setup_kite_connect()
        
        # Track anomaly history for better logging
        self.anomaly_history = {}  # ticker -> list of recent anomalies
        self.position_tracking = {}  # ticker -> position details over time
        
        # Anomaly thresholds
        self.anomaly_thresholds = {
            'exhaustion': {
                'vsr_min': 2.5,  # Minimum VSR to consider
                'price_lag_max': 1.0,  # Max price change % for exhaustion
                'volume_surge_min': 2.0  # Min volume surge multiplier
            },
            'divergence': {
                'vsr_decline_rate': 0.7,  # VSR dropped to 70% of previous
                'price_decline_min': -1.0  # Price dropped at least 1%
            },
            'climax': {
                'vsr_extreme': 4.0,  # Extreme VSR level
                'close_position_max': 0.3  # Closed in lower 30% of range
            }
        }
        
        self.logger.info(f"VSR Anomaly Detector initialized for {user_name}")
        self.logger.info(f"Anomalies will be logged to file for real-time monitoring")
    
    def setup_logging(self):
        """Set up logging for the service with detailed formatting"""
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'vsr_anomaly')
        os.makedirs(logs_dir, exist_ok=True)
        
        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f'vsr_anomaly_{today}.log')
        
        # Create a custom formatter for better readability
        class CustomFormatter(logging.Formatter):
            def format(self, record):
                # Add separator for anomaly messages
                if hasattr(record, 'anomaly') and record.anomaly:
                    return f"\n{'='*80}\n{super().format(record)}\n{'='*80}"
                return super().format(record)
        
        # Configure logging
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.handlers = []  # Clear existing handlers
        
        # File handler with custom formatter
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(CustomFormatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        # Console handler with simpler format
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)
        
        self.logger = logger
        self.logger.info(f"Logging to: {log_file}")
    
    def load_config(self):
        """Load configuration from config.ini"""
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.ini not found at {config_path}")
        
        config.read(config_path)
        return config
    
    def setup_kite_connect(self):
        """Initialize Kite Connect API"""
        try:
            # Get user credentials
            section = f'API_CREDENTIALS_{self.user_name}'
            if section not in self.config.sections():
                raise ValueError(f"No credentials found for user {self.user_name}")
            
            api_key = self.config.get(section, 'api_key')
            api_secret = self.config.get(section, 'api_secret')
            access_token = self.config.get(section, 'access_token')
            
            # Set up user context
            user_creds = UserCredentials(
                name=self.user_name,
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token
            )
            
            context_manager = get_context_manager()
            context_manager.set_current_user(user_creds.name, user_creds)
            
            # Initialize Kite Connect
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
            profile = self.kite.profile()
            self.logger.info(f"Connected to Zerodha as {profile['user_name']}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup Kite Connect: {e}")
            raise
    
    
    
    def get_all_positions(self) -> List[Dict]:
        """Fetch all positions (CNC, MIS, T1) from Zerodha"""
        try:
            all_positions = []
            
            # Get positions (includes MIS and CNC)
            positions = self.kite.positions()
            net_positions = positions.get('net', [])
            
            for pos in net_positions:
                quantity = pos.get('quantity', 0)
                if quantity > 0:  # Only long positions
                    all_positions.append({
                        'ticker': pos['tradingsymbol'],
                        'quantity': quantity,
                        'product': pos['product'],
                        'average_price': pos.get('average_price', 0),
                        'last_price': pos.get('last_price', 0),
                        'pnl': pos.get('pnl', 0),
                        'unrealised': pos.get('unrealised', 0)
                    })
            
            # Get holdings (CNC positions carried overnight)
            holdings = self.kite.holdings()
            
            for holding in holdings:
                quantity = holding.get('quantity', 0)
                t1_quantity = holding.get('t1_quantity', 0)
                total_quantity = quantity + t1_quantity
                
                if total_quantity > 0:
                    # Check if not already in positions
                    ticker = holding['tradingsymbol']
                    if not any(p['ticker'] == ticker for p in all_positions):
                        all_positions.append({
                            'ticker': ticker,
                            'quantity': total_quantity,
                            'product': 'CNC',
                            'average_price': holding.get('average_price', 0),
                            'last_price': holding.get('last_price', 0),
                            'pnl': holding.get('pnl', 0),
                            'unrealised': holding.get('day_change', 0) * total_quantity,
                            't1_quantity': t1_quantity
                        })
            
            self.logger.info(f"Found {len(all_positions)} total positions")
            return all_positions
            
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []
    
    def calculate_vsr_metrics(self, ticker: str) -> Optional[Dict]:
        """Calculate VSR metrics for a ticker using hourly data"""
        try:
            now = datetime.datetime.now()
            
            # Fetch hourly data for last 15 days
            from_date = (now - relativedelta(days=15)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            
            # Get hourly data
            hourly_data = fetch_data_kite(ticker, 'hour', from_date, to_date)
            
            if hourly_data.empty or len(hourly_data) < 50:
                return None
            
            # Calculate VSR indicators
            data_with_vsr = calculate_vsr_indicators(hourly_data)
            if data_with_vsr is None:
                return None
            
            # Get latest metrics
            latest = data_with_vsr.iloc[-1]
            previous = data_with_vsr.iloc[-2] if len(data_with_vsr) > 1 else latest
            
            # Calculate additional metrics for anomaly detection
            recent_data = data_with_vsr.tail(5)
            avg_vsr = recent_data['VSR_Ratio'].mean()
            max_vsr = recent_data['VSR_Ratio'].max()
            
            # Price movement analysis
            price_change_1h = ((latest['Close'] - previous['Close']) / previous['Close']) * 100
            price_change_5h = ((latest['Close'] - data_with_vsr.iloc[-5]['Close']) / data_with_vsr.iloc[-5]['Close']) * 100 if len(data_with_vsr) >= 5 else 0
            
            # Volume analysis
            avg_volume = data_with_vsr['Volume'].rolling(20).mean().iloc[-1]
            volume_ratio = latest['Volume'] / avg_volume if avg_volume > 0 else 1
            
            # Range analysis for climax detection
            range_size = latest['High'] - latest['Low']
            close_position = (latest['Close'] - latest['Low']) / range_size if range_size > 0 else 0.5
            
            return {
                'ticker': ticker,
                'vsr_ratio': latest['VSR_Ratio'],
                'vsr_previous': previous['VSR_Ratio'],
                'vsr_avg_5h': avg_vsr,
                'vsr_max_5h': max_vsr,
                'vsr_roc': latest.get('VSR_ROC', 0),
                'price_change_1h': price_change_1h,
                'price_change_5h': price_change_5h,
                'volume_ratio': volume_ratio,
                'close_position': close_position,
                'current_price': latest['Close'],
                'high': latest['High'],
                'low': latest['Low'],
                'volume': latest['Volume']
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating VSR metrics for {ticker}: {e}")
            return None
    
    def detect_anomalies(self, vsr_metrics: Dict) -> List[Dict]:
        """Detect various VSR anomalies"""
        anomalies = []
        ticker = vsr_metrics['ticker']
        
        # 1. Volume Exhaustion Detection
        if (vsr_metrics['vsr_ratio'] > self.anomaly_thresholds['exhaustion']['vsr_min'] and
            vsr_metrics['price_change_1h'] < self.anomaly_thresholds['exhaustion']['price_lag_max'] and
            vsr_metrics['volume_ratio'] > self.anomaly_thresholds['exhaustion']['volume_surge_min']):
            
            anomalies.append({
                'type': 'EXHAUSTION',
                'severity': 'HIGH',
                'message': f"{ticker}: Volume exhaustion detected! VSR: {vsr_metrics['vsr_ratio']:.2f}, "
                          f"Price change: {vsr_metrics['price_change_1h']:.2f}%, "
                          f"Volume surge: {vsr_metrics['volume_ratio']:.1f}x average"
            })
        
        # 2. VSR Divergence Detection
        vsr_decline_rate = vsr_metrics['vsr_ratio'] / vsr_metrics['vsr_previous'] if vsr_metrics['vsr_previous'] > 0 else 1
        
        if (vsr_metrics['vsr_previous'] > 2.0 and
            vsr_decline_rate < self.anomaly_thresholds['divergence']['vsr_decline_rate'] and
            vsr_metrics['price_change_1h'] < self.anomaly_thresholds['divergence']['price_decline_min']):
            
            anomalies.append({
                'type': 'DIVERGENCE',
                'severity': 'MEDIUM',
                'message': f"{ticker}: VSR-Price divergence! VSR dropped from {vsr_metrics['vsr_previous']:.2f} to "
                          f"{vsr_metrics['vsr_ratio']:.2f}, Price down {vsr_metrics['price_change_1h']:.2f}%"
            })
        
        # 3. Buying/Selling Climax Detection
        if (vsr_metrics['vsr_ratio'] > self.anomaly_thresholds['climax']['vsr_extreme'] and
            vsr_metrics['close_position'] < self.anomaly_thresholds['climax']['close_position_max']):
            
            anomalies.append({
                'type': 'CLIMAX',
                'severity': 'HIGH',
                'message': f"{ticker}: Potential selling climax! Extreme VSR: {vsr_metrics['vsr_ratio']:.2f}, "
                          f"Closed at {vsr_metrics['close_position']*100:.0f}% of range"
            })
        
        # 4. Momentum Loss Detection
        if (vsr_metrics['vsr_avg_5h'] > 2.5 and
            vsr_metrics['vsr_ratio'] < vsr_metrics['vsr_avg_5h'] * 0.5 and
            vsr_metrics['price_change_5h'] < 2.0):
            
            anomalies.append({
                'type': 'MOMENTUM_LOSS',
                'severity': 'MEDIUM',
                'message': f"{ticker}: Momentum loss! VSR dropped to {vsr_metrics['vsr_ratio']:.2f} from "
                          f"5h avg of {vsr_metrics['vsr_avg_5h']:.2f}, 5h price gain only {vsr_metrics['price_change_5h']:.2f}%"
            })
        
        return anomalies
    
    
    def format_position_info(self, position: Dict, vsr_metrics: Dict) -> str:
        """Format position information for logging"""
        pnl_indicator = "PROFIT" if position['pnl'] >= 0 else "LOSS"
        
        return (f"Position: {position['quantity']} shares @ ₹{position['average_price']:.2f} | "
                f"Current: ₹{vsr_metrics['current_price']:.2f} ({position['product']}) | "
                f"P&L: {pnl_indicator} ₹{abs(position['pnl']):.2f}")
    
    def log_anomaly_details(self, ticker: str, anomalies: List[Dict], position: Dict, vsr_metrics: Dict):
        """Log detailed anomaly information in a structured format"""
        # Create a detailed anomaly log entry
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'ticker': ticker,
            'anomalies': anomalies,
            'position': position,
            'vsr_metrics': vsr_metrics
        }
        
        # Store in history
        if ticker not in self.anomaly_history:
            self.anomaly_history[ticker] = []
        self.anomaly_history[ticker].append(log_entry)
        
        # Keep only last 100 entries per ticker
        if len(self.anomaly_history[ticker]) > 100:
            self.anomaly_history[ticker] = self.anomaly_history[ticker][-100:]
        
        # Log with special anomaly flag for formatting
        self.logger.info(f"\n{'='*80}\n🚨 ANOMALY DETECTED: {ticker}\n{'='*80}", extra={'anomaly': True})
        
        # Log each anomaly
        for anomaly in anomalies:
            severity_icon = "🔴" if anomaly['severity'] == 'HIGH' else "🟡"
            self.logger.warning(f"{severity_icon} [{anomaly['type']}] {anomaly['message']}")
        
        # Log VSR metrics
        self.logger.info(f"\n📊 VSR METRICS:")
        self.logger.info(f"  • Current VSR: {vsr_metrics['vsr_ratio']:.2f} (Previous: {vsr_metrics['vsr_previous']:.2f})")
        self.logger.info(f"  • 5H Average VSR: {vsr_metrics['vsr_avg_5h']:.2f} (Max: {vsr_metrics['vsr_max_5h']:.2f})")
        self.logger.info(f"  • Price Change: 1H: {vsr_metrics['price_change_1h']:+.2f}%, 5H: {vsr_metrics['price_change_5h']:+.2f}%")
        self.logger.info(f"  • Volume Ratio: {vsr_metrics['volume_ratio']:.2f}x average")
        self.logger.info(f"  • Close Position: {vsr_metrics['close_position']*100:.0f}% of range")
        
        # Log position details
        self.logger.info(f"\n💼 POSITION DETAILS:")
        self.logger.info(f"  • {self.format_position_info(position, vsr_metrics)}")
        self.logger.info(f"  • Entry Time: {position.get('entry_timestamp', 'Unknown')}")
        
        # Log recommendations based on anomaly type
        self.logger.info(f"\n💡 RECOMMENDATIONS:")
        for anomaly in anomalies:
            if anomaly['type'] == 'EXHAUSTION':
                self.logger.info("  ⚠️ Volume exhaustion detected - Consider reducing position size")
            elif anomaly['type'] == 'DIVERGENCE':
                self.logger.info("  ⚠️ VSR divergence - Monitor for further weakness")
            elif anomaly['type'] == 'CLIMAX':
                self.logger.info("  ⚠️ Potential climax - High reversal risk, consider exit")
            elif anomaly['type'] == 'MOMENTUM_LOSS':
                self.logger.info("  ⚠️ Momentum fading - Consider taking partial profits")
        
        self.logger.info(f"{'='*80}\n")
    
    def run_anomaly_check(self):
        """Run one cycle of anomaly detection"""
        try:
            cycle_start = datetime.datetime.now()
            self.logger.info(f"Starting anomaly detection cycle at {cycle_start.strftime('%H:%M:%S')}")
            
            # Get all positions
            positions = self.get_all_positions()
            if not positions:
                self.logger.info("No positions to monitor")
                return
            
            # Track positions for summary
            positions_summary = []
            
            # Check each position for anomalies
            total_anomalies = 0
            anomaly_details = []
            
            for position in positions:
                ticker = position['ticker']
                
                try:
                    # Calculate VSR metrics
                    vsr_metrics = self.calculate_vsr_metrics(ticker)
                    if not vsr_metrics:
                        continue
                    
                    # Track position status
                    position_status = {
                        'ticker': ticker,
                        'vsr': vsr_metrics['vsr_ratio'],
                        'price_change_1h': vsr_metrics['price_change_1h'],
                        'anomalies': []
                    }
                    
                    # Detect anomalies
                    anomalies = self.detect_anomalies(vsr_metrics)
                    
                    if anomalies:
                        total_anomalies += len(anomalies)
                        position_status['anomalies'] = [a['type'] for a in anomalies]
                        
                        # Log detailed anomaly information
                        self.log_anomaly_details(ticker, anomalies, position, vsr_metrics)
                        
                        # Store for summary
                        anomaly_details.append({
                            'ticker': ticker,
                            'anomalies': anomalies,
                            'severity': 'HIGH' if any(a['severity'] == 'HIGH' for a in anomalies) else 'MEDIUM'
                        })
                    
                    positions_summary.append(position_status)
                    
                    # Small delay between tickers
                    time.sleep(0.2)
                    
                except Exception as e:
                    self.logger.error(f"Error checking {ticker}: {e}")
                    continue
            
            # Log cycle summary
            cycle_duration = (datetime.datetime.now() - cycle_start).total_seconds()
            
            self.logger.info(f"\n📈 CYCLE SUMMARY:")
            self.logger.info(f"  • Positions checked: {len(positions)}")
            self.logger.info(f"  • Anomalies found: {total_anomalies}")
            self.logger.info(f"  • Duration: {cycle_duration:.1f}s")
            
            if positions_summary:
                # Log position status table
                self.logger.info(f"\n📊 POSITION STATUS:")
                self.logger.info(f"{'Ticker':12} | {'VSR':>6} | {'1H Chg%':>8} | Anomalies")
                self.logger.info(f"{'-'*12}-+-{'-'*6}-+-{'-'*8}-+-{'-'*30}")
                
                for pos in sorted(positions_summary, key=lambda x: x['vsr'], reverse=True):
                    anomaly_str = ', '.join(pos['anomalies']) if pos['anomalies'] else 'None'
                    self.logger.info(f"{pos['ticker']:12} | {pos['vsr']:6.2f} | {pos['price_change_1h']:+7.2f}% | {anomaly_str}")
            
            if anomaly_details:
                # Log high-priority anomalies summary
                high_priority = [a for a in anomaly_details if a['severity'] == 'HIGH']
                if high_priority:
                    self.logger.warning(f"\n⚠️ HIGH PRIORITY ANOMALIES: {len(high_priority)} positions need attention")
                    for item in high_priority:
                        self.logger.warning(f"  • {item['ticker']}: {', '.join([a['type'] for a in item['anomalies']])}")
            
        except Exception as e:
            self.logger.error(f"Error in anomaly check cycle: {e}")
    
    def run(self):
        """Main service loop"""
        self.logger.info("="*80)
        self.logger.info("VSR Anomaly Detection Service started")
        self.logger.info(f"Monitoring all positions for user: {self.user_name}")
        self.logger.info("Anomaly detection running every minute")
        self.logger.info("="*80)
        
        while True:
            try:
                start_time = time.time()
                
                # Run anomaly detection
                self.run_anomaly_check()
                
                # Calculate sleep time (run every minute)
                cycle_duration = time.time() - start_time
                sleep_time = max(60 - cycle_duration, 10)
                
                self.logger.info(f"\n⏱️ Next check in {sleep_time:.0f} seconds...\n")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                self.logger.info("\n" + "="*80)
                self.logger.info("Service stopped by user")
                self.logger.info("="*80)
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(60)

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VSR Anomaly Detection Service')
    parser.add_argument('-u', '--user', default='Sai', help='User name for credentials')
    
    args = parser.parse_args()
    
    # Create and run detector
    detector = VSRAnomalyDetector(user_name=args.user)
    detector.run()

if __name__ == "__main__":
    main()