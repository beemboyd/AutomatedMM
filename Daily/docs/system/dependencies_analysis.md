# Dependencies Analysis for India-TS/Daily Directory

## Summary
After analyzing all Python files in the Daily directory, I found that most files have dependencies outside the Daily folder. Here's the complete analysis:

## Files with External Dependencies

### 1. Files that modify sys.path to include parent directory (India-TS)
The following files add the parent India-TS directory to Python's sys.path:

**Files using `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))`:**
- `/analysis/Action_plan.py`
- `/portfolio/Prune_Portfolio.py`
- `/portfolio/Prune_Portfolio_SMA.py`
- `/portfolio/SL_watchdog.py`
- `/proposed_architecture/improved_place_orders_daily.py`
- `/scanners/Al_Brooks_Higher_Probability_Reversal.py`
- `/scanners/Al_Brooks_Higher_Probability_Reversal_Weekly.py`
- `/scanners/Al_Brooks_Inside_Bar_Patterns.py`
- `/scanners/Al_Brooks_vWAP_SMA20.py`
- `/scanners/Daily_improved.py`
- `/scanners/Long_Reversal_Daily.py`
- `/scanners/Short_Reversal_Daily.py`
- `/scanners/StrategyKV_C_Filter.py`
- `/trading/Double_Up_Position_Size.py`
- `/trading/One_ticker_sell.py`
- `/trading/place_orders_consolidated.py`
- `/trading/place_orders_daily.py`
- `/trading/place_orders_strategyc.py`
- `/utils/synch_zerodha_cnc_positions.py`
- `/utils/synch_zerodha_local.py`
- `/utils/update_orders_with_cnc.py`

**Files using `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`:**
- `/ML/keltner_channel_filter_analyzer.py`
- `/migrate_to_user_context.py`

### 2. Specific External Module Imports

#### From ML module (outside Daily):
- `/analysis/Action_plan.py`:
  - Imports: `from ML.Frequent_ticker_performance import FrequentTickerPerformanceAnalyzer`
  - Also adds ML directory to sys.path: `sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'ML'))`

### 3. Hardcoded Absolute Paths
Several files contain hardcoded absolute paths that reference the Daily directory:

- `/analysis/quick_market_summary.py`: `base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"`
- `/analysis/market_character_analyzer.py`: Default path `/Users/maverick/PycharmProjects/India-TS/Daily`
- `/analysis/trend_weakness_analyzer.py`: Default path `/Users/maverick/PycharmProjects/India-TS/Daily`
- `/analysis/market_character_analyzer_simple.py`: Default path `/Users/maverick/PycharmProjects/India-TS/Daily`
- `/analysis/risk_analysis.py`: Default path `/Users/maverick/PycharmProjects/India-TS/Daily`
- `/utils/rename_brooks_files.py`: `results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"`
- `/utils/brooks_reversal_scheduler.py`: 
  - Log file path: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_scheduler.log`
  - Script path: `/Users/maverick/PycharmProjects/India-TS/Daily/scripts/Al_Brooks_Higher_Probability_Reversal.py`
  - Working directory: `/Users/maverick/PycharmProjects/India-TS/Daily`

## Files Without External Dependencies
The following files appear to have no dependencies outside the Daily folder:
- `/loginz.py` - Only uses standard libraries and config.ini within Daily
- `/data/Sector.py`
- `/data/Sector_Fast.py`
- `/data/check_progress.py`
- `/ML/show_filtered_tickers.py`
- `/ML/fix_excel_dates.py`
- `/utils/reorganize.py`
- `/utils/run_daily_improved.py`
- `/utils/setup_log_rotation.py`
- `/analysis/Action_Plan_Score.py`
- `/proposed_architecture/user_context_manager.py`
- `/proposed_architecture/user_aware_state_manager.py`

## Recommendations

1. **For sys.path modifications**: Most files that modify sys.path are trying to import modules from the parent India-TS directory. This suggests these files may rely on shared utilities or modules that exist outside the Daily folder.

2. **For ML module dependency**: The Action_plan.py file specifically requires the ML module from the parent directory. This would need to be addressed if Daily is to be completely independent.

3. **For hardcoded paths**: These should be made relative or configurable to ensure portability.

4. **General approach**: To make the Daily folder completely independent, you would need to:
   - Copy any required modules from the parent directory into Daily
   - Update all imports to use relative paths within Daily
   - Replace hardcoded absolute paths with relative paths or configuration options
   - Ensure all data files and configurations are within the Daily directory