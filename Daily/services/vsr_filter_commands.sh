#!/bin/bash
# VSR Tracker Filtering Commands
# Useful commands to filter VSR tracker logs for high-quality signals

# Color codes for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== VSR Tracker Filter Commands ===${NC}"
echo ""

# Get today's log file
LOG_FILE="../logs/vsr_tracker/vsr_tracker_$(date +%Y%m%d).log"

echo -e "${YELLOW}1. High Score + Any Build (Score ≥80 + Build ≥10):${NC}"
echo "tail -f $LOG_FILE | grep -E 'Score: ([89][0-9]|100).*Build: 📈'"
echo ""

echo -e "${YELLOW}2. Strong Momentum Build Only (Build = 20):${NC}"
echo "tail -f $LOG_FILE | grep 'Build: 📈20'"
echo ""

echo -e "${YELLOW}3. Perfect Score with Build (Score = 100 + Any Build):${NC}"
echo "tail -f $LOG_FILE | grep -E 'Score: 100.*Build: 📈'"
echo ""

echo -e "${YELLOW}4. High Score + Strong Build (Score ≥80 + Build = 20):${NC}"
echo "tail -f $LOG_FILE | grep -E 'Score: ([89][0-9]|100).*Build: 📈20'"
echo ""

echo -e "${YELLOW}5. Any Ticker with Momentum Build (Build ≥10):${NC}"
echo "tail -f $LOG_FILE | grep '📈'"
echo ""

echo -e "${YELLOW}6. Top Performers (Score ≥90):${NC}"
echo "tail -f $LOG_FILE | grep -E 'Score: (9[0-9]|100)'"
echo ""

echo -e "${YELLOW}7. Latest High Score Summary (non-streaming):${NC}"
echo "grep -E 'Score: ([89][0-9]|100).*Build: 📈' $LOG_FILE | tail -20"
echo ""

echo -e "${PURPLE}=== One-Line Commands ===${NC}"
echo ""

echo -e "${BLUE}Show only high score + build tickers:${NC}"
echo -e "${GREEN}tail -f $LOG_FILE | grep -E 'Score: ([89][0-9]|100).*Build: 📈'${NC}"
echo ""

echo -e "${BLUE}Show strong momentum builds only:${NC}"
echo -e "${GREEN}tail -f $LOG_FILE | grep 'Build: 📈20'${NC}"
echo ""

echo -e "${BLUE}Show any momentum build:${NC}"
echo -e "${GREEN}tail -f $LOG_FILE | grep '📈'${NC}"