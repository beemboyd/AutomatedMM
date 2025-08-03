#!/usr/bin/env python3
"""
Train ML Model from Actual Reversal Strategy Results
Uses historical performance data from long and short reversal strategies
"""

import os
import sys
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error
import joblib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReversalStrategyTrainer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.long_results_dir = os.path.join(self.base_dir, 'Daily', 'results')
        self.short_results_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
        self.breadth_data_dir = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 'historical_breadth_data')
        self.models_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'models')
        
        # Create models directory if it doesn't exist
        os.makedirs(self.models_dir, exist_ok=True)
        
    def load_reversal_results(self, strategy_type='long'):
        """Load all reversal strategy results"""
        results_dir = self.long_results_dir if strategy_type == 'long' else self.short_results_dir
        pattern = '*Reversal*.xlsx'
        
        all_results = []
        files = glob.glob(os.path.join(results_dir, pattern))
        
        logger.info(f"Found {len(files)} {strategy_type} reversal result files")
        
        for file in files:
            try:
                # Extract date from filename
                filename = os.path.basename(file)
                date_str = filename.split('_')[-2]  # Extract date part
                time_str = filename.split('_')[-1].replace('.xlsx', '')
                
                # Parse date
                try:
                    date = datetime.strptime(date_str, '%Y%m%d')
                except:
                    continue
                
                # Read Excel file
                df = pd.read_excel(file)
                
                if len(df) > 0:
                    # Calculate average metrics for this scan
                    result = {
                        'date': date.strftime('%Y-%m-%d'),
                        'time': time_str,
                        'strategy': strategy_type,
                        'ticker_count': len(df),
                        'file': filename
                    }
                    
                    # Add performance metrics if available
                    if 'Change%' in df.columns:
                        result['avg_change'] = df['Change%'].mean()
                        result['max_change'] = df['Change%'].max()
                        result['min_change'] = df['Change%'].min()
                        result['positive_count'] = (df['Change%'] > 0).sum()
                        result['negative_count'] = (df['Change%'] < 0).sum()
                        result['win_rate'] = result['positive_count'] / len(df) if len(df) > 0 else 0
                    
                    all_results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error reading {file}: {e}")
                continue
        
        return pd.DataFrame(all_results)
    
    def load_breadth_data(self):
        """Load historical breadth data"""
        breadth_file = os.path.join(self.breadth_data_dir, 'sma_breadth_historical_latest.json')
        
        with open(breadth_file, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
        df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
        
        return df
    
    def merge_data(self, reversal_results, breadth_data):
        """Merge reversal results with breadth data"""
        # Convert dates for merging
        reversal_results['date'] = pd.to_datetime(reversal_results['date'])
        
        # Group by date and aggregate results
        daily_results = reversal_results.groupby(['date', 'strategy']).agg({
            'ticker_count': 'sum',
            'avg_change': 'mean',
            'win_rate': 'mean',
            'positive_count': 'sum',
            'negative_count': 'sum'
        }).reset_index()
        
        # Merge with breadth data
        merged = pd.merge(daily_results, breadth_data, on='date', how='inner')
        
        # Calculate additional features
        merged['sma20_roc_1d'] = merged['sma20_percent'].diff(1)
        merged['sma20_roc_5d'] = merged['sma20_percent'].diff(5)
        merged['sma20_ma5'] = merged['sma20_percent'].rolling(5).mean()
        merged['sma20_ma10'] = merged['sma20_percent'].rolling(10).mean()
        merged['sma20_std5'] = merged['sma20_percent'].rolling(5).std()
        
        # Add trend features
        merged['uptrend'] = ((merged['sma20_percent'] > merged['sma20_ma5']) & 
                            (merged['sma20_ma5'] > merged['sma20_ma10'])).astype(int)
        merged['downtrend'] = ((merged['sma20_percent'] < merged['sma20_ma5']) & 
                              (merged['sma20_ma5'] < merged['sma20_ma10'])).astype(int)
        
        return merged.dropna()
    
    def prepare_features(self, data):
        """Prepare features for ML model"""
        feature_columns = [
            'sma20_percent', 'sma50_percent', 'sma20_roc_1d', 'sma20_roc_5d',
            'sma20_ma5', 'sma20_ma10', 'sma20_std5', 'uptrend', 'downtrend'
        ]
        
        X = data[feature_columns]
        y = data['avg_change']  # Target is average change percentage
        
        return X, y
    
    def train_model(self, X, y, strategy_type='long'):
        """Train the ML model"""
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train model
        model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        
        logger.info(f"{strategy_type.upper()} Model Performance:")
        logger.info(f"  Train R²: {train_score:.4f}")
        logger.info(f"  Test R²: {test_score:.4f}")
        logger.info(f"  MAE: {mae:.4f}%")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info(f"\nFeature Importance:")
        for _, row in feature_importance.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")
        
        return model, {
            'train_r2': train_score,
            'test_r2': test_score,
            'mae': mae,
            'feature_importance': feature_importance.to_dict('records')
        }
    
    def save_model(self, model, metrics, strategy_type='long'):
        """Save the trained model"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save model
        model_path = os.path.join(self.models_dir, f'{strategy_type}_reversal_model_{timestamp}.pkl')
        joblib.dump(model, model_path)
        logger.info(f"Model saved to {model_path}")
        
        # Also save as the current model
        current_model_path = os.path.join(self.models_dir, f'{strategy_type}_model.pkl')
        joblib.dump(model, current_model_path)
        
        # Save metrics
        metrics['model_path'] = model_path
        metrics['timestamp'] = timestamp
        metrics['strategy'] = strategy_type
        
        metrics_path = os.path.join(self.models_dir, f'{strategy_type}_model_metrics_{timestamp}.json')
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        return model_path
    
    def train_both_models(self):
        """Train both long and short models"""
        # Load breadth data
        logger.info("Loading breadth data...")
        breadth_data = self.load_breadth_data()
        
        results = {}
        
        for strategy in ['long', 'short']:
            logger.info(f"\n{'='*60}")
            logger.info(f"Training {strategy.upper()} strategy model...")
            logger.info(f"{'='*60}")
            
            # Load reversal results
            reversal_results = self.load_reversal_results(strategy)
            
            if len(reversal_results) == 0:
                logger.warning(f"No {strategy} reversal results found")
                continue
            
            # Merge with breadth data
            merged_data = self.merge_data(reversal_results, breadth_data)
            logger.info(f"Merged data shape: {merged_data.shape}")
            
            # Prepare features
            X, y = self.prepare_features(merged_data)
            
            # Train model
            model, metrics = self.train_model(X, y, strategy)
            
            # Save model
            model_path = self.save_model(model, metrics, strategy)
            
            results[strategy] = {
                'model_path': model_path,
                'metrics': metrics,
                'data_points': len(merged_data)
            }
        
        # Update optimization report
        report = {
            'model_version': datetime.now().strftime('%Y%m%d'),
            'training_date': datetime.now().isoformat(),
            'models': results,
            'breadth_ranges': {
                'long': {
                    'optimal': '55-70%',
                    'acceptable': '45-55%',
                    'avoid': 'Below 45% or Above 70%'
                },
                'short': {
                    'optimal': '35-50%',
                    'acceptable': '25-35%',
                    'avoid': 'Below 20% or Above 50%'
                }
            }
        }
        
        report_path = os.path.join(self.models_dir, f'optimization_report_{datetime.now().strftime("%Y%m%d")}.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nTraining complete! Report saved to {report_path}")
        return results

def main():
    """Main training function"""
    trainer = ReversalStrategyTrainer()
    results = trainer.train_both_models()
    
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    
    for strategy, result in results.items():
        print(f"\n{strategy.upper()} Model:")
        print(f"  Data points: {result['data_points']}")
        print(f"  Test R²: {result['metrics']['test_r2']:.4f}")
        print(f"  MAE: {result['metrics']['mae']:.4f}%")

if __name__ == "__main__":
    main()