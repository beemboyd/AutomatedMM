# India-TS Daily Trading Documentation Hub

Welcome to the centralized documentation for the India-TS Daily Trading System. This is your one-stop resource for all system documentation, guides, and references.

## 🚀 Quick Start

- **New to the system?** Start with the [Quick Start Guide](QUICK_START_GUIDE.md)
- **Daily Operations** Follow the [Daily Trading Workflow](DAILY_WORKFLOW.md)
- **Having Issues?** Check the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

## 📚 Documentation Index

### Core System Documentation

| Document | Description |
|----------|-------------|
| [System Overview](SYSTEM_OVERVIEW.md) | Complete system architecture and components |
| [Daily Trading Workflow](DAILY_WORKFLOW.md) | Step-by-step daily operations guide |
| [Quick Reference](QUICK_REFERENCE.md) | Commands and shortcuts for daily use |

### 📊 Scanners & Analysis

| Component | Description |
|-----------|-------------|
| [Brooks Scanner Guide](scanners/brooks_scanner_guide.md) | Al Brooks reversal pattern scanner |
| [Reversal Scanner Guide](scanners/reversal_scanner_guide.md) | Long/Short reversal detection |
| [KC Pattern Scanner](scanners/kc_pattern_scanner_guide.md) | Keltner Channel pattern detection |
| [G Pattern Master](scanners/g_pattern_master_guide.md) | Advanced G pattern system |
| [Market Regime Analysis](analysis/market_regime_guide.md) | Market condition analysis |
| [Action Plan Generator](analysis/action_plan_guide.md) | Daily trading action plans |

### 💼 Trading & Portfolio Management

| Component | Description |
|-----------|-------------|
| [Order Placement](trading/order_placement_guide.md) | Automated order placement system |
| [Position Management](trading/position_management_guide.md) | Position tracking and management |
| [G Pattern Auto Trader](trading/g_pattern_auto_trader_guide.md) | Automated G pattern trading |
| **Stop Loss Management** | |
| [SL Watchdog Guide](portfolio/sl_watchdog_guide.md) | ATR-based trailing stop loss system |
| [Regime Stop Loss](portfolio/regime_stop_loss_guide.md) | Market regime-based stops |
| [Volume Anomaly Detection](portfolio/volume_anomaly_detection_guide.md) | Exhaustion pattern detection |

### 🖥️ Dashboards & Monitoring

| Component | Description |
|-----------|-------------|
| [Dashboard Overview](dashboards/dashboard_overview.md) | All dashboard systems |
| [Dashboard Quick Reference](dashboards/dashboard_quick_reference.md) | Quick commands |
| [Dashboard Startup Guide](dashboards/dashboard_startup_guide.md) | Starting dashboards |
| [Health Dashboard](dashboards/health_dashboard_guide.md) | System health monitoring |

### ⚙️ System Operations

| Component | Description |
|-----------|-------------|
| [Jobs Documentation](jobs/jobs_overview.md) | All LaunchAgent jobs |
| [Jobs Management](jobs/jobs_management_guide.md) | Managing scheduled tasks |
| [Backup & Restore](maintenance/backup_restore_guide.md) | System backup procedures |
| [Golden Version Setup](maintenance/golden_version_guide.md) | Golden version management |

### 🔧 Development & API

| Component | Description |
|-----------|-------------|
| [Zerodha Integration](api/zerodha_integration.md) | Broker API integration |
| [User Context Management](api/user_context_management.md) | Multi-user support |
| [Claude Instructions](development/claude_instructions.md) | AI assistant guidelines |
| [Git Workflow](development/git_workflow.md) | Version control practices |

### 📈 Flow Diagrams

| Flow | Description |
|------|-------------|
| [System Flow Overview](flows/system_overview_flow.md) | Complete system flow |
| [Scanner Flows](flows/scanner_flows.md) | All scanner flow diagrams |
| [Order Placement Flow](flows/order_placement_flow.md) | Order execution flow |
| [SL Watchdog Flow](flows/sl_watchdog_flow.md) | Stop loss monitoring flow |

## 🔍 Quick Links by Task

### Daily Operations
- [Start Scanners](scanners/scanner_startup_guide.md)
- [Place Orders](trading/order_placement_guide.md#daily-execution)
- [Monitor Positions](portfolio/sl_watchdog_guide.md#starting-watchdog)
- [Check Dashboards](dashboards/dashboard_quick_reference.md)

### Troubleshooting
- [Common Issues](TROUBLESHOOTING_GUIDE.md#common-issues)
- [API Errors](api/zerodha_integration.md#error-handling)
- [Job Failures](jobs/jobs_management_guide.md#troubleshooting)
- [Dashboard Issues](dashboards/dashboard_troubleshooting.md)

### Configuration
- [Config.ini Settings](configuration/config_guide.md)
- [User Setup](api/user_context_management.md#setup)
- [Scheduler Setup](jobs/scheduler_setup_guide.md)

## 📝 Documentation Standards

- **Markdown Format**: All docs use GitHub-flavored Markdown
- **Naming Convention**: lowercase with underscores (e.g., `scanner_guide.md`)
- **Updates**: Include date and version at top of significant changes
- **Examples**: Include practical examples and code snippets
- **Cross-references**: Link to related documentation

## 🆕 Recent Updates

- **2025-07-13**: Added Volume-Price Anomaly Detection to SL Watchdog
- **2025-07-11**: Updated KC Pattern Scanner with G Pattern integration
- **2025-07-10**: Enhanced Market Regime Analysis with confidence scoring
- **2025-07-09**: Added Dashboard Early Bird category

## 🤝 Contributing

When adding new documentation:
1. Place in appropriate subdirectory
2. Update this index
3. Follow naming conventions
4. Include in relevant flow diagrams
5. Update CLAUDE.md if it affects AI operations

---

*For system-wide documentation outside daily trading, see the [root Documentation folder](/Documentation/).*