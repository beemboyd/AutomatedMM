# VSR Momentum Tracker Documentation

## Overview
The VSR (Volume Spread Ratio) Momentum Tracker is a real-time monitoring system that analyzes ticker momentum using hourly data with minute-by-minute updates. It's designed to identify scaling opportunities in daily timeframe trading by detecting momentum builds early.

## Core Concept
- **Data Timeframe**: Hourly candles (clean signals, less noise)
- **Scoring Frequency**: Every minute (high responsiveness)
- **Purpose**: Detect momentum builds for position scaling in daily trading

## Technical Implementation

### Data Sources
- **VSR Calculation**: 15 days of hourly data (ensures 50+ data points)
- **Current Price/Volume**: 1-minute data for real-time updates
- **Ticker Universe**: Latest Long_Reversal_Daily_*.xlsx files

### VSR Scoring Algorithm (0-100 scale)
```python
# Base VSR scoring (based on hourly data)
if vsr_ratio > 1.0: score += 20
if vsr_ratio > 2.0: score += 25
if vsr_ratio > 3.0: score += 15
if vsr_roc > 50: score += 15
if volume_ratio > 1.5: score += 10
if momentum_hourly > 0: score += 5

# Momentum build bonus (key for scaling)
score += momentum_build_points
```

### Momentum Build Detection
Analyzes last 3 hourly bars to detect VSR acceleration:
- **📈20**: Strong momentum build (VSR rising for 3+ consecutive hours)
- **📈10**: Moderate momentum build (VSR rising for 2+ consecutive hours)
- **0**: No momentum build detected

## Log Format
```
[User] TICKER      | Score: XXX | VSR: X.XX | Price: ₹XXX.XX | Vol: XXX,XXX | Momentum: X.X% | Build: 📈XX | Trend: XXX | Sector: XXX
```

### Field Descriptions
- **Score**: Overall VSR momentum score (0-100)
- **VSR**: Volume Spread Ratio from hourly data
- **Price**: Current market price (minute data)
- **Vol**: Current volume (minute data)
- **Momentum**: 5-hour price momentum percentage
- **Build**: Momentum build indicator (0, 📈10, 📈20)
- **Trend**: Price/score trend vs previous cycle (📈💹, 📉🔻, ➡️)
- **Sector**: Stock sector classification

## Service Configuration

### Files
- **Service**: `/Daily/services/vsr_tracker_service.py`
- **Start Script**: `/Daily/services/start_vsr_tracker.sh`
- **Stop Script**: `/Daily/services/stop_vsr_tracker.sh`
- **Status Script**: `/Daily/services/status_vsr_tracker.sh`

### Service Management
```bash
# Start service
./start_vsr_tracker.sh [-u USER]

# Check status
./status_vsr_tracker.sh [-u USER]

# Stop service
./stop_vsr_tracker.sh [-u USER]
```

### Log Files
- **Location**: `/Daily/logs/vsr_tracker/vsr_tracker_YYYYMMDD.log`
- **Rotation**: Daily log files
- **Format**: Timestamped entries with structured data

## Trading Strategy Integration

### Current System Compatibility
- **Entry Source**: Long_Reversal_Daily files (Brooks reversal patterns)
- **Score Filter**: VSR score ≥ 60 for quality filtering
- **Product Type**: CNC (delivery) positions
- **Timeframe**: Daily entries with intraday momentum monitoring

### Recommended Usage Patterns

#### 1. Initial Position Entry
```python
# Filter Long_Reversal_Daily candidates
if vsr_score >= 60 and brooks_score == "5/7":
    # Consider for initial entry
    entry_confidence = "HIGH" if vsr_score >= 80 else "MEDIUM"
```

#### 2. Position Scaling Opportunities
```python
# Scale up on momentum builds
if momentum_build >= 10 and vsr_score >= 70:
    # Add to existing position
    scale_factor = 1.5 if momentum_build == 20 else 1.25
```

