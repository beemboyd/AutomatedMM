# India-TS Scheduled Jobs Audit

## Summary of Key Scheduled Jobs

### 1. Market Regime Analysis Jobs

| Job Name | Schedule | Purpose | Potential Conflicts |
|----------|----------|---------|-------------------|
| **com.india-ts.market_regime_analysis** | Every 30 min from 9:00-16:00 (Mon-Fri) | Runs market_regime_analyzer.py | Overlaps with reversal scanners at :00 and :30 |
| **com.india-ts.market_regime_daily_metrics** | Daily at 16:00 | Calculates daily metrics | Conflicts with 16:00 market_regime_analysis run |
| **com.india-ts.outcome_resolver** | Every 30 min offset by 5/35 min (9:35, 10:05, 10:35, etc.) | Resolves prediction outcomes | No conflicts - intelligently offset |

### 2. Trading Scanner Jobs

| Job Name | Schedule | Purpose | Potential Conflicts |
|----------|----------|---------|-------------------|
| **com.india-ts.long_reversal_daily** | Every 30 min from 9:00-15:30 (Mon-Fri) | Long reversal scanner | Exact overlap with market_regime_analysis |
| **com.india-ts.short_reversal_daily** | Every 30 min from 9:00-15:30 (Mon-Fri) | Short reversal scanner | Exact overlap with market_regime_analysis & long_reversal |

### 3. Utility Jobs

| Job Name | Schedule | Purpose | Potential Conflicts |
|----------|----------|---------|-------------------|
| **com.india-ts.consolidated_score** | Daily at 9:00 (Mon-Fri) | Action plan scoring | Conflicts with 9:00 scanners & market regime |
| **com.india-ts.daily_action_plan** | Daily at 8:30 (Mon-Fri) | Daily action plan generation | No conflicts - runs before market hours |
| **com.india-ts.synch_zerodha_local** | Every 15 min from 9:15-15:30 (Mon-Fri) | Sync with Zerodha positions | Overlaps with scanners at :15, :30, :45, :00 |

## Detailed Time Conflict Analysis

### Major Conflict Points (3+ jobs running simultaneously):

1. **9:00 AM** - 4 jobs conflict:
   - market_regime_analysis
   - long_reversal_daily
   - short_reversal_daily
   - consolidated_score

2. **Every 30 minutes (9:30, 10:00, 10:30... 15:30)** - 3 jobs conflict:
   - market_regime_analysis
   - long_reversal_daily
   - short_reversal_daily

3. **Every 15-minute mark** - synch_zerodha_local overlaps with:
   - At :00 and :30 - all scanners
   - At :15 and :45 - only synch runs

4. **16:00** - 2 jobs conflict:
   - market_regime_analysis (last run)
   - market_regime_daily_metrics

## Recommendations

### 1. **Stagger Scanner Execution**
   - **Current**: All scanners run at :00 and :30
   - **Suggested**: 
     - Long reversal: :00 and :30
     - Short reversal: :05 and :35
     - Market regime: :10 and :40
   - **Benefit**: Reduces system load and potential race conditions

### 2. **Offset Consolidated Score**
   - **Current**: Runs at 9:00 (conflicts with scanners)
   - **Suggested**: Run at 8:45 or 9:15
   - **Benefit**: Avoids conflict with market open activities

### 3. **Adjust Market Regime Daily Metrics**
   - **Current**: Runs at 16:00 (conflicts with last market_regime_analysis)
   - **Suggested**: Run at 16:15
   - **Benefit**: Ensures all intraday analysis is complete before daily metrics

### 4. **Optimize Synch Zerodha**
   - **Current**: Every 15 minutes
   - **Suggested**: Every 30 minutes at :20 and :50
   - **Benefit**: Runs between scanner cycles, reducing conflicts

### 5. **Outcome Resolver - NO CHANGES NEEDED**
   - Already intelligently offset by 5/35 minutes
   - No conflicts with other jobs
   - Good design pattern to follow

## Resource Impact Analysis

### Peak Load Times:
- **9:00 AM**: Highest load (4 concurrent jobs)
- **Every 30 minutes**: High load (3 concurrent jobs)
- **Every 15 minutes**: Medium load (1-4 jobs)

### Potential Issues:
1. **Database Lock Contention**: Multiple jobs may try to update same tables
2. **API Rate Limits**: Multiple scanners hitting market data APIs simultaneously
3. **CPU/Memory Spikes**: Resource intensive operations running concurrently
4. **Log File Conflicts**: Multiple jobs writing to similar log locations

## Implementation Priority

1. **High Priority**: Stagger the three main scanners (market_regime, long_reversal, short_reversal)
2. **Medium Priority**: Adjust consolidated_score and market_regime_daily_metrics timing
3. **Low Priority**: Optimize synch_zerodha_local frequency

## Additional Observations

1. **Good Practices Found**:
   - outcome_resolver has intelligent offset scheduling
   - daily_action_plan runs before market hours
   - All jobs have proper logging configured

2. **Areas for Improvement**:
   - No apparent job dependency management
   - No built-in retry mechanisms visible
   - Could benefit from a job orchestrator or queue system

3. **Missing Components**:
   - No visible job monitoring/alerting
   - No dead letter queue for failed jobs
   - No job execution history tracking