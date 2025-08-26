# India-TS TODO List & System Improvements

## 🚨 CRITICAL: Market Regime ML System Recovery

### Current Status (as of 2025-08-24)
**System Failure Detected**: Market Regime ML predictions stuck at 97.86% single regime (choppy_bullish)
- Model accuracy degraded from 94% to 90.74%
- No actual regime feedback being recorded
- Market scores exceeding valid range (up to 14.0 when max should be 1.0)
- Self-reinforcing bias causing prediction monoculture

### Phase 1: Emergency Fixes ✅ COMPLETED (2025-08-24)
**Status**: Implemented and verified
- [x] Disabled automatic retraining (prevents further degradation)
- [x] Restored baseline model v_20250702_094009 (94% accuracy)
- [x] Fixed data normalization (enforced -1 to 1 range)
- [x] Created emergency backup of corrupted state
- [x] Implemented monitoring configuration
- [x] Added to pre-market setup script for daily loading

**Files Modified**:
- `/Daily/Market_Regime/emergency_fix_phase1.py` - Emergency fix implementation
- `/Daily/Market_Regime/market_regime_predictor_fixed.py` - Fixed predictor with normalization
- `/Daily/Market_Regime/ml_config.json` - Emergency configuration
- `/Daily/Market_Regime/monitoring_config.json` - Drift monitoring setup
- `/Daily/pre_market_setup.sh` - Added Step 11 for loading Market Regime Analyzer

**Monitoring Period**: 2025-08-25 (24 hours)
- Check regime diversity improves (no single regime >70%)
- Verify market scores stay within [-1, 1] range
- Confirm system stability (no crashes)
- Run verification script: `python3 verify_phase1_fixes.py`

---

### Phase 2: Restore Learning ❌ FAILED (2025-08-26)
**Status**: Service failed due to technical issues
**Started**: 2025-08-25 11:30 IST
**Failed**: 2025-08-26 12:00 IST

#### Implementation Completed:
1. **✅ Actual Regime Calculator** (`actual_regime_calculator.py`)
   - Calculates regime 45 minutes after predictions
   - Uses NIFTY price data with thresholds:
     - Strong trend: >1.5% move
     - Moderate trend: 0.75-1.5% move  
     - Weak trend: 0.3-0.75% move
   - Incorporates volume ratio and volatility

2. **✅ Feedback Database Created** (`regime_feedback.db`)
   - Table: `regime_feedback` with full schema implemented
   - Table: `accuracy_metrics` for daily statistics
   - Unique constraint on prediction_id to prevent duplicates

3. **✅ Validation Pipeline Built** (`regime_validation_pipeline.py`)
   - Validates feedback coverage (target: >80%)
   - Checks regime distribution balance
   - Calculates confusion matrix
   - Determines retraining readiness

4. **✅ Automated Collection Service** 
   - Feedback collector runs every 5 minutes via launchctl
   - Validation monitor runs hourly (10 AM - 4 PM)
   - Integrated into pre-market setup script (Step 14)
   - Market hours wrapper ensures weekday-only operation

**Monitoring Commands**:
```bash
# Quick status check
./Market_Regime/check_phase2_status.sh

# Detailed monitoring
python3 Market_Regime/monitor_phase2.py

# Stop services if needed
./Market_Regime/stop_feedback_services.sh
```

**Issues Discovered** (2025-08-26 12:30 IST):
- ❌ Missing Python module dependencies (`schedule`)
- ❌ Incompatible UserContextManager API usage
- ❌ Database schema mismatch
- ❌ Time module import conflict
- ❌ **CRITICAL: 100% regime monoculture persists (all predictions are choppy_bullish)**

**Alternative Approach Implemented**:
- Created `load_historical_from_db.py` to extract existing predictions
- Attempting to calculate actual regimes from NIFTY market data
- This approach doesn't impact existing dashboards or services
- Preserves historical data for future training

**Next Steps**:
1. Let the system collect feedback for 24 hours
2. Check back on 2025-08-26 at 12:00 PM IST
3. Run `python3 Market_Regime/monitor_phase2.py` to assess readiness
4. If criteria met (>80% coverage, >70% accuracy, balanced distribution):
   - Proceed to Phase 3: Smart Retraining
