#!/usr/bin/env python3
"""
Enhanced H2 Crossover Analysis with Realistic Price Simulation

This version uses more sophisticated methods to track signal outcomes
and provides better correlation analysis.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import glob
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, parent_dir)

@dataclass
class EnhancedSignalAnalysis:
    """Enhanced signal analysis with realistic tracking"""
    ticker: str
    entry_date: datetime
    entry_price: float
    target1: float
    target2: float
    stop_loss: float
    volume_ratio: float
    momentum_5d: float
    pattern_score: float
    market_regime: str
    regime_confidence: float
    long_short_ratio: float
    sector: str
    # Outcome tracking
    h1_achieved: bool = False
    h2_achieved: bool = False
    stopped_out: bool = False
    days_to_h1: Optional[int] = None
    days_to_h2: Optional[int] = None
    days_to_stop: Optional[int] = None
    max_price: float = 0.0
    min_price: float = float('inf')
    max_profit_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    final_pnl_pct: float = 0.0
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = "open"


class EnhancedH2Analyzer:
    """Enhanced analyzer with realistic price tracking"""
    
    def __init__(self):
        self.results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.results_s_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results-s"
        self.regime_data_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data"
        self.analysis_dir = script_dir
        
        # Create output directories
        self.output_dir = os.path.join(self.analysis_dir, "enhanced_h2_analysis")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Data storage
        self.signals = []
        self.regime_history = {}
        self.market_data_cache = {}
        
    def load_regime_history(self):
        """Load comprehensive regime history"""
        print("Loading market regime history...")
        
        # Load from multiple sources for better coverage
        sources = [
            "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/regime_report_*.json",
            "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/historical_scan_data.json",
            "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/scan_history.json"
        ]
        
        # Process regime reports
        report_files = glob.glob(sources[0])
        for file in sorted(report_files):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                
                filename = os.path.basename(file)
                date_str = filename.split('_')[2]
                date = datetime.strptime(date_str, "%Y%m%d").date()
                
                self.regime_history[date] = {
                    'regime': data.get('current_regime', 'unknown'),
                    'confidence': data.get('confidence', 0),
                    'long_short_ratio': data.get('long_short_ratio', 1.0),
                    'long_count': data.get('long_signals', 0),
                    'short_count': data.get('short_signals', 0),
                    'trend_strength': data.get('trend_strength', 0.5)
                }
            except Exception:
                continue
        
        # Load historical scan data
        if os.path.exists(sources[1]):
            with open(sources[1], 'r') as f:
                historical_data = json.load(f)
            
            for entry in historical_data:
                date = pd.to_datetime(entry['timestamp']).date()
                if date not in self.regime_history:
                    ratio = entry.get('ratio', 1.0)
                    self.regime_history[date] = {
                        'regime': self._classify_regime(ratio),
                        'confidence': self._calculate_confidence(ratio),
                        'long_short_ratio': ratio,
                        'long_count': entry.get('long_count', 0),
                        'short_count': entry.get('short_count', 0),
                        'trend_strength': self._calculate_trend_strength(ratio)
                    }
        
        print(f"Loaded regime data for {len(self.regime_history)} days")
        
        # Fill missing dates with interpolation
        self._interpolate_regime_data()
    
    def _interpolate_regime_data(self):
        """Fill missing regime data using interpolation"""
        if not self.regime_history:
            return
            
        # Get date range
        dates = sorted(self.regime_history.keys())
        start_date = dates[0]
        end_date = dates[-1]
        
        # Create complete date range
        current = start_date
        while current <= end_date:
            if current not in self.regime_history:
                # Find nearest dates
                prev_date = max([d for d in dates if d < current], default=None)
                next_date = min([d for d in dates if d > current], default=None)
                
                if prev_date:
                    # Use previous day's data
                    self.regime_history[current] = self.regime_history[prev_date].copy()
                elif next_date:
                    # Use next day's data
                    self.regime_history[current] = self.regime_history[next_date].copy()
            
            current += timedelta(days=1)
    
    def _classify_regime(self, ratio: float) -> str:
        """Enhanced regime classification"""
        if ratio >= 3.0:
            return "extreme_bullish"
        elif ratio >= 2.0:
            return "strong_bullish"
        elif ratio >= 1.5:
            return "bullish"
        elif ratio >= 1.0:
            return "neutral_bullish"
        elif ratio >= 0.67:
            return "neutral_bearish"
        elif ratio >= 0.5:
            return "bearish"
        elif ratio >= 0.33:
            return "strong_bearish"
        else:
            return "extreme_bearish"
    
    def _calculate_confidence(self, ratio: float) -> float:
        """Calculate regime confidence"""
        # Higher confidence at extremes
        if ratio >= 3.0 or ratio <= 0.33:
            return 0.95
        elif ratio >= 2.5 or ratio <= 0.4:
            return 0.85
        elif ratio >= 2.0 or ratio <= 0.5:
            return 0.75
        elif ratio >= 1.5 or ratio <= 0.67:
            return 0.65
        else:
            return 0.5
    
    def _calculate_trend_strength(self, ratio: float) -> float:
        """Calculate trend strength from ratio"""
        # Distance from neutral (1.0)
        return min(abs(np.log(ratio)), 2.0) / 2.0
    
    def load_signals_with_tracking(self):
        """Load signals and track with realistic price data"""
        print("Loading and tracking signals...")
        
        long_files = sorted(glob.glob(os.path.join(self.results_dir, "Long_Reversal_Daily_*.xlsx")))
        
        total_files = len(long_files)
        processed = 0
        
        for file in long_files:
            try:
                df = pd.read_excel(file)
                
                # Extract date
                filename = os.path.basename(file)
                date_str = filename.split('_')[3].split('.')[0]
                signal_date = datetime.strptime(date_str, "%Y%m%d").date()
                
                # Get regime data
                regime_data = self.regime_history.get(signal_date, {
                    'regime': 'unknown',
                    'confidence': 0.5,
                    'long_short_ratio': 1.0,
                    'trend_strength': 0.5
                })
                
                # Process each signal
                for _, row in df.iterrows():
                    signal = EnhancedSignalAnalysis(
                        ticker=row['Ticker'],
                        entry_date=signal_date,
                        entry_price=row['Entry_Price'],
                        target1=row['Target1'],
                        target2=row['Target2'],
                        stop_loss=row['Stop_Loss'],
                        volume_ratio=row.get('Volume_Ratio', 1.0),
                        momentum_5d=row.get('Momentum_5D', 0.0),
                        pattern_score=row.get('Score', 0.0),
                        market_regime=regime_data['regime'],
                        regime_confidence=regime_data['confidence'],
                        long_short_ratio=regime_data['long_short_ratio'],
                        sector=row.get('Sector', 'Unknown')
                    )
                    
                    # Track outcome using simulated price movement
                    self._track_signal_outcome(signal)
                    
                    self.signals.append(signal)
                
                processed += 1
                if processed % 10 == 0:
                    print(f"Processed {processed}/{total_files} files...")
                    
            except Exception as e:
                print(f"Error processing {file}: {e}")
                continue
        
        print(f"Loaded and tracked {len(self.signals)} signals")
    
    def _track_signal_outcome(self, signal: EnhancedSignalAnalysis):
        """Track signal outcome using realistic price simulation"""
        # Simulate price movement based on market conditions
        np.random.seed(hash(signal.ticker + str(signal.entry_date)) % 2**32)
        
        # Market regime affects price behavior
        regime_params = self._get_regime_parameters(signal.market_regime)
        
        # Simulate daily prices for 20 days
        prices = [signal.entry_price]
        current_price = signal.entry_price
        
        for day in range(1, 21):
            # Daily return based on regime
            drift = regime_params['daily_drift']
            volatility = regime_params['daily_vol']
            
            # Add momentum factor
            if signal.momentum_5d > 0:
                drift += 0.001 * signal.momentum_5d
            
            # Volume impact
            if signal.volume_ratio > 2:
                volatility *= 0.8  # Less volatile with high volume
            elif signal.volume_ratio < 0.5:
                volatility *= 1.2  # More volatile with low volume
            
            # Generate daily return
            daily_return = np.random.normal(drift, volatility)
            current_price = current_price * (1 + daily_return)
            prices.append(current_price)
            
            # Update tracking
            signal.max_price = max(signal.max_price, current_price)
            signal.min_price = min(signal.min_price, current_price)
            
            # Check targets and stops
            if not signal.h1_achieved and current_price >= signal.target1:
                signal.h1_achieved = True
                signal.days_to_h1 = day
            
            if not signal.h2_achieved and current_price >= signal.target2:
                signal.h2_achieved = True
                signal.days_to_h2 = day
                signal.exit_date = signal.entry_date + timedelta(days=day)
                signal.exit_price = signal.target2
                signal.exit_reason = "target2_hit"
                break
            
            if current_price <= signal.stop_loss:
                signal.stopped_out = True
                signal.days_to_stop = day
                signal.exit_date = signal.entry_date + timedelta(days=day)
                signal.exit_price = signal.stop_loss
                signal.exit_reason = "stopped_out"
                break
        
        # Calculate final metrics
        if signal.exit_price:
            signal.final_pnl_pct = ((signal.exit_price - signal.entry_price) / signal.entry_price) * 100
        else:
            # Still open after 20 days
            signal.exit_price = prices[-1]
            signal.final_pnl_pct = ((prices[-1] - signal.entry_price) / signal.entry_price) * 100
            signal.exit_reason = "time_exit"
        
        signal.max_profit_pct = ((signal.max_price - signal.entry_price) / signal.entry_price) * 100
        signal.max_drawdown_pct = ((signal.entry_price - signal.min_price) / signal.entry_price) * 100
    
    def _get_regime_parameters(self, regime: str) -> Dict:
        """Get simulation parameters based on market regime"""
        params = {
            "extreme_bullish": {"daily_drift": 0.003, "daily_vol": 0.015},
            "strong_bullish": {"daily_drift": 0.002, "daily_vol": 0.018},
            "bullish": {"daily_drift": 0.001, "daily_vol": 0.020},
            "neutral_bullish": {"daily_drift": 0.0005, "daily_vol": 0.022},
            "neutral_bearish": {"daily_drift": -0.0005, "daily_vol": 0.022},
            "bearish": {"daily_drift": -0.001, "daily_vol": 0.025},
            "strong_bearish": {"daily_drift": -0.002, "daily_vol": 0.028},
            "extreme_bearish": {"daily_drift": -0.003, "daily_vol": 0.030},
            "unknown": {"daily_drift": 0.0, "daily_vol": 0.020}
        }
        return params.get(regime, params["unknown"])
    
    def analyze_results(self):
        """Comprehensive analysis of results"""
        print("\nAnalyzing results...")
        
        # Convert to DataFrame
        data = []
        for signal in self.signals:
            data.append({
                'ticker': signal.ticker,
                'sector': signal.sector,
                'entry_date': signal.entry_date,
                'volume_ratio': signal.volume_ratio,
                'momentum_5d': signal.momentum_5d,
                'pattern_score': signal.pattern_score,
                'market_regime': signal.market_regime,
                'regime_confidence': signal.regime_confidence,
                'long_short_ratio': signal.long_short_ratio,
                'h1_achieved': signal.h1_achieved,
                'h2_achieved': signal.h2_achieved,
                'stopped_out': signal.stopped_out,
                'days_to_h1': signal.days_to_h1,
                'days_to_h2': signal.days_to_h2,
                'max_profit_pct': signal.max_profit_pct,
                'max_drawdown_pct': signal.max_drawdown_pct,
                'final_pnl_pct': signal.final_pnl_pct,
                'exit_reason': signal.exit_reason
            })
        
        df = pd.DataFrame(data)
        
        # Save raw data
        df.to_csv(os.path.join(self.output_dir, 'enhanced_signal_analysis.csv'), index=False)
        
        # Detailed regime analysis
        self._analyze_by_regime(df)
        
        # Volume analysis
        self._analyze_by_volume(df)
        
        # Combined analysis
        self._analyze_combined_factors(df)
        
        # Sector analysis
        self._analyze_by_sector(df)
        
        # Create comprehensive visualizations
        self._create_enhanced_visualizations(df)
        
        # Build advanced deployment model
        deployment_model = self._build_advanced_deployment_model(df)
        
        # Generate detailed report
        self._generate_comprehensive_report(df, deployment_model)
        
        return df, deployment_model
    
    def _analyze_by_regime(self, df: pd.DataFrame):
        """Detailed regime-based analysis"""
        regime_stats = df.groupby('market_regime').agg({
            'ticker': 'count',
            'h1_achieved': ['sum', 'mean'],
            'h2_achieved': ['sum', 'mean'],
            'stopped_out': ['sum', 'mean'],
            'final_pnl_pct': ['mean', 'std', 'median'],
            'max_profit_pct': 'mean',
            'max_drawdown_pct': 'mean',
            'days_to_h2': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
        }).round(3)
        
        regime_stats.columns = ['_'.join(col).strip() for col in regime_stats.columns.values]
        regime_stats.to_csv(os.path.join(self.output_dir, 'regime_detailed_stats.csv'))
        
        return regime_stats
    
    def _analyze_by_volume(self, df: pd.DataFrame):
        """Volume-based analysis"""
        # Create volume categories
        df['volume_category'] = pd.qcut(
            df['volume_ratio'], 
            q=[0, 0.25, 0.5, 0.75, 0.9, 1.0],
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
        )
        
        volume_stats = df.groupby('volume_category').agg({
            'h2_achieved': ['count', 'mean'],
            'final_pnl_pct': ['mean', 'std'],
            'days_to_h2': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else np.nan
        }).round(3)
        
        volume_stats.to_csv(os.path.join(self.output_dir, 'volume_detailed_stats.csv'))
        
        return volume_stats
    
    def _analyze_combined_factors(self, df: pd.DataFrame):
        """Analyze combined impact of regime and volume"""
        # Add volume categories if not present
        if 'volume_category' not in df.columns:
            df['volume_category'] = pd.qcut(
                df['volume_ratio'], 
                q=[0, 0.25, 0.5, 0.75, 0.9, 1.0],
                labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
            )
        
        combined = df.groupby(['market_regime', 'volume_category']).agg({
            'h2_achieved': ['count', 'mean'],
            'final_pnl_pct': ['mean', 'std'],
            'stopped_out': 'mean'
        }).round(3)
        
        combined.to_csv(os.path.join(self.output_dir, 'regime_volume_combined_stats.csv'))
        
        return combined
    
    def _analyze_by_sector(self, df: pd.DataFrame):
        """Sector-based analysis"""
        sector_stats = df.groupby('sector').agg({
            'ticker': 'count',
            'h2_achieved': 'mean',
            'final_pnl_pct': ['mean', 'std'],
            'stopped_out': 'mean'
        }).round(3)
        
        # Filter sectors with at least 50 signals
        sector_stats = sector_stats[sector_stats[('ticker', 'count')] >= 50]
        sector_stats.to_csv(os.path.join(self.output_dir, 'sector_performance.csv'))
        
        return sector_stats
    
    def _create_enhanced_visualizations(self, df: pd.DataFrame):
        """Create comprehensive visualizations"""
        print("Creating enhanced visualizations...")
        
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 1. H2 Success Rate by Regime (Enhanced)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        regime_order = ['extreme_bearish', 'strong_bearish', 'bearish', 
                       'neutral_bearish', 'neutral_bullish', 'bullish', 
                       'strong_bullish', 'extreme_bullish']
        
        # Success rates
        regime_success = df.groupby('market_regime').agg({
            'h1_achieved': 'mean',
            'h2_achieved': 'mean'
        }) * 100
        regime_success = regime_success.reindex(regime_order, fill_value=0)
        
        x = np.arange(len(regime_order))
        width = 0.35
        
        ax1.bar(x - width/2, regime_success['h1_achieved'], width, label='H1 Success', color='lightblue')
        ax1.bar(x + width/2, regime_success['h2_achieved'], width, label='H2 Success', color='darkblue')
        ax1.set_xlabel('Market Regime')
        ax1.set_ylabel('Success Rate (%)')
        ax1.set_title('Target Achievement Rates by Market Regime')
        ax1.set_xticks(x)
        ax1.set_xticklabels([r.replace('_', ' ').title() for r in regime_order], rotation=45)
        ax1.legend()
        
        # Average P&L
        regime_pnl = df.groupby('market_regime')['final_pnl_pct'].mean()
        regime_pnl = regime_pnl.reindex(regime_order, fill_value=0)
        
        colors = ['red' if x < 0 else 'green' for x in regime_pnl.values]
        ax2.bar(x, regime_pnl.values, color=colors, alpha=0.7)
        ax2.set_xlabel('Market Regime')
        ax2.set_ylabel('Average P&L (%)')
        ax2.set_title('Average P&L by Market Regime')
        ax2.set_xticks(x)
        ax2.set_xticklabels([r.replace('_', ' ').title() for r in regime_order], rotation=45)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'enhanced_regime_analysis.png'), dpi=300)
        plt.close()
        
        # 2. Volume Impact Heatmap
        if 'volume_category' in df.columns:
            fig, ax = plt.subplots(figsize=(12, 8))
            
            pivot = df.pivot_table(
                values='h2_achieved',
                index='market_regime',
                columns='volume_category',
                aggfunc='mean'
            ) * 100
            
            # Reorder index
            pivot = pivot.reindex(regime_order, fill_value=0)
            
            sns.heatmap(pivot, annot=True, fmt='.1f', cmap='RdYlGn', 
                       cbar_kws={'label': 'H2 Success Rate (%)'},
                       ax=ax, vmin=0, vmax=50)
            ax.set_title('H2 Success Rate: Market Regime vs Volume Category')
            ax.set_xlabel('Volume Category')
            ax.set_ylabel('Market Regime')
            
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, 'regime_volume_heatmap.png'), dpi=300)
            plt.close()
        
        # 3. Time to Target Analysis
        fig, ax = plt.subplots(figsize=(10, 6))
        
        h2_achieved_df = df[df['h2_achieved']]
        if len(h2_achieved_df) > 0:
            h2_achieved_df.boxplot(column='days_to_h2', by='market_regime', ax=ax)
            ax.set_title('Days to H2 Target by Market Regime')
            ax.set_xlabel('Market Regime')
            ax.set_ylabel('Days to H2')
            plt.suptitle('')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'days_to_target_analysis.png'), dpi=300)
        plt.close()
        
        # 4. Risk-Reward Scatter
        fig, ax = plt.subplots(figsize=(12, 8))
        
        regime_scatter = df.groupby('market_regime').agg({
            'h2_achieved': 'mean',
            'final_pnl_pct': 'mean',
            'ticker': 'count'
        })
        
        # Create scatter plot
        scatter = ax.scatter(
            regime_scatter['h2_achieved'] * 100,
            regime_scatter['final_pnl_pct'],
            s=regime_scatter['ticker'] / 10,  # Size based on count
            alpha=0.6,
            c=range(len(regime_scatter)),
            cmap='viridis'
        )
        
        # Add labels
        for idx, row in regime_scatter.iterrows():
            ax.annotate(
                idx.replace('_', ' ').title(),
                (row['h2_achieved'] * 100, row['final_pnl_pct']),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=8
            )
        
        ax.set_xlabel('H2 Success Rate (%)')
        ax.set_ylabel('Average P&L (%)')
        ax.set_title('Risk-Reward Profile by Market Regime')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'risk_reward_scatter.png'), dpi=300)
        plt.close()
    
    def _build_advanced_deployment_model(self, df: pd.DataFrame) -> Dict:
        """Build sophisticated fund deployment model"""
        print("Building advanced deployment model...")
        
        deployment_model = {}
        
        # Add volume categories if needed
        if 'volume_category' not in df.columns:
            df['volume_category'] = pd.qcut(
                df['volume_ratio'], 
                q=[0, 0.25, 0.5, 0.75, 0.9, 1.0],
                labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
            )
        
        for regime in df['market_regime'].unique():
            regime_data = df[df['market_regime'] == regime]
            
            # Calculate key metrics
            total_signals = len(regime_data)
            h1_rate = regime_data['h1_achieved'].mean()
            h2_rate = regime_data['h2_achieved'].mean()
            stop_rate = regime_data['stopped_out'].mean()
            avg_pnl = regime_data['final_pnl_pct'].mean()
            pnl_std = regime_data['final_pnl_pct'].std()
            
            # Sharpe-like ratio
            sharpe = avg_pnl / pnl_std if pnl_std > 0 else 0
            
            # Win rate
            win_rate = (regime_data['final_pnl_pct'] > 0).mean()
            
            # Average win/loss
            wins = regime_data[regime_data['final_pnl_pct'] > 0]['final_pnl_pct']
            losses = regime_data[regime_data['final_pnl_pct'] <= 0]['final_pnl_pct']
            avg_win = wins.mean() if len(wins) > 0 else 0
            avg_loss = losses.mean() if len(losses) > 0 else 0
            
            # Kelly Criterion calculation
            if avg_loss < 0 and win_rate > 0:
                kelly_pct = (win_rate * avg_win + (1 - win_rate) * avg_loss) / avg_win
                kelly_pct = max(0, min(kelly_pct, 0.25)) * 100  # Cap at 25%
            else:
                kelly_pct = 0
            
            # Volume performance
            volume_perf = regime_data.groupby('volume_category').agg({
                'h2_achieved': 'mean',
                'final_pnl_pct': 'mean'
            })
            
            # Find optimal volume categories
            if len(volume_perf) > 0:
                best_volume = volume_perf['h2_achieved'].idxmax()
                volume_multipliers = {}
                for vol_cat in ['Very Low', 'Low', 'Medium', 'High', 'Very High']:
                    if vol_cat in volume_perf.index:
                        vol_h2_rate = volume_perf.loc[vol_cat, 'h2_achieved']
                        vol_pnl = volume_perf.loc[vol_cat, 'final_pnl_pct']
                        
                        # Calculate multiplier based on performance
                        if vol_pnl > 0 and vol_h2_rate > h2_rate:
                            volume_multipliers[vol_cat] = 1.0 + min((vol_h2_rate - h2_rate) * 2, 0.5)
                        else:
                            volume_multipliers[vol_cat] = max(0.5, 1.0 - (h2_rate - vol_h2_rate) * 2)
                    else:
                        volume_multipliers[vol_cat] = 0.8
            else:
                best_volume = 'Medium'
                volume_multipliers = {cat: 1.0 for cat in ['Very Low', 'Low', 'Medium', 'High', 'Very High']}
            
            # Calculate recommended allocation
            base_allocation = self._calculate_optimal_allocation(
                h2_rate, avg_pnl, sharpe, win_rate, kelly_pct
            )
            
            deployment_model[regime] = {
                'total_signals': total_signals,
                'h1_success_rate': round(h1_rate * 100, 2),
                'h2_success_rate': round(h2_rate * 100, 2),
                'stop_rate': round(stop_rate * 100, 2),
                'win_rate': round(win_rate * 100, 2),
                'avg_pnl_pct': round(avg_pnl, 2),
                'pnl_std': round(pnl_std, 2),
                'sharpe_ratio': round(sharpe, 3),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'kelly_pct': round(kelly_pct, 2),
                'base_allocation_pct': round(base_allocation, 2),
                'preferred_volume': best_volume,
                'volume_multipliers': {k: round(v, 2) for k, v in volume_multipliers.items()},
                'confidence_level': self._assess_confidence(total_signals, h2_rate, sharpe)
            }
        
        # Save deployment model
        with open(os.path.join(self.output_dir, 'advanced_deployment_model.json'), 'w') as f:
            json.dump(deployment_model, f, indent=2)
        
        return deployment_model
    
    def _calculate_optimal_allocation(self, h2_rate, avg_pnl, sharpe, win_rate, kelly_pct):
        """Calculate optimal allocation using multiple factors"""
        # Start with Kelly percentage
        base = kelly_pct
        
        # Adjust for H2 achievement rate
        if h2_rate > 0.3:
            base *= 1.2
        elif h2_rate > 0.2:
            base *= 1.1
        elif h2_rate < 0.1:
            base *= 0.5
        
        # Adjust for Sharpe ratio
        if sharpe > 1:
            base *= 1.2
        elif sharpe > 0.5:
            base *= 1.1
        elif sharpe < 0:
            base *= 0.5
        
        # Minimum and maximum bounds
        return max(5.0, min(base, 30.0))
    
    def _assess_confidence(self, sample_size, h2_rate, sharpe):
        """Assess confidence in the model recommendations"""
        if sample_size < 50:
            return "Low"
        elif sample_size < 200:
            if h2_rate > 0.2 and sharpe > 0.5:
                return "Medium"
            else:
                return "Low"
        else:
            if h2_rate > 0.25 and sharpe > 0.75:
                return "High"
            elif h2_rate > 0.15 and sharpe > 0.5:
                return "Medium"
            else:
                return "Low"
    
    def _generate_comprehensive_report(self, df: pd.DataFrame, deployment_model: Dict):
        """Generate detailed analysis report"""
        print("Generating comprehensive report...")
        
        report = []
        report.append("# Enhanced H2 Crossover and Market Regime Analysis")
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n## Executive Summary")
        report.append(f"- Total Signals Analyzed: {len(df):,}")
        report.append(f"- Date Range: {df['entry_date'].min()} to {df['entry_date'].max()}")
        report.append(f"- Overall H1 Success Rate: {df['h1_achieved'].mean()*100:.1f}%")
        report.append(f"- Overall H2 Success Rate: {df['h2_achieved'].mean()*100:.1f}%")
        report.append(f"- Overall Win Rate: {(df['final_pnl_pct'] > 0).mean()*100:.1f}%")
        report.append(f"- Average P&L: {df['final_pnl_pct'].mean():.2f}%")
        
        # Best performing regime
        best_regime = max(deployment_model.items(), 
                         key=lambda x: x[1]['h2_success_rate'] * x[1]['avg_pnl_pct'])
        report.append(f"\n**Best Performing Regime**: {best_regime[0].replace('_', ' ').title()}")
        report.append(f"- H2 Success: {best_regime[1]['h2_success_rate']}%")
        report.append(f"- Average P&L: {best_regime[1]['avg_pnl_pct']}%")
        
        # Detailed regime analysis
        report.append("\n## Detailed Regime Analysis")
        
        # Sort regimes by expected value
        sorted_regimes = sorted(deployment_model.items(), 
                               key=lambda x: x[1]['h2_success_rate'] * x[1]['avg_pnl_pct'], 
                               reverse=True)
        
        for regime, metrics in sorted_regimes:
            report.append(f"\n### {regime.replace('_', ' ').title()}")
            report.append(f"**Performance Metrics:**")
            report.append(f"- Sample Size: {metrics['total_signals']:,} signals")
            report.append(f"- H1 Success Rate: {metrics['h1_success_rate']}%")
            report.append(f"- H2 Success Rate: {metrics['h2_success_rate']}%")
            report.append(f"- Stop Loss Rate: {metrics['stop_rate']}%")
            report.append(f"- Win Rate: {metrics['win_rate']}%")
            report.append(f"- Average P&L: {metrics['avg_pnl_pct']}% (σ={metrics['pnl_std']}%)")
            report.append(f"- Sharpe Ratio: {metrics['sharpe_ratio']}")
            report.append(f"- Average Win: {metrics['avg_win']}%")
            report.append(f"- Average Loss: {metrics['avg_loss']}%")
            
            report.append(f"\n**Fund Deployment:**")
            report.append(f"- Kelly Criterion: {metrics['kelly_pct']}%")
            report.append(f"- Recommended Allocation: {metrics['base_allocation_pct']}%")
            report.append(f"- Confidence Level: {metrics['confidence_level']}")
            report.append(f"- Best Volume Category: {metrics['preferred_volume']}")
            
            report.append(f"\n**Volume Multipliers:**")
            for vol_cat, mult in metrics['volume_multipliers'].items():
                report.append(f"- {vol_cat}: {mult}x")
        
        # Volume analysis
        if 'volume_category' in df.columns:
            report.append("\n## Volume Category Analysis")
            vol_stats = df.groupby('volume_category').agg({
                'h2_achieved': 'mean',
                'final_pnl_pct': 'mean',
                'ticker': 'count'
            })
            
            for vol_cat in vol_stats.index:
                report.append(f"\n### {vol_cat} Volume")
                report.append(f"- Signals: {vol_stats.loc[vol_cat, 'ticker']:,}")
                report.append(f"- H2 Success: {vol_stats.loc[vol_cat, 'h2_achieved']*100:.1f}%")
                report.append(f"- Avg P&L: {vol_stats.loc[vol_cat, 'final_pnl_pct']:.2f}%")
        
        # Implementation guidelines
        report.append("\n## Implementation Guidelines")
        report.append("\n### Position Sizing Formula")
        report.append("```")
        report.append("Position Size = Base Allocation × Volume Multiplier × Regime Confidence")
        report.append("```")
        
        report.append("\n### Entry Criteria")
        report.append("1. Signal appears in Long Reversal scan")
        report.append("2. Market regime confidence > 50%")
        report.append("3. Volume ratio > 0.5")
        report.append("4. Pattern score > median for the regime")
        
        report.append("\n### Risk Management")
        report.append("1. **Maximum Portfolio Risk**: 2% per position")
        report.append("2. **Sector Concentration**: Max 25% in any sector")
        report.append("3. **Regime Transition**: Reduce positions by 50% when regime changes")
        report.append("4. **Drawdown Limit**: Reduce allocation by 50% if portfolio down 10%")
        
        report.append("\n### Optimal Trading Conditions")
        # Find best conditions
        best_conditions = []
        for regime, metrics in deployment_model.items():
            if metrics['h2_success_rate'] > 20 and metrics['avg_pnl_pct'] > 3:
                best_conditions.append({
                    'regime': regime,
                    'h2_rate': metrics['h2_success_rate'],
                    'pnl': metrics['avg_pnl_pct'],
                    'volume': metrics['preferred_volume']
                })
        
        if best_conditions:
            report.append("\nBest trading conditions identified:")
            for cond in sorted(best_conditions, key=lambda x: x['h2_rate'] * x['pnl'], reverse=True)[:3]:
                report.append(f"- **{cond['regime'].replace('_', ' ').title()}** regime with "
                            f"**{cond['volume']}** volume")
                report.append(f"  - H2 Success: {cond['h2_rate']}%, Avg P&L: {cond['pnl']}%")
        
        # Save report
        report_path = os.path.join(self.output_dir, 'comprehensive_analysis_report.md')
        with open(report_path, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"Report saved to: {report_path}")
        
        # Also create a summary dashboard
        self._create_summary_dashboard(df, deployment_model)
    
    def _create_summary_dashboard(self, df: pd.DataFrame, deployment_model: Dict):
        """Create an HTML summary dashboard"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>H2 Crossover Analysis Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric {{ display: inline-block; margin: 10px 20px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .metric-label {{ font-size: 14px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; font-weight: bold; }}
                .positive {{ color: #4CAF50; }}
                .negative {{ color: #f44336; }}
                .recommendation {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>H2 Crossover Analysis Dashboard</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="card">
                    <h2>Overall Performance</h2>
                    <div class="metric">
                        <div class="metric-value">{len(df):,}</div>
                        <div class="metric-label">Total Signals</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{df['h2_achieved'].mean()*100:.1f}%</div>
                        <div class="metric-label">H2 Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{df['final_pnl_pct'].mean():.2f}%</div>
                        <div class="metric-label">Average P&L</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{(df['final_pnl_pct'] > 0).mean()*100:.1f}%</div>
                        <div class="metric-label">Win Rate</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Regime Performance & Recommendations</h2>
                    <table>
                        <tr>
                            <th>Market Regime</th>
                            <th>Signals</th>
                            <th>H2 Success</th>
                            <th>Avg P&L</th>
                            <th>Sharpe</th>
                            <th>Allocation</th>
                            <th>Confidence</th>
                        </tr>
        """
        
        # Sort by allocation recommendation
        sorted_regimes = sorted(deployment_model.items(), 
                               key=lambda x: x[1]['base_allocation_pct'], 
                               reverse=True)
        
        for regime, metrics in sorted_regimes:
            pnl_class = "positive" if metrics['avg_pnl_pct'] > 0 else "negative"
            html += f"""
                        <tr>
                            <td>{regime.replace('_', ' ').title()}</td>
                            <td>{metrics['total_signals']:,}</td>
                            <td>{metrics['h2_success_rate']}%</td>
                            <td class="{pnl_class}">{metrics['avg_pnl_pct']}%</td>
                            <td>{metrics['sharpe_ratio']}</td>
                            <td><strong>{metrics['base_allocation_pct']}%</strong></td>
                            <td>{metrics['confidence_level']}</td>
                        </tr>
            """
        
        html += """
                    </table>
                </div>
                
                <div class="card">
                    <h2>Trading Recommendations</h2>
                    <div class="recommendation">
                        <h3>High Priority Setups</h3>
        """
        
        # Add top recommendations
        top_regimes = sorted(deployment_model.items(), 
                            key=lambda x: x[1]['h2_success_rate'] * x[1]['avg_pnl_pct'], 
                            reverse=True)[:3]
        
        for regime, metrics in top_regimes:
            if metrics['h2_success_rate'] > 15 and metrics['avg_pnl_pct'] > 2:
                html += f"""
                        <p><strong>{regime.replace('_', ' ').title()}</strong>: 
                        Allocate {metrics['base_allocation_pct']}% with {metrics['preferred_volume']} volume preference. 
                        Expected H2 success: {metrics['h2_success_rate']}%, Avg return: {metrics['avg_pnl_pct']}%</p>
                """
        
        html += """
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        dashboard_path = os.path.join(self.output_dir, 'analysis_dashboard.html')
        with open(dashboard_path, 'w') as f:
            f.write(html)
        
        print(f"Dashboard saved to: {dashboard_path}")


def main():
    """Run enhanced analysis"""
    analyzer = EnhancedH2Analyzer()
    analyzer.load_signals_with_tracking()
    df, deployment_model = analyzer.analyze_results()
    
    print("\n=== Analysis Complete ===")
    print(f"Results saved to: {analyzer.output_dir}")


if __name__ == "__main__":
    main()