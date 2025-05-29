# India Trading System (Version 2.0)

A comprehensive, modular trading system for the Indian stock market using Zerodha's API.

## Overview of Version 2.0

Version 2.0 represents a significant architectural improvement over the previous system, with a focus on reliability and real-time position management:

1. **Real-time Position Watchdog**: Continuous position monitoring via WebSocket connection
2. **Local Risk Management**: Eliminates dependency on Zerodha GTT for stop-loss management 
3. **Resilient Architecture**: Pub-sub model with real-time price event handling
4. **Zero State Dependencies**: GTT synchronization issues eliminated
5. **Improved Reliability**: Comprehensive error handling and retry mechanisms

## System Architecture

The system is organized into a modular Python package with the following structure:

```
India-TS/
├── config.ini                # Configuration file
├── config.py                 # Configuration management
├── data_handler.py           # Market data processing
├── indicators.py             # Technical indicators
├── order_manager.py          # Order placement/management
├── risk_management.py        # Stop-loss and position sizing
├── trading_logic.py          # Trading signals and strategy
├── data/                     # Data files and outputs
├── logs/                     # Log files
├── scripts/                  # Executable scripts
│   ├── scan_market.py        # Market scanner script
│   ├── place_orders.py       # Order placement script
│   └── manage_risk.py        # Legacy risk management script
├── utils/                    # Utility functions
│   ├── position_watchdog.py  # NEW: Real-time position monitor
│   ├── start_position_watchdog.sh  # NEW: Start watchdog service
│   ├── stop_position_watchdog.sh   # NEW: Stop watchdog service
│   ├── cleanup_gtt.py        # Clean up GTT orders (legacy)
│   ├── cleanup_positions.py  # Clean up position data
│   └── fix_cnc_mis_conflict.py  # Fix CNC-MIS conflicts
├── Daily/                    # CNC (delivery) order scripts
│   ├── Daily-Exit.py         # Exit delivery positions
│   └── Daily_SL.py           # Set stop-loss for delivery
└── kill/                     # Emergency scripts
    ├── killgtt.py            # Delete all GTT orders
    └── cleanup_problematic_gtts.py  # Fix problem GTTs
```

## Logical Flow and Operation Sequence (Version 2.0)

The system now operates with a new flow:

1. **Market Scanning Phase**:
   - Scans the market for trading opportunities
   - Analyzes tickers based on price action and technical indicators
   - Outputs signal files for both long and short sides
   - Run with: `python scripts/scan_market.py`

2. **Order Placement Phase**:
   - Reads signal files from the scan phase
   - Analyzes market breadth via advances/declines ratio
   - Selects top opportunities based on ranking
   - Places buy/sell orders for new positions
   - **No longer sets GTT orders** - this is handled by position_watchdog
   - Run with: `python scripts/place_orders.py`

3. **Real-time Position Monitoring** (New):
   - Continuously monitors all positions via WebSocket
   - Calculates and updates stop-losses based on price action
   - Triggers market orders when prices cross thresholds
   - Handles trailing stops and take-profit targets
   - Run with: `./utils/start_position_watchdog.sh`

## MIS vs CNC Trading

The system handles two types of trading products:

1. **MIS (Intraday)**:
   - Managed by scripts in the `scripts/` directory
   - Uses trading_state.json to track intraday positions
   - Requires product_type=MIS in config.ini
   - Position watchdog handles risk management in real-time
   - All positions automatically square off at end of day

2. **CNC (Delivery)**:
   - Managed by scripts in the `Daily/` directory
   - Separate from MIS tracking system
   - For longer-term holdings
   - Has its own stop-loss management

Important: The position_watchdog.py utility only operates on MIS positions. For CNC positions, continue using the scripts in the Daily folder.

## New Position Watchdog System

The position_watchdog.py utility is the cornerstone of the Version 2.0 architecture:

### Features:
- Real-time price monitoring via WebSocket connection
- Pub-sub model for immediate reaction to price movements
- Stateless design eliminates synchronization issues
- Automatic retry with exponential backoff for API failures
- Automatic reconnection if WebSocket disconnects
- Comprehensive logging for troubleshooting

