# Trading Systems Backup Guide

## Overview
This guide provides instructions for backing up both India-TS and US-TS trading systems. Regular backups ensure you can recover from system failures, code issues, or accidental deletions.

## Backup Scripts

### India-TS Backup
**Script Location:** `/Users/maverick/PycharmProjects/India-TS/backup_india_ts.sh`

**Run backup:**
```bash
cd /Users/maverick/PycharmProjects/India-TS
./backup_india_ts.sh
```

### US-TS Backup
**Script Location:** `/Users/maverick/PycharmProjects/India-TS/backup_us_ts.sh`

**Copy to US-TS and run:**
```bash
# Copy script to US-TS folder
cp /Users/maverick/PycharmProjects/India-TS/backup_us_ts.sh /Users/maverick/PycharmProjects/US-TS/

# Run backup
cd /Users/maverick/PycharmProjects/US-TS
./backup_us_ts.sh
```

## What Gets Backed Up

### 1. Configuration Files
- `config.ini` - API credentials and settings
- `config.json` - System configurations
- `.env` - Environment variables
- Watchdog configurations

### 2. Code Files
- All Python scripts (`.py`)
- Scanner scripts
- Dashboard code
- Market Regime analyzers
- Trading strategies
- Utility scripts

### 3. Critical Data
- Trading state JSON files
- Market breadth data (latest)
- Sector rotation database
- Regime learning databases
- Today's scan results

### 4. System Configurations
- LaunchAgent plist files
- Scheduled job configurations

### 5. Documentation
- All Markdown files (`.md`)
- System guides
- API documentation

## What's Excluded
- Python cache files (`__pycache__`, `*.pyc`)
- Large Excel/HTML reports (except today's)
- Log files (except list of recent)
- Virtual environments
- Git repositories
- Temporary files

## Backup Storage

### Location
- India-TS: `/Users/maverick/PycharmProjects/India-TS/backups/`
- US-TS: `/Users/maverick/PycharmProjects/US-TS/backups/`

### Format
- Folder: `backup_YYYYMMDD_HHMMSS/`
- Compressed: `india_ts_backup_YYYYMMDD_HHMMSS.tar.gz`
- Auto-cleanup: Keeps only last 5 backups

## Backup Schedule Recommendations

### Daily Backup
Best after market close:
```bash
# Add to crontab
0 22 * * * /Users/maverick/PycharmProjects/India-TS/backup_india_ts.sh
0 3 * * * /Users/maverick/PycharmProjects/US-TS/backup_us_ts.sh
```

### Before Major Changes
Always backup before:
- System updates
- Code refactoring
- Configuration changes
- Database migrations

## Quick Restore Process

### Full System Restore
1. Stop all services
2. Extract backup: `tar -xzf backup_file.tar.gz`
3. Copy files back to original locations
4. Reload LaunchAgents
5. Restart services

### Selective Restore
- **Just config:** Copy from `backup/config/`
- **Just code:** Copy from `backup/code/`
- **Just data:** Copy from `backup/data/`

## Verification After Backup

### Check Backup Integrity
```bash
# List contents
tar -tzf india_ts_backup_*.tar.gz | head -20

# Verify size
du -sh backups/india_ts_backup_*.tar.gz
```

### Test Restore (Recommended Monthly)
1. Create test directory
2. Extract backup to test location
3. Verify critical files exist
4. Check configuration integrity

## Cloud Backup (Optional)

### Using iCloud
```bash
# Create symbolic link to iCloud
ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/TradingBackups /Users/maverick/TradingBackups

# Copy backups to iCloud
cp backups/*.tar.gz /Users/maverick/TradingBackups/
```

### Using Time Machine
Ensure these folders are included:
- `/Users/maverick/PycharmProjects/India-TS/backups/`
- `/Users/maverick/PycharmProjects/US-TS/backups/`

## Emergency Recovery Checklist

If system fails:

1. **Stop Everything**
   ```bash
   launchctl list | grep -E "india-ts|usts" | awk '{print $3}' | xargs -I {} launchctl stop {}
   ```

2. **Locate Latest Backup**
   ```bash
   ls -la */backups/*.tar.gz | sort -k5 -r | head -5
   ```

3. **Create Recovery Directory**
   ```bash
   mkdir ~/TradingRecovery
   cd ~/TradingRecovery
   ```

4. **Extract Backup**
   ```bash
   tar -xzf /path/to/backup.tar.gz
   ```

5. **Follow Restore Instructions**
   Check `RESTORE_INSTRUCTIONS.md` in backup

## Backup Monitoring

### Check Last Backup
```bash
# India-TS
ls -la /Users/maverick/PycharmProjects/India-TS/backups/ | tail -5

# US-TS  
ls -la /Users/maverick/PycharmProjects/US-TS/backups/ | tail -5
```

### Disk Space Check
```bash
df -h | grep -E "/$|backups"
```

## Important Notes

1. **Test Restores:** Perform test restores quarterly
2. **Offsite Backup:** Keep at least one backup offsite
3. **Document Changes:** Update backup scripts when adding new components
4. **Credentials:** Store API keys/passwords separately and securely
5. **Automation:** Consider automating daily backups with cron

## Troubleshooting

### Backup Script Fails
- Check disk space: `df -h`
- Verify permissions: `ls -la backup_*.sh`
- Check for running processes that might lock files

### Restore Fails
- Ensure services are stopped
- Check file permissions
- Verify backup integrity first

### Missing Files in Backup
- Check exclusion rules in backup script
- Verify source files exist
- Run with verbose flag for debugging

## Support

For backup-related issues:
1. Check system logs
2. Verify backup completion messages
3. Test with small subset first
4. Keep previous backup until new one is verified