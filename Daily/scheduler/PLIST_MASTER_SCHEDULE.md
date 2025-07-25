# Master Plist Schedule Documentation

Generated on: 2025-07-23 08:11:44  
Last Updated: 2025-07-23 14:50:00

## Overview

This document contains a comprehensive list of all scheduled jobs (plist files) in the system,
organized by project. This helps manage plist changes and avoid conflicts between projects.

## Plist Management System

**Git-Based Backup Location:** `Daily/scheduler/plists/`

**Management Scripts:**
- `python Daily/scheduler/install_plists.py` - Install/restore all India-TS plists from backup
- `python Daily/scheduler/validate_plists.py` - Validate plist integrity and namespace compliance

**Namespace Separation:**
- India-TS jobs MUST use: `com.india-ts.*`
- US-TS jobs MUST use: `com.us-ts.*`

**Important:** Always update the backup copy in `Daily/scheduler/plists/` when modifying any plist file

---

## India-TS Jobs

**Total Jobs:** 29

**Timezone:** Asia/Kolkata


| Job Name | Schedule | Script/Program | Status |
|----------|----------|----------------|--------|
| consolidated_score | 09:00 (Mon-Fri) | Action_Plan_Score.py | ⏸️ On Schedule |
| daily_action_plan | 08:30 (Mon-Fri) | Action_plan.py | ✅ Active |
| fix_plists_on_startup | Every 86400 seconds | fix_brooks_plist.sh | ✅ Active |
| g_pattern_master_tracker | 09:15 (Mon-Fri), 10:15 (Mon-Fri), 11:15 (Mon-Fri), 12:15 (Mon-Fri), 13:15 (Mon-Fri), 14:15 (Mon-Fri), 15:15 (Mon-Fri) | G_Pattern_Master_Tracker.py | ⏸️ On Schedule |
| health_dashboard | Unknown | dashboard_health_check.py | ✅ Active |
| kc_g_pattern_scanner |  | KC_Upper_Limit_Trending.py | ⏸️ On Schedule |
| kc_lower_limit_trending | 09:15 (Mon-Fri), 10:15 (Mon-Fri), 11:15 (Mon-Fri), 12:15 (Mon-Fri), 13:15 (Mon-Fri), 14:15 (Mon-Fri), 15:15 (Mon-Fri) | KC_Lower_Limit_Trending.py | ⏸️ On Schedule |
| kc_lower_limit_trending_fno | 09:00 (Mon-Fri), 10:00 (Mon-Fri), 11:00 (Mon-Fri), 12:00 (Mon-Fri), 13:00 (Mon-Fri), 14:00 (Mon-Fri), 15:00 (Mon-Fri) | Sai | ⏸️ On Schedule |
| kc_upper_limit_trending | 09:10 (Mon-Fri), 10:10 (Mon-Fri), 11:10 (Mon-Fri), 12:10 (Mon-Fri), 13:10 (Mon-Fri), 14:10 (Mon-Fri), 15:10 (Mon-Fri) | KC_Upper_Limit_Trending.py | ⏸️ On Schedule |
| kc_upper_limit_trending_fno | 09:00 (Mon-Fri), 10:00 (Mon-Fri), 11:00 (Mon-Fri), 12:00 (Mon-Fri), 13:00 (Mon-Fri), 14:00 (Mon-Fri), 15:00 (Mon-Fri) | Sai | ⏸️ On Schedule |
| long_reversal_daily | 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri) | Long_Reversal_Daily.py | ⏸️ On Schedule |
| market_breadth_dashboard | Unknown | market_breadth_dashboard.py | ✅ Active |
| market_breadth_scanner | 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri) | Market_Breadth_Scanner.py | ⏸️ On Schedule |
| market_regime_analysis | 08:30 (Mon-Fri), 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri) | market_regime_analyzer.py | ⏸️ On Schedule |
| market_regime_analyzer_5min | Every 300 seconds | run_regime_analyzer_5min.sh | ⏸️ On Schedule |
| market_regime_daily_metrics |  | calculate_daily_metrics.py | ⏸️ On Schedule |
| market_regime_dashboard | Unknown | dashboard_enhanced.py | ✅ Active |
| outcome_resolver |  | outcome_resolver.py | ⏸️ On Schedule |
| short_reversal_daily | 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri) | Short_Reversal_Daily.py | ⏸️ On Schedule |
| sl_watchdog_start | 09:15 (Mon-Fri) | start_all_sl_watchdogs.py | ⏸️ On Schedule |
| sl_watchdog_stop | 15:30 (Mon-Fri) | true | ⏸️ On Schedule |
| strategyc_filter | 09:45 (Mon-Fri), 11:45 (Mon-Fri), 13:45 (Mon-Fri), 16:15 (Mon-Fri) | StrategyC_Auto.py | ⏸️ On Schedule |
| synch_zerodha_local | 09:15 (Mon-Fri), 09:30 (Mon-Fri), 09:45 (Mon-Fri), 10:00 (Mon-Fri), 10:15 (Mon-Fri), 10:30 (Mon-Fri), 10:45 (Mon-Fri), 11:00 (Mon-Fri), 11:15 (Mon-Fri), 11:30 (Mon-Fri), 11:45 (Mon-Fri), 12:00 (Mon-Fri), 12:15 (Mon-Fri), 12:30 (Mon-Fri), 12:45 (Mon-Fri), 13:00 (Mon-Fri), 13:15 (Mon-Fri), 13:30 (Mon-Fri), 13:45 (Mon-Fri), 14:00 (Mon-Fri), 14:15 (Mon-Fri), 14:30 (Mon-Fri), 14:45 (Mon-Fri), 15:00 (Mon-Fri), 15:15 (Mon-Fri), 15:30 (Mon-Fri) | --force | ⏸️ On Schedule |
| vsr_tracker_enhanced | 09:15 (Mon-Fri) | vsr_tracker_service_enhanced.py | ⏸️ On Schedule |
| vsr_dashboard | 09:15 (Mon-Fri) | vsr_tracker_dashboard.py | ⏸️ On Schedule |
| vsr_shutdown | 15:30 (Mon-Fri) | stop_vsr_services.py | ⏸️ On Schedule |
| short_momentum_tracker | 09:15 (Mon-Fri) | short_momentum_tracker_service.py | ⏸️ On Schedule |
| short_momentum_dashboard | 09:15 (Mon-Fri) | short_momentum_dashboard.py | ⏸️ On Schedule |
| weekly_backup | 03:00 (Sun) | weekly_backup.sh | ⏸️ On Schedule |

