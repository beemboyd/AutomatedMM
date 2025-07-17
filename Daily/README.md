# India-TS Daily Trading System

This is the main operational directory for the India-TS automated trading system.

## 📚 Documentation Quick Links

- **[Documentation Index](docs/DOCUMENTATION_INDEX.md)** - Complete index of all documentation
- **[Daily Workflow Guide](Documentation/DAILY_WORKFLOW.md)** - Step-by-step daily operations
- **[Dashboard Quick Reference](docs/dashboards/DASHBOARD_QUICK_REFERENCE.md)** - Dashboard commands and URLs
- **[Jobs Documentation](docs/system/INDIA_TS_JOBS_DOCUMENTATION.md)** - All automated jobs and schedules

## 🗂️ Directory Structure

```
Daily/
├── analysis/          # Analysis tools and market regime
├── bin/              # Executable scripts and SL watchdog management
├── config.ini        # Main configuration file
├── Current_Orders/   # User-specific order files
├── dashboards/       # Dashboard applications (DEPRECATED - see Market_Regime)
├── data/             # Data files and databases
├── Diagrams/         # Flow diagrams
├── Documentation/    # Detailed documentation
├── docs/             # Organized documentation
│   ├── automation/   # Automation reports and guides
│   ├── dashboards/   # Dashboard documentation
│   ├── guides/       # Pattern and tracker guides
│   └── system/       # System documentation and dependencies
├── Health/           # Job Manager Dashboard
├── logs/             # User-specific log files
├── Market_Regime/    # Market regime analysis and dashboards
├── pids/             # Process ID files
├── Plan/             # Daily plans and scores
├── portfolio/        # Portfolio management and SL watchdog
├── results/          # Scanner results (Excel files)
├── scanners/         # Market scanners
├── scheduler/        # LaunchAgent plist files
├── trading/          # Order placement and trading
└── utils/            # Utility scripts
```

## 🚀 Quick Start

1. **Check System Status**
   ```bash
   open http://localhost:5000  # Health Dashboard
   ```

2. **View Documentation Index**
   ```bash
   cat DOCUMENTATION_INDEX.md
   ```

3. **Follow Daily Workflow**
   ```bash
   cat Documentation/DAILY_WORKFLOW.md
   ```

## 🔑 Key Components

### Scanners
- **Al Brooks Scanner** - High probability reversal patterns
- **Reversal Scanner** - Long/short reversal detection
- **KC Pattern Scanner** - Keltner Channel patterns
- **G Pattern Master** - Advanced pattern recognition

### Trading
- **Order Placement** - Automated order execution
- **SL Watchdog** - Stop loss monitoring with volume anomaly detection
- **Position Management** - Real-time position tracking

### Analysis
- **Market Regime** - Market condition analysis
- **Action Plan** - Daily trading recommendations
- **Consolidated Score** - Pattern scoring system

### Dashboards
- Health Dashboard - http://localhost:5000
- Market Breadth - http://localhost:5001
- Enhanced Dashboard - http://localhost:8080

## 📊 Recent Updates

- **Volume Anomaly Detection** - Added exhaustion pattern warnings to SL Watchdog
- **Early Bird Category** - First appearance tracking in dashboards
- **KC Pattern Analysis** - Deep insights into KC_Breakout_Watch patterns
- **Market Regime Integration** - Dynamic stop loss adjustments

## 🛠️ Configuration

Main configuration file: `config.ini`

Key sections:
- `[DEFAULT]` - Trading parameters
- `[API_CREDENTIALS_*]` - User credentials
- `[VOLUME_ANOMALY]` - Anomaly detection settings
- `[REGIME_STOPS]` - Regime-based stop loss settings

## 📝 Logs

Logs are organized by user:
- `logs/<username>/` - User-specific logs
- `logs/` - System-wide logs

## 🆘 Support

- Check [Documentation Index](DOCUMENTATION_INDEX.md) for specific guides
- Review [Common Issues](../Diagrams/common_issues.md) for troubleshooting
- See [Daily Workflow](Documentation/DAILY_WORKFLOW.md) for operational guidance

---

*This is the active development directory. For system-wide documentation, see the root [Documentation](../Documentation/) folder.*