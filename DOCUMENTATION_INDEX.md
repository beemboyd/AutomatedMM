# India-TS Complete Documentation Index

## Overview
This document provides a comprehensive index to all documentation for the India-TS trading system, including the new Market Regime Analysis Module.

## Core System Documentation

### 1. System Overview & Architecture
- **[INDIA_TS_3.0_OVERVIEW.md](Documentation/INDIA_TS_3.0_OVERVIEW.md)** - Complete system overview and features
- **[INDIA_TS_3.0_COMPONENT_DIAGRAMS.md](Documentation/INDIA_TS_3.0_COMPONENT_DIAGRAMS.md)** - System architecture diagrams
- **[INDIA_TS_3.0_DASHBOARD_ARCHITECTURE.md](Documentation/INDIA_TS_3.0_DASHBOARD_ARCHITECTURE.md)** - Dashboard system design
- **[INDIA_TS_3.0_FEATURE_DETAILS.md](Documentation/INDIA_TS_3.0_FEATURE_DETAILS.md)** - Detailed feature specifications
- **[INDIA_TS_3.0_QUICK_REFERENCE.md](Documentation/INDIA_TS_3.0_QUICK_REFERENCE.md)** - Quick reference guide

### 2. Setup & Configuration
- **[GIT_WORKFLOW_GOLDEN_VERSION.md](Documentation/GIT_WORKFLOW_GOLDEN_VERSION.md)** - Git workflow and version management
- **[GOLDEN_VERSION_SETUP_GUIDE.md](GOLDEN_VERSION_SETUP_GUIDE.md)** - Complete setup instructions
- **[CLAUDE.md](CLAUDE.md)** - Claude AI assistant instructions and build commands

### 3. Recent Updates
- **[JULY_2025_DASHBOARD_UPDATE.md](Documentation/JULY_2025_DASHBOARD_UPDATE.md)** - Latest dashboard improvements
- **[MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md)** - System migration documentation

## Market Regime Analysis Module Documentation 📊

### 1. Core Documentation
- **[MARKET_REGIME_MODULE_DOCUMENTATION.md](Documentation/MARKET_REGIME_MODULE_DOCUMENTATION.md)** - Complete module overview, features, and implementation details
- **[MARKET_REGIME_ARCHITECTURE_DIAGRAMS.md](Documentation/MARKET_REGIME_ARCHITECTURE_DIAGRAMS.md)** - Architecture diagrams and component relationships
- **[MARKET_REGIME_SEQUENCE_DIAGRAMS.md](Documentation/MARKET_REGIME_SEQUENCE_DIAGRAMS.md)** - Detailed workflow sequence diagrams

### 2. Technical Specifications
- **[MARKET_REGIME_API_DATA_FLOW.md](Documentation/MARKET_REGIME_API_DATA_FLOW.md)** - API documentation and data flow specifications
- **[MARKET_REGIME_SETUP_CONFIGURATION.md](Documentation/MARKET_REGIME_SETUP_CONFIGURATION.md)** - Installation, configuration, and deployment guide

### 3. Key Features
- **Real-time Market Regime Detection** - 7 distinct market regimes with ML-powered classification
- **Macro/Micro Analysis** - Index-based (SMA20) vs Pattern-based regime views
- **Regime Smoothing** - Prevents frequent regime changes with persistence requirements
- **Multi-Dashboard System** - Three specialized dashboards for different use cases
- **Position Recommendations** - Dynamic position sizing based on market conditions

## Component Documentation

### 1. Trading Components
- **[SCANNER_DOCUMENTATION.md](SCANNER_DOCUMENTATION.md)** - Scanner system documentation
- **[Daily/DASHBOARD_HOSTING_GUIDE.md](Daily/DASHBOARD_HOSTING_GUIDE.md)** - Dashboard hosting setup
- **[Daily/DASHBOARD_QUICK_REFERENCE.md](Daily/DASHBOARD_QUICK_REFERENCE.md)** - Dashboard usage guide
- **[Daily/DASHBOARD_STARTUP_GUIDE.md](Daily/DASHBOARD_STARTUP_GUIDE.md)** - Dashboard startup procedures

### 2. Analysis & Patterns
- **[Daily/G_PATTERN_MASTER_GUIDE.md](Daily/G_PATTERN_MASTER_GUIDE.md)** - G Pattern analysis system
- **[Daily/INDIA_TS_JOBS_DOCUMENTATION.md](Daily/INDIA_TS_JOBS_DOCUMENTATION.md)** - Scheduled jobs documentation

### 3. Technical Diagrams
- **[Diagrams/system_overview.md](Diagrams/system_overview.md)** - System architecture overview
- **[Diagrams/scan_market_flow.md](Diagrams/scan_market_flow.md)** - Market scanning workflow
- **[Diagrams/place_orders_flow.md](Diagrams/place_orders_flow.md)** - Order placement process
- **[Diagrams/position_watchdog_flow.md](Diagrams/position_watchdog_flow.md)** - Position monitoring system

## Operational Guides

### 1. Daily Operations
- **[Daily/DASHBOARD_JOBS_UPDATE.md](Daily/DASHBOARD_JOBS_UPDATE.md)** - Job management procedures
- **[Daily/portfolio/REGIME_STOP_LOSS_GUIDE.md](Daily/portfolio/REGIME_STOP_LOSS_GUIDE.md)** - Regime-based stop loss management
- **[Daily/bin/SL_WATCHDOG_MANAGEMENT.md](Daily/bin/SL_WATCHDOG_MANAGEMENT.md)** - Stop loss watchdog operations

