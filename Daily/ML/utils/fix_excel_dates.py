#!/usr/bin/env python3
"""
Fix date formatting in existing Keltner Channel analysis Excel files
"""
import pandas as pd
import os
from openpyxl import load_workbook
from datetime import datetime

def fix_excel_dates():
    """Fix date columns in Excel files"""
    results_dir = 'results'
    
    # Find all Excel files
    excel_files = [f for f in os.listdir(results_dir) if f.endswith('.xlsx')]
    
    for excel_file in excel_files:
        file_path = os.path.join(results_dir, excel_file)
        print(f"Fixing dates in {excel_file}...")
        
        try:
            # Read the Excel file
            dfs = {}
            sheet_names = ['Original_Trades', 'Filtered_Trades', 'Summary_Comparison']
            
            for sheet in sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    
                    # Fix entry_date column if it exists
                    if 'entry_date' in df.columns:
                        # Convert Excel serial numbers to proper dates
                        df['entry_date'] = pd.to_datetime(df['entry_date'], errors='coerce')
                        df['entry_date'] = df['entry_date'].dt.strftime('%Y-%m-%d')
                        print(f"  Fixed entry_date column in {sheet}")
                    
                    dfs[sheet] = df
                except Exception as e:
                    print(f"  Warning: Could not read sheet {sheet}: {e}")
            
            # Write back to Excel with proper formatting
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for sheet_name, df in dfs.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"  ✓ Successfully fixed {excel_file}")
            
        except Exception as e:
            print(f"  ✗ Error fixing {excel_file}: {e}")

def create_clean_report():
    """Create a clean, formatted report of the latest results"""
    latest_file = 'results/keltner_filter_comparison_20250617_200546.xlsx'
    
    if not os.path.exists(latest_file):
        print("Latest file not found")
        return
    
    print("\n=== Creating Clean Report ===")
    
    # Read the data
    df_filtered = pd.read_excel(latest_file, sheet_name='Filtered_Trades')
    df_original = pd.read_excel(latest_file, sheet_name='Original_Trades')
    
    # Fix dates
    for df in [df_filtered, df_original]:
        if 'entry_date' in df.columns:
            df['entry_date'] = pd.to_datetime(df['entry_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Create clean report
    clean_file = 'results/keltner_analysis_clean_report.xlsx'
    
    with pd.ExcelWriter(clean_file, engine='openpyxl') as writer:
        # Filtered trades that passed
        passed_trades = df_filtered[df_filtered['outcome'] != 'filtered_out'].copy()
        passed_trades = passed_trades[['ticker', 'entry_date', 'outcome', 'pnl_percent', 'holding_days', 'score', 'pattern']].round(2)
        passed_trades.columns = ['Ticker', 'Entry_Date', 'Outcome', 'PnL_%', 'Holding_Days', 'Score', 'Pattern']
        passed_trades.to_excel(writer, sheet_name='Passed_Filter_Trades', index=False)
        
        # Top performers
        winners = passed_trades[passed_trades['PnL_%'] > 0].sort_values('PnL_%', ascending=False)
        winners.to_excel(writer, sheet_name='Top_Performers', index=False)
        
        # Summary stats
        summary_data = {
            'Metric': ['Total Analyzed', 'Passed Filter', 'Filter Efficiency %', 'Win Rate %', 'Avg PnL %', 'Best Trade', 'Worst Trade'],
            'Value': [
                len(df_filtered),
                len(passed_trades),
                f"{(1 - len(passed_trades)/len(df_filtered))*100:.1f}%",
                f"{len(winners)/len(passed_trades)*100:.1f}%" if len(passed_trades) > 0 else "0%",
                f"{passed_trades['PnL_%'].mean():.2f}%" if len(passed_trades) > 0 else "N/A",
                f"{passed_trades['PnL_%'].max():.2f}%" if len(passed_trades) > 0 else "N/A",
                f"{passed_trades['PnL_%'].min():.2f}%" if len(passed_trades) > 0 else "N/A"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"✓ Clean report saved as: {clean_file}")
    
    # Print top performers
    if len(winners) > 0:
        print("\n🏆 TOP PERFORMING FILTERED TICKERS:")
        print("=" * 50)
        for _, row in winners.head(10).iterrows():
            print(f"{row['Ticker']:12} | {row['Entry_Date']} | +{row['PnL_%']:5.2f}% | Score: {row['Score']}")

if __name__ == '__main__':
    fix_excel_dates()
    create_clean_report()