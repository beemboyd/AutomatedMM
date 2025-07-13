#!/usr/bin/env python
"""
Market Regime Daily Integration
==============================
Example of how to integrate market regime detection into daily trading workflow.
This script demonstrates using regime detection for position sizing and risk management.
"""

import os
import sys
import logging
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.market_regime import RegimeDetector, RegimeReporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RegimeAwareTrading:
    """Example class showing regime-aware trading decisions"""
    
    def __init__(self, base_dir: str = None):
        """Initialize regime-aware trading"""
        if base_dir is None:
            base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"
            
        self.base_dir = base_dir
        self.detector = RegimeDetector(base_dir)
        self.reporter = RegimeReporter(base_dir)
        
        # Default position sizing
        self.default_position_size = 100000  # Rs 1 lakh default
        self.max_portfolio_value = 5000000   # Rs 50 lakh portfolio
        
    def get_adjusted_position_size(self, ticker: str, entry_price: float) -> dict:
        """
        Calculate regime-adjusted position size
        
        Args:
            ticker: Stock ticker
            entry_price: Entry price per share
            
        Returns:
            Dict with position sizing details
        """
        # Get current regime
        regime, confidence = self.detector.detect_current_regime()
        recommendations = self.detector.get_regime_recommendations()
        
        # Get position sizing adjustments
        sizing = recommendations['position_sizing']
        size_multiplier = sizing['size_multiplier']
        max_exposure = sizing['max_portfolio_exposure']
        
        # Calculate adjusted position size
        adjusted_size = self.default_position_size * size_multiplier
        
        # Apply maximum exposure limit
        max_position_value = self.max_portfolio_value * max_exposure * 0.1  # 10% per position max
        adjusted_size = min(adjusted_size, max_position_value)
        
        # Calculate shares
        shares = int(adjusted_size / entry_price)
        actual_value = shares * entry_price
        
        return {
            'ticker': ticker,
            'shares': shares,
            'position_value': actual_value,
            'entry_price': entry_price,
            'regime': regime,
            'regime_confidence': confidence,
            'size_multiplier': size_multiplier,
            'max_exposure': max_exposure,
            'position_pct': (actual_value / self.max_portfolio_value) * 100
        }
        
    def get_adjusted_stop_loss(self, entry_price: float, atr: float, 
                             position_type: str = 'LONG') -> dict:
        """
        Calculate regime-adjusted stop loss
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            position_type: LONG or SHORT
            
        Returns:
            Dict with stop loss details
        """
        # Get current regime
        regime, confidence = self.detector.detect_current_regime()
        recommendations = self.detector.get_regime_recommendations()
        
        # Get stop loss multiplier
        sl_multiplier = recommendations['position_sizing']['stop_loss_multiplier']
        
        # Calculate stop distance
        stop_distance = atr * sl_multiplier
        
        # Calculate stop price
        if position_type == 'LONG':
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance
            
        return {
            'stop_price': round(stop_price, 2),
            'stop_distance': stop_distance,
            'stop_pct': (stop_distance / entry_price) * 100,
            'multiplier': sl_multiplier,
            'regime': regime,
            'regime_confidence': confidence
        }
        
    def should_take_trade(self, ticker: str, signal_type: str = 'LONG') -> dict:
        """
        Determine if trade should be taken based on regime
        
        Args:
            ticker: Stock ticker
            signal_type: LONG or SHORT
            
        Returns:
            Dict with trade decision
        """
        # Get current regime
        regime, confidence = self.detector.detect_current_regime()
        recommendations = self.detector.get_regime_recommendations()
        
        # Check risk level
        risk_level = recommendations['risk_level']
        
        # Decision logic based on regime
        take_trade = True
        reason = ""
        
        if regime in ['STRONG_BEAR', 'VOLATILE'] and signal_type == 'LONG':
            if confidence > 0.7:
                take_trade = False
                reason = f"Avoid long positions in {regime} regime"
        
        elif regime in ['STRONG_BULL'] and signal_type == 'SHORT':
            if confidence > 0.7:
                take_trade = False
                reason = f"Avoid short positions in {regime} regime"
                
        elif risk_level == 'HIGH':
            take_trade = True  # Can take but with reduced size
            reason = "High risk regime - trade with caution"
            
        # Check preferred sectors
        preferred_sectors = recommendations.get('preferred_sectors', [])
        
        return {
            'take_trade': take_trade,
            'reason': reason,
            'regime': regime,
            'confidence': confidence,
            'risk_level': risk_level,
            'preferred_sectors': preferred_sectors
        }
        
    def generate_daily_regime_report(self):
        """Generate comprehensive daily regime report"""
        # Detect current regime
        regime, confidence = self.detector.detect_current_regime()
        recommendations = self.detector.get_regime_recommendations()
        
        # Get regime data
        regime_data = self.detector.current_regime if self.detector.current_regime else {}
        
        # Generate reports
        saved_files = self.reporter.generate_daily_report(
            regime_data,
            recommendations,
            save_format=['text', 'excel', 'html']
        )
        
        # Get historical data for visualization
        historical = self.detector.get_historical_analysis(days=30)
        
        if not historical.empty:
            # Create visualizations
            viz_path = self.reporter.create_regime_visualization(historical)
            dashboard_path = self.reporter.generate_summary_dashboard(
                regime_data,
                recommendations,
                historical
            )
            saved_files.extend([viz_path, dashboard_path])
            
        return saved_files


