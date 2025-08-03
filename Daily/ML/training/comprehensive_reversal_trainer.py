#!/usr/bin/env python3
"""
Comprehensive Reversal Strategy ML Trainer
Combines reversal signals with Zerodha historical data and market breadth
to predict optimal market positioning (LONG/SHORT)
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
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
import time
from typing import Dict, List, Tuple
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Import Zerodha integration
from kiteconnect import KiteConnect

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveReversalTrainer:
    def __init__(self, user_name="Sai"):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.long_results_dir = os.path.join(self.base_dir, 'Daily', 'results')
        self.short_results_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
        self.breadth_data_dir = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 'historical_breadth_data')
        self.models_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'models')
        self.cache_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'data_cache')
        
        # Create directories
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load configuration
        self.user_name = user_name
        self.config = self._load_config()
        
        # Initialize Kite Connect
        self.kite = None
        self.instruments_cache = None
        try:
            self.kite = self._initialize_kite()
            logger.info("Kite Connect initialized successfully")
            # Cache instruments
            self._load_instruments()
        except Exception as e:
            logger.warning(f"Could not initialize Kite Connect: {e}")
    
    def _load_config(self):
        """Load configuration from Daily/config.ini"""
        config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
        
        if not os.path.exists(config_path):
            logger.error(f"config.ini file not found at {config_path}")
            raise FileNotFoundError(f"config.ini file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Check if credentials exist for user
        credential_section = f'API_CREDENTIALS_{self.user_name}'
        if credential_section not in config.sections():
            logger.error(f"No credentials found for user {self.user_name}")
            raise ValueError(f"No credentials found for user {self.user_name}")
        
        return config
    
    def _initialize_kite(self):
        """Initialize Kite Connect with user credentials"""
        credential_section = f'API_CREDENTIALS_{self.user_name}'
        
        api_key = self.config.get(credential_section, 'api_key')
        access_token = self.config.get(credential_section, 'access_token')
        
        if not api_key or not access_token:
            logger.error(f"Missing API credentials for user {self.user_name}")
            raise ValueError(f"API key or access token missing for user {self.user_name}")
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Test connection
        try:
            profile = kite.profile()
            logger.info(f"Connected as: {profile.get('user_name', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Could not verify connection: {e}")
        
        return kite
    
    def _load_instruments(self):
        """Cache instruments for faster lookup"""
        try:
            self.instruments_cache = {}
            instruments = self.kite.instruments('NSE')
            for instrument in instruments:
                self.instruments_cache[instrument['tradingsymbol']] = instrument['instrument_token']
            logger.info(f"Cached {len(self.instruments_cache)} instruments")
        except Exception as e:
            logger.warning(f"Could not cache instruments: {e}")
    
    def load_reversal_signals(self, weeks_back=2):
        """Load reversal signals from past N weeks"""
        cutoff_date = datetime.now() - timedelta(weeks=weeks_back)
        
        all_signals = []
        
        # Load long signals
        long_files = glob.glob(os.path.join(self.long_results_dir, '*Reversal*.xlsx'))
        for file in long_files:
            try:
                # Extract date from filename
                filename = os.path.basename(file)
                date_str = filename.split('_')[-2]
                signal_date = datetime.strptime(date_str, '%Y%m%d')
                
                if signal_date < cutoff_date:
                    continue
                
                # Read signals
                df = pd.read_excel(file)
                if len(df) > 0:
                    df['signal_date'] = signal_date
                    df['signal_type'] = 'LONG'
                    df['signal_file'] = filename
                    all_signals.append(df)
                    
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
                if len(df) > 0:
                    df['signal_date'] = signal_date
                    df['signal_type'] = 'SHORT'
                    df['signal_file'] = filename
                    all_signals.append(df)
                    
            except Exception as e:
                logger.debug(f"Error reading {file}: {e}")
        
        if all_signals:
            combined_df = pd.concat(all_signals, ignore_index=True)
            logger.info(f"Loaded {len(combined_df)} signals from {len(all_signals)} files")
            return combined_df
        else:
            logger.warning("No signals found")
            return pd.DataFrame()
    
    def fetch_signal_performance(self, signals_df, days_forward=5):
        """Fetch actual price performance for each signal using Zerodha API"""
        if self.kite is None or self.instruments_cache is None:
            logger.warning("Kite Connect not available, using simulated performance")
            return self._simulate_performance(signals_df)
        
        performance_data = []
        
        # Group by date to minimize API calls
        for signal_date, group in signals_df.groupby('signal_date'):
            logger.info(f"Fetching performance for {len(group)} signals on {signal_date}")
            
            for _, signal in group.iterrows():
                try:
                    ticker = signal['Ticker']
                    
                    # Get instrument token from cache
                    instrument_token = self.instruments_cache.get(ticker)
                    
                    if not instrument_token:
                        logger.debug(f"Instrument not found for {ticker}")
                        continue
                    
                    # Fetch historical data
                    from_date = signal_date
                    to_date = signal_date + timedelta(days=days_forward + 5)  # Extra days for weekends
                    
                    hist_data = self.kite.historical_data(
                        instrument_token,
                        from_date,
                        to_date,
                        'day'
                    )
                    
                    if hist_data and len(hist_data) > 0:
                        # Calculate performance
                        entry_price = hist_data[0]['close']
                        
                        # Find price after N trading days
                        if len(hist_data) > days_forward:
                            exit_price = hist_data[days_forward]['close']
                            
                            if signal['signal_type'] == 'LONG':
                                returns = ((exit_price - entry_price) / entry_price) * 100
                            else:  # SHORT
                                returns = ((entry_price - exit_price) / entry_price) * 100
                            
                            performance_data.append({
                                'ticker': ticker,
                                'signal_date': signal_date,
                                'signal_type': signal['signal_type'],
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'returns': returns,
                                'days_held': days_forward
                            })
                    
                    # Rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.debug(f"Error fetching data for {ticker}: {e}")
        
        return pd.DataFrame(performance_data)
    
    def _simulate_performance(self, signals_df):
        """Simulate performance when API is not available"""
        performance_data = []
        
        for _, signal in signals_df.iterrows():
            # Simulate based on market conditions
            base_return = np.random.normal(0, 2)  # Mean 0%, Std 2%
            
            # Add bias based on signal type
            if signal['signal_type'] == 'LONG':
                returns = base_return + 0.5
            else:
                returns = base_return - 0.3
            
            performance_data.append({
                'ticker': signal['Ticker'],
                'signal_date': signal['signal_date'],
                'signal_type': signal['signal_type'],
                'returns': returns,
                'days_held': 5
            })
        
        return pd.DataFrame(performance_data)
    
    def load_breadth_data(self):
        """Load market breadth data"""
        breadth_file = os.path.join(self.breadth_data_dir, 'sma_breadth_historical_latest.json')
        
        with open(breadth_file, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
        df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
        
        # Calculate additional features
        df['sma20_roc_1d'] = df['sma20_percent'].diff(1)
        df['sma20_roc_5d'] = df['sma20_percent'].diff(5)
        df['sma20_ma5'] = df['sma20_percent'].rolling(5).mean()
        df['sma20_ma10'] = df['sma20_percent'].rolling(10).mean()
        df['breadth_momentum'] = df['sma20_percent'] - df['sma20_ma5']
        
        return df
    
    def create_training_dataset(self, signals_df, performance_df, breadth_df):
        """Create comprehensive training dataset"""
        # Aggregate daily performance by signal type
        daily_performance = performance_df.groupby(['signal_date', 'signal_type']).agg({
            'returns': ['mean', 'std', 'count', lambda x: (x > 0).sum() / len(x)]
        }).reset_index()
        
        daily_performance.columns = ['signal_date', 'signal_type', 'avg_returns', 
                                    'std_returns', 'signal_count', 'win_rate']
        
        # Pivot to have long and short metrics side by side
        long_perf = daily_performance[daily_performance['signal_type'] == 'LONG'].copy()
        long_perf.columns = ['signal_date', 'signal_type', 'long_avg_returns', 
                            'long_std_returns', 'long_signal_count', 'long_win_rate']
        
        short_perf = daily_performance[daily_performance['signal_type'] == 'SHORT'].copy()
        short_perf.columns = ['signal_date', 'signal_type', 'short_avg_returns', 
                             'short_std_returns', 'short_signal_count', 'short_win_rate']
        
        # Merge with breadth data
        breadth_df['date'] = pd.to_datetime(breadth_df['date'])
        long_perf['signal_date'] = pd.to_datetime(long_perf['signal_date'])
        short_perf['signal_date'] = pd.to_datetime(short_perf['signal_date'])
        
        # Create daily dataset
        daily_data = breadth_df.copy()
        daily_data = pd.merge(daily_data, long_perf[['signal_date', 'long_avg_returns', 
                                                     'long_win_rate', 'long_signal_count']], 
                             left_on='date', right_on='signal_date', how='left')
        daily_data = pd.merge(daily_data, short_perf[['signal_date', 'short_avg_returns', 
                                                      'short_win_rate', 'short_signal_count']], 
                             left_on='date', right_on='signal_date_y', how='left')
        
        # Fill missing values
        daily_data.fillna({
            'long_avg_returns': 0,
            'short_avg_returns': 0,
            'long_win_rate': 0.5,
            'short_win_rate': 0.5,
            'long_signal_count': 0,
            'short_signal_count': 0
        }, inplace=True)
        
        # Create target variable: which strategy performed better
        daily_data['best_strategy'] = 'NEUTRAL'
        daily_data.loc[daily_data['long_avg_returns'] > daily_data['short_avg_returns'] + 0.5, 
                      'best_strategy'] = 'LONG'
        daily_data.loc[daily_data['short_avg_returns'] > daily_data['long_avg_returns'] + 0.5, 
                      'best_strategy'] = 'SHORT'
        
        # Add additional features
        daily_data['breadth_regime'] = pd.cut(daily_data['sma20_percent'], 
                                              bins=[0, 30, 50, 70, 100], 
                                              labels=['OVERSOLD', 'BEARISH', 'BULLISH', 'OVERBOUGHT'])
        
        daily_data['signal_strength_diff'] = daily_data['long_signal_count'] - daily_data['short_signal_count']
        daily_data['performance_spread'] = daily_data['long_avg_returns'] - daily_data['short_avg_returns']
        
        return daily_data
    
    def train_prediction_model(self, training_data):
        """Train the ML model to predict best strategy"""
        # Prepare features
        feature_columns = [
            'sma20_percent', 'sma50_percent', 'sma20_roc_1d', 'sma20_roc_5d',
            'sma20_ma5', 'sma20_ma10', 'breadth_momentum',
            'long_signal_count', 'short_signal_count', 'signal_strength_diff',
            'long_win_rate', 'short_win_rate'
        ]
        
        # Filter valid data
        valid_data = training_data.dropna(subset=feature_columns + ['best_strategy'])
        
        X = valid_data[feature_columns]
        y = valid_data['best_strategy']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train multiple models
        models = {
            'RandomForest': RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
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
            'model_type': type(best_model).__name__
        }
    
    def save_model_and_metadata(self, model, metadata):
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
    
    def run_complete_training(self):
        """Run the complete training pipeline"""
        logger.info("="*60)
        logger.info("Starting Comprehensive Reversal Strategy Training")
        logger.info("="*60)
        
        # Step 1: Load reversal signals
        logger.info("\nStep 1: Loading reversal signals...")
        signals_df = self.load_reversal_signals(weeks_back=6)
        
        if signals_df.empty:
            logger.error("No signals found. Exiting.")
            return
        
        # Step 2: Fetch performance data
        logger.info("\nStep 2: Fetching signal performance data...")
        
        # Check cache first
        cache_file = os.path.join(self.cache_dir, 'signal_performance_cache.pkl')
        if os.path.exists(cache_file):
            logger.info("Loading performance data from cache...")
            performance_df = pd.read_pickle(cache_file)
        else:
            performance_df = self.fetch_signal_performance(signals_df, days_forward=5)
            # Save to cache
            performance_df.to_pickle(cache_file)
        
        logger.info(f"Performance data shape: {performance_df.shape}")
        
        # Step 3: Load breadth data
        logger.info("\nStep 3: Loading market breadth data...")
        breadth_df = self.load_breadth_data()
        logger.info(f"Breadth data shape: {breadth_df.shape}")
        
        # Step 4: Create training dataset
        logger.info("\nStep 4: Creating training dataset...")
        training_data = self.create_training_dataset(signals_df, performance_df, breadth_df)
        logger.info(f"Training data shape: {training_data.shape}")
        
        # Save training data for analysis
        training_data.to_csv(os.path.join(self.cache_dir, 'training_data.csv'), index=False)
        
        # Step 5: Train model
        logger.info("\nStep 5: Training prediction model...")
        model, metadata = self.train_prediction_model(training_data)
        
        # Step 6: Save model
        logger.info("\nStep 6: Saving model...")
        model_path = self.save_model_and_metadata(model, metadata)
        
        logger.info("\n" + "="*60)
        logger.info("Training Complete!")
        logger.info(f"Model saved to: {model_path}")
        logger.info(f"Test Accuracy: {metadata['test_accuracy']:.4f}")
        logger.info("="*60)
        
        return model, metadata

def main():
    """Main training function"""
    trainer = ComprehensiveReversalTrainer()
    model, metadata = trainer.run_complete_training()

if __name__ == "__main__":
    main()