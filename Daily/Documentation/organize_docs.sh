#!/bin/bash

# Documentation Organization Script
# This script helps organize the India-TS documentation structure

echo "=== India-TS Documentation Organization Script ==="
echo "This script will help organize documentation into a centralized structure"
echo ""

# Create directory structure
echo "Creating directory structure..."

mkdir -p scanners
mkdir -p trading  
mkdir -p portfolio
mkdir -p analysis
mkdir -p jobs
mkdir -p dashboards
mkdir -p maintenance
mkdir -p api
mkdir -p development
mkdir -p flows
mkdir -p configuration

echo "✓ Directory structure created"

# Function to safely move files
move_file() {
    source=$1
    dest=$2
    if [ -f "$source" ]; then
        echo "Moving $source to $dest"
        cp "$source" "$dest"
        echo "✓ Moved successfully"
    else
        echo "⚠ File not found: $source"
    fi
}

echo ""
echo "=== Moving Dashboard Documentation ==="
move_file "../DASHBOARD_QUICK_REFERENCE.md" "dashboards/dashboard_quick_reference.md"
move_file "../DASHBOARD_STARTUP_GUIDE.md" "dashboards/dashboard_startup_guide.md"
move_file "../DASHBOARD_HOSTING_GUIDE.md" "dashboards/dashboard_hosting_guide.md"
move_file "../DASHBOARD_JOBS_UPDATE.md" "dashboards/dashboard_jobs_update.md"

echo ""
echo "=== Moving Pattern Documentation ==="
move_file "../G_PATTERN_MASTER_GUIDE.md" "scanners/g_pattern_master_guide.md"
move_file "../trading/G_PATTERN_AUTO_TRADER_GUIDE.md" "trading/g_pattern_auto_trader_guide.md"

echo ""
echo "=== Moving Jobs Documentation ==="
move_file "../INDIA_TS_JOBS_DOCUMENTATION.md" "jobs/jobs_overview.md"

echo ""
echo "=== Moving Maintenance Documentation ==="
move_file "../../BACKUP_GUIDE.md" "maintenance/backup_restore_guide.md"
move_file "../../GOLDEN_VERSION_SETUP_GUIDE.md" "maintenance/golden_version_guide.md"

echo ""
echo "=== Moving SL Watchdog Documentation ==="
move_file "../bin/SL_WATCHDOG_MANAGEMENT.md" "portfolio/sl_watchdog_management.md"
move_file "../bin/SL_WATCHDOG_QUICK_REFERENCE.txt" "portfolio/sl_watchdog_quick_reference.txt"

echo ""
echo "=== Consolidating Flow Diagrams ==="
move_file "sl_watchdog_flow.md" "flows/sl_watchdog_flow.md"
move_file "al_brooks_scanner_flow.md" "flows/al_brooks_scanner_flow.md"
move_file "place_orders_daily_flow.md" "flows/place_orders_daily_flow.md"
move_file "../Diagrams/scanner_flows.md" "flows/scanner_flows.md"
move_file "../Diagrams/order_placement_flow.md" "flows/order_placement_flow.md"
move_file "../Diagrams/action_plan_flow.md" "flows/action_plan_flow.md"

echo ""
echo "=== Creating Consolidated Guides ==="

# Create SL Watchdog consolidated guide
cat > portfolio/sl_watchdog_guide.md << 'EOF'
# SL Watchdog Complete Guide

This guide consolidates all SL Watchdog documentation into a single comprehensive resource.

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Management](#management)
7. [Volume Anomaly Detection](#volume-anomaly-detection)
8. [Troubleshooting](#troubleshooting)

## Overview

The SL Watchdog system provides automated stop-loss monitoring for CNC positions using ATR-based trailing stops.

### Key Components
- **SL_watchdog.py** - Standard ATR-based stop loss monitoring
- **SL_watchdog_regime.py** - Enhanced version with market regime integration

EOF

echo "✓ Created consolidated SL Watchdog guide template"

# Create Quick Reference
cat > QUICK_REFERENCE.md << 'EOF'
# India-TS Quick Reference

## Essential Commands

### Scanner Operations
```bash
# Run Brooks scanner
python Daily/utils/brooks_reversal_scheduler.py

# Run reversal scanners
python Daily/scanners/Scanner_Reversals_India.py --type long
python Daily/scanners/Scanner_Reversals_India.py --type short
```

### Position Management
```bash
# Start SL Watchdog
cd Daily/bin
./start_sl_watchdog_regime.sh

# Check watchdog status
./check_sl_watchdog_status.sh

# Stop watchdog
./stop_sl_watchdog_regime.sh
```

### Dashboard Operations
```bash
# Start dashboards
cd Daily/utils
./start_dashboards.sh

# Stop dashboards
./stop_dashboards.sh
```

### Job Management
```bash
# Load all jobs
cd Daily/utils
./load_all_jobs.sh

# Check job status
launchctl list | grep india-ts
```

## Key File Locations

- **Config**: `Daily/config.ini`
- **Logs**: `Daily/logs/<username>/`
- **Results**: `Daily/results/`
- **Orders**: `Daily/Current_Orders/<username>/`

## Important URLs

- Health Dashboard: http://localhost:5000
- Market Breadth: http://localhost:5001
- Enhanced Dashboard: http://localhost:8080

EOF

echo "✓ Created Quick Reference guide"

echo ""
echo "=== Summary ==="
echo "Documentation reorganization initiated."
echo "Note: This script copies files to preserve originals."
echo ""
echo "Next steps:"
echo "1. Review the new structure"
echo "2. Update internal links in moved documents"
echo "3. Replace README.md with README_NEW.md"
echo "4. Remove original files after verification"
echo ""
echo "To view the new structure:"
echo "  tree -L 2 ."