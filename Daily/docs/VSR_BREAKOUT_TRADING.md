# VSR Breakout Trading System Documentation

## Overview
The VSR Breakout Trading System (`place_orders_daily_long_vsr.py`) is an automated trading script that monitors the VSR (Volume Spread Ratio) dashboard for high-momentum stocks and places orders based on hourly candlestick breakouts.

## Purpose
- Monitor VSR dashboard (http://localhost:3001/) for trending tickers
- Identify stocks with positive momentum and high VSR scores
- Enter positions when price breaks above previous hourly candle high
- Manage position sizing at 1% of portfolio per trade
- Provide user control over ticker selection before order placement

## Key Features

### 1. VSR Dashboard Integration
- Fetches real-time data from VSR dashboard API
- Filters tickers based on:
  - Minimum VSR score: 60
  - Minimum positive momentum: 2.0%
  - Days tracked in the system

### 2. Hourly Breakout Strategy
- Entry Signal: Price crosses above previous hourly candle high
- Entry Price: Previous hourly high + 0.1% buffer
- Stop Loss: 2% below entry price
- Product Type: CNC (Cash and Carry - delivery)

### 3. Position Sizing
- Fixed 1% of total portfolio value per position
- Maximum 5 positions at a time
- Calculates based on available cash + holdings value

### 4. User Controls
- Interactive ticker selection with exclusion option
- Confirmation required before placing orders
- Display of all relevant metrics before trading

## Configuration

### System Requirements
- VSR Dashboard running on port 3001
- Zerodha account with API access
- Python 3.7+ with required libraries
- Active internet connection

### Configuration Parameters
```python
VSR_DASHBOARD_URL = "http://localhost:3001/api/vsr-tickers"
MIN_VSR_SCORE = 60          # Minimum VSR score
MIN_MOMENTUM = 2.0           # Minimum momentum %
POSITION_SIZE_PERCENT = 1.0  # Portfolio % per position
MAX_POSITIONS = 5            # Maximum concurrent positions
```

## Workflow

### 1. Data Collection
```
VSR Dashboard → API Call → Filter Tickers → Sort by Score/Momentum
```

### 2. Signal Generation
```
Fetch Hourly Data → Identify Previous High → Check Current Price → Generate Entry Level
```

### 3. Order Execution
```
Calculate Position Size → Set Entry/Stop Loss → Place Limit Order → Update State
```

## Usage

### Manual Execution
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/trading
python3 place_orders_daily_long_vsr.py
```

### Automated Execution (Future)
Schedule via cron/launchd:
- Time: 5 minutes after every hour
- Days: Monday to Friday
- Hours: 10:05 AM, 11:05 AM, 12:05 PM, 1:05 PM IST

Example cron entry:
```bash
5 10,11,12,13 * * 1-5 cd /path/to/India-TS/Daily/trading && python3 place_orders_daily_long_vsr.py --auto
```

## Sample Output

```
================================================================================
VSR DAILY LONG BREAKOUT TRADING SYSTEM
================================================================================

Available accounts:
1. Sai
2. Lavanya

Select account (1-2): 1

✅ Connected to Zerodha for user: Sai

Fetching VSR tickers from dashboard...
✅ Found 8 VSR tickers with positive momentum

================================================================================
VSR BREAKOUT CANDIDATES
================================================================================
No.   Ticker       Score    Momentum %   VSR      Price      Days  
--------------------------------------------------------------------------------
1     KRBL         85       5.23         2.45     ₹425.30    3     
2     INDIANB      80       4.15         2.10     ₹582.50    5     
3     LUPIN        75       3.88         1.95     ₹1245.60   2     
4     KPIL         70       2.95         1.82     ₹892.40    4     
--------------------------------------------------------------------------------

Enter ticker numbers to EXCLUDE (comma-separated, or press Enter for none): 

📊 Ready to place orders for 4 ticker(s)
Position size: 1.0% of portfolio per ticker

Proceed with order placement? (yes/no): yes

Placing orders...
✅ Order placed successfully for KRBL: 220250811000123
✅ Order placed successfully for INDIANB: 220250811000124
✅ Order placed successfully for LUPIN: 220250811000125
✅ Order placed successfully for KPIL: 220250811000126

================================================================================
ORDER SUMMARY
================================================================================
✅ Successfully placed 4 order(s):
  - KRBL: 235 shares @ ₹427.72
  - INDIANB: 171 shares @ ₹584.85
  - LUPIN: 80 shares @ ₹1250.48
  - KPIL: 112 shares @ ₹896.05
================================================================================
```

## Risk Management

### Position Limits
- Maximum 5 positions at a time
- 1% portfolio allocation per position
- Maximum 5% portfolio risk exposure

### Stop Loss Rules
- Initial stop: 2% below entry price
- Trailing stop: To be implemented
- Time-based exit: End of day for non-performers

### Entry Filters
- Minimum VSR score requirement
- Positive momentum only
- Sufficient volume confirmation
- No duplicate positions

## Dependencies

### Python Libraries
- pandas: Data manipulation
- requests: API calls
- configparser: Configuration management
- datetime: Time handling
- logging: Event logging

### System Components
- VSR Dashboard (port 3001)
- User Context Manager
- State Manager
- Order Manager
- Data Handler

### External Services
- Zerodha Kite API
- NSE data feed
- VSR calculation engine

## Error Handling

### Connection Errors
- Retry logic for API calls
- Fallback to cached data
- Graceful degradation

### Order Failures
- Logging of all errors
- State rollback on failure
- Manual intervention alerts

### Data Issues
- Validation of ticker data
- Handling of missing prices
- Skip invalid candidates

## Monitoring

### Log Files
Location: `/Daily/logs/{username}/place_orders_vsr_{username}.log`

### Key Metrics
- Orders placed per session
- Success/failure rates
- Average position size
- Portfolio utilization

### Alerts
- Failed orders
- Connection issues
- Unusual market conditions

## Future Enhancements

### Planned Features
1. Automated scheduling via launchd
2. Trailing stop loss implementation
3. Multi-timeframe confirmation
4. Volume spike detection
5. Sector rotation analysis
6. Performance analytics dashboard

### Integration Points
1. Link with position watchdog for monitoring
2. Connect to risk management system
3. Integrate with P&L tracking
4. Add to daily reporting system

## Troubleshooting

### Common Issues

1. **Dashboard Not Accessible**
   - Check if VSR dashboard is running on port 3001
   - Verify localhost connectivity
   - Restart dashboard service

2. **No Tickers Found**
   - Verify market hours
   - Check minimum score/momentum settings
   - Ensure data feed is active

3. **Order Placement Fails**
   - Verify Zerodha API credentials
   - Check market hours
   - Ensure sufficient funds

4. **Incorrect Position Size**
   - Verify portfolio value calculation
   - Check margin requirements
   - Review position sizing logic

## Support

For issues or questions:
1. Check log files for detailed error messages
2. Verify all services are running
3. Review this documentation
4. Contact system administrator

## Version History

### v1.0.0 (2025-08-11)
- Initial implementation
- VSR dashboard integration
- Hourly breakout strategy
- User confirmation flow
- 1% position sizing
- Basic risk management

---

*Last Updated: August 11, 2025*