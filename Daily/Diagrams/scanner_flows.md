# Scanner Flows

## Overview
The scanner system identifies trading opportunities based on various technical analysis strategies. Multiple scanners run throughout the trading day to capture different market conditions.

## Scanner Types and Execution

```mermaid
graph TB
    subgraph "Scanner Types"
        A[Al Brooks Scanner] -->|4x daily| A1[9:30 AM]
        A -->|11:30 AM| A2[11:30 AM]
        A -->|1:30 PM| A3[1:30 PM]
        A -->|4:00 PM| A4[4:00 PM]
        
        B[Pattern Scanner] -->|Daily| B1[Market Hours]
        C[Price Action Scanner] -->|Daily| C1[Market Hours]
        D[Reversal Scanner] -->|Multiple Times| D1[Scheduled]
    end
```

## Al Brooks Higher Probability Reversal Scanner Flow

```mermaid
flowchart TD
    Start([Scanner Triggered]) --> LoadConfig[Load Configuration]
    LoadConfig --> LoadTickers[Load Tickers from Ticker.xlsx]
    
    LoadTickers --> InitKite[Initialize Kite Connection]
    InitKite --> AuthCheck{Authentication Valid?}
    AuthCheck -->|No| Login[Perform Login]
    Login --> InitKite
    AuthCheck -->|Yes| ProcessTickers[Process Each Ticker]
    
    ProcessTickers --> FetchData[Fetch Historical Data]
    FetchData --> CalcIndicators[Calculate Technical Indicators]
    
    CalcIndicators --> CalcSwings[Calculate Swing Points]
    CalcSwings --> CalcEMA[Calculate EMAs 10/20]
    CalcEMA --> CalcVWAP[Calculate VWAP]
    CalcVWAP --> CalcATR[Calculate ATR]
    
    CalcATR --> CheckPattern{Check Reversal Pattern}
    CheckPattern -->|No Pattern| NextTicker{More Tickers?}
    CheckPattern -->|Pattern Found| ScorePattern[Calculate Pattern Score]
    
    ScorePattern --> CheckFilters{Apply Filters}
    CheckFilters -->|Pass| AddToResults[Add to Results]
    CheckFilters -->|Fail| NextTicker
    
    AddToResults --> NextTicker
    NextTicker -->|Yes| ProcessTickers
    NextTicker -->|No| GenerateReport[Generate Excel Report]
    
    GenerateReport --> CreateHTML[Create HTML Analysis]
    CreateHTML --> SaveResults[Save to results/]
    SaveResults --> End([Scanner Complete])
```

## Pattern Scanner Flow

```mermaid
flowchart TD
    Start([Pattern Scanner Start]) --> LoadData[Load Market Data]
    LoadData --> ScanPatterns[Scan for Patterns]
    
    ScanPatterns --> Pattern1{Head & Shoulders}
    ScanPatterns --> Pattern2{Double Top/Bottom}
    ScanPatterns --> Pattern3{Triangle Patterns}
    ScanPatterns --> Pattern4{Flag/Pennant}
    
    Pattern1 -->|Found| ValidateP1[Validate Pattern]
    Pattern2 -->|Found| ValidateP2[Validate Pattern]
    Pattern3 -->|Found| ValidateP3[Validate Pattern]
    Pattern4 -->|Found| ValidateP4[Validate Pattern]
    
    ValidateP1 --> CheckVolume1{Volume Confirmation?}
    ValidateP2 --> CheckVolume2{Volume Confirmation?}
    ValidateP3 --> CheckVolume3{Volume Confirmation?}
    ValidateP4 --> CheckVolume4{Volume Confirmation?}
    
    CheckVolume1 -->|Yes| AddResult1[Add to Results]
    CheckVolume2 -->|Yes| AddResult2[Add to Results]
    CheckVolume3 -->|Yes| AddResult3[Add to Results]
    CheckVolume4 -->|Yes| AddResult4[Add to Results]
    
    AddResult1 --> CombineResults[Combine All Results]
    AddResult2 --> CombineResults
    AddResult3 --> CombineResults
    AddResult4 --> CombineResults
    
    CombineResults --> FilterResults[Apply Risk Filters]
    FilterResults --> SaveScan[Save Scan Results]
    SaveScan --> NotifySystem[Notify Trading System]
    NotifySystem --> End([Scanner Complete])
```

## Scanner Integration with Trading System

```mermaid
flowchart LR
    subgraph "Scanners"
        S1[Al Brooks Scanner]
        S2[Pattern Scanner]
        S3[Price Action Scanner]
    end
    
    subgraph "Results Processing"
        R1[Scan Results]
        R2[Filter & Rank]
        R3[Store in Excel/CSV]
    end
    
    subgraph "Trading System"
        T1[Order Placement]
        T2[Position Management]
        T3[Risk Management]
    end
    
    S1 --> R1
    S2 --> R1
    S3 --> R1
    
    R1 --> R2
    R2 --> R3
    R3 --> T1
    T1 --> T2
    T2 --> T3
```

## Scanner Data Flow

```mermaid
sequenceDiagram
    participant Scheduler
    participant Scanner
    participant KiteAPI
    participant DataProcessor
    participant Storage
    participant TradingSystem
    
    Scheduler->>Scanner: Trigger scan
    Scanner->>KiteAPI: Request market data
    KiteAPI-->>Scanner: Return historical data
    Scanner->>DataProcessor: Process indicators
    DataProcessor->>DataProcessor: Calculate patterns
    DataProcessor-->>Scanner: Return signals
    Scanner->>Storage: Save results
    Storage-->>TradingSystem: Notify new signals
    TradingSystem->>TradingSystem: Process orders
```

## Scanner Configuration

```mermaid
graph TD
    Config[config.ini] --> ScannerSettings
    
    subgraph "Scanner Settings"
        SS1[Timeframe Settings]
        SS2[Indicator Parameters]
        SS3[Pattern Thresholds]
        SS4[Risk Filters]
        SS5[Output Formats]
    end
    
    ScannerSettings --> SS1
    ScannerSettings --> SS2
    ScannerSettings --> SS3
    ScannerSettings --> SS4
    ScannerSettings --> SS5
    
    SS1 --> Scanner[Scanner Execution]
    SS2 --> Scanner
    SS3 --> Scanner
    SS4 --> Scanner
    SS5 --> Scanner
```