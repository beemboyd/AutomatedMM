"""
Market Regime Detection System

A sophisticated market regime detection system that continuously learns and provides
actionable trading insights for the India-TS trading framework.

Main Components:
1. Regime Detection Engine - Identifies current market regime
2. Adaptive Learning System - Continuously improves detection accuracy
3. Action Recommendation Engine - Translates insights into trading actions
"""

from .core.regime_detector import RegimeDetector
from .core.market_indicators import MarketIndicators
from .actions.recommendation_engine import RecommendationEngine
from .learning.adaptive_learner import AdaptiveLearner

__version__ = "1.0.0"
__author__ = "India-TS Trading System"

__all__ = [
    "RegimeDetector",
    "MarketIndicators", 
    "RecommendationEngine",
    "AdaptiveLearner"
]