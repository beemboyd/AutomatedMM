# Market Regime Module - Architecture Diagrams

## System Architecture Overview

```mermaid
graph TB
    subgraph "External Data Sources"
        SC[Scanner Results<br/>Excel Files]
        KA[KiteConnect API<br/>Index Data]
        ML_DATA[Historical ML Data<br/>Training Sets]
    end
    
    subgraph "Data Layer"
        FS[File System<br/>JSON Reports]
        CACHE[Cache Layer<br/>Index Data]
        DB[SQLite Database<br/>ML Model]
    end
    
    subgraph "Core Processing Layer"
        MRA[Market Regime Analyzer<br/>Main Engine]
        RS[Regime Smoother<br/>Stability Filter]
        ISA[Index SMA Analyzer<br/>Macro Analysis]
        ML[ML Model<br/>Prediction Engine]
    end
    
    subgraph "Analysis Layer"
        PA[Pattern Analysis<br/>Micro View]
        IA[Index Analysis<br/>Macro View]
        CS[Confidence Scoring<br/>Risk Assessment]
        PR[Position Recommendations<br/>Trade Sizing]
    end
    
    subgraph "Presentation Layer"
        TD[Trend Dashboard<br/>Static HTML :5001]
        ED[Enhanced Dashboard<br/>Flask App :8080]
        HD[Health Dashboard<br/>Monitoring :7080]
    end
    
    subgraph "API Layer"
        API1[Current Analysis API<br/>/api/current_analysis]
        API2[Health Status API<br/>/api/health]
        API3[Pattern Data API<br/>/api/g_pattern_data]
    end
    
    %% Data Flow
    SC --> MRA
    KA --> ISA
    ML_DATA --> ML
    
    MRA --> FS
    ISA --> CACHE
    ML --> DB
    
    MRA --> RS
    MRA --> PA
    ISA --> IA
    PA --> CS
    IA --> CS
    CS --> PR
    
    FS --> TD
    FS --> API1
    FS --> API2
    
    API1 --> ED
    API2 --> HD
    API3 --> ED
    
    %% Styling
    classDef dataSource fill:#e1f5fe
    classDef processing fill:#f3e5f5
    classDef analysis fill:#e8f5e8
    classDef presentation fill:#fff3e0
    classDef api fill:#fce4ec
    
    class SC,KA,ML_DATA dataSource
    class MRA,RS,ISA,ML processing
    class PA,IA,CS,PR analysis
    class TD,ED,HD presentation
    class API1,API2,API3 api
```

## Component Interaction Diagram

```mermaid
graph LR
    subgraph "Input Processing"
        A[Scanner Results Loader]
        B[Data Validator]
        C[Index Data Fetcher]
    end
    
    subgraph "Analysis Core"
        D[Pattern Analyzer]
        E[Trend Calculator]
        F[Index SMA Calculator]
        G[Signal Combiner]
    end
    
    subgraph "Decision Engine"
        H[Regime Classifier]
        I[Confidence Calculator]
        J[Smoothing Filter]
        K[ML Predictor]
    end
    
    subgraph "Output Generation"
        L[Report Generator]
        M[Dashboard Updater]
        N[API Response Builder]
    end
    
    A --> B
    C --> B
    B --> D
    B --> F
    D --> E
    F --> G
    E --> G
    G --> H
    H --> I
    I --> J
    K --> H
    J --> L
    L --> M
    L --> N
```

## Data Flow Architecture