---

## US-TS Jobs

**Total Jobs:** 11

**Timezone:** US/Eastern


| Job Name | Schedule | Script/Program | Status |
|----------|----------|----------------|--------|
| health_dashboard | Unknown | health_check_visual.py | ✅ Active |
| long_reversal_daily | 09:15 (Fri, Mon, Sat, Thu, Tue, Wed), 09:45 (Fri, Mon, Sat, Thu, Tue, Wed), 10:15 (Fri, Mon, Sat, Thu, Tue, Wed), 10:45 (Fri, Mon, Sat, Thu, Tue, Wed), 11:15 (Fri, Mon, Sat, Thu, Tue, Wed), 11:45 (Fri, Mon, Sat, Thu, Tue, Wed), 12:15 (Fri, Mon, Sat, Thu, Tue, Wed), 12:45 (Fri, Mon, Sat, Thu, Tue, Wed), 13:15 (Fri, Mon, Sat, Thu, Tue, Wed), 13:45 (Fri, Mon, Sat, Thu, Tue, Wed), 14:15 (Fri, Mon, Sat, Thu, Tue, Wed), 14:45 (Fri, Mon, Sat, Thu, Tue, Wed), 15:15 (Fri, Mon, Sat, Thu, Tue, Wed), 15:45 (Fri, Mon, Sat, Thu, Tue, Wed), 16:15 (Fri, Mon, Sat, Thu, Tue, Wed), 16:45 (Fri, Mon, Sat, Thu, Tue, Wed), 17:15 (Fri, Mon, Sat, Thu, Tue, Wed) | Long_Reversal_Daily_US.py | ⏸️ On Schedule |
| market_regime_analysis |  | market_regime_analyzer_us.py | ⏸️ On Schedule |
| market_regime_daily_metrics |  | calculate_daily_metrics_us.py | ⏸️ On Schedule |
| outcome_tracker |  | scheduled_outcome_tracker.py | ⏸️ On Schedule |
| realtime_regime_detector | Unknown | realtime_regime_detector_service.py | ✅ Active |
| regime_dashboard | Unknown | 8089 | ✅ Active |
| regime_detection | Unknown | regime_detection_service.py | ✅ Active |
| short_reversal_daily | 09:15 (Fri, Mon, Sat, Thu, Tue, Wed), 09:45 (Fri, Mon, Sat, Thu, Tue, Wed), 10:15 (Fri, Mon, Sat, Thu, Tue, Wed), 10:45 (Fri, Mon, Sat, Thu, Tue, Wed), 11:15 (Fri, Mon, Sat, Thu, Tue, Wed), 11:45 (Fri, Mon, Sat, Thu, Tue, Wed), 12:15 (Fri, Mon, Sat, Thu, Tue, Wed), 12:45 (Fri, Mon, Sat, Thu, Tue, Wed), 13:15 (Fri, Mon, Sat, Thu, Tue, Wed), 13:45 (Fri, Mon, Sat, Thu, Tue, Wed), 14:15 (Fri, Mon, Sat, Thu, Tue, Wed), 14:45 (Fri, Mon, Sat, Thu, Tue, Wed), 15:15 (Fri, Mon, Sat, Thu, Tue, Wed), 15:45 (Fri, Mon, Sat, Thu, Tue, Wed), 16:15 (Fri, Mon, Sat, Thu, Tue, Wed), 16:45 (Fri, Mon, Sat, Thu, Tue, Wed), 17:15 (Fri, Mon, Sat, Thu, Tue, Wed) | Short_Reversal_Daily_US.py | ⏸️ On Schedule |
| sl_watchdog_start | 18:30 (Mon-Fri) | SL_watchdog.py | ⏸️ On Schedule |
| sl_watchdog_stop | 01:00 (Fri, Sat, Thu, Tue, Wed) | true | ⏸️ On Schedule |

