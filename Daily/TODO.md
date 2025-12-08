# India-TS Market Regime ML System - Development Roadmap

## 🎯 Mission
Build a robust, self-improving ML system for market regime prediction using best practices.

## 📁 Project Location
`/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/`

---

## Phase 1: Data Pipeline Foundation 🔄
**Timeline**: Days 1-3 (Starting 2025-08-26)
**Status**: ✅ COMPLETED

### Day 1 (2025-08-26)
- [x] Create project structure
- [x] Design implementation phases
- [x] Build Data Ingestor module
- [x] Test with sample data
- [x] Add market hours validation
- [x] Save data in parquet format

### Day 2
- [x] Implement Data Validator (partial - basic validation in place)
- [x] Add schema enforcement (via feature store)
- [x] Create validation reports (basic reporting implemented)

### Day 3 - COMPLETED 2025-09-07
- [x] Set up automated scheduling (LaunchAgent created and installed)
- [x] Add logging system (comprehensive logging in all modules)
- [x] Complete Phase 1 testing (data pipeline working)

### Components to Build:
1. **Data Ingestor** (`src/ingestion/data_ingestor.py`)
   - Collect scanner results every 5 minutes
   - Gather market data (indices, breadth)
   - Store in structured format

2. **Data Validator** (`src/validation/data_validator.py`)
   - Remove outliers (inf, NaN, zeros from token errors)
   - Enforce consistent schema
   - Generate data quality reports

### Deliverables:
- [x] Working data pipeline ✅
- [x] Clean, validated datasets ✅
- [x] Data quality documentation ✅

---

## Phase 2: Feature Engineering 🔧
**Timeline**: Days 4-7
**Status**: ✅ COMPLETED (Accelerated on Day 1)

### Day 1 (2025-08-26) - COMPLETED EARLY
- [x] Build Feature Builder module
- [x] Implement 21 market breadth features
- [x] Create Feature Store with SQLite metadata tracking
- [x] Implement versioning and schema validation
- [x] Build Regime Labeler with 7 regime types
- [x] Label data and create transition features
- [x] Validate labels and save to parquet
- [x] Complete end-to-end pipeline test

### Components:
1. **Feature Builder** - 30+ engineered features
2. **Feature Store** - Centralized storage with versioning
3. **Regime Labeler** - Define and label market regimes

### Deliverables:
- [x] Feature pipeline ✅
- [x] Feature documentation ✅
- [x] Labeled training data ✅

---

## Phase 3: Model Training & Registry 🤖
**Timeline**: Days 8-10
**Status**: 🚧 READY TO START (Data Collection Automated)

### Day 8
- [ ] Implement Model Trainer
- [ ] Create baseline model
- [ ] Add cross-validation

### Day 9
- [ ] Build Model Evaluator
- [ ] Compare with baseline
- [ ] Generate metrics

### Day 10
- [ ] Create Model Registry
- [ ] Add versioning system
- [ ] Test rollback capability

### Components:
1. **Model Trainer** - Random Forest with proper validation
2. **Model Evaluator** - Performance metrics and comparison
3. **Model Registry** - Version control and metadata

### Deliverables:
- [ ] Trained model
- [ ] Model registry
- [ ] Performance reports

---

## Phase 4: Model Serving 🚀
**Timeline**: Days 11-14
**Status**: 📅 SCHEDULED

### Day 11-12
- [ ] Build Batch Predictor
- [ ] Implement hourly jobs
- [ ] Test predictions

### Day 13-14
- [ ] Create API Server
- [ ] Build web dashboard
- [ ] Deploy on port 8080

### Components:
1. **Batch Predictor** - Hourly prediction jobs
2. **API Server** - REST API for real-time predictions
3. **Web Dashboard** - Visual interface on port 8080

### Deliverables:
- [ ] Working API
- [ ] Prediction pipeline
- [ ] Web dashboard

---

## Phase 5: Monitoring & Auto-Adaptation 🔄
**Timeline**: Days 15-20
**Status**: 📅 SCHEDULED

### Day 15-17
- [ ] Build Drift Detector
- [ ] Implement monitoring
- [ ] Create alerts

### Day 18-20
- [ ] Build Auto Retrainer
- [ ] Add A/B testing
- [ ] Complete feedback loop

### Components:
1. **Drift Detector** - Monitor feature and prediction drift
2. **Performance Monitor** - Track accuracy over time
3. **Auto Retrainer** - Automated retraining with validation

### Deliverables:
- [ ] Monitoring system
- [ ] Alert pipeline
- [ ] Auto-retraining capability

---

## 📊 Success Metrics

### Phase 1
- Data validation rate: >95%
- Schema consistency: 100%
- Ingestion uptime: >99%

### Phase 2
- Feature computation: <1 second
- Feature coverage: >90%
- Label accuracy: Manual validation

