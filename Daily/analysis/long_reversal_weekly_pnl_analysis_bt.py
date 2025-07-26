import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# Load the Excel file
file_path = '/Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_20250722_113719.xlsx'
df = pd.read_excel(file_path)

# Filter for tickers with 5/7 score
df_filtered = df[df['Score'] == '5/7']

# Take top 10
top_10_tickers = df_filtered.head(10)

print("Top 10 tickers with 5/7 score:")
print(top_10_tickers[['Ticker', 'Score', 'Entry_Price']])

# Define analysis parameters
capital_per_position = 500000
entry_date = datetime(2025, 7, 22)  # Date of the scan
end_date = datetime(2025, 7, 26)   # End of the week (Friday)

# Initialize results
results = []

# Path to historical data
data_dir = '/Users/maverick/PycharmProjects/India-TS/BT/data'

for idx, row in top_10_tickers.iterrows():
    ticker = row['Ticker']
    
    try:
        # Look for daily data file
        daily_file = os.path.join(data_dir, f"{ticker}_day.csv")
        
        if not os.path.exists(daily_file):
            print(f"No historical data file found for {ticker}")
            continue
            
        # Read historical data
        hist_df = pd.read_csv(daily_file)
        # Check if 'date' column exists (lowercase)
        if 'date' in hist_df.columns:
            hist_df['Date'] = pd.to_datetime(hist_df['date'])
            hist_df = hist_df.drop(columns=['date'])
        else:
            hist_df['Date'] = pd.to_datetime(hist_df['Date'])
        hist_df = hist_df.sort_values('Date')
        
        # Filter data for the analysis period
        hist_df_period = hist_df[(hist_df['Date'] >= entry_date) & (hist_df['Date'] <= end_date)]
        
        if hist_df_period.empty:
            print(f"No data available for {ticker} in the analysis period")
            continue
        
        # Get entry price (close of 22nd July or provided entry price)
        entry_price = row['Entry_Price']  # Use the entry price from scan results
        
        # Find exit price (Friday's close or last available day)
        exit_day_data = hist_df_period[hist_df_period['Date'].dt.date == end_date.date()]
        if not exit_day_data.empty:
            exit_price = exit_day_data.iloc[0]['Close']
        else:
            # Use last available day
            exit_price = hist_df_period.iloc[-1]['Close']
        
        # Calculate PnL
        shares = int(capital_per_position / entry_price)
        entry_value = shares * entry_price
        exit_value = shares * exit_price
        pnl = exit_value - entry_value
        pnl_percentage = (pnl / entry_value) * 100
        
        # Get high and low for the week
        week_high = hist_df_period['High'].max()
        week_low = hist_df_period['Low'].min()
        
        # Check if stop loss was hit
        stop_loss = row['Stop_Loss']
        sl_hit = hist_df_period['Low'].min() <= stop_loss
        
        # If stop loss was hit, find the day and adjust exit price
        if sl_hit:
            sl_day = hist_df_period[hist_df_period['Low'] <= stop_loss].iloc[0]
            exit_price = stop_loss
            exit_value = shares * exit_price
            pnl = exit_value - entry_value
            pnl_percentage = (pnl / entry_value) * 100
            exit_date_actual = sl_day['Date']
        else:
            exit_date_actual = hist_df_period.iloc[-1]['Date']
        
        result = {
            'Ticker': ticker,
            'Entry_Date': entry_date.strftime('%Y-%m-%d'),
            'Entry_Price': round(entry_price, 2),
            'Exit_Date': exit_date_actual.strftime('%Y-%m-%d'),
            'Exit_Price': round(exit_price, 2),
            'Stop_Loss': round(stop_loss, 2),
            'SL_Hit': sl_hit,
            'Shares': shares,
            'Capital_Deployed': round(entry_value, 2),
            'Exit_Value': round(exit_value, 2),
            'PnL': round(pnl, 2),
            'PnL_Percentage': round(pnl_percentage, 2),
            'Week_High': round(week_high, 2),
            'Week_Low': round(week_low, 2),
            'Max_Profit_Potential': round((week_high - entry_price) * shares, 2),
            'Max_Loss_Potential': round((week_low - entry_price) * shares, 2),
            'Target1': round(row['Target1'], 2),
            'Target2': round(row['Target2'], 2),
            'Target1_Hit': week_high >= row['Target1'],
            'Target2_Hit': week_high >= row['Target2']
        }
        
        results.append(result)
        print(f"\n{ticker}: Entry={entry_price:.2f}, Exit={exit_price:.2f}, PnL={pnl:.2f} ({pnl_percentage:.2f}%) {'[SL Hit]' if sl_hit else ''}")
        
    except Exception as e:
        print(f"Error processing {ticker}: {str(e)}")
        continue

