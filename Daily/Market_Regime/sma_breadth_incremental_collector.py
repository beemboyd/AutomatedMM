#!/usr/bin/env python3
"""
Simplified SMA Breadth Data Collector
Reduces API calls by:
1. Fetching index constituents data (single call)
2. Using sectoral indices as proxies
3. Incremental daily updates only
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from pathlib import Path
import configparser
from kiteconnect import KiteConnect

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimplifiedSMABreadthCollector:
    """Simplified collector that uses index data and samples to reduce API calls"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.dirname(self.script_dir)
        self.data_dir = os.path.join(self.script_dir, 'historical_breadth_data')
        
        # Create data directory
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Market indices that represent broad market
        self.market_indices = {
            'NIFTY 50': 256265,
            'NIFTY NEXT 50': 260105,
            'NIFTY 100': 260873,
            'NIFTY 200': 261129,
            'NIFTY 500': 261641,
            'NIFTY MIDCAP 150': 275465,
            'NIFTY SMALLCAP 250': 276249,
            'NIFTY BANK': 260105,
            'NIFTY IT': 261897,
            'NIFTY PHARMA': 261633,
            'NIFTY AUTO': 261889,
            'NIFTY FMCG': 261881,
            'NIFTY METAL': 261897,
            'NIFTY REALTY': 261641
        }
        
        # Representative stocks from each sector (30 stocks total)
        self.representative_stocks = [
            # Large caps (10)
            'RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'HINDUNILVR',
            'INFY', 'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK',
            # Mid caps (10)
            'BAJFINANCE', 'PIDILITIND', 'INDIGO', 'HAVELLS', 'TATACONSUM',
            'MUTHOOTFIN', 'VOLTAS', 'PAGEIND', 'DIXON', 'ASTRAL',
            # Small caps (10)
            'AAVAS', 'CREDITACC', 'HAPPSTMNDS', 'KPITTECH', 'LATENTVIEW',
            'POLYMED', 'ROUTE', 'SANOFI', 'STARHEALTH', 'ZOMATO'
        ]
        
        self._setup_user_context()
        
    def _setup_user_context(self):
        """Setup user context for API access"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                self.use_zerodha = False
                return
            
            config.read(config_path)
            
            user_section = 'API_CREDENTIALS_Sai'
            if user_section not in config:
                logger.warning(f"User section {user_section} not found in config")
                self.use_zerodha = False
                return
            
            api_key = config[user_section].get('api_key')
            access_token = config[user_section].get('access_token')
            
            if not all([api_key, access_token]):
                logger.warning(f"Incomplete credentials for {user_section}")
                self.use_zerodha = False
                return
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            try:
                profile = self.kite.profile()
                logger.info(f"Connected to Zerodha API for user: {profile.get('user_name', 'Unknown')}")
                self.use_zerodha = True
            except Exception as e:
                logger.warning(f"Failed to connect to Zerodha API: {e}")
                self.use_zerodha = False
                
        except Exception as e:
            logger.warning(f"Failed to setup Zerodha context: {e}")
            self.use_zerodha = False
    
    def fetch_index_historical_data(self, instrument_token, days=30):
        """Fetch historical data for an index"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=end_date,
                interval='day'
            )
            
            if not data:
                return None
                
            df = pd.DataFrame(data)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching index data: {e}")
            return None
    
    def calculate_breadth_from_indices(self, date=None):
        """Calculate approximate breadth using index movements and correlations"""
        try:
            if date is None:
                date = datetime.now().date()
            
            breadth_data = {
                'date': date.strftime('%Y-%m-%d'),
                'timestamp': datetime.now().isoformat(),
                'method': 'index_approximation'
            }
            
            # Fetch NIFTY 500 data (represents broad market)
            nifty500_data = self.fetch_index_historical_data(self.market_indices['NIFTY 500'], days=60)
            
            if nifty500_data is None or nifty500_data.empty:
                logger.error("Could not fetch NIFTY 500 data")
                return None
            
            # Calculate index SMA
            nifty500_data['SMA20'] = nifty500_data['close'].rolling(window=20).mean()
            nifty500_data['SMA50'] = nifty500_data['close'].rolling(window=50).mean()
            
            # Get latest values
            latest = nifty500_data.iloc[-1]
            
            # Index-based breadth approximation
            # If index is above SMA, assume 60-70% stocks are above
            # If index is below SMA, assume 30-40% stocks are above
            base_breadth_20 = 65 if latest['close'] > latest['SMA20'] else 35
            base_breadth_50 = 60 if latest['close'] > latest['SMA50'] else 40
            
            # Adjust based on index momentum
            momentum = (latest['close'] - nifty500_data.iloc[-5]['close']) / nifty500_data.iloc[-5]['close'] * 100
            
            # Momentum adjustment (±10% based on 5-day momentum)
            momentum_adj = min(max(momentum * 2, -10), 10)
            
            sma20_percent = base_breadth_20 + momentum_adj
            sma50_percent = base_breadth_50 + momentum_adj
            
            # Ensure within bounds
            sma20_percent = min(max(sma20_percent, 10), 90)
            sma50_percent = min(max(sma50_percent, 10), 90)
            
            # Determine regime
            if sma20_percent >= 70 and sma50_percent >= 65:
                regime = "Strong Uptrend"
            elif sma20_percent >= 55 and sma50_percent >= 50:
                regime = "Uptrend"
            elif sma20_percent <= 30 and sma50_percent <= 35:
                regime = "Strong Downtrend"
            elif sma20_percent <= 45 and sma50_percent <= 50:
                regime = "Downtrend"
            else:
                regime = "Choppy/Sideways"
            
            breadth_data['sma_breadth'] = {
                'above_sma20': int(sma20_percent * 5),  # Approximate count (out of 500)
                'below_sma20': int((100 - sma20_percent) * 5),
                'sma20_percent': round(sma20_percent, 2),
                'above_sma50': int(sma50_percent * 5),
                'below_sma50': int((100 - sma50_percent) * 5),
                'sma50_percent': round(sma50_percent, 2)
            }
            
            breadth_data['market_regime'] = regime
            breadth_data['market_score'] = round((sma20_percent * 0.6 + sma50_percent * 0.4) / 100, 3)
            breadth_data['index_momentum'] = round(momentum, 2)
            
            return breadth_data
            
        except Exception as e:
            logger.error(f"Error calculating breadth from indices: {e}")
            return None
    
    def update_daily_breadth(self):
        """Update breadth data for today only (1 API call)"""
        try:
            # Load existing data
            latest_file = os.path.join(self.data_dir, 'sma_breadth_historical_latest.json')
            
            if os.path.exists(latest_file):
                with open(latest_file, 'r') as f:
                    historical_data = json.load(f)
            else:
                historical_data = []
            
            # Get today's breadth
            today_breadth = self.calculate_breadth_from_indices()
            
            if today_breadth:
                # Check if today's data already exists
                today_str = datetime.now().strftime('%Y-%m-%d')
                existing_dates = [d['date'] for d in historical_data]
                
                if today_str in existing_dates:
                    # Update existing entry - preserve volume_breadth if it exists
                    for i, data in enumerate(historical_data):
                        if data['date'] == today_str:
                            # Preserve existing volume_breadth data if present
                            if 'volume_breadth' in historical_data[i]:
                                today_breadth['volume_breadth'] = historical_data[i]['volume_breadth']
                            historical_data[i] = today_breadth
                            break
                else:
                    # Add new entry
                    historical_data.append(today_breadth)
                
                # Sort by date
                historical_data = sorted(historical_data, key=lambda x: x['date'])
                
                # Keep only last 7 months
                cutoff_date = (datetime.now() - timedelta(days=210)).strftime('%Y-%m-%d')
                historical_data = [d for d in historical_data if d['date'] >= cutoff_date]
                
                # Save updated data
                with open(latest_file, 'w') as f:
                    json.dump(historical_data, f, indent=2)
                
                logger.info(f"✓ Updated breadth data for {today_str}")
                logger.info(f"  SMA20: {today_breadth['sma_breadth']['sma20_percent']}%")
                logger.info(f"  SMA50: {today_breadth['sma_breadth']['sma50_percent']}%")
                logger.info(f"  Regime: {today_breadth['market_regime']}")
                
                return today_breadth
            else:
                logger.error("Failed to calculate today's breadth")
                return None
                
        except Exception as e:
            logger.error(f"Error updating daily breadth: {e}")
            return None
    
    def backfill_using_samples(self, days=210):
        """Backfill historical data using sample stocks (30 API calls instead of 600+)"""
        try:
            logger.info(f"Backfilling {days} days using {len(self.representative_stocks)} sample stocks")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            all_data = []
            instruments = self.kite.instruments("NSE")
            
            # Fetch data for representative stocks
            for i, ticker in enumerate(self.representative_stocks):
                try:
                    # Get instrument token
                    instrument = next((inst for inst in instruments if inst['tradingsymbol'] == ticker), None)
                    if not instrument:
                        continue
                    
                    logger.info(f"Fetching {ticker} ({i+1}/{len(self.representative_stocks)})")
                    
                    # Fetch historical data
                    data = self.kite.historical_data(
                        instrument_token=instrument['instrument_token'],
                        from_date=start_date,
                        to_date=end_date,
                        interval='day'
                    )
                    
                    if data:
                        df = pd.DataFrame(data)
                        df['ticker'] = ticker
                        df['segment'] = 'large' if i < 10 else ('mid' if i < 20 else 'small')
                        all_data.append(df)
                    
                    # Small delay to avoid rate limits
                    import time
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                    continue
            
            if not all_data:
                logger.error("No data collected")
                return []
            
            # Combine all data
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Calculate SMAs for each stock
            breadth_data = []
            
            for ticker in self.representative_stocks:
                ticker_data = combined_df[combined_df['ticker'] == ticker].copy()
                if ticker_data.empty:
                    continue
                
                ticker_data = ticker_data.sort_values('date')
                ticker_data['SMA20'] = ticker_data['close'].rolling(window=20).mean()
                ticker_data['SMA50'] = ticker_data['close'].rolling(window=50).mean()
                ticker_data['above_sma20'] = (ticker_data['close'] > ticker_data['SMA20']).astype(int)
                ticker_data['above_sma50'] = (ticker_data['close'] > ticker_data['SMA50']).astype(int)
                
                combined_df.loc[combined_df['ticker'] == ticker, 'above_sma20'] = ticker_data['above_sma20']
                combined_df.loc[combined_df['ticker'] == ticker, 'above_sma50'] = ticker_data['above_sma50']
            
            # Aggregate by date
            daily_breadth = []
            
            for date, group in combined_df.groupby('date'):
                total_stocks = len(group)
                above_sma20 = group['above_sma20'].sum()
                above_sma50 = group['above_sma50'].sum()
                
                # Extrapolate to market (multiply by ~20 since we have 30 sample stocks for 600 total)
                multiplier = 20
                
                sma20_percent = (above_sma20 / total_stocks) * 100
                sma50_percent = (above_sma50 / total_stocks) * 100
                
                # Determine regime
                if sma20_percent >= 70 and sma50_percent >= 65:
                    regime = "Strong Uptrend"
                elif sma20_percent >= 55 and sma50_percent >= 50:
                    regime = "Uptrend"
                elif sma20_percent <= 30 and sma50_percent <= 35:
                    regime = "Strong Downtrend"
                elif sma20_percent <= 45 and sma50_percent <= 50:
                    regime = "Downtrend"
                else:
                    regime = "Choppy/Sideways"
                
                daily_breadth.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'timestamp': date.isoformat(),
                    'total_stocks': total_stocks * multiplier,
                    'sma_breadth': {
                        'above_sma20': int(above_sma20 * multiplier),
                        'below_sma20': int((total_stocks - above_sma20) * multiplier),
                        'sma20_percent': round(sma20_percent, 2),
                        'above_sma50': int(above_sma50 * multiplier),
                        'below_sma50': int((total_stocks - above_sma50) * multiplier),
                        'sma50_percent': round(sma50_percent, 2)
                    },
                    'market_regime': regime,
                    'market_score': round((sma20_percent * 0.6 + sma50_percent * 0.4) / 100, 3),
                    'method': 'sample_extrapolation'
                })
            
            # Save data
            if daily_breadth:
                latest_file = os.path.join(self.data_dir, 'sma_breadth_historical_latest.json')
                with open(latest_file, 'w') as f:
                    json.dump(sorted(daily_breadth, key=lambda x: x['date']), f, indent=2)
                
                logger.info(f"✓ Backfilled {len(daily_breadth)} days of breadth data")
                logger.info(f"  Used {len(self.representative_stocks)} sample stocks")
                logger.info(f"  Total API calls: ~{len(self.representative_stocks) + 1}")
            
            return daily_breadth
            
        except Exception as e:
            logger.error(f"Error in backfill: {e}")
            return []


def main():
    """Main function for daily updates or initial backfill"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simplified SMA Breadth Collector')
    parser.add_argument('--mode', choices=['daily', 'backfill', 'index'], default='daily',
                        help='Collection mode: daily update, backfill, or index-based approximation')
    parser.add_argument('--days', type=int, default=210,
                        help='Number of days to backfill (default: 210)')
    
    args = parser.parse_args()
    
    collector = SimplifiedSMABreadthCollector()
    
    if args.mode == 'daily':
        # Just update today's data (1 API call)
        logger.info("Running daily update...")
        collector.update_daily_breadth()
        
    elif args.mode == 'backfill':
        # Backfill using sample stocks (30 API calls)
        logger.info(f"Running backfill for {args.days} days...")
        collector.backfill_using_samples(days=args.days)
        
    elif args.mode == 'index':
        # Use index-based approximation (1 API call)
        logger.info("Calculating breadth using index approximation...")
        breadth = collector.calculate_breadth_from_indices()
        if breadth:
            print(json.dumps(breadth, indent=2))
    
    logger.info("✓ Complete!")


if __name__ == "__main__":
    main()