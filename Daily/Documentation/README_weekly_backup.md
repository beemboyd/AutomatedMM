# Weekly Backup System for India-TS

This document describes the automated weekly backup system for the India-TS trading platform.

## Overview

The weekly backup system creates compressed tar.gz snapshots of the entire India-TS codebase and data, with intelligent exclusions and retention policies.

## Components

1. **LaunchAgent plist**: `com.india-ts.weekly_backup.plist`
   - Schedules the backup to run every Sunday at 3:00 AM
   - Manages logging and error handling

2. **Backup Script**: `scripts/weekly_backup.sh`
   - Creates full and critical file backups
   - Manages retention (keeps last 4 weeks by default)
   - Generates checksums for integrity verification

## Installation

```bash
# Copy the plist to LaunchAgents
cp scheduler/com.india-ts.weekly_backup.plist ~/Library/LaunchAgents/

# Load the scheduler
launchctl load ~/Library/LaunchAgents/com.india-ts.weekly_backup.plist

# Verify it's loaded
launchctl list | grep india-ts.weekly_backup
```

## Configuration

Edit the backup script to configure:

1. **Backup Location**: 
   ```bash
   BACKUP_DIR="/Users/maverick/Backups/India-TS"  # Change this
   ```

2. **Retention Period**:
   ```bash
   RETENTION_WEEKS=4  # Number of weekly backups to keep
   ```

3. **Cloud Sync** (optional):
   - Uncomment the rclone section in the script
   - Configure rclone with your cloud provider

## Manual Execution

To run a backup manually:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
./scripts/weekly_backup.sh
```

## Backup Contents

### Full Backup Includes:
- All Python scripts
- Configuration files
- Data files (Ticker.xlsx, etc.)
- Current orders and positions
- Plans and reports
- Scheduler configurations

### Excludes:
- Virtual environment (.venv)
- Python cache files
- Git repository data
- Log files
- Temporary files

### Critical Backup Includes:
- config.ini (credentials)
- All scripts (*.py)
- Ticker.xlsx
- Scheduler plists
- Current Orders
- Trading Plans

## Backup Structure

```
/Users/maverick/Backups/India-TS/
├── india-ts-backup-20250609_030000.tar.gz       # Full backup
├── india-ts-critical-20250609_030000.tar.gz     # Critical files only
├── india-ts-latest.tar.gz -> india-ts-backup... # Symlink to latest
└── checksums-20250609_030000.txt                # SHA-256 checksums
```

## Monitoring

Check backup logs:
```bash
tail -f ~/PycharmProjects/India-TS/Daily/logs/weekly_backup.log
tail -f ~/PycharmProjects/India-TS/Daily/logs/weekly_backup_error.log
```

## Restoration

To restore from a backup:

```bash
# Full restoration
cd /path/to/restore/location
tar -xzf /Users/maverick/Backups/India-TS/india-ts-latest.tar.gz

# Critical files only
tar -xzf /Users/maverick/Backups/India-TS/india-ts-critical-TIMESTAMP.tar.gz

# Verify integrity
cd /Users/maverick/Backups/India-TS
shasum -c checksums-TIMESTAMP.txt
```

## Troubleshooting

1. **Backup not running**:
   ```bash
   # Check if scheduled
   launchctl list | grep weekly_backup
   
   # Check logs
   tail -100 ~/PycharmProjects/India-TS/Daily/logs/weekly_backup_error.log
   ```

2. **Disk space issues**:
   - Reduce RETENTION_WEEKS
   - Change backup location to external drive
   - Enable compression level adjustment in tar command

3. **Permission errors**:
   ```bash
   # Fix permissions
   chmod +x ~/PycharmProjects/India-TS/Daily/scripts/weekly_backup.sh
   ```

## Cloud Backup Integration

To enable cloud backups:

1. Install rclone:
   ```bash
   brew install rclone
   ```

2. Configure cloud provider:
   ```bash
   rclone config
   ```

3. Uncomment the rclone section in weekly_backup.sh

4. Test cloud sync:
   ```bash
   rclone ls gdrive:India-TS-Backups/
   ```

## Best Practices

1. **Test Restoration**: Periodically test restoring from backups
2. **Monitor Disk Space**: Ensure adequate space for backups
3. **Verify Checksums**: Regularly verify backup integrity
4. **Off-site Copies**: Keep at least one backup off-site (cloud/external drive)
5. **Document Changes**: Update this README when modifying backup configuration