# Winner Performance Analysis Summary

## Executive Summary

Based on analysis of **4,337 trades** across **481 tickers** over the last 30 days using live Zerodha API data:

### Key Statistics
- **Winners**: 133 tickers (27.7%)
- **Losers**: 345 tickers (71.7%)
- **Average Win Rate for Winners**: 68.9%
- **Average Expectancy for Winners**: 2.86%
- **Average Holding Period**: 7.5 days

## Top 10 Winning Tickers

| Rank | Ticker | Trades | Win% | Total PnL% | Expectancy% | Avg Days |
|------|--------|--------|------|------------|-------------|----------|
| 1 | COSMOFIRST | 26 | 73.1% | 402.16% | 15.24% | 12.3 |
| 2 | RPOWER | 30 | 76.7% | 363.10% | 12.10% | 8.7 |
| 3 | MUTHOOTFIN | 34 | 94.1% | 321.22% | 9.45% | 6.3 |
| 4 | CONCORDBIO | 21 | 95.2% | 290.57% | 13.84% | 7.9 |
| 5 | DBREALTY | 26 | 84.6% | 290.16% | 11.16% | 6.4 |
| 6 | SIGACHI | 30 | 86.7% | 248.45% | 8.28% | 8.3 |
| 7 | JKCEMENT | 31 | 87.1% | 170.02% | 5.48% | 6.0 |
| 8 | ASTRAZEN | 20 | 80.0% | 161.93% | 8.10% | 6.0 |
| 9 | ELECTCAST | 18 | 72.2% | 159.48% | 8.86% | 4.7 |
| 10 | NAVA | 24 | 83.3% | 146.56% | 6.11% | 7.5 |

## Key Insights for Spotting Future Winners

### 1. **High Win Rate is Critical**
- Top performers have win rates between 70-95%
- Average win rate for all winners: 68.9%
- Stocks with win rates below 50% rarely become top performers

### 2. **Score Analysis Reveals Surprising Pattern**
- **5/7 Score**: Best performance (4.02% avg PnL, 73.0% win rate)
- **6/7 Score**: Good performance (3.02% avg PnL, 70.4% win rate)
- **7/7 Score**: Lower performance (2.47% avg PnL, 61.3% win rate)
- **Insight**: Don't wait for perfect setups - good setups (5/7) often perform better

### 3. **Optimal Holding Period**
- Winners typically reach targets in 6-8 days
- Extended holding beyond 15 days often reduces returns
- Quick exits on stop losses preserve capital

### 4. **Consistent Winners (Repeat Performers)**
These tickers appear frequently with high success rates:
- COSMOFIRST, RPOWER, MUTHOOTFIN, CONCORDBIO, DBREALTY
- SIGACHI, JKCEMENT, ASTRAZEN, ELECTCAST, NAVA

### 5. **Winner Characteristics**
Based on the analysis, winning trades typically have:
- **High frequency appearance** in scans (20+ times)
- **Consistent win rates** above 70%
- **Positive expectancy** above 5%
- **Quick target achievement** (under 10 days)

### 6. **Risk Management Insights**
- Winners have lower stop loss hit rates
- Average winner reaches Target 1 frequently
- Position sizing should favor high-frequency winners

## Actionable Recommendations

1. **Focus on Repeat Winners**: Track tickers that appear frequently in scans with high win rates
2. **Don't Over-optimize**: 5/7 score setups perform as well or better than 7/7 setups
3. **Time Management**: Consider tightening stops after 10 days if no progress
4. **Position Sizing**: Allocate more capital to tickers with proven track records
5. **Watch List**: Create a priority list of the top 30 performers for quick action

## Technical Implementation

The analysis was performed using:
- **Data Source**: Zerodha Kite API for real-time OHLC data
- **Analysis Period**: Last 30 days of trading
- **Methodology**: Actual trade outcome tracking (entry to exit)
- **Scripts Created**:
  - `winner_performance_analyzer_optimized.py` - Main analysis engine
  - `winner_performance_visualizer.py` - Visualization tools

## Usage

To run your own analysis:
```bash
# Full analysis
python ML/winner_performance_analyzer_optimized.py --days 30 --top-n 30

# Quick test with limited tickers
python ML/winner_performance_analyzer_optimized.py --days 7 --top-n 10 --limit 50

# Generate visualizations
python ML/winner_performance_visualizer.py
```

## Files Generated
- Text reports: `ML/results/winner_analysis_optimized_*.txt`
- Excel reports: `ML/results/winner_analysis_optimized_*.xlsx`
- Visualizations: `ML/results/performance_dashboard_*.png`

---
*Analysis completed on 2025-06-15*