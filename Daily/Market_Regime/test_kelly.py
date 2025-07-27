#!/usr/bin/env python3
"""Test Kelly calculations"""

from market_regime_analyzer import MarketRegimeAnalyzer

analyzer = MarketRegimeAnalyzer()
report = analyzer.generate_regime_report()

if report:
    print("Market Regime:", report['market_regime']['regime'])
    print("Confidence:", report['market_regime']['confidence'])
    print("\nPosition Recommendations:")
    recs = report.get('position_recommendations', {})
    for key, value in recs.items():
        print(f"  {key}: {value}")
else:
    print("Failed to generate report")