# Daily Trading Workflow Guide

This guide provides a step-by-step workflow for daily trading operations using the India-TS system.

## 📅 Daily Schedule Overview

| Time | Activity | Automated? |
|------|----------|------------|
| 8:30 AM | Daily Action Plan Generation | ✅ Automated |
| 8:30 AM | Market Regime Analysis Starts | ✅ Automated |
| 9:00 AM | Consolidated Score Report | ✅ Automated |
| 9:15 AM | Market Opens - Scanners Start | ✅ Automated |
| 9:30 AM | Review Scanner Results | 👤 Manual |
| 10:00 AM | Place Orders (if needed) | 👤 Manual |
| 10:30 AM | Start SL Watchdog | 👤 Manual |
| Continuous | Monitor Positions & Dashboards | 👤 Manual |
| 3:30 PM | Market Close | ✅ Auto cleanup |

## 🚀 Pre-Market (8:30 AM - 9:15 AM)

### 1. Check System Health
```bash
# View health dashboard
open http://localhost:5000

# Check if all jobs are running
launchctl list | grep india-ts
```

### 2. Review Morning Reports
- **Action Plan**: Check `Daily/Plan/Consolidated_Plan_Latest.xlsx`
- **Consolidated Score**: Check `Daily/Plan/Consolidated_Score_Latest.xlsx`
- **Previous Day Results**: Review `Daily/results/` folder

## 📊 Market Hours (9:15 AM - 3:30 PM)

### 1. Scanner Monitoring (9:15 AM onwards)

Scanners run automatically every 30 minutes. Check results in:
- `Daily/results/Long_Reversal_Daily_*.xlsx`
- `Daily/results/Short_Reversal_Daily_*.xlsx`
- `Daily/results/KC_Upper_Limit_Trending_*.xlsx`
- `Daily/results/KC_Lower_Limit_Trending_*.xlsx`

### 2. Evaluate Opportunities (9:30 AM - 10:00 AM)

Review scanner results for:
- **KC_Breakout_Watch** patterns (high priority)
- **G_Pattern** formations
- **High probability reversals** (>60% win rate)

Check dashboards:
```bash
# Market Breadth Dashboard (includes Early Bird)
open http://localhost:5001

# Enhanced Dashboard
open http://localhost:8080
```

### 3. Place Orders (When Opportunities Arise)

For manual order placement:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/trading
python place_orders_daily.py
```

For G Pattern automated trading:
```bash
python g_pattern_auto_trader.py
```

### 4. Start Position Monitoring (After Orders Placed)

Start SL Watchdog for position monitoring:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/bin

# Check if already running
./check_sl_watchdog_status.sh

# Start regime-based watchdog (recommended)
./start_sl_watchdog_regime.sh
```

### 5. Continuous Monitoring

Monitor throughout the day:

#### Position Monitoring
- Watch SL Watchdog logs for:
  - ATR stop loss updates
  - ⚠️ Volume anomaly warnings
  - 🚨 High exhaustion risk alerts
  - Trailing stop adjustments

```bash
# View live logs
tail -f Daily/logs/<username>/SL_watchdog_*.log
```

#### Dashboard Monitoring
- **Health Dashboard** (http://localhost:5000): System status
- **Market Breadth** (http://localhost:5001): Market overview & early birds
- **Enhanced Dashboard** (http://localhost:8080): Detailed analysis

#### Volume Anomaly Alerts
Watch for exhaustion patterns:
- Score 3/8: Medium risk - Monitor closely
- Score 4+/8: High risk - Consider tightening stops

## 🔄 Intraday Tasks

### Every 30 Minutes
- New scanner results available
- Market regime updates
- Check for new opportunities

### Every Hour
- Review position performance
- Check volume anomaly warnings
- Assess market conditions

### At 2:30 PM
- Review all positions
- Consider closing weak positions
- Prepare for market close

## 🏁 End of Day (3:30 PM - 4:00 PM)

### 1. Automatic Cleanup
- SL Watchdog stops at 3:45 PM (automated)
- Positions marked for EOD closure

### 2. Review Day's Performance
```bash
# Check final results
ls -la Daily/results/*$(date +%Y%m%d)*

# Review logs for issues
grep -i error Daily/logs/*/$(date +%Y%m%d)*.log
```

### 3. Generate Reports
- Strategy C Filter runs at 3:45 PM
- Market Regime Dashboard updates at 5:00 PM

## 📋 Troubleshooting Quick Reference

### Scanner Issues
```bash
# Check scanner logs
tail -100 Daily/logs/Al_Brooks_Scanner_error.log
tail -100 Daily/logs/scanner_reversals_*.log
```

### Order Placement Issues
```bash
# Check order logs
tail -100 Daily/logs/<username>/place_orders_*.log
```

### SL Watchdog Issues
```bash
# Check status
./check_sl_watchdog_status.sh

# Restart if needed
./stop_sl_watchdog_regime.sh
./start_sl_watchdog_regime.sh
```

### Dashboard Issues
```bash
# Restart dashboards
cd Daily/utils
./stop_dashboards.sh
./start_dashboards.sh
```

## 💡 Best Practices

1. **Start Simple**: Begin with monitoring before placing orders
2. **Use Dashboards**: Visual monitoring is easier than logs
3. **Check Anomalies**: Pay attention to volume-price divergences
4. **Document Issues**: Note any problems for end-of-day review
5. **Stay Disciplined**: Follow the system, don't override without good reason

## 🔗 Related Documentation

- [SL Watchdog Management](../bin/SL_WATCHDOG_MANAGEMENT.md)
- [Dashboard Quick Reference](../DASHBOARD_QUICK_REFERENCE.md)
- [Jobs Documentation](../INDIA_TS_JOBS_DOCUMENTATION.md)
- [Volume Anomaly Detection](volume_anomaly_detection_guide.md)

---

*For detailed component documentation, see the [Documentation Index](../DOCUMENTATION_INDEX.md)*