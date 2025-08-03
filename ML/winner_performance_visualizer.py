"""
Winner Performance Visualizer

Companion script to winner_performance_analyzer.py that creates visual charts
and insights for better understanding of winning ticker characteristics.

Usage:
    python winner_performance_visualizer.py [--excel-file path_to_analysis.xlsx]
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class WinnerPerformanceVisualizer:
    """Create visualizations for winner performance analysis"""
    
    def __init__(self, excel_file: str = None):
        """Initialize visualizer with data file"""
        self.excel_file = excel_file
        self.data = {}
        self.output_dir = "ML/results"
        
    def load_data(self, excel_file: str = None):
        """Load data from Excel file"""
        if excel_file:
            self.excel_file = excel_file
            
        if not self.excel_file:
            # Find the latest analysis file
            files = [f for f in os.listdir(self.output_dir) 
                    if f.startswith('winner_performance_analysis_') and f.endswith('.xlsx')]
            if files:
                files.sort()
                self.excel_file = os.path.join(self.output_dir, files[-1])
            else:
                raise ValueError("No analysis file found. Run winner_performance_analyzer.py first.")
        
        # Load all sheets
        xl_file = pd.ExcelFile(self.excel_file)
        for sheet_name in xl_file.sheet_names:
            self.data[sheet_name] = pd.read_excel(xl_file, sheet_name)
        
        print(f"Loaded data from: {self.excel_file}")
        print(f"Available sheets: {list(self.data.keys())}")
    
    def create_performance_distribution_chart(self):
        """Create distribution chart of ticker performance"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Winner Performance Distribution Analysis', fontsize=16)
        
        summary_df = self.data['Ticker_Summary']
        
        # 1. Total PnL Distribution
        ax1 = axes[0, 0]
        summary_df['Total_PnL_%'].hist(bins=50, ax=ax1, edgecolor='black')
        ax1.axvline(0, color='red', linestyle='--', label='Break-even')
        ax1.set_xlabel('Total PnL %')
        ax1.set_ylabel('Number of Tickers')
        ax1.set_title('Distribution of Total Returns')
        ax1.legend()
        
        # 2. Win Rate vs Total PnL Scatter
        ax2 = axes[0, 1]
        scatter = ax2.scatter(summary_df['Win_Rate_%'], summary_df['Total_PnL_%'], 
                             c=summary_df['Total_Trades'], s=50, alpha=0.6, cmap='viridis')
        ax2.axhline(0, color='red', linestyle='--', alpha=0.5)
        ax2.axvline(50, color='red', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Win Rate %')
        ax2.set_ylabel('Total PnL %')
        ax2.set_title('Win Rate vs Returns (color = trade count)')
        plt.colorbar(scatter, ax=ax2)
        
        # 3. Expectancy Distribution
        ax3 = axes[1, 0]
        positive_exp = summary_df[summary_df['Expectancy_%'] > 0]['Expectancy_%']
        negative_exp = summary_df[summary_df['Expectancy_%'] <= 0]['Expectancy_%']
        
        ax3.hist(positive_exp, bins=30, alpha=0.7, label='Positive Expectancy', color='green')
        ax3.hist(negative_exp, bins=30, alpha=0.7, label='Negative Expectancy', color='red')
        ax3.set_xlabel('Expectancy %')
        ax3.set_ylabel('Number of Tickers')
        ax3.set_title('Expectancy Distribution')
        ax3.legend()
        
        # 4. Top 20 Performers
        ax4 = axes[1, 1]
        top_20 = summary_df.nlargest(20, 'Total_PnL_%')
        ax4.barh(range(len(top_20)), top_20['Total_PnL_%'])
        ax4.set_yticks(range(len(top_20)))
        ax4.set_yticklabels(top_20['Ticker'])
        ax4.set_xlabel('Total PnL %')
        ax4.set_title('Top 20 Performers')
        ax4.invert_yaxis()
        
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.output_dir}/winner_performance_distribution_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filename
    
    def create_winner_characteristics_chart(self):
        """Create chart showing characteristics of winners"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Winner Characteristics Analysis', fontsize=16)
        
        summary_df = self.data['Ticker_Summary']
        
        # Define winners as top 20% by total PnL
        pnl_threshold = summary_df['Total_PnL_%'].quantile(0.8)
        winners_df = summary_df[summary_df['Total_PnL_%'] > pnl_threshold]
        losers_df = summary_df[summary_df['Total_PnL_%'] < 0]
        
        # 1. Momentum Comparison
        ax1 = axes[0, 0]
        if 'Avg_Win_Momentum_%' in winners_df.columns:
            data_to_plot = [
                winners_df['Avg_Win_Momentum_%'].dropna(),
                losers_df['Avg_Win_Momentum_%'].dropna()
            ]
            ax1.boxplot(data_to_plot, labels=['Winners', 'Losers'])
            ax1.set_ylabel('Pre-Entry Momentum %')
            ax1.set_title('Momentum Comparison')
        
        # 2. Volume Surge Comparison
        ax2 = axes[0, 1]
        if 'Avg_Win_Volume_Surge' in winners_df.columns:
            winners_vol = winners_df['Avg_Win_Volume_Surge'].replace(0, np.nan).dropna()
            losers_vol = losers_df['Avg_Win_Volume_Surge'].replace(0, np.nan).dropna()
            
            if len(winners_vol) > 0 and len(losers_vol) > 0:
                ax2.boxplot([winners_vol, losers_vol], labels=['Winners', 'Losers'])
                ax2.set_ylabel('Volume Surge (x)')
                ax2.set_title('Volume Surge Comparison')
        
        # 3. Holding Period Comparison
        ax3 = axes[0, 2]
        ax3.boxplot([
            winners_df['Avg_Holding_Days'].dropna(),
            losers_df['Avg_Holding_Days'].dropna()
        ], labels=['Winners', 'Losers'])
        ax3.set_ylabel('Average Holding Days')
        ax3.set_title('Holding Period Comparison')
        
        # 4. Target Achievement Rates
        ax4 = axes[1, 0]
        target_data = pd.DataFrame({
            'Target 1': [winners_df['Target1_Hit_%'].mean(), losers_df['Target1_Hit_%'].mean()],
            'Target 2': [winners_df['Target2_Hit_%'].mean(), losers_df['Target2_Hit_%'].mean()],
            'Stop Loss': [winners_df['StopLoss_Hit_%'].mean(), losers_df['StopLoss_Hit_%'].mean()]
        }, index=['Winners', 'Losers'])
        
        target_data.plot(kind='bar', ax=ax4)
        ax4.set_ylabel('Hit Rate %')
        ax4.set_title('Target Achievement Rates')
        ax4.legend(loc='upper right')
        ax4.set_xticklabels(ax4.get_xticklabels(), rotation=0)
        
        # 5. Volatility Comparison
        ax5 = axes[1, 1]
        if 'Avg_Win_Volatility_%' in winners_df.columns:
            ax5.boxplot([
                winners_df['Avg_Win_Volatility_%'].dropna(),
                losers_df['Avg_Win_Volatility_%'].dropna()
            ], labels=['Winners', 'Losers'])
            ax5.set_ylabel('Volatility (ATR %)')
            ax5.set_title('Volatility Comparison')
        
        # 6. Win Rate Distribution
        ax6 = axes[1, 2]
        ax6.hist(winners_df['Win_Rate_%'], bins=20, alpha=0.7, label='Winners', color='green')
        ax6.hist(losers_df['Win_Rate_%'], bins=20, alpha=0.7, label='Losers', color='red')
        ax6.set_xlabel('Win Rate %')
        ax6.set_ylabel('Count')
        ax6.set_title('Win Rate Distribution')
        ax6.legend()
        
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.output_dir}/winner_characteristics_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filename
    
    def create_trade_pattern_analysis(self):
        """Analyze patterns in winning trades"""
        if 'Top_Winner_Trades' not in self.data:
            print("No detailed trade data available")
            return None
        
        trades_df = self.data['Top_Winner_Trades']
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Winning Trade Pattern Analysis', fontsize=16)
        
        # 1. Score vs PnL
        ax1 = axes[0, 0]
        score_groups = trades_df.groupby('Score')['PnL_%'].agg(['mean', 'count'])
        score_groups['mean'].plot(kind='bar', ax=ax1, color='skyblue')
        ax1.set_xlabel('Score')
        ax1.set_ylabel('Average PnL %')
        ax1.set_title('Average Returns by Score')
        
        # Add count labels
        for i, (idx, row) in enumerate(score_groups.iterrows()):
            ax1.text(i, row['mean'], f"n={row['count']}", ha='center', va='bottom')
        
        # 2. Outcome Distribution
        ax2 = axes[0, 1]
        outcome_counts = trades_df['Outcome'].value_counts()
        colors = {'target2': 'darkgreen', 'target1': 'lightgreen', 
                 'stoploss': 'red', 'open': 'yellow'}
        ax2.pie(outcome_counts.values, labels=outcome_counts.index, autopct='%1.1f%%',
                colors=[colors.get(x, 'gray') for x in outcome_counts.index])
        ax2.set_title('Trade Outcome Distribution')
        
        # 3. Holding Days vs PnL
        ax3 = axes[1, 0]
        winning_trades = trades_df[trades_df['PnL_%'] > 0]
        if len(winning_trades) > 0:
            ax3.scatter(winning_trades['Holding_Days'], winning_trades['PnL_%'], alpha=0.6)
            ax3.set_xlabel('Holding Days')
            ax3.set_ylabel('PnL %')
            ax3.set_title('Holding Period vs Returns (Winners Only)')
            
            # Add trend line
            z = np.polyfit(winning_trades['Holding_Days'], winning_trades['PnL_%'], 1)
            p = np.poly1d(z)
            ax3.plot(winning_trades['Holding_Days'], p(winning_trades['Holding_Days']), 
                    "r--", alpha=0.8, label=f'Trend: {z[0]:.2f}x + {z[1]:.2f}')
            ax3.legend()
        
        # 4. Maximum Favorable vs Adverse Excursion
        ax4 = axes[1, 1]
        ax4.scatter(trades_df['Max_Adverse_%'], trades_df['Max_Favorable_%'], 
                   c=trades_df['PnL_%'], cmap='RdYlGn', alpha=0.6, s=50)
        ax4.set_xlabel('Max Adverse Move %')
        ax4.set_ylabel('Max Favorable Move %')
        ax4.set_title('MAE vs MFE (color = final PnL%)')
        ax4.axhline(0, color='black', linestyle='-', alpha=0.3)
        ax4.axvline(0, color='black', linestyle='-', alpha=0.3)
        
        # Add colorbar
        scatter = ax4.scatter(trades_df['Max_Adverse_%'], trades_df['Max_Favorable_%'], 
                            c=trades_df['PnL_%'], cmap='RdYlGn', alpha=0.6, s=50)
        plt.colorbar(scatter, ax=ax4)
        
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.output_dir}/trade_pattern_analysis_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filename
    
    def create_correlation_heatmap(self):
        """Create correlation heatmap of various metrics"""
        summary_df = self.data['Ticker_Summary']
        
        # Select numeric columns for correlation
        corr_columns = [
            'Win_Rate_%', 'Total_PnL_%', 'Expectancy_%', 
            'Avg_Win_%', 'Avg_Loss_%', 'Target1_Hit_%', 
            'Target2_Hit_%', 'StopLoss_Hit_%', 'Avg_Holding_Days'
        ]
        
        # Add optional columns if they exist
        optional_cols = ['Avg_Win_Momentum_%', 'Avg_Win_Volume_Surge', 'Avg_Win_Volatility_%']
        for col in optional_cols:
            if col in summary_df.columns:
                corr_columns.append(col)
        
        # Calculate correlation
        corr_data = summary_df[corr_columns].corr()
        
        # Create heatmap
        plt.figure(figsize=(12, 10))
        sns.heatmap(corr_data, annot=True, cmap='coolwarm', center=0, 
                    square=True, linewidths=1, cbar_kws={"shrink": .8})
        plt.title('Performance Metrics Correlation Heatmap', fontsize=16)
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.output_dir}/correlation_heatmap_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filename
    
    def create_summary_dashboard(self):
        """Create a comprehensive summary dashboard"""
        # Create figure with GridSpec for flexible layout
        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)
        
        summary_df = self.data['Ticker_Summary']
        
        # Main title
        fig.suptitle('Winner Performance Analysis Dashboard', fontsize=20, y=0.98)
        
        # 1. Key Metrics (text box)
        ax_metrics = fig.add_subplot(gs[0, :2])
        ax_metrics.axis('off')
        
        total_tickers = len(summary_df)
        profitable_tickers = len(summary_df[summary_df['Total_PnL_%'] > 0])
        avg_pnl = summary_df['Total_PnL_%'].mean()
        best_ticker = summary_df.nlargest(1, 'Total_PnL_%')
        
        metrics_text = f"""Key Metrics:
        
