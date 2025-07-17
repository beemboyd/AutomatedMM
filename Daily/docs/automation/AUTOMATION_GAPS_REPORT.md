# India-TS Automation Gaps Report

## Current Automation Status

### ✅ What's Automated:
1. **Market Scanning** - All scanners run on schedule
2. **Market Analysis** - Regime analysis runs every 30 minutes
3. **Reporting** - Daily action plans and scores generated automatically
4. **Some Dashboards** - Health and regime dashboards run continuously

### ❌ What's NOT Automated:
1. **Order Placement** - All trading scripts require manual execution
2. **SL Watchdog Start** - Credential issues prevent automatic start
3. **Market Breadth Dashboard** - Requires manual startup
4. **Position Management** - No automatic stop loss monitoring

## Critical Missing Automations

### 1. Order Placement Automation
Create scheduled jobs for:
```bash
# Example: Schedule consolidated orders at 9:30 AM
com.india-ts.place_orders_consolidated
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/trading/place_orders_consolidated.py
- Schedule: 9:30 AM weekdays
- Parameters: --user Sai --mode auto

# Example: Schedule Strategy C orders at 10:00 AM
com.india-ts.place_orders_strategyc
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/trading/place_orders_strategyc.py
- Schedule: 10:00 AM weekdays
```

### 2. SL Watchdog Automation
Fix the existing job or create new ones:
```bash
# Fix credential issue in config.ini for 'Mom' user
# OR create new job with correct user
com.india-ts.sl_watchdog_start_sai
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog.py
- Schedule: 9:15 AM weekdays
- Parameters: --user Sai

# Schedule regime-based SL watchdog
com.india-ts.sl_watchdog_regime_start
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/bin/start_sl_watchdog_regime.sh
- Schedule: 9:15 AM weekdays
```

### 3. Market Breadth Dashboard
Create LaunchAgent:
```bash
com.india-ts.market_breadth_dashboard
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/utils/start_market_breadth_dashboard.sh
- KeepAlive: true
- RunAtLoad: true
```

### 4. Master Startup Sequence
Create a master job that ensures everything is running:
```bash
com.india-ts.master_startup
- Script: /Users/maverick/PycharmProjects/India-TS/Daily/utils/master_startup.sh
- Schedule: 9:00 AM weekdays
- Tasks:
  1. Verify all dashboards are running
  2. Start SL watchdog
  3. Check scanner outputs
  4. Send status notification
```

## Safety Considerations

Before automating order placement:
1. Add capital limit checks
2. Implement maximum position limits
3. Add market hours validation
4. Create emergency stop mechanism
5. Add trade logging and notifications

## Implementation Priority

1. **High Priority**: Fix SL Watchdog automation (risk management)
2. **High Priority**: Automate Market Breadth Dashboard
3. **Medium Priority**: Create master startup script
4. **Low Priority**: Automate order placement (requires safety features)

## Next Steps

1. Fix config.ini credentials for SL watchdog
2. Create missing LaunchAgent plists
3. Test automation in paper trading mode
4. Implement safety checks
5. Gradually enable automated trading

---
Generated: 2025-07-14