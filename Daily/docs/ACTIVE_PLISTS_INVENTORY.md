# Active India-TS Plists Inventory
*Last Updated: 2025-07-31 14:50 IST*

## Summary
Total Active Plists: 36

## Dashboard Management (4 plists)

### 1. com.india-ts.dashboard_manager_start.plist
- **Script**: dashboard_manager_start.sh
- **Schedule**: 8:00 AM IST (Mon-Fri)
- **Status**: ✅ Active
- **Purpose**: Starts all dashboards at market open

### 2. com.india-ts.dashboard_manager_stop.plist
- **Script**: dashboard_manager_stop.sh
- **Schedule**: 8:00 PM IST (Mon-Fri)
- **Status**: ✅ Active
- **Purpose**: Stops all dashboards after market hours

### 3. com.india-ts.dashboard_refresh_control.plist
- **Script**: dashboard_refresh_control.py
- **Schedule**: Every 30 minutes
- **Status**: ⚠️ May be redundant
- **Purpose**: Controls dashboard refresh cycles

### 4. com.india-ts.job_manager_dashboard.plist
- **Script**: job_manager_dashboard.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 9090)
- **Purpose**: Main job management dashboard

## Hourly Tracker Services (4 plists)

### 5. com.india-ts.hourly-tracker-service.plist
- **Script**: hourly_tracker_service_fixed.py --user Sai
- **Schedule**: Continuous (8:00 AM - 4:00 PM)
- **Status**: ✅ Active
- **Purpose**: Tracks hourly long reversal patterns

### 6. com.india-ts.hourly-tracker-dashboard.plist
- **Script**: hourly_tracker_dashboard.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 3002)
- **Purpose**: Dashboard for hourly tracker

### 7. com.india-ts.hourly-short-tracker-service.plist
- **Script**: hourly_short_tracker_service.py --user Sai
- **Schedule**: Continuous (8:00 AM - 4:00 PM)
- **Status**: ✅ Active
- **Purpose**: Tracks hourly short reversal patterns

### 8. com.india-ts.hourly-short-tracker-dashboard.plist
- **Script**: hourly_short_tracker_dashboard.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 3004)
- **Purpose**: Dashboard for hourly short tracker

## Scanner Jobs (9 plists)