#### 3. Exit Timing Considerations
```python
# Monitor for momentum exhaustion
if momentum_build == 0 and vsr_score < 50:
    # Consider position review
    exit_signal = "WEAK_MOMENTUM"
```

## Performance Metrics

### High-Quality Signals
- **Score ≥ 80**: High conviction plays
- **Score 60-79**: Medium conviction with momentum build
- **Score < 60**: Low conviction, avoid new entries

### Momentum Build Significance
- **📈20**: Strong acceleration, excellent for scaling
- **📈10**: Moderate acceleration, good for small additions
- **0**: No acceleration, hold current positions

## Monitoring and Analysis

### Daily Observation Points
1. **High Score Tickers**: Monitor tickers with score ≥ 50
2. **Momentum Builds**: Track frequency and duration of builds
3. **Trend Persistence**: Observe how long momentum builds last
4. **False Signals**: Document momentum builds that don't follow through

### Key Metrics to Track
- **Score Distribution**: Range and frequency of scores
- **Momentum Build Frequency**: How often builds occur
- **Build Duration**: How long momentum builds persist
- **Success Rate**: Correlation between builds and price moves

## Log Analysis Commands

### Real-time Monitoring
```bash
# View live logs
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log

# High scores only (≥50)
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log | grep -E 'Score: [5-9][0-9]|Score: 100'

# Momentum builds only
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log | grep "📈"

# HIGH SCORE + BUILD (Best scaling candidates) - Score ≥80 with any build
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log | grep -E 'Score: ([89][0-9]|100).*Build: 📈'

# STRONG MOMENTUM BUILDS ONLY (Build = 20)
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log | grep 'Build: 📈20'

# PERFECT SCORE WITH BUILD (Score = 100 + any build)
tail -f ../logs/vsr_tracker/vsr_tracker_YYYYMMDD.log | grep -E 'Score: 100.*Build: 📈'
```

### Historical Analysis
```bash
# Daily summary of high scores
grep "Score: [5-9][0-9]" vsr_tracker_YYYYMMDD.log | wc -l

# Count momentum builds
grep "📈" vsr_tracker_YYYYMMDD.log | wc -l

# Top scoring tickers
grep "Score: [89][0-9]" vsr_tracker_YYYYMMDD.log | sort -k6 -nr
```

## Future Enhancements

### Planned Improvements
1. **Historical Performance**: Track success rates of momentum builds
2. **Alert System**: Notifications for high-conviction setups
3. **Backtesting**: Historical validation of VSR momentum signals
4. **Risk Metrics**: Position sizing based on VSR conviction
5. **Sector Analysis**: Momentum patterns by sector

### Research Areas
1. **Optimal Build Thresholds**: Fine-tune momentum build detection
2. **Score Calibration**: Validate scoring algorithm effectiveness
3. **Timeframe Optimization**: Test different data periods
4. **Exit Signals**: Develop VSR-based exit criteria

## Troubleshooting

### Common Issues
1. **Insufficient Data Points**: Extend historical data period
2. **API Rate Limits**: Implement proper delays between requests
3. **Service Crashes**: Check log files for error patterns
4. **Memory Usage**: Monitor for data cache buildup

### Data Quality Checks
- **Missing Tickers**: Verify Long_Reversal_Daily file integrity
- **Stale Data**: Confirm real-time data feed connectivity
- **Score Anomalies**: Investigate extremely high/low scores

## Version History
- **v1.0**: Initial VSR tracker with 5-minute data
- **v1.1**: Enhanced with hourly data and momentum build detection
- **v1.2**: Added minute-by-minute scoring for better responsiveness

## Contact and Support
For issues or enhancements, refer to system logs and documentation in the Daily folder.

---

**Last Updated**: July 16, 2025
**Author**: Trading System Development Team
**File Location**: `/Daily/VSR_MOMENTUM_TRACKER.md`