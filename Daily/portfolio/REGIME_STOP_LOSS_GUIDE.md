# Regime-Based Stop Loss System Guide

## Overview

The regime-based stop loss system is an intelligent enhancement to the standard ATR-based stop loss watchdog. It dynamically adjusts stop loss multipliers based on:

- Current market regime (strong_uptrend, uptrend, choppy, downtrend, etc.)
- Regime confidence level
- Market momentum
- Pattern distribution (long vs short reversals)
- Position age
- Volatility conditions

## Key Features

### 1. Market Regime Integration
- Reads live market regime data from the Market Regime Analysis system
- Adapts stop losses based on current market conditions
- Tighter stops in strong trends (to protect profits)
- Wider stops in choppy/uncertain markets

### 2. Multi-Factor Adjustments
- **Confidence Adjustment**: High confidence = tighter stops
- **Momentum Adjustment**: Strong momentum in trend direction = tighter stops
- **Pattern Adjustment**: Clear directional bias = tighter stops
- **Time-Based Adjustment**: Older positions get tighter stops

### 3. Automatic Fallback
- If regime data is unavailable, falls back to standard ATR logic
- No disruption to stop loss monitoring
- Seamless transition between regime and standard modes

## Stop Loss Multiplier Matrix

### Strong Uptrend
- Low Volatility: 0.8x ATR
- Medium Volatility: 1.2x ATR
- High Volatility: 1.8x ATR
- Extreme Volatility: 2.5x ATR

### Uptrend
- Low Volatility: 1.0x ATR
- Medium Volatility: 1.5x ATR
- High Volatility: 2.0x ATR
- Extreme Volatility: 2.8x ATR

### Choppy Markets
- Low Volatility: 1.2-1.5x ATR
- Medium Volatility: 1.8-2.0x ATR
- High Volatility: 2.5-2.8x ATR
- Extreme Volatility: 3.0-3.5x ATR

### Downtrend/Bear Markets
- Low Volatility: 0.5-0.7x ATR
- Medium Volatility: 0.8-1.0x ATR
- High Volatility: 1.2-1.5x ATR
- Extreme Volatility: 1.5-2.0x ATR

## Configuration

Add to `config.ini`:

```ini
[REGIME_STOPS]
enable_regime_stops = true    # Enable/disable regime-based stops
min_multiplier = 0.5         # Minimum allowed multiplier
max_multiplier = 3.0         # Maximum allowed multiplier
confidence_weight = 0.2      # Weight for confidence adjustment
momentum_weight = 0.15       # Weight for momentum adjustment
pattern_weight = 0.15        # Weight for pattern adjustment
```

## Usage

### Option 1: Use the New Regime-Based Watchdog

```bash
# For specific user with all CNC positions
python SL_watchdog_regime.py

# With specific orders file
python SL_watchdog_regime.py orders_file.json
```

### Option 2: Run via Helper Script

```bash
python run_sl_watchdog_regime.py Sai
python run_sl_watchdog_regime.py Sai orders_file.json
```

## Example Scenarios

### Scenario 1: Strong Uptrend with High Confidence
- Market Regime: strong_uptrend (81.6% confidence)
- Stock ATR: 3% (medium volatility)
- Position Age: 5 days
- Result: 2.25x ATR multiplier (instead of standard 1.5x)
- Benefit: Wider stop to ride the trend

### Scenario 2: Choppy Market with Low Confidence
- Market Regime: choppy (45% confidence)
- Stock ATR: 2.5% (medium volatility)
- Position Age: 10 days
- Result: 1.8x ATR multiplier
- Benefit: Wider stop to handle whipsaws

### Scenario 3: Downtrend Warning
- Market Regime: downtrend (75% confidence)
- Stock ATR: 3% (medium volatility)
- Position Age: 2 days
- Result: 0.8x ATR multiplier (instead of 1.5x)
- Benefit: Tighter stop to preserve capital

## Benefits Over Standard ATR Stops

1. **Context-Aware**: Adjusts to market conditions
2. **Dynamic**: Changes with regime transitions
3. **Profit Protection**: Tighter stops in favorable conditions
4. **Risk Management**: Extra caution in bear markets
5. **Time-Based Tightening**: Protects profits as positions mature

## Monitoring and Logs

The system provides detailed logging:
- Shows when regime data is used vs standard logic
- Displays the reasoning for each multiplier
- Tracks all adjustments applied

Example log output:
```
METROPOLIS: Using regime-based multiplier: 2.25x - Regime: strong_uptrend | Vol: extreme | Base: 2.50x | Conf(81.6%): 0.90x | Mom(1.5): 1.00x | Pat(44/12): 1.00x = 2.25x
```

## Testing

Run the test script to verify functionality:
```bash
python test_regime_stop_loss.py
```

## Important Notes

1. **Requires Active Market Regime System**: The Market Regime Analysis must be running and generating data
2. **Graceful Degradation**: Always falls back to standard ATR if regime data is unavailable
3. **No Code Changes Required**: Drop-in replacement for standard SL_watchdog.py
4. **Configuration Control**: Can be disabled via config.ini if needed

## Troubleshooting

### Issue: "No regime data available"
- Check if Market Regime Analysis is running
- Verify latest_regime_summary.json exists
- Check file permissions

### Issue: Stop losses seem too tight/wide
- Adjust multipliers in config.ini
- Check regime confidence levels
- Review position age calculations

### Issue: Want to disable temporarily
- Set `enable_regime_stops = false` in config.ini
- System will use standard ATR logic

## Volume-Price Anomaly Detection (NEW)

Both SL_watchdog.py and SL_watchdog_regime.py now include volume-price anomaly detection:

### Features:
- **Automatic Monitoring**: Checks every 5 minutes for exhaustion patterns
- **Pattern Recognition**: Identifies 4 key volume-price divergences
- **Risk Scoring**: 0-8 scale with clear action levels
- **No Automatic Actions**: Warning-only mode for observation

### Exhaustion Patterns Detected:

1. **Volume Exhaustion (3 points)**
   - Volume > 3x average AND momentum < 5%
   - Indicates heavy distribution/accumulation with limited price movement

2. **Efficiency Breakdown (2 points)**
   - Volume efficiency < 0.5 (momentum/volume ratio)
   - Shows declining effectiveness of volume in moving price

3. **Narrow Range (1 point)**
   - Volume > 2x average AND daily range < 1.5%
   - Suggests resistance/support despite high activity

4. **Price Rejection (2 points)**
   - Volume > 2x average AND close in bottom 30% of range
   - Indicates selling pressure at highs

### Configuration in config.ini:
```ini
[VOLUME_ANOMALY]
anomaly_warning_enabled = true   # Enable/disable warnings
anomaly_check_interval = 300     # Check interval in seconds
```

### Portfolio Summary Enhancement:
The portfolio summary now includes a volume anomaly section:
```
🚨 VOLUME-PRICE ANOMALY ALERTS:
  JAGSNPHARM: HIGH RISK (Score: 5/8) - Volume: 7.5x, Momentum: 4.7%
  ANANDRATHI: MEDIUM RISK (Score: 3/8) - Volume: 6.7x, Momentum: 4.6%
```

## Future Enhancements

1. Individual stock regime analysis
2. Sector-based adjustments
3. Historical performance tracking
4. Machine learning optimization
5. Custom regime definitions
6. Automated stop loss tightening based on anomaly scores