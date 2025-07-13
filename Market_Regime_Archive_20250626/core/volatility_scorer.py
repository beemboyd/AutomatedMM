"""
Volatility Scoring System

Comprehensive volatility analysis using market indices and individual ticker data.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


class MarketSegment(Enum):
    """Market capitalization segments"""
    LARGE_CAP = "NIFTY100"
    MID_CAP = "CNXMIDCAP" 
    SMALL_CAP = "CNXSMALLCAP"
    

@dataclass
class VolatilityMetrics:
    """Container for volatility metrics"""
    ticker: str
    segment: MarketSegment
    
    # Price-based volatility
    historical_vol_20d: float
    historical_vol_50d: float
    atr_14d: float
    atr_percent: float
    intraday_range_avg: float
    
    # Relative metrics
    beta: float
    relative_vol_to_index: float
    relative_vol_to_sector: float
    
    # Advanced metrics
    gap_volatility: float
    volume_volatility: float
    volatility_of_volatility: float  # How stable is the volatility itself
    
    # Composite score
    volatility_score: float
    volatility_regime: str  # Low, Normal, High, Extreme


class VolatilityScoringSystem:
    """
    Comprehensive volatility scoring system combining index and ticker data
    """
    
    def __init__(self, kite_client=None):
        self.kite = kite_client
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.base_dir, "Market_Regime", "volatility_data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Index symbols for NSE
        self.indices = {
            MarketSegment.LARGE_CAP: "NIFTY 50",
            MarketSegment.MID_CAP: "NIFTY MIDCAP 100", 
            MarketSegment.SMALL_CAP: "NIFTY SMLCAP 100"
        }
        
        # Volatility regime thresholds
        self.vol_regimes = {
            'extreme': 75,    # > 75 score
            'high': 50,       # 50-75 score
            'normal': 25,     # 25-50 score
            'low': 0          # 0-25 score
        }
        
        # Cache for index data
        self._index_cache = {}
        self._cache_timestamp = {}
        
    def calculate_market_volatility_from_scanner(self, scanner_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate aggregate volatility metrics from scanner data
        
        Args:
            scanner_df: DataFrame with scanner results containing ATR, Volume_Ratio, etc.
            
        Returns:
            Dict with volatility metrics
        """
        try:
            volatility_metrics = {}
            
            # Basic volatility from ATR
            if 'ATR' in scanner_df.columns and 'Entry_Price' in scanner_df.columns:
                scanner_df['ATR_Percent'] = (scanner_df['ATR'] / scanner_df['Entry_Price']) * 100
                volatility_metrics['avg_atr_percent'] = scanner_df['ATR_Percent'].mean()
                volatility_metrics['median_atr_percent'] = scanner_df['ATR_Percent'].median()
                volatility_metrics['max_atr_percent'] = scanner_df['ATR_Percent'].max()
                
                # Classify volatility distribution
                high_vol_threshold = 3.0  # 3% ATR
                volatility_metrics['high_volatility_count'] = (scanner_df['ATR_Percent'] > high_vol_threshold).sum()
                volatility_metrics['high_volatility_percent'] = (volatility_metrics['high_volatility_count'] / len(scanner_df)) * 100
            
            # Volume expansion/contraction
            if 'Volume_Ratio' in scanner_df.columns:
                volatility_metrics['avg_volume_ratio'] = scanner_df['Volume_Ratio'].mean()
                volatility_metrics['volume_expansion_count'] = (scanner_df['Volume_Ratio'] > 1.5).sum()
                volatility_metrics['volume_contraction_count'] = (scanner_df['Volume_Ratio'] < 0.5).sum()
            
            # Risk metrics from stop loss distances
            if 'Risk' in scanner_df.columns and 'Entry_Price' in scanner_df.columns:
                scanner_df['Risk_Percent'] = (scanner_df['Risk'] / scanner_df['Entry_Price']) * 100
                volatility_metrics['avg_risk_percent'] = scanner_df['Risk_Percent'].mean()
                
            # Direction-based volatility
            if 'Direction' in scanner_df.columns:
                long_data = scanner_df[scanner_df['Direction'] == 'LONG']
                short_data = scanner_df[scanner_df['Direction'] == 'SHORT']
                
                if len(long_data) > 0:
                    volatility_metrics['long_avg_atr_percent'] = long_data['ATR_Percent'].mean() if 'ATR_Percent' in long_data.columns else 0
                    
                if len(short_data) > 0:
                    volatility_metrics['short_avg_atr_percent'] = short_data['ATR_Percent'].mean() if 'ATR_Percent' in short_data.columns else 0
                    
                # Volatility asymmetry
                if len(long_data) > 0 and len(short_data) > 0:
                    volatility_metrics['volatility_asymmetry'] = abs(
                        volatility_metrics.get('long_avg_atr_percent', 0) - 
                        volatility_metrics.get('short_avg_atr_percent', 0)
                    )
            
            # Calculate composite volatility score
            volatility_score = self._calculate_scanner_volatility_score(volatility_metrics)
            volatility_metrics['volatility_score'] = volatility_score
            volatility_metrics['volatility_regime'] = self._determine_volatility_regime(volatility_score)
            
            # Add timestamp
            volatility_metrics['timestamp'] = datetime.now().isoformat()
            
            return volatility_metrics
            
        except Exception as e:
            logger.error(f"Error calculating market volatility from scanner: {e}")
            return {
                'volatility_score': 50.0,
                'volatility_regime': 'normal',
                'error': str(e)
            }
    
    def _calculate_scanner_volatility_score(self, metrics: Dict[str, float]) -> float:
        """
        Calculate composite volatility score from scanner metrics (0-100)
        """
        score_components = []
        
        # ATR component (0-5% ATR maps to 0-100)
        if 'avg_atr_percent' in metrics:
            atr_score = min(100, (metrics['avg_atr_percent'] / 5.0) * 100)
            score_components.append(('atr', atr_score, 0.35))
        
        # High volatility prevalence (0-50% of stocks with high vol maps to 0-100)
        if 'high_volatility_percent' in metrics:
            high_vol_score = min(100, (metrics['high_volatility_percent'] / 50.0) * 100)
            score_components.append(('high_vol_prevalence', high_vol_score, 0.25))
        
        # Volume expansion (avg volume ratio 0-3 maps to 0-100)
        if 'avg_volume_ratio' in metrics:
            volume_score = min(100, (metrics['avg_volume_ratio'] / 3.0) * 100)
            score_components.append(('volume', volume_score, 0.20))
        
        # Risk percentage (0-10% risk maps to 0-100)
        if 'avg_risk_percent' in metrics:
            risk_score = min(100, (metrics['avg_risk_percent'] / 10.0) * 100)
            score_components.append(('risk', risk_score, 0.15))
        
        # Volatility asymmetry (0-2% difference maps to 0-100)
        if 'volatility_asymmetry' in metrics:
            asymmetry_score = min(100, (metrics['volatility_asymmetry'] / 2.0) * 100)
            score_components.append(('asymmetry', asymmetry_score, 0.05))
        
        # Calculate weighted average
        if score_components:
            total_weight = sum(weight for _, _, weight in score_components)
            weighted_score = sum(score * weight for _, score, weight in score_components) / total_weight
            return round(weighted_score, 2)
        
        return 50.0  # Default to normal volatility
    
    def _determine_volatility_regime(self, score: float) -> str:
        """
        Determine volatility regime based on score
        """
        if score >= self.vol_regimes['extreme']:
            return "extreme"
        elif score >= self.vol_regimes['high']:
            return "high"
        elif score >= self.vol_regimes['normal']:
            return "normal"
        else:
            return "low"
    
    def analyze_sector_volatility(self, scanner_df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Analyze volatility by sector
        """
        sector_volatility = {}
        
        if 'Sector' not in scanner_df.columns:
            return sector_volatility
        
        # Calculate ATR percentage if not already present
        if 'ATR_Percent' not in scanner_df.columns and 'ATR' in scanner_df.columns and 'Entry_Price' in scanner_df.columns:
            scanner_df['ATR_Percent'] = (scanner_df['ATR'] / scanner_df['Entry_Price']) * 100
        
        # Group by sector
        for sector in scanner_df['Sector'].unique():
            sector_data = scanner_df[scanner_df['Sector'] == sector]
            
            sector_metrics = {
                'ticker_count': len(sector_data),
                'avg_atr_percent': sector_data['ATR_Percent'].mean() if 'ATR_Percent' in sector_data.columns else 0,
                'max_atr_percent': sector_data['ATR_Percent'].max() if 'ATR_Percent' in sector_data.columns else 0,
                'avg_volume_ratio': sector_data['Volume_Ratio'].mean() if 'Volume_Ratio' in sector_data.columns else 1.0
            }
            
            # Calculate sector volatility score
            sector_score = min(100, (sector_metrics['avg_atr_percent'] / 5.0) * 100)
            sector_metrics['volatility_score'] = round(sector_score, 2)
            sector_metrics['volatility_regime'] = self._determine_volatility_regime(sector_score)
            
            sector_volatility[sector] = sector_metrics
        
        return sector_volatility
    
    def generate_volatility_insights(self, 
                                   market_vol: Dict[str, float],
                                   sector_vol: Dict[str, Dict],
                                   scanner_df: pd.DataFrame) -> List[str]:
        """
        Generate actionable volatility insights
        """
        insights = []
        
        # Market regime insight
        regime = market_vol.get('volatility_regime', 'normal')
        score = market_vol.get('volatility_score', 50)
        
        if regime == 'extreme':
            insights.append(f"⚠️ Market in EXTREME volatility (score: {score:.1f}) - Consider reducing position sizes by 50%")
        elif regime == 'high':
            insights.append(f"📊 Market showing HIGH volatility (score: {score:.1f}) - Use wider stops (1.5x normal) and smaller positions")
        elif regime == 'low':
            insights.append(f"😴 Market in LOW volatility (score: {score:.1f}) - Watch for breakout opportunities, tighten stops")
        else:
            insights.append(f"✅ Market volatility NORMAL (score: {score:.1f}) - Standard position sizing appropriate")
        
        # Volume insights
        if market_vol.get('avg_volume_ratio', 1.0) > 2.0:
            insights.append("📈 High volume expansion detected - Increased participation suggests conviction")
        elif market_vol.get('avg_volume_ratio', 1.0) < 0.5:
            insights.append("📉 Low volume environment - Be cautious of false breakouts")
        
        # High volatility stock alerts
        if 'ATR_Percent' in scanner_df.columns:
            extreme_vol_stocks = scanner_df[scanner_df['ATR_Percent'] > 4.0]
            if len(extreme_vol_stocks) > 0:
                tickers = extreme_vol_stocks.nlargest(5, 'ATR_Percent')['Ticker'].tolist()
                insights.append(f"🌊 Extreme volatility (>4% ATR) in: {', '.join(tickers)}")
        
        # Sector insights
        if sector_vol:
            high_vol_sectors = [s for s, m in sector_vol.items() if m.get('volatility_score', 0) > 60]
            if high_vol_sectors:
                insights.append(f"🔥 High volatility sectors: {', '.join(high_vol_sectors[:3])}")
            
            low_vol_sectors = [s for s, m in sector_vol.items() if m.get('volatility_score', 0) < 30]
            if low_vol_sectors:
                insights.append(f"🛡️ Low volatility sectors: {', '.join(low_vol_sectors[:3])}")
        
        # Direction-based insights
        if 'volatility_asymmetry' in market_vol and market_vol['volatility_asymmetry'] > 1.0:
            if market_vol.get('long_avg_atr_percent', 0) > market_vol.get('short_avg_atr_percent', 0):
                insights.append("📊 Long positions showing higher volatility than shorts - Bullish momentum building")
            else:
                insights.append("📊 Short positions showing higher volatility than longs - Bearish pressure increasing")
        
        # Risk management recommendations
        avg_atr = market_vol.get('avg_atr_percent', 2.5)
        if avg_atr > 3.5:
            insights.append(f"⚠️ Average ATR {avg_atr:.1f}% - Recommend position size: 50-70% of normal")
        elif avg_atr < 2.0:
            insights.append(f"✅ Average ATR {avg_atr:.1f}% - Can use full position sizes with tight stops")
        
        return insights
    
    def save_volatility_analysis(self, analysis: Dict[str, any]):
        """
        Save volatility analysis to file
        """
        try:
            # Save to JSON
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_path = os.path.join(self.data_dir, f'volatility_analysis_{timestamp}.json')
            
            with open(json_path, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
            
            # Also save as latest
            latest_path = os.path.join(self.data_dir, 'volatility_analysis_latest.json')
            with open(latest_path, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
            
            logger.info(f"Volatility analysis saved to {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving volatility analysis: {e}")


# Standalone function for integration
def calculate_volatility_score_from_scanner(scanner_df: pd.DataFrame) -> Dict[str, any]:
    """
    Convenience function to calculate volatility score from scanner data
    
    Args:
        scanner_df: DataFrame with scanner results
        
    Returns:
        Dict with volatility analysis
    """
    scorer = VolatilityScoringSystem()
    
    # Calculate market volatility
    market_volatility = scorer.calculate_market_volatility_from_scanner(scanner_df)
    
    # Analyze sector volatility
    sector_volatility = scorer.analyze_sector_volatility(scanner_df)
    
    # Generate insights
    insights = scorer.generate_volatility_insights(
        market_volatility,
        sector_volatility,
        scanner_df
    )
    
    # Compile analysis
    analysis = {
        'market_volatility': market_volatility,
        'sector_volatility': sector_volatility,
        'insights': insights,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save analysis
    scorer.save_volatility_analysis(analysis)
    
    return analysis