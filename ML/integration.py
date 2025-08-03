import logging
import os
import pandas as pd
import numpy as np
from datetime import datetime
import threading
import time

from ML.models.dynamic_stop_loss import DynamicStopLossModel, PositionType
from ML.utils.atr_calculator import ATRCalculator
from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType

from data_handler import get_data_handler
from risk_management import get_risk_manager
from state_manager import get_state_manager
from config import get_config

logger = logging.getLogger(__name__)

class DynamicStopLossIntegration:
    """
    Integrates the dynamic stop loss model with the existing trading system.
    Provides methods to calculate and update stop losses for open positions.
    """
    
    def __init__(self, model_path=None):
        """
        Initialize the integration module.
        
        Args:
            model_path (str): Path to a pre-trained model file. If None, will use rule-based stops.
        """
        self.data_handler = get_data_handler()
        self.risk_manager = get_risk_manager()
        self.state_manager = get_state_manager()
        self.config = get_config()
        
        # Initialize the dynamic stop loss model
        self.stop_loss_model = DynamicStopLossModel()
        
        # Try to load a pre-trained model if provided
        self.using_ml_model = False
        if model_path and os.path.exists(model_path):
            if self.stop_loss_model.load_model(model_path):
                self.using_ml_model = True
                logger.info(f"Using ML-based dynamic stop loss model loaded from {model_path}")
            else:
                logger.warning(f"Failed to load model from {model_path}. Using rule-based stops.")
        else:
            logger.info("Using rule-based dynamic stop loss calculation (no ML model)")
        
        # Get configuration settings
        self.timeframe = self.config.get('Trading', 'risk_atr_timeframe', fallback="day")
        self.min_data_points = self.config.get_int('ML', 'min_data_points', fallback=50)
        self.update_interval = self.config.get_int('ML', 'stop_loss_update_interval', fallback=900)  # seconds
        
        # Configure minimum price distance for stop loss (prevents too tight stops)
        self.min_price_distance_pct = self.config.get_float('ML', 'min_stop_loss_distance_pct', fallback=0.5)
        
        # Start background updater thread if configured
        self.auto_update = self.config.get_bool('ML', 'auto_update_stop_loss', fallback=True)
        self.updater_thread = None
        self.stop_event = threading.Event()
        
        if self.auto_update:
            self.start_background_updater()
            
        logger.info("Initialized DynamicStopLossIntegration")
    
    def get_historical_data(self, ticker, timeframe=None, count=None):
        """
        Get historical data for a ticker.
        
        Args:
            ticker (str): Ticker symbol
            timeframe (str): Timeframe to use (default from config)
            count (int): Number of candles to retrieve
            
        Returns:
            pd.DataFrame: Historical OHLC data
        """
        if timeframe is None:
            timeframe = self.timeframe
            
        if count is None:
            count = self.min_data_points + 50  # Add buffer
        
        try:
            # Use data handler to fetch historical data
            data = self.data_handler.get_historical_data(ticker, timeframe, count)
            
            # Ensure we have enough data
            if data is None or len(data) < self.min_data_points:
                logger.warning(f"Insufficient data for {ticker}: Got {len(data) if data is not None else 0} points, "
                             f"need at least {self.min_data_points}")
                return None
            
            # Ensure data has required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in data.columns for col in required_columns):
                logger.error(f"Missing required columns in data for {ticker}")
                return None
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
            return None
    
    def calculate_dynamic_stop_loss(self, ticker, position_type, current_price=None):
        """
        Calculate dynamic stop loss for a ticker.
        
        Args:
            ticker (str): Ticker symbol
            position_type (str): Type of position ('LONG' or 'SHORT')
            current_price (float): Current price (optional, will fetch if not provided)
            
        Returns:
            float: Calculated stop loss price
        """
        try:
            # Get current price if not provided
            if current_price is None:
                current_price = self.data_handler.fetch_current_price(ticker)
                if current_price is None:
                    logger.error(f"Could not fetch current price for {ticker}")
                    return None
            
            # Get historical data
            data = self.get_historical_data(ticker)
            if data is None:
                logger.warning(f"No historical data available for {ticker}")
                return None
            
            # Calculate stop loss using the model
            if self.using_ml_model:
                stop_loss = self.stop_loss_model.predict_stop_loss(data, current_price, position_type)
            else:
                stop_loss = self.stop_loss_model.calculate_rule_based_stop_loss(data, current_price, position_type)
            
            # Ensure minimum distance from current price
            min_distance = current_price * (self.min_price_distance_pct / 100)
            if position_type.upper() == "LONG":
                if current_price - stop_loss < min_distance:
                    stop_loss = current_price - min_distance
                    logger.info(f"Adjusted stop loss for {ticker} to ensure minimum distance of {self.min_price_distance_pct}%")
            else:  # SHORT
                if stop_loss - current_price < min_distance:
                    stop_loss = current_price + min_distance
                    logger.info(f"Adjusted stop loss for {ticker} to ensure minimum distance of {self.min_price_distance_pct}%")
            
            # Round to 2 decimal places
            stop_loss = round(stop_loss, 2)
            
            logger.info(f"Calculated dynamic stop loss for {ticker} ({position_type}): {stop_loss:.2f}")
            return stop_loss
        
        except Exception as e:
            logger.error(f"Error calculating dynamic stop loss for {ticker}: {str(e)}")
            return None
    
    def update_stop_loss_for_position(self, ticker, position_data=None):
        """
        Update stop loss for a specific position.
        
        Args:
            ticker (str): Ticker symbol
            position_data (dict): Position data (optional, will fetch if not provided)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get position data if not provided
            if position_data is None:
                position_data = self.state_manager.get_position(ticker)
                if position_data is None:
                    logger.warning(f"No position data found for {ticker}")
                    return False
            
            position_type = position_data.get('type')
            if not position_type:
                logger.warning(f"Position type not found for {ticker}")
                return False
            
            # Get current price
            current_price = self.data_handler.fetch_current_price(ticker)
            if current_price is None:
                logger.error(f"Could not fetch current price for {ticker}")
                return False
                
            # Calculate dynamic stop loss
            stop_loss = self.calculate_dynamic_stop_loss(ticker, position_type, current_price)
            if stop_loss is None:
                logger.warning(f"Could not calculate dynamic stop loss for {ticker}")
                return False
            
            # Get existing GTT data
            gtt_data = self.state_manager.get_gtt(ticker)
            
            # Check if stop loss has changed significantly (to avoid unnecessary updates)
            min_change_threshold = 0.1  # Minimum 0.1% change to trigger update
            
            if gtt_data and 'trigger_price' in gtt_data:
                existing_stop = gtt_data['trigger_price']
                percent_change = abs(stop_loss - existing_stop) / existing_stop * 100
                
                if percent_change < min_change_threshold:
                    logger.info(f"Skip updating stop loss for {ticker} - change too small ({percent_change:.2f}%)")
                    return True
            
            # Get position quantity
            quantity = position_data.get('quantity', 0)
            if quantity <= 0:
                logger.warning(f"Invalid quantity for {ticker}: {quantity}")
                return False
            
            # Delete existing GTT order if any
            if gtt_data and 'trigger_id' in gtt_data:
                trigger_id = gtt_data['trigger_id']
                if trigger_id:
                    logger.info(f"Deleting existing GTT order for {ticker}: {trigger_id}")
                    self.risk_manager.delete_gtt_order(trigger_id, ticker)
            
            # Determine transaction type for GTT (opposite of position)
            transaction_type = "SELL" if position_type.upper() == "LONG" else "BUY"
            
            # Place new GTT order
            logger.info(f"Placing new GTT order for {ticker} with stop loss: {stop_loss:.2f}")
            success = self.risk_manager.place_new_gtt_order(ticker, quantity, stop_loss, transaction_type)
            
            if success:
                logger.info(f"Successfully updated stop loss for {ticker} to {stop_loss:.2f}")
                return True
            else:
                logger.error(f"Failed to update stop loss for {ticker}")
                return False
        
        except Exception as e:
            logger.error(f"Error updating stop loss for {ticker}: {str(e)}")
            return False
    
    def update_all_stop_losses(self):
        """
        Update stop losses for all open positions.
        
        Returns:
            int: Number of positions successfully updated
        """
        try:
            # Get all positions
            positions = self.state_manager.get_all_positions()
            if not positions:
                logger.info("No open positions found to update")
                return 0
            
            logger.info(f"Updating stop losses for {len(positions)} positions")
            success_count = 0
            
            for ticker, position_data in positions.items():
                # Skip positions that aren't active
                if position_data.get('quantity', 0) <= 0:
                    continue
                    
                # Skip CNC (delivery) positions if configured
                if position_data.get('product_type') == 'CNC' and not self.config.get_bool('ML', 'update_cnc_stops', fallback=False):
                    logger.info(f"Skipping CNC position for {ticker} as configured")
                    continue
                
                if self.update_stop_loss_for_position(ticker, position_data):
                    success_count += 1
            
            logger.info(f"Updated stop losses for {success_count}/{len(positions)} positions")
            return success_count
        
        except Exception as e:
            logger.error(f"Error updating all stop losses: {str(e)}")
            return 0
    
    def start_background_updater(self):
        """Start the background thread for automatic stop loss updates"""
        if self.updater_thread and self.updater_thread.is_alive():
            logger.warning("Background updater already running")
            return
        
        self.stop_event.clear()
        self.updater_thread = threading.Thread(
            target=self._background_update_loop,
            daemon=True,
            name="DynamicStopLossUpdater"
        )
        self.updater_thread.start()
        logger.info(f"Started background stop loss updater (interval: {self.update_interval}s)")
    
    def stop_background_updater(self):
        """Stop the background updater thread"""
        if self.updater_thread and self.updater_thread.is_alive():
            self.stop_event.set()
            self.updater_thread.join(timeout=10)
            logger.info("Stopped background stop loss updater")
    
    def _background_update_loop(self):
        """Background thread function to periodically update stop losses"""
        while not self.stop_event.is_set():
            try:
                # Only update during market hours
                current_time = datetime.now().time()
                market_open = datetime.strptime('09:15:00', '%H:%M:%S').time()
                market_close = datetime.strptime('15:30:00', '%H:%M:%S').time()
                
                if market_open <= current_time <= market_close:
                    logger.info("Background updater: Updating all stop losses")
                    self.update_all_stop_losses()
                else:
                    logger.debug("Background updater: Outside market hours, skipping update")
                
                # Sleep for the configured interval, but check stop_event periodically
                for _ in range(self.update_interval // 10):
                    if self.stop_event.is_set():
                        break
                    time.sleep(10)
            
            except Exception as e:
                logger.error(f"Error in background updater: {str(e)}")
                time.sleep(60)  # Sleep for a minute on error before retrying

# Create singleton instance
_dynamic_stop_loss = None

def get_dynamic_stop_loss(model_path=None):
    """
    Get or create the singleton dynamic stop loss integration instance.
    
    Args:
        model_path (str): Path to a pre-trained model file
        
    Returns:
        DynamicStopLossIntegration: The singleton instance
    """
    global _dynamic_stop_loss
    if _dynamic_stop_loss is None:
        _dynamic_stop_loss = DynamicStopLossIntegration(model_path)
    return _dynamic_stop_loss