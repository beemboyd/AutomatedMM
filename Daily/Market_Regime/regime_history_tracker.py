#!/usr/bin/env python3
"""
Regime History Tracker
Maintains rolling 30-day history of regime changes and performance
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class RegimeHistoryTracker:
    """Track and analyze historical regime data"""
    
    def __init__(self, history_file: str = None):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # History file location
        if history_file:
            self.history_file = history_file
        else:
            self.history_file = os.path.join(self.data_dir, 'regime_history.json')
        
        # Performance metrics file
        self.metrics_file = os.path.join(self.data_dir, 'performance_metrics.json')
        
        # Load existing history
        self.history = self._load_history()
        self.performance_metrics = self._load_metrics()
        
        # Settings
        self.max_history_days = 30
        self.regime_sequence = deque(maxlen=100)  # Recent regime sequence
        
    def _load_history(self) -> List[Dict]:
        """Load historical regime data"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    # Ensure it's a list
                    if isinstance(data, list):
                        return data
                    else:
                        logger.warning("History file format incorrect, starting fresh")
                        return []
            except Exception as e:
                logger.error(f"Error loading history: {e}")
                return []
        return []
    
    def _load_metrics(self) -> Dict:
        """Load performance metrics"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    metrics = json.load(f)
                    
                # Convert regime_transitions back to defaultdict structure
                if 'regime_transitions' in metrics:
                    transitions = defaultdict(lambda: defaultdict(int))
                    for from_regime, to_regimes in metrics['regime_transitions'].items():
                        for to_regime, count in to_regimes.items():
                            transitions[from_regime][to_regime] = count
                    metrics['regime_transitions'] = transitions
                
                return metrics
            except Exception as e:
                logger.error(f"Error loading metrics: {e}")
                return self._initialize_metrics()
        return self._initialize_metrics()
    
    def _initialize_metrics(self) -> Dict:
        """Initialize performance metrics structure"""
        return {
            'regime_durations': {},
            'regime_transitions': defaultdict(lambda: defaultdict(int)),
            'regime_accuracy': {},
            'last_updated': None,
            'total_regimes_tracked': 0
        }
    
    def add_regime_entry(self, regime_data: Dict) -> None:
        """
        Add a new regime entry to history
        
        Args:
            regime_data: Dictionary containing:
                - regime: Current regime name
                - confidence: Confidence score
                - timestamp: ISO format timestamp
                - indicators: Market indicators
                - recommendations: Position recommendations
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in regime_data:
                regime_data['timestamp'] = datetime.now().isoformat()
            
            # Add to history
            self.history.append(regime_data)
            
            # Update regime sequence
            self.regime_sequence.append(regime_data['regime'])
            
            # Clean old entries
            self._clean_old_entries()
            
            # Update metrics
            self._update_metrics(regime_data)
            
            # Save to file
            self._save_history()
            self._save_metrics()
            
            logger.info(f"Added regime entry: {regime_data['regime']} "
                       f"(confidence: {regime_data.get('confidence', 0):.1%})")
            
        except Exception as e:
            logger.error(f"Error adding regime entry: {e}")
    
    def _clean_old_entries(self) -> None:
        """Remove entries older than max_history_days"""
        if not self.history:
            return
        
        cutoff_date = datetime.now() - timedelta(days=self.max_history_days)
        
        # Filter entries
        self.history = [
            entry for entry in self.history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_date
        ]
    
    def _update_metrics(self, new_entry: Dict) -> None:
        """Update performance metrics with new entry"""
        regime = new_entry['regime']
        timestamp = datetime.fromisoformat(new_entry['timestamp'])
        
        # Update total count
        self.performance_metrics['total_regimes_tracked'] += 1
        
        # Ensure regime_transitions is a defaultdict
        if not isinstance(self.performance_metrics.get('regime_transitions'), defaultdict):
            self.performance_metrics['regime_transitions'] = defaultdict(lambda: defaultdict(int))
        
        # Track regime transitions
        if len(self.history) > 1:
            prev_regime = self.history[-2]['regime']
            if prev_regime != regime:
                # Ensure nested structure exists
                if prev_regime not in self.performance_metrics['regime_transitions']:
                    self.performance_metrics['regime_transitions'][prev_regime] = defaultdict(int)
                self.performance_metrics['regime_transitions'][prev_regime][regime] += 1
        
        # Update last updated timestamp
        self.performance_metrics['last_updated'] = datetime.now().isoformat()
    
    def _save_history(self) -> None:
        """Save history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def _save_metrics(self) -> None:
        """Save metrics to file"""
        try:
            # Convert defaultdict to regular dict for JSON serialization
            metrics_copy = self.performance_metrics.copy()
            metrics_copy['regime_transitions'] = dict(metrics_copy['regime_transitions'])
            for key in metrics_copy['regime_transitions']:
                metrics_copy['regime_transitions'][key] = dict(
                    metrics_copy['regime_transitions'][key]
                )
            
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics_copy, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def get_regime_duration(self, current_regime: str = None) -> float:
        """Get duration of current regime in hours"""
        if not self.history:
            return 0.0
        
        if current_regime is None:
            current_regime = self.history[-1]['regime']
        
        # Find when current regime started
        regime_start = None
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i]['regime'] != current_regime:
                if i < len(self.history) - 1:
                    regime_start = datetime.fromisoformat(self.history[i + 1]['timestamp'])
                break
            elif i == 0:
                regime_start = datetime.fromisoformat(self.history[0]['timestamp'])
        
        if regime_start:
            duration = datetime.now() - regime_start
            return duration.total_seconds() / 3600  # Convert to hours
        
        return 0.0
    
    def get_regime_stability(self, lookback_hours: int = 24) -> float:
        """
        Calculate regime stability over lookback period
        
        Returns:
            Stability score between 0 and 1 (1 = perfectly stable)
        """
        if not self.history:
            return 0.5
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        recent_entries = [
            entry for entry in self.history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]
        
        if len(recent_entries) < 2:
            return 1.0  # Not enough data, assume stable
        
        # Count regime changes
        changes = 0
        for i in range(1, len(recent_entries)):
            if recent_entries[i]['regime'] != recent_entries[i-1]['regime']:
                changes += 1
        
        # Calculate stability
        max_changes = len(recent_entries) - 1
        stability = 1.0 - (changes / max_changes)
        
        return stability
    
    def get_regime_distribution(self, days: int = 7) -> Dict[str, float]:
        """Get distribution of regimes over specified days"""
        if not self.history:
            return {}
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_entries = [
            entry for entry in self.history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_date
        ]
        
        if not recent_entries:
            return {}
        
        # Count occurrences
        regime_counts = defaultdict(int)
        for entry in recent_entries:
            regime_counts[entry['regime']] += 1
        
        # Convert to percentages
        total = len(recent_entries)
        distribution = {
            regime: count / total
            for regime, count in regime_counts.items()
        }
        
        return distribution
    
    def get_transition_probabilities(self) -> Dict[str, Dict[str, float]]:
        """Calculate regime transition probabilities"""
        transitions = self.performance_metrics.get('regime_transitions', {})
        
        if not transitions:
            return {}
        
        # Calculate probabilities
        probabilities = {}
        for from_regime, to_regimes in transitions.items():
            total_transitions = sum(to_regimes.values())
            if total_transitions > 0:
                probabilities[from_regime] = {
                    to_regime: count / total_transitions
                    for to_regime, count in to_regimes.items()
                }
        
        return probabilities
    
    def get_recent_history(self, hours: int = 24) -> List[Dict]:
        """Get regime history for specified hours"""
        if not self.history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            entry for entry in self.history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]
    
    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary"""
        summary = {
            'current_regime': None,
            'regime_duration_hours': 0.0,
            'stability_24h': 0.0,
            'regime_distribution_7d': {},
            'transition_probabilities': {},
            'total_tracked': self.performance_metrics.get('total_regimes_tracked', 0),
            'last_updated': self.performance_metrics.get('last_updated')
        }
        
        if self.history:
            current_regime = self.history[-1]['regime']
            summary['current_regime'] = current_regime
            summary['regime_duration_hours'] = self.get_regime_duration(current_regime)
            summary['stability_24h'] = self.get_regime_stability(24)
            summary['regime_distribution_7d'] = self.get_regime_distribution(7)
            summary['transition_probabilities'] = self.get_transition_probabilities()
        
        return summary


