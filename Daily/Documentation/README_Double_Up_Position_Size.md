# Double Up Position Size Tool

A powerful interactive tool for doubling position sizes on performing stocks in your portfolio.

## Overview

This program allows you to:
- View your entire CNC portfolio with real-time performance metrics
- See positions sorted by performance (best to worst)
- Interactively select which positions to double
- Place market orders to add equal quantity of selected stocks
- View available funds before confirming orders

## Usage

### Basic Usage

```bash
# Interactive mode - prompts for user selection
python3 Double_Up_Position_Size.py

# Specify user directly
python3 Double_Up_Position_Size.py --user Sai
```

## Features

### 1. Portfolio Display
- Shows all CNC positions (both positions and holdings)
- Real-time price updates
- Color-coded P&L (green for profit, red for loss)
- Sorted by performance percentage

### 2. Interactive Selection
Multiple ways to select positions:
- Individual: `1,3,5` (select positions 1, 3, and 5)
- Range: `1-5` (select positions 1 through 5)
- All: `ALL` (select all positions)
- Mixed: `1,3-5,7` (combine individual and ranges)

### 3. Confirmation Screen
Before placing orders, you'll see:
- Selected positions with quantity to add
- Investment required for each position
- Total investment needed
- Available cash balance
- Current P&L % for each position

### 4. Order Placement
- Places MARKET orders for immediate execution
- Uses CNC product type for delivery
- Tags orders with "DOUBLE_UP" for tracking
- Shows success/failure for each order

## Example Session

```
============================================================
DOUBLE UP POSITION SIZE
============================================================
User: Sai
Time: 2025-06-02 10:45:00

Fetching portfolio data...
Updating live prices...

============================================================
PORTFOLIO PERFORMANCE - Sai
============================================================
╒═══╤══════════╤═══════╤═══════════╤═══════════╤══════════════╤═══════════════╤═══════════════╤═════════╕
│ # │ Symbol   │   Qty │ Avg Price │       LTP │   Investment │ Current Value │           P&L │   P&L % │
╞═══╪══════════╪═══════╪═══════════╪═══════════╪══════════════╪═══════════════╪═══════════════╪═════════╡
│ 1 │ RELIANCE │   100 │  ₹2500.00 │  ₹2650.00 │  ₹250,000.00 │   ₹265,000.00 │   ₹15,000.00  │   6.00% │
│ 2 │ TCS      │    50 │  ₹3200.00 │  ₹3350.00 │  ₹160,000.00 │   ₹167,500.00 │    ₹7,500.00  │   4.69% │
│ 3 │ INFY     │   200 │  ₹1400.00 │  ₹1450.00 │  ₹280,000.00 │   ₹290,000.00 │   ₹10,000.00  │   3.57% │
│ 4 │ WIPRO    │   300 │   ₹400.00 │   ₹398.00 │  ₹120,000.00 │   ₹119,400.00 │     ₹-600.00  │  -0.50% │
╘═══╧══════════╧═══════╧═══════════╧═══════════╧══════════════╧═══════════════╧═══════════════╧═════════╛

--------------------------------------------------------
TOTAL: Investment: ₹810,000.00 | Current Value: ₹841,900.00 | P&L: ₹31,900.00 (3.94%)
--------------------------------------------------------

============================================================
SELECT POSITIONS TO DOUBLE
============================================================

Enter position numbers to double (comma-separated)
Example: 1,3,5 or 1-5 or ALL
Enter 0 or press Enter to cancel

Your selection: 1-3

================================================================================
CONFIRMATION - POSITIONS TO DOUBLE
================================================================================
╒══════════╤══════════════╤═══════════════╤═══════════════════╤════════════════╕
│ Symbol   │   Qty to Add │ Current Price │ Investment Needed │   Current P&L% │
╞══════════╪══════════════╪═══════════════╪═══════════════════╪════════════════╡
│ RELIANCE │          100 │     ₹2,650.00 │      ₹265,000.00 │           6.00 │
│ TCS      │           50 │     ₹3,350.00 │      ₹167,500.00 │           4.69 │
│ INFY     │          200 │     ₹1,450.00 │      ₹290,000.00 │           3.57 │
╘══════════╧══════════════╧═══════════════╧═══════════════════╧════════════════╛

Total Investment Required: ₹722,500.00
================================================================================
Available Cash: ₹1,500,000.00

Proceed with orders? (YES/NO): YES

============================================================
PLACING ORDERS
============================================================
✅ RELIANCE: Order placed successfully (ID: 240602000123456)
✅ TCS: Order placed successfully (ID: 240602000123457)
✅ INFY: Order placed successfully (ID: 240602000123458)

============================================================
Orders Summary: 3 successful, 0 failed
============================================================
```

## Safety Features

1. **User Authentication**: Verifies credentials before connecting
2. **Real-time Pricing**: Uses latest market prices for calculations
3. **Fund Verification**: Shows available cash before order placement
4. **Confirmation Required**: Must type "YES" to proceed with orders
5. **Error Handling**: Graceful handling of API errors and network issues

## Best Practices

1. **Review Performance**: Check which positions are performing well before doubling
2. **Check Funds**: Ensure sufficient funds are available
3. **Market Hours**: Run during market hours for accurate prices
4. **Start Small**: Test with one or two positions first
5. **Monitor Orders**: Check order status after placement

## Integration

This tool integrates with:
- Zerodha Kite API for real-time data and order placement
- User context management for multi-user support
- Daily trading system configuration

## Notes

- Only works with CNC (delivery) positions
- Ignores MIS (intraday) positions
- Places MARKET orders for immediate execution
- Adds delay between orders to avoid rate limiting
- Shows both positions and holdings data