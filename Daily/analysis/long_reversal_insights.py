#!/usr/bin/env python3
"""
Long Reversal Pattern Insights and Strategy Optimization
Analyzes performance data to generate actionable insights
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

def load_latest_performance_data():
    """Load the most recent performance analysis data"""
    import glob
    import os
    
    # Find latest performance file
    pattern = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/long_reversal_performance_*.xlsx'
    files = glob.glob(pattern)
    
    if not files:
        print("No performance data files found")
        return None
    
    latest_file = max(files, key=os.path.getctime)
    print(f"Loading data from: {latest_file}")
    
    return pd.read_excel(latest_file)

def analyze_patterns(df):
    """Analyze patterns in the performance data"""
    insights = {}
    
    # 1. Best holding period analysis
    holding_periods = [1, 3, 5, 10, 20]
    holding_analysis = {}
    
    for period in holding_periods:
        ret_col = f'Return_{period}D'
        if ret_col in df.columns:
            returns = df[ret_col].dropna()
            holding_analysis[period] = {
                'avg_return': returns.mean(),
                'win_rate': (returns > 0).sum() / len(returns) * 100,
                'sharpe': returns.mean() / returns.std() if returns.std() > 0 else 0,
                'max_return': returns.max(),
                'min_return': returns.min(),
                'positive_avg': returns[returns > 0].mean() if len(returns[returns > 0]) > 0 else 0,
                'negative_avg': returns[returns < 0].mean() if len(returns[returns < 0]) > 0 else 0
            }
    
    insights['holding_period_analysis'] = holding_analysis
    
    # 2. Stop loss effectiveness
    if 'Stopped_Out' in df.columns:
        stopped_out = df[df['Stopped_Out'] == True]
        not_stopped = df[df['Stopped_Out'] != True]
        
        insights['stop_loss_analysis'] = {
            'stop_rate': len(stopped_out) / len(df) * 100,
            'avg_loss_when_stopped': stopped_out['Return_3D'].mean() if 'Return_3D' in stopped_out else None,
            'avg_return_when_not_stopped': not_stopped['Return_3D'].mean() if 'Return_3D' in not_stopped else None,
            'stop_day_distribution': stopped_out['Stop_Day'].value_counts().to_dict() if 'Stop_Day' in stopped_out else None
        }
    
    # 3. Entry timing analysis
    if 'Actual_Entry' in df.columns and 'Entry_Price' in df.columns:
        df['Entry_Slippage'] = ((df['Actual_Entry'] - df['Entry_Price']) / df['Entry_Price']) * 100
        
        insights['entry_analysis'] = {
            'avg_slippage': df['Entry_Slippage'].mean(),
            'positive_slippage_rate': (df['Entry_Slippage'] > 0).sum() / len(df) * 100,
            'slippage_impact_on_returns': df[['Entry_Slippage', 'Return_3D']].corr().iloc[0, 1] if 'Return_3D' in df else None
        }
    
    # 4. Target achievement analysis
    target_analysis = {}
    for period in [3, 5, 10]:
        t1_col = f'Target1_Hit_{period}D'
        t2_col = f'Target2_Hit_{period}D'
        
        if t1_col in df.columns:
            target_analysis[f'{period}D'] = {
                'target1_hit_rate': df[t1_col].sum() / len(df) * 100,
                'target2_hit_rate': df[t2_col].sum() / len(df) * 100 if t2_col in df.columns else 0
            }
    
    insights['target_analysis'] = target_analysis
    
    # 5. Score-based performance
    if 'Score' in df.columns and 'Return_3D' in df.columns:
        score_performance = df.groupby('Score')['Return_3D'].agg(['mean', 'std', 'count'])
        score_performance['win_rate'] = df.groupby('Score')['Return_3D'].apply(lambda x: (x > 0).sum() / len(x) * 100)
        insights['score_performance'] = score_performance.to_dict()
    
    # 6. Maximum favorable/adverse excursion
    mfe_mae_analysis = {}
    for period in [3, 5, 10]:
        max_gain_col = f'Max_Gain_{period}D'
        max_loss_col = f'Max_Loss_{period}D'
        
        if max_gain_col in df.columns and max_loss_col in df.columns:
            mfe_mae_analysis[f'{period}D'] = {
                'avg_max_gain': df[max_gain_col].mean(),
                'avg_max_loss': df[max_loss_col].mean(),
                'gain_to_loss_ratio': abs(df[max_gain_col].mean() / df[max_loss_col].mean()) if df[max_loss_col].mean() != 0 else 0
            }
    
    insights['mfe_mae_analysis'] = mfe_mae_analysis
    
    return insights

def generate_recommendations(insights):
    """Generate actionable recommendations based on insights"""
    recommendations = []
    
    # 1. Optimal holding period
    holding_analysis = insights.get('holding_period_analysis', {})
    if holding_analysis:
        best_sharpe = max(holding_analysis.items(), key=lambda x: x[1]['sharpe'])
        best_return = max(holding_analysis.items(), key=lambda x: x[1]['avg_return'])
        best_win_rate = max(holding_analysis.items(), key=lambda x: x[1]['win_rate'])
        
        recommendations.append({
            'category': 'Holding Period',
            'finding': f"Best risk-adjusted returns (Sharpe: {best_sharpe[1]['sharpe']:.2f}) at {best_sharpe[0]} days",
            'action': f"Consider {best_sharpe[0]}-day holding period as primary exit strategy"
        })
        
        if best_sharpe[0] != best_win_rate[0]:
            recommendations.append({
                'category': 'Alternative Exit',
                'finding': f"Highest win rate ({best_win_rate[1]['win_rate']:.1f}%) at {best_win_rate[0]} days",
                'action': f"For risk-averse traders, consider {best_win_rate[0]}-day holding period"
            })
    
    # 2. Stop loss optimization
    sl_analysis = insights.get('stop_loss_analysis', {})
    if sl_analysis and sl_analysis.get('stop_rate'):
        stop_rate = sl_analysis['stop_rate']
        
        if stop_rate > 50:
            recommendations.append({
                'category': 'Stop Loss',
                'finding': f"High stop loss hit rate ({stop_rate:.1f}%)",
                'action': "Consider widening stop loss by 0.5-1 ATR to reduce premature exits"
            })
        
        if sl_analysis.get('stop_day_distribution'):
            early_stops = sum(v for k, v in sl_analysis['stop_day_distribution'].items() if k <= 2)
            total_stops = sum(sl_analysis['stop_day_distribution'].values())
            if early_stops / total_stops > 0.5:
                recommendations.append({
                    'category': 'Stop Loss Timing',
                    'finding': "Most stop losses hit within 2 days",
                    'action': "Consider using wider initial stop loss or time-based stop adjustment"
                })
    
    # 3. Entry optimization
    entry_analysis = insights.get('entry_analysis', {})
    if entry_analysis and entry_analysis.get('avg_slippage') is not None:
        avg_slippage = entry_analysis['avg_slippage']
        
        if abs(avg_slippage) > 0.5:
            recommendations.append({
                'category': 'Entry Execution',
                'finding': f"Significant entry slippage ({avg_slippage:.2f}%)",
                'action': "Consider limit orders at signal price or slightly below for better entries"
            })
    
    # 4. Target optimization
    target_analysis = insights.get('target_analysis', {})
    if target_analysis:
        for period, data in target_analysis.items():
            if data['target1_hit_rate'] < 30:
                recommendations.append({
                    'category': 'Target Setting',
                    'finding': f"Low Target1 hit rate ({data['target1_hit_rate']:.1f}%) in {period}",
                    'action': "Consider reducing Target1 to 1.5x risk for higher probability exits"
                })
                break
    
    # 5. Score-based filtering
    score_perf = insights.get('score_performance', {})
    if score_perf and 'mean' in score_perf:
        means = score_perf['mean']
        if means:
            best_score = max(means.items(), key=lambda x: x[1])
            worst_score = min(means.items(), key=lambda x: x[1])
            
            if best_score[1] > worst_score[1] * 2:
                recommendations.append({
                    'category': 'Signal Filtering',
                    'finding': f"Score '{best_score[0]}' performs {best_score[1]/worst_score[1]:.1f}x better than '{worst_score[0]}'",
                    'action': f"Focus on signals with score '{best_score[0]}' for better returns"
                })
    
    # 6. Risk management
    mfe_mae = insights.get('mfe_mae_analysis', {})
    if mfe_mae:
        for period, data in mfe_mae.items():
            if data['gain_to_loss_ratio'] > 2:
                recommendations.append({
                    'category': 'Risk Management',
                    'finding': f"Strong gain/loss ratio ({data['gain_to_loss_ratio']:.1f}) in {period}",
                    'action': f"Consider trailing stops after {period} to capture upside while limiting downside"
                })
                break
    
    return recommendations

def create_visualizations(df, insights):
    """Create visualization plots for better understanding"""
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. Returns distribution by holding period
    ax1 = axes[0, 0]
    returns_data = []
    for period in [1, 3, 5, 10, 20]:
        col = f'Return_{period}D'
        if col in df.columns:
            returns_data.append(df[col].dropna())
    
    ax1.boxplot(returns_data, labels=['1D', '3D', '5D', '10D', '20D'])
    ax1.set_title('Returns Distribution by Holding Period')
    ax1.set_ylabel('Return (%)')
    ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    
    # 2. Win rate by holding period
    ax2 = axes[0, 1]
    holding_data = insights.get('holding_period_analysis', {})
    if holding_data:
        periods = list(holding_data.keys())
        win_rates = [holding_data[p]['win_rate'] for p in periods]
        
        ax2.bar(periods, win_rates)
        ax2.set_title('Win Rate by Holding Period')
        ax2.set_xlabel('Holding Period (Days)')
        ax2.set_ylabel('Win Rate (%)')
        ax2.axhline(y=50, color='r', linestyle='--', alpha=0.5)
    
    # 3. Score performance
    ax3 = axes[1, 0]
    if 'Score' in df.columns and 'Return_3D' in df.columns:
        score_returns = df.groupby('Score')['Return_3D'].mean().sort_values()
        ax3.bar(range(len(score_returns)), score_returns.values)
        ax3.set_xticks(range(len(score_returns)))
        ax3.set_xticklabels(score_returns.index, rotation=45)
        ax3.set_title('Average 3-Day Return by Score')
        ax3.set_ylabel('Return (%)')
    
    # 4. Stop loss analysis
    ax4 = axes[1, 1]
    if 'Stopped_Out' in df.columns and 'Stop_Day' in df.columns:
        stop_days = df[df['Stopped_Out'] == True]['Stop_Day'].value_counts().sort_index()
        ax4.bar(stop_days.index, stop_days.values)
        ax4.set_title('Stop Loss Hit Distribution')
        ax4.set_xlabel('Day Number')
        ax4.set_ylabel('Count')
    
    plt.tight_layout()
    plt.savefig('/Users/maverick/PycharmProjects/India-TS/Daily/analysis/long_reversal_insights.png', dpi=300)
    plt.close()

def main():
    # Load performance data
    df = load_latest_performance_data()
    if df is None:
        return
    
    print(f"\nAnalyzing {len(df)} Long Reversal signals...\n")
    
    # Generate insights
    insights = analyze_patterns(df)
    
    # Generate recommendations
    recommendations = generate_recommendations(insights)
    
    # Create visualizations
    create_visualizations(df, insights)
    
    # Print summary
    print("=" * 60)
    print("LONG REVERSAL PATTERN - STRATEGIC INSIGHTS")
    print("=" * 60)
    
    print("\n### KEY FINDINGS ###\n")
    
    # Print holding period summary
    holding_data = insights.get('holding_period_analysis', {})
    if holding_data:
        print("Holding Period Analysis:")
        for period, data in sorted(holding_data.items()):
            print(f"  {period:2d} days - Return: {data['avg_return']:6.2f}%, Win Rate: {data['win_rate']:5.1f}%, Sharpe: {data['sharpe']:5.2f}")
    
    # Print stop loss summary
    sl_data = insights.get('stop_loss_analysis', {})
    if sl_data:
        print(f"\nStop Loss Analysis:")
        print(f"  Hit Rate: {sl_data.get('stop_rate', 0):.1f}%")
        print(f"  Avg Loss When Stopped: {sl_data.get('avg_loss_when_stopped', 0):.2f}%")
        print(f"  Avg Return When Not Stopped: {sl_data.get('avg_return_when_not_stopped', 0):.2f}%")
    
    # Print entry analysis
    entry_data = insights.get('entry_analysis', {})
    if entry_data:
        print(f"\nEntry Analysis:")
        print(f"  Average Slippage: {entry_data.get('avg_slippage', 0):.2f}%")
        print(f"  Positive Slippage Rate: {entry_data.get('positive_slippage_rate', 0):.1f}%")
    
    print("\n### STRATEGIC RECOMMENDATIONS ###\n")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec['category']}:")
        print(f"   Finding: {rec['finding']}")
        print(f"   Action: {rec['action']}\n")
    
    # Save detailed insights
    with open('/Users/maverick/PycharmProjects/India-TS/Daily/analysis/long_reversal_detailed_insights.json', 'w') as f:
        json.dump(insights, f, indent=4, default=str)
    
    print("\nDetailed insights saved to:")
    print("- long_reversal_detailed_insights.json")
    print("- long_reversal_insights.png")
    
    # Generate optimal strategy parameters
    print("\n### OPTIMAL STRATEGY PARAMETERS ###\n")
    
    # Based on analysis, suggest optimal parameters
    holding_analysis = insights.get('holding_period_analysis', {})
    if holding_analysis:
        best_sharpe_period = max(holding_analysis.items(), key=lambda x: x[1]['sharpe'])[0]
        
        print(f"Entry: Market order at next day open")
        print(f"Initial Stop Loss: As per signal (consider widening by 0.5 ATR if stop rate > 50%)")
        print(f"Primary Exit: {best_sharpe_period} days (best risk-adjusted returns)")
        print(f"Target 1: Reduce to 1.5x risk if current hit rate < 30%")
        print(f"Target 2: Keep as stretch target")
        print(f"Position Sizing: Risk 1-2% of capital per trade")
        print(f"Signal Filter: Prefer higher scores if significant performance difference")

if __name__ == "__main__":
    main()