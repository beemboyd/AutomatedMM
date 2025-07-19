#!/bin/bash

# Standardize Python paths in all India-TS plist files
# This ensures consistent Python interpreter usage

echo "=========================================="
echo "Standardizing Python paths in plist files"
echo "=========================================="

# Recommended Python path based on module availability
RECOMMENDED_PYTHON="/usr/local/bin/python3"

# Virtual environment Python (has all modules)
VENV_PYTHON="/Users/maverick/PycharmProjects/India-TS/.venv/bin/python"

# Check which Python to use
# Since virtual env has all modules, use it
if [ -f "$VENV_PYTHON" ]; then
    echo "Using virtual environment Python: $VENV_PYTHON"
    PYTHON_PATH="$VENV_PYTHON"
else
    echo "Using system Python: $RECOMMENDED_PYTHON"
    PYTHON_PATH="$RECOMMENDED_PYTHON"
fi

# List of plist files that need Python path updates
PLIST_FILES=(
    "com.india-ts.brooks_reversal_4times.plist"
    "com.india-ts.brooks_reversal_simple.plist"
    "com.india-ts.consolidated_score.plist"
    "com.india-ts.daily_action_plan.plist"
    "com.india-ts.health_dashboard.plist"
    "com.india-ts.kc_lower_limit_trending.plist"
    "com.india-ts.kc_upper_limit_trending.plist"
    "com.india-ts.long_reversal_daily.plist"
    "com.india-ts.market_breadth_dashboard.plist"
    "com.india-ts.market_breadth_scanner.plist"
    "com.india-ts.market_regime_analysis.plist"
    "com.india-ts.short_reversal_daily.plist"
    "com.india-ts.sl_watchdog_start.plist"
    "com.india-ts.strategyc_filter.plist"
    "com.india-ts.synch_zerodha_local.plist"
)

LAUNCHAGENTS_DIR="/Users/maverick/Library/LaunchAgents"

for plist in "${PLIST_FILES[@]}"; do
    plist_path="$LAUNCHAGENTS_DIR/$plist"
    
    if [ -f "$plist_path" ]; then
        echo ""
        echo "Processing: $plist"
        
        # Check current Python path
        current_python=$(plutil -convert xml1 -o - "$plist_path" | grep -A 1 "ProgramArguments" | grep -E "python" | sed 's/.*<string>\(.*\)<\/string>/\1/' | head -1)
        
        if [ -n "$current_python" ]; then
            echo "  Current Python: $current_python"
            
            # Create temporary file
            temp_file=$(mktemp)
            
            # Convert to XML, replace Python path, convert back to binary
            plutil -convert xml1 -o "$temp_file" "$plist_path"
            
            # Replace various Python paths with our recommended one
            sed -i '' "s|/usr/bin/python3|$PYTHON_PATH|g" "$temp_file"
            sed -i '' "s|/usr/local/bin/python3|$PYTHON_PATH|g" "$temp_file"
            sed -i '' "s|/Library/Frameworks/Python.framework/Versions/3.11/bin/python3|$PYTHON_PATH|g" "$temp_file"
            sed -i '' "s|/Library/Frameworks/Python.framework/Versions/3.12/bin/python3|$PYTHON_PATH|g" "$temp_file"
            
            # Convert back to binary and replace
            plutil -convert binary1 -o "$plist_path" "$temp_file"
            rm "$temp_file"
            
            echo "  Updated to: $PYTHON_PATH"
            
            # Reload if currently loaded
            if launchctl list | grep -q "${plist%.plist}"; then
                echo "  Reloading..."
                launchctl unload "$plist_path" 2>/dev/null
                launchctl load "$plist_path" 2>/dev/null
            fi
        fi
    fi
done

echo ""
echo "=========================================="
echo "Python path standardization complete!"
echo "Recommended to restart all jobs with:"
echo "/Users/maverick/PycharmProjects/India-TS/Daily/utils/unload_all_jobs.sh"
echo "/Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh"
echo "=========================================="