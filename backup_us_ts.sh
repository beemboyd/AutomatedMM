#!/bin/bash
# US-TS System Backup Script
# Creates a comprehensive backup of the US-TS trading system
# Note: This script should be copied to US-TS folder and run from there

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set backup destination
BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/Users/maverick/PycharmProjects/US-TS/backups/backup_${BACKUP_DATE}"
PROJECT_ROOT="/Users/maverick/PycharmProjects/US-TS"

echo -e "${GREEN}Starting US-TS System Backup...${NC}"
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
cp -v "${PROJECT_ROOT}/Market_Regime/config.json" "${BACKUP_DIR}/config/market_regime_config.json" 2>/dev/null || echo "  - Market_Regime config.json not found"
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
    --exclude='*.db' \
    "${PROJECT_ROOT}/Market_Regime/" "${BACKUP_DIR}/code/Market_Regime/"

# 3. Backup Critical Data Files (latest only)
echo -e "\n${YELLOW}3. Backing up critical data files...${NC}"

# Trading state
cp -v "${PROJECT_ROOT}/data/trading_state.json" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - trading_state.json not found"

# Market Regime databases
cp -v "${PROJECT_ROOT}/Market_Regime/regime_history.db" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - regime_history.db not found"
cp -v "${PROJECT_ROOT}/Market_Regime/learning/learning_outcomes.db" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - learning_outcomes.db not found"
cp -v "${PROJECT_ROOT}/Market_Regime/predictions.db" "${BACKUP_DIR}/data/" 2>/dev/null || echo "  - predictions.db not found"

# Latest scan results (today only)
TODAY=$(date +"%Y%m%d")
find "${PROJECT_ROOT}/Daily/results" -name "*${TODAY}*.xlsx" -exec cp -v {} "${BACKUP_DIR}/data/" \; 2>/dev/null || echo "  - No scan results from today"

# 4. Backup LaunchAgents
echo -e "\n${YELLOW}4. Backing up LaunchAgent configurations...${NC}"
find ~/Library/LaunchAgents -name "com.usts.*.plist" -exec cp -v {} "${BACKUP_DIR}/launchd/" \; 2>/dev/null || echo "  - No US-TS LaunchAgents found"

# 5. Backup Documentation
echo -e "\n${YELLOW}5. Backing up documentation...${NC}"
find "${PROJECT_ROOT}" -name "*.md" -maxdepth 3 -exec cp -v {} "${BACKUP_DIR}/documentation/" \; 2>/dev/null

# 6. Create System Status Report
echo -e "\n${YELLOW}6. Creating system status report...${NC}"
cat > "${BACKUP_DIR}/SYSTEM_STATUS.txt" << EOF
US-TS System Status Report
Generated: $(date)

=== Running Processes ===
$(ps aux | grep -E "US-TS|usts" | grep -v grep)

=== Scheduled Jobs ===
$(launchctl list | grep "usts")

=== Dashboard URLs ===
Market Regime Dashboard: http://localhost:8090
Health Check Dashboard: http://localhost:7089

=== Disk Usage ===
$(du -sh "${PROJECT_ROOT}"/* 2>/dev/null | sort -hr | head -20)

=== Recent Logs ===
$(find "${PROJECT_ROOT}/Daily/logs" -name "*.log" -mtime -1 -exec basename {} \; 2>/dev/null)
$(find "${PROJECT_ROOT}/Market_Regime/logs" -name "*.log" -mtime -1 -exec basename {} \; 2>/dev/null)

=== Database Sizes ===
$(find "${PROJECT_ROOT}" -name "*.db" -exec ls -lh {} \; 2>/dev/null)

=== Today's Activities ===
$(find "${PROJECT_ROOT}/Daily/results" -name "*${TODAY}*.xlsx" -exec basename {} \; 2>/dev/null)
$(find "${PROJECT_ROOT}/Daily/Detailed_Analysis" -name "*${TODAY}*.html" -exec basename {} \; 2>/dev/null | head -5)
EOF

# 7. Create restore instructions
echo -e "\n${YELLOW}7. Creating restore instructions...${NC}"
cat > "${BACKUP_DIR}/RESTORE_INSTRUCTIONS.md" << 'EOF'
# US-TS System Restore Instructions

## Quick Restore

1. **Stop all services:**
   ```bash
   launchctl list | grep usts | awk '{print $3}' | xargs -I {} launchctl stop {}
   ```

2. **Restore code files:**
   ```bash
   cp -r code/* /Users/maverick/PycharmProjects/US-TS/
   ```

3. **Restore configuration:**
   ```bash
   cp config/config.ini /Users/maverick/PycharmProjects/US-TS/Daily/
   cp config/market_regime_config.json /Users/maverick/PycharmProjects/US-TS/Market_Regime/config.json
   ```

4. **Restore databases:**
   ```bash
   cp data/*.db /Users/maverick/PycharmProjects/US-TS/Market_Regime/
   ```

5. **Restore LaunchAgents:**
   ```bash
   cp launchd/* ~/Library/LaunchAgents/
   ```

6. **Reload LaunchAgents:**
   ```bash
   for plist in launchd/*.plist; do
     launchctl load ~/Library/LaunchAgents/$(basename "$plist")
   done
   ```

7. **Restart critical services:**
   ```bash
   launchctl start com.usts.regime_dashboard
   launchctl start com.usts.health_dashboard
   launchctl start com.usts.regime_detection
   ```

## Dashboard Access After Restore
- Market Regime: http://localhost:8090
- Health Check: http://localhost:7089

## Selective Restore

- **Config only:** `cp config/config.ini /Users/maverick/PycharmProjects/US-TS/Daily/`
- **Dashboards only:** `cp -r code/Market_Regime/dashboard/* /Users/maverick/PycharmProjects/US-TS/Market_Regime/dashboard/`
- **Scanners only:** `cp code/Daily/scripts/*.py /Users/maverick/PycharmProjects/US-TS/Daily/scripts/`
EOF

# 8. Compress the backup
echo -e "\n${YELLOW}8. Compressing backup...${NC}"
cd "${PROJECT_ROOT}/backups"
tar -czf "us_ts_backup_${BACKUP_DATE}.tar.gz" "backup_${BACKUP_DATE}"

# Calculate sizes
BACKUP_SIZE=$(du -sh "backup_${BACKUP_DATE}" | cut -f1)
COMPRESSED_SIZE=$(du -sh "us_ts_backup_${BACKUP_DATE}.tar.gz" | cut -f1)

echo -e "\n${GREEN}✅ US-TS Backup Complete!${NC}"
echo "================================"
echo "Backup Location: ${BACKUP_DIR}"
echo "Compressed File: ${PROJECT_ROOT}/backups/us_ts_backup_${BACKUP_DATE}.tar.gz"
echo "Backup Size: ${BACKUP_SIZE}"
echo "Compressed Size: ${COMPRESSED_SIZE}"
echo "================================"

# Cleanup old backups (keep last 5)
echo -e "\n${YELLOW}Cleaning up old backups (keeping last 5)...${NC}"
cd "${PROJECT_ROOT}/backups"
ls -t us_ts_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -I {} rm -v {}

echo -e "\n${GREEN}Backup process completed successfully!${NC}"