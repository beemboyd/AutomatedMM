# Dashboard Troubleshooting Playbook

## Common Issues and Solutions

### Issue 1: Dashboards Show No Data (Ports 3001, 3002, 3003, 3004)

#### Symptoms:
- Dashboard loads but shows no tickers
- API returns empty or minimal data
- Services are running but not tracking

#### Root Causes & Solutions:

1. **VSR Scanner hasn't run today**
   - Check: `ls -la /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Hourly/VSR_*$(date +%Y%m%d)*.xlsx`
   - Fix: Run manually: `python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/VSR_Momentum_Scanner.py`

2. **Persistence files corrupted/stale**
   - Check logs for: `KeyError: 'last_updated'` or `Total tickers tracked: 0`
   - Fix: Reset persistence files:
   ```bash
   # Backup and reset hourly long tracker
   mv /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json \
      /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json.backup_$(date +%Y%m%d)
   echo "{}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json

   # Backup and reset hourly short tracker
   mv /Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json \
      /Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json.backup_$(date +%Y%m%d)
   echo "{}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json
   ```

3. **Hourly scanners haven't run**
   - Check: `ls -la /Users/maverick/PycharmProjects/India-TS/Daily/results-h/*$(date +%Y%m%d)*.xlsx`
   - These run on schedule at 9:30 AM and every 30 minutes thereafter

### Daily Maintenance Checklist (9:15 AM)

1. **Verify VSR Scanner has run:**
   ```bash
   ls -la /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Hourly/VSR_*$(date +%Y%m%d)*.xlsx
   ```

2. **Check tracker service logs for errors:**
   ```bash
   tail -20 /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_enhanced_$(date +%Y%m%d).log | grep -E "ERROR|tracked: 0"
   tail -20 /Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_tracker/hourly_tracker_$(date +%Y%m%d).log | grep -E "ERROR|tracked: 0"
   ```

3. **Verify dashboards are accessible:**
   - VSR Dashboard: http://localhost:3001
   - Hourly Tracker: http://localhost:3002
   - Short Momentum: http://localhost:3003
   - Hourly Short Tracker: http://localhost:3004

### Quick Service Restart Commands

```bash
# Restart all VSR and tracker services
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist 2>/dev/null && \
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist

launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist 2>/dev/null && \
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist

launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist 2>/dev/null && \
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist

# Restart short momentum tracker
pkill -f "short_momentum_tracker_service.py"
sleep 2
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist 2>/dev/null && \
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
```

### Prevention Strategies

1. **Add automated persistence file validation** to services that checks for:
   - File format consistency
   - Date freshness (warn if data > 7 days old)
   - Required fields presence

2. **Create daily health check script** that runs at 9:10 AM to:
   - Verify all required scanners have run
   - Check persistence file integrity
   - Alert if any dashboards are not responding

3. **Implement auto-recovery** in tracker services:
   - If persistence file read fails, auto-backup and create fresh file
   - Log warning but continue operation

### Log Locations for Debugging

- VSR Tracker: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/`
- Hourly Tracker: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_tracker/`
- Short Momentum: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum/`
- Hourly Short Tracker: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_short_tracker/`

### Dashboard Log Files

- VSR Dashboard: `/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/vsr_dashboard.log`
- Other dashboards: Check respective dashboard directories

## Emergency Recovery Procedure

If all dashboards are down:

1. Stop all services:
   ```bash
   pkill -f "tracker_dashboard.py"
   pkill -f "momentum_dashboard.py"
   pkill -f "tracker_service"
   ```

2. Clear all persistence files:
   ```bash
   find /Users/maverick/PycharmProjects/India-TS/Daily/data -name "*persistence*.json" -exec mv {} {}.backup_$(date +%Y%m%d) \;
   find /Users/maverick/PycharmProjects/India-TS/Daily/data -name "*persistence*.json.backup_*" -prune -o -name "*persistence*.json" -exec sh -c 'echo "{}" > "$1"' _ {} \;
   ```

3. Restart all services using the commands above

4. Run VSR scanner manually if needed

## Monitoring Best Practices

1. Check dashboards at market open (9:15 AM)
2. Verify data is updating every hour
3. Monitor for persistence file growth (should not exceed 1MB)
4. Weekly cleanup of old backup files

Last Updated: 2025-08-05