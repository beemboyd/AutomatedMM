#!/bin/bash
#
# Fix Breadth Data Script
# Quick utility to clean bad breadth data after access token issues
#

echo "========================================"
echo "Breadth Data Cleanup Utility"
echo "========================================"
echo ""

# Navigate to Market Regime directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime

# Check recent data quality
echo "1. Checking data quality from last 24 hours..."
python3 breadth_data_validator.py --recent 24
echo ""

# Ask user if they want to clean
read -p "Do you want to clean all bad breadth data? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "2. Performing dry run to show what will be cleaned..."
    python3 breadth_data_validator.py --dry-run
    echo ""
    
    read -p "Proceed with actual cleaning? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        echo ""
        echo "3. Cleaning bad data..."
        python3 breadth_data_validator.py
        echo ""
        
        echo "4. Restarting Market Regime dashboard..."
        pkill -f "dashboard_enhanced.py"
        sleep 1
        nohup python3 dashboard_enhanced.py > /dev/null 2>&1 &
        echo "Dashboard restarted on port 8080"
        echo ""
        
        echo "✅ Cleanup complete!"
        echo "Dashboard should now display corrected data at http://localhost:8080/"
    else
        echo "Cleanup cancelled."
    fi
else
    echo "No cleanup performed."
fi

echo ""
echo "========================================"