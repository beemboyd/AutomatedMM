# Hourly Breadth Data Automation Plan

## Current Setup
The Market Regime dashboard at http://localhost:8080 now displays:
- **30 days of hourly breadth data** (141 data points)
- **Date range**: July 30, 2025 to August 29, 2025
- **Automatic updates every hour** during market hours

## Automation Components

### 1. Hourly Update Service (ACTIVE)
**Service**: `com.india-ts.hourly-breadth-update`
**Location**: `/Users/maverick/Library/LaunchAgents/com.india-ts.hourly-breadth-update.plist`
**Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/sma_breadth_hourly_collector.py`

**Schedule**: Runs every hour at :30 minutes past the hour
- Monday to Friday: 9:30 AM, 10:30 AM, 11:30 AM, 12:30 PM, 1:30 PM, 2:30 PM, 3:15 PM IST
- Captures market breadth data at regular intervals throughout the trading day

**Purpose**: 
- Collects real-time SMA breadth data (SMA20, SMA50, SMA200)
- Calculates volume participation metrics
- Updates the hourly breadth JSON file
- Maintains a rolling 30-day window of data

### 2. Daily End-of-Day Update
**Service**: `com.india-ts.breadth-update` 
**Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/update_breadth_data_daily.py`
**Schedule**: 6:30 PM IST daily

**Purpose**:
- Comprehensive end-of-day update for both daily and hourly data
- Ensures data completeness
- Archives historical data

### 3. Market Breadth Dashboard
**Service**: `com.india-ts.market-breadth-dashboard`
**Port**: 8080
**Auto-refresh**: Every 60 seconds

**Features**:
- Live display of hourly breadth charts
- Pattern count tracking
- ML regime predictions
- Multi-timeframe analysis

## Data Flow

```
Market Hours (9:30 AM - 3:30 PM)
    ↓
Hourly Collector (every hour at :30)
    ↓
Updates hourly_breadth_data/sma_breadth_hourly_latest.json
    ↓
Dashboard API endpoint serves data
    ↓
Dashboard auto-refreshes charts (every 60 seconds)
```

## Key Files

1. **Data Storage**:
   - `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/hourly_breadth_data/sma_breadth_hourly_latest.json`
   - Contains 30 days of hourly breadth data
   - Updated every hour during market hours

2. **Historical Archive**:
   - `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data/sma_breadth_hourly_latest.json`
   - Daily snapshot for long-term analysis

## Monitoring & Troubleshooting

### Check Service Status
```bash
# Check if hourly update service is running
launchctl list | grep hourly-breadth

# Check logs for errors
tail -f ~/PycharmProjects/India-TS/Daily/Market_Regime/logs/hourly_breadth_update.log
tail -f ~/PycharmProjects/India-TS/Daily/Market_Regime/logs/hourly_breadth_update_error.log
```

### Manual Update
```bash
# Run manual update if needed
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python3 sma_breadth_hourly_collector.py --update
```

### Restart Services
```bash
# Restart hourly update service
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-breadth-update.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-breadth-update.plist

# Restart dashboard
launchctl unload ~/Library/LaunchAgents/com.india-ts.market-breadth-dashboard.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.market-breadth-dashboard.plist
```

## Data Retention Policy

- **Hourly Data**: Maintains rolling 30-day window
- **Daily Data**: Archived indefinitely
- **Older data**: Automatically pruned to maintain performance

## API Endpoints

Dashboard provides these endpoints for hourly data:
- `/api/sma-breadth-hourly` - Returns formatted hourly breadth data
- `/api/regime-summary` - Current regime analysis including hourly metrics

## Future Enhancements

1. **Real-time updates**: Consider WebSocket for live updates instead of 60-second polling
2. **Alert system**: Add threshold-based alerts for significant breadth changes
3. **Data backup**: Implement daily backup to S3 or cloud storage
4. **Performance metrics**: Track update success/failure rates

## Verification

To verify the system is working:
1. Check dashboard at http://localhost:8080
2. Look for "Hourly SMA Breadth Analysis" section
3. Verify chart shows 30 days of data
4. Check timestamp shows recent update (within last hour during market hours)
5. Monitor pattern counts updating throughout the day

## Notes

- All times are in IST (India Standard Time)
- Service uses Zerodha API exclusively (no yfinance dependencies)
- Dashboard auto-refreshes every 60 seconds to show latest data
- Hourly collector handles market holidays automatically