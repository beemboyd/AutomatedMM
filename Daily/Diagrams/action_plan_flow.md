# Action Plan Flow

## Overview
The Action Plan system analyzes market conditions, portfolio performance, and generates daily trading recommendations. It runs every morning at 8:30 AM to prepare traders for the day ahead.

## Main Action Plan Flow

```mermaid
flowchart TD
    Start([Action Plan Start 8:30 AM]) --> LoadConfig[Load Configuration]
    LoadConfig --> InitSystems[Initialize Systems]
    
    InitSystems --> GatherData[Gather Market Data]
    GatherData --> MD1[Previous Day Summary]
    GatherData --> MD2[Global Market Status]
    GatherData --> MD3[Pre-Market Indicators]
    GatherData --> MD4[Economic Calendar]
    
    MD1 --> AnalyzeMarket[Analyze Market Conditions]
    MD2 --> AnalyzeMarket
    MD3 --> AnalyzeMarket
    MD4 --> AnalyzeMarket
    
    AnalyzeMarket --> DetermineCharacter[Determine Market Character]
    DetermineCharacter --> MC{Market Character}
    
    MC -->|Trending| TrendingPlan[Trending Strategy]
    MC -->|Range Bound| RangePlan[Range Strategy]
    MC -->|Volatile| VolatilePlan[Volatility Strategy]
    
    TrendingPlan --> AnalyzePortfolio[Analyze Portfolio]
    RangePlan --> AnalyzePortfolio
    VolatilePlan --> AnalyzePortfolio
    
    AnalyzePortfolio --> LoadPositions[Load Current Positions]
    LoadPositions --> CalcMetrics[Calculate Performance Metrics]
    CalcMetrics --> IdentifyRisks[Identify Risk Areas]
    
    IdentifyRisks --> GenerateActions[Generate Action Items]
    GenerateActions --> PrioritizeActions[Prioritize by Impact]
    PrioritizeActions --> CreateReport[Create Action Plan Report]
    
    CreateReport --> SaveReports[Save Reports]
    SaveReports --> SendNotifications[Send Notifications]
    SendNotifications --> End([Action Plan Complete])
```

## Market Analysis Flow

```mermaid
flowchart TD
    StartAnalysis([Market Analysis]) --> GetIndices[Get Index Data]
    GetIndices --> I1[NIFTY 50]
    GetIndices --> I2[BANK NIFTY]
    GetIndices --> I3[NIFTY MIDCAP]
    GetIndices --> I4[NIFTY SMALLCAP]
    
    I1 --> CalcTrend[Calculate Trends]
    I2 --> CalcTrend
    I3 --> CalcTrend
    I4 --> CalcTrend
    
    CalcTrend --> AnalyzeBreadth[Analyze Market Breadth]
    AnalyzeBreadth --> AB1[Advance/Decline Ratio]
    AnalyzeBreadth --> AB2[New Highs/Lows]
    AnalyzeBreadth --> AB3[Volume Analysis]
    
    AB1 --> SectorAnalysis[Sector Analysis]
    AB2 --> SectorAnalysis
    AB3 --> SectorAnalysis
    
    SectorAnalysis --> TopSectors[Identify Top Sectors]
    TopSectors --> WeakSectors[Identify Weak Sectors]
    WeakSectors --> MarketSentiment[Calculate Market Sentiment]
    
    MarketSentiment --> MS{Sentiment Score}
    MS -->|Bullish > 60| BullishOutlook[Bullish Outlook]
    MS -->|Bearish < 40| BearishOutlook[Bearish Outlook]
    MS -->|40-60| NeutralOutlook[Neutral Outlook]
    
    BullishOutlook --> FinalAnalysis[Final Market Analysis]
    BearishOutlook --> FinalAnalysis
    NeutralOutlook --> FinalAnalysis
```

## Portfolio Analysis Flow

```mermaid
flowchart TD
    StartPortfolio([Portfolio Analysis]) --> LoadHoldings[Load All Holdings]
    LoadHoldings --> SeparateTypes{Position Types}
    
    SeparateTypes --> MISPositions[MIS Positions]
    SeparateTypes --> CNCPositions[CNC Positions]
    
    MISPositions --> AnalyzeMIS[Analyze Intraday]
    CNCPositions --> AnalyzeCNC[Analyze Delivery]
    
    AnalyzeMIS --> MISMetrics[Calculate MIS Metrics]
    MISMetrics --> MM1[Win Rate]
    MISMetrics --> MM2[Average P&L]
    MISMetrics --> MM3[Risk/Reward]
    
    AnalyzeCNC --> CNCMetrics[Calculate CNC Metrics]
    CNCMetrics --> CM1[Holding Period]
    CNCMetrics --> CM2[Unrealized P&L]
    CNCMetrics --> CM3[Sector Exposure]
    
    MM3 --> RiskAnalysis[Risk Analysis]
    CM3 --> RiskAnalysis
    
    RiskAnalysis --> RA1[Position Sizing]
    RiskAnalysis --> RA2[Correlation Risk]
    RiskAnalysis --> RA3[Concentration Risk]
    RiskAnalysis --> RA4[Drawdown Analysis]
    
    RA4 --> GenerateInsights[Generate Portfolio Insights]
    GenerateInsights --> Recommendations[Create Recommendations]
```

## Action Generation Logic

