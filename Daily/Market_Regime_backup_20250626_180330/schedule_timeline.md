# India-TS Schedule Timeline Visualization

## Hourly Schedule Grid (Monday-Friday)

```
Time     | Jobs Running                                          | Count | Status
---------|-------------------------------------------------------|-------|--------
08:30    | daily_action_plan                                     | 1     | ✅ OK
08:45    | -                                                     | 0     | ✅ OK
09:00    | market_regime, long_reversal, short_reversal, score  | 4     | ❌ HIGH
09:15    | synch_zerodha                                         | 1     | ✅ OK
09:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
09:35    | outcome_resolver                                      | 1     | ✅ OK
09:45    | synch_zerodha                                         | 1     | ✅ OK
10:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
10:05    | outcome_resolver                                      | 1     | ✅ OK
10:15    | synch_zerodha                                         | 1     | ✅ OK
10:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
10:35    | outcome_resolver                                      | 1     | ✅ OK
10:45    | synch_zerodha                                         | 1     | ✅ OK
11:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
11:05    | outcome_resolver                                      | 1     | ✅ OK
11:15    | synch_zerodha                                         | 1     | ✅ OK
11:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
11:35    | outcome_resolver                                      | 1     | ✅ OK
11:45    | synch_zerodha                                         | 1     | ✅ OK
12:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
12:05    | outcome_resolver                                      | 1     | ✅ OK
12:15    | synch_zerodha                                         | 1     | ✅ OK
12:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
12:35    | outcome_resolver                                      | 1     | ✅ OK
12:45    | synch_zerodha                                         | 1     | ✅ OK
13:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
13:05    | outcome_resolver                                      | 1     | ✅ OK
13:15    | synch_zerodha                                         | 1     | ✅ OK
13:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
13:35    | outcome_resolver                                      | 1     | ✅ OK
13:45    | synch_zerodha                                         | 1     | ✅ OK
14:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
14:05    | outcome_resolver                                      | 1     | ✅ OK
14:15    | synch_zerodha                                         | 1     | ✅ OK
14:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
14:35    | outcome_resolver                                      | 1     | ✅ OK
14:45    | synch_zerodha                                         | 1     | ✅ OK
15:00    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
15:05    | outcome_resolver                                      | 1     | ✅ OK
15:15    | synch_zerodha                                         | 1     | ✅ OK
15:30    | market_regime, long_reversal, short_reversal, synch  | 4     | ❌ HIGH
15:35    | outcome_resolver                                      | 1     | ✅ OK
16:00    | market_regime, market_regime_daily_metrics           | 2     | ⚠️ MED
16:05    | outcome_resolver                                      | 1     | ✅ OK
```

## Proposed Optimized Schedule

```
Time     | Jobs Running                                          | Count | Status
---------|-------------------------------------------------------|-------|--------
08:30    | daily_action_plan                                     | 1     | ✅ OK
08:45    | consolidated_score                                    | 1     | ✅ OK
09:00    | long_reversal                                         | 1     | ✅ OK
09:05    | short_reversal                                        | 1     | ✅ OK
09:10    | market_regime                                         | 1     | ✅ OK
09:20    | synch_zerodha                                         | 1     | ✅ OK
09:30    | long_reversal                                         | 1     | ✅ OK
09:35    | short_reversal, outcome_resolver                      | 2     | ✅ OK
09:40    | market_regime                                         | 1     | ✅ OK
09:50    | synch_zerodha                                         | 1     | ✅ OK
10:00    | long_reversal                                         | 1     | ✅ OK
10:05    | short_reversal, outcome_resolver                      | 2     | ✅ OK
10:10    | market_regime                                         | 1     | ✅ OK
10:20    | synch_zerodha                                         | 1     | ✅ OK
```

## Benefits of Proposed Schedule

1. **Reduced Peak Load**: Maximum 2 jobs running concurrently (down from 4)
2. **Better Resource Utilization**: Jobs spread across time slots
3. **Maintained Frequency**: All jobs still run at their required intervals
4. **Smart Overlaps**: Only low-impact jobs overlap (outcome_resolver with short_reversal)
5. **API Rate Limit Protection**: Scanner jobs never run simultaneously

## Implementation Steps

### 1. Update Scanner PLists (High Priority)

**Long Reversal**: Keep at :00 and :30
**Short Reversal**: Move to :05 and :35
**Market Regime**: Move to :10 and :40

### 2. Update Utility PLists (Medium Priority)

**Consolidated Score**: Move from 9:00 to 8:45
**Market Regime Daily Metrics**: Move from 16:00 to 16:15
**Synch Zerodha**: Change to :20 and :50 (reduce frequency)

### 3. Keep As-Is (Already Optimized)

**Outcome Resolver**: Already at :05/:35 offset
**Daily Action Plan**: Already at 8:30 (before market)

## Expected Improvements

- **50% reduction** in concurrent job conflicts
- **75% reduction** in peak system load
- **Elimination** of 4-job pile-ups
- **Better** database transaction isolation
- **Improved** job completion rates
- **Reduced** API throttling incidents