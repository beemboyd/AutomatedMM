#!/usr/bin/env python3
"""
SMA Breadth Historical Data Collector
Fetches 7 months of historical data for SMA breadth analysis using Zerodha API
Stores data in structured format for dashboard display
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
import time
from kiteconnect import KiteConnect

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from user_context_manager import get_context_manager, UserCredentials, get_user_data_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SMABreadthHistoricalCollector:
    """Collects historical SMA breadth data for dashboard display"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.dirname(self.script_dir)  # Daily folder
        self.data_dir = os.path.join(self.script_dir, 'historical_breadth_data')
        self.ticker_file = os.path.join(self.daily_dir, 'data', 'Ticker.xlsx')
        
        # Create data directory
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Load user context for API access
        self._setup_user_context()
        
    def _setup_user_context(self):
        """Setup user context for API access using config.ini"""
        try:
            # Load config file
            config = configparser.ConfigParser()
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                self.use_zerodha = False
                return
            
            config.read(config_path)
            
            # Use Sai's credentials (first user with access token)
            user_section = 'API_CREDENTIALS_Sai'
            if user_section not in config:
                logger.warning(f"User section {user_section} not found in config")
                self.use_zerodha = False
                return
            
            api_key = config[user_section].get('api_key')
            api_secret = config[user_section].get('api_secret')
            access_token = config[user_section].get('access_token')
            
            if not all([api_key, api_secret, access_token]):
                logger.warning(f"Incomplete credentials for {user_section}")
                self.use_zerodha = False
                return
            
            # Setup direct KiteConnect instance
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
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
    
    def load_ticker_list(self):
        """Load ticker list from Excel file"""
        try:
            # First try to load FNO stocks for better market representation
            fno_file = os.path.join(self.daily_dir, 'data', 'Ticker.xlsx')
            if os.path.exists(fno_file):
                df = pd.read_excel(fno_file)
                tickers = df['Ticker'].dropna().unique().tolist()
                logger.info(f"Loaded {len(tickers)} FNO tickers for market breadth analysis")
                return tickers
            
            # Fallback to regular ticker file
            if os.path.exists(self.ticker_file):
                df = pd.read_excel(self.ticker_file)
                # Limit to first 250 most liquid stocks to avoid API limits
                tickers = df['Ticker'].dropna().unique().tolist()[:250]
                logger.info(f"Loaded {len(tickers)} tickers from {self.ticker_file}")
                return tickers
            else:
                # Fallback to test tickers
                logger.warning(f"Ticker files not found")
                return self._get_fallback_tickers()
                
        except Exception as e:
            logger.error(f"Error loading ticker list: {e}")
            return self._get_fallback_tickers()
    
    def _get_fallback_tickers(self):
        """Fallback ticker list for testing - smaller list to avoid rate limits"""
        return [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
            'ICICIBANK', 'KOTAKBANK', 'SBIN', 'BHARTIARTL', 'ITC'
        ]
    
    def fetch_historical_data_yfinance(self, ticker, start_date, end_date):
        """Fetch historical data using yfinance as fallback"""
        try:
            # Convert NSE ticker to Yahoo format
            yahoo_ticker = f"{ticker}.NS"
            
            stock = yf.Ticker(yahoo_ticker)
            data = stock.history(start=start_date, end=end_date, interval='1d')
            
            if data.empty:
                return None
                
            # Convert to required format
            data = data.reset_index()
            data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
            
            return {
                'ticker': ticker,
                'data': data[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
            }
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def fetch_historical_data_zerodha(self, ticker, start_date, end_date):
        """Fetch historical data using Zerodha API"""
        try:
            if not self.use_zerodha:
                return None
                
            # Get instrument token for ticker
            instruments = self.kite.instruments("NSE")
            instrument = next((inst for inst in instruments if inst['tradingsymbol'] == ticker), None)
            
            if not instrument:
                logger.warning(f"Instrument not found for {ticker}")
                return None
                
            # Fetch historical data
            data = self.kite.historical_data(
                instrument_token=instrument['instrument_token'],
                from_date=start_date,
                to_date=end_date,
                interval='day'
            )
            
            if not data:
                return None
                
            # Convert to required format
            formatted_data = []
            for candle in data:
                formatted_data.append({
                    'Date': candle['date'].strftime('%Y-%m-%d'),
                    'Open': candle['open'],
                    'High': candle['high'],
                    'Low': candle['low'],
                    'Close': candle['close'],
                    'Volume': candle['volume']
                })
            
            return {
                'ticker': ticker,
                'data': formatted_data
            }
            
        except Exception as e:
            logger.error(f"Error fetching Zerodha data for {ticker}: {e}")
            return None
    
    def calculate_sma_metrics(self, ticker_data):
        """Calculate SMA metrics and volume analysis for a ticker"""
        try:
            df = pd.DataFrame(ticker_data['data'])
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            
            # Calculate SMAs
            df['SMA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['SMA50'] = df['Close'].rolling(window=50, min_periods=1).mean()
            
            # Calculate Volume metrics
            df['Volume_SMA20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
            df['Volume_SMA50'] = df['Volume'].rolling(window=50, min_periods=1).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA20']
            
            # Calculate daily metrics
            results = []
            for _, row in df.iterrows():
                above_sma20 = 1 if row['Close'] > row['SMA20'] else 0
                above_sma50 = 1 if row['Close'] > row['SMA50'] else 0
                above_avg_volume = 1 if row['Volume'] > row['Volume_SMA20'] else 0
                
                results.append({
                    'date': row['Date'].strftime('%Y-%m-%d'),
                    'ticker': ticker_data['ticker'],
                    'close': row['Close'],
                    'volume': row['Volume'],
                    'sma20': row['SMA20'],
                    'sma50': row['SMA50'],
                    'volume_sma20': row['Volume_SMA20'],
                    'volume_sma50': row['Volume_SMA50'],
                    'volume_ratio': row['Volume_Ratio'],
                    'above_sma20': above_sma20,
                    'above_sma50': above_sma50,
                    'above_avg_volume': above_avg_volume
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error calculating SMA metrics for {ticker_data['ticker']}: {e}")
            return []
    
    def aggregate_daily_breadth(self, all_metrics):
        """Aggregate individual ticker metrics into daily breadth data with volume analysis"""
        try:
            # Convert to DataFrame for easier aggregation
            df = pd.DataFrame(all_metrics)
            df['date'] = pd.to_datetime(df['date'])
            
            # Group by date and calculate breadth metrics
            daily_breadth = []
            
            for date, group in df.groupby('date'):
                total_stocks = len(group)
                above_sma20 = group['above_sma20'].sum()
                above_sma50 = group['above_sma50'].sum()
                above_avg_volume = group['above_avg_volume'].sum()
                
                sma20_percent = (above_sma20 / total_stocks) * 100
                sma50_percent = (above_sma50 / total_stocks) * 100
                volume_breadth_percent = (above_avg_volume / total_stocks) * 100
                
                # Calculate average volume ratio
                avg_volume_ratio = group['volume_ratio'].mean()
                
                # Volume participation score
                volume_participation = volume_breadth_percent * avg_volume_ratio / 100
                
                # Calculate market regime based on breadth and volume
                if sma20_percent >= 70 and sma50_percent >= 70 and volume_participation > 1.0:
                    regime = "Strong Uptrend"
                elif sma20_percent >= 60 and sma50_percent >= 60:
                    regime = "Uptrend"
                elif sma20_percent <= 30 and sma50_percent <= 30:
                    regime = "Strong Downtrend"
                elif sma20_percent <= 40 and sma50_percent <= 40:
                    regime = "Downtrend"
                else:
                    regime = "Choppy/Sideways"
                
                # Calculate market score (0-1 scale) with volume component
                market_score = (sma20_percent * 0.5 + sma50_percent * 0.3 + volume_participation * 0.2) / 100
                
                daily_breadth.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'timestamp': date.isoformat(),
                    'total_stocks': int(total_stocks),
                    'sma_breadth': {
                        'above_sma20': int(above_sma20),
                        'below_sma20': int(total_stocks - above_sma20),
                        'sma20_percent': round(float(sma20_percent), 2),
                        'above_sma50': int(above_sma50),
                        'below_sma50': int(total_stocks - above_sma50),
                        'sma50_percent': round(float(sma50_percent), 2)
                    },
                    'volume_breadth': {
                        'above_avg_volume': int(above_avg_volume),
                        'below_avg_volume': int(total_stocks - above_avg_volume),
                        'volume_breadth_percent': round(float(volume_breadth_percent), 2),
                        'avg_volume_ratio': round(float(avg_volume_ratio), 2),
                        'volume_participation': round(float(volume_participation), 2)
                    },
                    'market_regime': regime,
                    'market_score': round(float(market_score), 3)
                })
            
            return sorted(daily_breadth, key=lambda x: x['date'])
            
        except Exception as e:
            logger.error(f"Error aggregating daily breadth: {e}")
            return []
    
    def collect_historical_data(self, months=7, batch_size=50, break_minutes=60):
        """Main method to collect historical SMA breadth data with volume analysis"""
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            
            logger.info(f"Collecting price and volume data from {start_date.date()} to {end_date.date()}")
            logger.info(f"Batch size: {batch_size} tickers with {break_minutes} minute breaks")
            
            # Load tickers
            tickers = self.load_ticker_list()
            logger.info(f"Processing {len(tickers)} tickers in batches of {batch_size}")
            
            # Estimate completion time
            total_batches = (len(tickers) + batch_size - 1) // batch_size
            estimated_hours = (total_batches - 1) * break_minutes / 60
            logger.info(f"Estimated completion time: {estimated_hours:.1f} hours")
            
            # Collect data for all tickers
            all_ticker_data = []
            
            # Process in batches
            total_batches = (len(tickers) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                batch_start = batch_num * batch_size
                batch_end = min((batch_num + 1) * batch_size, len(tickers))
                batch_tickers = tickers[batch_start:batch_end]
                
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing Batch {batch_num + 1}/{total_batches}")
                logger.info(f"Tickers {batch_start + 1} to {batch_end} of {len(tickers)}")
                logger.info(f"{'='*60}")
                
                # Process tickers in current batch
                for i, ticker in enumerate(batch_tickers):
                    try:
                        overall_index = batch_start + i + 1
                        logger.info(f"Processing {ticker} ({overall_index}/{len(tickers)})")
                        
                        # Try Zerodha first, fallback to yfinance
                        if self.use_zerodha:
                            ticker_data = self.fetch_historical_data_zerodha(ticker, start_date, end_date)
                        else:
                            ticker_data = self.fetch_historical_data_yfinance(ticker, start_date, end_date)
                        
                        if ticker_data:
                            all_ticker_data.append(ticker_data)
                            logger.info(f"✓ Collected data for {ticker}")
                        else:
                            logger.warning(f"✗ No data for {ticker}")
                            
                        # Rate limiting - 1 second between requests
                        time.sleep(1.0)
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        # Check for rate limit errors
                        if 'too many requests' in error_msg or 'rate limit' in error_msg or '429' in error_msg:
                            logger.warning(f"⚠️  Rate limit detected! Pausing for 60 minutes...")
                            logger.info(f"Resuming at: {(datetime.now() + timedelta(minutes=60)).strftime('%H:%M:%S')}")
                            
                            # Save current progress
                            if all_ticker_data:
                                emergency_file = os.path.join(self.data_dir, f'sma_breadth_emergency_save_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                                with open(emergency_file, 'w') as f:
                                    json.dump(all_ticker_data, f)
                                logger.info(f"💾 Saved emergency backup to {emergency_file}")
                            
                            time.sleep(60 * 60)  # 60 minute pause
                            # Retry the same ticker
                            i -= 1
                            continue
                        else:
                            logger.error(f"✗ Error collecting {ticker}: {e}")
                            time.sleep(1.0)
                
                # Progress summary for the batch
                batch_size_actual = batch_end - batch_start
                batch_success = len([1 for td in all_ticker_data[-batch_size_actual:] if td])
                logger.info(f"\n📊 Batch {batch_num + 1} Summary:")
                logger.info(f"   - Processed: {batch_size_actual} tickers")
                logger.info(f"   - Successful: {batch_success}")
                logger.info(f"   - Failed: {batch_size_actual - batch_success}")
                logger.info(f"   - Overall Progress: {batch_end}/{len(tickers)} ({(batch_end/len(tickers)*100):.1f}%)")
                
                # Time estimate
                batches_remaining = total_batches - batch_num - 1
                if batches_remaining > 0:
                    hours_remaining = batches_remaining * break_minutes / 60
                    logger.info(f"   - Estimated time remaining: {hours_remaining:.1f} hours")
                
                # Take a break between batches (except for the last batch)
                if batch_num < total_batches - 1:
                    logger.info(f"\n⏸️  Taking a {break_minutes} minute break before next batch...")
                    logger.info(f"Next batch starts at: {(datetime.now() + timedelta(minutes=break_minutes)).strftime('%H:%M:%S')}")
                    
                    # Save intermediate results in case of interruption
                    if all_ticker_data:
                        intermediate_file = os.path.join(self.data_dir, f'sma_breadth_partial_batch{batch_num+1}.json')
                        with open(intermediate_file, 'w') as f:
                            json.dump(all_ticker_data, f)
                        logger.info(f"💾 Saved intermediate results to {intermediate_file}")
                    
                    time.sleep(break_minutes * 60)
            
            # Final summary
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 COLLECTION COMPLETE!")
            logger.info(f"{'='*60}")
            logger.info(f"Total tickers processed: {len(tickers)}")
            logger.info(f"Successfully collected: {len(all_ticker_data)}")
            logger.info(f"Failed: {len(tickers) - len(all_ticker_data)}")
            logger.info(f"Success rate: {(len(all_ticker_data)/len(tickers)*100):.1f}%")
            logger.info(f"{'='*60}\n")
            
            # Clean up intermediate files
            for batch_file in os.listdir(self.data_dir):
                if batch_file.startswith('sma_breadth_partial_batch') or batch_file.startswith('sma_breadth_emergency_save'):
                    try:
                        os.remove(os.path.join(self.data_dir, batch_file))
                        logger.info(f"🗑️  Cleaned up intermediate file: {batch_file}")
                    except:
                        pass
            
            # Calculate SMA metrics for all tickers
            all_metrics = []
            for ticker_data in all_ticker_data:
                metrics = self.calculate_sma_metrics(ticker_data)
                all_metrics.extend(metrics)
            
            logger.info(f"Calculated SMA metrics for {len(all_metrics)} data points")
            
            # Aggregate into daily breadth data
            daily_breadth = self.aggregate_daily_breadth(all_metrics)
            
            logger.info(f"Generated {len(daily_breadth)} days of breadth data")
            
            # Save results
            self._save_historical_data(daily_breadth)
            
            return daily_breadth
            
        except Exception as e:
            logger.error(f"Error in collect_historical_data: {e}")
            return []
    
    def _save_historical_data(self, daily_breadth):
        """Save historical breadth data to files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save as JSON
            json_file = os.path.join(self.data_dir, f'sma_breadth_historical_{timestamp}.json')
            with open(json_file, 'w') as f:
                json.dump(daily_breadth, f, indent=2)
            
            # Save as CSV for analysis
            csv_file = os.path.join(self.data_dir, f'sma_breadth_historical_{timestamp}.csv')
            
            # Flatten data for CSV
            csv_data = []
            for day in daily_breadth:
                row = {
                    'date': day['date'],
                    'total_stocks': day['total_stocks'],
                    'above_sma20': day['sma_breadth']['above_sma20'],
                    'sma20_percent': day['sma_breadth']['sma20_percent'],
                    'above_sma50': day['sma_breadth']['above_sma50'],
                    'sma50_percent': day['sma_breadth']['sma50_percent'],
                    'above_avg_volume': day['volume_breadth']['above_avg_volume'],
                    'volume_breadth_percent': day['volume_breadth']['volume_breadth_percent'],
                    'avg_volume_ratio': day['volume_breadth']['avg_volume_ratio'],
                    'volume_participation': day['volume_breadth']['volume_participation'],
                    'market_regime': day['market_regime'],
                    'market_score': day['market_score']
                }
                csv_data.append(row)
            
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_file, index=False)
            
            # Save latest data for dashboard
            latest_file = os.path.join(self.data_dir, 'sma_breadth_historical_latest.json')
            with open(latest_file, 'w') as f:
                json.dump(daily_breadth, f, indent=2)
            
            logger.info(f"Historical data saved to:")
            logger.info(f"  JSON: {json_file}")
            logger.info(f"  CSV: {csv_file}")
            logger.info(f"  Latest: {latest_file}")
            
        except Exception as e:
            logger.error(f"Error saving historical data: {e}")

def main(months=7, test_mode=False, batch_size=50, break_minutes=60):
    """Main execution function with batch processing for price and volume data"""
    logger.info("Starting SMA Breadth + Volume Historical Data Collection")
    logger.info(f"Batch size: {batch_size} tickers, Break time: {break_minutes} minutes")
    
    collector = SMABreadthHistoricalCollector()
    
    # For test mode, use only 1 month and smaller batch
    if test_mode:
        months = 1
        batch_size = 5
        break_minutes = 5
        logger.info("TEST MODE: Collecting only 1 month of data with 5 ticker batches")
    
    # Collect historical data
    daily_breadth = collector.collect_historical_data(
        months=months, 
        batch_size=batch_size,
        break_minutes=break_minutes
    )
    
    if daily_breadth:
        logger.info(f"✓ Successfully collected {len(daily_breadth)} days of breadth data")
        logger.info(f"Date range: {daily_breadth[0]['date']} to {daily_breadth[-1]['date']}")
        
        # Print summary statistics
        sma20_values = [day['sma_breadth']['sma20_percent'] for day in daily_breadth]
        sma50_values = [day['sma_breadth']['sma50_percent'] for day in daily_breadth]
        
        logger.info(f"SMA20 Breadth - Min: {min(sma20_values):.1f}%, Max: {max(sma20_values):.1f}%, Avg: {np.mean(sma20_values):.1f}%")
        logger.info(f"SMA50 Breadth - Min: {min(sma50_values):.1f}%, Max: {max(sma50_values):.1f}%, Avg: {np.mean(sma50_values):.1f}%")
        
        # Volume statistics
        volume_values = [day['volume_breadth']['volume_breadth_percent'] for day in daily_breadth]
        participation_values = [day['volume_breadth']['volume_participation'] for day in daily_breadth]
        
        logger.info(f"Volume Breadth - Min: {min(volume_values):.1f}%, Max: {max(volume_values):.1f}%, Avg: {np.mean(volume_values):.1f}%")
        logger.info(f"Volume Participation - Min: {min(participation_values):.2f}, Max: {max(participation_values):.2f}, Avg: {np.mean(participation_values):.2f}")
        
    else:
        logger.error("✗ Failed to collect historical data")

if __name__ == "__main__":
    import sys
    # Check for test mode flag
    test_mode = "--test" in sys.argv
    main(test_mode=test_mode)