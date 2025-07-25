#!/usr/bin/env python
"""
Multi-Timeframe Market Regime Analyzer
Enhances regime predictions by analyzing multiple timeframes
"""

import os
import sys
import logging
import datetime
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TimeframeAnalysis:
    """Container for timeframe-specific analysis"""
    timeframe: str
    long_count: int
    short_count: int
    ratio: float
    regime: str
    trend_strength: float
    confidence: float
    data_points: int

class MultiTimeframeAnalyzer:
    """Analyzes market regime across multiple timeframes"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, "data")
        
        # Timeframe definitions (in days)
        self.timeframes = {
            'daily': 1,
            'weekly': 5,
            'biweekly': 10,
            'monthly': 20
        }
        
        # Timeframe weights for combined analysis
        self.timeframe_weights = {
            'daily': 0.4,
            'weekly': 0.4,
            'biweekly': 0.15,
            'monthly': 0.05
        }
        
        # Load historical data
        self.scan_history = self._load_scan_history()
        
    def _load_scan_history(self) -> pd.DataFrame:
        """Load historical scan data"""
        try:
            # First try to load the comprehensive historical data
            historical_file = os.path.join(self.data_dir, "historical_scan_data.json")
            if os.path.exists(historical_file):
                with open(historical_file, 'r') as f:
                    historical_data = json.load(f)
            else:
                historical_data = []
            
            # Then load the current scan history
            history_file = os.path.join(self.data_dir, "scan_history.json")
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    current_data = json.load(f)
            else:
                current_data = []
            
            # Combine both datasets
            all_data = historical_data + current_data
            
            if not all_data:
                logger.warning("No scan history found")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(all_data)
            # Handle mixed timestamp formats
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
            
            # Remove duplicates based on timestamp (keep last)
            df = df.sort_values('timestamp')
            df = df.drop_duplicates(subset=['timestamp'], keep='last')
            
            # Add date column for grouping
            df['date'] = df['timestamp'].dt.date
            
            logger.info(f"Loaded {len(df)} historical scan records (from {df['date'].min()} to {df['date'].max()})")
            return df
        except Exception as e:
            logger.error(f"Error loading scan history: {e}")
            return pd.DataFrame()
    
    def calculate_timeframe_ratio(self, days: int) -> Optional[TimeframeAnalysis]:
        """Calculate L/S ratio for a specific timeframe"""
        if self.scan_history.empty:
            return None
            
        try:
            # Get data for the specified number of days
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            timeframe_data = self.scan_history[self.scan_history['timestamp'] >= cutoff_date]
            
            if timeframe_data.empty:
                return None
            
            # Group by date and take the latest entry for each day
            daily_data = timeframe_data.groupby('date').last().reset_index()
            
            # Debug logging
            logger.debug(f"Timeframe {days}d: {len(daily_data)} days of data, date range: {daily_data['date'].min()} to {daily_data['date'].max()}")
            
            # Calculate aggregated counts
            total_long = daily_data['long_count'].sum()
            total_short = daily_data['short_count'].sum()
            
            if total_short == 0:
                ratio = float('inf')
            else:
                ratio = total_long / total_short
            
            # Determine regime based on ratio
            regime = self._classify_regime(ratio)
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(ratio)
            
            # Calculate confidence based on data points
            confidence = min(1.0, len(daily_data) / days)  # Penalize if missing data
            
            timeframe_name = next((k for k, v in self.timeframes.items() if v == days), f"{days}d")
            
            return TimeframeAnalysis(
                timeframe=timeframe_name,
                long_count=int(total_long),
                short_count=int(total_short),
                ratio=round(ratio, 3),
                regime=regime,
                trend_strength=round(trend_strength, 3),
                confidence=round(confidence, 3),
                data_points=len(daily_data)
            )
            
        except Exception as e:
            logger.error(f"Error calculating {days}-day ratio: {e}")
            return None
    
    def _classify_regime(self, ratio: float) -> str:
        """Classify regime based on L/S ratio"""
        if ratio >= 2.0:
            return "strong_uptrend"
        elif ratio >= 1.5:
            return "uptrend"
        elif ratio >= 1.2:
            return "choppy_bullish"
        elif ratio >= 0.8:
            return "choppy"
        elif ratio >= 0.67:
            return "choppy_bearish"
        elif ratio >= 0.5:
            return "downtrend"
        else:
            return "strong_downtrend"
    
    def _calculate_trend_strength(self, ratio: float) -> float:
        """Calculate trend strength from ratio"""
        # Convert ratio to a -1 to 1 scale
        if ratio >= 1:
            # Bullish: map 1 to inf -> 0 to 1
            strength = min(1.0, (ratio - 1) / 2)
        else:
            # Bearish: map 0 to 1 -> -1 to 0
            strength = max(-1.0, (ratio - 1))
        
        return strength
    
    def analyze_all_timeframes(self) -> Dict[str, TimeframeAnalysis]:
        """Analyze all configured timeframes"""
        results = {}
        
        for timeframe, days in self.timeframes.items():
            analysis = self.calculate_timeframe_ratio(days)
            if analysis:
                results[timeframe] = analysis
                logger.info(f"{timeframe.upper()}: L/S={analysis.ratio}, "
                          f"Regime={analysis.regime}, Confidence={analysis.confidence}")
        
        return results
    
    def calculate_alignment_score(self, analyses: Dict[str, TimeframeAnalysis]) -> float:
        """Calculate how well timeframes align (0-1 scale)"""
        if len(analyses) < 2:
            return 0.5
        
        regimes = [a.regime for a in analyses.values()]
        trend_strengths = [a.trend_strength for a in analyses.values()]
        
        # Check regime alignment
        regime_alignment = len(set(regimes)) / len(regimes)  # 1/n = all same, 1 = all different
        regime_score = 1 - regime_alignment + (1/len(regimes))  # Invert and normalize
        
        # Check trend direction alignment
        positive_trends = sum(1 for ts in trend_strengths if ts > 0)
        trend_alignment = abs(positive_trends - len(trend_strengths)/2) / (len(trend_strengths)/2)
        
        # Combined score
        alignment_score = (regime_score * 0.6 + trend_alignment * 0.4)
        
        return round(alignment_score, 3)
    
    def combine_timeframe_signals(self, analyses: Dict[str, TimeframeAnalysis]) -> Dict:
        """Combine signals from multiple timeframes"""
        if not analyses:
            return None
        
        # Calculate weighted averages
        weighted_ratio = 0
        weighted_strength = 0
        total_weight = 0
        
        for timeframe, analysis in analyses.items():
            weight = self.timeframe_weights.get(timeframe, 0.1) * analysis.confidence
            weighted_ratio += analysis.ratio * weight
            weighted_strength += analysis.trend_strength * weight
            total_weight += weight
        
        if total_weight == 0:
            return None
        
        # Normalize
        combined_ratio = weighted_ratio / total_weight
        combined_strength = weighted_strength / total_weight
        
        # Determine combined regime
        combined_regime = self._classify_regime(combined_ratio)
        
        # Calculate confidence boost/penalty from alignment
        alignment_score = self.calculate_alignment_score(analyses)
        base_confidence = sum(a.confidence * self.timeframe_weights.get(a.timeframe, 0.1) 
                            for a in analyses.values())
        
        # Boost confidence if aligned, reduce if divergent
        if alignment_score > 0.8:
            confidence_multiplier = 1.2
        elif alignment_score < 0.4:
            confidence_multiplier = 0.8
        else:
            confidence_multiplier = 1.0
        
        adjusted_confidence = min(1.0, base_confidence * confidence_multiplier)
        
        return {
            'combined_ratio': round(combined_ratio, 3),
            'combined_strength': round(combined_strength, 3),
            'combined_regime': combined_regime,
            'alignment_score': alignment_score,
            'confidence': round(adjusted_confidence, 3),
            'confidence_adjustment': round(confidence_multiplier, 2)
        }
    
    def get_timeframe_divergences(self, analyses: Dict[str, TimeframeAnalysis]) -> List[str]:
        """Identify divergences between timeframes"""
        divergences = []
        
        if len(analyses) < 2:
            return divergences
        
        # Get daily and weekly analyses
        daily = analyses.get('daily')
        weekly = analyses.get('weekly')
        
        if daily and weekly:
            # Check for regime divergence
            if daily.regime != weekly.regime:
                daily_bullish = daily.trend_strength > 0
                weekly_bullish = weekly.trend_strength > 0
                
                if daily_bullish and not weekly_bullish:
                    divergences.append("Daily bullish but weekly bearish - potential reversal down")
                elif not daily_bullish and weekly_bullish:
                    divergences.append("Daily bearish but weekly bullish - potential reversal up")
            
            # Check for extreme divergence in ratios
            ratio_diff = abs(daily.ratio - weekly.ratio)
            if ratio_diff > 0.5:
                if daily.ratio > weekly.ratio:
                    divergences.append("Daily momentum stronger than weekly - may not sustain")
                else:
                    divergences.append("Weekly momentum stronger than daily - trend building")
        
        return divergences
    
    def generate_enhanced_analysis(self, current_regime_data: Dict) -> Dict:
        """Generate enhanced regime analysis with multi-timeframe data"""
        # Get timeframe analyses
        timeframe_analyses = self.analyze_all_timeframes()
        
        if not timeframe_analyses:
            logger.warning("No timeframe data available")
            return current_regime_data
        
        # Combine signals
        combined_analysis = self.combine_timeframe_signals(timeframe_analyses)
        
        if not combined_analysis:
            return current_regime_data
        
        # Get divergences
        divergences = self.get_timeframe_divergences(timeframe_analyses)
        
        # Enhanced regime data
        enhanced_data = current_regime_data.copy()
        
        # Add multi-timeframe section
        enhanced_data['multi_timeframe_analysis'] = {
            'timeframes': {
                tf: {
                    'long_count': analysis.long_count,
                    'short_count': analysis.short_count,
                    'ratio': analysis.ratio,
                    'regime': analysis.regime,
                    'trend_strength': analysis.trend_strength,
                    'confidence': analysis.confidence,
                    'data_points': analysis.data_points
                }
                for tf, analysis in timeframe_analyses.items()
            },
            'combined_signals': combined_analysis,
            'divergences': divergences,
            'recommendation': self._generate_recommendation(
                timeframe_analyses, 
                combined_analysis, 
                divergences
            )
        }
        
        # Adjust main confidence if multi-timeframe shows divergence
        if combined_analysis['alignment_score'] < 0.5:
            current_confidence = enhanced_data.get('market_regime', {}).get('confidence', 0.5)
            adjusted_confidence = current_confidence * combined_analysis['confidence_adjustment']
            enhanced_data['market_regime']['confidence'] = round(adjusted_confidence, 3)
            enhanced_data['market_regime']['confidence_note'] = "Reduced due to timeframe divergence"
        
        return enhanced_data
    
    def _generate_recommendation(self, analyses: Dict, combined: Dict, divergences: List) -> str:
        """Generate actionable recommendation based on multi-timeframe analysis"""
        daily = analyses.get('daily')
        weekly = analyses.get('weekly')
        
        if not daily or not weekly:
            return "Insufficient data for multi-timeframe recommendation"
        
        # Strong alignment
        if combined['alignment_score'] > 0.8:
            if combined['combined_regime'] in ['strong_uptrend', 'uptrend']:
                return "Strong bullish alignment across timeframes - aggressive long positions recommended"
            elif combined['combined_regime'] in ['strong_downtrend', 'downtrend']:
                return "Strong bearish alignment across timeframes - aggressive short positions recommended"
            else:
                return "Timeframes aligned in neutral zone - range trading recommended"
        
        # Divergence
        elif combined['alignment_score'] < 0.4:
            if divergences:
                return f"Caution: {divergences[0]}. Reduce position sizes and wait for alignment"
            else:
                return "Mixed signals across timeframes - stay cautious with smaller positions"
        
        # Moderate alignment
        else:
            if combined['combined_strength'] > 0.3:
                return "Moderate bullish bias across timeframes - selective long positions"
            elif combined['combined_strength'] < -0.3:
                return "Moderate bearish bias across timeframes - selective short positions"
            else:
                return "No clear directional bias - focus on high-probability setups only"


def main():
    """Test the multi-timeframe analyzer"""
    analyzer = MultiTimeframeAnalyzer()
    
    # Analyze all timeframes
    print("\n=== Multi-Timeframe Analysis ===")
    analyses = analyzer.analyze_all_timeframes()
    
    # Combine signals
    if analyses:
        combined = analyzer.combine_timeframe_signals(analyses)
        print(f"\nCombined Analysis:")
        print(f"  Combined Ratio: {combined['combined_ratio']}")
        print(f"  Combined Regime: {combined['combined_regime']}")
        print(f"  Alignment Score: {combined['alignment_score']}")
        print(f"  Confidence: {combined['confidence']}")
        
        # Check divergences
        divergences = analyzer.get_timeframe_divergences(analyses)
        if divergences:
            print("\nDivergences:")
            for d in divergences:
                print(f"  - {d}")


if __name__ == "__main__":
    main()