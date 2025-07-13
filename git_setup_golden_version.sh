#!/bin/bash

# India TS 3.0 - Git Setup Script
# This script will initialize Git and push the current state as the golden version
# After this, all changes should be made on Git, not locally

echo "====================================="
echo "India TS 3.0 - Git Golden Version Setup"
echo "====================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "config.ini" ] || [ ! -d "Daily" ]; then
    echo -e "${RED}Error: This script must be run from the India-TS root directory${NC}"
    exit 1
fi

# Check if Git is already initialized
if [ -d ".git" ]; then
    echo -e "${YELLOW}Git is already initialized in this directory${NC}"
    echo "Current Git status:"
    git status
    echo ""
    read -p "Do you want to continue and force push to remote? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "Initializing Git repository..."
    git init
fi

# Create comprehensive .gitignore if it doesn't exist
echo "Creating .gitignore file..."
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
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Logs
*.log
logs/
*.log.*

# API Keys and Credentials
config.ini
credentials.json
.env
*.pem
*.key

# User-specific data
trading_state.json
*_state.json
user_data/

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

# Backups
backup/
backups/
*.bak
*.backup

# Process IDs
pids/
*.pid

# Results cache
.cache/
cache/

# But keep these important files
!.gitignore
!README.md
!requirements.txt
!config.ini.example
EOF

# Create config.ini.example with sanitized data
echo "Creating config.ini.example..."
if [ -f "config.ini" ]; then
    # Create a sanitized version of config.ini
    sed -E 's/(api_key|api_secret|access_token|password|token)\s*=.*/\1 = YOUR_\U\1_HERE/g' config.ini > config.ini.example
    echo -e "${GREEN}Created config.ini.example with sanitized credentials${NC}"
fi

# Create README if it doesn't exist
if [ ! -f "README.md" ]; then
    echo "Creating README.md..."
    cat > README.md << 'EOF'
# India TS 3.0 - Automated Trading System

**Version**: 3.0  
**Status**: Golden Version (Production)

## Overview

India TS 3.0 is a sophisticated multi-user automated trading system with adaptive market regime detection, machine learning-based predictions, and comprehensive risk management.

## Important Notice

This repository contains the golden version of India TS 3.0. 

**DO NOT MAKE CHANGES DIRECTLY TO LOCAL FILES**

All development should be done through Git branches and merged after testing.

## Setup Instructions

1. Clone the repository
2. Copy `config.ini.example` to `config.ini`
3. Add your API credentials to `config.ini`
4. Install dependencies: `pip install -r requirements.txt`
5. Run setup verification: `python test_system.py`

## Documentation

See the `Documentation/` folder for comprehensive system documentation:
- `INDIA_TS_3.0_OVERVIEW.md` - System overview and architecture
- `INDIA_TS_3.0_QUICK_REFERENCE.md` - Quick command reference
- `INDIA_TS_3.0_FEATURE_DETAILS.md` - Detailed feature documentation

## Support

For issues or questions, please create an issue in the Git repository.

---
*Golden Version established on: $(date)*
EOF
fi

# Create requirements.txt if it doesn't exist
if [ ! -f "requirements.txt" ]; then
    echo "Creating requirements.txt..."
    cat > requirements.txt << 'EOF'
# India TS 3.0 Requirements
pandas>=1.3.0
numpy>=1.21.0
openpyxl>=3.0.9
kiteconnect>=4.0.0
pytz>=2021.3
python-dateutil>=2.8.2
scikit-learn>=0.24.2
flask>=2.0.0
requests>=2.26.0
configparser>=5.0.2
EOF
fi

# Add all files to Git
echo -e "\n${YELLOW}Adding all files to Git...${NC}"
git add -A

# Create initial commit
echo -e "\n${YELLOW}Creating golden version commit...${NC}"
git commit -m "India TS 3.0 - Golden Version

This commit represents the production-ready state of India TS 3.0 with:
- Multi-user architecture with isolated contexts
- AI-powered market regime detection
- Adaptive risk management
- Comprehensive automation from signal to execution
- Real-time learning with 30-minute prediction cycles
- Optimized job scheduling
- Enhanced dashboard and monitoring

All future changes should be made through Git branches."

# Create tags
echo -e "\n${YELLOW}Creating version tags...${NC}"
git tag -a v3.0 -m "India TS 3.0 - Golden Version"
git tag -a golden-version -m "Golden Version - Do not modify local files"

# Show current status
echo -e "\n${GREEN}Git repository is ready!${NC}"
echo "Current status:"
git status

echo -e "\n${YELLOW}=== NEXT STEPS ===${NC}"
echo "1. Add your remote repository:"
echo "   git remote add origin YOUR_GIT_REPO_URL"
echo ""
echo "2. Push everything to remote:"
echo "   git push -u origin main"
echo "   git push --tags"
echo ""
echo "3. Set up branch protection on Git hosting service"
echo ""
echo "4. Create a development branch for future work:"
echo "   git checkout -b development"
echo ""
echo -e "${RED}IMPORTANT: After pushing, DO NOT modify local files directly!${NC}"
echo "All changes should be made in Git branches and merged back."

# Create a lock file to remind not to edit
echo "GOLDEN VERSION - DO NOT EDIT LOCAL FILES" > .GOLDEN_VERSION_LOCK

echo -e "\n${GREEN}Setup complete!${NC}"
EOF