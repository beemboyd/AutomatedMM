#!/usr/bin/env python3
"""
Long Reversal and Market Breadth Correlation Analysis
Analyzes the relationship between Long Reversal signals and market breadth conditions
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

class LongReversalBreadthAnalyzer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.reversal_dir = os.path.join(self.base_dir, 'Market_Regime', 'results')
        self.breadth_data_file = os.path.join(self.base_dir, 'Market_Regime', 'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
    def load_breadth_data(self):
        """Load historical market breadth data"""
        with open(self.breadth_data_file, 'r') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x['sma20_percent'])
        df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x['sma50_percent'])
        df['breadth_score'] = (df['sma20_percent'] * 0.6 + df['sma50_percent'] * 0.4) / 100
        
        return df
    
    def load_reversal_signals(self, start_date=None, end_date=None):
        """Load Long Reversal signals from Excel files"""
        all_signals = []
        
        # Get all Long Reversal files
        for filename in os.listdir(self.reversal_dir):
            if 'Long_Reversal' in filename and filename.endswith('.xlsx'):
                file_path = os.path.join(self.reversal_dir, filename)
                
                # Extract date from filename
                try:
                    # Filename format: Long_Reversal_Daily_YYYYMMDD_HHMMSS.xlsx
                    parts = filename.replace('.xlsx', '').split('_')
                    date_str = parts[3]  # Get YYYYMMDD part
                    signal_date = pd.to_datetime(date_str, format='%Y%m%d')
                    
                    # Filter by date range if provided
                    if start_date and signal_date < start_date:
                        continue
                    if end_date and signal_date > end_date:
                        continue
                    
                    # Read the Excel file
                    df = pd.read_excel(file_path)
                    df['signal_date'] = signal_date
                    all_signals.append(df)
                    
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
        
        if all_signals:
            return pd.concat(all_signals, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def analyze_breadth_on_signal_days(self):
        """Analyze market breadth conditions on days when Long Reversal signals are generated"""
        breadth_df = self.load_breadth_data()
        signals_df = self.load_reversal_signals()
        
        if signals_df.empty:
            print("No reversal signals found")
            return None
        
        # Get unique signal dates
        signal_dates = signals_df['signal_date'].dt.date.unique()
        
        # Extract breadth data for signal dates
        breadth_on_signals = []
        for signal_date in signal_dates:
            breadth_row = breadth_df[breadth_df['date'].dt.date == signal_date]
            if not breadth_row.empty:
                breadth_on_signals.append({
                    'date': signal_date,
                    'signal_count': len(signals_df[signals_df['signal_date'].dt.date == signal_date]),
                    'sma20_percent': breadth_row.iloc[0]['sma20_percent'],
                    'sma50_percent': breadth_row.iloc[0]['sma50_percent'],
                    'market_regime': breadth_row.iloc[0]['market_regime'],
                    'breadth_score': breadth_row.iloc[0]['breadth_score']
                })
        
        analysis_df = pd.DataFrame(breadth_on_signals)
        
        # Calculate statistics
        print("\n=== Market Breadth Analysis on Long Reversal Signal Days ===")
        print(f"Total signal days analyzed: {len(analysis_df)}")
        print(f"\nAverage breadth on signal days:")
        print(f"  SMA20: {analysis_df['sma20_percent'].mean():.1f}%")
        print(f"  SMA50: {analysis_df['sma50_percent'].mean():.1f}%")
        print(f"  Breadth Score: {analysis_df['breadth_score'].mean():.3f}")
        
        print(f"\nCompare to overall market averages:")
        print(f"  SMA20: {breadth_df['sma20_percent'].mean():.1f}%")
        print(f"  SMA50: {breadth_df['sma50_percent'].mean():.1f}%")
        print(f"  Breadth Score: {breadth_df['breadth_score'].mean():.3f}")
        
        # Market regime distribution
        print(f"\nMarket regime on signal days:")
        regime_counts = analysis_df['market_regime'].value_counts()
        for regime, count in regime_counts.items():
            print(f"  {regime}: {count} days ({count/len(analysis_df)*100:.1f}%)")
        
        return analysis_df
    
    def analyze_signal_performance_by_breadth(self):
        """Analyze how Long Reversal signals perform under different breadth conditions"""
        breadth_df = self.load_breadth_data()
        signals_df = self.load_reversal_signals()
        
        if signals_df.empty:
            print("No reversal signals found")
            return None
        
        # Merge signals with breadth data
        signals_df['date'] = signals_df['signal_date'].dt.date
        breadth_df['date'] = breadth_df['date'].dt.date
        
        merged_df = signals_df.merge(
            breadth_df[['date', 'sma20_percent', 'sma50_percent', 'market_regime', 'breadth_score']], 
            on='date', 
            how='left'
        )
        
        # Categorize breadth conditions
        merged_df['breadth_category'] = pd.cut(
            merged_df['sma20_percent'], 
            bins=[0, 30, 50, 70, 100],
            labels=['Bearish', 'Neutral-Low', 'Neutral-High', 'Bullish']
        )
        
        # Analyze signal quality by breadth
        print("\n=== Signal Analysis by Market Breadth ===")
        for category in ['Bearish', 'Neutral-Low', 'Neutral-High', 'Bullish']:
            category_data = merged_df[merged_df['breadth_category'] == category]
            if len(category_data) > 0:
                avg_score = category_data['Score'].mean() if 'Score' in category_data.columns else 0
                print(f"\n{category} Breadth (SMA20):")
                print(f"  Signal Count: {len(category_data)}")
                print(f"  Average Score: {avg_score:.2f}")
                print(f"  Top Tickers: {', '.join(category_data.nlargest(5, 'Score')['Ticker'].tolist() if 'Score' in category_data.columns else [])}")
        
        return merged_df
    
    def create_correlation_visualization(self):
        """Create visualizations showing the correlation between breadth and reversal signals"""
        analysis_df = self.analyze_breadth_on_signal_days()
        
        if analysis_df is None or analysis_df.empty:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. Scatter plot: Signal count vs Breadth
        ax1 = axes[0, 0]
        ax1.scatter(analysis_df['sma20_percent'], analysis_df['signal_count'], alpha=0.6, s=100)
        ax1.set_xlabel('SMA20 Breadth %')
        ax1.set_ylabel('Number of Signals')
        ax1.set_title('Long Reversal Signal Count vs Market Breadth')
        ax1.grid(True, alpha=0.3)
        
        # Add correlation coefficient
        corr = analysis_df['sma20_percent'].corr(analysis_df['signal_count'])
        ax1.text(0.05, 0.95, f'Correlation: {corr:.3f}', transform=ax1.transAxes, 
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # 2. Box plot: Signal distribution by market regime
        ax2 = axes[0, 1]
        regime_data = []
        regimes = []
        for regime in analysis_df['market_regime'].unique():
            regime_signals = analysis_df[analysis_df['market_regime'] == regime]['signal_count']
            if len(regime_signals) > 0:
                regime_data.append(regime_signals)
                regimes.append(regime)
        
        ax2.boxplot(regime_data, labels=regimes)
        ax2.set_ylabel('Number of Signals')
        ax2.set_title('Signal Distribution by Market Regime')
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. Time series: Breadth and signals
        ax3 = axes[1, 0]
        ax3_twin = ax3.twinx()
        
        ax3.plot(analysis_df['date'], analysis_df['sma20_percent'], 'b-', label='SMA20 Breadth', linewidth=2)
        ax3_twin.bar(analysis_df['date'], analysis_df['signal_count'], alpha=0.5, color='orange', label='Signal Count')
        
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Breadth %', color='b')
        ax3_twin.set_ylabel('Signal Count', color='orange')
        ax3.set_title('Market Breadth and Long Reversal Signals Over Time')
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. Heatmap: Average signals by breadth ranges
        ax4 = axes[1, 1]
        
        # Create breadth bins
        analysis_df['sma20_bin'] = pd.cut(analysis_df['sma20_percent'], bins=5)
        analysis_df['sma50_bin'] = pd.cut(analysis_df['sma50_percent'], bins=5)
        
        # Create pivot table
        pivot_data = analysis_df.pivot_table(
            values='signal_count', 
            index='sma50_bin', 
            columns='sma20_bin', 
            aggfunc='mean'
        )
        
        sns.heatmap(pivot_data, annot=True, fmt='.1f', cmap='YlOrRd', ax=ax4)
        ax4.set_xlabel('SMA20 Breadth Range')
        ax4.set_ylabel('SMA50 Breadth Range')
        ax4.set_title('Average Signal Count by Breadth Conditions')
        
        plt.tight_layout()
        
        # Save the plot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.base_dir, 'analysis', f'long_reversal_breadth_correlation_{timestamp}.png')
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"\nVisualization saved to: {output_file}")
        
        plt.show()
    
    def generate_trading_rules(self):
        """Generate suggested trading rules based on breadth conditions"""
        analysis_df = self.analyze_breadth_on_signal_days()
        
        if analysis_df is None or analysis_df.empty:
            return
        
        print("\n=== Suggested Trading Rules Based on Breadth Analysis ===")
        
        # Rule 1: Breadth threshold
        high_breadth_signals = analysis_df[analysis_df['sma20_percent'] > 50]
        low_breadth_signals = analysis_df[analysis_df['sma20_percent'] <= 30]
        
        if len(high_breadth_signals) > 0 and len(low_breadth_signals) > 0:
            avg_signals_high = high_breadth_signals['signal_count'].mean()
            avg_signals_low = low_breadth_signals['signal_count'].mean()
            
            print(f"\n1. Breadth Filter Rule:")
            print(f"   - High breadth (>50%): Avg {avg_signals_high:.1f} signals/day")
            print(f"   - Low breadth (≤30%): Avg {avg_signals_low:.1f} signals/day")
            print(f"   - Suggestion: {'Increase' if avg_signals_high > avg_signals_low else 'Decrease'} position sizing when breadth > 50%")
        
        # Rule 2: Regime-based filtering
        regime_stats = analysis_df.groupby('market_regime')['signal_count'].agg(['mean', 'std', 'count'])
        print(f"\n2. Market Regime Rules:")
        for regime, stats in regime_stats.iterrows():
            if stats['count'] > 2:  # Only if we have enough data
                print(f"   - {regime}: Avg {stats['mean']:.1f} signals (±{stats['std']:.1f})")
        
        # Rule 3: Breadth momentum
        analysis_df = analysis_df.sort_values('date')
        analysis_df['breadth_change'] = analysis_df['sma20_percent'].diff()
        
        improving_breadth = analysis_df[analysis_df['breadth_change'] > 5]
        declining_breadth = analysis_df[analysis_df['breadth_change'] < -5]
        
        print(f"\n3. Breadth Momentum Rule:")
        if len(improving_breadth) > 0:
            print(f"   - Improving breadth (>5% change): Avg {improving_breadth['signal_count'].mean():.1f} signals")
        if len(declining_breadth) > 0:
            print(f"   - Declining breadth (<-5% change): Avg {declining_breadth['signal_count'].mean():.1f} signals")
        
        # Rule 4: Combined score
        print(f"\n4. Combined Breadth Score Rule:")
        print(f"   - Consider signals when breadth score > {analysis_df['breadth_score'].median():.3f}")
        print(f"   - This represents market conditions better than average")
        
        return analysis_df


def main():
    analyzer = LongReversalBreadthAnalyzer()
    
    print("=== Long Reversal and Market Breadth Correlation Analysis ===\n")
    
    # Run analyses
    analyzer.analyze_breadth_on_signal_days()
    analyzer.analyze_signal_performance_by_breadth()
    analyzer.create_correlation_visualization()
    analyzer.generate_trading_rules()
    
    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()