def test_history_tracker():
    """Test the history tracker functionality"""
    # Create test instance
    tracker = RegimeHistoryTracker()
    
    # Add test entries
    test_regimes = [
        ('uptrend', 0.7),
        ('uptrend', 0.75),
        ('choppy_bullish', 0.5),
        ('choppy', 0.4),
        ('choppy_bearish', 0.45),
        ('downtrend', 0.6)
    ]
    
    base_time = datetime.now() - timedelta(hours=6)
    
    for i, (regime, confidence) in enumerate(test_regimes):
        timestamp = (base_time + timedelta(hours=i)).isoformat()
        tracker.add_regime_entry({
            'regime': regime,
            'confidence': confidence,
            'timestamp': timestamp,
            'indicators': {'ratio': 1.5 - (i * 0.2)}
        })
    
    # Test various methods
    print("History Tracker Test Results:")
    print("=" * 50)
    
    summary = tracker.get_performance_summary()
    print(f"\nCurrent Regime: {summary['current_regime']}")
    print(f"Duration: {summary['regime_duration_hours']:.1f} hours")
    print(f"24h Stability: {summary['stability_24h']:.1%}")
    
    print("\n7-Day Distribution:")
    for regime, pct in summary['regime_distribution_7d'].items():
        print(f"  {regime}: {pct:.1%}")
    
    print("\nTransition Probabilities:")
    for from_regime, transitions in summary['transition_probabilities'].items():
        print(f"  From {from_regime}:")
        for to_regime, prob in transitions.items():
            print(f"    -> {to_regime}: {prob:.1%}")


if __name__ == "__main__":
    test_history_tracker()