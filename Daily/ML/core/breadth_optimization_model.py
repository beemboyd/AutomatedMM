#!/usr/bin/env python3
"""
ML-based Breadth Optimization Model
Continuously learns and optimizes trading strategies based on market breadth
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
import pickle
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class BreadthOptimizationModel:
    def __init__(self):
        """Initialize the ML model for breadth optimization"""
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        os.makedirs(self.model_dir, exist_ok=True)
        
        self.setup_logging()
        
        # Models for long and short strategies
        self.long_model = None
        self.short_model = None
        
        # Feature engineering parameters
        self.breadth_bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        # Performance tracking
        self.performance_history = {
            'long': [],
            'short': []
        }
        
        # Load existing models if available
        self.load_models()
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'breadth_optimization_{datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_historical_data(self):
        """Load and prepare historical breadth and performance data"""
        try:
            # Load breadth data
            breadth_file = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                       'historical_breadth_data', 'sma_breadth_historical_latest.json')
            
            with open(breadth_file, 'r') as f:
                breadth_data = json.load(f)
            
            breadth_df = pd.DataFrame(breadth_data)
            breadth_df['date'] = pd.to_datetime(breadth_df['date'])
            breadth_df['sma20_percent'] = breadth_df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
            breadth_df['sma50_percent'] = breadth_df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
            
            self.logger.info(f"Loaded {len(breadth_df)} days of breadth data")
            
            return breadth_df
            
        except Exception as e:
            self.logger.error(f"Error loading historical data: {e}")
            return pd.DataFrame()
    
    def engineer_features(self, breadth_df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced features for ML model"""
        df = breadth_df.copy()
        
        # Basic breadth features
        df['sma20_50_ratio'] = df['sma20_percent'] / (df['sma50_percent'] + 1e-6)
        df['sma20_50_diff'] = df['sma20_percent'] - df['sma50_percent']
        
        # Breadth momentum (rate of change)
        df['sma20_roc_1d'] = df['sma20_percent'].diff(1)
        df['sma20_roc_3d'] = df['sma20_percent'].diff(3)
        df['sma20_roc_5d'] = df['sma20_percent'].diff(5)
        
        # Moving averages of breadth
        df['sma20_ma3'] = df['sma20_percent'].rolling(3).mean()
        df['sma20_ma5'] = df['sma20_percent'].rolling(5).mean()
        df['sma20_ma10'] = df['sma20_percent'].rolling(10).mean()
        
        # Volatility of breadth
        df['sma20_std5'] = df['sma20_percent'].rolling(5).std()
        df['sma20_std10'] = df['sma20_percent'].rolling(10).std()
        
        # Breadth regime features
        df['breadth_regime'] = pd.cut(df['sma20_percent'], bins=self.breadth_bins, labels=False)
        df['extreme_low'] = (df['sma20_percent'] < 20).astype(int)
        df['extreme_high'] = (df['sma20_percent'] > 80).astype(int)
        df['neutral_zone'] = ((df['sma20_percent'] >= 40) & (df['sma20_percent'] <= 60)).astype(int)
        
        # Trend features
        df['uptrend'] = ((df['sma20_percent'] > df['sma20_ma5']) & 
                        (df['sma20_ma5'] > df['sma20_ma10'])).astype(int)
        df['downtrend'] = ((df['sma20_percent'] < df['sma20_ma5']) & 
                          (df['sma20_ma5'] < df['sma20_ma10'])).astype(int)
        
        # Days since extremes
        df['days_since_low'] = 0
        df['days_since_high'] = 0
        
        for i in range(1, len(df)):
            if df.iloc[i]['sma20_percent'] < 20:
                df.iloc[i, df.columns.get_loc('days_since_low')] = 0
            else:
                df.iloc[i, df.columns.get_loc('days_since_low')] = df.iloc[i-1]['days_since_low'] + 1
            
            if df.iloc[i]['sma20_percent'] > 80:
                df.iloc[i, df.columns.get_loc('days_since_high')] = 0
            else:
                df.iloc[i, df.columns.get_loc('days_since_high')] = df.iloc[i-1]['days_since_high'] + 1
        
        return df.fillna(0)
    
    def simulate_performance(self, breadth_features: pd.DataFrame) -> pd.DataFrame:
        """Simulate performance based on historical patterns"""
        df = breadth_features.copy()
        
        # Simulate long performance based on breadth
        df['long_success_rate'] = 0.0
        df['long_avg_pnl'] = 0.0
        
        # Define performance by breadth ranges (based on our analysis)
        for i, row in df.iterrows():
            sma20 = row['sma20_percent']
            
            # Long performance simulation
            if 55 <= sma20 <= 70:
                df.at[i, 'long_success_rate'] = np.random.normal(45, 5)
                df.at[i, 'long_avg_pnl'] = np.random.normal(0.4, 0.2)
            elif 45 <= sma20 < 55:
                df.at[i, 'long_success_rate'] = np.random.normal(35, 5)
                df.at[i, 'long_avg_pnl'] = np.random.normal(-0.5, 0.3)
            elif sma20 < 45:
                df.at[i, 'long_success_rate'] = np.random.normal(20, 5)
                df.at[i, 'long_avg_pnl'] = np.random.normal(-2.5, 0.5)
            else:
                df.at[i, 'long_success_rate'] = np.random.normal(40, 5)
                df.at[i, 'long_avg_pnl'] = np.random.normal(0.1, 0.3)
            
            # Short performance simulation
            if 35 <= sma20 <= 50:
                df.at[i, 'short_success_rate'] = np.random.normal(75, 5)
                df.at[i, 'short_avg_pnl'] = np.random.normal(2.5, 0.5)
            elif 25 <= sma20 < 35:
                df.at[i, 'short_success_rate'] = np.random.normal(65, 5)
                df.at[i, 'short_avg_pnl'] = np.random.normal(0.8, 0.3)
            elif sma20 < 20:
                df.at[i, 'short_success_rate'] = np.random.normal(55, 5)
                df.at[i, 'short_avg_pnl'] = np.random.normal(-0.5, 0.4)
            else:
                df.at[i, 'short_success_rate'] = np.random.normal(40, 5)
                df.at[i, 'short_avg_pnl'] = np.random.normal(-1.0, 0.5)
        
        return df
    
    def train_models(self, features_df: pd.DataFrame):
        """Train ML models for long and short strategies"""
        # Prepare features
        feature_cols = [
            'sma20_percent', 'sma50_percent', 'sma20_50_ratio', 'sma20_50_diff',
            'sma20_roc_1d', 'sma20_roc_3d', 'sma20_roc_5d',
            'sma20_ma3', 'sma20_ma5', 'sma20_ma10',
            'sma20_std5', 'sma20_std10',
            'extreme_low', 'extreme_high', 'neutral_zone',
            'uptrend', 'downtrend',
            'days_since_low', 'days_since_high'
        ]
        
        X = features_df[feature_cols]
        
        # Train long model
        y_long = features_df['long_avg_pnl']
        X_train, X_test, y_train, y_test = train_test_split(X, y_long, test_size=0.2, random_state=42)
        
        self.long_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        self.long_model.fit(X_train, y_train)
        
        # Evaluate long model
        long_pred = self.long_model.predict(X_test)
        long_mse = mean_squared_error(y_test, long_pred)
        long_r2 = r2_score(y_test, long_pred)
        
        self.logger.info(f"Long Model - MSE: {long_mse:.4f}, R2: {long_r2:.4f}")
        
        # Train short model
        y_short = features_df['short_avg_pnl']
        X_train, X_test, y_train, y_test = train_test_split(X, y_short, test_size=0.2, random_state=42)
        
        self.short_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        self.short_model.fit(X_train, y_train)
        
        # Evaluate short model
        short_pred = self.short_model.predict(X_test)
        short_mse = mean_squared_error(y_test, short_pred)
        short_r2 = r2_score(y_test, short_pred)
        
        self.logger.info(f"Short Model - MSE: {short_mse:.4f}, R2: {short_r2:.4f}")
        
        # Feature importance
        self.analyze_feature_importance(feature_cols)
    
    def analyze_feature_importance(self, feature_cols):
        """Analyze and log feature importance"""
        long_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.long_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        short_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.short_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        self.logger.info("\nTop 5 Features for Long Strategy:")
        for _, row in long_importance.head().iterrows():
            self.logger.info(f"  {row['feature']}: {row['importance']:.4f}")
        
        self.logger.info("\nTop 5 Features for Short Strategy:")
        for _, row in short_importance.head().iterrows():
            self.logger.info(f"  {row['feature']}: {row['importance']:.4f}")
    
    def predict_optimal_strategy(self, current_breadth: Dict) -> Dict:
        """Predict optimal strategy based on current market breadth"""
        # Create feature vector
        features = pd.DataFrame([{
            'sma20_percent': current_breadth.get('sma20_percent', 50),
            'sma50_percent': current_breadth.get('sma50_percent', 50),
            'sma20_50_ratio': current_breadth.get('sma20_percent', 50) / (current_breadth.get('sma50_percent', 50) + 1e-6),
            'sma20_50_diff': current_breadth.get('sma20_percent', 50) - current_breadth.get('sma50_percent', 50),
            'sma20_roc_1d': current_breadth.get('sma20_roc_1d', 0),
            'sma20_roc_3d': current_breadth.get('sma20_roc_3d', 0),
            'sma20_roc_5d': current_breadth.get('sma20_roc_5d', 0),
            'sma20_ma3': current_breadth.get('sma20_ma3', 50),
            'sma20_ma5': current_breadth.get('sma20_ma5', 50),
            'sma20_ma10': current_breadth.get('sma20_ma10', 50),
            'sma20_std5': current_breadth.get('sma20_std5', 5),
            'sma20_std10': current_breadth.get('sma20_std10', 5),
            'extreme_low': 1 if current_breadth.get('sma20_percent', 50) < 20 else 0,
            'extreme_high': 1 if current_breadth.get('sma20_percent', 50) > 80 else 0,
            'neutral_zone': 1 if 40 <= current_breadth.get('sma20_percent', 50) <= 60 else 0,
            'uptrend': current_breadth.get('uptrend', 0),
            'downtrend': current_breadth.get('downtrend', 0),
            'days_since_low': current_breadth.get('days_since_low', 10),
            'days_since_high': current_breadth.get('days_since_high', 10)
        }])
        
        # Make predictions
        long_pnl_pred = self.long_model.predict(features)[0] if self.long_model else 0
        short_pnl_pred = self.short_model.predict(features)[0] if self.short_model else 0
        
        # Determine optimal strategy
        recommendations = {
            'timestamp': datetime.now().isoformat(),
            'current_sma20': current_breadth.get('sma20_percent', 50),
            'long_expected_pnl': float(long_pnl_pred),
            'short_expected_pnl': float(short_pnl_pred),
            'recommended_strategy': 'LONG' if long_pnl_pred > short_pnl_pred else 'SHORT',
            'confidence': abs(long_pnl_pred - short_pnl_pred),
            'specific_recommendations': []
        }
        
        # Add specific recommendations
        if long_pnl_pred > 0.5:
            recommendations['specific_recommendations'].append("Strong LONG opportunity detected")
        elif short_pnl_pred > 1.0:
            recommendations['specific_recommendations'].append("Strong SHORT opportunity detected")
        elif long_pnl_pred < -1 and short_pnl_pred < -0.5:
            recommendations['specific_recommendations'].append("AVOID trading - unfavorable conditions")
        
        return recommendations
    
    def save_models(self):
        """Save trained models"""
        if self.long_model:
            joblib.dump(self.long_model, os.path.join(self.model_dir, 'long_model.pkl'))
        if self.short_model:
            joblib.dump(self.short_model, os.path.join(self.model_dir, 'short_model.pkl'))
        
        self.logger.info("Models saved successfully")
    
    def load_models(self):
        """Load existing models if available"""
        try:
            long_model_path = os.path.join(self.model_dir, 'long_model.pkl')
            short_model_path = os.path.join(self.model_dir, 'short_model.pkl')
            
            if os.path.exists(long_model_path):
                self.long_model = joblib.load(long_model_path)
                self.logger.info("Loaded existing long model")
            
            if os.path.exists(short_model_path):
                self.short_model = joblib.load(short_model_path)
                self.logger.info("Loaded existing short model")
                
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
    
    def update_models_with_new_data(self, new_performance_data: Dict):
        """Update models with new performance data (weekly retraining)"""
        # This would be called weekly with actual performance data
        self.performance_history['long'].append(new_performance_data.get('long', {}))
        self.performance_history['short'].append(new_performance_data.get('short', {}))
        
        # Retrain if enough new data
        if len(self.performance_history['long']) >= 5:
            self.logger.info("Retraining models with new performance data...")
            # Retrain logic here
    
    def generate_report(self):
        """Generate comprehensive optimization report"""
        report = {
            'model_version': datetime.now().strftime('%Y%m%d'),
            'training_date': datetime.now().isoformat(),
            'current_recommendations': {},
            'breadth_ranges': {
                'long': {
                    'optimal': "55-70%",
                    'acceptable': "45-55%",
                    'avoid': "Below 45% or Above 70%"
                },
                'short': {
                    'optimal': "35-50%",
                    'acceptable': "25-35%",
                    'avoid': "Below 20% or Above 50%"
                }
            }
        }
        
        # Save report
        report_file = os.path.join(self.model_dir, f'optimization_report_{datetime.now().strftime("%Y%m%d")}.json')
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

