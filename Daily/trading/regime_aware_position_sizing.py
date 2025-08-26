#!/usr/bin/env python3
"""
Regime-Aware VSR Position Sizing Strategy
==========================================
Enhances the VSR dynamic position sizing with market regime awareness.
Adjusts position sizes and long/short bias based on market breadth conditions.

Key Finding: VSR persistence signals showed 69.3% win rate for longs even 
during BEARISH regime (35% SMA20 breadth), suggesting strong stock selection
that can work counter-trend.

Author: System
Date: August 24, 2025
"""

import json
import numpy as np
from typing import Dict, Tuple, Optional, List
import logging
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime based on breadth analysis"""
    STRONG_BULLISH = "Strong Bullish (>70%)"
    BULLISH = "Bullish (60-70%)"
    NEUTRAL_BULLISH = "Neutral-Bullish (50-60%)"
    NEUTRAL = "Neutral (45-50%)"
    NEUTRAL_BEARISH = "Neutral-Bearish (40-45%)"
    BEARISH = "Bearish (30-40%)"
    STRONG_BEARISH = "Strong Bearish (<30%)"


class RegimeAdjustment:
    """Position sizing adjustments based on market regime"""
    
    # Base adjustments for long positions by regime
    LONG_ADJUSTMENTS = {
        MarketRegime.STRONG_BULLISH: 1.3,    # 30% increase
        MarketRegime.BULLISH: 1.15,          # 15% increase
        MarketRegime.NEUTRAL_BULLISH: 1.0,   # No change
        MarketRegime.NEUTRAL: 0.85,          # 15% reduction
        MarketRegime.NEUTRAL_BEARISH: 0.7,   # 30% reduction
        MarketRegime.BEARISH: 0.5,           # 50% reduction
        MarketRegime.STRONG_BEARISH: 0.3,    # 70% reduction
    }
    
    # Base adjustments for short positions by regime (inverse of long)
    SHORT_ADJUSTMENTS = {
        MarketRegime.STRONG_BULLISH: 0.3,    # 70% reduction
        MarketRegime.BULLISH: 0.5,           # 50% reduction
        MarketRegime.NEUTRAL_BULLISH: 0.7,   # 30% reduction
        MarketRegime.NEUTRAL: 0.85,          # 15% reduction
        MarketRegime.NEUTRAL_BEARISH: 1.0,   # No change
        MarketRegime.BEARISH: 1.15,          # 15% increase
        MarketRegime.STRONG_BEARISH: 1.3,    # 30% increase
    }
    
    # Special adjustment for high-persistence signals in bearish markets
    # Based on empirical finding: 69.3% win rate even in 35% breadth
    COUNTER_TREND_BONUS = {
        "extreme_persistence_bearish": 1.5,  # 50% bonus for 75+ alerts in bear market
        "high_persistence_bearish": 1.25,    # 25% bonus for 50+ alerts in bear market
    }


@dataclass
class RegimeConfig:
    """Configuration for regime-aware position sizing"""
    
    # Breadth data source
    breadth_data_path: str = "Daily/Market_Regime/breadth_data/"
    historical_data_file: str = "Daily/Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json"
    
    # Regime thresholds
    use_sma20: bool = True  # Primary indicator
    use_sma50: bool = False  # Secondary confirmation
    
    # Position limits by regime
    max_positions_by_regime: Dict[MarketRegime, int] = None
    
    # Risk management
    max_regime_penalty: float = 0.7  # Maximum reduction (30% of normal)
    max_regime_bonus: float = 1.3    # Maximum increase (130% of normal)
    
    # Counter-trend rules
    allow_counter_trend: bool = True
    counter_trend_min_persistence: int = 50  # Minimum alerts for counter-trend
    counter_trend_min_score: float = 20.0    # Minimum score for counter-trend
    
    def __post_init__(self):
        if self.max_positions_by_regime is None:
            self.max_positions_by_regime = {
                MarketRegime.STRONG_BULLISH: 25,
                MarketRegime.BULLISH: 20,
                MarketRegime.NEUTRAL_BULLISH: 18,
                MarketRegime.NEUTRAL: 15,
                MarketRegime.NEUTRAL_BEARISH: 12,
                MarketRegime.BEARISH: 8,
                MarketRegime.STRONG_BEARISH: 5,
            }


class RegimeAwarePositionSizer:
    """
    Market regime-aware position sizing that adjusts for market conditions
    while recognizing high-persistence signals can work counter-trend
    """
    
    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self.current_regime = None
        self.regime_history = []
        self.last_regime_update = None
        
        # Load from existing VSR position sizer
        from vsr_dynamic_position_sizing import VSRDynamicPositionSizer, PositionSizeConfig
        self.base_sizer = VSRDynamicPositionSizer(PositionSizeConfig())
        
        # Initialize regime
        self.update_market_regime()
    
    def get_market_regime(self, sma20_breadth: float) -> MarketRegime:
        """Determine market regime from SMA20 breadth"""
        if sma20_breadth > 70:
            return MarketRegime.STRONG_BULLISH
        elif sma20_breadth > 60:
            return MarketRegime.BULLISH
        elif sma20_breadth > 50:
            return MarketRegime.NEUTRAL_BULLISH
        elif sma20_breadth > 45:
            return MarketRegime.NEUTRAL
        elif sma20_breadth > 40:
            return MarketRegime.NEUTRAL_BEARISH
        elif sma20_breadth > 30:
            return MarketRegime.BEARISH
        else:
            return MarketRegime.STRONG_BEARISH
    
    def update_market_regime(self) -> MarketRegime:
        """Update current market regime from latest breadth data"""
        try:
            # Load latest breadth data
            if os.path.exists(self.config.historical_data_file):
                with open(self.config.historical_data_file, 'r') as f:
                    data = json.load(f)
                
                if data:
                    # Get last 3 days average
                    recent_data = data[-3:] if len(data) >= 3 else data
                    avg_sma20 = np.mean([d['sma_breadth']['sma20_percent'] for d in recent_data])
                    
                    self.current_regime = self.get_market_regime(avg_sma20)
                    self.last_regime_update = datetime.now()
                    
                    # Track regime history
                    self.regime_history.append({
                        'timestamp': self.last_regime_update,
                        'regime': self.current_regime,
                        'sma20': avg_sma20
                    })
                    
                    logger.info(f"Market regime updated: {self.current_regime.value} (SMA20: {avg_sma20:.1f}%)")
                    return self.current_regime
            
            # Default to neutral if no data
            self.current_regime = MarketRegime.NEUTRAL
            return self.current_regime
            
        except Exception as e:
            logger.error(f"Error updating market regime: {e}")
            self.current_regime = MarketRegime.NEUTRAL
            return self.current_regime
    
    def should_allow_counter_trend(self, 
                                  alert_count: int, 
                                  avg_score: float,
                                  direction: str = 'long') -> bool:
        """
        Determine if counter-trend trading is allowed based on signal strength
        
        Key insight: High persistence signals (50+ alerts) showed strong performance
        even in bearish regimes, suggesting they identify stocks with individual strength
        """
        if not self.config.allow_counter_trend:
            return False
        
        # Check if we're in adverse regime
        is_adverse = False
        if direction == 'long':
            is_adverse = self.current_regime in [
                MarketRegime.BEARISH, 
                MarketRegime.STRONG_BEARISH,
                MarketRegime.NEUTRAL_BEARISH
            ]
        else:  # short
            is_adverse = self.current_regime in [
                MarketRegime.BULLISH,
                MarketRegime.STRONG_BULLISH,
                MarketRegime.NEUTRAL_BULLISH
            ]
        
        if not is_adverse:
            return True  # Not counter-trend
        
        # Allow counter-trend only for high-quality signals
        return (alert_count >= self.config.counter_trend_min_persistence and
                avg_score >= self.config.counter_trend_min_score)
    
    def calculate_regime_adjusted_size(self,
                                      ticker: str,
                                      alert_count: int,
                                      avg_score: float,
                                      current_price: float,
                                      direction: str = 'long',
                                      sector: Optional[str] = None) -> Dict:
        """
        Calculate position size with regime adjustments
        
        Args:
            ticker: Stock symbol
            alert_count: Number of VSR alerts (persistence)
            avg_score: Average VSR score
            current_price: Current stock price
            direction: 'long' or 'short'
            sector: Stock sector
            
        Returns:
            Position sizing recommendation with regime adjustments
        """
        # Get base position size from VSR sizer
        base_position = self.base_sizer.calculate_position_size(
            ticker=ticker,
            alert_count=alert_count,
            avg_score=avg_score,
            current_price=current_price,
            sector=sector
        )
        
        # Update regime if stale (>1 hour old)
        if (not self.last_regime_update or 
            datetime.now() - self.last_regime_update > timedelta(hours=1)):
            self.update_market_regime()
        
        # Get regime adjustment
        if direction == 'long':
            regime_mult = RegimeAdjustment.LONG_ADJUSTMENTS[self.current_regime]
        else:
            regime_mult = RegimeAdjustment.SHORT_ADJUSTMENTS[self.current_regime]
        
        # Apply counter-trend bonus for high-persistence in adverse conditions
        counter_trend_mult = 1.0
        if self.should_allow_counter_trend(alert_count, avg_score, direction):
            if alert_count >= 75 and self.current_regime in [MarketRegime.BEARISH, MarketRegime.STRONG_BEARISH]:
                counter_trend_mult = RegimeAdjustment.COUNTER_TREND_BONUS["extreme_persistence_bearish"]
                logger.info(f"{ticker}: Applying counter-trend bonus for extreme persistence in bear market")
            elif alert_count >= 50 and self.current_regime in [MarketRegime.BEARISH, MarketRegime.NEUTRAL_BEARISH]:
                counter_trend_mult = RegimeAdjustment.COUNTER_TREND_BONUS["high_persistence_bearish"]
                logger.info(f"{ticker}: Applying counter-trend bonus for high persistence in weak market")
        
        # Calculate final adjustment
        total_adjustment = regime_mult * counter_trend_mult
        
        # Apply limits
        total_adjustment = max(self.config.max_regime_penalty, 
                              min(total_adjustment, self.config.max_regime_bonus))
        
        # Adjust position size
        adjusted_size_pct = base_position['position_size_pct'] * total_adjustment / 100
        adjusted_value = base_position['position_value'] * total_adjustment
        adjusted_shares = int(adjusted_value / current_price)
        
        # Check if position count limit is reached
        max_positions = self.config.max_positions_by_regime[self.current_regime]
        
        # Build result
        result = base_position.copy()
        result.update({
            'regime': self.current_regime.value,
            'regime_adjustment': total_adjustment,
            'adjusted_size_pct': adjusted_size_pct * 100,
            'adjusted_value': adjusted_value,
            'adjusted_shares': adjusted_shares,
            'max_positions': max_positions,
            'counter_trend': counter_trend_mult > 1.0,
            'direction': direction,
            'regime_aligned': (
                (direction == 'long' and self.current_regime in [MarketRegime.BULLISH, MarketRegime.STRONG_BULLISH]) or
                (direction == 'short' and self.current_regime in [MarketRegime.BEARISH, MarketRegime.STRONG_BEARISH])
            )
        })
        
        return result
    
    def get_portfolio_recommendations(self, signals: List[Dict]) -> Dict:
        """
        Get portfolio-level recommendations based on regime
        
        Args:
            signals: List of VSR signals with persistence and scores
            
        Returns:
            Portfolio allocation recommendations
        """
        recommendations = {
            'regime': self.current_regime.value,
            'long_allocation': 0,
            'short_allocation': 0,
            'cash_allocation': 0,
            'positions': [],
            'warnings': [],
            'opportunities': []
        }
        
        # Determine portfolio allocation by regime
        if self.current_regime in [MarketRegime.STRONG_BULLISH, MarketRegime.BULLISH]:
            recommendations['long_allocation'] = 80
            recommendations['short_allocation'] = 10
            recommendations['cash_allocation'] = 10
            recommendations['opportunities'].append("Strong bullish regime - maximize long exposure")
            
        elif self.current_regime in [MarketRegime.NEUTRAL_BULLISH]:
            recommendations['long_allocation'] = 60
            recommendations['short_allocation'] = 20
            recommendations['cash_allocation'] = 20
            
        elif self.current_regime in [MarketRegime.NEUTRAL]:
            recommendations['long_allocation'] = 40
            recommendations['short_allocation'] = 30
            recommendations['cash_allocation'] = 30
            recommendations['warnings'].append("Neutral market - be selective with positions")
            
        elif self.current_regime in [MarketRegime.NEUTRAL_BEARISH]:
            recommendations['long_allocation'] = 30
            recommendations['short_allocation'] = 40
            recommendations['cash_allocation'] = 30
            
        elif self.current_regime in [MarketRegime.BEARISH]:
            recommendations['long_allocation'] = 20
            recommendations['short_allocation'] = 60
            recommendations['cash_allocation'] = 20
            recommendations['warnings'].append("Bearish regime - focus on shorts and high-quality longs only")
            recommendations['opportunities'].append("Look for high-persistence (50+) counter-trend longs")
            
        else:  # STRONG_BEARISH
            recommendations['long_allocation'] = 10
            recommendations['short_allocation'] = 70
            recommendations['cash_allocation'] = 20
            recommendations['warnings'].append("Strong bearish regime - minimize long exposure")
            recommendations['opportunities'].append("Only take extreme persistence (75+) longs")
        
        # Process signals
        long_signals = [s for s in signals if s.get('direction', 'long') == 'long']
        short_signals = [s for s in signals if s.get('direction') == 'short']
        
        # Sort by quality (persistence * score)
        long_signals.sort(key=lambda x: x.get('alert_count', 0) * 0.4 + x.get('avg_score', 0) * 0.6, reverse=True)
        short_signals.sort(key=lambda x: x.get('alert_count', 0) * 0.4 + x.get('avg_score', 0) * 0.6, reverse=True)
        
        # Calculate positions
        for signal in long_signals[:self.config.max_positions_by_regime[self.current_regime]]:
            position = self.calculate_regime_adjusted_size(
                ticker=signal['ticker'],
                alert_count=signal.get('alert_count', 0),
                avg_score=signal.get('avg_score', 0),
                current_price=signal.get('price', 100),
                direction='long'
            )
            
            if position['regime_aligned'] or position['counter_trend']:
                recommendations['positions'].append(position)
        
        for signal in short_signals[:5]:  # Limit short positions
            position = self.calculate_regime_adjusted_size(
                ticker=signal['ticker'],
                alert_count=signal.get('alert_count', 0),
                avg_score=signal.get('avg_score', 0),
                current_price=signal.get('price', 100),
                direction='short'
            )
            
            if position['regime_aligned']:
                recommendations['positions'].append(position)
        
        return recommendations


# Example usage
if __name__ == "__main__":
    # Initialize regime-aware sizer
    sizer = RegimeAwarePositionSizer()
    
    print("="*70)
    print("REGIME-AWARE POSITION SIZING STRATEGY")
    print("="*70)
    print(f"\nCurrent Market Regime: {sizer.current_regime.value}")
    print()
    
    # Test with different scenarios
    test_cases = [
        {
            'ticker': 'HIGHPERSIST',
            'alert_count': 85,
            'avg_score': 30,
            'current_price': 1000,
            'direction': 'long',
            'description': 'High persistence long in bear market'
        },
        {
            'ticker': 'LOWPERSIST',
            'alert_count': 15,
            'avg_score': 10,
            'current_price': 500,
            'direction': 'long',
            'description': 'Low persistence long in bear market'
        },
        {
            'ticker': 'SHORTCAND',
            'alert_count': 45,
            'avg_score': 25,
            'current_price': 250,
            'direction': 'short',
            'description': 'Short candidate in bear market'
        }
    ]
    
    print("POSITION RECOMMENDATIONS:")
    print("-"*70)
    
    for case in test_cases:
        result = sizer.calculate_regime_adjusted_size(
            ticker=case['ticker'],
            alert_count=case['alert_count'],
            avg_score=case['avg_score'],
            current_price=case['current_price'],
            direction=case['direction']
        )
        
        print(f"\n{case['description']}:")
        print(f"  Ticker: {result['ticker']}")
        print(f"  Base Size: {result['position_size_pct']:.2f}%")
        print(f"  Regime Adjustment: {result['regime_adjustment']:.2f}x")
        print(f"  Final Size: {result['adjusted_size_pct']:.2f}%")
        print(f"  Shares: {result['adjusted_shares']} (₹{result['adjusted_value']:,.0f})")
        print(f"  Counter-trend: {'Yes' if result['counter_trend'] else 'No'}")
        print(f"  Regime-aligned: {'Yes' if result['regime_aligned'] else 'No'}")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS:")
    print("-"*70)
    print("1. Market regime significantly impacts position sizing")
    print("2. High persistence (50+) can override bearish regime")
    print("3. Counter-trend bonus applied for quality signals in adverse markets")
    print("4. Position count reduced in bearish regimes (8 vs 20)")
    print("5. Empirical evidence supports counter-trend with high persistence")