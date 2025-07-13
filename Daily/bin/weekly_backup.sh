#!/bin/bash

# Weekly Backup Script for India-TS Trading System
# Creates tar.gz snapshots and manages retention

# Configuration
BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
BACKUP_DIR="/Users/maverick/Backups/India-TS"  # Change this to your preferred backup location
RETENTION_WEEKS=4  # Number of weekly backups to retain
LOG_FILE="${BASE_DIR}/Daily/logs/weekly_backup.log"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Start backup process
log_message "=== Starting weekly backup of India-TS ==="

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WEEK_NUMBER=$(date +%Y_W%U)
BACKUP_FILENAME="india-ts-backup-${TIMESTAMP}.tar.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Create exclusion file for tar
EXCLUDE_FILE="/tmp/india-ts-backup-exclude.txt"
cat > "$EXCLUDE_FILE" << 'EOF'
.venv
__pycache__
*.pyc
.DS_Store
*.log
logs/*.log
logs/*/*.log
.git
*.tmp
*.cache
EOF

# Create the backup
log_message "Creating backup: $BACKUP_FILENAME"

cd "$(dirname "$BASE_DIR")" || exit 1

# Create tar archive with progress
tar -czf "$BACKUP_PATH" \
    --exclude-from="$EXCLUDE_FILE" \
    --verbose \
    "$(basename "$BASE_DIR")" 2>&1 | while read line; do
    # Log every 100th file to avoid log bloat
    if [ $((RANDOM % 100)) -eq 0 ]; then
        log_message "Progress: $line"
    fi
done

# Check if backup was successful
if [ -f "$BACKUP_PATH" ]; then
    BACKUP_SIZE=$(ls -lh "$BACKUP_PATH" | awk '{print $5}')
    log_message "Backup created successfully: $BACKUP_FILENAME (Size: $BACKUP_SIZE)"
    
    # Create a symlink to latest backup
    ln -sf "$BACKUP_PATH" "${BACKUP_DIR}/india-ts-latest.tar.gz"
    
    # Also create a copy of critical files separately
    CRITICAL_BACKUP="${BACKUP_DIR}/india-ts-critical-${TIMESTAMP}.tar.gz"
    cd "$BASE_DIR" || exit 1
    tar -czf "$CRITICAL_BACKUP" \
        Daily/config.ini \
        Daily/scanners/*.py \
        Daily/trading/*.py \
        Daily/portfolio/*.py \
        Daily/analysis/*.py \
        Daily/utils/*.py \
        Daily/data/Ticker.xlsx \
        Daily/scheduler/*.plist \
        Daily/Current_Orders \
        Daily/Plan \
        2>/dev/null
    
    if [ -f "$CRITICAL_BACKUP" ]; then
        log_message "Critical files backup created: $(basename "$CRITICAL_BACKUP")"
    fi
else
    log_message "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups (retain only RETENTION_WEEKS)
log_message "Cleaning up old backups (retaining last $RETENTION_WEEKS weeks)..."

# Find and remove old backups
find "$BACKUP_DIR" -name "india-ts-backup-*.tar.gz" -type f -mtime +$((RETENTION_WEEKS * 7)) -exec rm {} \; -exec echo "Removed old backup: {}" \;
find "$BACKUP_DIR" -name "india-ts-critical-*.tar.gz" -type f -mtime +$((RETENTION_WEEKS * 7)) -exec rm {} \; -exec echo "Removed old critical backup: {}" \;

# List current backups
log_message "Current backups in $BACKUP_DIR:"
ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -10 | while read line; do
    log_message "  $line"
done

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log_message "Total backup directory size: $TOTAL_SIZE"

# Optional: Sync to cloud storage (uncomment and configure as needed)
# if command -v rclone &> /dev/null; then
#     log_message "Syncing to cloud storage..."
#     rclone copy "$BACKUP_PATH" "gdrive:India-TS-Backups/" --progress
#     rclone copy "$CRITICAL_BACKUP" "gdrive:India-TS-Backups/critical/" --progress
#     log_message "Cloud sync completed"
# fi

# Optional: Create checksums for integrity verification
CHECKSUM_FILE="${BACKUP_DIR}/checksums-${TIMESTAMP}.txt"
cd "$BACKUP_DIR" || exit 1
shasum -a 256 "$BACKUP_FILENAME" > "$CHECKSUM_FILE"
if [ -f "$(basename "$CRITICAL_BACKUP")" ]; then
    shasum -a 256 "$(basename "$CRITICAL_BACKUP")" >> "$CHECKSUM_FILE"
fi
log_message "Checksums saved to: $(basename "$CHECKSUM_FILE")"

# Clean up
rm -f "$EXCLUDE_FILE"

# Send notification (optional - requires terminal-notifier on macOS)
if command -v terminal-notifier &> /dev/null; then
    terminal-notifier -title "India-TS Backup" \
        -message "Weekly backup completed successfully" \
        -sound default
fi

log_message "=== Weekly backup completed successfully ==="
log_message ""

exit 0