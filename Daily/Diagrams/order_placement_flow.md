# Order Placement Flow

## Overview
The order placement system processes scanner results and executes trades based on configured strategies and risk parameters. It handles both MIS (intraday) and CNC (delivery) orders.

## Main Order Placement Flow

```mermaid
flowchart TD
    Start([Order Placement Triggered]) --> LoadContext[Load User Context]
    LoadContext --> CheckMarketHours{Market Hours?}
    CheckMarketHours -->|No| Exit1[Exit - Market Closed]
    CheckMarketHours -->|Yes| LoadScanResults[Load Scanner Results]
    
    LoadScanResults --> LoadPositions[Load Current Positions]
    LoadPositions --> CheckDailyLimit{Daily Order Limit Reached?}
    CheckDailyLimit -->|Yes| Exit2[Exit - Daily Limit Hit]
    CheckDailyLimit -->|No| ProcessTickers[Process Each Ticker]
    
    ProcessTickers --> CheckCooldown{Ticker in Cooldown?}
    CheckCooldown -->|Yes| NextTicker1{More Tickers?}
    CheckCooldown -->|No| CheckExisting{Already Have Position?}
    
    CheckExisting -->|Yes| NextTicker1
    CheckExisting -->|No| CalculateSize[Calculate Position Size]
    
    CalculateSize --> RiskCheck{Risk Check Pass?}
    RiskCheck -->|No| NextTicker1
    RiskCheck -->|Yes| PrepareOrder[Prepare Order Details]
    
    PrepareOrder --> SetOrderType{Order Type}
    SetOrderType -->|MIS| PrepareMIS[Set MIS Parameters]
    SetOrderType -->|CNC| PrepareCNC[Set CNC Parameters]
    
    PrepareMIS --> PlaceOrder[Place Order via Kite API]
    PrepareCNC --> PlaceOrder
    
    PlaceOrder --> OrderResponse{Order Successful?}
    OrderResponse -->|No| LogError[Log Error]
    OrderResponse -->|Yes| UpdateState[Update Trading State]
    
    LogError --> NextTicker1
    UpdateState --> RecordOrder[Record in Orders File]
    RecordOrder --> UpdateCooldown[Update Ticker Cooldown]
    UpdateCooldown --> NextTicker1
    
    NextTicker1 -->|Yes| ProcessTickers
    NextTicker1 -->|No| GenerateReport[Generate Order Report]
    GenerateReport --> End([Order Placement Complete])
```

## Position Size Calculation

```mermaid
flowchart TD
    StartCalc([Calculate Position Size]) --> GetCapital[Get Available Capital]
    GetCapital --> GetRiskParams[Get Risk Parameters]
    
    GetRiskParams --> CalcRisk[Calculate Risk Amount]
    CalcRisk --> GetPrice[Get Current Price]
    GetPrice --> GetStopLoss[Calculate Stop Loss]
    
    GetStopLoss --> CalcShares[Calculate Shares = Risk / (Price - StopLoss)]
    CalcShares --> CheckMin{Shares >= Min Lot?}
    CheckMin -->|No| SetMinLot[Set to Minimum Lot]
    CheckMin -->|Yes| CheckMax{Shares <= Max Position?}
    
    SetMinLot --> FinalSize[Final Position Size]
    CheckMax -->|No| SetMaxSize[Set to Max Position]
    CheckMax -->|Yes| FinalSize
    
    FinalSize --> ReturnSize([Return Position Size])
```

## Order Validation Flow

```mermaid
flowchart TD
    StartVal([Order Validation]) --> CheckBalance[Check Account Balance]
    CheckBalance --> BalanceOK{Sufficient Balance?}
    BalanceOK -->|No| RejectBalance[Reject - Insufficient Funds]
    BalanceOK -->|Yes| CheckMargin[Check Margin Requirements]
    
    CheckMargin --> MarginOK{Margin Available?}
    MarginOK -->|No| RejectMargin[Reject - Insufficient Margin]
    MarginOK -->|Yes| CheckLimits[Check Position Limits]
    
    CheckLimits --> CheckDaily{Daily Limit OK?}
    CheckDaily -->|No| RejectDaily[Reject - Daily Limit]
    CheckDaily -->|Yes| CheckTicker{Ticker Limit OK?}
    
    CheckTicker -->|No| RejectTicker[Reject - Ticker Limit]
    CheckTicker -->|Yes| CheckRisk[Check Risk Parameters]
    
    CheckRisk --> RiskOK{Risk Within Limits?}
    RiskOK -->|No| RejectRisk[Reject - Risk Exceeded]
    RiskOK -->|Yes| Approved[Order Approved]
    
    RejectBalance --> Failed([Validation Failed])
    RejectMargin --> Failed
    RejectDaily --> Failed
    RejectTicker --> Failed
    RejectRisk --> Failed
    Approved --> Success([Validation Success])
```

