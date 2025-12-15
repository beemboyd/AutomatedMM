#!/bin/bash
# Start/Restart VSR Simulations after token refresh
# Run this after ./Daily/refresh_token_services.sh or ./Daily/pre_market_setup_robust.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "VSR Simulation Startup - $(date)"
echo "========================================="

# Kill any existing simulation processes
echo "Stopping existing simulations..."
pkill -f "simulation_[1-4]\.py" 2>/dev/null
pkill -f "simulation_dashboard\.py" 2>/dev/null
sleep 2

# Start dashboards
echo "Starting dashboards on ports 4001-4004..."
nohup /usr/bin/python3 dashboards/simulation_dashboard.py --sim-id sim_1 --port 4001 > logs/dashboard_4001.log 2>&1 &
nohup /usr/bin/python3 dashboards/simulation_dashboard.py --sim-id sim_2 --port 4002 > logs/dashboard_4002.log 2>&1 &
nohup /usr/bin/python3 dashboards/simulation_dashboard.py --sim-id sim_3 --port 4003 > logs/dashboard_4003.log 2>&1 &
nohup /usr/bin/python3 dashboards/simulation_dashboard.py --sim-id sim_4 --port 4004 > logs/dashboard_4004.log 2>&1 &
sleep 3

# Start simulation runners
echo "Starting simulation runners..."
nohup /usr/bin/python3 runners/simulation_1.py > logs/simulation_1.log 2>&1 &
nohup /usr/bin/python3 runners/simulation_2.py > logs/simulation_2.log 2>&1 &
nohup /usr/bin/python3 runners/simulation_3.py > logs/simulation_3.log 2>&1 &
nohup /usr/bin/python3 runners/simulation_4.py > logs/simulation_4.log 2>&1 &
sleep 3

# Verify all are running
echo ""
echo "Verification:"
echo "-------------"
for port in 4001 4002 4003 4004; do
    status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/ 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo "Dashboard $port: OK"
    else
        echo "Dashboard $port: FAILED"
    fi
done

sim_count=$(ps aux | grep -E "simulation_[1-4]\.py" | grep -v grep | wc -l)
echo "Simulation runners: $sim_count/4 running"

echo ""
echo "Dashboard URLs:"
echo "  - http://localhost:4001 (Long + KC SL)"
echo "  - http://localhost:4002 (Long + PSAR SL)"
echo "  - http://localhost:4003 (Short + KC SL)"
echo "  - http://localhost:4004 (Short + PSAR SL)"
echo ""
echo "Simulation startup complete!"
