#!/bin/bash
# India-TS System Backup Script
# Creates a comprehensive backup of the India-TS trading system

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set backup destination
BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/Users/maverick/PycharmProjects/India-TS/backups/backup_${BACKUP_DATE}"
PROJECT_ROOT="/Users/maverick/PycharmProjects/India-TS"

echo -e "${GREEN}Starting India-TS System Backup...${NC}"
echo "Backup Date: ${BACKUP_DATE}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Create subdirectories for organized backup
mkdir -p "${BACKUP_DIR}/config"
mkdir -p "${BACKUP_DIR}/code"
mkdir -p "${BACKUP_DIR}/data"
mkdir -p "${BACKUP_DIR}/logs"
mkdir -p "${BACKUP_DIR}/launchd"
mkdir -p "${BACKUP_DIR}/documentation"

# 1. Backup Configuration Files
echo -e "\n${YELLOW}1. Backing up configuration files...${NC}"
cp -v "${PROJECT_ROOT}/Daily/config.ini" "${BACKUP_DIR}/config/" 2>/dev/null || echo "  - config.ini not found"
cp -v "${PROJECT_ROOT}/config.json" "${BACKUP_DIR}/config/" 2>/dev/null || echo "  - config.json not found"
cp -v "${PROJECT_ROOT}/Daily/regime_watchdog_config.json" "${BACKUP_DIR}/config/" 2>/dev/null || echo "  - regime_watchdog_config.json not found"
cp -v "${PROJECT_ROOT}/.env" "${BACKUP_DIR}/config/" 2>/dev/null || echo "  - .env not found"

# 2. Backup Code (excluding large data files and virtualenv)
echo -e "\n${YELLOW}2. Backing up code files...${NC}"
rsync -av --progress \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='env' \
    --exclude='*.log' \
    --exclude='*.xlsx' \
    --exclude='*.html' \
    --exclude='*.pdf' \
    --exclude='backups' \
    --exclude='*.db' \
    --exclude='*.pickle' \
    --exclude='*.h5' \
    "${PROJECT_ROOT}/Daily/" "${BACKUP_DIR}/code/Daily/"

rsync -av --progress \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    "${PROJECT_ROOT}/Market_Regime/" "${BACKUP_DIR}/code/Market_Regime/" 2>/dev/null || echo "  - Market_Regime not found"

rsync -av --progress \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    "${PROJECT_ROOT}/BT/" "${BACKUP_DIR}/code/BT/" 2>/dev/null || echo "  - BT not found"

# 3. Backup Critical Data Files (latest only)
echo -e "\n${YELLOW}3. Backing up critical data files...${NC}"

# Trading state
cp -v "${PROJECT_ROOT}/data/trading_state.json" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - trading_state.json not found"
cp -v "${PROJECT_ROOT}/data/trading_state_*.json" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - No user-specific trading states found"

# Market breadth data (latest only)
cp -v "${PROJECT_ROOT}/Daily/Market_Regime/breadth_data/market_breadth_latest.json" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - market_breadth_latest.json not found"

# Sector rotation database
cp -v "${PROJECT_ROOT}/Daily/Market_Regime/sector_rotation.db" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - sector_rotation.db not found"

# Regime learning database
cp -v "${PROJECT_ROOT}/data/regime_learning.db" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - regime_learning.db not found"

# Latest scan results (today only)
TODAY=$(date +"%Y%m%d")
find "${PROJECT_ROOT}/Daily/results" -name "*${TODAY}*.xlsx" -exec cp -v {} "${BACKUP_DIR}/data/" \; 2>/dev/null || echo "  - No scan results from today"

# 4. Backup LaunchAgents
echo -e "\n${YELLOW}4. Backing up LaunchAgent configurations...${NC}"
find ~/Library/LaunchAgents -name "com.india-ts.*.plist" -exec cp -v {} "${BACKUP_DIR}/launchd/" \; 2>/dev/null || echo "  - No India-TS LaunchAgents found"

