# Enhanced VSR Telegram Service Guide

## Overview

The Enhanced VSR Telegram Service provides real-time alerts for both hourly and daily VSR (Volume Spread Ratio) momentum signals. This allows you to catch momentum moves early (hourly) and confirm sustained moves (daily).

## Features

### 1. **Dual Alert System**
- **Hourly Alerts**: Early momentum detection (2%+ momentum, 2x+ VSR ratio)
- **Daily Alerts**: Confirmed high momentum moves (10%+ momentum, 60+ score)

### 2. **Configurable Parameters**
Each alert type can be independently enabled/disabled and configured.

### 3. **Alert Types**

#### Hourly VSR Alerts
- Monitors `results-h/` folder for VSR scan results
- Triggers on VSR ratio ≥ 2.0x and momentum ≥ 2.0%
- Provides early entry signals
- Format:
  ```
  🔥 Hourly VSR SURGE
  🎯 TICKER
  📊 VSR Ratio: 2.5x
  📈 Momentum: 3.2%
  🎯 Pattern: VSR Breakout
  ⏰ Time: 10:30 AM
  ```

#### Daily VSR Alerts
- Monitors live VSR tracker for confirmed moves
- Triggers on score ≥ 60 and momentum ≥ 10%
- Provides high-confidence signals
- Uses existing VSR tracker format

## Configuration

Edit `Daily/config.ini` in the `[TELEGRAM]` section:

```ini
[TELEGRAM]
# Basic Telegram settings
bot_token = YOUR_BOT_TOKEN
chat_id = YOUR_CHAT_ID
enabled = yes

# Daily alert thresholds
high_momentum_threshold = 10.0
min_score_for_alert = 60

# New Hourly/Daily configuration
hourly_telegram_on = yes          # Enable/disable hourly alerts
daily_telegram_on = yes           # Enable/disable daily alerts
hourly_momentum_threshold = 2.0   # Momentum % for hourly alerts
hourly_vsr_threshold = 2.0        # VSR ratio for hourly alerts
```

## Usage

### 1. **Test Configuration**
```bash
python3 Daily/alerts/test_enhanced_telegram.py
```

### 2. **Run Service Manually**
```bash
# Run the service directly (for testing)
python3 Daily/alerts/vsr_telegram_service_enhanced.py --user Sai

# Run with market hours management (9 AM - 3:30 PM IST)
python3 Daily/alerts/vsr_telegram_market_hours_manager.py --user Sai
```

### 3. **Install as Service**
```bash
# Load the plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Start the service (will run from 9 AM to 3:30 PM IST automatically)
launchctl start com.india-ts.vsr-telegram-alerts-enhanced
```

### 4. **Stop Service**
```bash
launchctl stop com.india-ts.vsr-telegram-alerts-enhanced
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
```

### 5. **Service Schedule**
- **Start Time**: 8:55 AM IST (Market Hours Manager starts)
- **Active Hours**: 9:00 AM - 3:30 PM IST (Service runs)
- **Stop Time**: 3:30 PM IST (Service stops automatically)
- **Days**: Monday through Friday only

## Testing Different Market Conditions

### Test 1: Hourly Alerts Only
```ini
hourly_telegram_on = yes
daily_telegram_on = no
```
- Good for catching early moves
- More alerts but earlier entry

### Test 2: Daily Alerts Only
```ini
hourly_telegram_on = no
daily_telegram_on = yes
```
- Fewer alerts but higher confidence
- Better for confirmed momentum

### Test 3: Both Enabled (Default)
```ini
hourly_telegram_on = yes
daily_telegram_on = yes
```
- Get early alerts AND confirmation
- Best for active traders

### Test 4: Adjust Hourly Sensitivity
```ini
hourly_momentum_threshold = 1.5   # More alerts
hourly_vsr_threshold = 1.5        # More sensitive
```

## Alert Frequency Management

The service includes:
- **Duplicate Prevention**: Each ticker alerted only once per timeframe
- **Batch Alerts**: Can group multiple signals (set `batch_alerts = yes`)
- **Rate Limiting**: Prevents Telegram spam

## Monitoring

### Check Logs
```bash
# Main log
tail -f Daily/logs/vsr_telegram/vsr_telegram_enhanced.log

# Error log
tail -f Daily/logs/vsr_telegram/vsr_telegram_enhanced_error.log
```

### Log Indicators
- `✅ Telegram connection successful` - Service started correctly
- `🔥 HIGH MOMENTUM DETECTED` - Alert triggered
- `Processing hourly VSR scan` - Hourly file being analyzed

## Troubleshooting

### No Alerts Received
1. Check `enabled = yes` in config
2. Verify `hourly_telegram_on` or `daily_telegram_on` is `yes`
3. Check bot token and chat ID are correct
4. Review logs for errors

### Too Many Alerts
1. Increase `hourly_momentum_threshold` (e.g., 3.0)
2. Increase `hourly_vsr_threshold` (e.g., 2.5)
3. Enable `batch_alerts = yes`

### Missing Hourly Alerts
1. Ensure VSR scanner is running and creating files in `results-h/`
2. Check file naming pattern matches `VSR_YYYYMMDD_HHMMSS.xlsx`
3. Verify service is running during market hours

## Best Practices

1. **Start Conservative**: Begin with higher thresholds and reduce gradually
2. **Monitor Performance**: Track which timeframe alerts perform better
3. **Market Conditions**: Adjust thresholds based on market volatility
4. **Review Daily**: Check logs to ensure optimal configuration

---
*Last Updated: August 3, 2025*