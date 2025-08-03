# India-TS Machine Learning Module

## Overview
The ML module provides machine learning capabilities for the India-TS trading system, including market regime prediction, breadth optimization, strategy recommendations, and pattern analysis.

## Directory Structure

```
Daily/ML/
├── README.md                    # This comprehensive documentation
├── ML_MODULE_SUMMARY.md        # Legacy summary (maintained for compatibility)
├── analysis_output.txt         # Analysis outputs
├── core/                       # Core ML models and base classes
│   ├── breadth_optimization_model.py    # Main breadth optimization ML model
│   └── regime_model_manager.py          # Market regime model management
├── predictors/                 # Real-time prediction modules
│   └── breadth_strategy_predictor.py    # Real-time strategy predictions
├── analyzers/                  # Analysis and pattern detection
│   └── keltner_channel_filter_analyzer.py  # Keltner channel analysis
├── training/                   # Model training and retraining scripts
│   └── retrain_breadth_model.py         # Weekly model retraining
├── utils/                      # Utility functions and helpers
│   ├── show_filtered_tickers.py         # Display utility for filtered results
│   └── fix_excel_dates.py               # Date fixing utility
├── notebooks/                  # Jupyter notebooks for experimentation
├── experiments/                # Experimental models and tests
├── models/                     # Trained model files
│   ├── long_model.pkl          # Trained long strategy model
│   ├── short_model.pkl         # Trained short strategy model
│   └── optimization_report_20250803.json  # Model performance report
├── logs/                       # Training and execution logs
│   ├── breadth_optimization_20250803.log
│   └── keltner_filter_analyzer.log
└── results/                    # Analysis results and reports
    ├── keltner_analysis_clean_report.xlsx
    └── keltner_filter_comparison_*.txt/xlsx  # Historical comparison files
```

## Core Components

### 1. Breadth Optimization Model (`core/breadth_optimization_model.py`)
**Purpose**: Main ML model using GradientBoostingRegressor for market breadth analysis
**Key Features**:
- Trains separate models for long and short strategies
- Uses market breadth indicators as primary features
- Provides strategy recommendations based on current market conditions

**Features Used**:
- SMA20/SMA50 breadth percentages
- Breadth momentum (1-day, 3-day, 5-day rate of change)
- Breadth volatility metrics
- Trend indicators
- Days since extremes

**Model Performance**:
- Long Model R²: 0.78
- Short Model R²: 0.83
- Top feature: SMA20 breadth percentage (93.7% importance for long, 89.1% for short)

### 2. Strategy Predictor (`predictors/breadth_strategy_predictor.py`)
**Purpose**: Real-time strategy predictions and recommendations
**Outputs**:
- Current strategy recommendation (LONG/SHORT)
- Expected PnL for both strategies
- Confidence levels
- Market condition analysis
- HTML widgets for dashboard integration

### 3. Regime Model Manager (`core/regime_model_manager.py`)
**Purpose**: Manages ML models for market regime prediction
**Features**:
- Model persistence and versioning
- Performance tracking
- Model backup and restoration
- Cross-validation and evaluation metrics

### 4. Keltner Channel Analyzer (`analyzers/keltner_channel_filter_analyzer.py`)
**Purpose**: Analyzes Keltner Channel patterns and generates filtered ticker lists
**Outputs**:
- Statistical analysis of Keltner patterns
- Performance metrics by pattern type
- Excel reports with detailed analysis

## ML-Validated Trading Insights

### Optimal Market Conditions

**Long Strategy (ML-Optimized)**:
- Best performance: SMA20 breadth 55-70%
- Avoid conditions: Below 45% or above 70%
- Confidence: High (R² = 0.78)

**Short Strategy (ML-Optimized)**:
- Best performance: SMA20 breadth 35-50%
- Good performance: 25-35%
- Avoid conditions: Below 20% or above 50%
- Confidence: Very High (R² = 0.83)

## Usage Examples

### Get Current Strategy Recommendation
```python
from ML.predictors.breadth_strategy_predictor import BreadthStrategyPredictor

predictor = BreadthStrategyPredictor()
recommendation = predictor.get_strategy_recommendation()
print(f"Strategy: {recommendation['recommended_strategy']}")
print(f"Confidence: {recommendation['confidence']}")
print(f"Expected PnL: {recommendation['expected_pnl']}")
```

