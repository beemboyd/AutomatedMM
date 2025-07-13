#!/usr/bin/env python
"""
Market Indicators Module
=======================
Calculates various market-wide indicators for regime detection.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MarketIndicators:
    """Calculate market-wide indicators for regime detection"""
    
    def __init__(self, base_dir: str = None):
        """Initialize market indicators calculator"""
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        self.base_dir = base_dir
        self.results_dir = os.path.join(base_dir, "results")
        self.data_dir = os.path.join(base_dir, "data")
        
    def calculate_market_breadth(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate market breadth indicators from scan results
        
        Args:
            df: DataFrame with scan results
            
        Returns:
            Dict with breadth indicators
        """
        breadth = {}
        
        # Basic advance/decline
        if 'Direction' in df.columns:
            total_tickers = len(df)
            longs = (df['Direction'] == 'LONG').sum()
            shorts = (df['Direction'] == 'SHORT').sum()
            
            breadth['advance_decline_ratio'] = longs / max(shorts, 1)
            breadth['bullish_percent'] = longs / max(total_tickers, 1)
            breadth['bearish_percent'] = shorts / max(total_tickers, 1)
            
        # Momentum breadth
        if 'Momentum_5D' in df.columns:
            df['Momentum_5D'] = pd.to_numeric(df['Momentum_5D'], errors='coerce').fillna(0)
            
            positive_momentum = (df['Momentum_5D'] > 0).sum()
            negative_momentum = (df['Momentum_5D'] < 0).sum()
            strong_positive = (df['Momentum_5D'] > 10).sum()
            strong_negative = (df['Momentum_5D'] < -10).sum()
            
            breadth['positive_momentum_percent'] = positive_momentum / len(df)
            breadth['strong_momentum_percent'] = strong_positive / len(df)
            breadth['weak_momentum_percent'] = strong_negative / len(df)
            breadth['momentum_ratio'] = positive_momentum / max(negative_momentum, 1)
            
        # Volume breadth
        if 'Volume_Ratio' in df.columns:
            df['Volume_Ratio'] = pd.to_numeric(df['Volume_Ratio'], errors='coerce').fillna(1)
            
            high_volume = (df['Volume_Ratio'] > 1.5).sum()
            breadth['high_volume_percent'] = high_volume / len(df)
            
        # New highs/lows (simplified)
        if 'Score' in df.columns:
            df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
            
            top_scores = (df['Score'] > df['Score'].quantile(0.8)).sum()
            bottom_scores = (df['Score'] < df['Score'].quantile(0.2)).sum()
            
            breadth['high_score_percent'] = top_scores / len(df)
            breadth['low_score_percent'] = bottom_scores / len(df)
            
        return breadth
    
    def calculate_momentum_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate momentum-based indicators"""
        momentum = {}
        
        if 'Momentum_5D' in df.columns:
            df['Momentum_5D'] = pd.to_numeric(df['Momentum_5D'], errors='coerce').fillna(0)
            
            momentum['average_momentum'] = df['Momentum_5D'].mean()
            momentum['median_momentum'] = df['Momentum_5D'].median()
            momentum['momentum_std'] = df['Momentum_5D'].std()
            
            # Momentum distribution
            momentum['extreme_positive'] = (df['Momentum_5D'] > 20).sum() / len(df)
            momentum['extreme_negative'] = (df['Momentum_5D'] < -20).sum() / len(df)
            
            # Momentum skew
            momentum['momentum_skew'] = df['Momentum_5D'].skew()
            momentum['momentum_kurtosis'] = df['Momentum_5D'].kurtosis()
            
        return momentum
    
    def calculate_volatility_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volatility indicators"""
        volatility = {}
        
        # Range-based volatility
        if all(col in df.columns for col in ['Entry', 'Target', 'Stop_Loss']):
            df['Entry'] = pd.to_numeric(df['Entry'], errors='coerce')
            df['Target'] = pd.to_numeric(df['Target'], errors='coerce')
            df['Stop_Loss'] = pd.to_numeric(df['Stop_Loss'], errors='coerce')
            
            # Calculate average range
            df['Range'] = ((df['Target'] - df['Stop_Loss']).abs() / df['Entry']) * 100
            volatility['average_range'] = df['Range'].mean()
            volatility['median_range'] = df['Range'].median()
            
        # Pattern-based volatility
        if 'Pattern' in df.columns:
            pattern_counts = df['Pattern'].value_counts()
            total_patterns = len(df)
            
            # Reversal patterns indicate volatility
            reversal_patterns = ['H H H L', 'L L L H', 'Reversal', 'Double Bottom', 'Double Top']
            reversal_count = sum(pattern_counts.get(p, 0) for p in reversal_patterns 
                               if p in pattern_counts.index)
            
            volatility['reversal_pattern_percent'] = reversal_count / max(total_patterns, 1)
            
        # Score dispersion as volatility proxy
        if 'Score' in df.columns:
            df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
            volatility['score_dispersion'] = df['Score'].std()
            
        return volatility
    
    def calculate_sector_indicators(self, df: pd.DataFrame) -> Dict[str, any]:
        """Calculate sector rotation indicators"""
        sector_data = {}
        
        try:
            # Load sector mapping
            ticker_file = os.path.join(self.data_dir, "Ticker_with_Sector.xlsx")
            if os.path.exists(ticker_file) and 'Ticker' in df.columns:
                sector_df = pd.read_excel(ticker_file)
                ticker_to_sector = dict(zip(sector_df['Ticker'], sector_df['Sector']))
                
                # Add sector to dataframe
                df['Sector'] = df['Ticker'].map(ticker_to_sector).fillna('Unknown')
                
                # Sector momentum
                if 'Momentum_5D' in df.columns:
                    sector_momentum = df.groupby('Sector')['Momentum_5D'].agg(['mean', 'count'])
                    sector_momentum = sector_momentum.sort_values('mean', ascending=False)
                    
                    sector_data['top_sectors'] = sector_momentum.head(5).to_dict()
                    sector_data['bottom_sectors'] = sector_momentum.tail(5).to_dict()
                    sector_data['sector_dispersion'] = sector_momentum['mean'].std()
                
                # Sector concentration
                sector_counts = df['Sector'].value_counts()
                sector_data['sector_concentration'] = sector_counts.head(3).sum() / len(df)
                
                # Direction by sector
                if 'Direction' in df.columns:
                    sector_direction = pd.crosstab(df['Sector'], df['Direction'])
                    if 'LONG' in sector_direction.columns and 'SHORT' in sector_direction.columns:
                        sector_direction['long_bias'] = (
                            sector_direction['LONG'] / 
                            (sector_direction['LONG'] + sector_direction['SHORT'])
                        )
                        sector_data['bullish_sectors'] = sector_direction[
                            sector_direction['long_bias'] > 0.7
                        ].index.tolist()
                        sector_data['bearish_sectors'] = sector_direction[
                            sector_direction['long_bias'] < 0.3
                        ].index.tolist()
                        
        except Exception as e:
            logger.warning(f"Error calculating sector indicators: {e}")
            
        return sector_data
    
    def calculate_pattern_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate pattern-based indicators"""
        patterns = {}
        
        if 'Pattern' in df.columns:
            pattern_counts = df['Pattern'].value_counts()
            total = len(df)
            
            # Categorize patterns
            bullish_patterns = ['H H H L', 'Double Bottom', 'Bull Flag', 'Cup Handle']
            bearish_patterns = ['L L L H', 'Double Top', 'Bear Flag', 'Head Shoulders']
            
            bullish_count = sum(pattern_counts.get(p, 0) for p in bullish_patterns)
            bearish_count = sum(pattern_counts.get(p, 0) for p in bearish_patterns)
            
            patterns['bullish_pattern_percent'] = bullish_count / max(total, 1)
            patterns['bearish_pattern_percent'] = bearish_count / max(total, 1)
            patterns['pattern_bias'] = (bullish_count - bearish_count) / max(total, 1)
            
            # Pattern diversity
            patterns['pattern_diversity'] = len(pattern_counts) / max(total, 1)
            
        return patterns
    
    def calculate_composite_indicators(self, 
                                     breadth: Dict,
                                     momentum: Dict,
                                     volatility: Dict) -> Dict[str, float]:
        """Calculate composite indicators from individual components"""
        composite = {}
        
        # Market Strength Index (0-100)
        strength_components = []
        
        if 'bullish_percent' in breadth:
            strength_components.append(breadth['bullish_percent'] * 100)
        if 'positive_momentum_percent' in breadth:
            strength_components.append(breadth['positive_momentum_percent'] * 100)
        if 'average_momentum' in momentum:
            # Normalize momentum to 0-100 scale
            norm_momentum = max(0, min(100, (momentum['average_momentum'] + 50)))
            strength_components.append(norm_momentum)
            
        if strength_components:
            composite['market_strength_index'] = np.mean(strength_components)
        
        # Volatility Index (normalized)
        if 'average_range' in volatility:
            composite['volatility_index'] = min(100, volatility['average_range'] * 5)
        
        # Trend Quality Score
        if 'momentum_std' in momentum and 'average_momentum' in momentum:
            # Lower std with positive momentum = higher quality trend
            if momentum['average_momentum'] > 0:
                composite['trend_quality'] = max(0, 100 - momentum['momentum_std'] * 2)
            else:
                composite['trend_quality'] = max(0, 50 - momentum['momentum_std'])
                
        # Market Risk Score
        risk_factors = []
        
        if 'bearish_percent' in breadth:
            risk_factors.append(breadth['bearish_percent'] * 100)
        if 'extreme_negative' in momentum:
            risk_factors.append(momentum['extreme_negative'] * 100)
        if 'reversal_pattern_percent' in volatility:
            risk_factors.append(volatility['reversal_pattern_percent'] * 100)
            
        if risk_factors:
            composite['market_risk_score'] = np.mean(risk_factors)
            
        return composite
    
    def get_all_indicators(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate all market indicators
        
        Args:
            df: DataFrame with market scan results
            
        Returns:
            Dict with all calculated indicators
        """
        indicators = {
            'timestamp': datetime.now().isoformat(),
            'data_points': len(df)
        }
        
        # Calculate individual indicator groups
        indicators['breadth'] = self.calculate_market_breadth(df)
        indicators['momentum'] = self.calculate_momentum_indicators(df)
        indicators['volatility'] = self.calculate_volatility_indicators(df)
        indicators['sectors'] = self.calculate_sector_indicators(df)
        indicators['patterns'] = self.calculate_pattern_indicators(df)
        
        # Calculate composite indicators
        indicators['composite'] = self.calculate_composite_indicators(
            indicators['breadth'],
            indicators['momentum'],
            indicators['volatility']
        )
        
        return indicators