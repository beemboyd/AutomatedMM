# India TS 3.0 - Comprehensive System Documentation

**Version**: 3.0  
**Release Date**: June 25, 2025  
**Last Updated**: July 2, 2025 (Dashboard Architecture Update)  
**Architecture**: Multi-user, AI-powered automated trading system with adaptive market regime detection

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Features](#core-features)
3. [Architecture Diagrams](#architecture-diagrams)
4. [Component Details](#component-details)
5. [Data Flow](#data-flow)
6. [Configuration Guide](#configuration-guide)
7. [Deployment and Operations](#deployment-and-operations)

## System Overview

India TS 3.0 represents a major evolution in automated trading systems, featuring:

- **Multi-user Architecture**: Seamless support for multiple traders with isolated contexts
- **AI-Powered Market Regime Detection**: Machine learning-based market condition analysis
- **Adaptive Risk Management**: Dynamic position sizing based on market conditions
- **Comprehensive Automation**: From signal generation to order execution and portfolio management
- **Real-time Learning**: Continuous model improvement through outcome tracking

### Key Innovations in Version 3.0

1. **Unified State Management**: Single source of truth for all trading states
2. **Smart Scanner Scheduling**: Optimized job scheduling to prevent resource conflicts
3. **Enhanced Market Regime Learning**: 30-minute prediction cycles with outcome verification
4. **Double Scanning Prevention**: Efficient resource utilization through shared scanner results
5. **Advanced Portfolio Management**: ATR-based trailing stops with volatility adjustments

## Core Features

### 1. Signal Generation System

#### Reversal Pattern Scanners
- **Long Reversal Daily Scanner**: Detects bullish reversal patterns
- **Short Reversal Daily Scanner**: Detects bearish reversal patterns
- **Scoring System**: 7-point criteria for high-probability trades

#### Brooks Pattern Recognition
- **Higher Probability Reversals**: Advanced Al Brooks methodology
- **Inside Bar Patterns**: Consolidation breakout detection
- **VWAP/SMA Crossovers**: Trend confirmation signals

### 2. Market Regime Analysis

#### Regime Detection Engine
- **7 Market Regimes**: From strong uptrend to strong downtrend
- **Real-time Classification**: Updates every 30 minutes
- **Breadth Indicators**: Market-wide strength measurement

#### Predictive Learning System
- **ML-based Predictions**: Forecasts next 30-minute regime
- **Outcome Tracking**: Validates predictions for continuous improvement
- **Confidence Scoring**: Adjusts trading parameters based on model confidence

### 3. Order Management

#### Intelligent Order Placement
- **Multi-user Support**: Isolated trading contexts per user
- **Position Limits**: Configurable max positions per user
- **Capital Deployment**: Risk-based position sizing
- **Duplicate Prevention**: Checks existing positions before ordering

### 4. Risk Management

#### Dynamic Stop Loss System
- **ATR-based Calculation**: Volatility-adjusted stop distances
- **True Trailing Stops**: Only move in profit direction
- **Regime Adjustments**: Tighter stops in adverse conditions

#### Portfolio Heat Management
- **Maximum Heat Limit**: 5% portfolio risk cap
- **Position Sizing**: Based on regime confidence
- **Diversification Rules**: Sector and correlation limits

### 5. Portfolio Optimization

#### Daily Portfolio Pruning
- **SMA-based Filtering**: Removes underperforming positions
- **Timing Optimization**: Executes before market close
- **Capital Recycling**: Frees up capital for better opportunities

#### Performance Analytics
- **Real-time P&L Tracking**: Per position and portfolio level
- **Risk Metrics**: Sharpe ratio, max drawdown, win rate
- **Regime Performance**: Track strategy performance by market condition

## Architecture Diagrams

### System Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        India TS 3.0                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   Scanner   │  │   Market    │  │   Trading   │           │
│  │   System    │→ │   Regime    │→ │   System    │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│         ↓                ↓                ↓                    │
│  ┌─────────────────────────────────────────────┐              │
│  │           Unified State Manager              │              │
│  └─────────────────────────────────────────────┘              │
│         ↓                ↓                ↓                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │   User   │    │   User   │    │   User   │               │
│  │ Context  │    │ Context  │    │ Context  │               │
│  │   (Sai)  │    │  (Ravi)  │    │  (Som)   │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Market    │     │  Technical  │     │   Sector    │
│    Data     │────→│ Indicators  │←────│    Data     │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                            ↓
                    ┌─────────────┐
                    │  Scanners   │
                    │  (L/S Rev)  │
                    └─────────────┘
                            │
                    ┌───────┴───────┐
                    ↓               ↓
            ┌─────────────┐ ┌─────────────┐
            │   Results   │ │   Results   │
            │  (*.xlsx)   │ │  (*.json)   │
            └─────────────┘ └─────────────┘
                    │               │
                    └───────┬───────┘
                            ↓
                    ┌─────────────┐
                    │   Market    │
                    │   Regime    │
                    └─────────────┘
                            │
                    ┌───────┴───────┐
                    ↓               ↓
            ┌─────────────┐ ┌─────────────┐
            │   Action    │ │   Order     │
            │    Plan     │ │ Placement   │
            └─────────────┘ └─────────────┘
```

### Market Regime State Machine
```
                    ┌─────────────────┐
                    │ Strong Uptrend  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    Uptrend      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Choppy Bullish  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     Choppy      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Choppy Bearish  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Downtrend     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │Strong Downtrend │
                    └─────────────────┘
```

## Component Details

### Scanner Components

#### Long/Short Reversal Scanners
- **Location**: `Daily/scanners/Long_Reversal_Daily.py`, `Short_Reversal_Daily.py`
- **Schedule**: Every 30 minutes (9:00 AM - 3:30 PM)
- **Output**: Excel files with scored opportunities
- **Key Logic**:
  ```python
  # 7-point scoring system
  1. Resistance/Support break
  2. Confirmation bars (2-3)
  3. Volume expansion
  4. Trend alignment
  5. Momentum indicators
  6. Price action quality
  7. Risk/Reward ratio
  ```

#### Market Regime Analyzer
- **Location**: `Daily/Market_Regime/market_regime_analyzer.py`
- **Schedule**: 10 minutes after each scanner run
- **Dependencies**: Scanner results, market indicators
- **Output**: JSON reports, regime classification

### Trading Components

#### Order Placement System
- **Location**: `Daily/trading/place_orders_daily.py`
- **Multi-user Support**: UserContextManager integration
- **Position Checks**: Prevents duplicate positions
- **Capital Management**: Risk-based position sizing

#### Stop Loss Management
- **Location**: `Daily/portfolio/SL_watchdog.py`
- **ATR Multipliers**:
  - Low volatility: 1.0x ATR
  - Medium volatility: 1.5x ATR
  - High volatility: 2.0x ATR
- **Trailing Logic**: Only adjusts upward for long positions

### Analysis Components

#### Action Plan Generator
- **Location**: `Daily/analysis/Action_plan.py`
- **Tiers**:
  - Tier 1: Appeared 4+ times (1-day), 6+ times (2-day), 9+ times (3-day)
  - Tier 2: Appeared 2-3 times (1-day), 3-5 times (2-day), 5-8 times (3-day)
  - Tier 3: Appeared 1 time across windows
- **ML Integration**: Uses frequency analysis for predictions

## Data Flow

### Primary Data Flow
1. **Market Data** → Fetched via Kite Connect API
2. **Scanners** → Process data, generate signals
3. **Market Regime** → Analyzes scanner output
4. **Action Plan** → Consolidates recommendations
5. **Order Placement** → Executes trades
6. **Position Management** → Monitors and adjusts
7. **State Synchronization** → Updates trading state

### File System Structure
```
India-TS/
├── Daily/
│   ├── scanners/           # Signal generation
│   ├── Market_Regime/      # Regime analysis
│   ├── trading/            # Order execution
│   ├── portfolio/          # Position management
│   ├── analysis/           # Analytics and reporting
│   ├── results/            # Long reversal results
│   ├── results-s/          # Short reversal results
│   ├── Plan/               # Action plans and scores
│   ├── logs/               # System logs
│   └── config.ini          # Configuration
├── Market_Regime/
│   ├── data/               # ML models and data
│   ├── dashboard/          # Web dashboard
│   └── logs/               # Regime logs
└── Documentation/          # System documentation
```

## Configuration Guide

### Essential Configuration (config.ini)

```ini
[DEFAULT]
# User contexts
users = Sai,Prash,Ravi,Som,Mom

# Trading parameters
max_cnc_positions = 10
capital_deployment_percent = 25
product_type = CNC
exchange = NSE

# Risk management
risk_per_trade = 0.01
max_portfolio_heat = 0.05
ticker_cooldown_hours = 2.0

[REGIME]
# Adaptive parameters set by market regime
current_regime = choppy
position_size_multiplier = 0.84
stop_loss_multiplier = 1.0
confidence_threshold = 0.5
```

### User Configuration

Each user requires:
1. API credentials in config.ini
2. User-specific state in trading_state.json
3. Isolated logging context

## Deployment and Operations

### System Requirements
- Python 3.8+
- macOS (for LaunchAgent scheduling)
- Kite Connect API access
- 4GB+ RAM recommended
- SSD storage for performance

### Daily Operations Checklist

1. **Pre-Market (8:30 AM)**
   - [ ] Verify all services running
   - [ ] Check Action Plan generation
   - [ ] Review overnight positions

2. **Market Hours (9:15 AM - 3:30 PM)**
   - [ ] Monitor scanner execution
   - [ ] Verify regime updates
   - [ ] Check order placement
   - [ ] Monitor stop loss adjustments

3. **Post-Market (After 3:30 PM)**
   - [ ] Review daily performance
   - [ ] Check portfolio pruning
   - [ ] Verify state synchronization
   - [ ] Review system logs

### Monitoring Commands

```bash
# Check system status
launchctl list | grep india-ts

# Monitor real-time logs
tail -f ~/PycharmProjects/India-TS/Daily/logs/*.log

# Check market regime
tail -f ~/PycharmProjects/India-TS/Market_Regime/logs/market_regime_analysis.log

# Database queries
sqlite3 ~/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db \
"SELECT COUNT(*) as predictions, 
COUNT(CASE WHEN actual_regime IS NOT NULL THEN 1 END) as resolved 
FROM regime_predictions WHERE date(timestamp) = date('now');"
```

### Troubleshooting Guide

1. **Scanner Failures**
   - Check API connectivity
   - Verify market hours
   - Review error logs

2. **Regime Not Updating**
   - Ensure scanners completed
   - Check file timestamps
   - Verify schedule alignment

3. **Orders Not Placing**
   - Check position limits
   - Verify capital availability
   - Review user context

## Version History

### India TS 3.0 (June 25, 2025)
- Unified state management system
- Enhanced market regime learning with 30-minute cycles
- Optimized job scheduling to prevent conflicts
- Multi-user architecture improvements
- Advanced risk management with regime adaptation

### Previous Versions
- India TS 2.0: Basic automation and scanning
- India TS 1.0: Manual trading with alerts

---

*This documentation reflects India TS 3.0 as of June 25, 2025. For updates and support, contact the development team.*