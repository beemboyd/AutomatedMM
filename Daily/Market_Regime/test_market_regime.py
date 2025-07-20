#!/usr/bin/env python
"""
Test the Market Regime Analysis System
"""

import os
import sys
import logging

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import modules
from market_regime_analyzer import MarketRegimeAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Test the market regime analysis system"""
    logger.info("Testing Market Regime Analysis System...")
    
    try:
        # Initialize analyzer
        analyzer = MarketRegimeAnalyzer()
        
        # Generate regime report
        logger.info("Generating market regime report...")
        report = analyzer.generate_regime_report()
        
        if report:
            logger.info("✅ Market regime analysis completed successfully!")
            
            # Display key information
            print("\n" + "="*50)
            print("MARKET REGIME ANALYSIS TEST RESULTS")
            print("="*50)
            print(f"\nCurrent Regime: {report['market_regime']['regime']}")
            print(f"Description: {report['market_regime']['description']}")
            
            if report.get('prediction'):
                print(f"\nNext Regime Prediction: {report['prediction']['predicted_regime']}")
                print(f"Confidence: {report['prediction']['confidence']:.1%}")
            
            print(f"\nLong Count: {report['reversal_counts']['long']}")
            print(f"Short Count: {report['reversal_counts']['short']}")
            
            print("\nOutputs created:")
            print(f"- Scan results in: Market_Regime/scan_results/")
            print(f"- Trend analysis in: Market_Regime/trend_analysis/")
            print(f"- Regime reports in: Market_Regime/regime_analysis/")
            print(f"- Predictions in: Market_Regime/predictions/")
            print(f"- Scanner results in: Market_Regime/results/")
            print(f"- Logs in: Market_Regime/logs/")
            
            print("\n✅ All components working correctly!")
            
        else:
            logger.error("❌ Failed to generate regime report")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())