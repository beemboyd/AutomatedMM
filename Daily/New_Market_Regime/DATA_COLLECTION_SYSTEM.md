# Data Collection System Documentation

## Overview
The New Market Regime ML Data Collection System is an automated pipeline that collects, processes, and stores market data for training machine learning models to predict market regimes.

## System Architecture

### Components

1. **Data Ingestor** (`src/ingestion/data_ingestor.py`)
   - Collects scanner results from existing India-TS scanners
   - Aggregates long/short reversal data
   - Calculates market breadth metrics
   - Runs every 5 minutes during market hours

2. **Feature Builder** (`src/features/feature_builder.py`)
   - Generates 21+ market features
   - Calculates technical indicators
   - Creates rolling averages and momentum scores

3. **Feature Store** (`src/features/feature_store.py`)
   - SQLite-based metadata tracking
   - Version control for features
   - Parquet format for efficient storage

4. **Regime Labeler** (`src/features/regime_labeler.py`)
   - Labels data with 7 regime types
   - Calculates confidence scores
   - Adds transition features

## Automation Setup

### LaunchAgent Configuration
- **File**: `com.india-ts.new_market_regime_collector.plist`
- **Schedule**: Every 5 minutes (9:15 AM - 3:30 PM IST, Mon-Fri)
- **Script**: `run_data_collection.sh`
- **Logs**: 
  - Output: `logs/collector_output.log`
  - Errors: `logs/collector_error.log`

### Installation
```bash
# Install LaunchAgent
cp com.india-ts.new_market_regime_collector.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.india-ts.new_market_regime_collector.plist

# Verify installation
launchctl list | grep new_market_regime
```

## Data Collection

### Automated Collection
The system automatically collects data during market hours:
- Checks if market is open (weekdays 9:15 AM - 3:30 PM IST)
- Ingests scanner results
- Builds features
- Labels regimes
- Stores in parquet format

### Historical Backfill
To backfill historical data:
```bash
# Simple backfill (recommended)
python3 simple_backfill.py --days 60

# Full pipeline backfill
python3 backfill_historical_data.py --days 60
```

### Manual Collection
To manually trigger data collection:
```bash
# Single collection
python3 src/pipeline/data_collection_pipeline.py --mode once

# Scheduled collection (runs continuously)
python3 src/pipeline/data_collection_pipeline.py --mode scheduled --interval 30
```

## Data Storage

### Directory Structure
```
data/
├── raw/                 # Raw scanner data (JSON)
├── features/           # Engineered features (Parquet)
│   ├── features_latest.parquet
│   └── feature_metadata.db
├── labels/             # Labeled data (Parquet)
│   └── labeled_features_latest.parquet
└── historical/         # Backfilled historical data
    ├── backfilled_features_*.parquet
    └── backfilled_features_*.csv
```

### Feature Set (19 features)
- **Market Breadth**: long_count, short_count, total_stocks
- **Ratios**: long_short_ratio, bullish_percent, bearish_percent
- **Indicators**: market_breadth, normalized_breadth, volatility_proxy
- **Momentum**: momentum_score, breadth_change, breadth_acceleration
- **Moving Averages**: ma_5_bullish, ma_10_bullish, ma_20_bullish
- **Labels**: regime (bullish/bearish/neutral), trend (5 types)

## Data Quality

### Current Status (as of 2025-09-07)
- **Historical Data**: 39 days (July 10 - Sept 5, 2025)
- **Data Points**: 39 daily aggregations
- **Regime Distribution**:
  - Bearish: 69.2%
  - Neutral: 17.9%
  - Bullish: 12.8%
- **Missing Values**: Minimal (3 in rolling calculations)

### Quality Checks
- Market hours validation
- Weekend/holiday detection
- Schema enforcement
- Outlier detection
- Data completeness validation

## Monitoring

### Job Manager Dashboard
The data collection job is integrated with the India-TS Job Manager Dashboard:
- **Job Name**: New Market Regime ML Data Collector
- **Status**: Can be monitored at http://localhost:9090
- **Controls**: Start/stop/restart via dashboard

### Log Files
Monitor system health via logs:
```bash
# Collection logs
tail -f logs/collector_output.log
tail -f logs/collector_error.log

# Pipeline logs
tail -f logs/data_ingestor.log
tail -f logs/feature_builder.log
tail -f logs/regime_labeler.log
```

## Troubleshooting

### Common Issues

1. **No data collected on weekdays**
   - Check if within market hours (9:15 AM - 3:30 PM IST)
   - Verify scanner files exist in `/Daily/results/`
   - Check logs for errors

2. **LaunchAgent not running**
   ```bash
   # Check status
   launchctl list | grep new_market_regime
   
   # Reload if needed
   launchctl unload ~/Library/LaunchAgents/com.india-ts.new_market_regime_collector.plist
   launchctl load -w ~/Library/LaunchAgents/com.india-ts.new_market_regime_collector.plist
   ```

3. **Import errors**
   - Ensure `__init__.py` files exist in all package directories
   - Check PYTHONPATH includes project directory

4. **Insufficient data for training**
   - Run historical backfill: `python3 simple_backfill.py --days 90`
   - Wait for more data collection (need 100+ samples)

## Next Steps

### Phase 3: Model Training
With data collection automated, Phase 3 can begin:
1. Implement Model Trainer with Random Forest
2. Create Model Evaluator for performance metrics
3. Build Model Registry for version control

### Recommendations
1. Let system collect data for 1-2 more weeks
2. Expand backfill to 90-120 days if possible
3. Start initial model training with current 39-day dataset
4. Implement incremental learning as new data arrives

## Maintenance

### Weekly Tasks
- Check log files for errors
- Verify data collection consistency
- Monitor disk space usage
- Review regime distribution for anomalies

### Monthly Tasks
- Archive old raw data files
- Update feature engineering if needed
- Retrain models with new data
- Generate performance reports

## Contact
For issues or questions, refer to:
- Project location: `/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/`
- Main TODO: `/Users/maverick/PycharmProjects/India-TS/Daily/TODO.md`
- Activity log: `/Users/maverick/PycharmProjects/India-TS/Daily/Activity.md`

---
*Last Updated: 2025-09-07 12:55 IST*