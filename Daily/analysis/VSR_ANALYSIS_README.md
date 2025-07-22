# VSR Loss Analysis System

This system analyzes your historical trading losses using Volume Spread Ratio (VSR) patterns and provides actionable insights to minimize future losses.

## Overview

Based on analysis of your actual losses, we found:
- 44% of losses were same-day exits (immediate reversals)
- Most losses occurred on shooting star patterns at KC upper limits
- High VSR entries (>2x average) often led to exhaustion and reversal
- Early exit signals could have saved ~50% of losses

## Components

### 1. VSR Loss Analyzer (`vsr_loss_analyzer.py`)
- Fetches 5-minute historical data from Zerodha
- Calculates Volume Spread Ratio (VSR) for each candle
- Identifies shooting star patterns
- Detects early exit signals

### 2. Loss Pattern Backtest (`loss_pattern_backtest.py`)
- Loads your actual loss trades from transaction files
- Backtests VSR exit strategies on historical data
- Shows potential savings with optimized exits
- Generates detailed backtest reports

### 3. VSR Exit Dashboard (`vsr_exit_dashboard.py`)
- Real-time monitoring dashboard for open positions
- Tracks VSR patterns and alerts on exit signals
- Visual charts showing price and VSR trends
- Actionable alerts for immediate exits

### 4. Run Loss Analysis (`run_loss_analysis.py`)
- Comprehensive analysis of all your losses
- Time-based pattern identification
- Generates actionable recommendations
- Creates summary reports

## Key Concepts

### Volume Spread Ratio (VSR)
```
VSR = Volume / (High - Low)
```
- High VSR + Narrow spread = Strong support/resistance
- High VSR + Wide spread = Distribution/exhaustion
- Declining VSR = Weakening momentum

### Exit Signals
1. **VSR_DETERIORATION**: Current VSR < 50% of entry VSR
2. **THREE_RED_CANDLES**: 3 consecutive red 5-min candles
3. **WEAK_SUPPORT**: Price below entry with declining VSR
4. **SHOOTING_STAR**: Candle with >60% upper shadow

## Usage

### 1. Run Comprehensive Analysis
```bash
python run_loss_analysis.py
```
This will:
- Load your actual loss trades
- Analyze patterns and timing
- Generate recommendations
- Save results to JSON and Excel

### 2. Backtest VSR Strategy
```bash
python loss_pattern_backtest.py
```
This will:
- Load historical losses
- Simulate VSR-based exits
- Show potential savings
- Generate detailed report

### 3. Monitor Live Positions
```bash
python vsr_exit_dashboard.py
```
Then open http://localhost:8050 in your browser

Add positions to monitor and get real-time alerts.

## Key Rules to Implement

### Entry Filters (AVOID these patterns)
- Candles with >60% upper shadow (shooting star)
- VSR > 2x average (exhaustion signal)
- Entries after 2:00 PM (momentum fades)

### Exit Rules (First 30 minutes)
- VSR drops below 50% of entry → EXIT
- 3 consecutive red 5-min candles → EXIT
- Price below entry + declining VSR → EXIT
- High volume reversal candle → EXIT

### Position Management
- Monitor first 30 minutes aggressively
- Trail stop loss after 30 min profitable
- Never let profit turn to loss

## Expected Results

Based on your historical data:
- Could save ~₹292,784 (50% of losses) with VSR exits
- Avoid entries on 30% of losing trades (shooting stars)
- Exit 15-30 minutes earlier on average
- Reduce average loss from -4.5% to -2.2%

## Files Generated

1. `loss_analysis_results.json` - Detailed analysis data
2. `loss_analysis_summary.xlsx` - Excel summary of all losses
3. `vsr_backtest_results.xlsx` - Backtest results with exit signals

## Dependencies

- pandas
- numpy
- plotly
- dash
- kiteconnect (via user_context_manager)

## Next Steps

1. Implement entry filters in your scanner
2. Add VSR calculation to order placement logic
3. Set up automated alerts for exit signals
4. Review analysis weekly and refine rules
5. Track improvement in loss reduction

## Support

For questions or improvements, review the individual script documentation or analyze your specific loss patterns using the provided tools.