### Running the Position Watchdog:

**Manual Start/Stop:**
```bash
# Start the watchdog
./utils/start_position_watchdog.sh

# Stop the watchdog
./utils/stop_position_watchdog.sh
```

**System Service Setup (macOS):**
```bash
# Copy the plist file to the LaunchAgents directory
cp plist/com.indiaTS.position_watchdog.plist ~/Library/LaunchAgents/

# Load the service
launchctl load ~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist

# Start the service
launchctl start com.indiaTS.position_watchdog
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd India-TS
   ```

2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Update `config.ini` with your API credentials

## Usage

### Market Scanning

Scan the market for trading opportunities:

```
python scripts/scan_market.py [-i INPUT_FILE] [-v]
```

Options:
- `-i, --input`: Path to Excel file with ticker list
- `-v, --verbose`: Enable verbose logging

### Order Placement

Place orders based on the scan results:

```
python scripts/place_orders.py [-l LONG_FILE] [-s SHORT_FILE] [-m MAX_POSITIONS] [--disable-long] [--disable-short] [-v]
```

Options:
- `-l, --long-file`: Path to long signal file
- `-s, --short-file`: Path to short signal file
- `-m, --max-positions`: Maximum positions to take
- `--disable-long`: Disable long orders
- `--disable-short`: Disable short orders
- `-v, --verbose`: Enable verbose logging

### Position Watchdog (Version 2.0)

Start the real-time position monitoring:

```
python utils/position_watchdog.py [--check-interval SECONDS] [--profit-target PERCENT] [-v]
```

Options:
- `--check-interval`: Interval in seconds to check for new positions (default: 60)
- `--profit-target`: Take profit percentage target (overrides config)
- `-v, --verbose`: Enable verbose logging

### CNC (Delivery) Trading

For delivery (CNC) positions:

```
python Daily/Daily_SL.py
```
Sets stop-loss orders for delivery positions based on Keltner Channels.

```
python Daily/Daily-Exit.py
```
Exits delivery positions based on custom criteria.

## Scheduling

For automated trading, set up the scripts to run at specific intervals:

1. **Market Scanning**: Run every 5 minutes during trading hours
2. **Order Placement**: Run 10 minutes after market scan
3. **Position Watchdog**: Run as a continuous service

Example launchd plist configuration (macOS):
```bash
# Copy plist files for auto-start
cp plist/com.indiaTS.scan_market.plist ~/Library/LaunchAgents/
cp plist/com.indiaTS.place_orders.plist ~/Library/LaunchAgents/
cp plist/com.indiaTS.position_watchdog.plist ~/Library/LaunchAgents/

# Load services
launchctl load ~/Library/LaunchAgents/com.indiaTS.scan_market.plist
launchctl load ~/Library/LaunchAgents/com.indiaTS.place_orders.plist
launchctl load ~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist
```

## Troubleshooting Common Issues

### Legacy GTT Issues (Version 1.0)
If you're still seeing issues related to GTT orders from Version 1.0:
1. Run `python utils/cleanup_gtt.py` to clean up existing GTT orders
2. Switch to using the position_watchdog.py utility for all risk management

### CNC vs MIS Conflicts
If you have both delivery (CNC) and intraday (MIS) positions for the same stock:
1. Run `python utils/fix_cnc_mis_conflict.py` to identify and resolve conflicts
2. If certain stocks continue causing issues, add them to the problematic_tickers list

## Version History

### Version 2.0 (2025-04-30)
- Implemented real-time position watchdog with WebSocket connection
- Removed GTT dependency from place_orders.py
- Added pub-sub model for price monitoring
- Implemented retry mechanism with exponential backoff
- Enhanced error handling and recovery
- Added automatic reconnection for WebSocket

### Version 1.0 (2025-04-25)
- Consolidated state management with trading_state.json
- Reduced chance of duplicate orders by eliminating state synchronization issues
- Added backward compatibility to avoid breaking existing scripts
- Fixed issues with order tracking when using both long and short positions

## Requirements

- Python 3.6+
- Zerodha account with API access
- Required Python packages:
  - kiteconnect
  - pandas
  - numpy
  - requests
  - openpyxl