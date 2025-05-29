# System State Management Flow

## State Interactions Between Components

```mermaid
flowchart TD
    subgraph "State Storage"
        TradingState[trading_state.json]
    end
    
    subgraph "State Manager"
        StateManager[state_manager.py]
        StateManager -- Reads/Writes --> TradingState
    end
    
    subgraph "Process Scripts"
        ScanMarket[scan_market.py]
        PlaceOrders[place_orders.py]
        PosWatchdog[position_watchdog.py]
        ManageRisk[manage_risk.py]
    end
    
    subgraph "Order Management"
        OrderManager[order_manager.py]
        KiteAPI[Zerodha Kite API]
    end
    
    %% State management interactions
    ScanMarket -. "Reads state\n(optional)" .-> StateManager
    ScanMarket --> |Generates| SignalFiles[Signal Files]
    
    SignalFiles --> |Read By| PlaceOrders
    PlaceOrders <--> |Get/Set Positions| StateManager
    PlaceOrders --> |Place Orders| OrderManager
    
    PosWatchdog <--> |Get/Update Positions| StateManager
    PosWatchdog <--> |Get/Close Positions| OrderManager
    PosWatchdog <--> |Risk Management| RiskManager
    
    OrderManager <--> |Verify/Update Positions| StateManager
    OrderManager <--> |Execute Orders| KiteAPI
    
    classDef process fill:#f9f,stroke:#333,stroke-width:1px;
    classDef state fill:#bfb,stroke:#333,stroke-width:1px;
    classDef api fill:#bbf,stroke:#333,stroke-width:1px;
    classDef file fill:#fbb,stroke:#333,stroke-width:1px;
    
    class ScanMarket,PlaceOrders,PosWatchdog process;
    class StateManager,TradingState state;
    class OrderManager,KiteAPI api;
    class SignalFiles file;
```

## State Data Structure

```mermaid
erDiagram
    META {
        string date
        string last_updated
    }
    POSITIONS {
        string ticker_symbol
        string type
        float entry_price
        float best_price
        int quantity
        string product_type
        string timestamp
        string entry_time
        string confirmation
        object gtt
        float exit_price
        string exit_time
        string exit_reason
        string exit_confirmation
        float pnl
    }
    DAILY_TICKERS {
        array long
        array short
    }
    
    META ||--|| TRADING_STATE : contains
    POSITIONS ||--o{ TRADING_STATE : contains
    DAILY_TICKERS ||--|| TRADING_STATE : contains
    
    GTT {
        int trigger_id
        float trigger_price
        string timestamp
    }
    
    POSITIONS ||--o| GTT : may_have
```

## Key State Management Functions

1. **State Initialization**:
   - State manager loads state from trading_state.json on startup
   - Performs new trading day reset checks based on date
   - Resets MIS positions after service restarts (>10 min inactive)

2. **Position Management**:
   - add_position(): Adds or updates a position with full details
   - remove_position(): Removes position or records exit details
   - update_position_quantity(): Updates quantity of existing position
   - update_best_price(): Updates best price for trailing stops
   - get_position(), get_all_positions(), get_positions_by_type()

3. **GTT Management**:
   - add_gtt(): Adds GTT information to a position
   - remove_gtt(): Removes GTT data
   - get_gtt(), get_all_gtts()

4. **Daily Ticker Management**:
   - add_daily_ticker(): Marks ticker as traded today
   - is_ticker_traded_today(): Checks if ticker was traded today
   - get_daily_tickers()

5. **Day Reset Logic**:
   - reset_for_new_trading_day(): Clears MIS positions, preserves CNC
   - Updates meta information with new date
   - Can be forced even on same day

## State Synchronization

1. **place_orders.py**:
   - Reads signal files to determine new positions
   - Adds new positions to state via state_manager
   - Uses state to avoid duplicate trades

2. **position_watchdog.py**:
   - Continuously monitors positions in state
   - Updates stop loss levels and best prices
   - Removes positions when stop loss is triggered

3. **Broker Synchronization**:
   - Periodically verifies positions with broker
   - Ensures state matches actual broker positions
   - Removes "ghost" positions not at broker

## Important Notes

- All components interact through the state_manager
- State is persisted in trading_state.json
- New trading day triggers state reset for MIS positions
- CNC positions are preserved across days
- State changes are logged with timestamps