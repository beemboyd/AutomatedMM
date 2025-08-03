# Dashboard Restart Fix Documentation

## Issues Fixed
1. The restart functionality for the Market Regime Dashboard (port 8080) and Health Dashboard (port 7080) was not working properly from the Job Manager Dashboard (port 9090).
2. Dashboard was failing to start due to missing joblib module and logger initialization order.

## Root Cause
The dashboards managed by launchctl with `KeepAlive: true` setting cannot be restarted using simple `launchctl stop` and `launchctl start` commands. When using `launchctl stop`, it only temporarily stops the service, but launchctl immediately restarts it due to the KeepAlive setting.

## Solution
Modified the `restart_dashboard` function in `job_manager_dashboard.py` to properly handle launchctl-managed dashboards:

1. For dashboards with KeepAlive (market_regime_dashboard_manual and health_dashboard_manual):
   - Use `launchctl unload` to completely remove the service from launchctl management
   - Wait 2 seconds for the service to fully stop
   - Use `launchctl load` to reload the service fresh

2. For other dashboards:
   - Continue using the regular stop/start approach

## Implementation Details

```python
# Special handling for launchctl-managed dashboards with KeepAlive
if dashboard_id in ['health_dashboard_manual', 'market_regime_dashboard_manual']:
    # Map dashboard_id to job_id
    job_id_map = {
        'health_dashboard_manual': 'com.india-ts.health_dashboard',
        'market_regime_dashboard_manual': 'com.india-ts.market_regime_dashboard'
    }
    job_id = job_id_map[dashboard_id]
    
    # Determine the plist path
    plist_path = f'/Users/maverick/Library/LaunchAgents/{job_id}.plist'
    
    # Unload the service (this stops it and removes from launchctl)
    unload_result = subprocess.run(['launchctl', 'unload', plist_path], 
                                 capture_output=True, text=True)
    
    # Wait a moment for the service to fully stop
    time.sleep(2)
    
    # Load the service again (this starts it fresh)
    load_result = subprocess.run(['launchctl', 'load', plist_path], 
                               capture_output=True, text=True)
```

## Affected Dashboards
- Market Regime Dashboard (port 8080) - com.india-ts.market_regime_dashboard
- Health Dashboard (port 7080) - com.india-ts.health_dashboard

## Testing
1. Access Job Manager Dashboard at http://localhost:9090
2. Click "Restart" button for Market Regime Dashboard
3. The dashboard should properly restart and be accessible at http://localhost:8080

## Additional Fixes
### Logger Initialization Issue
- Fixed `NameError: name 'logger' is not defined` by moving logging configuration before ML import
- Logger must be initialized before any try/except blocks that use it

### Missing Dependencies
- The system Python (/usr/bin/python3) needed joblib module installed
- Run: `/usr/bin/python3 -m pip install joblib` to install for system Python

## Notes
- This fix only applies to dashboards managed by launchctl with KeepAlive setting
- Other dashboards continue to use the regular stop/start approach
- The unload/load approach ensures a clean restart of the service
- Ensure all required Python modules are installed for the system Python used by launchctl