def main():
    """Example usage in daily workflow"""
    print("\n" + "="*60)
    print("MARKET REGIME INTEGRATION EXAMPLE")
    print("="*60)
    
    # Initialize regime-aware trading
    trading = RegimeAwareTrading()
    
    # Example 1: Position sizing
    print("\n1. POSITION SIZING EXAMPLE")
    print("-"*30)
    
    ticker = "RELIANCE"
    entry_price = 2500.0
    
    position_info = trading.get_adjusted_position_size(ticker, entry_price)
    
    print(f"Ticker: {ticker}")
    print(f"Entry Price: Rs {entry_price}")
    print(f"Current Regime: {position_info['regime']} ({position_info['regime_confidence']:.1%} confidence)")
    print(f"Size Multiplier: {position_info['size_multiplier']}x")
    print(f"Recommended Shares: {position_info['shares']}")
    print(f"Position Value: Rs {position_info['position_value']:,.0f}")
    print(f"Position %: {position_info['position_pct']:.1f}%")
    
    # Example 2: Stop loss calculation
    print("\n2. STOP LOSS EXAMPLE")
    print("-"*30)
    
    atr = 50.0  # Example ATR
    sl_info = trading.get_adjusted_stop_loss(entry_price, atr)
    
    print(f"Entry Price: Rs {entry_price}")
    print(f"ATR: Rs {atr}")
    print(f"Stop Loss Multiplier: {sl_info['multiplier']}x")
    print(f"Stop Loss Price: Rs {sl_info['stop_price']}")
    print(f"Stop Distance: Rs {sl_info['stop_distance']:.2f} ({sl_info['stop_pct']:.1f}%)")
    
    # Example 3: Trade decision
    print("\n3. TRADE DECISION EXAMPLE")
    print("-"*30)
    
    decision = trading.should_take_trade(ticker, 'LONG')
    
    print(f"Signal Type: LONG")
    print(f"Take Trade: {'YES' if decision['take_trade'] else 'NO'}")
    print(f"Reason: {decision['reason']}")
    print(f"Risk Level: {decision['risk_level']}")
    if decision['preferred_sectors']:
        print(f"Preferred Sectors: {', '.join(decision['preferred_sectors'])}")
        
    # Example 4: Generate daily report
    print("\n4. GENERATING DAILY REPORT")
    print("-"*30)
    
    try:
        saved_files = trading.generate_daily_regime_report()
        print("Reports generated:")
        for file in saved_files:
            print(f"  - {os.path.basename(file)}")
    except Exception as e:
        print(f"Error generating report: {e}")
        
    print("\n" + "="*60)
    print("Integration example completed!")
    print("="*60)


if __name__ == "__main__":
    main()