#!/usr/bin/env python3
"""
User-Aware State Manager
Replaces the global state file with user-specific state files
"""
import os
import json
import logging
import datetime
from typing import Dict, Any, Optional, List, Tuple
from config import get_config

logger = logging.getLogger(__name__)

class UserAwareStateManager:
    """
    State manager that maintains separate state files per user
    Replaces StateManager for multi-user support
    """
    
    def __init__(self, user_name: str):
        self.user_name = user_name
        self.config = get_config()
        self.data_dir = self.config.get('System', 'data_dir')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # User-specific state file
        self.state_file = os.path.join(self.data_dir, f'trading_state_{user_name}.json')
        
        # Initialize default state structure
        self.state = {
            "meta": {
                "user_name": user_name,
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.datetime.now().isoformat(),
                "created": datetime.datetime.now().isoformat()
            },
            "positions": {},
            "daily_tickers": {
                "long": [],
                "short": []
            },
            "gtt_orders": {},
            "session_data": {}
        }
        
        # Load existing state if available
        self._load_state()

        # Always save state to ensure file exists
        self._save_state()

        logger.info(f"UserAwareStateManager initialized for user: {user_name}")
        logger.info(f"State file: {self.state_file}")
    
    def _load_state(self) -> None:
        """Load user-specific state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    loaded_state = json.load(f)
                
                # Ensure the loaded state has all required keys
                for key in self.state:
                    if key not in loaded_state:
                        loaded_state[key] = self.state[key]
                
                # Ensure meta section has user_name
                if 'user_name' not in loaded_state['meta']:
                    loaded_state['meta']['user_name'] = self.user_name
                
                self.state = loaded_state
                logger.info(f"Loaded existing state for {self.user_name}")
                
            except Exception as e:
                logger.error(f"Error loading state for {self.user_name}: {e}")
                logger.info(f"Creating new state for {self.user_name}")
        else:
            logger.info(f"Creating new state file for {self.user_name}")
    
    def _save_state(self) -> None:
        """Save user-specific state to file"""
        try:
            # Update metadata
            self.state['meta']['last_updated'] = datetime.datetime.now().isoformat()
            self.state['meta']['user_name'] = self.user_name
            
            # Ensure data directory exists
            os.makedirs(self.data_dir, exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            
            logger.debug(f"State saved for {self.user_name}")
            
        except Exception as e:
            logger.error(f"Error saving state for {self.user_name}: {e}")
    
    # Position Management Methods
    def get_position(self, ticker: str) -> Optional[Dict]:
        """Get position data for a specific ticker"""
        return self.state['positions'].get(ticker)
    
    def set_position(self, ticker: str, position_data: Dict):
        """Set position data for a specific ticker"""
        self.state['positions'][ticker] = position_data
        self._save_state()
        logger.info(f"Position set for {ticker} (user: {self.user_name})")
    
    def remove_position(self, ticker: str):
        """Remove position for a specific ticker"""
        if ticker in self.state['positions']:
            del self.state['positions'][ticker]
            self._save_state()
            logger.info(f"Position removed for {ticker} (user: {self.user_name})")
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """Get all positions for this user"""
        return self.state['positions'].copy()
    
    def get_position_count(self) -> int:
        """Get total number of active positions"""
        return len(self.state['positions'])
    
    def get_positions_by_product_type(self, product_type: str) -> Dict[str, Dict]:
        """Get positions filtered by product type (MIS, CNC, etc.)"""
        filtered_positions = {}
        for ticker, position in self.state['positions'].items():
            if position.get('product_type') == product_type:
                filtered_positions[ticker] = position
        return filtered_positions
    
    # Daily Tickers Management
    def add_daily_ticker(self, ticker: str, position_type: str = "long"):
        """Add ticker to daily tracking list"""
        if position_type not in ["long", "short"]:
            raise ValueError("position_type must be 'long' or 'short'")
        
        if ticker not in self.state['daily_tickers'][position_type]:
            self.state['daily_tickers'][position_type].append(ticker)
            self._save_state()
            logger.info(f"Added {ticker} to daily {position_type} tickers (user: {self.user_name})")
    
    def remove_daily_ticker(self, ticker: str, position_type: str = None):
        """Remove ticker from daily tracking list"""
        removed = False
        
        if position_type:
            if ticker in self.state['daily_tickers'][position_type]:
                self.state['daily_tickers'][position_type].remove(ticker)
                removed = True
        else:
            # Remove from both long and short if position_type not specified
            for ptype in ["long", "short"]:
                if ticker in self.state['daily_tickers'][ptype]:
                    self.state['daily_tickers'][ptype].remove(ticker)
                    removed = True
        
        if removed:
            self._save_state()
            logger.info(f"Removed {ticker} from daily tickers (user: {self.user_name})")
    
    def get_daily_tickers(self, position_type: str = None) -> List[str]:
        """Get daily tickers list"""
        if position_type:
            return self.state['daily_tickers'].get(position_type, []).copy()
        else:
            # Return all tickers
            all_tickers = []
            for ptype in ["long", "short"]:
                all_tickers.extend(self.state['daily_tickers'].get(ptype, []))
            return list(set(all_tickers))  # Remove duplicates
    
    def clear_daily_tickers(self, position_type: str = None):
        """Clear daily tickers list"""
        if position_type:
            self.state['daily_tickers'][position_type] = []
        else:
            self.state['daily_tickers'] = {"long": [], "short": []}
        
        self._save_state()
        logger.info(f"Cleared daily tickers (user: {self.user_name})")
    
    # GTT Orders Management
    def add_gtt_order(self, gtt_id: str, order_data: Dict):
        """Add GTT order tracking"""
        self.state['gtt_orders'][gtt_id] = order_data
        self._save_state()
        logger.info(f"GTT order {gtt_id} added (user: {self.user_name})")
    
    def remove_gtt_order(self, gtt_id: str):
        """Remove GTT order tracking"""
        if gtt_id in self.state['gtt_orders']:
            del self.state['gtt_orders'][gtt_id]
            self._save_state()
            logger.info(f"GTT order {gtt_id} removed (user: {self.user_name})")
    
    def get_gtt_order(self, gtt_id: str) -> Optional[Dict]:
        """Get GTT order data"""
        return self.state['gtt_orders'].get(gtt_id)
    
    def get_all_gtt_orders(self) -> Dict[str, Dict]:
        """Get all GTT orders"""
        return self.state['gtt_orders'].copy()
    
    # Session Data Management
    def set_session_data(self, key: str, value: Any):
        """Set session-specific data"""
        self.state['session_data'][key] = value
        self._save_state()
    
    def get_session_data(self, key: str, default: Any = None) -> Any:
        """Get session-specific data"""
        return self.state['session_data'].get(key, default)
    
    def clear_session_data(self):
        """Clear all session data"""
        self.state['session_data'] = {}
        self._save_state()
        logger.info(f"Session data cleared (user: {self.user_name})")
    
    # Daily Reset Functionality
    def reset_daily_state(self):
        """Reset state for a new trading day"""
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Only reset if it's actually a new day
        if self.state['meta']['date'] != current_date:
            logger.info(f"Resetting daily state for new trading day: {current_date} (user: {self.user_name})")
            
            # Clear MIS positions (they don't carry over)
            mis_positions = []
            for ticker, position in list(self.state['positions'].items()):
                if position.get('product_type') == 'MIS':
                    mis_positions.append(ticker)
                    del self.state['positions'][ticker]
            
            if mis_positions:
                logger.info(f"Cleared MIS positions: {mis_positions} (user: {self.user_name})")
            
            # Clear daily tickers
            self.clear_daily_tickers()
            
            # Clear session data
            self.clear_session_data()
            
            # Update date
            self.state['meta']['date'] = current_date
            self._save_state()
    
    # Utility Methods
    def get_user_name(self) -> str:
        """Get the user name for this state manager"""
        return self.user_name
    
    def get_state_file_path(self) -> str:
        """Get the path to the state file"""
        return self.state_file
    
    def export_state(self) -> Dict:
        """Export current state (for backup/debugging)"""
        return self.state.copy()
    
    def import_state(self, state_data: Dict):
        """Import state data (for migration/restoration)"""
        # Validate that it's for the correct user
        if state_data.get('meta', {}).get('user_name') != self.user_name:
            raise ValueError(f"State data is for different user: {state_data.get('meta', {}).get('user_name')}")
        
        self.state = state_data
        self._save_state()
        logger.info(f"State imported for {self.user_name}")

# Factory function for user context manager
def create_user_state_manager(user_name: str) -> UserAwareStateManager:
    """Create a user-specific state manager"""
    return UserAwareStateManager(user_name)