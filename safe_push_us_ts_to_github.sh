#!/bin/bash
# Safe script to push US-TS to GitHub without altering the golden local copy
# This script creates a temporary copy, removes sensitive files, then pushes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
US_TS_SOURCE="/Users/maverick/PycharmProjects/US-TS"
TEMP_DIR="/tmp/us_ts_github_$(date +%Y%m%d_%H%M%S)"
REPO_URL="https://github.com/saivenkata1/India-June.git"
BRANCH_NAME="us-ts-system"

echo -e "${GREEN}=== Safe US-TS GitHub Push (Preserving Golden Copy) ===${NC}"
echo -e "Source (Golden Copy): ${BLUE}${US_TS_SOURCE}${NC}"
echo -e "Temporary Location: ${BLUE}${TEMP_DIR}${NC}"
echo -e "Repository: ${BLUE}${REPO_URL}${NC}"
echo ""

# Step 1: Create temporary directory
echo -e "${YELLOW}Step 1: Creating temporary working directory...${NC}"
mkdir -p "$TEMP_DIR"

# Step 2: Copy US-TS to temporary location (excluding sensitive files)
echo -e "${YELLOW}Step 2: Copying US-TS to temporary location (excluding sensitive files)...${NC}"
rsync -av --progress \
    --exclude='.git' \
    --exclude='config.ini' \
    --exclude='.env' \
    --exclude='credentials.json' \
    --exclude='*_credentials.json' \
    --exclude='*.log' \
    --exclude='logs/' \
    --exclude='*.db' \
    --exclude='*.pickle' \
    --exclude='*.h5' \
    --exclude='backups/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='data/trading_state*.json' \
    --exclude='data/positions*.json' \
    --exclude='Current_Orders/' \
    --exclude='Daily/results/*.xlsx' \
    --exclude='Daily/Detailed_Analysis/*.html' \
    --exclude='Market_Regime/regime_history.db' \
    --exclude='Market_Regime/learning/learning_outcomes.db' \
    --exclude='Market_Regime/predictions.db' \
    "$US_TS_SOURCE/" "$TEMP_DIR/"

# Step 3: Create sanitized config examples
echo -e "${YELLOW}Step 3: Creating sanitized configuration examples...${NC}"

# Create config.ini.example
cat > "$TEMP_DIR/config.ini.example" << 'EOF'
[DEFAULT]
# Rename this file to config.ini and fill in your credentials

[kite]
api_key = YOUR_API_KEY_HERE
api_secret = YOUR_API_SECRET_HERE
user_id = YOUR_USER_ID_HERE
password = YOUR_PASSWORD_HERE
pin = YOUR_PIN_HERE

[paths]
data_dir = ./data
logs_dir = ./logs
results_dir = ./Daily/results

[trading]
capital = 1000000
max_positions = 10
position_size = 100000

[market_hours]
start_time = 09:15
end_time = 15:30
timezone = Asia/Kolkata
EOF

# Create .env.example
cat > "$TEMP_DIR/.env.example" << 'EOF'
# Environment variables
# Rename this file to .env and fill in your values

# API Configuration
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here

# Database
DB_PATH=./data/trading.db

# Debug Mode
DEBUG=False
EOF

# Step 4: Create comprehensive .gitignore
echo -e "${YELLOW}Step 4: Creating comprehensive .gitignore...${NC}"
cat > "$TEMP_DIR/.gitignore" << 'EOF'
# Sensitive Configuration
config.ini
.env
credentials.json
*_credentials.json
*.pem
*.key

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
build/
dist/
*.egg-info/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
*.log
logs/
*.log.*
log/

# Data files
*.xlsx
*.xls
*.csv
*.db
*.sqlite
*.pickle
*.pkl
*.h5
*.hdf5

# Large files
*.pdf
*.zip
*.tar.gz
*.rar
*.7z

# Trading Data
data/trading_state*.json
data/positions*.json
data/historical/
data/cache/
cache/
Current_Orders/
results_archive/

# Backups
backups/
*.backup
*.bak
*.tmp
*.temp

# Output files
Daily/results/*
!Daily/results/.gitkeep
Daily/Detailed_Analysis/*.html
!Daily/Detailed_Analysis/.gitkeep
Market_Regime/breadth_data/*.json
!Market_Regime/breadth_data/.gitkeep

# Keep important files
!requirements.txt
!README.md
!.gitignore
!config.ini.example
!.env.example
EOF

# Step 5: Create comprehensive README
echo -e "${YELLOW}Step 5: Creating comprehensive README...${NC}"
cat > "$TEMP_DIR/README.md" << 'EOF'
# US-TS Trading System

A comprehensive automated trading system for US markets with real-time analysis, risk management, and machine learning capabilities.

## ⚠️ Important Notice

This repository contains the public version of the US-TS trading system. Sensitive configuration files, API credentials, and proprietary data have been removed for security reasons.

## 🚀 Features

### Market Analysis
- **Market Regime Detection**: ML-based classification of market conditions
- **Real-time Monitoring**: Continuous market state analysis
- **Sector Rotation Analysis**: Track sector performance and rotations
- **Technical Indicators**: Comprehensive technical analysis tools

### Trading Strategies
- **Al Brooks Patterns**: Price action pattern recognition
- **Reversal Strategies**: Long and short reversal detection
- **Trend Following**: Multiple trend-based strategies
- **Risk Management**: Automated stop-loss and position sizing

### Dashboards & Monitoring
- **Market Regime Dashboard**: http://localhost:8090
- **Health Check Dashboard**: http://localhost:7089
- **Real-time Updates**: WebSocket-based live data
- **Performance Analytics**: Track strategy performance

### Automation
- **Scheduled Scanners**: Automated market scanning
- **Position Management**: Automatic order placement and monitoring
- **Risk Controls**: Real-time risk management
- **LaunchAgent Integration**: macOS service management

## 📁 Project Structure

```
US-TS/
├── Daily/                      # Daily trading operations
│   ├── scripts/               # Trading scripts and scanners
│   ├── results/               # Scan results (gitignored)
│   ├── logs/                  # System logs (gitignored)
│   └── Detailed_Analysis/     # Detailed reports
│
├── Market_Regime/             # Market regime analysis system
│   ├── dashboard/             # Web dashboards
│   ├── models/                # Machine learning models
│   ├── learning/              # Learning and adaptation system
│   └── predictions/           # Prediction outputs
│
├── data/                      # Data storage (mostly gitignored)
│   ├── Ticker.xlsx           # Stock universe
│   └── config/               # Configuration files
│
├── launchd/                   # macOS service configurations
└── utils/                     # Utility scripts
```

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.11+
- macOS (for LaunchAgent scheduling)
- Zerodha Kite Connect API access

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/saivenkata1/India-June.git
   cd India-June/US-TS
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure credentials**
   ```bash
   # Copy example files
   cp config.ini.example config.ini
   cp .env.example .env
   
   # Edit with your credentials
   nano config.ini
   ```

5. **Initialize databases**
   ```bash
   python Market_Regime/initialize_db.py
   ```

6. **Start dashboards**
   ```bash
   # Market Regime Dashboard
   python Market_Regime/run_dashboard_us.py
   
   # Health Check Dashboard
   python Market_Regime/dashboard/health_check_visual.py
   ```

## 🔒 Security Notes

- **Never commit** credentials or API keys
- Use environment variables for sensitive data
- Keep your `config.ini` file secure
- Regularly rotate API keys
- Monitor access logs

## 📊 Data Requirements

The system expects:
- Real-time market data via Kite Connect API
- Historical price data for backtesting
- Ticker universe in `data/Ticker.xlsx`

## 🤝 Contributing

This is a private trading system. Contributions are not accepted.

## 📝 License

Proprietary - All rights reserved.

## ⚡ Quick Start

After setup, you can:
1. Access dashboards at http://localhost:8090 and http://localhost:7089
2. Run manual scans: `python Daily/scripts/Al_Brooks_Higher_Probability_Reversal.py`
3. Check system status: `launchctl list | grep usts`

## 🔧 Troubleshooting

- **Dashboard not accessible**: Check if process is binding to 0.0.0.0
- **Scanner failures**: Verify API credentials in config.ini
- **Database errors**: Ensure write permissions in data directories

## 📚 Documentation

Additional documentation available in:
- `/Documentation` - System documentation
- `/Diagrams` - Flow diagrams and architecture
- Individual script docstrings

---

**Note**: This is a sophisticated trading system. Ensure you understand the risks involved in automated trading before deployment.
EOF

# Step 6: Create requirements.txt if it doesn't exist
if [ ! -f "$TEMP_DIR/requirements.txt" ]; then
    echo -e "${YELLOW}Creating requirements.txt...${NC}"
    cat > "$TEMP_DIR/requirements.txt" << 'EOF'
# Core Dependencies
pandas>=1.5.0
numpy>=1.23.0
matplotlib>=3.5.0
seaborn>=0.12.0
scikit-learn>=1.1.0
scipy>=1.9.0

# Trading APIs
kiteconnect>=4.0.0

# Web Framework
flask>=2.2.0
flask-cors>=3.0.10

# Database
sqlite3

# Technical Analysis
ta>=0.10.0
talib>=0.4.25

# Data Processing
openpyxl>=3.0.10
xlsxwriter>=3.0.3
yfinance>=0.2.0

# Utilities
python-dotenv>=0.21.0
requests>=2.28.0
pytz>=2022.6
schedule>=1.1.0

# Logging and Monitoring
colorlog>=6.7.0

# Machine Learning
joblib>=1.2.0
xgboost>=1.7.0
lightgbm>=3.3.0

# Visualization
plotly>=5.11.0
dash>=2.7.0
EOF
fi

# Step 7: Initialize git repository
echo -e "${YELLOW}Step 7: Initializing git repository...${NC}"
cd "$TEMP_DIR"
git init
git remote add origin "$REPO_URL"

# Step 8: Create initial commit
echo -e "${YELLOW}Step 8: Creating initial commit...${NC}"
git add .
git commit -m "Add US-TS Trading System (Public Version)

This commit contains the US-TS trading system with:
- Market regime analysis and prediction
- Al Brooks pattern recognition
- Trading strategies and scanners
- Risk management systems
- Web dashboards for monitoring
- Automated scheduling via LaunchAgents

Note: Sensitive files (credentials, databases, logs) have been excluded.
Configuration examples are provided as .example files.

Repository structure:
- Daily/: Daily trading operations and scanners
- Market_Regime/: ML-based market analysis
- data/: Data storage (excluded from commits)
- utils/: Utility scripts and tools

Setup instructions in README.md"

# Step 9: Show what will be pushed
echo -e "${YELLOW}Step 9: Summary of files to be pushed...${NC}"
echo "Total files: $(git ls-files | wc -l)"
echo ""
echo "Top-level structure:"
git ls-files | cut -d'/' -f1 | sort | uniq -c | sort -rn | head -20

# Step 10: Confirm before pushing
echo -e "\n${YELLOW}Ready to push to GitHub${NC}"
echo -e "Repository: ${BLUE}${REPO_URL}${NC}"
echo -e "Branch: ${BLUE}${BRANCH_NAME}${NC}"
echo -e "Total size: $(du -sh . | cut -f1)"
echo ""
read -p "Do you want to proceed with the push? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create and push to branch
    git checkout -b "$BRANCH_NAME"
    
    echo -e "\n${YELLOW}Pushing to GitHub...${NC}"
    if git push -u origin "$BRANCH_NAME"; then
        echo -e "\n${GREEN}✅ SUCCESS! US-TS pushed to GitHub${NC}"
        echo -e "Repository: ${BLUE}${REPO_URL}${NC}"
        echo -e "Branch: ${BLUE}${BRANCH_NAME}${NC}"
        echo -e "\n${YELLOW}Next steps:${NC}"
        echo "1. Visit: https://github.com/saivenkata1/India-June/tree/${BRANCH_NAME}"
        echo "2. Review the files online"
        echo "3. Create a Pull Request if needed"
    else
        echo -e "\n${RED}❌ Push failed!${NC}"
        echo "The temporary copy is preserved at: ${TEMP_DIR}"
        echo "You can manually push later by:"
        echo "  cd ${TEMP_DIR}"
        echo "  git push -u origin ${BRANCH_NAME}"
        exit 1
    fi
else
    echo -e "\n${YELLOW}Push cancelled. Temporary copy preserved at:${NC}"
    echo "${TEMP_DIR}"
fi

echo -e "\n${GREEN}Your local golden copy at ${US_TS_SOURCE} remains unchanged.${NC}"

# Cleanup option
echo ""
read -p "Do you want to remove the temporary copy? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$TEMP_DIR"
    echo -e "${GREEN}Temporary copy removed.${NC}"
else
    echo -e "${YELLOW}Temporary copy preserved at: ${TEMP_DIR}${NC}"
fi