# Volume-Price Anomaly Detection Guide

## Overview

The Volume-Price Anomaly Detection system is a sophisticated pattern recognition feature integrated into both SL_watchdog.py and SL_watchdog_regime.py. It identifies potential exhaustion patterns by analyzing the relationship between volume and price movements, helping traders anticipate tops and reversals before positions hit stop losses.

## Key Concepts

### Volume-Price Divergence
When volume increases significantly but price movement remains limited, it often indicates:
- Distribution at tops (selling into strength)
- Accumulation at bottoms (buying into weakness)
- Exhaustion of the current trend
- Potential reversal points

### Volume Efficiency
The ratio of price momentum to volume ratio. Lower efficiency suggests that increased volume is not translating into proportional price movement, indicating potential exhaustion.

## Anomaly Patterns Detected

### 1. Volume Exhaustion (3 points)
- **Condition**: Volume > 3x 20-day average AND 5-day momentum < 5%
- **Interpretation**: Heavy volume but limited price progress
- **Risk Level**: HIGH
- **Example**: A stock trades 7.5x normal volume but only moves 4.7% in 5 days

### 2. Efficiency Breakdown (2 points)
- **Condition**: Volume efficiency < 0.5 AND volume > 2x average
- **Calculation**: Efficiency = 5-day momentum % / volume ratio
- **Interpretation**: Declining effectiveness of volume in moving price
- **Risk Level**: MEDIUM-HIGH

### 3. Narrow Range (1 point)
- **Condition**: Volume > 2x average AND daily range < 1.5%
- **Interpretation**: High activity but price constrained in tight range
- **Risk Level**: MEDIUM
- **Often precedes**: Breakout or breakdown

### 4. Price Rejection (2 points)
- **Condition**: Volume > 2x average AND close in bottom 30% of day's range
- **Interpretation**: Selling pressure overwhelms buying at highs
- **Risk Level**: MEDIUM-HIGH
- **Classic sign**: Failed breakout attempt

## Risk Scoring System

Total anomaly score ranges from 0-8:

| Score | Risk Level | Action | Log Symbol |
|-------|------------|--------|------------|
| 0-1   | None       | Continue normal monitoring | - |
| 2     | Low        | Informational logging only | 📊 |
| 3     | Medium     | Monitor closely, prepare exit plan | ⚠️ |
| 4+    | High       | Consider tightening stops or reducing position | 🚨 |

## Implementation Details

### Configuration
Add to config.ini (optional - defaults shown):
```ini
[VOLUME_ANOMALY]
anomaly_warning_enabled = true   # Enable/disable the feature
anomaly_check_interval = 300     # Check every 5 minutes
```

### Data Requirements
- Requires 20 days of historical data for baseline
- Uses Zerodha historical data API
- Calculates rolling averages and ratios

### Check Frequency
- Runs every 5 minutes (configurable)
- Only during market hours
- Skips if insufficient historical data

## Log Output Examples

### High Risk Warning:
```
🚨 HIGH EXHAUSTION RISK - JAGSNPHARM: Score 5/8
   Volume: 7.5x | Momentum: 4.7% | Efficiency: 0.63
   - Volume exhaustion: 7.5x volume but only 4.7% move
   - Efficiency breakdown: 0.63 momentum/volume ratio
   ⚠️ RECOMMENDATION: Consider tightening stops or reducing position
```

### Medium Risk Warning:
```
⚠️ MEDIUM EXHAUSTION RISK - ANANDRATHI: Score 3/8
   Volume: 6.7x | Momentum: 4.6%
   - Volume exhaustion: 6.7x volume but only 4.6% move
   💡 RECOMMENDATION: Monitor closely, prepare exit plan
```

### Portfolio Summary:
```
🚨 VOLUME-PRICE ANOMALY ALERTS:
  JAGSNPHARM: HIGH RISK (Score: 5/8) - Volume: 7.5x, Momentum: 4.7%
  ANANDRATHI: MEDIUM RISK (Score: 3/8) - Volume: 6.7x, Momentum: 4.6%
```

## Real-World Examples

### Example 1: JAGSNPHARM (July 2024)
- Volume: 7.52x average
- 5-day momentum: 4.73%
- Volume efficiency: 0.63
- Anomaly score: 5/8 (HIGH)
- Outcome: Stock reversed within 2 days

### Example 2: GLENMARK (July 2024)
- Volume: 8.27x average
- 5-day momentum: 18.83%
- Volume efficiency: 2.28
- Anomaly score: 2/8 (LOW)
- Outcome: Continued trending (good efficiency)

## Best Practices

1. **Don't Act on Warnings Alone**: Use as additional confirmation with other indicators
2. **Watch for Persistence**: Multiple consecutive warnings increase reliability
3. **Consider Market Context**: Anomalies more significant in trending markets
4. **Volume Quality**: Check if volume is institutional or retail driven
5. **Time of Day**: End-of-day anomalies often more significant

## Integration with Trading Workflow

1. **Morning Review**: Check previous day's anomaly alerts
2. **Intraday Monitoring**: Watch for real-time warnings in logs
3. **Position Management**: 
   - Score 3: Review position, ensure stops are appropriate
   - Score 4+: Consider partial exits or tighter stops
4. **End-of-Day**: Review portfolio summary for all anomalies

## Limitations

1. **No Automatic Actions**: System only warns, doesn't execute trades
2. **Historical Data Dependency**: Requires 20+ days of data
3. **Not Predictive**: Identifies current conditions, not future movements
4. **Market Conditions**: Less effective in news-driven moves
5. **Small Caps**: May generate false signals on illiquid stocks

## Future Enhancements

1. **Machine Learning**: Train models on historical anomaly outcomes
2. **Sector Analysis**: Adjust thresholds by sector characteristics
3. **Automatic Stop Tightening**: Optionally tighten stops on high scores
4. **Backtesting Integration**: Measure historical effectiveness
5. **Custom Thresholds**: User-configurable scoring weights

## Troubleshooting

### No Anomaly Warnings Appearing
- Check if `anomaly_warning_enabled = true` in config
- Verify Zerodha API access for historical data
- Ensure sufficient historical data (20+ days)

### Too Many False Warnings
- Increase thresholds in code
- Filter for specific market cap ranges
- Adjust check interval to reduce frequency

### Performance Impact
- Increase `anomaly_check_interval` if needed
- Disable for specific tickers if required
- Check API rate limits

## Technical Architecture

The system integrates seamlessly into the existing SL watchdog flow:

1. **Data Collection**: Fetches 20-day historical data via Zerodha API
2. **Metric Calculation**: Computes volume ratios, momentum, efficiency
3. **Pattern Detection**: Checks for 4 anomaly patterns
4. **Scoring**: Calculates weighted anomaly score (0-8)
5. **Logging**: Outputs warnings based on risk level
6. **Cleanup**: Removes data when positions are closed

This non-intrusive design ensures the core stop loss functionality remains unaffected while providing valuable additional insights.