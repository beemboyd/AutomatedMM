# Market Regime Quick Reference Card

## Daily Execution

```bash
# Run analysis (from project root)
./ML-Framework/scripts/run_daily_analysis.sh

# Or manually
python ML-Framework/scripts/daily_regime_analysis.py
```

## Key Decision Matrix

### Market Outlook → Action

| Outlook | Confidence | Position Size | Max Exposure | Action |
|---------|------------|---------------|--------------|---------|
| **BULLISH** | >70% | 100-120% | 80-100% | **GO LONG** |
| **CAUTIOUSLY_BULLISH** | >60% | 80-100% | 70-90% | **SELECTIVE LONG** |
| **NEUTRAL** | Any | 60-80% | 50-80% | **WAIT & WATCH** |
| **CAUTIOUSLY_BEARISH** | >60% | 40-60% | 30-60% | **REDUCE** |
| **BEARISH** | >70% | 20-40% | 20-40% | **DEFENSIVE** |
| **VOLATILE** | Any | 50% | 30-50% | **SMALL + WIDE STOPS** |
| **RISK_OFF** | >80% | 20% | 10-20% | **CASH/EXIT** |

### Regime-Based Stop Loss (ATR Multipliers)

| Your Position | Market Regime | Stop Loss Multiplier |
|--------------|---------------|---------------------|
| **LONG** | Bullish | 2.0x ATR |
| **LONG** | Neutral | 1.5x ATR |
| **LONG** | Bearish | 1.0x ATR |
| **LONG** | Volatile | 2.5x ATR |
| **SHORT** | Bullish | 1.2x ATR |
| **SHORT** | Bearish | 2.0x ATR |

## Daily Checklist

### Morning (8:30 AM)
- [ ] Run regime analysis
- [ ] Check MARKET OUTLOOK
- [ ] Review RISK ALERTS
- [ ] Note regime changes

### Pre-Market (9:00 AM)
- [ ] Adjust position sizes per recommendations
- [ ] Update stop losses for regime changes
- [ ] Exit HIGH urgency positions
- [ ] Identify new opportunities

### During Market
- [ ] Follow position size factors
- [ ] Use regime-based stops
- [ ] Monitor for regime alignment

## Quick Commands

```bash
# Today's outlook
grep "MARKET OUTLOOK" ML-Framework/results/daily_analysis/regime_summary_$(date +%Y%m%d).txt

# Risk alerts
grep -A5 "RISK ALERTS" ML-Framework/results/daily_analysis/regime_summary_$(date +%Y%m%d).txt

# Position details
open ML-Framework/results/daily_analysis/position_details_$(date +%Y%m%d).csv
```

## Warning Signals (Immediate Action)

1. **Market Outlook = RISK_OFF**
   → Reduce all positions to minimum

2. **Urgency = HIGH on your positions**
   → Exit or significantly reduce

3. **All indices BEARISH/VOLATILE**
   → Move to cash, wait for clarity

4. **Regime opposes position direction**
   → Long in BEARISH or Short in BULLISH = EXIT

## Position Sizing Formula

```
Adjusted Size = Base Size × Regime Factor × Confidence

Where:
- Base Size = Your normal position size
- Regime Factor = From config (0.2x to 1.2x)
- Confidence = Regime detection confidence
```

### Example:
- Normal position: ₹1,00,000
- Market regime: WEAK_BEARISH (0.6x)
- Confidence: 75%
- Adjusted size: ₹1,00,000 × 0.6 × 0.75 = ₹45,000

## Files to Monitor

1. **Summary** (Human Readable)
   `regime_summary_YYYYMMDD.txt`

2. **Positions** (Spreadsheet)
   `position_details_YYYYMMDD.csv`

3. **Risk Report** (Detailed)
   `risk_report_YYYYMMDD.txt`

4. **Raw Data** (For Systems)
   `regime_analysis_YYYYMMDD.json`

## Regime Characteristics

| Regime | Characteristics | Best Strategy |
|--------|----------------|---------------|
| **STRONG_BULLISH** | Trending up, Low volatility | Trend following, Larger positions |
| **WEAK_BULLISH** | Mild uptrend, Some volatility | Selective longs, Normal stops |
| **NEUTRAL** | Sideways, Range-bound | Range trading, Tight stops |
| **WEAK_BEARISH** | Mild downtrend, Increasing vol | Reduce longs, Consider shorts |
| **STRONG_BEARISH** | Trending down, High fear | Short or cash, Tight risk |
| **HIGH_VOLATILITY** | Large swings, No clear trend | Small positions, Wide stops |
| **CRISIS** | Extreme moves, Panic | Maximum cash, Survival mode |

## Integration Code Snippets

### Check Before Entry
```python
from ML_Framework.integration.regime_risk_integration import RegimeRiskIntegration
rri = RegimeRiskIntegration()

# Get recommendations
rec = rri.get_position_recommendations(ticker, current_positions)
if rec['action'] == 'REDUCE_EXPOSURE':
    print(f"Warning: {rec['reason']}")
    # Don't enter or reduce size
```

### Calculate Position Size
```python
position = rri.calculate_regime_adjusted_position_size(
    ticker=ticker,
    base_position_size=100000,
    entry_price=price,
    account_value=capital
)
print(f"Regime: {position['regime']}")
print(f"Shares: {position['shares']}")
```

### Set Stop Loss
```python
stop = rri.calculate_regime_adjusted_stop_loss(
    ticker=ticker,
    entry_price=price,
    position_type='LONG',
    atr=atr_value
)
print(f"Stop at: ₹{stop['stop_price']}")
```