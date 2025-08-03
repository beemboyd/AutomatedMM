#!/usr/bin/env python3
"""
Market Breadth and Short Performance Analysis Summary
"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Create summary data
data = {
    'Date': ['July 22', 'July 25', 'July 28'],
    'Market_Breadth': [26.4, 13.3, 54.2],  # Bullish percent
    'Bearish_Percent': [73.6, 86.7, 45.8],
    'Success_Rate': [80.0, 66.7, 57.1],
    'Average_PnL': [2.91, 0.66, -0.86],
    'Total_Signals': [45, 39, 14],
    'Profitable_Shorts': [36, 26, 8],
    'Market_Regime': ['Low Breadth', 'Strong Downtrend', 'Choppy Bullish']
}

df = pd.DataFrame(data)

# Create figure with subplots
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
fig.suptitle('Market Breadth vs Short Reversal Performance Analysis', fontsize=16, fontweight='bold')

# 1. Market Breadth vs Success Rate
ax1.scatter(df['Market_Breadth'], df['Success_Rate'], s=200, c=['red', 'darkred', 'orange'], alpha=0.7)
for i, txt in enumerate(df['Date']):
    ax1.annotate(txt, (df['Market_Breadth'][i], df['Success_Rate'][i]), 
                xytext=(5, 5), textcoords='offset points', fontsize=10)
ax1.set_xlabel('Market Breadth (%)', fontsize=12)
ax1.set_ylabel('Short Success Rate (%)', fontsize=12)
ax1.set_title('Market Breadth vs Short Success Rate', fontsize=14)
ax1.grid(True, alpha=0.3)
ax1.axvline(x=30, color='red', linestyle='--', alpha=0.5, label='30% Breadth Line')
ax1.legend()

# 2. Market Breadth vs Average PnL
ax2.bar(df['Date'], df['Average_PnL'], color=['darkgreen', 'green', 'red'])
ax2.set_ylabel('Average PnL (%)', fontsize=12)
ax2.set_title('Average PnL by Date', fontsize=14)
ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
ax2.grid(True, axis='y', alpha=0.3)

# Add breadth labels on bars
for i, (date, breadth) in enumerate(zip(df['Date'], df['Market_Breadth'])):
    ax2.text(i, df['Average_PnL'][i] + 0.1, f'Breadth: {breadth}%', 
             ha='center', va='bottom', fontsize=9)

# 3. Success Rate Comparison
categories = df['Date'].tolist()
success_rates = df['Success_Rate'].tolist()
colors = ['#2E8B57', '#228B22', '#DC143C']  # Sea Green, Forest Green, Crimson

bars = ax3.bar(categories, success_rates, color=colors, alpha=0.8)
ax3.set_ylabel('Success Rate (%)', fontsize=12)
ax3.set_title('Short Success Rate by Market Condition', fontsize=14)
ax3.set_ylim(0, 100)

# Add value labels on bars
for i, (bar, rate) in enumerate(zip(bars, success_rates)):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
             f'{rate}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    # Add market breadth below
    ax3.text(bar.get_x() + bar.get_width()/2., 5,
             f'Breadth:\n{df["Market_Breadth"][i]}%', 
             ha='center', va='bottom', fontsize=9, color='white', fontweight='bold')

# 4. Performance Summary Table
ax4.axis('tight')
ax4.axis('off')

# Create summary table
table_data = []
table_data.append(['Metric', 'July 22\n(26.4% Breadth)', 'July 25\n(13.3% Breadth)', 'July 28\n(54.2% Breadth)'])
table_data.append(['Success Rate', '80.0%', '66.7%', '57.1%'])
table_data.append(['Avg PnL', '+2.91%', '+0.66%', '-0.86%'])
table_data.append(['Total Signals', '45', '39', '14'])
table_data.append(['Winners', '36', '26', '8'])
table_data.append(['Best Trade', 'CDSL +11.19%', 'SBICARD +9.13%', 'VAIBHAVGBL +4.06%'])

table = ax4.table(cellText=table_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.2, 1.8)

# Style the header row
for i in range(4):
    table[(0, i)].set_facecolor('#4472C4')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Color code the performance rows
for i in range(1, 4):
    if i == 1:  # July 22 column
        table[(2, i)].set_facecolor('#90EE90')  # Light green
    elif i == 2:  # July 25 column
        table[(2, i)].set_facecolor('#FFFACD')  # Light yellow
    else:  # July 28 column
        table[(2, i)].set_facecolor('#FFB6C1')  # Light red

ax4.set_title('Performance Summary Table', fontsize=14, pad=20)

plt.tight_layout()
plt.savefig('/Users/maverick/PycharmProjects/India-TS/Daily/analysis/performance_analysis/market_breadth_short_analysis.png', 
            dpi=300, bbox_inches='tight')
plt.show()

# Print insights
print("\n" + "="*70)
print("KEY INSIGHTS: Market Breadth and Short Performance")
print("="*70)
print("\n1. INVERSE RELATIONSHIP:")
print("   - Lower market breadth correlates with HIGHER short success rates")
print("   - July 22 (26.4% breadth): 80% success rate, +2.91% avg return")
print("   - July 25 (13.3% breadth): 66.7% success rate, +0.66% avg return")
print("   - July 28 (54.2% breadth): 57.1% success rate, -0.86% avg return")

print("\n2. OPTIMAL CONDITIONS FOR SHORTS:")
print("   - Market breadth below 30% shows exceptional short performance")
print("   - Best performance: July 22 with 26.4% breadth → 80% win rate")
print("   - Even extremely low breadth (13.3%) maintains profitability")

print("\n3. RISK/REWARD PROFILE:")
print("   - Low breadth (<30%): High success rate, positive returns")
print("   - Mixed breadth (>50%): Lower success rate, negative returns")
print("   - Sweet spot appears to be 20-30% market breadth")

print("\n4. TRADING IMPLICATIONS:")
print("   ✓ Monitor market breadth as a key filter for short strategies")
print("   ✓ Increase position sizing when breadth < 30%")
print("   ✓ Avoid shorts when breadth > 50% (choppy conditions)")
print("   ✓ Combine with regime analysis for optimal results")

print("\n" + "="*70)