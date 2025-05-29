#!/usr/bin/env python3
"""
Proposed User Context Manager for Multi-User Trading System
This solves the singleton issue by providing user-scoped instances
"""
import os
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class UserCredentials:
    """User credentials container"""
    name: str
    api_key: str
    api_secret: str
    access_token: str

class UserContextManager:
    """
    Manages user-specific instances of trading components
    Replaces global singletons with user-scoped instances
    """
    
    def __init__(self):
        self._user_instances: Dict[str, Dict[str, Any]] = {}
        self._current_user: Optional[str] = None
        self._lock = threading.Lock()
    
    def set_current_user(self, user_name: str, credentials: UserCredentials):
        """
        Set the current active user and initialize their instances
        
        Args:
            user_name: Name of the user
            credentials: User's API credentials
        """
        with self._lock:
            self._current_user = user_name
            
            # Set environment variables for this user
            os.environ['ZERODHA_API_KEY'] = credentials.api_key
            os.environ['ZERODHA_API_SECRET'] = credentials.api_secret
            os.environ['ZERODHA_ACCESS_TOKEN'] = credentials.access_token
            
            # Initialize user-specific instances if not exists
            if user_name not in self._user_instances:
                self._user_instances[user_name] = {}
    
    def get_user_instance(self, component_type: str, factory_func):
        """
        Get user-specific instance of a component
        
        Args:
            component_type: Type of component ('state_manager', 'order_manager', etc.)
            factory_func: Function to create new instance
            
        Returns:
            User-specific instance of the component
        """
        if not self._current_user:
            raise RuntimeError("No current user set. Call set_current_user() first.")
        
        with self._lock:
            user_instances = self._user_instances[self._current_user]
            
            if component_type not in user_instances:
                # Create new instance for this user
                user_instances[component_type] = factory_func()
            
            return user_instances[component_type]
    
    def get_current_user(self) -> Optional[str]:
        """Get the current active user"""
        return self._current_user
    
    def clear_user_instances(self, user_name: str = None):
        """
        Clear instances for a specific user or current user
        
        Args:
            user_name: User to clear instances for. If None, clears current user.
        """
        target_user = user_name or self._current_user
        if target_user and target_user in self._user_instances:
            with self._lock:
                del self._user_instances[target_user]

# Global context manager instance
_context_manager = UserContextManager()

def get_context_manager() -> UserContextManager:
    """Get the global user context manager"""
    return _context_manager

# User-aware singleton getters
def get_user_state_manager():
    """Get state manager for current user"""
    from state_manager import StateManager
    return _context_manager.get_user_instance('state_manager', StateManager)

def get_user_order_manager():
    """Get order manager for current user"""
    from order_manager import OrderManager
    return _context_manager.get_user_instance('order_manager', OrderManager)

def get_user_data_handler():
    """Get data handler for current user"""
    from data_handler import DataHandler
    return _context_manager.get_user_instance('data_handler', DataHandler)

def get_user_config():
    """Get config for current user"""
    from config import Config
    return _context_manager.get_user_instance('config', Config)