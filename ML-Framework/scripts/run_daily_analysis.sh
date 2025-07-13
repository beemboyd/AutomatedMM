#!/bin/bash
# Daily Market Regime Analysis Runner
# This script runs the regime analysis and displays key results

# Set up environment
cd /Users/maverick/PycharmProjects/India-TS
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Create logs directory if it doesn't exist
mkdir -p ML-Framework/logs
mkdir -p ML-Framework/results/daily_analysis

# Get today's date
TODAY=$(date +%Y%m%d)
DISPLAY_DATE=$(date +"%A, %B %d, %Y")

echo "======================================"
echo "Market Regime Analysis for $DISPLAY_DATE"
echo "======================================"
echo ""

# Run the analysis
echo "Running regime detection analysis..."
python3 ML-Framework/scripts/daily_regime_analysis.py > ML-Framework/logs/regime_analysis_${TODAY}.log 2>&1

# Check if analysis completed successfully
if [ $? -eq 0 ]; then
    echo "✓ Analysis completed successfully"
    echo ""
    
    # Display market outlook
    echo "MARKET OUTLOOK:"
    echo "---------------"
    grep -A2 "MARKET OUTLOOK" ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt 2>/dev/null || echo "No summary found"
    echo ""
    
    # Display index regimes
    echo "INDEX REGIMES:"
    echo "---------------"
    grep -A5 "INDEX REGIMES:" ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt 2>/dev/null | tail -n 4
    echo ""
    
    # Display risk alerts
    echo "RISK ALERTS:"
    echo "---------------"
    ALERTS=$(grep -A10 "RISK ALERTS" ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt 2>/dev/null | grep -v "RISK ALERTS" | grep -v "^-")
    if [ -z "$ALERTS" ]; then
        echo "No risk alerts today ✓"
    else
        echo "$ALERTS"
    fi
    echo ""
    
    # Display position recommendations summary
    echo "POSITION RECOMMENDATIONS:"
    echo "------------------------"
    grep -A5 "POSITION RECOMMENDATIONS:" ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt 2>/dev/null | tail -n 4
    echo ""
    
    # Display new opportunities
    echo "NEW OPPORTUNITIES:"
    echo "-----------------"
    OPPS=$(grep -A10 "NEW OPPORTUNITIES" ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt 2>/dev/null | grep -v "NEW OPPORTUNITIES" | grep -v "^-" | head -n 5)
    if [ -z "$OPPS" ]; then
        echo "No new opportunities identified"
    else
        echo "$OPPS"
    fi
    echo ""
    
    # Show report locations
    echo "DETAILED REPORTS:"
    echo "-----------------"
    echo "Summary: ML-Framework/results/daily_analysis/regime_summary_${TODAY}.txt"
    echo "Positions: ML-Framework/results/daily_analysis/position_details_${TODAY}.csv"
    echo "Risk Report: ML-Framework/results/daily_analysis/risk_report_${TODAY}.txt"
    echo "JSON Data: ML-Framework/results/daily_analysis/regime_analysis_${TODAY}.json"
    
else
    echo "✗ Analysis failed. Check logs at:"
    echo "  ML-Framework/logs/regime_analysis_${TODAY}.log"
    exit 1
fi

echo ""
echo "======================================"
echo "Analysis complete at $(date +%H:%M:%S)"
echo "======================================" 