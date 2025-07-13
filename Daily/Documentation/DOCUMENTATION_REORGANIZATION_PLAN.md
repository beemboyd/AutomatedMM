# Documentation Reorganization Plan

## Overview
This plan consolidates and reorganizes the India-TS documentation to be primarily centered in the Daily folder, making it easier to find and maintain documentation.

## Current Issues
1. Documentation scattered across multiple directories
2. Duplicate documentation in different locations
3. Some docs in root directory that belong in Daily
4. Unclear hierarchy and organization

## Proposed Structure

### 📁 Daily/Documentation/ (Main Documentation Hub)

#### 1. **README.md** - Documentation Index
- Overview of all documentation
- Quick links to important docs
- Documentation conventions

#### 2. **Core System Docs**
- **SYSTEM_OVERVIEW.md** - Complete system overview (move from root)
- **QUICK_START_GUIDE.md** - Getting started guide
- **DAILY_WORKFLOW.md** - Daily trading workflow
- **TROUBLESHOOTING_GUIDE.md** - Common issues and solutions

#### 3. **Component Documentation**
- **scanners/** - Scanner documentation
  - `brooks_scanner_guide.md`
  - `reversal_scanner_guide.md`
  - `kc_pattern_scanner_guide.md`
  - `g_pattern_master_guide.md` (move from Daily/)
- **trading/** - Trading system docs
  - `order_placement_guide.md`
  - `position_management_guide.md`
  - `g_pattern_auto_trader_guide.md` (move from Daily/trading/)
- **portfolio/** - Portfolio management
  - `sl_watchdog_guide.md` (consolidate all watchdog docs)
  - `regime_stop_loss_guide.md` (already exists)
  - `volume_anomaly_detection_guide.md` (already exists)
- **analysis/** - Analysis tools
  - `market_regime_guide.md`
  - `action_plan_guide.md`
  - `consolidated_score_guide.md`

#### 4. **Operations Documentation**
- **jobs/** - LaunchAgent jobs
  - `jobs_overview.md` (move from Daily/INDIA_TS_JOBS_DOCUMENTATION.md)
  - `jobs_management_guide.md`
  - `scheduler_setup_guide.md`
- **dashboards/** - Dashboard documentation
  - `dashboard_overview.md`
  - `dashboard_quick_reference.md` (move from Daily/)
  - `dashboard_startup_guide.md` (move from Daily/)
  - `dashboard_hosting_guide.md` (move from Daily/)
- **maintenance/** - System maintenance
  - `backup_restore_guide.md` (move from root BACKUP_GUIDE.md)
  - `golden_version_guide.md` (move from root)
  - `weekly_backup_guide.md`

#### 5. **Development Documentation**
- **api/** - API documentation
  - `zerodha_integration.md`
  - `user_context_management.md`
- **development/** - Development guides
  - `claude_instructions.md` (CLAUDE.md)
  - `git_workflow.md`
  - `testing_guide.md`

#### 6. **Flow Diagrams**
- **flows/** - All flow diagrams in one place
  - Move all from Daily/Diagrams/
  - Move all from Daily/Documentation/
  - Consistent naming convention

## Migration Steps

### Phase 1: Create New Structure
1. Create new directory structure in Daily/Documentation/
2. Create index README.md with navigation

### Phase 2: Consolidate Documentation
1. Move and merge related documentation
2. Update internal links
3. Remove duplicates
4. Archive outdated docs

### Phase 3: Create Navigation
1. Update main README.md with clear navigation
2. Add breadcrumbs to each doc
3. Create quick reference cards

### Phase 4: Cleanup
1. Remove/archive old documentation locations
2. Update all code references to docs
3. Update CLAUDE.md with new structure

## Benefits
1. **Single source of truth** - All docs in Daily/Documentation/
2. **Logical organization** - Grouped by function
3. **Easy navigation** - Clear hierarchy and index
4. **Reduced duplication** - Consolidated similar docs
5. **Better maintenance** - Know where to update

## Quick Access Structure

```
Daily/Documentation/
├── README.md (Index & Navigation)
├── QUICK_START_GUIDE.md
├── DAILY_WORKFLOW.md
├── TROUBLESHOOTING_GUIDE.md
├── scanners/
├── trading/
├── portfolio/
├── analysis/
├── jobs/
├── dashboards/
├── maintenance/
├── api/
├── development/
└── flows/
```

## Implementation Timeline
- Phase 1: Create structure (30 min)
- Phase 2: Move and consolidate (2 hours)
- Phase 3: Create navigation (1 hour)
- Phase 4: Cleanup (30 min)

Total estimated time: 4 hours