---

## Detailed Job Information

### India-TS Jobs Details


#### consolidated_score
- **Label:** `com.india-ts.consolidated_score`
- **Schedule:** 09:00 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/analysis/Action_Plan_Score.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/consolidated_score.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/consolidated_score_error.log`

#### daily_action_plan
- **Label:** `com.india-ts.daily_action_plan`
- **Schedule:** 08:30 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/analysis/Action_plan.py`
- **Timezone:** Not specified
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/daily_action_plan.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/daily_action_plan_error.log`

#### fix_plists_on_startup
- **Label:** `com.india-ts.fix_plists_on_startup`
- **Schedule:** Every 86400 seconds
- **Program:** `/bin/bash /Users/maverick/PycharmProjects/India-TS/Daily/scripts/fix_brooks_plist.sh`
- **Timezone:** Not specified
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_fix_output.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_fix_error.log`

#### g_pattern_master_tracker
- **Label:** `com.india-ts.g_pattern_master_tracker`
- **Schedule:** 09:15 (Mon-Fri), 10:15 (Mon-Fri), 11:15 (Mon-Fri), 12:15 (Mon-Fri), 13:15 (Mon-Fri), 14:15 (Mon-Fri), 15:15 (Mon-Fri)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/G_Pattern_Master_Tracker.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/g_pattern_master_tracker.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/g_pattern_master_tracker_error.log`

#### health_dashboard
- **Label:** `com.india-ts.health_dashboard`
- **Schedule:** Unknown
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_health_check.py`
- **Timezone:** Not specified
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/logs/health_dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/logs/health_dashboard_error.log`

#### kc_g_pattern_scanner
- **Label:** `com.india-ts.kc_g_pattern_scanner`
- **Schedule:** 
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Upper_Limit_Trending.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_g_pattern_scanner.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_g_pattern_scanner_error.log`