### Phase 3
- Model accuracy: >85%
- Beats baseline by: >10%
- Training time: <5 minutes

### Phase 4
- API latency: <100ms
- Prediction availability: >99%
- Dashboard uptime: >99%

### Phase 5
- Drift detection lag: <1 hour
- Auto-retrain success: >90%
- No single regime >40%

---

## 🔑 Key Principles
1. **Modularity** - Each component is independent
2. **Reusability** - Shared code between training and serving
3. **Observability** - Comprehensive logging
4. **Safety** - Rollback capability
5. **Simplicity** - Clear, understandable code

---

## 📝 Daily Progress Log

### 2025-08-26 (Day 1)
- ✅ Created project structure at `/Daily/New_Market_Regime/`
- ✅ Designed 5-phase implementation plan
- ✅ Created detailed documentation
- ✅ **Phase 1 COMPLETE**: Built Data Ingestor that reuses existing scanner data
  - Scanner results: 14 long, 47 short stocks (L/S Ratio: 0.30)
  - Regime predictions: 81 predictions (still showing diversity issues)
  - Market breadth: Bearish sentiment (23% bullish)
  - Data saved in parquet format for efficient processing
  - Market hours check implemented (weekdays 9:15 AM - 3:30 PM only)
- ✅ **Phase 2 COMPLETE**: Feature Engineering Pipeline
  - Built Feature Builder with 21 market breadth features
  - Created Feature Store with SQLite metadata and versioning
  - Implemented Regime Labeler with 7 regime types
  - Labeled data as "choppy_bearish" with 70% confidence
  - Complete pipeline tested end-to-end
  - Features saved to parquet with full metadata tracking

**Progress**: Completed Phase 1 & 2 on Day 1 (40% of project) 🚀

---

## 🚀 Quick Commands

```bash
# Navigate to project
cd /Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime

# Run data ingestion
python src/ingestion/data_ingestor.py

# Run validation
python src/validation/data_validator.py

# Check data quality
python src/validation/generate_report.py
```

---

## ⚠️ Important Notes

1. **Current System Issues**:
   - Old system has 100% regime monoculture
   - Feedback collection failed due to technical issues
   - This new system addresses all these problems

2. **Key Improvements**:
   - Proper data validation
   - Feature store for consistency
   - Model registry with versioning
   - Automated drift detection
   - Self-healing capabilities

3. **Migration Plan**:
   - New system runs parallel to old
   - No disruption to existing dashboards
   - Gradual transition once stable

---

*Last Updated: 2025-09-07 12:50 IST*
*Next Review: 2025-09-09 - Check data collection & start Phase 3*

## Recent Updates (2025-09-07)
- ✅ Automated data collection pipeline installed
- ✅ Historical backfill completed (39 days)
- ✅ LaunchAgent configured for 5-minute collection during market hours
- 🚧 Ready for Phase 3 (Model Training) with current dataset

---

## 🎯 ML Prediction System - Priority Roadmap

### Week 1: Foundation Fixes
**Timeline**: Days 1-5
**Focus**: Get predictions running without errors

#### Day 1: Data Quality
- [ ] Fix NULL handling in feature pipeline
- [ ] Populate missing data points
- [ ] Validate data completeness

#### Day 2: Prediction Pipeline
- [ ] Get predictions running end-to-end
- [ ] Fix any runtime errors
- [ ] Validate output format

#### Days 3-4: Validation Methodology
- [ ] Fix train/test split methodology
- [ ] Implement proper cross-validation
- [ ] Address data leakage issues

#### Day 5: Model Retraining
- [ ] Retrain with proper validation
- [ ] Baseline model performance
- [ ] Document metrics

### Week 2: Monitoring & Dashboard
**Timeline**: Days 6-10
**Focus**: Deploy working system with visibility

#### Days 6-7: Monitoring Implementation
- [ ] Implement model monitoring
- [ ] Add prediction logging
- [ ] Create alert system

#### Day 8: Dashboard Deployment
- [ ] Deploy working dashboard
- [ ] Show live predictions
- [ ] Add performance metrics

#### Days 9-10: Feedback Loop
- [ ] Add feedback collection
- [ ] Implement data persistence
- [ ] Create retraining trigger

### Weeks 3-4: Optimization
**Timeline**: Days 11-20
**Focus**: Production hardening

- [ ] Feature improvements
- [ ] Model optimization
- [ ] Performance tuning
- [ ] Production hardening
- [ ] Documentation

### 📊 Success Metrics

**Immediate Goals**:
- Predictions running without errors
- No NULL/NaN issues in pipeline

**Week 1 Targets**:
- Model accuracy: 70-85% (realistic baseline)
- Clean validation methodology
- Reproducible results

