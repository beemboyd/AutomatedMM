#!/usr/bin/env python
"""
Market Regime Analyzer
Integrates reversal scan trend strength with broader market regime analysis
"""

import os
import sys
import logging
import datetime
import json
import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3
import glob

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import local modules
# from reversal_trend_scanner import ReversalTrendScanner  # No longer needed - we load existing results
from trend_strength_calculator import TrendStrengthCalculator
from market_regime_predictor import MarketRegimePredictor
from trend_dashboard import TrendDashboard
from confidence_calculator import ConfidenceCalculator
from position_recommender import PositionRecommender
from regime_history_tracker import RegimeHistoryTracker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.market_regime.market_indicators import MarketIndicators

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                       "market_regime_analyzer.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketRegimeAnalyzer:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.script_dir, "regime_analysis")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize components
        # self.scanner = ReversalTrendScanner()  # No longer needed - we load existing results
        self.calculator = TrendStrengthCalculator()
        self.predictor = MarketRegimePredictor()
        self.indicators = MarketIndicators()
        
        # Initialize new components
        self.confidence_calc = ConfidenceCalculator()
        self.position_rec = PositionRecommender()
        self.history_tracker = RegimeHistoryTracker()
        
        # Market regime definitions
        self.regimes = {
            'strong_uptrend': {
                'description': 'Strong Uptrend - Bull market conditions',
                'characteristics': ['Strong bullish reversals', 'Few bearish patterns', 'High confidence longs'],
                'strategy': 'Aggressive long positions, avoid shorts'
            },
            'uptrend': {
                'description': 'Uptrend - Bullish market conditions',
                'characteristics': ['More bullish than bearish reversals', 'Moderate confidence'],
                'strategy': 'Focus on long positions, selective shorts'
            },
            'choppy_bullish': {
                'description': 'Choppy with Bullish Bias',
                'characteristics': ['Mixed signals with slight bullish edge', 'Low confidence'],
                'strategy': 'Both directions viable, slight long preference'
            },
            'choppy': {
                'description': 'Choppy/Ranging Market',
                'characteristics': ['Balanced reversals', 'No clear direction', 'Range-bound'],
                'strategy': 'Trade both directions, focus on range boundaries'
            },
            'choppy_bearish': {
                'description': 'Choppy with Bearish Bias',
                'characteristics': ['Mixed signals with slight bearish edge', 'Low confidence'],
                'strategy': 'Both directions viable, slight short preference'
            },
            'downtrend': {
                'description': 'Downtrend - Bearish market conditions',
                'characteristics': ['More bearish than bullish reversals', 'Moderate confidence'],
                'strategy': 'Focus on short positions, selective longs'
            },
            'strong_downtrend': {
                'description': 'Strong Downtrend - Bear market conditions',
                'characteristics': ['Strong bearish reversals', 'Few bullish patterns', 'High confidence shorts'],
                'strategy': 'Aggressive short positions, avoid longs'
            }
        }
        
    def determine_market_regime(self, trend_report):
        """Determine market regime based on trend analysis"""
        trend = trend_report['trend_strength']['trend']
        
        # Map trend strength to market regime
        regime_mapping = {
            'strong_bullish': 'strong_uptrend',
            'bullish': 'uptrend',
            'neutral_bullish': 'choppy_bullish',
            'neutral': 'choppy',
            'neutral_bearish': 'choppy_bearish',
            'bearish': 'downtrend',
            'strong_bearish': 'strong_downtrend',
            'no_signals': 'choppy'
        }
        
        regime = regime_mapping.get(trend, 'choppy')
        
        # Adjust based on momentum if available
        if trend_report.get('momentum'):
            momentum = trend_report['momentum']['momentum']
            
            # Upgrade regime if strong momentum
            if momentum == 'increasing_bullish' and regime in ['choppy', 'choppy_bearish']:
                regime = 'choppy_bullish'
            elif momentum == 'increasing_bearish' and regime in ['choppy', 'choppy_bullish']:
                regime = 'choppy_bearish'
                
        return regime
    
    def _load_existing_scan_results(self):
        """Load the most recent scanner results from the Daily/results directories"""
        logger.info("Loading existing scanner results...")
        
        results_dir = os.path.join(os.path.dirname(self.script_dir), "results")
        results_short_dir = os.path.join(os.path.dirname(self.script_dir), "results-s")
        
        # Find most recent long reversal file
        long_files = glob.glob(os.path.join(results_dir, "Long_Reversal_Daily_*.xlsx"))
        long_file = max(long_files, key=os.path.getmtime) if long_files else None
        
        # Find most recent short reversal file
        short_files = glob.glob(os.path.join(results_short_dir, "Short_Reversal_Daily_*.xlsx"))
        short_file = max(short_files, key=os.path.getmtime) if short_files else None
        
        # Check if files are recent (within last 35 minutes to account for 30-min schedule)
        current_time = datetime.datetime.now()
        results_valid = True
        
        if long_file:
            long_time = datetime.datetime.fromtimestamp(os.path.getmtime(long_file))
            if current_time - long_time > datetime.timedelta(minutes=35):
                logger.warning(f"Long reversal results are stale (from {long_time})")
                results_valid = False
        else:
            logger.warning("No long reversal results found")
            results_valid = False
            
        if short_file:
            short_time = datetime.datetime.fromtimestamp(os.path.getmtime(short_file))
            if current_time - short_time > datetime.timedelta(minutes=35):
                logger.warning(f"Short reversal results are stale (from {short_time})")
                results_valid = False
        else:
            logger.warning("No short reversal results found")
            results_valid = False
            
        if not results_valid:
            logger.error("Scanner results are missing or stale. Ensure Long and Short reversal scanners are running.")
            # Return empty results
            return {
                'long_file': None,
                'short_file': None,
                'timestamp': current_time.isoformat()
            }
            
        logger.info(f"Using scanner results: Long={os.path.basename(long_file) if long_file else 'None'}, Short={os.path.basename(short_file) if short_file else 'None'}")
        
        return {
            'long_file': long_file,
            'short_file': short_file,
            'timestamp': current_time.isoformat()
        }
        
    def generate_regime_report(self):
        """Generate comprehensive market regime report"""
        logger.info("Generating market regime report...")
        
        # Load existing scanner results instead of running new scans
        scan_results = self._load_existing_scan_results()
        
        # Calculate trend strength
        trend_report = self.calculator.analyze_current_trend()
        
        # Calculate market breadth
        breadth_indicators = {}
        df_combined = pd.DataFrame()  # Initialize here for later use
        if scan_results and scan_results.get('long_file') and scan_results.get('short_file'):
            try:
                # Load scan dataframes
                df_long = pd.read_excel(scan_results['long_file']) if os.path.exists(scan_results['long_file']) else pd.DataFrame()
                df_short = pd.read_excel(scan_results['short_file']) if os.path.exists(scan_results['short_file']) else pd.DataFrame()
                
                # Combine dataframes
                if not df_long.empty:
                    df_long['Direction'] = 'LONG'
                if not df_short.empty:
                    df_short['Direction'] = 'SHORT'
                    
                df_combined = pd.concat([df_long, df_short], ignore_index=True) if not df_long.empty or not df_short.empty else pd.DataFrame()
                
                # Calculate breadth indicators
                if not df_combined.empty:
                    breadth_indicators = self.indicators.calculate_market_breadth(df_combined)
            except Exception as e:
                logger.error(f"Error calculating breadth indicators: {e}")
        
        if not trend_report:
            logger.error("Failed to generate trend report")
            return None
            
        # Determine market regime
        regime = self.determine_market_regime(trend_report)
        regime_info = self.regimes[regime]
        
        # Calculate confidence
        confidence_data = {
            'ratio': trend_report['trend_strength']['ratio'] if trend_report['trend_strength']['ratio'] != 'inf' else 10.0,
            'history': [entry['regime'] for entry in self.history_tracker.get_recent_history(24)],
            'volume_participation': breadth_indicators.get('volume_participation', 0.5) if breadth_indicators else 0.5,
            'trend_strength': trend_report['trend_strength'].get('strength', 0)
        }
        confidence = self.confidence_calc.calculate_confidence(confidence_data)
        
        # Calculate volatility from scanner data
        volatility_data = {}
        if not df_combined.empty and 'ATR' in df_combined.columns:
            atr_values = df_combined['ATR'].dropna()
            if len(atr_values) > 0:
                volatility_data = {
                    'volatility_score': min(np.percentile(atr_values, 75) / 5, 1.0),  # Normalize to 0-1
                    'avg_atr': atr_values.mean(),
                    'max_atr': atr_values.max()
                }
        
        # Get position recommendations
        position_recommendations = self.position_rec.get_recommendations(
            regime, confidence, volatility_data
        )
        
        # Update predictor with actual regime
        self.predictor.update_actual_regime(datetime.datetime.now().isoformat(), regime)
        
        # Get scan history for prediction
        scan_history = self.calculator.get_scan_history()
        
        # Make prediction for next regime
        prediction = None
        if scan_history and len(scan_history) >= 3:
            # Add current scan to history
            current_scan = {
                'long_count': trend_report['counts']['long'],
                'short_count': trend_report['counts']['short'],
                'timestamp': datetime.datetime.now().isoformat()
            }
            scan_history.append(current_scan)
            
            # Get prediction
            prediction_result = self.predictor.predict_next_regime(scan_history)
            if prediction_result:
                prediction_result['scan_data'] = current_scan
                self.predictor.record_prediction(prediction_result)
                prediction = prediction_result
                
                # Save model after prediction
                self.predictor.save_model()
        
        # Generate actionable insights
        insights = self._generate_insights(regime, trend_report, prediction)
        
        # Prepare complete report
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'market_regime': {
                'regime': regime,
                'description': regime_info['description'],
                'characteristics': regime_info['characteristics'],
                'strategy': regime_info['strategy'],
                'confidence': confidence,
                'confidence_level': self.position_rec._get_confidence_level(confidence)
            },
            'reversal_counts': trend_report['counts'],
            'trend_analysis': trend_report['trend_strength'],
            'momentum_analysis': trend_report.get('momentum'),
            'breadth_indicators': breadth_indicators,
            'volatility': volatility_data,
            'position_recommendations': position_recommendations,
            'prediction': prediction,
            'model_performance': self.predictor.get_model_insights(),
            'historical_context': self.history_tracker.get_performance_summary(),
            'insights': insights,
            'scan_files': {
                'long': scan_results.get('long_file'),
                'short': scan_results.get('short_file')
            }
        }
        
        # Add to history tracker
        history_entry = {
            'regime': regime,
            'confidence': confidence,
            'timestamp': datetime.datetime.now().isoformat(),
            'indicators': {
                'ratio': confidence_data['ratio'],
                'volume_participation': confidence_data.get('volume_participation', 0.5),
                'trend_strength': confidence_data.get('trend_strength', 0),
                'volatility_score': volatility_data.get('volatility_score', 0.5)
            },
            'recommendations': position_recommendations
        }
        self.history_tracker.add_regime_entry(history_entry)
        
        # Save report
        output_file = os.path.join(self.output_dir, 
                                 f"regime_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Market regime report saved to {output_file}")
        
        # Also save a summary file that always has the same name for easy access
        summary_file = os.path.join(self.output_dir, "latest_regime_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        # Save to central database
        self._save_report_to_db(report)
            
        return report
    
    def _save_report_to_db(self, report):
        """Save report summary to central database"""
        try:
            db_path = "/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Extract key metrics
            regime = report['market_regime']['regime']
            long_count = report['reversal_counts']['long']
            short_count = report['reversal_counts']['short']
            
            # Calculate market score
            if short_count > 0:
                market_score = long_count / short_count
            elif long_count > 0:
                market_score = 5.0
            else:
                market_score = 1.0
                
            # Extract additional scores if available
            trend_score = None
            momentum_score = None
            volatility_score = None
            breadth_score = None
            
            if report.get('trend_analysis'):
                ratio = report['trend_analysis'].get('ratio')
                if ratio and ratio != 'inf':
                    trend_score = float(ratio)
                    
            if report.get('momentum_analysis'):
                momentum = report['momentum_analysis'].get('momentum')
                if momentum == 'increasing_bullish':
                    momentum_score = 1.0
                elif momentum == 'increasing_bearish':
                    momentum_score = -1.0
                else:
                    momentum_score = 0.0
                    
            if report.get('breadth_indicators'):
                breadth = report['breadth_indicators']
                if breadth.get('advance_decline_ratio'):
                    breadth_score = breadth['advance_decline_ratio']
            
            # Save current regime analysis
            cursor.execute("""
                INSERT INTO predictions 
                (timestamp, regime, confidence, market_score, trend_score, 
                 momentum_score, volatility_score, breadth_score, indicators, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.datetime.now(),
                regime,
                1.0,  # Current analysis has 100% confidence
                market_score,
                trend_score,
                momentum_score,
                volatility_score,
                breadth_score,
                json.dumps(report['reversal_counts']),
                json.dumps(report.get('insights', []))
            ))
            
            # Track regime transitions
            cursor.execute("""
                SELECT regime FROM predictions 
                WHERE timestamp < datetime('now') 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            last_regime = cursor.fetchone()
            if last_regime and last_regime[0] != regime:
                cursor.execute("""
                    INSERT INTO regime_changes 
                    (timestamp, from_regime, to_regime, confidence, 
                     trigger_indicators, market_conditions)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.datetime.now(),
                    last_regime[0],
                    regime,
                    1.0,
                    json.dumps(report['reversal_counts']),
                    json.dumps({
                        'trend': report['trend_analysis']['trend'],
                        'momentum': report.get('momentum_analysis', {}).get('momentum'),
                        'breadth': report.get('breadth_indicators', {})
                    })
                ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved regime analysis to database: {regime}")
            
        except Exception as e:
            logger.error(f"Error saving report to database: {e}")
        
    def _generate_insights(self, regime, trend_report, prediction=None):
        """Generate actionable trading insights based on regime and prediction"""
        insights = []
        
        long_count = trend_report['counts']['long']
        short_count = trend_report['counts']['short']
        total_count = trend_report['counts']['total']
        
        # Volume of opportunities
        if total_count == 0:
            insights.append("No reversal patterns detected - Market may be in strong trend or low volatility")
        elif total_count < 5:
            insights.append("Low number of reversal patterns - Limited trading opportunities")
        elif total_count > 20:
            insights.append("High number of reversal patterns - Many potential opportunities")
            
        # Directional bias insights
        if regime in ['strong_uptrend', 'uptrend']:
            insights.append(f"Strong long bias with {long_count} bullish setups")
            insights.append("Focus on high-probability long entries")
            if short_count > 0:
                insights.append(f"Only {short_count} short setups - Be very selective with shorts")
                
        elif regime in ['strong_downtrend', 'downtrend']:
            insights.append(f"Strong short bias with {short_count} bearish setups")
            insights.append("Focus on high-probability short entries")
            if long_count > 0:
                insights.append(f"Only {long_count} long setups - Be very selective with longs")
                
        elif regime == 'choppy':
            insights.append("Balanced market - Trade both directions with equal weight")
            insights.append("Focus on range boundaries and clear support/resistance")
            
        # Momentum insights
        if trend_report.get('momentum'):
            momentum = trend_report['momentum']['momentum']
            if momentum == 'increasing_bullish':
                insights.append("Momentum shifting bullish - Watch for trend change")
            elif momentum == 'increasing_bearish':
                insights.append("Momentum shifting bearish - Watch for trend change")
                
        # Risk management insights
        if regime in ['strong_uptrend', 'strong_downtrend']:
            insights.append("High confidence regime - Can use normal position sizing")
        elif regime in ['choppy', 'choppy_bullish', 'choppy_bearish']:
            insights.append("Low confidence regime - Consider reduced position sizing")
            
        # Prediction insights
        if prediction:
            predicted_regime = prediction['predicted_regime']
            confidence = prediction['confidence']
            
            insights.append(f"\n📊 Next Regime Prediction: {predicted_regime} (Confidence: {confidence:.1%})")
            
            # Regime change insights
            if predicted_regime != regime:
                if predicted_regime in ['strong_uptrend', 'uptrend'] and regime in ['choppy', 'choppy_bearish', 'downtrend']:
                    insights.append("⚠️ Potential bullish regime change - Start looking for long setups")
                elif predicted_regime in ['strong_downtrend', 'downtrend'] and regime in ['choppy', 'choppy_bullish', 'uptrend']:
                    insights.append("⚠️ Potential bearish regime change - Start looking for short setups")
                else:
                    insights.append(f"📈 Regime transition expected from {regime} to {predicted_regime}")
                    
            # Confidence-based recommendations
            if confidence > 0.7:
                insights.append("High confidence prediction - Consider adjusting position sizing accordingly")
            elif confidence < 0.4:
                insights.append("Low confidence prediction - Maintain current strategy with caution")
                
        # Model performance insights
        model_insights = self.predictor.get_model_insights()
        if model_insights['performance']['accuracy'] > 0:
            insights.append(f"\n🤖 Model Performance: {model_insights['performance']['accuracy']:.1%} accuracy over {model_insights['performance']['total_predictions']} predictions")
            
        return insights
        
    def get_trading_bias(self):
        """Get current trading bias from latest regime analysis"""
        summary_file = os.path.join(self.output_dir, "latest_regime_summary.json")
        
        if not os.path.exists(summary_file):
            logger.warning("No regime summary found, running new analysis...")
            report = self.generate_regime_report()
        else:
            try:
                with open(summary_file, 'r') as f:
                    report = json.load(f)
                    
                # Check if report is recent (within last hour)
                report_time = datetime.datetime.fromisoformat(report['timestamp'])
                if datetime.datetime.now() - report_time > datetime.timedelta(hours=1):
                    logger.info("Regime report is stale, generating new one...")
                    report = self.generate_regime_report()
            except Exception as e:
                logger.error(f"Error loading regime summary: {e}")
                report = self.generate_regime_report()
                
        if report:
            return {
                'regime': report['market_regime']['regime'],
                'strategy': report['market_regime']['strategy'],
                'long_count': report['reversal_counts']['long'],
                'short_count': report['reversal_counts']['short']
            }
        else:
            return None
            

def main():
    """Main function to analyze market regime"""
    analyzer = MarketRegimeAnalyzer()
    
    try:
        # Generate regime report
        report = analyzer.generate_regime_report()
        
        if report:
            print("\n===== Market Regime Analysis =====")
            print(f"Timestamp: {report['timestamp']}")
            
            print(f"\nMarket Regime: {report['market_regime']['regime'].upper()}")
            print(f"Description: {report['market_regime']['description']}")
            print(f"Confidence: {report['market_regime']['confidence']:.1%} ({report['market_regime']['confidence_level']})")
            
            print("\nCharacteristics:")
            for char in report['market_regime']['characteristics']:
                print(f"  - {char}")
                
            print(f"\nStrategy: {report['market_regime']['strategy']}")
            
            print(f"\nReversal Pattern Counts:")
            print(f"  Long: {report['reversal_counts']['long']}")
            print(f"  Short: {report['reversal_counts']['short']}")
            print(f"  Total: {report['reversal_counts']['total']}")
            
            print(f"\nTrend Analysis:")
            print(f"  Trend: {report['trend_analysis']['trend']}")
            print(f"  Ratio: {report['trend_analysis']['ratio']:.2f}" if report['trend_analysis']['ratio'] != 'inf' else "  Ratio: Infinite")
            
            if report.get('momentum_analysis'):
                print(f"\nMomentum: {report['momentum_analysis']['description']}")
            
            if report.get('volatility') and report['volatility']:
                print(f"\nVolatility Analysis:")
                print(f"  Score: {report['volatility']['volatility_score']:.1%}")
                print(f"  Average ATR: {report['volatility']['avg_atr']:.2f}%")
            
            if report.get('position_recommendations'):
                recs = report['position_recommendations']
                print(f"\n📊 Position Recommendations:")
                print(f"  Position Size Multiplier: {recs['position_size_multiplier']}x")
                print(f"  Stop Loss Multiplier: {recs['stop_loss_multiplier']}x")
                print(f"  Max Positions: {recs['max_positions']}")
                print(f"  Risk per Trade: {recs['risk_per_trade']:.1%}")
                print(f"  Preferred Direction: {recs['preferred_direction']}")
                
            if report.get('prediction'):
                print(f"\n🔮 Next Regime Prediction:")
                print(f"  Predicted: {report['prediction']['predicted_regime']}")
                print(f"  Confidence: {report['prediction']['confidence']:.1%}")
                
            if report.get('model_performance'):
                perf = report['model_performance']['performance']
                if perf['total_predictions'] > 0:
                    print(f"\n📊 Model Performance:")
                    print(f"  Accuracy: {perf['accuracy']:.1%}")
                    print(f"  Total Predictions: {perf['total_predictions']}")
                
            print("\nKey Insights:")
            for insight in report['insights']:
                print(f"  • {insight}")
                
            print("=====================================\n")
            
        # Generate dashboard
        try:
            dashboard = TrendDashboard()
            dashboard_path = dashboard.generate_dashboard()
            logger.info(f"Dashboard generated: {dashboard_path}")
        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())