## Order Execution Sequence

```mermaid
sequenceDiagram
    participant Scanner
    participant OrderSystem
    participant RiskManager
    participant KiteAPI
    participant StateManager
    participant FileSystem
    
    Scanner->>OrderSystem: New signals available
    OrderSystem->>StateManager: Get current positions
    StateManager-->>OrderSystem: Return positions
    OrderSystem->>RiskManager: Validate order
    RiskManager-->>OrderSystem: Approval/Rejection
    
    alt Order Approved
        OrderSystem->>KiteAPI: Place order
        KiteAPI-->>OrderSystem: Order ID
        OrderSystem->>StateManager: Update position
        OrderSystem->>FileSystem: Save to orders file
        OrderSystem->>OrderSystem: Set ticker cooldown
    else Order Rejected
        OrderSystem->>FileSystem: Log rejection reason
    end
```

## Order Types and Parameters

```mermaid
graph TD
    OrderType[Order Type Decision] --> MIS[MIS Orders]
    OrderType --> CNC[CNC Orders]
    
    MIS --> MISParams[MIS Parameters]
    MISParams --> MP1[Product: MIS]
    MISParams --> MP2[Validity: DAY]
    MISParams --> MP3[Square-off: 3:20 PM]
    MISParams --> MP4[Leverage: Available]
    
    CNC --> CNCParams[CNC Parameters]
    CNCParams --> CP1[Product: CNC]
    CNCParams --> CP2[Validity: DAY/GTT]
    CNCParams --> CP3[No Auto Square-off]
    CNCParams --> CP4[Full Margin Required]
    
    MP1 --> Execute[Execute Order]
    MP2 --> Execute
    MP3 --> Execute
    MP4 --> Execute
    CP1 --> Execute
    CP2 --> Execute
    CP3 --> Execute
    CP4 --> Execute
```

## Error Handling Flow

```mermaid
flowchart TD
    Error([Order Error]) --> ErrorType{Error Type}
    
    ErrorType -->|Network| NetworkRetry[Retry with Backoff]
    ErrorType -->|Authentication| ReAuth[Re-authenticate]
    ErrorType -->|Validation| LogValidation[Log & Skip]
    ErrorType -->|Server| ServerRetry[Retry Later]
    ErrorType -->|Unknown| LogUnknown[Log & Alert]
    
    NetworkRetry --> RetryCount{Retry < 3?}
    RetryCount -->|Yes| RetryOrder[Retry Order]
    RetryCount -->|No| MarkFailed[Mark as Failed]
    
    ReAuth --> NewLogin[Trigger Login Flow]
    NewLogin --> RetryAfterAuth[Retry Order]
    
    ServerRetry --> WaitTime[Wait 30 seconds]
    WaitTime --> RetryOrder
    
    LogValidation --> NextOrder[Process Next Order]
    LogUnknown --> AlertUser[Send Alert]
    MarkFailed --> NextOrder
    AlertUser --> NextOrder
```

## Cooldown Management

```mermaid
flowchart TD
    OrderPlaced([Order Placed]) --> RecordTime[Record Order Time]
    RecordTime --> SetCooldown[Set Cooldown Period]
    
    SetCooldown --> CooldownType{Order Result}
    CooldownType -->|Success| NormalCooldown[2 Hour Cooldown]
    CooldownType -->|Stop Hit| ExtendedCooldown[4 Hour Cooldown]
    CooldownType -->|Failed| ShortCooldown[30 Min Cooldown]
    
    NormalCooldown --> UpdateTracker[Update Cooldown Tracker]
    ExtendedCooldown --> UpdateTracker
    ShortCooldown --> UpdateTracker
    
    UpdateTracker --> SaveState[Save to State File]
    
    NewOrder([New Order Request]) --> CheckCooldown{In Cooldown?}
    CheckCooldown -->|Yes| TimeRemaining[Calculate Time Left]
    CheckCooldown -->|No| AllowOrder[Allow Order]
    
    TimeRemaining --> ShowMessage[Skip with Message]
    AllowOrder --> ProcessOrder[Process Order]
```