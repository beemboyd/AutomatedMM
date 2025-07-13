# Prune Portfolio Flow

## Overview
The Prune Portfolio system runs at 3:00 PM daily to clean up losing positions and manage end-of-day portfolio actions. It helps maintain portfolio health by removing underperforming positions before market close.

## Main Prune Portfolio Flow

```mermaid
flowchart TD
    Start([Prune Portfolio 3:00 PM]) --> CheckTime[Verify Market Hours]
    CheckTime --> TimeOK{Time Valid?}
    TimeOK -->|No| Exit[Exit - Wrong Time]
    TimeOK -->|Yes| LoadContext[Load User Context]
    
    LoadContext --> GetPositions[Get All Open Positions]
    GetPositions --> SeparateTypes[Separate Position Types]
    
    SeparateTypes --> MIS[MIS Positions]
    SeparateTypes --> CNC[CNC Positions]
    
    MIS --> ProcessMIS[Process MIS Positions]
    CNC --> ProcessCNC[Process CNC Positions]
    
    ProcessMIS --> CheckMISPnL{Check P&L}
    CheckMISPnL -->|Loss > Threshold| MarkMISExit[Mark for Exit]
    CheckMISPnL -->|Profitable| KeepMIS[Keep Position]
    
    ProcessCNC --> CheckCNCCriteria{Check Exit Criteria}
    CheckCNCCriteria -->|Met| MarkCNCExit[Mark for Exit]
    CheckCNCCriteria -->|Not Met| KeepCNC[Keep Position]
    
    MarkMISExit --> CollectExits[Collect Exit Orders]
    MarkCNCExit --> CollectExits
    KeepMIS --> NextPosition1{More Positions?}
    KeepCNC --> NextPosition2{More Positions?}
    
    NextPosition1 -->|Yes| ProcessMIS
    NextPosition1 -->|No| ExecuteExits[Execute Exit Orders]
    NextPosition2 -->|Yes| ProcessCNC
    NextPosition2 -->|No| ExecuteExits
    
    CollectExits --> ExecuteExits
    ExecuteExits --> GenerateReport[Generate Prune Report]
    GenerateReport --> UpdateState[Update Portfolio State]
    UpdateState --> End([Prune Complete])
```

## Exit Criteria Evaluation

```mermaid
flowchart TD
    Position([Evaluate Position]) --> GetMetrics[Get Position Metrics]
    GetMetrics --> M1[Current P&L]
    GetMetrics --> M2[Holding Duration]
    GetMetrics --> M3[Volume/Liquidity]
    GetMetrics --> M4[Technical Indicators]
    
    M1 --> CheckCriteria{Exit Criteria}
    M2 --> CheckCriteria
    M3 --> CheckCriteria
    M4 --> CheckCriteria
    
    CheckCriteria --> C1{Loss > 2%?}
    C1 -->|Yes| Exit1[Exit: Stop Loss]
    
    CheckCriteria --> C2{Time > 3:00 PM?}
    C2 -->|Yes| C2a{MIS Position?}
    C2a -->|Yes| Exit2[Exit: EOD Square Off]
    
    CheckCriteria --> C3{Low Volume?}
    C3 -->|Yes| Exit3[Exit: Liquidity Risk]
    
    CheckCriteria --> C4{Technical Breakdown?}
    C4 -->|Yes| Exit4[Exit: Technical]
    
    CheckCriteria --> C5{Profit > Target?}
    C5 -->|Yes| Exit5[Exit: Target Hit]
    
    Exit1 --> FinalDecision[Exit Position]
    Exit2 --> FinalDecision
    Exit3 --> FinalDecision
    Exit4 --> FinalDecision
    Exit5 --> FinalDecision
    
    C1 -->|No| CheckNext[Check Next Criteria]
    C2a -->|No| CheckNext
    C3 -->|No| CheckNext
    C4 -->|No| CheckNext
    C5 -->|No| KeepPosition[Keep Position]
```

## MIS Position Pruning Logic

```mermaid
flowchart TD
    MISStart([MIS Position]) --> GetTime[Get Current Time]
    GetTime --> TimeCheck{Time Check}
    
    TimeCheck -->|Before 3:00| NormalPrune[Normal Pruning]
    TimeCheck -->|3:00-3:15| AggressivePrune[Aggressive Pruning]
    TimeCheck -->|After 3:15| ForcedExit[Forced Exit All]
    
    NormalPrune --> NP1{Loss > 2%?}
    NP1 -->|Yes| ExitNow1[Exit Position]
    NP1 -->|No| NP2{Stagnant > 2hrs?}
    NP2 -->|Yes| ExitNow2[Exit Position]
    NP2 -->|No| KeepNormal[Keep Position]
    
    AggressivePrune --> AP1{Any Loss?}
    AP1 -->|Yes| ExitAggressive[Exit Position]
    AP1 -->|No| AP2{Profit < 0.5%?}
    AP2 -->|Yes| ExitSmallProfit[Exit Position]
    AP2 -->|No| KeepAggressive[Keep for Now]
    
    ForcedExit --> ExitAll[Exit All MIS]
    
    ExitNow1 --> ExecuteExit[Execute Market Order]
    ExitNow2 --> ExecuteExit
    ExitAggressive --> ExecuteExit
    ExitSmallProfit --> ExecuteExit
    ExitAll --> ExecuteExit
```

## CNC Position Pruning Logic

