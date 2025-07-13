#!/bin/bash

# Check Backup Status Script
# Shows current backup status and recent backup history

BACKUP_DIR="/Users/maverick/Backups/India-TS"
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/weekly_backup.log"

echo "=========================================="
echo "India-TS Backup Status Report"
echo "Generated: $(date)"
echo "=========================================="

# Check if backup directory exists
if [ -d "$BACKUP_DIR" ]; then
    echo -e "\n✓ Backup directory exists: $BACKUP_DIR"
else
    echo -e "\n✗ Backup directory not found: $BACKUP_DIR"
    echo "  Please create it or update the backup script configuration"
    exit 1
fi

# Show latest backup
echo -e "\n📦 Latest Backup:"
if [ -L "${BACKUP_DIR}/india-ts-latest.tar.gz" ]; then
    LATEST=$(readlink "${BACKUP_DIR}/india-ts-latest.tar.gz")
    if [ -f "$LATEST" ]; then
        ls -lh "$LATEST"
        echo "  Age: $(( ($(date +%s) - $(stat -f %m "$LATEST")) / 86400 )) days old"
    fi
else
    echo "  No latest backup symlink found"
fi

# List all backups
echo -e "\n📋 All Backups (sorted by date):"
echo "SIZE     DATE       TIME     FILENAME"
echo "----     ----       ----     --------"
ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | grep -v "latest" | head -10 | while read perms links owner group size month day time filename; do
    printf "%-8s %-10s %-8s %s\n" "$size" "$month $day" "$time" "$(basename "$filename")"
done

# Check disk usage
echo -e "\n💾 Disk Usage:"
if [ -d "$BACKUP_DIR" ]; then
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "india-ts-backup-*.tar.gz" -type f 2>/dev/null | wc -l | tr -d ' ')
    CRITICAL_COUNT=$(find "$BACKUP_DIR" -name "india-ts-critical-*.tar.gz" -type f 2>/dev/null | wc -l | tr -d ' ')
    
    echo "  Total backup size: $TOTAL_SIZE"
    echo "  Full backups: $BACKUP_COUNT"
    echo "  Critical backups: $CRITICAL_COUNT"
fi

# Check LaunchAgent status
echo -e "\n🔧 Scheduler Status:"
if launchctl list | grep -q "com.india-ts.weekly_backup"; then
    echo "  ✓ Weekly backup scheduler is loaded"
    PLIST_INFO=$(launchctl list | grep "com.india-ts.weekly_backup")
    echo "  Status: $PLIST_INFO"
else
    echo "  ✗ Weekly backup scheduler is NOT loaded"
    echo "  To enable: launchctl load ~/Library/LaunchAgents/com.india-ts.weekly_backup.plist"
fi

# Show recent log entries
echo -e "\n📄 Recent Backup Log (last 10 entries):"
if [ -f "$LOG_FILE" ]; then
    tail -10 "$LOG_FILE" | sed 's/^/  /'
else
    echo "  No log file found at: $LOG_FILE"
fi

# Check for errors
echo -e "\n⚠️  Recent Errors:"
ERROR_LOG="/Users/maverick/PycharmProjects/India-TS/Daily/logs/weekly_backup_error.log"
if [ -f "$ERROR_LOG" ] && [ -s "$ERROR_LOG" ]; then
    echo "  Last 5 error entries:"
    tail -5 "$ERROR_LOG" | sed 's/^/  /'
else
    echo "  No recent errors found"
fi

# Recommendations
echo -e "\n💡 Recommendations:"

# Check if latest backup is too old
if [ -L "${BACKUP_DIR}/india-ts-latest.tar.gz" ]; then
    LATEST=$(readlink "${BACKUP_DIR}/india-ts-latest.tar.gz")
    if [ -f "$LATEST" ]; then
        AGE_DAYS=$(( ($(date +%s) - $(stat -f %m "$LATEST")) / 86400 ))
        if [ $AGE_DAYS -gt 7 ]; then
            echo "  ⚠️  Latest backup is $AGE_DAYS days old. Consider running a manual backup."
        else
            echo "  ✓ Latest backup is recent ($AGE_DAYS days old)"
        fi
    fi
fi

# Check disk space
AVAILABLE_SPACE=$(df -h "$BACKUP_DIR" | tail -1 | awk '{print $4}')
echo "  💾 Available disk space: $AVAILABLE_SPACE"

echo -e "\n=========================================="