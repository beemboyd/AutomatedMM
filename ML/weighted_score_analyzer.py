"""
Weighted Score Analysis - Testing if accuracy increases with cumulative weight

This script analyzes if combining frequency and score (e.g., 2 times 5/7 = weight of 10)
is a good predictor of winning stocks.

Usage:
    python weighted_score_analyzer.py [--days 7]
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/weighted_score_analyzer.log'),
        logging.StreamHandler()
    ]
)

class WeightedScoreAnalyzer:
    def __init__(self):
        self.results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       "Daily", "results")
        self.logger = logging.getLogger(__name__)
        
    def load_reports(self, days: int) -> pd.DataFrame:
        """Load Excel reports from the last N days"""
        self.logger.info(f"Loading reports from last {days} days...")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        files = [f for f in os.listdir(self.results_dir) if f.endswith('.xlsx')]
        files.sort()
        
        for file in files:
            try:
                # Extract date from filename
                date_str = file.split('_')[2]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if file_date < cutoff_date:
                    continue
                    
                df = pd.read_excel(os.path.join(self.results_dir, file))
                df['scan_date'] = file_date
                all_data.append(df)
                
            except Exception as e:
                self.logger.debug(f"Skipping {file}: {e}")
                
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Loaded {len(combined_df)} entries from {len(all_data)} files")
            return combined_df
        else:
            self.logger.warning("No data found")
            return pd.DataFrame()
    
    def calculate_weighted_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate weighted scores for each ticker"""
        self.logger.info("Calculating weighted scores...")
        
        # Group by ticker and calculate metrics
        ticker_stats = []
        
        for ticker in df['Ticker'].unique():
            ticker_df = df[df['Ticker'] == ticker]
            
            # Calculate frequency (number of appearances)
            frequency = len(ticker_df)
            
            # Calculate scores and weights
            scores = ticker_df['Score'].values
            weighted_score = sum(scores)  # Sum of all scores
            avg_score = np.mean(scores)
            
            # Count score distribution
            score_counts = ticker_df['Score'].value_counts().to_dict()
            
            # For now, we'll set win rate and PnL to 0 since we don't have trade outcomes
            # These would need to be calculated from actual trade results
            win_rate = 0
            avg_pnl = 0
            total_pnl = 0
            
            ticker_stats.append({
                'Ticker': ticker,
                'Frequency': frequency,
                'Weighted_Score': weighted_score,
                'Avg_Score': avg_score,
                'Win_Rate': win_rate,
                'Avg_PnL': avg_pnl,
                'Total_PnL': total_pnl,
                'Score_7/7': score_counts.get(7, 0),
                'Score_6/7': score_counts.get(6, 0),
                'Score_5/7': score_counts.get(5, 0),
                'Score_4/7': score_counts.get(4, 0),
                'Score_Distribution': score_counts
            })
        
        return pd.DataFrame(ticker_stats)
    
    def analyze_weight_correlation(self, stats_df: pd.DataFrame) -> dict:
        """Analyze correlation between weighted scores and performance"""
        self.logger.info("Analyzing weight correlation...")
        
        # Create weight bins
        stats_df['Weight_Bin'] = pd.cut(stats_df['Weighted_Score'], 
                                       bins=[0, 10, 20, 30, 40, 50, 100],
                                       labels=['0-10', '11-20', '21-30', '31-40', '41-50', '50+'])
        
        # Analyze by weight bins
        weight_analysis = stats_df.groupby('Weight_Bin').agg({
            'Win_Rate': ['mean', 'std', 'count'],
            'Avg_PnL': ['mean', 'std'],
            'Total_PnL': ['mean', 'sum'],
            'Frequency': 'mean'
        }).round(2)
        
        # Calculate correlations
        correlations = {
            'Weight_vs_WinRate': stats_df['Weighted_Score'].corr(stats_df['Win_Rate']),
            'Weight_vs_AvgPnL': stats_df['Weighted_Score'].corr(stats_df['Avg_PnL']),
            'Weight_vs_TotalPnL': stats_df['Weighted_Score'].corr(stats_df['Total_PnL']),
            'Frequency_vs_WinRate': stats_df['Frequency'].corr(stats_df['Win_Rate']),
            'AvgScore_vs_WinRate': stats_df['Avg_Score'].corr(stats_df['Win_Rate'])
        }
        
        return {
            'weight_bins': weight_analysis,
            'correlations': correlations,
            'stats_df': stats_df
        }
    
    def create_visualizations(self, analysis: dict, output_prefix: str):
        """Create visualization charts"""
        self.logger.info("Creating visualizations...")
        
        stats_df = analysis['stats_df']
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Weighted Score Analysis - Does Higher Weight Mean Better Performance?', fontsize=16)
        
        # 1. Scatter plot: Weighted Score vs Win Rate
        ax1 = axes[0, 0]
        scatter = ax1.scatter(stats_df['Weighted_Score'], stats_df['Win_Rate'], 
                            c=stats_df['Total_PnL'], cmap='RdYlGn', s=100, alpha=0.6)
        ax1.set_xlabel('Weighted Score (Sum of Scores)')
        ax1.set_ylabel('Win Rate (%)')
        ax1.set_title('Weighted Score vs Win Rate (colored by Total PnL)')
        plt.colorbar(scatter, ax=ax1, label='Total PnL (%)')
        
        # Add trend line
        z = np.polyfit(stats_df['Weighted_Score'], stats_df['Win_Rate'], 1)
        p = np.poly1d(z)
        ax1.plot(stats_df['Weighted_Score'], p(stats_df['Weighted_Score']), "r--", alpha=0.8)
        
        # 2. Box plot: Win Rate by Weight Bins
        ax2 = axes[0, 1]
        stats_df.boxplot(column='Win_Rate', by='Weight_Bin', ax=ax2)
        ax2.set_xlabel('Weight Score Bins')
        ax2.set_ylabel('Win Rate (%)')
        ax2.set_title('Win Rate Distribution by Weight Bins')
        
        # 3. Bar plot: Average metrics by weight bins
        ax3 = axes[1, 0]
        weight_bins = analysis['weight_bins']
        x = range(len(weight_bins.index))
        width = 0.35
        
        ax3.bar([i - width/2 for i in x], weight_bins[('Win_Rate', 'mean')], 
                width, label='Avg Win Rate', color='green', alpha=0.7)
        ax3.bar([i + width/2 for i in x], weight_bins[('Avg_PnL', 'mean')], 
                width, label='Avg PnL', color='blue', alpha=0.7)
        
        ax3.set_xlabel('Weight Score Bins')
        ax3.set_ylabel('Percentage')
        ax3.set_title('Average Performance by Weight Bins')
        ax3.set_xticks(x)
        ax3.set_xticklabels(weight_bins.index, rotation=45)
        ax3.legend()
        
        # 4. Correlation heatmap
        ax4 = axes[1, 1]
        corr_data = pd.DataFrame({
            'Weight Score': [1.0, analysis['correlations']['Weight_vs_WinRate'], 
                           analysis['correlations']['Weight_vs_AvgPnL']],
            'Win Rate': [analysis['correlations']['Weight_vs_WinRate'], 1.0, 0],
            'Avg PnL': [analysis['correlations']['Weight_vs_AvgPnL'], 0, 1.0]
        }, index=['Weight Score', 'Win Rate', 'Avg PnL'])
        
        sns.heatmap(corr_data, annot=True, cmap='coolwarm', center=0, 
                   vmin=-1, vmax=1, ax=ax4, fmt='.3f')
        ax4.set_title('Correlation Matrix')
        
        plt.tight_layout()
        plt.savefig(f'{output_prefix}_visualizations.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Create additional detailed chart
        fig2, ax = plt.subplots(figsize=(12, 8))
        
        # Bubble chart: Frequency vs Avg Score, sized by weight, colored by win rate
        bubble = ax.scatter(stats_df['Frequency'], stats_df['Avg_Score'], 
                          s=stats_df['Weighted_Score']*10, 
                          c=stats_df['Win_Rate'], 
                          cmap='RdYlGn', alpha=0.6, edgecolors='black', linewidth=1)
        
        ax.set_xlabel('Frequency (Number of Appearances)')
        ax.set_ylabel('Average Score')
        ax.set_title('Frequency vs Average Score\n(Bubble size = Weighted Score, Color = Win Rate)')
        
        # Add colorbar
        cbar = plt.colorbar(bubble, ax=ax)
        cbar.set_label('Win Rate (%)')
        
        # Add annotations for top performers
        top_performers = stats_df.nlargest(10, 'Weighted_Score')
        for _, row in top_performers.iterrows():
            ax.annotate(row['Ticker'], 
                       (row['Frequency'], row['Avg_Score']),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=8, alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(f'{output_prefix}_bubble_chart.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_report(self, analysis: dict, output_file: str):
        """Generate detailed text report"""
        self.logger.info("Generating report...")
        
        with open(output_file, 'w') as f:
            f.write("WEIGHTED SCORE ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Analysis Date: {datetime.now()}\n\n")
            
            # Correlation findings
            f.write("CORRELATION ANALYSIS\n")
            f.write("-" * 40 + "\n")
            corr = analysis['correlations']
            f.write(f"Weight Score vs Win Rate:    {corr['Weight_vs_WinRate']:.3f}\n")
            f.write(f"Weight Score vs Avg PnL:     {corr['Weight_vs_AvgPnL']:.3f}\n")
            f.write(f"Weight Score vs Total PnL:   {corr['Weight_vs_TotalPnL']:.3f}\n")
            f.write(f"Frequency vs Win Rate:       {corr['Frequency_vs_WinRate']:.3f}\n")
            f.write(f"Avg Score vs Win Rate:       {corr['AvgScore_vs_WinRate']:.3f}\n\n")
            
            # Interpretation
            f.write("INTERPRETATION\n")
            f.write("-" * 40 + "\n")
            
            if corr['Weight_vs_WinRate'] > 0.3:
                f.write("✓ Strong positive correlation between Weight Score and Win Rate\n")
                f.write("  → Higher weighted scores DO indicate better winning probability\n\n")
            elif corr['Weight_vs_WinRate'] > 0.1:
                f.write("~ Moderate positive correlation between Weight Score and Win Rate\n")
                f.write("  → Some relationship exists but not strongly predictive\n\n")
            else:
                f.write("✗ Weak/No correlation between Weight Score and Win Rate\n")
                f.write("  → Weight scores alone are not good predictors of success\n\n")
            
            # Performance by weight bins
            f.write("PERFORMANCE BY WEIGHT BINS\n")
            f.write("-" * 40 + "\n")
            weight_bins = analysis['weight_bins']
            f.write(f"{'Weight Bin':<12} {'Avg Win%':<10} {'Avg PnL%':<10} {'Count':<8}\n")
            f.write("-" * 40 + "\n")
            
            for idx in weight_bins.index:
                win_rate = weight_bins.loc[idx, ('Win_Rate', 'mean')]
                avg_pnl = weight_bins.loc[idx, ('Avg_PnL', 'mean')]
                count = weight_bins.loc[idx, ('Win_Rate', 'count')]
                f.write(f"{idx:<12} {win_rate:<10.1f} {avg_pnl:<10.2f} {count:<8.0f}\n")
            
            # Top performers by weight
            f.write("\n\nTOP 20 TICKERS BY WEIGHTED SCORE\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<5} {'Ticker':<12} {'Weight':<8} {'Freq':<6} {'Avg Score':<10} {'Win%':<8} {'Avg PnL':<10}\n")
            f.write("-" * 80 + "\n")
            
            stats_df = analysis['stats_df']
            top_weighted = stats_df.nlargest(20, 'Weighted_Score')
            
            for i, (_, row) in enumerate(top_weighted.iterrows(), 1):
                f.write(f"{i:<5} {row['Ticker']:<12} {row['Weighted_Score']:<8.0f} "
                       f"{row['Frequency']:<6.0f} {row['Avg_Score']:<10.1f} "
                       f"{row['Win_Rate']:<8.1f} {row['Avg_PnL']:<10.2f}\n")
            
            # Best performers with high weight
            f.write("\n\nBEST PERFORMERS WITH HIGH WEIGHT (Weight > 20, Win% > 70%)\n")
            f.write("-" * 80 + "\n")
            
            high_weight_winners = stats_df[(stats_df['Weighted_Score'] > 20) & 
                                          (stats_df['Win_Rate'] > 70)].sort_values('Total_PnL', ascending=False)
            
            if len(high_weight_winners) > 0:
                f.write(f"{'Ticker':<12} {'Weight':<8} {'Win%':<8} {'Total PnL':<12} {'Frequency':<10}\n")
                f.write("-" * 50 + "\n")
                
                for _, row in high_weight_winners.head(15).iterrows():
                    f.write(f"{row['Ticker']:<12} {row['Weighted_Score']:<8.0f} "
                           f"{row['Win_Rate']:<8.1f} {row['Total_PnL']:<12.2f} "
                           f"{row['Frequency']:<10.0f}\n")
            else:
                f.write("No tickers found with Weight > 20 and Win% > 70%\n")
            
            # Recommendations
            f.write("\n\nRECOMMENDATIONS\n")
            f.write("-" * 40 + "\n")
            
            if corr['Weight_vs_WinRate'] > 0.3 and corr['Weight_vs_TotalPnL'] > 0.3:
                f.write("1. ✓ Weighted Score IS a good predictor - use it for filtering\n")
                f.write("2. Focus on tickers with weight > 30 for best results\n")
                f.write("3. Combine with other filters for optimal selection\n")
            else:
                f.write("1. ⚠ Weighted Score alone is not sufficient for prediction\n")
                f.write("2. Consider additional factors beyond frequency and score\n")
                f.write("3. Look at recent performance trends and market conditions\n")
    
    def run(self, days: int = 7):
        """Run the complete analysis"""
        # Load data
        df = self.load_reports(days)
        if df.empty:
            self.logger.error("No data to analyze")
            return None
        
        # Calculate weighted scores
        stats_df = self.calculate_weighted_scores(df)
        
        # Analyze correlations
        analysis = self.analyze_weight_correlation(stats_df)
        
        # Generate outputs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_prefix = f'ML/results/weighted_score_analysis_{timestamp}'
        
        # Create visualizations
        self.create_visualizations(analysis, output_prefix)
        
        # Generate report
        report_file = f'{output_prefix}.txt'
        self.generate_report(analysis, report_file)
        
        # Save detailed data
        excel_file = f'{output_prefix}.xlsx'
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            stats_df.to_excel(writer, sheet_name='Weighted_Scores', index=False)
            analysis['weight_bins'].to_excel(writer, sheet_name='Weight_Bins')
            
            # Add correlation summary
            corr_df = pd.DataFrame([analysis['correlations']], index=['Correlation'])
            corr_df.to_excel(writer, sheet_name='Correlations')
        
        self.logger.info(f"Analysis complete! Files saved:")
        self.logger.info(f"- Report: {report_file}")
        self.logger.info(f"- Excel: {excel_file}")
        self.logger.info(f"- Charts: {output_prefix}_*.png")
        
        return report_file, excel_file

def main():
    parser = argparse.ArgumentParser(description='Analyze weighted score correlation with performance')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')
    
    args = parser.parse_args()
    
    # Create directories
    os.makedirs('ML/results', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Run analysis
    analyzer = WeightedScoreAnalyzer()
    results = analyzer.run(days=args.days)
    
    if results:
        report_file, excel_file = results
        print(f"\nAnalysis complete!")
        print(f"Report: {report_file}")
        print(f"Excel: {excel_file}")
        
        # Display summary
        with open(report_file, 'r') as f:
            lines = f.readlines()
            print("\n" + "".join(lines[:50]))
            print("... (see full report for details)")

if __name__ == "__main__":
    main()