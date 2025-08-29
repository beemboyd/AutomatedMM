# Data Collection Guide - New Market Regime System

## Overview
This guide explains how to collect and validate data for the New Market Regime ML System. The system is now fully independent of the old regime predictor and ready for data collection.

## ✅ Current Status (2025-08-28)

### Phase 1 & 2 Completed:
- **Data Ingestor**: Working ✅
- **Feature Builder**: Working with 21 features ✅
- **Regime Labeler**: Working (currently detecting bearish market) ✅
- **Data Pipeline**: Fully automated ✅
- **Validation**: Implemented ✅

### Key Improvements Made Today:
1. **Removed dependency on old regime predictor** - System is now self-contained
2. **Fixed all NoneType errors** - Robust error handling implemented
3. **All 21 features now generated** successfully
4. **Created automated collection pipeline** with validation

## Data Collection Pipeline

### 1. Single Data Collection
Run a single collection cycle to capture current market state:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime
python3 src/pipeline/data_collection_pipeline.py --mode once
```

Output will show:
- Current regime (e.g., "choppy_bearish")
- L/S Ratio (long/short stock ratio)
- Bullish Percent (percentage of bullish signals)
- Confidence level

### 2. Scheduled Collection (During Market Hours)
Run continuous collection every 30 minutes during market hours:
```bash
python3 src/pipeline/data_collection_pipeline.py --mode scheduled --interval 30
```

This will:
- Check if market is open (9:15 AM - 3:30 PM IST, Mon-Fri)
- Collect data every 30 minutes
- Skip collection when market is closed
- Save all data with timestamps

### 3. Validate Collected Data
Check data quality and regime diversity:
```bash
python3 src/pipeline/data_collection_pipeline.py --mode validate
```

Shows:
- Total data points collected
- Regime distribution
- Feature quality metrics
- Date range of collection
- Market breadth statistics

## Current Market Analysis (Aug 28, 2025)

```
Current Market State:
- Regime: Choppy Bearish (70% confidence)
- L/S Ratio: 0.38 (6 long, 16 short stocks)
- Bullish Percent: 27.3%
- Market Score: -0.43 (bearish)
```

This correctly identifies the bearish market conditions based on:
- More short signals than long (16 vs 6)
- Low bullish percentage (< 30%)
- Negative market score

## Data Files Generated

### Raw Data (`data/raw/`)
- `unified_data_YYYYMMDD_HHMMSS.json` - Combined scanner and market data
- `scanner_data_YYYYMMDD_HHMMSS.json` - Scanner results
- `breadth_data_YYYYMMDD_HHMMSS.json` - Market breadth metrics

### Features (`data/features/`)
- `features_vYYYYMMDD_HHMMSS.parquet` - Engineered features
- `features_latest.parquet` - Symlink to most recent features

### Labels (`data/labels/`)
- `labeled_features_vYYYYMMDD_HHMMSS.parquet` - Features with regime labels
- `labeled_features_latest.parquet` - Symlink to most recent labeled data

### Logs (`data/`)
- `collection_log.json` - History of all collection cycles

## Automated Collection Setup

### Option 1: Cron Job (Recommended)
Add to crontab for automatic collection during market hours:
```bash
# Run every 30 minutes from 9:30 AM to 3:30 PM IST on weekdays
*/30 9-15 * * 1-5 cd /Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime && python3 src/pipeline/data_collection_pipeline.py --mode once
```

### Option 2: LaunchAgent (macOS)
Create a plist file for launchd to manage the collection.

### Option 3: Manual Scheduled Run
Keep a terminal open with:
```bash
python3 src/pipeline/data_collection_pipeline.py --mode scheduled
```

## Achieving Regime Diversity

Currently seeing only "choppy_bearish" regime because the market IS bearish today. To achieve diversity:

1. **Collect data over multiple days**: Different market conditions will produce different regimes
2. **Include different time periods**: Morning vs afternoon often show different patterns  
3. **Wait for market transitions**: Bull/bear cycles naturally occur

Expected timeline:
- **Day 1-3**: Collect initial data (may see single regime)
- **Week 1**: Should see 2-3 different regimes
- **Week 2**: Should have 4-5 regime types
- **Week 3+**: Full regime diversity for training

## Features Being Collected (21 total)

### Market Breadth (8)
- long_short_ratio
- bullish_percent
- long_stocks_count
- short_stocks_count
- breadth_thrust
- market_sentiment_score
- breadth_momentum
- active_scanners

### Regime Features (8)
- regime_entropy
- regime_concentration
- bullish_regime_count
- bearish_regime_count
- neutral_regime_count
- market_score_mean
- market_score_std
- market_score_range

### Temporal Features (5)
- hour
- day_of_week
- day_of_month
- month
- minutes_since_open

## Validation Checks

Run validation regularly to ensure data quality:

```bash
python3 src/pipeline/data_collection_pipeline.py --mode validate
```

### Good indicators:
- ✅ Feature quality > 95% (non-null values)
- ✅ Multiple regime types after several days
- ✅ L/S ratio varying between collections
- ✅ No single regime > 60% after 1 week

### Warning signs:
- ⚠️ Single regime > 80% after multiple days
- ⚠️ Features with < 90% quality
- ⚠️ Same L/S ratio repeatedly

## Next Steps

1. **Set up automated collection** (cron or launchd)
2. **Collect data for 5-7 days** minimum
3. **Monitor regime diversity** daily
4. **Proceed to Phase 3** (Model Training) once you have:
   - At least 100 data points
   - Minimum 3 different regime types
   - Good feature quality (>95%)

## Troubleshooting

### "Already processed" errors
```bash
rm -f data/raw/last_ingestion.json
```

### No scanner data found
Check that scanners are running and generating files in:
- `/Users/maverick/PycharmProjects/India-TS/Daily/Detailed_Analysis/`

### Features not generated
Ensure unified data files exist in `data/raw/`

### Single regime persisting
This is normal if market conditions haven't changed. Continue collecting data.

---

*Last Updated: 2025-08-28 13:00 IST*