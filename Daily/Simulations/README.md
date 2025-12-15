# VSR Simulation Framework

Paper trading simulation system that mirrors the live Telegram alert signals for backtesting and strategy validation.

## Overview

This framework runs 4 parallel simulations with different configurations:

| Simulation | Port | Direction | Stop Loss Method | Charges | Hold Period |
|------------|------|-----------|------------------|---------|-------------|
| sim_1 | 4001 | LONG | Keltner Channel Lower | 0.15%/leg | Overnight OK |
| sim_2 | 4002 | LONG | PSAR Dynamic | 0.15%/leg | Overnight OK |
| sim_3 | 4003 | SHORT | Keltner Channel Upper | 0.035%/leg | Intraday Only |
| sim_4 | 4004 | SHORT | PSAR Dynamic | 0.035%/leg | Intraday Only |

## Signal Sources

The simulations read from the **exact same data sources** as the Telegram alerts:

### Long Signals
- **Source**: `/Daily/results-h/Long_Reversal_Hourly_*.xlsx`
- **Scanner**: Long Reversal Hourly scan
- **Score Format**: "X/7" (e.g., "5/7" = 71.4%)
- **Minimum Score**: 70% (5/7 conditions)

### Short Signals
- **Source**: `/Daily/FNO/Short/Liquid/Short_Reversal_Daily_*.xlsx`
- **Scanner**: Short Reversal Daily (FNO Liquid)
- **Score Format**: "X/7"
- **Minimum Score**: 70% (5/7 conditions)

## Configuration

### Capital & Position Sizing
- **Initial Capital**: Rs 1,00,00,000 (1 Crore)
- **Position Size**: 5% of portfolio per trade (~Rs 5 Lakh)
- **Max Positions**: 20

### Charges
- **Long trades**: 0.15% per leg (delivery)
- **Short trades**: 0.035% per leg (intraday)

### Stop Loss Methods
1. **Keltner Channel (KC)**
   - EMA Period: 20
   - ATR Period: 10
   - ATR Multiplier: 2.0
   - Long: KC Lower band
   - Short: KC Upper band

2. **Parabolic SAR (PSAR)**
   - Dynamic trailing stop
   - Follows price movement

## Directory Structure

```
Simulations/
├── config/
│   └── simulation_config.json    # Central configuration
├── core/
│   ├── database_manager.py       # SQLite persistence
│   ├── simulation_engine.py      # Core trading logic
│   ├── signal_listener.py        # Signal detection
│   ├── keltner_calculator.py     # KC stop loss
│   ├── psar_calculator.py        # PSAR stop loss
│   └── excel_exporter.py         # Excel reports
├── dashboards/
│   └── simulation_dashboard.py   # Flask web dashboard
├── runners/
│   ├── base_runner.py            # Base simulation runner
│   ├── simulation_1.py           # Long + KC
│   ├── simulation_2.py           # Long + PSAR
│   ├── simulation_3.py           # Short + KC
│   └── simulation_4.py           # Short + PSAR
├── data/                         # SQLite databases
├── logs/                         # Runtime logs
├── results/                      # Excel exports
└── scheduler/
    └── plists/                   # LaunchAgent configs
```

## Running the Simulations

### Start All Dashboards
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Simulations
nohup python3 dashboards/simulation_dashboard.py --sim-id sim_1 --port 4001 &
nohup python3 dashboards/simulation_dashboard.py --sim-id sim_2 --port 4002 &
nohup python3 dashboards/simulation_dashboard.py --sim-id sim_3 --port 4003 &
nohup python3 dashboards/simulation_dashboard.py --sim-id sim_4 --port 4004 &
```

### Start All Simulations
```bash
nohup python3 runners/simulation_1.py > logs/simulation_1.log 2>&1 &
nohup python3 runners/simulation_2.py > logs/simulation_2.log 2>&1 &
nohup python3 runners/simulation_3.py > logs/simulation_3.log 2>&1 &
nohup python3 runners/simulation_4.py > logs/simulation_4.log 2>&1 &
```

### Access Dashboards
- http://localhost:4001 - Long + KC Lower SL
- http://localhost:4002 - Long + PSAR Dynamic SL
- http://localhost:4003 - Short + KC Upper SL
- http://localhost:4004 - Short + PSAR Dynamic SL

## Signal Flow

```
Long_Reversal_Hourly_*.xlsx  ─┬─> sim_1 (Long + KC)
                              └─> sim_2 (Long + PSAR)

Short_Reversal_Daily_*.xlsx  ─┬─> sim_3 (Short + KC)
                              └─> sim_4 (Short + PSAR)
```

## Score Parsing

The Long/Short Reversal scans use a "conditions met" score format:
- "7/7" = 100% (all conditions met)
- "6/7" = 85.7%
- "5/7" = 71.4% (minimum threshold)
- "4/7" = 57.1% (rejected)

## Database Schema

### Trades Table
- trade_id, ticker, direction, entry_time, entry_price
- exit_time, exit_price, quantity, pnl, charges
- stop_loss_type, stop_loss_price, target_price
- vsr_score, signal_pattern, metadata

### Positions Table
- Current open positions with real-time P&L

### Snapshots Table
- Daily portfolio snapshots for performance tracking

## Export Options

Use excel_exporter.py to export results:
```python
from core.excel_exporter import SimulationExporter

exporter = SimulationExporter()
exporter.export_all_simulations()  # Exports all to results/
exporter.export_daily_report()      # Combined daily report
```

## Implementation Notes

1. **Self-Contained**: All simulation code is in the Simulations/ folder. No modifications to external files.

2. **Signal Matching**: Uses exact same data sources as Telegram alerts to ensure simulation matches real signals.

3. **Fresh Start**: Clear databases before restarting:
   ```bash
   rm -f data/*.db logs/*.log
   ```

4. **API Token**: If Kite API token expires, simulations fall back to 5% default stop loss.

## Created
- Date: 2025-12-15
- Author: Claude Code
