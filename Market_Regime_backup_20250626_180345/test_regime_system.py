"""
Test script for Market Regime Detection System

Demonstrates the functionality of the regime detection system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging

from Market_Regime.core.regime_detector import RegimeDetector
from Market_Regime.core.market_indicators import MarketIndicators
from Market_Regime.actions.recommendation_engine import RecommendationEngine
from Market_Regime.learning.adaptive_learner import AdaptiveLearner
from Market_Regime.integration.daily_integration import DailyTradingIntegration


def generate_sample_market_data(regime_type='bull', days=100):
    """Generate sample market data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Base parameters for different regimes
    params = {
        'strong_bull': {'trend': 0.002, 'volatility': 0.015, 'bias': 0.7},
        'bull': {'trend': 0.001, 'volatility': 0.02, 'bias': 0.6},
        'neutral': {'trend': 0.0, 'volatility': 0.025, 'bias': 0.5},
        'bear': {'trend': -0.001, 'volatility': 0.025, 'bias': 0.4},
        'strong_bear': {'trend': -0.002, 'volatility': 0.03, 'bias': 0.3},
        'volatile': {'trend': 0.0, 'volatility': 0.04, 'bias': 0.5},
        'crisis': {'trend': -0.003, 'volatility': 0.05, 'bias': 0.2}
    }
    
    p = params.get(regime_type, params['neutral'])
    
    # Generate price data
    returns = np.random.normal(p['trend'], p['volatility'], days)
    prices = 15000 * np.exp(np.cumsum(returns))
    
    # Generate OHLCV data
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.005, 0.005, days)),
        'high': prices * (1 + np.random.uniform(0, 0.01, days)),
        'low': prices * (1 - np.random.uniform(0, 0.01, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, days) * (1 + p['bias'])
    })
    
    # Add market breadth data
    data['advances'] = np.random.binomial(1000, p['bias'], days)
    data['declines'] = 1000 - data['advances']
    data['new_highs'] = np.random.binomial(100, p['bias'], days)
    data['new_lows'] = np.random.binomial(100, 1-p['bias'], days)
    
    data.set_index('date', inplace=True)
    return data


def generate_sample_scanner_data(regime_type='bull', num_stocks=50):
    """Generate sample scanner data"""
    # Stock symbols
    symbols = [f'STOCK{i:03d}' for i in range(num_stocks)]
    
    # Sector distribution
    sectors = ['IT', 'Banking', 'Pharma', 'Auto', 'FMCG', 'Metal', 'Realty', 'Energy']
    
    # Generate based on regime
    if regime_type in ['strong_bull', 'bull']:
        bullish_prob = 0.7
    elif regime_type in ['bear', 'strong_bear', 'crisis']:
        bullish_prob = 0.3
    else:
        bullish_prob = 0.5
    
    data = []
    for symbol in symbols:
        is_bullish = np.random.random() < bullish_prob
        
        data.append({
            'Symbol': symbol,
            'signal': 'BUY' if is_bullish else 'SELL',
            'strength': np.random.uniform(0.5, 1.0) if is_bullish else np.random.uniform(0.3, 0.7),
            'Score': np.random.uniform(60, 90) if is_bullish else np.random.uniform(30, 60),
            'sector': np.random.choice(sectors),
            'price_position': np.random.uniform(0.7, 0.95) if is_bullish else np.random.uniform(0.05, 0.3)
        })
    
    return pd.DataFrame(data)


def test_regime_detection():
    """Test regime detection functionality"""
    print("="*60)
    print("TESTING REGIME DETECTION SYSTEM")
    print("="*60)
    
    # Initialize components
    regime_detector = RegimeDetector()
    indicators_calc = MarketIndicators()
    
    # Test different market conditions
    test_regimes = ['strong_bull', 'bull', 'neutral', 'bear', 'volatile', 'crisis']
    
    for test_regime in test_regimes:
        print(f"\n\nTesting {test_regime.upper()} Market Conditions")
        print("-"*40)
        
        # Generate test data
        market_data = generate_sample_market_data(test_regime)
        scanner_data = generate_sample_scanner_data(test_regime)
        
        # Calculate indicators
        indicators = indicators_calc.calculate_all_indicators(market_data)
        
        # Print key indicators
        print(f"Market Score: {indicators.get('market_score', 0):.3f}")
        print(f"Trend Score: {indicators.get('trend_score', 0):.3f}")
        print(f"Momentum: {indicators.get('momentum_composite', 0):.3f}")
        print(f"Volatility: {indicators.get('volatility_score', 0):.3f}")
        print(f"Breadth: {indicators.get('breadth_score', 0):.3f}")
        
        # Detect regime
        regime_analysis = regime_detector.detect_regime(market_data, scanner_data)
        
        print(f"\nDetected Regime: {regime_analysis['regime']}")
        print(f"Confidence: {regime_analysis['confidence']:.1%}")
        print(f"Regime Changed: {regime_analysis['regime_changed']}")
        
        # Print reasoning
        print("\nReasoning:")
        for reason in regime_analysis['reasoning']:
            print(f"  - {reason}")


