# Market Regime Module - Sequence Diagrams

## Complete Analysis Workflow

```mermaid
sequenceDiagram
    participant Scheduler as Cron/Scheduler
    participant MRA as MarketRegimeAnalyzer
    participant FileLoader as FileLoader
    participant ISA as IndexSMAAnalyzer
    participant KiteAPI as KiteConnect API
    participant RS as RegimeSmoother
    participant ML as MLModel
    participant Storage as JSON Storage
    participant Dashboard as Dashboard Generator
    participant API as API Server
    
    Scheduler->>MRA: Trigger Analysis (every 30min)
    
    Note over MRA: Load Scanner Results
    MRA->>FileLoader: Load latest scanner files
    FileLoader->>FileLoader: Find Long_Reversal_*.xlsx
    FileLoader->>FileLoader: Find Short_Reversal_*.xlsx
    FileLoader-->>MRA: Scanner DataFrames
    
    Note over MRA: Validate Data
    MRA->>MRA: Validate data quality
    alt Data Invalid
        MRA->>Storage: Log error
        MRA-->>Scheduler: Exit with error
    end
    
    Note over MRA: Index Analysis
    MRA->>ISA: Request index analysis
    ISA->>KiteAPI: Fetch NIFTY 50 data
    KiteAPI-->>ISA: Price data
    ISA->>KiteAPI: Fetch NIFTY MIDCAP data
    KiteAPI-->>ISA: Price data
    ISA->>KiteAPI: Fetch NIFTY SMALLCAP data
    KiteAPI-->>ISA: Price data
    
    ISA->>ISA: Calculate SMA20 for each index
    ISA->>ISA: Determine above/below SMA20
    ISA->>ISA: Calculate position percentages
    ISA->>ISA: Determine overall trend
    ISA-->>MRA: Index analysis results
    
    Note over MRA: Pattern Analysis
    MRA->>MRA: Count long/short patterns
    MRA->>MRA: Calculate L/S ratio
    MRA->>MRA: Analyze pattern quality
    MRA->>MRA: Calculate trend metrics
    
    Note over MRA: ML Prediction
    MRA->>ML: Get regime prediction
    ML->>ML: Feature extraction
    ML->>ML: Model inference
    ML-->>MRA: Predicted regime + confidence
    
    Note over MRA: Signal Combination
    MRA->>MRA: Combine patterns (70%) + indices (30%)
    MRA->>MRA: Calculate weighted regime
    MRA->>MRA: Determine confidence score
    
    Note over MRA: Regime Smoothing
    MRA->>RS: Check regime change validity
    RS->>RS: Check minimum duration (2hrs)
    RS->>RS: Validate confidence threshold (70%)
    RS->>RS: Check volatility limits
    alt Change Not Allowed
        RS-->>MRA: Maintain current regime
    else Change Allowed
        RS-->>MRA: Accept new regime
    end
    
    Note over MRA: Generate Output
    MRA->>MRA: Generate insights
    MRA->>MRA: Calculate position recommendations
    MRA->>MRA: Create comprehensive report
    
    MRA->>Storage: Save regime_report_*.json
    MRA->>Storage: Update latest_regime_summary.json
    
    MRA->>Dashboard: Trigger dashboard generation
    Dashboard->>Storage: Read latest summary
    Dashboard->>Dashboard: Generate HTML dashboard
    
    MRA->>API: Notify new data available
    API->>API: Update cached responses
    
    MRA-->>Scheduler: Analysis complete
```