```mermaid
flowchart TD
    subgraph "Data Sources"
        DS1["📊 Long Reversals<br/>Daily/results/*.xlsx"]
        DS2["📊 Short Reversals<br/>Daily/results-s/*.xlsx"]
        DS3["📈 NIFTY 50<br/>Token: 256265"]
        DS4["📈 NIFTY MIDCAP<br/>Token: 288009"]
        DS5["📈 NIFTY SMALLCAP<br/>Token: 288265"]
    end
    
    subgraph "Data Processing"
        DP1["🔄 Load & Validate<br/>Excel → DataFrame"]
        DP2["🔄 Fetch Index Data<br/>KiteConnect API"]
        DP3["🔄 Calculate SMA20<br/>20-period average"]
    end
    
    subgraph "Analysis Engine"
        AE1["📊 Pattern Analysis<br/>Long/Short Ratio"]
        AE2["📈 Index Analysis<br/>Above/Below SMA20"]
        AE3["🤖 ML Prediction<br/>Regime Classification"]
        AE4["⚖️ Signal Combination<br/>70% Pattern + 30% Index"]
    end
    
    subgraph "Filtering & Validation"
        FV1["🕐 Regime Smoother<br/>Min 2hr Duration"]
        FV2["📊 Confidence Check<br/>Min 70% Threshold"]
        FV3["📈 Volatility Filter<br/>Max 50% Volatility"]
    end
    
    subgraph "Output Generation"
        OG1["📄 JSON Report<br/>latest_regime_summary.json"]
        OG2["🌐 Static Dashboard<br/>HTML Generation"]
        OG3["⚡ Real-time API<br/>Flask Endpoints"]
        OG4["🏥 Health Monitor<br/>System Status"]
    end
    
    DS1 --> DP1
    DS2 --> DP1
    DS3 --> DP2
    DS4 --> DP2
    DS5 --> DP2
    DP2 --> DP3
    
    DP1 --> AE1
    DP3 --> AE2
    AE1 --> AE3
    AE2 --> AE3
    AE1 --> AE4
    AE2 --> AE4
    AE3 --> AE4
    
    AE4 --> FV1
    FV1 --> FV2
    FV2 --> FV3
    
    FV3 --> OG1
    OG1 --> OG2
    OG1 --> OG3
    OG1 --> OG4
```

## Service Architecture

```mermaid
graph TB
    subgraph "Load Balancer / Reverse Proxy"
        LB[nginx/Apache<br/>Port 80/443]
    end
    
    subgraph "Dashboard Services"
        DS1[Static Dashboard<br/>HTML Files<br/>Port 5001]
        DS2[Enhanced Dashboard<br/>Flask App<br/>Port 8080]
        DS3[Health Dashboard<br/>Flask App<br/>Port 7080]
    end
    
    subgraph "Background Services"
        BS1[Market Regime Analyzer<br/>Scheduled Task]
        BS2[Index Data Fetcher<br/>API Service]
        BS3[ML Model Trainer<br/>Periodic Job]
    end
    
    subgraph "Data Storage"
        ST1[JSON Files<br/>regime_analysis/]
        ST2[Cache Layer<br/>Index Data]
        ST3[SQLite DB<br/>ML Training Data]
    end
    
    LB --> DS1
    LB --> DS2
    LB --> DS3
    
    BS1 --> ST1
    BS2 --> ST2
    BS3 --> ST3
    
    DS2 --> ST1
    DS3 --> ST1
    DS1 --> ST1
```

## Integration Architecture

```mermaid
graph LR
    subgraph "India-TS Core System"
        SCAN[Scanner Module<br/>Pattern Detection]
        POS[Position Manager<br/>Trade Execution]
        RISK[Risk Manager<br/>Stop Loss Logic]
        STATE[State Manager<br/>System State]
    end
    
    subgraph "Market Regime Module"
        MRM[Regime Analyzer<br/>Market Analysis]
        DASH[Dashboard Suite<br/>Visualization]
        API[API Layer<br/>Data Access]
    end
    
    subgraph "External Systems"
        KITE[KiteConnect<br/>Broker API]
        ALERT[Alert System<br/>Notifications]
        REPORT[Reporting<br/>Analytics]
    end
    
    SCAN --> MRM
    MRM --> POS
    MRM --> RISK
    STATE --> MRM
    
    MRM --> DASH
    MRM --> API
    
    API --> ALERT
    API --> REPORT
    KITE --> MRM
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Web Server"
            WS1[nginx<br/>Static Content]
            WS2[uWSGI<br/>Flask Apps]
        end
        
        subgraph "Application Layer"
            APP1[Dashboard Apps<br/>Python/Flask]
            APP2[Analysis Engine<br/>Python Scripts]
            APP3[Cron Jobs<br/>Scheduled Tasks]
        end
        
        subgraph "Data Layer"
            DATA1[File System<br/>JSON/Excel]
            DATA2[SQLite DB<br/>ML Data]
            DATA3[Log Files<br/>System Logs]
        end
    end
    
    subgraph "External Services"
        EXT1[KiteConnect API<br/>Market Data]
        EXT2[Scanner Results<br/>Pattern Detection]
        EXT3[Monitoring<br/>Health Checks]
    end
    
    WS1 --> APP1
    WS2 --> APP1
    APP1 --> APP2
    APP2 --> DATA1
    APP2 --> DATA2
    APP3 --> APP2
    
    APP2 --> EXT1
    EXT2 --> APP2
    APP1 --> EXT3
```

## Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        subgraph "Network Security"
            FW[Firewall<br/>Port Restrictions]
            SSL[SSL/TLS<br/>HTTPS Only]
        end
        
        subgraph "Application Security"
            AUTH[Authentication<br/>API Keys]
            VALID[Input Validation<br/>Data Sanitization]
            RATE[Rate Limiting<br/>API Throttling]
        end
        
        subgraph "Data Security"
            ENCRYPT[File Encryption<br/>Sensitive Data]
            BACKUP[Secure Backups<br/>Data Recovery]
            ACCESS[Access Control<br/>File Permissions]
        end
    end
    
    subgraph "Monitoring & Logging"
        LOG[Security Logs<br/>Audit Trail]
        ALERT[Security Alerts<br/>Anomaly Detection]
        HEALTH[Health Checks<br/>System Integrity]
    end
    
    FW --> AUTH
    SSL --> VALID
    AUTH --> RATE
    VALID --> ENCRYPT
    RATE --> BACKUP
    ENCRYPT --> ACCESS
    
    ACCESS --> LOG
    LOG --> ALERT
    ALERT --> HEALTH
```

## Performance Architecture

```mermaid
graph LR
    subgraph "Performance Optimization"
        subgraph "Caching Strategy"
            C1[Index Data Cache<br/>5-minute TTL]
            C2[Analysis Cache<br/>Result Memoization]
            C3[Dashboard Cache<br/>Static Generation]
        end
        
        subgraph "Async Processing"
            A1[Background Jobs<br/>Non-blocking Analysis]
            A2[API Responses<br/>Cached Results]
            A3[File I/O<br/>Batched Operations]
        end
        
        subgraph "Resource Management"
            R1[Memory Limits<br/>Process Monitoring]
            R2[CPU Throttling<br/>Load Management]
            R3[Disk I/O<br/>Efficient Storage]
        end
    end
    
    C1 --> A1
    C2 --> A2
    C3 --> A3
    A1 --> R1
    A2 --> R2
    A3 --> R3
```

---

## Component Relationships

### Core Dependencies

```mermaid
graph TD
    MRA[MarketRegimeAnalyzer] --> |uses| RS[RegimeSmoother]
    MRA --> |uses| ISA[IndexSMAAnalyzer]
    MRA --> |generates| JSON[JSON Reports]
    
    TD[TrendDashboard] --> |reads| JSON
    ED[DashboardEnhanced] --> |reads| JSON
    HD[HealthDashboard] --> |reads| JSON
    
    ISA --> |fetches from| KITE[KiteConnect API]
    MRA --> |processes| SCAN[Scanner Results]
    
    RS --> |validates| CONF[Configuration]
    ISA --> |caches to| CACHE[Cache Layer]
    MRA --> |trains| ML[ML Model]
```

### Data Dependencies

```mermaid
flowchart LR
    subgraph "Input Dependencies"
        I1[Scanner Excel Files]
        I2[KiteConnect API Access]
        I3[Historical ML Data]
    end
    
    subgraph "Processing Dependencies"
        P1[Python 3.8+]
        P2[pandas, numpy]
        P3[scikit-learn]
        P4[Flask, requests]
    end
    
    subgraph "Output Dependencies"
        O1[Web Server (nginx)]
        O2[File System Access]
        O3[Network Ports 5001,8080,7080]
    end
    
    I1 --> P1
    I2 --> P2
    I3 --> P3
    P1 --> O1
    P2 --> O2
    P4 --> O3
```

---

*Architecture diagrams for India-TS Market Regime Analysis Module v3.0*  
*Generated: July 14, 2025*