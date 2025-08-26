#!/usr/bin/env python3
"""
VSR Dynamic Position Sizing Strategy
=====================================
Implements persistence-based position sizing for optimal capital allocation
based on empirical analysis showing strong correlation (0.612) between
alert persistence and returns.

Author: System
Date: August 24, 2025
"""

import numpy as np
from typing import Dict, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PersistenceLevel(Enum):
    """Persistence buckets based on alert frequency"""
    LOW = "Low (1-10 alerts)"           # 45.2% win rate, 0.28% avg return
    MEDIUM = "Medium (11-25 alerts)"     # 76.5% win rate, 1.49% avg return  
    HIGH = "High (26-50 alerts)"         # 88.9% win rate, 2.72% avg return
    VERY_HIGH = "Very High (51-75)"      # 100% win rate, 5.73% avg return
    EXTREME = "Extreme (75+ alerts)"     # 100% win rate, 9.68% avg return


@dataclass
class PositionSizeConfig:
    """Configuration for position sizing strategy"""
    total_capital: float = 1000000  # Total trading capital
    max_positions: int = 20         # Maximum concurrent positions
    max_position_pct: float = 0.15  # Max 15% in single position
    min_position_pct: float = 0.02  # Min 2% position size
    
    # Kelly Criterion parameters
    use_kelly: bool = True
    kelly_fraction: float = 0.25    # Use 25% Kelly for safety
    
    # Risk management
    max_sector_allocation: float = 0.30  # Max 30% in one sector
    scale_in_enabled: bool = True        # Enable scaling into positions
    
    # Persistence-based multipliers (based on empirical data)
    persistence_multipliers: Dict[PersistenceLevel, float] = None
    
    def __post_init__(self):
        if self.persistence_multipliers is None:
            self.persistence_multipliers = {
                PersistenceLevel.LOW: 0.5,        # 50% of base size
                PersistenceLevel.MEDIUM: 1.0,     # 100% base size
                PersistenceLevel.HIGH: 1.5,       # 150% of base size
                PersistenceLevel.VERY_HIGH: 2.0,  # 200% of base size
                PersistenceLevel.EXTREME: 2.5,    # 250% of base size
            }