Total Tickers Analyzed: {total_tickers}
Profitable Tickers: {profitable_tickers} ({profitable_tickers/total_tickers*100:.1f}%)
Average PnL: {avg_pnl:.2f}%
Best Performer: {best_ticker['Ticker'].values[0]} ({best_ticker['Total_PnL_%'].values[0]:.2f}%)
        
Top 20% Threshold: {summary_df['Total_PnL_%'].quantile(0.8):.2f}%"""
        
        ax_metrics.text(0.1, 0.5, metrics_text, fontsize=14, verticalalignment='center',
                       bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray"))
        
        # 2. PnL Distribution
        ax_dist = fig.add_subplot(gs[0, 2:])
        summary_df['Total_PnL_%'].hist(bins=50, ax=ax_dist, edgecolor='black', alpha=0.7)
        ax_dist.axvline(0, color='red', linestyle='--', label='Break-even')
        ax_dist.axvline(summary_df['Total_PnL_%'].quantile(0.8), color='green', 
                       linestyle='--', label='Top 20% threshold')
        ax_dist.set_xlabel('Total PnL %')
        ax_dist.set_ylabel('Number of Tickers')
        ax_dist.set_title('Returns Distribution')
        ax_dist.legend()
        
        # 3. Top 15 Winners
        ax_top = fig.add_subplot(gs[1:3, :2])
        top_15 = summary_df.nlargest(15, 'Total_PnL_%')
        bars = ax_top.barh(range(len(top_15)), top_15['Total_PnL_%'])
        
        # Color bars based on win rate
        colors = plt.cm.RdYlGn(top_15['Win_Rate_%'] / 100)
        for bar, color in zip(bars, colors):
            bar.set_color(color)
        
        ax_top.set_yticks(range(len(top_15)))
        ax_top.set_yticklabels(top_15['Ticker'])
        ax_top.set_xlabel('Total PnL %')
        ax_top.set_title('Top 15 Winners (color = win rate)')
        ax_top.invert_yaxis()
        
        # 4. Win Rate vs PnL Scatter
        ax_scatter = fig.add_subplot(gs[1:3, 2:])
        scatter = ax_scatter.scatter(summary_df['Win_Rate_%'], summary_df['Total_PnL_%'], 
                                   c=summary_df['Expectancy_%'], s=summary_df['Total_Trades']*10, 
                                   alpha=0.6, cmap='coolwarm')
        ax_scatter.axhline(0, color='black', linestyle='-', alpha=0.3)
        ax_scatter.axvline(50, color='black', linestyle='-', alpha=0.3)
        ax_scatter.set_xlabel('Win Rate %')
        ax_scatter.set_ylabel('Total PnL %')
        ax_scatter.set_title('Win Rate vs Returns (size=trades, color=expectancy)')
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax_scatter)
        cbar.set_label('Expectancy %')
        
        # 5. Success Rate Comparison
        ax_success = fig.add_subplot(gs[3, :2])
        
        # Define success categories
        high_return = summary_df[summary_df['Total_PnL_%'] > 50]
        moderate_return = summary_df[(summary_df['Total_PnL_%'] > 0) & (summary_df['Total_PnL_%'] <= 50)]
        negative_return = summary_df[summary_df['Total_PnL_%'] < 0]
        
        success_data = pd.DataFrame({
            'Target 1 Hit': [high_return['Target1_Hit_%'].mean(), 
                           moderate_return['Target1_Hit_%'].mean(),
                           negative_return['Target1_Hit_%'].mean()],
            'Target 2 Hit': [high_return['Target2_Hit_%'].mean(), 
                           moderate_return['Target2_Hit_%'].mean(),
                           negative_return['Target2_Hit_%'].mean()],
            'Stop Loss Hit': [high_return['StopLoss_Hit_%'].mean(), 
                            moderate_return['StopLoss_Hit_%'].mean(),
                            negative_return['StopLoss_Hit_%'].mean()]
        }, index=['High Return\n(>50%)', 'Moderate Return\n(0-50%)', 'Negative Return\n(<0%)'])
        
        success_data.plot(kind='bar', ax=ax_success)
        ax_success.set_ylabel('Hit Rate %')
        ax_success.set_title('Target Achievement by Return Category')
        ax_success.legend(loc='upper right')
        ax_success.set_xticklabels(ax_success.get_xticklabels(), rotation=0)
        
        # 6. Holding Period Analysis
        ax_hold = fig.add_subplot(gs[3, 2:])
        
        # Group by holding period ranges
        summary_df['Hold_Range'] = pd.cut(summary_df['Avg_Holding_Days'], 
                                         bins=[0, 3, 7, 14, 30, 100],
                                         labels=['0-3 days', '4-7 days', '8-14 days', 
                                                '15-30 days', '>30 days'])
        
        hold_analysis = summary_df.groupby('Hold_Range')['Total_PnL_%'].agg(['mean', 'count'])
        hold_analysis['mean'].plot(kind='bar', ax=ax_hold, color='skyblue')
        ax_hold.set_xlabel('Holding Period')
        ax_hold.set_ylabel('Average PnL %')
        ax_hold.set_title('Returns by Holding Period')
        ax_hold.set_xticklabels(ax_hold.get_xticklabels(), rotation=45)
        
        # Add count labels
        for i, (idx, row) in enumerate(hold_analysis.iterrows()):
            ax_hold.text(i, row['mean'], f"n={row['count']}", ha='center', va='bottom')
        
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.output_dir}/performance_dashboard_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filename
    
    def generate_all_visualizations(self):
        """Generate all visualization charts"""
        print("\nGenerating visualizations...")
        
        charts = []
        
        # 1. Performance Distribution
        try:
            chart = self.create_performance_distribution_chart()
            charts.append(chart)
            print(f"Created: {chart}")
        except Exception as e:
            print(f"Error creating performance distribution chart: {e}")
        
        # 2. Winner Characteristics
        try:
            chart = self.create_winner_characteristics_chart()
            charts.append(chart)
            print(f"Created: {chart}")
        except Exception as e:
            print(f"Error creating winner characteristics chart: {e}")
        
        # 3. Trade Pattern Analysis
        try:
            chart = self.create_trade_pattern_analysis()
            if chart:
                charts.append(chart)
                print(f"Created: {chart}")
        except Exception as e:
            print(f"Error creating trade pattern analysis: {e}")
        
        # 4. Correlation Heatmap
        try:
            chart = self.create_correlation_heatmap()
            charts.append(chart)
            print(f"Created: {chart}")
        except Exception as e:
            print(f"Error creating correlation heatmap: {e}")
        
        # 5. Summary Dashboard
        try:
            chart = self.create_summary_dashboard()
            charts.append(chart)
            print(f"Created: {chart}")
        except Exception as e:
            print(f"Error creating summary dashboard: {e}")
        
        print(f"\nTotal charts created: {len(charts)}")
        return charts


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize winner performance analysis results')
    parser.add_argument('--excel-file', help='Path to analysis Excel file (uses latest if not specified)')
    
    args = parser.parse_args()
    
    # Create visualizer
    visualizer = WinnerPerformanceVisualizer(args.excel_file)
    
    try:
        # Load data
        visualizer.load_data()
        
        # Generate all visualizations
        charts = visualizer.generate_all_visualizations()
        
        print("\nVisualization complete!")
        print("Generated charts:")
        for chart in charts:
            print(f"  - {chart}")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()