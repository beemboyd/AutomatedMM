#!/usr/bin/env python3
"""
Market Breadth Scanner
Calculates comprehensive market internals including SMA20/50, RSI, Volume, and Momentum
Runs every 30 minutes during market hours to feed the enhanced dashboard
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
import configparser
import argparse
import time
from kiteconnect import KiteConnect

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "market_breadth_scanner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Market Breadth Scanner with Sector Information")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        logger.error(f"config.ini file not found at {config_path}")
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        logger.error(f"No credentials found for user {user_name} in {config_path}")
        raise ValueError(f"No credentials found for user {user_name}")
    
    return config

class MarketBreadthScanner:
    def __init__(self, user_name="Sai"):
        self.user_name = user_name
        self.config = load_daily_config(user_name)
        self.credential_section = f'API_CREDENTIALS_{user_name}'
        
        # Initialize Kite Connect
        self.kite = KiteConnect(api_key=self.config.get(self.credential_section, 'api_key'))
        self.kite.set_access_token(self.config.get(self.credential_section, 'access_token'))
        
        # Set up paths
        self.ticker_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'Ticker.xlsx')
        self.sector_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'Ticker_with_Sector.xlsx')
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Market_Regime', 'breadth_data')
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Load sector data once
        self.sector_data = self.load_sector_data()
        
        # Cache for instruments
        self.instruments_cache = None
        self.instrument_tokens = {}
        
    def load_sector_data(self):
        """Load sector data from Ticker_with_Sector.xlsx"""
        try:
            if os.path.exists(self.sector_file):
                df = pd.read_excel(self.sector_file)
                logger.info(f"Loaded sector data from {self.sector_file}")
                return df
            else:
                logger.warning(f"Sector file not found: {self.sector_file}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading sector data: {e}")
            return pd.DataFrame()
    
    def get_sector_for_ticker(self, ticker):
        """Get sector information for a specific ticker"""
        if self.sector_data.empty:
            return "Unknown"
        
        # Look up ticker in sector data
        ticker_upper = ticker.upper()
        sector_match = self.sector_data[self.sector_data['Ticker'].str.upper() == ticker_upper]
        
        if not sector_match.empty:
            sector = sector_match.iloc[0]['Sector']
            # Check if sector is NaN or empty
            if pd.isna(sector) or sector == '' or sector is None:
                return "Unknown"
            return str(sector)
        else:
            return "Unknown"
        
    def load_tickers(self):
        """Load tickers from the Excel file"""
        try:
            df = pd.read_excel(self.ticker_file, sheet_name="Ticker")
            tickers = df['Ticker'].dropna().tolist()
            logger.info(f"Read {len(tickers)} tickers from {self.ticker_file}")
            return tickers
        except Exception as e:
            logger.error(f"Error loading tickers: {e}")
            return []
    
    def calculate_sma(self, data, period):
        """Calculate Simple Moving Average"""
        return data['close'].rolling(window=period).mean()
    
    def calculate_rsi(self, data, period=14):
        """Calculate Relative Strength Index"""
        close_prices = data['close']
        deltas = close_prices.diff()
        gain = deltas.where(deltas > 0, 0)
        loss = -deltas.where(deltas < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_volume_ratio(self, data, period=20):
        """Calculate current volume vs average volume ratio"""
        avg_volume = data['volume'].rolling(window=period).mean()
        current_volume = data['volume'].iloc[-1]
        return current_volume / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 1
    
    def calculate_momentum(self, data, period):
        """Calculate price momentum"""
        return (data['close'].iloc[-1] / data['close'].iloc[-period-1] - 1) * 100
    
    def get_instrument_token(self, ticker):
        """Get instrument token for a ticker with caching"""
        # Check cache first
        if ticker in self.instrument_tokens:
            return self.instrument_tokens[ticker]
        
        try:
            # Load instruments if not cached
            if self.instruments_cache is None:
                logger.info("Loading instruments data from Kite...")
                self.instruments_cache = self.kite.instruments()
            
            # Search for the ticker
            ticker_upper = ticker.upper()
            for inst in self.instruments_cache:
                if inst['tradingsymbol'] == ticker_upper and inst['exchange'] == 'NSE':
                    token = inst['instrument_token']
                    self.instrument_tokens[ticker] = token
                    return token
            
            logger.warning(f"Instrument token for {ticker} not found.")
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token for {ticker}: {e}")
            return None
    
    def scan_ticker(self, ticker):
        """Scan individual ticker for all market breadth indicators"""
        try:
            # Get sector information
            sector = self.get_sector_for_ticker(ticker)
            
            # Fetch historical data (60 days for SMA50 calculation)
            to_date = datetime.now()
            from_date = to_date - timedelta(days=90)
            
            # Get instrument token
            token = self.get_instrument_token(ticker)
            if token is None:
                return None
                
            # Fetch historical data
            historical_data = self.kite.historical_data(
                token,
                from_date,
                to_date,
                interval="day"
            )
            
            if not historical_data:
                logger.warning(f"No historical data for {ticker}")
                return None
                
            df = pd.DataFrame(historical_data)
            
            # Calculate indicators
            current_price = df['close'].iloc[-1]
            sma20 = self.calculate_sma(df, 20).iloc[-1]
            sma50 = self.calculate_sma(df, 50).iloc[-1]
            rsi = self.calculate_rsi(df).iloc[-1]
            volume_ratio = self.calculate_volume_ratio(df)
            momentum_5d = self.calculate_momentum(df, 5)
            momentum_10d = self.calculate_momentum(df, 10)
            
            # Calculate positions relative to SMAs
            above_sma20 = current_price > sma20
            above_sma50 = current_price > sma50
            sma20_distance = ((current_price - sma20) / sma20) * 100
            sma50_distance = ((current_price - sma50) / sma50) * 100
            
            return {
                'ticker': ticker,
                'sector': sector,
                'current_price': current_price,
                'sma20': sma20,
                'sma50': sma50,
                'above_sma20': above_sma20,
                'above_sma50': above_sma50,
                'sma20_distance': sma20_distance,
                'sma50_distance': sma50_distance,
                'rsi': rsi,
                'volume_ratio': volume_ratio,
                'momentum_5d': momentum_5d,
                'momentum_10d': momentum_10d,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            # If rate limited, wait a bit
            if "Too many requests" in str(e):
                import time
                logger.info("Rate limit hit, waiting 2 seconds...")
                time.sleep(2)
            return None
    
    def calculate_market_breadth(self, scan_results):
        """Calculate overall market breadth indicators"""
        df = pd.DataFrame(scan_results)
        
        total_stocks = len(df)
        
        # SMA breadth
        above_sma20 = df['above_sma20'].sum()
        above_sma50 = df['above_sma50'].sum()
        sma20_breadth = (above_sma20 / total_stocks) * 100
        sma50_breadth = (above_sma50 / total_stocks) * 100
        
        # RSI distribution
        rsi_overbought = (df['rsi'] > 70).sum()
        rsi_oversold = (df['rsi'] < 30).sum()
        rsi_neutral = total_stocks - rsi_overbought - rsi_oversold
        
        # Volume participation
        high_volume = (df['volume_ratio'] > 1.5).sum()
        normal_volume = ((df['volume_ratio'] >= 0.5) & (df['volume_ratio'] <= 1.5)).sum()
        low_volume = (df['volume_ratio'] < 0.5).sum()
        
        # Momentum distribution
        positive_momentum_5d = (df['momentum_5d'] > 0).sum()
        positive_momentum_10d = (df['momentum_10d'] > 0).sum()
        
        # Sector performance
        sector_performance = df.groupby('sector').agg({
            'above_sma20': 'mean',
            'above_sma50': 'mean',
            'rsi': 'mean',
            'momentum_5d': 'mean',
            'momentum_10d': 'mean'
        }).to_dict('index')
        
        # Market score calculation (enhanced)
        # Weighted combination of multiple factors
        sma_score = (sma20_breadth * 0.3 + sma50_breadth * 0.2) / 50
        momentum_score = (positive_momentum_5d / total_stocks) * 0.25 + (positive_momentum_10d / total_stocks) * 0.25
        
        # RSI score (penalize extremes)
        rsi_score = (rsi_neutral / total_stocks) * 0.5
        if rsi_overbought > rsi_oversold:
            rsi_score -= (rsi_overbought - rsi_oversold) / total_stocks * 0.25
        else:
            rsi_score -= (rsi_oversold - rsi_overbought) / total_stocks * 0.25
            
        market_score = sma_score + momentum_score + rsi_score
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': total_stocks,
            'sma_breadth': {
                'above_sma20': above_sma20,
                'below_sma20': total_stocks - above_sma20,
                'above_sma50': above_sma50,
                'below_sma50': total_stocks - above_sma50,
                'sma20_percent': sma20_breadth,
                'sma50_percent': sma50_breadth
            },
            'rsi_distribution': {
                'overbought': rsi_overbought,
                'neutral': rsi_neutral,
                'oversold': rsi_oversold,
                'avg_rsi': df['rsi'].mean()
            },
            'volume_analysis': {
                'high_volume': high_volume,
                'normal_volume': normal_volume,
                'low_volume': low_volume,
                'avg_volume_ratio': df['volume_ratio'].mean()
            },
            'momentum_indicators': {
                'positive_5d': positive_momentum_5d,
                'negative_5d': total_stocks - positive_momentum_5d,
                'positive_10d': positive_momentum_10d,
                'negative_10d': total_stocks - positive_momentum_10d,
                'avg_momentum_5d': df['momentum_5d'].mean(),
                'avg_momentum_10d': df['momentum_10d'].mean()
            },
            'market_score': market_score,
            'market_regime': self.determine_regime(market_score, sma20_breadth, momentum_score),
            'sector_performance': sector_performance
        }
    
    def determine_regime(self, market_score, sma20_breadth, momentum_score):
        """Determine market regime based on breadth indicators"""
        if market_score > 0.7 and sma20_breadth > 70:
            return "Strong Uptrend"
        elif market_score > 0.5 and sma20_breadth > 50:
            return "Uptrend"
        elif market_score < 0.3 and sma20_breadth < 30:
            return "Downtrend"
        elif market_score < 0.2 and sma20_breadth < 20:
            return "Strong Downtrend"
        else:
            return "Choppy/Sideways"
    
    def save_results(self, scan_results, breadth_summary):
        """Save scan results and breadth summary"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed scan results
        scan_df = pd.DataFrame(scan_results)
        scan_file = os.path.join(self.output_dir, f"market_breadth_scan_{timestamp}.xlsx")
        scan_df.to_excel(scan_file, index=False)
        logger.info(f"Saved scan results to {scan_file}")
        
        # Convert numpy types to Python types for JSON serialization
        def convert_to_serializable(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                val = float(obj)
                # Handle NaN and Infinity
                if np.isnan(val):
                    return None
                elif np.isinf(val):
                    return None
                return val
            elif isinstance(obj, float):
                # Handle regular Python float NaN/Infinity
                if np.isnan(obj):
                    return None
                elif np.isinf(obj):
                    return None
                return obj
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(i) for i in obj]
            return obj
        
        breadth_summary_serializable = convert_to_serializable(breadth_summary)
        
        # Save breadth summary as JSON
        summary_file = os.path.join(self.output_dir, "market_breadth_latest.json")
        with open(summary_file, 'w') as f:
            json.dump(breadth_summary_serializable, f, indent=2)
        logger.info(f"Saved breadth summary to {summary_file}")
        
        # Also save timestamped summary
        summary_timestamp_file = os.path.join(self.output_dir, f"market_breadth_{timestamp}.json")
        with open(summary_timestamp_file, 'w') as f:
            json.dump(breadth_summary_serializable, f, indent=2)
            
        return scan_file, summary_file
    
    def run(self):
        """Main scanning function"""
        logger.info("Starting Market Breadth Scanner")
        
        # Load tickers
        tickers = self.load_tickers()
        if not tickers:
            logger.error("No tickers loaded")
            return
            
        logger.info(f"Loaded {len(tickers)} tickers")
        
        # Scan each ticker
        scan_results = []
        for idx, ticker in enumerate(tickers):
            result = self.scan_ticker(ticker)
            if result:
                scan_results.append(result)
                
            # Progress update
            if (idx + 1) % 10 == 0:
                logger.info(f"Scanned {idx + 1}/{len(tickers)} tickers")
                
            # Small delay to avoid rate limiting (3 requests per second limit)
            time.sleep(0.35)  # ~2.8 requests per second
        
        logger.info(f"Successfully scanned {len(scan_results)} tickers")
        
        # Calculate market breadth
        if scan_results:
            breadth_summary = self.calculate_market_breadth(scan_results)
            
            # Add individual stock results to summary
            breadth_summary['stocks'] = scan_results
            
            # Save results
            scan_file, summary_file = self.save_results(scan_results, breadth_summary)
            
            # Update sector rotation tracking
            try:
                from Market_Regime.sector_rotation_analyzer import SectorRotationAnalyzer
                rotation_analyzer = SectorRotationAnalyzer()
                
                # Store daily performance
                if 'sector_performance' in breadth_summary:
                    date = breadth_summary['timestamp'].split('T')[0]
                    rotation_analyzer.store_daily_performance(date, breadth_summary['sector_performance'])
                    logger.info("Updated sector rotation database")
                
                rotation_analyzer.close()
            except Exception as e:
                logger.warning(f"Failed to update sector rotation data: {str(e)}")
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("MARKET BREADTH SUMMARY")
            logger.info("="*50)
            logger.info(f"Market Score: {breadth_summary['market_score']:.3f}")
            logger.info(f"Market Regime: {breadth_summary['market_regime']}")
            logger.info(f"Above SMA20: {breadth_summary['sma_breadth']['above_sma20']} ({breadth_summary['sma_breadth']['sma20_percent']:.1f}%)")
            logger.info(f"Above SMA50: {breadth_summary['sma_breadth']['above_sma50']} ({breadth_summary['sma_breadth']['sma50_percent']:.1f}%)")
            logger.info(f"RSI Distribution - OB: {breadth_summary['rsi_distribution']['overbought']}, N: {breadth_summary['rsi_distribution']['neutral']}, OS: {breadth_summary['rsi_distribution']['oversold']}")
            logger.info(f"Positive Momentum (5D): {breadth_summary['momentum_indicators']['positive_5d']} stocks")
            logger.info("="*50)
            
        else:
            logger.error("No scan results obtained")

if __name__ == "__main__":
    # Get user from arguments
    args = parse_args()
    user_name = args.user
    logger.info(f"Using credentials for user: {user_name}")
    
    # Initialize and run scanner
    scanner = MarketBreadthScanner(user_name)
    scanner.run()