#### kc_lower_limit_trending
- **Label:** `com.india-ts.kc_lower_limit_trending`
- **Schedule:** 09:15 (Mon-Fri), 10:15 (Mon-Fri), 11:15 (Mon-Fri), 12:15 (Mon-Fri), 13:15 (Mon-Fri), 14:15 (Mon-Fri), 15:15 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Lower_Limit_Trending.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_lower_limit.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_lower_limit_error.log`

#### kc_lower_limit_trending_fno
- **Label:** `com.india-ts.kc_lower_limit_trending_fno`
- **Schedule:** 09:00 (Mon-Fri), 10:00 (Mon-Fri), 11:00 (Mon-Fri), 12:00 (Mon-Fri), 13:00 (Mon-Fri), 14:00 (Mon-Fri), 15:00 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Lower_Limit_Trending_FNO.py -u Sai`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_lower_limit_trending_fno_launchd.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_lower_limit_trending_fno_launchd_error.log`

#### kc_upper_limit_trending
- **Label:** `com.india-ts.kc_upper_limit_trending`
- **Schedule:** 09:10 (Mon-Fri), 10:10 (Mon-Fri), 11:10 (Mon-Fri), 12:10 (Mon-Fri), 13:10 (Mon-Fri), 14:10 (Mon-Fri), 15:10 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Upper_Limit_Trending.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_upper_limit_trending_scheduler.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_upper_limit_trending_scheduler_error.log`

#### kc_upper_limit_trending_fno
- **Label:** `com.india-ts.kc_upper_limit_trending_fno`
- **Schedule:** 09:00 (Mon-Fri), 10:00 (Mon-Fri), 11:00 (Mon-Fri), 12:00 (Mon-Fri), 13:00 (Mon-Fri), 14:00 (Mon-Fri), 15:00 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Upper_Limit_Trending_FNO.py -u Sai`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_upper_limit_trending_fno_launchd.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/kc_upper_limit_trending_fno_launchd_error.log`

#### long_reversal_daily
- **Label:** `com.india-ts.long_reversal_daily`
- **Schedule:** 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Long_Reversal_Daily.py`
- **Timezone:** Asia/Kolkata
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/long_reversal_cron.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/long_reversal_error.log`

#### market_breadth_dashboard
- **Label:** `com.india-ts.market_breadth_dashboard`
- **Schedule:** Unknown
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_breadth_dashboard.py`
- **Timezone:** Not specified
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_dashboard_error.log`

#### market_breadth_scanner
- **Label:** `com.india-ts.market_breadth_scanner`
- **Schedule:** 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Market_Breadth_Scanner.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner_error.log`

#### market_regime_analysis
- **Label:** `com.india-ts.market_regime_analysis`
- **Schedule:** 08:30 (Mon-Fri), 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analysis.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analysis_error.log`

#### market_regime_analyzer_5min
- **Label:** `com.india-ts.market_regime_analyzer_5min`
- **Schedule:** Every 300 seconds
- **Program:** `/bin/bash /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/run_regime_analyzer_5min.sh`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min_error.log`

#### market_regime_daily_metrics
- **Label:** `com.india-ts.market_regime_daily_metrics`
- **Schedule:** 
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Market_Regime/calculate_daily_metrics.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/daily_metrics.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/daily_metrics_error.log`

#### market_regime_dashboard
- **Label:** `com.india-ts.market_regime_dashboard`
- **Schedule:** Unknown
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py`
- **Timezone:** Not specified
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/dashboard_error.log`