# Create results DataFrame
results_df = pd.DataFrame(results)

if not results_df.empty:
    # Calculate summary statistics
    total_capital = results_df['Capital_Deployed'].sum()
    total_pnl = results_df['PnL'].sum()
    total_pnl_percentage = (total_pnl / total_capital) * 100 if total_capital > 0 else 0
    
    winners = results_df[results_df['PnL'] > 0]
    losers = results_df[results_df['PnL'] < 0]
    sl_hits = results_df[results_df['SL_Hit'] == True]
    target1_hits = results_df[results_df['Target1_Hit'] == True]
    target2_hits = results_df[results_df['Target2_Hit'] == True]
    
    print("\n" + "="*80)
    print("WEEKLY PERFORMANCE SUMMARY")
    print("="*80)
    print(f"Analysis Period: {entry_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Total Positions: {len(results_df)}")
    print(f"Total Capital Deployed: ₹{total_capital:,.2f}")
    print(f"Total PnL: ₹{total_pnl:,.2f} ({total_pnl_percentage:.2f}%)")
    print(f"Winners: {len(winners)} ({len(winners)/len(results_df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(results_df)*100:.1f}%)")
    print(f"Stop Loss Hit: {len(sl_hits)} ({len(sl_hits)/len(results_df)*100:.1f}%)")
    print(f"Target 1 Hit: {len(target1_hits)} ({len(target1_hits)/len(results_df)*100:.1f}%)")
    print(f"Target 2 Hit: {len(target2_hits)} ({len(target2_hits)/len(results_df)*100:.1f}%)")
    
    if not winners.empty:
        print(f"\nAverage Winner: ₹{winners['PnL'].mean():,.2f} ({winners['PnL_Percentage'].mean():.2f}%)")
        print(f"Best Trade: {winners.loc[winners['PnL'].idxmax(), 'Ticker']} - ₹{winners['PnL'].max():,.2f}")
    
    if not losers.empty:
        print(f"Average Loser: ₹{losers['PnL'].mean():,.2f} ({losers['PnL_Percentage'].mean():.2f}%)")
        print(f"Worst Trade: {losers.loc[losers['PnL'].idxmin(), 'Ticker']} - ₹{losers['PnL'].min():,.2f}")
    
    # Save detailed results
    output_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/long_reversal_weekly_pnl_results.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name='Trade_Details', index=False)
        
        # Add summary sheet
        summary_data = {
            'Metric': ['Total Positions', 'Total Capital Deployed', 'Total PnL', 'Total PnL %', 
                      'Winners', 'Losers', 'Win Rate', 'Stop Loss Hit', 'Target 1 Hit', 'Target 2 Hit',
                      'Average Winner', 'Average Loser', 'Best Trade', 'Worst Trade', 
                      'Max Profit Potential', 'Max Loss Potential'],
            'Value': [
                len(results_df),
                f"₹{total_capital:,.2f}",
                f"₹{total_pnl:,.2f}",
                f"{total_pnl_percentage:.2f}%",
                len(winners),
                len(losers),
                f"{len(winners)/len(results_df)*100:.1f}%" if len(results_df) > 0 else "0%",
                f"{len(sl_hits)} ({len(sl_hits)/len(results_df)*100:.1f}%)",
                f"{len(target1_hits)} ({len(target1_hits)/len(results_df)*100:.1f}%)",
                f"{len(target2_hits)} ({len(target2_hits)/len(results_df)*100:.1f}%)",
                f"₹{winners['PnL'].mean():,.2f}" if not winners.empty else "N/A",
                f"₹{losers['PnL'].mean():,.2f}" if not losers.empty else "N/A",
                f"{winners.loc[winners['PnL'].idxmax(), 'Ticker']} - ₹{winners['PnL'].max():,.2f}" if not winners.empty else "N/A",
                f"{losers.loc[losers['PnL'].idxmin(), 'Ticker']} - ₹{losers['PnL'].min():,.2f}" if not losers.empty else "N/A",
                f"₹{results_df['Max_Profit_Potential'].sum():,.2f}",
                f"₹{results_df['Max_Loss_Potential'].sum():,.2f}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Display individual trade details
    print("\n" + "="*80)
    print("INDIVIDUAL TRADE DETAILS")
    print("="*80)
    print(results_df[['Ticker', 'Entry_Price', 'Exit_Price', 'PnL', 'PnL_Percentage', 'SL_Hit']].to_string(index=False))
    
else:
    print("\nNo valid trades could be analyzed.")