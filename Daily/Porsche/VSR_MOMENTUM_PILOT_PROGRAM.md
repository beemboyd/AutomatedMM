# VSR Momentum Trading Pilot Program - "Porsche"

## Overview
This pilot program implements a semi-automated momentum trading strategy using Volume Spread Ratio (VSR) indicators. The system automatically identifies high-momentum opportunities while keeping order placement and exits under manual control.

## System Architecture

### 1. Ticker Discovery & Tracking
- **Source**: Long_Reversal_Daily_*.xlsx files (updated every 30 minutes)
- **Auto-Refresh**: Every 5 minutes checks for new files
- **Persistence**: 3-day ticker history maintained
- **Coverage**: All tickers from current + past 3 days

### 2. Momentum Detection
- **Data Frequency**: Hourly candles for VSR calculation
- **Update Rate**: Every 60 seconds
- **Scoring**: 0-100 based on VSR, volume, and momentum
- **Indicators**:
  - VSR Ratio (Volume × Price Spread)
  - Momentum % (5-hour price change)
  - Volume Ratio (current vs average)
  - Build Indicator (momentum acceleration)

### 3. Dashboard Monitoring
- **URL**: http://localhost:3001
- **Categories**:
  - Perfect Scores (100)
  - High VSR (≥10)
  - High Momentum (≥5%)
  - Strong Build (≥10)

### 4. Manual Order Placement
```bash
python Daily/trading/place_orders_vsr_momentum.py
```
- Shows candidates meeting criteria
- Displays position sizing
- Requires user confirmation
- Places LIMIT orders at current price
- Uses MIS (intraday) positions

### 5. Manual Exit Management
- Monitor positions via broker terminal
- No automated stop losses during pilot
- Manual decision on:
  - Profit booking
  - Stop loss execution
  - Time-based exits

## Pilot Program Workflow

### Daily Operations

#### 1. Pre-Market (9:00 - 9:15 AM)
- Verify VSR tracker is running
- Check dashboard at http://localhost:3001
- Review any overnight developments

#### 2. Market Hours (9:15 AM - 3:30 PM)

**Continuous Monitoring**:
- Dashboard auto-updates every minute
- New tickers appear within 5 minutes of scan

**Entry Process**:
1. Monitor dashboard for high-scoring opportunities
2. When ready to enter:
   ```bash
   cd /Users/maverick/PycharmProjects/India-TS
   python Daily/trading/place_orders_vsr_momentum.py
   ```
3. Review proposed orders
4. Confirm with 'y' to place orders
5. Note entry details in trade log

**Exit Process**:
1. Monitor positions in broker terminal
2. Make exit decisions based on:
   - Price action
   - Volume patterns
   - Market conditions
   - Time in trade
3. Execute exits manually
4. Record exit details

#### 3. Post-Market (After 3:30 PM)
- Review day's trades
- Update trade log
- Note observations

## Trade Logging

### Required Data Points
Create a spreadsheet (Porsche_Trades.xlsx) with:

| Date | Time | Ticker | Entry Price | Entry VSR | Entry Mom% | Entry Score | Exit Time | Exit Price | PnL% | Hold Time | Exit Reason | Notes |
|------|------|--------|-------------|-----------|------------|-------------|-----------|------------|------|-----------|-------------|-------|

### Exit Reasons Categories
- **TP**: Target Profit reached
- **SL**: Stop Loss hit
- **TS**: Trailing Stop
- **ME**: Momentum Exhaustion
- **TM**: Time-based exit
- **MR**: Market Reversal
- **VD**: Volume Dried up
- **OT**: Other (specify in notes)

## Analysis Framework

### Daily Metrics
1. **Win Rate**: Winning trades / Total trades
2. **Average Win**: Mean profit on winners
3. **Average Loss**: Mean loss on losers
4. **Profit Factor**: Total wins / Total losses
5. **Average Hold Time**: By outcome

### Pattern Analysis
Track patterns for optimization:

1. **Best Entry Conditions**:
   - Optimal VSR range
   - Ideal momentum %
   - Best time of day
   - Volume patterns

2. **Exit Patterns**:
   - Average time to peak
   - Typical retracement %
   - Volume at reversal
   - Hold time vs outcome

3. **Market Conditions**:
   - Performance by market regime
   - Sector performance
   - Day of week analysis

## Configuration Tuning

### Current Settings (Baseline)
```python
# Entry Criteria
min_score = 80
min_vsr = 2.0
min_momentum = 2.0
max_momentum = 10.0

# Position Sizing
position_size_pct = 2.0
max_positions = 5
```

### Tuning Guidelines
Based on pilot results, adjust:

1. **Entry Thresholds**:
   - Raise min_score if too many false signals
   - Adjust momentum range based on hold times
   - Modify VSR threshold for quality

2. **Position Management**:
   - Increase position_size_pct if high win rate
   - Adjust max_positions based on management capacity
   - Consider scaling strategies

## Risk Management

### Pilot Phase Guidelines
1. **Start Conservative**:
   - Small position sizes (2% per trade)
   - Maximum 5 concurrent positions
   - Focus on learning patterns

2. **Monitor Closely**:
   - Real-time position tracking
   - Quick exit on adverse moves
   - Document all observations

3. **Gradual Scaling**:
   - Increase size only after 50+ trades
   - Adjust based on win rate
   - Consider market conditions

## Success Metrics

### Phase 1 (First 50 trades)
- **Target Win Rate**: >60%
- **Average Winner**: >2%
- **Average Loser**: <1.5%
- **Focus**: Pattern recognition

### Phase 2 (Next 100 trades)
- **Target Win Rate**: >65%
- **Profit Factor**: >2.0
- **Focus**: Optimization

### Phase 3 (Ongoing)
- **Consistent Profitability**
- **Refined Entry/Exit Rules**
- **Consider Automation**

## Weekly Review Process

Every Friday after market:

1. **Export Trade Log**
2. **Calculate Metrics**:
   - Weekly win rate
   - Average PnL
   - Best/worst trades
3. **Pattern Analysis**:
   - What worked well?
   - What patterns failed?
   - Market condition impact?
4. **Adjustments**:
   - Document proposed changes
   - Test in small size first
   - Update configuration if needed

## Emergency Procedures

### System Issues
1. **Dashboard Not Updating**:
   ```bash
   # Restart VSR tracker
   launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-enhanced-tracker.plist
   launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-enhanced-tracker.plist
   ```

2. **Order Placement Fails**:
   - Check account balance
   - Verify market hours
   - Check for trading holidays

3. **Data Issues**:
   - Verify Long_Reversal_Daily files exist
   - Check VSR tracker logs
   - Restart if necessary

## Next Steps

### Immediate Actions
1. Create Porsche_Trades.xlsx for logging
2. Set up daily routine
3. Start with 1-2 trades to test workflow

### After 50 Trades
1. Analyze patterns
2. Identify optimal conditions
3. Refine entry criteria

### After 100 Trades
1. Consider semi-automation for exits
2. Implement refined rules
3. Scale position sizes if profitable

---

## Quick Reference

**Dashboard**: http://localhost:3001

**Place Orders**:
```bash
python Daily/trading/place_orders_vsr_momentum.py
```

**Check Logs**:
```bash
tail -f Daily/logs/vsr_tracker/vsr_tracker_enhanced_*.log
tail -f Daily/logs/Sai/vsr_momentum_orders_*.log
```

**Emergency Stop All Positions**: Use broker terminal

---

*Document Created: July 24, 2025*
*Pilot Program: Porsche - High-Performance Momentum Trading*