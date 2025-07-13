# Brooks Analysis Every 30 Minutes with Google Drive

This setup runs the Al Brooks Higher Probability Reversal analysis every 30 minutes during market hours. Results are saved directly to the synced folders for automatic Google Drive upload.

## Features

- Runs Brooks analysis every 30 minutes during market hours (9:30 AM - 4:00 PM)
- Works with existing Google Drive File Stream sync
- Excel files saved to: `/Users/maverick/PycharmProjects/India-TS/Daily/results/`
- HTML files saved to: `/Users/maverick/PycharmProjects/India-TS/Daily/Detailed_Analysis/`
- Google Drive automatically syncs both directories

## Prerequisites

- Google Drive File Stream installed and running
- The folder `/Users/maverick/PycharmProjects/India-TS/Daily/results` is already syncing to Google Drive

## Setup Instructions

### 1. Initial Setup

```bash
# Make the script executable
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/scripts/hourly_brooks_gdrive.py

# Test run
python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/hourly_brooks_gdrive.py --once
```

### 2. Enable Hourly Schedule

```bash
# Copy plist to LaunchAgents
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.hourly_brooks_analysis.plist ~/Library/LaunchAgents/

# Load the schedule
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist

# Verify it's loaded
launchctl list | grep hourly_brooks
```

## Accessing Results

### File Locations:
- **Excel files**: `Daily/results/Brooks_Higher_Probability_LONG_Reversal_*.xlsx`
- **HTML files**: `Daily/Detailed_Analysis/Higher_Probability_LONG_Analysis_*.html`

### Sharing on Google Drive:
1. Open Google Drive in your browser
2. Navigate to the `Daily/results/` or `Daily/Detailed_Analysis/` folder
3. Right-click on any file
4. Select "Share" → "Get link"
5. Choose "Anyone with the link can view"
6. Copy and share the link

## File Naming Convention

- **Excel files**: `Brooks_Higher_Probability_LONG_Reversal_DD_MM_YYYY_HH_MM.xlsx`
- **HTML files**: `Higher_Probability_LONG_Analysis_DD_MM_YYYY_HH-MM.html`

Files are timestamped with the analysis run time for easy identification.

## Management Commands

```bash
# Check if running
launchctl list | grep hourly_brooks

# Stop the schedule
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist

# Restart the schedule
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist

# View logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_brooks.log

# Manual run
python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/hourly_brooks_gdrive.py --once
```

## Customization

### Change Schedule Timing
Edit the plist file to modify the hours when the analysis runs.

### File Management
Files are saved with timestamps. You can manually manage old files in the results and Detailed_Analysis folders as needed.

## Troubleshooting

1. **Permission Errors**: Make sure Python has full disk access in System Preferences
2. **Cloud Sync Issues**: Ensure cloud service desktop app is running and synced
3. **No Output**: Check logs at `/Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_brooks.log`

## Notes

- The analysis runs every 30 minutes: at :00 and :30 past each hour during market hours
- First run at 9:30 AM, last run at 4:00 PM (total of 14 runs per day)
- Final run at 4:00 PM captures end-of-day data
- All generated files are automatically synced to Google Drive
- Files are not automatically cleaned up - manage them manually as needed