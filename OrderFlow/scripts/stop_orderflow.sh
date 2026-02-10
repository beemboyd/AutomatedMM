#!/bin/bash
# Stop OrderFlow service
# Usage: ./stop_orderflow.sh

BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
PID_FILE="${BASE_DIR}/OrderFlow/logs/orderflow.pid"

if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if kill -0 "${PID}" 2>/dev/null; then
        echo "Stopping OrderFlow service (PID: ${PID})..."
        kill "${PID}"
        sleep 3
        # Force kill if still running
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Force killing PID ${PID}..."
            kill -9 "${PID}"
        fi
        echo "OrderFlow service stopped"
    else
        echo "OrderFlow service not running (stale PID file)"
    fi
    rm -f "${PID_FILE}"
else
    # Try to find by process name
    PIDS=$(pgrep -f "orderflow_service" 2>/dev/null)
    if [ -n "${PIDS}" ]; then
        echo "Killing OrderFlow processes: ${PIDS}"
        kill ${PIDS} 2>/dev/null
        sleep 2
        echo "OrderFlow service stopped"
    else
        echo "OrderFlow service is not running"
    fi
fi
