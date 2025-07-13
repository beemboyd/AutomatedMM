# Stop Loss (SL) Watchdog Flow

## Overview
The SL Watchdog (position_watchdog.py) monitors all open positions and manages stop losses dynamically. It runs continuously during market hours to protect positions and implement trailing stop strategies.

## Main SL Watchdog Flow

```mermaid
flowchart TD
    Start([SL Watchdog Start]) --> InitWatchdog[Initialize Watchdog]
    InitWatchdog --> LoadConfig[Load Configuration]
    LoadConfig --> ConnectKite[Connect to Kite API]
    
    ConnectKite --> MainLoop{Market Open?}
    MainLoop -->|No| Sleep1[Sleep 60 seconds]
    Sleep1 --> MainLoop
    MainLoop -->|Yes| LoadPositions[Load All Positions]
    
    LoadPositions --> SyncBroker[Sync with Broker Positions]
    SyncBroker --> ProcessEach[Process Each Position]
    
    ProcessEach --> CheckType{Position Type}
    CheckType -->|MIS| ProcessMIS[Process MIS Position]
    CheckType -->|CNC| ProcessCNC[Process CNC Position]
    
    ProcessMIS --> CheckPrice[Get Current Price]
    ProcessCNC --> CheckPrice
    
    CheckPrice --> CalculatePnL[Calculate P&L]
    CalculatePnL --> CheckStopLoss{Stop Loss Hit?}
    
    CheckStopLoss -->|Yes| TriggerExit[Trigger Exit Order]
    CheckStopLoss -->|No| CheckTrailing{Trailing SL Enabled?}
    
    TriggerExit --> PlaceExitOrder[Place Exit Order]
    PlaceExitOrder --> UpdateState1[Update Position State]
    UpdateState1 --> LogExit[Log Exit Details]
    
    CheckTrailing -->|No| NextPosition{More Positions?}
    CheckTrailing -->|Yes| CheckProfit{Profit > Threshold?}
    
    CheckProfit -->|No| NextPosition
    CheckProfit -->|Yes| UpdateTrailingSL[Update Trailing SL]
    
    UpdateTrailingSL --> UpdateState2[Update SL in State]
    UpdateState2 --> NextPosition
    
    NextPosition -->|Yes| ProcessEach
    NextPosition -->|No| Sleep2[Sleep 10 seconds]
    Sleep2 --> MainLoop
    
    LogExit --> NextPosition
```

## Stop Loss Calculation Logic

```mermaid
flowchart TD
    StartSL([Calculate Stop Loss]) --> GetStrategy[Get Position Strategy]
    GetStrategy --> StrategyType{Strategy Type}
    
    StrategyType -->|Al Brooks| BrooksSL[Brooks SL Logic]
    StrategyType -->|Pattern| PatternSL[Pattern SL Logic]
    StrategyType -->|Default| DefaultSL[Default SL Logic]
    
    BrooksSL --> BSL1[Initial: Entry - 2*ATR]
    BSL1 --> BSL2[Trailing: Move to Breakeven]
    BSL2 --> BSL3[Advanced: Trail by ATR]
    
    PatternSL --> PSL1[Initial: Pattern Low]
    PSL1 --> PSL2[Trailing: 50% of Move]
    
    DefaultSL --> DSL1[Initial: 2% Below Entry]
    DSL1 --> DSL2[Trailing: 1% Below High]
    
    BSL3 --> FinalSL[Final Stop Loss]
    PSL2 --> FinalSL
    DSL2 --> FinalSL
    
    FinalSL --> ValidateSL{Valid SL?}
    ValidateSL -->|No| UseDefault[Use Default 2%]
    ValidateSL -->|Yes| ReturnSL([Return Stop Loss])
    UseDefault --> ReturnSL
```

## Position Monitoring Sequence

```mermaid
sequenceDiagram
    participant Watchdog
    participant StateManager
    participant KiteAPI
    participant RiskManager
    participant OrderSystem
    
    loop Every 10 seconds
        Watchdog->>StateManager: Get open positions
        StateManager-->>Watchdog: Return positions
        Watchdog->>KiteAPI: Get market prices
        KiteAPI-->>Watchdog: Return LTP
        
        Watchdog->>Watchdog: Calculate P&L
        Watchdog->>RiskManager: Check risk limits
        
        alt Stop Loss Hit
            Watchdog->>OrderSystem: Place exit order
            OrderSystem->>KiteAPI: Execute sell order
            KiteAPI-->>OrderSystem: Order confirmation
            OrderSystem->>StateManager: Update position status
            Watchdog->>Watchdog: Log exit reason
        else Trailing SL Update
            Watchdog->>Watchdog: Calculate new SL
            Watchdog->>StateManager: Update SL level
        end
    end
```

## Multi-User Position Management

```mermaid
flowchart TD
    Start([Multi-User Watchdog]) --> LoadUsers[Load Active Users]
    LoadUsers --> UserLoop[For Each User]
    
    UserLoop --> SetContext[Set User Context]
    SetContext --> LoadUserPos[Load User Positions]
    LoadUserPos --> CheckEmpty{Has Positions?}
    
    CheckEmpty -->|No| NextUser{More Users?}
    CheckEmpty -->|Yes| MonitorPos[Monitor Positions]
    
    MonitorPos --> ProcessUserPos[Process Each Position]
    ProcessUserPos --> ApplyUserRules[Apply User-Specific Rules]
    ApplyUserRules --> UpdateUserState[Update User State]
    
    UpdateUserState --> NextUser
    NextUser -->|Yes| UserLoop
    NextUser -->|No| SleepCycle[Sleep 10 seconds]
    SleepCycle --> Start
```