```mermaid
flowchart TD
    StartActions([Generate Actions]) --> AnalyzeConditions[Analyze All Conditions]
    
    AnalyzeConditions --> CheckConditions{Check Conditions}
    
    CheckConditions --> C1{High Risk Positions?}
    C1 -->|Yes| A1[Add: Reduce Position Size]
    
    CheckConditions --> C2{Concentrated Holdings?}
    C2 -->|Yes| A2[Add: Diversify Portfolio]
    
    CheckConditions --> C3{Losing Streak?}
    C3 -->|Yes| A3[Add: Reduce Activity]
    
    CheckConditions --> C4{Strong Trends?}
    C4 -->|Yes| A4[Add: Increase Trending Positions]
    
    CheckConditions --> C5{High Volatility?}
    C5 -->|Yes| A5[Add: Tighten Stop Losses]
    
    A1 --> CollectActions[Collect All Actions]
    A2 --> CollectActions
    A3 --> CollectActions
    A4 --> CollectActions
    A5 --> CollectActions
    
    CollectActions --> PrioritizeByRisk[Prioritize by Risk Impact]
    PrioritizeByRisk --> AssignScores[Assign Priority Scores]
    AssignScores --> SortActions[Sort by Priority]
    SortActions --> FinalActions[Final Action List]
```

## Report Generation Flow

```mermaid
flowchart TD
    StartReport([Generate Report]) --> CollectData[Collect All Analysis]
    
    CollectData --> CD1[Market Analysis]
    CollectData --> CD2[Portfolio Metrics]
    CollectData --> CD3[Risk Assessment]
    CollectData --> CD4[Action Items]
    
    CD1 --> FormatSections[Format Report Sections]
    CD2 --> FormatSections
    CD3 --> FormatSections
    CD4 --> FormatSections
    
    FormatSections --> CreateHTML[Create HTML Report]
    FormatSections --> CreateExcel[Create Excel Report]
    FormatSections --> CreatePDF[Create PDF Summary]
    
    CreateHTML --> AddCharts[Add Interactive Charts]
    CreateExcel --> AddTables[Add Data Tables]
    CreatePDF --> AddSummary[Add Executive Summary]
    
    AddCharts --> SaveHTML[Save HTML File]
    AddTables --> SaveExcel[Save Excel File]
    AddSummary --> SavePDF[Save PDF File]
    
    SaveHTML --> PrepareEmail[Prepare Email]
    SaveExcel --> PrepareEmail
    SavePDF --> PrepareEmail
    
    PrepareEmail --> SendReports[Send to Users]
```

## Action Plan Scoring System

```mermaid
flowchart TD
    StartScoring([Action Scoring]) --> GetAction[Get Action Item]
    GetAction --> EvaluateFactors[Evaluate Factors]
    
    EvaluateFactors --> F1[Risk Impact: 0-40 points]
    EvaluateFactors --> F2[Profit Potential: 0-30 points]
    EvaluateFactors --> F3[Urgency: 0-20 points]
    EvaluateFactors --> F4[Ease of Execution: 0-10 points]
    
    F1 --> CalculateScore[Calculate Total Score]
    F2 --> CalculateScore
    F3 --> CalculateScore
    F4 --> CalculateScore
    
    CalculateScore --> ScoreRange{Score Range}
    ScoreRange -->|80-100| Critical[Critical Priority]
    ScoreRange -->|60-79| High[High Priority]
    ScoreRange -->|40-59| Medium[Medium Priority]
    ScoreRange -->|< 40| Low[Low Priority]
    
    Critical --> AssignColor1[Color: Red]
    High --> AssignColor2[Color: Orange]
    Medium --> AssignColor3[Color: Yellow]
    Low --> AssignColor4[Color: Green]
    
    AssignColor1 --> FinalScore[Return Scored Action]
    AssignColor2 --> FinalScore
    AssignColor3 --> FinalScore
    AssignColor4 --> FinalScore
```

## Integration with Trading System

```mermaid
sequenceDiagram
    participant Scheduler
    participant ActionPlan
    participant MarketData
    participant Portfolio
    participant MLAnalysis
    participant ReportGen
    participant TradingSystem
    
    Scheduler->>ActionPlan: Trigger at 8:30 AM
    ActionPlan->>MarketData: Request market analysis
    MarketData-->>ActionPlan: Return market conditions
    
    ActionPlan->>Portfolio: Get portfolio status
    Portfolio-->>ActionPlan: Return positions & metrics
    
    ActionPlan->>MLAnalysis: Analyze patterns
    MLAnalysis-->>ActionPlan: Return insights
    
    ActionPlan->>ActionPlan: Generate action items
    ActionPlan->>ReportGen: Create reports
    
    ReportGen->>ReportGen: Format outputs
    ReportGen-->>ActionPlan: Reports ready
    
    ActionPlan->>TradingSystem: Update trading parameters
    TradingSystem-->>ActionPlan: Confirmation
    
    ActionPlan->>ActionPlan: Send notifications
```

## Daily Action Categories

```mermaid
graph TD
    Actions[Action Categories] --> Risk[Risk Management]
    Actions --> Opportunity[Opportunities]
    Actions --> Maintenance[Maintenance]
    Actions --> Strategy[Strategy Adjustment]
    
    Risk --> R1[Stop Loss Updates]
    Risk --> R2[Position Sizing]
    Risk --> R3[Hedge Recommendations]
    
    Opportunity --> O1[New Entry Signals]
    Opportunity --> O2[Scale-In Points]
    Opportunity --> O3[Sector Rotation]
    
    Maintenance --> M1[Rebalance Portfolio]
    Maintenance --> M2[Close Weak Positions]
    Maintenance --> M3[Update Watchlists]
    
    Strategy --> S1[Market Regime Change]
    Strategy --> S2[Adjust Parameters]
    Strategy --> S3[Switch Strategies]
```