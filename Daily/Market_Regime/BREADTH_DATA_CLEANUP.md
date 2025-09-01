# Breadth Data Cleanup Guide

## Problem Description
When the Zerodha access token expires or becomes invalid, the hourly breadth collector may save incorrect data with 100% values for SMA20, SMA50, and volume breadth. This causes the Market Regime dashboard to display misleading information.

## Prevention (Automatic)
The hourly breadth collector (`sma_breadth_hourly_collector.py`) now includes validation that automatically:
- Rejects entries with all 100% values
- Skips data with less than 10 stocks
- Ignores weekend and after-hours data
- Validates data quality before saving

## Detection
Signs of bad breadth data:
1. Dashboard shows 100% for all breadth indicators
2. Unusually low stock count (< 10)
3. Data appearing on weekends or outside market hours
4. All indicators showing perfect 100% simultaneously

## Manual Cleanup Process

### Quick Fix (One Command)
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
./fix_breadth_data.sh
```
This interactive script will:
1. Check data quality from last 24 hours
2. Show what will be cleaned (dry run)
3. Clean bad data after confirmation
4. Restart the dashboard

### Manual Steps

#### 1. Check Recent Data Quality
```bash
python3 breadth_data_validator.py --recent 24
```
This shows bad entries from the last 24 hours.

#### 2. Dry Run (See What Will Be Cleaned)
```bash
python3 breadth_data_validator.py --dry-run
```
Shows what entries would be removed without making changes.

#### 3. Clean All Bad Data
```bash
python3 breadth_data_validator.py
```
Removes all invalid entries and creates backups.

#### 4. Clean Specific File
```bash
python3 breadth_data_validator.py --file hourly_breadth_data/sma_breadth_hourly_latest.json
```

#### 5. Restart Dashboard
```bash
pkill -f "dashboard_enhanced.py"
nohup python3 dashboard_enhanced.py > /dev/null 2>&1 &
```

## Validation Rules
The validator checks for:
- **All 100% Values**: SMA20, SMA50, and volume all at 100%
- **Low Stock Count**: Less than 10 stocks in the data
- **Weekend Data**: Data from Saturday or Sunday
- **After Hours**: Data outside 9:15 AM - 3:30 PM IST
- **Impossible Values**: Breadth percentages > 100% or < 0%

## File Locations
- **Hourly Data**: `hourly_breadth_data/`
- **Historical Data**: `historical_breadth_data/`
- **Latest File**: `hourly_breadth_data/sma_breadth_hourly_latest.json`
- **Backups**: Created with `.backup_YYYYMMDD_HHMMSS` extension

## Automated Cleanup (Optional)
Add to crontab for daily cleanup at 6 AM:
```bash
0 6 * * * cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime && python3 breadth_data_validator.py >> cleanup.log 2>&1
```

## Recovery
If you accidentally clean valid data:
1. Backups are created automatically before cleaning
2. Find backup files: `ls -la */*.backup*`
3. Restore: `cp file.json.backup_YYYYMMDD_HHMMSS file.json`

## Dashboard Verification
After cleanup, verify at http://localhost:8080/:
1. SMA Breadth shows realistic values (not 100%)
2. Historical charts display normal progression
3. No JSON parsing errors in console