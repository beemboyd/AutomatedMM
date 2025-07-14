#!/usr/bin/env python3
"""
Market Regime Smoother

This module implements smoothing logic to prevent frequent regime changes.
It uses multiple techniques:
1. Moving averages of long/short counts
2. Regime persistence requirements
3. Confidence thresholds
4. Volatility-based smoothing
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class RegimeSmoother:
    """Smooths market regime transitions to prevent whipsaws"""
    
    def __init__(self, history_file: str = None):
        """
        Initialize the regime smoother
        
        Args:
            history_file: Path to regime history file
        """
        self.history_file = history_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            'data', 'regime_history.json'
        )
        
        # Configuration parameters
        self.config = {
            'min_regime_duration_hours': 2.0,  # Minimum hours before allowing regime change
            'confidence_threshold': 0.7,       # Minimum confidence for regime change
            'ma_periods': 3,                   # Moving average periods for smoothing
            'extreme_ratio_threshold': 3.0,    # Ratio threshold for immediate change
            'volatility_window': 5,            # Number of scans to calculate volatility
            'max_volatility': 0.5              # Maximum allowed volatility in ratios
        }
        
        self.scan_history = []  # Store recent scan results
        self.load_scan_history()
        
    def load_scan_history(self):
        """Load recent scan history from files"""
        try:
            history_file = os.path.join(
                os.path.dirname(self.history_file), 
                'scan_history.json'
            )
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    self.scan_history = json.load(f)
                # Keep only recent history (last 24 hours)
                cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                self.scan_history = [
                    s for s in self.scan_history 
                    if s['timestamp'] > cutoff
                ]
        except Exception as e:
            logger.error(f"Error loading scan history: {e}")
            self.scan_history = []
    
    def save_scan_history(self):
        """Save scan history to file"""
        try:
            history_file = os.path.join(
                os.path.dirname(self.history_file), 
                'scan_history.json'
            )
            with open(history_file, 'w') as f:
                json.dump(self.scan_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving scan history: {e}")
    
    def add_scan_result(self, long_count: int, short_count: int, timestamp: str = None):
        """Add a new scan result to history"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
            
        self.scan_history.append({
            'timestamp': timestamp,
            'long_count': long_count,
            'short_count': short_count,
            'ratio': long_count / short_count if short_count > 0 else float('inf')
        })
        
        # Keep only recent history
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        self.scan_history = [
            s for s in self.scan_history 
            if s['timestamp'] > cutoff
        ]
        
        self.save_scan_history()
    
    def calculate_smoothed_counts(self, long_count: int, short_count: int) -> Tuple[float, float]:
        """
        Calculate smoothed long/short counts using moving average
        
        Returns:
            Tuple of (smoothed_long, smoothed_short)
        """
        # Add current scan to history
        self.add_scan_result(long_count, short_count)
        
        # Get recent scans for moving average
        recent_scans = self.scan_history[-self.config['ma_periods']:]
        
        if len(recent_scans) < 2:
            # Not enough history, return current values
            return float(long_count), float(short_count)
        
        # Calculate moving averages
        avg_long = np.mean([s['long_count'] for s in recent_scans])
        avg_short = np.mean([s['short_count'] for s in recent_scans])
        
        # Weight current values more heavily (exponential smoothing)
        weight_current = 0.5
        weight_history = 1 - weight_current
        
        smoothed_long = weight_current * long_count + weight_history * avg_long
        smoothed_short = weight_current * short_count + weight_history * avg_short
        
        return smoothed_long, smoothed_short
    
    def calculate_ratio_volatility(self) -> float:
        """Calculate volatility of recent ratios"""
        if len(self.scan_history) < self.config['volatility_window']:
            return 0.0
            
        recent_ratios = []
        for scan in self.scan_history[-self.config['volatility_window']:]:
            if scan['ratio'] != float('inf'):
                recent_ratios.append(scan['ratio'])
                
        if len(recent_ratios) < 2:
            return 0.0
            
        return np.std(recent_ratios) / (np.mean(recent_ratios) + 1e-6)
    
    def should_change_regime(self, 
                           current_regime: str, 
                           new_regime: str, 
                           confidence: float,
                           regime_duration_hours: float) -> Tuple[bool, str]:
        """
        Determine if regime should change based on smoothing rules
        
        Returns:
            Tuple of (should_change, reason)
        """
        # Rule 1: Minimum duration requirement
        if regime_duration_hours < self.config['min_regime_duration_hours']:
            return False, f"Current regime active for only {regime_duration_hours:.1f} hours (min: {self.config['min_regime_duration_hours']})"
        
        # Rule 2: Confidence threshold
        if confidence < self.config['confidence_threshold']:
            return False, f"Confidence {confidence:.1%} below threshold {self.config['confidence_threshold']:.1%}"
        
        # Rule 3: Check if it's a minor change
        minor_changes = [
            ('strong_uptrend', 'uptrend'),
            ('uptrend', 'strong_uptrend'),
            ('strong_downtrend', 'downtrend'),
            ('downtrend', 'strong_downtrend'),
            ('choppy_bullish', 'choppy'),
            ('choppy', 'choppy_bullish'),
            ('choppy_bearish', 'choppy'),
            ('choppy', 'choppy_bearish')
        ]
        
        if (current_regime, new_regime) in minor_changes or (new_regime, current_regime) in minor_changes:
            # Minor changes require higher confidence
            if confidence < 0.8:
                return False, f"Minor regime change requires 80% confidence (current: {confidence:.1%})"
        
        # Rule 4: Check volatility
        volatility = self.calculate_ratio_volatility()
        if volatility > self.config['max_volatility']:
            return False, f"Market too volatile (volatility: {volatility:.1%})"
        
        # Rule 5: Extreme ratio override
        if len(self.scan_history) > 0:
            current_ratio = self.scan_history[-1]['ratio']
            if current_ratio != float('inf') and (
                current_ratio > self.config['extreme_ratio_threshold'] or 
                current_ratio < 1/self.config['extreme_ratio_threshold']
            ):
                return True, f"Extreme ratio {current_ratio:.2f} triggers immediate change"
        
        return True, "All smoothing criteria met"
    
    def get_smoothing_metrics(self) -> Dict:
        """Get current smoothing metrics for display"""
        metrics = {
            'scan_history_length': len(self.scan_history),
            'volatility': self.calculate_ratio_volatility(),
            'recent_ratios': [],
            'smoothing_active': True
        }
        
        # Get recent ratios
        for scan in self.scan_history[-5:]:
            metrics['recent_ratios'].append({
                'timestamp': scan['timestamp'],
                'ratio': scan['ratio'] if scan['ratio'] != float('inf') else 'inf',
                'long': scan['long_count'],
                'short': scan['short_count']
            })
        
        return metrics


