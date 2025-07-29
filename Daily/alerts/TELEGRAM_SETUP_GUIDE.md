# VSR Telegram Alert Setup Guide

This guide explains how to set up and use the VSR Telegram Alert Service with the ZTTrending bot.

## Overview

The VSR Telegram Alert Service monitors the VSR tracker for high momentum tickers and sends real-time alerts via Telegram. It integrates with the existing VSR tracker service to provide instant notifications when significant momentum is detected.

## Features

- **Real-time Alerts**: Get instant notifications for high momentum tickers
- **Configurable Thresholds**: Set your own momentum and score thresholds
- **Batch Alerts**: Option to group alerts to reduce notification spam
- **Daily Summary**: Receive end-of-day summary with top gainers
- **Cooldown Period**: Prevents duplicate alerts for the same ticker
- **Market Hours Only**: Alerts only during market hours (9:15 AM - 3:30 PM IST)

## Setup Instructions

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "ZTTrending Alert Bot")
4. Choose a username (must end with 'bot', e.g., "ZTTrendingBot")
5. Save the bot token provided by BotFather

### 2. Get Your Chat ID

1. Start a chat with your new bot
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your chat ID in the response (look for `"chat":{"id":YOUR_CHAT_ID}`)

### 3. Configure Environment Variables

Add these to your `.bashrc` or `.zshrc`:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### 4. Test the Connection

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Alerts
python3 telegram_notifier.py
```

You should receive a test message in Telegram.

## Running the Service

### Basic Usage

Start with default settings (momentum threshold: 10%, score threshold: 60):
```bash
python3 vsr_telegram_service.py
```

### Custom Thresholds

Set custom momentum and score thresholds:
```bash
python3 vsr_telegram_service.py --momentum-threshold 15 --score-threshold 70
```

### Batch Alerts Mode

Send grouped alerts every 5 minutes instead of individual alerts:
```bash
python3 vsr_telegram_service.py --batch
```

### All Options

```bash
python3 vsr_telegram_service.py --help

Options:
  --user USER               User name for tracking (default: Sai)
  --momentum-threshold M    Minimum momentum % for alerts (default: 10.0)
  --score-threshold S       Minimum score for alerts (default: 60)
  --batch                   Send batch alerts instead of individual
  --interval SECONDS        Tracking interval in seconds (default: 60)
```

## Alert Types

### 1. High Momentum Alert
Triggered when:
- Score ≥ 60 AND Momentum ≥ 10%
- OR Score ≥ 80 (strong signal)
- OR Score ≥ 70 with building indicator

Example:
```
🔥 HIGH MOMENTUM ALERT 🔥

Ticker: RELIANCE
Score: 85/100 🏗️
VSR: 2.45
Price: ₹2,450.50
Momentum: 12.5% 🚀
Volume: 15,234,567
Sector: Oil & Gas
Days Tracked: 2

Alert from ZTTrending at 10:30 IST
```

### 2. Batch Alert
When using `--batch` mode, alerts are grouped:
```
📊 MOMENTUM BATCH UPDATE 📊

Found 5 high momentum tickers:

1. RELIANCE - Score: 85 | Momentum: 12.5% 🚀
2. TCS - Score: 78 | Momentum: 10.2% ⬆️
3. HDFC - Score: 72 | Momentum: 11.0% ⬆️
...
```

### 3. Daily Summary
Sent at 4:00 PM IST:
```
📈 DAILY VSR SUMMARY 📈

Date: 2025-07-29
Total Tracked: 45
High Momentum Alerts: 12

Top Gainers:
1. RELIANCE - 12.5%
2. TCS - 10.2%
...
```

## Creating a Service (Auto-start)

### 1. Create a plist file

Create `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.vsr_telegram_alerts.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.vsr_telegram_alerts</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/maverick/PycharmProjects/India-TS/Daily/Alerts/vsr_telegram_service.py</string>
        <string>--momentum-threshold</string>
        <string>10</string>
        <string>--score-threshold</string>
        <string>60</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>your_bot_token_here</string>
        <key>TELEGRAM_CHAT_ID</key>
        <string>your_chat_id_here</string>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_telegram.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_telegram_error.log</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>15</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily</string>
</dict>
</plist>
```

### 2. Install the service

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
python scheduler/install_plists.py
```

## Monitoring

### Check Logs
```bash
# Service logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_tracker_enhanced_*.log

# Telegram specific logs (if using service)
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_telegram.log
```

### Check Service Status
```bash
launchctl list | grep vsr_telegram
```

## Troubleshooting

### No Alerts Received
1. Check if bot token and chat ID are correct
2. Verify market hours (9:15 AM - 3:30 PM IST)
3. Check momentum thresholds - may be too high
4. Look for errors in logs

### Too Many Alerts
1. Increase momentum threshold (e.g., 15% or 20%)
2. Increase score threshold (e.g., 70 or 80)
3. Use batch mode with `--batch` flag

### Bot Not Responding
1. Ensure you've started a chat with the bot
2. Send `/start` to the bot
3. Check bot token is correct
4. Verify internet connectivity

## Best Practices

1. **Start Conservative**: Begin with higher thresholds and lower as needed
2. **Use Batch Mode**: For less frequent but comprehensive updates
3. **Monitor Quality**: Track which alerts lead to profitable trades
4. **Adjust Thresholds**: Fine-tune based on market conditions
5. **Review Daily Summary**: Use end-of-day summary for analysis

## Security Notes

- Never commit bot tokens to git
- Use environment variables for sensitive data
- Keep chat ID private
- Regularly rotate bot tokens if needed

## Support

For issues or questions:
1. Check the logs first
2. Verify configuration
3. Test with lower thresholds
4. Ensure VSR tracker is working properly