**Week 2 Targets**:
- Dashboard showing live predictions
- Monitoring alerts functional
- Feedback loop operational

**Month 1 Target**:
- Stable production system
- Automated retraining
- Performance tracking

### 🛠️ Tools & Infrastructure

**Required Tools**:
1. **MLflow** - For experiment tracking and model versioning
2. **Grafana** - For monitoring dashboards and alerting
3. **PostgreSQL** - Better than SQLite for production scale
4. **Redis** - For caching predictions and reducing latency
5. **Airflow** - For pipeline orchestration and scheduling

**Implementation Priority**:
1. Start with MLflow (experiment tracking)
2. Add PostgreSQL (data persistence)
3. Implement Redis (performance optimization)
4. Deploy Grafana (monitoring)
5. Integrate Airflow (orchestration)

---

## 📊 Service Redundancy Analysis (2025-10-06)

### Current State: 7 Errored Services
All services showing Exit -15 (SIGTERM - terminated during cleanup/token refresh)

**Services analyzed**:
1. hourly-breakout-alerts (Exit: -15, PID: 39708)
2. hourly-short-tracker-service (Exit: -15, PID: 39711)
3. hourly-tracker-service (Exit: -15, PID: 39781)
4. hourly-tracker-dashboard (Exit: -15, PID: 39782)
5. hourly-short-tracker-dashboard (Exit: -9, PID: 39783)
6. short-momentum-tracker (Exit: -15, PID: 39852)
7. vsr-tracker-enhanced (Exit: -15, PID: 39853)

### Analysis Results

#### TRUE REDUNDANCIES (4 services)
1. **hourly-tracker-service** (Long_Reversal_Hourly tracker)
   - Uses VSR_Momentum_Scanner functions
   - Tracks minute data for VSR calculation
   - Outputs to: `logs/hourly_tracker/`
   - **Redundant with**: vsr-tracker-enhanced

2. **hourly-short-tracker-service** (Short_Reversal_Hourly tracker)
   - Identical VSR calculation logic to hourly-tracker-service
   - Tracks short positions with same methodology
   - Outputs to: `logs/hourly_short_tracker/`
   - **Redundant with**: vsr-tracker-enhanced (can handle shorts)

3. **short-momentum-tracker** (Short_Reversal_Daily tracker)
   - Tracks 3-day persistence for shorts
   - Calculates momentum scores
   - **Redundant with**: hourly-short-tracker-service

4. **hourly-short-tracker-dashboard** (Port 3004)
   - Parses hourly_short_tracker logs
   - Categorizes by negative momentum
   - **Redundant with**: hourly-tracker-dashboard (can show both)

#### UNIQUE SERVICES (3 services - KEEP)
1. **vsr-tracker-enhanced** ✅
   - Enhanced VSR tracker with 3-day persistence
   - Liquidity metrics integration
   - Handles both long/short positions
   - Most comprehensive tracker
   - **Status**: Keep as primary tracker

2. **hourly-tracker-dashboard** (Port 3002) ✅
   - Web dashboard for VSR data
   - Real-time ticker monitoring
   - Persistence tier categorization
   - **Status**: Keep and enhance for both long/short

3. **hourly-breakout-alerts** ✅
   - Monitors hourly breakout patterns
   - Price crosses above previous hourly close
   - Telegram alerts for trend continuation
   - **Unique logic**: Breakout-based (not VSR-based)
   - **Status**: Keep - provides unique functionality

### Consolidation Recommendation

**FROM**: 7 services → **TO**: 3 services

#### Services to Archive (4):
- ❌ hourly-tracker-service
- ❌ hourly-short-tracker-service
- ❌ short-momentum-tracker
- ❌ hourly-short-tracker-dashboard

#### Services to Keep (3):
- ✅ vsr-tracker-enhanced (primary VSR tracker)
- ✅ hourly-tracker-dashboard (unified dashboard)
- ✅ hourly-breakout-alerts (unique breakout logic)

#### Enhancement Needed:
1. **vsr-tracker-enhanced**: Verify short position handling
2. **hourly-tracker-dashboard**: Add long/short tabs to UI

### Risk Assessment

**LOW RISK**:
- All trackers use identical VSR_Momentum_Scanner functions
- vsr-tracker-enhanced already has full VSR logic
- Dashboards only parse log files (safe to merge)

**MEDIUM RISK**:
- Need to verify vsr-tracker-enhanced handles shorts properly
- Dashboard template updates required for long/short views

**MITIGATION**:
- Archive old services (don't delete files)
- Keep backup plists in scheduler/plists/
- Test consolidated services before removing old ones

### Implementation Status
- **Decision**: HOLD OFF (2025-10-06)
- **Reason**: Analysis complete, awaiting approval
- **Next Steps**: Available when ready to consolidate

---

*Analysis completed: 2025-10-06*