```mermaid
flowchart TD
    CNCStart([CNC Position]) --> GetHolding[Get Holding Period]
    GetHolding --> CheckPeriod{Holding Period}
    
    CheckPeriod -->|< 1 Day| SkipCNC[Skip - Too New]
    CheckPeriod -->|>= 1 Day| EvaluateCNC[Evaluate Position]
    
    EvaluateCNC --> E1{Loss > 5%?}
    E1 -->|Yes| CheckTrend{Trend Analysis}
    E1 -->|No| E2{Profit > 10%?}
    
    CheckTrend -->|Downtrend| ExitCNC1[Exit Position]
    CheckTrend -->|Uptrend| HoldCNC1[Hold - May Recover]
    
    E2 -->|Yes| PartialExit[Consider Partial Exit]
    E2 -->|No| E3{Sideways > 5 Days?}
    
    E3 -->|Yes| ExitCNC2[Exit - No Movement]
    E3 -->|No| E4{Volume Declining?}
    
    E4 -->|Yes| ExitCNC3[Exit - Low Interest]
    E4 -->|No| HoldCNC2[Hold Position]
    
    PartialExit --> PE{Exit 50%?}
    PE -->|Yes| PartialExitOrder[Place 50% Exit]
    PE -->|No| HoldCNC3[Hold Full Position]
    
    ExitCNC1 --> PlaceCNCExit[Place Exit Order]
    ExitCNC2 --> PlaceCNCExit
    ExitCNC3 --> PlaceCNCExit
    PartialExitOrder --> UpdatePosition[Update Position Size]
```

## Batch Order Execution

```mermaid
flowchart TD
    StartBatch([Execute Exits]) --> GroupOrders[Group by Symbol]
    GroupOrders --> PrioritizeOrders[Prioritize Orders]
    
    PrioritizeOrders --> P1[1. Large Losses First]
    PrioritizeOrders --> P2[2. MIS Before CNC]
    PrioritizeOrders --> P3[3. Illiquid Stocks]
    PrioritizeOrders --> P4[4. Others]
    
    P1 --> CreateBatch[Create Order Batch]
    P2 --> CreateBatch
    P3 --> CreateBatch
    P4 --> CreateBatch
    
    CreateBatch --> ExecuteBatch[Execute Batch]
    ExecuteBatch --> OrderLoop[For Each Order]
    
    OrderLoop --> PlaceOrder[Place Market Order]
    PlaceOrder --> CheckResponse{Order Success?}
    
    CheckResponse -->|Yes| LogSuccess[Log Success]
    CheckResponse -->|No| RetryLogic{Retry?}
    
    RetryLogic -->|Yes| PlaceOrder
    RetryLogic -->|No| LogFailure[Log Failure]
    
    LogSuccess --> NextOrder{More Orders?}
    LogFailure --> NextOrder
    
    NextOrder -->|Yes| OrderLoop
    NextOrder -->|No| SummaryReport[Create Summary]
```

## Prune Report Generation

```mermaid
flowchart TD
    StartReport([Generate Report]) --> CollectData[Collect Prune Data]
    
    CollectData --> CD1[Positions Evaluated]
    CollectData --> CD2[Positions Exited]
    CollectData --> CD3[Total P&L Impact]
    CollectData --> CD4[Reasons for Exit]
    
    CD1 --> AnalyzeResults[Analyze Results]
    CD2 --> AnalyzeResults
    CD3 --> AnalyzeResults
    CD4 --> AnalyzeResults
    
    AnalyzeResults --> AR1[Exit Success Rate]
    AnalyzeResults --> AR2[Capital Freed Up]
    AnalyzeResults --> AR3[Loss Prevention]
    AnalyzeResults --> AR4[Pattern Analysis]
    
    AR4 --> CreateSections[Create Report Sections]
    CreateSections --> S1[Summary Section]
    CreateSections --> S2[Detailed Exits]
    CreateSections --> S3[Retained Positions]
    CreateSections --> S4[Recommendations]
    
    S1 --> FormatReport[Format Report]
    S2 --> FormatReport
    S3 --> FormatReport
    S4 --> FormatReport
    
    FormatReport --> SaveReport[Save to File]
    SaveReport --> EmailReport[Email Summary]
    EmailReport --> UpdateDashboard[Update Dashboard]
```

## Integration with Risk Management

```mermaid
sequenceDiagram
    participant PruneSystem
    participant RiskManager
    participant PositionManager
    participant KiteAPI
    participant StateManager
    participant Reporter
    
    PruneSystem->>RiskManager: Get risk thresholds
    RiskManager-->>PruneSystem: Return limits
    
    PruneSystem->>PositionManager: Get all positions
    PositionManager-->>PruneSystem: Return position list
    
    loop For each position
        PruneSystem->>RiskManager: Evaluate position risk
        RiskManager-->>PruneSystem: Risk assessment
        
        alt Exit required
            PruneSystem->>KiteAPI: Place exit order
            KiteAPI-->>PruneSystem: Order confirmation
            PruneSystem->>StateManager: Update state
        end
    end
    
    PruneSystem->>Reporter: Generate report
    Reporter-->>PruneSystem: Report created
    
    PruneSystem->>StateManager: Final state update
```

## Time-Based Pruning Strategy

```mermaid
graph TD
    TimeStrategy[Time-Based Strategy] --> EarlyDay[9:30 AM - 12:00 PM]
    TimeStrategy --> MidDay[12:00 PM - 2:30 PM]
    TimeStrategy --> LateDay[2:30 PM - 3:30 PM]
    
    EarlyDay --> ED1[Monitor Only]
    EarlyDay --> ED2[Exit if Loss > 3%]
    EarlyDay --> ED3[Allow Winners to Run]
    
    MidDay --> MD1[Tighten Criteria]
    MidDay --> MD2[Exit if Loss > 2%]
    MidDay --> MD3[Take Partial Profits]
    
    LateDay --> LD1[Aggressive Pruning]
    LateDay --> LD2[Exit if Loss > 1%]
    LateDay --> LD3[Close All MIS]
    LateDay --> LD4[Review CNC Positions]
```