# Daily Portfolio Regime Analysis Guide

## Quick Setup (One Time)

1. **Add to your daily routine** - Set a reminder for 8:30 AM daily
2. **Bookmark this command**: `./ML-Framework/daily_portfolio_check.sh`

## Daily Execution (Every Morning)

### Option 1: Simple Command (Recommended)
```bash
cd /Users/maverick/PycharmProjects/India-TS
./ML-Framework/daily_portfolio_check.sh
```

### Option 2: Direct Python Script
```bash
cd /Users/maverick/PycharmProjects/India-TS
python3 ML-Framework/scripts/analyze_my_portfolio.py
```

### Option 3: Automated Daily Run (Set Once)
Create a LaunchAgent to run automatically at 8:30 AM:

```bash
cat > ~/Library/LaunchAgents/com.india-ts.portfolio_regime.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.portfolio_regime</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/daily_portfolio_check.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/logs/portfolio_regime.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/logs/portfolio_regime_error.log</string>
</dict>
</plist>
EOF

# Load the agent
launchctl load ~/Library/LaunchAgents/com.india-ts.portfolio_regime.plist
```

## What the Analysis Shows

### 1. Portfolio Summary
```
PORTFOLIO SUMMARY:
Total Positions: 10
Total Value: ₹15,00,000
Total P&L: +₹75,000 (+5.00%)
```

### 2. Position-Specific Analysis
For each stock in your portfolio, you'll see:
```
RELIANCE (LONG):
  Entry: ₹1400.00 → Current: ₹1426.80
  P&L: +₹2,680.00 (+1.91%)
  Quantity: 100

  Regime: trending_bullish
  ACTION: HOLD_OR_ADD

  Stop Loss: ₹1370.90 (2.0x ATR)
  Stop Distance: ₹55.90 (3.9%)
  Position Size Recommendation: 120% of normal
```

### 3. Action Summary
```
ACTION SUMMARY:

REDUCE_OR_EXIT:
  VOLTAS, IDEA

MONITOR:
  TCS, HDFCBANK

HOLD_OR_ADD:
  RELIANCE, FEDERALBNK, IOC
```

## Key Actions Based on Analysis

### 🔴 REDUCE_OR_EXIT
**What it means**: Stock regime opposes your position
**Action**: Exit or reduce position size immediately
**Example**: If you're LONG but regime is TRENDING_BEARISH

### 🟡 REDUCE_SIZE
**What it means**: High volatility detected
**Action**: Cut position size by 50%
**Stop Loss**: Use wider stops (2.5x ATR)

### 🟢 HOLD_OR_ADD
**What it means**: Regime favors your position
**Action**: Can increase position size
**Position Size**: 120% of normal

### ⚪ MONITOR
**What it means**: Neutral/transitioning regime
**Action**: Hold current position
**Position Size**: 80% of normal

## Daily Workflow

### Morning Checklist (8:30 AM)

1. **Run the analysis**
   ```bash
   ./ML-Framework/daily_portfolio_check.sh
   ```

2. **Check URGENT actions**
   - Look for REDUCE_OR_EXIT warnings
   - Note any HIGH VOLATILITY alerts

3. **Update Stop Losses**
   - The script shows exact stop loss levels
   - Update your broker orders accordingly

4. **Adjust Position Sizes**
   - New entries: Use the position factor shown
   - Existing positions: Consider adjusting if action requires

### Example Daily Output
```
====================================
Daily Portfolio Regime Analysis
Date: Monday, June 15, 2025
====================================

PORTFOLIO SUMMARY:
Total Positions: 5
Total Value: ₹8,45,000
Total P&L: +₹23,500 (+2.78%)

REGIME DISTRIBUTION:
  trending_bullish          | 2 positions (40.0%)
  transitioning            | 2 positions (40.0%)
  trending_bearish         | 1 positions (20.0%)

ACTION SUMMARY:

REDUCE_OR_EXIT:
  VOLTAS

MONITOR:
  TCS, HDFCBANK

HOLD_OR_ADD:
  RELIANCE, IOC
```

## Integration with Your Trading

### For New Positions
```python
# Check regime before entering
Regime: trending_bullish
Position Factor: 1.2x
Action: Safe to enter with 120% size
```

### For Existing Positions
```python
# Daily regime check shows
VOLTAS: REDUCE_OR_EXIT
Current Stop: ₹1250
New Stop: ₹1227 (tighter due to bearish regime)
```

### Position Sizing Formula
```
New Position Size = Base Size × Regime Factor

Example:
- Normal size: ₹1,00,000
- Regime: trending_bullish (1.2x)
- Adjusted size: ₹1,20,000
```

## Reports Location

All reports are saved in:
```
ML-Framework/results/portfolio_analysis/
├── portfolio_regime_20250615_083000.csv  # Spreadsheet format
└── portfolio_regime_20250615_083000.json # Raw data
```

## Troubleshooting

**No positions found**: 
- Check if `data/trading_state.json` exists
- The script will use example positions if file not found

**No data for ticker**:
- Ensure CSV files exist in `BT/data/` directory
- File format: `TICKER_day.csv`

**Regime shows "transitioning"**:
- Normal during uncertain markets
- Use reduced position sizes (70-80%)

## Quick Reference

| Regime | Your Position | Action | Position Size | Stop Loss |
|--------|--------------|---------|---------------|-----------|
| BULLISH | LONG | HOLD/ADD | 120% | 2.0x ATR |
| BULLISH | SHORT | EXIT | - | - |
| BEARISH | LONG | EXIT | - | - |
| BEARISH | SHORT | HOLD/ADD | 120% | 2.0x ATR |
| HIGH VOL | ANY | REDUCE | 50% | 2.5x ATR |

## Summary

Run `./ML-Framework/daily_portfolio_check.sh` every morning to:
1. See which positions need immediate attention
2. Get exact stop loss levels
3. Know how to size new positions
4. Identify regime misalignments

This removes guesswork and provides systematic risk management based on market conditions.