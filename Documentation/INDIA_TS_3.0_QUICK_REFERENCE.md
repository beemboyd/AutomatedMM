# India TS 3.0 - Quick Reference Guide

## System Commands

### Start/Stop Services
```bash
# Start all services
launchctl load ~/Library/LaunchAgents/com.india-ts.*.plist

# Stop all services
launchctl unload ~/Library/LaunchAgents/com.india-ts.*.plist

# Check service status
launchctl list | grep india-ts

# Start dashboard
cd ~/PycharmProjects/India-TS/Market_Regime/dashboard
python3 run_dashboard.py
```

### Manual Runs
```bash
# Run scanners manually
python3 ~/PycharmProjects/India-TS/Daily/scanners/Long_Reversal_Daily.py
python3 ~/PycharmProjects/India-TS/Daily/scanners/Short_Reversal_Daily.py

# Run market regime analysis
python3 ~/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py

# Generate action plan
python3 ~/PycharmProjects/India-TS/Daily/analysis/Action_plan.py
```

### Monitoring
```bash
# Watch logs in real-time
tail -f ~/PycharmProjects/India-TS/Daily/logs/*.log

# Check market regime logs
tail -f ~/PycharmProjects/India-TS/Market_Regime/logs/market_regime_analysis.log

# Database queries
sqlite3 ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db

# Common queries
.tables
SELECT * FROM regime_predictions ORDER BY timestamp DESC LIMIT 10;
SELECT COUNT(*) as total, COUNT(CASE WHEN actual_regime IS NOT NULL THEN 1 END) as resolved FROM regime_predictions WHERE date(timestamp) = date('now');
```

## File Locations

### Configuration
- Main config: `Daily/config.ini`
- User credentials: `Daily/config.ini` (per user section)
- Regime config: `Daily/config.ini` [REGIME] section

### Output Files
- Scanner results: `Daily/results/` and `Daily/results-s/`
- Action plans: `Daily/Plan/`
- HTML reports: `Daily/Detailed_Analysis/`
- Regime reports: `Daily/Market_Regime/regime_analysis/`

### State Files
- Trading state: `Daily/trading_state.json`
- Regime database: `Market_Regime/data/regime_learning.db`

### Logs
- Scanner logs: `Daily/logs/long_reversal_daily.log`, `short_reversal_daily.log`
- Regime logs: `Market_Regime/logs/market_regime_analysis.log`
- Trading logs: `Daily/logs/place_orders_daily.log`
- Watchdog logs: `Daily/logs/sl_watchdog.log`

## Key Parameters

### Trading Limits
```ini
max_cnc_positions = 10
capital_deployment_percent = 25
risk_per_trade = 0.01
max_portfolio_heat = 0.05
ticker_cooldown_hours = 2.0
```

### Scanner Thresholds
- Minimum score: 5/7
- ATR multiplier: 2.5x
- Volume threshold: 150% of average
- Confirmation bars: 2-3

### Regime Multipliers
| Regime | Position Size | Stop Loss |
|--------|--------------|-----------|
| Strong Uptrend | 1.5x | 0.8x |
| Uptrend | 1.2x | 0.9x |
| Choppy | 0.8x | 1.0x |
| Downtrend | 0.5x | 1.2x |

## Schedule Summary

### Daily Schedule
- **08:30** - Action Plan
- **08:45** - Consolidated Score
- **09:00-15:30** - Scanners (every 30 min)
- **09:10-15:40** - Market Regime (10 min after scanners)
- **09:35-16:05** - Outcome Resolver (35 min after predictions)
- **15:00** - Portfolio Prune
- **16:15** - Daily Metrics

### Continuous
- SL Watchdog - Always running during market hours
- Dashboard - Available on port 8088

## Troubleshooting

### Common Issues

1. **Scanner not finding signals**
   - Check market hours
   - Verify API connectivity
   - Review score thresholds

2. **Orders not placing**
   - Check position limits
   - Verify capital availability
   - Review recent trades log

3. **Stop losses not updating**
   - Check GTT order status
   - Verify position exists
   - Review ATR calculations

4. **Dashboard not updating**
   - Check Flask server running
   - Verify scanner results exist
   - Check browser console

### Quick Fixes
```bash
# Reset stuck service
launchctl unload -w ~/Library/LaunchAgents/com.india-ts.SERVICE_NAME.plist
launchctl load -w ~/Library/LaunchAgents/com.india-ts.SERVICE_NAME.plist

# Clear old logs (if too large)
echo "" > ~/PycharmProjects/India-TS/Daily/logs/LOGFILE.log

# Fix database locks
fuser ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db
# Kill process if needed

# Verify Python path
which python3
# Should be: /usr/local/bin/python3 or /Library/Frameworks/Python.framework/Versions/3.11/bin/python3
```

## Performance Metrics

### Check System Health
```bash
# API usage
grep "API call" ~/PycharmProjects/India-TS/Daily/logs/*.log | wc -l

# Scanner performance
grep "Successfully wrote" ~/PycharmProjects/India-TS/Daily/logs/long_reversal_daily.log | tail -5

# Error count
grep -i error ~/PycharmProjects/India-TS/Daily/logs/*.log | wc -l

# Database size
du -h ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db
```

### Daily Checklist
- [ ] All services running (launchctl list)
- [ ] Scanner results generated
- [ ] Market regime updated
- [ ] Positions synced with broker
- [ ] Stop losses verified
- [ ] No critical errors in logs
- [ ] Dashboard accessible

## Emergency Procedures

### Full System Restart
```bash
# 1. Stop all services
launchctl unload ~/Library/LaunchAgents/com.india-ts.*.plist

# 2. Check no processes running
ps aux | grep -i "india-ts\|reversal\|regime"

# 3. Clear any locks
rm -f ~/PycharmProjects/India-TS/Daily/*.lock

# 4. Start services
launchctl load ~/Library/LaunchAgents/com.india-ts.*.plist

# 5. Verify startup
launchctl list | grep india-ts
```

### Data Recovery
```bash
# Backup current state
cp ~/PycharmProjects/India-TS/Daily/trading_state.json ~/backup/trading_state_$(date +%Y%m%d_%H%M%S).json

# Backup database
cp ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db ~/backup/

# Restore from backup
cp ~/backup/trading_state_TIMESTAMP.json ~/PycharmProjects/India-TS/Daily/trading_state.json
```

---

*India TS 3.0 - Quick Reference - Last Updated: June 25, 2025*