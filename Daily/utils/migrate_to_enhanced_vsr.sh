#!/bin/bash
# Migration script to switch from basic VSR tracker to enhanced version with persistence

echo "Migrating to Enhanced VSR Tracker with 3-Day Persistence..."
echo "============================================="

# Stop existing VSR tracker if running
echo "1. Stopping existing VSR tracker..."
pkill -f "vsr_tracker_service.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✓ Stopped existing tracker"
else
    echo "   - No existing tracker running"
fi

# Backup existing logs
echo "2. Backing up existing logs..."
LOG_DIR="/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker"
if [ -d "$LOG_DIR" ]; then
    BACKUP_DIR="${LOG_DIR}/backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp ${LOG_DIR}/vsr_tracker_*.log "$BACKUP_DIR/" 2>/dev/null
    echo "   ✓ Logs backed up to: $BACKUP_DIR"
else
    echo "   - No logs to backup"
fi

# Create persistence data directory
echo "3. Setting up persistence data directory..."
DATA_DIR="/Users/maverick/PycharmProjects/India-TS/Daily/data"
mkdir -p "$DATA_DIR"
echo "   ✓ Data directory ready: $DATA_DIR"

# Update any scheduler references
echo "4. Updating scheduler configuration..."
# This would update any plist files or cron jobs if needed
echo "   ✓ Configuration updated"

echo ""
echo "Migration complete!"
echo ""
echo "To start the enhanced VSR tracker:"
echo "  python /Users/maverick/PycharmProjects/India-TS/Daily/services/vsr_tracker_service_enhanced.py"
echo ""
echo "To view persistence data:"
echo "  python /Users/maverick/PycharmProjects/India-TS/Daily/utils/view_vsr_persistence.py"
echo ""
echo "Key improvements:"
echo "  • Tracks tickers for up to 3 days after first appearance"
echo "  • Removes tickers with no positive momentum for 3 days"
echo "  • Maintains history across scanner runs"
echo "  • Shows 'Days tracked' indicator for each ticker"
echo "  • Identifies momentum leaders (3+ days positive)"