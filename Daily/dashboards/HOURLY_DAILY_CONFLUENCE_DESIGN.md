# Hourly-Daily Confluence Dashboard Enhancement Design

## Overview
Enhancement to capture early momentum moves by combining hourly and daily persistence data in the VSR dashboard.

## Key Insight
"If something passes hourly and stays persistent in Daily tracker, it gives a solid move. This helps catch moves earlier."

## Proposed Dashboard Enhancements

### 1. New Confluence Section
Add a new section to the VSR dashboard showing:

#### A. Confluence Tickers (🎯 Perfect Setup)
- Tickers appearing in BOTH hourly and daily scans
- Sorted by confluence score (combination of hourly + daily strength)
- Visual indicators:
  - 🟢 Strong Signal (both timeframes > 5% momentum)
  - 🟡 Medium Signal (both timeframes > 3% momentum)
  - 🔵 Building Signal (mixed momentum)

#### B. Emerging Tickers (🚀 Early Movers)
- Tickers with strong hourly persistence NOT YET in daily
- These are potential early entries
- Show:
  - Hourly appearances count
  - Average hourly momentum
  - Time since first appearance
  - "Readiness" indicator for daily transition

#### C. Momentum Consistency Badge
- For existing daily tickers, show if they have recent hourly support
- Visual badge: ⚡ (Has hourly support) or ⏸️ (No recent hourly activity)

### 2. Enhanced Ticker Cards
Modify existing ticker display to show:
```
┌─────────────────────────────────┐
│ TICKER  ⚡ H:3 D:5  Score: 95   │
│ ₹1,234.56  ↑5.2%  VSR: 12.5     │
│ Hourly: ●●●○○  Daily: ●●●●●     │
│ Confluence: STRONG 🟢            │
└─────────────────────────────────┘
```

Where:
- H:3 = Hourly appearances
- D:5 = Daily appearances
- Dots show momentum strength history
- Confluence indicator shows signal quality

### 3. Alert System Design

#### Alert Types:
1. **Confluence Alert** 🎯
   - Triggered when ticker appears in both hourly AND daily with strong momentum
   - Priority: HIGH
   - Message: "TICKER showing strong hourly+daily confluence"

2. **Emerging Alert** 🚀
   - Triggered when hourly ticker shows 3+ appearances with >5% avg momentum
   - Priority: MEDIUM
   - Message: "TICKER building momentum in hourly scans"

3. **Transition Alert** ✅
   - Triggered when hourly ticker transitions to daily
   - Priority: HIGH
   - Message: "TICKER confirmed - moved from hourly to daily"

#### Alert Delivery Options:
- Dashboard notification banner
- Log file entries for automated parsing
- Optional: Telegram/Discord webhook integration

### 4. API Enhancements

New endpoints for the VSR dashboard:

#### `/api/confluence-analysis`
```json
{
  "confluence_tickers": [
    {
      "ticker": "AFFLE",
      "hourly_appearances": 3,
      "daily_appearances": 5,
      "confluence_score": 85,
      "signal": "STRONG",
      "momentum_trend": "ACCELERATING"
    }
  ],
  "emerging_tickers": [...],
  "alerts": [...]
}
```

#### `/api/ticker-confluence/<ticker>`
Detailed confluence data for a specific ticker

### 5. Implementation Without Service Changes

#### Option 1: Scheduled Analysis Script
- Run `hourly_daily_confluence_analyzer.py` every 30 minutes via cron/plist
- Output JSON files that dashboard reads
- Dashboard polls these files for updates

#### Option 2: Dashboard-Side Analysis
- Dashboard loads both persistence files directly
- Performs confluence analysis on each refresh
- Caches results for 5 minutes to avoid repeated calculations

#### Option 3: Lightweight Monitoring Service
- Create a separate confluence monitor (not modifying existing services)
- Reads both persistence files
- Generates alerts and confluence data
- Dashboard reads from this monitor's output

### 6. Visual Design Mockup

```
┌─ VSR Tracker Dashboard ─────────────────────────┐
│                                                 │
│ 🎯 CONFLUENCE OPPORTUNITIES (Hourly + Daily)    │
│ ┌─────────────────────────────────────────────┐│
│ │ AFFLE     Score: 95  H:3 D:5  🟢 STRONG    ││
│ │ VBL       Score: 87  H:3 D:4  🟢 STRONG    ││
│ │ TORNTPHARM Score: 82  H:3 D:3  🟡 MEDIUM   ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ 🚀 EMERGING (Strong Hourly, Pre-Daily)         │
│ ┌─────────────────────────────────────────────┐│
│ │ LAURUSLABS  H:4  Avg: 6.5%  🔥 HIGH        ││
│ │ AMBER       H:3  Avg: 5.2%  ⚡ MEDIUM      ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ 📊 DAILY TRACKERS (Original View)              │
│ ┌─────────────────────────────────────────────┐│
│ │ [Existing daily ticker display]             ││
│ └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

## Benefits

1. **Earlier Entry Signals**: Catch moves when they start in hourly before daily confirmation
2. **Higher Confidence**: Confluence of multiple timeframes reduces false signals
3. **Risk Management**: See if daily positions still have hourly support
4. **Trend Acceleration**: Identify when existing trends are accelerating

## Next Steps

1. Run the confluence analyzer to verify data quality
2. Choose implementation approach (Option 1, 2, or 3)
3. Create mockup/prototype of dashboard changes
4. Test with historical data to validate signal quality
5. Implement chosen solution

## Success Metrics

- Confluence tickers show higher average gains than single-timeframe signals
- Emerging tickers successfully transition to daily 60%+ of the time
- Earlier entry points captured (measured by entry vs eventual high)
- Reduced false signals through multi-timeframe confirmation