#### outcome_resolver
- **Label:** `com.india-ts.outcome_resolver`
- **Schedule:** 
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Market_Regime/outcome_resolver.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/outcome_resolver.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/outcome_resolver_error.log`

#### short_reversal_daily
- **Label:** `com.india-ts.short_reversal_daily`
- **Schedule:** 09:00 (Mon-Fri), 09:30 (Mon-Fri), 10:00 (Mon-Fri), 10:30 (Mon-Fri), 11:00 (Mon-Fri), 11:30 (Mon-Fri), 12:00 (Mon-Fri), 12:30 (Mon-Fri), 13:00 (Mon-Fri), 13:30 (Mon-Fri), 14:00 (Mon-Fri), 14:30 (Mon-Fri), 15:00 (Mon-Fri), 15:30 (Mon-Fri)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Short_Reversal_Daily.py`
- **Timezone:** Asia/Kolkata
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_reversal_cron.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_reversal_error.log`

#### sl_watchdog_start
- **Label:** `com.india-ts.sl_watchdog_start`
- **Schedule:** 09:15 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/start_all_sl_watchdogs.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/logs/sl_watchdog_start.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/logs/sl_watchdog_start_error.log`

#### sl_watchdog_stop
- **Label:** `com.india-ts.sl_watchdog_stop`
- **Schedule:** 15:30 (Mon-Fri)
- **Program:** `/bin/bash -c pkill -f "SL_watchdog.py.*India-TS" || true`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/logs/sl_watchdog_stop.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/logs/sl_watchdog_stop_error.log`

#### strategyc_filter
- **Label:** `com.india-ts.strategyc_filter`
- **Schedule:** 09:45 (Mon-Fri), 11:45 (Mon-Fri), 13:45 (Mon-Fri), 16:15 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scanners/StrategyC_Auto.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/strategyc_filter.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/strategyc_filter_error.log`

#### synch_zerodha_local
- **Label:** `com.india-ts.synch_zerodha_local`
- **Schedule:** 09:15 (Mon-Fri), 09:30 (Mon-Fri), 09:45 (Mon-Fri), 10:00 (Mon-Fri), 10:15 (Mon-Fri), 10:30 (Mon-Fri), 10:45 (Mon-Fri), 11:00 (Mon-Fri), 11:15 (Mon-Fri), 11:30 (Mon-Fri), 11:45 (Mon-Fri), 12:00 (Mon-Fri), 12:15 (Mon-Fri), 12:30 (Mon-Fri), 12:45 (Mon-Fri), 13:00 (Mon-Fri), 13:15 (Mon-Fri), 13:30 (Mon-Fri), 13:45 (Mon-Fri), 14:00 (Mon-Fri), 14:15 (Mon-Fri), 14:30 (Mon-Fri), 14:45 (Mon-Fri), 15:00 (Mon-Fri), 15:15 (Mon-Fri), 15:30 (Mon-Fri)
- **Program:** `/usr/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/utils/synch_zerodha_cnc_positions.py --force`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/synch_zerodha_local.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/synch_zerodha_local.log`

#### vsr_tracker_enhanced
- **Label:** `com.india-ts.vsr-tracker-enhanced`
- **Schedule:** 09:15 (Mon-Fri)
- **Program:** `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/services/vsr_tracker_service_enhanced.py --user Sai --interval 60`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_enhanced_service.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_enhanced_service_error.log`

#### vsr_dashboard
- **Label:** `com.india-ts.vsr-dashboard`
- **Schedule:** 09:15 (Mon-Fri)
- **Program:** `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/vsr_tracker_dashboard.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_dashboard_error.log`

#### vsr_shutdown
- **Label:** `com.india-ts.vsr-shutdown`
- **Schedule:** 15:30 (Mon-Fri)
- **Program:** `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/scripts/stop_vsr_services.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_shutdown.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker/vsr_shutdown_error.log`