### Train/Retrain Models
```bash
# Weekly retraining (recommended)
python3 Daily/ML/training/retrain_breadth_model.py

# Force retrain with new data
python3 Daily/ML/training/retrain_breadth_model.py --force-retrain
```

### Run Keltner Analysis
```python
from ML.analyzers.keltner_channel_filter_analyzer import KeltnerChannelAnalyzer

analyzer = KeltnerChannelAnalyzer()
results = analyzer.analyze_patterns()
analyzer.generate_excel_report(results)
```

## Integration Points

### 1. Dashboard Integration
- Real-time ML predictions displayed in market regime dashboard
- Confidence indicators for strategy recommendations
- Performance tracking widgets

### 2. Trading System Integration
- Strategy recommendations feed into order placement logic
- Confidence levels adjust position sizing
- Risk management based on ML predictions

### 3. Scanner Integration
- ML-filtered ticker recommendations
- Pattern-based screening using trained models
- Real-time market condition assessment

## Model Management

### Training Schedule
- **Automatic**: Weekly retraining via scheduled job
- **Manual**: On-demand retraining when needed
- **Data Source**: Historical breadth data and actual trading performance

### Model Versioning
- Models are versioned with timestamp
- Previous versions backed up automatically
- Performance comparison reports generated

### Quality Assurance
- Cross-validation on training
- Out-of-sample testing
- Performance degradation monitoring

## Development Guidelines

### Adding New Models
1. Create model class in `core/` directory
2. Implement standard interface methods:
   - `train(data)` - Training method
   - `predict(features)` - Prediction method
   - `evaluate(test_data)` - Evaluation method
   - `save_model(path)` - Model persistence
   - `load_model(path)` - Model loading

2. Add predictor wrapper in `predictors/` if real-time predictions needed
3. Create training script in `training/` directory
4. Update this documentation

### Adding New Features
1. Document feature engineering in model class
2. Include feature importance analysis
3. Validate feature impact on model performance
4. Update feature documentation

### Adding New Analyzers
1. Create analyzer class in `analyzers/` directory
2. Implement standard methods:
   - `analyze()` - Main analysis method
   - `generate_report()` - Report generation
   - `save_results()` - Result persistence

## Performance Monitoring

### Metrics Tracked
- Model accuracy (R², MSE, MAE)
- Prediction confidence distributions
- Feature importance stability
- Trading performance correlation

### Alerts and Monitoring
- Model performance degradation alerts
- Data quality issues
- Prediction confidence drops
- Feature drift detection

## Future Enhancements

### Short-term (Next Month)
1. Include actual ticker performance data instead of simulated
2. Add ensemble models for better predictions
3. Implement feature selection optimization
4. Add real-time model performance monitoring

### Medium-term (Next Quarter)
1. Implement deep learning models for pattern recognition
2. Add sentiment analysis integration
3. Create multi-timeframe prediction models
4. Develop automated feature engineering

### Long-term (Next 6 Months)
1. Real-time model updating based on live trading results
2. Advanced market regime detection using unsupervised learning
3. Integration with external data sources (news, economic indicators)
4. Automated strategy discovery using reinforcement learning

## Troubleshooting

### Common Issues
1. **Model Loading Errors**: Check file paths and model compatibility
2. **Prediction Failures**: Validate input data format and feature availability
3. **Poor Performance**: Check data quality and consider retraining
4. **Memory Issues**: Optimize model size or implement batch processing

### Log Locations
- Training logs: `Daily/ML/logs/`
- Model performance: `Daily/ML/models/optimization_report_*.json`
- Analysis results: `Daily/ML/results/`

### Support
- Check logs for detailed error messages
- Validate data pipeline integrity
- Review model performance reports
- Test with known good data samples

## Dependencies

### Required Python Packages
- scikit-learn (>=1.0.0)
- pandas (>=1.3.0)
- numpy (>=1.21.0)
- joblib (>=1.1.0)
- matplotlib (>=3.4.0)
- seaborn (>=0.11.0)

### System Requirements
- Python 3.8+
- Minimum 4GB RAM for model training
- 1GB disk space for models and results

## Change Log

### 2025-08-03
- Reorganized ML module structure with proper subdirectories
- Created comprehensive documentation
- Moved existing files to appropriate locations
- Improved model management and organization

### Previous Changes
- See ML_MODULE_SUMMARY.md for historical changes
- Training logs contain detailed change history
- Model performance reports track improvements over time