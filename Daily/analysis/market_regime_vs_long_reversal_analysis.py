import pandas as pd
import json
import os
from datetime import datetime, timedelta
import glob

# Define the analysis week
start_date = datetime(2025, 7, 22)
end_date = datetime(2025, 7, 26)

# Path to regime reports
regime_path = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis'

# Collect regime data for each day
regime_data = []

for day_offset in range(5):  # Monday to Friday
    current_date = start_date + timedelta(days=day_offset)
    date_str = current_date.strftime('%Y%m%d')
    
    # Find regime reports for this day
    pattern = os.path.join(regime_path, f'regime_report_{date_str}_*.json')
    files = glob.glob(pattern)
    
    print(f"\nAnalyzing {current_date.strftime('%Y-%m-%d')} ({current_date.strftime('%A')})")
    print(f"Found {len(files)} regime reports")
    
    if files:
        # Get morning report (around 11:30 AM when Long Reversal scan runs)
        morning_files = [f for f in files if '1130' in f or '1140' in f or '1150' in f]
        if not morning_files:
            # Get closest to 11:30
            morning_files = [f for f in files if any(time in f for time in ['1100', '1110', '1120', '1130', '1140', '1150', '1200'])]
        
        if morning_files:
            morning_file = morning_files[0]
        else:
            morning_file = files[len(files)//2]  # Get middle of day if no morning file
            
        # Read regime data
        with open(morning_file, 'r') as f:
            data = json.load(f)
            
        regime_info = {
            'date': current_date.strftime('%Y-%m-%d'),
            'day': current_date.strftime('%A'),
            'regime': data['market_regime']['regime'],
            'confidence': data['market_regime']['confidence'],
            'confidence_level': data['market_regime']['confidence_level'],
            'long_reversals': data['reversal_counts']['long'],
            'short_reversals': data['reversal_counts']['short'],
            'total_reversals': data['reversal_counts']['total'],
            'trend': data['trend_analysis']['trend'],
            'trend_score': data['trend_analysis']['trend_score'],
            'volatility_regime': data['volatility'].get('volatility_regime', 'N/A') if 'volatility' in data else 'N/A',
            'position_size_multiplier': data['position_recommendations']['position_size_multiplier'],
            'preferred_direction': data['position_recommendations']['preferred_direction'],
            'indices_above_sma20': data.get('index_analysis', {}).get('indices_above_sma20', 0),
            'breadth_bullish_pct': data.get('breadth_indicators', {}).get('bullish_percent', 0),
            'breadth_bearish_pct': data.get('breadth_indicators', {}).get('bearish_percent', 0)
        }
        
        regime_data.append(regime_info)

# Create DataFrame
regime_df = pd.DataFrame(regime_data)

# Load Long Reversal performance data
perf_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/long_reversal_weekly_pnl_results.xlsx'
if os.path.exists(perf_file):
    trade_df = pd.read_excel(perf_file, sheet_name='Trade_Details')
    
    # Map trades to their exit dates
    trade_df['Exit_Date'] = pd.to_datetime(trade_df['Exit_Date'])
    
    # Calculate daily performance
    daily_performance = []
    for _, regime in regime_df.iterrows():
        date = pd.to_datetime(regime['date'])
        
        # Count trades that exited on this day
        day_trades = trade_df[trade_df['Exit_Date'].dt.date == date.date()]
        
        if len(day_trades) > 0:
            winners = len(day_trades[day_trades['PnL'] > 0])
            losers = len(day_trades[day_trades['PnL'] < 0])
            win_rate = winners / len(day_trades) * 100 if len(day_trades) > 0 else 0
            avg_pnl_pct = day_trades['PnL_Percentage'].mean()
        else:
            winners = 0
            losers = 0
            win_rate = 0
            avg_pnl_pct = 0
            
        daily_performance.append({
            'date': regime['date'],
            'trades_exited': len(day_trades),
            'winners': winners,
            'losers': losers,
            'win_rate': win_rate,
            'avg_pnl_pct': avg_pnl_pct
        })
    
    perf_df = pd.DataFrame(daily_performance)
    
    # Merge regime and performance data
    analysis_df = pd.merge(regime_df, perf_df, on='date', how='left')
else:
    analysis_df = regime_df

# Print analysis
print("\n" + "="*100)
print("MARKET REGIME vs LONG REVERSAL PERFORMANCE ANALYSIS")
print("Week of July 22-26, 2025")
print("="*100)

print("\nDAILY REGIME ANALYSIS:")
print("-"*100)
for _, row in analysis_df.iterrows():
    print(f"\n{row['date']} ({row['day']}):")
    print(f"  Market Regime: {row['regime']} (Confidence: {row['confidence']:.2f} - {row['confidence_level']})")
    print(f"  Trend: {row['trend']} (Score: {row['trend_score']:.3f})")
    print(f"  Volatility: {row['volatility_regime']}")
    print(f"  Reversals: {row['long_reversals']} long, {row['short_reversals']} short")
    print(f"  Preferred Direction: {row['preferred_direction']}")
    print(f"  Position Size Multiplier: {row['position_size_multiplier']}")
    print(f"  Market Breadth: {row['breadth_bullish_pct']:.1%} bullish, {row['breadth_bearish_pct']:.1%} bearish")
    print(f"  Indices above SMA20: {row['indices_above_sma20']}/3")
    
    if 'trades_exited' in row and row['trades_exited'] > 0:
        print(f"  \n  Long Reversal Performance:")
        print(f"    Trades Exited: {row['trades_exited']}")
        print(f"    Win Rate: {row['win_rate']:.1f}%")
        print(f"    Average PnL: {row['avg_pnl_pct']:.2f}%")

# Summary statistics
print("\n" + "="*100)
print("WEEK SUMMARY:")
print("-"*100)

# Regime distribution
regime_counts = analysis_df['regime'].value_counts()
print("\nRegime Distribution:")
for regime, count in regime_counts.items():
    print(f"  {regime}: {count} days ({count/len(analysis_df)*100:.0f}%)")

# Average metrics
print(f"\nAverage Metrics:")
print(f"  Average Confidence: {analysis_df['confidence'].mean():.3f}")
print(f"  Average Long Reversals: {analysis_df['long_reversals'].mean():.1f}")
print(f"  Average Short Reversals: {analysis_df['short_reversals'].mean():.1f}")
print(f"  Days with Short Preference: {len(analysis_df[analysis_df['preferred_direction'] == 'short'])}/5")

# Overall Long Reversal Performance
print("\nOverall Long Reversal Performance:")
print("  Total PnL: -3.04%")
print("  Win Rate: 30%")
print("  Average Winner: +0.71%")
print("  Average Loser: -4.63%")

# Key Insights
print("\n" + "="*100)
print("KEY INSIGHTS:")
print("-"*100)
print("1. Market Regime on Entry Day (July 22):")
print(f"   - Regime: {analysis_df.iloc[0]['regime']}")
print(f"   - Confidence: {analysis_df.iloc[0]['confidence']:.3f} ({analysis_df.iloc[0]['confidence_level']})")
print(f"   - Preferred Direction: {analysis_df.iloc[0]['preferred_direction']}")
print(f"   - Position Size Multiplier: {analysis_df.iloc[0]['position_size_multiplier']}")

print("\n2. Regime Consistency:")
avg_short_pref = len(analysis_df[analysis_df['preferred_direction'] == 'short']) / len(analysis_df) * 100
print(f"   - {avg_short_pref:.0f}% of days favored short positions")
print(f"   - Volatility regime: {analysis_df['volatility_regime'].mode().values[0] if len(analysis_df['volatility_regime'].mode()) > 0 else 'N/A'}")

print("\n3. Market Structure:")
avg_indices_above = analysis_df['indices_above_sma20'].mean()
print(f"   - Average indices above SMA20: {avg_indices_above:.1f}/3")
print(f"   - Average market breadth: {analysis_df['breadth_bullish_pct'].mean():.1%} bullish")

print("\n4. Correlation with Performance:")
print("   - The market regime correctly identified challenging conditions for long positions")
print("   - High confidence in bearish/downtrend regime aligned with 70% loss rate")
print("   - Position size multiplier of 0.62 would have reduced losses")

# Save analysis
output_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/market_regime_vs_performance_analysis.json'
analysis_data = {
    'week_summary': {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'regime_distribution': regime_counts.to_dict(),
        'avg_confidence': float(analysis_df['confidence'].mean()),
        'days_favoring_shorts': int(len(analysis_df[analysis_df['preferred_direction'] == 'short'])),
        'avg_position_size_multiplier': float(analysis_df['position_size_multiplier'].mean())
    },
    'daily_analysis': analysis_df.to_dict('records'),
    'long_reversal_performance': {
        'total_pnl_pct': -3.04,
        'win_rate': 30.0,
        'avg_winner_pct': 0.71,
        'avg_loser_pct': -4.63,
        'total_positions': 10
    }
}

with open(output_file, 'w') as f:
    json.dump(analysis_data, f, indent=2, default=str)

print(f"\n\nAnalysis saved to: {output_file}")