# ML Scheduled Service Documentation

## Overview
The ML-Based Strategy Recommendations service has been enhanced to operate with time-aware data management. It uses live market data during trading hours and cached data during off-hours and weekends.

## Schedule Logic

### Market Hours (Monday-Friday, 9:15 AM - 3:30 PM IST)
- Uses live data from `sma_breadth_historical_latest.json`
- Real-time market breadth analysis
- Fresh ML predictions based on current market conditions

### Outside Market Hours
- **Weekends (Saturday & Sunday)**: Uses Friday 3:30 PM cached data
- **Weekdays before 9:15 AM**: Uses previous day's data (Friday cache on Monday morning)
- **Weekdays after 3:30 PM**: Uses current day's latest data

## Components

### 1. ml_dashboard_integration_scheduled.py
Enhanced ML integration with scheduling logic:
- Detects current time and day
- Automatically selects appropriate data source
- Adds metadata to API responses indicating data source

### 2. save_friday_breadth_data.py
Script to cache Friday's closing data:
- Runs automatically every Friday at 3:30 PM IST
- Creates `sma_breadth_friday_cache.json`
- Maintains timestamped backups (keeps last 4 weeks)
- Adds metadata to cached files

### 3. Scheduled Job (plist)
- **Label**: `com.india-ts.save_friday_breadth_data`
- **Schedule**: Every Friday at 15:30 IST
- **Purpose**: Automatically cache Friday's closing data

## API Response Metadata

The `/api/ml_insights` endpoint now includes metadata:

```json
{
  "data_metadata": {
    "is_market_hours": false,
    "data_source": "friday_cache",
    "current_time": "2025-08-03T17:48:05.919865+05:30",
    "using_cached_data": true,
    "cache_warning": "Using Friday 3:30 PM data (market closed)"
  }
}
```

## Manual Operations

### Force Save Friday Data
```bash
python /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/save_friday_breadth_data.py
```

### Check Scheduled Job Status
```bash
launchctl list | grep save_friday_breadth
```

### View Friday Cache
```bash
cat /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data/sma_breadth_friday_cache.json | jq '.metadata'
```

## Testing

### Test During Market Hours (Weekday)
1. Access dashboard during 9:15 AM - 3:30 PM on a weekday
2. Check `/api/ml_insights` - should show `"data_source": "live_data"`

### Test Outside Market Hours
1. Access dashboard on weekend or outside market hours
2. Check `/api/ml_insights` - should show `"data_source": "friday_cache"`

## Benefits

1. **24/7 Availability**: ML insights available anytime
2. **Weekend Planning**: Users can review strategies on weekends using Friday's closing data
3. **Consistency**: Weekend analysis uses end-of-week data, not stale weekend scans
4. **Transparency**: API clearly indicates data source being used
5. **Automatic Management**: No manual intervention needed

## Troubleshooting

### Friday Cache Not Found
- Check if the scheduled job ran: `launchctl list | grep save_friday_breadth`
- Manually run the save script
- Verify file exists in historical_breadth_data directory

### Old Data Being Used
- Check current time vs market hours logic
- Verify Friday cache has recent timestamp
- Check logs at `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/`

### Schedule Not Working
- Ensure plist is loaded: `launchctl load [plist_path]`
- Check error logs for the scheduled job
- Verify system time and timezone settings