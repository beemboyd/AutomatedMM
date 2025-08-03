#!/usr/bin/env python3
"""
Analyze Brooks Higher Probability LONG Reversal performance
Compare entry prices with current market close prices to calculate success rates
"""

import pandas as pd
import glob
import os
from datetime import datetime, timedelta
import logging
import sys

# Add the project root to the path to import ML modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BrooksReversalAnalyzer:
    def __init__(self):
        self.results_path = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.data_path = "/Users/maverick/PycharmProjects/India-TS/ML/data/ohlc_data/daily"
        self.pattern = "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"
        
    def get_latest_market_data(self, ticker):
        """Get the latest close price for a ticker"""
        try:
            file_path = os.path.join(self.data_path, f"{ticker}_day.csv")
            if not os.path.exists(file_path):
                logger.warning(f"Data file not found for {ticker}")
                return None
                
            df = pd.read_csv(file_path)
            if df.empty:
                return None
                
            # Get the latest close price
            df['date'] = pd.to_datetime(df['date'])
            latest_data = df.loc[df['date'].idxmax()]
            return latest_data['close']
            
        except Exception as e:
            logger.error(f"Error reading data for {ticker}: {str(e)}")
            return None
    
    def analyze_reversal_files(self):
        """Analyze all Brooks reversal files"""
        files = glob.glob(os.path.join(self.results_path, self.pattern))
        files.sort()  # Sort by filename to get chronological order
        
        logger.info(f"Found {len(files)} Brooks reversal files")
        
        all_results = []
        
        for file_path in files:
            logger.info(f"Processing: {os.path.basename(file_path)}")
            
            try:
                # Read the Excel file
                df = pd.read_excel(file_path)
                
                # Extract date from filename
                filename = os.path.basename(file_path)
                date_str = filename.split('_')[-3:-1]  # Get date and time parts
                file_date = '_'.join(date_str)
                
                # Process each row
                for _, row in df.iterrows():
                    ticker = row.get('Ticker', row.get('Symbol', ''))
                    entry_price = row.get('Entry_Price', row.get('Close', 0))
                    
                    if not ticker or entry_price == 0:
                        continue
                    
                    # Get current market price
                    current_price = self.get_latest_market_data(ticker)
                    
                    if current_price is not None:
                        # Calculate performance
                        pnl_percentage = ((current_price - entry_price) / entry_price) * 100
                        
                        result = {
                            'file_date': file_date,
                            'ticker': ticker,
                            'entry_price': entry_price,
                            'current_price': current_price,
                            'pnl_percentage': pnl_percentage,
                            'is_profitable': pnl_percentage > 0,
                            'file_path': file_path
                        }
                        
                        all_results.append(result)
                        
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                continue
        
        return all_results
    
    def generate_summary_report(self, results):
        """Generate summary statistics"""
        if not results:
            logger.error("No results to analyze")
            return
        
        df_results = pd.DataFrame(results)
        
        # Overall statistics
        total_trades = len(df_results)
        profitable_trades = len(df_results[df_results['is_profitable']])
        win_rate = (profitable_trades / total_trades) * 100
        
        avg_pnl = df_results['pnl_percentage'].mean()
        median_pnl = df_results['pnl_percentage'].median()
        max_profit = df_results['pnl_percentage'].max()
        max_loss = df_results['pnl_percentage'].min()
        
        # Print summary
        print("\n" + "="*60)
        print("BROOKS HIGHER PROBABILITY LONG REVERSAL ANALYSIS")
        print("="*60)
        print(f"Analysis Period: {df_results['file_date'].min()} to {df_results['file_date'].max()}")
        print(f"Total Trades Analyzed: {total_trades}")
        print(f"Profitable Trades: {profitable_trades}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Average P&L: {avg_pnl:.2f}%")
        print(f"Median P&L: {median_pnl:.2f}%")
        print(f"Best Trade: {max_profit:.2f}%")
        print(f"Worst Trade: {max_loss:.2f}%")
        
        # Top performers
        print("\n" + "-"*40)
        print("TOP 10 PERFORMERS:")
        print("-"*40)
        top_performers = df_results.nlargest(10, 'pnl_percentage')
        for _, trade in top_performers.iterrows():
            print(f"{trade['ticker']:12} | Entry: ₹{trade['entry_price']:8.2f} | Current: ₹{trade['current_price']:8.2f} | P&L: {trade['pnl_percentage']:6.2f}%")
        
        # Worst performers
        print("\n" + "-"*40)
        print("WORST 10 PERFORMERS:")
        print("-"*40)
        worst_performers = df_results.nsmallest(10, 'pnl_percentage')
        for _, trade in worst_performers.iterrows():
            print(f"{trade['ticker']:12} | Entry: ₹{trade['entry_price']:8.2f} | Current: ₹{trade['current_price']:8.2f} | P&L: {trade['pnl_percentage']:6.2f}%")
        
        # Performance by date
        print("\n" + "-"*40)
        print("PERFORMANCE BY FILE DATE:")
        print("-"*40)
        date_summary = df_results.groupby('file_date').agg({
            'ticker': 'count',
            'is_profitable': 'sum',
            'pnl_percentage': ['mean', 'median']
        }).round(2)
        
        date_summary.columns = ['Total_Trades', 'Profitable_Trades', 'Avg_PnL', 'Median_PnL']
        date_summary['Win_Rate'] = (date_summary['Profitable_Trades'] / date_summary['Total_Trades'] * 100).round(2)
        
        print(date_summary.to_string())
        
        # Save detailed results
        output_file = f"/Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        df_results.to_excel(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")
        
        return df_results

def main():
    analyzer = BrooksReversalAnalyzer()
    results = analyzer.analyze_reversal_files()
    
    if results:
        analyzer.generate_summary_report(results)
    else:
        print("No data found to analyze")

if __name__ == "__main__":
    main()