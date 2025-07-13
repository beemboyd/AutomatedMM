# Trend Weakness Analyzer

This tool analyzes portfolio positions for trend weakness patterns based on Al Brooks' price action methodology.

## Overview

The analyzer examines each position in a user's portfolio and scores the trend weakness from 0-100 based on multiple price action patterns. Higher scores indicate greater trend weakness and potential exit signals.

## Al Brooks Trend Weakness Patterns

### Bull Trend Weakness Patterns (Long Positions)

1. **Smaller Bull Bodies** - Bull candles getting progressively smaller
2. **Top Tails Forming** - Upper shadows appearing on candles
3. **Top Tails Increasing** - Upper shadows getting larger
4. **Bar Overlap Increasing** - More overlap between consecutive bars
5. **Small Body/Doji** - Very small real bodies or doji candles
6. **Bear Body** - Appearance of red/bearish candles
7. **High at/below Prior** - Current high not exceeding previous high
8. **Low at/above Prior** - Current low at or above previous low
9. **Low Below Prior** - Breaking below previous low
10. **One-Leg Pullback** - Single leg down (High 1 buy setup)
11. **Two-Leg Pullback** - Two legs down lasting 5-10 bars
12. **Three-Leg Pullback** - Wedge or triangle lasting 5-15 bars
13. **Minor Trendline Break** - Break of short-term trend line
14. **Touch MA** - Price touching 20-period moving average
15. **New High with Bear Bars** - Rally to new high contains bear bars
16. **Close Below MA** - Closing below moving average
17. **High Below MA** - High of bar below moving average
18. **Major Trendline Break** - Break of significant trend line
19. **Second Leg Down** - After MA break, second leg down occurs
20. **Multiple Pullbacks** - Rally has 2+ pullbacks with bear bodies
21. **Larger Two-Leg Pullback** - Extended pullback >10 bars
22. **Trading Range Formed** - Sideways movement with equal bulls/bears
23. **False Breakout** - Break above range followed by return

### Bear Trend Weakness Patterns (Short Positions)

1. **Smaller Bear Bodies** - Bear candles getting progressively smaller
2. **Bottom Tails Forming** - Lower shadows appearing on candles
3. **Bottom Tails Increasing** - Lower shadows getting larger
4. **Bar Overlap Increasing** - More overlap between consecutive bars
5. **Small Body/Doji** - Very small real bodies or doji candles
6. **Bull Body** - Appearance of green/bullish candles
7. **Low at/above Prior** - Current low not breaking previous low
8. **High at/below Prior** - Current high at or below previous high
9. **High Above Prior** - Breaking above previous high
10. **One-Leg Pullback** - Single leg up (Low 1 sell setup)
11. **Two-Leg Pullback** - Two legs up lasting 5-10 bars
12. **Three-Leg Pullback** - Wedge or triangle lasting 5-15 bars
13. **Minor Trendline Break** - Break of short-term trend line
14. **Touch MA** - Price touching 20-period moving average
15. **New Low with Bull Bars** - Decline to new low contains bull bars
16. **Close Above MA** - Closing above moving average
17. **Low Above MA** - Low of bar above moving average
18. **Major Trendline Break** - Break of significant trend line
19. **Second Leg Up** - After MA break, second leg up occurs
20. **Multiple Pullbacks** - Decline has 2+ pullbacks with bull bodies
21. **Larger Two-Leg Pullback** - Extended pullback >10 bars
22. **Trading Range Formed** - Sideways movement with equal bulls/bears
23. **False Breakout** - Break below range followed by return

## Scoring System

Each pattern has a weight from 1-8 based on significance:
- **1-2**: Minor weakness signals
- **3-4**: Moderate weakness signals
- **5-6**: Significant weakness signals
- **7-8**: Major weakness signals

The final score is normalized to 0-100:
- **0-30**: Trend intact, hold position
- **30-50**: Monitor closely for further weakness
- **50-70**: Consider tightening stops
- **70-100**: Exit signal, trend severely weakened

## Usage

```bash
# Analyze all users
python scripts/trend_weakness_analyzer.py

# Analyze specific users
python scripts/trend_weakness_analyzer.py --users Sai Mom

# Use different API credentials
python scripts/trend_weakness_analyzer.py --user Sai
```

## Output

The analyzer generates:

1. **Console Report**: Shows top positions with highest weakness scores
2. **Excel Report**: Detailed analysis saved to `reports/trend_weakness_*.xlsx`

### Report Contents

- **Summary Sheet**: Overview of all users' portfolios
- **User Sheets**: Detailed analysis for each position including:
  - Ticker symbol
  - Current trend (bull/bear/sideways)
  - Weakness score (0-100)
  - P&L percentage
  - Recommendation (hold/monitor/tighten_stop/exit)
  - Detected weakness patterns

## Recommendations

- **Hold**: Score < 30 - Trend is intact
- **Monitor Closely**: Score 30-50 - Early weakness signs
- **Tighten Stop**: Score 50-70 - Significant weakness
- **Exit Immediately**: Score ≥ 70 - Trend has likely reversed

## Integration with Trading System

This analyzer can be run:
- Daily after market close
- When significant market moves occur
- Before placing new orders
- As part of risk management routine

## Best Practices

1. Run analysis regularly (daily/weekly)
2. Combine with other indicators and risk management
3. Don't rely solely on automated scores
4. Review detected patterns manually for confirmation
5. Consider market context and news events

## Limitations

- Requires sufficient historical data (minimum 20 days)
- Pattern detection is simplified compared to manual analysis
- Does not consider fundamental factors
- May generate false signals in choppy markets

## Future Enhancements

1. Add more sophisticated pattern recognition
2. Include volume analysis
3. Consider market breadth indicators
4. Add machine learning for pattern weights
5. Include options data for additional signals