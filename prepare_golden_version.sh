#!/bin/bash

# India TS 3.0 - Prepare Golden Version
# This script will prepare the current state as golden version

echo "====================================="
echo "India TS 3.0 - Preparing Golden Version"
echo "====================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check current status
echo -e "${YELLOW}Current Git Status:${NC}"
git status --short

# Create comprehensive .gitignore
echo -e "\n${YELLOW}Updating .gitignore...${NC}"
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

# Logs
*.log
logs/*.log
*.log.*

# Excel/Data files that change frequently
*.xlsx
*.xls
*.csv

# State files
trading_state.json
*_state.json
trading_state_*.json

# Temporary files
*.tmp
*.temp
*.swp
*.swo
*~
.DS_Store

# IDE
.idea/
.vscode/
*.sublime-project
*.sublime-workspace

# Database
*.db
*.sqlite
*.sqlite3

# Process IDs
pids/
*.pid

# Results (optional - uncomment if you want to exclude)
# results/
# results-s/

# Keep templates and examples
!*.example
!config.ini.example

# API Keys and sensitive data
config.ini
credentials.json
.env
*.pem
*.key

# Backups
backup/
backups/
*.bak
*.backup
EOF

# Create config.ini.example
echo -e "\n${YELLOW}Creating config.ini.example...${NC}"
if [ -f "Daily/config.ini" ]; then
    sed -E 's/(api_key|api_secret|access_token|password|token|secret)\s*=.*/\1 = YOUR_\U\1_HERE/g' Daily/config.ini > Daily/config.ini.example
    echo -e "${GREEN}Created Daily/config.ini.example${NC}"
fi

# Stash current changes
echo -e "\n${YELLOW}Stashing current changes...${NC}"
git stash push -m "Stash before golden version preparation"

# Create new branch for golden version
echo -e "\n${YELLOW}Creating golden-version branch...${NC}"
git checkout -b golden-version-3.0

# Add all new files
echo -e "\n${YELLOW}Adding all files...${NC}"
git add -A

# Commit everything
echo -e "\n${YELLOW}Creating golden version commit...${NC}"
git commit -m "India TS 3.0 - Golden Version Release

This commit represents the production-ready state of India TS 3.0 with:

Major Features:
- Multi-user architecture with isolated contexts
- AI-powered market regime detection with learning
- Adaptive risk management based on market conditions
- Comprehensive automation from signal generation to execution
- Real-time learning with 30-minute prediction cycles
- Optimized job scheduling to prevent conflicts
- Enhanced dashboard with monitoring capabilities

Technical Improvements:
- Unified state management (trading_state.json)
- Market regime learning with outcome tracking
- Double scanning prevention
- ATR-based dynamic stop loss management
- Improved error handling and logging

Documentation:
- Comprehensive system documentation
- Component diagrams and data flow
- Quick reference guide
- Git workflow documentation

This is the golden version. All future changes should be made through Git branches."

# Tag the version
echo -e "\n${YELLOW}Creating version tags...${NC}"
git tag -a v3.0-golden -m "India TS 3.0 - Golden Version"

# Push to remote
echo -e "\n${YELLOW}Ready to push to remote repository${NC}"
echo -e "${RED}IMPORTANT: This will create a new branch 'golden-version-3.0'${NC}"
echo ""
echo "Next steps:"
echo "1. Push this branch: git push -u origin golden-version-3.0"
echo "2. Push tags: git push --tags"
echo "3. Create a pull request to merge into main/master"
echo "4. After merge, protect the main branch"
echo ""
echo -e "${GREEN}To set this as the default branch on GitHub/GitLab:${NC}"
echo "- Go to Settings → Branches"
echo "- Change default branch to 'golden-version-3.0' or merge to main"
echo "- Enable branch protection"

# Create protection file
echo "GOLDEN VERSION 3.0 - DO NOT EDIT LOCAL FILES DIRECTLY" > .GOLDEN_VERSION_LOCK
echo "All changes must be made through Git branches and pull requests" >> .GOLDEN_VERSION_LOCK
echo "Created on: $(date)" >> .GOLDEN_VERSION_LOCK

# Show final status
echo -e "\n${GREEN}Current branch: $(git branch --show-current)${NC}"
echo -e "${GREEN}Latest commit:${NC}"
git log --oneline -1

echo -e "\n${YELLOW}=== GOLDEN VERSION PREPARED ===${NC}"
echo -e "${RED}Remember: After pushing, DO NOT edit local files!${NC}"
EOF