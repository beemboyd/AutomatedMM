#!/usr/bin/env python3
"""
H2 Crossover and Market Regime Correlation Analysis

This script analyzes the correlation between successful H2 crossovers (Target2 achievements),
market regime conditions, and volume patterns to build a fund deployment model.
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
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, parent_dir)

@dataclass
class SignalAnalysis:
    """Store analysis results for a signal"""
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
    h1_achieved: bool = False
    h2_achieved: bool = False
    stopped_out: bool = False
    days_to_h1: Optional[int] = None
    days_to_h2: Optional[int] = None
    max_profit_pct: float = 0.0
    final_pnl_pct: float = 0.0


class H2CrossoverRegimeAnalyzer:
    """Analyze correlation between H2 crossovers and market regime"""
    
    def __init__(self):
        self.results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.results_s_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results-s"
        self.regime_data_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data"
        self.analysis_dir = script_dir
        
        # Create output directories
        self.output_dir = os.path.join(self.analysis_dir, "h2_crossover_analysis")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Data storage
        self.long_signals = []
        self.short_signals = []
        self.regime_history = {}
        self.price_data = {}
        
    def load_regime_history(self):
        """Load historical market regime data"""
        print("Loading market regime history...")
        
        # Load from regime reports
        regime_reports_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis"
        report_files = glob.glob(os.path.join(regime_reports_dir, "regime_report_*.json"))
        
        for file in sorted(report_files):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                
                # Extract date from filename
                filename = os.path.basename(file)
                date_str = filename.split('_')[2]  # regime_report_YYYYMMDD_...
                date = datetime.strptime(date_str, "%Y%m%d").date()
                
                self.regime_history[date] = {
                    'regime': data.get('current_regime', 'unknown'),
                    'confidence': data.get('confidence', 0),
                    'long_short_ratio': data.get('long_short_ratio', 1.0),
                    'long_count': data.get('long_signals', 0),
                    'short_count': data.get('short_signals', 0)
                }
            except Exception as e:
                continue
        
        # Also load from historical scan data
        historical_file = os.path.join(self.regime_data_dir, "historical_scan_data.json")
        if os.path.exists(historical_file):
            with open(historical_file, 'r') as f:
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
                        'short_count': entry.get('short_count', 0)
                    }
        
        print(f"Loaded regime data for {len(self.regime_history)} days")
    
    def _classify_regime(self, ratio: float) -> str:
        """Classify regime based on L/S ratio"""
        if ratio >= 2.0:
            return "strong_bullish"
        elif ratio >= 1.2:
            return "bullish"
        elif ratio >= 0.8:
            return "choppy"
        elif ratio >= 0.5:
            return "bearish"
        else:
            return "strong_bearish"
    
    def _calculate_confidence(self, ratio: float) -> float:
        """Calculate confidence based on L/S ratio extremity"""
        if ratio >= 2.0 or ratio <= 0.5:
            return 0.9
        elif ratio >= 1.5 or ratio <= 0.67:
            return 0.7
        elif ratio >= 1.2 or ratio <= 0.83:
            return 0.5
        else:
            return 0.3
    
    def load_price_data(self):
        """Load historical price data for tracking signal outcomes"""
        print("Loading historical price data...")
        
        # For this analysis, we'll use a simplified approach
        # In production, you'd load from your data provider
        # Here we'll track outcomes from subsequent scan files
        
        # Load all long reversal files to track ticker appearances
        long_files = sorted(glob.glob(os.path.join(self.results_dir, "Long_Reversal_Daily_*.xlsx")))
        
        for file in long_files:
            try:
                df = pd.read_excel(file)
                date_str = os.path.basename(file).split('_')[3].split('.')[0]
                date = datetime.strptime(date_str, "%Y%m%d").date()
                
                for _, row in df.iterrows():
                    ticker = row['Ticker']
                    if ticker not in self.price_data:
                        self.price_data[ticker] = {}
                    
                    self.price_data[ticker][date] = {
                        'close': row['Entry_Price'],
                        'volume_ratio': row.get('Volume_Ratio', 1.0)
                    }
            except Exception as e:
                continue
        
        print(f"Loaded price data for {len(self.price_data)} tickers")
    
    def load_reversal_signals(self):
        """Load all long reversal signals"""
        print("Loading reversal signals...")
        
        long_files = sorted(glob.glob(os.path.join(self.results_dir, "Long_Reversal_Daily_*.xlsx")))
        
        for file in long_files:
            try:
                df = pd.read_excel(file)
                
                # Extract date from filename
                filename = os.path.basename(file)
                date_str = filename.split('_')[3].split('.')[0]
                signal_date = datetime.strptime(date_str, "%Y%m%d").date()
                
                # Get regime for this date
                regime_data = self.regime_history.get(signal_date, {
                    'regime': 'unknown',
                    'confidence': 0,
                    'long_short_ratio': 1.0
                })
                
                for _, row in df.iterrows():
                    signal = SignalAnalysis(
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
                        long_short_ratio=regime_data['long_short_ratio']
                    )
                    
                    self.long_signals.append(signal)
                    
            except Exception as e:
                print(f"Error loading {file}: {e}")
                continue
        
        print(f"Loaded {len(self.long_signals)} long reversal signals")
    
    def track_signal_outcomes(self):
        """Track outcomes of signals using available price data"""
        print("Tracking signal outcomes...")
        
        for signal in self.long_signals:
            # Track for up to 20 trading days
            for days in range(1, 21):
                check_date = signal.entry_date + timedelta(days=days)
                
                # Skip weekends
                while check_date.weekday() >= 5:
                    check_date += timedelta(days=1)
                
                # Get price data for this date
                ticker_data = self.price_data.get(signal.ticker, {})
                if check_date in ticker_data:
                    price = ticker_data[check_date]['close']
                    
                    # Calculate profit percentage
                    profit_pct = ((price - signal.entry_price) / signal.entry_price) * 100
                    signal.max_profit_pct = max(signal.max_profit_pct, profit_pct)
                    
                    # Check if targets hit
                    if not signal.h1_achieved and price >= signal.target1:
                        signal.h1_achieved = True
                        signal.days_to_h1 = days
                    
                    if not signal.h2_achieved and price >= signal.target2:
                        signal.h2_achieved = True
                        signal.days_to_h2 = days
                    
                    # Check if stopped out
                    if price <= signal.stop_loss:
                        signal.stopped_out = True
                        signal.final_pnl_pct = ((signal.stop_loss - signal.entry_price) / signal.entry_price) * 100
                        break
                
                # If H2 achieved, we're done
                if signal.h2_achieved:
                    signal.final_pnl_pct = ((signal.target2 - signal.entry_price) / signal.entry_price) * 100
                    break
        
        # Calculate final P&L for signals that didn't hit H2 or stop
        for signal in self.long_signals:
            if not signal.h2_achieved and not signal.stopped_out:
                if signal.h1_achieved:
                    signal.final_pnl_pct = ((signal.target1 - signal.entry_price) / signal.entry_price) * 100
                else:
                    signal.final_pnl_pct = signal.max_profit_pct
    
    def analyze_correlations(self):
        """Analyze correlations between H2 success and various factors"""
        print("\nAnalyzing correlations...")
        
        # Convert signals to DataFrame for easier analysis
        data = []
        for signal in self.long_signals:
            data.append({
                'ticker': signal.ticker,
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
                'final_pnl_pct': signal.final_pnl_pct
            })
        
        df = pd.DataFrame(data)
        
        # Save raw data
        df.to_csv(os.path.join(self.output_dir, 'signal_analysis_raw.csv'), index=False)
        
        # Calculate success rates by regime
        regime_analysis = df.groupby('market_regime').agg({
            'h1_achieved': ['count', 'sum', 'mean'],
            'h2_achieved': ['sum', 'mean'],
            'stopped_out': ['sum', 'mean'],
            'final_pnl_pct': ['mean', 'std'],
            'days_to_h2': 'mean'
        }).round(3)
        
        regime_analysis.to_csv(os.path.join(self.output_dir, 'regime_success_rates.csv'))
        
        # Analyze volume impact
        df['volume_category'] = pd.qcut(df['volume_ratio'], q=4, labels=['Low', 'Medium', 'High', 'Very High'])
        volume_analysis = df.groupby('volume_category').agg({
            'h2_achieved': ['count', 'mean'],
            'final_pnl_pct': 'mean'
        }).round(3)
        
        volume_analysis.to_csv(os.path.join(self.output_dir, 'volume_impact_analysis.csv'))
        
        # Combined analysis: Regime + Volume
        combined = df.groupby(['market_regime', 'volume_category']).agg({
            'h2_achieved': ['count', 'mean'],
            'final_pnl_pct': 'mean'
        }).round(3)
        
        combined.to_csv(os.path.join(self.output_dir, 'regime_volume_combined.csv'))
        
        return df, regime_analysis, volume_analysis, combined
    
    def create_visualizations(self, df: pd.DataFrame):
        """Create visualization plots"""
        print("Creating visualizations...")
        
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 1. H2 Success Rate by Market Regime
        fig, ax = plt.subplots(figsize=(10, 6))
        regime_success = df.groupby('market_regime')['h2_achieved'].mean() * 100
        regime_success.plot(kind='bar', ax=ax)
        ax.set_title('H2 Target Achievement Rate by Market Regime')
        ax.set_ylabel('Success Rate (%)')
        ax.set_xlabel('Market Regime')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'h2_success_by_regime.png'))
        plt.close()
        
        # 2. Volume Impact on H2 Success
        fig, ax = plt.subplots(figsize=(10, 6))
        volume_success = df.groupby('volume_category')['h2_achieved'].mean() * 100
        volume_success.plot(kind='bar', ax=ax, color='green')
        ax.set_title('H2 Target Achievement Rate by Volume Category')
        ax.set_ylabel('Success Rate (%)')
        ax.set_xlabel('Volume Category')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'h2_success_by_volume.png'))
        plt.close()
        
        # 3. Heatmap: Regime vs Volume Success Rate
        pivot_data = df.pivot_table(
            values='h2_achieved',
            index='market_regime',
            columns='volume_category',
            aggfunc='mean'
        ) * 100
        
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(pivot_data, annot=True, fmt='.1f', cmap='RdYlGn', ax=ax)
        ax.set_title('H2 Success Rate Heatmap: Market Regime vs Volume')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'regime_volume_heatmap.png'))
        plt.close()
        
        # 4. Average Days to H2 by Regime
        fig, ax = plt.subplots(figsize=(10, 6))
        days_to_h2 = df[df['h2_achieved']].groupby('market_regime')['days_to_h2'].mean()
        days_to_h2.plot(kind='bar', ax=ax, color='orange')
        ax.set_title('Average Days to H2 Target by Market Regime')
        ax.set_ylabel('Days')
        ax.set_xlabel('Market Regime')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'days_to_h2_by_regime.png'))
        plt.close()
        
        # 5. P&L Distribution by Regime
        fig, ax = plt.subplots(figsize=(12, 6))
        df.boxplot(column='final_pnl_pct', by='market_regime', ax=ax)
        ax.set_title('P&L Distribution by Market Regime')
        ax.set_ylabel('P&L %')
        ax.set_xlabel('Market Regime')
        plt.suptitle('')  # Remove default title
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'pnl_distribution_by_regime.png'))
        plt.close()
    
    def build_deployment_model(self, df: pd.DataFrame) -> Dict:
        """Build fund deployment recommendations based on analysis"""
        print("\nBuilding fund deployment model...")
        
        deployment_model = {}
        
        # Calculate optimal deployment percentages for each regime
        regimes = df['market_regime'].unique()
        
        for regime in regimes:
            regime_data = df[df['market_regime'] == regime]
            
            # Calculate key metrics
            h2_success_rate = regime_data['h2_achieved'].mean()
            avg_pnl = regime_data['final_pnl_pct'].mean()
            risk_adjusted_score = h2_success_rate * avg_pnl
            total_signals = len(regime_data)
            
            # Volume category performance in this regime
            volume_performance = regime_data.groupby('volume_category').agg({
                'h2_achieved': 'mean',
                'final_pnl_pct': 'mean'
            })
            
            # Find best volume category for this regime
            best_volume = volume_performance['h2_achieved'].idxmax() if len(volume_performance) > 0 else 'High'
            
            deployment_model[regime] = {
                'base_allocation_pct': self._calculate_allocation(h2_success_rate, avg_pnl),
                'h2_success_rate': round(h2_success_rate * 100, 2),
                'avg_pnl_pct': round(avg_pnl, 2),
                'risk_adjusted_score': round(risk_adjusted_score, 2),
                'total_signals': total_signals,
                'preferred_volume_category': best_volume,
                'volume_multipliers': {
                    'Low': 0.7,
                    'Medium': 0.9,
                    'High': 1.0,
                    'Very High': 1.1 if regime in ['strong_bullish', 'bullish'] else 0.8
                }
            }
        
        # Save deployment model
        with open(os.path.join(self.output_dir, 'fund_deployment_model.json'), 'w') as f:
            json.dump(deployment_model, f, indent=2)
        
        return deployment_model
    
    def _calculate_allocation(self, success_rate: float, avg_pnl: float) -> float:
        """Calculate base allocation percentage based on success metrics"""
        # Base allocation formula
        # Higher success rate and positive P&L = higher allocation
        if avg_pnl < 0:
            return 5.0  # Minimal allocation for negative expectancy
        
        base = success_rate * 100  # Start with success rate as percentage
        
        # Adjust based on P&L magnitude
        if avg_pnl > 5:
            base *= 1.5
        elif avg_pnl > 3:
            base *= 1.2
        elif avg_pnl > 1:
            base *= 1.0
        else:
            base *= 0.8
        
        # Cap allocations
        return min(max(base, 5.0), 40.0)  # Between 5% and 40%
    
    def generate_report(self, df: pd.DataFrame, deployment_model: Dict):
        """Generate comprehensive analysis report"""
        print("Generating analysis report...")
        
        report = []
        report.append("# H2 Crossover and Market Regime Correlation Analysis Report")
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\nTotal Signals Analyzed: {len(df)}")
        report.append(f"Date Range: {df['entry_date'].min()} to {df['entry_date'].max()}")
        
        # Overall Statistics
        report.append("\n## Overall Statistics")
        report.append(f"- H1 Achievement Rate: {df['h1_achieved'].mean()*100:.1f}%")
        report.append(f"- H2 Achievement Rate: {df['h2_achieved'].mean()*100:.1f}%")
        report.append(f"- Stop Loss Rate: {df['stopped_out'].mean()*100:.1f}%")
        report.append(f"- Average P&L: {df['final_pnl_pct'].mean():.2f}%")
        report.append(f"- Average Days to H2: {df[df['h2_achieved']]['days_to_h2'].mean():.1f}")
        
        # Regime-based Analysis
        report.append("\n## Market Regime Analysis")
        for regime, model in deployment_model.items():
            report.append(f"\n### {regime.replace('_', ' ').title()}")
            report.append(f"- H2 Success Rate: {model['h2_success_rate']}%")
            report.append(f"- Average P&L: {model['avg_pnl_pct']}%")
            report.append(f"- Risk-Adjusted Score: {model['risk_adjusted_score']}")
            report.append(f"- Recommended Base Allocation: {model['base_allocation_pct']:.1f}%")
            report.append(f"- Best Volume Category: {model['preferred_volume_category']}")
            report.append(f"- Total Signals: {model['total_signals']}")
        
        # Volume Impact
        report.append("\n## Volume Impact Analysis")
        volume_stats = df.groupby('volume_category').agg({
            'h2_achieved': 'mean',
            'final_pnl_pct': 'mean',
            'ticker': 'count'
        })
        
        for category in volume_stats.index:
            h2_rate = volume_stats.loc[category, 'h2_achieved'] * 100
            avg_pnl = volume_stats.loc[category, 'final_pnl_pct']
            count = volume_stats.loc[category, 'ticker']
            report.append(f"\n### {category} Volume")
            report.append(f"- H2 Success Rate: {h2_rate:.1f}%")
            report.append(f"- Average P&L: {avg_pnl:.2f}%")
            report.append(f"- Signal Count: {count}")
        
        # Key Findings
        report.append("\n## Key Findings")
        
        # Find best and worst regimes
        best_regime = max(deployment_model.items(), key=lambda x: x[1]['h2_success_rate'])
        worst_regime = min(deployment_model.items(), key=lambda x: x[1]['h2_success_rate'])
        
        report.append(f"\n1. **Best Regime for H2 Success**: {best_regime[0].replace('_', ' ').title()} ({best_regime[1]['h2_success_rate']}%)")
        report.append(f"2. **Worst Regime for H2 Success**: {worst_regime[0].replace('_', ' ').title()} ({worst_regime[1]['h2_success_rate']}%)")
        
        # Volume insights
        best_volume = df.groupby('volume_category')['h2_achieved'].mean().idxmax()
        report.append(f"3. **Best Volume Category**: {best_volume} (across all regimes)")
        
        # Correlation insights
        if len(df) > 30:
            correlation = df[['volume_ratio', 'momentum_5d', 'long_short_ratio']].corrwith(df['h2_achieved'])
            report.append("\n4. **Factor Correlations with H2 Success**:")
            report.append(f"   - Volume Ratio: {correlation['volume_ratio']:.3f}")
            report.append(f"   - 5D Momentum: {correlation['momentum_5d']:.3f}")
            report.append(f"   - L/S Ratio: {correlation['long_short_ratio']:.3f}")
        
        # Fund Deployment Recommendations
        report.append("\n## Fund Deployment Recommendations")
        report.append("\nBased on the analysis, here are the recommended allocation strategies:")
        
        for regime, model in sorted(deployment_model.items(), key=lambda x: x[1]['base_allocation_pct'], reverse=True):
            report.append(f"\n### {regime.replace('_', ' ').title()} Regime")
            report.append(f"- Base Allocation: {model['base_allocation_pct']:.1f}% of trading capital")
            report.append(f"- Volume Adjustments:")
            for vol_cat, multiplier in model['volume_multipliers'].items():
                report.append(f"  - {vol_cat}: {multiplier}x base allocation")
        
        # Risk Management
        report.append("\n## Risk Management Guidelines")
        report.append("\n1. **Position Sizing**: Use Kelly Criterion with 25% reduction for safety")
        report.append("2. **Maximum Exposure**: Never exceed 40% allocation even in best conditions")
        report.append("3. **Regime Transition**: Reduce positions by 50% when regime confidence < 50%")
        report.append("4. **Volume Filter**: Avoid positions with volume ratio < 0.5")
        report.append("5. **Correlation Management**: Limit sector concentration to 20% of portfolio")
        
        # Save report
        report_path = os.path.join(self.output_dir, 'analysis_report.md')
        with open(report_path, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"Report saved to: {report_path}")
        
        return '\n'.join(report)
    
    def run_analysis(self):
        """Run the complete analysis pipeline"""
        print("Starting H2 Crossover and Market Regime Analysis...")
        
        # Load all data
        self.load_regime_history()
        self.load_price_data()
        self.load_reversal_signals()
        
        # Track outcomes
        self.track_signal_outcomes()
        
        # Analyze correlations
        df, regime_analysis, volume_analysis, combined = self.analyze_correlations()
        
        # Create visualizations
        self.create_visualizations(df)
        
        # Build deployment model
        deployment_model = self.build_deployment_model(df)
        
        # Generate report
        report = self.generate_report(df, deployment_model)
        
        print("\nAnalysis complete! Check the output directory for results.")
        print(f"Output directory: {self.output_dir}")
        
        # Print summary
        print("\n=== SUMMARY ===")
        print(f"Total Signals Analyzed: {len(df)}")
        print(f"Overall H2 Success Rate: {df['h2_achieved'].mean()*100:.1f}%")
        print(f"Average P&L: {df['final_pnl_pct'].mean():.2f}%")
        
        print("\nTop 3 Regime Recommendations:")
        sorted_regimes = sorted(deployment_model.items(), key=lambda x: x[1]['base_allocation_pct'], reverse=True)[:3]
        for regime, model in sorted_regimes:
            print(f"- {regime}: {model['base_allocation_pct']:.1f}% allocation (H2 success: {model['h2_success_rate']}%)")


def main():
    """Main execution function"""
    analyzer = H2CrossoverRegimeAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()