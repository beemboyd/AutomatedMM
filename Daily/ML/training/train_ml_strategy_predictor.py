#!/usr/bin/env python3
"""
Train ML Strategy Predictor
Uses historical reversal signals and market breadth data to predict optimal strategies
Without requiring Zerodha API for initial training
"""

import os
import sys
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import pytz
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MLStrategyPredictor:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.long_results_dir = os.path.join(self.base_dir, 'Daily', 'results')
        self.short_results_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
        self.breadth_data_dir = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 'historical_breadth_data')
        self.models_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'models')
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Create directories
        os.makedirs(self.models_dir, exist_ok=True)
    
    def load_reversal_signals(self, weeks_back=6):
        """Load reversal signals from past N weeks"""
        cutoff_date = datetime.now() - timedelta(weeks=weeks_back)
        
        # Aggregate daily signal counts
        daily_signals = {}
        
        # Load long signals
        long_files = glob.glob(os.path.join(self.long_results_dir, '*Reversal*.xlsx'))
        for file in long_files:
            try:
                filename = os.path.basename(file)
                date_str = filename.split('_')[-2]
                signal_date = datetime.strptime(date_str, '%Y%m%d')
                
                if signal_date < cutoff_date:
                    continue
                
                df = pd.read_excel(file)
                date_key = signal_date.strftime('%Y-%m-%d')
                
                if date_key not in daily_signals:
                    daily_signals[date_key] = {'long_count': 0, 'short_count': 0}
                
                daily_signals[date_key]['long_count'] += len(df)
                
            except Exception as e:
                logger.debug(f"Error reading {file}: {e}")
        
        # Load short signals
        short_files = glob.glob(os.path.join(self.short_results_dir, '*Reversal*.xlsx'))
        for file in short_files:
            try:
                filename = os.path.basename(file)
                date_str = filename.split('_')[-2]
                signal_date = datetime.strptime(date_str, '%Y%m%d')
                
                if signal_date < cutoff_date:
                    continue
                
                df = pd.read_excel(file)
                date_key = signal_date.strftime('%Y-%m-%d')
                
                if date_key not in daily_signals:
                    daily_signals[date_key] = {'long_count': 0, 'short_count': 0}
                
                daily_signals[date_key]['short_count'] += len(df)
                
            except Exception as e:
                logger.debug(f"Error reading {file}: {e}")
        
        return pd.DataFrame.from_dict(daily_signals, orient='index').reset_index()
    
    def load_breadth_data(self):
        """Load market breadth data"""
        breadth_file = os.path.join(self.breadth_data_dir, 'sma_breadth_historical_latest.json')
        
        with open(breadth_file, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
        df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
        
        # Calculate features
        df['sma20_roc_1d'] = df['sma20_percent'].diff(1)
        df['sma20_roc_5d'] = df['sma20_percent'].diff(5)
        df['sma20_ma5'] = df['sma20_percent'].rolling(5).mean()
        df['sma20_ma10'] = df['sma20_percent'].rolling(10).mean()
        df['breadth_momentum'] = df['sma20_percent'] - df['sma20_ma5']
        
        return df
    
    def create_training_dataset(self, signal_counts_df, breadth_df):
        """Create training dataset by merging signals with breadth data"""
        # Rename index column
        signal_counts_df.columns = ['date', 'long_count', 'short_count']
        signal_counts_df['date'] = pd.to_datetime(signal_counts_df['date'])
        
        # Merge with breadth data
        merged_df = pd.merge(breadth_df, signal_counts_df, on='date', how='inner')
        
        # Calculate additional features
        merged_df['signal_strength_diff'] = merged_df['long_count'] - merged_df['short_count']
        merged_df['signal_ratio'] = merged_df['long_count'] / (merged_df['long_count'] + merged_df['short_count'] + 1)
        
        # Create target based on which strategy would have been better
        # This is a simplified assumption based on market breadth conditions
        merged_df['best_strategy'] = 'NEUTRAL'
        
        # Long is better in moderate bullish conditions
        long_condition = (
            (merged_df['sma20_percent'] >= 55) & 
            (merged_df['sma20_percent'] <= 70) &
            (merged_df['breadth_momentum'] > 0)
        )
        merged_df.loc[long_condition, 'best_strategy'] = 'LONG'
        
        # Short is better in moderate bearish conditions
        short_condition = (
            (merged_df['sma20_percent'] >= 35) & 
            (merged_df['sma20_percent'] <= 50) &
            (merged_df['breadth_momentum'] < 0)
        )
        merged_df.loc[short_condition, 'best_strategy'] = 'SHORT'
        
        # Additional rules based on signal counts
        strong_long_signals = (
            (merged_df['long_count'] > merged_df['short_count'] * 1.5) &
            (merged_df['sma20_percent'] > 50)
        )
        merged_df.loc[strong_long_signals, 'best_strategy'] = 'LONG'
        
        strong_short_signals = (
            (merged_df['short_count'] > merged_df['long_count'] * 1.5) &
            (merged_df['sma20_percent'] < 50)
        )
        merged_df.loc[strong_short_signals, 'best_strategy'] = 'SHORT'
        
        return merged_df
    
    def train_strategy_predictor(self, training_data):
        """Train the ML model to predict optimal strategy"""
        # Prepare features
        feature_columns = [
            'sma20_percent', 'sma50_percent', 'sma20_roc_1d', 'sma20_roc_5d',
            'sma20_ma5', 'sma20_ma10', 'breadth_momentum',
            'long_count', 'short_count', 'signal_strength_diff', 'signal_ratio'
        ]
        
        # Filter valid data
        valid_data = training_data.dropna(subset=feature_columns + ['best_strategy'])
        
        X = valid_data[feature_columns]
        y = valid_data['best_strategy']
        
        logger.info(f"Training data shape: {X.shape}")
        logger.info(f"Class distribution: \n{y.value_counts()}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train models
        models = {
            'RandomForest': RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            ),
            'GradientBoosting': GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
        }
        
        best_model = None
        best_score = 0
        
        for name, model in models.items():
            logger.info(f"\nTraining {name}...")
            
            # Train
            model.fit(X_train, y_train)
            
            # Evaluate
            train_score = model.score(X_train, y_train)
            test_score = model.score(X_test, y_test)
            cv_scores = cross_val_score(model, X_train, y_train, cv=5)
            
            logger.info(f"Train Accuracy: {train_score:.4f}")
            logger.info(f"Test Accuracy: {test_score:.4f}")
            logger.info(f"CV Score: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
            
            # Detailed classification report
            y_pred = model.predict(X_test)
            logger.info("\nClassification Report:")
            logger.info(classification_report(y_test, y_pred))
            
            # Feature importance
            if hasattr(model, 'feature_importances_'):
                importance_df = pd.DataFrame({
                    'feature': feature_columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                logger.info("\nTop 5 Important Features:")
                for _, row in importance_df.head().iterrows():
                    logger.info(f"  {row['feature']}: {row['importance']:.4f}")
            
            if test_score > best_score:
                best_score = test_score
                best_model = model
        
        return best_model, {
            'test_accuracy': best_score,
            'feature_columns': feature_columns,
            'model_type': type(best_model).__name__,
            'training_samples': len(X),
            'class_distribution': y.value_counts().to_dict()
        }
    
    def save_model(self, model, metadata):
        """Save the trained model and metadata"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save model
        model_path = os.path.join(self.models_dir, f'strategy_predictor_{timestamp}.pkl')
        joblib.dump(model, model_path)
        
        # Also save as current model
        current_path = os.path.join(self.models_dir, 'current_strategy_predictor.pkl')
        joblib.dump(model, current_path)
        
        # Save metadata
        metadata['timestamp'] = timestamp
        metadata['model_path'] = model_path
        
        metadata_path = os.path.join(self.models_dir, f'strategy_predictor_metadata_{timestamp}.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Also save as current metadata
        current_metadata_path = os.path.join(self.models_dir, 'current_strategy_metadata.json')
        with open(current_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved to {model_path}")
        return model_path
    
    def run_training_pipeline(self):
        """Run the complete training pipeline"""
        logger.info("="*60)
        logger.info("Starting ML Strategy Predictor Training")
        logger.info("="*60)
        
        # Step 1: Load signal counts
        logger.info("\nStep 1: Loading reversal signal counts...")
        signal_counts = self.load_reversal_signals(weeks_back=6)
        logger.info(f"Loaded signal data for {len(signal_counts)} days")
        
        # Step 2: Load breadth data
        logger.info("\nStep 2: Loading market breadth data...")
        breadth_data = self.load_breadth_data()
        logger.info(f"Breadth data shape: {breadth_data.shape}")
        
        # Step 3: Create training dataset
        logger.info("\nStep 3: Creating training dataset...")
        training_data = self.create_training_dataset(signal_counts, breadth_data)
        logger.info(f"Training data shape: {training_data.shape}")
        
        # Save training data for analysis
        training_data.to_csv(os.path.join(self.models_dir, 'training_data.csv'), index=False)
        
        # Step 4: Train model
        logger.info("\nStep 4: Training prediction model...")
        model, metadata = self.train_strategy_predictor(training_data)
        
        # Step 5: Save model
        logger.info("\nStep 5: Saving model...")
        model_path = self.save_model(model, metadata)
        
        logger.info("\n" + "="*60)
        logger.info("Training Complete!")
        logger.info(f"Model saved to: {model_path}")
        logger.info(f"Test Accuracy: {metadata['test_accuracy']:.4f}")
        logger.info("="*60)
        
        return model, metadata

def main():
    """Main training function"""
    trainer = MLStrategyPredictor()
    model, metadata = trainer.run_training_pipeline()

if __name__ == "__main__":
    main()