## Dashboard Update Sequence

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Static as Static Dashboard
    participant Enhanced as Enhanced Dashboard
    participant Health as Health Dashboard
    participant API as API Endpoints
    participant FileSystem as File System
    participant Cache as Cache Layer
    
    Note over User: Access Dashboards
    
    User->>Static: GET http://localhost:5001
    Static->>FileSystem: Read market_regime_dashboard.html
    FileSystem-->>Static: HTML content
    Static-->>User: Display static dashboard
    
    User->>Enhanced: GET http://localhost:8080
    Enhanced->>Enhanced: Load dashboard template
    Enhanced-->>User: Dashboard with "Loading..." states
    
    Note over Enhanced: JavaScript Auto-Update
    Enhanced->>API: GET /api/current_analysis
    API->>FileSystem: Read latest_regime_summary.json
    FileSystem-->>API: JSON data
    API->>API: Format API response
    API-->>Enhanced: Current analysis data
    
    Enhanced->>Enhanced: updateDashboard()
    Enhanced->>Enhanced: Update regime display
    Enhanced->>Enhanced: Update metrics
    Enhanced->>Enhanced: updateMacroMicroView()
    Enhanced->>Enhanced: Update charts
    Enhanced-->>User: Updated dashboard content
    
    User->>Health: GET http://localhost:7080
    Health->>API: GET /api/health
    API->>FileSystem: Check file timestamps
    API->>FileSystem: Validate data freshness
    FileSystem-->>API: Health metrics
    API-->>Health: System status
    Health->>Health: updateMacroMicroView()
    Health-->>User: Health dashboard
    
    Note over Enhanced,Health: Auto-refresh every 30 seconds
    loop Auto Refresh
        Enhanced->>API: GET /api/current_analysis
        API->>Cache: Check cached response
        alt Cache Valid
            Cache-->>API: Cached data
        else Cache Expired
            API->>FileSystem: Read fresh data
            FileSystem-->>API: Latest data
            API->>Cache: Update cache
        end
        API-->>Enhanced: Response data
        Enhanced->>Enhanced: Update UI components
    end
```

## Regime Smoothing Logic Flow

```mermaid
sequenceDiagram
    participant MRA as MarketRegimeAnalyzer
    participant RS as RegimeSmoother
    participant Config as Configuration
    participant History as RegimeHistory
    participant Validator as ChangeValidator
    
    MRA->>RS: smooth_regime_change(new_regime, confidence)
    
    RS->>Config: Get smoothing parameters
    Config-->>RS: min_duration=2hrs, threshold=0.7, etc.
    
    RS->>History: Get current regime info
    History-->>RS: current_regime, start_time, duration
    
    Note over RS: Duration Check
    RS->>RS: Calculate regime duration
    alt Duration < 2 hours
        RS->>RS: Log: "Regime too new, maintaining current"
        RS-->>MRA: current_regime (no change)
    end
    
    Note over RS: Confidence Check
    alt Confidence < 70%
        RS->>Validator: Check volatility conditions
        Validator->>Validator: Calculate market volatility
        alt High Volatility (>50%)
            Validator-->>RS: Reject change - high volatility
            RS-->>MRA: current_regime (no change)
        else Low Volatility
            Validator-->>RS: Allow change - low volatility
        end
    end
    
    Note over RS: Moving Average Check
    RS->>RS: Apply 3-period moving average
    RS->>RS: Check against extreme thresholds
    alt Extreme ratio (>3.0 or <0.33)
        RS->>RS: Log: "Extreme ratio detected"
        RS-->>MRA: current_regime (no change)
    end
    
    Note over RS: Final Validation
    RS->>RS: All conditions passed
    RS->>History: Update regime history
    History->>History: Record regime change
    RS->>RS: Log: "Regime change approved"
    RS-->>MRA: new_regime (change accepted)
```

## Index Data Fetching Workflow

```mermaid
sequenceDiagram
    participant ISA as IndexSMAAnalyzer
    participant Cache as CacheManager
    participant KiteAPI as KiteConnect API
    participant Calculator as SMACalculator
    participant Validator as DataValidator
    
    ISA->>ISA: fetch_index_data()
    
    loop For each index (NIFTY 50, MIDCAP, SMALLCAP)
        ISA->>Cache: Check cached data
        Cache->>Cache: Check timestamp (5min TTL)
        alt Cache Valid
            Cache-->>ISA: Return cached data
        else Cache Expired/Missing
            ISA->>KiteAPI: fetch_single_index(token)
            KiteAPI->>KiteAPI: Get current price
            alt API Success
                KiteAPI-->>ISA: Price data
                ISA->>Calculator: Calculate SMA20
                Calculator->>Calculator: Get 20-period average
                Calculator-->>ISA: SMA20 value
                
                ISA->>Validator: Validate data quality
                Validator->>Validator: Check price > 0
                Validator->>Validator: Check SMA20 > 0
                Validator->>Validator: Check reasonable deviation
                alt Data Valid
                    Validator-->>ISA: Data OK
                    ISA->>Cache: Update cache
                    Cache->>Cache: Store with timestamp
                else Data Invalid
                    Validator-->>ISA: Data error
                    ISA->>ISA: Log error, use fallback
                end
            else API Failure
                KiteAPI-->>ISA: Error response
                ISA->>Cache: Try to use stale cache
                alt Stale Cache Available
                    Cache-->>ISA: Stale but usable data
                else No Cache
                    ISA->>ISA: Mark index as unavailable
                end
            end
        end
    end
    
    ISA->>ISA: analyze_trend()
    ISA->>ISA: Count indices above SMA20
    ISA->>ISA: Calculate average position
    ISA->>ISA: Determine overall trend
    ISA-->>Calculator: Complete index analysis
