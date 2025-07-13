# US-TS Market Regime Analysis Report

## Summary of Findings

### 1. Duplicate Dashboard Files

In `/Users/maverick/PycharmProjects/US-TS/Market_Regime/dashboard/`:

**Active Dashboard Files:**
- `regime_dashboard_8088_enhanced.py` - Actually runs on port 8090 (misleading filename)
- `health_check_visual.py` - Health monitoring dashboard
- `health_monitor_dashboard.py` - Another health monitoring dashboard
- `learning_dashboard_endpoint.py` - Learning progress dashboard

**Obsolete/Duplicate Files:**
- `regime_dashboard_8088.py` - Old version, runs on port 8088
- `regime_dashboard_enhanced_us.py.archived` - Original archived version

**Recommendation:** The naming is confusing. The file `regime_dashboard_8088_enhanced.py` actually runs on port 8090, not 8088. Consider renaming it to `regime_dashboard_8090_enhanced.py` for clarity.

### 2. Port References

Found the following port configurations:

**Port 8088:**
- Referenced in: `regime_dashboard_8088.py` (old dashboard)
- Also referenced in: `generate_health_report.py`, `health_check.py`, `learning/api_examples.py`

**Port 8089:**
- Referenced in README.md as the dashboard port (outdated documentation)

**Port 8090:**
- Actually used by: `regime_dashboard_8088_enhanced.py` (the current active dashboard)
- Also used by: `health_check_visual.py`, `health_monitor_dashboard.py`

**Recommendation:** Update all references to use port 8090 consistently, or choose a single port for the main dashboard.

### 3. Missing Modules

The following modules are imported in `market_regime_analyzer.py` but don't exist:
- `reversal_trend_scanner.py`
- `trend_strength_calculator.py`
- `market_regime_predictor.py`
- `trend_dashboard.py`

These appear to be from an older version or different project and are not present in the current US-TS codebase.

**Recommendation:** Either:
1. Comment out these imports if they're not being used
2. Remove `market_regime_analyzer.py` if it's obsolete (there's a newer `market_regime_analyzer_us.py`)

### 4. Documentation Issues

**README.md Issues:**
- States dashboard runs on port 8089, but it actually runs on port 8090
- References `regime_dashboard_enhanced_us.py` which is now archived

**US_MARKET_REGIME_SETUP.md Issues:**
- More accurate but still references the need for "Full Dashboard Implementation"
- The dashboard already exists but with a confusing filename

### 5. Current Working Configuration

Based on the analysis:
- **Main Dashboard:** `dashboard/regime_dashboard_8088_enhanced.py` (runs on port 8090)
- **Dashboard Runner:** `run_dashboard_us.py` correctly imports from `regime_dashboard_8088_enhanced`
- **Health Dashboard:** `health_check_visual.py` (launched by LaunchAgent)
- **Config Files:** Found in parent directory (`config.py`, `data_handler.py`)

### 6. Cleanup Recommendations

1. **Rename Files:**
   - `regime_dashboard_8088_enhanced.py` → `regime_dashboard_8090_enhanced.py`
   - Update `run_dashboard_us.py` import accordingly

2. **Remove Obsolete Files:**
   - `regime_dashboard_8088.py` (old version)
   - Consider removing `market_regime_analyzer.py` if `market_regime_analyzer_us.py` is the active version

3. **Update Documentation:**
   - Fix port references in README.md (8089 → 8090)
   - Update dashboard filename references
   - Remove references to missing modules

4. **Fix Import Issues:**
   - Either find and add the missing modules or remove the imports from `market_regime_analyzer.py`
   - Verify which analyzer is actually being used

5. **Consolidate Health Dashboards:**
   - There are two health monitoring dashboards (`health_check_visual.py` and `health_monitor_dashboard.py`)
   - Determine which one is primary and consider removing the duplicate

## File Status Summary

### Active and Working:
- `dashboard/regime_dashboard_8088_enhanced.py` (main dashboard, port 8090)
- `dashboard/health_check_visual.py` (health monitor)
- `run_dashboard_us.py` (dashboard runner)
- `market_regime_analyzer_us.py` (US-adapted analyzer)

### Obsolete/Duplicate:
- `dashboard/regime_dashboard_8088.py` (old dashboard)
- `dashboard/regime_dashboard_enhanced_us.py.archived` (archived)
- `market_regime_analyzer.py` (has missing imports, likely obsolete)

### Needs Review:
- `dashboard/health_monitor_dashboard.py` (duplicate health monitor?)
- `dashboard/learning_dashboard_endpoint.py` (purpose unclear)