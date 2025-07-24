#!/usr/bin/env python3
"""
VSR Momentum Exit Rules
Defines exit strategies for VSR momentum trades
To be used by SL_watchdog.py for position management
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple

class VSRMomentumExitRules:
    """Exit rules for VSR momentum trades"""
    
    def __init__(self):
        # Exit parameters
        self.initial_stop_loss_pct = 3.0  # Initial stop loss %
        self.trailing_activation_pct = 2.0  # Activate trailing at 2% profit
        self.trailing_distance_pct = 1.5  # Trail by 1.5% from peak
        
        # Time-based exits
        self.max_hold_minutes = 180  # Maximum 3 hours for momentum trades
        self.quick_profit_target = 5.0  # Take 50% profit at 5%
        self.full_profit_target = 8.0  # Exit fully at 8%
        
        # Momentum exhaustion
        self.momentum_exhaustion_minutes = 30  # Check after 30 minutes
        self.min_momentum_continuation = 0.5  # Minimum 0.5% move in 30 min
        
    def calculate_stop_loss(self, position_data: Dict, current_price: float) -> Tuple[float, str]:
        """
        Calculate stop loss for VSR momentum position
        Returns: (stop_price, reason)
        """
        entry_price = position_data.get('entry_price', position_data.get('average_price', 0))
        peak_price = position_data.get('peak_price', entry_price)
        entry_time = position_data.get('entry_time')
        
        if not entry_price or entry_price <= 0:
            return 0, "Invalid entry price"
        
        # Calculate profit/loss percentage
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Update peak if needed
        if current_price > peak_price:
            peak_price = current_price
            position_data['peak_price'] = peak_price
        
        # Time-based exit
        if entry_time:
            try:
                entry_dt = datetime.fromisoformat(entry_time)
                time_held = (datetime.now() - entry_dt).total_seconds() / 60  # minutes
                
                # Exit after max hold time
                if time_held >= self.max_hold_minutes:
                    return current_price * 0.999, f"Max hold time reached ({self.max_hold_minutes} min)"
                
                # Check momentum exhaustion after 30 minutes
                if time_held >= self.momentum_exhaustion_minutes and pnl_pct < self.min_momentum_continuation:
                    return current_price * 0.999, f"Momentum exhausted (only {pnl_pct:.1f}% in {time_held:.0f} min)"
                    
            except:
                pass
        
        # Profit-based exits
        if pnl_pct >= self.full_profit_target:
            return current_price * 0.995, f"Full profit target reached ({pnl_pct:.1f}%)"
        
        # Trailing stop logic
        if pnl_pct >= self.trailing_activation_pct:
            # Trailing stop is active
            position_data['trailing_active'] = True
            trailing_stop = peak_price * (1 - self.trailing_distance_pct / 100)
            
            # Make sure trailing stop is above entry
            trailing_stop = max(trailing_stop, entry_price * 1.002)  # At least 0.2% above entry
            
            return trailing_stop, f"Trailing stop (Peak: ₹{peak_price:.2f})"
        
        # Initial stop loss
        initial_stop = entry_price * (1 - self.initial_stop_loss_pct / 100)
        return initial_stop, "Initial stop loss"
    
    def should_take_partial_profit(self, position_data: Dict, current_price: float) -> Tuple[bool, float, str]:
        """
        Check if partial profit should be taken
        Returns: (should_exit, exit_percentage, reason)
        """
        entry_price = position_data.get('entry_price', position_data.get('average_price', 0))
        partial_taken = position_data.get('partial_profit_taken', False)
        
        if not entry_price or entry_price <= 0 or partial_taken:
            return False, 0, ""
        
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Take 50% at quick profit target
        if pnl_pct >= self.quick_profit_target:
            position_data['partial_profit_taken'] = True
            return True, 50, f"Partial profit at {pnl_pct:.1f}%"
        
        return False, 0, ""
    
    def get_exit_summary(self, position_data: Dict, current_price: float) -> Dict:
        """Get complete exit analysis for position"""
        entry_price = position_data.get('entry_price', position_data.get('average_price', 0))
        
        if not entry_price or entry_price <= 0:
            return {}
        
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        stop_loss, stop_reason = self.calculate_stop_loss(position_data, current_price)
        should_partial, partial_pct, partial_reason = self.should_take_partial_profit(position_data, current_price)
        
        # Calculate risk/reward
        risk = ((entry_price - stop_loss) / entry_price) * 100
        potential_reward = self.full_profit_target
        risk_reward_ratio = potential_reward / risk if risk > 0 else 0
        
        return {
            'current_pnl_pct': pnl_pct,
            'stop_loss': stop_loss,
            'stop_reason': stop_reason,
            'stop_distance_pct': ((current_price - stop_loss) / current_price) * 100,
            'should_take_partial': should_partial,
            'partial_percentage': partial_pct,
            'partial_reason': partial_reason,
            'trailing_active': position_data.get('trailing_active', False),
            'risk_reward_ratio': risk_reward_ratio,
            'peak_price': position_data.get('peak_price', entry_price),
            'time_held_minutes': self._get_time_held(position_data)
        }
    
    def _get_time_held(self, position_data: Dict) -> float:
        """Calculate time held in minutes"""
        entry_time = position_data.get('entry_time')
        if entry_time:
            try:
                entry_dt = datetime.fromisoformat(entry_time)
                return (datetime.now() - entry_dt).total_seconds() / 60
            except:
                pass
        return 0

# Integration function for SL_watchdog.py
def get_vsr_momentum_stop_loss(position_data: Dict, current_price: float) -> float:
    """
    Function to be called by SL_watchdog.py
    Returns the stop loss price for VSR momentum positions
    """
    if position_data.get('metadata', {}).get('strategy') != 'VSR_MOMENTUM':
        return 0  # Not a VSR momentum position
    
    rules = VSRMomentumExitRules()
    stop_loss, reason = rules.calculate_stop_loss(position_data.get('metadata', {}), current_price)
    
    # Log the stop loss reason if needed
    if stop_loss > 0:
        print(f"VSR Momentum Stop: {reason} at ₹{stop_loss:.2f}")
    
    return stop_loss