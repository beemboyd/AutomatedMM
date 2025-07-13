#!/bin/bash
# Simplified script to push US-TS to GitHub

echo "=== Simple US-TS GitHub Push ==="
echo ""

# Navigate to US-TS
cd /Users/maverick/PycharmProjects/US-TS || exit 1

# Initialize git if needed
if [ ! -d ".git" ]; then
    git init
    git remote add origin https://github.com/saivenkata1/India-June.git
fi

# Create basic .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.log
*.db
*.xlsx
*.csv
.env
config.ini
credentials.json
.DS_Store
backups/
Daily/results/*.xlsx
Daily/Detailed_Analysis/*.html
data/trading_state*.json
Current_Orders/
EOF

# Add all files
git add .

# Commit
git commit -m "Add US-TS Trading System

Complete US trading system with:
- Market regime analysis
- Trading strategies
- Risk management
- Dashboards
- Automated scanners"

# Push to main branch
git push origin main

echo "Done! Check https://github.com/saivenkata1/India-June"