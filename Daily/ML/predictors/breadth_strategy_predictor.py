#!/usr/bin/env python3
"""
Real-time Breadth Strategy Predictor
Uses trained ML model to provide current strategy recommendations
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
import joblib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.ML.core.breadth_optimization_model import BreadthOptimizationModel

class BreadthStrategyPredictor:
    def __init__(self):
        """Initialize the predictor with trained model"""
        self.model = BreadthOptimizationModel()
        # Go up to India-TS directory
        current_file = os.path.abspath(__file__)
        ml_dir = os.path.dirname(os.path.dirname(current_file))  # Daily/ML
        daily_dir = os.path.dirname(ml_dir)  # Daily
        self.base_dir = os.path.dirname(daily_dir)  # India-TS
        
    def get_current_breadth_features(self) -> dict:
        """Get current market breadth features"""
        try:
            # Load recent breadth data
            breadth_file = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                       'historical_breadth_data', 'sma_breadth_historical_latest.json')
            
            with open(breadth_file, 'r') as f:
                breadth_data = json.load(f)
            
            # Convert to DataFrame
            df = pd.DataFrame(breadth_data)
            df['date'] = pd.to_datetime(df['date'])
            df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
            df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
            
            # Sort by date and get latest values
            df = df.sort_values('date')
            
            # Calculate features for prediction
            current_features = {
                'sma20_percent': df.iloc[-1]['sma20_percent'],
                'sma50_percent': df.iloc[-1]['sma50_percent'],
                'sma20_roc_1d': df['sma20_percent'].diff(1).iloc[-1],
                'sma20_roc_3d': df['sma20_percent'].diff(3).iloc[-1],
                'sma20_roc_5d': df['sma20_percent'].diff(5).iloc[-1],
                'sma20_ma3': df['sma20_percent'].rolling(3).mean().iloc[-1],
                'sma20_ma5': df['sma20_percent'].rolling(5).mean().iloc[-1],
                'sma20_ma10': df['sma20_percent'].rolling(10).mean().iloc[-1],
                'sma20_std5': df['sma20_percent'].rolling(5).std().iloc[-1],
                'sma20_std10': df['sma20_percent'].rolling(10).std().iloc[-1],
            }
            
            # Calculate trend features
            current_features['uptrend'] = int(
                (current_features['sma20_percent'] > current_features['sma20_ma5']) and
                (current_features['sma20_ma5'] > current_features['sma20_ma10'])
            )
            current_features['downtrend'] = int(
                (current_features['sma20_percent'] < current_features['sma20_ma5']) and
                (current_features['sma20_ma5'] < current_features['sma20_ma10'])
            )
            
            # Calculate days since extremes
            days_since_low = 0
            days_since_high = 0
            
            for i in range(len(df)-1, -1, -1):
                if df.iloc[i]['sma20_percent'] < 20:
                    break
                days_since_low += 1
            
            for i in range(len(df)-1, -1, -1):
                if df.iloc[i]['sma20_percent'] > 80:
                    break
                days_since_high += 1
            
            current_features['days_since_low'] = days_since_low
            current_features['days_since_high'] = days_since_high
            
            return current_features
            
        except Exception as e:
            print(f"Error getting current breadth features: {e}")
            return None
    
    def get_strategy_recommendation(self) -> dict:
        """Get current strategy recommendation from ML model"""
        features = self.get_current_breadth_features()
        
        if not features:
            return {
                'error': 'Unable to get current market breadth data',
                'timestamp': datetime.now().isoformat()
            }
        
        # Get prediction from model
        recommendation = self.model.predict_optimal_strategy(features)
        
        # Add additional context
        recommendation['current_features'] = {
            'sma20_breadth': features['sma20_percent'],
            'sma50_breadth': features['sma50_percent'],
            'breadth_momentum_1d': features['sma20_roc_1d'],
            'breadth_momentum_5d': features['sma20_roc_5d'],
            'breadth_trend': 'Uptrend' if features['uptrend'] else ('Downtrend' if features['downtrend'] else 'Neutral')
        }
        
        # Add rule-based recommendations for comparison
        recommendation['rule_based'] = {
            'long_favorable': 55 <= features['sma20_percent'] <= 70,
            'short_favorable': 35 <= features['sma20_percent'] <= 50,
            'avoid_trading': features['sma20_percent'] < 20 or features['sma20_percent'] > 80
        }
        
        return recommendation
    
    def create_dashboard_widget(self) -> str:
        """Create HTML widget for dashboard integration"""
        rec = self.get_strategy_recommendation()
        
        if 'error' in rec:
            return f"<div class='error'>Error: {rec['error']}</div>"
        
        strategy_color = '#28a745' if rec['recommended_strategy'] == 'LONG' else '#dc3545'
        
        html = f"""
        <div class="ml-strategy-widget">
            <h3>🤖 ML Strategy Recommendation</h3>
            <div class="strategy-box" style="background-color: {strategy_color}; color: white; padding: 15px; border-radius: 5px;">
                <h2>{rec['recommended_strategy']}</h2>
                <p>Confidence: {rec['confidence']:.2f}</p>
            </div>
            
            <div class="predictions" style="margin-top: 15px;">
                <div class="prediction-row">
                    <span>Expected Long PnL:</span>
                    <span style="color: {'green' if rec['long_expected_pnl'] > 0 else 'red'}">
                        {rec['long_expected_pnl']:.2f}%
                    </span>
                </div>
                <div class="prediction-row">
                    <span>Expected Short PnL:</span>
                    <span style="color: {'green' if rec['short_expected_pnl'] > 0 else 'red'}">
                        {rec['short_expected_pnl']:.2f}%
                    </span>
                </div>
            </div>
            
            <div class="current-conditions" style="margin-top: 15px; font-size: 0.9em;">
                <h4>Current Market Conditions:</h4>
                <ul>
                    <li>SMA20 Breadth: {rec['current_features']['sma20_breadth']:.1f}%</li>
                    <li>Breadth Trend: {rec['current_features']['breadth_trend']}</li>
                    <li>1-Day Momentum: {rec['current_features']['breadth_momentum_1d']:.1f}%</li>
                </ul>
            </div>
            
            <div class="update-time" style="margin-top: 10px; font-size: 0.8em; color: #666;">
                Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        """
        
        return html

def main():
    """Test the predictor"""
    print("Breadth Strategy Predictor")
    print("-" * 60)
    
    predictor = BreadthStrategyPredictor()
    
    # Get current recommendation
    rec = predictor.get_strategy_recommendation()
    
    if 'error' in rec:
        print(f"Error: {rec['error']}")
        return
    
    print(f"\nCurrent Market Breadth: {rec['current_features']['sma20_breadth']:.1f}%")
    print(f"Breadth Trend: {rec['current_features']['breadth_trend']}")
    print(f"\nML RECOMMENDATION: {rec['recommended_strategy']}")
    print(f"Confidence Level: {rec['confidence']:.2f}")
    print(f"\nExpected Returns:")
    print(f"  Long Strategy: {rec['long_expected_pnl']:.2f}%")
    print(f"  Short Strategy: {rec['short_expected_pnl']:.2f}%")
    
    if rec['specific_recommendations']:
        print(f"\nSpecific Recommendations:")
        for recommendation in rec['specific_recommendations']:
            print(f"  - {recommendation}")
    
    print(f"\nRule-Based Check:")
    print(f"  Long Favorable (55-70%): {rec['rule_based']['long_favorable']}")
    print(f"  Short Favorable (35-50%): {rec['rule_based']['short_favorable']}")
    print(f"  Avoid Trading: {rec['rule_based']['avoid_trading']}")

if __name__ == "__main__":
    main()