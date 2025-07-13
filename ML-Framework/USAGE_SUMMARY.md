# Market Regime Detection - Usage Summary

## Quick Start (What You Need to Know)

### 1. Daily Execution

Run the simplified regime checker every morning before market open:

```bash
cd /Users/maverick/PycharmProjects/India-TS
python3 ML-Framework/scripts/daily_regime_check.py
```

This will analyze your portfolio stocks and provide:
- Market overview (bullish/bearish/mixed)
- Individual stock regimes
- Position sizing recommendations
- Stop loss levels
- Action items (reduce/increase/hold)

### 2. Key Parameters to Monitor

**Market Regimes:**
- **TRENDING_BULLISH** → Position size: 120%, Stop: 2.0x ATR
- **TRENDING_BEARISH** → Position size: 40%, Stop: 1.0x ATR  
- **RANGING_HIGH_VOL** → Position size: 50%, Stop: 2.5x ATR
- **RANGING_LOW_VOL** → Position size: 80%, Stop: 1.5x ATR
- **TRANSITIONING** → Position size: 70%, Stop: 2.0x ATR

**Actions:**
- **REDUCE_OR_EXIT** → Exit position or reduce to minimum
- **REDUCE_SIZE** → Cut position size by 50%
- **WAIT** → Don't add new positions
- **RANGE_TRADE** → Trade range boundaries
- **INCREASE_LONGS** → Can increase position size

### 3. Decision Framework

**ENTER new positions when:**
- Stock shows INCREASE_LONGS action
- Market sentiment is BULLISH
- Position factor > 0.8x

**EXIT or REDUCE when:**
- Stock shows REDUCE_OR_EXIT action
- Stock regime opposes market (e.g., stock bearish while market bullish)
- High volatility detected (>4%)

**HOLD CASH when:**
- Market sentiment is BEARISH
- Most stocks show WAIT or REDUCE actions
- Volatility is extreme

### 4. Position Sizing Formula

```
Adjusted Position = Base Position × Regime Factor

Example:
- Normal position: ₹1,00,000
- Stock in TRENDING_BEARISH (0.4x)
- Adjusted position: ₹40,000
```

### 5. Stop Loss Calculation

```
Stop Loss = Entry Price ± (ATR × Regime Multiplier)

Example for LONG position:
- Entry: ₹1000
- ATR: ₹20
- BULLISH regime (2.0x)
- Stop Loss: ₹1000 - (₹20 × 2.0) = ₹960
```

## Daily Workflow

### Morning (8:30 AM)

1. **Run regime analysis**
   ```bash
   python3 ML-Framework/scripts/daily_regime_check.py
   ```

2. **Check Market Overview**
   - Note overall sentiment (BULLISH/BEARISH/MIXED)
   - Check regime distribution

3. **Review Individual Stocks**
   - Focus on stocks with REDUCE_OR_EXIT warnings
   - Note new INCREASE_LONGS opportunities

4. **Update Orders**
   - Adjust position sizes based on regime factors
   - Update stop losses using new multipliers
   - Exit positions with urgent warnings

### During Market Hours

- Follow position size recommendations
- Use regime-based stop losses
- Don't override REDUCE_OR_EXIT warnings

## Examples

### Example 1: Bullish Market
```
Market Overview: 70% stocks in TRENDING_BULLISH
Action: Increase exposure to 80-100% of capital
Position sizes: Use 100-120% of normal size
Stops: Use wider stops (2.0x ATR)
```

### Example 2: Bearish Market
```
Market Overview: 60% stocks in TRENDING_BEARISH
Action: Reduce exposure to 20-40% of capital
Position sizes: Use 40% of normal size
Stops: Use tight stops (1.0x ATR)
```

### Example 3: High Volatility
```
Stock shows RANGING_HIGH_VOL
Action: Reduce position to 50% of normal
Stops: Use very wide stops (2.5x ATR)
Consider staying out until volatility reduces
```

## Integration with Existing System

The regime detection integrates with your existing trading system:

1. **Position Sizing**: Multiply your Kelly Criterion size by regime factor
2. **Stop Loss**: Replace fixed stops with regime-based ATR multipliers
3. **Entry Signals**: Filter signals based on regime alignment
4. **Risk Management**: Use regime-based portfolio exposure limits

## Troubleshooting

**No data for ticker:**
- Ensure CSV files exist in BT/data/ directory
- Files should be named: TICKER_day.csv

**All regimes show TRANSITIONING:**
- Normal during market turning points
- Wait for clearer signals (1-2 days)

**Different from expected:**
- Regimes are based on price action, not fundamentals
- Trust the quantitative signals

## Key Takeaways

1. **Position Size = Normal Size × Regime Factor**
2. **Stop Loss = Entry ± (ATR × Regime Multiplier)**
3. **REDUCE_OR_EXIT = Immediate action required**
4. **Align positions with market regime**
5. **Reduce activity in high volatility**

The system removes emotion from position sizing and risk management decisions, helping you systematically adjust exposure based on market conditions.