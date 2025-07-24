# Porsche VSR Momentum Trading - Quick Start Guide

## Pre-Market Checklist (9:00 - 9:15 AM)

- [ ] Check VSR tracker is running:
  ```bash
  launchctl list | grep vsr-enhanced-tracker
  ```

- [ ] Open VSR Dashboard:
  ```
  http://localhost:3001
  ```

- [ ] Verify dashboard is updating (check timestamp)

- [ ] Open trade log spreadsheet

- [ ] Check account balance and margin

## During Market Hours

### 1. Monitor Dashboard
- Focus on **Perfect Scores (100)** section
- Watch for **New Entries** marked with 🆕
- Check **High Momentum** (>5%) tickers

### 2. When You See Opportunity

```bash
cd /Users/maverick/PycharmProjects/India-TS
python Daily/trading/place_orders_vsr_momentum.py
```

### 3. Entry Checklist
Before confirming order:
- [ ] Score ≥ 80
- [ ] VSR ≥ 2.0
- [ ] Momentum between 2-10%
- [ ] Adequate volume
- [ ] Not already in 5 positions
- [ ] Market conditions favorable

### 4. After Entry
- [ ] Note entry details in log
- [ ] Set mental stop loss (-3%)
- [ ] Set mental targets (5%, 8%)
- [ ] Monitor in broker terminal

### 5. Exit Decision Points
Monitor for:
- **Profit Target**: 5% (partial), 8% (full)
- **Stop Loss**: -3% from entry
- **Time Stop**: 3 hours maximum
- **Momentum Loss**: Price stalls for 30 min
- **Volume Dry Up**: Volume < 50% of entry

## Quick Commands

**Check VSR Logs**:
```bash
tail -f ~/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_enhanced_*.log
```

**Check Order Logs**:
```bash
tail -f ~/PycharmProjects/India-TS/Daily/logs/Sai/vsr_momentum_orders_*.log
```

**Restart VSR Tracker** (if needed):
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-enhanced-tracker.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-enhanced-tracker.plist
```

## Position Sizing Quick Reference

| Account Value | 2% Position | Max at ₹100 | Max at ₹500 | Max at ₹1000 |
|--------------|-------------|-------------|--------------|---------------|
| ₹10,00,000 | ₹20,000 | 200 shares | 40 shares | 20 shares |
| ₹25,00,000 | ₹50,000 | 500 shares | 100 shares | 50 shares |
| ₹50,00,000 | ₹1,00,000 | 1000 shares | 200 shares | 100 shares |

## Emergency Contacts

- **Trading Desk**: [Your broker support]
- **Technical Issues**: Check Daily/logs/
- **System Admin**: [Your contact]

## End of Day

- [ ] Close all MIS positions by 3:20 PM
- [ ] Update trade log with exits
- [ ] Calculate daily PnL
- [ ] Note key observations
- [ ] Plan for tomorrow

---

**Remember**: 
- Start small, learn patterns
- Document everything
- Exits are more important than entries
- When in doubt, stay out

*Quick Start v1.0 - July 2025*