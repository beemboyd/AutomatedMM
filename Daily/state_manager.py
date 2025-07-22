import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any, Tuple

try:
    from .config import get_config
except ImportError:
    from config import get_config

logger = logging.getLogger(__name__)

class StateManager:
    """
    Centralized state manager for the trading system.
    Handles all position tracking, GTT management, and daily ticker records.
    Replaces multiple state files with a single consolidated state file.
    """
    
    def __init__(self):
        self.config = get_config()
        self.data_dir = self.config.get('System', 'data_dir')
        self.state_file = os.path.join(self.data_dir, 'trading_state.json')
        
        # Initialize default state structure
        self.state = {
            "meta": {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.datetime.now().isoformat()
            },
            "positions": {},
            "daily_tickers": {
                "long": [],
                "short": []
            }
        }
        
        # Load existing state if available
        self._load_state()
        
        # One-time migration from legacy files if needed
        if not os.path.exists(self.state_file):
            self._migrate_from_legacy_files()
    
    def _load_state(self) -> None:
        """Load state from the consolidated state file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded state from {self.state_file}")
                
                # Get the last modified time of the state file
                last_modified = os.path.getmtime(self.state_file)
                last_modified_time = datetime.datetime.fromtimestamp(last_modified)
                current_time = datetime.datetime.now()
                
                # Check if we need to reset for a new day
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                if self.state["meta"]["date"] != today:
                    logger.info("New trading day detected, performing full reset")
                    self.reset_for_new_trading_day()
                # Check if this is a service restart (file was last modified more than 10 minutes ago)
                elif (current_time - last_modified_time).total_seconds() > 600:
                    logger.info("Service restart detected, cleaning MIS positions")
                    # Force reset to clean MIS positions on restart, even on the same day
                    self.reset_for_new_trading_day(force=True)
            except Exception as e:
                logger.error(f"Error loading state from {self.state_file}: {e}")
                # Keep using default initialized state
    
    def _save_state(self) -> None:
        """Save current state to the consolidated state file"""
        try:
            # Update last_updated timestamp
            self.state["meta"]["last_updated"] = datetime.datetime.now().isoformat()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            # Write to file with pretty formatting
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            logger.debug(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state to {self.state_file}: {e}")
    
    def _migrate_from_legacy_files(self) -> None:
        """Create new consolidated state format"""
        try:
            # Initialize with empty structure
            self.state = {
                "meta": {
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "last_updated": datetime.datetime.now().isoformat()
                },
                "positions": {},
                "daily_tickers": {
                    "long": [],
                    "short": []
                }
            }
            
            # Save the consolidated state
            self._save_state()
            logger.info("Created new consolidated state file")
        
        except Exception as e:
            logger.error(f"Error creating state file: {e}")
    
    # Position Management Methods
    
    def add_position(self, ticker: str, position_type: str, quantity: int, 
                     entry_price: float, product_type: str = "MIS", timestamp: Optional[str] = None,
                     confirmation: Optional[str] = None) -> None:
        """
        Add a new position or update an existing one
        
        Args:
            ticker: The stock ticker symbol
            position_type: "LONG" or "SHORT"
            quantity: Number of shares
            entry_price: Entry price per share
            product_type: "MIS" (intraday) or "CNC" (delivery)
            timestamp: Optional timestamp (ISO format)
            confirmation: Optional trade confirmation number
        """
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat()
        
        if ticker in self.state["positions"]:
            # Update existing position
            position = self.state["positions"][ticker]
            position["type"] = position_type
            position["entry_price"] = entry_price
            position["quantity"] = quantity
            position["product_type"] = product_type  # Explicitly track product type
            position["timestamp"] = timestamp
            # Keep the best_price if exists, otherwise initialize with entry_price
            if "best_price" not in position:
                position["best_price"] = entry_price
            # Add confirmation number if provided
            if confirmation:
                position["confirmation"] = confirmation
        else:
            # Create new position
            position_data = {
                "type": position_type,
                "entry_price": entry_price,
                "best_price": entry_price,
                "quantity": quantity,
                "product_type": product_type,  # Explicitly track product type
                "timestamp": timestamp,
                "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            # Add confirmation number if provided
            if confirmation:
                position_data["confirmation"] = confirmation
                
            self.state["positions"][ticker] = position_data
        
        # Add to daily tickers
        position_type_lower = position_type.lower()
        if position_type_lower in ["long", "short"]:
            if ticker not in self.state["daily_tickers"][position_type_lower]:
                self.state["daily_tickers"][position_type_lower].append(ticker)
        
        self._save_state()
    
    def remove_position(self, ticker: str, exit_price: Optional[float] = None, 
                          exit_reason: Optional[str] = None, 
                          exit_confirmation: Optional[str] = None) -> bool:
        """
        Remove a position completely or mark it as exited with details
        
        Args:
            ticker: The stock ticker symbol
            exit_price: Optional exit price to record
            exit_reason: Optional reason for the exit
            exit_confirmation: Optional exit trade confirmation number
            
        Returns:
            bool: True if position was removed, False if not found
        """
        if ticker in self.state["positions"]:
            if exit_price is not None:
                # Record exit details instead of removing
                self.state["positions"][ticker]["exit_price"] = exit_price
                self.state["positions"][ticker]["exit_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if exit_reason:
                    self.state["positions"][ticker]["exit_reason"] = exit_reason
                    
                if exit_confirmation:
                    self.state["positions"][ticker]["exit_confirmation"] = exit_confirmation
                    
                # Calculate profit/loss
                entry_price = float(self.state["positions"][ticker]["entry_price"])
                quantity = int(self.state["positions"][ticker]["quantity"])
                position_type = self.state["positions"][ticker]["type"].lower()
                
                if position_type == "long":
                    pnl = (exit_price - entry_price) * quantity
                else:  # Short position
                    pnl = (entry_price - exit_price) * quantity
                    
                self.state["positions"][ticker]["pnl"] = pnl
                
                # Save the complete transaction but don't actually remove
                # This preserves the trade history for reporting
                self._save_state()
                return True
            else:
                # Traditional remove behavior
                del self.state["positions"][ticker]
                self._save_state()
                return True
                
        return False
    
    def update_position_quantity(self, ticker: str, quantity: int) -> bool:
        """
        Update the quantity of an existing position
        
        Args:
            ticker: The stock ticker symbol
            quantity: New quantity
            
        Returns:
            bool: True if updated, False if position not found
        """
        if ticker in self.state["positions"]:
            self.state["positions"][ticker]["quantity"] = quantity
            self.state["positions"][ticker]["timestamp"] = datetime.datetime.now().isoformat()
            self._save_state()
            return True
        return False
    
    def update_best_price(self, ticker: str, best_price: float) -> bool:
        """
        Update the best price for trailing stop calculation
        
        Args:
            ticker: The stock ticker symbol
            best_price: New best price
            
        Returns:
            bool: True if updated, False if position not found
        """
        if ticker in self.state["positions"]:
            self.state["positions"][ticker]["best_price"] = best_price
            self._save_state()
            return True
        return False
    
    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get position data for a specific ticker
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            Optional[Dict]: Position data or None if not found
        """
        return self.state["positions"].get(ticker)
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all positions
        
        Returns:
            Dict: All position data
        """
        return self.state["positions"]
    
    def get_positions_by_type(self, position_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get positions filtered by type (LONG or SHORT)
        
        Args:
            position_type: "LONG" or "SHORT"
            
        Returns:
            Dict: Filtered position data
        """
        return {
            ticker: data for ticker, data in self.state["positions"].items()
            if data.get("type") == position_type
        }
    
    # GTT Management Methods
    
    def add_gtt(self, ticker: str, trigger_id: int, trigger_price: float) -> bool:
        """
        Add or update a GTT (Good Till Triggered) order
        
        Args:
            ticker: The stock ticker symbol
            trigger_id: GTT ID from broker
            trigger_price: Price at which the order triggers
            
        Returns:
            bool: True if updated, False if position not found
        """
        if ticker in self.state["positions"]:
            if "gtt" not in self.state["positions"][ticker]:
                self.state["positions"][ticker]["gtt"] = {}
            
            self.state["positions"][ticker]["gtt"] = {
                "trigger_id": trigger_id,
                "trigger_price": trigger_price,
                "timestamp": datetime.datetime.now().isoformat()
            }
            self._save_state()
            return True
        return False
    
    def remove_gtt(self, ticker: str) -> bool:
        """
        Remove GTT data for a position
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            bool: True if removed, False if not found
        """
        if ticker in self.state["positions"] and "gtt" in self.state["positions"][ticker]:
            del self.state["positions"][ticker]["gtt"]
            self._save_state()
            return True
        return False
    
    def get_gtt(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get GTT data for a specific ticker
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            Optional[Dict]: GTT data or None if not found
        """
        if ticker in self.state["positions"] and "gtt" in self.state["positions"][ticker]:
            return self.state["positions"][ticker]["gtt"]
        return None
    
    def get_all_gtts(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all GTT data
        
        Returns:
            Dict: All GTT data mapped by ticker
        """
        return {
            ticker: data["gtt"] 
            for ticker, data in self.state["positions"].items() 
            if "gtt" in data
        }
    
    # Daily Ticker Management Methods
    
    def add_daily_ticker(self, ticker: str, position_type: str) -> None:
        """
        Add ticker to the daily tickers list
        
        Args:
            ticker: The stock ticker symbol
            position_type: "long" or "short"
        """
        position_type = position_type.lower()
        if position_type in ["long", "short"]:
            if ticker not in self.state["daily_tickers"][position_type]:
                self.state["daily_tickers"][position_type].append(ticker)
                self._save_state()
                
    def remove_daily_ticker(self, ticker: str, position_type: str) -> None:
        """
        Remove ticker from the daily tickers list
        
        Args:
            ticker: The stock ticker symbol
            position_type: "long" or "short"
        """
        position_type = position_type.lower()
        if position_type in ["long", "short"]:
            if ticker in self.state["daily_tickers"][position_type]:
                self.state["daily_tickers"][position_type].remove(ticker)
                self._save_state()
    
    def get_daily_tickers(self, position_type: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get daily tickers
        
        Args:
            position_type: Optional filter by "long" or "short"
            
        Returns:
            Dict or List: Daily tickers data
        """
        if position_type:
            position_type = position_type.lower()
            if position_type in ["long", "short"]:
                return self.state["daily_tickers"][position_type]
            return []
        return self.state["daily_tickers"]
    
    def is_ticker_traded_today(self, ticker: str, position_type: Optional[str] = None) -> bool:
        """
        Check if a ticker has been traded today
        
        Args:
            ticker: The stock ticker symbol
            position_type: Optional filter by "long" or "short"
            
        Returns:
            bool: True if ticker traded today in the specified direction
        """
        if position_type:
            position_type = position_type.lower()
            if position_type in ["long", "short"]:
                return ticker in self.state["daily_tickers"][position_type]
            return False
        
        # Check both long and short
        return (ticker in self.state["daily_tickers"]["long"] or 
                ticker in self.state["daily_tickers"]["short"])
    
    def is_long_ticker(self, ticker: str) -> bool:
        """
        Check if a ticker is in the long tickers list
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            bool: True if ticker is in long tickers list
        """
        ticker = ticker.upper()
        if 'daily_tickers' not in self.state or 'long' not in self.state['daily_tickers']:
            return False
        return ticker in self.state['daily_tickers']['long']
    
    def is_short_ticker(self, ticker: str) -> bool:
        """
        Check if a ticker is in the short tickers list
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            bool: True if ticker is in short tickers list
        """
        ticker = ticker.upper()
        if 'daily_tickers' not in self.state or 'short' not in self.state['daily_tickers']:
            return False
        return ticker in self.state['daily_tickers']['short']
    
        
    def reset_for_new_trading_day(self, force: bool = False) -> bool:
        """
        Reset all state files for a new trading day:
        1. Reset daily tickers
        2. Clear all MIS positions (since they can't carry over to the next day)
        3. Handle special cases or flags
        4. Log all reset actions
        
        Args:
            force: Force reset even if it's the same day
            
        Returns:
            bool: True if reset was performed, False otherwise
        """
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # Check if we need to reset for a new day
            if not force and self.state["meta"]["date"] == today:
                logger.info("Already reset for today, skipping. Use force=True to override.")
                return False
            
            logger.info(f"Performing state reset for new trading day: {today}")
            
            # Store previous state for logging purposes
            prev_state = {
                "date": self.state["meta"]["date"],
                "positions_count": len(self.state["positions"]),
                "daily_long_count": len(self.state["daily_tickers"]["long"]),
                "daily_short_count": len(self.state["daily_tickers"]["short"])
            }
            
            # 1. Reset meta date
            self.state["meta"]["date"] = today
            
            # 2. Reset daily tickers - complete clean slate for new day
            self.state["daily_tickers"] = {"long": [], "short": []}
            logger.info("Daily tickers reset successfully")
            
            # 3. Clear ALL MIS positions (aggressive cleanup)
            positions_to_keep = {}
            mis_positions = []
            cnc_positions = []
            
            # First pass - identify MIS vs CNC positions
            for ticker, position in self.state["positions"].items():
                # Check if product type is explicitly stored in position data
                product_type = position.get("product_type", "").upper()
                
                # Only keep positions explicitly marked as CNC
                if product_type == "CNC":
                    positions_to_keep[ticker] = position
                    cnc_positions.append(ticker)
                    logger.info(f"Keeping {ticker} - explicit CNC product type")
                else:
                    # Everything else is considered MIS and will be removed
                    mis_positions.append(ticker)
                    logger.info(f"Removing {ticker} - treating as MIS position")
            
            # Replace positions with only the CNC positions we're keeping
            self.state["positions"] = positions_to_keep
            
            # Log the cleanup results
            if mis_positions:
                logger.info(f"Cleared {len(mis_positions)} MIS positions: {', '.join(mis_positions)}")
            else:
                logger.info("No MIS positions to clear")
                
            if cnc_positions:
                logger.info(f"Kept {len(cnc_positions)} CNC positions: {', '.join(cnc_positions)}")
            else:
                logger.info("No CNC positions found to keep")
            
            # 4. Handle any special flags stored in persistent state
            persistent_state_file = os.path.join(self.data_dir, 'persistent_state.json')
            if os.path.exists(persistent_state_file):
                try:
                    with open(persistent_state_file, 'r') as f:
                        persistent_state = json.load(f)
                    
                    # Process any special flags that should affect reset behavior
                    if persistent_state.get("preserve_positions", False):
                        logger.info("Preserve positions flag detected - positions were not cleared")
                    
                    # Any other special flags can be handled here
                    
                except Exception as e:
                    logger.error(f"Error processing persistent state during reset: {e}")
            
            # 5. Save the updated state
            self._save_state()
            
            # 6. Log summary of changes
            logger.info(f"State reset summary: Previous state from {prev_state['date']} - "
                       f"{prev_state['positions_count']} positions, "
                       f"{prev_state['daily_long_count']} daily long tickers, "
                       f"{prev_state['daily_short_count']} daily short tickers. "
                       f"New state has {len(self.state['positions'])} positions.")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during state reset for new trading day: {e}")
            # In case of error, try to restore a clean default state
            try:
                self.state["meta"]["date"] = today
                self.state["daily_tickers"] = {"long": [], "short": []}
                self._save_state()
                logger.info("Restored basic state after error")
            except Exception as recovery_error:
                logger.critical(f"Failed to recover state after reset error: {recovery_error}")
            
            return False


# Create singleton instance
_state_manager = None

def get_state_manager():
    """Get or create the singleton state manager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager