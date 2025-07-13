#!/usr/bin/env python3
"""
Calculate Daily ML Metrics for Market Regime Model

Comprehensive daily metrics including MAE, RMSE, accuracy, precision, and more.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score
import warnings
warnings.filterwarnings('ignore')

class DailyMetricsCalculator:
    """Calculate comprehensive daily metrics for regime model"""
    
    def __init__(self):
        self.db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
        self.reports_dir = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/reports"
        self.output_dir = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/ML_Measure"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def load_today_predictions(self):
        """Load predictions from the last 24 hours"""
        conn = sqlite3.connect(self.db_path)
        
        # Get predictions from last 24 hours
        query = """
        SELECT timestamp, regime, confidence, market_score, 
               volatility_score, trend_score, momentum_score,
               breadth_score, scanner_volatility_score
        FROM predictions
        WHERE datetime(timestamp) >= datetime('now', '-24 hours')
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def calculate_mae_metrics(self, df):
        """Calculate various MAE metrics"""
        metrics = {}
        
        # 1. Prediction Stability MAE (consecutive prediction changes)
        for col in ['confidence', 'market_score', 'volatility_score', 'trend_score', 'momentum_score']:
            if col in df.columns:
                changes = df[col].diff().abs().dropna()
                metrics[f'{col}_stability_mae'] = changes.mean()
        
        # 2. Cross-indicator consistency MAE
        if 'market_score' in df.columns and 'trend_score' in df.columns:
            # Market score should correlate with trend score
            expected_market = df['trend_score'] * 0.3 + df['momentum_score'] * 0.3
            metrics['market_score_consistency_mae'] = np.mean(np.abs(df['market_score'] - expected_market))
        
        return metrics
    
    def calculate_rmse_metrics(self, df):
        """Calculate Root Mean Square Error metrics"""
        metrics = {}
        
        # RMSE for prediction changes
        for col in ['confidence', 'market_score', 'volatility_score']:
            if col in df.columns:
                changes = df[col].diff().dropna()
                metrics[f'{col}_stability_rmse'] = np.sqrt(np.mean(changes ** 2))
        
        return metrics
    
    def calculate_accuracy_metrics(self, df):
        """Calculate accuracy-related metrics"""
        metrics = {}
        
        # 1. Regime consistency accuracy
        if len(df) > 1:
            # Count how often regime stays the same
            regime_consistent = (df['regime'] == df['regime'].shift(1)).sum()
            metrics['regime_consistency_rate'] = regime_consistent / (len(df) - 1)
        
        # 2. High confidence accuracy (confidence > 0.7 should mean stable regime)
        high_conf_mask = df['confidence'] > 0.7
        if high_conf_mask.sum() > 0:
            high_conf_df = df[high_conf_mask]
            if len(high_conf_df) > 1:
                stable_high_conf = (high_conf_df['regime'] == high_conf_df['regime'].shift(1)).sum()
                metrics['high_confidence_stability'] = stable_high_conf / (len(high_conf_df) - 1)
        
        # 3. Regime distribution entropy (lower = more decisive)
        regime_counts = df['regime'].value_counts()
        regime_probs = regime_counts / len(df)
        entropy = -np.sum(regime_probs * np.log2(regime_probs + 1e-10))
        metrics['regime_entropy'] = entropy
        
        return metrics
    
    def calculate_volatility_metrics(self, df):
        """Calculate volatility-specific metrics"""
        metrics = {}
        
        if 'scanner_volatility_score' in df.columns and 'volatility_score' in df.columns:
            # Correlation between scanner and calculated volatility
            correlation = df['scanner_volatility_score'].corr(df['volatility_score'])
            metrics['scanner_vs_calc_volatility_corr'] = correlation
            
            # MAE between scanner and calculated volatility
            mae = np.mean(np.abs(df['scanner_volatility_score'] - df['volatility_score']))
            metrics['scanner_vs_calc_volatility_mae'] = mae
        
        return metrics
    
    def calculate_prediction_quality_metrics(self, df):
        """Calculate metrics related to prediction quality"""
        metrics = {}
        
        # 1. Confidence calibration (average confidence vs actual stability)
        avg_confidence = df['confidence'].mean()
        metrics['average_confidence'] = avg_confidence
        
        # 2. Prediction decisiveness (how often we're in neutral vs strong regimes)
        regime_strengths = {
            'strong_bull': 1.0,
            'bull': 0.7,
            'neutral': 0.3,
            'bear': 0.7,
            'strong_bear': 1.0
        }
        
        df['regime_strength'] = df['regime'].map(regime_strengths).fillna(0.3)
        metrics['average_decisiveness'] = df['regime_strength'].mean()
        
        # 3. Signal clarity (spread between different scores)
        score_cols = ['market_score', 'trend_score', 'momentum_score', 'breadth_score']
        available_scores = [col for col in score_cols if col in df.columns]
        
        if len(available_scores) >= 2:
            score_spreads = []
            for i in range(len(df)):
                scores = [df.iloc[i][col] for col in available_scores if pd.notna(df.iloc[i][col])]
                if len(scores) >= 2:
                    spread = np.max(scores) - np.min(scores)
                    score_spreads.append(spread)
            
            if score_spreads:
                metrics['average_signal_spread'] = np.mean(score_spreads)
        
        return metrics
    
    def calculate_trend_metrics(self, df):
        """Calculate trend-following metrics"""
        metrics = {}
        
        # Trend consistency over the day
        if 'trend_score' in df.columns:
            # Count trend direction changes
            trend_signs = np.sign(df['trend_score'])
            direction_changes = (trend_signs != trend_signs.shift(1)).sum() - 1
            metrics['trend_direction_changes'] = direction_changes
            metrics['trend_consistency_rate'] = 1 - (direction_changes / max(len(df) - 1, 1))
        
        return metrics
    
    def generate_insights(self, all_metrics):
        """Generate actionable insights from metrics"""
        insights = []
        
        # MAE insights
        avg_mae = np.mean([v for k, v in all_metrics.items() if 'mae' in k and v is not None])
        if avg_mae < 0.1:
            insights.append("✅ Excellent prediction stability (MAE < 0.1)")
        elif avg_mae < 0.2:
            insights.append("👍 Good prediction stability (MAE < 0.2)")
        else:
            insights.append("⚠️ High prediction variability (MAE > 0.2)")
        
        # Confidence insights
        if 'average_confidence' in all_metrics:
            conf = all_metrics['average_confidence']
            if conf > 0.8:
                insights.append(f"💪 High average confidence ({conf:.1%})")
            elif conf < 0.5:
                insights.append(f"⚠️ Low average confidence ({conf:.1%})")
        
        # Regime consistency
        if 'regime_consistency_rate' in all_metrics:
            consistency = all_metrics['regime_consistency_rate']
            if consistency > 0.9:
                insights.append(f"🎯 Very stable regime detection ({consistency:.1%})")
            elif consistency < 0.7:
                insights.append(f"🔄 Frequent regime changes ({consistency:.1%})")
        
        # Volatility correlation
        if 'scanner_vs_calc_volatility_corr' in all_metrics:
            corr = all_metrics['scanner_vs_calc_volatility_corr']
            if abs(corr) > 0.7:
                insights.append(f"✅ Strong scanner/calc volatility correlation ({corr:.2f})")
            else:
                insights.append(f"⚠️ Weak scanner/calc volatility correlation ({corr:.2f})")
        
        return insights
    
    def create_daily_report(self):
        """Create comprehensive daily metrics report"""
        print("=" * 60)
        print("MARKET REGIME MODEL - DAILY METRICS REPORT")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # Load data
        df = self.load_today_predictions()
        
        if len(df) < 5:
            print("Insufficient data for today's analysis")
            return None
        
        print(f"\nTotal predictions today: {len(df)}")
        print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        all_metrics = {}
        
        # Calculate all metrics
        print("\n1. MAE METRICS")
        print("-" * 40)
        mae_metrics = self.calculate_mae_metrics(df)
        all_metrics.update(mae_metrics)
        for metric, value in mae_metrics.items():
            print(f"{metric}: {value:.4f}")
        
        print("\n2. RMSE METRICS")
        print("-" * 40)
        rmse_metrics = self.calculate_rmse_metrics(df)
        all_metrics.update(rmse_metrics)
        for metric, value in rmse_metrics.items():
            print(f"{metric}: {value:.4f}")
        
        print("\n3. ACCURACY METRICS")
        print("-" * 40)
        accuracy_metrics = self.calculate_accuracy_metrics(df)
        all_metrics.update(accuracy_metrics)
        for metric, value in accuracy_metrics.items():
            if 'rate' in metric or 'stability' in metric:
                print(f"{metric}: {value:.1%}")
            else:
                print(f"{metric}: {value:.4f}")
        
        print("\n4. VOLATILITY METRICS")
        print("-" * 40)
        vol_metrics = self.calculate_volatility_metrics(df)
        all_metrics.update(vol_metrics)
        for metric, value in vol_metrics.items():
            print(f"{metric}: {value:.4f}")
        
        print("\n5. PREDICTION QUALITY")
        print("-" * 40)
        quality_metrics = self.calculate_prediction_quality_metrics(df)
        all_metrics.update(quality_metrics)
        for metric, value in quality_metrics.items():
            print(f"{metric}: {value:.4f}")
        
        print("\n6. TREND METRICS")
        print("-" * 40)
        trend_metrics = self.calculate_trend_metrics(df)
        all_metrics.update(trend_metrics)
        for metric, value in trend_metrics.items():
            if 'rate' in metric:
                print(f"{metric}: {value:.1%}")
            else:
                print(f"{metric}: {value}")
        
        # Generate insights
        insights = self.generate_insights(all_metrics)
        
        print("\n7. KEY INSIGHTS")
        print("-" * 40)
        for insight in insights:
            print(f"  {insight}")
        
        # Calculate aggregate scores
        mae_values = [v for k, v in all_metrics.items() if 'mae' in k and v is not None]
        rmse_values = [v for k, v in all_metrics.items() if 'rmse' in k and v is not None]
        
        aggregate_mae = np.mean(mae_values) if mae_values else None
        aggregate_rmse = np.mean(rmse_values) if rmse_values else None
        
        print("\n8. AGGREGATE SCORES")
        print("-" * 40)
        if aggregate_mae:
            print(f"Overall MAE: {aggregate_mae:.4f}")
        if aggregate_rmse:
            print(f"Overall RMSE: {aggregate_rmse:.4f}")
        
        # Save report
        report = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'predictions_count': int(len(df)),
            'metrics': {k: float(v) if isinstance(v, (np.int64, np.float64)) else v 
                       for k, v in all_metrics.items()},
            'aggregate_mae': float(aggregate_mae) if aggregate_mae else None,
            'aggregate_rmse': float(aggregate_rmse) if aggregate_rmse else None,
            'insights': insights,
            'regime_distribution': {k: int(v) for k, v in df['regime'].value_counts().to_dict().items()}
        }
        
        # Save to JSON
        filename = f"daily_metrics_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nReport saved to: {filepath}")
        
        # Also save as latest
        latest_path = os.path.join(self.output_dir, "daily_metrics_latest.json")
        with open(latest_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

def main():
    """Run daily metrics calculation"""
    calculator = DailyMetricsCalculator()
    report = calculator.create_daily_report()
    
    print("\n" + "=" * 60)
    print("DAILY METRICS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()