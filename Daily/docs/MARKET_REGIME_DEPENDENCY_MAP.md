# Market Regime Dashboard & Services Dependency Map

## Overview
The Market Regime system analyzes market conditions and provides regime classifications (bull/bear/choppy) with alerts on changes. This document maps all dependencies for quick troubleshooting.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MARKET REGIME SYSTEM (Port 8080)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  DATA SOURCES                    ANALYSIS                    OUTPUTS             │
│  ────────────                    ────────                    ───────             │
│                                                                                  │
│  ┌─────────────────┐            ┌─────────────────┐        ┌──────────────┐    │
│  │ Long Reversal   │───────────▶│ Market Regime   │───────▶│ Dashboard    │    │
│  │ Daily Scanner   │            │ Analyzer        │        │ (Port 8080)  │    │
│  └─────────────────┘            │ (5 min cycle)  │        └──────────────┘    │
│                                 └────────┬────────┘                            │
│  ┌─────────────────┐                    │                  ┌──────────────┐    │
│  │ Short Reversal  │                    ▼                  │ Telegram     │    │
│  │ Daily Scanner   │            ┌─────────────────┐        │ Alerts on    │    │
│  └─────────────────┘            │ Regime Change   │───────▶│ Regime       │    │
│                                 │ Notifier        │        │ Changes      │    │
│  ┌─────────────────┐            └─────────────────┘        └──────────────┘    │
│  │ Market Breadth  │                    │                                      │
│  │ Scanner         │                    ▼                                      │
│  └─────────────────┘            ┌─────────────────┐        ┌──────────────┐    │
│                                 │ Regime History  │        │ SQLite DB    │    │
│  ┌─────────────────┐            │ Tracker         │───────▶│ regime_      │    │
│  │ Index Data      │            └─────────────────┘        │ learning.db  │    │
│  │ (NIFTY, etc)    │                                       └──────────────┘    │
│  └─────────────────┘                                                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Service Dependencies

### 1. Market Regime Analyzer (Core Service)
**Service**: `com.india-ts.market_regime_analyzer_5min`
**Schedule**: Every 5 minutes during market hours

#### Input Dependencies:
- **Reversal Scanner Results**:
  - Long: `/Daily/results/Long_Reversal_Daily_*.xlsx`
  - Short: `/Daily/results-s/Short_Reversal_Daily_*.xlsx`
  - Requirement: Must have recent scans (within last hour)

- **Market Breadth Data**:
  - Source: `/Daily/Market_Regime/breadth_data/market_breadth_*.json`
  - Updated by: Market Breadth Scanner

- **Index Data**:
  - Source: Real-time via KiteConnect API
  - Indices: NIFTY 50, NIFTY MIDCAP 100, NIFTY SMLCAP 100

#### Output Files:
- **Latest Regime**: `/Daily/Market_Regime/regime_analysis/latest_regime_summary.json`
- **Regime History**: `/Daily/Market_Regime/data/regime_history.json`
- **Performance Metrics**: `/Daily/Market_Regime/data/performance_metrics.json`
- **Database**: `/data/regime_learning.db`

### 2. Market Breadth Dashboard (Port 8080)
**URL**: http://localhost:8080/
**Service**: Started via `start_market_breadth_dashboard.sh`

#### Dependencies:
- **Data Files**:
  - Latest regime: `regime_analysis/latest_regime_summary.json`
  - Regime history: `data/regime_history.json`
  - Breadth data: `breadth_data/market_breadth_*.json`
  - Historical breadth: `historical_breadth_data/sma_breadth_historical_latest.json`

- **Real-time Updates**:
  - Auto-refreshes every 30 seconds
  - Reads latest files from disk

### 3. Regime Change Notifier (NEW)
**Component**: `regime_change_notifier.py`
**Trigger**: Called after each regime analysis

#### Dependencies:
- **Current Regime**: `regime_analysis/latest_regime_summary.json`
- **State File**: `data/regime_notifier_state.json`
- **Telegram**: Uses `alerts.telegram_notifier.TelegramNotifier`

#### Alert Conditions:
- Regime changes from previous state
- Sends to Telegram channel configured in config.ini

## Key Components & Their Roles

### Analysis Components:
1. **TrendStrengthCalculator** - Calculates bull/bear ratio from reversals
2. **MarketRegimePredictor** - ML model for regime prediction
3. **ConfidenceCalculator** - Calculates confidence in regime
4. **RegimeSmoother** - Prevents rapid regime oscillations
5. **IndexSMAAnalyzer** - Analyzes index positions vs SMA20
6. **BreadthRegimeConsistencyChecker** - Ensures breadth aligns with regime
7. **RegimeHistoryTracker** - Tracks regime changes over time

