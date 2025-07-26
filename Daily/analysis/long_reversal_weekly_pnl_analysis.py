import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
from kiteconnect import KiteConnect

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_config
from data_handler import get_data_handler

# Load the Excel file
file_path = '/Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_20250722_113719.xlsx'
df = pd.read_excel(file_path)

# Filter for tickers with 5/7 score
df_filtered = df[df['Score'] == '5/7']

# Sort by some metric (assuming we have a ranking or we'll use the order in the file)
# Take top 10
top_10_tickers = df_filtered.head(10)

print("Top 10 tickers with 5/7 score:")
print(f"Available columns: {list(df.columns)}")
if len(top_10_tickers) > 0:
    print(top_10_tickers[['Ticker', 'Score']])

# Initialize Kite connection using existing config
config = get_config()
api_key = config.get('API', 'api_key')
access_token = config.get('API', 'access_token')

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Define analysis parameters
capital_per_position = 500000
entry_date = datetime(2025, 7, 22)  # Date of the scan
end_date = datetime(2025, 7, 26)   # End of the week (Friday)

# Initialize results
results = []

# Get data handler
data_handler = get_data_handler()

for idx, row in top_10_tickers.iterrows():
    ticker = row['Ticker']
    
    try:
        # Get historical data for the week
        hist_df = data_handler.fetch_historical_data(
            ticker=ticker,
            interval="day",
            from_date=entry_date,
            to_date=end_date
        )
        
        if hist_df.empty:
            print(f"No data available for {ticker}")
            continue
            
        # Data is already a DataFrame from fetch_historical_data
        # Convert column names to lowercase for consistency
        hist_df.columns = hist_df.columns.str.lower()
        hist_df['date'] = pd.to_datetime(hist_df['date'])
        hist_df = hist_df.sort_values('date')
        
        # Get entry price (close of 22nd July or open of 23rd July)
        entry_price = None
        exit_price = None
        
        # Find entry price
        entry_day_data = hist_df[hist_df['date'].dt.date == entry_date.date()]
        if not entry_day_data.empty:
            entry_price = entry_day_data.iloc[0]['close']
        else:
            # Use next day's open
            next_day_data = hist_df[hist_df['date'].dt.date == (entry_date + timedelta(days=1)).date()]
            if not next_day_data.empty:
                entry_price = next_day_data.iloc[0]['open']
        
        # Find exit price (Friday's close or last available day)
        exit_day_data = hist_df[hist_df['date'].dt.date == end_date.date()]
        if not exit_day_data.empty:
            exit_price = exit_day_data.iloc[0]['close']
        else:
            # Use last available day
            if not hist_df.empty:
                exit_price = hist_df.iloc[-1]['close']
        
        if entry_price and exit_price:
            # Calculate PnL
            shares = int(capital_per_position / entry_price)
            entry_value = shares * entry_price
            exit_value = shares * exit_price
            pnl = exit_value - entry_value
            pnl_percentage = (pnl / entry_value) * 100
            
            # Get high and low for the week
            week_high = hist_df['high'].max()
            week_low = hist_df['low'].min()
            
            result = {
                'Ticker': ticker,
                'Entry_Date': entry_date.strftime('%Y-%m-%d'),
                'Entry_Price': round(entry_price, 2),
                'Exit_Date': hist_df.iloc[-1]['date'].strftime('%Y-%m-%d'),
                'Exit_Price': round(exit_price, 2),
                'Shares': shares,
                'Capital_Deployed': round(entry_value, 2),
                'Exit_Value': round(exit_value, 2),
                'PnL': round(pnl, 2),
                'PnL_Percentage': round(pnl_percentage, 2),
                'Week_High': round(week_high, 2),
                'Week_Low': round(week_low, 2),
                'Max_Profit_Potential': round((week_high - entry_price) * shares, 2),
                'Max_Loss_Potential': round((week_low - entry_price) * shares, 2)
            }
            
            results.append(result)
            print(f"\n{ticker}: Entry={entry_price:.2f}, Exit={exit_price:.2f}, PnL={pnl:.2f} ({pnl_percentage:.2f}%)")
        
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
    
    print("\n" + "="*80)
    print("WEEKLY PERFORMANCE SUMMARY")
    print("="*80)
    print(f"Analysis Period: {entry_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Total Positions: {len(results_df)}")
    print(f"Total Capital Deployed: ₹{total_capital:,.2f}")
    print(f"Total PnL: ₹{total_pnl:,.2f} ({total_pnl_percentage:.2f}%)")
    print(f"Winners: {len(winners)} ({len(winners)/len(results_df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(results_df)*100:.1f}%)")
    
    if not winners.empty:
        print(f"Average Winner: ₹{winners['PnL'].mean():,.2f} ({winners['PnL_Percentage'].mean():.2f}%)")
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
                      'Winners', 'Losers', 'Win Rate', 'Average Winner', 'Average Loser',
                      'Best Trade', 'Worst Trade', 'Max Profit Potential', 'Max Loss Potential'],
            'Value': [
                len(results_df),
                f"₹{total_capital:,.2f}",
                f"₹{total_pnl:,.2f}",
                f"{total_pnl_percentage:.2f}%",
                len(winners),
                len(losers),
                f"{len(winners)/len(results_df)*100:.1f}%" if len(results_df) > 0 else "0%",
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
    print(results_df[['Ticker', 'Entry_Price', 'Exit_Price', 'PnL', 'PnL_Percentage']].to_string(index=False))
    
else:
    print("\nNo valid trades could be analyzed.")