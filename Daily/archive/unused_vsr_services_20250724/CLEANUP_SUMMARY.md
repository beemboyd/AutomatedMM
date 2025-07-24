# VSR Services Cleanup Summary
Date: 2025-07-24

## Files Moved to Archive

### From /Daily/services/:
1. **vsr_tracker_service.py** - Old VSR tracker (replaced by enhanced version)
2. **vsr_anomaly_detector.py** - Unused anomaly detector service
3. **vsr_log_viewer.py** - Standalone log viewer (replaced by dashboards)
4. **start_vsr_anomaly.sh** - Startup script for anomaly detector
5. **stop_vsr_anomaly.sh** - Stop script for anomaly detector
6. **status_vsr_anomaly.sh** - Status script for anomaly detector
7. **start_vsr_log_viewer.sh** - Startup script for log viewer
8. **VSR_ANOMALY_README.md** - Documentation for anomaly detector
9. **VSR_LOG_VIEWER_README.md** - Documentation for log viewer
10. **vsr_filter_commands.sh** - Utility script with grep commands
11. **start_vsr_tracker.sh** - Startup script for old tracker
12. **stop_vsr_tracker.sh** - Stop script for old tracker
13. **status_vsr_tracker.sh** - Status script for old tracker

## Active Services Retained

### In /Daily/services/:
- **vsr_tracker_service_enhanced.py** - Active enhanced VSR tracker
- **vsr_ticker_persistence.py** - Required by enhanced tracker
- **VSR_TRACKER_START_GUIDE.md** - Updated documentation

### In /Daily/dashboards/:
- **vsr_tracker_dashboard.py** - Active VSR dashboard (port 3001)
- **sl_watchdog_dashboard.py** - Active SL watchdog dashboard (port 2001)
- **start_sl_watchdog_dashboard.sh** - Startup script for SL dashboard
- **start_vsr_dashboard.sh** - Startup script for VSR dashboard
- **stop_vsr_dashboard.sh** - Stop script for VSR dashboard
- **templates/** - HTML templates for dashboards
- **VSR_DASHBOARD_GUIDE.md** - Dashboard documentation

## Scheduled Services (via launchctl)
1. **com.india-ts.vsr-tracker-enhanced** - Runs 9:15 AM - 3:30 PM
2. **com.india-ts.vsr-dashboard** - Runs 9:15 AM - 3:30 PM
3. **com.india-ts.vsr-shutdown** - Runs at 3:30 PM to stop services

## Documentation Updated
- **VSR_TRACKER_START_GUIDE.md** - Updated to reflect current automated scheduling

Total files cleaned up: 13