# 5. Backup Documentation
echo -e "\n${YELLOW}5. Backing up documentation...${NC}"
find "${PROJECT_ROOT}" -name "*.md" -exec cp -v {} "${BACKUP_DIR}/documentation/" \; 2>/dev/null

# 6. Create System Status Report
echo -e "\n${YELLOW}6. Creating system status report...${NC}"
cat > "${BACKUP_DIR}/SYSTEM_STATUS.txt" << EOF
India-TS System Status Report
Generated: $(date)

=== Running Processes ===
$(ps aux | grep -E "India-TS|india-ts" | grep -v grep)

=== Scheduled Jobs ===
$(launchctl list | grep "india-ts")

=== Disk Usage ===
$(du -sh "${PROJECT_ROOT}"/* 2>/dev/null | sort -hr | head -20)

=== Recent Logs ===
$(find "${PROJECT_ROOT}/Daily/logs" -name "*.log" -mtime -1 -exec basename {} \; 2>/dev/null)

=== Database Sizes ===
$(find "${PROJECT_ROOT}" -name "*.db" -exec ls -lh {} \; 2>/dev/null)

=== Today's Activities ===
$(find "${PROJECT_ROOT}/Daily/results" -name "*${TODAY}*.xlsx" -exec basename {} \; 2>/dev/null)
EOF

# 7. Create restore instructions
echo -e "\n${YELLOW}7. Creating restore instructions...${NC}"
cat > "${BACKUP_DIR}/RESTORE_INSTRUCTIONS.md" << 'EOF'
# India-TS System Restore Instructions

## Quick Restore

1. **Stop all services:**
   ```bash
   launchctl list | grep india-ts | awk '{print $3}' | xargs -I {} launchctl stop {}
   ```

2. **Restore code files:**
   ```bash
   cp -r code/* /Users/maverick/PycharmProjects/India-TS/
   ```

3. **Restore configuration:**
   ```bash
   cp config/* /Users/maverick/PycharmProjects/India-TS/Daily/
   ```

4. **Restore LaunchAgents:**
   ```bash
   cp launchd/* ~/Library/LaunchAgents/
   ```

5. **Reload LaunchAgents:**
   ```bash
   for plist in launchd/*.plist; do
     launchctl load ~/Library/LaunchAgents/$(basename "$plist")
   done
   ```

6. **Restart services:**
   ```bash
   launchctl start com.india-ts.market_regime_dashboard
   launchctl start com.india-ts.health_dashboard
   ```

## Selective Restore

- **Config only:** `cp config/config.ini /Users/maverick/PycharmProjects/India-TS/Daily/`
- **Trading state:** `cp data/trading_state*.json /Users/maverick/PycharmProjects/India-TS/data/`
- **Specific scanner:** `cp code/Daily/scanners/[scanner_name].py /Users/maverick/PycharmProjects/India-TS/Daily/scanners/`
EOF

# 8. Compress the backup
echo -e "\n${YELLOW}8. Compressing backup...${NC}"
cd "${PROJECT_ROOT}/backups"
tar -czf "india_ts_backup_${BACKUP_DATE}.tar.gz" "backup_${BACKUP_DATE}"

# Calculate sizes
BACKUP_SIZE=$(du -sh "backup_${BACKUP_DATE}" | cut -f1)
COMPRESSED_SIZE=$(du -sh "india_ts_backup_${BACKUP_DATE}.tar.gz" | cut -f1)

echo -e "\n${GREEN}✅ India-TS Backup Complete!${NC}"
echo "================================"
echo "Backup Location: ${BACKUP_DIR}"
echo "Compressed File: ${PROJECT_ROOT}/backups/india_ts_backup_${BACKUP_DATE}.tar.gz"
echo "Backup Size: ${BACKUP_SIZE}"
echo "Compressed Size: ${COMPRESSED_SIZE}"
echo "================================"

# Cleanup old backups (keep last 5)
echo -e "\n${YELLOW}Cleaning up old backups (keeping last 5)...${NC}"
cd "${PROJECT_ROOT}/backups"
ls -t india_ts_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -I {} rm -v {}

echo -e "\n${GREEN}Backup process completed successfully!${NC}"