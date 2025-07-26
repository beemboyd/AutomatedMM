#!/usr/bin/env python
"""
Weekly Performance Visualizer
Creates charts and visualizations for Long Reversal performance analysis
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json
import os

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class WeeklyPerformanceVisualizer:
    def __init__(self, report_path=None):
        """Initialize visualizer with report data"""
        if report_path is None:
            report_path = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports/latest_4week_analysis.json'
        
        with open(report_path, 'r') as f:
            self.report = json.load(f)
            
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
    def create_all_visualizations(self):
        """Create all visualization charts"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create figure with subplots
        fig = plt.figure(figsize=(20, 16))
        
        # 1. Weekly Win Rate Chart
        ax1 = plt.subplot(3, 3, 1)
        self.plot_weekly_win_rates(ax1)
        
        # 2. Weekly P&L Chart
        ax2 = plt.subplot(3, 3, 2)
        self.plot_weekly_pnl(ax2)
        
        # 3. Regime Performance
        ax3 = plt.subplot(3, 3, 3)
        self.plot_regime_performance(ax3)
        
        # 4. Daily Win Rate Trend
        ax4 = plt.subplot(3, 3, 4)
        self.plot_daily_win_rate_trend(ax4)
        
        # 5. P&L Distribution
        ax5 = plt.subplot(3, 3, 5)
        self.plot_pnl_distribution(ax5)
        
        # 6. Cumulative P&L
        ax6 = plt.subplot(3, 3, 6)
        self.plot_cumulative_pnl(ax6)
        
        # 7. Win/Loss Analysis
        ax7 = plt.subplot(3, 3, 7)
        self.plot_win_loss_analysis(ax7)
        
        # 8. Regime vs Confidence
        ax8 = plt.subplot(3, 3, 8)
        self.plot_regime_confidence_scatter(ax8)
        
        # 9. Summary Stats
        ax9 = plt.subplot(3, 3, 9)
        self.plot_summary_stats(ax9)
        
        plt.suptitle('Long Reversal 4-Week Performance Analysis', fontsize=16, y=0.995)
        plt.tight_layout()
        
        # Save figure
        chart_file = os.path.join(self.output_dir, f'performance_charts_{timestamp}.png')
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        
        # Save latest
        latest_chart = os.path.join(self.output_dir, 'latest_performance_charts.png')
        plt.savefig(latest_chart, dpi=150, bbox_inches='tight')
        
        plt.close()
        
        print(f"Charts saved to: {chart_file}")
        
    def plot_weekly_win_rates(self, ax):
        """Plot weekly win rates"""
        weeks = list(self.report['weekly_breakdown'].keys())
        win_rates = [self.report['weekly_breakdown'][w]['win_rate'] for w in weeks]
        
        bars = ax.bar(weeks, win_rates, color=['green' if wr >= 50 else 'red' for wr in win_rates])
        ax.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        ax.set_title('Weekly Win Rates')
        ax.set_ylabel('Win Rate (%)')
        ax.set_ylim(0, 100)
        
        # Add value labels
        for bar, rate in zip(bars, win_rates):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{rate:.1f}%', ha='center', va='bottom')
    
    def plot_weekly_pnl(self, ax):
        """Plot weekly P&L"""
        weeks = list(self.report['weekly_breakdown'].keys())
        pnls = [self.report['weekly_breakdown'][w]['total_pnl'] for w in weeks]
        
        bars = ax.bar(weeks, pnls, color=['green' if pnl >= 0 else 'red' for pnl in pnls])
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax.set_title('Weekly P&L')
        ax.set_ylabel('P&L (₹)')
        
        # Format y-axis
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1000:.0f}K'))
    
    def plot_regime_performance(self, ax):
        """Plot performance by regime"""
        regimes = list(self.report['regime_correlation'].keys())
        win_rates = [self.report['regime_correlation'][r]['win_rate'] for r in regimes]
        
        # Sort by win rate
        sorted_data = sorted(zip(regimes, win_rates), key=lambda x: x[1], reverse=True)
        regimes, win_rates = zip(*sorted_data)
        
        bars = ax.barh(regimes, win_rates, color='skyblue')
        ax.axvline(x=50, color='black', linestyle='--', alpha=0.5)
        ax.set_title('Win Rate by Market Regime')
        ax.set_xlabel('Win Rate (%)')
        ax.set_xlim(0, 100)
    
    def plot_daily_win_rate_trend(self, ax):
        """Plot daily win rate trend"""
        if 'detailed_trades' not in self.report:
            ax.text(0.5, 0.5, 'No daily data available', ha='center', va='center', transform=ax.transAxes)
            return
            
        daily_data = self.report['detailed_trades']
        dates = [d['date'] for d in daily_data]
        win_rates = [d['win_rate'] for d in daily_data]
        
        # Convert dates to datetime for better plotting
        dates = pd.to_datetime(dates)
        
        ax.plot(dates, win_rates, marker='o', linewidth=2, markersize=6)
        ax.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        ax.set_title('Daily Win Rate Trend')
        ax.set_ylabel('Win Rate (%)')
        ax.set_ylim(0, 100)
        ax.tick_params(axis='x', rotation=45)
        
        # Add 7-day moving average
        if len(win_rates) >= 7:
            ma7 = pd.Series(win_rates).rolling(7).mean()
            ax.plot(dates, ma7, color='red', alpha=0.7, label='7-day MA')
            ax.legend()
    
    def plot_pnl_distribution(self, ax):
        """Plot P&L distribution histogram"""
        # Collect all trade P&Ls
        all_pnls = []
        if 'detailed_trades' in self.report:
            for day_result in self.report['detailed_trades']:
                if 'trades' in day_result:
                    all_pnls.extend([t['pnl_percentage'] for t in day_result['trades']])
        
        if all_pnls:
            ax.hist(all_pnls, bins=30, color='blue', alpha=0.7, edgecolor='black')
            ax.axvline(x=0, color='red', linestyle='--', alpha=0.7)
            ax.axvline(x=np.mean(all_pnls), color='green', linestyle='-', alpha=0.7, label=f'Mean: {np.mean(all_pnls):.1f}%')
            ax.set_title('P&L Distribution')
            ax.set_xlabel('P&L (%)')
            ax.set_ylabel('Frequency')
            ax.legend()
        else:
            ax.text(0.5, 0.5, 'No trade data available', ha='center', va='center', transform=ax.transAxes)
    
    def plot_cumulative_pnl(self, ax):
        """Plot cumulative P&L over time"""
        if 'detailed_trades' not in self.report:
            ax.text(0.5, 0.5, 'No daily data available', ha='center', va='center', transform=ax.transAxes)
            return
            
        daily_data = self.report['detailed_trades']
        dates = pd.to_datetime([d['date'] for d in daily_data])
        daily_pnls = [d['total_pnl'] for d in daily_data]
        
        # Calculate cumulative P&L
        cum_pnl = np.cumsum(daily_pnls)
        
        ax.plot(dates, cum_pnl, linewidth=3, color='darkgreen')
        ax.fill_between(dates, 0, cum_pnl, alpha=0.3, color='green', where=(cum_pnl >= 0))
        ax.fill_between(dates, 0, cum_pnl, alpha=0.3, color='red', where=(cum_pnl < 0))
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax.set_title('Cumulative P&L')
        ax.set_ylabel('Cumulative P&L (₹)')
        ax.tick_params(axis='x', rotation=45)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1000:.0f}K'))
    
    def plot_win_loss_analysis(self, ax):
        """Plot win/loss analysis"""
        summary = self.report['summary']
        
        # Create pie chart
        sizes = [summary.get('total_winners', 0), summary.get('total_losers', 0)]
        labels = ['Winners', 'Losers']
        colors = ['green', 'red']
        
        if sum(sizes) > 0:
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                               startangle=90, textprops={'fontsize': 10})
            ax.set_title(f"Win/Loss Distribution\n(Total Trades: {sum(sizes)})")
        else:
            ax.text(0.5, 0.5, 'No trade data available', ha='center', va='center', transform=ax.transAxes)
    
    def plot_regime_confidence_scatter(self, ax):
        """Plot regime confidence vs win rate scatter"""
        if 'detailed_trades' not in self.report:
            ax.text(0.5, 0.5, 'No daily data available', ha='center', va='center', transform=ax.transAxes)
            return
            
        daily_data = self.report['detailed_trades']
        
        # Extract data
        confidences = []
        win_rates = []
        regimes = []
        
        for day in daily_data:
            if day.get('regime_confidence', 0) > 0 and day.get('total_trades', 0) > 0:
                confidences.append(day['regime_confidence'])
                win_rates.append(day['win_rate'])
                regimes.append(day.get('regime', 'unknown'))
        
        if confidences:
            # Create scatter plot
            scatter = ax.scatter(confidences, win_rates, c=range(len(confidences)), 
                               cmap='viridis', s=100, alpha=0.6)
            
            # Add trend line
            z = np.polyfit(confidences, win_rates, 1)
            p = np.poly1d(z)
            ax.plot(np.linspace(min(confidences), max(confidences), 100),
                   p(np.linspace(min(confidences), max(confidences), 100)),
                   "r--", alpha=0.8)
            
            ax.set_xlabel('Regime Confidence')
            ax.set_ylabel('Win Rate (%)')
            ax.set_title('Regime Confidence vs Win Rate')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 100)
        else:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax.transAxes)
    
    def plot_summary_stats(self, ax):
        """Plot summary statistics table"""
        ax.axis('off')
        
        summary = self.report['summary']
        
        # Create summary text
        stats_text = f"""
4-WEEK PERFORMANCE SUMMARY

Total Scans: {summary.get('total_scans', 0)}
Total Trades: {summary.get('total_trades', 0)}

Overall Win Rate: {summary.get('overall_win_rate', 0):.1f}%
Total P&L: ₹{summary.get('total_pnl', 0):,.0f}

Average Win: {summary.get('avg_win_percentage', 0):.2f}%
Average Loss: {summary.get('avg_loss_percentage', 0):.2f}%

Best Day: {summary.get('best_day', 'N/A')}
Worst Day: {summary.get('worst_day', 'N/A')}
        """
        
        ax.text(0.1, 0.9, stats_text, transform=ax.transAxes, fontsize=12,
               verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

def main():
    """Main function"""
    visualizer = WeeklyPerformanceVisualizer()
    visualizer.create_all_visualizations()
    print("Visualizations created successfully!")

if __name__ == "__main__":
    main()