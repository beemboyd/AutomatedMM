# VSR Order Watchdog Documentation

## Overview
The VSR Order Watchdog is an automated trading system that continuously monitors VSR (Volume Spread Ratio) momentum tickers for:
1. **BUY signals**: Clean breakouts above 4-candle resistance levels
2. **SELL signals**: Breakdowns below 2-candle support levels

The system operates entirely in-memory without maintaining any state files, ensuring clean operation across restarts.

## Strategy Logic

### Entry (BUY) Conditions
1. Fetch high-momentum VSR tickers (Score ≥ 60, Momentum ≥ 2%)
2. Calculate resistance level from the highest high of previous 4 hourly candles
3. Monitor for clean breakout: Current Price > Resistance
4. Place LIMIT BUY order at Resistance + 0.5%
5. Position size: 1% of portfolio value
6. Maximum positions: 5

### Exit (SELL) Conditions
1. Monitor all active MIS positions
2. Calculate support level from the lowest low of previous 2 hourly candles
3. Monitor for breakdown: Current Price < Support
4. Place MARKET SELL order immediately
5. Exit captures both profits and limits losses

## Key Features
- **No State Files**: All tracking is in-memory only
- **Real-time Monitoring**: Polls every 60 seconds during market hours
- **Clean Breakouts Only**: Waits for price to clear congestion/resistance
- **Dynamic Support/Resistance**: Levels are recalculated continuously
- **Position Sync**: Syncs with broker positions on each cycle
- **MIS Orders Only**: All positions are intraday (auto-squared off at 3:20 PM)

## Configuration
Located in `order_watchdog_vsr.py`:
```python
MIN_VSR_SCORE = 60           # Minimum VSR score
MIN_MOMENTUM = 2.0            # Minimum momentum %
POSITION_SIZE_PERCENT = 1.0   # 1% per position
MAX_POSITIONS = 5             # Maximum concurrent positions
POLL_INTERVAL = 60            # Check every 60 seconds
BREAKOUT_BUFFER = 0.005       # 0.5% above resistance
LOOKBACK_CANDLES_BUY = 4      # Candles for resistance
LOOKBACK_CANDLES_SELL = 2     # Candles for support
```

## Usage

### Starting the Watchdog
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/services
./start_vsr_order_watchdog.sh
```

### Stopping the Watchdog
```bash
./stop_vsr_order_watchdog.sh
```

### Running in Test Mode
```bash
python3 Daily/trading/order_watchdog_vsr.py --user Sai --test
```

### Command Line Options
- `-u, --user`: Select user account (default: Sai)
- `--test`: Run single monitoring cycle for testing

## Monitoring

### Log Files
- **Main Log**: `logs/Sai/order_watchdog_vsr_YYYYMMDD.log`
- **Console Log**: `logs/vsr_order_watchdog_console.log`

### Log Entries
- 📈 Breakout detected - Buy signal
- 📉 Breakdown detected - Sell signal
- ✅ Order placed successfully
- 🔻 Exit triggered

## Example Scenarios

### Scenario 1: Clean Breakout
```
Ticker: RELIANCE
Resistance (4-candle high): ₹2500
Current Price: ₹2510
Action: Place LIMIT BUY at ₹2512.50 (2500 * 1.005)
```

### Scenario 2: In Congestion
```
Ticker: TCS
Resistance (4-candle high): ₹3500
Current Price: ₹3480
Action: Wait (price below resistance, no order)
```

### Scenario 3: Support Breakdown
```
Ticker: INFY
Support (2-candle low): ₹1500
Current Price: ₹1495
Entry was at: ₹1520
Action: Place MARKET SELL immediately
```

## Risk Management
1. **Position Sizing**: 1% of portfolio per position limits risk
2. **Max Positions**: Limited to 5 concurrent positions (5% max exposure)
3. **MIS Orders**: All positions auto-squared off at EOD
4. **Support-based Exits**: Dynamic 2-candle support acts as trailing stop
5. **Clean Breakouts**: Only enters after clearing resistance (reduces false signals)

## Data Sources
1. **Primary**: VSR Dashboard API (`http://localhost:3001/api/trending-tickers`)
2. **Fallback**: VSR JSON persistence file
3. **Price Data**: Zerodha Kite API (real-time quotes and historical candles)

## Architecture
```
VSROrderWatchdog
├── sync_active_positions()      # Sync MIS positions from broker
├── fetch_vsr_tickers()          # Get high-momentum tickers
├── calculate_resistance_level() # 4-candle resistance
├── calculate_support_level()    # 2-candle support
├── monitor_ticker_for_buy()     # Check for breakouts
├── monitor_position_for_sell()  # Check for breakdowns
├── place_breakout_order()       # LIMIT BUY at resistance + 0.5%
├── place_sell_order()           # MARKET SELL on breakdown
└── run_monitoring_cycle()       # Main loop (60 seconds)
```

## Performance Metrics
- **Breakout Success Rate**: Tracks clean breakouts that continue upward
- **Average Hold Time**: Typically 1-4 hours (intraday)
- **Win/Loss Ratio**: Depends on market conditions
- **Slippage**: Minimal with LIMIT orders for entry

## Best Practices
1. **Start after 9:30 AM**: Allow market to settle
2. **Monitor logs**: Check for successful breakouts
3. **Review daily**: Analyze performance and adjust parameters
4. **Market conditions**: Works best in trending markets
5. **Stop before 3:00 PM**: Allow time for position management

## Troubleshooting

### No Breakouts Detected
- Check if VSR dashboard is running
- Verify market is in session
- Review resistance levels in logs
- Consider lowering MIN_VSR_SCORE temporarily

### Orders Not Placing
- Check Zerodha API connection
- Verify sufficient margin
- Review order rejection reasons in logs

### Positions Not Syncing
- Restart watchdog to force sync
- Check broker positions manually
- Verify MIS vs CNC product type

## Integration Points
- **VSR Dashboard**: Source of momentum tickers
- **Zerodha Kite**: Order execution and position management
- **State Manager**: Optional position tracking (not for persistence)
- **Order Manager**: Handles order placement logic

## Future Enhancements
1. Add profit target exits (e.g., 2% gain)
2. Implement partial profit booking
3. Add volume confirmation for breakouts
4. Include market regime filters
5. Support for different timeframes (15min, 30min)
6. Email/Telegram alerts for trades

## Related Scripts
- `place_orders_daily_long_vsr.py`: One-time VSR order placement
- `test_vsr_breakout_logic.py`: Test breakout detection logic
- `VSR_Momentum_Scanner.py`: Generates VSR signals

## Author
Created by Claude on August 11, 2025
Based on VSR momentum strategy with hourly breakout confirmation