# Weekly Performance Reports

This directory contains automated weekly performance analysis reports for the Long Reversal trading strategy.

## Overview

The Long Reversal 4-Week Performance Analyzer tracks and analyzes the performance of Long Reversal Daily signals over a rolling 4-week period, correlating results with market regime predictions.

## Reports Generated

### 1. JSON Reports
- `long_reversal_4week_analysis_YYYYMMDD_HHMMSS.json` - Timestamped detailed analysis
- `latest_4week_analysis.json` - Always contains the most recent analysis

### 2. Excel Reports
- `long_reversal_4week_analysis_YYYYMMDD_HHMMSS.xlsx` - Timestamped Excel report with multiple sheets:
  - **Summary**: Overall 4-week performance metrics
  - **Weekly_Breakdown**: Week-by-week performance
  - **Regime_Correlation**: Performance by market regime
  - **Daily_Results**: Day-by-day detailed results
- `latest_4week_analysis.xlsx` - Always contains the most recent analysis

### 3. Text Summary
- `weekly_summary.txt` - Human-readable summary suitable for email/notifications

## Key Metrics Tracked

### Overall Metrics
- Total number of scans analyzed
- Total trades taken (top 10 with 5/7 score)
- Overall win rate
- Total P&L
- Average win/loss percentages

### Weekly Breakdown
- Number of scans per week
- Weekly win rates
- Weekly P&L
- Trade distribution

### Regime Correlation
- Performance by market regime (uptrend, downtrend, choppy, etc.)
- Win rates for each regime
- Average P&L per scan by regime
- Helps identify which market conditions favor the strategy

## Usage

### Manual Run
```bash
python Daily/analysis/long_reversal_4week_performance_analyzer.py
```

### Weekend Automation
```bash
python Daily/analysis/run_weekend_analysis.py
```

### Schedule with Cron (Every Saturday at 6 PM)
```bash
0 18 * * 6 cd /Users/maverick/PycharmProjects/India-TS && python3 Daily/analysis/run_weekend_analysis.py
```

## Configuration

Default settings in the analyzer:
- **Analysis Period**: 4 weeks
- **Capital per Position**: ₹500,000
- **Max Positions**: 10 (top-scored tickers)
- **Score Filter**: 5/7
- **Holding Period**: 5 trading days

## Interpretation

### Win Rate Benchmarks
- **>60%**: Excellent - Strategy performing very well
- **50-60%**: Good - Profitable with proper risk management
- **40-50%**: Average - May need regime filtering
- **<40%**: Poor - Review strategy or market conditions

### Regime Correlation
- Look for regimes with consistently higher win rates
- Avoid trading when the unfavorable regime is detected
- Adjust position sizing based on regime confidence

### Weekly Trends
- Identify if performance is improving or deteriorating
- Correlate with market conditions and events
- Adjust strategy parameters if needed

## Future Enhancements
1. Add Short Reversal analysis
2. Include risk-adjusted returns (Sharpe ratio)
3. Add maximum drawdown analysis
4. Create comparison with buy-and-hold benchmark
5. Add email notifications for weekly summaries
6. Include charts and visualizations
7. Track slippage and execution quality

## Files in this Directory
- Analysis reports (JSON, Excel, Text)
- `weekend_analysis.log` - Execution logs
- This README file