### 9. com.india-ts.long_reversal_daily.plist
- **Script**: Long_Reversal_Daily.py
- **Schedule**: Every 30 min (9:00-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Daily long reversal scanner

### 10. com.india-ts.short_reversal_daily.plist
- **Script**: Short_Reversal_Daily.py
- **Schedule**: Every 30 min (9:00-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Daily short reversal scanner

### 11. com.india-ts.long-reversal-hourly.plist
- **Script**: Long_Reversal_Hourly.py --user Sai
- **Schedule**: Every 30 min (9:30-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Hourly long reversal scanner

### 12. com.india-ts.short-reversal-hourly.plist
- **Script**: Short_Reversal_Hourly.py --user Sai
- **Schedule**: Every 30 min (9:30-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Hourly short reversal scanner

### 13. com.india-ts.kc_lower_limit_trending_fno.plist
- **Script**: KC_Lower_Limit_Trending_FNO.py -u Sai
- **Schedule**: Hourly (9:00-15:00 IST)
- **Status**: ✅ Active
- **Purpose**: FNO KC lower limit scanner

### 14. com.india-ts.kc_upper_limit_trending_fno.plist
- **Script**: KC_Upper_Limit_Trending_FNO.py -u Sai
- **Schedule**: Hourly (9:00-15:00 IST)
- **Status**: ✅ Active
- **Purpose**: FNO KC upper limit scanner

### 15. com.india-ts.fno_liquid_reversal_scanners.plist
- **Script**: run_fno_liquid_reversal_scanners.py
- **Schedule**: Hourly at :19 (9:19-15:19 IST)
- **Status**: ✅ Active
- **Purpose**: FNO liquid stocks reversal scanner

### 16. com.india-ts.market_breadth_scanner.plist
- **Script**: Market_Breadth_Scanner.py
- **Schedule**: Every 30 min (9:00-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Market breadth analysis

### 17. com.india-ts.market_regime_analysis.plist
- **Script**: market_regime_analyzer.py
- **Schedule**: Every 30 min (8:30-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Market regime analysis

## Market Analysis & Dashboards (5 plists)

### 18. com.india-ts.market_regime_analyzer_5min.plist
- **Script**: run_regime_analyzer_5min.sh
- **Schedule**: Every 5 minutes (9:00-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: 5-minute market regime analysis

### 19. com.india-ts.market_regime_dashboard.plist
- **Script**: dashboard_enhanced.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 8080)
- **Purpose**: Market regime dashboard

### 20. com.india-ts.market_breadth_dashboard.plist
- **Script**: market_breadth_dashboard.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 5001)
- **Purpose**: Market breadth dashboard

### 21. com.india-ts.health_dashboard.plist
- **Script**: dashboard_health_check.py
- **Schedule**: Continuous (KeepAlive)
- **Status**: ✅ Active (Port 7080)
- **Purpose**: System health monitoring

### 22. com.india-ts.market_regime_daily_metrics.plist
- **Script**: calculate_daily_metrics.py
- **Schedule**: End of day
- **Status**: ✅ Active
- **Purpose**: Daily metrics calculation

## VSR Services (3 plists)

### 23. com.india-ts.vsr-tracker-enhanced.plist
- **Script**: vsr_tracker_service_enhanced.py --user Sai --interval 60
- **Schedule**: 9:15 AM start (runs continuously)
- **Status**: ✅ Active
- **Purpose**: Enhanced VSR tracking service

### 24. com.india-ts.vsr-dashboard.plist
- **Script**: vsr_tracker_dashboard.py
- **Schedule**: 9:15 AM start (KeepAlive)
- **Status**: ✅ Active (Port 3001)
- **Purpose**: VSR tracker dashboard

### 25. com.india-ts.vsr-shutdown.plist
- **Script**: stop_vsr_services.py
- **Schedule**: 3:30 PM IST
- **Status**: ✅ Active
- **Purpose**: Shutdown VSR services

## Momentum Tracking (2 plists)

### 26. com.india-ts.short-momentum-tracker.plist
- **Script**: short_momentum_tracker_service.py --user Sai --interval 60
- **Schedule**: 9:15 AM start (runs continuously)
- **Status**: ✅ Active
- **Purpose**: Short momentum tracking

### 27. com.india-ts.short-momentum-dashboard.plist
- **Script**: short_momentum_dashboard.py
- **Schedule**: 9:15 AM start (KeepAlive)
- **Status**: ✅ Active (Port 3003)
- **Purpose**: Short momentum dashboard

## Trading Support (2 plists)

### 28. com.india-ts.sl_watchdog_start.plist
- **Script**: start_all_sl_watchdogs.py
- **Schedule**: 9:15 AM IST
- **Status**: ✅ Active
- **Purpose**: Start stop-loss monitoring

### 29. com.india-ts.sl_watchdog_stop.plist
- **Script**: pkill -f "SL_watchdog.py.*India-TS"
- **Schedule**: 3:30 PM IST
- **Status**: ✅ Active
- **Purpose**: Stop SL watchdog service

## Data Management (5 plists)

### 30. com.india-ts.synch_zerodha_local.plist
- **Script**: synch_zerodha_cnc_positions.py --force
- **Schedule**: Every 15 min (9:15-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Sync Zerodha positions

### 31. com.india-ts.regime_data_updater_10min.plist
- **Script**: update_regime_data.py
- **Schedule**: Every 10 min (9:10-15:30 IST)
- **Status**: ✅ Active
- **Purpose**: Update regime data

### 32. com.india-ts.regime_data_updater.plist
- **Script**: update_regime_data.py
- **Schedule**: Unknown
- **Status**: ⚠️ Redundant (use 10min version)
- **Purpose**: Update regime data

### 33. com.india-ts.sma_breadth_historical_update.plist
- **Script**: append_historical_breadth.py
- **Schedule**: 6:30 PM IST
- **Status**: ✅ Active
- **Purpose**: Update historical breadth data

### 34. com.india-ts.outcome_resolver.plist
- **Script**: outcome_resolver.py
- **Schedule**: End of day
- **Status**: ⚠️ Check if needed
- **Purpose**: Resolve trade outcomes

## Utility Jobs (2 plists)

### 35. com.india-ts.fix_plists_on_startup.plist
- **Script**: fix_brooks_plist.sh
- **Schedule**: Every 86400 seconds (24 hours)
- **Status**: ⚠️ May not be needed
- **Purpose**: Fix plist configurations

### 36. com.india-ts.weekly_backup.plist
- **Script**: weekly_backup.sh
- **Schedule**: Sundays 3:00 AM
- **Status**: ✅ Active
- **Purpose**: Weekly system backup

## Recommendations

### Consider Removing:
1. **dashboard_refresh_control.plist** - Redundant with dashboard manager
2. **regime_data_updater.plist** - Keep only 10min version
3. **fix_plists_on_startup.plist** - One-time fix, may not be needed
4. **outcome_resolver.plist** - Check if still required

### Active Dashboard Ports:
- 3001: VSR Tracker
- 3002: Hourly Tracker  
- 3003: Short Momentum
- 3004: Hourly Short Tracker
- 5001: Market Breadth
- 7080: Health Dashboard
- 8080: Market Regime
- 9090: Job Manager