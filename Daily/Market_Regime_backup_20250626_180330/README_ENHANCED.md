# Enhanced Market Regime Analysis System with Self-Improving Predictions

This enhanced system analyzes market trend strength based on Long vs Short reversal scan counts to determine the overall market regime and provides self-improving predictive capabilities.

## New Features

### 1. Self-Improving Prediction Model (`market_regime_predictor.py`)
- **Machine Learning Integration**: Uses Random Forest classifier to predict next market regime
- **Continuous Learning**: Tracks predictions vs actual outcomes and retrains automatically
- **Threshold Optimization**: Dynamically adjusts regime classification thresholds based on historical performance
- **Feature Engineering**: Extracts 16 features including:
  - Average and volatility of long/short counts
  - Trend direction and momentum
  - Moving averages and acceleration
  - Volume ratios and pattern scores

### 2. Performance Tracking
- **Accuracy Metrics**: Overall and per-regime accuracy tracking
- **Prediction History**: Maintains history of all predictions with outcomes
- **Model Insights**: Feature importance analysis and optimization history
- **Confidence Scoring**: Each prediction includes confidence level

### 3. Enhanced Output Structure
All outputs are now organized within the Market_Regime folder:
- `data/` - Optimized thresholds and configuration
- `results/` - Scanner output files (Excel and HTML)
- `logs/` - System and scanner logs
- `predictions/` - Prediction history and performance metrics
- `models/` - Saved ML models and scalers
- `scan_results/` - JSON scan summaries
- `trend_analysis/` - Trend strength reports
- `regime_analysis/` - Complete regime analysis reports

## Components

### Core Modules

1. **`market_regime_analyzer.py`** (Enhanced)
   - Integrates with new predictor module
   - Updates predictor with actual regimes for learning
   - Includes prediction insights in reports

2. **`market_regime_predictor.py`** (NEW)
   - Self-improving ML model for regime prediction
   - Tracks prediction accuracy and optimizes over time
   - Features:
     - Automatic retraining every 50 predictions
     - Threshold optimization every 100 predictions
     - Feature importance tracking
     - Confidence-based recommendations

3. **`Long_Reversal_Daily.py` & `Short_Reversal_Daily.py`** (Local copies)
   - Configured to output to Market_Regime/results/
   - Logs stored in Market_Regime/logs/

### Existing Components

4. **`reversal_trend_scanner.py`**
   - Updated to use local scanner copies
   - Outputs to Market_Regime directories

5. **`trend_strength_calculator.py`**
   - Enhanced with `get_scan_history()` method
   - Provides historical data for predictions

6. **`trend_dashboard.py`**
   - Visual HTML dashboard (unchanged)

7. **`run_market_regime_analysis.py`**
   - Simple runner script (unchanged)

## Usage

### Testing the System
```bash
python test_market_regime.py
```

### Manual Execution
```bash
python market_regime_analyzer.py
```

### Scheduled Execution
The system is configured to run every 30 minutes from 9:15 AM to 3:30 PM IST on weekdays.

Enable scheduling:
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
```

Disable scheduling:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
```

Check status:
```bash
launchctl list | grep market_regime
```

## Prediction Model Details

### How It Works
1. **Feature Extraction**: Analyzes patterns in historical scan data
2. **Prediction**: Uses Random Forest to predict next regime
3. **Tracking**: Records prediction with timestamp
4. **Validation**: Compares prediction with actual regime
5. **Learning**: Updates model based on accuracy
6. **Optimization**: Adjusts thresholds for better classification

### Prediction Features
- Long/Short count statistics (mean, std)
- Ratio analysis and changes
- Trend indicators (MA3, direction)
- Momentum and acceleration
- Historical patterns

### Model Performance
- Tracks overall accuracy
- Per-regime accuracy breakdown
- Feature importance ranking
- Optimization history

## Output Files

### Predictions Directory
- `predictions_history.json` - All predictions with outcomes
- `model_performance.json` - Accuracy metrics and insights

### Models Directory
- `regime_predictor_model.pkl` - Trained Random Forest model
- `regime_predictor_scaler.pkl` - Feature scaler

### Data Directory
- `optimized_thresholds.json` - Dynamically optimized regime thresholds

### Enhanced Reports
Regime reports now include:
- Current market regime analysis
- **Prediction for next regime with confidence**
- **Model performance metrics**
- **Regime change warnings**
- Historical context and momentum

## Trading Insights

The enhanced system provides:
1. **Predictive Alerts**: Warns of potential regime changes
2. **Confidence-Based Sizing**: Adjust positions based on prediction confidence
3. **Trend Anticipation**: Position for upcoming regime shifts
4. **Performance Tracking**: Monitor prediction accuracy over time

## Monitoring

Check logs for system health:
- `logs/market_regime_predictor.log` - Prediction model logs
- `logs/market_regime_analyzer.log` - Main system logs
- `logs/long_reversal_daily.log` - Long scanner logs
- `logs/short_reversal_daily.log` - Short scanner logs

## Continuous Improvement

The system automatically improves over time:
1. **Every 50 predictions**: Retrains the ML model
2. **Every 100 predictions**: Optimizes regime thresholds
3. **Continuous tracking**: Updates accuracy metrics in real-time

## Troubleshooting

1. **Model not predicting**
   - Need at least 3 historical scans
   - Check predictions/ directory permissions

2. **Low accuracy**
   - Model needs time to learn (50+ predictions)
   - Check if market conditions have changed significantly

3. **Scanner errors**
   - Verify config.ini has valid credentials
   - Check data/ directory exists in parent Daily folder