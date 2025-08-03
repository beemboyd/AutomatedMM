#!/usr/bin/env python3
"""
Brooks Strategy Refinement Analysis
Identify opportunities to improve the Brooks Higher Probability LONG Reversal strategy
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import os
import sys
import logging

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StrategyRefinementAnalyzer:
    def __init__(self):
        self.results_data = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_analysis_20250526_212145.xlsx')
        self.data_path = "/Users/maverick/PycharmProjects/India-TS/ML/data/ohlc_data/daily"
        
    def analyze_market_regime_conditions(self):
        """Analyze market conditions on successful vs unsuccessful days"""
        print("\n" + "="*60)
        print("1. MARKET REGIME ANALYSIS")
        print("="*60)
        
        # Group by date and calculate success metrics
        date_performance = self.results_data.groupby('file_date').agg({
            'ticker': 'count',
            'is_profitable': ['sum', 'mean'],
            'pnl_percentage': ['mean', 'std', 'min', 'max']
        }).round(3)
        
        date_performance.columns = ['Total_Trades', 'Profitable_Count', 'Win_Rate', 
                                  'Avg_PnL', 'PnL_Std', 'Min_PnL', 'Max_PnL']
        
        print("Performance by Trading Date:")
        print(date_performance.to_string())
        
        # Identify best vs worst performing days
        best_day = date_performance.loc[date_performance['Win_Rate'].idxmax()]
        worst_day = date_performance.loc[date_performance['Win_Rate'].idxmin()]
        
        print(f"\nBest Performing Day: {date_performance['Win_Rate'].idxmax()}")
        print(f"Win Rate: {best_day['Win_Rate']:.2%}, Avg P&L: {best_day['Avg_PnL']:.2f}%")
        
        print(f"\nWorst Performing Day: {date_performance['Win_Rate'].idxmin()}")
        print(f"Win Rate: {worst_day['Win_Rate']:.2%}, Avg P&L: {worst_day['Avg_PnL']:.2f}%")
        
        return date_performance
    
    def analyze_existing_conditions(self):
        """Examine the existing technical conditions used"""
        print("\n" + "="*60)
        print("2. EXISTING TECHNICAL CONDITIONS ANALYSIS")
        print("="*60)
        
        # Load one of the Excel files to examine the conditions
        sample_file = "/Users/maverick/PycharmProjects/India-TS/Daily/results/Brooks_Higher_Probability_LONG_Reversal_26_05_2025_15_24.xlsx"
        df_sample = pd.read_excel(sample_file)
        
        print("Current Strategy Parameters:")
        try:
            print(f"- Average Risk-Reward Ratio: {df_sample['Risk_Reward_Ratio'].mean():.2f}")
            print(f"- Average Volume Ratio: {df_sample['Volume_Ratio'].mean():.2f}")
            print(f"- Average 5D Momentum: {df_sample['Momentum_5D'].mean():.2f}%")
            print(f"- Average ATR: {df_sample['ATR'].mean():.2f}")
        except Exception as e:
            print(f"Error calculating averages: {e}")
            print("Sample of data:")
            print(df_sample[['Risk_Reward_Ratio', 'Volume_Ratio', 'Momentum_5D', 'ATR']].head())
        
        # Analyze which conditions are most common
        print("\nSample Conditions from Latest File:")
        if 'Conditions_Met' in df_sample.columns:
            print(df_sample['Conditions_Met'].iloc[0])
        
        return df_sample
    
    def analyze_volume_momentum_patterns(self):
        """Analyze volume and momentum patterns for successful trades"""
        print("\n" + "="*60)
        print("3. VOLUME & MOMENTUM PATTERN ANALYSIS")
        print("="*60)
        
        # Separate profitable vs unprofitable trades
        profitable = self.results_data[self.results_data['is_profitable'] == True]
        unprofitable = self.results_data[self.results_data['is_profitable'] == False]
        
        print("Comparison: Profitable vs Unprofitable Trades")
        print("-" * 50)
        
        # Get more detailed data for analysis
        metrics_comparison = []
        
        for file_path in self.results_data['file_path'].unique():
            try:
                df = pd.read_excel(file_path)
                df['profitable'] = df['Ticker'].isin(
                    profitable[profitable['file_path'] == file_path]['ticker']
                )
                
                for profitable_flag in [True, False]:
                    subset = df[df['profitable'] == profitable_flag]
                    if len(subset) > 0:
                        try:
                            metrics_comparison.append({
                                'profitable': profitable_flag,
                                'count': len(subset),
                                'avg_volume_ratio': subset['Volume_Ratio'].mean(),
                                'avg_momentum_5d': subset['Momentum_5D'].mean(),
                                'avg_risk_reward': subset['Risk_Reward_Ratio'].mean(),
                                'avg_atr': subset['ATR'].mean()
                            })
                        except Exception as e:
                            logger.warning(f"Error processing metrics for {file_path}: {e}")
                            continue
            except Exception as e:
                continue
        
        if metrics_comparison:
            comparison_df = pd.DataFrame(metrics_comparison)
            summary = comparison_df.groupby('profitable').agg({
                'count': 'sum',
                'avg_volume_ratio': 'mean',
                'avg_momentum_5d': 'mean',
                'avg_risk_reward': 'mean',
                'avg_atr': 'mean'
            }).round(3)
            
            print("Profitable vs Unprofitable Trade Characteristics:")
            print(summary.to_string())
            
            return summary
        
        return None
    
    def analyze_risk_management_opportunities(self):
        """Analyze stop-loss and position sizing optimization opportunities"""
        print("\n" + "="*60)
        print("4. RISK MANAGEMENT OPTIMIZATION")
        print("="*60)
        
        # Analyze the distribution of losses and gains
        profitable = self.results_data[self.results_data['is_profitable'] == True]
        unprofitable = self.results_data[self.results_data['is_profitable'] == False]
        
        print("P&L Distribution Analysis:")
        print(f"Profitable trades - Average: {profitable['pnl_percentage'].mean():.2f}%, Max: {profitable['pnl_percentage'].max():.2f}%")
        print(f"Unprofitable trades - Average: {unprofitable['pnl_percentage'].mean():.2f}%, Min: {unprofitable['pnl_percentage'].min():.2f}%")
        
        # Calculate percentiles for risk management
        loss_percentiles = np.percentile(unprofitable['pnl_percentage'], [10, 25, 50, 75, 90])
        gain_percentiles = np.percentile(profitable['pnl_percentage'], [10, 25, 50, 75, 90])
        
        print(f"\nLoss Distribution Percentiles: {loss_percentiles}")
        print(f"Gain Distribution Percentiles: {gain_percentiles}")
        
        # Risk-reward analysis
        avg_gain = profitable['pnl_percentage'].mean()
        avg_loss = abs(unprofitable['pnl_percentage'].mean())
        current_risk_reward = avg_gain / avg_loss if avg_loss > 0 else 0
        
        print(f"\nCurrent Risk-Reward Metrics:")
        print(f"Average Gain: {avg_gain:.2f}%")
        print(f"Average Loss: {avg_loss:.2f}%")
        print(f"Risk-Reward Ratio: {current_risk_reward:.2f}")
        
        return {
            'avg_gain': avg_gain,
            'avg_loss': avg_loss,
            'risk_reward': current_risk_reward,
            'loss_percentiles': loss_percentiles,
            'gain_percentiles': gain_percentiles
        }
    
    def generate_refinement_recommendations(self):
        """Generate comprehensive strategy refinement recommendations"""
        print("\n" + "="*60)
        print("5. STRATEGY REFINEMENT RECOMMENDATIONS")
        print("="*60)
        
        win_rate = self.results_data['is_profitable'].mean()
        avg_pnl = self.results_data['pnl_percentage'].mean()
        
        recommendations = []
        
        # 1. Market Regime Filtering
        recommendations.append({
            'category': 'Market Regime Filtering',
            'priority': 'HIGH',
            'recommendations': [
                'Add market breadth indicators (advance/decline ratio)',
                'Include VIX or India VIX for volatility filtering', 
                'Add Nifty 50 trend confirmation (above/below key MAs)',
                'Avoid strategy deployment on high-volatility days'
            ]
        })
        
        # 2. Entry Criteria Enhancement
        recommendations.append({
            'category': 'Entry Criteria Enhancement',
            'priority': 'HIGH',
            'recommendations': [
                'Increase minimum score threshold (current avg appears low)',
                'Add RSI divergence confirmation',
                'Require minimum volume surge (2x+ average)',
                'Add sector strength filter',
                'Implement time-of-day filtering (avoid first/last hour)'
            ]
        })
        
        # 3. Risk Management
        recommendations.append({
            'category': 'Risk Management',
            'priority': 'HIGH', 
            'recommendations': [
                'Implement dynamic stop-losses based on ATR',
                'Use position sizing based on volatility',
                'Add maximum daily loss limits',
                'Implement partial profit booking at 3-5% gains',
                'Add correlation filters to avoid overexposure'
            ]
        })
        
        # 4. Technical Filters
        recommendations.append({
            'category': 'Additional Technical Filters',
            'priority': 'MEDIUM',
            'recommendations': [
                'Add momentum confirmation (price > 5-day MA)',
                'Require minimum distance from resistance levels',
                'Add volume-weighted average price (VWAP) confirmation',
                'Include relative strength vs Nifty 50',
                'Add earnings date proximity filter'
            ]
        })
        
        # 5. Portfolio Management
        recommendations.append({
            'category': 'Portfolio Management',
            'priority': 'MEDIUM',
            'recommendations': [
                'Limit maximum concurrent positions',
                'Add sector diversification requirements',
                'Implement position concentration limits',
                'Add correlation-based position sizing',
                'Create position cooling-off periods'
            ]
        })
        
        for rec in recommendations:
            print(f"\n{rec['category']} ({rec['priority']} Priority):")
            for i, item in enumerate(rec['recommendations'], 1):
                print(f"  {i}. {item}")
        
        return recommendations

def main():
    analyzer = StrategyRefinementAnalyzer()
    
    # Run all analyses
    date_perf = analyzer.analyze_market_regime_conditions()
    sample_conditions = analyzer.analyze_existing_conditions()
    volume_analysis = analyzer.analyze_volume_momentum_patterns()
    risk_analysis = analyzer.analyze_risk_management_opportunities()
    recommendations = analyzer.generate_refinement_recommendations()
    
    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # Win rate by date
    axes[0,0].bar(date_perf.index, date_perf['Win_Rate'] * 100)
    axes[0,0].set_title('Win Rate by Trading Date')
    axes[0,0].set_ylabel('Win Rate (%)')
    axes[0,0].tick_params(axis='x', rotation=45)
    
    # P&L distribution
    axes[0,1].hist(analyzer.results_data['pnl_percentage'], bins=30, alpha=0.7)
    axes[0,1].axvline(0, color='red', linestyle='--')
    axes[0,1].set_title('P&L Distribution')
    axes[0,1].set_xlabel('P&L (%)')
    
    # Average P&L by date
    axes[1,0].bar(date_perf.index, date_perf['Avg_PnL'])
    axes[1,0].set_title('Average P&L by Trading Date')
    axes[1,0].set_ylabel('Average P&L (%)')
    axes[1,0].tick_params(axis='x', rotation=45)
    axes[1,0].axhline(0, color='red', linestyle='--', alpha=0.5)
    
    # Risk-Reward visualization
    profitable = analyzer.results_data[analyzer.results_data['is_profitable']]
    unprofitable = analyzer.results_data[~analyzer.results_data['is_profitable']]
    
    axes[1,1].scatter(range(len(profitable)), profitable['pnl_percentage'], 
                     color='green', alpha=0.6, label='Profitable')
    axes[1,1].scatter(range(len(unprofitable)), unprofitable['pnl_percentage'], 
                     color='red', alpha=0.6, label='Unprofitable')
    axes[1,1].set_title('Trade Outcomes Scatter')
    axes[1,1].set_ylabel('P&L (%)')
    axes[1,1].legend()
    
    plt.tight_layout()
    plt.savefig('/Users/maverick/PycharmProjects/India-TS/ML/results/strategy_refinement_analysis.png', 
                dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\nAnalysis complete. Charts saved to: /Users/maverick/PycharmProjects/India-TS/ML/results/strategy_refinement_analysis.png")

if __name__ == "__main__":
    main()