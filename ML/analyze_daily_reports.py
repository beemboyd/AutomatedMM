#!/usr/bin/env python3
"""
Analyze Brooks Higher Probability LONG Reversal reports from yesterday and today.
Counts ticker occurrences and report runs, saves results to a text file.
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_report_files(report_dir, target_dates):
    """Get all report files matching the target dates."""
    report_files = []
    
    if not os.path.exists(report_dir):
        logger.error(f"Report directory not found: {report_dir}")
        return report_files
    
    for filename in os.listdir(report_dir):
        if not filename.endswith('.xlsx'):
            continue
            
        # Extract date from filename (format: DD_MM_YYYY)
        try:
            parts = filename.split('_')
            if len(parts) >= 8:
                day = parts[5]
                month = parts[6]
                year = parts[7]
                file_date = f"{day}_{month}_{year}"
                
                if file_date in target_dates:
                    file_path = os.path.join(report_dir, filename)
                    # Extract time from filename
                    hour = parts[8]
                    minute = parts[9].replace('.xlsx', '')
                    time_str = f"{hour}:{minute}"
                    
                    report_files.append({
                        'path': file_path,
                        'filename': filename,
                        'date': file_date,
                        'time': time_str,
                        'datetime': datetime.strptime(f"{day}/{month}/{year} {hour}:{minute}", "%d/%m/%Y %H:%M")
                    })
        except Exception as e:
            logger.warning(f"Could not parse filename {filename}: {e}")
    
    return sorted(report_files, key=lambda x: x['datetime'])

def extract_tickers_from_report(file_path):
    """Extract ticker symbols from a Brooks report Excel file."""
    try:
        df = pd.read_excel(file_path)
        
        # Find ticker column - usually named 'Symbol' or 'Ticker'
        ticker_column = None
        for col in df.columns:
            if col.lower() in ['symbol', 'ticker', 'stock', 'scrip']:
                ticker_column = col
                break
        
        if ticker_column is None and len(df.columns) > 0:
            # If no obvious ticker column, use the first column
            ticker_column = df.columns[0]
        
        if ticker_column:
            tickers = df[ticker_column].dropna().unique().tolist()
            return [str(ticker).strip() for ticker in tickers if str(ticker).strip()]
        else:
            logger.warning(f"No ticker column found in {file_path}")
            return []
            
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []

def analyze_reports(report_dir, output_dir, days_back=3):
    """Main function to analyze reports and generate output."""
    # Get dates for the past N days
    today = datetime.now()
    target_dates = []
    date_strings = []
    
    for i in range(days_back):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%d_%m_%Y")
        target_dates.append(date_str)
        date_strings.append(target_date.strftime("%Y-%m-%d"))
    
    logger.info(f"Analyzing reports for the past {days_back} days: {', '.join(reversed(date_strings))}")
    
    # Get report files
    report_files = get_report_files(report_dir, target_dates)
    
    # Group reports by date
    reports_by_date = {}
    for date_str in target_dates:
        reports_by_date[date_str] = [r for r in report_files if r['date'] == date_str]
    
    # Track ticker occurrences
    ticker_count = defaultdict(int)
    ticker_appearances = defaultdict(list)  # Track which reports each ticker appeared in
    
    # Process all reports
    all_reports = report_files
    
    for report in all_reports:
        tickers = extract_tickers_from_report(report['path'])
        report_id = f"{report['date']} {report['time']}"
        
        for ticker in tickers:
            ticker_count[ticker] += 1
            ticker_appearances[ticker].append(report_id)
    
    # Generate output
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("BROOKS HIGHER PROBABILITY LONG REVERSAL - TICKER ANALYSIS")
    output_lines.append("=" * 80)
    output_lines.append(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append(f"Reports analyzed for the past {days_back} days\n")
    
    # Report run summary
    output_lines.append("-" * 80)
    output_lines.append("REPORT RUN SUMMARY")
    output_lines.append("-" * 80)
    
    # Show reports for each day (in chronological order)
    for i in range(days_back-1, -1, -1):
        date_str = target_dates[i]
        date_obj = today - timedelta(days=i)
        day_name = date_obj.strftime("%A")
        formatted_date = date_obj.strftime("%Y-%m-%d")
        
        output_lines.append(f"\n{day_name}, {formatted_date} ({date_str}):")
        day_reports = reports_by_date[date_str]
        output_lines.append(f"  Total reports: {len(day_reports)}")
        
        if day_reports:
            output_lines.append("  Report times:")
            for report in day_reports:
                output_lines.append(f"    - {report['time']} ({report['filename']})")
        else:
            output_lines.append("  No reports found for this day")
    
    output_lines.append(f"\nTotal reports analyzed: {len(all_reports)}")
    
    # Ticker occurrence summary
    output_lines.append("\n" + "-" * 80)
    output_lines.append("TICKER OCCURRENCE SUMMARY")
    output_lines.append("-" * 80)
    
    if ticker_count:
        # Sort tickers by occurrence count (descending)
        sorted_tickers = sorted(ticker_count.items(), key=lambda x: x[1], reverse=True)
        
        output_lines.append(f"\nTotal unique tickers: {len(ticker_count)}")
        output_lines.append(f"Total ticker occurrences: {sum(ticker_count.values())}")
        
        # Top tickers
        output_lines.append("\nTop 20 Most Frequent Tickers:")
        output_lines.append("-" * 40)
        for i, (ticker, count) in enumerate(sorted_tickers[:20], 1):
            output_lines.append(f"{i:3d}. {ticker:<15} - appeared {count:2d} times")
        
        # Tickers that appeared in all reports
        if all_reports:
            all_report_tickers = [ticker for ticker, count in ticker_count.items() 
                                  if count == len(all_reports)]
            if all_report_tickers:
                output_lines.append(f"\nTickers appearing in ALL {len(all_reports)} reports:")
                output_lines.append(", ".join(sorted(all_report_tickers)))
        
        # Full ticker list with appearances
        output_lines.append("\n" + "-" * 80)
        output_lines.append("DETAILED TICKER APPEARANCES")
        output_lines.append("-" * 80)
        
        for ticker, count in sorted_tickers:
            output_lines.append(f"\n{ticker} (appeared {count} times):")
            appearances = ticker_appearances[ticker]
            for appearance in appearances:
                output_lines.append(f"  - {appearance}")
    else:
        output_lines.append("\nNo tickers found in the analyzed reports.")
    
    # Save output
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"ticker_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_path = os.path.join(output_dir, output_filename)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(output_lines))
    
    logger.info(f"Analysis complete. Results saved to: {output_path}")
    
    # Also print summary to console
    print("\n".join(output_lines[:50]))  # Print first 50 lines
    if len(output_lines) > 50:
        print(f"\n... (Full report saved to {output_path})")
    
    return output_path

if __name__ == "__main__":
    report_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
    output_dir = "/Users/maverick/PycharmProjects/India-TS/ML/results"
    
    output_file = analyze_reports(report_dir, output_dir)