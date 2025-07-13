# G Pattern Auto Trader Guide

## Overview
The G Pattern Auto Trader follows a strategic approach based on G_Pattern_Summary.txt recommendations, focusing on gradual position building through pattern evolution.

## Configuration

Edit the following sections in `/Users/maverick/PycharmProjects/India-TS/Daily/config.ini`:

### [RISK_MANAGEMENT]
```ini
base_capital = 100000          # Your trading capital
position_size_percentage = 5.0  # % of capital per position
max_positions = 5              # Maximum concurrent positions
max_risk_per_trade = 2.0       # Maximum risk % per trade
g_pattern_multiplier = 1.5     # Multiplier for high-prob trades (>80%)
```

### [G_PATTERN_TRADING]
```ini
min_probability_score = 65.0    # Minimum score to consider
initial_position_percent = 25.0  # % for initial positions
double_position_percent = 50.0   # % when doubling
full_position_percent = 100.0    # % for full positions
enable_auto_trading = yes        # Enable/disable auto trading
confirm_before_order = yes       # Ask for confirmation
```

## Usage

### Basic Usage
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/trading
python g_pattern_auto_trader.py
```

### With Different User
```bash
python g_pattern_auto_trader.py --user Su
```

### Force Run (Outside Market Hours)
```bash
python g_pattern_auto_trader.py --force
```

## Strategy-Based Approach

The auto trader now follows the G Pattern Summary recommendations:

### Categories:
1. **G PATTERN CONFIRMED**: Full position (100%) - Deployed in following days as pattern evolves
2. **PATTERN EMERGING**: Initial position (25%) - Immediate entry for pattern building
3. **WATCH CLOSELY**: Pre-entry monitoring - No positions yet
4. **WATCH ONLY**: Observation only

## How It Works

1. **Reads Strategy**: Parses G_Pattern_Summary.txt for categorized recommendations
2. **Filters by Category**: Currently focuses on PATTERN EMERGING stocks for initial positions
3. **Checks Existing Positions**: Skips stocks already in portfolio
4. **Calculates Position Size**: Uses formula from config.ini deployment percentage
5. **Shows Confirmation**: Displays strategic allocation for review
6. **Places Orders**: Executes MARKET orders after confirmation

## Position Sizing Formula

For PATTERN EMERGING stocks:
```
Position Size = (capital_deployment_percent × Available Capital) ÷ Number of Stocks
```

Where capital_deployment_percent is read from config.ini (default: 25%)

Example:
- Available Capital: ₹2,000,000
- Config Deployment: 25%
- Number of Stocks: 3
- Total Allocation = 25% × ₹2,000,000 = ₹500,000
- Per Stock = ₹500,000 ÷ 3 = ₹166,667

## Risk Management

- **Maximum Risk**: Each trade is limited to `max_risk_per_trade` (default 2%)
- **Position Limit**: Maximum `max_positions` concurrent positions
- **Stop Loss**: Automatically placed based on scanner recommendations
- **Capital Protection**: Never risks more than configured limits

## Order Confirmation Display

```
📊 G PATTERN AUTO TRADER - ORDER CONFIRMATION
================================================================================

Base Capital: ₹1,00,000.00
Position Size: 5% (₹5,000.00)
Max Risk per Trade: 2%
Minimum Probability Score: 65%

--------------------------------------------------------------------------------
PROPOSED ORDERS:
--------------------------------------------------------------------------------

1. GLENMARK - G_Pattern
   Probability Score: 92.5%
   Recommendation: G PATTERN CONFIRMED - FULL POSITION (100%)
   Entry: ₹750.50 | Stop Loss: ₹735.00 | Target: ₹781.00
   Quantity: 10 shares (100% position)
   Position Value: ₹7,505.00
   Risk: ₹155.00 (0.16% of capital)

2. ABCAPITAL - Building_G
   Probability Score: 78.3%
   Recommendation: G PATTERN DEVELOPING - DOUBLE POSITION (50%)
   Entry: ₹185.25 | Stop Loss: ₹180.00 | Target: ₹195.75
   Quantity: 13 shares (50% position)
   Position Value: ₹2,408.25
   Risk: ₹68.25 (0.07% of capital)

--------------------------------------------------------------------------------
TOTAL ORDERS: 2
TOTAL VALUE: ₹9,913.25 (9.9% of capital)
TOTAL RISK: ₹223.25 (0.22% of capital)
--------------------------------------------------------------------------------

Do you want to place these orders? (yes/no): 
```

## Order History

All orders are saved to:
```
/Users/maverick/PycharmProjects/India-TS/Daily/G_Pattern_Master/G_Pattern_Order_History.csv
```

## Schedule Integration

Add to your daily workflow:

### Morning (9:00 AM)
1. Run KC scanner: `python scanners/KC_Upper_Limit_Trending.py`
2. Run master tracker: `python scanners/G_Pattern_Master_Tracker.py`
3. Run auto trader: `python trading/g_pattern_auto_trader.py`

### Mid-day (12:30 PM)
- Re-run auto trader for new opportunities

### EOD (3:15 PM)
- Final scan for any missed opportunities

## Safety Features

1. **Market Hours Check**: Only runs during market hours (use --force to override)
2. **Existing Position Check**: Won't double up on existing positions
3. **User Confirmation**: Always asks before placing orders
4. **Risk Limits**: Enforces position and risk limits from config
5. **Stop Loss**: Automatically places stop loss orders

## Troubleshooting

### No Orders Generated
- Check if probability scores are >= 65%
- Verify you're not already positioned in high-prob stocks
- Ensure latest scanner report exists

### Order Placement Failed
- Check Kite access token is valid
- Verify sufficient margin available
- Check if stock is in F&O ban period

### Configuration Issues
- Ensure config.ini has all required sections
- Verify base_capital matches your actual capital
- Check position sizing makes sense for your account

## Best Practices

1. **Review Daily**: Always review orders before confirming
2. **Start Small**: Begin with smaller position sizes
3. **Monitor Positions**: Track your G Pattern positions closely
4. **Update Config**: Adjust parameters based on performance
5. **Keep Logs**: Check logs for any issues or patterns

---

Remember: This tool is meant to assist, not replace your judgment. Always review and understand each trade before confirming.