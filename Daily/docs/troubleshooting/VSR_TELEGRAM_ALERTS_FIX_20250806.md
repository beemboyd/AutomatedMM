# VSR Telegram Alerts Troubleshooting - Root Cause Analysis

**Date:** 2025-08-06  
**Issue:** VSR Telegram notifications not working  
**Resolution:** Fixed with code corrections and threshold adjustments

## Root Causes Identified

### 1. Code Errors in vsr_telegram_service_enhanced.py

#### Issue 1: Missing base_dir Attribute
- **Error:** `AttributeError: 'EnhancedVSRTelegramService' object has no attribute 'base_dir'`
- **Cause:** The class was trying to use `self.base_dir` in `_load_config()` before it was initialized
- **Fix:** Added `self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` before parent class init

#### Issue 2: Method Name Mismatch
- **Error:** `'super' object has no attribute 'run_monitoring_cycle'`
- **Cause:** Parent class `EnhancedVSRTracker` has method `run_tracking_cycle()` not `run_monitoring_cycle()`
- **Fix:** Changed call from `super().run_monitoring_cycle()` to `super().run_tracking_cycle()`

#### Issue 3: Missing check_high_momentum Method
- **Error:** `'EnhancedVSRTelegramService' object has no attribute 'check_high_momentum'`
- **Cause:** Method was being called but not defined in the class
- **Fix:** Added the `check_high_momentum()` method to check momentum and score thresholds

#### Issue 4: Missing Alert Counter Attributes
- **Error:** `'EnhancedVSRTelegramService' object has no attribute 'daily_alerts_count'`
- **Cause:** Attributes `daily_alerts_count` and `hourly_alerts_count` were not initialized
- **Fix:** Added initialization of both counters in `__init__` method

### 2. Configuration Issues

#### Unrealistic Momentum Thresholds
- **Problem:** Momentum threshold was set to 10% (high_momentum_threshold = 10.0)
- **Reality:** Most stocks have momentum between 1-7% during normal trading
- **Fix:** Adjusted thresholds to realistic levels:
  - `high_momentum_threshold = 3.0` (was 10.0)
  - `extreme_momentum_threshold = 5.0` (was 20.0)

#### Hourly Alerts Disabled
- **Problem:** `hourly_telegram_on = no` in config.ini
- **Fix:** Changed to `hourly_telegram_on = yes`

## Verification Steps

1. **Telegram Connection Test:**
   ```python
   # Direct test showed Telegram was working
   ✅ Test message sent successfully
   ```

2. **Service Status Check:**
   - VSR service processing 112 tickers successfully
   - High-scoring tickers identified (GODFRYPHLP: Score 110, SAREGAMA: Score 110)
   - Momentum values: GODFRYPHLP (5.3%), SAREGAMA (6.7%)

3. **After Fix Verification:**
   - Alerts now triggering: "🔥 HIGH MOMENTUM DETECTED: AMBER - Score: 95, Momentum: -3.1%"
   - Telegram messages being sent successfully
   - User confirmed receiving notifications

## Summary

The root cause was a combination of:
1. **Multiple code errors** preventing the service from running properly
2. **Unrealistic configuration thresholds** (10% momentum threshold when most stocks move 1-7%)

The issue was not with Telegram connectivity itself, which was working fine, but with the service logic and thresholds preventing alerts from being triggered.

## Files Modified

1. `/Daily/alerts/vsr_telegram_service_enhanced.py` - Fixed 4 code errors
2. `/Daily/config.ini` - Adjusted momentum thresholds and enabled hourly alerts

## Current Working Configuration

- **high_momentum_threshold:** 3.0%
- **extreme_momentum_threshold:** 5.0%
- **min_score_for_alert:** 60
- **hourly_telegram_on:** yes
- **daily_telegram_on:** yes
- **Telegram Channel ID:** -1002690613302

## Monitoring Commands

```bash
# Check service status
launchctl list | grep vsr-telegram

# View recent logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_enhanced_*.log

# Test Telegram directly
python3 -c "
import sys
sys.path.insert(0, '/Users/maverick/PycharmProjects/India-TS/Daily/alerts')
from telegram_notifier import TelegramNotifier
TelegramNotifier().send_message('Test message')
"
```