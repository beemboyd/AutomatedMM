#!/usr/bin/env python3
"""
User-Aware State Manager
Replaces the global state file with user-specific state files
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

class UserAwareStateManager:
    """
    State manager that maintains separate state files per user
    """
    
    def __init__(self, user_name: str):
        self.user_name = user_name
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # User-specific state file
        self.state_file = os.path.join(self.data_dir, f'trading_state_{user_name}.json')
        self.state = self._load_state()
        
        logging.info(f"StateManager initialized for user: {user_name}")
        logging.info(f"State file: {self.state_file}")
    
    def _load_state(self) -> Dict[str, Any]:
        """Load user-specific state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logging.info(f"Loaded existing state for {self.user_name}")
                return state
            except Exception as e:
                logging.error(f"Error loading state for {self.user_name}: {e}")
        
        # Create new state
        logging.info(f"Creating new state for {self.user_name}")
        return {
            'user_name': self.user_name,
            'positions': {},
            'gtt_orders': {},
            'daily_tickers': {},
            'last_updated': datetime.now().isoformat(),
            'session_data': {}
        }
    
    def _save_state(self):
        """Save user-specific state to file"""
        try:
            self.state['last_updated'] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            logging.debug(f"State saved for {self.user_name}")
        except Exception as e:
            logging.error(f"Error saving state for {self.user_name}: {e}")
    
    def get_position(self, ticker: str) -> Optional[Dict]:
        """Get position data for a specific ticker"""
        return self.state['positions'].get(ticker)
    
    def set_position(self, ticker: str, position_data: Dict):
        """Set position data for a specific ticker"""
        self.state['positions'][ticker] = position_data
        self._save_state()
    
    def remove_position(self, ticker: str):
        """Remove position for a specific ticker"""
        if ticker in self.state['positions']:
            del self.state['positions'][ticker]
            self._save_state()
    
    def get_all_positions(self) -> Dict[str, Dict]:
        """Get all positions for this user"""
        return self.state['positions'].copy()
    
    def add_gtt_order(self, gtt_id: str, order_data: Dict):
        """Add GTT order tracking"""
        self.state['gtt_orders'][gtt_id] = order_data
        self._save_state()
    
    def remove_gtt_order(self, gtt_id: str):
        """Remove GTT order tracking"""
        if gtt_id in self.state['gtt_orders']:
            del self.state['gtt_orders'][gtt_id]
            self._save_state()
    
    def get_user_name(self) -> str:
        """Get the user name for this state manager"""
        return self.user_name

# Factory function for user context manager
def create_user_state_manager(user_name: str) -> UserAwareStateManager:
    """Create a user-specific state manager"""
    return UserAwareStateManager(user_name)