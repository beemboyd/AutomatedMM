# Market Regime Implementation Notes - India-TS & US-TS

## Summary of Changes Made

### India-TS Fixes
1. **Trend Score Fix**
   - **Problem**: Dashboard showed trend score as 0 despite correct calculation
   - **Solution**: Added `get_trend_score_from_db()` method in `market_indicators.py`
   - **File**: `/Users/maverick/PycharmProjects/India-TS/Market_Regime/core/market_indicators.py`
   - **Result**: Trend score now displays correctly (changed from 0 to 5.3)

### US-TS Implementation

#### 1. Market Regime System
- **Copied from India-TS**: Entire Market_Regime directory structure
- **Key Modification**: Changed trend score calculation from technical indicators to scanner signal ratio
- **Formula**: `trend_score = long_signals / short_signals`

#### 2. Adaptive Learning System
**Created Files**:
- `learning/adaptive_learner.py` - RandomForest model implementation
- `learning/regime_predictor.py` - Real-time predictions
- `learning/outcome_tracker.py` - Performance tracking
- `learning/config/feature_config.yaml` - Feature definitions
- `learning/config/model_config.yaml` - Model parameters

**Database Schema**:
```sql
-- predictions table
id, timestamp, regime, confidence, trend_score, breadth_score, volatility_score, features

-- outcomes table  
id, prediction_id, actual_regime, outcome_timestamp, market_return

-- learning_progress table
id, timestamp, metric_type, metric_value, description
```

#### 3. Monitoring Tools Created

**Progress Monitor**:
- File: `learning/progress_monitor.py`
- Tracks: Accuracy, learning velocity, regime performance

**Visualization Tools**:
- File: `learning/visualization_tools.py`
- Creates: Performance charts, confusion matrices, learning curves

**Health Dashboards**:
1. `health_check.py` - Command-line health verification
2. `health_monitor_dashboard.py` (Port 8090) - Real-time metrics
3. `health_check_visual.py` (Port 8091) - Comprehensive visual dashboard
4. `generate_health_report.py` - HTML report generation
5. `daily_checklist.md` - Operational guide

#### 4. Service Configuration

**Fixed Timezone Issues**:
- Original: PST times in plist files
- Problem: System timezone was IST
- Solution: Converted all schedules to IST

**Active Services**:
```
com.usts.long_reversal_daily      # Runs every 30 min during market
com.usts.short_reversal_daily     # Runs every 30 min during market
com.usts.market_regime_analysis   # Runs every 30 min during market
com.usts.regime_dashboard         # Always running
com.usts.albrooks.hourly         # Runs hourly
com.usts.market_regime_daily_metrics # Runs at market close
```

**Removed Services**:
- com.usts.place_orders
- com.usts.manage_risk_realtime
- com.usts.market_scan
- com.usts.daily_shutdown

## Key Differences: India-TS vs US-TS

| Component | India-TS | US-TS |
|-----------|----------|--------|
| API | Zerodha (Kite) | Alpaca |
| Market Hours | 9:15-15:30 IST | 9:30-16:00 EST |
| Scanner Schedule | Market hours | 19:00-01:30 IST |
| Trend Calculation | Long/Short ratio | Long/Short ratio |
| Learning DB | regime_learning.db | regime_learning.db |

## Critical Integration Points

### 1. Scanner → Market Regime
- Scanners generate signal files
- Market regime reads latest files
- Calculates trend score from signal counts
- Updates dashboard in real-time

### 2. Market Regime → Learning System
- Every analysis creates a prediction
- Outcomes tracked next day
- Model retrained with new data
- Progress monitored continuously

### 3. Dashboard Integration
- Main dashboard (8089): Shows current regime
- Health monitor (8090): Shows system metrics
- Visual health (8091): Comprehensive overview

## Troubleshooting Guide

### If Trend Score = 0
1. Check scanner files exist in results directory
2. Verify scanners are running
3. Check database connection
4. Review market_indicators.py implementation

### If Scanners Don't Run
1. Check launchctl status
2. Verify timezone in plist files
3. Check Python path in plist
4. Review error logs

### If Learning Not Working
1. Check database exists
2. Verify predictions being created
3. Check daily_metrics service
4. Review outcome tracking

## File Locations Reference

**India-TS**:
- Base: `/Users/maverick/PycharmProjects/India-TS`
- Market Regime: `Market_Regime/`
- Results: `Daily/results/`

**US-TS**:
- Base: `/Users/maverick/PycharmProjects/US-TS`
- Market Regime: `Market_Regime/`
- Results: `Daily/results/`

## Dashboard URLs
- India-TS: http://localhost:7077
- US-TS Main: http://localhost:8089
- US-TS Health: http://localhost:8090
- US-TS Visual: http://localhost:8091

---
Created: June 25, 2025
Purpose: Quick reference for future debugging and enhancements