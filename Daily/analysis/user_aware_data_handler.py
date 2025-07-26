import os
import pandas as pd
import logging
import datetime
from kiteconnect import KiteConnect

logger = logging.getLogger(__name__)

class UserAwareDataHandler:
    """Data handler that uses user-specific credentials"""
    
    def __init__(self, api_key, access_token):
        """Initialize with specific API credentials"""
        self.api_key = api_key
        self.access_token = access_token
        
        # Initialize Kite Connect
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Cache for instruments
        self.instruments_df = None
        self.instrument_tokens = {}
        
    def get_instruments_data(self):
        """Fetch instruments data with caching"""
        if self.instruments_df is None:
            try:
                logger.info("Fetching instruments data from exchange")
                instruments = self.kite.instruments("NSE")
                self.instruments_df = pd.DataFrame(instruments)
                logger.info(f"Fetched {len(instruments)} instruments successfully")
            except Exception as e:
                logger.error(f"Error fetching instruments data: {e}")
                self.instruments_df = pd.DataFrame()
        return self.instruments_df
    
    def get_instrument_token(self, ticker):
        """Get instrument token for a ticker with caching"""
        ticker = ticker.upper()
        if ticker in self.instrument_tokens:
            return self.instrument_tokens[ticker]

        df = self.get_instruments_data()
        if df.empty:
            logger.warning("Instruments data is empty. Cannot lookup instrument token.")
            return None

        # Use vectorized operations for filtering
        df_filtered = df[df['tradingsymbol'].str.upper() == ticker]

        if not df_filtered.empty:
            token = int(df_filtered.iloc[0]['instrument_token'])
            self.instrument_tokens[ticker] = token
            return token
        else:
            logger.warning(f"Instrument token for {ticker} not found.")
            return None
    
    def fetch_historical_data(self, ticker, interval, from_date, to_date):
        """Fetch historical data"""
        token = self.get_instrument_token(ticker)
        if token is None:
            logger.warning(f"Instrument token for {ticker} not found.")
            return pd.DataFrame()

        try:
            logger.info(f"Fetching data for {ticker} with interval {interval} from {from_date} to {to_date}...")
            data = self.kite.historical_data(token, from_date, to_date, interval)
            
            if not data:
                logger.warning(f"No data returned for {ticker}.")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df.rename(columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            }, inplace=True)
            
            logger.info(f"Successfully fetched {len(df)} records for {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()