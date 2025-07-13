#!/usr/bin/env python
"""
Market Regime Bridge
====================
Bridges the Daily Market_Regime analysis with the main Market_Regime system.
Ensures predictions are saved to the central database and provides outcome tracking.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Daily', 'Market_Regime'))

from core.regime_detector import RegimeDetector
from learning.adaptive_learner import AdaptiveLearner
from market_regime_analyzer import MarketRegimeAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketRegimeBridge:
    """Bridges Daily analysis with main Market Regime system"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(self.base_dir, 'data', 'regime_learning.db')
        
        # Initialize components
        self.daily_analyzer = MarketRegimeAnalyzer()
        self.regime_detector = RegimeDetector()
        self.adaptive_learner = AdaptiveLearner()
        
    def run_integrated_analysis(self):
        """Run integrated market regime analysis"""
        logger.info("Running integrated market regime analysis...")
        
        try:
            # 1. Run Daily analysis
            daily_report = self.daily_analyzer.generate_regime_report()
            
            if not daily_report:
                logger.error("Failed to generate daily report")
                return None
                
            # 2. Run main regime detection
            main_regime = self.regime_detector.detect_regime()
            
            # 3. Compare and reconcile regimes
            daily_regime = daily_report['market_regime']['regime']
            reconciled_regime = self._reconcile_regimes(daily_regime, main_regime['regime'])
            
            # 4. Save integrated analysis
            integrated_report = {
                'timestamp': datetime.now().isoformat(),
                'daily_analysis': {
                    'regime': daily_regime,
                    'counts': daily_report['reversal_counts'],
                    'trend': daily_report['trend_analysis'],
                    'prediction': daily_report.get('prediction')
                },
                'main_analysis': {
                    'regime': main_regime['regime'],
                    'confidence': main_regime['confidence'],
                    'indicators': main_regime.get('indicators', {})
                },
                'reconciled_regime': reconciled_regime,
                'insights': self._generate_integrated_insights(daily_report, main_regime)
            }
            
            # 5. Save to database
            self._save_integrated_analysis(integrated_report)
            
            # 6. Track outcomes of previous predictions
            self._track_prediction_outcomes()
            
            # 7. Update adaptive learner
            self.adaptive_learner.learn_from_outcome(
                regime=reconciled_regime['regime'],
                confidence=reconciled_regime['confidence'],
                indicators=integrated_report
            )
            
            return integrated_report
            
        except Exception as e:
            logger.error(f"Error in integrated analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def _reconcile_regimes(self, daily_regime, main_regime):
        """Reconcile regimes from different sources"""
        # Map daily regimes to main regime format
        regime_mapping = {
            'strong_uptrend': 'STRONG_BULL',
            'uptrend': 'BULLISH',
            'choppy_bullish': 'NEUTRAL_BULLISH',
            'choppy': 'NEUTRAL',
            'choppy_bearish': 'NEUTRAL_BEARISH',
            'downtrend': 'BEARISH',
            'strong_downtrend': 'STRONG_BEAR'
        }
        
        mapped_daily = regime_mapping.get(daily_regime, 'NEUTRAL')
        
        # If regimes match, high confidence
        if mapped_daily == main_regime:
            return {
                'regime': main_regime,
                'confidence': 0.9,
                'source': 'consensus'
            }
        
        # If regimes are adjacent, use weighted average
        regime_order = ['STRONG_BEAR', 'BEARISH', 'NEUTRAL_BEARISH', 'NEUTRAL', 
                       'NEUTRAL_BULLISH', 'BULLISH', 'STRONG_BULL']
        
        daily_idx = regime_order.index(mapped_daily)
        main_idx = regime_order.index(main_regime)
        
        if abs(daily_idx - main_idx) == 1:
            # Adjacent regimes - average them
            avg_idx = int((daily_idx + main_idx) / 2)
            return {
                'regime': regime_order[avg_idx],
                'confidence': 0.7,
                'source': 'averaged'
            }
        
        # If regimes differ significantly, use main regime but lower confidence
        return {
            'regime': main_regime,
            'confidence': 0.5,
            'source': 'main_system',
            'disagreement': f'Daily: {mapped_daily}, Main: {main_regime}'
        }
        
    def _generate_integrated_insights(self, daily_report, main_regime):
        """Generate insights from integrated analysis"""
        insights = []
        
        # Add daily insights
        if daily_report.get('insights'):
            insights.extend(daily_report['insights'])
            
        # Add prediction insights
        if daily_report.get('prediction'):
            pred = daily_report['prediction']
            insights.append(f"Next regime prediction: {pred['predicted_regime']} "
                          f"(confidence: {pred['confidence']:.1%})")
            
        # Add main system insights
        if main_regime.get('reasoning'):
            insights.append(f"Main system: {main_regime['reasoning']}")
            
        # Add reconciliation insights
        daily_regime = daily_report['market_regime']['regime']
        if self._map_regime(daily_regime) != main_regime['regime']:
            insights.append("⚠️ Regime disagreement between systems - trade with caution")
            
        return insights
        
    def _map_regime(self, daily_regime):
        """Map daily regime to main regime format"""
        mapping = {
            'strong_uptrend': 'STRONG_BULL',
            'uptrend': 'BULLISH',
            'choppy_bullish': 'NEUTRAL_BULLISH',
            'choppy': 'NEUTRAL',
            'choppy_bearish': 'NEUTRAL_BEARISH',
            'downtrend': 'BEARISH',
            'strong_downtrend': 'STRONG_BEAR'
        }
        return mapping.get(daily_regime, 'NEUTRAL')
        
    def _save_integrated_analysis(self, report):
        """Save integrated analysis to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Save to predictions table
            cursor.execute("""
                INSERT INTO predictions 
                (timestamp, regime, confidence, market_score, trend_score, 
                 indicators, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(),
                report['reconciled_regime']['regime'],
                report['reconciled_regime']['confidence'],
                report['daily_analysis']['counts']['long'] / max(1, report['daily_analysis']['counts']['short']),
                report['daily_analysis']['trend'].get('ratio', 1.0) if report['daily_analysis']['trend'].get('ratio') != 'inf' else 5.0,
                json.dumps(report),
                json.dumps(report['insights'])
            ))
            
            # Track if this is a regime change
            cursor.execute("""
                SELECT regime FROM predictions 
                WHERE timestamp < datetime('now') 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            last_regime = cursor.fetchone()
            if last_regime and last_regime[0] != report['reconciled_regime']['regime']:
                cursor.execute("""
                    INSERT INTO regime_changes 
                    (timestamp, from_regime, to_regime, confidence, 
                     trigger_indicators, market_conditions)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now(),
                    last_regime[0],
                    report['reconciled_regime']['regime'],
                    report['reconciled_regime']['confidence'],
                    json.dumps(report['daily_analysis']['counts']),
                    json.dumps(report)
                ))
                
            conn.commit()
            conn.close()
            logger.info("Saved integrated analysis to database")
            
        except Exception as e:
            logger.error(f"Error saving integrated analysis: {e}")
            
    def _track_prediction_outcomes(self):
        """Track outcomes of previous predictions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get predictions from 1-4 hours ago that need outcome tracking
            cursor.execute("""
                SELECT id, predicted_regime, confidence, timestamp
                FROM regime_predictions
                WHERE datetime(timestamp) BETWEEN datetime('now', '-4 hours') 
                                              AND datetime('now', '-1 hours')
                  AND actual_regime IS NULL
            """)
            
            predictions_to_update = cursor.fetchall()
            
            for pred_id, predicted_regime, confidence, timestamp in predictions_to_update:
                # Get actual regime around that time
                cursor.execute("""
                    SELECT regime FROM predictions
                    WHERE datetime(timestamp) BETWEEN datetime(?, '-30 minutes') 
                                                 AND datetime(?, '+30 minutes')
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (timestamp, timestamp))
                
                actual_result = cursor.fetchone()
                if actual_result:
                    actual_regime = self._reverse_map_regime(actual_result[0])
                    
                    # Update prediction with actual outcome
                    cursor.execute("""
                        UPDATE regime_predictions
                        SET actual_regime = ?,
                            outcome_score = ?,
                            feedback_timestamp = ?
                        WHERE id = ?
                    """, (
                        actual_regime,
                        confidence if predicted_regime == actual_regime else -confidence,
                        datetime.now(),
                        pred_id
                    ))
                    
                    logger.info(f"Updated prediction {pred_id}: predicted={predicted_regime}, "
                              f"actual={actual_regime}, correct={predicted_regime == actual_regime}")
                    
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error tracking prediction outcomes: {e}")
            
    def _reverse_map_regime(self, main_regime):
        """Map main regime back to daily regime format"""
        reverse_mapping = {
            'STRONG_BULL': 'strong_uptrend',
            'BULLISH': 'uptrend',
            'NEUTRAL_BULLISH': 'choppy_bullish',
            'NEUTRAL': 'choppy',
            'NEUTRAL_BEARISH': 'choppy_bearish',
            'BEARISH': 'downtrend',
            'STRONG_BEAR': 'strong_downtrend'
        }
        return reverse_mapping.get(main_regime, 'choppy')
        
    def get_performance_metrics(self):
        """Get performance metrics for the integrated system"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get prediction accuracy
            df_predictions = pd.read_sql_query("""
                SELECT * FROM regime_predictions
                WHERE actual_regime IS NOT NULL
                  AND timestamp > datetime('now', '-30 days')
            """, conn)
            
            if not df_predictions.empty:
                df_predictions['correct'] = df_predictions['predicted_regime'] == df_predictions['actual_regime']
                accuracy = df_predictions['correct'].mean()
                
                # Get per-regime accuracy
                regime_accuracy = df_predictions.groupby('predicted_regime')['correct'].agg(['mean', 'count'])
                
                # Get recent performance trend
                df_predictions['date'] = pd.to_datetime(df_predictions['timestamp']).dt.date
                daily_accuracy = df_predictions.groupby('date')['correct'].mean()
                
                metrics = {
                    'overall_accuracy': accuracy,
                    'total_predictions': len(df_predictions),
                    'regime_accuracy': regime_accuracy.to_dict(),
                    'recent_trend': {
                        'last_7_days': df_predictions[df_predictions['date'] >= (datetime.now().date() - timedelta(days=7))]['correct'].mean(),
                        'last_30_days': accuracy
                    },
                    'daily_accuracy': daily_accuracy.tail(7).to_dict()
                }
            else:
                metrics = {
                    'overall_accuracy': 0,
                    'total_predictions': 0,
                    'regime_accuracy': {},
                    'recent_trend': {},
                    'daily_accuracy': {}
                }
                
            conn.close()
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return None


def main():
    """Run integrated market regime analysis"""
    bridge = MarketRegimeBridge()
    
    # Run analysis
    report = bridge.run_integrated_analysis()
    
    if report:
        print("\n" + "="*60)
        print("INTEGRATED MARKET REGIME ANALYSIS")
        print("="*60)
        
        print(f"\nTimestamp: {report['timestamp']}")
        
        print("\nDaily Analysis:")
        print(f"  Regime: {report['daily_analysis']['regime']}")
        print(f"  Long Count: {report['daily_analysis']['counts']['long']}")
        print(f"  Short Count: {report['daily_analysis']['counts']['short']}")
        
        print("\nMain System Analysis:")
        print(f"  Regime: {report['main_analysis']['regime']}")
        print(f"  Confidence: {report['main_analysis']['confidence']:.1%}")
        
        print("\nReconciled Analysis:")
        print(f"  Final Regime: {report['reconciled_regime']['regime']}")
        print(f"  Confidence: {report['reconciled_regime']['confidence']:.1%}")
        print(f"  Source: {report['reconciled_regime']['source']}")
        
        if report['daily_analysis'].get('prediction'):
            pred = report['daily_analysis']['prediction']
            print(f"\nNext Regime Prediction:")
            print(f"  Predicted: {pred['predicted_regime']}")
            print(f"  Confidence: {pred['confidence']:.1%}")
        
        print("\nInsights:")
        for insight in report['insights']:
            print(f"  • {insight}")
            
        # Get performance metrics
        metrics = bridge.get_performance_metrics()
        if metrics and metrics['total_predictions'] > 0:
            print(f"\nSystem Performance:")
            print(f"  Overall Accuracy: {metrics['overall_accuracy']:.1%}")
            print(f"  Total Predictions: {metrics['total_predictions']}")
            if metrics['recent_trend']:
                print(f"  Last 7 Days: {metrics['recent_trend'].get('last_7_days', 0):.1%}")
                
        print("\n" + "="*60)
        
    else:
        print("Failed to generate integrated analysis")


if __name__ == "__main__":
    main()