# VSR Anomaly Detection Service

## Overview
The VSR Anomaly Detection Service monitors all your portfolio positions (CNC, MIS, T1) for Volume Spread Ratio (VSR) anomalies and logs detailed information to a running log file that can be monitored in real-time.

## Features
- **Real-time Monitoring**: Checks all positions every minute
- **Multiple Anomaly Types**:
  - Volume Exhaustion: High volume without proportional price movement
  - VSR Divergence: Declining VSR with falling prices
  - Buying/Selling Climax: Extreme VSR with weak closes
  - Momentum Loss: Declining momentum from recent highs
- **Detailed Logging**: Comprehensive log entries with recommendations
- **Position Status Table**: Summary of all positions with VSR metrics
- **Anomaly History**: Tracks anomaly patterns over time

## Setup

No additional setup required. The service uses existing Zerodha API credentials from `config.ini`.

## Usage

### Start the Service
```bash
cd Daily/services
./start_vsr_anomaly.sh

# With custom user
./start_vsr_anomaly.sh -u Sai
```

### Check Status
```bash
./status_vsr_anomaly.sh
```

### Stop the Service
```bash
./stop_vsr_anomaly.sh
```

### View Logs
```bash
tail -f ../logs/vsr_anomaly/vsr_anomaly_$(date +%Y%m%d).log
```

## Anomaly Detection Logic

### 1. Volume Exhaustion
- **Trigger**: VSR > 2.5, Price change < 1%, Volume > 2x average
- **Meaning**: High buying volume but price isn't responding
- **Action**: Consider reducing position

### 2. VSR Divergence
- **Trigger**: VSR drops 30%+ from previous hour, Price drops 1%+
- **Meaning**: Selling pressure increasing
- **Action**: Monitor closely for further weakness

### 3. Buying/Selling Climax
- **Trigger**: VSR > 4.0, Close in lower 30% of hourly range
- **Meaning**: Heavy selling into buying attempts
- **Action**: High risk of reversal

### 4. Momentum Loss
- **Trigger**: VSR < 50% of 5-hour average, Price gain < 2% over 5 hours
- **Meaning**: Momentum fading despite earlier strength
- **Action**: Consider taking profits

## Log Format

The service creates detailed log entries for each anomaly:

```
================================================================================
🚨 ANOMALY DETECTED: RELIANCE
================================================================================
2025-07-17 14:32:15,123 - WARNING - 🔴 [EXHAUSTION] RELIANCE: Volume exhaustion detected! VSR: 3.45, Price change: 0.2%, Volume surge: 2.8x average

📊 VSR METRICS:
  • Current VSR: 3.45 (Previous: 2.81)
  • 5H Average VSR: 2.23 (Max: 3.45)
  • Price Change: 1H: +0.20%, 5H: +1.50%
  • Volume Ratio: 2.80x average
  • Close Position: 25% of range

💼 POSITION DETAILS:
  • Position: 100 shares @ ₹2450.00 | Current: ₹2455.50 (CNC) | P&L: PROFIT ₹550.00
  • Entry Time: 2025-07-17T09:15:00

💡 RECOMMENDATIONS:
  ⚠️ Volume exhaustion detected - Consider reducing position size
================================================================================

📈 CYCLE SUMMARY:
  • Positions checked: 8
  • Anomalies found: 2
  • Duration: 4.5s

📊 POSITION STATUS:
Ticker       |    VSR |   1H Chg% | Anomalies
-------------+--------+----------+------------------------------
RELIANCE     |   3.45 |   +0.20% | EXHAUSTION
TCS          |   2.81 |   +1.15% | None
INFY         |   1.92 |   -0.45% | DIVERGENCE
```

## Configuration

### Log Rotation
- New log file created daily
- Logs stored in: `Daily/logs/vsr_anomaly/`
- Format: `vsr_anomaly_YYYYMMDD.log`

### Anomaly Thresholds
Customize in `vsr_anomaly_detector.py`:
```python
self.anomaly_thresholds = {
    'exhaustion': {
        'vsr_min': 2.5,
        'price_lag_max': 1.0,
        'volume_surge_min': 2.0
    },
    # ... other thresholds
}
```

## Troubleshooting

### Reading Logs in Real-time
1. Use tail to follow the log:
   ```bash
   tail -f ../logs/vsr_anomaly/vsr_anomaly_$(date +%Y%m%d).log
   ```
2. Filter for anomalies only:
   ```bash
   tail -f ../logs/vsr_anomaly/vsr_anomaly_$(date +%Y%m%d).log | grep -E "ANOMALY|WARNING"
   ```
3. Watch specific ticker:
   ```bash
   tail -f ../logs/vsr_anomaly/vsr_anomaly_$(date +%Y%m%d).log | grep "RELIANCE"
   ```

### Service Not Starting
1. Check if already running: `./status_vsr_anomaly.sh`
2. Verify Python path and dependencies
3. Check log file for errors

### No Positions Found
1. Ensure Zerodha access token is valid
2. Check if market is open
3. Verify positions exist in your account

## Performance Impact
- API calls: ~1 per position per minute
- Memory usage: Minimal (~50MB)
- CPU usage: Low (< 5%)

## Future Enhancements
1. Custom anomaly thresholds per ticker
2. Integration with trading decisions
3. Historical anomaly analysis dashboard
4. Export anomaly reports to Excel
5. Email alerts for critical anomalies