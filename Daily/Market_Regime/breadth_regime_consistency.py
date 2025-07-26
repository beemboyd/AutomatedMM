#!/usr/bin/env python
"""
Breadth-Regime Consistency Checker
Validates market regime classifications against market breadth indicators
to prevent false signals and improve reliability
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

class BreadthRegimeConsistencyChecker:
    def __init__(self):
        """Initialize the consistency checker with thresholds"""
        # Divergence thresholds
        self.extreme_divergence_threshold = 0.60  # 60% opposing breadth = extreme
        self.moderate_divergence_threshold = 0.50  # 50% opposing breadth = moderate
        
        # Confidence penalties
        self.extreme_penalty = 0.50  # Reduce confidence by 50%
        self.moderate_penalty = 0.25  # Reduce confidence by 25%
        
        # Minimum confidence levels after penalty
        self.min_confidence_after_penalty = 0.30
        
    def check_consistency(self, regime, breadth_indicators, confidence):
        """
        Check if regime classification is consistent with market breadth
        
        Args:
            regime: Current regime classification
            breadth_indicators: Dict with breadth data
            confidence: Current confidence level
            
        Returns:
            dict: {
                'is_consistent': bool,
                'divergence_type': str ('none', 'moderate', 'extreme'),
                'adjusted_confidence': float,
                'warnings': list,
                'recommendation': str
            }
        """
        result = {
            'is_consistent': True,
            'divergence_type': 'none',
            'adjusted_confidence': confidence,
            'warnings': [],
            'recommendation': 'proceed'
        }
        
        if not breadth_indicators:
            result['warnings'].append("No breadth data available for consistency check")
            return result
            
        # Get breadth percentages
        bullish_pct = breadth_indicators.get('bullish_percent', 0.5)
        bearish_pct = breadth_indicators.get('bearish_percent', 0.5)
        advance_decline_ratio = breadth_indicators.get('advance_decline_ratio', 1.0)
        
        # Define bullish and bearish regimes
        bullish_regimes = ['strong_uptrend', 'uptrend', 'choppy_bullish']
        bearish_regimes = ['strong_downtrend', 'downtrend', 'choppy_bearish']
        
        # Check for divergences
        if regime in bullish_regimes:
            # Check if breadth is bearish during bullish regime
            if bearish_pct > self.extreme_divergence_threshold:
                result['is_consistent'] = False
                result['divergence_type'] = 'extreme'
                result['warnings'].append(
                    f"EXTREME DIVERGENCE: {regime} regime but {bearish_pct:.1%} of stocks are bearish"
                )
                result['adjusted_confidence'] = max(
                    confidence * (1 - self.extreme_penalty),
                    self.min_confidence_after_penalty
                )
                result['recommendation'] = 'avoid_or_reduce'
                
            elif bearish_pct > self.moderate_divergence_threshold:
                result['is_consistent'] = False
                result['divergence_type'] = 'moderate'
                result['warnings'].append(
                    f"MODERATE DIVERGENCE: {regime} regime but {bearish_pct:.1%} of stocks are bearish"
                )
                result['adjusted_confidence'] = max(
                    confidence * (1 - self.moderate_penalty),
                    self.min_confidence_after_penalty
                )
                result['recommendation'] = 'reduce_size'
                
        elif regime in bearish_regimes:
            # Check if breadth is bullish during bearish regime
            if bullish_pct > self.extreme_divergence_threshold:
                result['is_consistent'] = False
                result['divergence_type'] = 'extreme'
                result['warnings'].append(
                    f"EXTREME DIVERGENCE: {regime} regime but {bullish_pct:.1%} of stocks are bullish"
                )
                result['adjusted_confidence'] = max(
                    confidence * (1 - self.extreme_penalty),
                    self.min_confidence_after_penalty
                )
                result['recommendation'] = 'avoid_or_reduce'
                
            elif bullish_pct > self.moderate_divergence_threshold:
                result['is_consistent'] = False
                result['divergence_type'] = 'moderate'
                result['warnings'].append(
                    f"MODERATE DIVERGENCE: {regime} regime but {bullish_pct:.1%} of stocks are bullish"
                )
                result['adjusted_confidence'] = max(
                    confidence * (1 - self.moderate_penalty),
                    self.min_confidence_after_penalty
                )
                result['recommendation'] = 'reduce_size'
        
        # Additional check for advance/decline ratio
        if regime in bullish_regimes and advance_decline_ratio < 0.5:
            result['warnings'].append(
                f"Weak A/D ratio ({advance_decline_ratio:.2f}) for bullish regime"
            )
            if result['divergence_type'] == 'none':
                result['divergence_type'] = 'moderate'
                result['adjusted_confidence'] *= 0.85
                
        elif regime in bearish_regimes and advance_decline_ratio > 2.0:
            result['warnings'].append(
                f"Strong A/D ratio ({advance_decline_ratio:.2f}) contradicts bearish regime"
            )
            if result['divergence_type'] == 'none':
                result['divergence_type'] = 'moderate'
                result['adjusted_confidence'] *= 0.85
        
        # Log the consistency check
        if result['divergence_type'] != 'none':
            logger.warning(f"Breadth-Regime Divergence: {result}")
        else:
            logger.info(f"Breadth-Regime Consistent: {regime} with {bullish_pct:.1%} bullish")
            
        return result
    
    def get_regime_override(self, regime, breadth_indicators):
        """
        Suggest regime override when extreme divergence exists
        
        Args:
            regime: Current regime classification
            breadth_indicators: Dict with breadth data
            
        Returns:
            str or None: Suggested regime override or None
        """
        if not breadth_indicators:
            return None
            
        bullish_pct = breadth_indicators.get('bullish_percent', 0.5)
        bearish_pct = breadth_indicators.get('bearish_percent', 0.5)
        
        # Define bullish and bearish regimes
        bullish_regimes = ['strong_uptrend', 'uptrend']
        bearish_regimes = ['strong_downtrend', 'downtrend']
        
        # Override only in extreme cases
        if regime in bullish_regimes and bearish_pct > 0.70:
            # 70%+ bearish breadth overrides bullish regime
            return 'choppy_bearish'
            
        elif regime in bearish_regimes and bullish_pct > 0.70:
            # 70%+ bullish breadth overrides bearish regime
            return 'choppy_bullish'
            
        return None
    
    def format_divergence_alert(self, regime, breadth_indicators, consistency_result):
        """
        Format a detailed divergence alert for display
        
        Args:
            regime: Current regime
            breadth_indicators: Breadth data
            consistency_result: Result from check_consistency
            
        Returns:
            str: Formatted alert message
        """
        if consistency_result['divergence_type'] == 'none':
            return ""
            
        bullish_pct = breadth_indicators.get('bullish_percent', 0) * 100
        bearish_pct = breadth_indicators.get('bearish_percent', 0) * 100
        
        alert = f"\n🚨 BREADTH-REGIME DIVERGENCE ALERT 🚨\n"
        alert += f"{'='*50}\n"
        alert += f"Regime: {regime}\n"
        alert += f"Market Breadth: {bullish_pct:.1f}% Bullish, {bearish_pct:.1f}% Bearish\n"
        alert += f"Divergence Type: {consistency_result['divergence_type'].upper()}\n"
        alert += f"Confidence Adjustment: {consistency_result['adjusted_confidence']:.2f} "
        alert += f"(from {consistency_result['adjusted_confidence'] / (1 - self.extreme_penalty if consistency_result['divergence_type'] == 'extreme' else 1 - self.moderate_penalty):.2f})\n"
        alert += f"Recommendation: {consistency_result['recommendation'].replace('_', ' ').title()}\n"
        
        if consistency_result['warnings']:
            alert += "\nWarnings:\n"
            for warning in consistency_result['warnings']:
                alert += f"  • {warning}\n"
                
        alert += f"{'='*50}\n"
        
        return alert