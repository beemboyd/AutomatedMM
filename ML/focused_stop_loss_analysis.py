#!/usr/bin/env python3
"""
Focused Stop Loss Analysis for Brooks Strategy
Analyze stop loss patterns and optimal mechanisms
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FocusedStopLossAnalyzer:
    def __init__(self):
        self.results_path = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.pattern = "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"
        
    def load_brooks_data(self):
        """Load all Brooks files and analyze stop loss data"""
        files = glob.glob(os.path.join(self.results_path, self.pattern))
        files.sort()
        
        all_data = []
        
        for file_path in files:
            try:
                df = pd.read_excel(file_path)
                filename = os.path.basename(file_path)
                date_parts = filename.split('_')[-3:-1]
                file_date = '_'.join(date_parts)
                df['file_date'] = file_date
                all_data.append(df)
                logger.info(f"Loaded {len(df)} records from {filename}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total records: {len(combined_df)}")
            return combined_df
        return pd.DataFrame()
    
    def analyze_current_stops(self, df):
        """Analyze current stop loss implementation"""
        print("\n" + "="*60)
        print("CURRENT STOP LOSS ANALYSIS")
        print("="*60)
        
        # Calculate stop loss percentages
        df['stop_loss_pct'] = ((df['Entry_Price'] - df['Stop_Loss']) / df['Entry_Price']) * 100
        df['atr_pct'] = (df['ATR'] / df['Entry_Price']) * 100
        df['risk_pct'] = (df['Risk'] / df['Entry_Price']) * 100
        
        # Basic statistics
        print(f"Stop Loss Statistics:")
        print(f"├─ Average: {df['stop_loss_pct'].mean():.2f}%")
        print(f"├─ Median: {df['stop_loss_pct'].median():.2f}%")
        print(f"├─ Range: {df['stop_loss_pct'].min():.2f}% to {df['stop_loss_pct'].max():.2f}%")
        print(f"└─ Std Dev: {df['stop_loss_pct'].std():.2f}%")
        
        # ATR relationship
        df['atr_multiple'] = np.where(df['atr_pct'] > 0, df['stop_loss_pct'] / df['atr_pct'], 0)
        valid_multiples = df[df['atr_multiple'] > 0]['atr_multiple']
        
        print(f"\nATR Relationship:")
        print(f"├─ Average ATR: {df['atr_pct'].mean():.2f}%")
        print(f"├─ Current Stop/ATR Multiple: {valid_multiples.mean():.2f}x")
        print(f"└─ Multiple Range: {valid_multiples.min():.2f}x to {valid_multiples.max():.2f}x")
        
        # Risk-Reward Analysis
        df['target1_pct'] = ((df['Target1'] - df['Entry_Price']) / df['Entry_Price']) * 100
        df['target2_pct'] = ((df['Target2'] - df['Entry_Price']) / df['Entry_Price']) * 100
        
        print(f"\nRisk-Reward Analysis:")
        print(f"├─ Average Target 1: {df['target1_pct'].mean():.2f}%")
        print(f"├─ Average Target 2: {df['target2_pct'].mean():.2f}%")
        print(f"├─ Current Risk-Reward (T1): 1:{(df['target1_pct'].mean() / df['stop_loss_pct'].mean()):.2f}")
        print(f"└─ Current Risk-Reward (T2): 1:{(df['target2_pct'].mean() / df['stop_loss_pct'].mean()):.2f}")
        
        return df
    
    def analyze_stop_distribution(self, df):
        """Analyze stop loss distribution patterns"""
        print("\n" + "="*60)
        print("STOP LOSS DISTRIBUTION ANALYSIS")
        print("="*60)
        
        # Create bins for analysis
        df['stop_range'] = pd.cut(df['stop_loss_pct'], 
                                 bins=[0, 1.5, 2.5, 3.5, 4.5, 10], 
                                 labels=['0-1.5%', '1.5-2.5%', '2.5-3.5%', '3.5-4.5%', '4.5%+'])
        
        distribution = df['stop_range'].value_counts().sort_index()
        
        print("Stop Loss Distribution:")
        for range_label, count in distribution.items():
            percentage = (count / len(df)) * 100
            print(f"├─ {range_label}: {count} trades ({percentage:.1f}%)")
        
        # Analyze by volatility (ATR)
        df['volatility_group'] = pd.cut(df['atr_pct'], 
                                       bins=[0, 2, 4, 6, 20], 
                                       labels=['Low (<2%)', 'Medium (2-4%)', 'High (4-6%)', 'Very High (6%+)'])
        
        print(f"\nStop Loss by Volatility Group:")
        vol_analysis = df.groupby('volatility_group')['stop_loss_pct'].agg(['count', 'mean', 'std']).round(2)
        print(vol_analysis.to_string())
        
        return df
    
    def compare_stop_methods(self, df):
        """Compare different stop loss methodologies"""
        print("\n" + "="*60)
        print("STOP LOSS METHOD COMPARISON")
        print("="*60)
        
        # Calculate different stop methods
        methods = {
            'Current': df['stop_loss_pct'],
            'Fixed_2pct': pd.Series([2.0] * len(df)),
            'Fixed_3pct': pd.Series([3.0] * len(df)),
            'Fixed_4pct': pd.Series([4.0] * len(df)),
            'ATR_1x': df['atr_pct'] * 1.0,
            'ATR_1.5x': df['atr_pct'] * 1.5,
            'ATR_2x': df['atr_pct'] * 2.0,
        }
        
        print("Method Comparison:")
        print(f"{'Method':<12} {'Avg Stop':<10} {'Std Dev':<10} {'Min':<8} {'Max':<8} {'RR Ratio':<10}")
        print("-" * 65)
        
        avg_target = df['target1_pct'].mean()
        
        for method_name, stop_values in methods.items():
            avg_stop = stop_values.mean()
            std_stop = stop_values.std()
            min_stop = stop_values.min()
            max_stop = stop_values.max()
            rr_ratio = avg_target / avg_stop if avg_stop > 0 else 0
            
            print(f"{method_name:<12} {avg_stop:<10.2f} {std_stop:<10.2f} {min_stop:<8.2f} {max_stop:<8.2f} 1:{rr_ratio:<8.2f}")
        
        return methods
    
    def analyze_optimal_stops(self, df):
        """Determine optimal stop loss levels"""
        print("\n" + "="*60)
        print("OPTIMAL STOP LOSS ANALYSIS")
        print("="*60)
        
        # Load our previous performance analysis
        try:
            perf_data = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_analysis_20250526_212145.xlsx')
            
            # Merge with current data
            merged = df.merge(perf_data[['ticker', 'file_date', 'pnl_percentage', 'is_profitable']], 
                            left_on=['Ticker', 'file_date'], 
                            right_on=['ticker', 'file_date'], 
                            how='left')
            
            # Analyze stop effectiveness
            print("Stop Effectiveness Analysis:")
            
            # Group by stop ranges and analyze success rates
            stop_effectiveness = merged.groupby('stop_range').agg({
                'is_profitable': ['count', 'sum', 'mean'],
                'pnl_percentage': 'mean',
                'stop_loss_pct': 'mean'
            }).round(3)
            
            stop_effectiveness.columns = ['Total_Trades', 'Profitable_Trades', 'Win_Rate', 'Avg_PnL', 'Avg_Stop']
            
            print(stop_effectiveness.to_string())
            
            # Find optimal range
            if not stop_effectiveness.empty:
                best_range = stop_effectiveness.loc[stop_effectiveness['Win_Rate'].idxmax()]
                print(f"\nBest Performing Stop Range: {stop_effectiveness['Win_Rate'].idxmax()}")
                print(f"├─ Win Rate: {best_range['Win_Rate']:.1%}")
                print(f"├─ Average P&L: {best_range['Avg_PnL']:.2f}%")
                print(f"└─ Average Stop: {best_range['Avg_Stop']:.2f}%")
            
        except Exception as e:
            print(f"Could not load performance data: {e}")
            print("Proceeding with theoretical analysis...")
        
        # Theoretical optimal analysis
        print(f"\nTheoretical Optimization:")
        
        # Calculate efficiency score for each method
        avg_target = df['target1_pct'].mean()
        efficiency_scores = {}
        
        for method_name in ['Fixed_2pct', 'Fixed_3pct', 'ATR_1.5x']:
            if method_name == 'Fixed_2pct':
                stop_level = 2.0
            elif method_name == 'Fixed_3pct':
                stop_level = 3.0
            else:
                stop_level = (df['atr_pct'] * 1.5).mean()
            
            # Simple efficiency calculation
            risk_reward = avg_target / stop_level
            # Penalize very tight stops (higher false signals) and very wide stops (lower RR)
            if stop_level < 2.0:
                penalty = 0.8  # Tight stops penalty
            elif stop_level > 5.0:
                penalty = 0.9  # Wide stops penalty
            else:
                penalty = 1.0
            
            efficiency = risk_reward * penalty
            efficiency_scores[method_name] = efficiency
            
            print(f"├─ {method_name}: Stop {stop_level:.2f}%, RR 1:{risk_reward:.2f}, Efficiency {efficiency:.2f}")
        
        best_method = max(efficiency_scores, key=efficiency_scores.get)
        print(f"└─ Best Method: {best_method}")
        
        return efficiency_scores
    
    def generate_recommendations(self, df, methods, efficiency_scores):
        """Generate final stop loss recommendations"""
        print("\n" + "="*60)
        print("STOP LOSS RECOMMENDATIONS")
        print("="*60)
        
        # Current method analysis
        current_avg = df['stop_loss_pct'].mean()
        atr_avg = df['atr_pct'].mean()
        
        print("RECOMMENDED STOP LOSS FRAMEWORK:")
        print("-" * 40)
        
        print("🎯 PRIMARY METHOD: Adaptive ATR-Based Stops")
        print("   Formula: Stop = Entry_Price - (Multiplier × ATR)")
        print("   └─ Low Volatility (ATR <2%): Use 1.0x ATR")
        print("   └─ Medium Volatility (ATR 2-4%): Use 1.5x ATR") 
        print("   └─ High Volatility (ATR >4%): Use 2.0x ATR")
        
        print(f"\n🛡️  BACKUP METHOD: Fixed 3% Stop")
        print("   └─ Use when ATR data unavailable")
        print("   └─ Provides consistent risk management")
        
        print(f"\n⚡ DYNAMIC ADJUSTMENTS:")
        print("   1. Move to breakeven after 2% profit")
        print("   2. Trail by 1.5x ATR from highest point")
        print("   3. Tighten before earnings/events")
        print("   4. Widen during market stress (VIX >25)")
        
        print(f"\n📊 POSITION SIZING:")
        print("   └─ Position Size = (2% of Capital) ÷ Stop Distance")
        print("   └─ Maximum risk per trade: 2% of portfolio")
        
        print(f"\n🚨 RISK CONTROLS:")
        print("   1. Daily loss limit: 6% (3 stop-outs)")
        print("   2. Maximum drawdown: 15%")
        print("   3. Review stops weekly")
        print("   4. Emergency exit at -8% loss")
        
        # Implementation example
        print(f"\n💡 IMPLEMENTATION EXAMPLE:")
        example_price = 1000
        example_atr = 30  # ₹30 ATR
        example_atr_pct = (example_atr / example_price) * 100  # 3%
        
        if example_atr_pct <= 2:
            multiplier = 1.0
        elif example_atr_pct <= 4:
            multiplier = 1.5
        else:
            multiplier = 2.0
            
        stop_price = example_price - (multiplier * example_atr)
        stop_pct = ((example_price - stop_price) / example_price) * 100
        
        print(f"   Stock Price: ₹{example_price}")
        print(f"   ATR: ₹{example_atr} ({example_atr_pct:.1f}%)")
        print(f"   Multiplier: {multiplier}x")
        print(f"   Stop Price: ₹{stop_price:.2f}")
        print(f"   Stop Distance: {stop_pct:.2f}%")
        print(f"   Position Size: ₹{(20000 / (example_price - stop_price)):.0f} shares")
        print(f"   (Assuming ₹10,00,000 capital, 2% risk = ₹20,000)")
    
    def create_visualizations(self, df, methods):
        """Create stop loss analysis charts"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. Current stop distribution
        axes[0,0].hist(df['stop_loss_pct'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0,0].set_title('Current Stop Loss Distribution', fontweight='bold')
        axes[0,0].set_xlabel('Stop Loss (%)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].axvline(df['stop_loss_pct'].mean(), color='red', linestyle='--', 
                         label=f'Mean: {df["stop_loss_pct"].mean():.2f}%')
        axes[0,0].legend()
        
        # 2. ATR vs Current Stops
        axes[0,1].scatter(df['atr_pct'], df['stop_loss_pct'], alpha=0.6, color='green')
        axes[0,1].set_title('ATR vs Stop Loss Relationship', fontweight='bold')
        axes[0,1].set_xlabel('ATR (%)')
        axes[0,1].set_ylabel('Current Stop Loss (%)')
        
        # Add trend line
        z = np.polyfit(df['atr_pct'], df['stop_loss_pct'], 1)
        p = np.poly1d(z)
        axes[0,1].plot(df['atr_pct'], p(df['atr_pct']), "r--", alpha=0.8)
        
        # 3. Method comparison
        method_names = ['Current', 'Fixed 2%', 'Fixed 3%', 'ATR 1.5x']
        method_avgs = [
            df['stop_loss_pct'].mean(),
            2.0,
            3.0,
            (df['atr_pct'] * 1.5).mean()
        ]
        
        bars = axes[0,2].bar(method_names, method_avgs, 
                            color=['blue', 'orange', 'green', 'red'], alpha=0.7)
        axes[0,2].set_title('Stop Loss Method Comparison', fontweight='bold')
        axes[0,2].set_ylabel('Average Stop Loss (%)')
        axes[0,2].tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar, value in zip(bars, method_avgs):
            axes[0,2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                          f'{value:.2f}%', ha='center', va='bottom')
        
        # 4. Risk-Reward analysis
        rr_ratios = []
        avg_target = df['target1_pct'].mean()
        for avg_stop in method_avgs:
            rr_ratios.append(avg_target / avg_stop if avg_stop > 0 else 0)
        
        axes[1,0].bar(method_names, rr_ratios, color='purple', alpha=0.7)
        axes[1,0].set_title('Risk-Reward Ratios by Method', fontweight='bold')
        axes[1,0].set_ylabel('Risk-Reward Ratio (1:X)')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # 5. Stop distribution by volatility
        volatility_data = df.groupby('volatility_group')['stop_loss_pct'].mean()
        axes[1,1].bar(volatility_data.index, volatility_data.values, color='orange', alpha=0.7)
        axes[1,1].set_title('Average Stop by Volatility Group', fontweight='bold')
        axes[1,1].set_ylabel('Average Stop Loss (%)')
        axes[1,1].tick_params(axis='x', rotation=45)
        
        # 6. ATR distribution
        axes[1,2].hist(df['atr_pct'], bins=20, alpha=0.7, color='coral', edgecolor='black')
        axes[1,2].set_title('ATR Distribution', fontweight='bold')
        axes[1,2].set_xlabel('ATR (%)')
        axes[1,2].set_ylabel('Frequency')
        axes[1,2].axvline(df['atr_pct'].mean(), color='red', linestyle='--',
                         label=f'Mean: {df["atr_pct"].mean():.2f}%')
        axes[1,2].legend()
        
        plt.tight_layout()
        plt.savefig('/Users/maverick/PycharmProjects/India-TS/ML/results/focused_stop_loss_analysis.png', 
                    dpi=300, bbox_inches='tight')
        plt.show()

def main():
    analyzer = FocusedStopLossAnalyzer()
    
    # Load and process data
    print("Loading Brooks reversal data...")
    df = analyzer.load_brooks_data()
    
    if df.empty:
        print("No data found!")
        return
    
    # Run analyses
    df = analyzer.analyze_current_stops(df)
    df = analyzer.analyze_stop_distribution(df)
    methods = analyzer.compare_stop_methods(df)
    efficiency = analyzer.analyze_optimal_stops(df)
    analyzer.generate_recommendations(df, methods, efficiency)
    
    # Create visualizations
    analyzer.create_visualizations(df, methods)
    
    print(f"\n✅ Analysis complete! Charts saved to:")
    print(f"   /Users/maverick/PycharmProjects/India-TS/ML/results/focused_stop_loss_analysis.png")

if __name__ == "__main__":
    main()