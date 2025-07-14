#!/bin/bash

# Start SL Watchdog for all users with access tokens
# This script is scheduled to run at 9:15 AM IST on weekdays

echo "=========================================="
echo "Starting SL Watchdogs for all users"
echo "Time: $(date)"
echo "=========================================="

# Set working directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/portfolio

# Run the Python script
/usr/bin/python3 start_all_sl_watchdogs.py

echo "=========================================="
echo "SL Watchdog startup complete"
echo "=========================================="