5. If not ready:
   - Continue collecting data
   - Investigate any issues with feedback collection
   - May need to adjust thresholds or calculation timing

---

### Phase 3: Smart Retraining 📅 SCHEDULED (Target: Week of 2025-08-26)
**Prerequisite**: 100+ validated predictions from Phase 2

#### Implementation Tasks:
1. **Quality Gates**
   - Minimum 100 validated predictions
   - All regimes represented (no regime <10%)
   - New model must beat baseline by 2%

2. **A/B Testing Framework**
   ```python
   class ABTestFramework:
       def shadow_run(new_model, hours=24):
           # Run new model in parallel
           # Compare predictions without deploying
           # Calculate performance delta
   ```

3. **Rollback Triggers**
   - Auto-revert if accuracy drops >5%
   - Alert on regime monoculture
   - Emergency restore capability

4. **Balanced Training**
   - Use SMOTE for underrepresented regimes
   - Cross-validation with regime stratification
   - Feature importance analysis

**Success Criteria**:
- Safe model updates without degradation
- Maintain >92% accuracy
- No single regime dominance

---

### Phase 4: Continuous Improvement 🚀 FUTURE (Target: 2025-09-01+)
**Prerequisite**: Stable Phase 3 with successful retraining cycles

#### Implementation Tasks:
1. **Drift Detection System**
   - Real-time monitoring every 30 minutes
   - Alert if any regime >40% of daily predictions
   - Auto-correction mechanisms

2. **Ensemble Models**
   - 3 models with different architectures
   - Voting mechanism for final prediction
   - Diversity enforcement

3. **Human Oversight Dashboard**
   - Real-time metrics visualization
   - Manual intervention capability
   - Performance trending

4. **Advanced Features**
   - Option chain analysis integration
   - Market microstructure features
   - Cross-market correlations

---

## 📊 Key Metrics to Monitor

### Daily Checks
```bash
# Check regime diversity
sqlite3 /Users/maverick/PycharmProjects/India-TS/data/regime_learning.db \
"SELECT regime, COUNT(*) as count, 
ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM predictions WHERE DATE(timestamp) = DATE('now')), 2) as pct 
FROM predictions WHERE DATE(timestamp) = DATE('now') GROUP BY regime;"

# Verify market scores in range
grep "Market score normalized" /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log

# Check prediction frequency
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log
```

### Success Thresholds
- **Regime Diversity**: No single regime >40% daily
- **Model Accuracy**: Maintain >92% on validated predictions  
- **Market Scores**: 100% within [-1, 1] range
- **Prediction Frequency**: ~78 predictions/day (every 5 min during market hours)
- **Feedback Coverage**: >80% predictions get actual regime validation

---

## 🔧 Technical Context for Implementation

### System Architecture
```
Scanner Results → Feature Extraction → ML Prediction → Regime Smoothing → Dashboard
                                            ↓
                                    SQLite Database (Learning)
                                            ↓
                                    Feedback Loop (BROKEN - needs Phase 2)
```

### File Structure
```
Daily/Market_Regime/
├── market_regime_predictor.py       # Main predictor (needs replacing with _fixed version)
├── market_regime_predictor_fixed.py # Fixed version with normalization
├── model_manager.py                 # Handles model versioning
├── regime_smoother.py               # Prevents rapid regime changes
├── models/                          # Model versions
│   ├── v_20250702_094009/          # Best baseline model (94% accuracy)
│   └── regime_predictor_model.pkl  # Current active model
├── predictions/                     # Prediction history
├── emergency_backup/                # Backup of corrupted state
└── ml_config.json                  # Emergency configuration
```

### Database Schema
```sql
-- Current tables
predictions (id, timestamp, regime, confidence, market_score, indicators)
regime_changes (id, timestamp, from_regime, to_regime, confidence)

-- Needed for Phase 2
regime_feedback (prediction_id, actual_regime, feedback_timestamp, accuracy)
```

### Key Functions to Modify (Phase 2)
1. `update_actual_regime()` - Currently broken, needs price-based calculation
2. `retrain_model()` - Currently disabled, needs quality gates
3. `_save_prediction_to_db()` - Works but needs feedback integration
4. `optimize_thresholds()` - Needs balanced data before running

---

## 🎯 Other System TODOs

### High Priority
- [ ] Fix VSR scanner early market data requirements (currently needs 50 points, reduced to 20)
- [ ] Implement position size recommendations based on regime
- [ ] Add PnL tracking for regime-based trades

### Medium Priority  
- [ ] Create unified error handling for all scanners
- [ ] Implement scanner result caching (reduce API calls)
- [ ] Add regime-aware stop loss adjustments

### Low Priority
- [ ] Dashboard UI improvements
- [ ] Historical backtesting with regime filters
- [ ] Documentation updates

---

## 📝 Notes for Future Sessions

1. **CRITICAL**: Do NOT enable auto-retraining until Phase 3 quality gates are implemented
2. **Market Hours Only**: System runs 9:00 AM - 3:30 PM IST, Monday-Friday
3. **Emergency Restore**: Backup at `/Daily/Market_Regime/emergency_backup/backup_20250824_213039`
4. **Best Model**: v_20250702_094009 with 94% accuracy (currently active)
5. **Monitoring Dashboard**: Open `/Daily/Market_Regime/emergency_monitoring.html`

### Quick Commands
```bash
# Run Phase 1 verification
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python3 verify_phase1_fixes.py

# Check if Market Regime Analyzer is running
launchctl list | grep market_regime

# View real-time predictions
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log

# Emergency restore if needed
python3 emergency_fix_phase1.py
```

---

*Last Updated: 2025-08-26 12:35 IST*
*Status: Phase 2 FAILED - Critical regime monoculture issue persists*
*Next Action: Need to address root cause of 100% choppy_bullish predictions before proceeding*

## 🚨 CRITICAL ISSUE SUMMARY (2025-08-26)

### The Problem:
1. **100% Regime Monoculture**: All 780 recent predictions are `choppy_bullish`
2. **Phase 1 fixes were ineffective**: Despite normalization, predictions still show no diversity
3. **Phase 2 feedback collection failed**: Multiple technical issues prevented automatic feedback
4. **Model is not learning**: Without diverse predictions, feedback won't help

### Root Cause Analysis:
- The model appears to be stuck in a local minimum
- Market score normalization alone isn't enough
- The predictor may not be using the fixed version properly
- Possible issues with feature extraction or model weights

### Recommended Immediate Actions:
1. **Verify the fixed predictor is actually being used** in production
2. **Check if market_regime_predictor_fixed.py is loaded** by the analyzer
3. **Consider forcing regime diversity** through threshold adjustments
4. **Manual intervention may be needed** to break the monoculture

### Impact on System:
- ✅ **Dashboards remain functional** - No impact on existing services  
- ✅ **Trading operations unaffected** - Position sizing still works
- ❌ **ML predictions unreliable** - All predictions are the same regime
- ❌ **Cannot proceed to Phase 3** - Retraining would reinforce the problem

## Quick Status Check Commands

```bash
# Check Phase 2 feedback collection status
cd /Users/maverick/PycharmProjects/India-TS/Daily
./Market_Regime/check_phase2_status.sh

# Detailed monitoring with metrics
python3 Market_Regime/monitor_phase2.py

# View recent feedback collection logs
tail -20 logs/regime_feedback_collector.log

# Check if services are running
launchctl list | grep -E "regime-feedback|regime-validation"
```

## Expected by Tomorrow (2025-08-26 12:00 IST)

After ~78 predictions (every 5 min during 6.5 market hours):
- [ ] Feedback coverage should be >60% (allowing for 45-min delay)
- [ ] At least 40-50 validated predictions
- [ ] Some diversity in regime distribution
- [ ] Initial accuracy metrics available
- [ ] Ready to assess if we can proceed to Phase 3

If system meets criteria tomorrow, we'll implement Phase 3: Smart Retraining with quality gates and A/B testing.