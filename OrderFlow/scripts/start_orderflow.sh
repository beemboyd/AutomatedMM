#!/bin/bash
# Start OrderFlow service
# Usage: ./start_orderflow.sh [--user Sai] [--tickers RELIANCE,HDFCBANK]

BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
PID_FILE="${BASE_DIR}/OrderFlow/logs/orderflow.pid"
LOG_DIR="${BASE_DIR}/OrderFlow/logs"

mkdir -p "${LOG_DIR}"

# Check if already running
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "OrderFlow service already running (PID: ${OLD_PID})"
        exit 1
    else
        echo "Removing stale PID file"
        rm -f "${PID_FILE}"
    fi
fi

echo "Starting OrderFlow service..."

cd "${BASE_DIR}"
nohup python3 -m OrderFlow.services.orderflow_service "$@" > /dev/null 2>&1 &
PID=$!
echo "${PID}" > "${PID_FILE}"

sleep 3

if kill -0 "${PID}" 2>/dev/null; then
    echo "OrderFlow service started (PID: ${PID})"
    echo "Logs: ${LOG_DIR}/orderflow_$(date '+%Y%m%d').log"
else
    echo "ERROR: OrderFlow service failed to start"
    rm -f "${PID_FILE}"
    exit 1
fi
