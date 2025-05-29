# Removing manage_risk.py

The `manage_risk.py` script has been identified as obsolete and should be removed from the system. The position_watchdog.py script now handles all risk management functions.

## Steps to Remove manage_risk.py

1. Delete the file:
   ```bash
   rm /Users/maverick/PycharmProjects/India-TS/scripts/manage_risk.py
   ```

2. Remove any scheduled tasks or services that run this script:
   ```bash
   # Check if launchd is running the script
   launchctl list | grep manage_risk
   
   # Remove the service if found
   launchctl unload /Users/maverick/PycharmProjects/India-TS/plist/com.indiaTS.manage_risk.plist
   ```

3. Delete the plist file if it exists:
   ```bash
   rm /Users/maverick/PycharmProjects/India-TS/plist/com.indiaTS.manage_risk.plist
   ```

## Important Note

All risk management functionality previously handled by `manage_risk.py` is now integrated into `position_watchdog.py`. No functionality will be lost by removing this obsolete script.

The risk management integration includes:
- Position sizing
- Stop loss management
- Trailing stop updates
- Risk parameter enforcement

This removal will simplify the system architecture and eliminate duplicate/conflicting functionality.