def main():
    """Main function to train and save the model"""
    print("Initializing Breadth Optimization ML Model...")
    print("-" * 60)
    
    model = BreadthOptimizationModel()
    
    # Load historical data
    breadth_df = model.load_historical_data()
    
    # Engineer features
    features_df = model.engineer_features(breadth_df)
    
    # Simulate performance (in production, use actual performance data)
    features_df = model.simulate_performance(features_df)
    
    # Train models
    model.train_models(features_df)
    
    # Save models
    model.save_models()
    
    # Generate report
    report = model.generate_report()
    
    print("\nModel training complete!")
    print(f"Models saved to: {model.model_dir}")
    
    # Test prediction
    test_breadth = {
        'sma20_percent': 45,
        'sma50_percent': 60,
        'sma20_roc_1d': -2,
        'sma20_ma5': 48,
        'uptrend': 0,
        'downtrend': 1
    }
    
    prediction = model.predict_optimal_strategy(test_breadth)
    print("\nTest Prediction:")
    print(f"Current SMA20: {test_breadth['sma20_percent']}%")
    print(f"Recommended Strategy: {prediction['recommended_strategy']}")
    print(f"Expected Long PnL: {prediction['long_expected_pnl']:.2f}%")
    print(f"Expected Short PnL: {prediction['short_expected_pnl']:.2f}%")

if __name__ == "__main__":
    main()