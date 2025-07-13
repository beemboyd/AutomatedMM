"""
Market Regime Detection Module
=============================

A comprehensive market regime detection system for the India-TS Daily trading framework.
This module analyzes market conditions to identify different market regimes (Bull, Bear,
Volatile, Range-bound) and provides actionable insights for position sizing and risk management.

Main Components:
- RegimeDetector: Core regime detection engine
- MarketIndicators: Calculation of market-wide indicators
- RegimeSignals: Detection of regime change signals
- RegimeReporter: Reporting and visualization tools

Usage:
    from analysis.market_regime import RegimeDetector
    
    detector = RegimeDetector()
    regime, confidence = detector.detect_current_regime()
    recommendations = detector.get_regime_recommendations()
"""

from .regime_detector import RegimeDetector
from .market_indicators import MarketIndicators
from .regime_signals import RegimeSignals
from .regime_reporter import RegimeReporter

__all__ = [
    'RegimeDetector',
    'MarketIndicators', 
    'RegimeSignals',
    'RegimeReporter'
]

__version__ = '1.0.0'