# Daily Folder Reorganization Plan

## Proposed Structure

```
Daily/
├── config.ini                    # Keep at root
├── loginz.py                     # Keep at root
├── manage_watchdogs.sh          # Keep at root
├── start_watchdogs.sh           # Keep at root
├── stop_watchdogs.sh            # Keep at root
├── watchdog_status.sh           # Keep at root
├── migrate_to_user_context.py   # Keep at root
├── scanners/                    # All market scanning scripts
│   ├── Al_Brooks_Higher_Probability_Reversal.py
│   ├── Al_Brooks_Higher_Probability_Reversal_Weekly.py
│   ├── Al_Brooks_Inside_Bar_Patterns.py
│   ├── Al_Brooks_vWAP_SMA20.py
│   ├── Daily_improved.py
│   ├── Long_Reversal_Daily.py
│   ├── Short_Reversal_Daily.py
│   └── StrategyKV_C_Filter.py
├── trading/                     # Order management and execution
│   ├── place_orders_daily.py
│   ├── place_orders_consolidated.py
│   ├── place_orders_strategyc.py
│   ├── One_ticker_sell.py
│   └── Double_Up_Position_Size.py
├── portfolio/                   # Portfolio management
│   ├── SL_watchdog.py
│   ├── Prune_Portfolio.py
│   └── Prune_Portfolio_SMA.py
├── analysis/                    # Analysis and reporting
│   ├── Action_plan.py
│   ├── Action_Plan_Score.py
│   ├── market_character_analyzer.py
│   ├── market_character_analyzer_simple.py
│   ├── risk_analysis.py
│   ├── trend_weakness_analyzer.py
│   └── quick_market_summary.py
├── utils/                       # Utility scripts
│   ├── synch_zerodha_local.py
│   ├── synch_zerodha_cnc_positions.py
│   ├── update_orders_with_cnc.py
│   ├── setup_log_rotation.py
│   ├── rename_brooks_files.py
│   ├── brooks_reversal_scheduler.py
│   ├── run_daily_improved.py
│   ├── reorganize.py
│   ├── weekly_backup.sh
│   ├── check_backup_status.sh
│   ├── monitor_plist_changes.sh
│   ├── fix_brooks_plist.sh
│   └── cleanup_logs.sh
├── data/                        # Keep as is
├── logs/                        # Keep as is
├── pids/                        # Keep as is
├── reports/                     # Keep as is
├── results/                     # Keep as is
├── results-s/                   # Keep as is
├── scanner_files/               # Keep as is
├── Current_Orders/              # Keep as is
├── Detailed_Analysis/           # Keep as is
├── Plan/                        # Keep as is
├── ML/                          # Keep as is
├── scheduler/                   # Keep as is
├── archive_scripts/             # Keep as is
├── proposed_architecture/       # Keep as is
└── Diagrams/                    # Keep as is
```

## Import Updates Required

### For scripts in scanners/:
Change from:
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
To:
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

### For scripts in trading/, portfolio/, analysis/, utils/:
Same update as above - add one more parent directory level.

## Files that reference script paths:
1. scheduler/*.plist files - Update paths to scripts
2. manage_watchdogs.sh - Update script paths
3. start_watchdogs.sh - Update script paths
4. Shell scripts that call Python scripts

## Migration Steps:
1. Create new directories
2. Move files to appropriate directories
3. Update import statements in Python files
4. Update paths in scheduler plist files
5. Update paths in shell scripts
6. Test each component

## Benefits:
- Clear separation of concerns
- Easier to find specific functionality
- Better code organization
- Maintains all existing functionality