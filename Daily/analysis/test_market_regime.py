#!/usr/bin/env python
"""
Test Market Regime Module
========================
Script to test the market regime detection functionality.
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import regime detector
from market_regime import RegimeDetector, RegimeReporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run market regime analysis"""
    print("\n" + "="*60)
    print("MARKET REGIME DETECTION TEST")
    print("="*60)
    
    # Initialize detector
    base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"
    detector = RegimeDetector(base_dir)
    
    print("\n1. Detecting current market regime...")
    
    # Detect current regime
    try:
        regime, confidence = detector.detect_current_regime()
        
        print(f"\nCurrent Market Regime: {regime}")
        print(f"Confidence: {confidence:.1%}")
        
        # Get recommendations
        print("\n2. Getting regime-based recommendations...")
        recommendations = detector.get_regime_recommendations()
        
        print(f"\nRisk Level: {recommendations['risk_level']}")
        print(f"\nPosition Sizing:")
        sizing = recommendations['position_sizing']
        print(f"  - Size Multiplier: {sizing['size_multiplier']}x")
        print(f"  - Max Portfolio Exposure: {sizing['max_portfolio_exposure']*100:.0f}%")
        print(f"  - Stop Loss Multiplier: {sizing['stop_loss_multiplier']}x")
        
        if recommendations.get('preferred_sectors'):
            print(f"\nPreferred Sectors: {', '.join(recommendations['preferred_sectors'])}")
            
        print("\nAction Items:")
        for i, action in enumerate(recommendations['action_items'], 1):
            print(f"  {i}. {action}")
            
        # Check for alerts
        if recommendations.get('alerts'):
            print("\nALERTS:")
            for alert in recommendations['alerts']:
                print(f"  [{alert['level']}] {alert['message']}")
                
        # Generate report
        print("\n3. Generating reports...")
        reporter = RegimeReporter(base_dir)
        
        # Get current indicators
        if detector.current_regime:
            regime_data = detector.current_regime
        else:
            regime_data = {'indicators': {}}
            
        # Generate reports in multiple formats
        saved_files = reporter.generate_daily_report(
            regime_data,
            recommendations,
            save_format=['text', 'excel', 'html']
        )
        
        print("\nReports generated:")
        for file in saved_files:
            print(f"  - {file}")
            
        # Get historical analysis
        print("\n4. Analyzing regime history...")
        historical = detector.get_historical_analysis(days=30)
        
        if not historical.empty:
            print(f"\nRegime history (last 30 days):")
            regime_counts = historical['regime'].value_counts()
            for regime, count in regime_counts.items():
                print(f"  - {regime}: {count} observations")
                
            # Create visualization
            print("\n5. Creating visualizations...")
            viz_path = reporter.create_regime_visualization(historical)
            print(f"Visualization saved to: {viz_path}")
            
            # Create dashboard
            dashboard_path = reporter.generate_summary_dashboard(
                regime_data,
                recommendations,
                historical
            )
            print(f"Dashboard saved to: {dashboard_path}")
        else:
            print("No historical data available yet")
            
        print("\n" + "="*60)
        print("Market regime analysis completed successfully!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Error during regime analysis: {e}")
        import traceback
        traceback.print_exc()
        

if __name__ == "__main__":
    main()