```

## ML Model Integration Flow

```mermaid
sequenceDiagram
    participant MRA as MarketRegimeAnalyzer
    participant ML as MLModel
    participant Features as FeatureExtractor
    participant Model as RandomForestModel
    participant Performance as PerformanceTracker
    
    MRA->>ML: get_regime_prediction(pattern_data, index_data)
    
    ML->>Features: extract_features()
    Features->>Features: Calculate current_ratio
    Features->>Features: Calculate ma3_long, ma3_short
    Features->>Features: Calculate avg_ratio
    Features->>Features: Calculate momentum
    Features->>Features: Add index features
    Features-->>ML: Feature vector
    
    ML->>Model: predict(features)
    Model->>Model: Apply trained random forest
    Model->>Model: Get prediction probabilities
    Model-->>ML: Predicted regime + confidence
    
    ML->>Performance: record_prediction()
    Performance->>Performance: Store prediction details
    Performance->>Performance: Update prediction count
    Performance-->>ML: Tracking updated
    
    Note over ML: Format Response
    ML->>ML: Map prediction to regime string
    ML->>ML: Calculate confidence percentage
    ML->>ML: Add model metadata
    ML-->>MRA: Regime prediction with confidence
    
    Note over Performance: Background Performance Tracking
    Performance->>Performance: Check if outcome available
    alt Outcome Available
        Performance->>Performance: Calculate accuracy
        Performance->>Performance: Update regime-specific accuracy
        Performance->>Performance: Store performance metrics
    end
```

## Error Handling and Recovery

```mermaid
sequenceDiagram
    participant MRA as MarketRegimeAnalyzer
    participant ErrorHandler as ErrorHandler
    participant Logger as Logger
    participant Fallback as FallbackSystem
    participant AlertSystem as AlertSystem
    
    Note over MRA: Error Scenarios
    
    alt Scanner Files Missing
        MRA->>ErrorHandler: handle_missing_files()
        ErrorHandler->>Logger: Log critical error
        ErrorHandler->>Fallback: Use previous analysis
        Fallback-->>ErrorHandler: Previous regime data
        ErrorHandler->>AlertSystem: Send alert
        ErrorHandler-->>MRA: Fallback regime
    end
    
    alt Index API Failure
        MRA->>ErrorHandler: handle_api_failure()
        ErrorHandler->>Logger: Log API error
        ErrorHandler->>Fallback: Use pattern-only analysis
        Fallback->>Fallback: Analyze with 100% pattern weight
        Fallback-->>ErrorHandler: Pattern-based regime
        ErrorHandler->>AlertSystem: Send degraded mode alert
        ErrorHandler-->>MRA: Pattern-only regime
    end
    
    alt ML Model Error
        MRA->>ErrorHandler: handle_ml_failure()
        ErrorHandler->>Logger: Log ML error
        ErrorHandler->>Fallback: Use rule-based classification
        Fallback->>Fallback: Apply traditional thresholds
        Fallback-->>ErrorHandler: Rule-based regime
        ErrorHandler-->>MRA: Fallback regime
    end
    
    alt Data Corruption
        MRA->>ErrorHandler: handle_data_corruption()
        ErrorHandler->>Logger: Log data integrity error
        ErrorHandler->>Fallback: Attempt data recovery
        Fallback->>Fallback: Clean and validate data
        alt Recovery Successful
            Fallback-->>ErrorHandler: Cleaned data
            ErrorHandler-->>MRA: Continue with cleaned data
        else Recovery Failed
            Fallback-->>ErrorHandler: Recovery failed
            ErrorHandler->>AlertSystem: Send critical alert
            ErrorHandler-->>MRA: Use emergency fallback
        end
    end
