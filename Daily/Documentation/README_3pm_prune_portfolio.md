# 3PM Portfolio Pruning Scheduler

This document explains the automated 3PM portfolio pruning functionality based on Day 1 Return analysis.

## Overview

The `3PM_Prune_Portfolio.py` script runs daily at 3:00 PM IST to identify and exit underperforming positions based on statistical analysis from the Brooks Strategy.

## Exit Rule

**If Day 1 Return < 1.0%, exit the position**

### Statistical Evidence
- Winners average: ~2.5% on Day 1
- Losers average: ~0.6% on Day 1  
- Performance difference: 311.5%
- Early momentum is crucial for success

## Installation

### 1. Load the Launch Agent

```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.3pm_prune_portfolio.plist
```

### 2. Verify it's loaded

```bash
launchctl list | grep 3pm_prune_portfolio
```

### 3. Manual Run (for testing)

```bash
# Interactive mode - prompts for user selection
python3 /Users/maverick/PycharmProjects/India-TS/Daily/scripts/3PM_Prune_Portfolio.py --force

# Run for specific user (with confirmation prompt)
python3 /Users/maverick/PycharmProjects/India-TS/Daily/scripts/3PM_Prune_Portfolio.py --user Sai --force

# Run without confirmation prompt (for automation)
python3 /Users/maverick/PycharmProjects/India-TS/Daily/scripts/3PM_Prune_Portfolio.py --user Sai --force --no-confirm

# Dry run (analyze without placing orders)
python3 /Users/maverick/PycharmProjects/India-TS/Daily/scripts/3PM_Prune_Portfolio.py --force --dry-run
```

### Interactive Features

When run without specifying a user, the script will:
1. Display a list of available users from config and orders directory
2. Prompt for user selection with numbered options
3. Show positions to be exited with their values
4. Ask for confirmation before placing orders (unless --no-confirm is used)

Example interaction:
```
==================================================
3PM Portfolio Pruning - User Selection
==================================================

Available users:
  1. Sai
  2. Som  
  3. Su
  0. Exit

Select user number (or 0 to exit): 1

Selected user: Sai

[... analysis runs ...]

============================================================
POSITIONS TO BE EXITED:
============================================================
WIPRO: 100 shares @ ₹402.00 = ₹40,200.00 (Return: 0.50%)
TECHM: 50 shares @ ₹1,005.00 = ₹50,250.00 (Return: 0.75%)

Total value to be sold: ₹90,450.00
============================================================

Proceed with exit orders? (yes/no): yes
```

## Monitoring

### Check Logs

User-specific logs are created in:
```
Daily/logs/{user_name}/3PM_prune_portfolio_{user_name}.log
```

Standard output/error logs:
```
Daily/logs/3pm_prune_portfolio_stdout.log
Daily/logs/3pm_prune_portfolio_stderr.log
```

### Example Log Output

```
2025-05-31 15:00:00 - INFO - Starting 3PM Portfolio Pruning
2025-05-31 15:00:01 - INFO - Found 5 orders placed today: RELIANCE, TCS, INFY, WIPRO, HCLTECH
2025-05-31 15:00:02 - INFO - RELIANCE: Entry: ₹2500.00, Current: ₹2562.50, Day 1 Return: 2.50%
2025-05-31 15:00:02 - INFO - RELIANCE performing well: 2.50% >= 1.00% threshold
2025-05-31 15:00:03 - INFO - WIPRO: Entry: ₹400.00, Current: ₹402.00, Day 1 Return: 0.50%
2025-05-31 15:00:03 - WARNING - WIPRO UNDERPERFORMING: 0.50% < 1.00% threshold
2025-05-31 15:00:05 - INFO - EXIT ORDER PLACED - WIPRO: Sold 100 shares at market
```

## Uninstallation

To stop and unload the scheduler:

```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.3pm_prune_portfolio.plist
```

## How It Works

1. **3:00 PM Daily**: Script automatically runs
2. **Load Today's Orders**: Reads orders placed today from JSON files
3. **Fetch Positions**: Gets current CNC positions from Zerodha
4. **Calculate Returns**: Computes Day 1 return for each position
5. **Identify Underperformers**: Flags positions with < 1.0% return
6. **Place Exit Orders**: Market orders to sell underperforming positions
7. **Log Results**: Detailed logging of all actions

## Command Line Options

- `--user USER`: Specify user name (otherwise prompts for selection)
- `--force`: Run regardless of time (for testing)
- `--dry-run`: Analyze without placing orders
- `--no-confirm`: Skip confirmation prompt (used for automated runs)

## Integration with Trading System

This pruning mechanism works alongside:
- `SL_watchdog.py`: Monitors stop losses and SMA20 violations
- `place_orders_daily.py`: Places new orders based on scans
- Brooks Strategy signals: Identifies high-probability setups

The 3PM pruning adds an additional layer of risk management by cutting losses early on positions that fail to show expected Day 1 momentum.

## Notes

- Only processes positions from today's orders
- Ignores holdings from previous days
- Requires market to be open (9:15 AM - 3:30 PM IST)
- Executes at 3:00 PM to allow time before market close
- All exits are market orders for immediate execution