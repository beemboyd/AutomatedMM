#!/usr/bin/env python3
"""
Metrics Improvement Tracker

Tracks and visualizes improvements for each metric in the Market Regime system.
Measures accuracy, precision, and effectiveness of predictions and recommendations.
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import statistics

class MetricsTracker:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.predictions_dir = os.path.join(self.base_dir, 'predictions')
        self.metrics_dir = os.path.join(self.base_dir, 'metrics')
        self.results_dir = os.path.join(self.base_dir, 'results')
        
        os.makedirs(self.metrics_dir, exist_ok=True)
        
        # Metrics to track
        self.metrics_config = {
            'market_score': {
                'name': 'Market Score Accuracy',
                'type': 'regression',
                'range': [-1, 1]
            },
            'volatility_score': {
                'name': 'Volatility Prediction',
                'type': 'regression',
                'range': [0, 1]
            },
            'regime_prediction': {
                'name': 'Regime Classification',
                'type': 'classification',
                'classes': ['strong_bull', 'bull', 'neutral', 'bear', 'strong_bear', 'volatile', 'crisis']
            },
            'position_size': {
                'name': 'Position Size Effectiveness',
                'type': 'effectiveness',
                'range': [0, 1.2]
            },
            'stop_loss': {
                'name': 'Stop Loss Optimization',
                'type': 'effectiveness',
                'range': [0.5, 1.5]
            },
            'trend_strength': {
                'name': 'Trend Strength Accuracy',
                'type': 'regression',
                'range': [-1, 1]
            },
            'breadth_score': {
                'name': 'Market Breadth Analysis',
                'type': 'regression',
                'range': [-1, 1]
            },
            'long_short_ratio': {
                'name': 'L/S Ratio Prediction',
                'type': 'regression',
                'range': [0, 5]
            }
        }
        
    def calculate_metric_accuracy(self, metric_type, predictions, actuals):
        """Calculate accuracy based on metric type"""
        if metric_type == 'regression':
            # Mean Absolute Error and R-squared
            mae = np.mean(np.abs(np.array(predictions) - np.array(actuals)))
            
            # R-squared
            ss_res = np.sum((np.array(actuals) - np.array(predictions)) ** 2)
            ss_tot = np.sum((np.array(actuals) - np.mean(actuals)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Directional accuracy (did we predict the direction correctly?)
            direction_correct = sum(
                (p > 0 and a > 0) or (p < 0 and a < 0) or (p == 0 and a == 0)
                for p, a in zip(predictions, actuals)
            )
            direction_accuracy = direction_correct / len(predictions) if predictions else 0
            
            return {
                'mae': mae,
                'r_squared': r2,
                'direction_accuracy': direction_accuracy,
                'accuracy_score': (1 - mae) * 0.5 + r2 * 0.3 + direction_accuracy * 0.2
            }
            
        elif metric_type == 'classification':
            # Classification accuracy
            correct = sum(p == a for p, a in zip(predictions, actuals))
            accuracy = correct / len(predictions) if predictions else 0
            
            # Per-class accuracy
            class_accuracy = {}
            for class_name in set(actuals):
                class_preds = [(p, a) for p, a in zip(predictions, actuals) if a == class_name]
                if class_preds:
                    class_correct = sum(p == a for p, a in class_preds)
                    class_accuracy[class_name] = class_correct / len(class_preds)
            
            return {
                'overall_accuracy': accuracy,
                'class_accuracy': class_accuracy,
                'accuracy_score': accuracy
            }
            
        elif metric_type == 'effectiveness':
            # Measure if recommendations improved outcomes
            # This would need actual trading results
            return {
                'effectiveness': 0.75,  # Placeholder - would need actual P&L data
                'accuracy_score': 0.75
            }
    
    def load_historical_data(self, days=30):
        """Load historical predictions and actuals"""
        data = {
            'predictions': [],
            'actuals': [],
            'timestamps': []
        }
        
        # Load prediction history
        history_file = os.path.join(self.predictions_dir, 'prediction_history.json')
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
                
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for entry in history:
                timestamp = datetime.fromisoformat(entry['timestamp'])
                if timestamp >= cutoff_date:
                    data['predictions'].append(entry)
                    data['timestamps'].append(timestamp)
        
        # Load regime reports to get actuals
        for filename in os.listdir(self.results_dir):
            if filename.startswith('regime_report_') and filename.endswith('.json'):
                filepath = os.path.join(self.results_dir, filename)
                with open(filepath, 'r') as f:
                    report = json.load(f)
                    
                timestamp = datetime.fromisoformat(report['timestamp'])
                if timestamp >= cutoff_date:
                    data['actuals'].append(report)
        
        return data
    
    def calculate_improvements(self):
        """Calculate improvement metrics for each tracked metric"""
        improvements = {}
        
        # Load data for different time periods
        periods = {
            'last_24h': 1,
            'last_week': 7,
            'last_month': 30
        }
        
        for period_name, days in periods.items():
            period_data = self.load_historical_data(days)
            
            if not period_data['predictions']:
                continue
                
            # Calculate metrics for each tracked metric
            for metric_key, metric_config in self.metrics_config.items():
                metric_improvements = self._calculate_metric_improvement(
                    metric_key, 
                    metric_config, 
                    period_data
                )
                
                if metric_key not in improvements:
                    improvements[metric_key] = {}
                    
                improvements[metric_key][period_name] = metric_improvements
        
        # Calculate trend (improving/declining)
        for metric_key in improvements:
            if 'last_week' in improvements[metric_key] and 'last_month' in improvements[metric_key]:
                week_score = improvements[metric_key]['last_week'].get('accuracy_score', 0)
                month_score = improvements[metric_key]['last_month'].get('accuracy_score', 0)
                
                improvements[metric_key]['trend'] = {
                    'direction': 'improving' if week_score > month_score else 'declining',
                    'change': week_score - month_score
                }
        
        return improvements
    
    def _calculate_metric_improvement(self, metric_key, metric_config, period_data):
        """Calculate improvement for a specific metric"""
        predictions = []
        actuals = []
        
        # Extract relevant data based on metric
        for pred in period_data['predictions']:
            if metric_key == 'regime_prediction' and 'predicted_regime' in pred:
                predictions.append(pred['predicted_regime'])
            elif metric_key == 'market_score' and 'features' in pred:
                # Predicted market score would be in features
                predictions.append(pred['features'].get('market_score', 0))
            # Add more metric extractions as needed
        
        # Match with actuals
        for actual in period_data['actuals']:
            if metric_key == 'regime_prediction':
                actuals.append(actual['market_regime']['regime'])
            elif metric_key == 'market_score':
                actuals.append(actual['trend_analysis'].get('market_score', 0))
            # Add more actual extractions
        
        # Ensure equal length
        min_len = min(len(predictions), len(actuals))
        predictions = predictions[:min_len]
        actuals = actuals[:min_len]
        
        if predictions and actuals:
            return self.calculate_metric_accuracy(
                metric_config['type'], 
                predictions, 
                actuals
            )
        
        return {'accuracy_score': 0, 'no_data': True}
    
    def generate_improvement_report(self):
        """Generate comprehensive improvement report"""
        improvements = self.calculate_improvements()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'improving_metrics': [],
                'declining_metrics': [],
                'stable_metrics': []
            },
            'detailed_metrics': improvements,
            'recommendations': []
        }
        
        # Categorize metrics
        for metric_key, metric_data in improvements.items():
            if 'trend' in metric_data:
                if metric_data['trend']['change'] > 0.05:
                    report['summary']['improving_metrics'].append({
                        'metric': self.metrics_config[metric_key]['name'],
                        'improvement': f"+{metric_data['trend']['change']:.1%}"
                    })
                elif metric_data['trend']['change'] < -0.05:
                    report['summary']['declining_metrics'].append({
                        'metric': self.metrics_config[metric_key]['name'],
                        'decline': f"{metric_data['trend']['change']:.1%}"
                    })
                else:
                    report['summary']['stable_metrics'].append(
                        self.metrics_config[metric_key]['name']
                    )
        
        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(improvements)
        
        # Save report
        report_file = os.path.join(
            self.metrics_dir,
            f"improvement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        return report
    
    def _generate_recommendations(self, improvements):
        """Generate recommendations based on metric performance"""
        recommendations = []
        
        for metric_key, metric_data in improvements.items():
            if 'trend' not in metric_data:
                continue
                
            metric_name = self.metrics_config[metric_key]['name']
            
            if metric_data['trend']['direction'] == 'declining':
                change = abs(metric_data['trend']['change'])
                
                if change > 0.1:
                    recommendations.append({
                        'priority': 'HIGH',
                        'metric': metric_name,
                        'issue': f"Significant decline of {change:.1%}",
                        'action': f"Review and retrain {metric_key} model components"
                    })
                elif change > 0.05:
                    recommendations.append({
                        'priority': 'MEDIUM',
                        'metric': metric_name,
                        'issue': f"Moderate decline of {change:.1%}",
                        'action': f"Monitor {metric_key} closely, consider parameter tuning"
                    })
        
        return recommendations
    
    def visualize_improvements(self):
        """Create visualization of metric improvements"""
        improvements = self.calculate_improvements()
        
        # Create subplots for each metric
        n_metrics = len(self.metrics_config)
        fig, axes = plt.subplots(
            nrows=(n_metrics + 1) // 2, 
            ncols=2, 
            figsize=(15, 5 * ((n_metrics + 1) // 2))
        )
        axes = axes.flatten()
        
        for idx, (metric_key, metric_config) in enumerate(self.metrics_config.items()):
            ax = axes[idx]
            
            # Prepare data for visualization
            periods = ['last_24h', 'last_week', 'last_month']
            scores = []
            
            for period in periods:
                if metric_key in improvements and period in improvements[metric_key]:
                    score = improvements[metric_key][period].get('accuracy_score', 0)
                    scores.append(score * 100)  # Convert to percentage
                else:
                    scores.append(0)
            
            # Create bar chart
            bars = ax.bar(periods, scores, color=['#2ecc71', '#3498db', '#9b59b6'])
            ax.set_title(metric_config['name'], fontsize=12, fontweight='bold')
            ax.set_ylabel('Accuracy (%)')
            ax.set_ylim(0, 100)
            
            # Add value labels
            for bar, score in zip(bars, scores):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{score:.1f}%', ha='center', va='bottom')
            
            # Add trend indicator
            if metric_key in improvements and 'trend' in improvements[metric_key]:
                trend = improvements[metric_key]['trend']
                color = 'green' if trend['direction'] == 'improving' else 'red'
                symbol = '↑' if trend['direction'] == 'improving' else '↓'
                ax.text(0.95, 0.95, f"{symbol} {abs(trend['change']):.1%}",
                       transform=ax.transAxes, ha='right', va='top',
                       color=color, fontsize=14, fontweight='bold')
        
        # Remove empty subplots
        for idx in range(len(self.metrics_config), len(axes)):
            fig.delaxes(axes[idx])
        
        plt.suptitle('Market Regime Metrics - Improvement Tracking', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save visualization
        viz_file = os.path.join(
            self.metrics_dir,
            f"improvement_viz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        plt.savefig(viz_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return viz_file
    
    def create_performance_dashboard(self):
        """Create HTML dashboard for metric improvements"""
        improvements = self.calculate_improvements()
        report = self.generate_improvement_report()
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Market Regime - Metrics Improvement Dashboard</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .metric-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #007bff;
        }}
        .improving {{ border-left-color: #28a745; }}
        .declining {{ border-left-color: #dc3545; }}
        .stable {{ border-left-color: #6c757d; }}
        .metric-name {{
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 10px;
        }}
        .accuracy-score {{
            font-size: 36px;
            font-weight: bold;
            color: #007bff;
        }}
        .trend {{
            font-size: 24px;
            margin-left: 10px;
        }}
        .trend.up {{ color: #28a745; }}
        .trend.down {{ color: #dc3545; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .recommendation {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
        }}
        .recommendation.high {{
            background: #f8d7da;
            border-color: #dc3545;
        }}
        h1, h2 {{
            color: #333;
        }}
        .timestamp {{
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Market Regime Metrics - Improvement Tracking</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Improving Metrics:</strong> {len(report['summary']['improving_metrics'])}</p>
            <p><strong>Declining Metrics:</strong> {len(report['summary']['declining_metrics'])}</p>
            <p><strong>Stable Metrics:</strong> {len(report['summary']['stable_metrics'])}</p>
        </div>
        
        <h2>Metric Performance</h2>
        <div class="grid">
"""
        
        # Add metric cards
        for metric_key, metric_config in self.metrics_config.items():
            if metric_key not in improvements:
                continue
                
            # Get latest accuracy
            latest_accuracy = 0
            trend_class = 'stable'
            trend_symbol = ''
            trend_value = ''
            
            if 'last_24h' in improvements[metric_key]:
                latest_accuracy = improvements[metric_key]['last_24h'].get('accuracy_score', 0) * 100
            
            if 'trend' in improvements[metric_key]:
                trend = improvements[metric_key]['trend']
                if trend['direction'] == 'improving':
                    trend_class = 'improving'
                    trend_symbol = '↑'
                    trend_value = f"+{trend['change']:.1%}"
                else:
                    trend_class = 'declining'
                    trend_symbol = '↓'
                    trend_value = f"{trend['change']:.1%}"
            
            html_content += f"""
            <div class="metric-card {trend_class}">
                <div class="metric-name">{metric_config['name']}</div>
                <div>
                    <span class="accuracy-score">{latest_accuracy:.1f}%</span>
                    <span class="trend {'up' if trend_class == 'improving' else 'down'}">{trend_symbol} {trend_value}</span>
                </div>
                <div style="margin-top: 10px; font-size: 14px; color: #666;">
                    Type: {metric_config['type'].title()}
                </div>
            </div>
"""
        
        html_content += """
        </div>
        
        <h2>Recommendations</h2>
"""
        
        # Add recommendations
        if report['recommendations']:
            for rec in report['recommendations']:
                priority_class = 'high' if rec['priority'] == 'HIGH' else ''
                html_content += f"""
                <div class="recommendation {priority_class}">
                    <strong>[{rec['priority']}] {rec['metric']}</strong><br>
                    Issue: {rec['issue']}<br>
                    Action: {rec['action']}
                </div>
"""
        else:
            html_content += "<p>No specific recommendations at this time. All metrics performing well!</p>"
        
        html_content += """
    </div>
</body>
</html>
"""
        
        # Save dashboard
        dashboard_file = os.path.join(
            self.metrics_dir,
            "metrics_improvement_dashboard.html"
        )
        
        with open(dashboard_file, 'w') as f:
            f.write(html_content)
            
        return dashboard_file


