#!/usr/bin/env python
"""
Weekend Analysis Runner
Runs comprehensive performance analysis for Long Reversal strategy
and generates weekly reports
"""

import os
import sys
import datetime
import logging
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from long_reversal_4week_performance_analyzer import LongReversalPerformanceAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 
                                       'Weekly_Reports', 'weekend_analysis.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_weekend_analysis():
    """Run weekend analysis and generate reports"""
    logger.info("="*80)
    logger.info("Starting Weekend Analysis")
    logger.info(f"Date: {datetime.datetime.now()}")
    logger.info("="*80)
    
    try:
        # Run Long Reversal 4-week analysis
        logger.info("\n1. Running Long Reversal 4-Week Performance Analysis...")
        analyzer = LongReversalPerformanceAnalyzer(weeks_to_analyze=4)
        report = analyzer.run_analysis()
        
        # Generate summary email content
        summary = generate_email_summary(report)
        
        # Save summary for easy access
        summary_file = os.path.join(analyzer.output_dir, 'weekly_summary.txt')
        with open(summary_file, 'w') as f:
            f.write(summary)
        
        logger.info(f"\nAnalysis complete! Reports saved to: {analyzer.output_dir}")
        
        # Future: Add more analysis here
        # - Short Reversal analysis
        # - Regime accuracy analysis
        # - Strategy comparison
        
        return True
        
    except Exception as e:
        logger.error(f"Error during weekend analysis: {e}")
        return False

def generate_email_summary(report):
    """Generate a summary suitable for email notification"""
    summary = []
    summary.append("WEEKLY LONG REVERSAL PERFORMANCE SUMMARY")
    summary.append("=" * 60)
    summary.append(f"Analysis Period: {report['analysis_period']['start']} to {report['analysis_period']['end']}")
    summary.append("")
    
    # Overall performance
    s = report['summary']
    summary.append("OVERALL PERFORMANCE (4 WEEKS):")
    summary.append(f"  • Total Scans: {s.get('total_scans', 0)}")
    summary.append(f"  • Total Trades: {s.get('total_trades', 0)}")
    summary.append(f"  • Win Rate: {s.get('overall_win_rate', 0):.1f}%")
    summary.append(f"  • Total P&L: ₹{s.get('total_pnl', 0):,.2f}")
    summary.append(f"  • Average Win: {s.get('avg_win_percentage', 0):.2f}%")
    summary.append(f"  • Average Loss: {s.get('avg_loss_percentage', 0):.2f}%")
    summary.append("")
    
    # Last week performance
    last_week = sorted(report['weekly_breakdown'].keys())[-1] if report['weekly_breakdown'] else None
    if last_week:
        lw = report['weekly_breakdown'][last_week]
        summary.append(f"LAST WEEK PERFORMANCE ({last_week}):")
        summary.append(f"  • Scans: {lw['scans']}")
        summary.append(f"  • Win Rate: {lw['win_rate']:.1f}%")
        summary.append(f"  • P&L: ₹{lw['total_pnl']:,.2f}")
        summary.append("")
    
    # Regime correlation insights
    summary.append("KEY INSIGHTS BY MARKET REGIME:")
    best_regime = None
    best_win_rate = 0
    
    for regime, data in report['regime_correlation'].items():
        if data['win_rate'] > best_win_rate and data['trades'] >= 5:
            best_regime = regime
            best_win_rate = data['win_rate']
        summary.append(f"  • {regime}: {data['win_rate']:.1f}% win rate ({data['trades']} trades)")
    
    if best_regime:
        summary.append(f"\nBest performing regime: {best_regime} ({best_win_rate:.1f}% win rate)")
    
    summary.append("")
    summary.append("Full reports available in: Daily/analysis/Weekly_Reports/")
    
    return "\n".join(summary)

def main():
    """Main function"""
    # Check if it's weekend (Saturday or Sunday)
    today = datetime.datetime.now()
    
    if today.weekday() in [5, 6]:  # Saturday = 5, Sunday = 6
        logger.info("It's weekend! Running analysis...")
    else:
        logger.info(f"Today is {today.strftime('%A')}. Running analysis anyway...")
    
    success = run_weekend_analysis()
    
    if success:
        logger.info("\nWeekend analysis completed successfully!")
        sys.exit(0)
    else:
        logger.error("\nWeekend analysis failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()