def test_recommendations():
    """Test recommendation generation"""
    print("\n\n" + "="*60)
    print("TESTING RECOMMENDATION ENGINE")
    print("="*60)
    
    # Initialize components
    regime_detector = RegimeDetector()
    recommendation_engine = RecommendationEngine()
    
    # Test portfolio state
    portfolio_state = {
        'total_capital': 1000000,
        'deployed_capital': 600000,
        'cash': 400000,
        'cash_percentage': 0.4,
        'total_exposure': 0.6,
        'positions': [
            {'symbol': 'INFY', 'quantity': 100, 'value': 150000, 'allocation': 0.15},
            {'symbol': 'HDFC', 'quantity': 50, 'value': 200000, 'allocation': 0.20},
            {'symbol': 'TCS', 'quantity': 30, 'value': 100000, 'allocation': 0.10}
        ]
    }
    
    # Test different regimes
    for test_regime in ['bull', 'bear', 'volatile']:
        print(f"\n\nRecommendations for {test_regime.upper()} Regime")
        print("-"*40)
        
        # Generate test data
        market_data = generate_sample_market_data(test_regime)
        regime_analysis = regime_detector.detect_regime(market_data)
        
        # Generate recommendations
        recommendations = recommendation_engine.generate_recommendations(
            regime_analysis, portfolio_state
        )
        
        # Print position sizing
        print("\nPosition Sizing:")
        ps = recommendations['position_sizing']
        print(f"  Size Multiplier: {ps['size_multiplier']}")
        print(f"  Max Position Size: {ps['max_position_size']:.1%}")
        print(f"  Recommended Positions: {ps['recommended_positions']}")
        print(f"  Guidance: {ps['guidance']}")
        
        # Print risk management
        print("\nRisk Management:")
        rm = recommendations['risk_management']
        print(f"  Stop Loss Multiplier: {rm['stop_loss_multiplier']}")
        print(f"  Risk Per Trade: {rm['risk_per_trade']:.1%}")
        print(f"  Portfolio Heat: {rm['portfolio_heat']:.1%}")
        
        # Print capital deployment
        print("\nCapital Deployment:")
        cd = recommendations['capital_deployment']
        print(f"  Deployment Rate: {cd['deployment_rate']:.1%}")
        print(f"  Cash Allocation: {cd['cash_allocation']:.1%}")
        print(f"  Entry Strategy: {cd['entry_strategy']}")
        
        # Print specific actions
        print("\nSpecific Actions:")
        for action in recommendations['specific_actions'][:3]:
            print(f"  [{action['priority']}] {action['action']}: {action['description']}")
        
        # Print alerts
        if recommendations['alerts']:
            print("\nAlerts:")
            for alert in recommendations['alerts']:
                print(f"  [{alert['severity']}] {alert['message']}")


