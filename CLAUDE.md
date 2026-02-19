# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Activity Logging
**IMPORTANT**: When making any changes to the India-TS system, you MUST update the activity log:
- Location: `/Users/maverick/PycharmProjects/India-TS/Daily/Activity.md`
- Format: Include date/time (IST), author (Claude/System), changes made, and impact
- Update BEFORE committing changes
- Include service names, file paths, and configuration changes

## Build/Test Commands
- Run full system test: `python test_system.py`
- Run backtest (unified interface): `python BT/backtest.py --mode [interactive|single|portfolio] --strategy strategy_name --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
- Run backtest with specific ticker: `python BT/backtest.py --mode single --strategy strategy_name --ticker TICKER`
- Run portfolio backtest: `python BT/backtest.py --mode portfolio --strategy strategy_name --ticker-file Ticker.xlsx`
- Run interactive backtest: `python BT/backtest.py` (will prompt for all parameters)
- Run test backtest: `python BT/backtest.py --mode portfolio --strategy strategy_name --test-tickers 5`
- Fix position inconsistencies: `python utils/cleanup_positions.py --include-zerodha --fix-inconsistencies`
- Reset MIS positions: `python utils/cleanup_mis_positions.py --reset-mis`
- Sync with broker positions: `python utils/cleanup_mis_positions.py --sync-broker`
- Remove specific position: `python utils/cleanup_mis_positions.py --remove-ticker TICKER`
- AMM dry run (verify config): `python -m TG.AMM.run --dry-run`
- AMM start engine: `python -m TG.AMM.run`
- AMM start engine with overrides: `python -m TG.AMM.run --base-qty 5000 --sample-interval 30 --product MIS`
- AMM monitor dashboard: `python -m TG.AMM.run --dashboard --mode monitor --port 7797`
- AMM config/admin dashboard: `python -m TG.AMM.run --dashboard --mode config --port 7796`
- AMM start from config file: `python -m TG.AMM.run --config-file TG/AMM/state/amm_config.json`

## System Startup & Token Management
**IMPORTANT - Daily Service Management:**
- **Before 9 AM (Pre-market setup)**: System automatically runs `./Daily/pre_market_setup_robust.sh` at 8:00 AM via cron
  - This starts all services fresh for the day with the current token
  - No manual intervention needed unless services fail
- **After 9 AM (Token refresh ONLY)**: Run `./Daily/refresh_token_services.sh`
  - Use ONLY when you refresh the API token after services are already running
  - This handles all token caching issues (process-level, Python cache, persistence files)
  - Kills ALL services and restarts them with the new token
- **Key Point**: You only need ONE script - pre_market for daily startup (automatic), refresh_token for token updates (manual)

## Code Style Guidelines
- **Formatting**: 4-space indentation, ~100 char line length
- **Imports**: Standard lib first, third-party libs second, local modules last
- **Naming**: snake_case for variables/functions, CamelCase for classes, UPPER_CASE for constants
- **Documentation**: Triple double-quote docstrings for modules, classes and functions
- **Error handling**: Use try/except with specific error messages and logging
- **Logging**: Use Python's logging module (not print statements)
- **Organization**: Maintain modular structure following directory organization
- **Testing**: Use mock_kiteconnect for testing instead of real API connections

## System Changes & Fixes
- **2026-02-19**: Added AMM (Automated Market Maker) stat-arb bot in `TG/AMM/`. Trades ratio mean-reversion between pairs sharing SPCENET as denominator (R1=TATAGOLD/SPCENET, R2=YESBANK/SPCENET). Multi-instrument XTS client (01MU07 account), rolling z-score signals, 2-leg entry/exit, stacking up to 3 positions per pair, target-only exit (no stop-loss). Dashboards: Monitor on 7797, Config/Admin on 7796. Files: `TG/AMM/{__init__,__main__,config,client,state,engine,run,dashboard}.py`.
- **2025-05-10**: Consolidated all backtesting functionality into a single unified script (backtest.py). This new script replaces the following older scripts which have been moved to the archive folder: run_kb_hh_sl.py, run_kb_hh_sl_interactive.py, run_backtest.py, run_backtest_optimizer.py, run_price_action_backtest.py, run_test_backtest.py, run_simplified_backtest.py, portfolio_backtest.py, and simple_portfolio_report.py. Also archived create_test_tickers.py and test_tickers.xlsx as they're no longer needed with the new consolidated backtest system. The consolidated script provides a single interface for all backtesting functionality with improved error handling, support for data caching, and enhanced reporting.
- **2025-05-07 14:00**: Added ticker_cooldown_hours (default: 2.0) to config.ini to prevent placing multiple orders for the same ticker within the specified time period. This addresses the issue with tickers like WELSPUNLIV and BANARISUG having multiple positions opened and closed in quick succession when they are stopped out and then reappear in scan results.
- **2025-05-07 11:40**: Identified manage_risk.py as obsolete and recommended removal since all risk management functionality has been integrated into position_watchdog.py. Created documentation explaining this change in Diagrams/delete_manage_risk.md.
- **2025-05-07 11:25**: Modified place_orders.py to ONLY place new orders and NOT close positions when tickers drop out of scan results. Fixed issue where tickers like AGI and JAGSNPHARM would be closed prematurely when they disappeared from scan results, causing duplicate orders and position tracking confusion. Position closing now happens exclusively through position_watchdog.py (stop losses) or EOD closure from Zerodha.
- **2025-05-07 10:00**: Fixed scan_market.py to properly handle GapPercent values. Added safe extraction of gap percentage data with proper exception handling to prevent KeyError(0) during signal processing. Previously, this was causing errors like "Error processing TICKER: 0" in the logs.
- **2025-05-05**: Fixed position_watchdog.py to track and set stop losses for all positions regardless of daily_tickers list status. Previously, positions not in the daily_tickers list were being skipped with "likely a closed" messages.
- **2025-05-05**: Added proper daily state reset logic to state_manager.py to automatically clear all MIS positions at the start of a new trading day and ensure consistent state tracking.
- **2025-05-05**: Added broker-state synchronization for position_watchdog.py that verifies positions exist with broker on startup, removing "ghost positions" from previous sessions.
- **2025-05-05**: Improved service restart handling in state_manager.py to clear MIS positions when the service is restarted, preventing old positions from reappearing.
- **2025-05-05**: Added explicit product_type tracking to position state management to differentiate between MIS (intraday) and CNC (delivery) positions.
- **2025-05-05**: Force position state cleanup after 10 minutes of inactivity to handle service restarts on the same trading day.
- **2025-05-05**: Removed legacy state files (position_data.json, gttz_gtt_tracker.json, long_positions.txt, short_positions.txt, daily_ticker_tracker.json) and related code, fully migrating to the consolidated trading_state.json system.
- **2025-05-05**: Updated risk_management.py to work directly with the state_manager without legacy compatibility layers.
- **2025-05-05**: Fixed place_orders.py to load position data directly from the state_manager instead of legacy state files, preventing ghost position errors.
- **2025-05-05**: Enhanced the state reset logic to completely purge all MIS positions at the start of each trading day.
- **2025-05-05**: Created cleanup_mis_positions.py utility to provide easy command-line tools for managing positions and cleaning state.
- **2025-07-22**: Fixed VSR tracker real-time data updates by implementing cache expiration in VSR_Momentum_Scanner.py. The DataCache now has TTL-based expiration (1 min for minute data, 1 hour for hourly data) to ensure real-time updates instead of showing static/frozen data throughout the day. See Daily/docs/VSR_TRACKER_REALTIME_FIX.md for full details.
- **2025-07-23**: Implemented Git-based plist management system to prevent accidental cross-project contamination. All India-TS plists are now backed up in Daily/scheduler/plists/ with install/validate scripts. This prevents issues like the Long/Short Reversal Daily jobs being accidentally archived when editing US-TS system.

## BT Module Guidelines
- New strategies must inherit from BaseStrategy in strategies/base.py
- Add new strategies to AVAILABLE_STRATEGIES in strategies/__init__.py
- Include strategy parameters in bt_config.json
- Use cached data from BT/data/ directory when possible to avoid API calls
- Always verify parameters in _set_default_params method
- Include detailed docstrings for strategy entry/exit logic
- Use the unified backtest.py script for all backtesting needs
- The BacktestEngine class supports both single ticker and portfolio backtesting
- For debugging and development, use the interactive mode: `python BT/backtest.py`
- Archived backtesting scripts are available in the BT/archive/ directory for reference

Always verify changes with individual strategy tests before committing. Be careful with Zerodha API interactions to avoid unintended orders.

## AMM Module Guidelines (TG/AMM/)
- AMM is a ratio mean-reversion stat-arb bot living in `TG/AMM/`
- Uses XTS account **01MU07** (separate from TollGate's 01MU01 and Grid's 01MU06)
- Pair config is defined in `PairConfig` dataclass in `config.py` — each pair has numerator/denominator tickers, entry_sd threshold, and trade percentages
- Engine samples ratios every `sample_interval` (default 60s) and computes rolling mean/SD over `rolling_window` (default 30) samples
- No trading occurs during `warmup_samples` (default 30) collection period (~30 min at 60s intervals)
- Positions are 2-legged (numerator + denominator) with independent fill tracking per leg
- State persists to `TG/AMM/state/amm_state.json` (atomic writes)
- Dashboards: Monitor on **7797**, Config/Admin on **7796**
- XTS credentials are in `AMMConfig` dataclass defaults — do not hardcode elsewhere
- WebSocket market data with REST fallback (30s staleness threshold)
- Session management: 30-min proactive refresh + 5-error reactive refresh (same pattern as TollGate)

## Git Workflow - IMPORTANT
**COMMIT AND PUSH AFTER EVERY CHANGE**: When making any code modifications, you MUST:
1. Stage the changed files: `git add <modified_files>`
2. Commit with a descriptive message: `git commit -m "Description of change"`
3. Push to remote immediately: `git push origin master`

This ensures:
- No work is lost
- Changes are immediately backed up
- Team members have access to latest updates
- Easy rollback if issues arise

Example workflow:
```bash
# After modifying a file
git add Daily/scanners/modified_scanner.py
git commit -m "Fix scanner logic for handling edge cases"
git push origin master
```

For multiple related changes, commit them together but push immediately after.

## Plist Management - CRITICAL
**Namespace Separation**: All India-TS scheduled jobs MUST use the `com.india-ts.*` namespace to prevent conflicts with US-TS jobs.

**Git-Based Backup System**: 
1. All plists are backed up in `Daily/scheduler/plists/`
2. Use `python Daily/scheduler/install_plists.py` to install/restore all plists
3. Use `python Daily/scheduler/validate_plists.py` to verify plist integrity
4. Never manually edit plists in LaunchAgents without updating the backup

**Adding New Scheduled Jobs**:
1. Create plist with correct namespace: `com.india-ts.your_job_name`
2. Save to `Daily/scheduler/plists/`
3. Run install script to deploy
4. Update `PLIST_MASTER_SCHEDULE.md`
5. Add to job manager dashboard if needed

**Important**: When working on US-TS, NEVER modify files with `com.india-ts.*` namespace. Similarly, when working on India-TS, NEVER modify files with `com.us-ts.*` namespace.