### 2. Trading Guides
- **[Daily/trading/G_PATTERN_AUTO_TRADER_GUIDE.md](Daily/trading/G_PATTERN_AUTO_TRADER_GUIDE.md)** - Automated G Pattern trading
- **[Daily/trading/COLORAMA_FIX_SUMMARY.md](Daily/trading/COLORAMA_FIX_SUMMARY.md)** - Display formatting fixes

### 3. Backup & Recovery
- **[BACKUP_GUIDE.md](BACKUP_GUIDE.md)** - System backup procedures
- **[MARKET_REGIME_MIGRATION_PLAN.md](MARKET_REGIME_MIGRATION_PLAN.md)** - Module migration documentation

## Dashboard System

### 1. Market Regime Dashboards
- **Static Dashboard (Port 5001)** - HTML-based regime display
- **Enhanced Dashboard (Port 8080)** - Real-time Flask application with APIs
- **Health Dashboard (Port 7080)** - System monitoring and health checks

### 2. Dashboard Features
- **Macro vs Micro View** - Divergence detection between index and pattern analysis
- **Real-time Updates** - 30-second refresh cycles with live data
- **Position Recommendations** - Dynamic sizing based on regime and volatility
- **Performance Monitoring** - ML model accuracy and system health metrics

## API Reference

### 1. Market Regime APIs
```
GET /api/current_analysis    - Current regime analysis
GET /api/health             - System health status
GET /api/g_pattern_data     - G Pattern analysis
GET /api/early_bird         - KC breakout opportunities
GET /api/reversal_patterns  - Top reversal patterns
```

### 2. Data Formats
- **JSON Reports** - Structured regime analysis data
- **Excel Integration** - Scanner result processing
- **SQLite Storage** - ML training and performance data

## Quick Navigation

### For Developers
1. Start with [INDIA_TS_3.0_OVERVIEW.md](Documentation/INDIA_TS_3.0_OVERVIEW.md)
2. Review [MARKET_REGIME_MODULE_DOCUMENTATION.md](Documentation/MARKET_REGIME_MODULE_DOCUMENTATION.md)
3. Check [MARKET_REGIME_ARCHITECTURE_DIAGRAMS.md](Documentation/MARKET_REGIME_ARCHITECTURE_DIAGRAMS.md)
4. Follow [MARKET_REGIME_SETUP_CONFIGURATION.md](Documentation/MARKET_REGIME_SETUP_CONFIGURATION.md)

### For Operations
1. Start with [DASHBOARD_STARTUP_GUIDE.md](Daily/DASHBOARD_STARTUP_GUIDE.md)
2. Review [MARKET_REGIME_SETUP_CONFIGURATION.md](Documentation/MARKET_REGIME_SETUP_CONFIGURATION.md)
3. Check [DASHBOARD_HOSTING_GUIDE.md](Daily/DASHBOARD_HOSTING_GUIDE.md)
4. Monitor with Health Dashboard (Port 7080)

### For Traders
1. Start with [DASHBOARD_QUICK_REFERENCE.md](Daily/DASHBOARD_QUICK_REFERENCE.md)
2. Access Enhanced Dashboard (Port 8080) for real-time analysis
3. Review [G_PATTERN_MASTER_GUIDE.md](Daily/G_PATTERN_MASTER_GUIDE.md)
4. Check [REGIME_STOP_LOSS_GUIDE.md](Daily/portfolio/REGIME_STOP_LOSS_GUIDE.md)

## Recent Additions (July 2025)

### Market Regime Module
- Complete regime analysis system with ML integration
- Macro/Micro view divergence detection
- Real-time dashboard system with multiple interfaces
- Comprehensive API documentation
- Full setup and configuration guides

### Enhanced Features
- Regime smoothing to prevent frequent changes
- Index SMA20 analysis for macro market view
- Position sizing recommendations based on regime
- Health monitoring and alerting system
- Performance tracking and optimization

## File Organization

```
India-TS/
├── Documentation/                    # Main documentation folder
│   ├── MARKET_REGIME_*.md           # Market Regime module docs
│   ├── INDIA_TS_3.0_*.md           # Core system docs
│   └── *.md                        # Other documentation
├── Daily/                          # Daily trading system
│   ├── Market_Regime/              # Market regime analysis module
│   ├── *.md                        # Daily system documentation
│   └── */                          # Component directories
├── Diagrams/                       # Technical diagrams
├── ML-Framework/                   # Machine learning components
├── BT/                            # Backtesting system
└── *.md                           # Root level documentation
```

## Getting Help

### Documentation Issues
- Check the specific module documentation first
- Review setup guides for configuration issues
- Check diagram files for architectural understanding

### System Issues
- Use Health Dashboard (Port 7080) for system status
- Check log files in respective component directories
- Review troubleshooting sections in setup guides

### Development
- Follow the git workflow in [GIT_WORKFLOW_GOLDEN_VERSION.md](Documentation/GIT_WORKFLOW_GOLDEN_VERSION.md)
- Use [CLAUDE.md](CLAUDE.md) for build and test commands
- Reference architecture diagrams for system understanding

---

*Complete Documentation Index for India-TS Trading System v3.0*  
*Last updated: July 14, 2025*  
*Market Regime Module: Fully documented and integrated*