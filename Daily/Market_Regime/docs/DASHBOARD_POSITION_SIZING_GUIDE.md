# Dashboard Position Sizing Quick Reference

## Reading the Kelly Position Sizing Panel

### What Each Metric Means:

**Kelly %** 
- The recommended position size as a percentage of your capital
- Example: 15.99% means invest ₹15,990 per ₹1,00,000 capital

**Expected Value**
- Your expected return per trade
- Example: +115.1% means for every ₹100 risked, expect ₹115.10 profit on average

**Win Probability**
- The model's confidence in a successful trade
- Based on market regime, score, and historical data

**Win/Loss Ratio**
- Expected profit vs loss size
- Example: 1.8:1 means wins are 1.8× larger than losses

**Max Positions**
- Maximum number of simultaneous positions
- Calculated to limit total exposure based on Kelly %

**Stop Loss**
- Recommended stop loss percentage
- Adjusted for current market volatility

## Quick Decision Rules

### 🟢 **Strong Signal** (Take Position)
- Kelly % > 10%
- Expected Value > +50%
- Win Probability > 65%

### 🟡 **Moderate Signal** (Smaller Position)
- Kelly % 5-10%
- Expected Value +10% to +50%
- Win Probability 55-65%

### 🔴 **Weak/No Signal** (Avoid Trading)
- Kelly % < 5%
- Expected Value < +10%
- Win Probability < 55%

## Position Size Calculation

```
Position Size = Account Capital × Kelly %

Example:
- Account: ₹10,00,000
- Kelly %: 15.99%
- Position Size: ₹1,59,900
```

## Maximum Exposure

```
Total Exposure = Kelly % × Max Positions

Example:
- Kelly %: 15.99%
- Max Positions: 6
- Maximum Exposure: 95.94%
```

## Risk Per Trade

```
Risk Amount = Position Size × Stop Loss %

Example:
- Position Size: ₹1,59,900
- Stop Loss: 4%
- Risk per trade: ₹6,396
```

## When to Override

### Reduce Position Size When:
- First time using the system
- Recent losing streak
- Major market events
- Personal risk tolerance is lower

### Consider Larger Size When:
- Consistent winning streak
- High confidence in setup
- Strong market breadth support
- Additional confirming signals

## Color Guide

🟢 **Green Numbers**: Favorable conditions
🟡 **Orange Numbers**: Moderate conditions  
🔴 **Red Numbers**: Unfavorable conditions

## Daily Workflow

1. **Check Market Regime** (top left)
2. **Review Kelly %** (position sizing panel)
3. **Verify Direction** matches your analysis
4. **Calculate position size** based on Kelly %
5. **Set stop loss** at recommended level
6. **Monitor max positions** to avoid overexposure

Remember: Kelly Criterion assumes accurate probabilities. Start conservatively and increase as you verify the model's accuracy with your actual results.