# India-TS Schedule Optimization Plan

## Current Problems

### 1. **Severe Conflicts Every 30 Minutes**
At :00 and :30, these 4 jobs run simultaneously:
- `market_regime_analysis` 
- `long_reversal_daily`
- `short_reversal_daily`
- `synch_zerodha_local`

This causes:
- Database lock conflicts
- API rate limiting
- CPU/memory spikes
- Slow/failed executions

### 2. **Redundant Processing**
- Market regime analyzer appears to run its own scanners
- Scanner results not being reused efficiently
- Multiple jobs doing similar work

## Optimized Schedule

### Pre-Market (8:00 - 9:00 AM)
- **8:30** - `daily_action_plan` (prepare for day)
- **8:45** - `consolidated_score` (calculate scores)

### Market Hours (9:00 AM - 4:00 PM)

#### Every 30 Minutes Pattern:
```
:00 - long_reversal_daily
:05 - short_reversal_daily + outcome_resolver  
:10 - market_regime_analysis (uses scanner results)
:20 - synch_zerodha_local
:30 - long_reversal_daily
:35 - short_reversal_daily + outcome_resolver
:40 - market_regime_analysis (uses scanner results)
:50 - synch_zerodha_local
```

### Post-Market (4:00 PM+)
- **4:15** - `market_regime_daily_metrics`
- **4:30** - Final `outcome_resolver` run

## Key Changes

### 1. **Stagger Scanner Executions**
- Long reversal: :00 and :30 (unchanged)
- Short reversal: :05 and :35 (5 min offset)
- Market regime: :10 and :40 (10 min offset)

### 2. **Market Regime Uses Scanner Results**
Instead of running scanners internally, it should:
1. Wait for scanners to complete
2. Load their results from files
3. Process the combined data

### 3. **Reduce Synch Frequency**
- From every 5 minutes to every 30 minutes
- Offset to :20 and :50 to avoid conflicts

## Implementation Commands

```bash
# 1. Unload all agents
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.consolidated_score.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_daily_metrics.plist

# 2. Update the plist files with new schedules

# 3. Reload all agents
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.consolidated_score.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_daily_metrics.plist
```

## Expected Benefits

1. **No More Conflicts**: Max 2 jobs running concurrently
2. **Faster Execution**: No resource contention
3. **Better Data Flow**: Scanners → Market Regime → Predictions
4. **Stable System**: No timeouts or failures

## Monitoring

After implementation, monitor:
```bash
# Check job status
launchctl list | grep india-ts

# Watch for conflicts
tail -f ~/PycharmProjects/India-TS/Market_Regime/logs/*.log

# Verify predictions being made and resolved
sqlite3 ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db \
"SELECT COUNT(*) as total, 
COUNT(CASE WHEN actual_regime IS NOT NULL THEN 1 END) as resolved 
FROM regime_predictions WHERE date(timestamp) = date('now');"
```

## Summary

The new schedule:
- ✅ Eliminates all major conflicts
- ✅ Maintains 30-minute prediction cycle
- ✅ Allows proper data flow between components
- ✅ Reduces system load
- ✅ Enables true learning from outcomes

The `outcome_resolver` is already properly scheduled and doesn't need changes!