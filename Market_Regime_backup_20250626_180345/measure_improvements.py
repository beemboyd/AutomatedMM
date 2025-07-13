#!/usr/bin/env python3
"""
Quick script to measure and display metric improvements
"""

import json
import os
from datetime import datetime, timedelta
import pandas as pd

class ImprovementMeasurer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.predictions_dir = os.path.join(self.base_dir, 'predictions')
        self.data_dir = os.path.join(self.base_dir, 'data')
        
    def get_model_performance(self):
        """Load current model performance metrics"""
        perf_file = os.path.join(self.predictions_dir, 'model_performance.json')
        if os.path.exists(perf_file):
            with open(perf_file, 'r') as f:
                return json.load(f)
        return None
    
    def get_threshold_history(self):
        """Track how thresholds have been optimized over time"""
        threshold_file = os.path.join(self.data_dir, 'optimized_thresholds.json')
        original_file = os.path.join(self.data_dir, 'trend_config.json')
        
        optimized = {}
        original = {}
        
        if os.path.exists(threshold_file):
            with open(threshold_file, 'r') as f:
                optimized = json.load(f)
                
        if os.path.exists(original_file):
            with open(original_file, 'r') as f:
                original = json.load(f)
                
        return {
            'original': original.get('thresholds', {}),
            'optimized': optimized.get('optimized_thresholds', {}),
            'last_updated': optimized.get('last_updated', 'Never')
        }
    
    def calculate_prediction_accuracy_trend(self):
        """Calculate how prediction accuracy has improved over time"""
        history_file = os.path.join(self.predictions_dir, 'prediction_history.json')
        
        if not os.path.exists(history_file):
            return None
            
        with open(history_file, 'r') as f:
            history = json.load(f)
            
        if not history:
            return None
            
        # Group by date and calculate daily accuracy
        daily_accuracy = {}
        
        for entry in history:
            date = entry['timestamp'][:10]  # Extract date
            
            if date not in daily_accuracy:
                daily_accuracy[date] = {'correct': 0, 'total': 0}
                
            daily_accuracy[date]['total'] += 1
            
            if entry.get('actual_regime') == entry.get('predicted_regime'):
                daily_accuracy[date]['correct'] += 1
        
        # Calculate accuracy percentages
        results = []
        for date, stats in sorted(daily_accuracy.items()):
            accuracy = (stats['correct'] / stats['total']) * 100 if stats['total'] > 0 else 0
            results.append({
                'date': date,
                'accuracy': accuracy,
                'correct': stats['correct'],
                'total': stats['total']
            })
            
        return results
    
    def get_feature_importance_changes(self):
        """Track how feature importance has evolved"""
        perf = self.get_model_performance()
        
        if perf and 'feature_importance' in perf:
            importance = perf['feature_importance']
            
            # Sort by importance
            sorted_features = sorted(
                importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            return sorted_features
        
        return None
    
    def generate_improvement_summary(self):
        """Generate a comprehensive improvement summary"""
        print("\n" + "="*60)
        print("MARKET REGIME MODEL - IMPROVEMENT METRICS")
        print("="*60)
        
        # 1. Model Performance
        perf = self.get_model_performance()
        if perf:
            print(f"\n📊 MODEL PERFORMANCE")
            print(f"   Overall Accuracy: {perf['overall_accuracy']:.1%}")
            print(f"   Total Predictions: {perf['total_predictions']}")
            print(f"   Correct Predictions: {perf['correct_predictions']}")
            
            if 'last_retrain_date' in perf:
                print(f"   Last Model Retrain: {perf['last_retrain_date']}")
            
            # Regime-specific accuracy
            if 'regime_accuracy' in perf:
                print(f"\n   Regime-Specific Accuracy:")
                for regime, acc in perf['regime_accuracy'].items():
                    print(f"   - {regime}: {acc:.1%}")
        
        # 2. Accuracy Trend
        accuracy_trend = self.calculate_prediction_accuracy_trend()
        if accuracy_trend and len(accuracy_trend) > 1:
            print(f"\n📈 ACCURACY TREND")
            
            # Show last 7 days
            recent = accuracy_trend[-7:]
            
            print(f"   Last 7 Days:")
            for day in recent:
                bar = "█" * int(day['accuracy'] / 5)  # Visual bar
                print(f"   {day['date']}: {bar} {day['accuracy']:.1f}% ({day['correct']}/{day['total']})")
            
            # Calculate improvement
            if len(accuracy_trend) >= 7:
                week_ago = accuracy_trend[-7]['accuracy']
                current = accuracy_trend[-1]['accuracy']
                improvement = current - week_ago
                
                if improvement > 0:
                    print(f"\n   ✅ Improvement: +{improvement:.1f}% over last week")
                else:
                    print(f"\n   ⚠️  Decline: {improvement:.1f}% over last week")
        
        # 3. Threshold Optimization
        thresholds = self.get_threshold_history()
        if thresholds['optimized']:
            print(f"\n🎯 THRESHOLD OPTIMIZATION")
            print(f"   Last Updated: {thresholds['last_updated']}")
            
            # Compare original vs optimized
            for key in thresholds['original']:
                if key in thresholds['optimized']:
                    orig = thresholds['original'][key]
                    opt = thresholds['optimized'][key]
                    
                    if isinstance(orig, dict) and isinstance(opt, dict):
                        print(f"\n   {key}:")
                        for subkey in orig:
                            if subkey in opt:
                                print(f"     {subkey}: {orig[subkey]} → {opt[subkey]}")
        
        # 4. Feature Importance
        features = self.get_feature_importance_changes()
        if features:
            print(f"\n🔍 TOP PREDICTIVE FEATURES")
            for i, (feature, importance) in enumerate(features[:5]):
                print(f"   {i+1}. {feature}: {importance:.3f}")
        
        # 5. Recommendations
        print(f"\n💡 RECOMMENDATIONS FOR IMPROVEMENT")
        
        if perf and perf['overall_accuracy'] < 0.7:
            print("   - Accuracy below 70% - Consider collecting more data")
            print("   - Review feature engineering for better signals")
        
        if perf and perf['total_predictions'] < 100:
            print("   - Less than 100 predictions - Model needs more training data")
            print("   - Continue running for better optimization")
        
        if accuracy_trend and len(accuracy_trend) > 3:
            recent_accuracies = [d['accuracy'] for d in accuracy_trend[-3:]]
            if all(acc < 60 for acc in recent_accuracies):
                print("   - Recent accuracy declining - Check data quality")
                print("   - Consider manual threshold adjustment")
        
        print("\n" + "="*60)
    
    def create_metrics_report(self):
        """Create a detailed metrics report file"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'model_performance': self.get_model_performance(),
            'accuracy_trend': self.calculate_prediction_accuracy_trend(),
            'threshold_optimization': self.get_threshold_history(),
            'feature_importance': self.get_feature_importance_changes()
        }
        
        # Save report
        report_file = os.path.join(
            self.base_dir, 
            'metrics',
            f"improvement_metrics_{datetime.now().strftime('%Y%m%d')}.json"
        )
        
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        return report_file


def main():
    measurer = ImprovementMeasurer()
    
    # Generate and display summary
    measurer.generate_improvement_summary()
    
    # Create detailed report
    report_file = measurer.create_metrics_report()
    print(f"\nDetailed report saved: {report_file}")
    
    # Quick metrics
    perf = measurer.get_model_performance()
    if perf:
        print(f"\n🎯 QUICK METRICS:")
        print(f"   Current Accuracy: {perf['overall_accuracy']:.1%}")
        print(f"   Predictions Made: {perf['total_predictions']}")
        
        # Estimate time to reliable predictions
        if perf['total_predictions'] < 50:
            remaining = 50 - perf['total_predictions']
            hours = (remaining * 30) / 60  # 30 min intervals
            print(f"   Time to first retrain: ~{hours:.1f} hours")
        elif perf['total_predictions'] < 100:
            remaining = 100 - perf['total_predictions']
            hours = (remaining * 30) / 60
            print(f"   Time to threshold optimization: ~{hours:.1f} hours")


if __name__ == "__main__":
    main()