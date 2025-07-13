# Daily Usage Guide for Market Regime Detection

## Running the Daily Analysis

### 1. Manual Execution

Run the daily analysis script from the project root:

```bash
cd /Users/maverick/PycharmProjects/India-TS
python ML-Framework/scripts/daily_regime_analysis.py
```

With custom configuration:
```bash
python ML-Framework/scripts/daily_regime_analysis.py --config ML-Framework/config/ml_config.json
```

### 2. Automated Daily Execution

Create a LaunchAgent for macOS to run automatically at 8:30 AM:

```bash
# Create the plist file
cat > ~/Library/LaunchAgents/com.india-ts.regime_analysis.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.regime_analysis</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/scripts/daily_regime_analysis.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/maverick/PycharmProjects/India-TS</string>
    <key>StandardOutPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/logs/regime_analysis.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/ML-Framework/logs/regime_analysis_error.log</string>
</dict>
</plist>
EOF

# Load the LaunchAgent
launchctl load ~/Library/LaunchAgents/com.india-ts.regime_analysis.plist
```

## Key Parameters to Monitor

### 1. Market Outlook (Primary Decision Factor)

Located in: `ML-Framework/results/daily_analysis/regime_summary_YYYYMMDD.txt`

**What to look for:**
```
MARKET OUTLOOK: [BULLISH/NEUTRAL/BEARISH/VOLATILE/RISK_OFF]
Confidence: XX%
```

**Decision Rules:**
- **BULLISH** (Confidence > 70%): Full position sizing, focus on long positions
- **NEUTRAL**: Selective positioning, reduced sizes
- **BEARISH/RISK_OFF**: Minimal positions, consider cash or hedges
- **VOLATILE**: Reduce all position sizes, widen stops

### 2. Index Regime Alignment

**What to look for:**
```
INDEX REGIMES:
SMALLCAP     | STRONG_BULLISH  | 85%
MIDCAP       | WEAK_BULLISH    | 72%
TOP100CASE   | NEUTRAL         | 68%
```

**Decision Rules:**
- All indices aligned bullish → Aggressive positioning
- Mixed signals → Selective positioning
- All indices bearish → Defensive mode

### 3. Individual Stock Analysis

Located in: `ML-Framework/results/daily_analysis/position_details_YYYYMMDD.csv`

**Key columns to monitor:**
- `regime`: Current regime for the stock
- `confidence`: Confidence level (prefer > 70%)
- `action`: REDUCE_EXPOSURE, MAINTAIN_OR_INCREASE, etc.
- `position_size_factor`: Multiplier for position sizing
- `urgency`: HIGH = immediate action needed

### 4. Risk Alerts (Immediate Action Items)

Located in: `ML-Framework/results/daily_analysis/risk_report_YYYYMMDD.txt`

**Critical alerts to act on:**
```
RISK ALERTS:
TIMKEN: Market in STRONG_BEARISH regime - reduce risk exposure
  Recommended Action: CONSIDER_EXIT
```

**Action Required When:**
- Urgency = HIGH
- Stock regime opposes position direction
- Market regime hits CRISIS

### 5. Position Sizing Recommendations

**Current vs Recommended:**
```
OVERALL MARKET RISK: HIGH

POSITION SIZING RECOMMENDATIONS:
- Maximum position size: 2% per position
- Current recommendation: 0.4x normal size
```

**Quick Reference Table:**

| Market Risk | Max Position | Size Factor | Action |
|------------|--------------|-------------|---------|
| LOW | 5% | 1.0-1.2x | Normal/Increase |
| MODERATE | 3% | 0.8x | Selective |
| HIGH | 2% | 0.4-0.6x | Reduce |
| EXTREME | 1% | 0.2x | Minimal/Exit |

### 6. Stop Loss Adjustments

**Monitor these multipliers:**
```
Stop Loss Multipliers:
- Long: 2.0x ATR (bullish regime)
- Long: 1.0x ATR (bearish regime)
```

**When to adjust stops:**
- Regime changes from bullish to bearish → Tighten stops
- Volatility increases → Widen stops
- HIGH_VOLATILITY regime → Use 2.5x ATR minimum

## Daily Workflow

### Morning Routine (8:30 AM)

1. **Check Summary Report**
   ```bash
   cat ML-Framework/results/daily_analysis/regime_summary_$(date +%Y%m%d).txt
   ```

2. **Review Risk Alerts**
   - Any HIGH urgency items?
   - Any positions against market regime?

