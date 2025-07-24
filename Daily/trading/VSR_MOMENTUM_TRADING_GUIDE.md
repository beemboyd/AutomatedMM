# VSR Momentum Trading Guide

## Overview
The VSR Momentum Trading system identifies and trades stocks showing strong volume-price momentum using the Volume Spread Ratio (VSR) indicator. It automatically places orders for high-scoring tickers and manages positions with intelligent exit rules.

## System Components

### 1. VSR Tracker Dashboard (Port 3001)
- **Purpose**: Monitors and scores tickers based on VSR patterns
- **Update Frequency**: Every 60 seconds
- **Data Source**: Live market data from Kite API

### 2. Place Orders VSR Momentum Script
- **File**: `place_orders_vsr_momentum.py`
- **Purpose**: Automatically places orders for qualified momentum tickers
- **Schedule**: Can be run every 5-10 minutes during market hours

### 3. Exit Rules Module
- **File**: `vsr_momentum_exit_rules.py`
- **Purpose**: Defines stop loss and profit-taking rules
- **Integration**: Used by SL_watchdog.py for position management

## Entry Criteria

### Minimum Requirements
- **VSR Score**: ≥ 80 (out of 100)
- **VSR Ratio**: ≥ 2.0
- **Momentum**: 2.0% - 10.0% (5-hour)
- **Build Indicator**: Preferably with 📈 (momentum building)

### Scoring Priority
Tickers are prioritized based on:
```
Priority = Score + (VSR × 10) + (Momentum × 5) + (Days_Tracked × 5) + Build_Bonus
```

### Position Sizing
- **Default**: 2% of account value per position
- **Maximum Positions**: 5 concurrent positions
- **Product Type**: MIS (intraday)

## Exit Strategy

### Stop Loss Rules
1. **Initial Stop Loss**: 3% below entry
2. **Trailing Stop Activation**: At 2% profit
3. **Trailing Distance**: 1.5% below peak

### Profit Targets
1. **Partial Profit**: 50% at 5% gain
2. **Full Exit**: At 8% gain

### Time-Based Exits
1. **Maximum Hold**: 3 hours
2. **Momentum Exhaustion**: Exit if < 0.5% move in 30 minutes

## Usage Instructions

### Manual Execution
```bash
# Run with default settings (user: Sai, live mode)
python Daily/trading/place_orders_vsr_momentum.py

# Run for different user
python Daily/trading/place_orders_vsr_momentum.py --user Som

# Run in paper trading mode
python Daily/trading/place_orders_vsr_momentum.py --mode PAPER

# Set maximum positions
python Daily/trading/place_orders_vsr_momentum.py --max-positions 3
```

### Scheduled Execution
Add to crontab or launchd for automated trading:
```bash
# Run every 10 minutes from 9:30 AM to 2:30 PM
*/10 9-14 * * 1-5 python /path/to/place_orders_vsr_momentum.py
```

## Risk Management

### Position Limits
- Maximum 5 positions at any time (duplicate positions allowed)
- No more than 10% of capital in momentum trades
- Automatic position sizing based on account value
- Duplicate orders on same ticker are permitted for scaling in

### Market Hours
- **Start**: 9:15 AM (after market stabilizes)
- **Stop**: 3:00 PM (avoid end-of-day volatility)
- **Best Time**: 9:30 AM - 2:30 PM

### Risk Parameters
- **Maximum Loss per Trade**: 3%
- **Risk-Reward Ratio**: Minimum 1:2.5
- **Daily Loss Limit**: Consider stopping after 3 consecutive losses

## Integration with Existing System

### With SL Watchdog
The SL watchdog will automatically:
1. Monitor VSR momentum positions
2. Apply trailing stops based on exit rules
3. Execute stop losses when triggered
4. Show 2% peak warnings as configured

### With State Manager
All positions are tracked with metadata:
- Entry price, time, and score
- Peak price for trailing stops
- Strategy identifier: "VSR_MOMENTUM"

## Performance Monitoring

### Log Files
Monitor performance in:
```
/Daily/logs/{user}/vsr_momentum_orders_YYYYMMDD.log
```

### Key Metrics to Track
1. **Win Rate**: Target > 60%
2. **Average Winner**: Target > 4%
3. **Average Loser**: Should be < 2%
4. **Hold Time**: Average 1-2 hours

## Best Practices

### DO's
✅ Run during high-volume periods (10 AM - 2 PM)
✅ Check market regime before trading
✅ Monitor VSR dashboard for quality signals
✅ Allow winners to run with trailing stops
✅ Take partial profits at 5%

### DON'Ts
❌ Trade during first/last 15 minutes
❌ Override stop losses
❌ Add to losing positions
❌ Trade on expiry days
❌ Ignore market regime

## Troubleshooting

### No Orders Placed
1. Check if VSR tracker is running
2. Verify market hours
3. Check position limits
4. Review entry criteria

### Orders Not Filling
1. Use LIMIT orders at current price
2. Check market liquidity
3. Verify margin availability

### Stop Loss Issues
1. Ensure SL_watchdog.py is running
2. Check position metadata
3. Verify exit rules integration

## Example Trade Flow

1. **Signal Generation** (12:00 PM)
   - RAINBOW shows Score: 100, VSR: 11.89, Momentum: 5.7%
   
2. **Order Placement**
   - Buy 10 shares at ₹1,615 (LIMIT order)
   - Initial stop: ₹1,566 (-3%)
   
3. **Position Management**
   - Price reaches ₹1,647 (+2%)
   - Trailing stop activated at ₹1,622
   
4. **Profit Taking**
   - Partial exit (50%) at ₹1,695 (+5%)
   - Trailing remaining position
   
5. **Final Exit**
   - Full exit at ₹1,736 (+7.5%)
   - Or stopped out at trailing level

## Advanced Configuration

### Custom Entry Criteria
Edit in `place_orders_vsr_momentum.py`:
```python
self.min_score = 80       # Minimum VSR score
self.min_vsr = 2.0       # Minimum VSR ratio
self.min_momentum = 2.0  # Minimum momentum %
self.max_momentum = 10.0 # Maximum momentum %
```

### Custom Exit Rules
Edit in `vsr_momentum_exit_rules.py`:
```python
self.initial_stop_loss_pct = 3.0
self.trailing_activation_pct = 2.0
self.trailing_distance_pct = 1.5
self.quick_profit_target = 5.0
self.full_profit_target = 8.0
```

## Safety Features

1. **Maximum Position Limits**: Prevents overexposure
2. **Time-Based Exits**: Prevents holding stale positions
3. **Momentum Validation**: Ensures continued momentum
4. **Automatic Stop Loss**: Via SL_watchdog integration
5. **Market Hours Check**: Prevents off-hours trading

---

**Note**: This is a momentum-based strategy that works best in trending markets. Always monitor market conditions and adjust parameters based on performance.