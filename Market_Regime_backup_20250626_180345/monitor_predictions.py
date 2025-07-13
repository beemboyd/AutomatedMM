#!/usr/bin/env python
"""
Monitor Market Regime Predictions
=================================
Monitor prediction accuracy and system performance.
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PredictionMonitor:
    """Monitor market regime prediction performance"""
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                     'data', 'regime_learning.db')
        
    def get_prediction_accuracy(self, days=30):
        """Get prediction accuracy for the last N days"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT 
                predicted_regime,
                actual_regime,
                confidence,
                timestamp,
                outcome_score
            FROM regime_predictions
            WHERE actual_regime IS NOT NULL
              AND timestamp > datetime('now', ? || ' days')
            ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[-days])
        conn.close()
        
        if df.empty:
            return None
            
        # Calculate accuracy
        df['correct'] = df['predicted_regime'] == df['actual_regime']
        
        # Overall accuracy
        overall_accuracy = df['correct'].mean()
        
        # Accuracy by regime
        regime_accuracy = df.groupby('predicted_regime')['correct'].agg(['mean', 'count'])
        
        # Accuracy by confidence level
        df['confidence_bin'] = pd.cut(df['confidence'], 
                                     bins=[0, 0.4, 0.6, 0.8, 1.0],
                                     labels=['Low', 'Medium', 'High', 'Very High'])
        confidence_accuracy = df.groupby('confidence_bin')['correct'].agg(['mean', 'count'])
        
        # Daily accuracy trend
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_accuracy = df.groupby('date')['correct'].mean()
        
        return {
            'overall_accuracy': overall_accuracy,
            'total_predictions': len(df),
            'regime_accuracy': regime_accuracy.to_dict(),
            'confidence_accuracy': confidence_accuracy.to_dict(),
            'daily_trend': daily_accuracy.to_dict(),
            'avg_confidence': df['confidence'].mean(),
            'avg_outcome_score': df['outcome_score'].mean()
        }
        
    def get_regime_transitions(self, days=7):
        """Get regime transitions for the last N days"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT 
                timestamp,
                from_regime,
                to_regime,
                confidence,
                market_conditions
            FROM regime_changes
            WHERE timestamp > datetime('now', ? || ' days')
            ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[-days])
        conn.close()
        
        transitions = []
        for _, row in df.iterrows():
            transitions.append({
                'timestamp': row['timestamp'],
                'from': row['from_regime'],
                'to': row['to_regime'],
                'confidence': row['confidence'],
                'conditions': json.loads(row['market_conditions']) if row['market_conditions'] else {}
            })
            
        return transitions
        
    def get_pending_predictions(self):
        """Get predictions awaiting outcome tracking"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT 
                id,
                timestamp,
                predicted_regime,
                confidence,
                market_score
            FROM regime_predictions
            WHERE actual_regime IS NULL
              AND timestamp < datetime('now', '-1 hour')
              AND timestamp > datetime('now', '-24 hours')
            ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[])
        conn.close()
        
        return df.to_dict('records')
        
    def generate_performance_report(self):
        """Generate comprehensive performance report"""
        print("\n" + "="*60)
        print("MARKET REGIME PREDICTION PERFORMANCE REPORT")
        print("="*60)
        print(f"Generated at: {datetime.now()}")
        
        # Get 30-day accuracy
        accuracy_30d = self.get_prediction_accuracy(30)
        
        if accuracy_30d:
            print(f"\n30-DAY PERFORMANCE:")
            print(f"  Overall Accuracy: {accuracy_30d['overall_accuracy']:.1%}")
            print(f"  Total Predictions: {accuracy_30d['total_predictions']}")
            print(f"  Average Confidence: {accuracy_30d['avg_confidence']:.1%}")
            print(f"  Average Outcome Score: {accuracy_30d['avg_outcome_score']:.2f}")
            
            print("\n  Accuracy by Regime:")
            for regime, stats in accuracy_30d['regime_accuracy'].items():
                print(f"    {regime}: {stats['mean']:.1%} ({stats['count']} predictions)")
                
            print("\n  Accuracy by Confidence:")
            for conf_level, stats in accuracy_30d['confidence_accuracy'].items():
                print(f"    {conf_level}: {stats['mean']:.1%} ({stats['count']} predictions)")
        else:
            print("\nNo prediction data available for the last 30 days")
            
        # Get 7-day accuracy for comparison
        accuracy_7d = self.get_prediction_accuracy(7)
        
        if accuracy_7d:
            print(f"\n7-DAY PERFORMANCE:")
            print(f"  Overall Accuracy: {accuracy_7d['overall_accuracy']:.1%}")
            print(f"  Total Predictions: {accuracy_7d['total_predictions']}")
            
            if accuracy_30d:
                diff = accuracy_7d['overall_accuracy'] - accuracy_30d['overall_accuracy']
                trend = "↑" if diff > 0 else "↓" if diff < 0 else "→"
                print(f"  Trend: {trend} {abs(diff):.1%} vs 30-day average")
                
        # Get recent transitions
        transitions = self.get_regime_transitions(7)
        
        if transitions:
            print(f"\nRECENT REGIME TRANSITIONS (Last 7 days):")
            for trans in transitions[:5]:  # Show last 5
                print(f"  {trans['timestamp']}: {trans['from']} → {trans['to']} "
                      f"(confidence: {trans['confidence']:.1%})")
                
        # Get pending predictions
        pending = self.get_pending_predictions()
        
        if pending:
            print(f"\nPENDING PREDICTIONS (Awaiting outcomes):")
            for pred in pending[:5]:  # Show first 5
                print(f"  {pred['timestamp']}: {pred['predicted_regime']} "
                      f"(confidence: {pred['confidence']:.1%})")
            if len(pending) > 5:
                print(f"  ... and {len(pending) - 5} more")
                
        print("\n" + "="*60)
        
        return accuracy_30d
        
    def export_performance_data(self, output_file='prediction_performance.xlsx'):
        """Export detailed performance data to Excel"""
        conn = sqlite3.connect(self.db_path)
        
        # Get all predictions with outcomes
        query = """
            SELECT * FROM regime_predictions
            WHERE actual_regime IS NOT NULL
            ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn, params=[])
        
        # Add calculated fields
        df['correct'] = df['predicted_regime'] == df['actual_regime']
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        
        # Create Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Overall data
            df.to_excel(writer, sheet_name='All Predictions', index=False)
            
            # Daily summary
            daily_summary = df.groupby('date').agg({
                'correct': ['mean', 'count'],
                'confidence': 'mean',
                'outcome_score': 'mean'
            }).round(3)
            daily_summary.to_excel(writer, sheet_name='Daily Summary')
            
            # Regime accuracy
            regime_accuracy = df.groupby(['predicted_regime', 'actual_regime']).size().unstack(fill_value=0)
            regime_accuracy.to_excel(writer, sheet_name='Confusion Matrix')
            
        conn.close()
        print(f"\nPerformance data exported to: {output_file}")


def main():
    """Run performance monitoring"""
    monitor = PredictionMonitor()
    
    # Generate performance report
    monitor.generate_performance_report()
    
    # Optionally export detailed data
    response = input("\nExport detailed performance data to Excel? (y/n): ")
    if response.lower() == 'y':
        monitor.export_performance_data()


if __name__ == "__main__":
    main()