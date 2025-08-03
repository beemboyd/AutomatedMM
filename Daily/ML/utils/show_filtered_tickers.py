#!/usr/bin/env python3
"""
Show tickers that passed the Keltner Channel filter
"""
import pandas as pd

def show_filtered_results():
    print('=== KELTNER CHANNEL FILTER RESULTS ===')
    try:
        # Read the Excel file with successful filter results
        df = pd.read_excel('results/keltner_filter_comparison_20250617_200546.xlsx', sheet_name='Filtered_Trades')
        
        # Filter out the ones that were filtered out
        passed_filter = df[df['outcome'] != 'filtered_out']
        
        print(f'Total tickers that PASSED filter: {len(passed_filter)} out of {len(df)}')
        print()
        
        if len(passed_filter) > 0:
            print('TICKERS THAT PASSED KELTNER CHANNEL FILTER:')
            print('=' * 60)
            for idx, row in passed_filter.iterrows():
                entry_date = pd.to_datetime(row['entry_date']).strftime('%Y-%m-%d')
                print(f'{row["ticker"]:12} | {entry_date} | {row["outcome"]:10} | PnL: {row["pnl_percent"]:6.2f}% | Days: {row["holding_days"]:4.1f}')
            
            print()
            print('PERFORMANCE SUMMARY:')
            print('=' * 30)
            winning = passed_filter[passed_filter['pnl_percent'] > 0]
            print(f'Win Rate: {len(winning)}/{len(passed_filter)} = {len(winning)/len(passed_filter)*100:.1f}%')
            print(f'Avg PnL: {passed_filter["pnl_percent"].mean():.2f}%')
            print(f'Total PnL: {passed_filter["pnl_percent"].sum():.2f}%')
            
            print()
            print('WINNING TICKERS:')
            print('=' * 20)
            for idx, row in winning.iterrows():
                print(f'{row["ticker"]:12} | +{row["pnl_percent"]:5.2f}% | Score: {row["score"]}')
        else:
            print('No tickers passed the filter in this analysis')
            
        # Show some filtered out examples
        print()
        print('EXAMPLES OF FILTERED OUT TICKERS:')
        print('=' * 40)
        filtered_out = df[df['outcome'] == 'filtered_out'].head(5)
        for idx, row in filtered_out.iterrows():
            entry_date = pd.to_datetime(row['entry_date']).strftime('%Y-%m-%d')
            print(f'{row["ticker"]:12} | {entry_date} | KC Crossings: {row["keltner_crossings"]}')
            
        # Also show summary comparison
        print('\n=== SUMMARY COMPARISON ===')
        summary_df = pd.read_excel('results/keltner_filter_comparison_20250617_200546.xlsx', sheet_name='Summary_Comparison')
        print(summary_df.to_string(index=False))
        
    except Exception as e:
        print(f'Error reading file: {e}')
        print('Available files:')
        import os
        files = os.listdir('results/')
        for f in files:
            if f.endswith('.xlsx'):
                print(f'  {f}')

if __name__ == '__main__':
    show_filtered_results()