def main():
    """Run metrics improvement analysis"""
    tracker = MetricsTracker()
    
    print("Market Regime Metrics Improvement Tracker")
    print("=" * 50)
    
    # Generate improvement report
    print("\nGenerating improvement report...")
    report = tracker.generate_improvement_report()
    
    print(f"\nSummary:")
    print(f"- Improving: {len(report['summary']['improving_metrics'])} metrics")
    print(f"- Declining: {len(report['summary']['declining_metrics'])} metrics")
    print(f"- Stable: {len(report['summary']['stable_metrics'])} metrics")
    
    # Show improving metrics
    if report['summary']['improving_metrics']:
        print("\nImproving Metrics:")
        for metric in report['summary']['improving_metrics']:
            print(f"  ✓ {metric['metric']}: {metric['improvement']}")
    
    # Show declining metrics
    if report['summary']['declining_metrics']:
        print("\nDeclining Metrics:")
        for metric in report['summary']['declining_metrics']:
            print(f"  ✗ {metric['metric']}: {metric['decline']}")
    
    # Create visualization
    print("\nCreating visualization...")
    viz_file = tracker.visualize_improvements()
    print(f"Visualization saved: {viz_file}")
    
    # Create dashboard
    print("\nCreating HTML dashboard...")
    dashboard_file = tracker.create_performance_dashboard()
    print(f"Dashboard saved: {dashboard_file}")
    
    # Show recommendations
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"\n[{rec['priority']}] {rec['metric']}")
            print(f"  Issue: {rec['issue']}")
            print(f"  Action: {rec['action']}")
    
    print("\n" + "=" * 50)
    print("Analysis complete!")


if __name__ == "__main__":
    main()