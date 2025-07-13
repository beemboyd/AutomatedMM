#!/bin/bash

echo "=========================================="
echo "India-TS Jobs Status Report"
echo "Generated: $(date)"
echo "=========================================="
echo ""

# Function to check if a job should be running based on current time
should_be_running() {
    local job_name=$1
    local current_hour=$(date +%H)
    local current_min=$(date +%M)
    local current_day=$(date +%u)  # 1=Monday, 7=Sunday
    
    # Skip weekends for most jobs
    if [ $current_day -gt 5 ]; then
        case $job_name in
            "com.india-ts.weekly_backup")
                # Weekly backup runs on Saturday
                if [ $current_day -eq 6 ] && [ $current_hour -eq 10 ]; then
                    return 0
                fi
                ;;
            "com.india-ts.health_dashboard")
                # Health dashboard runs 24/7
                return 0
                ;;
        esac
        return 1
    fi
    
    # Check market hours jobs (9:00 AM - 3:30 PM)
    case $job_name in
        "com.india-ts.long_reversal_daily"|"com.india-ts.short_reversal_daily"|"com.india-ts.market_regime_analysis")
            if [ $current_hour -ge 9 ] && [ $current_hour -lt 16 ]; then
                return 0
            fi
            ;;
        "com.india-ts.health_dashboard")
            # Always running
            return 0
            ;;
    esac
    
    return 1
}

# Arrays to store job categories
RUNNING_JOBS=()
SUCCESSFUL_JOBS=()
ERROR_JOBS=()
NOT_LOADED_JOBS=()

# Expected jobs
EXPECTED_JOBS=(
    "com.india-ts.brooks_reversal_4times"
    "com.india-ts.brooks_reversal_simple"
    "com.india-ts.consolidated_score"
    "com.india-ts.daily_action_plan"
    "com.india-ts.health_dashboard"
    "com.india-ts.long_reversal_daily"
    "com.india-ts.market_regime_analysis"
    "com.india-ts.market_regime_dashboard"
    "com.india-ts.short_reversal_daily"
    "com.india-ts.sl_watchdog_stop"
    "com.india-ts.strategyc_filter"
    "com.india-ts.synch_zerodha_local"
    "com.india-ts.weekly_backup"
)

# Check each expected job
for job in "${EXPECTED_JOBS[@]}"; do
    job_info=$(launchctl list | grep "$job")
    
    if [ -z "$job_info" ]; then
        NOT_LOADED_JOBS+=("$job")
    else
        pid=$(echo $job_info | awk '{print $1}')
        status=$(echo $job_info | awk '{print $2}')
        
        if [ "$pid" != "-" ]; then
            RUNNING_JOBS+=("$job (PID: $pid)")
        elif [ "$status" = "0" ]; then
            SUCCESSFUL_JOBS+=("$job")
        else
            ERROR_JOBS+=("$job (exit code: $status)")
        fi
    fi
done

# Display results
echo "📊 SUMMARY"
echo "=========="
echo "Total Expected Jobs: ${#EXPECTED_JOBS[@]}"
echo "Currently Running: ${#RUNNING_JOBS[@]}"
echo "Last Run Successful: ${#SUCCESSFUL_JOBS[@]}"
echo "Errors: ${#ERROR_JOBS[@]}"
echo "Not Loaded: ${#NOT_LOADED_JOBS[@]}"
echo ""

if [ ${#RUNNING_JOBS[@]} -gt 0 ]; then
    echo "✅ RUNNING JOBS (${#RUNNING_JOBS[@]})"
    echo "================"
    for job in "${RUNNING_JOBS[@]}"; do
        echo "  • $job"
    done
    echo ""
fi

if [ ${#SUCCESSFUL_JOBS[@]} -gt 0 ]; then
    echo "✅ SUCCESSFUL (Last Run) (${#SUCCESSFUL_JOBS[@]})"
    echo "========================"
    for job in "${SUCCESSFUL_JOBS[@]}"; do
        echo "  • $job"
    done
    echo ""
fi

if [ ${#ERROR_JOBS[@]} -gt 0 ]; then
    echo "❌ ERRORS (${#ERROR_JOBS[@]})"
    echo "========="
    for job in "${ERROR_JOBS[@]}"; do
        echo "  • $job"
    done
    echo ""
    echo "To check error details, run:"
    echo "tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/logs/*error*.log"
    echo ""
fi

if [ ${#NOT_LOADED_JOBS[@]} -gt 0 ]; then
    echo "⚠️  NOT LOADED (${#NOT_LOADED_JOBS[@]})"
    echo "============="
    for job in "${NOT_LOADED_JOBS[@]}"; do
        echo "  • $job"
    done
    echo ""
    echo "To load missing jobs, run:"
    echo "/Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh"
    echo ""
fi

# Check for deprecated jobs that might still be loaded
echo "🔍 CHECKING FOR DEPRECATED JOBS"
echo "=============================="
deprecated_found=0
deprecated_jobs=("com.india-ts.outcome_resolver" "com.india-ts.market_regime_daily_metrics" "com.india-ts.sl_watchdog_start")

for job in "${deprecated_jobs[@]}"; do
    if launchctl list | grep -q "$job"; then
        echo "  ⚠️  Found deprecated job: $job (should be unloaded)"
        deprecated_found=1
    fi
done

if [ $deprecated_found -eq 0 ]; then
    echo "  ✅ No deprecated jobs found"
fi

echo ""
echo "=========================================="
echo "For full documentation, see:"
echo "/Users/maverick/PycharmProjects/India-TS/Daily/INDIA_TS_JOBS_DOCUMENTATION.md"
echo "==========================================="