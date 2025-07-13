#!/bin/bash
# Weekly G Pattern Workflow Script

echo "=== G PATTERN WEEKLY WORKFLOW ==="
echo "Running at: $(date)"

# Define paths
DAILY_DIR="/Users/maverick/PycharmProjects/India-TS/Daily"
PYTHON_PATH="/Users/maverick/PycharmProjects/India-TS/.venv/bin/python"

# Day of week (1=Monday, 7=Sunday)
DAY_OF_WEEK=$(date +%u)

case $DAY_OF_WEEK in
    1)  # Monday - Fresh week scan
        echo "MONDAY: Starting fresh week scan..."
        echo "1. Clearing last week's history"
        # Archive last week's data
        mv "$DAILY_DIR/G_Pattern_Master/G_Pattern_History.json" \
           "$DAILY_DIR/G_Pattern_Master/Archive/G_Pattern_History_$(date -v-7d +%Y%m%d).json" 2>/dev/null
        
        echo "2. Running initial scan..."
        $PYTHON_PATH "$DAILY_DIR/scanners/KC_Upper_Limit_Trending.py"
        
        echo "3. Generating master tracker..."
        $PYTHON_PATH "$DAILY_DIR/scanners/G_Pattern_Master_Tracker.py"
        ;;
        
    2|3)  # Tuesday/Wednesday - Look for initial positions
        echo "TUESDAY/WEDNESDAY: Scanning for initial positions..."
        $PYTHON_PATH "$DAILY_DIR/scanners/KC_Upper_Limit_Trending.py"
        $PYTHON_PATH "$DAILY_DIR/scanners/G_Pattern_Master_Tracker.py"
        
        echo "CHECK: G_Pattern_Master_List.xlsx for INITIAL POSITION recommendations"
        ;;
        
    4|5)  # Thursday/Friday - Look for doubling opportunities
        echo "THURSDAY/FRIDAY: Scanning for position doubling..."
        $PYTHON_PATH "$DAILY_DIR/scanners/KC_Upper_Limit_Trending.py"
        $PYTHON_PATH "$DAILY_DIR/scanners/G_Pattern_Master_Tracker.py"
        
        echo "CHECK: G_Pattern_Master_List.xlsx for DOUBLE POSITION recommendations"
        ;;
        
    6)  # Saturday - Weekly review
        echo "SATURDAY: Weekly review..."
        echo "1. Generating weekly performance report..."
        $PYTHON_PATH "$DAILY_DIR/scanners/G_Pattern_Master_Tracker.py"
        
        echo "2. Archiving week's data..."
        cp "$DAILY_DIR/G_Pattern_Master/G_Pattern_Master_List.xlsx" \
           "$DAILY_DIR/G_Pattern_Master/Archive/Master_List_$(date +%Y%m%d).xlsx"
        ;;
        
    7)  # Sunday - Maintenance
        echo "SUNDAY: System maintenance day"
        ;;
esac

echo "Workflow complete!"
echo "Check master reports at: $DAILY_DIR/G_Pattern_Master/"