```

## Dashboard Real-time Update Flow

```mermaid
sequenceDiagram
    participant JS as JavaScript Client
    participant API as Flask API Server
    participant FileWatcher as File Watcher
    participant JSON as JSON Files
    participant UI as UI Components
    
    Note over JS: Dashboard Initialization
    JS->>JS: Page load complete
    JS->>JS: Start auto-refresh timer (30s)
    JS->>API: Initial data fetch
    
    loop Auto-refresh Cycle
        JS->>API: GET /api/current_analysis
        API->>JSON: Check latest_regime_summary.json
        JSON-->>API: File content + timestamp
        API->>API: Parse and validate JSON
        API->>API: Format for client consumption
        API-->>JS: Structured response
        
        JS->>JS: Update regime display
        JS->>JS: Update confidence metrics
        JS->>JS: updateMacroMicroView(data)
        
        Note over JS: Macro/Micro View Update
        JS->>JS: Process index_analysis data
        JS->>UI: Update macro status
        JS->>UI: Update macro recommendation
        JS->>UI: Update index details
        JS->>UI: Update micro status
        JS->>UI: Update micro recommendation
        JS->>UI: Update micro details
        
        JS->>JS: Check for divergence
        alt Divergence Detected
            JS->>UI: Show divergence warning
            JS->>UI: Set warning styling
        else Views Aligned
            JS->>UI: Show alignment indicator
            JS->>UI: Set success styling
        end
        
        JS->>JS: Update charts and sparklines
        JS->>JS: Update timestamps
        
        Note over JS: Wait for next cycle
        JS->>JS: setTimeout(30000)
    end
    
    Note over FileWatcher: Background File Monitoring
    FileWatcher->>JSON: Monitor file changes
    alt File Updated
        FileWatcher->>API: Invalidate cache
        FileWatcher->>FileWatcher: Log file change
    end
```

## System Health Monitoring Flow

```mermaid
sequenceDiagram
    participant Monitor as HealthMonitor
    participant Files as FileSystem
    participant APIs as ExternalAPIs
    participant Services as ServiceCheck
    participant Alerting as AlertSystem
    participant Dashboard as HealthDashboard
    
    Monitor->>Monitor: Start health check cycle
    
    Note over Monitor: File System Checks
    Monitor->>Files: Check regime analysis files
    Files->>Files: Verify latest_regime_summary.json exists
    Files->>Files: Check file timestamp (< 40 min old)
    Files->>Files: Validate JSON structure
    Files-->>Monitor: File health status
    
    Note over Monitor: Scanner Results Check
    Monitor->>Files: Check scanner result files
    Files->>Files: Look for today's Long_Reversal files
    Files->>Files: Look for today's Short_Reversal files
    Files-->>Monitor: Scanner file status
    
    Note over Monitor: API Health Check
    Monitor->>APIs: Test KiteConnect connectivity
    APIs->>APIs: Attempt token validation
    APIs-->>Monitor: API status
    
    Note over Monitor: Service Health Check
    Monitor->>Services: Check dashboard processes
    Services->>Services: Verify Flask apps running
    Services->>Services: Test port connectivity
    Services-->>Monitor: Service status
    
    Note over Monitor: ML Model Check
    Monitor->>Files: Check model performance metrics
    Files->>Files: Verify accuracy thresholds
    Files-->>Monitor: Model health status
    
    Note over Monitor: Generate Health Report
    Monitor->>Monitor: Aggregate all status checks
    Monitor->>Monitor: Calculate overall health score
    Monitor->>Monitor: Identify critical issues
    
    alt Critical Issues Found
        Monitor->>Alerting: Send critical alerts
        Alerting->>Alerting: Format alert messages
        Alerting->>Alerting: Send notifications
    end
    
    Monitor->>Dashboard: Update health dashboard
    Dashboard->>Dashboard: Display status indicators
    Dashboard->>Dashboard: Show system metrics
    Dashboard->>Dashboard: updateMacroMicroView()
    
    Monitor->>Monitor: Schedule next health check
```

---

## Key Sequence Patterns

### 1. **Error-First Design**
All sequences include comprehensive error handling with graceful degradation.

### 2. **Caching Strategy**
Data fetching sequences implement multi-level caching for performance.

### 3. **Real-time Updates**
Dashboard sequences show how real-time data flows to users.

### 4. **Validation Gates**
Each sequence includes validation checkpoints to ensure data quality.

### 5. **Monitoring Integration**
All flows include monitoring and alerting touchpoints.

---

*Sequence diagrams for India-TS Market Regime Analysis Module v3.0*  
*Generated: July 14, 2025*