3. **Check Position Report**
   ```bash
   # View in Excel or:
   cat ML-Framework/results/daily_analysis/position_details_$(date +%Y%m%d).csv | column -t -s,
   ```

4. **Make Decisions**
   - Exit positions with HIGH urgency alerts
   - Adjust position sizes per recommendations
   - Update stop losses for regime changes

### Key Decision Points

#### ENTER NEW POSITIONS when:
- Market Outlook = BULLISH/CAUTIOUSLY_BULLISH
- Stock regime = STRONG_BULLISH/WEAK_BULLISH
- Confidence > 70%
- Position size factor > 0.8

#### HOLD CASH when:
- Market Outlook = BEARISH/RISK_OFF
- Confidence < 60%
- Multiple HIGH urgency alerts
- Index regimes not aligned

#### REDUCE EXPOSURE when:
- Market Risk = HIGH/EXTREME
- Stock regime opposes position type
- Volatility regime detected
- Stop losses being hit frequently

## Monitoring Commands

### Quick Status Check
```bash
# Today's market outlook
grep "MARKET OUTLOOK" ML-Framework/results/daily_analysis/regime_summary_$(date +%Y%m%d).txt

# Risk alerts
grep -A5 "RISK ALERTS" ML-Framework/results/daily_analysis/regime_summary_$(date +%Y%m%d).txt

# Position recommendations
grep "action" ML-Framework/results/daily_analysis/regime_analysis_$(date +%Y%m%d).json
```

### Weekly Review
```bash
# Compare regime changes over the week
for i in {0..6}; do
  date=$(date -v-${i}d +%Y%m%d)
  echo "Date: $date"
  grep "MARKET OUTLOOK" ML-Framework/results/daily_analysis/regime_summary_$date.txt 2>/dev/null
done
```

## Configuration Adjustments

### Sensitivity Settings

Edit `ML-Framework/config/ml_config.json`:

```json
{
  "regime_detection": {
    "min_regime_confidence": 0.6,  // Increase to 0.7 for fewer but higher confidence signals
    "regime_persistence_threshold": 5,  // Days before confirming regime change
  }
}
```

### Risk Tolerance

Adjust position factors for your risk tolerance:

```json
"position_adjustment_factors": {
  "STRONG_BULLISH": 1.2,  // Reduce to 1.0 for conservative
  "CRISIS": 0.2,  // Reduce to 0.1 for more conservative
}
```

## Integration with Trading Workflow

### Before Placing Orders

```python
# In your order placement script
from ML_Framework.integration.regime_risk_integration import RegimeRiskIntegration

regime_risk = RegimeRiskIntegration()

# Check if should enter
recommendations = regime_risk.check_portfolio_exposure_limits(current_exposure=0.6)
if not recommendations['within_limits']:
    print(f"WARNING: {recommendations['reasoning']}")
    # Reduce order size or skip
```

### Position Sizing

```python
# Get regime-adjusted size
position_info = regime_risk.calculate_regime_adjusted_position_size(
    ticker=ticker,
    base_position_size=100000,
    entry_price=current_price,
    account_value=total_capital
)

# Use the adjusted size
order_quantity = position_info['shares']
print(f"Regime: {position_info['regime']}")
print(f"Adjusted size: {position_info['shares']} shares ({position_info['position_pct']:.1%})")
```

## Troubleshooting

### Common Issues

1. **No regime detected**
   - Check if data files exist in BT/data/
   - Verify at least 200 days of history

2. **Low confidence scores**
   - Normal during regime transitions
   - Wait for persistence threshold (5 days)

3. **Conflicting signals**
   - Trust the ensemble (uses multiple methods)
   - Higher confidence = more reliable

### Logs Location
- Daily logs: `ML-Framework/logs/regime_analysis_YYYYMMDD.log`
- Error logs: `ML-Framework/logs/regime_analysis_error.log`

## Best Practices

1. **Don't Override High Urgency Alerts**
   - These are based on significant regime misalignment

2. **Use Gradual Position Changes**
   - Don't go from 0% to 100% exposure in one day
   - Scale in/out based on confidence

3. **Monitor Regime Persistence**
   - Wait for regime to persist 3-5 days before major changes

4. **Combine with Your Analysis**
   - Regime detection is one input
   - Combine with your fundamental/technical analysis

5. **Review Weekly Patterns**
   - Look for regime stability/changes
   - Adjust strategy based on regime cycles