#### weekly_backup
- **Label:** `com.india-ts.weekly_backup`
- **Schedule:** 03:00 (Sun)
- **Program:** `/Users/maverick/PycharmProjects/India-TS/Daily/bin/weekly_backup.sh`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/weekly_backup.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/weekly_backup_error.log`

#### short_momentum_tracker
- **Label:** `com.india-ts.short-momentum-tracker`
- **Schedule:** 09:15 (Mon-Fri)
- **Program:** `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/services/short_momentum_tracker_service.py --user Sai --interval 60`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum/short_momentum_tracker.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum/short_momentum_tracker_error.log`

#### short_momentum_dashboard
- **Label:** `com.india-ts.short-momentum-dashboard`
- **Schedule:** 09:15 (Mon-Fri)
- **Program:** `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/short_momentum_dashboard.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum/short_momentum_dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum/short_momentum_dashboard_error.log`
- **Dashboard URL:** http://localhost:3003

### US-TS Jobs Details


#### health_dashboard
- **Label:** `com.usts.health_dashboard`
- **Schedule:** Unknown
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/dashboard/health_check_visual.py`
- **Timezone:** US/Eastern
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/logs/health_dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/logs/health_dashboard_error.log`

#### long_reversal_daily
- **Label:** `com.usts.long_reversal_daily`
- **Schedule:** 09:15 (Fri, Mon, Sat, Thu, Tue, Wed), 09:45 (Fri, Mon, Sat, Thu, Tue, Wed), 10:15 (Fri, Mon, Sat, Thu, Tue, Wed), 10:45 (Fri, Mon, Sat, Thu, Tue, Wed), 11:15 (Fri, Mon, Sat, Thu, Tue, Wed), 11:45 (Fri, Mon, Sat, Thu, Tue, Wed), 12:15 (Fri, Mon, Sat, Thu, Tue, Wed), 12:45 (Fri, Mon, Sat, Thu, Tue, Wed), 13:15 (Fri, Mon, Sat, Thu, Tue, Wed), 13:45 (Fri, Mon, Sat, Thu, Tue, Wed), 14:15 (Fri, Mon, Sat, Thu, Tue, Wed), 14:45 (Fri, Mon, Sat, Thu, Tue, Wed), 15:15 (Fri, Mon, Sat, Thu, Tue, Wed), 15:45 (Fri, Mon, Sat, Thu, Tue, Wed), 16:15 (Fri, Mon, Sat, Thu, Tue, Wed), 16:45 (Fri, Mon, Sat, Thu, Tue, Wed), 17:15 (Fri, Mon, Sat, Thu, Tue, Wed)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Daily/scanners/Long_Reversal_Daily_US.py`
- **Timezone:** US/Eastern
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Daily/logs/long_reversal_cron.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Daily/logs/long_reversal_error.log`

#### market_regime_analysis
- **Label:** `com.usts.market_regime_analysis`
- **Schedule:** 
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/market_regime_analyzer_us.py`
- **Timezone:** US/Eastern
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/regime_analysis.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/regime_analysis_error.log`

#### market_regime_daily_metrics
- **Label:** `com.usts.market_regime_daily_metrics`
- **Schedule:** 
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/calculate_daily_metrics_us.py`
- **Timezone:** America/New_York
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/daily_metrics.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/daily_metrics_error.log`