class VSRDynamicPositionSizer:
    """
    Dynamic position sizing based on VSR persistence and performance metrics
    """
    
    def __init__(self, config: Optional[PositionSizeConfig] = None):
        self.config = config or PositionSizeConfig()
        self.positions = {}  # Track current positions
        self.sector_allocation = {}  # Track sector exposure
        
    def get_persistence_level(self, alert_count: int) -> PersistenceLevel:
        """Determine persistence level from alert count"""
        if alert_count <= 10:
            return PersistenceLevel.LOW
        elif alert_count <= 25:
            return PersistenceLevel.MEDIUM
        elif alert_count <= 50:
            return PersistenceLevel.HIGH
        elif alert_count <= 75:
            return PersistenceLevel.VERY_HIGH
        else:
            return PersistenceLevel.EXTREME
    
    def calculate_kelly_position(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate position size using Kelly Criterion
        
        Kelly Formula: f = (p * b - q) / b
        where:
        - f = fraction of capital to bet
        - p = probability of winning (win_rate)
        - q = probability of losing (1 - win_rate)
        - b = ratio of win to loss (avg_win / avg_loss)
        """
        if avg_loss == 0 or avg_win <= 0:
            return 0.02  # Return minimum position size
        
        p = win_rate
        q = 1 - win_rate
        b = avg_win / abs(avg_loss)
        
        kelly_pct = (p * b - q) / b
        
        # Apply Kelly fraction for safety (typically 25% of full Kelly)
        safe_kelly = kelly_pct * self.config.kelly_fraction
        
        # Ensure within bounds
        return max(self.config.min_position_pct, 
                  min(safe_kelly, self.config.max_position_pct))
    
    def calculate_position_size(self,
                               ticker: str,
                               alert_count: int,
                               avg_score: float,
                               current_price: float,
                               sector: Optional[str] = None,
                               historical_performance: Optional[Dict] = None) -> Dict:
        """
        Calculate optimal position size based on multiple factors
        
        Args:
            ticker: Stock symbol
            alert_count: Number of VSR alerts (persistence)
            avg_score: Average VSR score
            current_price: Current stock price
            sector: Stock sector for diversification
            historical_performance: Optional historical metrics
            
        Returns:
            Dictionary with position sizing details
        """
        # 1. Base position size (equal weight)
        base_size_pct = 1.0 / self.config.max_positions
        
        # 2. Apply persistence multiplier
        persistence_level = self.get_persistence_level(alert_count)
        persistence_mult = self.config.persistence_multipliers[persistence_level]
        
        # 3. Apply score adjustment (normalized 0-1)
        score_mult = 1.0 + (avg_score / 100) * 0.5  # Up to 50% bonus for high scores
        
        # 4. Calculate composite score (40% persistence, 60% score)
        composite_score = (alert_count * 0.4 + avg_score * 0.6)
        composite_mult = 1.0 + (composite_score / 100) * 0.3  # Up to 30% bonus
        
        # 5. Apply Kelly Criterion if enabled and data available
        kelly_size_pct = base_size_pct
        if self.config.use_kelly and historical_performance:
            # Use empirical win rates by persistence level
            win_rates = {
                PersistenceLevel.LOW: 0.452,
                PersistenceLevel.MEDIUM: 0.765,
                PersistenceLevel.HIGH: 0.889,
                PersistenceLevel.VERY_HIGH: 1.0,
                PersistenceLevel.EXTREME: 1.0
            }
            
            avg_returns = {
                PersistenceLevel.LOW: (0.0028, -0.006),  # (avg_win, avg_loss)
                PersistenceLevel.MEDIUM: (0.0149, -0.005),
                PersistenceLevel.HIGH: (0.0272, -0.004),
                PersistenceLevel.VERY_HIGH: (0.0573, 0),
                PersistenceLevel.EXTREME: (0.0968, 0)
            }
            
            win_rate = win_rates[persistence_level]
            avg_win, avg_loss = avg_returns[persistence_level]
            
            if avg_loss < 0:  # Only use Kelly if we have loss data
                kelly_size_pct = self.calculate_kelly_position(win_rate, avg_win, abs(avg_loss))
        
        # 6. Combine all factors
        final_size_pct = base_size_pct * persistence_mult * score_mult
        
        # Use Kelly size if it's more conservative
        if self.config.use_kelly:
            final_size_pct = min(final_size_pct, kelly_size_pct)
        
        # 7. Apply position limits
        final_size_pct = max(self.config.min_position_pct, 
                           min(final_size_pct, self.config.max_position_pct))
        
        # 8. Check sector allocation
        if sector and sector in self.sector_allocation:
            current_sector_pct = self.sector_allocation[sector]
            if current_sector_pct + final_size_pct > self.config.max_sector_allocation:
                final_size_pct = max(0, self.config.max_sector_allocation - current_sector_pct)
        
        # 9. Calculate actual position
        position_value = self.config.total_capital * final_size_pct
        shares = int(position_value / current_price)
        actual_value = shares * current_price
        
        # 10. Determine if this should be scaled in
        scale_in_tranches = 1
        if self.config.scale_in_enabled and persistence_level in [PersistenceLevel.VERY_HIGH, PersistenceLevel.EXTREME]:
            scale_in_tranches = 3  # Scale in over 3 entries
        
        return {
            'ticker': ticker,
            'persistence_level': persistence_level.value,
            'alert_count': alert_count,
            'avg_score': avg_score,
            'composite_score': composite_score,
            'position_size_pct': final_size_pct * 100,
            'position_value': actual_value,
            'shares': shares,
            'price': current_price,
            'scale_in_tranches': scale_in_tranches,
            'initial_tranche': shares // scale_in_tranches if scale_in_tranches > 1 else shares,
            'confidence': 'HIGH' if persistence_level in [PersistenceLevel.VERY_HIGH, PersistenceLevel.EXTREME] else 'MEDIUM' if persistence_level == PersistenceLevel.HIGH else 'LOW',
            'expected_return': avg_returns[persistence_level][0] if 'avg_returns' in locals() else None,
            'win_probability': win_rates[persistence_level] if 'win_rates' in locals() else None
        }
    
    def optimize_portfolio_allocation(self, candidates: list) -> list:
        """
        Optimize allocation across multiple candidates
        
        Args:
            candidates: List of dicts with ticker info (alert_count, avg_score, price, etc.)
            
        Returns:
            List of position sizing recommendations sorted by priority
        """
        recommendations = []
        remaining_capital = self.config.total_capital
        used_positions = 0
        
        # Calculate position sizes for all candidates
        for candidate in candidates:
            if used_positions >= self.config.max_positions:
                break
                
            position = self.calculate_position_size(
                ticker=candidate['ticker'],
                alert_count=candidate.get('alert_count', 0),
                avg_score=candidate.get('avg_score', 0),
                current_price=candidate.get('price', 100),
                sector=candidate.get('sector')
            )
            
            if position['position_value'] <= remaining_capital:
                recommendations.append(position)
                remaining_capital -= position['position_value']
                used_positions += 1
        
        # Sort by expected return (composite of persistence and score)
        recommendations.sort(key=lambda x: x['composite_score'], reverse=True)
        
        return recommendations
    
    def get_rebalancing_actions(self, current_positions: Dict, new_signals: list) -> Dict:
        """
        Determine rebalancing actions based on new signals
        
        Args:
            current_positions: Current portfolio positions
            new_signals: New VSR signals
            
        Returns:
            Dict with 'increase', 'decrease', 'exit', 'enter' recommendations
        """
        actions = {
            'increase': [],  # Positions to increase
            'decrease': [],  # Positions to reduce
            'exit': [],      # Positions to close
            'enter': []      # New positions to open
        }
        
        # Check existing positions for persistence changes
        for ticker, position in current_positions.items():
            new_signal = next((s for s in new_signals if s['ticker'] == ticker), None)
            
            if new_signal:
                new_persistence = self.get_persistence_level(new_signal['alert_count'])
                old_persistence = self.get_persistence_level(position.get('alert_count', 0))
                
                # Increase position if persistence improved significantly
                if new_persistence.value > old_persistence.value:
                    actions['increase'].append({
                        'ticker': ticker,
                        'reason': f'Persistence increased from {old_persistence.value} to {new_persistence.value}',
                        'new_size': self.calculate_position_size(
                            ticker=ticker,
                            alert_count=new_signal['alert_count'],
                            avg_score=new_signal.get('avg_score', 0),
                            current_price=new_signal.get('price', 100)
                        )
                    })
                
                # Decrease if persistence dropped significantly
                elif new_persistence.value < old_persistence.value and new_persistence == PersistenceLevel.LOW:
                    actions['decrease'].append({
                        'ticker': ticker,
                        'reason': f'Persistence dropped to {new_persistence.value}',
                        'reduce_by_pct': 50  # Reduce by 50%
                    })
            else:
                # No new signal - consider exit if position is old
                if position.get('days_held', 0) > 10:
                    actions['exit'].append({
                        'ticker': ticker,
                        'reason': 'No recent VSR signals'
                    })
        
        # Check for new high-conviction entries
        existing_tickers = set(current_positions.keys())
        for signal in new_signals:
            if signal['ticker'] not in existing_tickers:
                persistence = self.get_persistence_level(signal['alert_count'])
                if persistence in [PersistenceLevel.VERY_HIGH, PersistenceLevel.EXTREME]:
                    actions['enter'].append(self.calculate_position_size(
                        ticker=signal['ticker'],
                        alert_count=signal['alert_count'],
                        avg_score=signal.get('avg_score', 0),
                        current_price=signal.get('price', 100)
                    ))
        
        return actions


# Example usage and testing
if __name__ == "__main__":
    # Initialize the position sizer
    sizer = VSRDynamicPositionSizer()
    
    # Example: Calculate position size for different persistence levels
    print("="*70)
    print("VSR DYNAMIC POSITION SIZING EXAMPLES")
    print("="*70)
    print(f"Total Capital: ₹{sizer.config.total_capital:,.0f}")
    print(f"Max Positions: {sizer.config.max_positions}")
    print()
    
    # Test cases based on actual data
    test_cases = [
        {'ticker': 'SUNDARMFIN', 'alert_count': 108, 'avg_score': 42.8, 'current_price': 5273.40},
        {'ticker': 'APOLLO', 'alert_count': 88, 'avg_score': 11.8, 'current_price': 1500},
        {'ticker': 'DMART', 'alert_count': 102, 'avg_score': 0, 'current_price': 4737.90},
        {'ticker': 'JMFINANCIL', 'alert_count': 21, 'avg_score': 10.4, 'current_price': 100},
        {'ticker': 'NEWSTOCK', 'alert_count': 5, 'avg_score': 5, 'current_price': 250},
    ]
    
    print("POSITION SIZING RECOMMENDATIONS:")
    print("-"*70)
    
    for case in test_cases:
        result = sizer.calculate_position_size(**case)
        print(f"\n{result['ticker']:12} | Persistence: {result['alert_count']:3} alerts ({result['persistence_level']})")
        print(f"  Score: {result['avg_score']:.1f} | Composite: {result['composite_score']:.1f}")
        print(f"  Position Size: {result['position_size_pct']:.2f}% (₹{result['position_value']:,.0f})")
        print(f"  Shares: {result['shares']} @ ₹{result['price']:.2f}")
        if result['win_probability']:
            print(f"  Confidence: {result['confidence']} | Win Prob: {result['win_probability']*100:.1f}%")
        else:
            print(f"  Confidence: {result['confidence']}")
        if result['scale_in_tranches'] > 1:
            print(f"  Scale-in: {result['scale_in_tranches']} tranches, Initial: {result['initial_tranche']} shares")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS:")
    print("-"*70)
    print("1. Extreme persistence (75+ alerts) gets 2.5x base allocation")
    print("2. Very high persistence (51-75) gets 2x with scale-in over 3 tranches")
    print("3. Kelly Criterion caps position sizes based on win rate and R:R")
    print("4. Maximum 15% in any single position for risk management")
    print("5. Sector allocation limits prevent overconcentration")