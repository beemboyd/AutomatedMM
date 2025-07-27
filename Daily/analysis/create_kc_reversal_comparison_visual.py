#!/usr/bin/env python3
"""
Create visual comparison of KC Limit vs Reversal strategies
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from datetime import datetime
import os

def create_comparison_visual():
    """Create comprehensive visual comparison"""
    
    # Data from analysis
    weeks = ['Week 1\n(Jun 28-Jul 4)', 'Week 2\n(Jul 5-11)', 
             'Week 3\n(Jul 12-18)', 'Week 4\n(Jul 19-25)']
    
    # Reversal performance
    reversal_long_wins = [31.9, 41.4, 36.8, 17.6]
    reversal_short_wins = [58.5, 66.9, 67.8, 77.4]
    
    # KC signals
    kc_long_signals = [0, 252, 287, 236]  # 0 for Week 1 (no data)
    kc_short_signals = [0, 83, 201, 309]
    
    # Enhanced market score
    enhanced_scores = [0.543, 0.156, 0.331, 0.005]
    confidence_levels = [86.1, 57.3, 74.6, 69.0]
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))
    
    # Define grid
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1, 1], hspace=0.3, wspace=0.3)
    
    # 1. Win Rate Comparison (Top Left)
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(weeks))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, reversal_long_wins, width, label='Long Win %', 
                    color='green', alpha=0.7)
    bars2 = ax1.bar(x + width/2, reversal_short_wins, width, label='Short Win %', 
                    color='red', alpha=0.7)
    
    ax1.set_ylabel('Win Rate %')
    ax1.set_title('Reversal Strategy Performance by Week', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(weeks)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.annotate(f'{height:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        fontsize=9)
    
    # 2. KC Signal Distribution (Top Right)
    ax2 = fig.add_subplot(gs[0, 1])
    
    # Skip Week 1 for KC signals
    kc_weeks = weeks[1:]
    kc_x = np.arange(len(kc_weeks))
    
    bars3 = ax2.bar(kc_x - width/2, kc_long_signals[1:], width, 
                    label='KC Long Signals', color='green', alpha=0.7)
    bars4 = ax2.bar(kc_x + width/2, kc_short_signals[1:], width, 
                    label='KC Short Signals', color='red', alpha=0.7)
    
    ax2.set_ylabel('Number of Signals')
    ax2.set_title('KC Limit Signal Distribution', fontsize=14, fontweight='bold')
    ax2.set_xticks(kc_x)
    ax2.set_xticklabels(kc_weeks)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Add value labels
    for bars in [bars3, bars4]:
        for bar in bars:
            height = bar.get_height()
            ax2.annotate(f'{int(height)}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        fontsize=9)
    
    # 3. Enhanced Market Score vs Actual Performance (Middle Left)
    ax3 = fig.add_subplot(gs[1, 0])
    
    # Create color map for scores
    colors = ['green' if score > 0.3 else 'red' if score < -0.3 else 'gray' 
              for score in enhanced_scores]
    
    bars5 = ax3.bar(x, enhanced_scores, color=colors, alpha=0.7)
    
    # Add horizontal lines for thresholds
    ax3.axhline(y=0.3, color='green', linestyle='--', alpha=0.5, label='Long Threshold')
    ax3.axhline(y=-0.3, color='red', linestyle='--', alpha=0.5, label='Short Threshold')
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    ax3.set_ylabel('Enhanced Score')
    ax3.set_title('Enhanced Market Score by Week', fontsize=14, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(weeks)
    ax3.set_ylim(-0.6, 0.8)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Add confidence labels
    for i, (bar, conf) in enumerate(zip(bars5, confidence_levels)):
        height = bar.get_height()
        y_pos = height + 0.02 if height > 0 else height - 0.05
        ax3.text(bar.get_x() + bar.get_width()/2, y_pos, 
                f'{conf:.0f}%', ha='center', va='bottom' if height > 0 else 'top',
                fontsize=8, style='italic')
    
    # 4. Accuracy Comparison (Middle Right)
    ax4 = fig.add_subplot(gs[1, 1])
    
    # Create accuracy visualization
    systems = ['Enhanced\nMarket Score', 'KC Signal\nBias']
    accuracy = [0, 33.3]  # 0% for enhanced score, 33.3% for KC (1/3 weeks)
    
    bars6 = ax4.bar(systems, accuracy, color=['orange', 'purple'], alpha=0.7)
    
    ax4.set_ylabel('Accuracy %')
    ax4.set_title('System Accuracy in Predicting Winners', fontsize=14, fontweight='bold')
    ax4.set_ylim(0, 100)
    ax4.grid(True, alpha=0.3)
    
    # Add value labels
    for bar in bars6:
        height = bar.get_height()
        ax4.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=12, fontweight='bold')
    
    # 5. Summary Table (Bottom)
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('tight')
    ax5.axis('off')
    
    # Create summary data
    summary_data = [
        ['Metric', 'Reversal Strategies', 'KC Limit Strategies', 'Enhanced Market Score'],
        ['4-Week Signal Count', 'N/A', '1,368 total (775 L, 593 S)', 'N/A'],
        ['Average Win Rate', 'Long: 31.9%, Short: 67.7%', 'Not measured directly', 'N/A'],
        ['Directional Bias', 'SHORT consistently better', 'LONG bias (56.6%)', 'LONG bias (avg 0.259)'],
        ['Prediction Accuracy', 'Ground truth', '33.3% (1/3 weeks)', '0% (0/4 weeks)'],
        ['Key Insight', 'Shorts dominated all weeks', 'Signal count ≠ performance', 'High confidence, wrong direction']
    ]
    
    # Create table
    table = ax5.table(cellText=summary_data, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(summary_data)):
        for j in range(4):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#E7E6E6')
    
    ax5.set_title('Comparative Analysis Summary', fontsize=14, fontweight='bold', pad=20)
    
    # Main title
    fig.suptitle('KC Limit Trending vs Reversal Strategies: 4-Week Analysis', 
                 fontsize=16, fontweight='bold')
    
    # Save the figure
    output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plt.savefig(os.path.join(output_dir, f'kc_vs_reversal_visual_{timestamp}.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    # Create a second figure for signal bias accuracy
    fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Signal Bias Match Chart
    match_data = {
        'Week 2': {'kc_bias': 'LONG', 'winner': 'SHORT', 'match': False},
        'Week 3': {'kc_bias': 'LONG', 'winner': 'SHORT', 'match': False},
        'Week 4': {'kc_bias': 'SHORT', 'winner': 'SHORT', 'match': True}
    }
    
    week_names = list(match_data.keys())
    x_pos = np.arange(len(week_names))
    
    # Create match visualization
    for i, week in enumerate(week_names):
        data = match_data[week]
        color = 'green' if data['match'] else 'red'
        marker = '✓' if data['match'] else '✗'
        
        ax1.bar(i, 1, color=color, alpha=0.3)
        ax1.text(i, 0.5, f"KC: {data['kc_bias']}\nWinner: {data['winner']}\n{marker}", 
                ha='center', va='center', fontsize=12, fontweight='bold')
    
    ax1.set_ylim(0, 1.2)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(week_names)
    ax1.set_title('KC Signal Bias vs Actual Winners', fontsize=14, fontweight='bold')
    ax1.set_yticks([])
    
    # Performance differential
    weeks_all = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    performance_diff = [
        reversal_short_wins[i] - reversal_long_wins[i] 
        for i in range(len(weeks_all))
    ]
    
    bars = ax2.bar(weeks_all, performance_diff, color='darkred', alpha=0.7)
    ax2.set_ylabel('Performance Differential (%)')
    ax2.set_title('Short vs Long Performance Gap', fontsize=14, fontweight='bold')
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax2.grid(True, alpha=0.3)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(f'+{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=10, fontweight='bold')
    
    fig2.suptitle('Signal Bias Accuracy & Performance Gaps', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    plt.savefig(os.path.join(output_dir, f'kc_signal_accuracy_{timestamp}.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Visualizations saved to {output_dir}")
    print(f"  - kc_vs_reversal_visual_{timestamp}.png")
    print(f"  - kc_signal_accuracy_{timestamp}.png")


if __name__ == "__main__":
    create_comparison_visual()