def test_integration():
    """Test Daily trading integration"""
    print("\n\n" + "="*60)
    print("TESTING DAILY TRADING INTEGRATION")
    print("="*60)
    
    # Initialize integration
    integration = DailyTradingIntegration()
    
    # Test regime analysis
    print("\nRunning Full Market Regime Analysis...")
    analysis = integration.analyze_current_market_regime()
    
    if 'error' not in analysis:
        regime = analysis['regime_analysis']['regime']
        confidence = analysis['regime_analysis']['confidence']
        enhanced_regime = analysis['regime_analysis']['enhanced_regime']
        enhanced_confidence = analysis['regime_analysis']['enhanced_confidence']
        
        print(f"\nBase Detection:")
        print(f"  Regime: {regime}")
        print(f"  Confidence: {confidence:.1%}")
        
        print(f"\nEnhanced Detection:")
        print(f"  Regime: {enhanced_regime}")
        print(f"  Confidence: {enhanced_confidence:.1%}")
        
        # Test order placement check
        print("\n\nTesting Order Placement Checks:")
        test_signals = [
            {'symbol': 'INFY', 'sector': 'IT', 'strength': 0.8},
            {'symbol': 'HDFC', 'sector': 'Banking', 'strength': 0.6},
            {'symbol': 'COAL', 'sector': 'Mining', 'strength': 0.9}
        ]
        
        for signal in test_signals:
            should_place, reason = integration.should_place_order(signal['symbol'], signal)
            print(f"\n{signal['symbol']} ({signal['sector']}):")
            print(f"  Should Place: {should_place}")
            print(f"  Reason: {reason}")
        
        # Test parameter adjustments
        print("\n\nTesting Parameter Adjustments:")
        print(f"Position Size Multiplier: {integration.get_position_size_multiplier('TEST', 100000)}")
        print(f"Stop Loss Adjustment: {integration.get_stop_loss_adjustment('TEST', 0.02)}")
        
        # Test scan filters
        print("\n\nRegime-Aware Scan Filters:")
        filters = integration.get_regime_aware_scan_filters()
        print(f"  Min Volume: {filters['min_volume']:,}")
        print(f"  Price Range: {filters['min_price']} - {filters['max_price']}")
        print(f"  RSI Range: {filters['min_rsi']} - {filters['max_rsi']}")
        print(f"  Preferred Sectors: {filters['preferred_sectors']}")
        
    else:
        print(f"Error: {analysis['error']}")


def test_adaptive_learning():
    """Test adaptive learning functionality"""
    print("\n\n" + "="*60)
    print("TESTING ADAPTIVE LEARNING")
    print("="*60)
    
    # Initialize learner
    learner = AdaptiveLearner()
    
    # Simulate some predictions and outcomes
    print("\nSimulating predictions and outcomes...")
    
    regimes = ['bull', 'bear', 'volatile', 'neutral']
    
    for i in range(20):
        # Make a prediction
        regime = np.random.choice(regimes)
        confidence = np.random.uniform(0.5, 0.9)
        indicators = {
            'market_score': np.random.uniform(-1, 1),
            'trend_score': np.random.uniform(-1, 1),
            'momentum_composite': np.random.uniform(-1, 1),
            'volatility_score': np.random.uniform(0, 1),
            'breadth_score': np.random.uniform(-1, 1)
        }
        
        # Record prediction
        prediction_id = learner.record_prediction(regime, confidence, indicators, 
                                                indicators['market_score'])
        
        # Simulate outcome
        actual_regime = regime if np.random.random() < 0.7 else np.random.choice(regimes)
        outcome = {
            'actual_regime': actual_regime,
            'market_return': np.random.uniform(-0.02, 0.02),
            'volatility': np.random.uniform(10, 30),
            'predicted_regime': regime
        }
        
        # Update with outcome
        learner.update_prediction_outcome(prediction_id, outcome)
    
    # Get performance stats
    print("\nRegime Performance Statistics:")
    stats = learner.get_regime_performance_stats()
    
    for regime, perf in stats.items():
        print(f"\n{regime.upper()}:")
        print(f"  Total Predictions: {perf['total_predictions']}")
        print(f"  Accuracy: {perf['accuracy']:.1%}")
        print(f"  Avg Confidence: {perf['avg_confidence']:.1%}")
        print(f"  Avg Outcome Score: {perf['avg_outcome_score']:.2f}")
    
    # Get feature importance
    print("\n\nFeature Importance Ranking:")
    importance = learner.get_feature_importance_ranking()
    
    for i, (feature, score) in enumerate(importance[:5]):
        print(f"  {i+1}. {feature}: {score:.3f}")
    
    # Get suggestions
    print("\n\nParameter Adjustment Suggestions:")
    suggestions = learner.suggest_parameter_adjustments()
    
    for key, suggestion in suggestions.items():
        print(f"\n{key}:")
        for k, v in suggestion.items():
            print(f"  {k}: {v}")


def run_all_tests():
    """Run all tests"""
    # Setup logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Run tests
    test_regime_detection()
    test_recommendations()
    test_integration()
    test_adaptive_learning()
    
    print("\n\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()