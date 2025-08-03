#!/usr/bin/env python3
"""Test ML Dashboard Integration"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.Market_Regime.ml_dashboard_integration_scheduled import ScheduledMLDashboardIntegration

def main():
    try:
        integration = ScheduledMLDashboardIntegration()
        insights = integration.get_ml_insights()
        
        print("ML Dashboard Insights:")
        print("=" * 60)
        
        # Strategy info
        strategy = insights.get('strategy', {})
        print(f"Recommended Strategy: {strategy.get('recommended', 'N/A')}")
        print(f"Confidence: {strategy.get('confidence', 0):.2%}")
        
        # Market conditions
        conditions = insights.get('market_conditions', {})
        print(f"\nMarket Conditions:")
        print(f"  SMA20 Breadth: {conditions.get('sma20_breadth', 0):.1f}%")
        print(f"  SMA50 Breadth: {conditions.get('sma50_breadth', 0):.1f}%")
        
        # Data metadata
        metadata = insights.get('data_metadata', {})
        print(f"\nData Source: {metadata.get('data_source', 'unknown')}")
        print(f"Is Market Hours: {metadata.get('is_market_hours', False)}")
        
        # Save full insights for inspection
        with open('ml_insights_test.json', 'w') as f:
            json.dump(insights, f, indent=2)
        print("\nFull insights saved to ml_insights_test.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()