def test_smoother():
    """Test the regime smoother"""
    smoother = RegimeSmoother()
    
    # Test data: simulating market swings
    test_scans = [
        (29, 30),  # Neutral
        (6, 18),   # Strong bearish
        (21, 9),   # Strong bullish
        (15, 15),  # Back to neutral
        (25, 10),  # Strong bullish again
    ]
    
    print("Testing Regime Smoother")
    print("=" * 50)
    
    for i, (long, short) in enumerate(test_scans):
        print(f"\nScan {i+1}: Long={long}, Short={short}")
        
        # Get smoothed values
        smoothed_long, smoothed_short = smoother.calculate_smoothed_counts(long, short)
        
        raw_ratio = long / short if short > 0 else float('inf')
        smoothed_ratio = smoothed_long / smoothed_short if smoothed_short > 0 else float('inf')
        
        print(f"  Raw ratio: {raw_ratio:.2f}")
        print(f"  Smoothed: Long={smoothed_long:.1f}, Short={smoothed_short:.1f}")
        print(f"  Smoothed ratio: {smoothed_ratio:.2f}")
        print(f"  Volatility: {smoother.calculate_ratio_volatility():.2%}")
        
        # Test regime change logic
        should_change, reason = smoother.should_change_regime(
            'uptrend', 'strong_downtrend', 0.75, 3.0
        )
        print(f"  Should change regime: {should_change} ({reason})")


if __name__ == "__main__":
    test_smoother()