# Momentum Historical Analysis System

## Overview
This system downloads and stores historical price data locally, calculates momentum indicators daily, and maintains a comprehensive database for tracking market momentum trends over time.

## Architecture

### 1. Data Storage
- **SQLite Database**: `Daily/Momentum/historical_data/momentum_history.db`
- **Tables**:
  - `price_data`: Stores OHLC data for all tickers
  - `momentum_data`: Stores calculated momentum indicators
  - `daily_summary`: Stores daily aggregated counts and top movers

### 2. Key Components

#### momentum_historical_builder.py
- Downloads historical data from Kite API
- Calculates momentum indicators (EMAs, WM, Slope)
- Stores results in local database
- Handles rate limiting automatically

#### momentum_historical_api.py
- Provides API endpoints for dashboard
- Returns historical trends, ticker data, market breadth
- Calculates market regime based on momentum counts

#### update_momentum_daily.py
- Run daily after market close
- Updates only today's momentum data
- Shows summary and trend

## How to Build Historical Data

### Initial Setup (One-time, takes ~3-4 hours)
```bash
# Build 7 months of historical data
python Daily/scripts/momentum_historical_builder.py --months 7
```

### Daily Updates (Run after 4 PM IST)
```bash
# Update today's momentum
python Daily/scripts/update_momentum_daily.py
```

## Dashboard Integration

Add these routes to your main dashboard:

```python
# In Daily/Market_Regime/dashboard_enhanced.py
from dashboards.momentum_historical_api import (
    get_momentum_historical_trend,
    get_momentum_ticker_history,
    get_momentum_top_movers,
    get_momentum_breadth_history
)

# Add routes
@app.route('/api/momentum_historical')
def momentum_historical():
    return get_momentum_historical_trend()

@app.route('/api/momentum_ticker/<ticker>')
def momentum_ticker(ticker):
    return get_momentum_ticker_history(ticker)

@app.route('/api/momentum_breadth')
def momentum_breadth():
    return get_momentum_breadth_history()
```

## Market Regime Interpretation

Based on momentum counts:
- **>100 stocks**: Strong Bullish (16%+ of market)
- **70-100 stocks**: Bullish (11-16% of market)
- **40-70 stocks**: Neutral (7-11% of market)
- **20-40 stocks**: Bearish (3-7% of market)
- **<20 stocks**: Strong Bearish (<3% of market)

## Benefits

1. **No API calls for historical analysis**: All data stored locally
2. **Fast dashboard updates**: Query local database instead of API
3. **Trend analysis**: Track momentum changes over months
4. **Market breadth insights**: See percentage of stocks in momentum
5. **Pattern recognition**: Identify market regime changes early

## Automation

Create a plist to run daily updates:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.momentum_daily_update</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/maverick/PycharmProjects/India-TS/Daily/scripts/update_momentum_daily.py</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
</dict>
</plist>
```

## Data Analysis Examples

### Get momentum trend for specific date range
```sql
SELECT date, daily_count 
FROM daily_summary 
WHERE date BETWEEN '2025-01-01' AND '2025-08-01'
ORDER BY date;
```

### Find stocks consistently in momentum
```sql
SELECT ticker, COUNT(*) as days_in_momentum
FROM momentum_data
WHERE meets_criteria = 1
GROUP BY ticker
HAVING COUNT(*) > 100
ORDER BY days_in_momentum DESC;
```

### Analyze WCross patterns
```sql
SELECT date, 
       SUM(CASE WHEN wcross = 'Yes' THEN 1 ELSE 0 END) as wcross_count,
       COUNT(*) as total_momentum
FROM momentum_data
WHERE meets_criteria = 1
GROUP BY date
ORDER BY date DESC;
```