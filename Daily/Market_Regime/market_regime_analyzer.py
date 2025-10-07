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
import math

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import local modules
# from reversal_trend_scanner import ReversalTrendScanner  # No longer needed - we load existing results
from trend_strength_calculator import TrendStrengthCalculator
from market_regime_predictor import MarketRegimePredictor  # Use original version with full methods
from trend_dashboard import TrendDashboard
from confidence_calculator import ConfidenceCalculator
from kelly_position_recommender import KellyPositionRecommender
from regime_history_tracker import RegimeHistoryTracker
from regime_smoother import RegimeSmoother
from index_sma_analyzer import IndexSMAAnalyzer
from multi_timeframe_analyzer import MultiTimeframeAnalyzer
from breadth_regime_consistency import BreadthRegimeConsistencyChecker
from enhanced_market_score_calculator import EnhancedMarketScoreCalculator
from regime_change_notifier import RegimeChangeNotifier
from pcr_analyzer import PCRAnalyzer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# DEPRECATED: MarketIndicators moved/archived - breadth calculation now handled by other components
# from analysis.market_regime.market_indicators import MarketIndicators

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
        # self.indicators = MarketIndicators()  # DEPRECATED - no longer available
        
        # Initialize new components
        self.confidence_calc = ConfidenceCalculator()
        self.position_rec = KellyPositionRecommender()
        self.history_tracker = RegimeHistoryTracker()
        self.regime_smoother = RegimeSmoother()
        self.index_analyzer = IndexSMAAnalyzer()
        self.multi_tf_analyzer = MultiTimeframeAnalyzer()
        self.breadth_consistency_checker = BreadthRegimeConsistencyChecker()
        self.enhanced_score_calculator = EnhancedMarketScoreCalculator()
        self.regime_notifier = RegimeChangeNotifier()
        self.pcr_analyzer = PCRAnalyzer()
        
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
        
    def determine_market_regime(self, trend_report, use_index_analysis=True, use_pcr_analysis=True):
        """Determine market regime based on trend analysis, index SMA positions, and PCR"""
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
        
        base_regime = regime_mapping.get(trend, 'choppy')
        
        # Get index analysis if enabled
        if use_index_analysis:
            try:
                index_trend = self.index_analyzer.analyze_index_trend()
                
                # Combine pattern-based regime with index-based regime
                combined_regime = self._combine_regime_signals(base_regime, index_trend)
                
                logger.info(f"Regime determination: Pattern-based={base_regime}, Index trend={index_trend['trend']}, Combined={combined_regime}")
                
                regime = combined_regime
            except Exception as e:
                logger.error(f"Error in index analysis: {e}")
                regime = base_regime
        else:
            regime = base_regime
        
        # Apply PCR adjustment if enabled
        if use_pcr_analysis:
            try:
                pcr_data = self.pcr_analyzer.get_latest_pcr()
                if pcr_data:
                    pcr_adjustment, pcr_weight = self.pcr_analyzer.get_pcr_regime_adjustment(pcr_data)
                    
                    # Apply PCR adjustment with 20% weightage
                    PCR_WEIGHTAGE = 0.20
                    adjusted_weight = pcr_weight * PCR_WEIGHTAGE
                    
                    if pcr_adjustment == 'bullish' and adjusted_weight > 0.1:
                        # PCR suggests bullish bias - upgrade regime
                        if regime == 'strong_downtrend':
                            regime = 'downtrend'
                        elif regime == 'downtrend':
                            regime = 'choppy_bearish'
                        elif regime == 'choppy_bearish':
                            regime = 'choppy'
                        elif regime == 'choppy':
                            regime = 'choppy_bullish'
                        elif regime == 'choppy_bullish':
                            regime = 'uptrend'
                        elif regime == 'uptrend' and adjusted_weight > 0.15:
                            regime = 'strong_uptrend'
                            
                        logger.info(f"PCR adjustment applied: {pcr_adjustment} (PCR: {pcr_data['pcr_combined']:.3f}, Weight: {adjusted_weight:.1%})")
                        
                    elif pcr_adjustment == 'bearish' and adjusted_weight > 0.1:
                        # PCR suggests bearish bias - downgrade regime
                        if regime == 'strong_uptrend':
                            regime = 'uptrend'
                        elif regime == 'uptrend':
                            regime = 'choppy_bullish'
                        elif regime == 'choppy_bullish':
                            regime = 'choppy'
                        elif regime == 'choppy':
                            regime = 'choppy_bearish'
                        elif regime == 'choppy_bearish':
                            regime = 'downtrend'
                        elif regime == 'downtrend' and adjusted_weight > 0.15:
                            regime = 'strong_downtrend'
                            
                        logger.info(f"PCR adjustment applied: {pcr_adjustment} (PCR: {pcr_data['pcr_combined']:.3f}, Weight: {adjusted_weight:.1%})")
                    else:
                        logger.info(f"PCR neutral or weak signal (PCR: {pcr_data.get('pcr_combined', 'N/A')}, Weight: {adjusted_weight:.1%})")
                        
            except Exception as e:
                logger.error(f"Error in PCR analysis: {e}")
        
        # Adjust based on momentum if available
        if trend_report.get('momentum'):
            momentum = trend_report['momentum']['momentum']
            
            # Upgrade regime if strong momentum
            if momentum == 'increasing_bullish' and regime in ['choppy', 'choppy_bearish']:
                regime = 'choppy_bullish'
            elif momentum == 'increasing_bearish' and regime in ['choppy', 'choppy_bullish']:
                regime = 'choppy_bearish'
                
        return regime
    
    def _combine_regime_signals(self, pattern_regime, index_trend):
        """Combine pattern-based regime with index-based signals"""
        # Weight for index analysis (30% weight)
        index_weight = 0.3
        pattern_weight = 0.7
        
        # Convert regimes to numerical scores
        regime_scores = {
            'strong_uptrend': 3,
            'uptrend': 2,
            'choppy_bullish': 1,
            'choppy': 0,
            'choppy_bearish': -1,
            'downtrend': -2,
            'strong_downtrend': -3
        }
        
        index_regime_map = {
            'strong_bullish': 'strong_uptrend',
            'bullish': 'uptrend',
            'neutral': 'choppy',
            'bearish': 'downtrend',
            'strong_bearish': 'strong_downtrend'
        }
        
        # Get scores
        pattern_score = regime_scores.get(pattern_regime, 0)
        index_regime = index_regime_map.get(index_trend['trend'], 'choppy')
        index_score = regime_scores.get(index_regime, 0)
        
        # Calculate weighted score
        combined_score = pattern_score * pattern_weight + index_score * index_weight
        
        # Map back to regime
        if combined_score >= 2.5:
            return 'strong_uptrend'
        elif combined_score >= 1.5:
            return 'uptrend'
        elif combined_score >= 0.5:
            return 'choppy_bullish'
        elif combined_score >= -0.5:
            return 'choppy'
        elif combined_score >= -1.5:
            return 'choppy_bearish'
        elif combined_score >= -2.5:
            return 'downtrend'
        else:
            return 'strong_downtrend'
    
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
            if current_time - long_time > datetime.timedelta(days=7):  # Temporarily relaxed for historical analysis
                logger.warning(f"Long reversal results are stale (from {long_time})")
                results_valid = False
        else:
            logger.warning("No long reversal results found")
            results_valid = False
            
        if short_file:
            short_time = datetime.datetime.fromtimestamp(os.path.getmtime(short_file))
            if current_time - short_time > datetime.timedelta(days=7):  # Temporarily relaxed for historical analysis
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
                # DEPRECATED: MarketIndicators no longer available - breadth calculated elsewhere
                # if not df_combined.empty:
                #     breadth_indicators = self.indicators.calculate_market_breadth(df_combined)
            except Exception as e:
                logger.error(f"Error calculating breadth indicators: {e}")
        
        if not trend_report:
            logger.error("Failed to generate trend report")
            return None
            
        # Calculate enhanced market score with breadth integration
        enhanced_score_result = None
        try:
            # Try with breadth data if available, otherwise calculate without it
            if breadth_indicators:
                enhanced_score_result = self.enhanced_score_calculator.calculate_enhanced_market_score(
                    reversal_counts=trend_report['counts'],
                    breadth_data=breadth_indicators,
                    momentum_data=trend_report.get('momentum')
                )
            else:
                # Fallback to basic market score calculation without breadth
                market_score = trend_report['trend_strength'].get('market_score', 0)
                enhanced_score_result = {
                    'market_score': market_score,
                    'breadth_score': None,
                    'direction': trend_report['trend_strength'].get('direction', 'neutral'),
                    'confidence': trend_report['trend_strength'].get('strength', 0.5),
                    'weekly_bias': None,
                    'strategy_recommendation': trend_report['trend_strength'].get('strategy', '')
                }
            
            if enhanced_score_result:
                logger.info(f"Market score: {enhanced_score_result['market_score']:.3f}, "
                          f"Direction: {enhanced_score_result['direction']}, "
                          f"Confidence: {enhanced_score_result['confidence']:.1%}")
        except Exception as e:
            logger.error(f"Error calculating market score: {e}")
        
        # Determine market regime
        new_regime = self.determine_market_regime(trend_report)
        
        # Check if we should actually change the regime (smoothing)
        current_regime = None
        regime_duration_hours = 0
        
        # Get current regime from history
        history_summary = self.history_tracker.get_performance_summary()
        if history_summary and history_summary.get('current_regime'):
            current_regime = history_summary['current_regime']
            regime_duration_hours = history_summary.get('regime_duration_hours', 0)
        
        # Apply smoothing logic
        if current_regime and self.regime_smoother:
            # Calculate confidence for the new regime
            temp_confidence_data = {
                'ratio': trend_report['trend_strength']['ratio'] if trend_report['trend_strength']['ratio'] != 'inf' else 10.0,
                'history': [entry['regime'] for entry in self.history_tracker.get_recent_history(24)],
                'volume_participation': breadth_indicators.get('volume_participation', 0.5) if breadth_indicators else 0.5,
                'trend_strength': trend_report['trend_strength'].get('strength', 0)
            }
            temp_confidence = self.confidence_calc.calculate_confidence(temp_confidence_data)
            
            should_change, reason = self.regime_smoother.should_change_regime(
                current_regime, new_regime, temp_confidence, regime_duration_hours
            )
            
            if not should_change:
                logger.info(f"Regime change blocked by smoother: {current_regime} -> {new_regime} ({reason})")
                regime = current_regime  # Keep current regime
            else:
                logger.info(f"Regime change approved: {current_regime} -> {new_regime} ({reason})")
                regime = new_regime
        else:
            # No current regime or smoother not available, use new regime
            regime = new_regime
            
        regime_info = self.regimes[regime]
        
        # Calculate confidence
        confidence_data = {
            'ratio': trend_report['trend_strength']['ratio'] if trend_report['trend_strength']['ratio'] != 'inf' else 10.0,
            'history': [entry['regime'] for entry in self.history_tracker.get_recent_history(24)],
            'volume_participation': breadth_indicators.get('volume_participation', 0.5) if breadth_indicators else 0.5,
            'trend_strength': trend_report['trend_strength'].get('strength', 0)
        }
        confidence = self.confidence_calc.calculate_confidence(confidence_data)
        
        # Check breadth-regime consistency and adjust confidence if needed
        consistency_result = self.breadth_consistency_checker.check_consistency(
            regime, breadth_indicators, confidence
        )
        
        # Check if we should override the regime due to extreme divergence
        regime_override = self.breadth_consistency_checker.get_regime_override(
            regime, breadth_indicators
        )
        
        if regime_override:
            logger.warning(f"Regime override due to extreme breadth divergence: {regime} -> {regime_override}")
            regime = regime_override
            regime_info = self.regimes[regime]
        
        # Use adjusted confidence from consistency check
        original_confidence = confidence
        confidence = consistency_result['adjusted_confidence']
        # Calculate confidence level
        if confidence >= 0.8:
            confidence_level = 'very_high'
        elif confidence >= 0.6:
            confidence_level = 'high'
        elif confidence >= 0.4:
            confidence_level = 'moderate'
        elif confidence >= 0.2:
            confidence_level = 'low'
        else:
            confidence_level = 'very_low'
        
        # Add divergence alert to insights if needed
        divergence_alert = None
        if consistency_result['divergence_type'] != 'none':
            divergence_alert = self.breadth_consistency_checker.format_divergence_alert(
                regime, breadth_indicators, consistency_result
            )
        
        # Calculate volatility from scanner data
        volatility_data = {}
        if not df_combined.empty and 'ATR' in df_combined.columns:
            atr_values = df_combined['ATR'].dropna()
            if len(atr_values) > 0:
                # Calculate volatility score based on ATR distribution
                # Low volatility: < 2% ATR, Medium: 2-4%, High: > 4%
                avg_atr = atr_values.mean()
                median_atr = atr_values.median()
                p75_atr = np.percentile(atr_values, 75)
                
                # Use median ATR for more robust calculation (less affected by outliers)
                # Normalize volatility score (0-1 scale) based on percentile ranges
                # Indian market typically has ATR of 20-80, not 2-6 like US markets
                
                # Calculate percentile-based volatility score
                percentile_25 = np.percentile(atr_values, 25)
                percentile_75 = np.percentile(atr_values, 75)
                
                # Use median for scoring (more stable than mean)
                if median_atr < 20:
                    volatility_score = median_atr / 40.0  # 0 to 0.5 for ATR 0-20
                elif median_atr < 40:
                    volatility_score = 0.5 + (median_atr - 20) / 40.0  # 0.5 to 0.75 for ATR 20-40
                elif median_atr < 60:
                    volatility_score = 0.75 + (median_atr - 40) / 80.0  # 0.75 to 0.875 for ATR 40-60
                else:
                    volatility_score = min(0.875 + (median_atr - 60) / 160.0, 1.0)  # 0.875 to 1.0 for ATR > 60
                
                # Determine volatility regime based on thresholds appropriate for Indian markets
                if median_atr < 25:
                    volatility_regime = 'low'
                elif median_atr < 35:
                    volatility_regime = 'normal'
                elif median_atr < 50:
                    volatility_regime = 'high'
                else:
                    volatility_regime = 'extreme'
                
                volatility_data = {
                    'volatility_score': round(volatility_score, 3),
                    'avg_atr': round(avg_atr, 2),
                    'median_atr': round(median_atr, 2),
                    'p25_atr': round(percentile_25, 2),
                    'p75_atr': round(p75_atr, 2),
                    'max_atr': round(atr_values.max(), 2),
                    'volatility_regime': volatility_regime,
                    'atr_spread': round(p75_atr - percentile_25, 2)  # Measure of volatility dispersion
                }
        
        # Get position recommendations using Kelly Criterion
        # Extract market score and breadth score for Kelly calculations
        market_score = enhanced_score_result['market_score'] if enhanced_score_result else trend_report['trend_strength'].get('market_score', 0)
        breadth_score = enhanced_score_result['breadth_score'] if enhanced_score_result else breadth_indicators.get('breadth_score', 0.5) if breadth_indicators else 0.5
        
        position_recommendations = self.position_rec.get_recommendations(
            regime, confidence, volatility_data,
            market_score=market_score,
            breadth_score=breadth_score
        )
        
        # Add breadth consistency warnings to position recommendations
        if consistency_result['warnings']:
            if 'specific_guidance' not in position_recommendations:
                position_recommendations['specific_guidance'] = []
            # Add warnings at the beginning
            position_recommendations['specific_guidance'] = (
                consistency_result['warnings'] + 
                position_recommendations.get('specific_guidance', [])
            )
            
        # Update recommendation based on divergence
        if consistency_result['recommendation'] == 'avoid_or_reduce':
            position_recommendations['position_size_multiplier'] *= 0.5
            position_recommendations['max_positions'] = max(2, position_recommendations['max_positions'] // 2)
            position_recommendations['avoid'] = "Trading against breadth divergence"
        
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
        
        # Get index analysis
        index_analysis = None
        try:
            index_analysis = self.index_analyzer.analyze_index_trend()
            logger.info(f"Index analysis: {index_analysis['trend']} - {index_analysis['analysis']}")
        except Exception as e:
            logger.error(f"Error getting index analysis: {e}")
            
        # Generate actionable insights
        insights = self._generate_insights(regime, trend_report, prediction, index_analysis)
        
        # Add divergence alert to insights if present
        if divergence_alert:
            insights.insert(0, divergence_alert)
        
        # Prepare complete report
        # Get PCR data for the report
        pcr_data = None
        pcr_signal = None
        try:
            pcr_data = self.pcr_analyzer.get_latest_pcr()
            if pcr_data:
                pcr_adjustment, pcr_weight = self.pcr_analyzer.get_pcr_regime_adjustment(pcr_data)
                pcr_signal = {
                    'pcr_oi': pcr_data.get('pcr_oi'),
                    'pcr_volume': pcr_data.get('pcr_volume'),
                    'pcr_combined': pcr_data.get('pcr_combined'),
                    'sentiment': pcr_data.get('sentiment'),
                    'signal_strength': pcr_data.get('signal_strength'),
                    'regime_adjustment': pcr_adjustment,
                    'adjustment_weight': pcr_weight * 0.20  # 20% weightage
                }
        except Exception as e:
            logger.error(f"Error getting PCR data for report: {e}")
        
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'market_regime': {
                'regime': regime,
                'description': regime_info['description'],
                'characteristics': regime_info['characteristics'],
                'strategy': regime_info['strategy'],
                'confidence': confidence,
                'confidence_level': confidence_level,
                'original_confidence': original_confidence if original_confidence != confidence else None,
                'confidence_adjusted_reason': consistency_result.get('warnings', []) if consistency_result['divergence_type'] != 'none' else None
            },
            'reversal_counts': trend_report['counts'],
            'smoothed_counts': trend_report.get('smoothed_counts', trend_report['counts']),
            'trend_analysis': {
                **trend_report['trend_strength'],
                'enhanced_market_score': enhanced_score_result['market_score'] if enhanced_score_result else None,
                'breadth_score': enhanced_score_result['breadth_score'] if enhanced_score_result else None,
                'weekly_bias': enhanced_score_result['weekly_bias'] if enhanced_score_result else None,
                'enhanced_direction': enhanced_score_result['direction'] if enhanced_score_result else None
            },
            'momentum_analysis': trend_report.get('momentum'),
            'breadth_indicators': breadth_indicators,
            'breadth_consistency': {
                'is_consistent': consistency_result['is_consistent'],
                'divergence_type': consistency_result['divergence_type'],
                'warnings': consistency_result['warnings'],
                'recommendation': consistency_result['recommendation']
            },
            'volatility': volatility_data,
            'index_analysis': index_analysis,
            'position_recommendations': position_recommendations,
            'enhanced_strategy_recommendation': enhanced_score_result['strategy_recommendation'] if enhanced_score_result else None,
            'prediction': prediction,
            'model_performance': self.predictor.get_model_insights(),
            'historical_context': self.history_tracker.get_performance_summary(),
            'insights': insights,
            'scan_files': {
                'long': scan_results.get('long_file'),
                'short': scan_results.get('short_file')
            },
            'pcr_analysis': pcr_signal if pcr_signal else None
        }
        
        # Enhance report with multi-timeframe analysis
        try:
            enhanced_report = self.multi_tf_analyzer.generate_enhanced_analysis(report)
            report = enhanced_report
            logger.info("Successfully added multi-timeframe analysis to report")
        except Exception as e:
            logger.error(f"Error adding multi-timeframe analysis: {e}")
        
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
        
        # Clean NaN values before saving
        cleaned_report = self._clean_nan_values(report)
        
        with open(output_file, 'w') as f:
            json.dump(cleaned_report, f, indent=2)
            
        logger.info(f"Market regime report saved to {output_file}")
        
        # Also save a summary file that always has the same name for easy access
        summary_file = os.path.join(self.output_dir, "latest_regime_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(cleaned_report, f, indent=2)
            
        # Save to central database
        self._save_report_to_db(report)
        
        # Check for regime change and send alert if needed
        try:
            self.regime_notifier.check_regime_change()
        except Exception as e:
            logger.error(f"Error checking regime change: {e}")
            
        return report
    
    def _clean_nan_values(self, obj):
        """Recursively clean NaN values from nested dictionaries and lists"""
        if isinstance(obj, dict):
            return {k: self._clean_nan_values(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_nan_values(item) for item in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, np.float64) or isinstance(obj, np.float32):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.int64) or isinstance(obj, np.int32):
            return int(obj)
        elif hasattr(obj, 'item'):  # numpy scalar
            val = obj.item()
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val
        else:
            return obj
    
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
        
    def _generate_insights(self, regime, trend_report, prediction=None, index_analysis=None):
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
                
        # Index analysis insights
        if index_analysis:
            indices_above = index_analysis.get('indices_above_sma20', 0)
            total_indices = index_analysis.get('total_indices', 3)
            avg_position = index_analysis.get('avg_position', 0)
            
            insights.append(f"\n📈 Index Analysis: {indices_above}/{total_indices} indices above SMA20")
            
            if index_analysis.get('index_details'):
                for idx_name, idx_data in index_analysis['index_details'].items():
                    position = idx_data.get('sma_position_pct', 0)
                    status = "above" if idx_data.get('above_sma20', False) else "below"
                    insights.append(f"  • {idx_name}: {position:+.1f}% {status} SMA20")
            
            # Index-based warnings
            if indices_above == 0 and regime in ['uptrend', 'strong_uptrend']:
                insights.append("⚠️ Warning: All indices below SMA20 despite bullish patterns")
            elif indices_above == total_indices and regime in ['downtrend', 'strong_downtrend']:
                insights.append("⚠️ Warning: All indices above SMA20 despite bearish patterns")
                
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
            
            # Display breadth consistency check results
            if report.get('breadth_consistency'):
                bc = report['breadth_consistency']
                if bc['divergence_type'] != 'none':
                    print(f"\n⚠️  BREADTH-REGIME CONSISTENCY CHECK:")
                    print(f"  Divergence Type: {bc['divergence_type'].upper()}")
                    print(f"  Recommendation: {bc['recommendation'].replace('_', ' ').title()}")
                    if bc['warnings']:
                        print(f"  Warnings:")
                        for warning in bc['warnings']:
                            print(f"    - {warning}")
                    if report['market_regime'].get('original_confidence'):
                        print(f"  Confidence Adjusted: {report['market_regime']['original_confidence']:.1%} → {report['market_regime']['confidence']:.1%}")
            
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
                
            if report.get('index_analysis'):
                idx_analysis = report['index_analysis']
                print(f"\n📈 Index Analysis:")
                print(f"  Trend: {idx_analysis.get('trend', 'N/A')}")
                print(f"  Indices above SMA20: {idx_analysis.get('indices_above_sma20', 0)}/{idx_analysis.get('total_indices', 3)}")
                print(f"  Average position: {idx_analysis.get('avg_position', 0):.1f}%")
                
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