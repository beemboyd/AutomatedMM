# Order Execution & SL Watchdog System Documentation

**Created:** 2025-12-08
**Author:** Claude
**Purpose:** Complete documentation of the VSR-based order execution and PSAR stop-loss watchdog systems

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Order Execution Program](#order-execution-program)
3. [SL Watchdog (PSAR-based)](#sl-watchdog-psar-based)
4. [Configuration Parameters](#configuration-parameters)
5. [Data Flow](#data-flow)
6. [How to Run Daily](#how-to-run-daily)
7. [Scheduled Jobs Reference](#scheduled-jobs-reference)
8. [Quick Reference Commands](#quick-reference-commands)

---

## System Overview

The India-TS trading system consists of two main components for automated trading:

1. **Order Execution** (`place_orders_daily_long_vsr.py`) - Places CNC/MIS orders for high-momentum tickers identified by VSR tracking
2. **SL Watchdog** (`SL_watchdog_PSAR.py`) - Monitors positions and executes stop-loss orders using Parabolic SAR and ATR-based trailing stops

### Architecture

```
VSR Scanner (hourly)
       │
       ▼
vsr_ticker_persistence.json ──► VSR Dashboard (port 3001)
       │                              │
       │                              ▼
       │                    place_orders_daily_long_vsr.py
       │                              │
       │                    ┌─────────┴─────────┐
       │                    │ Breakout Check    │
       │                    │ (4-candle high)   │
       │                    └─────────┬─────────┘
       │                              │
       │                              ▼
       │                    ┌─────────────────────┐
       │                    │ Place LIMIT Order   │
       │                    │ at breakout + 0.5%  │
       │                    └─────────┬───────────┘
       │                              │
       ▼                              ▼
   Zerodha ◄──────────────────────────┘
       │
       │ Positions filled
       ▼
┌──────────────────────────────────────────────────────────┐
│                  SL_watchdog_PSAR.py                     │
├──────────────────────────────────────────────────────────┤
│  1. Load positions from Zerodha (CNC/MIS/BOTH)           │
│  2. Calculate 20-day ATR & initial stop loss             │
│  3. Poll prices every 45 seconds                         │
│  4. Trail stop loss up as position_high increases        │
│  5. Exit partially/fully when stop loss hit              │
│  6. Exit at profit targets (2x, 3x, 4x, 5x ATR)          │
└──────────────────────────────────────────────────────────┘
```

---

## Order Execution Program

### File Location
`/Users/maverick/PycharmProjects/India-TS/Daily/trading/place_orders_daily_long_vsr.py`

### Purpose
Places CNC (delivery) or MIS (intraday) orders for high-momentum tickers identified by the VSR (Volume Spread Ratio) tracking system.

### How It Works

#### Step 1: User Authentication
```python
# Loads user credentials from config.ini sections like [API_CREDENTIALS_Sai]
users = get_available_users(config)
selected_user = select_user(users)  # Interactive selection
```

#### Step 2: Fetch VSR Momentum Tickers
- **Source:** VSR Dashboard API (`http://localhost:3001/api/trending-tickers`) or JSON file
- **Filters:**
  - Minimum VSR Score: 60
  - Minimum Momentum: 2.0%
  - Positive momentum only

#### Step 3: Breakout Detection
```python
def get_hourly_breakout_level(ticker, data_handler, lookback_candles=4):
    """Get HIGHEST high from previous 4 hourly candles"""
    # Fetches 2 days of hourly data
    # Excludes current incomplete candle
    # Returns highest high from last 4 completed hourly candles
```

#### Step 4: Entry Logic
```python
# Only place order if current price ABOVE breakout level (confirmed breakout)
if current_price <= breakout_level:
    continue  # Skip - not a breakout yet

# Place LIMIT order at 0.5% above breakout level (waiting for pullback)
limit_price = round(breakout_level * 1.005, 2)
```

#### Step 5: Position Sizing
```python
def calculate_position_size(portfolio_value, price):
    position_value = portfolio_value * (POSITION_SIZE_PERCENT / 100)  # 1%
    quantity = int(position_value / price)
    return max(1, quantity)  # At least 1 share
```

#### Step 6: Order Placement
```python
order_manager.place_order(
    tradingsymbol=ticker,
    transaction_type='BUY',
    order_type='LIMIT',
    quantity=quantity,
    price=limit_price,
    product_type='MIS'  # or 'CNC' for delivery
)
```

---

## SL Watchdog (PSAR-based)

### File Location
`/Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog_PSAR.py`

### Purpose
Real-time stop-loss monitoring using Parabolic SAR (PSAR) and ATR-based trailing stops.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SL_watchdog_PSAR                         │
├─────────────────────────────────────────────────────────────┤
│  THREADS:                                                    │
│  ├── Price Poll Thread (every 45s)                          │
│  │   └── Fetches LTP via kite.ltp()                         │
│  ├── Order Processing Thread                                 │
│  │   └── Executes queued exit orders                        │
│  └── WebSocket Thread (real-time ticks)                     │
│       └── Aggregates 1000 ticks → OHLC candles              │
├─────────────────────────────────────────────────────────────┤
│  DATA STRUCTURES:                                            │
│  ├── tracked_positions{}  - All monitored positions         │
│  ├── current_prices{}     - Latest prices per ticker        │
│  ├── position_high_prices{} - Highest price since entry     │
│  ├── atr_data{}           - ATR & stop loss per ticker      │
│  ├── psar_data{}          - PSAR values per ticker          │
│  └── order_queue          - Pending exit orders             │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Position Loading
- Supports CNC, MIS, or BOTH product types
- Loads from `kite.positions()` and `kite.holdings()`
- Creates tracked_positions with: type, quantity, entry_price, investment_amount, product type, instrument_token

#### 2. ATR-Based Stop Loss Calculation
```python
def calculate_atr_and_stop_loss(ticker):
    # Fetches 45 days of daily data
    # Calculates 20-day ATR (Average True Range)

    # Volatility categories and multipliers:
    if atr_percentage < 2.0:      # Low volatility
        multiplier = 1.0
    elif atr_percentage <= 4.0:   # Medium volatility
        multiplier = 1.5
    else:                         # High volatility
        multiplier = 2.0

    # Stop loss = Current Price - (ATR × Multiplier)
    stop_loss_price = latest_close - (latest_atr * multiplier)
```

#### 3. Trailing Stop Logic
```python
# Position high trailing - stop loss moves UP only
if position_high > stored_position_high:
    new_stop_loss = position_high - (atr_value * multiplier)

    # KEY: Only adjust upward, never downward
    if new_stop_loss > stop_loss_price:
        self.atr_data[ticker]['stop_loss'] = new_stop_loss
```

#### 4. Exit Tranches (Partial Exits)
Based on volatility category:

| Volatility | Stop Loss | Profit Target 1 | Profit Target 2 |
|------------|-----------|-----------------|-----------------|
| Low        | 50%       | 30% at 2x ATR   | 20% at 3x ATR   |
| Medium     | 40%       | 30% at 2.5x ATR | 30% at 4x ATR   |
| High       | 30%       | 30% at 3x ATR   | 40% at 5x ATR   |

#### 5. Safety Features

| Feature | Implementation |
|---------|----------------|
| Position Verification | Checks broker before every sell order |
| Duplicate Prevention | `has_pending_order` flag per position |
| Ghost Position Removal | Syncs with broker every 10 minutes |
| Dry Run Mode | `dry_run = yes` logs but doesn't execute |
| Order Retries | 5 retries with exponential backoff |
| Tick Size Rounding | Ensures valid price increments |
| Market Hours Check | Stops after 3:30 PM IST |

---

## Configuration Parameters

### config.ini Settings

```ini
[DEFAULT]
max_cnc_positions = 2
capital_deployment_percent = 1.0    # Total capital to deploy (across ALL positions)
exchange = NSE
product_type = CNC
psar_watchdog_enabled = yes

[Trading]
max_positions = 3
product_type = MIS
position_size_percent = 2.0         # Per-position size for VSR/MIS trades
ticker_cooldown_hours = 2.0

[PSAR]
start = 0.02                        # Initial acceleration factor
increment = 0.02                    # AF increment per new extreme
maximum = 0.2                       # Maximum AF
tick_aggregate_size = 1000          # Ticks per candle
dry_run = yes                       # Set to 'no' for LIVE orders
```

### capital_deployment_percent Explained

This parameter controls **what percentage of your available capital** will be used for placing orders across all positions.

**Formula:**
```
Usable Capital = Available Capital × (capital_deployment_percent / 100)
Capital per Position = Usable Capital / Number of Positions
Position Size (shares) = Capital per Position / Stock Price
```

**Example with `capital_deployment_percent = 1.0`:**

| Metric | Value |
|--------|-------|
| Available Capital | ₹10,00,000 |
| Deployment % | 1.0% |
| **Usable Capital** | **₹10,000** |
| Number of Positions | 3 |
| Capital per Position | ₹3,333 |
| Stock Price (e.g.) | ₹500 |
| **Shares to Buy** | **6 shares** |

**Comparison with Different Values:**

| `capital_deployment_percent` | Available Capital | Usable Capital | Per Position (3 stocks) |
|------------------------------|-------------------|----------------|-------------------------|
| **1.0** (current) | ₹10,00,000 | ₹10,000 | ₹3,333 |
| 5.0 | ₹10,00,000 | ₹50,000 | ₹16,667 |
| 25.0 | ₹10,00,000 | ₹2,50,000 | ₹83,333 |
| 50.0 (default fallback) | ₹10,00,000 | ₹5,00,000 | ₹1,66,667 |

---

## Data Flow

### VSR Ticker Selection
1. VSR Scanner runs hourly → generates `vsr_ticker_persistence.json`
2. VSR Dashboard API serves tickers at `http://localhost:3001/api/trending-tickers`
3. Order execution fetches tickers with:
   - Score >= 60
   - Momentum >= 2.0%
   - Positive momentum

### Order Flow
1. Fetch VSR tickers from dashboard/file
2. Check for existing positions (skip duplicates)
3. Get 4-candle hourly high (breakout level)
4. Verify current price > breakout level (confirmed breakout)
5. Place LIMIT order at breakout + 0.5%
6. Store position in state manager

### Stop Loss Flow
1. Load positions from Zerodha (CNC/MIS/BOTH)
2. Calculate 20-day ATR for each position
3. Set initial stop loss based on volatility
4. Poll prices every 45 seconds
5. Trail stop loss upward as position_high increases
6. Execute exit when price <= stop loss
7. Partial exits at profit targets

---

## How to Run Daily

### Option 1: Automatic (Scheduled Jobs)

The SL Watchdog is already scheduled:

| Job | Schedule | What It Does |
|-----|----------|--------------|
| `sl_watchdog_start` | 9:15 AM Mon-Fri | Runs `start_all_sl_watchdogs.py` |
| `sl_watchdog_stop` | 3:30 PM Mon-Fri | Kills all watchdog processes |

**Verify jobs are loaded:**
```bash
launchctl list | grep india-ts.*sl_watchdog
```

**If not loaded, install them:**
```bash
python /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/install_plists.py
```

### Option 2: Manual Start

#### Start SL Watchdog
```bash
# Start for all users with valid tokens
python /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/start_all_sl_watchdogs.py

# OR start PSAR watchdog for specific user (CNC positions)
python /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog_PSAR.py --product-type CNC

# For MIS (intraday) positions
python /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog_PSAR.py --product-type MIS

# For BOTH CNC and MIS
python /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog_PSAR.py --product-type BOTH
```

#### Start Order Execution
```bash
# VSR-based order execution (interactive)
python /Users/maverick/PycharmProjects/India-TS/Daily/trading/place_orders_daily_long_vsr.py

# VSR momentum orders (interactive)
python /Users/maverick/PycharmProjects/India-TS/Daily/trading/place_orders_vsr_momentum.py --user Sai --mode LIVE
```

### Prerequisites Checklist

Before the system runs automatically each day:

1. **Access Token**: Ensure `config.ini` has a valid `access_token` for at least one user
2. **Token Refresh**: After refreshing the Zerodha token, run:
   ```bash
   ./Daily/refresh_token_services.sh
   ```
3. **PSAR Config**: Check `config.ini` settings:
   ```ini
   [DEFAULT]
   psar_watchdog_enabled = yes    # Enable/disable

   [PSAR]
   dry_run = no                   # Set to 'no' for LIVE orders
   ```

---

## Scheduled Jobs Reference

### Jobs Required for Order Execution & SL Watchdog

| Job Label | Schedule | Script | Purpose |
|-----------|----------|--------|---------|
| `com.india-ts.sl_watchdog_start` | 9:15 AM Mon-Fri | `start_all_sl_watchdogs.py` | Start SL monitoring |
| `com.india-ts.sl_watchdog_stop` | 3:30 PM Mon-Fri | `pkill SL_watchdog` | Stop SL monitoring |
| `com.india-ts.vsr-tracker-enhanced` | 9:15 AM Mon-Fri | `vsr_tracker_service_enhanced.py` | Track VSR tickers |
| `com.india-ts.vsr-dashboard` | 9:15 AM Mon-Fri | `vsr_tracker_dashboard.py` | Serve VSR API |
| `com.india-ts.long_reversal_daily` | Every 30 min 9-3:30 | `Long_Reversal_Daily.py` | Generate scan results |
| `com.india-ts.synch_zerodha_local` | Every 15 min 9:15-3:30 | `synch_zerodha_cnc_positions.py` | Sync positions |

### Supporting Jobs

| Job Label | Schedule | Purpose |
|-----------|----------|---------|
| `com.india-ts.vsr-telegram-alerts-enhanced` | 8:55 AM Mon-Fri | Telegram alerts |
| `com.india-ts.vsr-shutdown` | 3:30 PM Mon-Fri | Stop VSR services |
| `com.india-ts.market_regime_analyzer_5min` | Every 5 min | Market regime analysis |

---

## Quick Reference Commands

### Check Status
```bash
# See all loaded India-TS jobs
launchctl list | grep india-ts

# Check running watchdog processes
ps aux | grep SL_watchdog

# Check watchdog logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/sl_watchdog_master.log

# Check PSAR watchdog log for specific user
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/Sai/SL_watchdog_PSAR_Sai.log
```

### Start/Stop Jobs
```bash
# Start SL watchdog manually (triggers the job now)
launchctl start com.india-ts.sl_watchdog_start

# Stop SL watchdog manually
launchctl start com.india-ts.sl_watchdog_stop

# Kill all watchdog processes immediately
pkill -f "SL_watchdog.*India-TS"
```

### Configuration Check
```bash
# Verify config.ini has valid access token
grep -A3 "API_CREDENTIALS_Sai" /Users/maverick/PycharmProjects/India-TS/Daily/config.ini

# Check PSAR settings
grep -A5 "\[PSAR\]" /Users/maverick/PycharmProjects/India-TS/Daily/config.ini
```

### Install/Validate Plists
```bash
# Install all India-TS plists from backup
python /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/install_plists.py

# Validate plist integrity
python /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/validate_plists.py
```

---

## File Locations Summary

| Component | Location |
|-----------|----------|
| Order Execution (VSR) | `Daily/trading/place_orders_daily_long_vsr.py` |
| Order Execution (Momentum) | `Daily/trading/place_orders_vsr_momentum.py` |
| SL Watchdog (PSAR) | `Daily/portfolio/SL_watchdog_PSAR.py` |
| SL Watchdog Starter | `Daily/portfolio/start_all_sl_watchdogs.py` |
| Configuration | `Daily/config.ini` |
| VSR Persistence | `Daily/data/vsr_ticker_persistence.json` |
| Plist Backups | `Daily/scheduler/plists/` |
| Logs | `Daily/logs/` |

---

## Troubleshooting

### SL Watchdog Not Starting
1. Check access token is valid in `config.ini`
2. Verify market hours (9:15 AM - 3:30 PM IST)
3. Check logs: `tail -f Daily/logs/sl_watchdog_master.log`

### Orders Not Placing
1. Verify VSR Dashboard is running: `curl http://localhost:3001/api/trending-tickers`
2. Check for valid tickers with positive momentum
3. Ensure sufficient capital in account

### Ghost Positions
1. Run position sync: `python Daily/utils/synch_zerodha_cnc_positions.py --force`
2. Check broker positions match local state
3. SL Watchdog auto-syncs every 10 minutes

---

*Document generated: 2025-12-08*
