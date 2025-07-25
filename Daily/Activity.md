# India-TS Activity Log

This file maintains a chronological record of all changes made to the India-TS system.
Each entry should include: Date, Time, Author, Changes Made, and Impact.

## Format
```
### YYYY-MM-DD HH:MM IST - [Author]
**Changes:**
- Description of changes

**Impact:**
- Systems/services affected
- Any configuration updates
- Testing performed

---
```

## Activity Log

### 2025-07-23 14:50 IST - [System]
**Changes:**
- Implemented Git-based plist management system
- Created backup of all India-TS plists in Daily/scheduler/plists/
- Added install_plists.py and validate_plists.py scripts
- Updated PLIST_MASTER_SCHEDULE.md documentation

**Impact:**
- Prevents accidental cross-project plist contamination
- All India-TS plists now have versioned backups
- Easier recovery from plist corruption or accidental changes

---

### 2025-07-23 09:28 IST - [System]
**Changes:**
- Added FNO Liquid reversal scanner plist (com.india-ts.fno_liquid_reversal_scanners)
- Configured to run on hourly schedule

**Impact:**
- New automated scanner for FNO liquid stocks
- Integrated with existing reversal scanning infrastructure

---

### 2025-07-25 03:35 IST - [Claude/System]
**Changes:**
- Updated job_manager_dashboard.py to fix PID column visibility issue
- Added horizontal scrolling to tables (overflow-x: auto)
- Reduced font sizes and padding for better space utilization
- Added minimum table width of 900px
- Updated VSR job entries in JOBS dictionary

**Impact:**
- PID column now visible in job manager dashboard
- Added VSR jobs: vsr-tracker-enhanced, vsr-dashboard, vsr-shutdown
- Better table layout with horizontal scrolling when needed
- VSR dashboard available on port 3001

---

### 2025-07-25 09:07 IST - [Claude/System]
**Changes:**
- Updated job_manager_dashboard.py time restrictions
- Changed from 9:30 AM - 3:30 PM to 9:00 AM - 4:00 PM IST
- Updated all error messages to reflect new time range

**Impact:**
- Job manager dashboard now accessible from 9:00 AM to 4:00 PM IST
- Provides 30 minutes earlier access and 30 minutes later access
- Better accommodates pre-market and post-market activities

---
