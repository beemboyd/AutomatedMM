# India-TS Version 2.0 Project Summary

## Version 2.0 Overview

Version 2.0 of the India Trading System (India-TS) represents a significant architectural improvement, introducing a real-time position monitoring system that eliminates reliance on Zerodha's GTT feature for risk management. This version focuses on reliability, real-time responsiveness, and robust error handling.

## Key Enhancements in Version 2.0

1. **Real-time Position Watchdog**:
   - WebSocket-based continuous position monitoring
   - Pub-sub model with immediate reaction to price movements
   - Handles stop-loss and take-profit execution entirely locally

2. **Improved Reliability**:
   - Eliminates GTT synchronization issues by removing GTT dependency
   - Stateless design minimizes system state inconsistencies
   - Comprehensive retry mechanisms with exponential backoff
   - Automatic reconnection for WebSocket disconnections

3. **System Architecture Changes**:
   - Moved from polling-based to event-driven architecture
   - Separated order placement (entry) from risk management (exit)
   - Introduced dedicated service for position monitoring

4. **Gap Strategy Trading System** (NEW):
   - Identifies trading opportunities based on price gaps between market sessions
   - Detects gap up/down patterns combined with intraday trend confirmation
   - Scheduled execution at market open (9:15, 9:30, and 9:45 AM)
   - Analyzes Higher High/Higher Low and Lower High/Lower Low patterns
   - Generates separate lists for long and short trading opportunities

## System Architecture

The system is organized into the following components:

### Core Modules

1. **config.py**: Central configuration management
2. **data_handler.py**: Market data fetching and processing
3. **indicators.py**: Technical indicators calculation
4. **order_manager.py**: Order placement and tracking
5. **risk_management.py**: Risk management logic (legacy)
6. **trading_logic.py**: Trading signal generation
7. **position_watchdog.py** (NEW): Real-time position monitoring

### Entry Point Scripts

1. **scan_market.py**: Scans market for standard trading opportunities
2. **scan_markets_gap.py** (NEW): Scans market for gap-based trading opportunities
3. **place_orders.py**: Places entry orders based on scanner results (modified to remove GTT logic)
4. **start_position_watchdog.sh**: Starts the real-time position monitoring service
5. **install_gap_strategy_service.py** (NEW): Manages the gap strategy service

## Technical Implementation Details

### Position Watchdog System

The cornerstone of Version 2.0 is the new position_watchdog.py utility, which:

1. **Connects to Zerodha via WebSocket**:
   - Establishes persistent connection to KiteTicker WebSocket API
   - Subscribes to real-time price feeds for all positions
   - Handles reconnection if connection drops

2. **Monitors Positions in Real-time**:
   - Detects new positions by polling portfolio API
   - Calculates stop-loss levels based on previous candles
   - Updates trailing stops as positions move favorably
   - Implements take-profit logic based on configured targets

3. **Executes Orders Immediately**:
   - Places market orders when stop-loss thresholds crossed
   - Queues orders for reliable execution with retries
   - Handles rate limiting with exponential backoff

4. **Maintains Comprehensive Logs**:
   - Detailed position monitoring events
   - Order execution audit trail
   - Error handling and recovery actions

### System Integration

1. **Seamless Integration with Existing Components**:
   - Works with existing market scanner unchanged
   - Modified order placement to remove GTT code
   - Maintains backward compatibility for state files

2. **MIS-only Focus**:
   - Position watchdog only manages MIS (intraday) positions
   - CNC (delivery) positions still handled by Daily scripts
   - Explicitly filters by product_type to prevent conflicts

3. **Deployment Options**:
   - Can run as standalone process
   - Integrates with macOS launchd for service management
   - Custom start/stop scripts for easy operation

## Improvements Over Version 1.0

1. **Eliminated GTT Synchronization Issues**:
   - No more reliance on Zerodha's GTT feature 
   - Stop-loss and take-profit handled locally
   - Removed race conditions between client and server state

2. **Enhanced Responsiveness**:
   - Real-time price monitoring vs periodic polling
   - Immediate order execution upon threshold crossing
   - Sub-second reaction to price movements

3. **Improved Resilience**:
   - Comprehensive retry logic for API failures
   - Automatic reconnection for WebSocket disruptions
   - Exponential backoff for rate limit handling

4. **Better Error Recovery**:
   - Robust handling of duplicate order attempts
   - Graceful recovery from connection issues
   - Service auto-restart capability

## Bug Fixes From Version 1.0

1. **Position Tracking Consistency**:
   - Fixed issue with positions appearing in both long and short lists
   - Eliminated synchronization issues between client and GTT state
   - Improved position cleanup when trades are closed

2. **Duplicate Order Prevention**:
   - Fixed root cause of duplicate orders with stateless design
   - Improved order queue to handle duplicate detection
   - Better error handling for "already executed" responses

3. **API Error Handling**:
   - Enhanced retry mechanism for transient API failures
   - Better handling of rate limit errors with pauseS
   - Improved logging for troubleshooting

## Recent Bug Fixes (May 2025)

1. **Daily Ticker Synchronization Issue**:
   - **Bug**: RAILTEL BUY orders were placed automatically at 15:04 even though the ticker was not in the source file
   - **Root Cause**: The position_watchdog was monitoring daily_tickers in trading_state.json and adding positions if they appeared in broker data and matched a ticker in daily_tickers lists (long/short) even if they should not be tracked anymore
   - **Fix**: 
     - Added `remove_daily_ticker()` method to StateManager
     - Enhanced position_watchdog to clean up daily ticker lists by removing tickers that don't have corresponding broker positions
     - This prevents unwanted position tracking for tickers that should no longer be monitored

## Deployment and Operation

### Position Watchdog Setup

**Manual Start/Stop:**
```bash
# Start the watchdog
./utils/start_position_watchdog.sh

# Stop the watchdog
./utils/stop_position_watchdog.sh
```

**System Service Setup (macOS):**
```bash
# Copy the plist file and load service
cp plist/com.indiaTS.position_watchdog.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist
```

### Recommended Workflow

1. Run market scanner to identify opportunities:
   ```
   python scripts/scan_market.py
   ```

2. For gap-based trading opportunities (optional):
   ```
   python scripts/scan_markets_gap.py
   ```
   Or install the automated service:
   ```
   python utils/install_gap_strategy_service.py install
   python utils/install_gap_strategy_service.py start
   ```

3. Place entry orders (no GTT orders):
   ```
   python scripts/place_orders.py
   ```

4. Start position watchdog to manage risk:
   ```
   ./utils/start_position_watchdog.sh
   ```

## Future Enhancements

1. **Additional WebSocket Features**:
   - Order updates via WebSocket for faster execution feedback
   - Portfolio value streaming for real-time P&L
   - Market depth integration for improved execution

2. **Enhanced Analytics**:
   - Real-time performance monitoring
   - Position lifecycle analysis
   - Trade journaling capabilities

3. **Risk Improvements**:
   - Dynamic stop-loss calculation based on volatility
   - Portfolio-level risk management
   - Correlated position detection

4. **User Experience**:
   - Console-based dashboard for monitoring
   - Alert notifications for significant events
   - Status visualization for active positions