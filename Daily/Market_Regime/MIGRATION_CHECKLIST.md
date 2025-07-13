# Market Regime Migration Checklist

## Immediate Actions (Today)

- [ ] Stop main Market_Regime dashboards
  ```bash
  # Kill main system dashboards
  pkill -f "Market_Regime/dashboard"
  pkill -f "Market_Regime/run_dashboard"
  ```

- [ ] Backup current Daily system
  ```bash
  cp -r Daily/Market_Regime Daily/Market_Regime_backup_$(date +%Y%m%d)
  ```

- [ ] Export historical data from main system
  ```bash
  sqlite3 Market_Regime/data/regime_learning.db ".dump" > regime_data_backup_$(date +%Y%m%d).sql
  ```

## Phase 1: Feature Implementation (Priority Order)

### 1. Confidence Calculator (Day 1-2)
- [ ] Create `Daily/Market_Regime/confidence_calculator.py`
- [ ] Port confidence logic from main system
- [ ] Simplify to remove ML dependencies
- [ ] Add to market_regime_analyzer.py

### 2. Volatility Enhancement (Day 3)
- [ ] Enhance existing volatility calculations
- [ ] Add risk multiplier logic
- [ ] Integrate with regime analysis

### 3. Position Recommendations (Day 4)
- [ ] Create `Daily/Market_Regime/position_recommender.py`
- [ ] Implement sizing logic based on regime
- [ ] Add stop-loss multipliers
- [ ] Update output format

### 4. Historical Tracking (Day 5)
- [ ] Create `Daily/Market_Regime/regime_history_tracker.py`
- [ ] Implement 30-day rolling window
- [ ] Add regime persistence metrics
- [ ] Create performance tracking

## Phase 2: Integration Updates

### Update Output Format
- [ ] Modify market_regime_analyzer.py to include new fields
- [ ] Ensure backward compatibility
- [ ] Update result file format

### Dashboard Enhancements
- [ ] Add confidence display
- [ ] Show position recommendations
- [ ] Display historical regime chart
- [ ] Add volatility indicators

## Phase 3: Testing

### Parallel Testing
- [ ] Run both systems for comparison
- [ ] Log differences in classifications
- [ ] Validate confidence scores
- [ ] Check recommendation accuracy

### Integration Testing
- [ ] Verify scanner integration
- [ ] Test scheduled runs
- [ ] Validate file outputs
- [ ] Check dashboard updates

## Phase 4: Cutover

### Pre-Cutover
- [ ] Document all dependent systems
- [ ] Update integration points
- [ ] Prepare rollback plan
- [ ] Notify team of changes

### Cutover Day
- [ ] Stop main system schedulers
- [ ] Archive main system code
- [ ] Update all imports
- [ ] Monitor for issues

### Post-Cutover
- [ ] Verify all systems working
- [ ] Check scheduled runs
- [ ] Monitor for 24 hours
- [ ] Document any issues

## Code Templates

### Confidence Calculator Template
```python
class ConfidenceCalculator:
    def __init__(self):
        self.history_window = 10
        
    def calculate_confidence(self, regime_data):
        # Base confidence from ratio
        ratio = regime_data['ratio']
        base_confidence = self._ratio_to_confidence(ratio)
        
        # Stability factor
        stability = self._calculate_stability(regime_data.get('history', []))
        
        # Volume factor
        volume_factor = regime_data.get('volume_participation', 0.5)
        
        # Combined confidence
        confidence = base_confidence * (0.7 + 0.3 * stability)
        confidence = confidence * (0.5 + 0.5 * volume_factor)
        
        return min(max(confidence, 0.1), 0.95)
```

### Position Recommender Template
```python
class PositionRecommender:
    def __init__(self):
        self.regime_multipliers = {
            'strong_uptrend': 1.5,
            'uptrend': 1.2,
            'choppy_bullish': 1.0,
            'choppy': 0.8,
            'choppy_bearish': 0.8,
            'downtrend': 1.2,
            'strong_downtrend': 1.5
        }
        
    def get_recommendations(self, regime, confidence, volatility):
        base_multiplier = self.regime_multipliers.get(regime, 1.0)
        confidence_factor = 0.5 + (confidence * 0.5)
        volatility_factor = 2.0 - volatility.get('risk_multiplier', 1.0)
        
        return {
            'position_size_multiplier': base_multiplier * confidence_factor * volatility_factor,
            'stop_loss_multiplier': volatility.get('risk_multiplier', 1.0),
            'max_positions': self._calculate_max_positions(regime, volatility),
            'preferred_direction': self._get_preferred_direction(regime)
        }
```

## Success Metrics

- [ ] Daily system runs every 30 minutes without failure
- [ ] Confidence scores are logical and consistent
- [ ] Position recommendations align with regime
- [ ] Historical tracking captures all regime changes
- [ ] Dashboard displays all key metrics clearly
- [ ] No dependencies on main Market_Regime system

## Notes

- Keep backups of both systems until migration is proven stable
- Document any custom logic that differs from main system
- Consider adding unit tests for new components
- Monitor system performance for first week after migration