# Sector Rotation Analysis Guide

## Overview
The Sector Rotation Analysis system tracks and analyzes sector performance patterns to identify market cycles, rotation events, and predict future sector leadership changes.

## Key Features

### 1. Sector Performance Tracking
- **Historical Data Storage**: Stores daily sector performance metrics in SQLite database
- **Metrics Tracked**:
  - Percentage of stocks above SMA20/50
  - Average RSI
  - 5-day and 10-day momentum
  - Relative strength scores
  - Sector rankings

### 2. Rotation Event Detection
- **Leadership Changes**: Identifies when market leadership shifts between sectors
- **Emerging Leaders**: Detects sectors moving up 2+ ranks
- **Losing Momentum**: Identifies sectors declining 2+ ranks
- **Event Types**:
  - `LEADERSHIP_CHANGE`: Top sector changes
  - `EMERGING_LEADER`: Sector gaining strength
  - `LOSING_MOMENTUM`: Sector weakening

### 3. Cycle Analysis
- **Cycle Identification**: Detects bullish and bearish cycles for each sector
- **Duration Tracking**: Measures how long sectors maintain leadership
- **Performance Metrics**: Peak and trough performance levels
- **Minimum Cycle**: 20 days to filter out noise

### 4. Market Cycle Phases
The system identifies four main market cycle phases based on sector leadership:

1. **Early Expansion**
   - Leaders: Technology, Consumer Cyclical
   - Characteristics: Risk-on sentiment, growth focus

2. **Mid Expansion**
   - Leaders: Industrials, Basic Materials
   - Characteristics: Broad economic growth

3. **Late Expansion**
   - Leaders: Energy, Utilities
   - Characteristics: Inflation concerns, defensive positioning

4. **Contraction**
   - Leaders: Consumer Defensive, Healthcare
   - Characteristics: Risk-off, flight to quality

### 5. Rotation Predictions
- **Momentum Analysis**: Compares 5-day vs 10-day momentum
- **Volatility Assessment**: Lower rank volatility indicates stable trend
- **Probability Scoring**: 0-100% probability of becoming next leader

## API Endpoints

### 1. `/api/sector-rotation`
Returns comprehensive rotation analysis:
```json
{
  "rotation_events": [...],
  "statistics": {
    "leadership_duration": {...},
    "rotation_frequency": 5,
    "avg_days_between_rotations": 18
  },
  "predictions": [...],
  "current_cycle_phase": "MID_EXPANSION"
}
```

### 2. `/api/sector-cycles/<sector>`
Returns cycle history for specific sector:
```json
{
  "sector": "Technology",
  "cycles": [...],
  "total_cycles": 4,
  "avg_cycle_duration": 45.5
}
```

### 3. `/api/rotation-report`
Comprehensive rotation report with all metrics

## Key Statistics Tracked

### 1. Leadership Duration
- Average days each sector maintains top position
- Helps identify stable vs volatile leadership

### 2. Rotation Frequency
- Number of leadership changes in period
- Higher frequency indicates choppy market

### 3. Momentum Persistence
- Percentage of time sector maintains positive momentum
- Average momentum magnitude

### 4. Cycle Patterns
- Average cycle duration by sector
- Typical peak-to-trough performance ranges

## Using the Analysis

### 1. Portfolio Positioning
- **Early Rotation Signals**: Position in emerging leaders before rotation completes
- **Cycle Phase Awareness**: Adjust risk based on market cycle phase
- **Sector Allocation**: Overweight sectors showing improving relative strength

### 2. Risk Management
- **Late Cycle Indicators**: Reduce risk when defensive sectors lead
- **Rotation Velocity**: High rotation frequency suggests increased volatility

### 3. Timing Decisions
- **Entry Points**: Best when sector shows improving momentum but not yet leader
- **Exit Points**: Consider reducing when sector loses momentum after extended leadership

## Integration with Market Breadth

The sector rotation analysis integrates seamlessly with the Market Breadth Scanner:
- Automatically updates database after each scan
- Provides context for overall market regime
- Enhances position sizing recommendations

## Reports and Monitoring

### Daily Monitoring
- Check `/api/sector-rotation` for latest rotation events
- Monitor prediction scores for emerging opportunities

### Weekly Analysis
- Review rotation frequency trends
- Analyze cycle phase transitions
- Evaluate prediction accuracy

### Monthly Reports
- Comprehensive cycle analysis
- Sector leadership patterns
- Market phase progression

## Technical Implementation

### Database Schema
- `sector_performance`: Daily performance metrics
- `rotation_events`: Detected rotation events
- `sector_cycles`: Identified bull/bear cycles

### Analysis Methods
- **Relative Strength Calculation**: Composite score from multiple metrics
- **Trend Detection**: 5-day moving average of relative strength
- **Cycle Identification**: Trend reversal points with minimum duration

### Performance Considerations
- SQLite database for fast queries
- Efficient data storage with daily updates
- Minimal overhead on Market Breadth Scanner

## Future Enhancements

1. **Machine Learning Integration**
   - Pattern recognition for rotation prediction
   - Anomaly detection for unusual rotations

2. **Advanced Visualizations**
   - Sector rotation wheel
   - Heat maps of relative strength
   - Cycle phase indicators

3. **Alert System**
   - Real-time rotation event notifications
   - Cycle phase change alerts
   - Prediction threshold triggers

4. **Backtesting Framework**
   - Test rotation-based strategies
   - Optimize entry/exit timing
   - Validate prediction accuracy