#!/usr/bin/env python3
"""
Calculate MAE (Mean Absolute Error) for Market Regime Model

Analyzes prediction accuracy by comparing predictions with actual outcomes.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

class MAECalculator:
    """Calculate MAE for regime predictions"""
    
    def __init__(self):
        self.db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
        self.reports_dir = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/reports"
        
    def load_predictions(self):
        """Load predictions from database"""
        conn = sqlite3.connect(self.db_path)
        
        # Load predictions with timestamps
        query = """
        SELECT timestamp, regime, confidence, market_score, 
               volatility_score, trend_score, momentum_score
        FROM predictions
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def calculate_regime_mae(self, predictions_df):
        """Calculate MAE for regime predictions"""
        
        # For regime prediction, we need to compare with actual future regimes
        # Since regime is categorical, we'll convert to numerical scores
        regime_map = {
            'strong_bull': 1.0,
            'bull': 0.5,
            'neutral': 0.0,
            'bear': -0.5,
            'strong_bear': -1.0,
            'volatile': 0.0,  # Treat volatile as neutral
            'crisis': -1.0
        }
        
        # Convert regimes to numerical values
        predictions_df['regime_score'] = predictions_df['regime'].map(regime_map)
        
        # Calculate regime persistence (how long regime lasts)
        regime_changes = []
        for i in range(1, len(predictions_df)):
            if predictions_df.iloc[i]['regime'] != predictions_df.iloc[i-1]['regime']:
                regime_changes.append(i)
        
        print(f"Total predictions: {len(predictions_df)}")
        print(f"Regime changes: {len(regime_changes)}")
        print(f"Average regime duration: {len(predictions_df) / (len(regime_changes) + 1):.1f} periods")
        
        return predictions_df
    
    def calculate_confidence_mae(self, predictions_df):
        """Calculate MAE for confidence scores"""
        
        # For confidence, we can measure how well it predicts regime stability
        # Higher confidence should mean regime persists longer
        
        mae_results = {}
        
        # Group by consecutive regimes
        regime_groups = []
        current_group = {'regime': predictions_df.iloc[0]['regime'], 'confidences': [], 'duration': 0}
        
        for i in range(len(predictions_df)):
            if predictions_df.iloc[i]['regime'] == current_group['regime']:
                current_group['confidences'].append(predictions_df.iloc[i]['confidence'])
                current_group['duration'] += 1
            else:
                regime_groups.append(current_group)
                current_group = {
                    'regime': predictions_df.iloc[i]['regime'], 
                    'confidences': [predictions_df.iloc[i]['confidence']], 
                    'duration': 1
                }
        
        regime_groups.append(current_group)
        
        # Analyze confidence vs duration
        avg_confidences = []
        durations = []
        
        for group in regime_groups:
            if group['duration'] > 1:  # Only consider regimes that lasted more than 1 period
                avg_conf = np.mean(group['confidences'])
                avg_confidences.append(avg_conf)
                durations.append(group['duration'])
        
        if avg_confidences and durations:
            # Normalize durations to 0-1 scale
            max_duration = max(durations)
            norm_durations = [d / max_duration for d in durations]
            
            # Calculate MAE between confidence and normalized duration
            mae = np.mean(np.abs(np.array(avg_confidences) - np.array(norm_durations)))
            mae_results['confidence_duration_mae'] = mae
            
            print(f"\nConfidence vs Duration MAE: {mae:.4f}")
            print(f"(Lower is better - perfect prediction would be 0)")
        
        return mae_results
    
    def calculate_indicator_mae(self, predictions_df):
        """Calculate MAE for various indicators"""
        
        mae_results = {}
        
        # For continuous indicators, we can calculate MAE between consecutive predictions
        indicators = ['market_score', 'volatility_score', 'trend_score', 'momentum_score']
        
        for indicator in indicators:
            if indicator in predictions_df.columns:
                # Calculate changes between consecutive predictions
                actual_changes = predictions_df[indicator].diff().dropna()
                
                # For now, assume predicted change is 0 (no change)
                # In a more sophisticated model, we would have actual predictions
                predicted_changes = np.zeros(len(actual_changes))
                
                mae = np.mean(np.abs(actual_changes - predicted_changes))
                mae_results[f'{indicator}_mae'] = mae
                
                print(f"\n{indicator.replace('_', ' ').title()} MAE: {mae:.4f}")
                
                # Also calculate volatility of the indicator
                volatility = np.std(actual_changes)
                print(f"  Volatility: {volatility:.4f}")
                print(f"  MAE/Volatility ratio: {mae/volatility:.2f}")
        
        return mae_results
    
    def analyze_prediction_accuracy(self):
        """Comprehensive analysis of prediction accuracy"""
        
        print("=" * 60)
        print("MARKET REGIME MODEL - MAE ANALYSIS")
        print("=" * 60)
        
        # Load predictions
        predictions_df = self.load_predictions()
        
        if len(predictions_df) < 10:
            print("Insufficient data for MAE calculation")
            print("Need at least 10 predictions")
            return None
        
        # Analyze regime predictions
        print("\n1. REGIME ANALYSIS")
        print("-" * 40)
        predictions_df = self.calculate_regime_mae(predictions_df)
        
        # Regime distribution
        regime_counts = predictions_df['regime'].value_counts()
        print("\nRegime Distribution:")
        for regime, count in regime_counts.items():
            print(f"  {regime}: {count} ({count/len(predictions_df)*100:.1f}%)")
        
        # Analyze confidence scores
        print("\n2. CONFIDENCE ANALYSIS")
        print("-" * 40)
        confidence_mae = self.calculate_confidence_mae(predictions_df)
        
        avg_confidence = predictions_df['confidence'].mean()
        std_confidence = predictions_df['confidence'].std()
        print(f"\nAverage confidence: {avg_confidence:.4f}")
        print(f"Confidence std dev: {std_confidence:.4f}")
        
        # Analyze indicators
        print("\n3. INDICATOR MAE ANALYSIS")
        print("-" * 40)
        indicator_mae = self.calculate_indicator_mae(predictions_df)
        
        # Overall assessment
        print("\n4. OVERALL ASSESSMENT")
        print("-" * 40)
        
        # Since we don't have actual future values to compare against,
        # we use regime stability and indicator consistency as proxies
        
        # Calculate regime stability score
        regime_changes = predictions_df['regime'].ne(predictions_df['regime'].shift()).sum()
        regime_stability = 1 - (regime_changes / len(predictions_df))
        
        print(f"Regime stability score: {regime_stability:.2%}")
        print("(Higher is better - indicates consistent regime detection)")
        
        # Calculate confidence consistency
        confidence_changes = predictions_df['confidence'].diff().abs().mean()
        print(f"\nAverage confidence change: {confidence_changes:.4f}")
        print("(Lower is better - indicates stable confidence)")
        
        # Summary MAE metrics
        all_mae = {**confidence_mae, **indicator_mae}
        
        if all_mae:
            avg_mae = np.mean(list(all_mae.values()))
            print(f"\n5. AGGREGATE MAE: {avg_mae:.4f}")
            print("-" * 40)
            print("Note: Without ground truth labels, MAE is calculated based on:")
            print("- Prediction consistency over time")
            print("- Confidence vs regime duration correlation")
            print("- Indicator stability metrics")
        
        return all_mae

def main():
    """Run MAE analysis"""
    calculator = MAECalculator()
    mae_results = calculator.analyze_prediction_accuracy()
    
    if mae_results:
        # Save results
        output_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/metrics/mae_analysis.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'mae_metrics': mae_results
            }, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")

if __name__ == "__main__":
    main()