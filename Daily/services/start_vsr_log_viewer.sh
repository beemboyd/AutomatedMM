#!/bin/bash

# Start VSR Anomaly Log Viewer
# This script starts a web server to view VSR anomaly logs

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Starting VSR Log Viewer..."
echo "Access at: http://localhost:9901"
echo ""
echo "Options:"
echo "  --port PORT     Port to run on (default: 9901)"
echo "  --lines N       Number of lines to display (default: 100)"
echo "  --refresh N     Refresh interval in seconds (default: 60)"
echo ""

cd "$PROJECT_DIR"
python3 Daily/services/vsr_log_viewer.py "$@"