## Stop Loss Types and Triggers

```mermaid
graph TD
    SLTypes[Stop Loss Types] --> Fixed[Fixed Stop Loss]
    SLTypes --> Trailing[Trailing Stop Loss]
    SLTypes --> Dynamic[Dynamic Stop Loss]
    
    Fixed --> F1[Set at Entry]
    Fixed --> F2[Never Changes]
    Fixed --> F3[Simple Protection]
    
    Trailing --> T1[Moves with Profit]
    Trailing --> T2[Never Moves Down]
    Trailing --> T3[Locks in Gains]
    
    Dynamic --> D1[Based on Volatility]
    Dynamic --> D2[ATR-Based]
    Dynamic --> D3[Market Conditions]
    
    Triggers[SL Triggers] --> PriceTrigger[Price-Based]
    Triggers --> TimeTrigger[Time-Based]
    Triggers --> VolumeTrigger[Volume-Based]
    
    PriceTrigger --> PT1[LTP <= Stop Loss]
    TimeTrigger --> TT1[End of Day]
    VolumeTrigger --> VT1[Unusual Volume]
```

## Error Recovery Flow

```mermaid
flowchart TD
    Error([Watchdog Error]) --> ErrorType{Error Type}
    
    ErrorType -->|Connection Lost| Reconnect[Attempt Reconnection]
    ErrorType -->|API Error| APIRetry[Retry API Call]
    ErrorType -->|State Error| RepairState[Repair State File]
    ErrorType -->|Order Failed| ManualAlert[Alert for Manual Action]
    
    Reconnect --> ConnectSuccess{Connected?}
    ConnectSuccess -->|Yes| Resume[Resume Monitoring]
    ConnectSuccess -->|No| WaitConnect[Wait & Retry]
    
    APIRetry --> RetryCount{Retry < 3?}
    RetryCount -->|Yes| RetryCall[Retry API Call]
    RetryCount -->|No| SkipPosition[Skip This Cycle]
    
    RepairState --> LoadBackup[Load Backup State]
    LoadBackup --> ValidateState[Validate State]
    ValidateState --> Resume
    
    ManualAlert --> LogError[Log Critical Error]
    LogError --> NotifyUser[Send Notification]
    NotifyUser --> ContinueOthers[Continue Other Positions]
    
    WaitConnect --> Reconnect
    SkipPosition --> NextPosition[Next Position]
    ContinueOthers --> NextPosition
```

## Trailing Stop Loss Logic

```mermaid
flowchart TD
    CurrentPrice([Current Price]) --> CheckProfit{In Profit?}
    CheckProfit -->|No| KeepSL[Keep Current SL]
    CheckProfit -->|Yes| CalcProfit[Calculate Profit %]
    
    CalcProfit --> ProfitLevel{Profit Level}
    ProfitLevel -->|< 1%| NoTrail[No Trailing]
    ProfitLevel -->|1-2%| TrailBreakeven[Move to Breakeven]
    ProfitLevel -->|2-5%| Trail50[Trail 50% of Move]
    ProfitLevel -->|> 5%| TrailTight[Tight Trailing]
    
    TrailBreakeven --> NewSL1[SL = Entry Price]
    Trail50 --> NewSL2[SL = Entry + 50% Profit]
    TrailTight --> NewSL3[SL = Price - 1%]
    
    NewSL1 --> CompareOld{New > Old SL?}
    NewSL2 --> CompareOld
    NewSL3 --> CompareOld
    
    CompareOld -->|Yes| UpdateSL[Update Stop Loss]
    CompareOld -->|No| KeepSL
    
    UpdateSL --> SaveNewSL[Save to State]
    KeepSL --> Continue[Continue Monitoring]
    SaveNewSL --> Continue
```

## Position Exit Flow

```mermaid
flowchart TD
    TriggerExit([Exit Triggered]) --> ExitReason{Exit Reason}
    
    ExitReason -->|Stop Loss| SLExit[Stop Loss Exit]
    ExitReason -->|Target Hit| TargetExit[Target Exit]
    ExitReason -->|Time Based| TimeExit[Time Exit]
    ExitReason -->|Manual| ManualExit[Manual Exit]
    
    SLExit --> PrepareOrder[Prepare Exit Order]
    TargetExit --> PrepareOrder
    TimeExit --> PrepareOrder
    ManualExit --> PrepareOrder
    
    PrepareOrder --> OrderParams[Set Order Parameters]
    OrderParams --> OP1[Order Type: MARKET]
    OrderParams --> OP2[Transaction: SELL]
    OrderParams --> OP3[Quantity: Position Size]
    
    OP1 --> PlaceOrder[Place Exit Order]
    OP2 --> PlaceOrder
    OP3 --> PlaceOrder
    
    PlaceOrder --> OrderStatus{Order Success?}
    OrderStatus -->|Yes| UpdateRecords[Update Records]
    OrderStatus -->|No| RetryExit[Retry Exit]
    
    UpdateRecords --> UR1[Update State File]
    UpdateRecords --> UR2[Update Orders File]
    UpdateRecords --> UR3[Log Exit Details]
    UpdateRecords --> UR4[Calculate Final P&L]
    
    RetryExit --> MaxRetry{Max Retries?}
    MaxRetry -->|No| PlaceOrder
    MaxRetry -->|Yes| AlertCritical[Critical Alert]
    
    UR4 --> Complete([Exit Complete])
    AlertCritical --> ManualIntervention[Require Manual Action]
```