### Regime Classifications:
- `strong_uptrend` - Strong bull market
- `uptrend` - Bullish conditions
- `choppy_bullish` - Choppy with bullish bias
- `choppy` - Range-bound market
- `choppy_bearish` - Choppy with bearish bias
- `downtrend` - Bearish conditions
- `strong_downtrend` - Strong bear market

## Configuration Files

### config.ini
```ini
[TELEGRAM]
bot_token = your_token
chat_id = your_chat_id
enabled = yes
```

## Troubleshooting Guide

### Issue: Dashboard shows old data
**Check**:
```bash
# 1. Verify analyzer is running
launchctl list | grep market_regime_analyzer_5min

# 2. Check latest file timestamps
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json

# 3. Check analyzer logs
tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.log
```

### Issue: No regime change alerts
**Check**:
```bash
# 1. Check notifier state
cat /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/data/regime_notifier_state.json

# 2. Verify Telegram config
grep -A5 "[TELEGRAM]" /Users/maverick/PycharmProjects/India-TS/Daily/config.ini

# 3. Test Telegram connection
python3 -c "
from Daily.alerts.telegram_notifier import TelegramNotifier
t = TelegramNotifier()
print('Configured:', t.is_configured())
print('Test:', t.test_connection())
"
```

### Issue: Analyzer not finding scanner results
**Check**:
```bash
# 1. Check scanner results exist
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_$(date +%Y%m%d)*.xlsx
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/results-s/Short_Reversal_Daily_$(date +%Y%m%d)*.xlsx

# 2. Verify scanners are scheduled
launchctl list | grep -E "long_reversal_daily|short_reversal_daily"
```

## Service Control Commands

### Start Services
```bash
# Start dashboard
cd /Users/maverick/PycharmProjects/India-TS/Daily/utils
./start_market_breadth_dashboard.sh

# Start/restart analyzer
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
```

### Check Status
```bash
# All regime-related services
launchctl list | grep -E "market_regime|breadth"

# Dashboard status
curl -s http://localhost:8080 > /dev/null && echo "Dashboard: ✓ Running" || echo "Dashboard: ✗ Not responding"

# Latest regime
python3 -c "
import json
with open('/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json') as f:
    d = json.load(f)
    print(f\"Current Regime: {d['market_regime']['regime']}\")
    print(f\"Confidence: {d['market_regime']['confidence']:.1%}\")
    print(f\"Last Update: {d['timestamp']}\")
"
```

## Data Flow Timeline

```
8:30 AM ─┬─ Reversal scanners start
         └─ Market Breadth scanner starts
         
9:00 AM ─┬─ First scanner results available
         └─ Market Regime Analyzer can start
         
9:05 AM ─── First regime analysis complete
         
9:10 AM ─── Regime updates every 5 minutes
         
3:30 PM ─── Last regime update of the day
```

## Quick Diagnostic Script

Save as `check_regime_status.sh`:
```bash
#!/bin/bash

echo "=== Market Regime System Status ==="
echo ""

# Check services
echo "1. Services:"
launchctl list | grep market_regime_analyzer_5min | awk '{print "   Analyzer: PID " $1}'
ps aux | grep "market_regime_dashboard" | grep -v grep > /dev/null && echo "   Dashboard: Running" || echo "   Dashboard: Not running"
echo ""

# Check data freshness
echo "2. Data Freshness:"
if [ -f "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json" ]; then
    mod_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json")
    echo "   Latest regime update: $mod_time"
fi
echo ""

# Current regime
echo "3. Current Regime:"
python3 -c "
import json
try:
    with open('/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json') as f:
        d = json.load(f)
        print(f'   Regime: {d[\"market_regime\"][\"regime\"]}')
        print(f'   Confidence: {d[\"market_regime\"][\"confidence\"]:.1%}')
        print(f'   Long Count: {d[\"reversal_counts\"][\"long\"]}')
        print(f'   Short Count: {d[\"reversal_counts\"][\"short\"]}')
except:
    print('   Unable to read regime data')
"
echo ""

# Dashboard
echo "4. Dashboard:"
curl -s http://localhost:8080 > /dev/null && echo "   Status: ✓ Accessible" || echo "   Status: ✗ Not accessible"
echo "   URL: http://localhost:8080/"
```

## Regime Change Alert Format

When a regime changes, the alert will look like:
```
🚨 Market Regime Change Detected

📈 Uptrend
    ⬇️
📉 Strong Downtrend

📊 Current Market Conditions:
• Confidence: 77.5%
• Long Reversals: 20
• Short Reversals: 61
• Market Score: -0.50

📋 Strategy:
Aggressive short positions, avoid longs

⏰ 12:10 PM

Dashboard: http://localhost:8080/
```

---

Last Updated: 2025-08-05