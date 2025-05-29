#!/usr/bin/env python
"""
Zerodha API Handler
Provides a common interface for interacting with Zerodha's Kite Connect API
"""
import os
import logging
import datetime
import time
from typing import Dict, List, Optional, Any

from kiteconnect import KiteConnect

from config import get_config

logger = logging.getLogger(__name__)

class ZerodhaHandler:
    """Handler for Zerodha operations, providing a simplified interface"""
    
    def __init__(self):
        self.config = get_config()
        self.api_key = self.config.get('API', 'api_key')
        self.api_secret = self.config.get('API', 'api_secret', fallback=None)
        self.access_token = self.config.get('API', 'access_token')
        self.exchange = self.config.get('Trading', 'exchange')
        
        # Initialize Kite Connect client
        self.kite = self._initialize_kite()
        
        # Cache for data
        self.instruments_df = None
        self.ltp_cache = {}
        self.ltp_timestamp = {}
        self.holdings_cache = None
        self.holdings_cache_time = 0
        self.positions_cache = None
        self.positions_cache_time = 0
        
        # Cache TTL (time-to-live) in seconds
        self.cache_ttl = 300  # 5 minutes
        self.ltp_cache_ttl = 60  # 1 minute
    
    def _initialize_kite(self):
        """Initialize KiteConnect client with error handling"""
        try:
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(self.access_token)
            logger.info("KiteConnect initialized successfully")
            return kite
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect: {e}")
            raise
    
    def get_holdings(self, force_refresh=False) -> List[Dict[str, Any]]:
        """
        Get current holdings (CNC positions)
        
        Args:
            force_refresh: Force refresh from API instead of using cache
            
        Returns:
            List of holdings (each as a dict)
        """
        current_time = time.time()
        
        # Use cache if available and not expired
        if (not force_refresh and 
            self.holdings_cache is not None and 
            current_time - self.holdings_cache_time < self.cache_ttl):
            logger.debug("Using cached holdings data")
            return self.holdings_cache
        
        try:
            logger.info("Fetching holdings from Zerodha")
            holdings = self.kite.holdings()
            
            # Format and clean holdings data
            for holding in holdings:
                # Convert numeric strings to appropriate types
                for key in ['quantity', 'used_quantity', 'authorised_quantity', 't1_quantity']:
                    if key in holding:
                        holding[key] = int(holding.get(key, 0))
                
                for key in ['average_price', 'last_price', 'pnl', 'day_change', 'day_change_percentage']:
                    if key in holding:
                        holding[key] = float(holding.get(key, 0.0))
            
            # Update cache
            self.holdings_cache = holdings
            self.holdings_cache_time = current_time
            
            logger.info(f"Retrieved {len(holdings)} holdings from Zerodha")
            return holdings
            
        except Exception as e:
            logger.error(f"Error getting holdings: {e}")
            # Return cache if available (even if expired) in case of error
            if self.holdings_cache is not None:
                logger.warning("Using expired cached holdings data due to API error")
                return self.holdings_cache
            return []
    
    def get_positions(self, force_refresh=False) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get current positions (both day/MIS and CNC)
        
        Args:
            force_refresh: Force refresh from API instead of using cache
            
        Returns:
            Dict with keys 'day', 'net' containing lists of position data
        """
        current_time = time.time()
        
        # Use cache if available and not expired
        if (not force_refresh and 
            self.positions_cache is not None and 
            current_time - self.positions_cache_time < self.cache_ttl):
            logger.debug("Using cached positions data")
            return self.positions_cache
        
        try:
            logger.info("Fetching positions from Zerodha")
            positions = self.kite.positions()
            
            # Update cache
            self.positions_cache = positions
            self.positions_cache_time = current_time
            
            logger.info(f"Retrieved {len(positions.get('net', []))} net positions from Zerodha")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            # Return cache if available (even if expired) in case of error
            if self.positions_cache is not None:
                logger.warning("Using expired cached positions data due to API error")
                return self.positions_cache
            return {'day': [], 'net': []}
    
    def get_ltp(self, tickers):
        """
        Get Last Traded Price for one or more tickers
        
        Args:
            tickers: Single ticker or list of tickers
            
        Returns:
            Dict mapping exchange:ticker -> price data
        """
        if isinstance(tickers, str):
            tickers = [tickers]
            
        # Prepare full exchange:ticker format
        instruments = [f"{self.exchange}:{ticker}" for ticker in tickers]
        
        try:
            ltp_data = self.kite.ltp(instruments)
            return ltp_data
        except Exception as e:
            logger.error(f"Error getting LTP data: {e}")
            return {}
    
    def get_historical_data(self, ticker, interval, from_date, to_date, continuous=False):
        """
        Get historical data for a ticker
        
        Args:
            ticker: Trading symbol
            interval: Candle interval (minute, day, etc)
            from_date: Start date (YYYY-MM-DD or datetime)
            to_date: End date (YYYY-MM-DD or datetime)
            continuous: Get continuous data for futures and options
            
        Returns:
            List of dicts with OHLCV data
        """
        try:
            instrument_token = self._get_instrument_token(ticker)
            if not instrument_token:
                logger.error(f"Could not find instrument token for {ticker}")
                return []
            
            # Convert datetime objects to strings if needed
            if isinstance(from_date, datetime.datetime):
                from_date = from_date.strftime('%Y-%m-%d')
            if isinstance(to_date, datetime.datetime):
                to_date = to_date.strftime('%Y-%m-%d')
                
            historical_data = self.kite.historical_data(
                instrument_token, from_date, to_date, interval, continuous=continuous
            )
            
            return historical_data
        except Exception as e:
            logger.error(f"Error getting historical data for {ticker}: {e}")
            return []
    
    def _get_instrument_token(self, ticker):
        """Get instrument token for a given ticker"""
        try:
            instruments = self.kite.instruments(self.exchange)
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token for {ticker}: {e}")
            return None

# Singleton instance
_zerodha_handler = None

def get_zerodha_handler():
    """Get or create the singleton zerodha handler instance"""
    global _zerodha_handler
    if _zerodha_handler is None:
        _zerodha_handler = ZerodhaHandler()
    return _zerodha_handler