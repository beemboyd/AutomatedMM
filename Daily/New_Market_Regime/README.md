# New Market Regime ML System

## Overview
A clean, modular implementation of Market Regime prediction using ML best practices.

## Architecture
```
Data Ingestion → Validation → Feature Engineering → Training → Model Registry → Serving → Monitoring → Auto-Adaptation
```

## Directory Structure
```
New_Market_Regime/
├── README.md                    # This file
├── config/                      # Configuration files
│   ├── config.yaml             # Main configuration
│   ├── features.yaml           # Feature definitions
│   └── models.yaml             # Model configurations
├── data/                       # Data storage
│   ├── raw/                    # Raw ingested data
│   ├── cleaned/                # Validated, cleaned data
│   ├── features/               # Feature store
│   └── labels/                 # Labeled datasets
├── src/                        # Source code
│   ├── ingestion/              # Data ingestion modules
│   ├── validation/             # Data cleaning & validation
│   ├── features/               # Feature engineering
│   ├── training/               # Model training
│   ├── serving/                # Model serving
│   └── monitoring/             # Monitoring & drift detection
├── models/                     # Model registry
│   ├── registry.json           # Model metadata
│   └── artifacts/              # Saved model files
├── notebooks/                  # Exploration & analysis
├── tests/                      # Unit tests
└── logs/                       # System logs
```

## Phases

### Phase 1: Data Pipeline (Week 1)
**Goal**: Reliable data ingestion and validation

**Components**:
1. **Data Ingestor** (`src/ingestion/data_ingestor.py`)
   - Reuse existing scanner results
   - Collect market data every 5 minutes
   - Store in structured format

2. **Data Validator** (`src/validation/data_validator.py`)
   - Remove outliers (inf, 0, NaN)
   - Handle access token errors
   - Enforce consistent schema
   - Log validation issues

**Deliverables**:
- Clean data pipeline
- Validation reports
- Schema documentation

### Phase 2: Feature Engineering (Week 1-2)
**Goal**: Consistent feature generation for training and serving

**Components**:
1. **Feature Builder** (`src/features/feature_builder.py`)
   - Price-based features (returns, volatility)
   - Technical indicators (RSI, MACD, moving averages)
   - Market breadth metrics
   - Volume features

2. **Feature Store** (`src/features/feature_store.py`)
   - Centralized feature storage
   - Version control for features
   - Same logic for training and serving

3. **Regime Labeler** (`src/features/regime_labeler.py`)
   - Define regime change points
   - Label historical data
   - Store labeled datasets

**Deliverables**:
- Feature pipeline
- Feature documentation
- Labeled training data

### Phase 3: Model Development (Week 2)
**Goal**: Train robust models with proper validation

**Components**:
1. **Model Trainer** (`src/training/model_trainer.py`)
   - Time-based train/test split
   - Random Forest implementation
   - Hyperparameter tuning
   - Cross-validation

2. **Model Evaluator** (`src/training/model_evaluator.py`)
   - Compare with baseline
   - Calculate metrics (accuracy, precision, recall)
   - Confusion matrix analysis
   - Feature importance

3. **Model Registry** (`src/training/model_registry.py`)
   - Save trained models
   - Store metadata (date, metrics, version)
   - Model versioning
   - Rollback capability

**Deliverables**:
- Trained model
- Performance reports
- Model comparison results

### Phase 4: Model Serving (Week 3)
**Goal**: Deploy model for predictions

**Components**:
1. **Batch Predictor** (`src/serving/batch_predictor.py`)
   - Hourly prediction jobs
   - Store predictions in database
   - Generate reports

2. **API Server** (`src/serving/api_server.py`)
   - REST API on port 8080
   - Real-time predictions
   - Web dashboard integration

3. **Prediction Store** (`src/serving/prediction_store.py`)
   - Store all predictions
   - Track prediction history
   - Enable backtesting

**Deliverables**:
- Working API
- Dashboard integration
- Prediction history

### Phase 5: Monitoring & Auto-Adaptation (Week 3-4)
**Goal**: Self-improving system

**Components**:
1. **Drift Detector** (`src/monitoring/drift_detector.py`)
   - Monitor feature distributions
   - Detect prediction drift
   - Raise alerts

2. **Performance Monitor** (`src/monitoring/performance_monitor.py`)
   - Track accuracy over time
   - Compare predictions vs actual
   - Generate reports

3. **Auto Retrainer** (`src/monitoring/auto_retrainer.py`)
   - Trigger retraining on drift
   - A/B test new models
   - Automatic model updates
   - Rollback on failure

**Deliverables**:
- Monitoring dashboard
- Alert system
- Auto-retraining pipeline

## Implementation Plan

### Week 1: Foundation
- [ ] Set up folder structure
- [ ] Implement data ingestion
- [ ] Build validation pipeline
- [ ] Start feature engineering

### Week 2: ML Core
- [ ] Complete feature engineering
- [ ] Implement training pipeline
- [ ] Build model registry
- [ ] Create baseline model

### Week 3: Deployment
- [ ] Build prediction API
- [ ] Create batch predictor
- [ ] Integrate with dashboard
- [ ] Deploy initial model

### Week 4: Intelligence
- [ ] Implement drift detection
- [ ] Build monitoring system
- [ ] Create auto-retraining
- [ ] Complete feedback loop

## Success Criteria
1. **Data Quality**: <1% invalid data after validation
2. **Model Performance**: >85% accuracy, no regime >40%
3. **System Reliability**: 99% uptime, <100ms prediction latency
4. **Adaptability**: Auto-retrain within 24hrs of drift detection

## Key Principles
1. **Modularity**: Each component is independent
2. **Reusability**: Shared code between training and serving
3. **Observability**: Comprehensive logging and monitoring
4. **Safety**: Rollback capability at every stage
5. **Simplicity**: Clear, understandable code

## Quick Start
```bash
# Set up environment
cd Daily/New_Market_Regime
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run data ingestion
python src/ingestion/data_ingestor.py

# Train model
python src/training/model_trainer.py

# Start API server
python src/serving/api_server.py
```

## Next Steps
1. Create folder structure
2. Define configuration files
3. Build data ingestion module
4. Start with simple validation rules