#### outcome_tracker
- **Label:** `com.usts.outcome_tracker`
- **Schedule:** 
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/learning/scheduled_outcome_tracker.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/logs/outcome_tracker.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/logs/outcome_tracker_error.log`

#### realtime_regime_detector
- **Label:** `com.usts.realtime_regime_detector`
- **Schedule:** Unknown
- **Program:** `/Users/maverick/PycharmProjects/US-TS/.venv/bin/python /Users/maverick/PycharmProjects/US-TS/Market_Regime/realtime_regime_detector_service.py`
- **Timezone:** US/Eastern
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/realtime_regime_detector.out`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/realtime_regime_detector.err`

#### regime_dashboard
- **Label:** `com.usts.regime_dashboard`
- **Schedule:** Unknown
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/run_dashboard_us.py --port 8089`
- **Timezone:** America/New_York
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/dashboard.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/dashboard_error.log`

#### regime_detection
- **Label:** `com.usts.regime_detection`
- **Schedule:** Unknown
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Market_Regime/regime_detection_service.py`
- **Timezone:** US/Eastern
- **Run at Load:** True
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/regime_detection.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/regime_detection_error.log`

#### short_reversal_daily
- **Label:** `com.usts.short_reversal_daily`
- **Schedule:** 09:15 (Fri, Mon, Sat, Thu, Tue, Wed), 09:45 (Fri, Mon, Sat, Thu, Tue, Wed), 10:15 (Fri, Mon, Sat, Thu, Tue, Wed), 10:45 (Fri, Mon, Sat, Thu, Tue, Wed), 11:15 (Fri, Mon, Sat, Thu, Tue, Wed), 11:45 (Fri, Mon, Sat, Thu, Tue, Wed), 12:15 (Fri, Mon, Sat, Thu, Tue, Wed), 12:45 (Fri, Mon, Sat, Thu, Tue, Wed), 13:15 (Fri, Mon, Sat, Thu, Tue, Wed), 13:45 (Fri, Mon, Sat, Thu, Tue, Wed), 14:15 (Fri, Mon, Sat, Thu, Tue, Wed), 14:45 (Fri, Mon, Sat, Thu, Tue, Wed), 15:15 (Fri, Mon, Sat, Thu, Tue, Wed), 15:45 (Fri, Mon, Sat, Thu, Tue, Wed), 16:15 (Fri, Mon, Sat, Thu, Tue, Wed), 16:45 (Fri, Mon, Sat, Thu, Tue, Wed), 17:15 (Fri, Mon, Sat, Thu, Tue, Wed)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Daily/scanners/Short_Reversal_Daily_US.py`
- **Timezone:** US/Eastern
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/Daily/logs/short_reversal_cron.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/Daily/logs/short_reversal_error.log`

#### sl_watchdog_start
- **Label:** `com.usts.sl_watchdog_start`
- **Schedule:** 18:30 (Mon-Fri)
- **Program:** `/usr/local/bin/python3 /Users/maverick/PycharmProjects/US-TS/Daily/scripts/SL_watchdog.py`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/logs/sl_watchdog_start.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/logs/sl_watchdog_start_error.log`

#### sl_watchdog_stop
- **Label:** `com.usts.sl_watchdog_stop`
- **Schedule:** 01:00 (Fri, Sat, Thu, Tue, Wed)
- **Program:** `/bin/bash -c pkill -f "SL_watchdog.py.*US-TS" || true`
- **Timezone:** Not specified
- **Run at Load:** False
- **Log Path:** `/Users/maverick/PycharmProjects/US-TS/logs/sl_watchdog_stop.log`
- **Error Path:** `/Users/maverick/PycharmProjects/US-TS/logs/sl_watchdog_stop_error.log`

---

## Plist Management Guidelines


### Best Practices
1. **Always backup** existing plist files before modifications
2. **Use project-specific prefixes** (com.india-ts.* or com.usts.*)
3. **Document schedule changes** in this master file
4. **Test plist files** before deploying to production
5. **Avoid schedule conflicts** between similar jobs

### Common Commands
```bash
# Load a plist
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.job_name.plist

# Unload a plist
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.job_name.plist

# List all loaded jobs
launchctl list | grep -E '(india-ts|usts)'

# Start a job manually
launchctl start com.india-ts.job_name

# Stop a job
launchctl stop com.india-ts.job_name
```

---

## Notes
- Jobs marked as '⏸️ On Schedule' run according to their schedule
- Jobs marked as '✅ Active' have RunAtLoad=true and start when system boots
- Always update this documentation when adding/modifying plist files
- Run `python generate_plist_master.py` to regenerate this documentation