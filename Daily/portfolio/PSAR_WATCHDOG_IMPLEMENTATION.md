# PSAR Watchdog Implementation Guide

## Overview
Created a new PSAR-based stop loss watchdog (`SL_watchdog_PSAR.py`) by cloning and modifying `SL_watchdog.py`.

## Key Changes Made

### 1. **File Structure**
- **Source**: `Daily/portfolio/SL_watchdog.py` (ATR-based)
- **New File**: `Daily/portfolio/SL_watchdog_PSAR.py` (PSAR-based)
- **Helper**: `Daily/portfolio/psar_methods.py` (PSAR calculation methods)

### 2. **Class Renamed**
- `SLWatchdog` → `PSARWatchdog`

### 3. **New Dependencies**
```python
import numpy as np
from collections import deque
from kiteconnect import KiteConnect, KiteTicker  # Added KiteTicker
```

### 4. **Configuration Support**
Added to `config.ini`:
```ini
[DEFAULT]
psar_watchdog_enabled = yes  # Enable/disable PSAR watchdog

[PSAR]
start = 0.02              # Initial acceleration factor
increment = 0.02          # AF increment per new extreme
maximum = 0.2             # Maximum AF
tick_aggregate_size = 1000  # Ticks per candle
```

### 5. **Command Line Arguments**
```bash
python SL_watchdog_PSAR.py [orders_file] --product-type [CNC|MIS|BOTH]
```

### 6. **Product Type Support**
- **CNC**: Delivery positions
- **MIS**: Intraday positions
- **BOTH**: Monitor both types

### 7. **Data Structures**
Replaced ATR tracking with PSAR tracking:
```python
# Removed
self.atr_data = {}
self.sma20_hourly_data = {}

# Added
self.psar_data = {}  # PSAR values, AF, trend, EP
self.tick_buffers = {}  # Tick aggregation buffers
self.tick_candles = {}  # OHLC candles from ticks
self.instrument_tokens = {}  # Websocket subscriptions
self.position_low_prices = {}  # For SHORT positions
```

### 8. **Core PSAR Logic**

#### **Tick Aggregation**
- Listen to websocket for real-time ticks
- Aggregate every 1000 ticks (configurable) into OHLC candles
- Calculate PSAR from these candles

#### **PSAR Calculation**
- Standard Parabolic SAR algorithm
- Configurable start, increment, and maximum AF
- Tracks trend (LONG/SHORT), extreme point (EP)
- Auto-detects trend reversals

#### **Exit Logic**
- **LONG positions**: Exit when price < PSAR
- **SHORT positions**: Exit when price > PSAR
- Places limit orders with 0.5% buffer for better fills

### 9. **Websocket Integration**
- `KiteTicker` for real-time tick data
- Callbacks: `on_ticks`, `on_connect`, `on_close`, `on_error`
- Auto-reconnection on disconnect
- LTP mode (most efficient)

## Remaining Integration Steps

### Step 1: Integrate PSAR Methods
Copy methods from `psar_methods.py` into `PSARWatchdog` class:
1. `calculate_psar()`
2. `aggregate_ticks_to_candle()`
3. `check_psar_exit()`
4. `on_ticks()`, `on_connect()`, `on_close()`, `on_error()`
5. `start_websocket()`, `stop_websocket()`
6. `subscribe_position_to_websocket()`

### Step 2: Replace ATR Methods
Remove/comment out in `SL_watchdog_PSAR.py`:
- `calculate_atr_and_stop_loss()`
- `update_atr_stop_losses()`
- `check_atr_stop_loss()`
- `check_sma20_hourly_violations()`
- `update_sma20_hourly_data()`
- `check_sma20_exit_at_230pm()`
- `check_sma20_today_only()`

### Step 3: Update Position Loading
Modify `load_positions_from_zerodha()`:
- Filter by `product_type_filter` (CNC/MIS/BOTH)
- Call `subscribe_position_to_websocket()` for each position
- Initialize PSAR tracking for each position

### Step 4: Update Main Monitoring Loop
In `poll_prices()`:
- Remove ATR/SMA20 checks
- PSAR checks happen in websocket `on_ticks` callback
- Keep price polling as backup for position verification

### Step 5: Update start() Method
```python
def start(self):
    # ... existing code ...

    # Start websocket for tick data
    if self.psar_watchdog_enabled:
        self.start_websocket()

    # Load positions
    if self.orders_file:
        self.load_positions_from_orders_file()
    else:
        self.load_positions_from_zerodha()

    # Subscribe positions to websocket
    for ticker in self.tracked_positions.keys():
        self.subscribe_position_to_websocket(ticker)

    # ... rest of start logic ...
```

### Step 6: Update stop() Method
```python
def stop(self):
    self.logger.info("Stopping PSAR watchdog...")
    self.running = False

    # Stop websocket
    self.stop_websocket()

    # ... existing cleanup ...
```

### Step 7: Update main() Function
```python
def main():
    args = parse_args()

    # ... existing setup ...

    # Create watchdog with product type filter
    watchdog = PSARWatchdog(
        user_credentials=user_creds,
        config=config,
        orders_file=args.orders_file,
        price_poll_interval=args.poll_interval,
        product_type=args.product_type  # NEW
    )

    watchdog.start()
```

## Configuration Examples

### Monitor Only CNC Positions
```bash
python SL_watchdog_PSAR.py --product-type CNC
```

### Monitor Only MIS Positions
```bash
python SL_watchdog_PSAR.py --product-type MIS
```

### Monitor Both CNC and MIS
```bash
python SL_watchdog_PSAR.py --product-type BOTH
```

### Disable PSAR Watchdog
In `config.ini`:
```ini
[DEFAULT]
psar_watchdog_enabled = no
```

## Testing Plan

1. **Test with single CNC position**
2. **Test with single MIS position**
3. **Test with multiple positions (BOTH)**
4. **Test websocket disconnection/reconnection**
5. **Test PSAR exit trigger**
6. **Test enable/disable configuration**

## Files Modified/Created

1. ✅ Created: `Daily/portfolio/SL_watchdog_PSAR.py` (partial)
2. ✅ Created: `Daily/portfolio/psar_methods.py` (helper methods)
3. ✅ Created: `Daily/portfolio/PSAR_WATCHDOG_IMPLEMENTATION.md` (this file)
4. ⏳ TODO: Complete integration of PSAR methods
5. ⏳ TODO: Remove ATR/SMA20 methods
6. ⏳ TODO: Update `Daily/config.ini` with PSAR section
7. ⏳ TODO: Test implementation
8. ⏳ TODO: Update `Daily/Activity.md`
9. ⏳ TODO: Commit and push changes

## Notes

- **Backward Compatibility**: Original `SL_watchdog.py` unchanged
- **User Selection**: Users choose which watchdog to run
- **Resource Usage**: Websocket adds minimal overhead
- **Tick Limits**: Zerodha allows ~3000 instrument subscriptions
- **Rate Limits**: LTP mode has generous limits

## Future Enhancements

1. Persist PSAR state across restarts
2. Add PSAR value to portfolio summary
3. Create dashboard showing PSAR vs price chart
4. Add alerts for PSAR trend reversals
5. Backtest PSAR vs ATR performance
