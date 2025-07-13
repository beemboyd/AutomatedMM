#!/bin/bash
# Script to commit and push US-TS system to GitHub repository
# Repository: https://github.com/saivenkata1/India-June.git

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
US_TS_DIR="/Users/maverick/PycharmProjects/US-TS"
REPO_URL="https://github.com/saivenkata1/India-June.git"
BRANCH_NAME="us-ts-system"
COMMIT_DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo -e "${GREEN}=== US-TS GitHub Push Script ===${NC}"
echo -e "Repository: ${BLUE}${REPO_URL}${NC}"
echo -e "Branch: ${BLUE}${BRANCH_NAME}${NC}"
echo ""

# Navigate to US-TS directory
cd "$US_TS_DIR" || exit 1

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}Initializing git repository...${NC}"
    git init
fi

# Check current remote
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null)
if [ -z "$CURRENT_REMOTE" ]; then
    echo -e "${YELLOW}Adding remote origin...${NC}"
    git remote add origin "$REPO_URL"
elif [ "$CURRENT_REMOTE" != "$REPO_URL" ]; then
    echo -e "${YELLOW}Updating remote origin...${NC}"
    git remote set-url origin "$REPO_URL"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo -e "${YELLOW}Creating .gitignore file...${NC}"
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store

# Logs
*.log
logs/
*.log.*

# Data files
*.xlsx
*.xls
*.csv
*.db
*.pickle
*.h5

# Config files with sensitive data
config.ini
.env
credentials.json
*_credentials.json

# Temporary files
*.tmp
*.temp
*.bak
*.backup

# Large files
*.pdf
*.zip
*.tar.gz
*.rar

# Market data
data/historical/
data/cache/
cache/

# Results (keep only latest)
results_archive/
Daily/results/*
!Daily/results/.gitkeep

# HTML reports (too many)
Daily/Detailed_Analysis/*.html
!Daily/Detailed_Analysis/.gitkeep

# Personal data
data/trading_state*.json
data/positions*.json
Current_Orders/

# Backup files
backups/
*.backup

# System files
.DS_Store
Thumbs.db

# Keep important structure
!.gitkeep
!README.md
!requirements.txt
EOF
fi

# Create README if it doesn't exist
if [ ! -f "README.md" ]; then
    echo -e "${YELLOW}Creating README.md...${NC}"
    cat > README.md << 'EOF'
# US-TS Trading System

US Trading System - Automated trading strategies for US markets.

## Overview
This system provides automated trading capabilities for US markets including:
- Market regime analysis and prediction
- Al Brooks pattern recognition
- Real-time market monitoring
- Risk management and position tracking
- Multiple trading strategies

## Structure
```
US-TS/
├── Daily/                  # Daily trading operations
│   ├── scripts/           # Trading scripts and scanners
│   ├── results/           # Scan results
│   └── logs/              # System logs
├── Market_Regime/         # Market regime analysis
│   ├── dashboard/         # Web dashboards
│   ├── models/            # ML models
│   └── learning/          # Learning system
├── data/                  # Data storage
└── config/                # Configuration files
```

## Dashboards
- Market Regime Dashboard: http://localhost:8090
- Health Check Dashboard: http://localhost:7089

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure credentials in `config.ini`
3. Start services using launchctl

## Security Note
Never commit sensitive credentials. Use environment variables or secure config files.
EOF
fi

# Check git status
echo -e "\n${YELLOW}Checking git status...${NC}"
git status --porcelain | head -20

# Count changes
CHANGES=$(git status --porcelain | wc -l)
echo -e "Total changes to commit: ${BLUE}${CHANGES}${NC} files/directories"

# Create/checkout branch
echo -e "\n${YELLOW}Creating/checking out branch: ${BRANCH_NAME}${NC}"
git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"

# Stage all files
echo -e "\n${YELLOW}Staging files...${NC}"
git add .

# Show what will be committed (summary)
echo -e "\n${YELLOW}Files to be committed:${NC}"
git diff --cached --name-status | head -30
if [ $(git diff --cached --name-status | wc -l) -gt 30 ]; then
    echo "... and $(( $(git diff --cached --name-status | wc -l) - 30 )) more files"
fi

# Commit
echo -e "\n${YELLOW}Creating commit...${NC}"
git commit -m "Add US-TS Trading System - ${COMMIT_DATE}

- Complete US trading system implementation
- Market regime analysis and prediction
- Al Brooks pattern recognition
- Trading strategies and risk management
- Dashboards and monitoring tools
- Scheduled jobs via launchctl

This commit includes the full US-TS system as of ${COMMIT_DATE}" || {
    echo -e "${RED}No changes to commit or commit failed${NC}"
    exit 1
}

# Show commit info
echo -e "\n${GREEN}Commit created successfully!${NC}"
git log --oneline -1

# Push to GitHub
echo -e "\n${YELLOW}Pushing to GitHub...${NC}"
echo -e "Branch: ${BLUE}${BRANCH_NAME}${NC}"
echo -e "Repository: ${BLUE}${REPO_URL}${NC}"

# Push with upstream tracking
git push -u origin "$BRANCH_NAME" || {
    echo -e "\n${RED}Push failed!${NC}"
    echo -e "${YELLOW}Possible issues:${NC}"
    echo "1. Authentication required - you may need to enter GitHub credentials"
    echo "2. Repository permissions - ensure you have write access"
    echo "3. Network issues - check your internet connection"
    echo ""
    echo -e "${YELLOW}To configure GitHub authentication:${NC}"
    echo "git config --global user.name 'Your Name'"
    echo "git config --global user.email 'your-email@example.com'"
    echo ""
    echo -e "${YELLOW}For GitHub token authentication:${NC}"
    echo "1. Create a token at: https://github.com/settings/tokens"
    echo "2. Use token as password when prompted"
    exit 1
}

echo -e "\n${GREEN}✅ US-TS system successfully pushed to GitHub!${NC}"
echo -e "Repository: ${BLUE}${REPO_URL}${NC}"
echo -e "Branch: ${BLUE}${BRANCH_NAME}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Visit: https://github.com/saivenkata1/India-June/tree/${BRANCH_NAME}"
echo "2. Create a Pull Request to merge into main branch"
echo "3. Review the changes online"
echo ""
echo -e "${GREEN}Push completed at: $(date)${NC}"