# VSR Paper Trading Simulation System

A paper trading system that monitors VSR (Volume Surge Ratio) signals and simulates order entries with intelligent time-based slicing.

## Features

1. **Automated Signal Detection**
   - Monitors VSR tracker output for high-momentum stocks
   - Filters based on VSR threshold (≥3.0) and momentum score (≥75)
   - Tracks any ticker that appears in VSR tracker

2. **Time-Based Order Slicing**
   - T+0 min: 25% (immediate entry)
   - T+3 min: 25% (if momentum continues)
   - T+7 min: 25% (if trend holds)
   - T+15 min: 25% (final slice)

3. **Risk Management**
   - 2% risk per trade
   - Maximum 5 concurrent positions
   - Position sizing based on capital allocation

4. **Real-Time Dashboard** (Port 5005)
   - Active positions with P&L
   - Pending order slices
   - Recent trades
   - Performance metrics

5. **Performance Analytics**
   - Entry timing analysis
   - Slice effectiveness metrics
   - Win rate and profit factor
   - Best/worst trades analysis

## Quick Start

```bash
# Start the paper trading system
./start_paper_trading.sh

# Or run components separately:
# 1. Start dashboard
python3 vsr_paper_dashboard.py

# 2. Start paper trader
python3 vsr_paper_trader.py

# 3. Analyze performance
python3 analyze_performance.py
```

## Configuration

Edit `config/paper_trading_config.json`:

```json
{
    "capital": 1000000,           # Starting capital
    "risk_per_trade": 0.02,       # 2% risk per trade
    "max_positions": 5,           # Max concurrent positions
    "vsr_threshold": 3.0,         # Minimum VSR to enter
    "momentum_threshold": 75,     # Minimum momentum score
    "slice_schedule": {           # Time-based slicing
        "0": 0.25,
        "3": 0.25,
        "7": 0.25,
        "15": 0.25
    }
}
```

## How It Works

1. **Signal Detection**: Reads VSR tracker logs for stocks with:
   - VSR ≥ 3.0 (strong volume surge)
   - Momentum Score ≥ 75
   - No existing position

2. **Order Slicing**: When a signal is detected:
   - Calculates total position size based on risk
   - Places 25% immediately
   - Schedules remaining slices at 3, 7, and 15 minutes
   - Each slice executes if conditions remain favorable

3. **Position Tracking**: 
   - Updates positions with simulated price movements
   - Tracks P&L in real-time
   - Stores all data in SQLite database

## Database Schema

- **trades**: All executed trades with slice information
- **positions**: Current positions with P&L
- **performance**: Daily performance metrics

## Monitoring

Access the dashboard at: http://localhost:5005

## Files

- `vsr_paper_trader.py` - Main paper trading engine
- `vsr_paper_dashboard.py` - Real-time monitoring dashboard
- `analyze_performance.py` - Performance analytics
- `config/paper_trading_config.json` - Configuration
- `data/paper_trades.db` - SQLite database
- `logs/` - System logs

## Next Steps

1. Run paper trading to collect data
2. Analyze entry timing effectiveness
3. Optimize slice schedule based on results
4. Fine-tune VSR and momentum thresholds
5. Add more sophisticated exit strategies