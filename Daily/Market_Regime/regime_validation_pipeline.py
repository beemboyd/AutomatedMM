#!/usr/bin/env python3
"""
Regime Validation Pipeline
Validates predictions against actual outcomes and tracks performance
Part of Phase 2: Restore Learning
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import Counter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RegimeValidationPipeline:
    """Pipeline for validating regime predictions"""
    
    def __init__(self):
        # Database paths
        self.predictions_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
        self.feedback_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
        
        # Performance thresholds
        self.min_feedback_coverage = 0.80  # 80% of predictions should have feedback
        self.min_regime_representation = 0.10  # Each regime should be at least 10% of data
        self.min_accuracy_threshold = 0.70  # Minimum 70% accuracy for validation
        
        # Regime categories
        self.all_regimes = [
            'strong_bullish', 'choppy_bullish', 'sideways',
            'choppy_bearish', 'strong_bearish',
            'volatile_bullish', 'volatile_bearish'
        ]
        
    def validate_feedback_coverage(self, hours=24):
        """Validate that sufficient predictions have feedback"""
        try:
            # Get prediction count
            conn_pred = sqlite3.connect(self.predictions_db)
            cursor_pred = conn_pred.cursor()
            
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor_pred.execute(
                "SELECT COUNT(*) FROM predictions WHERE timestamp > ?",
                (cutoff,)
            )
            total_predictions = cursor_pred.fetchone()[0]
            conn_pred.close()
            
            # Get feedback count
            conn_fb = sqlite3.connect(self.feedback_db)
            cursor_fb = conn_fb.cursor()
            
            cursor_fb.execute(
                "SELECT COUNT(*) FROM regime_feedback WHERE prediction_timestamp > ?",
                (cutoff,)
            )
            total_feedback = cursor_fb.fetchone()[0]
            conn_fb.close()
            
            if total_predictions > 0:
                coverage = total_feedback / total_predictions
                logger.info(f"Feedback Coverage: {coverage:.2%} ({total_feedback}/{total_predictions})")
                
                return {
                    'coverage': coverage,
                    'total_predictions': total_predictions,
                    'total_feedback': total_feedback,
                    'meets_threshold': coverage >= self.min_feedback_coverage,
                    'threshold': self.min_feedback_coverage
                }
            else:
                return {
                    'coverage': 0,
                    'total_predictions': 0,
                    'total_feedback': 0,
                    'meets_threshold': False,
                    'threshold': self.min_feedback_coverage
                }
                
        except Exception as e:
            logger.error(f"Error validating feedback coverage: {str(e)}")
            return None
            
    def validate_regime_distribution(self, hours=24):
        """Validate that all regimes are represented in feedback"""
        try:
            conn = sqlite3.connect(self.feedback_db)
            cursor = conn.cursor()
            
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Get actual regime distribution
            cursor.execute('''
                SELECT actual_regime, COUNT(*) as count
                FROM regime_feedback
                WHERE feedback_timestamp > ?
                GROUP BY actual_regime
            ''', (cutoff,))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return {
                    'balanced': False,
                    'distribution': {},
                    'missing_regimes': self.all_regimes,
                    'underrepresented': self.all_regimes
                }
                
            # Calculate distribution
            total = sum(r[1] for r in results)
            distribution = {r[0]: r[1]/total for r in results}
            
            # Find missing and underrepresented regimes
            missing_regimes = [r for r in self.all_regimes if r not in distribution]
            underrepresented = [r for r in distribution 
                              if distribution[r] < self.min_regime_representation]
            
            balanced = len(missing_regimes) == 0 and len(underrepresented) <= 2
            
            logger.info(f"Regime Distribution: {distribution}")
            if missing_regimes:
                logger.warning(f"Missing regimes: {missing_regimes}")
            if underrepresented:
                logger.warning(f"Underrepresented regimes: {underrepresented}")
                
            return {
                'balanced': balanced,
                'distribution': distribution,
                'missing_regimes': missing_regimes,
                'underrepresented': underrepresented,
                'total_samples': total
            }
            
        except Exception as e:
            logger.error(f"Error validating regime distribution: {str(e)}")
            return None
            
    def calculate_confusion_matrix(self, hours=24):
        """Calculate confusion matrix for predictions"""
        try:
            conn = sqlite3.connect(self.feedback_db)
            
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Get all feedback data
            df = pd.read_sql_query('''
                SELECT predicted_regime, actual_regime, price_change_pct
                FROM regime_feedback
                WHERE feedback_timestamp > ?
            ''', conn, params=(cutoff,))
            
            conn.close()
            
            if df.empty:
                return None
                
            # Create confusion matrix
            confusion_matrix = pd.crosstab(
                df['predicted_regime'], 
                df['actual_regime'],
                margins=True
            )
            
            # Calculate per-regime accuracy
            regime_accuracy = {}
            for regime in self.all_regimes:
                if regime in df['predicted_regime'].values:
                    correct = df[(df['predicted_regime'] == regime) & 
                                (df['actual_regime'] == regime)].shape[0]
                    total = df[df['predicted_regime'] == regime].shape[0]
                    regime_accuracy[regime] = correct / total if total > 0 else 0
                    
            return {
                'confusion_matrix': confusion_matrix.to_dict(),
                'regime_accuracy': regime_accuracy,
                'overall_accuracy': (df['predicted_regime'] == df['actual_regime']).mean()
            }
            
        except Exception as e:
            logger.error(f"Error calculating confusion matrix: {str(e)}")
            return None
            
    def validate_prediction_quality(self, hours=24):
        """Comprehensive validation of prediction quality"""
        try:
            conn = sqlite3.connect(self.feedback_db)
            
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            # Get feedback data
            df = pd.read_sql_query('''
                SELECT 
                    predicted_regime,
                    actual_regime,
                    predicted_confidence,
                    price_change_pct,
                    volatility,
                    feedback_timestamp
                FROM regime_feedback
                WHERE feedback_timestamp > ?
            ''', conn, params=(cutoff,))
            
            conn.close()
            
            if df.empty:
                return {
                    'valid': False,
                    'reason': 'No feedback data available'
                }
                
            # Calculate metrics
            total_predictions = len(df)
            correct_predictions = (df['predicted_regime'] == df['actual_regime']).sum()
            accuracy = correct_predictions / total_predictions
            
            # Confidence calibration - are high confidence predictions more accurate?
            high_conf = df[df['predicted_confidence'] > 0.7]
            high_conf_accuracy = (high_conf['predicted_regime'] == high_conf['actual_regime']).mean() if len(high_conf) > 0 else 0
            
            # Price movement correlation - do bullish predictions correlate with positive moves?
            bullish_preds = df[df['predicted_regime'].str.contains('bullish')]
            bullish_correlation = bullish_preds['price_change_pct'].mean() if len(bullish_preds) > 0 else 0
            
            bearish_preds = df[df['predicted_regime'].str.contains('bearish')]
            bearish_correlation = bearish_preds['price_change_pct'].mean() if len(bearish_preds) > 0 else 0
            
            # Determine if predictions are valid
            valid = (
                accuracy >= self.min_accuracy_threshold and
                high_conf_accuracy >= accuracy and  # High confidence should be more accurate
                bullish_correlation > 0 and  # Bullish predictions should have positive price moves
                bearish_correlation < 0  # Bearish predictions should have negative price moves
            )
            
            quality_report = {
                'valid': valid,
                'total_predictions': total_predictions,
                'correct_predictions': correct_predictions,
                'accuracy': accuracy,
                'high_confidence_accuracy': high_conf_accuracy,
                'confidence_calibrated': high_conf_accuracy >= accuracy,
                'bullish_correlation': bullish_correlation,
                'bearish_correlation': bearish_correlation,
                'directional_accuracy': bullish_correlation > 0 and bearish_correlation < 0
            }
            
            logger.info(f"Prediction Quality - Accuracy: {accuracy:.2%}, Valid: {valid}")
            
            return quality_report
            
        except Exception as e:
            logger.error(f"Error validating prediction quality: {str(e)}")
            return None
            
    def generate_validation_report(self, hours=24):
        """Generate comprehensive validation report"""
        try:
            logger.info(f"Generating validation report for last {hours} hours")
            
            # Run all validations
            coverage = self.validate_feedback_coverage(hours)
            distribution = self.validate_regime_distribution(hours)
            confusion = self.calculate_confusion_matrix(hours)
            quality = self.validate_prediction_quality(hours)
            
            # Compile report
            report = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'period_hours': hours,
                'feedback_coverage': coverage,
                'regime_distribution': distribution,
                'confusion_matrix': confusion,
                'prediction_quality': quality,
                'overall_status': 'READY' if all([
                    coverage and coverage['meets_threshold'],
                    distribution and distribution['balanced'],
                    quality and quality['valid']
                ]) else 'NOT_READY'
            }
            
            # Save report
            report_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/validation_reports/validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
                
            logger.info(f"Validation report saved to {report_path}")
            logger.info(f"Overall Status: {report['overall_status']}")
            
            # Print summary
            print("\n" + "="*50)
            print("REGIME VALIDATION REPORT")
            print("="*50)
            
            if coverage:
                print(f"Feedback Coverage: {coverage['coverage']:.1%} ({coverage['total_feedback']}/{coverage['total_predictions']})")
                print(f"  ✓ Meets threshold" if coverage['meets_threshold'] else f"  ✗ Below threshold ({self.min_feedback_coverage:.0%})")
                
            if distribution:
                print(f"\nRegime Distribution:")
                for regime, pct in distribution['distribution'].items():
                    print(f"  {regime:20s}: {pct:6.1%}")
                if distribution['missing_regimes']:
                    print(f"  Missing: {', '.join(distribution['missing_regimes'])}")
                    
            if quality:
                print(f"\nPrediction Quality:")
                print(f"  Overall Accuracy: {quality['accuracy']:.1%} ({quality['correct_predictions']}/{quality['total_predictions']})")
                print(f"  High Conf Accuracy: {quality['high_confidence_accuracy']:.1%}")
                print(f"  Directional Accuracy: {'✓' if quality['directional_accuracy'] else '✗'}")
                
            print(f"\nOVERALL STATUS: {report['overall_status']}")
            print("="*50)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating validation report: {str(e)}")
            return None
            
    def check_readiness_for_retraining(self):
        """Check if system is ready for Phase 3 retraining"""
        report = self.generate_validation_report(hours=24)
        
        if not report:
            return False, "Could not generate validation report"
            
        if report['overall_status'] != 'READY':
            reasons = []
            
            if not report['feedback_coverage']['meets_threshold']:
                reasons.append(f"Insufficient feedback coverage ({report['feedback_coverage']['coverage']:.1%})")
                
            if not report['regime_distribution']['balanced']:
                reasons.append("Imbalanced regime distribution")
                
            if not report['prediction_quality']['valid']:
                reasons.append(f"Low prediction accuracy ({report['prediction_quality']['accuracy']:.1%})")
                
            return False, "; ".join(reasons)
            
        return True, "System ready for retraining"


def main():
    """Main function for testing"""
    pipeline = RegimeValidationPipeline()
    
    # Generate validation report
    report = pipeline.generate_validation_report(hours=24)
    
    # Check readiness for retraining
    ready, message = pipeline.check_readiness_for_retraining()
    print(f"\nRetraining Readiness: {ready}")
    print(f"Message: {message}")


if __name__ == "__main__":
    main()