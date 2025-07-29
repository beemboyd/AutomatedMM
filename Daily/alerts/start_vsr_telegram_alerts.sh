#!/bin/bash
# Start VSR Telegram Alert Service

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}VSR Telegram Alert Service Startup${NC}"
echo "======================================"

# Check if config.ini has telegram chat_id configured
CONFIG_FILE="$PROJECT_DIR/config.ini"
if [ -f "$CONFIG_FILE" ]; then
    CHAT_ID=$(grep -A10 "^\[TELEGRAM\]" "$CONFIG_FILE" | grep "^chat_id" | cut -d'=' -f2 | xargs)
    if [ -z "$CHAT_ID" ] || [ "$CHAT_ID" = " " ]; then
        echo -e "${YELLOW}Warning: Telegram chat_id not configured in config.ini${NC}"
        echo ""
        echo "To set up Telegram alerts:"
        echo "1. Get your chat ID by running:"
        echo "   python3 $SCRIPT_DIR/get_telegram_chat_id.py"
        echo ""
        echo "2. Add the chat_id to config.ini in the [TELEGRAM] section"
        echo ""
        read -p "Continue without Telegram alerts? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}Telegram configured with chat_id: ${CHAT_ID}${NC}"
    fi
else
    echo -e "${RED}Error: config.ini not found at $CONFIG_FILE${NC}"
    exit 1
fi

# Default settings
MOMENTUM_THRESHOLD=${MOMENTUM_THRESHOLD:-10.0}
SCORE_THRESHOLD=${SCORE_THRESHOLD:-60}
BATCH_MODE=${BATCH_MODE:-false}
INTERVAL=${INTERVAL:-60}

echo -e "${GREEN}Configuration:${NC}"
echo "  Momentum Threshold: ${MOMENTUM_THRESHOLD}%"
echo "  Score Threshold: ${SCORE_THRESHOLD}"
echo "  Batch Mode: ${BATCH_MODE}"
echo "  Update Interval: ${INTERVAL}s"
echo ""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--momentum)
            MOMENTUM_THRESHOLD="$2"
            shift 2
            ;;
        -s|--score)
            SCORE_THRESHOLD="$2"
            shift 2
            ;;
        -b|--batch)
            BATCH_MODE="true"
            shift
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-m momentum_threshold] [-s score_threshold] [-b] [-i interval]"
            exit 1
            ;;
    esac
done

# Build command
CMD="python3 $SCRIPT_DIR/vsr_telegram_service.py"
CMD="$CMD --momentum-threshold $MOMENTUM_THRESHOLD"
CMD="$CMD --score-threshold $SCORE_THRESHOLD"
CMD="$CMD --interval $INTERVAL"

if [ "$BATCH_MODE" = "true" ]; then
    CMD="$CMD --batch"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs/vsr_telegram"

# Start the service
echo -e "${GREEN}Starting VSR Telegram Alert Service...${NC}"
echo "Command: $CMD"
echo ""
echo "Logs: $PROJECT_DIR/logs/vsr_telegram/"
echo "Press Ctrl+C to stop"
echo ""

# Run the service
cd "$PROJECT_DIR"
exec $CMD